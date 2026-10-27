#!/usr/bin/env python3
"""Generate a native Concert Workflows v5 flow using authenticated HTTP and constrained functions.
Credentials are authentication references, never embedded values. Import generated JSON in Workflows.
"""
import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / 'scripts/patch-policy.json').read_text())


def build(config):
    required = ['repository', 'concert_host', 'application_api', 'source_repo_id', 'github_auth', 'concert_auth']
    if any(not config.get(k) for k in required):
        raise ValueError('Missing required non-secret configuration')
    if not config['application_api'].startswith('/concert/core/api/v2/applications/'):
        raise ValueError('Expected a scoped application version API path')
    cfg = {**config, 'policy': POLICY}
    def variable(name, value='null', **kw):
        return {'name': name, 'isInput': False, 'isOutput': False, 'required': False,
                'level': 'INTERMEDIATE', 'type': {'type': 'any'}, 'value': value, **kw}
    def function(name, code):
        return {'name': name, 'function': code}
    def http(name, host, path, auth, method='GET', body=None, query=None):
        ins = {'method': json.dumps(method), 'host': host, 'path': path,
               'headers': '{"Accept":"application/json","Content-Type":"application/json","User-Agent":"Concert-Patch-Demo","InstanceID":"0000-0000-0000-0000"}',
               'authKey': auth, 'rejectUnauthorized': 'true', 'timeout': '60'}
        if body is not None:
            ins['body'] = body
        if query:
            ins['query'] = query
        return {'name': name, 'action': 'system/Common/HTTP/HTTP Request',
                'inputs': [{'name': k, 'value': v} for k, v in ins.items()]}
    gh = lambda name, path, **kw: http(name, '"https://api.github.com"', path, '$config.github_auth', **kw)
    concert_path = '$config.application_api + "/source_repos/" + $config.source_repo_id'
    prefix = '"/repos/" + $config.repository'
    blocks = [function('01_ValidatePolicy', r'''
if (!["plan", "create-pr", "verify"].includes($operation)) throw new Error("Unsupported operation");
if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test($config.repository)) throw new Error("Invalid repository");
if ($config.policy.package !== "requests" || $config.policy.to_version !== "2.33.0") throw new Error("Policy is not approved");
'''), http('02_ReadConcertFindings', '"https://" + $config.concert_host', concert_path + ' + "/cve_findings"', '$config.concert_auth', query='{"page_size":2000}'),
    http('03_ReadConcertInventory', '"https://" + $config.concert_host', concert_path + ' + "/packages"', '$config.concert_auth', query='{"page_size":2000}'),
    gh('04_ReadSource', prefix + ' + "/contents/" + $config.policy.file', query='{"ref":"main"}'),
    function('05_AssessPatch', '''
function json(x) { return typeof x === "string" ? JSON.parse(x) : x; }
for (const step of [$02_ReadConcertFindings,$03_ReadConcertInventory,$04_ReadSource]) {
 if (step.statusCode !== 200) throw new Error("Evidence read failed: HTTP " + step.statusCode);
}
const findings=json($02_ReadConcertFindings.result);
if (findings.pagination && findings.pagination.total_count > 2000) throw new Error("Findings pagination requires extension");
const inventory=json($03_ReadConcertInventory.result);
if (inventory.pagination && inventory.pagination.total_count > 2000) throw new Error("Inventory pagination requires extension");
const p=$config.policy;
$source=json($04_ReadSource.result);
$before=Buffer.from($source.content.replace(/\\n/g,""),"base64").toString("utf8");
$evidence=(findings.cve_findings||[]).filter(f=>f.package_name===p.package && f.package_version===p.from_version && p.cves.includes(f.cve));
$alreadyFixed=$before.split(/\\r?\\n/).includes(p.package+"=="+p.to_version);
$result={operation:$operation,package:p.package,from:p.from_version,to:p.to_version,file:p.file,
 target_cves:p.cves,concert_finding_rows:$evidence.length,status:$alreadyFixed?"source_already_patched":"patch_proposed"};
if (!$alreadyFixed) {
 const found=[...new Set($evidence.map(f=>f.cve))];
 if (!p.cves.every(c=>found.includes(c))) throw new Error("Expected Concert CVE evidence is missing");
 if ($before.split(/\\r?\\n/).filter(l=>l===p.package+"=="+p.from_version).length!==1) throw new Error("Base dependency changed; review required");
 const allowedFixed=["2.32.0","2.32.4","2.33.0"];
 if ($evidence.some(f=>!allowedFixed.some(v=>f.fixed_version==="Upgrade requests to version "+v))) throw new Error("Fix recommendation changed; review required");
 $after=$before.replace(p.package+"=="+p.from_version,p.package+"=="+p.to_version);
}
'''),
    {'action': 'if', 'name': '06_CreatePRWhenRequested', 'condition': '$operation === "create-pr" && !$alreadyFixed', 'then': [
        gh('FindExistingPR', prefix+' + "/pulls"', query='{"state":"open","head":$config.repository.split("/")[0]+":"+$config.policy.branch}'),
        function('CheckExistingPR', '''
if ($FindExistingPR.statusCode!==200) throw new Error("Cannot read existing PRs");
$existing=typeof $FindExistingPR.result==="string"?JSON.parse($FindExistingPR.result):$FindExistingPR.result;
if ($existing.length) $result={...$result,status:"existing_pr",pull_request:$existing[0].html_url,number:$existing[0].number};
'''),
        {'action': 'if', 'name': 'CreateOnlyOnce', 'condition': '$existing.length === 0', 'then': [
            gh('ReadMainCommit', prefix+' + "/git/ref/heads/main"'),
            function('RequireMainCommit', 'if ($ReadMainCommit.statusCode!==200) throw new Error("Cannot read main commit");\n$main=typeof $ReadMainCommit.result==="string"?JSON.parse($ReadMainCommit.result):$ReadMainCommit.result;'),
            gh('CreatePatchBranch', prefix+' + "/git/refs"', method='POST', body='{"ref":"refs/heads/"+$config.policy.branch,"sha":$main.object.sha}'),
            function('RequireBranch', 'if ($CreatePatchBranch.statusCode!==201 && $CreatePatchBranch.statusCode!==422) throw new Error("Cannot create patch branch");'),
            gh('ReadBranchSource', prefix+' + "/contents/"+$config.policy.file', query='{"ref":$config.policy.branch}'),
            function('GuardBranchContent', '''
if ($ReadBranchSource.statusCode!==200) throw new Error("Cannot read patch branch");
$branchSource=typeof $ReadBranchSource.result==="string"?JSON.parse($ReadBranchSource.result):$ReadBranchSource.result;
const content=Buffer.from($branchSource.content.replace(/\\n/g,""),"base64").toString("utf8");
if(content!==$before && content!==$after) throw new Error("Existing branch contains unexpected changes");
$needsCommit=content===$before;
'''),
            {'action':'if','name':'CommitIfNeeded','condition':'$needsCommit','then':[
                gh('CommitVersionPatch', prefix+' + "/contents/"+$config.policy.file', method='PUT', body='{"message":"fix: upgrade requests to 2.33.0 for three CVEs","branch":$config.policy.branch,"sha":$branchSource.sha,"content":Buffer.from($after,"utf8").toString("base64")}'),
                function('RequireCommit', 'if ($CommitVersionPatch.statusCode!==200 && $CommitVersionPatch.statusCode!==201) throw new Error("Patch commit failed");')
            ],'else':[]},
            gh('CreateRemediationPR', prefix+' + "/pulls"', method='POST', body='{"title":"fix: remediate requests CVEs with 2.33.0","head":$config.policy.branch,"base":"main","body":"Concert Workflows detected requests 2.31.0 in the source inventory. This PR changes only services/langflow-ai-service/requirements.txt to requests 2.33.0.\\n\\nTarget findings: CVE-2024-35195, CVE-2024-47081, CVE-2026-25645.\\n\\nPatch PR verification checks the exact diff, Python dependency resolution, HTTP behavior, service health, source/image vulnerability inventory and CodeQL. Existing unrelated findings remain for triage.\\n\\nReview and merge this PR to run the main build, Concert ingestion, deployment and smoke pipeline. A successful PR or merge alone is not remediation closure; run the Workflows verify operation after that pipeline succeeds."}'),
            function('ReturnCreatedPR', '''
if ($CreateRemediationPR.statusCode!==201) throw new Error("PR creation failed");
const pr=typeof $CreateRemediationPR.result==="string"?JSON.parse($CreateRemediationPR.result):$CreateRemediationPR.result;
$result={...$result,status:"pr_created",pull_request:pr.html_url,number:pr.number};
''')], 'else': []}], 'else': []},
    {'action':'if','name':'07_VerifyAfterMerge','condition':'$operation === "verify"','then':[
        gh('ReadMainRuns',prefix+' + "/actions/workflows/concert-devsecops.yml/runs"',query='{"branch":"main","event":"push","per_page":5}'),
        gh('ReadCurrentMain',prefix+' + "/git/ref/heads/main"'),
        function('VerifyDeploymentEvidence', '''
if ($ReadMainRuns.statusCode!==200 || $ReadCurrentMain.statusCode!==200) throw new Error("Cannot read deployment pipeline evidence");
const runs=(typeof $ReadMainRuns.result==="string"?JSON.parse($ReadMainRuns.result):$ReadMainRuns.result).workflow_runs;
const main=typeof $ReadCurrentMain.result==="string"?JSON.parse($ReadCurrentMain.result):$ReadCurrentMain.result;
const run=runs.find(r=>r.head_sha===main.object.sha);
const inventory=typeof $03_ReadConcertInventory.result==="string"?JSON.parse($03_ReadConcertInventory.result):$03_ReadConcertInventory.result;
const packages=(inventory.packages||[]).filter(p=>p.name===$config.policy.package);
const findings=typeof $02_ReadConcertFindings.result==="string"?JSON.parse($02_ReadConcertFindings.result):$02_ReadConcertFindings.result;
const open=(findings.cve_findings||[]).filter(f=>f.package_name===$config.policy.package && $config.policy.cves.includes(f.cve) && !["Resolved","Fixed","Closed","Not affected","False positive"].includes(f.assessment_status));
const ready=$alreadyFixed && run && run.status==="completed" && run.conclusion==="success" && packages.some(p=>p.version===$config.policy.to_version);
$result={...$result,status:ready?(open.length?"deployment_verified_concert_findings_pending":"verified"):"verification_pending",pipeline:run?run.html_url:null,
 source_version_verified:$alreadyFixed,concert_package_versions:[...new Set(packages.map(p=>p.version))],
 remaining_concert_target_rows:open.length,closure:ready && open.length===0?"verified":"not_closed"};
''')], 'else': []}]
    return {'name':'Langflow Package Patch Demo','platform':'node',
        'meta':{'version':5,'layout':'flow','workerGroup':'default','description':'Plan → constrained package patch PR → PR checks → review/merge → existing deployment pipeline → evidence verification. No automatic merge.'},
        'variables':[variable('operation','"plan"',isInput=True,type={'type':'string','enum':['plan','create-pr','verify']}),
            variable('config',json.dumps(cfg)),variable('result','{}',isOutput=True)]+
            [variable(n) for n in ['source','before','after','evidence','alreadyFixed','existing','main','branchSource','needsCommit']],
        'blocks':blocks}


if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    pathlib.Path(a.output).write_text(json.dumps(build(json.loads(pathlib.Path(a.config).read_text())),indent=2,ensure_ascii=False)+'\n')
