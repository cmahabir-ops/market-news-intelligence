import unittest
from datetime import datetime, timezone, timedelta
from validation import completed_rows, eligibility, independent_clusters

NOW=datetime(2026,11,25,12,tzinfo=timezone.utc)
def event():
    t=lambda mins:(NOW+timedelta(minutes=mins)).isoformat()
    return {'id':'test','title':'Test event','attribution_method':'headline_mentions_v3','primary_asset':'BTC',
        'direction':'Potentially bullish','detected_at':t(0),'price_reactions':{'BTC':{'baseline':{'price':100,'observed_at':t(0),'valid_for_reaction':True},
        'followups':{'15':{'price':102,'observed_at':t(16),'valid_for_reaction':True}}}}}
class Tests(unittest.TestCase):
    def test_eligible(self):
        self.assertEqual(eligibility(event()),'eligible')
        self.assertEqual(len(completed_rows([event()])),1)
    def test_invalid_baseline(self):
        e=event();e['price_reactions']['BTC']['baseline']['valid_for_reaction']=False
        self.assertEqual(eligibility(e),'missing_valid_baseline')
    def test_premature_followup(self):
        e=event();e['price_reactions']['BTC']['followups']['15']['observed_at']=(NOW+timedelta(minutes=5)).isoformat()
        self.assertEqual(eligibility(e),'no_valid_completed_followup')
    def test_no_hypothesis(self):
        e=event();e['direction']='Unclear / mixed'
        self.assertEqual(eligibility(e),'no_directional_hypothesis')
    def test_repeated_clusters(self):
        r=completed_rows([event(),event()]); kept,conflicts=independent_clusters(r)
        self.assertEqual((len(kept),conflicts),(1,0))
    def test_conflicting_clusters(self):
        e=event(); f=event(); f['direction']='Potentially bearish'
        kept,conflicts=independent_clusters(completed_rows([e,f]))
        self.assertEqual((len(kept),conflicts),(0,1))
if __name__=='__main__': unittest.main()
