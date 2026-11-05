"""Owner-dispatched, synthetic-only CI evaluation. No document bytes, paths or URLs are accepted."""
import argparse
import base64
import hashlib
import json
import os
from importlib.resources import files
from pathlib import Path

from signguard.audit import append_event, verify_log
from signguard.container_runner import analyze_container
from signguard.demo import CASES, load_case
from signguard.supervisor import encode_request


def authorize(event):
    if (event.get('event_name')!='workflow_dispatch' or event.get('actor_id')!='220234042'
            or event.get('repository')!='Saisathwik045/signguard' or event.get('private') is not False):
        raise PermissionError('Only the fixed repository owner may dispatch this synthetic evaluation')


def evaluate(case_id, output, analyze=analyze_container):
    if case_id not in CASES:raise ValueError('Unknown bundled synthetic case')
    _,provenance=load_case(case_id)  # Validate the fixed bundle before worker admission.
    data=files('signguard').joinpath('demo_assets',case_id+'.pdf').read_bytes()
    report=analyze(encode_request(data))
    if report.get('sha256')!=hashlib.sha256(data).hexdigest():raise ValueError('Worker input/report digest mismatch')
    controls=report.get('execution_controls',{})
    if controls.get('isolation')!='docker_disposable' or not controls.get('network_isolation'):
        raise ValueError('Required isolated worker evidence absent')
    output.mkdir(parents=True,exist_ok=False)
    raw=(json.dumps(report,sort_keys=True,indent=2)+'\n').encode()
    (output/'report.json').write_bytes(raw)
    (output/'report.pdf').write_bytes(base64.b64decode(report['pdf_report']['base64'],validate=True))
    for index,evidence in enumerate(report['visual_evidence']):
        (output/f'evidence-{index}.png').write_bytes(base64.b64decode(evidence['base64'],validate=True))
    head=append_event(output/'audit.jsonl',{'synthetic_case':case_id,'input_sha256':report['sha256'],
                      'report_sha256':hashlib.sha256(raw).hexdigest(),'run_id':os.environ.get('GITHUB_RUN_ID','codex-cloud')})
    assert verify_log(output/'audit.jsonl',head)[1]==1
    summary={'synthetic_only':True,'case_id':case_id,'fresh_worker_analysis':True,'input_sha256':report['sha256'],
             'report_sha256':hashlib.sha256(raw).hexdigest(),'audit_head':head,'classification':report['structure']['refined_classification'],
             'verdict':report['assessment']['verdict'],'private_upload_supported':False,'bundled_provenance':provenance}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=list(CASES),required=True)
    args=parser.parse_args()
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    authorize({'event_name':os.environ['GITHUB_EVENT_NAME'],'actor_id':os.environ['GITHUB_ACTOR_ID'],
               'repository':os.environ['GITHUB_REPOSITORY'],'private':event['repository']['private']})
    print(json.dumps(evaluate(args.case,Path('zero-cost-output')),indent=2))
