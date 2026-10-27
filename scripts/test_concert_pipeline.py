import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('api',ROOT/'scripts/concert-audit-api.py')
api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)

class IngestionBoundaryTests(unittest.TestCase):
    def upload(self, doc, metadata):
        client=api.Concert.__new__(api.Concert)
        client.request=lambda *args: {'accepted':True}
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'source.json';p.write_text(json.dumps(doc))
            return client.upload(p,'package_sbom',metadata)
    def test_repository_sbom_is_not_treated_as_an_image(self):
        doc={'bomFormat':'CycloneDX','metadata':{'component':{'name':'langflow-shop'}}}
        self.assertTrue(self.upload(doc,{'repo_url':'https://github.ibm.com/seokbin/langflow-shop','repo_name':'langflow-shop','component_type':'repository'})['accepted'])
    def test_repository_upload_cannot_relabel_an_image_scan(self):
        doc={'bomFormat':'CycloneDX','metadata':{'component':{'name':'langflow-shop'}}}
        with self.assertRaises(ValueError):self.upload(doc,{'repo_url':'https://github.ibm.com/seokbin/langflow-shop','repo_name':'langflow-shop','image_name':'registry/image'})
    def test_source_root_mismatch_is_rejected_before_upload(self):
        doc={'bomFormat':'CycloneDX','metadata':{'component':{'name':'other'}}}
        with self.assertRaises(ValueError):self.upload(doc,{'repo_url':'https://github.ibm.com/seokbin/langflow-shop','repo_name':'langflow-shop'})
    def test_deployment_waits_for_successful_ingestion(self):
        file=ROOT/'openshift/pipelines/langflow-shop-devsecops.json'
        if not file.exists():self.skipTest('pipeline manifest not generated')
        pipeline=next(x for x in json.loads(file.read_text())['items'] if x['kind']=='Pipeline')
        tasks={t['name']:t for t in pipeline['spec']['tasks']}
        self.assertEqual(tasks['deploy']['runAfter'],['concert-ingest'])
        self.assertEqual(tasks['link-verify']['runAfter'],['deploy'])
        self.assertNotIn('when',tasks['concert-ingest'])

if __name__=='__main__':unittest.main()
