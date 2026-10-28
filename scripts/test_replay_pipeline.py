"""Retrying ingestion preserves findings/identities while avoiding Concert CDX replay rejection."""
import copy
from email.parser import BytesParser
from email.policy import default
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('CONCERT_HOST','unused.invalid')
os.environ.setdefault('CONCERT_APP_API','/unused')
spec=importlib.util.spec_from_file_location('audit',Path(__file__).parent/'concert-audit-api.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class ReplayPipelineTests(unittest.TestCase):
    def test_replay_and_separate_scan_types_get_new_documents_without_relabeling(self):
        original={'bomFormat':'CycloneDX','specVersion':'1.5','serialNumber':'urn:uuid:old','version':1,
          'metadata':{'component':{'name':'shop','bom-ref':'repo:shop'}},
          'components':[{'name':'requests','bom-ref':'pkg:pypi/requests@2.33.0','purl':'pkg:pypi/requests@2.33.0'}],
          'dependencies':[{'ref':'repo:shop','dependsOn':['pkg:pypi/requests@2.33.0']}],
          'vulnerabilities':[{'id':'CVE-demo','affects':[{'ref':'pkg:pypi/requests@2.33.0'}]}]}
        submitted=[]
        client=object.__new__(audit.Concert)
        def request(path,data,method,content_type):
            message=BytesParser(policy=default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+data)
            part=next(p for p in message.iter_parts() if p.get_param('name',header='content-disposition')=='filename')
            submitted.append(json.loads(part.get_payload(decode=True)))
            return {'event_ids':['event']}
        client.request=request
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'repo.json';path.write_text(json.dumps(original))
            for typ in ['package_sbom','code_scan','package_sbom']:
                result=client.upload(path,typ,{'repo_url':'https://github.com/demo/shop','repo_name':'shop'})
                self.assertEqual(result['submitted_sbom_serial_number'],submitted[-1]['serialNumber'])
            self.assertEqual(json.loads(path.read_text()),original)
        self.assertEqual(len({x['serialNumber'] for x in submitted}),3)
        for doc in submitted:
            normalized=copy.deepcopy(doc);normalized['serialNumber']=original['serialNumber']
            self.assertEqual(normalized,original)


if __name__=='__main__':unittest.main()
