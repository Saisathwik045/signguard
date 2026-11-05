"""Offline OCI eligibility screen; deliberately has no cloud SDK or resource-create operation."""
import argparse
import json
import math
from pathlib import Path


def assess(config):
    blockers=[]
    if config['provisioning_enabled']:blockers.append('Provisioning is disabled under the current approval scope')
    for name in ['trial_expired','home_region_confirmed','always_free_eligibility_confirmed','capacity_available','arm64_runtime_qualified']:
        if config.get(name) is not True:blockers.append(name+' is unverified')
    if config.get('account_type')!='ALWAYS_FREE_NON_UPGRADED':blockers.append('Non-upgraded free account is unverified')
    for field in ['existing_ocpus','existing_memory_gib','existing_block_storage_gib','requested_ocpus','requested_memory_gib','requested_boot_storage_gib']:
        value=config.get(field)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
            raise ValueError('Invalid quota value: '+field)
    if config['existing_ocpus']+config['requested_ocpus']>2:blockers.append('Exceeds published 2 OCPU envelope')
    if config['existing_memory_gib']+config['requested_memory_gib']>12:blockers.append('Exceeds published 12 GiB envelope')
    if config['existing_block_storage_gib']+config['requested_boot_storage_gib']>200:blockers.append('Exceeds 200 GiB combined boot/block envelope')
    if config['requested_ocpus']<1 or config['requested_memory_gib']<4 or config['requested_boot_storage_gib']<50:
        blockers.append('Below conservative single-host requirements')
    if config.get('public_ingress_enabled') is not False:blockers.append('Ingress must remain disabled')
    return {'eligibility_precheck_passed':not blockers,'blockers':blockers,'resource_creation_supported':False,
            'billing_guaranteed':False,'deployment_ready':False,
            'limitations':'Account-wide usage, tenancy quotas, backups, traffic and current provider terms need authoritative verification'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('config',type=Path)
    args=parser.parse_args();print(json.dumps(assess(json.loads(args.config.read_text())),indent=2))
