import unittest
from datetime import datetime, timezone, timedelta
from attribution import attribute
from diagnostics import reason
from validation import completed_rows
NOW=datetime.now(timezone.utc)
def stamp(offset=0):return (NOW+timedelta(minutes=offset)).isoformat()
class Tests(unittest.TestCase):
 def test_primary(self):self.assertEqual(attribute('Nvidia shares rise','', ['NVDA'])['primary_asset'],'NVDA')
 def test_multi(self):self.assertIsNone(attribute('Nvidia and Tesla','', ['NVDA','TSLA'])['primary_asset'])
 def test_neutral(self):self.assertEqual(reason({'attribution_method':'headline_mentions_v3','primary_asset':'NVDA','direction':'Unclear / mixed'}),'No directional hypothesis')
 def test_delayed(self):
  e={'attribution_method':'headline_mentions_v3','primary_asset':'NVDA','direction':'Potentially bullish','detected_at':stamp(-60),'price_reactions':{'NVDA':{'baseline':{'valid_for_reaction':True,'observed_at':stamp()},'followups':{'15':{'valid_for_reaction':True,'change_pct':1,'observed_at':stamp(15)}}}}}
  self.assertEqual(completed_rows([e]),[])
  self.assertIn('30 minutes',reason(e))
 def test_valid(self):
  e={'id':'x','title':'Nvidia upgrade','attribution_method':'headline_mentions_v3','primary_asset':'NVDA','direction':'Potentially bullish','detected_at':stamp(-1),'price_reactions':{'NVDA':{'baseline':{'valid_for_reaction':True,'observed_at':stamp()},'followups':{'15':{'valid_for_reaction':True,'change_pct':1,'observed_at':stamp(15)}}}}}
  self.assertEqual(len(completed_rows([e])),1)
if __name__=='__main__':unittest.main()
