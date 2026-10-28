#!/usr/bin/env python3
"""Shared DevSecOps stage runner; source and images share an immutable source archive hash."""
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import time
import uuid

ROOT=pathlib.Path(__file__).resolve().parents[1]
NS = os.environ.get('SHOP_NAMESPACE', 'shopping-mall')
WORK=pathlib.Path(os.environ.get('PIPELINE_WORKSPACE','/workspace/shared'))
OUT=WORK/'output';OUT.mkdir(exist_ok=True)
MANIFEST=json.loads((WORK/'source-manifest.json').read_text())
OWN=['api-gateway','cart-service','frontend','langflow-ai-service','order-service','product-service','user-service']
AUTH=pathlib.Path(os.environ.get('CONCERT_AUTH_FILE','/concert-auth/authorization'))
spec=importlib.util.spec_from_file_location('api',ROOT/'scripts/concert-audit-api.py')
api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
from concert_image_identity import identity, normalize_sbom, select_artifact


def run(*args, **kw):
    return subprocess.check_output(list(args),text=True,**kw).strip()


def oc(*args, data=None):
    return run('oc',*args,input=json.dumps(data) if data is not None else None)


def items(kind):return json.loads(oc('get',kind,'-n',NS,'-o','json'))['items']
def save(name,data):
    p=OUT/name;p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');return p

def event(stage,state,**values):
    result={'stage':stage,'state':state,'source_snapshot_sha256':MANIFEST['archive_sha256'],**values}
    save(stage+'.status.json',result)
    public = {k:v for k,v in result.items() if k in ['stage','state','source_snapshot_sha256','run_id','git_base_commit','dirty','packages','cves','images','built_images','source_uploaded']} if os.environ.get('PIPELINE_PUBLIC_LOGS') else result
    print(json.dumps(public),flush=True)


def scan_args():return ['--cache-dir',str(WORK/'cache'),'--skip-version-check','--timeout','15m']
def scan(name,image=None):
    raw=OUT/(name+'.trivy.json');cdx=OUT/(name+'.cdx.json')
    env=os.environ.copy()
    if image:
        scan_image=image
        if image.startswith('image-registry.openshift-image-registry.svc:5000/'):
            env['TRIVY_USERNAME']='serviceaccount'
            if os.environ.get('DOCKER_REGISTRY_HOST'):
                scan_image=os.environ['DOCKER_REGISTRY_HOST']+'/'+image.split('/',1)[1]
                env['TRIVY_PASSWORD']=os.environ['OPENSHIFT_TOKEN']
            else:env['TRIVY_PASSWORD']=pathlib.Path('/var/run/secrets/kubernetes.io/serviceaccount/token').read_text().strip()
        command=['trivy','image','--image-src','remote',*scan_args(),'--scanners','vuln','--list-all-pkgs','--format','json','--output',str(raw),scan_image]
    else:command=['trivy','fs',*scan_args(),'--scanners','vuln','--list-all-pkgs','--format','json','--output',str(raw),str(ROOT/'services')]
    with (OUT/(name+'.scan.log')).open('w') as log:
        subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        subprocess.run(['trivy','convert','--format','cyclonedx','--output',str(cdx),str(raw)],stdout=log,stderr=subprocess.STDOUT,check=True)
    os_unsupported=bool(image) and json.loads(raw.read_text()).get('Metadata',{}).get('OS',{}).get('Family')=='centos-stream'
    if os_unsupported:
        # Unsupported OS vulnerability scan has no Results: collect inventory separately.
        with (OUT/(name+'.scan.log')).open('a') as log:
            subprocess.run(['trivy','image','--image-src','remote',*scan_args(),'--format','cyclonedx','--output',str(cdx),scan_image],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    doc=json.loads(cdx.read_text())
    if image:
        repo,digest=identity(image);doc=normalize_sbom(doc,repo,digest)
    else:
        doc['serialNumber']='urn:uuid:'+str(uuid.uuid4())
        root=doc['metadata']['component'];root['name']=MANIFEST.get('repo_name','langflow-shop')
        root['externalReferences']=[{'type':'vcs','url':MANIFEST['repository']}]
        if not MANIFEST['dirty']:root['version']=MANIFEST['git_base_commit']
        root.setdefault('properties',[]).extend([
            {'name':'source.snapshot_sha256','value':MANIFEST['archive_sha256']},
            {'name':'source.revision_status','value':'working_tree_snapshot' if MANIFEST['dirty'] else 'clean_git_checkout'}])
    cdx.write_text(json.dumps(doc))
    return {'name':name,'image':image,'file':str(cdx),'packages':len({x['purl'] for x in doc.get('components',[]) if x.get('purl') and x.get('type')!='operating-system'}),'vulnerabilities':len(doc.get('vulnerabilities',[])),
            'os_unsupported':json.loads(raw.read_text()).get('Metadata',{}).get('OS',{}).get('Family')=='centos-stream'}


def prepare():
    actual=hashlib.sha256((WORK/'source.tar.gz').read_bytes()).hexdigest()
    if actual!=MANIFEST['archive_sha256']:raise RuntimeError('Source archive checksum mismatch')
    event('prepare','succeeded',run_id=MANIFEST['run_id'],git_base_commit=MANIFEST['git_base_commit'],dirty=MANIFEST['dirty'])


def source_scan():
    result=scan('repository');save('source-scan.json',result);event('source-scan','succeeded',**result)


def build_one(name):
    archive=OUT/(name+'.build.tar.gz')
    with tarfile.open(archive,'w:gz') as tar:tar.add(ROOT/'services'/name,arcname='.')
    build=oc('start-build',name,'-n',NS,'--from-archive='+str(archive),'-o','name')
    annotations={'source.snapshot-sha256':MANIFEST['archive_sha256'],'source.git-base-commit':MANIFEST['git_base_commit'],
                 'source.git-dirty':str(MANIFEST['dirty']).lower(),'source.context-sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
                 'pipeline.run':MANIFEST['run_id']}
    oc('annotate',build,'-n',NS,'--overwrite',*[f'langflow-shop.dev/{k}={v}' for k,v in annotations.items()])
    deadline=time.monotonic()+1200
    while True:
        obj=json.loads(oc('get',build,'-n',NS,'-o','json'));phase=obj['status']['phase']
        if phase=='Complete':break
        if phase in ['Failed','Cancelled','Error'] or time.monotonic()>deadline:raise RuntimeError(build+' '+phase)
        time.sleep(5)
    digest=obj['status']['output']['to']['imageDigest']
    repo='image-registry.openshift-image-registry.svc:5000/shopping-mall/'+name
    result={'name':name,'build':obj['metadata']['name'],'build_uid':obj['metadata']['uid'],'image':repo+'@'+digest,**annotations}
    save(name+'.build.json',result);print(json.dumps(result),flush=True);return result


def build():
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(build_one,OWN))
    save('builds.json',results);event('build','succeeded',built_images=len(results))


