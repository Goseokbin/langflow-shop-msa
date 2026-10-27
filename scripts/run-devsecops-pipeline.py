#!/usr/bin/env python3
"""Install and start the real OpenShift Tekton pipeline from a frozen workspace.

The local launch is one command. All scan/build/ingest/deploy/link stages execute
in OpenShift. For push-triggered execution, use the supplied GitHub workflow.
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import os
import subprocess
import tarfile
import time

ROOT=pathlib.Path(__file__).resolve().parents[1]
NS='shopping-mall';SA='langflow-shop-pipeline';PVC='langflow-shop-pipeline-workspace'


def oc(*args,data=None):
    return subprocess.check_output(['oc',*args],input=json.dumps(data) if data is not None else None,text=True).strip()


def obj(kind,name,**values):
    return {'apiVersion':'v1','kind':kind,'metadata':{'name':name,'namespace':NS},**values}


def main():
    p=argparse.ArgumentParser();p.add_argument('--authorization-file',type=pathlib.Path);p.add_argument('--start-only',action='store_true');p.add_argument('--wait-for-idle',action='store_true');p.add_argument('--wait',action='store_true');p.add_argument('--timeout',type=int,default=3600);a=p.parse_args()
    if not a.start_only and not a.authorization_file:p.error('--authorization-file is required for installation')
    idle_deadline=time.monotonic()+1800
    while True:
        runs=json.loads(oc('get','pipelineruns','-n',NS,'-l','app=langflow-shop-devsecops','-o','json'))['items']
        if not any(not r.get('status',{}).get('completionTime') for r in runs):break
        if not a.wait_for_idle or time.monotonic()>idle_deadline:raise RuntimeError('Another PipelineRun is active; shared workspace is locked')
        print('Waiting for the previous PipelineRun to release the workspace',flush=True);time.sleep(10)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S');run_id='langflow-shop-'+stamp
    local=ROOT/'.runtime/pipeline-runs'/run_id;local.mkdir(parents=True)
    # Freeze only regular project files. No credentials, caches, Git internals or symlinks.
    archive=local/'source.tar.gz'
    excluded={'.git','.runtime','node_modules','.next','__pycache__','.DS_Store','captures','.venv','venv'}
    with tarfile.open(archive,'w:gz') as tar:
        for path in sorted(ROOT.rglob('*')):
            rel=path.relative_to(ROOT)
            if any(part in excluded for part in rel.parts) or path.name.startswith('.env') or not path.is_file() or path.is_symlink():continue
            tar.add(path,arcname='src/'+rel.as_posix(),recursive=False)
    manifest={'run_id':run_id,'repository':oc_git('remote','get-url','origin').removesuffix('.git'),'branch':oc_git('branch','--show-current'),
              'repo_name':oc_git('remote','get-url','origin').removesuffix('.git').rstrip('/').split('/')[-1],'git_base_commit':oc_git('rev-parse','HEAD'),'dirty':bool(oc_git('status','--porcelain')),
              'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (local/'source-manifest.json').write_text(json.dumps(manifest,indent=2))
    if a.start_only:
        config=json.loads(oc('get','configmap/langflow-shop-pipeline-config','-n',NS,'-o','json'))['data']
        uid=int(config['uid']);cli=config['cli_image']
    else:
        namespace=json.loads(oc('get','namespace',NS,'-o','json'))
        uid=int(namespace['metadata']['annotations']['openshift.io/sa.scc.uid-range'].split('/')[0])
        cli=json.loads(oc('get','istag','cli:latest','-n','openshift','-o','json'))['image']['dockerImageReference']
        import importlib.util
        spec=importlib.util.spec_from_file_location('api',ROOT/'scripts/concert-audit-api.py')
        api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
        linkspec=importlib.util.spec_from_file_location('links',ROOT/'scripts/link-concert-source-routes.py')
        links=importlib.util.module_from_spec(linkspec);linkspec.loader.exec_module(links)
        config={'uid':str(uid),'cli_image':cli,'CONCERT_HOST':api.HOST,'CONCERT_APP_API':api.APP,
                'CONCERT_ENVIRONMENT_ID':links.ENV_ID,'CONCERT_DEPLOYMENT_ID':links.DEPLOY_ID,
                'CONCERT_PREVIOUS_REPO_URL':os.environ.get('CONCERT_PREVIOUS_REPO_URL','')}
    pod_security={'runAsUser':uid,'runAsGroup':uid,'fsGroup':uid,'runAsNonRoot':True,'seccompProfile':{'type':'RuntimeDefault'}}
    image=json.loads(oc('get','deployment/api-gateway','-n',NS,'-o','json'))['spec']['template']['spec']['containers'][0]['image']
    security={'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']},'runAsNonRoot':True}
    env=[{'name':'HOME','value':'/workspace/shared'},{'name':'PATH','value':'/workspace/shared/tools:/usr/local/bin:/usr/bin:/bin'},
         {'name':'SSL_CERT_DIR','value':'/etc/ssl/certs'},{'name':'PYTHONUNBUFFERED','value':'1'}]
    env.extend({'name':key,'valueFrom':{'configMapKeyRef':{'name':'langflow-shop-pipeline-config','key':key}}} for key in config if key.startswith('CONCERT_'))
    step={'name':'execute','image':image,'workingDir':'/workspace/shared/src','command':['python3'],'args':['scripts/pipeline-stage.py','$(params.stage)'],
          'env':env,'securityContext':security,'computeResources':{'requests':{'cpu':'250m','memory':'512Mi'},'limits':{'cpu':'2','memory':'4Gi'}},
          'volumeMounts':[{'name':'concert-auth','mountPath':'/concert-auth','readOnly':True},{'name':'registry-ca','mountPath':'/registry-ca','readOnly':True}]}
    volumes=[{'name':'concert-auth','secret':{'secretName':'concert-pipeline-auth'}},{'name':'registry-ca','configMap':{'name':'openshift-service-ca.crt'}}]
    workspace=[{'name':'shared','mountPath':'/workspace/shared'}]
    resources=[obj('ConfigMap','langflow-shop-pipeline-config',data=config),obj('ServiceAccount',SA),obj('PersistentVolumeClaim',PVC,spec={'accessModes':['ReadWriteMany'],'storageClassName':'ocs-external-storagecluster-cephfs','resources':{'requests':{'storage':'25Gi'}}}),
      obj('Role','langflow-shop-pipeline',apiVersion='rbac.authorization.k8s.io/v1',rules=[
       {'apiGroups':['build.openshift.io'],'resources':['buildconfigs','builds'],'verbs':['get','list','watch','patch','update']},
       {'apiGroups':['build.openshift.io'],'resources':['buildconfigs/instantiatebinary'],'verbs':['create']},
       {'apiGroups':['apps'],'resources':['deployments'],'verbs':['get','list','watch','patch','update']},
       {'apiGroups':[''],'resources':['pods','services'],'verbs':['get','list','watch']},
       {'apiGroups':['route.openshift.io'],'resources':['routes'],'verbs':['get','list']}]),
      obj('RoleBinding','langflow-shop-pipeline',apiVersion='rbac.authorization.k8s.io/v1',roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'langflow-shop-pipeline'},subjects=[{'kind':'ServiceAccount','name':SA,'namespace':NS}]),
      obj('RoleBinding','langflow-shop-pipeline-image-puller',apiVersion='rbac.authorization.k8s.io/v1',roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':'system:image-puller'},subjects=[{'kind':'ServiceAccount','name':SA,'namespace':NS}]),
      obj('Task','langflow-shop-devsecops-stage',apiVersion='tekton.dev/v1',spec={'params':[{'name':'stage','type':'string'}],'workspaces':workspace,'steps':[step],'volumes':volumes})]
    prep_steps=[]
    for name,img,path in [('oc',cli,'/usr/bin/oc'),('trivy','docker.io/aquasec/trivy:0.75.0','/usr/local/bin/trivy')]:
        prep_steps.append({'name':'copy-'+name,'image':img,'script':f'#!/bin/sh\nset -eu\nmkdir -p /workspace/shared/tools\ncp -L {path} /workspace/shared/tools/{name}\nchmod 755 /workspace/shared/tools/{name}\n','securityContext':security})
    prep_steps.append(dict(step,args=['scripts/pipeline-stage.py','prepare']))
    resources.append(obj('Task','langflow-shop-devsecops-prepare',apiVersion='tekton.dev/v1',spec={'workspaces':workspace,'steps':prep_steps,'volumes':volumes}))
    tasks=[]
    for i,stage in enumerate(['prepare','source-scan','build','image-scan','concert-ingest','deploy','link-verify']):
        task={'name':stage,'taskRef':{'name':'langflow-shop-devsecops-prepare' if stage=='prepare' else 'langflow-shop-devsecops-stage'},'workspaces':[{'name':'shared','workspace':'shared'}]}
        if stage!='prepare':task['params']=[{'name':'stage','value':stage}];task['runAfter']=[tasks[-1]['name']]
        tasks.append(task)
    resources.append(obj('Pipeline','langflow-shop-devsecops',apiVersion='tekton.dev/v1',spec={'workspaces':[{'name':'shared'}],'tasks':tasks}))
    path=ROOT/'openshift/pipelines/langflow-shop-devsecops.json';path.write_text(json.dumps({'apiVersion':'v1','kind':'List','items':resources},indent=2)+'\n')
    if not a.start_only:oc('apply','-f','-',data={'apiVersion':'v1','kind':'List','items':resources})
    # Secret goes directly to the API, never into the saved manifests or logs.
    if not a.start_only:oc('apply','-f','-',data=obj('Secret','concert-pipeline-auth',type='Opaque',stringData={'authorization':a.authorization_file.read_text().strip()}))
    seeder='langflow-shop-source-upload'
    oc('delete','pod',seeder,'-n',NS,'--ignore-not-found','--wait=true')
    oc('apply','-f','-',data=obj('Pod',seeder,spec={'serviceAccountName':SA,'securityContext':pod_security,'terminationGracePeriodSeconds':1,'restartPolicy':'Never','containers':[{'name':'upload','image':image,'command':['python3','-c','import time; time.sleep(3600)'],'securityContext':security,'volumeMounts':[{'name':'shared','mountPath':'/workspace/shared'}]}],'volumes':[{'name':'shared','persistentVolumeClaim':{'claimName':PVC}}]}))
    oc('wait','pod/'+seeder,'-n',NS,'--for=condition=Ready','--timeout=180s')
    for filename in ['source.tar.gz','source-manifest.json']:subprocess.run(['oc','cp',str(local/filename),NS+'/'+seeder+':/workspace/shared/'+filename],check=True)
    oc('exec','-n',NS,seeder,'--','python3','-c',"import tarfile,shutil,pathlib; p=pathlib.Path('/workspace/shared'); shutil.rmtree(p/'src',ignore_errors=True); shutil.rmtree(p/'output',ignore_errors=True); tarfile.open(p/'source.tar.gz').extractall(p)")
    oc('delete','pod',seeder,'-n',NS,'--wait=true','--grace-period=1')
    pipeline_run=obj('PipelineRun',run_id,apiVersion='tekton.dev/v1',spec={'pipelineRef':{'name':'langflow-shop-devsecops'},'taskRunTemplate':{'serviceAccountName':SA,'podTemplate':{'securityContext':pod_security}},'timeouts':{'pipeline':'1h0m0s'},'workspaces':[{'name':'shared','persistentVolumeClaim':{'claimName':PVC}}]})
    pipeline_run['metadata']['labels']={'app':'langflow-shop-devsecops'}
    pipeline_run['metadata']['annotations']={'langflow-shop.dev/source.snapshot-sha256':manifest['archive_sha256']}
    oc('create','-f','-',data=pipeline_run)
    (ROOT/'.runtime/latest-pipeline-run.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'pipeline_run':run_id,'source_snapshot_sha256':manifest['archive_sha256'],'local_evidence':str(local)}),flush=True)
    if a.wait:
        deadline=time.monotonic()+a.timeout;previous=None
        while time.monotonic()<deadline:
            value=json.loads(oc('get','pipelinerun',run_id,'-n',NS,'-o','json'));condition=value.get('status',{}).get('conditions',[{}])[0]
            if condition.get('message')!=previous:print(condition.get('message','Pending'),flush=True);previous=condition.get('message')
            if condition.get('status')=='True':return
            if condition.get('status')=='False':raise RuntimeError(condition.get('message'))
            time.sleep(10)
        raise RuntimeError('Pipeline did not complete before launcher timeout')


def oc_git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
if __name__=='__main__':main()
