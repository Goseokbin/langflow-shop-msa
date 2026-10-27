import json
import pathlib
import unittest
from concert_image_identity import identity, normalize_sbom, select_artifact

D = 'sha256:' + 'a' * 64
class IdentityTests(unittest.TestCase):
    def test_registry_port_and_tag(self):
        self.assertEqual(identity('registry.local:5000/team/image:v1@' + D), ('registry.local:5000/team/image', D))
    def test_docker_hub_aliases(self):
        for prefix in ('', 'docker.io/', 'index.docker.io/', 'registry-1.docker.io/'):
            self.assertEqual(identity(prefix + 'langflowai/langflow', D), ('langflowai/langflow', D))
    def test_same_digest_different_repository_does_not_match(self):
        with self.assertRaises(ValueError):
            select_artifact([{'name': 'other/image', 'digest': D, 'id': 'wrong'}], 'team/image', D)
    def test_malformed_alias_cannot_win(self):
        arts = [{'name': 'image-registry.openshift-image-registry.svc', 'digest': D, 'id': 'bad'},
                {'name': 'registry.local:5000/team/image', 'digest': D, 'id': 'good'}]
        self.assertEqual(select_artifact(arts, 'registry.local:5000/team/image', D)['id'], 'good')
    def test_ambiguous_aliases_fail(self):
        arts = [{'name': p + 'team/image', 'digest': D, 'id': p} for p in ('docker.io/', 'index.docker.io/')]
        with self.assertRaises(ValueError): select_artifact(arts, 'team/image', D)
    def test_report_preserves_package_and_vulnerability_references(self):
        src = {'bomFormat':'CycloneDX', 'metadata':{'component':{'name':'old','bom-ref':'root'}},
               'components':[{'bom-ref':'pkg:pypi/a@1','purl':'pkg:pypi/a@1'}],
               'dependencies':[{'ref':'root','dependsOn':['pkg:pypi/a@1']}],
               'vulnerabilities':[{'id':'CVE-TEST','affects':[{'ref':'pkg:pypi/a@1'}]}]}
        result = normalize_sbom(src, 'registry.local:5000/team/image', D)
        self.assertEqual(result['dependencies'][0]['ref'],result['metadata']['component']['bom-ref'])
        self.assertEqual(result['components'],src['components'])
        self.assertEqual(result['vulnerabilities'],src['vulnerabilities'])
        self.assertNotEqual(result['serialNumber'],normalize_sbom(src, 'team/image', D)['serialNumber'])
    def test_all_nine_real_reports_keep_inventory_and_findings(self):
        out=pathlib.Path(__file__).resolve().parents[1]/'.runtime/image-scans'
        if not (out/'summary.json').exists(): self.skipTest('local scan evidence not available')
        summary=json.loads((out/'summary.json').read_text())
        self.assertEqual(len(summary),9)
        for entry in summary:
            src=json.loads((out/(entry['name']+'.cdx.json')).read_text())
            repo,digest=identity(entry['image']); dest=normalize_sbom(src,repo,digest)
            self.assertEqual(dest.get('components'),src.get('components'))
            self.assertEqual(dest.get('vulnerabilities'),src.get('vulnerabilities'))
    def test_raw_trivy_rejected(self):
        with self.assertRaises(ValueError): normalize_sbom({'ArtifactName':'image'},'team/image',D)
if __name__ == '__main__': unittest.main()
