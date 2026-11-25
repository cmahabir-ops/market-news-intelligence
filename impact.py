"""V3.5 observational cross-asset reactions; never infer news causality.

No historical candles are fabricated. A completed horizon requires a scan near that
horizon; delayed scans are marked missed rather than treated as five-minute data.
"""
from datetime import datetime, timezone
from math import isfinite

# Explicit research baskets, NOT inferred causal links.
BASKETS = {
    'NVDA': ('NVDA', 'AMD', 'SMH', 'QQQ', 'SPY'),
    'AMD': ('AMD', 'NVDA', 'SMH', 'QQQ', 'SPY'),
    'AAPL': ('AAPL', 'XLK', 'QQQ', 'SPY'),
    'MSFT': ('MSFT', 'XLK', 'QQQ', 'SPY'),
    'TSLA': ('TSLA', 'QQQ', 'SPY'),
    'COIN': ('COIN', 'BTC', 'QQQ', 'SPY'),
    'MSTR': ('MSTR', 'BTC', 'QQQ', 'SPY'),
    'BTC': ('BTC', 'ETH', 'SOL'),
    'ETH': ('ETH', 'BTC', 'SOL'),
    'SOL': ('SOL', 'BTC', 'ETH'),
    'XRP': ('XRP', 'BTC', 'ETH'),
    'ADA': ('ADA', 'BTC', 'ETH'),
    'DOGE': ('DOGE', 'BTC', 'ETH'),
}
MACRO = ('SPY', 'QQQ', 'SMH', 'XLK', 'BTC')
HORIZONS = {5: 2, 15: 5, 60: 15}  # minutes, max lateness
MAX_DELAY_MIN = 10  # no claim of initial response for late-detected news
MAX_EVENT_AGE_MIN = 90


def parse_dt(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def basket(event):
    if event.get('intelligence_method') != 'observational_v3_3':
        return ()  # historical records intentionally unchanged
    primary = event.get('primary_asset')
    if primary in BASKETS:
        return BASKETS[primary]
    if event.get('macro_status') == 'candidate_context':
        return MACRO
    return ()


def positive_quote(q):
    try:
        if not (q and q.get('valid_for_reaction') is True and
                isfinite(float(q['price'])) and float(q['price']) > 0 and parse_dt(q.get('observed_at'))):
            return False
        # Stocks must carry a recent exchange timestamp, not just a fresh HTTP response.
        if q.get('session') == 'regular_candidate':
            provider = parse_dt(q.get('quote_at'))
            received = parse_dt(q.get('observed_at'))
            return bool(provider and received and -60 <= (received-provider).total_seconds() <= 120)
        return q.get('session') == 'continuous'
    except (ValueError, TypeError, KeyError):
        return False


def valid_delay(event):
    detected = parse_dt(event.get('detected_at'))
    published = parse_dt(event.get('published_at'))
    if not detected or not published:
        return False
    minutes = (detected - published).total_seconds() / 60
    return -1 <= minutes <= MAX_DELAY_MIN


def update(event, quotes, now):
    """Update an event in place, preserving missing-data status and timestamps.

    Snapshots are taken at scan time; stock quotes must have valid session flags.
    Coinbase spot timestamps are unavailable and are labeled indicative.
    """
    assets = basket(event)
    if not assets:
        return
    now = parse_dt(now.isoformat() if hasattr(now, 'isoformat') else now)
    detected = parse_dt(event.get('detected_at'))
    if not now or not detected:
        return
    state = event.setdefault('cross_market_impact', {
        'method': 'scan_snapshots_v3_5_1', 'assets': list(assets),
        'status': 'awaiting_baseline', 'baseline': {}, 'windows': {},
        'detection_delay_eligible': valid_delay(event),
    })
    # Never reset or backfill the baseline. No event-time price if the first scan was late.
    if not state['baseline']:
        if (now - detected).total_seconds() > 120:
            state['status'] = 'baseline_missed'
            return
        state['baseline'] = {a: dict(quotes[a]) for a in assets if positive_quote(quotes.get(a))}
        state['status'] = 'tracking' if state['baseline'] else 'awaiting_baseline'
        return
    baseline = state['baseline']
    if not baseline:
        return
    base_time = min(parse_dt(q['observed_at']) for q in baseline.values())
    elapsed = (now - base_time).total_seconds() / 60
    if elapsed < 0:
        return
    for horizon, grace in HORIZONS.items():
        key = str(horizon)
        if key in state['windows']:
            continue
        # Use actual per-asset receipt times, with a disclosed 30-second early tolerance.
        early = 0.5 if state.get('method') == 'scan_snapshots_v3_5_1' else 0
        if elapsed < horizon - early:
            continue
        if elapsed > horizon + grace + 2:
            state['windows'][key] = {'status': 'missed_window', 'elapsed_min': round(elapsed, 2)}
            continue
        returns = {}
        asset_elapsed = {}
        for a, base in baseline.items():
            current = quotes.get(a)
            if not positive_quote(current):
                continue
            observed = parse_dt(current['observed_at'])
            # Must be a fresh scan quote near the window, not an old provider observation.
            if abs((now - observed).total_seconds()) > 120:
                continue
            age = (observed - parse_dt(base['observed_at'])).total_seconds() / 60
            if age < horizon - early:
                continue
            if age > horizon + grace:
                continue
            asset_elapsed[a] = round(age, 4)
            ret = 100 * (float(current['price']) / float(base['price']) - 1)
            if isfinite(ret):
                returns[a] = round(ret, 4)
        if not returns:
            continue
        primary = event.get('primary_asset')
        benchmark = 'BTC' if primary in {'ETH','SOL','XRP','ADA','DOGE'} else 'QQQ' if primary in {'NVDA','AMD','AAPL','MSFT','TSLA','COIN','MSTR'} else None
        excess = round(returns[primary] - returns[benchmark], 4) if primary in returns and benchmark in returns else None
        state['windows'][key] = {
            'status': 'observed' if returns else 'missing_valid_quotes',
            'elapsed_min': round(elapsed, 2), 'observed_at': now.isoformat(),
            'returns_pct': returns, 'asset_elapsed_min': asset_elapsed, 'benchmark': benchmark,
            'primary_excess_return_pct': excess,
            'positive_assets': sum(v > 0 for v in returns.values()),
            'negative_assets': sum(v < 0 for v in returns.values()),
            'limitations': 'Scan-time indicative snapshots; no causal attribution; may be delayed.'
        }
    if elapsed > MAX_EVENT_AGE_MIN:
        state['status'] = 'completed_or_expired'


def rows(events):
    result = []
    for e in events:
        state = e.get('cross_market_impact')
        if not state:
            continue
        for horizon, window in state.get('windows', {}).items():
            result.append({
                'Detected UTC': e.get('detected_at'), 'Headline': e.get('title'),
                'Primary asset': e.get('primary_asset'), 'Horizon (min)': int(horizon),
                'Status': window.get('status'), 'Actual elapsed (min)': window.get('elapsed_min'),
                'Returns (%)': ', '.join(f'{a}: {v:+.2f}%' for a,v in window.get('returns_pct', {}).items()),
                'Excess return (%)': window.get('primary_excess_return_pct'),
                'Positive assets': window.get('positive_assets'), 'Negative assets': window.get('negative_assets'),
                'Fresh event': state.get('detection_delay_eligible', False),
                'Method': state.get('method'), 'Assets observed': len(window.get('returns_pct', {})),
                'Asset elapsed (min)': str(window.get('asset_elapsed_min', {})),
            })
    return result
