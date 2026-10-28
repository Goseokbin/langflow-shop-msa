#!/usr/bin/env python3
"""Native Concert workflow: evidence → constrained PR → per-environment verification."""
import argparse,importlib.util,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('patch_builder',Path(__file__).with_name('build-patch-workflow.py'))
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

def build(config):
    policy=json.loads((ROOT/'scripts/patch-policies/multipart.json').read_text())
    for role in ['staging','production']:
        assert config[role+'_environment_id'] and config[role+'_deployment_id']
    flow=base.build({**config,'workflow_name':'Langflow Multipart CVE Promotion Demo'},policy=policy)
    def fn(name,code):return {'name':name,'function':code}
    def request(name,path):
        return {'name':name,'action':'system/Common/HTTP/HTTP Request','inputs':[
            {'name':'method','value':'"GET"'},{'name':'host','value':'"https://"+$config.concert_host'},
            {'name':'path','value':path},{'name':'authKey','value':'$config.concert_auth'},
            {'name':'headers','value':'{"Accept":"application/json","InstanceID":"0000-0000-0000-0000"}'},
            {'name':'query','value':'{"page_size":2000}'},{'name':'rejectUnauthorized','value':'true'},{'name':'timeout','value':'60'}]}
    scope=[]
    for role in ['staging','production']:
        scope.append(request('Read_'+role+'_deployment','"/concert/core/api/v2/environments/"+$config.'+role+'_environment_id+"/deployments/"+$config.'+role+'_deployment_id+"/sbom"'))
    scope += [request('Read_build_artifacts','$config.application_api+"/build_artifacts"'),fn('Resolve_current_runtime_images',r'''
function data(r){if(r.statusCode!==200)throw new Error("Concert evidence HTTP "+r.statusCode);return typeof r.result==="string"?JSON.parse(r.result):r.result;}
const inventory=data($Read_build_artifacts);if(inventory.pagination.total_count>2000)throw new Error("Artifact pagination limit");
function resolve(doc){
 let images=[];function walk(x){if(Array.isArray(x))return x.forEach(walk);if(x&&typeof x==="object"){if(x.type==="image"&&x.name===$config.policy.service)images.push(x.uri);Object.values(x).forEach(walk);}}
 walk(doc["runtime-components"]);images=[...new Set(images)];if(images.length!==1)throw new Error("Ambiguous runtime image");
 const uri=images[0],at=uri.lastIndexOf("@"),name=uri.slice(0,at),digest=uri.slice(at+1);
 const matches=inventory.build_artifacts.filter(a=>a.name===name&&a.digest===digest);if(matches.length!==1)throw new Error("Runtime image has no unique scanned artifact");
 return {image:uri,artifact:matches[0].id};
}
$stagingRuntime=resolve(data($Read_staging_deployment));$productionRuntime=resolve(data($Read_production_deployment));
''')]
    for role in ['staging','production']:
        for kind in ['packages','cve_findings']:
            scope.append(request('Read_'+role+'_'+kind,'$config.application_api+"/build_artifacts/"+$'+role+'Runtime.artifact+"/'+kind+'"'))
    scope += [fn('Summarize_environment_evidence',r'''
function data(r){if(r.statusCode!==200)throw new Error("Concert image evidence HTTP "+r.statusCode);let d=typeof r.result==="string"?JSON.parse(r.result):r.result;if(d.pagination.total_count>2000)throw new Error("Evidence pagination limit");return d;}
function snapshot(runtime,p,v){let ps=data(p).packages.filter(p=>p.name.toLowerCase().replace(/_/g,"-")===$config.policy.package);if(!ps.length)throw new Error("Missing package inventory");let vs=data(v).cve_findings.filter(f=>f.package_name.toLowerCase().replace(/_/g,"-")===$config.policy.package&&$config.policy.cves.includes(f.cve));return {image:runtime.image,artifact_id:runtime.artifact,package_versions:[...new Set(ps.map(p=>p.version))],target_finding_rows:vs.length};}
$result={...$result,environments:{staging:snapshot($stagingRuntime,$Read_staging_packages,$Read_staging_cve_findings),production:snapshot($productionRuntime,$Read_production_packages,$Read_production_cve_findings)}};
''')]
    flow['blocks'][5:5]=scope
    def modify(xs):
        for block in xs:
            if block.get('name')=='VerifyDeploymentEvidence':
                code=block['function'];start=code.index('const open=');end=code.index('const sourceMatchesRelease=',start)
                code=code[:start]+'''const snapshots=$result.environments;
const remaining=snapshots.staging.target_finding_rows+snapshots.production.target_finding_rows;
const bothFixed=Object.values(snapshots).every(e=>e.package_versions.length===1&&e.package_versions[0]===$config.policy.to_version&&e.target_finding_rows===0);
const sameImages=snapshots.staging.image===snapshots.production.image;
'''+code[end:]
                code=code.replace('const ready=$alreadyFixed','const ready=bothFixed && sameImages && $alreadyFixed')
                code=code.replace('open.length','remaining').replace('concert_package_versions:[...new Set(packages.map(p=>p.version))],','concert_package_versions:[...new Set(packages.map(p=>p.version))],same_image_in_both_environments:sameImages,')
                block['function']=code
            for key in ['then','else']:modify(block.get(key,[]))
    modify(flow['blocks'])
    flow['variables'] += [{'name':name,'isInput':False,'isOutput':False,'required':False,'level':'INTERMEDIATE','type':{'type':'any'},'value':'null'} for name in ['stagingRuntime','productionRuntime']]
    flow['meta']['description']='Live CVE evidence in both deployments → allowlisted python-multipart patch PR → PR checks → staging tests → human approval → same images in production → verify current-image CVE absence. No automatic merge or approval.'
    return flow
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    flow=build(json.loads(Path(a.config).read_text()));data=json.dumps(flow,ensure_ascii=False,indent=2)+'\n'
    if Path(a.output).suffix=='.zip':
        with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(flow['name']+'.json',data)
    else:Path(a.output).write_text(data)
