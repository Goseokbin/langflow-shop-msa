import copy
import json
import unittest
from concert_source_metadata import sync,strip,OWNED


class SourceMetadataTests(unittest.TestCase):
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
