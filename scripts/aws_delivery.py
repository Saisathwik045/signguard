"""Protected GitHub job driver: publish reviewed image digests and stage via SSM, never enable uploads."""
import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path


def raise_if_zero_budget():
    policy=json.loads((Path(__file__).resolve().parents[1]/'deploy/free/policy.json').read_text())
    if policy['maximum_spend_inr']==0 or not policy['paid_provisioning_allowed']:
        raise PermissionError('Phase 10 strict zero budget prohibits AWS publication and deployment')


def run(arguments, *, data=None):
    return subprocess.check_output(arguments, input=data)


def aws(*args):
    return json.loads(run(['aws',*args,'--region','us-east-1','--output','json']))


def validate_outputs(outputs):
    instance = outputs['instance_id']['value']
    volume = outputs['audit_volume_id']['value']
    origin = outputs['prospective_https_origin']['value']
    if not re.fullmatch(r'i-[0-9a-f]{8,32}',instance) or not re.fullmatch(r'vol-[0-9a-f]{8,32}',volume):
        raise ValueError('Invalid reviewed infrastructure outputs')
    return instance,volume,origin


def publish(outputs, destination):
    raise_if_zero_budget()
    account=aws('sts','get-caller-identity')['Account']
    if account!=os.environ['AWS_ACCOUNT_ID'] or not re.fullmatch(r'[0-9]{12}',account):
        raise ValueError('Wrong AWS account')
    commit=os.environ['GITHUB_SHA']
    run_id=os.environ['GITHUB_RUN_ID']
    attempt=os.environ['GITHUB_RUN_ATTEMPT']
    if not re.fullmatch(r'[0-9a-f]{40}',commit) or not run_id.isdigit() or not attempt.isdigit():
        raise ValueError('Untrusted release identity')
    instance,volume,origin=validate_outputs(outputs)
    tag=f'{commit}-{run_id}-{attempt}'
    registry=account+'.dkr.ecr.us-east-1.amazonaws.com'
    # CI ephemeral Docker config must be removed by the workflow after completion.
    password=run(['aws','ecr','get-login-password','--region','us-east-1'])
    subprocess.run(['docker','login','--username','AWS','--password-stdin',registry],input=password,check=True,stdout=subprocess.DEVNULL)
    images={}
    for role in ('worker','ui','controller'):
        local='signguard-'+role+':aws'
        image=registry+'/signguard-staging-'+role+':'+tag
        subprocess.run(['docker','tag',local,image],check=True)
        subprocess.run(['docker','push',image],check=True)
        details=aws('ecr','describe-images','--repository-name','signguard-staging-'+role,'--image-ids','imageTag='+tag)
        digest=details['imageDetails'][0]['imageDigest']
        if not re.fullmatch(r'sha256:[0-9a-f]{64}',digest):raise ValueError('Unpinned registry response')
        images[role]=image.rsplit(':',1)[0]+'@'+digest
    release={'account_id':account,'region':'us-east-1','public_ipv4':origin.removeprefix('https://'),
             'commit':commit,'images':images}
    bundle=destination/'source.tar.gz'
    bundle.write_bytes(run(['git','archive','--format=tar.gz',commit]))
    bucket='signguard-staging-state-'+account
    source_key='releases/'+tag+'/source.tar.gz'
    subprocess.run(['aws','s3','cp',str(bundle),'s3://'+bucket+'/'+source_key,'--sse','AES256','--only-show-errors'],check=True)
    delivery={'release':release,'instance_id':instance,'volume_id':volume,'source_key':source_key,
              'source_sha256':hashlib.sha256(bundle.read_bytes()).hexdigest(),'state_bucket':bucket,'id':tag}
    path=destination/'delivery.json';path.write_text(json.dumps(delivery,indent=2)+'\n')
    subprocess.run(['aws','s3','cp',str(path),'s3://'+bucket+'/releases/'+tag+'/delivery.json','--sse','AES256','--only-show-errors'],check=True)
    return delivery


