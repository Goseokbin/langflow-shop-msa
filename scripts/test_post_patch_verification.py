import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).parent


def fixture():
    values = {'$service': 'user-service', '$expected_package': 'python-multipart',
              '$cve': 'CVE-2024-53981', '$result': {}, '$deploymentSnapshots': {},
              '$Read_release_runs': {'statusCode': 200, 'result': {'workflow_runs': [
                  {'head_sha': 'abcdef1234567890', 'status': 'completed', 'conclusion': 'success',
                   'html_url': 'https://github.com/demo/shop/actions/runs/1'}]}}}
    for role in ['staging', 'production']:
        values['$'+role+'Runtime'] = {'image': 'registry/user@sha256:abc', 'artifact': 'current'}
        values['$deploymentSnapshots'][role] = {'application_version': '1.0.1-abcdef123456'}
        values['$Read_'+role+'_packages'] = {'statusCode': 200, 'result': {
            'pagination': {'total_count': 1}, 'packages': [{'name': 'python-multipart', 'version': '0.0.32'}]}}
        values['$Read_'+role+'_cve_findings'] = {'statusCode': 200, 'result': {
            'pagination': {'total_count': 0}, 'cve_findings': []}}
    return values


def evaluate(data):
    harness = """const fs=require('fs'),vm=require('vm');const x=JSON.parse(fs.readFileSync(0,'utf8'));vm.runInNewContext(fs.readFileSync(x.path,'utf8'),x.data);console.log(JSON.stringify(x.data.$result));"""
    return json.loads(subprocess.check_output(['node', '-e', harness], text=True,
        input=json.dumps({'path': str(HERE/'post-patch-verification.js'), 'data': data})))


class PostPatchVerification(unittest.TestCase):
    def test_current_scans_and_successful_same_release_verify(self):
        result = evaluate(fixture())
        self.assertTrue(result['verified'])
        self.assertFalse(result['writes_enabled'])

    def test_remaining_cve_even_manually_closed_is_not_remediated(self):
        data = fixture()
        for role in ['staging', 'production']:
            data['$Read_'+role+'_cve_findings']['result']['cve_findings'] = [
                {'cve': data['$cve'], 'assessment_status': 'Closed'}]
        self.assertEqual(evaluate(data)['verdict'], 'target_present')

    def test_staging_fix_only_waits_for_production(self):
        data = fixture()
        data['$Read_production_cve_findings']['result']['cve_findings'] = [{'cve': data['$cve']}]
        self.assertEqual(evaluate(data)['verdict'], 'awaiting_production')

    def test_missing_package_never_means_safe(self):
        data = fixture(); data['$Read_production_packages']['result']['packages'] = []
        self.assertFalse(evaluate(data)['verified'])

    def test_failed_pipeline_or_mismatched_release_or_image_blocks_verification(self):
        for reason in ['pipeline', 'release', 'image']:
            data = fixture()
            if reason == 'pipeline': data['$Read_release_runs']['result']['workflow_runs'][0]['conclusion'] = 'failure'
            if reason == 'release': data['$deploymentSnapshots']['production']['application_version'] = 'old-release'
            if reason == 'image': data['$productionRuntime']['image'] = 'registry/user@sha256:other'
            with self.subTest(reason=reason): self.assertFalse(evaluate(data)['verified'])

    def test_generated_workflow_has_no_write_actions_or_governance_settings(self):
        spec = importlib.util.spec_from_file_location('verification', HERE/'build-post-patch-verification-workflow.py')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        config = json.loads((HERE.parent/'openshift/remediation/verification-workflow-config.example.json').read_text())
        flow = builder.build(config)
        for block in flow['blocks']:
            if block.get('action'):
                self.assertEqual(next(p['value'] for p in block['inputs'] if p['name'] == 'method'), '"GET"')
        config_variable = next(v for v in flow['variables'] if v['name'] == 'config')
        self.assertNotIn('owners', json.loads(config_variable['value']))
        self.assertNotIn('sla_hours', json.loads(config_variable['value']))
        self.assertNotIn('ticket_connection_id', json.loads(config_variable['value']))

        retired = builder.retirement_notice()
        self.assertFalse(any(block.get('action') for block in retired['blocks']))
