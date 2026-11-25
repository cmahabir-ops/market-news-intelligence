"""Indicative public price snapshots; no fabricated or backfilled prices."""
import requests
from datetime import datetime, timezone
CRYPTO={'BTC','ETH','SOL'}
def quote(asset):
    try:
        if asset in CRYPTO:
            r=requests.get(f'https://api.coinbase.com/v2/prices/{asset}-USD/spot',timeout=12);r.raise_for_status()
            value=float(r.json()['data']['amount']); source='Coinbase public spot indicative USD'
        else:
            r=requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{asset}',params={'interval':'1m','range':'1d'},headers={'User-Agent':'Mozilla/5.0'},timeout=12);r.raise_for_status()
            result=r.json()['chart']['result'][0]; value=result['meta'].get('regularMarketPrice'); source='Yahoo Finance chart indicative USD'
            if value is None: return None
            value=float(value)
        if value<=0: return None
        return {'price':value,'observed_at':datetime.now(timezone.utc).isoformat(),'source':source,'currency':'USD'}
    except (ValueError,KeyError,IndexError,TypeError,requests.RequestException) as exc:
        print(f'PRICE UNAVAILABLE {asset}: {type(exc).__name__}: {exc}');return None
