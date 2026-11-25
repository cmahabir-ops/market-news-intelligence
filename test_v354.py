import unittest
from latency import delay, summarize, publisher

def event(minutes=5, **kw):
    return dict(source='Google News - Crypto', title='Headline - Example', published_at='2026-01-01T00:00:00Z', detected_at=f'2026-01-01T00:{minutes:02}:00Z', **kw)
class AuditTests(unittest.TestCase):
    def test_delay(self): self.assertEqual(delay(event()),5)
    def test_invalid(self):
        for x in ({}, {'published_at':'2026-01-01T00:00:00','detected_at':'2026-01-01T00:05:00Z'}, {'published_at':'2026-01-01T01:00:00Z','detected_at':'2026-01-01T00:05:00Z'}): self.assertIsNone(delay(x))
    def test_stats(self):
        r=summarize([event(5),event(10),event(30),{'source':'Google News - Crypto'}])[0]
        self.assertEqual((r['Median delay (min)'],r['P90 delay (min)'],r['Fresh ≤10 min %'],r['Invalid timestamp %']),(10,30,66.67,25))
    def test_denominators(self):
        r=summarize([event(),event(quality_v352={'method':'headline_quality_v3_5_2','tier':'B','review_candidate':False},duplicate_status='possible_duplicate')])[0]
        self.assertEqual((r['A/B yield %'],r['Possible duplicate %'],r['Priority yield %']),(100,100,0))
        self.assertIsNone(summarize([event()])[0]['A/B yield %'])
    def test_publisher(self): self.assertEqual(publisher(event()),'Example')
    def test_empty(self): self.assertEqual(summarize([]),[])
