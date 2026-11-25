"""Conservative descriptive validation of V3+ directional hypotheses.

No outcome is evidence of news causality or a profitable trading strategy.
"""
from datetime import datetime, timezone
from collections import Counter
import math

BENCHMARK = {'NVDA':'QQQ','AMD':'QQQ','AAPL':'QQQ','MSFT':'QQQ',
             'TSLA':'SPY','COIN':'SPY','MSTR':'SPY','ETH':'BTC','SOL':'BTC',
             'XRP':'BTC','ADA':'BTC','DOGE':'BTC'}
HORIZONS = (15, 60, 240, 1440)

def benchmark_for(asset):
    return BENCHMARK.get(asset)

def _dt(value):
    try:
        d = datetime.fromisoformat(value.replace('Z','+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (TypeError, ValueError, AttributeError):
        return None

def _number(v):
    return isinstance(v, (float,int)) and not isinstance(v,bool) and math.isfinite(v)

def _direction(e):
    if e.get('catalyst_method') == 'headline_rules_v3_2':
        if e.get('hypothesis_status') != 'candidate':
            return None
        return e.get('hypothesis_direction')
    return e.get('direction')

def eligibility(e):
    if e.get('attribution_method') != 'headline_mentions_v3':
        return 'legacy_not_v3'
    asset = e.get('primary_asset')
    if not asset:
        return 'no_primary_asset'
    if _direction(e) not in ('Potentially bullish','Potentially bearish'):
        return 'no_directional_hypothesis'
    detected = _dt(e.get('detected_at'))
    if not detected:
        return 'invalid_detection_timestamp'
    record = e.get('price_reactions',{}).get(asset,{})
    baseline = record.get('baseline',{})
    if not baseline.get('valid_for_reaction'):
        return 'missing_valid_baseline'
    bt = _dt(baseline.get('observed_at'))
    if not bt or abs((bt-detected).total_seconds()) > 1800:
        return 'baseline_outside_30_minute_window'
    if not _number(baseline.get('price')) or baseline['price'] <= 0:
        return 'invalid_baseline_price'
    if not record.get('followups'):
        return 'awaiting_followup'
    if not _valid_followups(record):
        return 'no_valid_completed_followup'
    return 'eligible'

def _valid_followups(record):
    base = record.get('baseline',{})
    bt = _dt(base.get('observed_at'))
    if not bt: return []
    result=[]
    for horizon, f in record.get('followups',{}).items():
        try: minutes=int(horizon)
        except (ValueError,TypeError): continue
        if minutes not in HORIZONS or not isinstance(f,dict) or not f.get('valid_for_reaction'):
            continue
        ft=_dt(f.get('observed_at'))
        if not ft or (ft-bt).total_seconds() < minutes*60:
            continue
        if not _number(f.get('price')) or f['price'] <= 0:
            continue
        # A quote with a provider timestamp must not predate the baseline quote.
        bq=_dt(base.get('quote_at'))
        fq=_dt(f.get('quote_at'))
        if bq and fq and fq <= bq:
            continue
        result.append((minutes,f,ft))
    return result

def completed_rows(events):
    rows=[]
    for e in events:
        if eligibility(e) != 'eligible': continue
        asset=e['primary_asset']; rec=e['price_reactions'][asset]
        b=rec['baseline']; direction=_direction(e)
        expected=1 if direction=='Potentially bullish' else -1
        for horizon,f,ft in _valid_followups(rec):
            change=100*(f['price']/b['price']-1)
            bm=f.get('benchmark_return_pct')
            if not _number(bm): bm=None
            excess=change-bm if bm is not None else None
            # Preserve baseline identity: events with different starts are not one cluster.
            cluster='|'.join([asset,str(horizon),b.get('quote_at') or b['observed_at'],f.get('quote_at') or f['observed_at']])
            rows.append({'event_id':e.get('id'), 'title':e.get('title',''), 'asset':asset,
                         'horizon_min':horizon,'return_pct':round(change,4),
                         'direction':direction,'direction_match':change*expected>0,
                         'benchmark_return_pct':bm,'excess_return_pct':round(excess,4) if excess is not None else None,
                         'cluster':cluster,'baseline_at':b.get('observed_at'),
                         'followup_at':f.get('observed_at')})
    return rows

def validation_funnel(events):
    counts=Counter(eligibility(e) for e in events)
    return [{'Status':k,'Events':v} for k,v in sorted(counts.items(),key=lambda x:(x[0]!='eligible',-x[1],x[0]))]

def independent_clusters(rows):
    """Count only nonconflicting clusters; never silently count repeated headlines."""
    groups={}
    for row in rows: groups.setdefault(row['cluster'],[]).append(row)
    kept=[]; conflicting=0
    for group in groups.values():
        if len({r['direction'] for r in group}) != 1:
            conflicting+=1;continue
        kept.append(group[0])
    return kept,conflicting
