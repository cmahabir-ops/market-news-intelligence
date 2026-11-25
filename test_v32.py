import unittest
from catalysts import classify
from attribution import attribute
from datetime import datetime,timezone,timedelta
T=datetime.now(timezone.utc)
def dt(m):return (T+timedelta(minutes=m)).isoformat()
class Tests(unittest.TestCase):
 def test_new_assets(self):
  for symbol in ('XRP','ADA','DOGE'):
   self.assertEqual(attribute(f'{symbol} update','',[symbol])['primary_asset'],symbol)
 def test_single_catalyst(self):
  x=classify('SEC approves XRP ETF','XRP',dt(-10),dt(0))
  self.assertEqual((x['hypothesis_status'],x['hypothesis_direction']),('candidate','Potentially bullish'))
 def test_price_recap_excluded(self):
  x=classify('XRP stock falls after SEC approves XRP ETF','XRP',dt(-10),dt(0))
  self.assertEqual(x['hypothesis_status'],'commentary_or_price_recap')
 def test_stale(self):
  x=classify('SEC approves XRP ETF','XRP',dt(-180),dt(0))
  self.assertEqual(x['hypothesis_status'],'stale_or_unverified_publication')
 def test_multi(self):
  self.assertIsNone(attribute('Bitcoin and Ethereum rally','',['BTC','ETH'])['primary_asset'])
 def test_neutral(self):
  x=classify('XRP price forecast for 2027','XRP',dt(-10),dt(0))
  self.assertIsNone(x['hypothesis_direction'])
 def test_negative(self):
  x=classify('SEC rejects XRP ETF','XRP',dt(-10),dt(0))
  self.assertEqual(x['hypothesis_direction'],'Potentially bearish')
if __name__=='__main__':unittest.main()
