import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('workspace',Path(__file__).with_name('pipeline-workspace.py'))
workspace=importlib.util.module_from_spec(spec);spec.loader.exec_module(workspace)

class WorkspaceTests(unittest.TestCase):
    def test_transfer_preserves_snapshot_and_reports_but_excludes_credentials_and_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'original';work.mkdir();(work/'source').mkdir();(work/'source/a.py').write_text('print(1)')
            with tarfile.open(work/'source.tar.gz','w:gz') as tar:tar.add(work/'source/a.py',arcname='a.py')
            (work/'source-manifest.json').write_text(json.dumps({'archive_sha256':hashlib.sha256((work/'source.tar.gz').read_bytes()).hexdigest()}))
            (work/'output').mkdir();(work/'output/report.json').write_text('{"count":9}')
            (work/'authorization').write_text('credential-must-not-transfer');(work/'cache').mkdir();(work/'cache/private').write_text('cached')
            encrypted=root/'state.enc';workspace.seal(work,encrypted,'test-only-key-'*4)
            restored=root/'restored';workspace.restore(encrypted,restored,'test-only-key-'*4)
            self.assertEqual((restored/'source/a.py').read_text(),'print(1)')
            self.assertEqual((restored/'output/report.json').read_text(),'{"count":9}')
            self.assertFalse((restored/'authorization').exists());self.assertFalse((restored/'cache').exists())
            self.assertNotIn(b'credential-must-not-transfer',encrypted.read_bytes())
    def test_modified_ciphertext_is_rejected_before_extract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.enc';cipher=b'changed ciphertext'
            path.write_bytes(workspace.MAGIC+b'0'*32+cipher)
            with self.assertRaisesRegex(ValueError,'authentication failed'):workspace.restore(path,Path(tmp)/'out','test-only-key-'*4)
            self.assertFalse((Path(tmp)/'out').exists())

if __name__=='__main__':unittest.main()
