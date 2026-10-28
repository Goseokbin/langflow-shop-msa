#!/usr/bin/env python3
"""Link observed source/build/image/deployment metadata and public OCP Routes.

Generates files by default; --apply uploads via Concert. Does not claim a Git
revision for Binary builds that did not record one. Never changes workloads.
"""
import argparse
import datetime
import importlib.util
import json
import pathlib
import os
import subprocess
import urllib.request

from concert_image_identity import identity
from concert_internal_endpoints import collect, compact_properties, enrich, restore_application_services, verify_document

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / '.runtime/source-route-links'
ENV_ID = os.environ['CONCERT_ENVIRONMENT_ID']
DEPLOY_ID = os.environ['CONCERT_DEPLOYMENT_ID']
OWN = {'api-gateway','frontend','cart-service','user-service','product-service','order-service','langflow-ai-service'}


def oc(kind):
    return json.loads(subprocess.check_output(['oc','get',kind,'-n','shopping-mall','-o','json'], text=True))['items']


def walk(items):
    for item in items:
        yield item
        yield from walk(item.get('components', []))


def properties(values):
    return [{'name': k, 'value': str(v)} for k,v in values.items()]


def matched_build(builds, digest):
    matches = [b for b in builds if b['status'].get('phase') == 'Complete' and
               b['status'].get('output',{}).get('to',{}).get('imageDigest') == digest]
    if len(matches) != 1:
        raise ValueError(f'Expected one completed build for {digest}, found {len(matches)}')
    return matches[0]


