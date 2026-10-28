#!/usr/bin/env python3
"""Activate a staging-verified release only inside the protected production job."""
import argparse
import copy
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from promotion_bundle import ALL, unseal
from concert_image_identity import identity, select_artifact
from concert_internal_endpoints import collect, compact_properties, enrich, verify_document

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.runtime/production'
NS='shopping-mall-prod'


def oc(*args,data=None):
    return subprocess.check_output(['oc',*args],input=json.dumps(data).encode() if data is not None else None).decode().strip()


def get(kind,name=None):
    args=['get',kind]+([name] if name else [])+['-n',NS,'-o','json']
    return json.loads(oc(*args))


def patch(name,value):
    oc('patch','deployment',name,'-n',NS,'--type=merge','--patch-file=/dev/stdin',data=value)


def wait(name):
    oc('rollout','status','deployment/'+name,'-n',NS,'--timeout=600s')
    print('Ready: '+name,flush=True)


def verify_images(release):
    rows=[]
    for image in release['images']:
        d=get('deployment',image['name'])
        actual=d['spec']['template']['spec']['containers'][0]['image']
        if actual!=image['pull_image'] or d['status'].get('readyReplicas',0)!=1:
            raise ValueError('Production image/readiness mismatch: '+image['name'])
        rows.append({'name':image['name'],'digest':image['digest'],'same_as_staging':True,'ready':True})
    return rows


