"""Promotion must fail closed on digest replacement, missing checks and modified evidence."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from promotion_bundle import ALL, seal, unseal, validate_release


def release():
    digest='sha256:'+'a'*64
    return {'schema_version':1,'commit':'b'*40,'run_id':'123','repository':'Goseokbin/langflow-shop-msa',
      'registry_host':'registry.example.com','images':[{'name':n,'source_image':'quay.io/demo/'+n+'@'+digest,'pull_image':'quay.io/demo/'+n+'@'+digest,'digest':digest} for n in sorted(ALL)],
      'deployments':{n:{'spec':{'template':{'spec':{'containers':[{'name':n,'env':[{'name':'JWT_SECRET_KEY','valueFrom':{'secretKeyRef':{'name':'jwt-secret','key':'JWT_SECRET_KEY'}}}]}]}}}} for n in ALL},
      'verification':{'commerce_passed':8,'internal_endpoints_verified':True}}


class PromotionPipelineTests(unittest.TestCase):
    def test_authenticated_round_trip_and_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'release.enc';key='c'*64;original=release()
            digest=seal(original,path,key)
            self.assertEqual(unseal(path,digest,key),original)
            blob=bytearray(path.read_bytes());blob[-1]^=1;path.write_bytes(blob)
            with self.assertRaisesRegex(ValueError,'hash differs'):unseal(path,digest,key)
            with self.assertRaisesRegex(ValueError,'authentication failed'):unseal(path,hashlib.sha256(blob).hexdigest(),key)
    def test_unverified_or_substituted_images_rejected(self):
        for change in ['digest','checks','missing','secret','hostpath']:
            r=release()
            if change=='digest':r['images'][0]['pull_image']=r['images'][0]['pull_image'].replace('a'*64,'d'*64)
            if change=='checks':r['verification']['commerce_passed']=7
            if change=='missing':r['images'].pop()
            p=next(iter(r['deployments'].values()))['spec']['template']['spec']
            if change=='secret':p['containers'][0]['env'][0]={'name':'JWT_SECRET_KEY','value':'do-not-export'}
            if change=='hostpath':p['volumes']=[{'hostPath':{'path':'/'}}]
            with self.subTest(change=change),self.assertRaises(ValueError):validate_release(r)
    def test_external_registry_alias_requires_same_repository_and_digest(self):
        r=release();row=r['images'][0];d=row['digest']
        row['source_image']='image-registry.openshift-image-registry.svc:5000/shopping-mall/api-gateway@'+d
        row['pull_image']='registry.example.com/shopping-mall/api-gateway@'+d
        validate_release(r)
        row['pull_image']='registry.example.com/another-team/api-gateway@'+d
        with self.assertRaises(ValueError):validate_release(r)


if __name__=='__main__':unittest.main()
