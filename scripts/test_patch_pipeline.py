import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('patch', pathlib.Path(__file__).with_name('verify-patch.py'))
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


class PatchGuards(unittest.TestCase):
    def test_exact_diff(self):
        patch.validate_change('requests==2.31.0\n', 'requests==2.33.0\n', [patch.POLICY['file']])
        for changed, after in [(['Dockerfile'], 'requests==2.33.0\n'),
                               ([patch.POLICY['file']], 'requests==2.33.0\nextra==1\n')]:
            with self.assertRaises(ValueError):
                patch.validate_change('requests==2.31.0\n', after, changed)

    def test_missing_inventory_is_not_success(self):
        with self.assertRaises(ValueError):
            patch.validate_scan({'Results': []})

    def test_scan_requires_version_and_cve_absence(self):
        doc = {'Results': [{'Packages': [{'Name': 'requests', 'Version': '2.33.0'}]}]}
        self.assertEqual(patch.validate_scan(doc)['version'], '2.33.0')
        doc['Results'][0]['Vulnerabilities'] = [{'PkgName': 'requests', 'VulnerabilityID': patch.POLICY['cves'][0]}]
        with self.assertRaises(ValueError):
            patch.validate_scan(doc)
