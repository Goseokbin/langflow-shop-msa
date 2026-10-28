import importlib.util
import json
from pathlib import Path
import unittest
from patch_catalog import load_policies, resolve_branch

HERE=Path(__file__).parent
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,HERE/file)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
guard=module('generic_guard','verify-patch.py')
builder=module('generic_builder','build-two-env-patch-workflow.py')

class ReusablePolicyGuards(unittest.TestCase):
    def test_branch_must_match_exact_reviewed_policy(self):
        for name,p in load_policies().items():self.assertEqual(resolve_branch(p['branch'])[0],name)
        for branch in ['concert-patch/python-jose-unreviewed','main','concert-patch/../../other']:
            with self.assertRaises(ValueError):resolve_branch(branch)

    def test_extras_and_other_dependencies_are_preserved(self):
        old=guard.POLICY
        try:
            guard.POLICY=load_policies()['jose']
            before='python-jose[cryptography]==3.3.0\nother==1\n'
            after=before.replace('3.3.0','3.5.0')
            guard.validate_change(before,after,[guard.POLICY['file']])
            with self.assertRaises(ValueError):guard.validate_change(before,after.replace('[cryptography]',''),[guard.POLICY['file']])
            with self.assertRaises(ValueError):guard.validate_change(before,after.replace('other==1','other==2'),[guard.POLICY['file']])
        finally:guard.POLICY=old

    def test_single_flow_contains_all_selectable_policies_and_current_deployments(self):
        c={'repository':'demo/shop','concert_host':'concert.example.invalid','application_api':'/concert/core/api/v2/applications/app/versions/version','source_repo_id':'source','github_auth':'owner/github','concert_auth':'owner/concert','staging_environment_id':'stage','staging_deployment_id':'old-stage','production_environment_id':'prod','production_deployment_id':'old-prod','staging_deployment_prefix':'stage_','production_deployment_prefix':'prod_'}
        f=builder.build(c)
        selector=next(v for v in f['variables'] if v['name']=='policy_id')
        self.assertNotIn('enum',selector['type'])
        self.assertNotIn('policies',json.loads(next(v['value'] for v in f['variables'] if v['name']=='config')))
        self.assertTrue(selector['isInput'])
        blocks={b['name']:b for b in f['blocks']}
        self.assertIn('Select_latest_deployments',blocks)
        self.assertIn('Unknown approved policy',blocks['01_ValidatePolicy']['function'])
        self.assertIn('ReadPolicyCatalog',blocks)
        self.assertIn('/contents/scripts/remediation-policies.json',str(blocks['ReadPolicyCatalog']))
        self.assertNotIn('$02_ReadConcertFindings',blocks['05_AssessPatch']['function'])
        self.assertLess(list(blocks).index('Read_staging_cve_findings'),list(blocks).index('05_AssessPatch'))
