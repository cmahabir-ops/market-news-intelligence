"""Scan health and conservative exact-title source comparisons."""
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

def now(): return datetime.now(timezone.utc).isoformat()

def save(path, report):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(report,indent=2),encoding='utf-8'); tmp.replace(path)

def archive_summary(root):
    root=Path(root); groups=defaultdict(dict); counts={'snapshots':0,'arrivals':0,'unreadable':0}; ids=set()
    for category in ('events','arrivals'):
        for path in (root/category).glob('*/*.json'):
            try:
                r=json.loads(path.read_text(encoding='utf-8'))
                if category=='events':
                    ids.add(r['id']); counts['snapshots']+=1
                else:
                    t=datetime.fromisoformat(r['detected_at']); assert t.tzinfo is not None
                    key=r['event_id']; source=r['source']; old=groups[key].get(source)
                    if old is None or t<old: groups[key][source]=t
                    counts['arrivals']+=1
            except (OSError,ValueError,KeyError,TypeError,AssertionError): counts['unreadable']+=1
    counts['unique_events']=len(ids)
    rows=[]
    for key,sources in groups.items():
        if len(sources)<2: continue
        first=min(sources.values())
        for source,t in sorted(sources.items(),key=lambda x:x[1]):
            rows.append(dict(event_id=key,source=source,detected_at=t.isoformat(),minutes_after_first=round((t-first).total_seconds()/60,2)))
    counts['matched_groups']=len({r['event_id'] for r in rows})
    return counts, sorted(rows,key=lambda r:r['detected_at'],reverse=True)