def image_scan():
    builds=json.loads((OUT/'builds.json').read_text());images={b['name']:b['image'] for b in builds}
    for deployment in items('deployments'):
        name=deployment['metadata']['name']
        if name not in images:images[name]=deployment['spec']['template']['spec']['containers'][0]['image']
    results=[]
    for name,image in sorted(images.items(),key=lambda x:x[0]=='langflow'):
        print('Scanning image '+name,flush=True);result=scan(name,image);results.append(result);save('image-scans.json',results)
    # A patched release must prove the target CVEs absent in both source and its new image.
    from patch_catalog import load_policies
    policies=load_policies()
    patch_gates={}
    for policy in policies.values():
        if (policy.get('requirement',policy['package'])+'=='+policy['to_version']) in (ROOT/policy['file']).read_text().splitlines():
            patch_spec=importlib.util.spec_from_file_location('patch_guard',ROOT/'scripts/verify-patch.py')
            patch_guard=importlib.util.module_from_spec(patch_spec);patch_spec.loader.exec_module(patch_guard)
            patch_gates[policy['package']]={name:patch_guard.validate_scan(json.loads((OUT/(name+'.trivy.json')).read_text()),policy=policy,source=name=='repository')
                   for name in ['repository',policy['service']]}
    if patch_gates:save('patch-verification.json',patch_gates)
    event('image-scan','succeeded',images=len(results),unsupported_os=[r['name'] for r in results if r['os_unsupported']])


def upload(client,file,typ,metadata):
    response=client.upload(file,typ,metadata)
    save(pathlib.Path(file).stem+'.'+typ+'.ingestion.json',response)
    client.wait_for_upload(response,timeout=900)
    print('Ingested '+typ+' '+pathlib.Path(file).name,flush=True)


def ingest():
    client=api.Concert(authorization=AUTH)
    meta={'repo_url':MANIFEST['repository'],'repo_name':MANIFEST.get('repo_name','langflow-shop'),'branch':MANIFEST['branch'],'branch_name':MANIFEST['branch'],
          'component_type':'repository','component_name':MANIFEST.get('repo_name','langflow-shop'),'scanner_name':'trivy','application_name':os.environ.get('APPLICATION_NAME','langflow-shop'),'application_version':os.environ.get('APPLICATION_VERSION','1.0.0')}
    if not MANIFEST['dirty']:meta['commit_sha']=MANIFEST['git_base_commit']
    source=json.loads((OUT/'source-scan.json').read_text())
    for typ in ['package_sbom','code_scan']:upload(client,source['file'],typ,meta)
    for result in json.loads((OUT/'image-scans.json').read_text()):
        repo,digest=identity(result['image']);meta={'image_name':repo,'component_name':repo,'component_type':'image','digest':digest,'scanner_name':'trivy','application_name':os.environ.get('APPLICATION_NAME','langflow-shop'),'application_version':os.environ.get('APPLICATION_VERSION','1.0.0')}
        upload(client,result['file'],'package_sbom',meta)
        if not result['os_unsupported']:upload(client,result['file'],'image_scan',meta)
    event('concert-ingest','succeeded',source_uploaded=True)


