import importlib.util
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plan_guard', ROOT / 'scripts/check-dev-plan.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def plan():
    return {'resource_changes': [{
        'address': guard.ADDRESS,
        'change': {'actions': ['create'], 'after': {
            'project': guard.PROJECT, 'location': guard.LOCATION,
            'repository_id': guard.REPOSITORY, 'format': 'DOCKER',
            'docker_config': [{'immutable_tags': True}],
            'labels': {'owner': 'platform-team'},
        }},
    }], 'output_changes': {}}


class PlanSafety(unittest.TestCase):
    def test_expected_create_and_noop(self):
        candidate = plan()
        self.assertEqual(guard.check(candidate)[1], 1)
        candidate['resource_changes'][0]['change']['actions'] = ['no-op']
        self.assertEqual(guard.check(candidate)[1], 0)

    def test_unsafe_mutations_are_rejected(self):
        for actions in [['update'], ['delete'], ['delete', 'create'], ['create', 'delete'], ['read']]:
            with self.subTest(actions=actions):
                candidate = plan()
                candidate['resource_changes'][0]['change']['actions'] = actions
                with self.assertRaises(ValueError):
                    guard.check(candidate)

    def test_wrong_targets_and_mutable_tags_are_rejected(self):
        for key, bad in [('project', 'production'), ('location', 'us-central1'),
                         ('repository_id', 'another-repo'), ('format', 'MAVEN'),
                         ('docker_config', [{'immutable_tags': False}])]:
            with self.subTest(key=key):
                candidate = plan()
                candidate['resource_changes'][0]['change']['after'][key] = bad
                with self.assertRaises(ValueError):
                    guard.check(candidate)

    def test_empty_additional_or_moved_resources_are_rejected(self):
        for value in [[], plan()['resource_changes'] * 2]:
            with self.assertRaises(ValueError):
                guard.check({'resource_changes': value})
        candidate = plan()
        candidate['resource_changes'][0]['previous_address'] = 'old.resource'
        with self.assertRaises(ValueError):
            guard.check(candidate)

    def test_incomplete_plan_is_rejected(self):
        for field, value in [('complete', False), ('errored', True), ('deferred_changes', [{}])]:
            candidate = plan()
            candidate[field] = value
            with self.assertRaises(ValueError):
                guard.check(candidate)

    def test_fingerprint_ignores_order_but_detects_semantic_changes(self):
        candidate = plan()
        original = guard.check(candidate)[0]
        candidate['timestamp'] = 'later'
        self.assertEqual(guard.check(candidate)[0], original)
        candidate['resource_changes'][0]['change']['after']['labels']['owner'] = 'another-owner'
        self.assertNotEqual(guard.check(candidate)[0], original)
        candidate = plan()
        candidate['output_changes'] = {'unexpected': {'after': 'changed'}}
        self.assertNotEqual(guard.check(candidate)[0], original)

    def test_changed_plan_is_rejected_after_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'plan.json')
            path.write_text(json.dumps(plan()))
            with patch.dict(os.environ, {'EXPECTED_PLAN_DIGEST': 'wrong', 'REVIEWED_PLAN_AT': '1000'}), \
                 patch('sys.argv', ['guard', str(path)]), patch.object(guard.time, 'time', return_value=1001):
                with self.assertRaisesRegex(ValueError, 'Plan changed'):
                    guard.main()

    def test_approval_window_rejects_old_future_and_missing_times(self):
        guard.check_age('1000', now=4600)
        for timestamp in ['999', '4601', '0', 'not-a-time']:
            with self.assertRaises(ValueError):
                guard.check_age(timestamp, now=4600)


class StateSnapshot(unittest.TestCase):
    def run_snapshot(self, error):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory, 'stacks/03-application')
            target.mkdir(parents=True)
            with patch.dict(os.environ, {'RUNNER_TEMP': directory, 'ACCESS_TOKEN': 'test-token'}), \
                 patch('urllib.request.urlopen', side_effect=error):
                old = Path.cwd()
                os.chdir(directory)
                try:
                    if error.code == 404:
                        runpy.run_path(str(ROOT / 'scripts/read-dev-state.py'))
                        override = json.loads((target / 'backend_override.tf.json').read_text())
                        self.assertIn('local', override['terraform']['backend'])
                        self.assertFalse(Path(directory, 'flashcart-dev.tfstate').exists())
                    else:
                        with self.assertRaises(SystemExit):
                            runpy.run_path(str(ROOT / 'scripts/read-dev-state.py'))
                        self.assertFalse((target / 'backend_override.tf.json').exists())
                finally:
                    os.chdir(old)

    def test_missing_state_plans_new_stack(self):
        self.run_snapshot(urllib.error.HTTPError('url', 404, 'missing', {}, None))

    def test_permission_or_server_errors_never_look_like_empty_state(self):
        for status in [401, 403, 500]:
            with self.subTest(status=status):
                self.run_snapshot(urllib.error.HTTPError('url', status, 'error', {}, None))


class WorkflowGates(unittest.TestCase):
    def read(self, name):
        return yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader)

    def test_deployment_requires_manual_main_and_explicit_request(self):
        workflow = self.read('deploy-dev.yml')
        self.assertEqual(set(workflow['on']), {'workflow_dispatch'})
        self.assertEqual(workflow['on']['workflow_dispatch']['inputs']['deploy']['default'], 'false')
        for job in ['plan', 'apply']:
            self.assertIn("github.ref == 'refs/heads/main'", workflow['jobs'][job]['if'])
        job = workflow['jobs']['apply']
        for gate in ['inputs.deploy', "inputs.confirmation == 'ritru-fc-dev-01/flashcart-docker'",
                     "vars.FLASHCART_DEV_APPLY_ENABLED == 'true'", "needs.plan.outputs.creates == '1'"]:
            self.assertIn(gate, job['if'])
        self.assertEqual(job['environment'], 'dev-artifact-registry')
        self.assertEqual(job['needs'], 'plan')
        self.assertEqual(workflow['concurrency']['cancel-in-progress'], 'false')

    def test_saved_plan_is_checked_before_apply_and_not_uploaded(self):
        workflow = self.read('deploy-dev.yml')
        steps = workflow['jobs']['apply']['steps']
        names = [step.get('name', '') for step in steps]
        self.assertLess(names.index('Check policies and match the reviewed plan'), names.index('Apply the checked saved plan'))
        command = next(s['run'] for s in steps if s.get('name') == 'Apply the checked saved plan')
        self.assertIn('terraform apply -no-color -lock-timeout=5m tfplan', command)
        self.assertIn('check-dev-plan.py" --check-age', command)
        all_text = (ROOT / '.github/workflows/deploy-dev.yml').read_text()
        self.assertNotIn('upload-artifact', all_text)
        self.assertNotIn('auto-approve', all_text)
        self.assertNotIn('environment: prod', all_text)

    def test_pr_path_cannot_apply_and_drift_is_paused(self):
        workflow = self.read('infra.yml')
        self.assertEqual(set(workflow['on']), {'pull_request'})
        reusable = self.read('terraform-stack.yml')
        self.assertEqual(set(reusable['jobs']), {'plan'})
        self.assertEqual(reusable['env']['ENVIRONMENT'], 'dev')
        self.assertNotIn('terraform apply', (ROOT / '.github/workflows/terraform-stack.yml').read_text())
        drift = self.read('drift.yml')
        self.assertEqual(set(drift['jobs']), {'paused'})


if __name__ == '__main__':
    unittest.main()
