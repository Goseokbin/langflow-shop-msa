"""A verified release contains image digests and configuration references, never Secret data."""
import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from concert_image_identity import identity

OWN = {'api-gateway','cart-service','frontend','langflow-ai-service','order-service','product-service','user-service'}
ALL = OWN | {'langflow','postgresql'}
MAGIC = b'LFSHOPPROMOTION1\n'


def validate_release(release):
    if release.get('schema_version') != 1 or not re.fullmatch(r'[0-9a-f]{40}', release.get('commit','')):
        raise ValueError('Invalid release identity')
    if not str(release.get('run_id','')).isdigit() or release.get('repository') != 'Goseokbin/langflow-shop-msa':
        raise ValueError('Release must originate from the configured GitHub repository/run')
    rows = release.get('images',[])
    if len(rows)!=9 or {r['name'] for r in rows} != ALL:
        raise ValueError('Expected all nine verified images')
    for row in rows:
        repo,digest=identity(row['source_image'])
        if digest != row['digest'] or identity(row['pull_image'])[1] != digest:
            raise ValueError('Promotion may not substitute an image digest')
        expected = row['source_image']
        prefix='image-registry.openshift-image-registry.svc:5000/'
        if expected.startswith(prefix):expected=release['registry_host']+'/'+expected[len(prefix):]
        if row['pull_image']!=expected:
            raise ValueError('Only the verified registry alias may be used for pulls')
    if set(release['deployments']) != ALL:
        raise ValueError('Release is missing deployment templates')
    for name, deployment in release['deployments'].items():
        containers=deployment['spec']['template']['spec']['containers']
        if len(containers)!=1 or containers[0]['name']!=name:
            raise ValueError('Review unexpected container layout')
        for env in containers[0].get('env',[]):
            if 'value' in env and env['value'] and re.search(r'PASSWORD|SECRET|API_KEY|TOKEN',env['name']):
                raise ValueError('Secret values must not enter a release bundle')
        if any(v.get('hostPath') for v in deployment['spec']['template']['spec'].get('volumes',[])):
            raise ValueError('Release workload may not mount host paths')
    if release['verification'].get('commerce_passed')!=8 or not release['verification'].get('internal_endpoints_verified'):
        raise ValueError('A release requires commerce and Concert endpoint verification')
    return release


def seal(release, destination, secret):
    validate_release(release)
    if len(secret)<32:raise ValueError('Promotion encryption key is missing or too short')
    with tempfile.TemporaryDirectory(prefix='shop-release-') as td:
        plain=Path(td)/'release.json';cipher=Path(td)/'release.aes'
        plain.write_text(json.dumps(release,separators=(',',':')))
        subprocess.run(['openssl','enc','-aes-256-cbc','-pbkdf2','-iter','200000','-salt','-in',str(plain),'-out',str(cipher),'-pass','env:PROMOTION_STATE_KEY'],env={**os.environ,'PROMOTION_STATE_KEY':secret},check=True)
        encrypted=cipher.read_bytes()
    key=hmac.digest(secret.encode(),b'langflow-shop-promotion-v1','sha256')
    blob=MAGIC+hmac.digest(key,encrypted,'sha256')+encrypted
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(blob)
    return hashlib.sha256(blob).hexdigest()


def unseal(source, expected_hash, secret):
    blob=source.read_bytes()
    if not re.fullmatch(r'[a-f0-9]{64}',expected_hash) or hashlib.sha256(blob).hexdigest()!=expected_hash:
        raise ValueError('Release artifact hash differs from the staging job output')
    if not blob.startswith(MAGIC):raise ValueError('Invalid release envelope')
    key=hmac.digest(secret.encode(),b'langflow-shop-promotion-v1','sha256')
    signature=blob[len(MAGIC):len(MAGIC)+32];encrypted=blob[len(MAGIC)+32:]
    if not hmac.compare_digest(signature,hmac.digest(key,encrypted,'sha256')):
        raise ValueError('Release artifact authentication failed')
    with tempfile.TemporaryDirectory(prefix='shop-release-') as td:
        cipher=Path(td)/'release.aes';plain=Path(td)/'release.json';cipher.write_bytes(encrypted)
        subprocess.run(['openssl','enc','-d','-aes-256-cbc','-pbkdf2','-iter','200000','-in',str(cipher),'-out',str(plain),'-pass','env:PROMOTION_STATE_KEY'],env={**os.environ,'PROMOTION_STATE_KEY':secret},check=True)
        release=json.loads(plain.read_text())
    return validate_release(release)


