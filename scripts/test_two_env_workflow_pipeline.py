import importlib.util
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('two_env_builder',Path(__file__).with_name('build-two-env-patch-workflow.py'))
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class RuntimeEvidenceQueries(unittest.TestCase):
    def test_active_artifact_groups_are_not_filtered_out_as_uncorrelated(self):
        config={'repository':'demo/shop','concert_host':'concert.example.invalid','application_api':'/concert/core/api/v2/applications/app/versions/version','source_repo_id':'source','github_auth':'owner/github','concert_auth':'owner/concert','staging_environment_id':'staging','staging_deployment_id':'staging-current','production_environment_id':'production','production_deployment_id':'production-current'}
        flow=builder.build(config)
        queries={b['name']:json.loads(next(i['value'] for i in b['inputs'] if i['name']=='query')) for b in flow['blocks'] if b.get('name') in ['Read_build_artifacts','Read_image_instances','Read_staging_packages','Read_production_cve_findings']}
        self.assertNotIn('uncorrelated',queries['Read_build_artifacts'])
        self.assertNotIn('uncorrelated',queries['Read_image_instances'])
        self.assertTrue(queries['Read_staging_packages']['uncorrelated'])
        self.assertTrue(queries['Read_production_cve_findings']['uncorrelated'])
