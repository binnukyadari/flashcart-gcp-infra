import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('backend_guard', Path(__file__).resolve().parents[1]/'scripts/backend-dev.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def plan():
    resources = []
    for address in guard.EXPECTED:
        kind = address.split('.')[0]
        after = {'project': guard.PROJECT}
        resource = {'address': address, 'type': kind, 'change': {'actions': ['create'], 'after': after}}
        if kind == 'google_project_iam_member':
            key = address.split('["')[1].split('"')[0]
            resource['index'] = key
            after['role'] = guard.ROLES[key]
        elif kind == 'google_project_iam_custom_role':
            after['permissions'] = ['storage.objects.create', 'storage.objects.get']
        elif kind == 'google_sql_user':
            after['instance'] = 'flashcart-dev-inventory'
        elif kind == 'google_service_account':
            after['account_id'] = 'flashcart-'+address.split('["')[1].split('"')[0]
        elif kind == 'google_storage_bucket_iam_member':
            after.update(bucket='flashcart-dev-invoices-ritru-fc-dev-01', condition=[{'expression': "resource.name.startsWith('projects/_/buckets/flashcart-dev-invoices-ritru-fc-dev-01/objects/invoices/')"}])
        elif kind in {'google_cloud_run_v2_service', 'google_cloud_run_v2_job'}:
            name = address.split('.')[1]
            template = {'containers': [{'image': guard.IMAGE_PREFIX+'a'*64}], 'vpc_access': [{'network_interfaces': [{'network': 'flashcart-dev', 'subnetwork': 'flashcart-dev-run'}]}], 'max_retries': 0}
            if kind == 'google_cloud_run_v2_service':
                template['scaling'] = [{'max_instance_count': 1}]
                after['template'] = [template]
            else:
                after['template'] = [{'template': [template]}]
            after.update(name='flashcart-'+name+'-dev', location='asia-south1')
        elif kind == 'google_cloud_run_v2_service_iam_member':
            after.update(role='roles/run.invoker', member='user:contact@ritru.com')
        resources.append(resource)
    return {'resource_changes': resources, 'variables': {'backend_image': {'value': guard.IMAGE_PREFIX+'a'*64}}}


class BackendPlan(unittest.TestCase):
    def test_declared_creates(self):
        self.assertEqual(guard.check_plan(plan())[1], 33)

    def test_deletions_updates_other_projects_and_extra_resources_rejected(self):
        for mutation in ('delete', 'update', 'project', 'extra'):
            candidate = plan()
            if mutation in ('delete', 'update'):
                candidate['resource_changes'][0]['change']['actions'] = [mutation]
            elif mutation == 'project':
                candidate['resource_changes'][0]['change']['after']['project'] = 'production'
            else:
                candidate['resource_changes'].append(copy.deepcopy(candidate['resource_changes'][0]))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                guard.check_plan(candidate)

    def test_public_api_escalated_role_mutable_image_and_unbounded_scale_rejected(self):
        for mutation in ('public', 'owner', 'image', 'scale'):
            candidate = plan()
            resources = {r['address']: r for r in candidate['resource_changes']}
            if mutation == 'public':
                resources['google_cloud_run_v2_service_iam_member.trainer']['change']['after']['member'] = 'allUsers'
            elif mutation == 'owner':
                resources['google_project_iam_member.runtime["api_orders"]']['change']['after']['role'] = 'roles/owner'
            elif mutation == 'image':
                candidate['variables']['backend_image']['value'] = 'image:latest'
            else:
                resources['google_cloud_run_v2_service.api']['change']['after']['template'][0]['scaling'][0]['max_instance_count'] = 50
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                guard.check_plan(candidate)

    def test_semantic_change_alters_fingerprint(self):
        candidate = plan()
        first = guard.check_plan(candidate)[0]
        candidate['output_changes'] = {'changed': {'after': 'new'}}
        self.assertNotEqual(first, guard.check_plan(candidate)[0])


if __name__ == '__main__':
    unittest.main()