def merge_dependency(doc, ref, target):
    dep = next((d for d in doc.setdefault('dependencies',[]) if d['ref'] == ref), None)
    if dep is None:
        dep = {'ref':ref,'dependsOn':[]};doc['dependencies'].append(dep)
    dep['dependsOn'] = sorted(set(dep['dependsOn'] + [target]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization-file')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--repo-url')
    parser.add_argument('--branch')
    parser.add_argument('--provenance-file')
    parser.add_argument('--build-evidence-file')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    spec=importlib.util.spec_from_file_location('api', ROOT/'scripts/concert-audit-api.py')
    api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
    client=api.Concert(authorization=args.authorization_file)
    app=client.request(api.APP+'/sbom')
    deploy=client.request(f'/concert/core/api/v2/environments/{ENV_ID}/deployments/{DEPLOY_ID}/sbom')
    (OUT/'before-application.json').write_text(json.dumps(app,indent=2))
    (OUT/'before-deployment.json').write_text(json.dumps(deploy,indent=2))
    compact_properties(app)
    compact_properties(deploy)
    builds=[] if args.build_evidence_file else oc('builds')
    external_builds={b['name']:b for b in json.loads(pathlib.Path(args.build_evidence_file).read_text())} if args.build_evidence_file else {}
    routes,deployments=oc('routes'),oc('deployments')
    internal = collect(oc('services'), OUT)
    internal['restored_application_services'] = restore_application_services(app, deploy, internal)
    enrich(app, internal)
    enrich(deploy, internal, deployment=True)
    images={d['metadata']['name']:identity(d['spec']['template']['spec']['containers'][0]['image']) for d in deployments}
    remote=args.repo_url or subprocess.check_output(['git','remote','get-url','origin'],cwd=ROOT,text=True).strip().removesuffix('.git')
    from urllib.parse import urlparse
    parsed=urlparse(remote)
    if parsed.scheme!='https' or parsed.hostname not in {'github.com','github.ibm.com'} or len(parsed.path.strip('/').split('/'))!=2:
        raise ValueError('Expected an HTTPS GitHub repository URL')
    repo_name=parsed.path.strip('/').split('/')[-1]
    branch=args.branch or subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    app['metadata']['timestamp']=now;deploy['metadata']['timestamp']=now
    records=[]
    for name in sorted(OWN):
        comp=next(x for x in app['components'] if x['name']==name)
        code={'bom-ref':'code:'+repo_name,'type':'code','name':repo_name,'purl':remote,'branch':branch}
        comp['components']=[x for x in comp['components'] if not (x['type']=='code' and x.get('purl') in {remote,os.environ.get('CONCERT_PREVIOUS_REPO_URL')})]+[code]
        repo,digest=images[name]
        if args.build_evidence_file:
            recorded=external_builds[name]
            if identity(recorded['image'])!=(repo,digest):raise ValueError('Deployment and build digest mismatch')
            revision=recorded['git_commit']
            evidence={'build.engine':'github-actions','build.name':recorded['build'],'build.url':recorded['run_url'],
                      'source.repository':remote,'source.context_dir':'services/'+name,'source.revision_status':'verified_clean_checkout',
                      'source.git_commit':revision,'image.digest':digest}
        else:
            build=matched_build(builds,digest);revision=build['spec'].get('revision',{}).get('git',{}).get('commit')
            evidence={'build.name':build['metadata']['name'],'build.uid':build['metadata']['uid'],
                      'build.source_type':build['spec']['source']['type'],'source.repository':remote,
                      'source.context_dir':'services/'+name,'source.revision_status':'recorded' if revision else 'not_recorded_in_binary_build','image.digest':digest}
        if args.provenance_file:
            provenance=json.loads(pathlib.Path(args.provenance_file).read_text())
            # Concert repository scans are branch-scoped in this installation.
            # Keep that key stable; immutable commit evidence lives on each image/workload.
            code.pop('commit_sha',None)
            code['properties']=properties({'source.latest_scanned_commit':provenance['git_base_commit'],'source.scope':'branch'})
            evidence.update({'source.snapshot_sha256':provenance['archive_sha256'],'source.git_base_commit':provenance['git_base_commit'],'source.git_dirty':str(provenance['dirty']).lower(),'pipeline.run':provenance['run_id']})
        image_definition = next(x for x in comp['components'] if x['type']=='image')
        image_definition['properties'] = [p for p in image_definition.get('properties',[]) if p['name'] not in evidence] + properties(evidence)
        file=OUT/(name+'.build-evidence.json')
        file.write_text(json.dumps(evidence,indent=2))
        # Store the evidence in the existing deployment component as well.
        workload=next(x for x in walk(deploy['runtime-components']) if x['type']=='deployment' and x['name']==name)
        for deployed_image in workload.get('components',[]):
            if deployed_image['type']=='image':deployed_image['uri']=repo+'@'+digest
        workload['properties']=[p for p in workload.get('properties',[]) if p['name'] not in evidence]+properties(evidence)
        records.append({'component':name,**evidence,'commit_sha':revision})
    public=[]
    managed_public = {'api-gateway-public','frontend-public','langflow-public'}
    app['services']=[s for s in app.get('services',[]) if s['name'] not in managed_public]
    deploy['services']=[s for s in deploy.get('services',[]) if s['name'] not in managed_public]
    # Remove only this script's public service edges; preserve internal edges.
    for doc in [app,deploy]:
        for d in doc.get('dependencies',[]):
            d['dependsOn']=[r for r in d['dependsOn'] if r not in {'service:'+n for n in managed_public}]
    for route in routes:
        name=route['metadata']['name'];target=route['spec']['to']['name']
        # The isolated certificate lab is inventoried by its dedicated certificate workflow.
        # Keep it out of the production app's three managed public services.
        if name=='certificate-demo' and target=='frontend' and route['metadata'].get('labels',{}).get('langflow-shop.dev/certificate-demo')=='true':
            continue
        if name not in {'frontend','api-gateway','langflow'} or target!=name:
            raise ValueError('Review unexpected Route target: '+name)
        if not any(c.get('type')=='Admitted' and c.get('status')=='True' for ing in route.get('status',{}).get('ingress',[]) for c in ing.get('conditions',[])):
            raise ValueError('Route not admitted: '+name)
        base='https://'+route['spec']['host'];paths=['/']
        if name in {'api-gateway','langflow'}:
            with urllib.request.urlopen(base+'/openapi.json',timeout=30) as r: schema=json.load(r)
            (OUT/(name+'.openapi.json')).write_text(json.dumps(schema))
            if name=='api-gateway':paths=sorted(schema['paths'])
            else:paths=['/']+[p for p in schema['paths'] if p.startswith('/api/v1/run/')]
        service_name=name+'-public';sr='service:'+service_name
        props=properties({'kubernetes.route':name,'kubernetes.namespace':'shopping-mall',
                          'route.target_service':target,'route.tls_termination':route['spec']['tls']['termination'],
                          'source':'OpenShift Route and live OpenAPI; public denotes network exposure, not anonymous access'})
        app_service={'bom-ref':sr,'name':service_name,'network-exposure':'public','endpoints':paths,'properties':props}
        deploy_service={'bom-ref':sr,'name':service_name,'network_exposure':'public',
                        'base-url':base,'port':443,'endpoints':paths,'properties':props}
        app['services'].append(app_service);deploy['services'].append(deploy_service)
        for doc in [app,deploy]:
            merge_dependency(doc,'image:'+name,sr)
        public.append({'service':service_name,'url':base,'route':name,'target_service':target,'endpoints':paths})
    appfile=OUT/'application.cdef.json';appfile.write_text(json.dumps(app,indent=2))
    depfile=OUT/'deployment.cdef.json';depfile.write_text(json.dumps(deploy,indent=2))
    report={'repository':remote,'branch':branch,'provenance':records,'public_services':public,
            'internal_endpoints':internal,
            'revision_limit':('Repository SCA is branch-scoped; the build commit is verified in OCI labels and deployment evidence.' if args.build_evidence_file else 'Binary builds have no recorded commit SHA; branch association is declared, not commit attestation.')}
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'builds':len(records),'routes':len(public),'apply':args.apply}),flush=True)
    if args.apply:
        for file in [appfile,depfile]:
            response=client.upload(file,'application_sbom',{})
            (OUT/(file.stem+'.ingestion.json')).write_text(json.dumps(response,indent=2))
            client.wait_for_upload(response)
            print('Processed '+file.name,flush=True)
        verify_document(client.request(api.APP+'/sbom'), internal)
        verify_document(client.request(f'/concert/core/api/v2/environments/{ENV_ID}/deployments/{DEPLOY_ID}/sbom'), internal, deployment=True)
        print(json.dumps({'internal_openapi_verified':True,'api_services':internal['api_services'],
                          'api_paths':internal['api_paths'],'internal_endpoints':internal['endpoint_count']}),flush=True)

if __name__=='__main__':main()
