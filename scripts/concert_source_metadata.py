"""Keep branch-scoped mutable metadata out of repeated per-service SBOM declarations."""
import json
import re
import urllib.parse

OWNED={'source.latest_scanned_commit','source.scope'}


def normalized(url):return url.rstrip('/').removesuffix('.git')


def migrate_repository(document,previous,current):
    """Retarget declared code in a new release blueprint, preserving image provenance."""
    if not previous or normalized(previous)==normalized(current):return document
    if isinstance(document,dict):
        if document.get('type')=='code' and normalized(document.get('purl',''))==normalized(previous):
            document['purl']=normalized(current)
        for value in document.values():migrate_repository(value,previous,current)
    elif isinstance(document,list):
        for value in document:migrate_repository(value,previous,current)
    return document


def sync(client,url,branch,commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('Expected a verified source commit')
    query=urllib.parse.urlencode({'search':normalized(url),'page_size':100})
    repos=client.request('/concert/core/api/v2/source_repos?'+query)['source_repos']
    matches=[r for r in repos if normalized(r['repo_url'])==normalized(url)]
    if len(matches)!=1:raise ValueError('Expected one existing source repository')
    base='/concert/core/api/v2/source_repos/'+matches[0]['id']+'/instances'
    instances=client.request(base+'?page_size=100')['instances']
    matches=[r for r in instances if r.get('branch')==branch and not r.get('commit_sha')]
    if len(matches)!=1:raise ValueError('Expected one branch-scoped source instance')
    instance=matches[0];repo_id=base.split('/')[-2];path=base+'/'+instance['id']
    values=[{'name':'source.latest_scanned_commit','value':commit},{'name':'source.scope','value':'branch'}]
    # Two requests make ordering explicit; no unowned metadata is removed.
    client.request(path,json.dumps({'delete_properties':sorted(OWNED)}).encode(),'PATCH','application/merge-patch+json')
    client.request(path,json.dumps({'properties':values}).encode(),'PATCH','application/merge-patch+json')
    current=next(r for r in client.request(base+'?page_size=100')['instances'] if r['id']==instance['id'])
    observed=[p for p in current.get('properties',[]) if p['name'] in OWNED]
    if sorted(observed,key=lambda p:p['name'])!=sorted(values,key=lambda p:p['name']):
        raise ValueError('Owned source properties were not replaced exactly once')
    return {'repository_id':repo_id,
            'instance_id':instance['id'],'owned_properties':len(observed),'commit':commit}


def strip(document,url):
    """Immutable source/image evidence and other owners' properties stay unchanged."""
    if isinstance(document,dict):
        if document.get('type')=='code' and normalized(document.get('purl',''))==normalized(url):
            if 'properties' in document:
                document['properties']=[p for p in document['properties'] if p['name'] not in OWNED]
        for value in document.values():strip(value,url)
    elif isinstance(document,list):
        for value in document:strip(value,url)
    return document
