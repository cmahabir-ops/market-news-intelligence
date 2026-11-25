"""Explain V3 validation exclusions without rewriting historical events."""
from datetime import datetime

def reason(event):
    if event.get('attribution_method') != 'headline_mentions_v3':
        return 'Legacy record (not V3)'
    asset = event.get('primary_asset')
    if not asset:
        return 'No unique primary asset'
    if event.get('direction') not in ('Potentially bullish','Potentially bearish'):
        return 'No directional hypothesis'
    record = (event.get('price_reactions') or {}).get(asset)
    if not record:
        return 'No price record'
    baseline = record.get('baseline') or {}
    if not baseline.get('valid_for_reaction'):
        return 'Invalid or stale baseline'
    try:
        lag=abs((datetime.fromisoformat(baseline['observed_at'])-datetime.fromisoformat(event['detected_at'])).total_seconds())
        if lag>1800:
            return 'Baseline captured over 30 minutes after detection'
    except (ValueError, TypeError, KeyError):
        return 'Missing baseline timestamp'
    followups=record.get('followups') or {}
    if not followups:
        return 'Awaiting eligible follow-up'
    if not any(f.get('valid_for_reaction') and isinstance(f.get('change_pct'),(int,float)) for f in followups.values()):
        return 'No valid completed follow-up'
    return 'Eligible for directional analysis'
