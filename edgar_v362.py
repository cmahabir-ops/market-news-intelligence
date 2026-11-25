"""SEC submissions metadata only; no directional interpretation of filing types."""
from datetime import datetime, timezone, timedelta
import requests
COMPANIES={'NVDA':1045810,'AMD':2488,'AAPL':320193,'MSFT':789019,'TSLA':1318605,'COIN':1679788,'MSTR':1050446}
FORMS={'8-K','8-K/A','10-Q','10-K','S-3','424B2','424B3','424B5'}
def entries(payload,symbol,cik,now):
    recent=payload['filings']['recent']
    for i,form in enumerate(recent['form']):
        if form not in FORMS: continue
        stamp=recent['acceptanceDateTime'][i]
        dt=datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if dt.tzinfo is None or not now-timedelta(hours=48)<=dt<=now: continue
        acc=recent['accessionNumber'][i]
        doc=recent['primaryDocument'][i]
        yield dict(symbol=symbol,form=form,accession=acc,published_at=dt.isoformat(),title=f'{symbol} SEC filing {form} {acc}',url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace("-", "")}/{doc}')
def collect(contact,watchlist,health=None):
    if not contact or '@' not in contact:
        if health is not None: health.append(dict(status='skipped',reason='missing contact'))
        print('EDGAR skipped: configure CONTACT_EMAIL'); return
    for symbol,cik in COMPANIES.items():
        if symbol not in watchlist: continue
        try:
            r=requests.get(f'https://data.sec.gov/submissions/CIK{cik:010d}.json',headers={'User-Agent':f'MarketNewsIntelligence research {contact}'},timeout=8)
            r.raise_for_status()
            rows=list(entries(r.json(),symbol,cik,datetime.now(timezone.utc)))
            print(f'EDGAR {symbol}: {len(rows)} recent selected filings')
            if health is not None: health.append(dict(symbol=symbol,status="ok",filings=len(rows)))
            yield from rows
        except Exception as exc:
            if health is not None: health.append(dict(symbol=symbol,status="error",error_type=type(exc).__name__))
            print(f'EDGAR ERROR {symbol}: {type(exc).__name__}')
