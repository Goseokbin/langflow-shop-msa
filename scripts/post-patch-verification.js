// Read-only verification of the current scanned images in two deployments.
const documents={};
for(const role of ["staging","production"]){
 const packageResponse=role==="staging"?$Read_staging_packages:$Read_production_packages;
 const cveResponse=role==="staging"?$Read_staging_cve_findings:$Read_production_cve_findings;
 if(packageResponse.statusCode!==200||cveResponse.statusCode!==200)throw new Error("Missing "+role+" scan evidence");
 const inventory=typeof packageResponse.result==="string"?JSON.parse(packageResponse.result):packageResponse.result;
 const findings=typeof cveResponse.result==="string"?JSON.parse(cveResponse.result):cveResponse.result;
 if(inventory.pagination.total_count>2000||findings.pagination.total_count>2000)throw new Error("Evidence pagination requires extension");
 if(inventory.packages.length>=2000||findings.cve_findings.length>=2000)throw new Error("Evidence page may be incomplete");
 const packages=inventory.packages.filter(p=>p.name.toLowerCase().replace(/_/g,"-")===$expected_package.toLowerCase().replace(/_/g,"-"));
 const target=findings.cve_findings.filter(f=>f.cve===$cve);
 const runtime=role==="staging"?$stagingRuntime:$productionRuntime;
 documents[role]={image:runtime.image,artifact_id:runtime.artifact,release:$deploymentSnapshots[role].application_version,package_versions:[...new Set(packages.map(p=>p.version))].sort(),target_cve_rows:target.length,inventory_present:packages.length>0};
}
if($Read_release_runs.statusCode!==200)throw new Error("Missing deployment pipeline evidence");
const runDoc=typeof $Read_release_runs.result==="string"?JSON.parse($Read_release_runs.result):$Read_release_runs.result;
if(!Array.isArray(runDoc.workflow_runs)||!runDoc.workflow_runs.length)throw new Error("No deployment pipeline evidence");
function sourceCommit(response){
 if(!response||response.statusCode!==200)return null;
 const doc=typeof response.result==="string"?JSON.parse(response.result):response.result;
 const found=new Set();
 function walk(x){if(Array.isArray(x))x.forEach(walk);else if(x&&typeof x==="object"){
  if(["source.commit","source.git_base_commit"].includes(x.name)&&/^[a-f0-9]{40}$/.test(x.value))found.add(x.value);
  Object.values(x).forEach(walk);
 }}
 walk(doc);return found.size===1?[...found][0]:null;
}
const devCommit=sourceCommit(typeof $Read_staging_deployment==="undefined"?null:$Read_staging_deployment);
const prodCommit=sourceCommit(typeof $Read_production_deployment==="undefined"?null:$Read_production_deployment);
const compatible=runDoc.workflow_runs.filter(r=>documents.production.release.endsWith("-"+r.head_sha.slice(0,12))||(devCommit&&devCommit===prodCommit&&r.head_sha===devCommit));
const run=compatible[0]||runDoc.workflow_runs[0];
const sameImage=documents.staging.image===documents.production.image;
const matchingRelease=documents.staging.release===documents.production.release&&(documents.production.release.endsWith("-"+run.head_sha.slice(0,12))||(devCommit&&devCommit===prodCommit&&run.head_sha===devCommit));
const pipelineSucceeded=run.status==="completed"&&run.conclusion==="success";
const inventoryComplete=documents.staging.inventory_present&&documents.production.inventory_present;
const bothClear=documents.staging.target_cve_rows===0&&documents.production.target_cve_rows===0;
const verified=bothClear&&sameImage&&matchingRelease&&pipelineSucceeded&&inventoryComplete;
const verdict=verified?"verified":documents.staging.target_cve_rows===0&&documents.production.target_cve_rows>0?"awaiting_production":!bothClear?"target_present":"verification_incomplete";
const environmentLabel=(d)=>d.release+" | "+$expected_package+" "+(d.package_versions.join(", ")||"inventory missing")+" | "+$cve+": "+d.target_cve_rows;
const nextAction=verdict==="verified"?"운영 반영과 대상 CVE 제거 확인 완료":verdict==="awaiting_production"?"Dev 패치 확인 완료 · 운영 승인/승격 대기":verdict==="target_present"?"대상 취약점이 남아 있습니다 · 패치 PR과 Dev 검증 필요":"스캔·배포 증거를 확인하세요";
$result={verdict:verdict,dev_status:environmentLabel(documents.staging),production_status:environmentLabel(documents.production),next_action:nextAction,verified:verified,writes_enabled:false,service:$service,expected_package:$expected_package,cve:$cve,environments:documents,checks:{both_target_cve_clear:bothClear,both_package_inventories_present:inventoryComplete,same_image_in_both_environments:sameImage,matching_release:matchingRelease,pipeline_succeeded:pipelineSucceeded},pipeline:run.html_url,evaluated_at:new Date().toISOString(),scope:"Current images recorded by the deployment pipeline in Concert; no ticket, owner, SLA, assessment or deployment is modified."};
