"""Conservative lexical review candidates, never verified event equivalence."""
import json,re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
STOP=set('the a an to of in on for and as by with from is at after says news'.split())
def tokens(s): return set(re.findall(r'[a-z]+|\d+(?:\.\d+)?',s.lower()))-STOP

def candidates(root, limit=2000):
    rows=[]
    for p in (Path(root)/'arrivals').glob('*/*.json'):
        try:
            r=json.loads(p.read_text(encoding='utf-8')); t=datetime.fromisoformat(r['published_at']); d=datetime.fromisoformat(r['detected_at']);
            if t.tzinfo is None or d.tzinfo is None: continue
            rows.append((t.timestamp(),d.timestamp(),r,tokens(r['title'])))
        except (OSError,ValueError,KeyError,TypeError): continue
    rows=sorted(rows,key=lambda x:x[1])[-limit:]; rows.sort(key=lambda x:x[0]); out=[]
    for i,(t,d,r,a) in enumerate(rows):
        for j in range(i-1,-1,-1):
            u,e,s,b=rows[j]
            if t-u>3600: break
            if r['source']==s['source'] or len(a&b)<5: continue
            if {x for x in a if x[0].isdigit()}!={x for x in b if x[0].isdigit()}: continue
            score=len(a&b)/len(a|b)
            if score>=.65: out.append(dict(source_a=s['source'],title_a=s['title'],source_b=r['source'],title_b=r['title'],similarity=round(score,3),arrival_gap_minutes=round((d-e)/60,2),status='unverified candidate'))
    return sorted(out,key=lambda x:x['similarity'],reverse=True)[:200]
