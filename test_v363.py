import unittest,tempfile
from pathlib import Path
from health_v363 import archive_summary,save
from archive_v362 import sighting,snapshot
class HealthTests(unittest.TestCase):
    def test_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(archive_summary(d)[0]['unique_events'],0)
    def test_match(self):
        with tempfile.TemporaryDirectory() as d:
            snapshot(d,[{'id':'a'},{'id':'a','x':1}])
            sighting(d,'A','url','title','2026-01-01T00:00:00+00:00','2026-01-01T00:01:00+00:00','a')
            sighting(d,'B','url','title','2026-01-01T00:00:00+00:00','2026-01-01T00:03:00+00:00','a')
            c,r=archive_summary(d); self.assertEqual(c['unique_events'],1); self.assertEqual(c['snapshots'],2); self.assertEqual(c['matched_groups'],1); self.assertEqual(max(x['minutes_after_first'] for x in r),2)
    def test_save(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'health.json'; save(p,{'ok':True}); self.assertTrue(p.exists())
