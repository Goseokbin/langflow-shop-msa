#!/usr/bin/env python3
"""Administrative bootstrap only: isolated storage, secrets, RBAC and zero-replica workloads."""
import argparse
import base64
import copy
import json
from pathlib import Path
import secrets
import subprocess
import time

from promotion_bundle import ALL

LABELS={'app.kubernetes.io/part-of':'langflow-shop','langflow-shop.dev/environment':'production',
        'app.kubernetes.io/managed-by':'langflow-shop-promotion'}


class Cluster:
    def __init__(self, kubeconfig):self.prefix=['oc','--kubeconfig='+str(kubeconfig)]
    def run(self,*args,data=None):
        return subprocess.check_output([*self.prefix,*args],input=json.dumps(data).encode() if data is not None else None).decode().strip()
    def get(self,kind,name,namespace=None):
        args=['get',kind,name,'--ignore-not-found','-o','json']
        if namespace:args+=['-n',namespace]
        value=self.run(*args)
        return json.loads(value) if value else None
    def ensure(self,obj):
        meta=obj['metadata'];existing=self.get(obj['kind'],meta['name'],meta.get('namespace'))
        if existing:
            if any(existing['metadata'].get('labels',{}).get(k)!=v for k,v in LABELS.items()):
                raise ValueError('Refusing to overwrite an unrelated resource: '+obj['kind']+'/'+meta['name'])
            return False
        self.run('create','-f','-',data=obj);return True


def resource(kind,name,namespace=None,**kw):
    meta={'name':name,'labels':LABELS}
    if namespace:meta['namespace']=namespace
    return {'apiVersion':'v1','kind':kind,'metadata':meta,**kw}


