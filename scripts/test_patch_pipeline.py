import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('patch', pathlib.Path(__file__).with_name('verify-patch.py'))
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


class PatchGuards(unittest.TestCase):
    def test_exact_diff(self):
        old=patch.POLICY['package']+'=='+patch.POLICY['from_version']+'\n'
        new=patch.POLICY['package']+'=='+patch.POLICY['to_version']+'\n'
        patch.validate_change(old,new,[patch.POLICY['file']])
        for changed, after in [(['Dockerfile'],new),([patch.POLICY['file']],new+'extra==1\n')]:
            with self.assertRaises(ValueError):
                patch.validate_change(old,after,changed)

    def test_missing_inventory_is_not_success(self):
        with self.assertRaises(ValueError):
            patch.validate_scan({'Results': []})

    def test_scan_requires_version_and_cve_absence(self):
        doc = {'Results': [{'Packages': [{'Name':patch.POLICY['package'],'Version':patch.POLICY['to_version']}]}]}
        self.assertEqual(patch.validate_scan(doc)['version'],patch.POLICY['to_version'])
        doc['Results'][0]['Vulnerabilities'] = [{'PkgName':patch.POLICY['package'], 'VulnerabilityID': patch.POLICY['cves'][0]}]
        with self.assertRaises(ValueError):
            patch.validate_scan(doc)

    def test_source_gate_is_scoped_to_selected_service(self):
        p=patch.POLICY
        doc={'Results':[{'Target':str(pathlib.PurePosixPath(p['file']).relative_to('services')),'Packages':[{'Name':p['package'],'Version':p['to_version']}]},{'Target':'other-service/requirements.txt','Packages':[{'Name':p['package'],'Version':p['from_version']}],'Vulnerabilities':[{'PkgName':p['package'],'VulnerabilityID':p['cves'][0]}]}]}
        patch.validate_scan(doc,source=True)
        with self.assertRaises(ValueError):patch.validate_scan(doc)
        doc['Results'][0]['Vulnerabilities']=doc['Results'][1]['Vulnerabilities']
        with self.assertRaises(ValueError):patch.validate_scan(doc,source=True)
