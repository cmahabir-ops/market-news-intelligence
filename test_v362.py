import unittest,tempfile
from pathlib import Path
from archive_v362 import snapshot,sighting
from edgar_v362 import entries
from datetime import datetime,timezone
class Tests(unittest.TestCase):
    def test_archive(self):
        with tempfile.TemporaryDirectory() as d:
            snapshot(d,[{'id':'a','x':1}]);snapshot(d,[{'id':'a','x':1}]);snapshot(d,[{'id':'a','x':2}]);self.assertEqual(len(list(Path(d).rglob('*.json'))),2)
    def test_arrivals(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(sighting(d,'a','u','t','p','d','k'));self.assertFalse(sighting(d,'a','u','t','p','later','k'));self.assertTrue(sighting(d,'b','u','t','p','d','k'))
    def test_edgar(self):
        p={'filings':{'recent':{'form':['8-K','4'],'acceptanceDateTime':['2026-11-25T12:00:00Z']*2,'accessionNumber':['1-2','3-4'],'primaryDocument':['a.htm','b.htm']}}}
        self.assertEqual(len(list(entries(p,'NVDA',1045810,datetime(2026,11,25,13,tzinfo=timezone.utc)))),1)
if __name__=='__main__': unittest.main()
