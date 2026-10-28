import json
import pathlib
import tempfile
import unittest
from concert_release_context import configure,release_version,validate_application_api,blueprint_matches,wait_for_blueprint

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

    def test_new_release_does_not_reingest_repeated_mutable_source_properties(self):
        import copy
        version=release_version('a'*40);new_id='479fd085-6582-48a6-8d6a-a1e7501b94b7'
        template=self.template
        class API:
            uploaded=None
            def request(self,path,data=None,method=None,content_type=None):
                if 'advanced_search' in path:
                    return {'toc_records':[{'status':'processing_in_progress','metadata':[{'name':'component_api_result','value':json.dumps({'status':{'code':201,'message_code':'processSbomSuccessMsg'},'result':{'release_id':new_id}})}]}]}
                if path.endswith('/versions?page_size=2000'):
                    return {'pagination':{'total_count':bool(self.uploaded)},'versions':[{'version':version,'id':new_id}] if self.uploaded else []}
                if path==template+'/sbom':
                    return {'metadata':{'application-name':'shop','application-version':'1.0.0'},'components':[{'name':'user-service','components':[{'type':'code','name':'shop','purl':'https://github.com/demo/shop','properties':[{'name':'source.scope','value':'branch'}]*10000+[{'name':'team','value':'orders'}]*10}]}],'services':[]}
                return copy.deepcopy(self.uploaded)
            def upload(self,path,kind,metadata):
                self.uploaded=json.loads(path.read_text());return {'event_ids':['event']}
        api=API()
        with tempfile.TemporaryDirectory() as td:
            configure(api,template,{'git_base_commit':'a'*40,'repository':'https://github.com/demo/shop'},pathlib.Path(td)/'context.json')
        props=api.uploaded['components'][0]['components'][0]['properties']
        self.assertEqual(props,[{'name':'team','value':'orders'}])

    def test_accepted_request_or_mismatched_readback_is_not_completion(self):
        class API:
            def request(self,*args,**kwargs):return {'toc_records':[{'status':'processing_in_progress','metadata':[]}]}
        with self.assertRaises(ValueError):
            wait_for_blueprint(API(),{'event_ids':['event']},self.template,'1.0.1',{},timeout=0)
