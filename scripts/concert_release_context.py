"""Keep a distinct Concert application release for each immutable source revision."""
import copy
import datetime
import json
import os
import re
import time
from pathlib import Path


def release_version(commit,prefix='1.0.1'):
    if not re.fullmatch(r'[a-f0-9]{40}',commit) or not re.fullmatch(r'\d+\.\d+\.\d+',prefix):
        raise ValueError('Expected a full source SHA and semantic release prefix')
    return prefix+'-'+commit[:12]


def deployment_name_for_release(name,old_version,new_version):
    if old_version==new_version:return name
    suffix='_'+old_version
    result=(name[:-len(suffix)] if name.endswith(suffix) else name)+'_'+new_version
    if len(result)>128:raise ValueError('Deployment name exceeds Concert limit')
    return result


def validate_application_api(path,template):
    pattern=r'/concert/core/api/v2/applications/([a-f0-9-]{36})/versions/([a-f0-9-]{36})'
    result=re.fullmatch(pattern,path);base=re.fullmatch(pattern,template)
    if not result or not base or result[1]!=base[1]:raise ValueError('Release may not select a different Concert application')
    return path


def blueprint_signature(doc):
    components=sorted((c['name'],sorted((x['type'],x['name'],x.get('purl',''),x.get('branch','')) for x in c.get('components',[]))) for c in doc.get('components',[]))
    # Runtime-enriched exposure and API paths are verified after deploy in stage 09.
    services=sorted({s['name'] for s in doc.get('services',[])})
    return components,services


def blueprint_matches(actual,expected):
    observed_components,observed_services=blueprint_signature(actual)
    expected_components,expected_services=blueprint_signature(expected)
    if not set(expected_services).issubset(observed_services) or not all(c in observed_components for c in expected_components):return False
    repositories={v['purl'] for c in expected.get('components',[]) for v in c.get('components',[]) if v['type']=='code' and v.get('purl')}
    extras=[c for c in observed_components if c not in expected_components]
    return all(name in repositories and all(kind=='code' and purl in repositories for kind,_,purl,_ in children) for name,children in extras)


def wait_for_blueprint(client,response,parent,version,expected,timeout=900):
    deadline=time.monotonic()+timeout
    while True:
        evidence=[]
        for event in response.get('event_ids',[]):
            query={'filters':{'logic':'and','conditions':[{'field':'event_id','value':event,'operator':'='}]},'pagination':{'page':1,'page_size':50}}
            records=client.request('/concert/ingestion/api/v1/table_of_contents/lz/advanced_search',json.dumps(query).encode(),'POST','application/json').get('toc_records',[])
            if not records:break
            record=records[0];status=record.get('status','')
            if status.startswith('error') or 'failed' in status:raise ValueError('Application blueprint ingestion failed')
            for item in record.get('metadata',[]):
                if item['name']=='component_api_result':
                    result=json.loads(item['value'])
                    if result.get('status',{}).get('code') in [200,201] and result.get('status',{}).get('message_code')=='processSbomSuccessMsg':
                        evidence.append(result['result'])
            if status=='processing_completed' and not evidence:evidence.append({'release_id':None})
        if evidence:
            versions=client.request(parent+'/versions?page_size=2000')['versions']
            matches=[v for v in versions if v['version']==version]
            if len(matches)==1 and all(e.get('release_id') in [None,matches[0]['id']] for e in evidence):
                actual=client.request(parent+'/versions/'+matches[0]['id']+'/sbom')
                if actual['metadata']['application-version']==version and blueprint_matches(actual,expected):
                    return 'core_success_and_blueprint_readback'
        if time.monotonic()>=deadline:raise ValueError('Application blueprint completion could not be verified')
        time.sleep(3)


def configure(client,template,manifest,destination,prefix='1.0.1'):
    destination=Path(destination);version=release_version(manifest['git_base_commit'],prefix)
    if destination.exists():
        result=json.loads(destination.read_text())
        if result['commit']!=manifest['git_base_commit'] or result['version']!=version:raise ValueError('Concert context belongs to another source revision')
        validate_application_api(result['application_api'],template)
        return result
    parent=template.rsplit('/versions/',1)[0]
    response=client.request(parent+'/versions?page_size=2000')
    if response['pagination']['total_count']>2000:raise ValueError('Application version pagination limit')
    matches=[v for v in response['versions'] if v['version']==version]
    if not matches:
        from concert_internal_endpoints import compact_properties
        from concert_source_metadata import migrate_repository,strip
        doc=copy.deepcopy(client.request(template+'/sbom'))
        # The old URL remains in historical releases and image provenance. Only
        # declared code in this new release uses the configured transfer target.
        migrate_repository(doc,os.environ.get('CONCERT_PREVIOUS_REPO_URL',''),manifest['repository'])
        doc=strip(compact_properties(doc),manifest['repository'])
        doc['metadata'].update({'application-version':version,'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat()})
        destination.parent.mkdir(parents=True,exist_ok=True)
        blueprint=destination.with_name('release-blueprint.json');blueprint.write_text(json.dumps(doc))
        wait_for_blueprint(client,client.upload(blueprint,'application_sbom',{}),parent,version,doc)
        matches=[v for v in client.request(parent+'/versions?page_size=2000')['versions'] if v['version']==version]
    if len(matches)!=1:raise ValueError('Concert release was not uniquely created')
    result={'commit':manifest['git_base_commit'],'version':version,'application_api':parent+'/versions/'+matches[0]['id']}
    validate_application_api(result['application_api'],template)
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(result,indent=2))
    return result