def commands(delivery, tls_email=None):
    # Strict fixed grammar before producing any host shell text. Values never contain secrets.
    release=delivery['release']
    import tempfile

    from scripts.render_aws_staging import render
    with tempfile.TemporaryDirectory() as directory:render(release,Path(directory))
    instance,volume,_=validate_outputs({key:{'value':delivery[value]} for key,value in
        [('instance_id','instance_id'),('audit_volume_id','volume_id')]} | {'prospective_https_origin':{'value':'https://'+release['public_ipv4']}})
    if (delivery['state_bucket']!='signguard-staging-state-'+release['account_id']
            or not re.fullmatch(r'[0-9a-f]{40}-[0-9]+-[0-9]+',delivery['id'])
            or delivery['source_key']!='releases/'+delivery['id']+'/source.tar.gz'
            or not re.fullmatch(r'[0-9a-f]{64}',delivery['source_sha256'])):
        raise ValueError('Invalid delivery manifest')
    root='/opt/signguard/releases/'+delivery['id']
    encoded=base64.b64encode(json.dumps(release).encode()).decode()
    script=['set -euo pipefail',f'install -d -m 0755 {root}',
            'aws s3 cp '+shlex.quote('s3://'+delivery['state_bucket']+'/'+delivery['source_key'])+' /var/tmp/signguard-source.tar.gz --only-show-errors',
            "printf '%s  %s\\n' "+delivery['source_sha256']+" /var/tmp/signguard-source.tar.gz | sha256sum -c -",
            'tar -xzf /var/tmp/signguard-source.tar.gz -C '+root,
            "printf '%s' '"+encoded+"' | base64 -d > "+root+'/release.json',
            'bash '+root+'/deploy/aws/host/mount-audit.sh '+volume,
            'bash '+root+'/deploy/aws/host/stage-release.sh '+root+' signguard/staging/runtime',
            'rm -f /var/tmp/signguard-source.tar.gz']
    if tls_email:
        if not re.fullmatch(r'[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+',tls_email):
            raise ValueError('Invalid certificate contact')
        script.insert(-2, 'if ! test -f /etc/letsencrypt/live/signguard/fullchain.pem; then bash '+root+
                      '/deploy/aws/host/issue-tls.sh '+release['public_ipv4']+' '+shlex.quote(tls_email)+'; fi')
    return instance,"bash <<'SIGNGUARD_APPROVED_RELEASE'\n"+'\n'.join(script)+"\nSIGNGUARD_APPROVED_RELEASE"


def stage(delivery):
    raise_if_zero_budget()
    instance,script=commands(delivery,os.environ.get("SIGNGUARD_TLS_CONTACT_EMAIL"))
    info=aws('ec2','describe-instances','--instance-ids',instance)['Reservations'][0]['Instances'][0]
    if {t['Key']:t['Value'] for t in info['Tags']}.get('ManagedBy')!='signguard-deployment':
        raise ValueError('Refusing an unmanaged host')
    response=aws('ssm','send-command','--document-name','AWS-RunShellScript','--instance-ids',instance,
                 '--parameters',json.dumps({'commands':[script]}),'--timeout-seconds','900')
    identifier=response['Command']['CommandId']
    for _ in range(120):
        try:result=aws('ssm','get-command-invocation','--command-id',identifier,'--instance-id',instance)
        except subprocess.CalledProcessError:
            time.sleep(5);continue
        status=result['Status']
        if status=='Success':return {'staged_maintenance':True,'uploads_enabled':False,'command_id':identifier,'hosted_browser_verified':False}
        if status not in {'Pending','InProgress','Delayed'}:raise RuntimeError('SSM staging failed; inspect redacted host operations logs')
        time.sleep(5)
    raise TimeoutError('Staging deadline exceeded')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('outputs',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--stage',action='store_true')
    args=parser.parse_args();args.destination.mkdir(parents=True,exist_ok=True)
    delivery=publish(json.loads(args.outputs.read_text()),args.destination)
    if args.stage:(args.destination/'stage-result.json').write_text(json.dumps(stage(delivery),indent=2)+'\n')
