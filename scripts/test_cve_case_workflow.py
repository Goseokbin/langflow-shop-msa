import copy
import json
from pathlib import Path
import subprocess
import unittest

HERE=Path(__file__).parent
def fixture():
    return {'$operation':'reconcile','$preview_days':8,'$hasCase':True,'$mutate':True,'$issueNumber':4,'$caseKey':'app/cart-service/CVE-2024-53981','$caseMarker':'<!-- concert-case-key:app/cart-service/CVE-2024-53981 -->',
        '$config':{'repository':'demo/shop'},'$service':'cart-service','$cve':'CVE-2024-53981',
        '$case':{'schema':1,'key':'app/cart-service/CVE-2024-53981','service':'cart-service','cve':'CVE-2024-53981','owner':'owner','severity':'high','sla_hours':168,'first_seen_at':'2026-10-28T00:00:00.000Z','due_at':'2026-11-04T00:00:00.000Z','baseline_packages':['python-multipart'],'baseline_images':{'staging':'old-image','production':'old-image'},'baseline_affected_environments':{'staging':True,'production':True},'state':'assigned','sla_state':'on-track'},
        '$environmentEvidence':{role:{'image':'new-image','artifact_id':'new','release':'1.0.1-abcdef123456','packages':[{'name':'python-multipart','version':'0.0.32'}],'findings':[]} for role in ['staging','production']},
        '$Read_release_runs':{'result':{'workflow_runs':[{'head_sha':'abcdef1234567890','status':'completed','conclusion':'success','html_url':'https://github.com/demo/shop/actions/runs/1'}]}},
        '$origin':{'id':'selected-row','assessment_id':'assessment','findings_id':'finding','application_id':'app','application_release_id':'old-release','assessment_status':'Assessment in progress','assessment_custom_details':{}},
        '$timeline':[],'$issue':{'body':'Human notes must survive.','labels':[{'name':'human-label'},{'name':'concert-assigned'}],'state':'open','assignees':[{'login':'owner'}]},'$result':{}}

def evaluate(data):
    harness='''const vm=require('vm'),fs=require('fs');const x=JSON.parse(fs.readFileSync(0,'utf8'));const code=fs.readFileSync(x.path,'utf8');class Clock extends Date{static now(){return Date.parse('2026-10-29T00:00:00Z')}};x.data.Date=Clock;vm.runInNewContext(code,x.data);console.log(JSON.stringify({result:x.data.$result,issue:x.data.$issuePatch,assessment:x.data.$assessmentPatch}));'''
    return json.loads(subprocess.check_output(['node','-e',harness],input=json.dumps({'path':str(HERE/'cve-case-assess.js'),'data':data}),text=True))

class CaseLifecycle(unittest.TestCase):
    def test_only_verified_current_deployments_close_case(self):
        r=evaluate(fixture());self.assertEqual(r['result']['status'],'verified');self.assertEqual(r['issue']['state'],'closed')
        self.assertEqual([a['id'] for a in r['assessment']['assessments']],['selected-row'])

    def test_staging_only_fix_waits_for_production(self):
        d=fixture();d['$environmentEvidence']['production']['findings']=[{'cve':d['$cve']}];d['$environmentEvidence']['production']['image']='old-image'
        r=evaluate(d);self.assertEqual(r['result']['status'],'awaiting-production');self.assertEqual(r['issue']['state'],'open')

    def test_missing_inventory_failed_pipeline_or_unchanged_image_never_close(self):
        for reason in ['inventory','pipeline','replacement']:
            d=fixture()
            if reason=='inventory':d['$environmentEvidence']['production']['packages']=[]
            if reason=='pipeline':d['$Read_release_runs']['result']['workflow_runs'][0]['conclusion']='failure'
            if reason=='replacement':d['$environmentEvidence']['production']['image']='old-image'
            with self.subTest(reason=reason):self.assertEqual(evaluate(d)['issue']['state'],'open')

    def test_preview_is_explicit_and_preserves_original_deadline(self):
        d=fixture();d['$operation']='preview-deadline';d['$mutate']=False
        d['$environmentEvidence']['production']['findings']=[{'cve':d['$cve']}]
        r=evaluate(d);self.assertTrue(r['result']['simulation']);self.assertEqual(r['result']['deadline']['state'],'overdue')
        self.assertEqual(r['result']['deadline']['due_at'],d['$case']['due_at'])

    def test_human_notes_and_labels_survive(self):
        r=evaluate(fixture());self.assertTrue(r['issue']['body'].startswith('Human notes must survive.'));self.assertIn('human-label',r['issue']['labels'])

    def test_new_release_does_not_extend_deadline(self):
        d=fixture();before=d['$case']['due_at'];d['$environmentEvidence']['staging']['release']='newer-release'
        self.assertEqual(evaluate(d)['result']['deadline']['due_at'],before)

    def test_completed_case_does_not_become_overdue_later(self):
        d=fixture();d['$case']['completed_at']='2026-10-29T00:00:00.000Z';d['$operation']='preview-deadline'
        self.assertEqual(evaluate(d)['result']['deadline']['state'],'on-track')

    def test_incomplete_verification_reopens_prematurely_closed_ticket(self):
        d=fixture();d['$issue']['state']='closed';d['$environmentEvidence']['production']['findings']=[{'cve':d['$cve']}]
        self.assertEqual(evaluate(d)['issue']['state'],'open')
