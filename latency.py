"""Read-only feed latency audit. Counts stored records, not all feed deliveries."""
from datetime import datetime
from statistics import median
from collections import defaultdict
import math

def delay(event):
    try:
        p,d=(datetime.fromisoformat(event[k].replace('Z','+00:00')) for k in ('published_at','detected_at'))
        if p.utcoffset() is None or d.utcoffset() is None: return None
        v=(d-p).total_seconds()/60
        return v if v>=0 and math.isfinite(v) else None
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError): return None

def publisher(event):
    if str(event.get('source','')).startswith('Google News'):
        title=str(event.get('title',''))
        return title.rsplit(' - ',1)[1].strip() if ' - ' in title and title.rsplit(' - ',1)[1].strip() else 'Unknown'
    return 'Not independently identified'

def summarize(events, by_publisher=False):
    groups=defaultdict(list)
    for e in events:
        key=(str(e.get('source') or 'Unknown'), publisher(e) if by_publisher else '')
        groups[key].append(e)
    result=[]
    for (feed,pub),items in sorted(groups.items()):
        ds=sorted(v for e in items if (v:=delay(e)) is not None)
        n=len(items); valid=len(ds)
        quality=[q for e in items if isinstance(q:=e.get('quality_v352'),dict) and q.get('method')=='headline_quality_v3_5_2' and q.get('tier') in ('A','B','C','D')]
        dup=[e for e in items if e.get('duplicate_status') in ('possible_duplicate','no_near_duplicate_found')]
        def pct(a,b): return round(100*a/b,2) if b else None
        r={'Feed':feed,'Records':n,'Valid timestamps':valid,'Invalid timestamp %':pct(n-valid,n),'Median delay (min)':round(median(ds),2) if ds else None,'P90 delay (min)':round(ds[math.ceil(.9*valid)-1],2) if ds else None,'Fresh ≤10 min %':pct(sum(v<=10 for v in ds),valid),'Classified':len(quality),'A/B candidates':sum(q['tier'] in ('A','B') for q in quality),'A/B yield %':pct(sum(q['tier'] in ('A','B') for q in quality),len(quality)),'Priority review':sum(q.get('review_candidate') is True for q in quality),'Priority yield %':pct(sum(q.get('review_candidate') is True for q in quality),len(quality)),'Duplicate assessed':len(dup),'Possible duplicate %':pct(sum(e.get('duplicate_status')=='possible_duplicate' for e in dup),len(dup))}
        if by_publisher: r={'Reported publisher (unverified)':pub,**r}
        result.append(r)
    return result
