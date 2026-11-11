#!/usr/bin/env python3
"""Validate and fingerprint the sole approved dev Artifact Registry resource."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ADDRESS = 'module.application.google_artifact_registry_repository.docker'
PROJECT = 'ritru-fc-dev-01'
LOCATION = 'asia-south1'
REPOSITORY = 'flashcart-docker'


def check(plan):
    changes = plan.get('resource_changes', [])
    if len(changes) != 1:
        raise ValueError('Expected exactly one Artifact Registry resource')
    resource = changes[0]
    change = resource['change']
    if resource['address'] != ADDRESS or change['actions'] not in [['create'], ['no-op']]:
        raise ValueError('Only the expected resource creation or no-op is allowed')
    if resource.get('previous_address') or change.get('importing'):
        raise ValueError('Imports and resource moves require separate review')
    after = change['after']
    required = {'project': PROJECT, 'location': LOCATION, 'repository_id': REPOSITORY, 'format': 'DOCKER'}
    if any(after.get(key) != value for key, value in required.items()):
        raise ValueError('Unexpected project, region, repository or format')
    if after.get('docker_config') != [{'immutable_tags': True}]:
        raise ValueError('Immutable Docker tags are required')
    if plan.get('deferred_changes') or plan.get('errored') or plan.get('complete') is False:
        raise ValueError('Incomplete plans cannot be approved')
    # Compare all resource/output changes, including labels, unknown fields and drift.
    # Backend-local details and timestamps differ between the two plan jobs.
    payload = {key: plan.get(key, []) for key in ('resource_changes', 'resource_drift')}
    payload['output_changes'] = plan.get('output_changes', {})
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return digest, int(change['actions'] == ['create'])


def check_age(value, now=None):
    now = time.time() if now is None else now
    age = now - int(value)
    if not 0 <= age <= 3600:
        raise ValueError('Reviewed plan is outside its one-hour approval window; start a new run')


def main():
    if sys.argv[1:] == ['--check-age']:
        check_age(os.environ.get('REVIEWED_PLAN_AT', '0'))
        return
    digest, creates = check(json.loads(Path(sys.argv[1]).read_text()))
    expected = os.environ.get('EXPECTED_PLAN_DIGEST')
    if expected:
        check_age(os.environ.get('REVIEWED_PLAN_AT', '0'))
    if expected and digest != expected:
        raise ValueError('Plan changed after review; stop and request a fresh plan review')
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write(f'plan_digest={digest}\ncreates={creates}\nplanned_at={int(time.time())}\n')
    if 'GITHUB_STEP_SUMMARY' in os.environ:
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
            output.write('### FlashCart Artifact Registry dev plan\n\n')
            output.write(f'Target: `{PROJECT}`, `{LOCATION}`, `{REPOSITORY}` (DOCKER, immutable tags).\n\n')
            output.write(f'- Create: {creates}\n- Update: 0\n- Delete: 0\n')
            output.write(f'- Source commit: `{os.environ.get("GITHUB_SHA", "local")}`\n')
            output.write(f'- Plan fingerprint: `{digest}`\n\n')
            output.write('Plan generation does not deploy. Deployment requires the manual workflow and environment approval.\n')
    print(f'Dev plan scope verified: create={creates}, update=0, delete=0; fingerprint={digest}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise SystemExit(f'Dev plan rejected: {error}') from None
