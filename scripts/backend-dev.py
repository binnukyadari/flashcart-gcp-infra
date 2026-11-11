#!/usr/bin/env python3
"""Read-only state snapshot and scope checks for the single dev training stack."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

PROJECT = 'ritru-fc-dev-01'
STACK = 'stacks/04-backend'
PREFIX = 'gcp-02-flashcart/stacks/04-backend/dev'
BUCKET = 'ritru-tfstate-586582398977'
IMAGE_PREFIX = 'asia-south1-docker.pkg.dev/ritru-fc-dev-01/flashcart-docker/backend@sha256:'
ROLES = {
    'api_database': 'roles/cloudsql.client', 'api_login': 'roles/cloudsql.instanceUser',
    'api_orders': 'roles/datastore.user', 'worker_database': 'roles/cloudsql.client',
    'worker_login': 'roles/cloudsql.instanceUser', 'worker_orders': 'roles/datastore.user',
    'bootstrap_sql': 'roles/cloudsql.client',
}
EXPECTED = {
    'google_sql_user.bootstrap', 'google_project_iam_custom_role.invoice_writer',
    'google_storage_bucket_iam_member.worker', 'google_secret_manager_secret.api_key',
    'google_secret_manager_secret.bootstrap', 'google_secret_manager_secret_version.api_key',
    'google_secret_manager_secret_version.bootstrap',
    'google_secret_manager_secret_iam_member.bootstrap', 'google_pubsub_schema.events',
    'google_pubsub_topic.events', 'google_pubsub_subscription.inspect',
    'google_pubsub_topic_iam_member.worker', 'google_cloud_run_v2_service.api',
    'google_cloud_run_v2_service_iam_member.trainer', 'google_cloud_run_v2_job.worker',
    'google_cloud_run_v2_job.bootstrap',
}
for account in ('api', 'worker', 'bootstrap'):
    EXPECTED.add(f'google_service_account.runtime["{account}"]')
    EXPECTED.add(f'google_service_account_iam_member.deployer["{account}"]')
for account in ('api', 'worker'):
    EXPECTED.add(f'google_sql_user.runtime["{account}"]')
    EXPECTED.add(f'google_secret_manager_secret_iam_member.api_key["{account}"]')
for role in ROLES:
    EXPECTED.add(f'google_project_iam_member.runtime["{role}"]')


def check_age(value):
    age = time.time() - int(value)
    if not 0 <= age <= 3600:
        raise ValueError('The reviewed plan expired; start a new run')


def check_plan(plan):
    changes = plan.get('resource_changes', [])
    if {r['address'] for r in changes} != EXPECTED or len(changes) != len(EXPECTED):
        raise ValueError('Plan must contain exactly the declared dev backend resources')
    if plan.get('errored') or plan.get('complete') is False or plan.get('deferred_changes'):
        raise ValueError('Incomplete plans are not allowed')
    image = plan['variables']['backend_image']['value']
    if not image.startswith(IMAGE_PREFIX) or len(image.removeprefix(IMAGE_PREFIX)) != 64:
        raise ValueError('Expected a pinned image from the dev backend repository')
    creates = 0
    for resource in changes:
        address, change = resource['address'], resource['change']
        after = change['after']
        if change['actions'] not in [['create'], ['no-op']] or change.get('importing') or resource.get('previous_address'):
            raise ValueError('Only declared resource creates or no-ops are allowed')
        creates += change['actions'] == ['create']
        if after.get('project') not in (None, PROJECT):
            raise ValueError('Another project is not allowed')
        kind = resource['type']
        if kind == 'google_project_iam_member':
            key = resource['index']
            if after['role'] != ROLES[key]:
                raise ValueError('Unexpected runtime project role')
        if kind == 'google_project_iam_custom_role' and set(after['permissions']) != {'storage.objects.create', 'storage.objects.get'}:
            raise ValueError('Invoice permissions must be create/get only')
        if kind == 'google_sql_user' and after['instance'] != 'flashcart-dev-inventory':
            raise ValueError('Another database instance is not allowed')
        if kind == 'google_service_account' and after['account_id'] not in {'flashcart-api', 'flashcart-worker', 'flashcart-bootstrap'}:
            raise ValueError('Unexpected runtime identity')
        if kind == 'google_storage_bucket_iam_member':
            if after['bucket'] not in {'flashcart-dev-invoices-ritru-fc-dev-01', 'b/flashcart-dev-invoices-ritru-fc-dev-01'} or not after['condition']:
                raise ValueError('Invoice access must be conditioned on the existing bucket')
            if after['condition'][0]['expression'] != "resource.name.startsWith('projects/_/buckets/flashcart-dev-invoices-ritru-fc-dev-01/objects/invoices/')":
                raise ValueError('Invoice access must use the invoices prefix')
        if kind in {'google_cloud_run_v2_service', 'google_cloud_run_v2_job'}:
            if after['location'] != 'asia-south1' or after['name'] not in {'flashcart-api-dev', 'flashcart-worker-dev', 'flashcart-bootstrap-dev'}:
                raise ValueError('Unexpected Cloud Run target')
            template = after['template'][0]
            if kind == 'google_cloud_run_v2_job':
                template = template['template'][0]
                if template['max_retries'] != 0:
                    raise ValueError('Training jobs must not automatically repeat writes')
            else:
                if template['scaling'][0]['max_instance_count'] != 1:
                    raise ValueError('Dev API must be capped at one instance')
            if template['containers'][0]['image'] != image:
                raise ValueError('Cloud Run must use the reviewed image digest')
            network = template['vpc_access'][0]['network_interfaces'][0]
            if network['network'] != 'flashcart-dev' or network['subnetwork'] != 'flashcart-dev-run':
                raise ValueError('Only the existing dev network is allowed')
        if kind == 'google_cloud_run_v2_service_iam_member':
            if after['role'] != 'roles/run.invoker' or after['member'] != 'user:contact@ritru.com':
                raise ValueError('The API must remain private to the trusted trainer')
    payload = {key: plan.get(key, []) for key in ('resource_changes', 'resource_drift')}
    payload['output_changes'] = plan.get('output_changes', {})
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return digest, int(creates), image


def snapshot():
    state = Path(os.environ['RUNNER_TEMP']) / 'flashcart-backend-dev.tfstate'
    url = f'https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/' + urllib.parse.quote(PREFIX+'/default.tfstate', safe='') + '?alt=media'
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer '+os.environ['ACCESS_TOKEN']})
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read()
        json.loads(raw)
        state.write_bytes(raw)
        state.chmod(0o600)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise RuntimeError(f'State fetch failed: HTTP {error.code}') from None
        state.unlink(missing_ok=True)
    Path(STACK+'/backend_override.tf.json').write_text(json.dumps({'terraform': {'backend': {'local': {'path': str(state)}}}}))
    print('Prepared private local dev backend state snapshot; no remote writes.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['snapshot', 'check-plan', 'check-age'])
    parser.add_argument('path', nargs='?')
    args = parser.parse_args()
    if args.command == 'snapshot':
        snapshot()
    elif args.command == 'check-age':
        check_age(os.environ.get('REVIEWED_PLAN_AT', '0'))
    else:
        digest, creates, image = check_plan(json.loads(Path(args.path).read_text()))
        expected = os.environ.get('EXPECTED_PLAN_DIGEST')
        if expected:
            check_age(os.environ.get('REVIEWED_PLAN_AT', '0'))
            if expected != digest:
                raise ValueError('Plan changed after review; a new review is required')
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                out.write(f'plan_digest={digest}\ncreates={creates}\nplanned_at={int(time.time())}\n')
        if 'GITHUB_STEP_SUMMARY' in os.environ:
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
                out.write('### FlashCart connected dev demo plan\n\n')
                out.write(f'Project: `{PROJECT}`; region: `asia-south1`.\n\n')
                out.write(f'- Create: {creates}\n- Update: 0\n- Delete: 0\n')
                out.write('- Private API, bootstrap job, worker job, scoped runtime identities, secrets and new event topic.\n')
                out.write('- Existing SQL instance, network, Firestore, storage bucket and registry are preserved.\n')
                out.write(f'- Image: `{image}`\n- Source: `{os.environ.get("GITHUB_SHA", "local")}`\n- Fingerprint: `{digest}`\n')
        print(f'BACKEND_PLAN create={creates} update=0 delete=0 fingerprint={digest}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, IndexError, TypeError, RuntimeError) as error:
        raise SystemExit(f'Dev backend check failed: {error}') from None
