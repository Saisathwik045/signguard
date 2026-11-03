"""Real HTTPS on a disposable cloud container; private test CA, not public-host verification."""
import http.client
import json
import os
import socket
import ssl
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

pytestmark=pytest.mark.skipif(os.environ.get('SIGNGUARD_TLS_GATEWAY_TESTS')!='1',reason='Explicit cloud TLS/container job required')


def test_real_tls_gateway_denies_anonymous_and_spoofed_identity(tmp_path):
    docker=['docker','--host=unix:///var/run/docker.sock']
    name='signguard-tls-probe-'+str(os.getpid())
    artifacts=Path(os.environ.get('SIGNGUARD_BROWSER_ARTIFACTS','browser-artifacts'))
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);tls=root/'tls';auth=root/'auth';tls.mkdir();auth.mkdir()
        def openssl(*args):subprocess.run(['openssl',*args],check=True,capture_output=True)
        openssl('req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root/'ca.key'),'-out',str(root/'ca.pem'),
                '-days','1','-subj','/CN=SignGuard ephemeral cloud test CA')
        openssl('req','-newkey','rsa:2048','-nodes','-keyout',str(tls/'privkey.pem'),'-out',str(root/'server.csr'),
                '-subj','/CN=127.0.0.1')
        (root/'extensions').write_text('subjectAltName=IP:127.0.0.1\nextendedKeyUsage=serverAuth\n')
        openssl('x509','-req','-in',str(root/'server.csr'),'-CA',str(root/'ca.pem'),'-CAkey',str(root/'ca.key'),
                '-CAcreateserial','-out',str(tls/'fullchain.pem'),'-days','1','-extfile',str(root/'extensions'))
        # Bind mounts deliberately grant only the actual container UID access to test material.
        for p in [tls,auth,*tls.iterdir()]:
            subprocess.run(['sudo','chown','65532:65532',str(p)],check=True)
        tls.chmod(0o750);auth.chmod(0o700)
        for p in tls.iterdir():p.chmod(0o640)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        command=[*docker,'run','-d','--name',name,'--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
            '--memory=1g','--pids-limit=64','--tmpfs=/tmp:rw,noexec,nosuid,size=64m',
            '--publish',f'127.0.0.1:{port}:8501','--mount',f'type=bind,src={tls},dst=/etc/signguard/tls,readonly',
            '--mount',f'type=bind,src={auth},dst=/var/lib/signguard/auth',
            '--env=SIGNGUARD_PUBLIC_ORIGIN=https://8.8.8.8','--env=SIGNGUARD_REQUIRE_AUTH=true',
            '--env=SIGNGUARD_BACKEND=broker','--env=SIGNGUARD_GITHUB_OWNER_ID=12345',
            '--env=SIGNGUARD_SESSION_DATABASE=/var/lib/signguard/auth/session.sqlite3',
            '--env=SIGNGUARD_GATEWAY_TOKEN=synthetic-cloud-only-not-a-real-secret-12345',
            '--env=SIGNGUARD_GITHUB_CLIENT_ID=synthetic-client','--env=SIGNGUARD_GITHUB_CLIENT_SECRET=synthetic-secret',
            '--env=SIGNGUARD_LIVE_UPLOADS_ENABLED=false','--entrypoint=python','signguard-ui:phase4','-m','signguard.production_web']
        context=ssl.create_default_context(cafile=str(root/'ca.pem'))
        assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED
        try:
            subprocess.run(command,check=True,capture_output=True)
            for _ in range(60):
                try:
                    connection=http.client.HTTPSConnection('127.0.0.1',port,context=context,timeout=2)
                    connection.connect();protocol=connection.sock.version();connection.close();break
                except (OSError,ssl.SSLError):time.sleep(.5)
            else:raise AssertionError('TLS gateway did not start')
            assert protocol in {'TLSv1.2','TLSv1.3'}
            observations=[]
            for method,path in [('GET','/'),('GET','/media/report.json'),('GET','/_stcore/health'),
                                ('POST','/_stcore/upload_file/session/id'),('GET','/auth/callback?code=fake&state=forged')]:
                connection=http.client.HTTPSConnection('127.0.0.1',port,context=context,timeout=5)
                connection.request(method,path,body=b'not-a-document' if method=='POST' else None,
                                   headers={'X-SignGuard-Gateway':'spoofed','X-Forwarded-User':'12345'})
                response=connection.getresponse();response.read()
                assert response.status in {303,403}
                assert response.getheader('Cache-Control')=='no-store'
                observations.append({'method':method,'path':path,'status':response.status})
                connection.close()
            (artifacts/'tls-gateway.json').write_text(json.dumps({'scope':'cloud_loopback_with_ephemeral_test_CA',
                'tls_protocol':protocol,'certificate_validation_enabled':True,'anonymous_denials':observations,
                'real_github_login_verified':False,'public_aws_tls_verified':False,'uploads_enabled':False},indent=2)+'\n')
        finally:
            with (artifacts/'tls-gateway.log').open('w') as log:
                subprocess.run([*docker,'logs',name],stdout=log,stderr=log,check=False)
            subprocess.run([*docker,'rm','-f',name],capture_output=True,check=False)
            # Clean root-owned mounted SQLite test data only after the test container is removed.
            subprocess.run(['sudo','chown','-R',str(os.getuid())+':'+str(os.getgid()),str(root)],check=True)
