import unittest
from datetime import datetime,timezone,timedelta
from impact import update
class Timing(unittest.TestCase):
 def test_windows(self):
  t=datetime.now(timezone.utc)
  for seconds,expected in [(269,None),(270,'observed'),(299,'observed'),(420,'observed'),(600,'missed_window')]:
   with self.subTest(seconds=seconds):
    e={'intelligence_method':'observational_v3_3','primary_asset':'BTC','detected_at':t.isoformat(),'published_at':t.isoformat()}
    def q(at):return {'BTC':{'price':100,'observed_at':at.isoformat(),'session':'continuous','valid_for_reaction':True}}
    update(e,q(t),t); now=t+timedelta(seconds=seconds);update(e,q(now),now)
    self.assertEqual(e['cross_market_impact']['windows'].get('5',{}).get('status'),expected)
if __name__=='__main__':unittest.main()
