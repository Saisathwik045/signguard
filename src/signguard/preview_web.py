"""Single-owner private-preview gateway: protects HTTP media/uploads and WebSockets, not just widgets."""
import asyncio
import contextlib
import os
import secrets
import subprocess
import sys
import time

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route, WebSocketRoute
from websockets.asyncio.client import connect

from .preview_auth import verify

SESSIONS = {}
COOKIE = "signguard_preview"
UPSTREAM = "http://127.0.0.1:"+os.environ.get("SIGNGUARD_STREAMLIT_PORT", "8502")
FORM = '''<!doctype html><html><head><title>SignGuard private preview</title></head>
<body><h1>SignGuard</h1><p>Private preview: sign in before uploading a document.</p>
<form method="post" action="/auth/login"><label for="password">Preview password</label>
<input id="password" name="password" type="password" maxlength="256" required autocomplete="current-password">
<button type="submit">Sign in</button></form>{error}</body></html>'''


def valid(cookies):
    session = cookies.get(COOKIE)
    expires = SESSIONS.get(session, 0)
    if expires <= time.monotonic():
        SESSIONS.pop(session, None)
        return False
    return True


async def login(request):
    if request.method == "GET":
        return HTMLResponse(FORM.replace("{error}", ""))
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 2048:
            return Response(status_code=413)
    from urllib.parse import parse_qs
    password = parse_qs(body.decode(errors="replace")).get("password", [""])[0]
    if not verify(password, os.environ.get("SIGNGUARD_PREVIEW_PASSWORD_HASH", "")):
        return HTMLResponse(FORM.replace("{error}", "<p>Access denied.</p>"), status_code=403)
    for key, expiry in list(SESSIONS.items()):
        if expiry <= time.monotonic():
            SESSIONS.pop(key, None)
    if len(SESSIONS) >= 100:
        return Response(status_code=429)
    session = secrets.token_urlsafe(32)
    SESSIONS[session] = time.monotonic()+900
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(COOKIE, session, httponly=True, samesite="strict", max_age=900,
                        secure=os.environ.get("SIGNGUARD_COOKIE_SECURE", "true") == "true")
    return response


async def logout(request):
    SESSIONS.pop(request.cookies.get(COOKIE), None)
    response = RedirectResponse("/auth/login", status_code=303)
    response.delete_cookie(COOKIE)
    return response


def upstream_headers(headers):
    excluded = {"host", "connection", "upgrade", "content-length", "transfer-encoding",
                "sec-websocket-key", "sec-websocket-version", "sec-websocket-extensions", "sec-websocket-protocol",
                "x-signguard-gateway"}
    result = {key: value for key, value in headers.items() if key.lower() not in excluded}
    result["X-SignGuard-Gateway"] = os.environ["SIGNGUARD_GATEWAY_TOKEN"]
    return result


async def proxy(request: Request):
    if request.url.path == "/_stcore/health":
        try:
            async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
                ready = await client.get(UPSTREAM+"/_stcore/health", headers=upstream_headers(request.headers))
            response = Response("ok", status_code=ready.status_code)
            for cookie in ready.headers.get_list("set-cookie"):
                response.raw_headers.append((b"set-cookie", cookie.encode("latin-1")))
            response.headers["Cache-Control"] = "no-store"
            return response
        except httpx.HTTPError:
            return Response("starting", status_code=503)
    if not valid(request.cookies):
        if request.url.path == "/":
            return RedirectResponse("/auth/login", status_code=303)
        return Response("Authentication required", status_code=403)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 30*1024*1024:
            return Response(status_code=413)
    target = UPSTREAM+request.url.path+("?"+request.url.query if request.url.query else "")
    async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
        upstream = await client.request(request.method, target, content=bytes(body), headers=upstream_headers(request.headers))
        headers = {key: value for key, value in upstream.headers.items()
                   if key not in {"content-length", "content-encoding", "transfer-encoding", "connection", "set-cookie"}}
        response = Response(upstream.content, status_code=upstream.status_code, headers=headers)
        for value in upstream.headers.get_list("set-cookie"):
            response.raw_headers.append((b"set-cookie", value.encode("latin-1")))
        return response


async def websocket_proxy(websocket):
    if not valid(websocket.cookies):
        await websocket.close(code=1008)
        return
    target = UPSTREAM.replace("http://", "ws://")+websocket.url.path+("?"+websocket.url.query if websocket.url.query else "")
    try:
        async with connect(target, additional_headers=upstream_headers(websocket.headers),
                           subprotocols=websocket.scope.get("subprotocols", []), max_size=50*1024*1024,
                           proxy=None) as upstream:
            cookies = [(b"set-cookie", value.encode("latin-1"))
                       for value in upstream.response.headers.get_all("Set-Cookie")]
            await websocket.accept(subprotocol=upstream.subprotocol, headers=cookies)

            async def outgoing():
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    await upstream.send(message.get("bytes") if message.get("bytes") is not None else message.get("text"))

            async def incoming():
                async for message in upstream:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            async def expiry():
                while valid(websocket.cookies):
                    await asyncio.sleep(1)

            tasks = [asyncio.create_task(function()) for function in (outgoing, incoming, expiry)]
            _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        with contextlib.suppress(RuntimeError):
            await websocket.close()


app = Starlette(routes=[Route("/auth/login", login, methods=["GET", "POST"]), Route("/auth/logout", logout),
                        WebSocketRoute("/{path:path}", websocket_proxy),
                        Route("/{path:path}", proxy, methods=["GET", "POST", "PUT", "DELETE", "HEAD"])])


def main():
    if (os.environ.get("SIGNGUARD_BACKEND") != "broker" or
            os.environ.get("SIGNGUARD_PREVIEW_PRIVATE_CONFIRMED") != "true" or
            len(os.environ.get("SIGNGUARD_GATEWAY_TOKEN", "")) < 32):
        raise SystemExit("Private gateway requires isolated backend, confirmed private configuration and gateway secret")
    child = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.address=127.0.0.1",
                              "--server.port="+os.environ.get("SIGNGUARD_STREAMLIT_PORT", "8502"), "--server.headless=true",
                              "--server.maxUploadSize=25", "--server.maxMessageSize=50",
                              "--server.enableXsrfProtection=true", "--server.xsrfCookieSameSite=lax",
                              "--browser.gatherUsageStats=false"])
    try:
        uvicorn.run(app, host=os.environ.get("SIGNGUARD_WEB_HOST", "127.0.0.1"),
                    port=int(os.environ.get("SIGNGUARD_WEB_PORT", "8501")), access_log=False)
    finally:
        child.terminate()
        child.wait(timeout=10)


if __name__ == "__main__":
    main()
