import unittest, tempfile, json
from pathlib import Path
from market_v364 import connect, ingest, metrics
from matching_v364 import candidates
class Tests(unittest.TestCase):
 def test_ticks(self):
  with tempfile.TemporaryDirectory() as d:
   db=connect(Path(d)/'ticks.db'); m=dict(type='ticker',product_id='BTC-USD',trade_id=1,time='2026-01-01T00:00:00Z',price='100',last_size='2'); t=1767225600
   self.assertTrue(ingest(db,m,t)); self.assertFalse(ingest(db,m,t)); self.assertFalse(ingest(db,dict(m,price='nan',trade_id=2),t)); self.assertEqual(metrics(db,t)[0]['ticks'],1); db.close()
 def test_candidates(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'arrivals'/'aa'; p.mkdir(parents=True)
   r=dict(title='Nvidia announces new chip export restrictions today',published_at='2026-01-01T00:00:00+00:00',detected_at='2026-01-01T00:01:00+00:00',source='A')
   for i,x in enumerate([r,dict(r,source='B'),dict(r,source='C',title=r['title']+' 25')]): (p/f'{i}.json').write_text(json.dumps(x))
   self.assertEqual(len(candidates(d)),1)
if __name__=='__main__': unittest.main()