def deploy():
    previous={d['metadata']['name']:d['spec']['template']['spec']['containers'][0]['image'] for d in items('deployments')}
    save('previous-deployment-images.json',previous)
    for result in json.loads((OUT/'builds.json').read_text()):
        oc('set','image','deployment/'+result['name'],result['name']+'='+result['image'],'-n',NS)
        oc('annotate','deployment/'+result['name'],'-n',NS,'--overwrite','langflow-shop.dev/source.snapshot-sha256='+MANIFEST['archive_sha256'],'langflow-shop.dev/pipeline.run='+MANIFEST['run_id'],'langflow-shop.dev/source.git-commit='+MANIFEST['git_base_commit'])
    for name in OWN:oc('rollout','status','deployment/'+name,'-n',NS,'--timeout=300s')
    event('deploy','succeeded',deployments=len(OWN))


def link_verify():
    link_args=['--build-evidence-file',str(OUT/'builds.json')] if os.environ.get('PIPELINE_ENGINE')=='github-actions' else []
    subprocess.run(['python3',str(ROOT/'scripts/link-concert-source-routes.py'),'--apply','--authorization-file',str(AUTH),
                    '--repo-url',MANIFEST['repository'],'--branch',MANIFEST['branch'],'--provenance-file',str(WORK/'source-manifest.json'),*link_args],check=True,cwd=ROOT)
    current_deployment=json.loads((ROOT/'.runtime/source-route-links/current-deployment.json').read_text())
    os.environ['CONCERT_DEPLOYMENT_ID']=current_deployment['id']
    context_path=OUT/'release-context.json'
    if context_path.exists():
        context=json.loads(context_path.read_text());context['current_deployment_id']=current_deployment['id'];context_path.write_text(json.dumps(context))
    client=api.Concert(authorization=AUTH);repos=client.request(api.APP+'/source_repos?page_size=2000')['source_repos']
    repo=next(r for r in repos if r['repo_url'].removesuffix('.git')==MANIFEST['repository'] and r.get('branch')==MANIFEST['branch'])
    root=api.APP+'/source_repos/'+repo['id'];packages=client.request(root+'/packages?page_size=1')['pagination']['total_count'];cves=client.request(root+'/cve_findings?page_size=1')['pagination']['total_count']
    expected_source=json.loads((OUT/'source-scan.json').read_text())
    if packages<expected_source['packages'] or cves<expected_source['vulnerabilities']:raise RuntimeError('Repository packages/CVEs were not fully linked')
    artifacts=client.request(api.APP+'/build_artifacts?page_size=2000')['build_artifacts'];verified=[]
    for result in json.loads((OUT/'image-scans.json').read_text()):
        name,digest=identity(result['image']);art=select_artifact(artifacts,name,digest);root=api.APP+'/build_artifacts/'+art['id']
        count=client.request(root+'/packages?page_size=1')['pagination']['total_count']
        cv=client.request(root+'/cve_findings?page_size=1')['pagination']['total_count']
        if count<result['packages']:raise RuntimeError('Image inventory incomplete: '+name)
        if not result['os_unsupported'] and result['vulnerabilities'] and not cv:raise RuntimeError('Image CVEs absent: '+name)
        verified.append({'name':result['name'],'id':art['id'],'image':result['image'],'packages':count,'cves':cv,'os_unsupported':result['os_unsupported']})
    topo=client.request(api.APP+'/topology')
    internal=json.loads((ROOT/'.runtime/source-route-links/internal-endpoints.json').read_text())
    report={'run_id':MANIFEST['run_id'],'source_snapshot_sha256':MANIFEST['archive_sha256'],'git_base_commit':MANIFEST['git_base_commit'],'dirty':MANIFEST['dirty'],
            'repository':{'id':repo['id'],'packages':packages,'cves':cves,'scope':'branch','scanned_commit':MANIFEST['git_base_commit']},'images':verified,
            'internal_endpoints':{'api_services':internal['api_services'],'api_paths':internal['api_paths'],
                 'endpoint_count':internal['endpoint_count'],'verified':True,
                 'services':[{k:r[k] for k in ['name','kind']} | {'paths':len(r['endpoints']),'operations':len(r['operations'])} for r in internal['services']]},
            'deployment':current_deployment,'topology_counts':{k:len(topo[k]) for k in ['source_repos','build_artifacts','public_services','private_services','public_access_points']}}
    save('verification.json',report);event('link-verify','succeeded',**report)


if __name__=='__main__':
    stage=sys.argv[1];event(stage,'running')
    try:{'prepare':prepare,'source-scan':source_scan,'build':build,'image-scan':image_scan,'concert-ingest':ingest,'deploy':deploy,'link-verify':link_verify}[stage]()
    except Exception as exc:
        event(stage,'failed',error=str(exc));raise
