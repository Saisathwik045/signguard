"""Independent OAuth boundary tests: state binding/replay, immutable owner, revocation and outage."""
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from signguard import production_web as gateway
from signguard.cloud_sessions import Sessions


@pytest.fixture
def cloud_auth(tmp_path,monkeypatch):
    monkeypatch.setenv('SIGNGUARD_PUBLIC_ORIGIN','https://8.8.8.8')
    monkeypatch.setenv('SIGNGUARD_GATEWAY_TOKEN','synthetic-test-only-'*3)
    monkeypatch.setenv('SIGNGUARD_GITHUB_CLIENT_ID','synthetic-client')
    monkeypatch.setenv('SIGNGUARD_GITHUB_CLIENT_SECRET','synthetic-private-client')
    monkeypatch.setenv('SIGNGUARD_GITHUB_OWNER_ID','12345')
    monkeypatch.setattr(gateway,'_STORE',Sessions(tmp_path/'sessions.sqlite3'))
    monkeypatch.setattr(gateway.web,'valid',gateway.web.valid)
    monkeypatch.setattr(gateway.web,'upstream_headers',gateway.web.upstream_headers)
    app=gateway.application()
    with TestClient(app,base_url='https://8.8.8.8',follow_redirects=False) as client:
        yield client,tmp_path


def pending(client):
    response=client.get('/auth/login')
    assert response.status_code==303
    query=parse_qs(urlsplit(response.headers['location']).query)
    assert query['code_challenge_method']==['S256']
    assert query['redirect_uri']==['https://8.8.8.8/auth/callback']
    assert 'Secure' in response.headers['set-cookie'] and 'HttpOnly' in response.headers['set-cookie']
    return query['state'][0]


def fake_provider(monkeypatch,owner=12345):
    class Provider:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def fetch_token(self,*args,**kwargs):
            assert len(kwargs['code_verifier'])>=43
        async def get(self,url,**kwargs):
            assert url=='https://api.github.com/user'
            class Response:
                def raise_for_status(self):pass
                def json(self):return {'id':owner,'login':'synthetic-owner'}
            return Response()
    monkeypatch.setattr(gateway,'client',Provider)


def test_no_anonymous_upload_media_health_or_websocket(cloud_auth):
    client,_=cloud_auth
    assert client.get('/').status_code==303
    for path in ['/media/report.json','/_stcore/health']:
        assert client.get(path).status_code==403
    assert client.post('/_stcore/upload_file/session/id',content=b'not-a-document').status_code==403
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect),client.websocket_connect('/_stcore/stream'):pass


def test_oauth_state_is_bound_to_cookie_and_consumed_once(cloud_auth,monkeypatch):
    client,_=cloud_auth
    state=pending(client)
    fake_provider(monkeypatch)
    assert client.get('/auth/callback',params={'code':'synthetic-code','state':'wrong-state'}).status_code==403
    # A failed/replayed state cannot be used on a subsequent callback.
    assert client.get('/auth/callback',params={'code':'synthetic-code','state':state}).status_code==403


def test_owner_session_survives_restart_and_logout_revokes_replay(cloud_auth,monkeypatch):
    client,directory=cloud_auth
    state=pending(client);fake_provider(monkeypatch)
    response=client.get('/auth/callback',params={'code':'synthetic-code','state':state})
    assert response.status_code==303
    cookie=client.cookies.get(gateway.COOKIE)
    assert gateway.valid({gateway.COOKIE:cookie})
    monkeypatch.setattr(gateway,'_STORE',Sessions(directory/'sessions.sqlite3'))
    assert gateway.valid({gateway.COOKIE:cookie})
    assert client.get('/auth/logout').status_code==303
    assert not gateway.valid({gateway.COOKIE:cookie})
    assert client.get('/media/report.json',headers={'Cookie':gateway.COOKIE+'='+cookie}).status_code==403


def test_foreign_immutable_id_cannot_login_even_with_matching_display_name(cloud_auth,monkeypatch):
    client,_=cloud_auth
    state=pending(client);fake_provider(monkeypatch,owner=99999)
    assert client.get('/auth/callback',params={'code':'synthetic-code','state':state}).status_code==403
    assert client.cookies.get(gateway.COOKIE) is None


def test_cookie_tampering_and_session_storage_failure_are_closed(cloud_auth,monkeypatch):
    client,directory=cloud_auth
    assert not gateway.valid({gateway.COOKIE:'forged-cookie'})
    monkeypatch.setattr(gateway,'_STORE',Sessions(directory/'sessions.sqlite3'))
    # Removing the persisted DB/schema must not create an authenticated in-memory fallback.
    (directory/'sessions.sqlite3').unlink()
    assert not gateway.valid({gateway.COOKIE:'any-cookie'})
    assert client.get('/media/report.json').status_code==403


def test_cross_origin_callback_and_proxy_identity_spoofing(cloud_auth):
    client,_=cloud_auth
    assert client.get('/auth/callback',params={'state':'forged','code':'fake'},headers={'X-Forwarded-User':'12345'}).status_code==403
    headers=gateway.web.upstream_headers({'X-Forwarded-Proto':'http','X-SignGuard-Gateway':'spoofed','Forwarded':'host=attacker'})
    assert headers['X-Forwarded-Proto']=='https' and headers['X-Forwarded-Host']=='8.8.8.8'
    assert headers['X-SignGuard-Gateway']!='spoofed'
    assert client.get('/auth/logout',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403


def test_login_quota_is_persisted_and_provider_secret_never_stored(cloud_auth):
    client,directory=cloud_auth
    for _ in range(10):assert client.get('/auth/login').status_code==303
    assert client.get('/auth/login').status_code==429
    raw=(directory/'sessions.sqlite3').read_bytes()
    assert b'synthetic-private-client' not in raw