def database_bootstrap(release):
    name='initialize-databases-'+os.environ['GITHUB_RUN_ID'][-12:]+'-'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
    image=next(r['pull_image'] for r in release['images'] if r['name']=='postgresql')
    command='''set -eu
for db in product_db cart_db order_db; do
  exists=$(psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'")
  if [ "$exists" != "1" ]; then createdb -O shop "$db"; fi
done
'''
    job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name,'namespace':NS},'spec':{
      'backoffLimit':1,'activeDeadlineSeconds':180,'ttlSecondsAfterFinished':86400,
      'template':{'spec':{'restartPolicy':'Never','serviceAccountName':'shop-runtime','automountServiceAccountToken':False,
        'imagePullSecrets':[{'name':'release-registry'}], 'containers':[{'name':'initialize','image':image,
        'command':['sh','-c',command], 'env':[{'name':'PGHOST','value':'postgresql'},{'name':'PGUSER','value':'postgres'},
        {'name':'PGPASSWORD','valueFrom':{'secretKeyRef':{'name':'postgres-secrets','key':'POSTGRES_ADMIN_PASSWORD'}}}],
        'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}}}]}}}}
    oc('create','-f','-',data=job)
    oc('wait','--for=condition=complete','job/'+name,'-n',NS,'--timeout=240s')
    print('Independent production databases initialized',flush=True)


def production_document(release,config,inventory):
    doc=compact_properties(copy.deepcopy(release['deployment_sbom']))
    doc['metadata'].update({'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'deploy-name':'deploy_'+config['CONCERT_ENVIRONMENT_NAME']+'_'+release['application_name']+'_'+release['application_version'],
      'application-name':release['application_name'],'application-version':release['application_version']})
    mapping={}
    def unique(value):
        if isinstance(value,dict):
            ref=value.get('bom-ref')
            if ref and ref.startswith('infra:'):mapping[ref]=ref+':production'
            for x in value.values():unique(x)
        elif isinstance(value,list):
            for x in value:unique(x)
    unique(doc.get('runtime-components',[]))
    old_env=[d['ref'] for d in doc['dependencies'] if d['ref'].startswith('environment:')]
    for ref in old_env:mapping[ref]='environment:'+config['CONCERT_ENVIRONMENT_NAME']
    def remap(value):
        if isinstance(value,dict):
            for k,v in list(value.items()):value[k]=remap(v)
        elif isinstance(value,list):return [remap(x) for x in value]
        elif isinstance(value,str):return mapping.get(value,value)
        return value
    remap(doc)
    doc['environment']['name']=config['CONCERT_ENVIRONMENT_NAME']
    images={r['name']:r for r in release['images']}
    def update(value):
        if isinstance(value,dict):
            typ=value.get('type');name=value.get('name')
            if typ=='kubernetes':
                value['name']=config['PRODUCTION_CLUSTER_NAME'];value['api-server']=config['PRODUCTION_SERVER']
                value['properties']=[{'name':'cluster_id','value':config['PRODUCTION_CLUSTER_ID']},{'name':'cluster_name','value':config['PRODUCTION_CLUSTER_NAME']},{'name':'platform','value':'ocp'}]
            elif typ=='namespace':value['name']=NS;value['properties']=[]
            elif typ=='deployment' and name in images:
                actual=get('deployment',name)
                value['properties']=[{'name':'workload.type','value':'k8s:Deployment'},
                  {'name':'metadata','value':json.dumps({'containers':[{'container':c['name'],'image':c['image']} for c in actual['spec']['template']['spec']['containers']]})},
                  {'name':'source.commit','value':release['commit']},{'name':'promotion.run','value':os.environ['GITHUB_RUN_ID']},
                  {'name':'runtime.image.pull_reference','value':images[name]['pull_image']},
                  {'name':'promotion.verified_digest','value':images[name]['digest']}]
            elif typ=='image' and name in images:
                value['uri']=images[name]['source_image']
                # CDEF image nodes allow uri, not properties. Evidence belongs to the workload.
                value.pop('properties',None)
            for k,x in list(value.items()):
                if k not in ['properties']:update(x)
        elif isinstance(value,list):
            for x in value:update(x)
    update(doc['runtime-components'])
    enrich(doc,inventory,deployment=True)
    for service in doc.get('services',[]):
        service['properties']=[p for p in service.get('properties',[]) if p['name']!='kubernetes.namespace']+[{'name':'kubernetes.namespace','value':NS}]
        if service.get('network_exposure')=='public':
            route_name=service['name'].removesuffix('-public')
            route=get('route',route_name)
            service['base-url']='https://'+route['spec']['host']
    return compact_properties(doc)


def main(args):
    if os.environ.get('DEPLOYMENT_TIER')!='production':raise ValueError('This command requires the protected production job')
    release=unseal(args.release,args.expected_sha256,os.environ['PROMOTION_STATE_KEY'])
    source_commit=args.source_commit or os.environ['GITHUB_SHA']
    source_run=args.source_run or os.environ['GITHUB_RUN_ID']
    if release['commit']!=source_commit or release['run_id']!=source_run:
        raise ValueError('Release belongs to another commit/run')
    config=get('configmap','langflow-shop-pipeline-config')['data']
    if release.get('concert_application_api'):
        from concert_release_context import validate_application_api
        config['CONCERT_APP_API']=validate_application_api(release['concert_application_api'],config['CONCERT_APP_API'])
    server=oc('whoami','--show-server')
    if server!=config['PRODUCTION_SERVER'] or server==release['source_server']:raise ValueError('Wrong production cluster')
    for row in release['images']:
        d=get('deployment',row['name'])
        if d['metadata'].get('labels',{}).get('app.kubernetes.io/managed-by')!='langflow-shop-promotion':
            raise ValueError('Production workload was not prepared for promotion')
    OUT.mkdir(parents=True,exist_ok=True)
    # Only image references and promotion evidence change; production Secret/PVC references stay independent.
    for row in release['images']:
        patch(row['name'],{'spec':{'template':{'metadata':{'annotations':{
            'langflow-shop.dev/promoted-commit':release['commit'],'langflow-shop.dev/source-run':release['run_id']}},
            'spec':{'containers':[dict(get('deployment',row['name'])['spec']['template']['spec']['containers'][0],image=row['pull_image'])]}}}})
    patch('postgresql',{'spec':{'replicas':1}});wait('postgresql');database_bootstrap(release)
    patch('langflow',{'spec':{'replicas':1}});wait('langflow')
    subprocess.run([sys.executable,str(ROOT/'scripts/configure-langflow.py'),'--configure-only'],check=True,env={**os.environ,'SHOP_NAMESPACE':NS})
    for name in sorted(ALL-{'postgresql','langflow'}):patch(name,{'spec':{'replicas':1}})
    for name in sorted(ALL-{'postgresql','langflow'}):wait(name)
    rows=verify_images(release)
    result=subprocess.check_output([sys.executable,str(ROOT/'scripts/smoke-test.py')],env={**os.environ,'SHOP_NAMESPACE':NS})
    smoke=json.loads(result);assert len(smoke['results'])==8
    inventory=collect(get('services')['items'],OUT/'openapi',namespace=NS)
    os.environ.update(CONCERT_HOST=config['CONCERT_HOST'],CONCERT_APP_API=config['CONCERT_APP_API'])
    spec=importlib.util.spec_from_file_location('audit',ROOT/'scripts/concert-audit-api.py');api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
    auth=OUT/'authorization';auth.touch(mode=0o600);auth.chmod(0o600);auth.write_text(os.environ['CONCERT_AUTH_HEADER'])
    try:
        client=api.Concert(authorization=auth);doc=production_document(release,config,inventory)
        path=OUT/'deployment.cdef.json';path.write_text(json.dumps(doc))
        response=client.upload(path,'application_sbom',{});client.wait_for_upload(response)
        env_api='/concert/core/api/v2/environments/'+config['CONCERT_ENVIRONMENT_ID']
        deployments=client.request(env_api+'/deployments?page_size=2000')['deployments']
        matches=[d for d in deployments if d['name']==doc['metadata']['deploy-name']]
        if len(matches)!=1:raise ValueError('Production deployment identity was not uniquely created')
        dep_id=matches[0]['id'];observed=client.request(env_api+'/deployments/'+dep_id+'/sbom')
        verify_document(observed,inventory,deployment=True)
        oc('patch','configmap','langflow-shop-pipeline-config','-n',NS,'--type=merge','--patch-file=/dev/stdin',data={'data':{'CONCERT_DEPLOYMENT_ID':dep_id,'CONCERT_APP_API':config['CONCERT_APP_API'],'APPLICATION_VERSION':release['application_version']}})
        artifacts=client.request(api.APP+'/build_artifacts?page_size=2000')['build_artifacts']
        artifact_checks=[]
        for image in release['images']:
            repo,digest=identity(image['source_image'])
            artifact=select_artifact(artifacts,repo,digest)
            root=api.APP+'/build_artifacts/'+artifact['id']
            packages=client.request(root+'/packages?page_size=1')['pagination']['total_count']
            cves=client.request(root+'/cve_findings?page_size=1')['pagination']['total_count']
            if not packages:raise ValueError('Promoted artifact has no package inventory: '+image['name'])
            artifact_checks.append({'name':image['name'],'artifact_id':artifact['id'],'packages':packages,'cves':cves})
        runtime_images=[]
        def walk(value):
            if isinstance(value,dict):
                if value.get('type')=='image':runtime_images.append(value['uri'])
                for child in value.values():walk(child)
            elif isinstance(value,list):
                for child in value:walk(child)
        walk(observed.get('runtime-components',[]))
        if {identity(x) for x in runtime_images}!={identity(x['source_image']) for x in release['images']}:
            raise ValueError('Concert production runtime images differ from the verified release')
        report={'commit':release['commit'],'source_run':release['run_id'],'release_sha256':args.expected_sha256,
            'images':rows,'concert_artifacts':artifact_checks,'commerce_checks':len(smoke['results']),'internal_api_paths':inventory['api_paths'],
            'concert_environment_id':config['CONCERT_ENVIRONMENT_ID'],'concert_deployment_id':dep_id,
            'frontend':'https://'+get('route','frontend')['spec']['host'],'model_inference':'not tested; requires a production model credential and available credits'}
        (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        summary='## 11 · 승인 후 동일 이미지 운영 배포\n\n검증과 동일한 이미지 9개, 기능 검사 8개, 내부 API 경로 '+str(inventory['api_paths'])+'개 확인.\n\n[운영 쇼핑몰]('+report['frontend']+')\n\n| 서비스 | 검증·운영 동일 digest |\n| --- | --- |\n'+'\n'.join('| '+r['name']+' | `'+r['digest']+'` |' for r in rows)+'\n'
        if os.environ.get('GITHUB_STEP_SUMMARY'):Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(summary)
        print(json.dumps(report,ensure_ascii=False))
    finally:auth.unlink(missing_ok=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--expected-sha256',required=True)
    p.add_argument('--source-commit',help='Verified original build commit for deployment-only recovery')
    p.add_argument('--source-run',help='Verified original build run for deployment-only recovery')
    main(p.parse_args())
