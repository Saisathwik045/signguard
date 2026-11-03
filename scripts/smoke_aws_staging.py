"""Actual-origin anonymous maintenance checks; never treats these as successful owner login."""
import argparse
import http.client
import ipaddress
import json
import ssl
from pathlib import Path
from urllib.parse import urlsplit


def address(origin):
    parsed=urlsplit(origin)
    if parsed.scheme!='https' or parsed.netloc!=parsed.hostname or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('Exact HTTPS IPv4 origin required')
    ip=ipaddress.ip_address(parsed.hostname)
    if ip.version!=4 or not ip.is_global:raise ValueError('Global IPv4 required')
    return str(ip)


def check(origin):
    host=address(origin)
    context=ssl.create_default_context()  # System trust and hostname/IP verification; no bypass.
    observations=[]
    for path,status in [('/',303),('/media/report.json',403),('/_stcore/health',403),('/auth/callback?state=forged&code=fake',403)]:
        connection=http.client.HTTPSConnection(host,context=context,timeout=10)
        try:
            connection.request('GET',path,headers={'X-SignGuard-Gateway':'forged','X-Forwarded-User':'220234042'})
            response=connection.getresponse();response.read(4096)
            if response.status!=status or response.getheader('Cache-Control')!='no-store':
                raise ValueError('Hosted authentication boundary failed')
            if path=='/' and response.getheader('Location')!='/auth/login':
                raise ValueError('Unexpected login redirect')
            observations.append({'path':path,'status':response.status})
        finally:connection.close()
    return {'origin':origin,'trusted_tls_anonymous_smoke':True,'observations':observations,
            'real_owner_login_verified':False,'live_uploads_verified':False,'production_ready':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('delivery',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();release=json.loads(args.delivery.read_text())['release']
    args.output.write_text(json.dumps(check('https://'+release['public_ipv4']),indent=2)+'\n')
