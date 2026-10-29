import json,tempfile,unittest
from pathlib import Path
from semantic_release import load_release,verify_remediation
class SemanticReleaseTests(unittest.TestCase):
    def test_release_cannot_omit_patch_scope(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'release.json';p.write_text(json.dumps({'version':'1.0.1','remediation_policy':None}))
            with self.assertRaises(ValueError):load_release(p)
    def test_real_source_and_image_inventory_required(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'release.json').write_text(json.dumps({'version':'1.0.1','remediation_policy':'multipart-cart'}))
            (p/'source-scan.json').write_text(json.dumps({'name':'repository','file':'repository.cdx.json'}))
            (p/'image-scans.json').write_text(json.dumps([{'name':'cart-service','file':'cart-service.cdx.json'}]))
            row={'Target':'cart-service/requirements.txt','Packages':[{'Name':'python-multipart','Version':'0.0.32'}]}
            for n in ['repository.cdx.json','cart-service.cdx.json']:(p/n).write_text(json.dumps({'bomFormat':'CycloneDX','components':[]}))
            for n in ['repository.trivy.json','cart-service.trivy.json']:(p/n).write_text(json.dumps({'Results':[row]}))
            self.assertTrue(verify_remediation(p/'release.json',p)['passed'])
            row['Vulnerabilities']=[{'PkgName':'python-multipart','VulnerabilityID':'CVE-2024-53981'}]
            (p/'cart-service.trivy.json').write_text(json.dumps({'Results':[row]}))
            with self.assertRaises(ValueError):verify_remediation(p/'release.json',p)
            (p/'cart-service.trivy.json').write_text(json.dumps({'Results':[]}))
            with self.assertRaises(ValueError):verify_remediation(p/'release.json',p)
