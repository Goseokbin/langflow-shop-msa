import copy
import unittest
from concert_sast import summarize_sarif

class SastBoundaryTests(unittest.TestCase):
    def doc(self):
        return {'version':'2.1.0','runs':[{'tool':{'driver':{'name':'CodeQL','rules':[{'id':'py/test-rule'}]}},'invocations':[{'executionSuccessful':True}],
          'results':[{'ruleId':'py/test-rule','message':{'text':'test-only fixture'},'locations':[{'physicalLocation':{'artifactLocation':{'uri':'services/test.py'},'region':{'startLine':7}}}]}]}]}
    def test_original_location_and_rule_are_preserved(self):
        data=self.doc();before=copy.deepcopy(data);result=summarize_sarif(data)
        self.assertEqual(result['findings'][0]['locations'],[{'file':'services/test.py','line':7}]);self.assertEqual(data,before)
    def test_failed_analysis_cannot_be_reported_as_zero_findings(self):
        data=self.doc();data['runs'][0]['invocations'][0]['executionSuccessful']=False;data['runs'][0]['results']=[]
        with self.assertRaises(ValueError):summarize_sarif(data)
    def test_unknown_rule_and_machine_local_path_are_rejected(self):
        for mutate in ['rule','path']:
            data=self.doc()
            if mutate=='rule':data['runs'][0]['results'][0]['ruleId']='unknown'
            else:data['runs'][0]['results'][0]['locations'][0]['physicalLocation']['artifactLocation']['uri']='file:///runner/test.py'
            with self.assertRaises(ValueError):summarize_sarif(data)
    def test_successful_zero_finding_analysis_remains_zero(self):
        data=self.doc();data['runs'][0]['results']=[]
        self.assertEqual(summarize_sarif(data)['finding_count'],0)

if __name__=='__main__':unittest.main()
