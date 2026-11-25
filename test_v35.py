import unittest
from datetime import datetime, timezone, timedelta
from impact import basket, update, rows, positive_quote
T = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)

def q(price, time):
    return {'price': price, 'observed_at': time.isoformat(), 'quote_at': None,
            'valid_for_reaction': True, 'session': 'continuous'}

def e(primary='BTC'):
    return {'id': 'x', 'title': 'Example', 'published_at': (T-timedelta(minutes=1)).isoformat(),
            'detected_at': T.isoformat(), 'primary_asset': primary,
            'intelligence_method': 'observational_v3_3'}

class ImpactTests(unittest.TestCase):
    def test_legacy_ignored(self):
        event=e();event.pop('intelligence_method');self.assertEqual(basket(event), ())
    def test_baseline_and_five_min(self):
        event=e(); update(event, {'BTC':q(100,T),'ETH':q(50,T),'SOL':q(20,T)},T)
        self.assertEqual(event['cross_market_impact']['status'],'tracking')
        t=T+timedelta(minutes=5)
        update(event,{'BTC':q(102,t),'ETH':q(51,t),'SOL':q(20,t)},t)
        window=event['cross_market_impact']['windows']['5']
        self.assertEqual(window['status'],'observed')
        self.assertEqual(window['returns_pct']['BTC'],2.0)
        self.assertEqual(len(rows([event])),1)
    def test_late_scan_is_not_five_min(self):
        event=e();update(event,{'BTC':q(100,T)},T)
        t=T+timedelta(minutes=12)
        update(event,{'BTC':q(110,t)},t)
        self.assertEqual(event['cross_market_impact']['windows']['5']['status'],'missed_window')
    def test_late_initial_baseline_rejected(self):
        event=e();t=T+timedelta(minutes=5)
        update(event,{'BTC':q(100,t)},t)
        self.assertEqual(event['cross_market_impact']['status'],'baseline_missed')
    def test_invalid_stock_quote(self):
        t=T
        self.assertFalse(positive_quote({'price':100,'observed_at':t.isoformat(),
            'quote_at':(t-timedelta(minutes=10)).isoformat(),
            'valid_for_reaction':True,'session':'regular_candidate'}))
    def test_macro_basket(self):
        event=e(None);event['macro_status']='candidate_context'
        self.assertIn('SPY',basket(event))
    def test_no_backfill(self):
        event=e();update(event,{'BTC':q(100,T)},T)
        t=T+timedelta(minutes=12)
        update(event,{'BTC':q(110,t)},t)
        update(event,{'BTC':q(111,t)},t)
        self.assertEqual(event['cross_market_impact']['windows']['5']['status'],'missed_window')
if __name__=='__main__': unittest.main()
