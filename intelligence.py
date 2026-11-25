"""V3.3 observational macro/source/duplicate diagnostics; never create trade signals."""
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher

MACRO = {
 'central_bank_rate_decision': (r'\b(?:fed|federal reserve|fomc|central bank)\b', r'\b(?:rate (?:decision|cut|hike)|raises? rates|cuts? rates|interest rates?)\b'),
 'inflation_release': (r'\b(?:cpi|pce|consumer price index|personal consumption expenditures)\b', r'\b(?:inflation|data|report|index|release|rose|fell|rises|falls)\b'),
 'employment_release': (r'\b(?:nonfarm payrolls|jobs report|unemployment rate|employment report)\b', r'\b(?:report|data|rises|falls|rose|fell|jobs|rate)\b'),
}
OFFICIAL_DOMAINS = {'federalreserve.gov', 'sec.gov', 'bls.gov', 'bea.gov'}

def macro_context(title):
    hits=[kind for kind,(a,b) in MACRO.items() if re.search(a,title,re.I) and re.search(b,title,re.I)]
    return {'macro_event_type':hits[0] if len(hits)==1 else None,
            'macro_status':'candidate_context' if len(hits)==1 else ('ambiguous' if hits else 'not_detected'),
            'macro_benchmarks':['SPY','QQQ','BTC'] if len(hits)==1 else [],
            'macro_direction':None, 'macro_validation_eligible':False}

def source_quality(source,url):
    from urllib.parse import urlparse
    domain=(urlparse(url).hostname or '').lower().removeprefix('www.')
    # Google News RSS URLs are aggregators, not original publisher links.
    if domain=='news.google.com' or source.lower().startswith('google news'):
        return {'source_tier':'aggregated_unverified','source_domain':domain}
    if domain in OFFICIAL_DOMAINS and not source.lower().startswith('google news'):
        return {'source_tier':'official_domain','source_domain':domain}
    return {'source_tier':'other_unverified','source_domain':domain}

def fingerprint(title):
    # Drop publisher suffix and punctuation; preserve financial terms and figures.
    title=re.sub(r'\s+[-|]\s+[^-|]{2,65}$','',title).lower()
    return ' '.join(re.findall(r'[a-z0-9]+',title))

def duplicate_of(event, prior, window_hours=24, threshold=.92):
    title=fingerprint(event.get('title',''))
    if len(title)<24: return None
    try: t=datetime.fromisoformat(event['published_at'].replace('Z','+00:00'))
    except (KeyError,ValueError,AttributeError): return None
    for old in prior:
        try: other=datetime.fromisoformat(old['published_at'].replace('Z','+00:00'))
        except (KeyError,ValueError,AttributeError): continue
        if abs((t-other).total_seconds())>window_hours*3600: continue
        oldtitle=fingerprint(old.get('title',''))
        if len(oldtitle)>=24 and SequenceMatcher(None,title,oldtitle).ratio()>=threshold:
            return old.get('id')
    return None

def enrich(event, prior):
    result={**source_quality(event.get('source',''),event.get('url','')),
            **macro_context(event.get('title','')),
            'intelligence_method':'observational_v3_3'}
    match=duplicate_of(event,prior)
    result['possible_duplicate_of']=match
    result['duplicate_status']='possible_duplicate' if match else 'no_near_duplicate_found'
    return result
