"""RSS-based public-news monitor. Heuristic impact, NOT investment advice."""
import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import feedparser
import requests
from prices import quote

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "events.json"
CONFIG = ROOT / "config.json"
HEADERS = {"User-Agent": "MarketNewsIntelligence/1.0 (public research; contact: set CONTACT_EMAIL env var)"}

ASSETS = {
    "BTC": [r"\bbitcoin\b", r"\bbtc\b"],
    "ETH": [r"\bethereum\b", r"\bether\b", r"\beth\b"],
    "SOL": [r"\bsolana\b", r"\bsol\b"],
    "NVDA": [r"\bnvidia\b", r"\bnvda\b"],
    "AMD": [r"\badvanced micro devices\b", r"\bamd\b"],
    "AAPL": [r"\bapple\b", r"\baapl\b"],
    "MSFT": [r"\bmicrosoft\b", r"\bmsft\b"],
    "TSLA": [r"\btesla\b", r"\btsla\b"],
    "COIN": [r"\bcoinbase\b", r"\bcoin\b"],
    "MSTR": [r"\bmicrostrategy\b", r"\bstrategy inc\b", r"\bmstr\b"],
}
CRYPTO = {"BTC", "ETH", "SOL"}
BULL = [r"\bapproval\b", r"\bapproved\b", r"\bbeat(s)? expectations\b", r"\brecord (revenue|profit)\b", r"\bpartnership\b", r"\bupgrade\b", r"\brate cut\b", r"\betf inflows?\b", r"\bbuyback\b", r"\bpositive guidance\b"]
BEAR = [r"\bhack(ed)?\b", r"\bbreach\b", r"\blawsuit\b", r"\bcharged\b", r"\bfine(d)?\b", r"\bdowngrade\b", r"\bmiss(es|ed)? expectations\b", r"\blayoffs?\b", r"\bban(ned)?\b", r"\brate hike\b", r"\betf outflows?\b", r"\bbankrupt(cy)?\b", r"\brestrictions?\b"]
HIGH = [r"\bfederal reserve\b", r"\bsec\b", r"\binterest rates?\b", r"\betf\b", r"\bearnings\b", r"\bregulat", r"\bexport controls?\b", r"\bliquidat"]


def utcnow():
    return datetime.now(timezone.utc)


def canonical_url(url):
    """Remove common tracking params, retain link as provided otherwise."""
    try:
        p = urlparse(url)
        q = parse_qs(p.query)
        q = {k: v for k, v in q.items() if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}}
        return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), p.params, urlencode(q, doseq=True), ""))
    except Exception:
        return url


def normalized_title(title):
    title = re.sub(r"\s+[-|]\s+[^-|]{2,60}$", "", title)
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def event_id(title):
    return hashlib.sha256(normalized_title(title).encode()).hexdigest()[:20]


def parsed_time(entry):
    import calendar
    for attr in ("published_parsed", "updated_parsed"):
        val = entry.get(attr)
        if val:
            return datetime.fromtimestamp(calendar.timegm(val), tz=timezone.utc)
    return None


def analyze(title, summary, watchlist):
    # Deliberately use headline only for directional terms to reduce unrelated summary noise.
    t = title.lower()
    full = (title + " " + summary).lower()
    matched = [a for a in watchlist if a in ASSETS and any(re.search(p, full) for p in ASSETS[a])]
    bull = [p for p in BULL if re.search(p, t)]
    bear = [p for p in BEAR if re.search(p, t)]
    if bull and not bear:
        direction = "Potentially bullish"
    elif bear and not bull:
        direction = "Potentially bearish"
    else:
        direction = "Unclear / mixed"
    score = min(5, 1 + int(bool(matched)) + int(bool(bull or bear)) + int(any(re.search(p, full) for p in HIGH)) + int(len(matched) > 1))
    market = "Both" if any(a in CRYPTO for a in matched) and any(a not in CRYPTO for a in matched) else "Crypto" if any(a in CRYPTO for a in matched) else "Stocks" if matched else "Macro / unspecified"
    rationale = ("Headline contains potentially positive catalysts." if direction == "Potentially bullish" else "Headline contains potentially negative catalysts." if direction == "Potentially bearish" else "Headline does not provide a reliable directional catalyst.")
    return {"assets": matched, "market": market, "direction": direction, "significance_score": score, "rationale": rationale + " This is a keyword-based hypothesis, not a verified price forecast; check primary source and live market response."}


