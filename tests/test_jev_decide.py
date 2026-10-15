import unittest,importlib.util,json,unittest.mock as mock,contextlib,io
from pathlib import Path
spec=importlib.util.spec_from_file_location('jev', str(Path(__file__).resolve().parents[1] / 'hebe-security-scan/scripts/jev_decide.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Contract(unittest.TestCase):
 def setUp(self):
  self.data={'state':{'goal':'scoped review','scope':'route'},'questions':[{'id':'next','type':'choice','question':'Which evidence next?','options':['guard','icon','unknown']}]};self.req=m.prepare(self.data)
 def response(self,p=None):
  return {'model':'fixture-jev','answers':{'next':{'choice':'guard','probabilities':p or {'guard':.9,'icon':.05,'unknown':.05}}}}
 def test_missing_or_extra_answers_rejected(self):
  for answers in [{},{'next':{},'invented':{}}]:
   with self.assertRaises(ValueError):m.validate_reply({'model':'fixture','answers':answers},self.req)
 def test_nonprobabilities_rejected(self):
  for v in [float('nan'),float('inf'),True,-.2,1.2,10**1000]:
   with self.assertRaises(ValueError):m.validate_reply(self.response({'guard':v,'icon':.05,'unknown':.05}),self.req)
 def test_unknown_or_split_remains_uncertain(self):
  for probs in [{'guard':.45,'icon':.4,'unknown':.15},{'guard':.79,'icon':.2,'unknown':.01}]:self.assertTrue(m.validate_reply(self.response(probs),self.req)['answers']['next']['uncertain'])
 def test_answer_has_no_action_authority(self):
  d=m.validate_reply(self.response(),self.req);self.assertEqual(d['authority'],'advisory_only');self.assertEqual(d['executed_actions'],[])
 def test_bad_distribution_rejected_atomically(self):
  for probs in [{'guard':.95,'icon':.4,'unknown':.15},{'guard':.9,'icon':.1},{'guard':.9,'icon':.04,'unknown':.05,'invented':.01}]:
   with self.assertRaises(ValueError):m.validate_reply(self.response(probs),self.req)
 def test_input_limits_and_duplicate_ids(self):
  self.data['state']['goal']='x'*12001
  with self.assertRaises(ValueError):m.prepare(self.data)
  self.data['state']['goal']='review';self.data['questions']*=2
  with self.assertRaises(ValueError):m.prepare(self.data)
 def test_missing_credential_does_not_call_network(self):
  inp=mock.Mock();inp.buffer=io.BytesIO(json.dumps(self.data).encode());out=io.StringIO()
  with mock.patch.object(m.sys,'stdin',inp),mock.patch.object(m,'credential',return_value=''),mock.patch.object(m.urllib.request,'build_opener') as net,contextlib.redirect_stdout(out):
   self.assertEqual(m.main(),1);net.assert_not_called()
  self.assertEqual(json.loads(out.getvalue())['status'],'unavailable')
 def test_redirect_refuses_forwarding_credential(self):
  self.assertIsNone(m.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://other.invalid'))
if __name__=='__main__':unittest.main()
