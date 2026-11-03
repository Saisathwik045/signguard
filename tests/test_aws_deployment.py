"""Infrastructure safety contracts independent of paid provider credentials."""
import concurrent.futures
import json
from pathlib import Path

import pytest
import yaml

from scripts.render_aws_staging import render
from scripts.write_aws_runtime_secrets import write
from signguard.container_runner import docker_prefix
from signguard.persistent_quota import allowed


def release():
    return {'account_id':'123456789012','region':'us-east-1','public_ipv4':'8.8.8.8','commit':'a'*40,
            'images':{key:f'123456789012.dkr.ecr.us-east-1.amazonaws.com/signguard-staging-{key}@sha256:'+('b'*64)
                      for key in ('worker','ui','controller')}}


def test_generated_maintenance_has_no_daemon_access_or_uploads(tmp_path):
    render(release(),tmp_path)
    services=yaml.safe_load((tmp_path/'compose.yaml').read_text())['services']
    assert services['ui']['environment']['SIGNGUARD_LIVE_UPLOADS_ENABLED']=='false'
    assert 'ports' not in services['controller']
    assert all('/var/run/docker.sock' not in str(value) and '/run/user/1001' not in str(value)
               for value in services.values())
    assert services['ui']['ports']==['443:8501']
    assert services['ui']['networks']==['control','identity']
    assert services['controller']['environment']['SIGNGUARD_QUOTA_DATABASE'].endswith('.sqlite3')
    assert 'cookie' not in (tmp_path/'release.json').read_text().lower()
    assert services['ui']['entrypoint']==['python','-m','signguard.production_web']
    assert set(services)=={'ui','controller'}


@pytest.mark.parametrize('field,value',[('public_ipv4','127.0.0.1'),('public_ipv4','https://attacker.test'),
    ('commit','main'),('region','unreviewed-region'),('account_id','wrong')])
def test_release_rejects_unreviewed_identity(tmp_path,field,value):
    data=release();data[field]=value
    with pytest.raises(ValueError):render(data,tmp_path)


def test_release_refuses_tags_or_foreign_registry(tmp_path):
    data=release();data['images']['worker']='attacker/worker:latest'
    with pytest.raises(ValueError):render(data,tmp_path)


@pytest.mark.parametrize('address',['tcp://daemon:2375','unix:///tmp/../docker.sock','file:///run/docker.sock'])
def test_executor_refuses_remote_or_ambiguous_docker(monkeypatch,address):
    monkeypatch.setenv('SIGNGUARD_DOCKER_SOCKET',address)
    with pytest.raises(ValueError):docker_prefix()


def test_executor_uses_explicit_rootless_socket(monkeypatch):
    monkeypatch.setenv('SIGNGUARD_DOCKER_SOCKET','unix:///run/user/1001/docker.sock')
    assert docker_prefix()[1]=='--host=unix:///run/user/1001/docker.sock'


def test_persistent_quota_survives_connections_and_concurrent_attempts(tmp_path):
    path=str(tmp_path/'quota.sqlite3')
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results=list(executor.map(lambda _:allowed(path,'stable-owner',3,60),range(8)))
    assert sum(results)==3
    assert not allowed(path,'stable-owner',3,60)
    assert allowed(path,'second-owner',3,60)


def test_quota_storage_failure_does_not_reset_to_memory(monkeypatch,tmp_path):
    from signguard.broker import quota_allowed
    monkeypatch.setenv('SIGNGUARD_QUOTA_DATABASE',str(tmp_path/'missing'/'quota.sqlite3'))
    assert not quota_allowed('owner')


def test_secret_generation_persists_and_is_never_in_source_or_release(tmp_path):
    values={'oauth_client_id':'syntheticClient123','oauth_client_secret':'syntheticSecret123'}
    write(values,tmp_path)
    before=(tmp_path/'ui.env').read_text()
    write(values,tmp_path)
    assert (tmp_path/'ui.env').read_text()==before
    assert (tmp_path/'ui.env').stat().st_mode & 0o777==0o600
    with pytest.raises(ValueError):write({**values,'extra':'untrusted'},tmp_path)


def test_bootstrap_oidc_has_environment_bound_subject_and_no_compute():
    template=json.loads(Path('deploy/aws/bootstrap.cfn.json').read_text())
    assert all(v['Type']!='AWS::EC2::Instance' for v in template['Resources'].values())
    condition=template['Resources']['DeployRole']['Properties']['AssumeRolePolicyDocument']['Statement'][0]['Condition']
    assert condition['StringEquals']['token.actions.githubusercontent.com:sub']=='repo:Saisathwik045/signguard:environment:aws-staging'
    runtime=template['Resources']['RuntimeRole']['Properties']['Policies'][0]['PolicyDocument']['Statement']
    assert not any('s3:DeleteObject' in str(item) or 's3:BypassGovernanceRetention' in str(item) for item in runtime)


def test_all_host_shell_scripts_parse():
    import subprocess
    for path in Path('deploy/aws/host').glob('*.sh'):
        subprocess.run(['bash','-n',str(path)],check=True)


def test_ssm_delivery_rejects_injected_paths_before_shell():
    from scripts.aws_delivery import commands
    delivery={'release':release(),'instance_id':'i-0123456789abcdef0','volume_id':'vol-0123456789abcdef0',
              'source_key':'releases/untrusted;exit/source.tar.gz','source_sha256':'c'*64,
              'state_bucket':'signguard-staging-state-123456789012','id':'a'*40+'-123-1'}
    with pytest.raises(ValueError):commands(delivery)
    delivery['source_key']='releases/'+delivery['id']+'/source.tar.gz'
    instance,script=commands(delivery)
    assert instance.startswith('i-') and 'sha256sum -c -' in script and 'mount-audit.sh' in script
    assert 'secret' not in json.dumps(delivery).lower()


def test_hosted_smoke_refuses_http_private_hosts_and_redirect_targets():
    from scripts.smoke_aws_staging import address
    for value in ['http://8.8.8.8','https://127.0.0.1','https://8.8.8.8/path','https://8.8.8.8@evil.test','https://8.8.8.8:443']:
        with pytest.raises(ValueError):address(value)
    assert address('https://8.8.8.8')=='8.8.8.8'
