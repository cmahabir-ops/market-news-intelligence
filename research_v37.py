"""Local research audit; no live forecasts. Standard library only."""
import argparse, json, sqlite3, math, csv
from pathlib import Path
from datetime import datetime
from collections import Counter
from bisect import bisect_right

def stamp(s):
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('naive timestamp')
    return d.timestamp()

def load_events(root):
    events={}
    for p in sorted((root/'research_archive'/'events').rglob('*.json')):
        e=json.loads(p.read_text(encoding='utf-8')); events.setdefault(e['id'],e)
    for e in json.loads((root/'events.json').read_text(encoding='utf-8')): events[e['id']]=e
    return sorted(events.values(),key=lambda e:e['detected_at'])

def quote(rows,t,known=False):
    i=bisect_right(rows,(t,float('inf'),float('inf')))-1
    while i>=0:
        ts,received,p=rows[i]
        if t-ts>10: return None
        if (not known or received<=t) and p>0: return p
        i-=1
    return None

def classify(r,threshold=.1):
    return 'bullish' if r>threshold else 'bearish' if r< -threshold else 'neutral'

def audit(events,db):
    counts=Counter(); results=[]; last={}
    with sqlite3.connect(db) as c:
        for e in events:
            q=e.get('quality_v352') or {}; a=e.get('primary_asset'); cat=e.get('catalyst_type')
            if not q.get('review_candidate') or not q.get('fresh') or q.get('tier') not in ('A','B') or not cat or e.get('possible_duplicate_of'):
                counts['quality_excluded']+=1; continue
            if a not in ('BTC','ETH','SOL','XRP','ADA','DOGE'): counts['unsupported_asset']+=1; continue
            t=stamp(e['detected_at']); rows=c.execute('SELECT ts,received,price FROM ticks WHERE product=? AND ts BETWEEN ? AND ? ORDER BY ts,received,price',(a+'-USD',t-310,t+86400)).fetchall()
            p=quote(rows,t,True); pre=quote(rows,t-300,True)
            if p is None or pre is None: counts['missing_baseline_or_context']+=1; continue
            for h in (5,15,60,240,1440):
                end=t+h*60; after=quote(rows,end)
                if after is None: counts['missing_outcome_window']+=1; continue
                # Require continuous observed trade coverage, conservatively reject sparse intervals.
                times=[t]+[r[0] for r in rows if t<r[0]<=end]+[end]
                if max(y-x for x,y in zip(times,times[1:]))>60: counts['coverage_gap']+=1; continue
                key=(a,h)
                if t<last.get(key,-math.inf): counts['overlapping_window']+=1; continue
                last[key]=end; ret=100*(after/p-1)
                results.append(dict(event_id=e['id'],asset=a,catalyst=cat,detected_at=e['detected_at'],t=t,end=end,horizon=h,momentum=100*(p/pre-1),return_pct=ret,outcome=classify(ret)))
    return results,dict(counts)

def backtest(rows):
    predictions=[]
    for r in rows:
        past=[p for p in rows if p['end']<r['t'] and p['asset']==r['asset'] and p['horizon']==r['horizon']]
        similar=[p for p in past if p['catalyst']==r['catalyst'] and (p['momentum']>=0)==(r['momentum']>=0)]
        if len(similar)<30: continue
        labels=('bullish','neutral','bearish'); n=len(similar); counts=Counter(p['outcome'] for p in similar); base=Counter(p['outcome'] for p in past)
        probs={k:(counts[k]+1)/(n+3) for k in labels}; baseline={k:(base[k]+1)/(len(past)+3) for k in labels}
        score=lambda v:sum((v[k]-(k==r['outcome']))**2 for k in labels)
        predictions.append(dict(event_id=r['event_id'],horizon=r['horizon'],n=n,probabilities=probs,brier=score(probs),baseline_brier=score(baseline)))
    return predictions

def main():
    p=argparse.ArgumentParser(); p.add_argument('--db',default='local_market/ticks.sqlite'); p.add_argument('--data',default='data'); p.add_argument('--output',default='local_market/research_v37.json'); args=p.parse_args()
    if not Path(args.db).is_file(): p.error('market database not found')
    events=load_events(Path(args.data)); rows,excluded=audit(events,args.db); tests=backtest(rows)
    report=dict(events=len(events),eligible_windows=len(rows),exclusions=excluded,backtest_predictions=len(tests),forecast_status='withheld_research_only',rows=rows,backtests=tests)
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps({k:v for k,v in report.items() if k not in ('rows','backtests')},indent=2))
if __name__=='__main__': main()
