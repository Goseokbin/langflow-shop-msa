"""Keep a distinct Concert application release for each immutable source revision."""
import copy
import datetime
import json
import os
import re
from pathlib import Path


def release_version(commit,prefix='1.0.1'):
    if not re.fullmatch(r'[a-f0-9]{40}',commit) or not re.fullmatch(r'\d+\.\d+\.\d+',prefix):
        raise ValueError('Expected a full source SHA and semantic release prefix')
    return prefix+'-'+commit[:12]


def validate_application_api(path,template):
    pattern=r'/concert/core/api/v2/applications/([a-f0-9-]{36})/versions/([a-f0-9-]{36})'
    result=re.fullmatch(pattern,path);base=re.fullmatch(pattern,template)
    if not result or not base or result[1]!=base[1]:raise ValueError('Release may not select a different Concert application')
    return path


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
        doc=copy.deepcopy(client.request(template+'/sbom'))
        doc['metadata'].update({'application-version':version,'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat()})
        destination.parent.mkdir(parents=True,exist_ok=True)
        blueprint=destination.with_name('release-blueprint.json');blueprint.write_text(json.dumps(doc))
        client.wait_for_upload(client.upload(blueprint,'application_sbom',{}),timeout=900)
        matches=[v for v in client.request(parent+'/versions?page_size=2000')['versions'] if v['version']==version]
    if len(matches)!=1:raise ValueError('Concert release was not uniquely created')
    result={'commit':manifest['git_base_commit'],'version':version,'application_api':parent+'/versions/'+matches[0]['id']}
    validate_application_api(result['application_api'],template)
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(result,indent=2))
    return result
