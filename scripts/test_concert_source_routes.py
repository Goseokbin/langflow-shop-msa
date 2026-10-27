import importlib.util
import pathlib
import unittest

spec=importlib.util.spec_from_file_location('links',pathlib.Path(__file__).with_name('link-concert-source-routes.py'))
links=importlib.util.module_from_spec(spec);spec.loader.exec_module(links)

class ProvenanceTests(unittest.TestCase):
    def test_failed_build_never_proves_running_image(self):
        builds=[{'status':{'phase':'Failed','output':{'to':{'imageDigest':'sha256:test'}}}}]
        with self.assertRaises(ValueError):links.matched_build(builds,'sha256:test')
    def test_other_digest_never_matches(self):
        builds=[{'status':{'phase':'Complete','output':{'to':{'imageDigest':'sha256:old'}}}}]
        with self.assertRaises(ValueError):links.matched_build(builds,'sha256:running')
    def test_ambiguous_build_evidence_requires_review(self):
        build={'status':{'phase':'Complete','output':{'to':{'imageDigest':'sha256:running'}}}}
        with self.assertRaises(ValueError):links.matched_build([build,build],'sha256:running')
    def test_public_edge_preserves_internal_relations_and_is_repeatable(self):
        doc={'dependencies':[{'ref':'image:frontend','dependsOn':['service:frontend']},{'ref':'environment:test','dependsOn':['cluster:test']}]}
        for _ in range(2):links.merge_dependency(doc,'image:frontend','service:frontend-public')
        self.assertEqual(doc['dependencies'][0]['dependsOn'],['service:frontend','service:frontend-public'])
        self.assertEqual(doc['dependencies'][1]['dependsOn'],['cluster:test'])
    def test_generated_reports_do_not_invent_git_revision(self):
        root=pathlib.Path(__file__).resolve().parents[1]/'.runtime/source-route-links'
        if not root.exists():self.skipTest('local evidence unavailable')
        import json
        files=list(root.glob('*.build-evidence.json'));self.assertEqual(len(files),7)
        for file in files:
            doc=json.loads(file.read_text())
            self.assertNotIn('commit_sha',doc)
            self.assertEqual(doc['source.revision_status'],'not_recorded_in_binary_build')
            self.assertTrue(doc['image.digest'].startswith('sha256:'))
if __name__=='__main__':unittest.main()