def create_release(stages, manifest, client):
    work=stages.WORK
    verification=json.loads((stages.OUT/'verification.json').read_text())
    smoke=json.loads((stages.OUT/'smoke.json').read_text())
    scans={r['name']:r for r in json.loads((stages.OUT/'image-scans.json').read_text())}
    builds={r['name']:r for r in json.loads((stages.OUT/'builds.json').read_text())}
    namespace=os.environ.get('SHOP_NAMESPACE','shopping-mall')
    server=stages.oc('whoami','--show-server')
    deployments={};images=[]
    for d in stages.items('deployments'):
        name=d['metadata']['name']
        if name not in ALL:continue
        image=d['spec']['template']['spec']['containers'][0]['image']
        if identity(image)!=identity(scans[name]['image']):raise ValueError('Running and scanned image differ: '+name)
        if d['status'].get('readyReplicas',0)!=d['spec'].get('replicas',1):raise ValueError('Staging is not ready')
        if name in OWN and (image!=builds[name]['image'] or builds[name]['git_commit']!=manifest['git_base_commit']):
            raise ValueError('Built image/source revision mismatch')
        pull=image
        prefix='image-registry.openshift-image-registry.svc:5000/'
        if image.startswith(prefix):pull=os.environ['DOCKER_REGISTRY_HOST']+'/'+image[len(prefix):]
        images.append({'name':name,'source_image':image,'pull_image':pull,'digest':identity(image)[1]})
        spec=copy.deepcopy(d['spec']);spec['replicas']=1
        spec['template']['metadata'].pop('annotations',None)
        deployments[name]={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':name},'spec':spec}
    services=[]
    for s in stages.items('services'):
        if s['metadata']['name'] in ALL:
            services.append({'apiVersion':'v1','kind':'Service','metadata':{'name':s['metadata']['name']},
                             'spec':{k:copy.deepcopy(s['spec'][k]) for k in ['selector','ports','type'] if k in s['spec']}})
    routes=[]
    for r in stages.items('routes'):
        if r['metadata']['name'] in {'frontend','api-gateway','langflow'}:
            routes.append({'apiVersion':'route.openshift.io/v1','kind':'Route','metadata':{'name':r['metadata']['name']},
                'spec':{'to':copy.deepcopy(r['spec']['to']),'port':copy.deepcopy(r['spec']['port']),
                        'tls':{'termination':'edge','insecureEdgeTerminationPolicy':'Redirect'}}})
    env=os.environ['CONCERT_ENVIRONMENT_ID'];deploy=os.environ['CONCERT_DEPLOYMENT_ID']
    release={'schema_version':1,'repository':os.environ['GITHUB_REPOSITORY'],'run_id':os.environ['GITHUB_RUN_ID'],
        'commit':manifest['git_base_commit'],'snapshot_sha256':manifest['archive_sha256'],
        'source_server':server,'source_namespace':namespace,'registry_host':os.environ['DOCKER_REGISTRY_HOST'],
        'application_name':os.environ.get('APPLICATION_NAME','langflow-shop'),'application_version':os.environ.get('APPLICATION_VERSION','1.0.0'),
        'images':sorted(images,key=lambda r:r['name']),'deployments':deployments,'services':services,'routes':routes,
        'deployment_sbom':client.request(f'/concert/core/api/v2/environments/{env}/deployments/{deploy}/sbom'),
        'verification':{'commerce_passed':smoke['passed'],'internal_endpoints_verified':verification['internal_endpoints']['verified'],
                        'api_paths':verification['internal_endpoints']['api_paths'],'scanned_images':len(scans)}}
    destination=stages.OUT/'release.enc';digest=seal(release,destination,os.environ['PROMOTION_STATE_KEY'])
    stages.save('promotion-release.json',{'sha256':digest,'images':[{k:r[k] for k in ['name','digest']} for r in release['images']],
        'source_commit':manifest['git_base_commit'],'source_run':os.environ['GITHUB_RUN_ID'],'approval_environment':'production'})
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('release_sha256='+digest+'\n')
    return digest
