"""Headline-only research triage; never a verified catalyst or training label."""
import re
from datetime import datetime

METHOD = 'headline_quality_v3_5_2'

def assess(event):
    title = re.sub(r'\s+[-|]\s+[^-|]{2,65}$', '', event.get('title','')).lower()
    def hit(pattern): return bool(re.search(pattern, title))
    delay = None
    try:
        p,d = [datetime.fromisoformat(event[k].replace('Z','+00:00')) for k in ('published_at','detected_at')]
        if p.tzinfo and d.tzinfo: delay = (d-p).total_seconds()/60
    except (KeyError, ValueError, TypeError, AttributeError): pass
    fresh = delay is not None and 0 <= delay <= 10
    linked = bool(event.get('primary_asset') or event.get('macro_status') == 'candidate_context')
    if hit(r'\b(sportsbook|casino|giveaway|how to buy|coupon|price, news, quote and history)\b'):
        tier,kind='D','irrelevant_or_promotional'
    elif hit(r'\b(price prediction|price forecast|current price|technical analysis|outlook|opinion|what next|could|might|may|expected to|set to|preview|recap|last year|anniversary)\b'):
        tier,kind='C','commentary_or_speculation'
    elif linked and (event.get('catalyst_type') or hit(r'\b(?:raises?|cuts?|holds?) (?:interest )?rates\b|\b(?:earnings|revenue|profit) (?:beats?|misses?)\b|\b(?:announces?|completes?) (?:an? )?(?:acquisition|merger|buyback)\b|\b(?:sec|regulator) (?:approves?|rejects?|sues?|charges?)\b|\b(?:reports?|suffers?) (?:a )?(?:security breach|hack)\b')):
        tier,kind='A','direct_candidate'
    elif linked and hit(r'\b(?:export controls|supply chain disruption|tariffs|sanctions|production halt|trade restrictions)\b'):
        tier,kind='B','indirect_candidate'
    elif linked:
        tier,kind='C','reaction_or_unclassified'
    else:
        tier,kind='D','no_clear_asset_or_macro_link'
    reasons=[]
    if tier not in ('A','B'): reasons.append('not_catalyst_candidate')
    if not fresh: reasons.append('late_or_invalid_feed_timestamp')
    if event.get('possible_duplicate_of') or event.get('duplicate_status')=='possible_duplicate': reasons.append('possible_duplicate')
    if event.get('source_tier')!='official_domain': reasons.append('original_source_unverified')
    # Even official-domain links do not verify the underlying event time or surprise.
    return {'method':METHOD,'tier':tier,'kind':kind,'delay_min':round(delay,2) if delay is not None else None,'fresh':fresh,'review_candidate':not reasons,'exclusions':reasons,'forecast_ready':False}

def rows(events):
    return [{'Detected UTC':e.get('detected_at'),'Headline':e.get('title'),'Asset':e.get('primary_asset'),'Tier':q['tier'],'Type':q['kind'],'Delay (min)':q['delay_min'],'Review candidate':q['review_candidate'],'Exclusions':', '.join(q['exclusions']) or 'Manual verification required'} for e in events if (q:=e.get('quality_v352')) and q.get('method')==METHOD]