def prepare(source,target,namespace,node,output):
    source_server=source.run('whoami','--show-server');target_server=target.run('whoami','--show-server')
    if source_server==target_server or namespace!='shopping-mall-prod':raise ValueError('A separate production cluster/namespace is required')
    if target.get('Node',node) is None:raise ValueError('Storage node does not exist')
    cluster=target.get('ClusterVersion','version');cluster_id=cluster['spec']['clusterID']
    target.ensure(resource('Namespace',namespace))
    target.ensure(resource('ServiceAccount','shop-runtime',namespace,imagePullSecrets=[{'name':'release-registry'}],automountServiceAccountToken=False))
    target.ensure(resource('ServiceAccount','langflow-shop-ci',namespace))
    # Secret values are generated independently. Existing production values are never replaced.
    values={
      'postgres-secrets':{'POSTGRES_USER':'shop','POSTGRES_PASSWORD':secrets.token_hex(24),'POSTGRES_ADMIN_PASSWORD':secrets.token_hex(32)},
      'jwt-secret':{'JWT_SECRET_KEY':secrets.token_hex(32)},
      'langflow-admin':{'LANGFLOW_SUPERUSER':'shop-admin','LANGFLOW_SUPERUSER_PASSWORD':secrets.token_urlsafe(32),'LANGFLOW_SECRET_KEY':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()},
      'langflow-api':{'LANGFLOW_API_KEY':'','LANGFLOW_URL':'http://langflow:7860/api/v1/run/shopping-assistant'}}
    for name,data in values.items():target.ensure(resource('Secret',name,namespace,type='Opaque',stringData=data))
    # One short-lived privileged preparer, with no API token and only the dedicated host directory.
    setup='langflow-shop-storage-setup';target.ensure(resource('Namespace',setup))
    target.ensure(resource('ServiceAccount','local-pv-preparer',setup,automountServiceAccountToken=False))
    target.ensure(resource('RoleBinding','local-pv-preparer',setup,apiVersion='rbac.authorization.k8s.io/v1',
        roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':'system:openshift:scc:privileged'},
        subjects=[{'kind':'ServiceAccount','name':'local-pv-preparer','namespace':setup}]))
    pod=resource('Pod','prepare-local-dirs',setup,spec={'nodeName':node,'serviceAccountName':'local-pv-preparer',
        'automountServiceAccountToken':False,'restartPolicy':'Never','containers':[{'name':'prepare',
        'image':source.get('Deployment','api-gateway','shopping-mall')['spec']['template']['spec']['containers'][0]['image'],
        'command':['sh','-c','mkdir -p /storage/postgres /storage/langflow && chmod 0777 /storage/postgres /storage/langflow && chcon -t container_file_t /storage/postgres /storage/langflow'],
        'securityContext':{'privileged':True,'runAsUser':0},'volumeMounts':[{'name':'storage','mountPath':'/storage'}]}],
        'volumes':[{'name':'storage','hostPath':{'path':'/var/mnt/langflow-shop-prod','type':'DirectoryOrCreate'}}]})
    # The public pinned PostgreSQL image has the small shell utilities needed for preparation.
    pod['spec']['containers'][0]['image']=source.get('Deployment','postgresql','shopping-mall')['spec']['template']['spec']['containers'][0]['image']
    try:
        target.ensure(pod)
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            status=target.get('Pod','prepare-local-dirs',setup)['status'].get('phase')
            if status=='Succeeded':break
            if status=='Failed':raise RuntimeError('Local directory preparation failed')
            time.sleep(3)
        else:raise RuntimeError('Local directory preparation timed out')
    finally:
        target.run('delete','pod/prepare-local-dirs','rolebinding/local-pv-preparer','serviceaccount/local-pv-preparer','-n',setup,'--ignore-not-found','--wait=true')
    sc=resource('StorageClass','langflow-shop-local',apiVersion='storage.k8s.io/v1',provisioner='kubernetes.io/no-provisioner',volumeBindingMode='WaitForFirstConsumer',reclaimPolicy='Retain')
    target.ensure(sc)
    for claim,path in [('postgres-data','postgres'),('langflow-data','langflow')]:
        target.ensure(resource('PersistentVolume','langflow-shop-prod-'+claim,spec={
            'capacity':{'storage':'10Gi'},'accessModes':['ReadWriteOnce'],'storageClassName':sc['metadata']['name'],
            'persistentVolumeReclaimPolicy':'Retain','volumeMode':'Filesystem',
            'local':{'path':'/var/mnt/langflow-shop-prod/'+path},
            'claimRef':{'namespace':namespace,'name':claim},
            'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':[node]}]}]}}}))
        target.ensure(resource('PersistentVolumeClaim',claim,namespace,spec={'accessModes':['ReadWriteOnce'],
            'storageClassName':sc['metadata']['name'],'resources':{'requests':{'storage':'10Gi'}}}))
    # Prepare only zero-replica workloads. The approval-gated job activates their images.
    for name in sorted(ALL):
        d=source.get('Deployment',name,'shopping-mall');spec=copy.deepcopy(d['spec']);spec['replicas']=0
        spec['template']['metadata']={'labels':{**spec['template']['metadata']['labels'],**LABELS}}
        spec['template']['spec']['imagePullSecrets']=[{'name':'release-registry'}]
        if name=='postgresql':spec['template']['spec']['containers'][0]['env'].append({'name':'POSTGRESQL_ADMIN_PASSWORD','valueFrom':{'secretKeyRef':{'name':'postgres-secrets','key':'POSTGRES_ADMIN_PASSWORD'}}})
        # The placeholder image is pinned but no Pod may start until production approval.
        target.ensure(resource('Deployment',name,namespace,apiVersion='apps/v1',spec=spec))
        s=source.get('Service',name,'shopping-mall')
        target.ensure(resource('Service',name,namespace,spec={k:s['spec'][k] for k in ['ports','selector','type'] if k in s['spec']}))
    for name in ['frontend','api-gateway','langflow']:
        r=source.get('Route',name,'shopping-mall')
        target.ensure(resource('Route',name,namespace,apiVersion='route.openshift.io/v1',spec={
            'to':r['spec']['to'],'port':r['spec']['port'],'tls':{'termination':'edge','insecureEdgeTerminationPolicy':'Redirect'}}))
    rules=[
      {'apiGroups':['apps'],'resources':['deployments'],'verbs':['get','list','watch']},
      {'apiGroups':['apps'],'resources':['deployments'],'resourceNames':sorted(ALL),'verbs':['patch','update']},
      {'apiGroups':[''],'resources':['services','pods'],'verbs':['get','list','watch']},
      {'apiGroups':[''],'resources':['configmaps'],'resourceNames':['langflow-shop-pipeline-config'],'verbs':['get','patch','update']},
      {'apiGroups':[''],'resources':['secrets'],'resourceNames':['langflow-admin','langflow-api'],'verbs':['get']},
      {'apiGroups':[''],'resources':['secrets'],'resourceNames':['langflow-api'],'verbs':['patch','update']},
      {'apiGroups':['batch'],'resources':['jobs'],'verbs':['create','get','list','watch','delete']},
      {'apiGroups':[''],'resources':['services/proxy'],'verbs':['get'],'resourceNames':['http:'+n+':'+str(p) for n,p in {'api-gateway':8000,'cart-service':8003,'langflow':7860,'langflow-ai-service':8005,'order-service':8004,'product-service':8002,'user-service':8001}.items()]},
      {'apiGroups':['route.openshift.io'],'resources':['routes'],'verbs':['get','list']}]
    target.ensure(resource('Role','langflow-shop-promotion',namespace,apiVersion='rbac.authorization.k8s.io/v1',rules=rules))
    target.ensure(resource('RoleBinding','langflow-shop-promotion',namespace,apiVersion='rbac.authorization.k8s.io/v1',
        roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'langflow-shop-promotion'},subjects=[{'kind':'ServiceAccount','name':'langflow-shop-ci','namespace':namespace}]))
    result={'namespace':namespace,'source_server':source_server,'production_server':target_server,'cluster_id':cluster_id,
            'storage_node':node,'storage_class':'langflow-shop-local','workload_replicas_before_approval':0}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-kubeconfig',required=True,type=Path);p.add_argument('--target-kubeconfig',required=True,type=Path)
    p.add_argument('--namespace',default='shopping-mall-prod');p.add_argument('--storage-node',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    prepare(Cluster(a.source_kubeconfig),Cluster(a.target_kubeconfig),a.namespace,a.storage_node,a.output)
