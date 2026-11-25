"""Descriptive event outcomes only; no claim of predictive or causal validity."""
from datetime import datetime,timezone
BENCHMARK={'NVDA':'QQQ','AMD':'QQQ','AAPL':'QQQ','MSFT':'QQQ','TSLA':'SPY','COIN':'SPY','MSTR':'SPY','ETH':'BTC','SOL':'BTC','XRP':'BTC','ADA':'BTC','DOGE':'BTC'}
def benchmark_for(asset): return BENCHMARK.get(asset)
def completed_rows(events):
    rows=[]
    for e in events:
        if e.get('attribution_method')!='headline_mentions_v3':continue
        asset=e.get('primary_asset')
        if not asset or e.get('direction') not in ('Potentially bullish','Potentially bearish'):continue
        if e.get('catalyst_method') == 'headline_rules_v3_2' and e.get('hypothesis_status') != 'candidate':continue
        # Avoid treating a delayed next-session baseline as a response to old news.
        try:
            detected=datetime.fromisoformat(e['detected_at'])
        except (KeyError,ValueError,TypeError):
            continue
        rec=e.get('price_reactions',{}).get(asset,{})
        for horizon,f in rec.get('followups',{}).items():
            if not f.get('valid_for_reaction'):continue
            b=rec.get('baseline',{})
            if not b.get('valid_for_reaction'):continue
            try:
                baseline_time=datetime.fromisoformat(b['observed_at'])
                if abs((baseline_time-detected).total_seconds())>30*60:continue
            except (KeyError,ValueError,TypeError):continue
            change=f.get('change_pct')
            if not isinstance(change,(int,float)):continue
            expected=1 if e['direction']=='Potentially bullish' else -1
            rows.append({'event_id':e['id'],'title':e['title'],'asset':asset,'horizon_min':int(horizon),
                         'return_pct':change,'direction':e['direction'],'direction_match':(change*expected>0),
                         'benchmark_return_pct':f.get('benchmark_return_pct'),
                         'excess_return_pct':f.get('excess_return_pct'),
                         'cluster':f'{asset}:{horizon}:{f.get("quote_at") or f.get("observed_at", "")[:16]}',
                         'baseline_at':b.get('observed_at'),'followup_at':f.get('observed_at')})
    return rows
