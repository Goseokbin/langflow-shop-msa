import copy
import json
from pathlib import Path
import tempfile
import unittest

from concert_internal_endpoints import API_PORTS, OTHER_PORTS, collect, compact_properties, enrich, parse_paths, verify_document


class EndpointInventoryTests(unittest.TestCase):
    def test_compaction_preserves_distinct_values_and_components(self):
        doc={'components':[{'name':'a','properties':[{'name':'commit','value':'old'},
             {'value':'old','name':'commit'},{'name':'commit','value':'new'}]}]}
        compact_properties(doc)
        self.assertEqual(doc['components'][0]['properties'],[{'name':'commit','value':'old'},{'name':'commit','value':'new'}])
        self.assertEqual(len(doc['components']),1)

    def test_methods_are_evidence_not_duplicate_paths(self):
        paths, operations = parse_paths({'openapi':'3.1.0','paths':{'/items/{id}':{'parameters':[], 'get':{},'patch':{}}}})
        self.assertEqual(paths, ['/items/{id}'])
        self.assertEqual({x['method'] for x in operations}, {'GET','PATCH'})

    def test_unresolved_or_empty_schema_does_not_silently_fall_back_to_host(self):
        for schema in [{'paths':{'/':{'get':{}}}}, {'openapi':'3.1.0','paths':{}},
                       {'openapi':'3.1.0','paths':{'/items':{'$ref':'other.json'}}},
                       {'openapi':'3.1.0','paths':{'https://outside.invalid/':{'get':{}}}}]:
            with self.subTest(schema=schema), self.assertRaises(ValueError):parse_paths(schema)

    def inventory(self, path):
        services=[{'metadata':{'name':n,'namespace':'shopping-mall'},'spec':{'ports':[{'port':p}]}}
                  for n,p in {**API_PORTS,**OTHER_PORTS}.items()]
        calls=[]
        def fetch(url):
            calls.append(url)
            return json.dumps({'openapi':'3.1.0','paths':{'/actual/{id}':{'get':{},'delete':{}}}}).encode()
        report=collect(services,path,fetch)
        self.assertEqual(len(calls),7)
        self.assertEqual(report['api_paths'],7)
        return report

    def test_internal_replacement_preserves_public_paths_refs_dependencies_and_base(self):
        with tempfile.TemporaryDirectory() as td:report=self.inventory(Path(td))
        doc={'services':[{'name':r['name'],'bom-ref':'stable:'+r['name'],'network_exposure':'private',
                          'base-url':r['base_url'],'port':r['port'],'endpoints':[r['base_url']]}
                         for r in report['services']], 'dependencies':[{'ref':'image:product','dependsOn':['stable:product-service']}]}
        public={'name':'product-public','network_exposure':'public','endpoints':['/external']}
        doc['services'].append(copy.deepcopy(public))
        deps=copy.deepcopy(doc['dependencies']);enrich(doc,report,True);once=copy.deepcopy(doc);enrich(doc,report,True)
        self.assertEqual(doc,once);self.assertEqual(doc['dependencies'],deps);self.assertEqual(doc['services'][-1],public)
        verify_document(doc,report,True)
        doc['services'][0]['endpoints']=['/stale']
        with self.assertRaises(ValueError):verify_document(doc,report,True)

    def test_missing_service_is_not_created_with_an_unrelated_identity(self):
        with tempfile.TemporaryDirectory() as td:report=self.inventory(Path(td))
        with self.assertRaises(ValueError):enrich({'services':[]},report)


if __name__=='__main__':unittest.main()
