#!/usr/bin/env python3
"""Native Concert workflow: evidence → constrained PR → per-environment verification."""
import argparse,importlib.util,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def build(config, evidence_only=False):
    for role in ['staging','production']:
        assert config[role+'_environment_id'] and config[role+'_deployment_prefix']
    def fn(name,code):return {'name':name,'function':code}
    def request(name,path):
        query={'page_size':2000}
        if name.endswith('_packages') or name.endswith('_cve_findings'):query['uncorrelated']=True
        return {'name':name,'action':'system/Common/HTTP/HTTP Request','inputs':[
            {'name':'method','value':'"GET"'},{'name':'host','value':'"https://"+$config.concert_host'},
            {'name':'path','value':path},{'name':'authKey','value':'$config.concert_auth'},
            {'name':'headers','value':'{"Accept":"application/json","InstanceID":"0000-0000-0000-0000"}'},
            {'name':'query','value':json.dumps(query)},{'name':'rejectUnauthorized','value':'true'},{'name':'timeout','value':'60'}]}
    scope=[]
    # Resolve each latest pipeline-owned deployment on every run, not a pinned old release.
    for role in ['staging','production']:
        scope.append(request('List_'+role+'_deployments','"/concert/core/api/v2/environments/"+$config.'+role+'_environment_id+"/deployments"'))
    scope.append(fn('Select_latest_deployments',r'''
const application=$config.application_api.split("/")[6];
for(const role of ["staging","production"]){
 const response=role==="staging"?$List_staging_deployments:$List_production_deployments;
 if(response.statusCode!==200)throw new Error("Cannot list "+role+" deployments");
 const doc=typeof response.result==="string"?JSON.parse(response.result):response.result;
 if(doc.pagination.total_count>2000)throw new Error("Deployment pagination limit");
 const prefix=role==="staging"?$config.staging_deployment_prefix:$config.production_deployment_prefix;
 if(!prefix)throw new Error("Missing pipeline deployment prefix");
 const candidates=doc.deployments.filter(d=>d.application_id===application&&d.name.startsWith(prefix)).sort((a,b)=>b.created_on-a.created_on);
 if(!candidates.length || (candidates.length>1&&candidates[0].created_on===candidates[1].created_on))throw new Error("No unambiguous latest pipeline deployment");
 $config={...$config,[role+"_deployment_id"]:candidates[0].id};
}
'''))
    for role in ['staging','production']:
        scope.append(request('Read_'+role+'_deployment','"/concert/core/api/v2/environments/"+$config.'+role+'_environment_id+"/deployments/"+$config.'+role+'_deployment_id+"/sbom"'))
    scope += [request('Read_build_artifacts','"/concert/core/api/v2/build_artifacts"'),fn('Select_service_artifact',r'''
if($Read_build_artifacts.statusCode!==200)throw new Error("Cannot read artifact groups");
const groups=typeof $Read_build_artifacts.result==="string"?JSON.parse($Read_build_artifacts.result):$Read_build_artifacts.result;
if(groups.pagination.total_count>2000)throw new Error("Artifact group pagination limit");
const matches=groups.build_artifacts.filter(a=>a.name===$config.policy.service&&a.type==="image");
if(matches.length!==1)throw new Error("No unique service artifact group");
$targetBuildArtifact=matches[0].id;
'''),request('Read_image_instances','"/concert/core/api/v2/build_artifacts/"+$targetBuildArtifact+"/instances"'),fn('Resolve_current_runtime_images',r'''
for(const r of [$Read_image_instances,$Read_staging_deployment,$Read_production_deployment]){if(r.statusCode!==200)throw new Error("Runtime evidence HTTP "+r.statusCode);}
const inventory=typeof $Read_image_instances.result==="string"?JSON.parse($Read_image_instances.result):$Read_image_instances.result;
if(inventory.pagination.total_count>2000)throw new Error("Artifact pagination limit");
const stagingDoc=typeof $Read_staging_deployment.result==="string"?JSON.parse($Read_staging_deployment.result):$Read_staging_deployment.result;
const stagingImages=stagingDoc["runtime-components"].flatMap(c=>c.components||[]).flatMap(c=>c.components||[]).flatMap(c=>c.components||[]).filter(i=>i.type==="image"&&i.name===$config.policy.service);
if(stagingImages.length!==1)throw new Error("Ambiguous staging runtime image");
const stagingURI=stagingImages[0].uri;
const stagingAt=stagingURI.lastIndexOf("@");
const stagingArtifacts=inventory.instances.filter(a=>a.name===stagingURI.slice(0,stagingAt)&&a.image_digest===stagingURI.slice(stagingAt+1));
if(stagingArtifacts.length!==1)throw new Error("No unique staging scanned artifact");
$stagingRuntime={image:stagingURI,artifact:stagingArtifacts[0].id,build_artifact:$targetBuildArtifact};
const productionDoc=typeof $Read_production_deployment.result==="string"?JSON.parse($Read_production_deployment.result):$Read_production_deployment.result;
const productionImages=productionDoc["runtime-components"].flatMap(c=>c.components||[]).flatMap(c=>c.components||[]).flatMap(c=>c.components||[]).filter(i=>i.type==="image"&&i.name===$config.policy.service);
if(productionImages.length!==1)throw new Error("Ambiguous production runtime image");
const productionURI=productionImages[0].uri;
const productionAt=productionURI.lastIndexOf("@");
const productionArtifacts=inventory.instances.filter(a=>a.name===productionURI.slice(0,productionAt)&&a.image_digest===productionURI.slice(productionAt+1));
if(productionArtifacts.length!==1)throw new Error("No unique production scanned artifact");
$productionRuntime={image:productionURI,artifact:productionArtifacts[0].id,build_artifact:$targetBuildArtifact};
''')]
    for role in ['staging','production']:
        for kind in ['packages','cve_findings']:
            scope.append(request('Read_'+role+'_'+kind,'"/concert/core/api/v2/build_artifacts/"+$'+role+'Runtime.build_artifact+"/instances/"+$'+role+'Runtime.artifact+"/'+kind+'"'))
    scope += [fn('Summarize_environment_evidence',r'''
if($Read_staging_packages.statusCode!==200)throw new Error("staging packages HTTP evidence unavailable");
const stagingPackages=typeof $Read_staging_packages.result==="string"?JSON.parse($Read_staging_packages.result):$Read_staging_packages.result;
if(stagingPackages.pagination.total_count>2000)throw new Error("Evidence pagination limit");
if($Read_staging_cve_findings.statusCode!==200)throw new Error("staging cve_findings HTTP evidence unavailable");
const stagingCveFindings=typeof $Read_staging_cve_findings.result==="string"?JSON.parse($Read_staging_cve_findings.result):$Read_staging_cve_findings.result;
if(stagingCveFindings.pagination.total_count>2000)throw new Error("Evidence pagination limit");
const stagingPackageRows=stagingPackages.packages.filter(p=>p.name.toLowerCase().replace(/_/g,"-")===$config.policy.package);
if(!stagingPackageRows.length)throw new Error("Missing staging package inventory");
const stagingTargetRows=stagingCveFindings.cve_findings.filter(f=>f.package_name.toLowerCase().replace(/_/g,"-")===$config.policy.package&&$config.policy.cves.includes(f.cve));
if($Read_production_packages.statusCode!==200)throw new Error("production packages HTTP evidence unavailable");
const productionPackages=typeof $Read_production_packages.result==="string"?JSON.parse($Read_production_packages.result):$Read_production_packages.result;
if(productionPackages.pagination.total_count>2000)throw new Error("Evidence pagination limit");
if($Read_production_cve_findings.statusCode!==200)throw new Error("production cve_findings HTTP evidence unavailable");
const productionCveFindings=typeof $Read_production_cve_findings.result==="string"?JSON.parse($Read_production_cve_findings.result):$Read_production_cve_findings.result;
if(productionCveFindings.pagination.total_count>2000)throw new Error("Evidence pagination limit");
const productionPackageRows=productionPackages.packages.filter(p=>p.name.toLowerCase().replace(/_/g,"-")===$config.policy.package);
if(!productionPackageRows.length)throw new Error("Missing production package inventory");
const productionTargetRows=productionCveFindings.cve_findings.filter(f=>f.package_name.toLowerCase().replace(/_/g,"-")===$config.policy.package&&$config.policy.cves.includes(f.cve));
$result={...$result,verification_scope:$config.policy.service+" current image in staging and production",global_cve_closed:false,environments:{
staging:{image:$stagingRuntime.image,artifact_id:$stagingRuntime.artifact,package_versions:[...new Set(stagingPackageRows.map(p=>p.version))],target_finding_rows:stagingTargetRows.length},
production:{image:$productionRuntime.image,artifact_id:$productionRuntime.artifact,package_versions:[...new Set(productionPackageRows.map(p=>p.version))],target_finding_rows:productionTargetRows.length}}};
''')]
    if evidence_only:
        return {'blocks': scope}
    from patch_catalog import load_policies
    policies=load_policies()
    spec=importlib.util.spec_from_file_location('patch_builder',Path(__file__).with_name('build-patch-workflow.py'))
    base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    flow=base.build({**config,'workflow_name':'Langflow Dependency Remediation'},policies=policies)
    # Current image evidence supplies the CVE precondition; avoid a stale source-release snapshot.
    original={b['name']:b for b in flow['blocks']}
    assess=original['05_AssessPatch']
    assess['function']=assess['function'].replace('$02_ReadConcertFindings','$Read_staging_cve_findings').replace('$03_ReadConcertInventory','$Read_staging_packages')
    flow['blocks']=[original['ReadPolicyCatalog'],original['01_ValidatePolicy'],original['04_ReadSource'],*scope[:-1],assess,scope[-1],original['06_CreatePRWhenRequested'],original['07_VerifyAfterMerge']]
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
                code=code.replace(' && packages.some(p=>p.version===$config.policy.to_version)','')
                code=code.replace('$03_ReadConcertInventory','$Read_staging_packages').replace('$02_ReadConcertFindings','$Read_staging_cve_findings')
                code=code.replace('open.length','remaining').replace('concert_package_versions:[...new Set(packages.map(p=>p.version))],','concert_package_versions:[...new Set(packages.map(p=>p.version))],same_image_in_both_environments:sameImages,')
                code=code.replace('closure:ready && remaining===0?"verified":"not_closed"','closure:ready && remaining===0?"selected_service_verified":"not_closed"')
                block['function']=code
            for key in ['then','else']:modify(block.get(key,[]))
    modify(flow['blocks'])
    flow['variables'] += [{'name':name,'isInput':False,'isOutput':False,'required':False,'level':'INTERMEDIATE','type':{'type':'any'},'value':'null'} for name in ['stagingRuntime','productionRuntime','targetBuildArtifact']]
    flow['meta']['description']='Live CVE evidence in both deployments → selected approved dependency patch PR → PR checks → staging tests → human approval → same images in production → verify current-image CVE absence. No automatic merge or approval.'
    return flow
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    flow=build(json.loads(Path(a.config).read_text()));data=json.dumps(flow,ensure_ascii=False,indent=2)+'\n'
    if Path(a.output).suffix=='.zip':
        with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(flow['name']+'.json',data)
    else:Path(a.output).write_text(data)
