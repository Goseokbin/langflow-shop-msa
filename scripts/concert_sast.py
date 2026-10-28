"""Collect original CodeQL SARIF and verify Concert's real SAST ingestion."""
import json
import os
import copy
from pathlib import Path
import shutil
import time
from urllib.parse import unquote


def summarize_sarif(document):
    if document.get('version')!='2.1.0' or not document.get('runs'):
        raise ValueError('CodeQL must produce SARIF 2.1.0 with analysis runs')
    findings=[];tools=[]
    for run in document['runs']:
        driver=run['tool']['driver']
        if 'codeql' not in driver['name'].lower():raise ValueError('Expected original CodeQL analysis')
        tools.append({'name':driver['name'],'version':driver.get('semanticVersion',driver.get('version','unknown'))})
        for invocation in run.get('invocations',[]):
            if invocation.get('executionSuccessful') is False:raise ValueError('CodeQL invocation did not succeed')
        rules={r['id']:r for component in [driver,*run['tool'].get('extensions',[])] for r in component.get('rules',[])}
        for result in run.get('results',[]):
            rule=result.get('ruleId') or result.get('rule',{}).get('id')
            if not rule or rule not in rules:raise ValueError('SAST result references an unknown rule')
            rule_data=rules[rule];props=rule_data.get('properties',{})
            locations=[]
            for loc in result.get('locations',[]):
                physical=loc.get('physicalLocation',{});uri=unquote(physical.get('artifactLocation',{}).get('uri',''))
                line=physical.get('region',{}).get('startLine')
                if uri and not uri.startswith('file:') and not Path(uri).is_absolute() and line:
                    locations.append({'file':uri,'line':line})
            if not locations:raise ValueError('CodeQL finding lacks a relative source file and line')
            findings.append({'rule_id':rule,'severity':result.get('level',rule_data.get('defaultConfiguration',{}).get('level','warning')),
                             'security_severity':props.get('security-severity'),'cwe_tags':[x for x in props.get('tags',[]) if 'cwe' in x.lower()],
                             'message':result.get('message',{}).get('text',''),'locations':locations})
    return {'tools':tools,'findings':findings,'finding_count':len(findings),'rules':sorted({f['rule_id'] for f in findings})}


def normalize_sarif(document):
    """Flatten tool-component rules for collectors that read driver.rules only."""
    result=copy.deepcopy(document)
    for run in result['runs']:
        rules={r['id']:r for component in [run['tool']['driver'],*run['tool'].get('extensions',[])] for r in component.get('rules',[])}
        run['tool']['driver']['rules']=list(rules.values())
        indices={rule:index for index,rule in enumerate(rules)}
        for finding in run.get('results',[]):
            rule=finding.get('ruleId') or finding.get('rule',{}).get('id')
            if rule not in indices:raise ValueError('Unknown SARIF rule')
            finding['ruleId']=rule;finding['ruleIndex']=indices[rule]
            finding['rule']={'id':rule,'index':indices[rule]}
    return result


def merge_sarif(documents):
    """Keep one repository scan snapshot, preserving all real language results."""
    first=documents[0]['runs'][0]
    driver=copy.deepcopy(first['tool']['driver']);rules={};results=[];invocations=[]
    for document in documents:
        normalized=normalize_sarif(document)
        for run in normalized['runs']:
            for rule in run['tool']['driver']['rules']:rules[rule['id']]=rule
            artifacts=run.get('artifacts',[])
            invocation_offset=len(invocations);invocations.extend(copy.deepcopy(run.get('invocations',[])))
            def expand_artifact_references(node):
                if isinstance(node,list):
                    for item in node:expand_artifact_references(item)
                elif isinstance(node,dict):
                    if isinstance(node.get('artifactLocation'),dict):
                        loc=node['artifactLocation'];index=loc.get('index')
                        if 'uri' not in loc and index is not None:loc.update(artifacts[index]['location'])
                        loc.pop('index',None)
                    for value in node.values():expand_artifact_references(value)
            for finding in copy.deepcopy(run.get('results',[])):
                expand_artifact_references(finding)
                provenance=finding.get('provenance',{})
                if 'invocationIndex' in provenance:provenance['invocationIndex']+=invocation_offset
                results.append(finding)
    driver['rules']=list(rules.values());indices={key:i for i,key in enumerate(rules)}
    for finding in results:
        rule=finding['ruleId'];finding['ruleIndex']=indices[rule];finding['rule']={'id':rule,'index':indices[rule]}
    run={'tool':{'driver':driver},'results':results,'invocations':invocations}
    for key in ['versionControlProvenance','taxonomies','columnKind']:
        if key in first:run[key]=copy.deepcopy(first[key])
    merged={'version':'2.1.0','$schema':'https://json.schemastore.org/sarif-2.1.0.json','runs':[run]}
    before=[finding for doc in documents for finding in summarize_sarif(doc)['findings']]
    if summarize_sarif(merged)['findings']!=before:raise ValueError('SARIF merge changed actual findings')
    return merged


