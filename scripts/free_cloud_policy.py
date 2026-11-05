"""Fail-closed repository cost policy. This does not read or prove account billing settings."""
import argparse
import json
from pathlib import Path

import yaml

GATE = "vars.SIGNGUARD_ZERO_SPEND_CONFIRMED == 'true' && github.event.repository.private == false"
RUNNERS = {'ubuntu-latest', 'ubuntu-24.04', 'ubuntu-24.04-arm'}


def check(root):
    policy=json.loads((root/'deploy/free/policy.json').read_text())
    if policy['maximum_spend_inr']!=0 or policy['paid_provisioning_allowed'] or policy['remote_artifact_upload_allowed']:
        raise ValueError('Strict zero-cost policy changed')
    workflows=[]
    for path in sorted((root/'.github/workflows').glob('*.yml')):
        workflow=yaml.safe_load(path.read_text())
        for job in workflow['jobs'].values():
            if not job.get('if','').startswith('${{ '+GATE) or '||' in job.get('if',''):raise ValueError('Missing account cost gate: '+path.name)
            if job['runs-on'] not in RUNNERS:raise ValueError('Unapproved runner')
            if job.get('permissions',{}).get('id-token')=='write':raise ValueError('Cloud provisioning identity forbidden')
            for step in job.get('steps',[]):
                command=step.get('run','')
                if any(token in command for token in ['terraform apply','scripts.aws_delivery','aws ec2','aws s3','aws secretsmanager']):
                    raise ValueError('Chargeable provisioning command forbidden')
                action=step.get('uses','')
                if any(word in action for word in ['upload-artifact','actions/cache','configure-aws','deploy']):
                    raise ValueError('Storage/provisioning action forbidden')
                if step.get('with',{}).get('cache'):raise ValueError('Persistent CI cache forbidden')
        workflows.append(path.name)
    return {'policy_passed':True,'maximum_spend_inr':0,'workflows':workflows,
            'billing_account_settings_verified':False,'private_upload_available':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('.'))
    args=parser.parse_args();print(json.dumps(check(args.root),indent=2))
