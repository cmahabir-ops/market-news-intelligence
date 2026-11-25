import json
from datetime import datetime, timezone
import requests
import feedparser

cfg = json.load(open("config.json", encoding="utf-8"))
failed = 0
for feed in cfg["feeds"]:
    try:
        r = requests.get(feed["url"], headers={"User-Agent": "MarketNewsIntelligence/1.0"}, timeout=25)
        r.raise_for_status()
        parsed = feedparser.parse(r.content)
        if not parsed.entries:
            raise ValueError("No entries returned")
        ages = []
        for entry in parsed.entries[:60]:
            stamp = entry.get("published_parsed") or entry.get("updated_parsed")
            if stamp:
                dt = datetime(*stamp[:6], tzinfo=timezone.utc)
                ages.append((datetime.now(timezone.utc)-dt).total_seconds()/60)
        print(f"{feed['name']}: HTTP {r.status_code}; entries={len(parsed.entries)}; dated={len(ages)}; recent={sum(0<=a<=2880 for a in ages)}; newest age={min(ages) if ages else None} min")
        if not ages:
            failed += 1
    except Exception as exc:
        failed += 1
        print(f"FAIL {feed['name']}: {exc}")
raise SystemExit(1 if failed else 0)