def collect(work):
    destination=work/'output/sast';destination.mkdir(parents=True,exist_ok=True)
    files=sorted((work/'codeql-results').glob('*.sarif'))
    if len(files)!=2:raise ValueError(f'Expected Python and JavaScript SARIF, got {len(files)}')
    analyses=[];documents=[]
    for file in files:
        document=json.loads(file.read_text());documents.append(document)
        row=summarize_sarif(document)
        if 'python' not in file.stem and 'javascript' not in file.stem:raise ValueError('Unexpected CodeQL language report')
        raw=destination/'original';raw.mkdir(exist_ok=True);shutil.copy2(file,raw/file.name)
        normalized=normalize_sarif(json.loads(file.read_text()))
        target=destination/(file.stem+'.json');target.write_text(json.dumps(normalized))
        if summarize_sarif(normalized)['findings']!=row['findings']:raise ValueError('SARIF normalization changed actual findings')
        analyses.append({'language':file.stem,'file':target.name,**row})
    if not any('python' in a['language'] for a in analyses) or not any('javascript' in a['language'] for a in analyses):
        raise ValueError('Both Python and JavaScript/TypeScript analyses must complete')
    (destination/'codeql.json').write_text(json.dumps(merge_sarif(documents)))
    summary={'merged_file':'codeql.json','analyses':analyses,'finding_count':sum(a['finding_count'] for a in analyses),
             'rules':sorted({r for a in analyses for r in a['rules']}),'scope':'services/','query_suite':'security-extended'}
    (work/'output/sast-scan.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary


def verify(client,api,work):
    summary=json.loads((work/'output/sast-scan.json').read_text())
    manifest=json.loads((work/'source-manifest.json').read_text())
    repositories=client.request(api.APP+'/source_repos?page_size=2000')['source_repos']
    repository=next(r for r in repositories if r['repo_url'].removesuffix('.git')==manifest['repository'] and r.get('branch')==manifest['branch'])
    deadline=time.monotonic()+180
    while True:
        response=client.request(api.APP+'/exposures?show_unique=true&page_size=2000')
        (work/'output/sast-concert-exposures.json').write_text(json.dumps(response,ensure_ascii=False,indent=2))
        repo_response=client.request(api.APP+'/source_repos/'+repository['id']+'/exposures?show_unique=true&page_size=2000')
        (work/'output/sast-concert-repository.json').write_text(json.dumps(repo_response,ensure_ascii=False,indent=2))
        serialized=json.dumps(response)
        repo_serialized=json.dumps(repo_response)
        missing=[rule for rule in summary['rules'] if rule not in serialized or rule not in repo_serialized]
        if not missing:break
        if time.monotonic()>deadline:raise RuntimeError('Concert SAST rules not linked: '+', '.join(missing))
        time.sleep(5)
    result={'source_findings':summary['finding_count'],'source_rules':summary['rules'],'matched_rules':len(summary['rules'])-len(missing),
            'concert_rule_groups':response.get('pagination',{}).get('total_count',len(response.get('exposures',[]))),
            'application_verified':True,'repository_verified':True,'repository_rule_groups':repo_response.get('pagination',{}).get('total_count',0),'scope':'services/','query_suite':'security-extended'}
    (work/'output/sast-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def ingest(work,manifest,stages,authorization):
    summary=json.loads((work/'output/sast-scan.json').read_text())
    metadata={'repo_url':manifest['repository'],'repo_name':manifest['repo_name'],'branch':manifest['branch'],'branch_name':manifest['branch'],
              'scanner_name':'CodeQL','application_name':os.environ.get('APPLICATION_NAME','langflow-shop'),'application_version':os.environ.get('APPLICATION_VERSION','1.0.0')}
    client=stages.api.Concert(authorization=authorization)
    stages.upload(client,work/'output/sast'/summary['merged_file'],'static_code_scan',metadata)
    return verify(client,stages.api,work)