def load_events():
    if not DATA.exists():
        return []
    try:
        value = json.loads(DATA.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (ValueError, OSError):
        raise RuntimeError("events.json invalid; refusing to overwrite history")


def save_events(events):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    temp = DATA.with_suffix(".tmp")
    temp.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(DATA)


def discord_webhook_for(event):
    """Choose a channel based on significance and affected market."""
    if event["significance_score"] >= 5:
        return os.environ.get("DISCORD_CRITICAL_WEBHOOK_URL", "").strip()
    market = event["market"]
    if market == "Crypto":
        return os.environ.get("DISCORD_CRYPTO_WEBHOOK_URL", "").strip()
    if market == "Stocks":
        return os.environ.get("DISCORD_STOCK_WEBHOOK_URL", "").strip()
    return os.environ.get("DISCORD_CRITICAL_WEBHOOK_URL", "").strip()


def send_discord(event):
    """Post one real news event to the appropriate Discord webhook."""
    url = discord_webhook_for(event)
    if not url:
        print("Discord webhook missing for market; skipping alert")
        return False
    if not url.startswith("https://discord.com/api/webhooks/"):
        raise ValueError("Invalid Discord webhook URL")
    content = (
        f"**MARKET NEWS | {event['direction']}**\n"
        f"**{event['title'][:240]}**\n"
        f"Market: {event['market']} | Assets: {', '.join(event['assets']) or 'Unspecified'}\n"
        f"Significance: {event['significance_score']}/5 (not a probability)\n"
        f"Published UTC: {event['published_at']}\n"
        f"Detected UTC: {event['detected_at']}\n"
        f"Source: {event['source']}\n"
        f"{event['rationale'][:400]}\n"
        f"Article: {event['url']}\n"
        "*Heuristic analysis only. No price confirmation; not investment advice.*"
    )
    response = requests.post(url, json={"content": content[:1900], "allowed_mentions": {"parse": []}}, timeout=20)
    response.raise_for_status()
    return True


def run():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    existing = load_events()
    initial = not existing
    known = {e["id"] for e in existing}
    fresh = []
    cutoff = utcnow() - timedelta(hours=cfg.get("max_age_hours", 48))
    for feed in cfg["feeds"]:
        try:
            headers = dict(HEADERS)
            if os.environ.get("CONTACT_EMAIL"):
                headers["User-Agent"] = f"MarketNewsIntelligence/1.0 {os.environ['CONTACT_EMAIL']}"
            r = requests.get(feed["url"], headers=headers, timeout=25)
            r.raise_for_status()
            parsed = feedparser.parse(r.content)
            if parsed.bozo and not parsed.entries:
                raise ValueError(f"Invalid feed: {parsed.bozo_exception}")
            for entry in parsed.entries[:60]:
                title = html.unescape(re.sub(r"<[^>]+>", "", entry.get("title", ""))).strip()
                url = canonical_url(entry.get("link", ""))
                if not title or not url:
                    continue
                dt = parsed_time(entry)
                # Reject undated items rather than pretending they are new.
                if not dt or dt < cutoff or dt > utcnow() + timedelta(minutes=10):
                    continue
                key = event_id(title)
                if key in known:
                    continue
                summary = html.unescape(re.sub(r"<[^>]+>", " ", entry.get("summary", "")))[:600]
                details = analyze(title, summary, cfg.get("watchlist", []))
                e = {"id": key, "title": title, "url": url, "source": feed["name"], "published_at": dt.isoformat(), "detected_at": utcnow().isoformat(), **details}
                fresh.append(e)
                known.add(key)
            print(f"{feed['name']}: fetched {len(parsed.entries)} entries")
        except Exception as ex:
            print(f"FEED ERROR {feed['name']}: {type(ex).__name__}: {ex}")
    fresh.sort(key=lambda x: x["published_at"])
    # Save before sending; GitHub Actions commit preserves dedup across runs.
    combined = sorted(existing + fresh, key=lambda x: x["detected_at"], reverse=True)[:cfg.get("max_events", 2000)]
    # Preserve delivery status across scans; retry unsuccessful eligible notifications.
    for e in combined:
        if 'alert_status' not in e:
            e['alert_status'] = 'pending' if e['significance_score'] >= cfg.get('alert_min_score', 3) else 'below_threshold'
    if initial and not cfg.get('alert_on_first_run', False):
        for e in fresh: e['alert_status'] = 'first_run_suppressed'
    # Record only actual observation-time prices. Do not claim historical publication-time quotes.
    targets = sorted({a for e in combined[:300] for a in e.get('assets', []) if a in ASSETS})
    quotes = {a: quote(a) for a in targets}
    horizons = [15, 60, 240, 1440]
    for e in combined[:300]:
        reactions = e.setdefault('price_reactions', {})
        for a in e.get('assets', []):
            if not quotes.get(a): continue
            record = reactions.setdefault(a, {'baseline': quotes[a], 'followups': {}})
            baseline = record.get('baseline', {})
            try:
                start = datetime.fromisoformat(baseline['observed_at'])
                elapsed = (utcnow()-start).total_seconds()/60
                for minutes in horizons:
                    key = str(minutes)
                    if elapsed >= minutes and key not in record.setdefault('followups', {}):
                        current = dict(quotes[a]); current['change_pct'] = round(100*(current['price']/float(baseline['price'])-1), 4)
                        record['followups'][key] = current
            except (KeyError,TypeError,ValueError,ZeroDivisionError): pass
    save_events(combined)
    alerts = 0
    attempted = failed = 0
    for e in combined:
        if e.get('alert_status') not in ('pending', 'failed'): continue
        attempted += 1
        try:
            if send_discord(e):
                e['alert_status'] = 'delivered'; e['alert_delivered_at'] = utcnow().isoformat(); alerts += 1
            else:
                e['alert_status'] = 'failed'; failed += 1
        except Exception as ex:
            e['alert_status'] = 'failed'; failed += 1
            print(f"ALERT ERROR for {e['id']}: {type(ex).__name__}: {ex}")
        e['alert_last_attempt_at'] = utcnow().isoformat()
        e['alert_attempts'] = e.get('alert_attempts', 0) + 1
        save_events(combined)
    print(f"Discord attempted: {attempted}; failed: {failed}")
    print(f"New events: {len(fresh)}; Discord alerts: {alerts}; total stored: {len(combined)}")


if __name__ == "__main__":
    run()
