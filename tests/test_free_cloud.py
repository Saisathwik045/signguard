import json
import shutil
from pathlib import Path

import pytest

from scripts.free_cloud_policy import check
from scripts.oracle_free_eligibility import assess
from scripts.zero_cost_demo import authorize, evaluate
from signguard.demo import load_case


def test_repository_cost_policy():
    assert check(Path('.'))['policy_passed']


@pytest.mark.parametrize('mutation',['runs-on: ubuntu-latest','uses: actions/upload-artifact@v4','cache: pip'])
def test_cost_policy_rejects_unguarded_or_metered_steps(tmp_path,mutation):
    shutil.copytree('deploy/free',tmp_path/'deploy/free')
    folder=tmp_path/'.github/workflows';folder.mkdir(parents=True)
    (folder/'bad.yml').write_text('jobs:\n  test:\n    '+mutation+'\n')
    with pytest.raises((ValueError,KeyError)):check(tmp_path)


def test_public_runner_is_not_an_account_billing_guarantee():
    result=check(Path('.'))
    assert not result['billing_account_settings_verified'] and not result['private_upload_available']


def test_oracle_default_is_blocked_without_authoritative_entitlements():
    result=assess(json.loads(Path('deploy/oracle/free-only.example.json').read_text()))
    assert not result['eligibility_precheck_passed'] and not result['resource_creation_supported']


def eligible():
    value=json.loads(Path('deploy/oracle/free-only.example.json').read_text())
    for name in ['trial_expired','home_region_confirmed','always_free_eligibility_confirmed','capacity_available','arm64_runtime_qualified']:
        value[name]=True
    value['account_type']='ALWAYS_FREE_NON_UPGRADED'
    return value


@pytest.mark.parametrize('field,value',[('existing_ocpus',2),('existing_memory_gib',12),('existing_block_storage_gib',200),('public_ingress_enabled',True),('provisioning_enabled',True),('account_type','PAID')])
def test_oracle_other_tenancy_consumption_and_ingress_block(field,value):
    config=eligible();config[field]=value
    assert not assess(config)['eligibility_precheck_passed']


@pytest.mark.parametrize('value',[True,-1,'1',float('inf'),float('nan')])
def test_oracle_invalid_numbers_cannot_prove_free_eligibility(value):
    config=eligible();config['requested_ocpus']=value
    with pytest.raises(ValueError):assess(config)


def test_even_fully_attested_oracle_precheck_does_not_create_resources():
    result=assess(eligible())
    assert result['eligibility_precheck_passed']
    assert not result['billing_guaranteed'] and not result['deployment_ready']


@pytest.mark.parametrize('field,value',[('actor_id','foreign-owner'),('private',True),('repository','other/repo'),('event_name','repository_dispatch')])
def test_synthetic_dispatch_identity_is_fixed(field,value):
    event={'actor_id':'220234042','private':False,'repository':'Saisathwik045/signguard','event_name':'workflow_dispatch'}
    event[field]=value
    with pytest.raises(PermissionError):authorize(event)


def test_synthetic_evaluation_refuses_paths_and_does_not_call_worker(tmp_path):
    def forbidden(_):raise AssertionError('Untrusted input reached worker')
    for case in ['../../private.pdf','https://example.com/test.pdf','/tmp/real.pdf']:
        with pytest.raises(ValueError):evaluate(case,tmp_path/'output',forbidden)


def test_report_provenance_output_and_audit_contract_with_mocked_worker(tmp_path):
    report,_=load_case('genuine_signed')
    result=evaluate('genuine_signed',tmp_path/'output',lambda _, report=report:report)
    assert result['case_id']=='genuine_signed' and not result['private_upload_supported']
    assert (tmp_path/'output/report.pdf').read_bytes().startswith(b'%PDF')
    assert len(result['audit_head'])==64


def test_worker_result_for_different_input_or_missing_isolation_is_rejected(tmp_path):
    for mode in ['digest','isolation']:
        report,_=load_case('unsigned')
        if mode=='digest':report['sha256']='0'*64
        else:report['execution_controls']['network_isolation']=False
        with pytest.raises(ValueError):evaluate('unsigned',tmp_path/mode,lambda _, report=report:report)


def test_paid_delivery_refuses_before_contacting_provider(monkeypatch,tmp_path):
    from scripts import aws_delivery
    def forbidden(*args):raise AssertionError('A chargeable provider was contacted')
    monkeypatch.setattr(aws_delivery,'aws',forbidden)
    with pytest.raises(PermissionError):aws_delivery.publish({},tmp_path)
    with pytest.raises(PermissionError):aws_delivery.stage({})


@pytest.mark.parametrize('extra',[{'uses':'actions/upload-artifact@v4'},{'uses':'actions/setup-python@v5','with':{'cache':'pip'}},{'run':'terraform apply -auto-approve'}])
def test_guarded_job_still_refuses_storage_and_provisioning(tmp_path,extra):
    import yaml

    from scripts.free_cloud_policy import GATE
    shutil.copytree('deploy/free',tmp_path/'deploy/free')
    folder=tmp_path/'.github/workflows';folder.mkdir(parents=True)
    job={'if':'${{ '+GATE+' }}','runs-on':'ubuntu-latest','steps':[extra]}
    (folder/'bad.yml').write_text(yaml.safe_dump({'jobs':{'test':job}}))
    with pytest.raises(ValueError):check(tmp_path)
