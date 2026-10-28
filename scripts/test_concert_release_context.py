import json
import pathlib
import tempfile
import unittest
from concert_release_context import configure,release_version,validate_application_api,blueprint_matches

class ImmutableReleaseTests(unittest.TestCase):
    template='/concert/core/api/v2/applications/1199cceb-e68f-4f6f-a96c-b9bffa0b7431/versions/a6b8821f-b02b-4417-b91e-d3831aea377a'
    def test_each_commit_has_a_different_release(self):
        self.assertNotEqual(release_version('a'*40),release_version('b'*40))
        with self.assertRaises(ValueError):release_version('main')
    def test_artifact_cannot_redirect_to_another_application(self):
        self.assertEqual(validate_application_api(self.template,self.template),self.template)
        with self.assertRaises(ValueError):validate_application_api(self.template.replace('1199cceb','00000000'),self.template)
    def test_resume_rejects_context_for_another_commit(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'context.json';p.write_text(json.dumps({'commit':'a'*40,'version':release_version('a'*40),'application_api':self.template}))
            with self.assertRaises(ValueError):configure(None,self.template,{'git_base_commit':'b'*40},p)
    def test_existing_release_does_not_create_a_new_blueprint(self):
        class Client:
            def request(self,path):return {'pagination':{'total_count':1},'versions':[{'version':release_version('a'*40),'id':'a6b8821f-b02b-4417-b91e-d3831aea377a'}]}
        with tempfile.TemporaryDirectory() as td:
            r=configure(Client(),self.template,{'git_base_commit':'a'*40},pathlib.Path(td)/'context.json')
            self.assertEqual(r['application_api'],self.template)

    def test_readback_allows_only_known_derived_repository_component(self):
        import copy
        code={'type':'code','name':'shop','purl':'https://github.com/owner/shop','branch':'main'}
        expected={'components':[{'name':'user-service','components':[code]}],'services':[]}
        observed=copy.deepcopy(expected);observed['components'].append({'name':code['purl'],'components':[code]})
        self.assertTrue(blueprint_matches(observed,expected))
        observed['components'][-1]['name']='unrelated'
        self.assertFalse(blueprint_matches(observed,expected))
        self.assertFalse(blueprint_matches({'components':[],'services':[]},expected))
