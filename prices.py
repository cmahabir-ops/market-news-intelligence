"""Observed indicative quotes with provider timestamps and US regular-session checks."""
import requests
from datetime import datetime,timezone,timedelta,time
from zoneinfo import ZoneInfo
CRYPTO={'BTC','ETH','SOL'}
STOCKS={'NVDA','AMD','AAPL','MSFT','TSLA','COIN','MSTR','SPY','QQQ'}
def quote(asset):
    try:
        now=datetime.now(timezone.utc)
        if asset in CRYPTO:
            r=requests.get(f'https://api.coinbase.com/v2/prices/{asset}-USD/spot',timeout=12);r.raise_for_status()
            value=float(r.json()['data']['amount'])
            # Coinbase spot endpoint lacks an exchange quote timestamp.
            result={'price':value,'observed_at':now.isoformat(),'quote_at':None,'source':'Coinbase public spot indicative USD','currency':'USD','session':'continuous','valid_for_reaction':True,'freshness':'provider_timestamp_unavailable'}
        elif asset in STOCKS:
            r=requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{asset}',params={'interval':'1m','range':'1d'},headers={'User-Agent':'Mozilla/5.0'},timeout=12);r.raise_for_status()
            meta=r.json()['chart']['result'][0]['meta']
            value=float(meta['regularMarketPrice'])
            ts=meta.get('regularMarketTime')
            quote_at=datetime.fromtimestamp(int(ts),timezone.utc) if ts else None
            local=now.astimezone(ZoneInfo('America/New_York'))
            in_regular=local.weekday()<5 and time(9,30)<=local.time()<time(16,0)
            age=(now-quote_at).total_seconds() if quote_at else None
            # Conservative: market-session calendar (holidays/half-days) not available; timestamp required.
            valid=bool(in_regular and age is not None and -60<=age<=900)
            result={'price':value,'observed_at':now.isoformat(),'quote_at':quote_at.isoformat() if quote_at else None,
                    'source':'Yahoo Finance chart indicative USD','currency':'USD',
                    'session':'regular_candidate' if in_regular else 'outside_regular_hours',
                    'valid_for_reaction':valid,'freshness':'recent' if valid else 'stale_or_unverified'}
        else: return None
        if value<=0:return None
        return result
    except (ValueError,KeyError,IndexError,TypeError,requests.RequestException) as exc:
        print(f'PRICE UNAVAILABLE {asset}: {type(exc).__name__}: {exc}');return None
