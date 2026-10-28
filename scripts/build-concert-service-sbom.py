#!/usr/bin/env python3
"""Exported application definition + observed Kubernetes Services -> ConcertDef.

Input snapshots contain metadata only; no Secret values are read. Removing an item
from this document requests definition reconciliation, not runtime deletion.
"""
import argparse
import datetime
import json
import pathlib
from concert_image_identity import identity
from concert_internal_endpoints import collect, enrich

ROOT = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--kind', choices=['application', 'deploy'], default='application')
p.add_argument('--export', type=pathlib.Path, default=ROOT / '.runtime/concert-application-export')
p.add_argument('--output', type=pathlib.Path, default=ROOT / '.runtime/concert-services.cdef.json')
a = p.parse_args()
doc = json.loads(a.export.read_text())
scans = {x['name']: x for x in json.loads((ROOT / '.runtime/image-scans/summary.json').read_text())}
services = json.loads((ROOT / '.runtime/current-services.json').read_text())['items']
doc['metadata']['timestamp'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
kept = []
for comp in doc['components']:
    name = comp['name']
    if name == 'image-registry.openshift-image-registry.svc':
        continue  # confirmed malformed alias, not a Kubernetes workload
    if name not in scans:
        raise ValueError('Unknown component; refusing to remove or remap: ' + name)
    repo, digest = identity(scans[name]['image'])
    images = [x for x in comp['components'] if x['type'] == 'image']
    if len(images) != 1:
        raise ValueError('Expected one image for ' + name)
    # Application image definitions use names; exact digests belong to build/deploy SBOMs.
    images[0].pop('uri', None)
    kept.append(comp)
doc['components'] = kept
doc['services'] = []
doc['dependencies'] = []
for service in services:
    name = service['metadata']['name']
    comp = next(x for x in kept if x['name'] == name)
    ref = next(x['bom-ref'] for x in comp['components'] if x['type'] == 'image')
    endpoints = []
    for port in service['spec']['ports']:
        scheme = 'tcp' if name == 'postgresql' else 'http'
        endpoints.append(f"{scheme}://{name}.shopping-mall.svc:{port['port']}")
    sr = 'service:shopping-mall:' + name
    doc['services'].append({'bom-ref': sr, 'name': name, 'endpoints': endpoints,
                            'network-exposure': 'private', 'properties': [
                                {'name': 'kubernetes.namespace', 'value': 'shopping-mall'},
                                {'name': 'source', 'value': 'Kubernetes Service snapshot'}]})
    doc['dependencies'].append({'ref': ref, 'dependsOn': [sr]})


if a.kind == 'deploy':
    deploy = json.loads((ROOT / '.runtime/concert-deploy-export.json').read_text())
    deploy['metadata']['timestamp'] = doc['metadata']['timestamp']
    deploy['services'] = []
    managed_refs = {x['bom-ref'] for x in doc['services']}
    for dependency in deploy.get('dependencies', []):
        dependency['dependsOn'] = [x for x in dependency['dependsOn'] if x not in managed_refs]
    def walk(items):
        for item in items:
            yield item
            yield from walk(item.get('components', []))
    images = {x['name']: x for x in walk(deploy['runtime-components']) if x['type'] == 'image'}
    for service in doc['services']:
        name = service['name']
        image_name = 'postgresql-16-c9s' if name == 'postgresql' else name
        image = images[image_name]
        repo, digest = identity(scans[name]['image'])
        image['uri'] = repo + '@' + digest
        port = next(x for x in services if x['metadata']['name'] == name)['spec']['ports'][0]['port']
        item = dict(service)
        item['network_exposure'] = item.pop('network-exposure')
        item['base-url'] = f"{'tcp' if name == 'postgresql' else 'http'}://{name}.shopping-mall.svc:{port}"
        item['port'] = port
        deploy['services'].append(item)
        dependency = next((x for x in deploy['dependencies'] if x['ref'] == image['bom-ref']), None)
        if dependency is None:
            dependency = {'ref': image['bom-ref'], 'dependsOn': []}
            deploy['dependencies'].append(dependency)
        dependency['dependsOn'].append(item['bom-ref'])

inventory = collect(services, a.output.parent / 'internal-openapi')
enrich(deploy if a.kind == 'deploy' else doc, inventory, deployment=a.kind == 'deploy')
a.output.write_text(json.dumps(deploy if a.kind == 'deploy' else doc, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'kind': a.kind, 'components': len(kept), 'services': len(doc['services']), 'api_paths':inventory['api_paths'], 'output': str(a.output)}))
