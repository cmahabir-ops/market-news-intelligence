import unittest
from research_v37 import quote,classify,backtest,stamp
class ResearchTests(unittest.TestCase):
 def test_no_future(self): self.assertIsNone(quote([(101,101,5)],100,True))
 def test_sorted(self): self.assertEqual(quote([(98,98,4),(99,101,5)],100,True),4)
 def test_stale(self): self.assertIsNone(quote([(80,80,4)],100))
 def test_labels(self): self.assertEqual([classify(x) for x in (-1,0,1)],['bearish','neutral','bullish'])
 def test_no_sample(self): self.assertEqual(backtest([]),[])
