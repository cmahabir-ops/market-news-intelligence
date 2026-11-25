import unittest
from intelligence import macro_context,source_quality,duplicate_of,enrich
class V33Tests(unittest.TestCase):
 def test_macro_is_context_not_signal(self):
  d=macro_context('Federal Reserve announces interest rate decision')
  self.assertEqual(d['macro_event_type'],'central_bank_rate_decision')
  self.assertIsNone(d['macro_direction'])
  self.assertFalse(d['macro_validation_eligible'])
 def test_no_generic_macro(self):
  self.assertEqual(macro_context('Bitcoin price forecast for next week')['macro_status'],'not_detected')
 def test_aggregator_not_official(self):
  self.assertEqual(source_quality('Google News - Markets','https://news.google.com/rss/articles/x')['source_tier'],'aggregated_unverified')
 def test_official_domain(self):
  self.assertEqual(source_quality('Federal Reserve Press Releases','https://www.federalreserve.gov/newsevents/pressreleases/a.htm')['source_tier'],'official_domain')
 def test_duplicate(self):
  old={'id':'abc','title':'Federal Reserve announces rate decision after meeting - Example','published_at':'2026-11-25T01:00:00+00:00'}
  new={'title':'Federal Reserve announces rate decision after meeting - Other','published_at':'2026-11-25T02:00:00+00:00'}
  self.assertEqual(duplicate_of(new,[old]),'abc')
 def test_distant_not_duplicate(self):
  old={'id':'abc','title':'Federal Reserve announces rate decision after meeting','published_at':'2026-11-20T01:00:00+00:00'}
  new={'title':old['title'],'published_at':'2026-11-25T02:00:00+00:00'}
  self.assertIsNone(duplicate_of(new,[old]))
 def test_enrichment_does_not_change_prediction(self):
  e={'id':'new','title':'Federal Reserve announces rate decision','published_at':'2026-11-25T02:00:00+00:00','source':'Google News - Markets','url':'https://news.google.com/rss/articles/x'}
  d=enrich(e,[])
  self.assertNotIn('direction',d)
  self.assertNotIn('alert_status',d)
if __name__=='__main__':unittest.main()
