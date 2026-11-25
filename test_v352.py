import unittest
from quality import assess, rows
class QualityTests(unittest.TestCase):
    def event(self,title,**kw):
        return dict({'title':title,'primary_asset':'BTC','published_at':'2026-11-25T12:00:00+00:00','detected_at':'2026-11-25T12:05:00+00:00','source_tier':'official_domain'},**kw)
    def test_direct(self): self.assertEqual(assess(self.event('SEC approves Bitcoin ETF'))['tier'],'A')
    def test_indirect(self): self.assertEqual(assess(self.event('Bitcoin affected by tariffs'))['tier'],'B')
    def test_commentary(self): self.assertEqual(assess(self.event('Bitcoin price prediction'))['tier'],'C')
    def test_noise(self): self.assertEqual(assess(self.event('Bitcoin sportsbook payouts'))['tier'],'D')
    def test_late(self): self.assertFalse(assess(self.event('SEC approves Bitcoin ETF',detected_at='2026-11-25T13:00:00+00:00'))['review_candidate'])
    def test_duplicate(self): self.assertFalse(assess(self.event('SEC approves Bitcoin ETF',possible_duplicate_of='old'))['review_candidate'])
    def test_unverified(self): self.assertFalse(assess(self.event('SEC approves Bitcoin ETF',source_tier='aggregated_unverified'))['review_candidate'])
    def test_no_forecast(self): self.assertFalse(assess(self.event('SEC approves Bitcoin ETF'))['forecast_ready'])
    def test_rows(self):
        e=self.event('SEC approves Bitcoin ETF'); e['quality_v352']=assess(e)
        self.assertEqual(len(rows([{},e])),1)
    def test_empty(self): self.assertEqual(rows([{}]),[])
