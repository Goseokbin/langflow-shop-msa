"""Promotion must fail closed on digest replacement, missing checks and modified evidence."""
import copy
import hashlib
import importlib.util
import os
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

from promotion_bundle import ALL, image_references, seal, unseal, validate_release


def release():
    digest='sha256:'+'a'*64
    return {'schema_version':1,'commit':'b'*40,'run_id':'123','repository':'goseokbin-concert/langflow-shop-msa',
      'registry_host':'registry.example.com','images':[{'name':n,'source_image':'quay.io/demo/'+n+'@'+digest,'pull_image':'quay.io/demo/'+n+'@'+digest,'digest':digest} for n in sorted(ALL)],
      'deployments':{n:{'spec':{'template':{'spec':{'containers':[{'name':n,'env':[{'name':'JWT_SECRET_KEY','valueFrom':{'secretKeyRef':{'name':'jwt-secret','key':'JWT_SECRET_KEY'}}}]}]}}}} for n in ALL},
      'verification':{'commerce_passed':8,'internal_endpoints_verified':True}}


class PromotionPipelineTests(unittest.TestCase):
    def test_promotion_only_accepts_the_migrated_application_repository(self):
        validate_release(release())
        for repository in ['Goseokbin/langflow-shop-msa','goseokbin-concert/concert-remediation','another-owner/langflow-shop-msa']:
            candidate=release();candidate['repository']=repository
            with self.subTest(repository=repository),self.assertRaisesRegex(ValueError,'configured GitHub repository'):
                validate_release(candidate)

    def test_production_model_keeps_canonical_image_and_separates_environment(self):
        spec=importlib.util.spec_from_file_location('promote',Path(__file__).parent/'promote-release.py')
        promote=importlib.util.module_from_spec(spec);spec.loader.exec_module(promote)
        r=release();image=r['images'][0];name=image['name'];r.update(application_name='langflow-shop',application_version='1.0.0')
        r['deployment_sbom']={'metadata':{},'environment':{'name':'stage','bom-ref':'environment:stage'},
          'runtime-components':[{'bom-ref':'infra:cluster:stage','type':'kubernetes','name':'stage','components':[
            {'bom-ref':'infra:ns:stage','type':'namespace','name':'shopping-mall','components':[
             {'type':'deployment','name':name,'components':[{'type':'image','name':name,'uri':image['source_image']}]}]}]}],
          'services':[{'name':'internal','network_exposure':'private','properties':[{'name':'kubernetes.namespace','value':'shopping-mall'}]}],'dependencies':[{'ref':'environment:stage','dependsOn':['infra:cluster:stage']} ]}
        config={'CONCERT_ENVIRONMENT_NAME':'production','PRODUCTION_CLUSTER_NAME':'prod-cluster','PRODUCTION_CLUSTER_ID':'prod-id','PRODUCTION_SERVER':'https://prod'}
        with patch.dict(os.environ,{'GITHUB_RUN_ID':'123'}), patch.object(promote,'get',return_value={'spec':{'template':{'spec':{'containers':[{'name':name,'image':image['pull_image']}]}}}}):
            doc=promote.production_document(r,config,{'services':[]})
        self.assertEqual(doc['environment'],{'name':'production','bom-ref':'environment:production'})
        cluster=doc['runtime-components'][0]
        self.assertEqual(cluster['api-server'],'https://prod')
        self.assertEqual(doc['services'][0]['properties'],[{'name':'kubernetes.namespace','value':'shopping-mall-prod'}])
        self.assertEqual(doc['dependencies'][0]['dependsOn'],[cluster['bom-ref']])
        self.assertEqual(cluster['components'][0]['name'],'shopping-mall-prod')
        workload=cluster['components'][0]['components'][0]
        props={p['name']:p['value'] for p in workload['properties']}
        self.assertEqual(props['workload.type'],'k8s:Deployment')
        import json
        self.assertEqual(json.loads(props['metadata'])['containers'],[{'container':name,'image':image['pull_image']}])
        self.assertEqual(workload['components'][0]['uri'],image['source_image'])
        self.assertNotIn('properties',workload['components'][0],
                         'Concert CDEF rejects properties on image nodes')

    def test_docker_hub_alias_and_registry_port_have_one_scanner_identity(self):
        d='sha256:'+'a'*64
        row=image_references('docker.io/langflowai/langflow@'+d,'registry.example.com')
        self.assertEqual(row['source_image'],'langflowai/langflow@'+d)
        self.assertEqual(row['pull_image'],row['source_image'])
        internal='image-registry.openshift-image-registry.svc:5000/shopping-mall/api-gateway@'+d
        row=image_references(internal,'registry.example.com')
        self.assertEqual(row['source_image'],internal)
        self.assertEqual(row['pull_image'],'registry.example.com/shopping-mall/api-gateway@'+d)

    def test_authenticated_round_trip_and_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'release.enc';key='c'*64;original=release()
            digest=seal(original,path,key)
            self.assertEqual(unseal(path,digest,key),original)
            blob=bytearray(path.read_bytes());blob[-1]^=1;path.write_bytes(blob)
            with self.assertRaisesRegex(ValueError,'hash differs'):unseal(path,digest,key)
            with self.assertRaisesRegex(ValueError,'authentication failed'):unseal(path,hashlib.sha256(blob).hexdigest(),key)
    def test_additional_catalog_checks_do_not_invalidate_verified_commerce(self):
        r=release();r['verification']['commerce_passed']=9
        validate_release(r)

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
