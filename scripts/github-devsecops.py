#!/usr/bin/env python3
"""Run scans, native Docker builds, Concert ingestion and deployment in Actions."""
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.runtime/github-actions'
OWN = ['api-gateway','cart-service','frontend','langflow-ai-service','order-service','product-service','user-service']


def output(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def main():
    config = json.loads(output('oc','get','configmap','langflow-shop-pipeline-config','-n','shopping-mall','-o','json'))['data']
    for key in ['CONCERT_HOST','CONCERT_APP_API','CONCERT_ENVIRONMENT_ID','CONCERT_DEPLOYMENT_ID','CONCERT_PREVIOUS_REPO_URL','DOCKER_REGISTRY_HOST']:
        os.environ[key] = config[key]
    if output('git','status','--porcelain','--untracked-files=no',cwd=ROOT):
        raise RuntimeError('Build requires a clean checkout')
    commit = output('git','rev-parse','HEAD',cwd=ROOT)
    if commit != os.environ['GITHUB_SHA']:
        raise RuntimeError('Checkout SHA differs from Actions event SHA')
    WORK.mkdir(parents=True,exist_ok=True)
    archive = WORK/'source.tar.gz'
    tracked = output('git','ls-files','-z',cwd=ROOT).split('\0')
    with tarfile.open(archive,'w:gz') as tar:
        for name in tracked:
            if name:
                tar.add(ROOT/name,arcname=name,recursive=False)
    source = WORK/'source';source.mkdir(exist_ok=True)
    with tarfile.open(archive) as tar:
        tar.extractall(source,filter='data')
    manifest = {'run_id':'github-'+os.environ['GITHUB_RUN_ID'],
                'repository':'https://github.com/'+os.environ['GITHUB_REPOSITORY'],
                'repo_name':os.environ['GITHUB_REPOSITORY'].split('/')[-1],
                'branch':os.environ['GITHUB_REF_NAME'],'git_base_commit':commit,'dirty':False,
                'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
    (WORK/'source-manifest.json').write_text(json.dumps(manifest,indent=2))
    auth = WORK/'authorization';auth.touch(mode=0o600);auth.chmod(0o600)
    auth.write_text(os.environ.pop('CONCERT_AUTH_HEADER').strip())
    os.environ.update(PIPELINE_WORKSPACE=str(WORK),CONCERT_AUTH_FILE=str(auth),PIPELINE_ENGINE='github-actions',PIPELINE_PUBLIC_LOGS='1')
    sys.path.insert(0,str(source/'scripts'))
    spec=importlib.util.spec_from_file_location('pipeline',source/'scripts/pipeline-stage.py')
    stages=importlib.util.module_from_spec(spec);spec.loader.exec_module(stages)
    registry=os.environ['DOCKER_REGISTRY_HOST']
    run_url=f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    try:
        stages.prepare();stages.source_scan()
        subprocess.run(['docker','login',registry,'--username','serviceaccount','--password-stdin'],
                       input=os.environ['OPENSHIFT_TOKEN'],text=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        def build(name):
            tag=f'{registry}/shopping-mall/{name}:{commit}'
            labels={'org.opencontainers.image.source':manifest['repository'],'org.opencontainers.image.revision':commit,
                    'io.langflow-shop.source-snapshot-sha256':manifest['archive_sha256']}
            args=['docker','build','--pull','--tag',tag]
            for key,value in labels.items():args.extend(['--label',key+'='+value])
            logfile=stages.OUT/(name+'.build.log')
            with logfile.open('w') as log:
                try:
                    subprocess.run([*args,str(source/'services'/name)],stdout=log,stderr=subprocess.STDOUT,check=True)
                    subprocess.run(['docker','push',tag],stdout=log,stderr=subprocess.STDOUT,check=True)
                except subprocess.CalledProcessError:
                    # Build output may contain internal registry names; retain locally.
                    print('Docker build/push failed: '+name,flush=True)
                    raise
            image=json.loads(output('docker','image','inspect',tag))[0]
            if any(image['Config']['Labels'].get(k)!=v for k,v in labels.items()):
                raise RuntimeError('Image source label mismatch: '+name)
            digests=[x.split('@',1)[1] for x in image['RepoDigests'] if x.startswith(registry+'/shopping-mall/'+name+'@')]
            if len(set(digests))!=1:raise RuntimeError('Cannot establish pushed digest: '+name)
            result={'name':name,'build':f"github-actions/{os.environ['GITHUB_RUN_ID']}/{name}",'run_url':run_url,
                    'image':'image-registry.openshift-image-registry.svc:5000/shopping-mall/'+name+'@'+digests[0],
                    'git_commit':commit,'source.snapshot-sha256':manifest['archive_sha256'],'verified_oci_labels':labels}
            stages.save(name+'.build.json',result)
            print('Built and verified image: '+name,flush=True)
            return result
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            builds=list(pool.map(build,OWN))
        stages.save('builds.json',builds);stages.event('build','succeeded',built_images=len(builds))
        stages.image_scan();stages.ingest();stages.deploy();stages.link_verify()
        # Functional commerce test creates its own test user and cancels its order.
        (source/'docs').mkdir(exist_ok=True)
        with (stages.OUT/'smoke.log').open('w') as log:
            subprocess.run(['python3',str(source/'scripts/smoke-test.py')],cwd=source,stdout=log,stderr=subprocess.STDOUT,check=True)
        report=json.loads((stages.OUT/'verification.json').read_text())
        public={'run_url':run_url,'git_commit':commit,'source_snapshot_sha256':manifest['archive_sha256'],
                'repository':report['repository'],'images':[{k:v for k,v in r.items() if k in ['name','packages','cves','os_unsupported']} for r in report['images']],
                'topology_counts':report['topology_counts'],'commerce_smoke':'passed','oci_revision_verified_images':len(builds)}
        stages.save('public-verification.json',public)
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as summary:
            summary.write(f"## Verified DevSecOps result\n\nCommit: `{commit}`\n\nRepository: {report['repository']['packages']} packages, {report['repository']['cves']} CVE findings (branch scope).\n\nImages: {len(report['images'])}; built and source-label verified: {len(builds)}. Commerce smoke: passed.\n\nPostgreSQL OS vulnerability matching remains unsupported; package inventory is collected.\n")
    finally:
        auth.unlink(missing_ok=True)
        subprocess.run(['docker','logout',registry],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

if __name__=='__main__':main()
