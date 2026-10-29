import copy
import json
import unittest
from concert_source_metadata import migrate_repository,sync,strip,OWNED


class SourceMetadataTests(unittest.TestCase):
    def test_transfer_retargets_new_blueprint_code_without_rewriting_old_image_evidence(self):
        previous='https://github.com/Goseokbin/langflow-shop-msa'
        current='https://github.com/goseokbin-concert/langflow-shop-msa'
        template={'components':[{'name':'frontend','components':[
            {'type':'code','purl':previous+'.git','branch':'main'},
            {'type':'image','purl':'pkg:oci/frontend@sha256:abc','properties':[{'name':'source.repository','value':previous}]},
            {'type':'code','purl':'https://github.com/other/library','branch':'main'}]}]}
        blueprint=migrate_repository(copy.deepcopy(template),previous,current)
        children=blueprint['components'][0]['components']
        self.assertEqual(children[0]['purl'],current)
        self.assertEqual(children[1],template['components'][0]['components'][1])
        self.assertEqual(children[2],template['components'][0]['components'][2])
        self.assertEqual(template['components'][0]['components'][0]['purl'],previous+'.git')

    def test_repeated_collection_replaces_only_owned_properties_once(self):
        class API:
            def __init__(self):
                self.props=[{'name':'source.scope','value':'branch'}]*1000+[{'name':'team','value':'orders'}]
            def request(self,path,data=None,method=None,content_type=None):
                if method=='PATCH':
                    patch=json.loads(data)
                    if 'delete_properties' in patch:self.props=[p for p in self.props if p['name'] not in patch['delete_properties']]
                    self.props+=patch.get('properties',[])
                    return {}
                if path.startswith('/concert/core/api/v2/source_repos?'):
                    return {'source_repos':[{'id':'repo','repo_url':'https://github.com/demo/shop'}]}
                return {'instances':[{'id':'main','branch':'main','commit_sha':'','properties':copy.deepcopy(self.props)}]}
        api=API()
        for commit in ['a'*40,'b'*40]:
            result=sync(api,'https://github.com/demo/shop.git','main',commit)
            self.assertEqual(result['owned_properties'],2)
            self.assertEqual(len(api.props),3)
            self.assertIn({'name':'team','value':'orders'},api.props)
            self.assertIn({'name':'source.latest_scanned_commit','value':commit},api.props)
    def test_sbom_does_not_repeat_mutable_repository_properties(self):
        props=[{'name':'source.scope','value':'branch'},{'name':'team','value':'orders'}]
        doc={'components':[{'type':'code','purl':'https://github.com/demo/shop','properties':copy.deepcopy(props)},
                           {'type':'code','purl':'https://github.com/other/repo','properties':copy.deepcopy(props)},
                           {'type':'image','properties':[{'name':'source.git_commit','value':'a'*40}]}]}
        strip(doc,'https://github.com/demo/shop.git')
        self.assertEqual(doc['components'][0]['properties'],[{'name':'team','value':'orders'}])
        self.assertEqual(doc['components'][1]['properties'],props)
        self.assertEqual(doc['components'][2]['properties'],[{'name':'source.git_commit','value':'a'*40}])


if __name__=='__main__':unittest.main()
