"""Append-only research snapshots and per-feed first sightings, partitioned by hash."""
import json, hashlib
from pathlib import Path

def write(root, category, key, record, replace=False):
    digest=hashlib.sha256(key.encode()).hexdigest()
    path=Path(root)/category/digest[:2]/(digest+'.json')
    if path.exists() and not replace: return False
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(record,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    tmp.replace(path)
    return True

def snapshot(root, events):
    for e in events:
        payload=json.dumps(e,sort_keys=True,ensure_ascii=False)
        write(root,'events',e['id']+':'+hashlib.sha256(payload.encode()).hexdigest(),e)

def sighting(root, source, url, title, published, detected, event_key):
    return write(root,'arrivals',source+'\n'+url+'\n'+title,dict(source=source,url=url,title=title,published_at=published,detected_at=detected,event_id=event_key))
