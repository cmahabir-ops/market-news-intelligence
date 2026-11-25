"""V3.2 transparent headline-only hypotheses. Not trading predictions."""
import re
from datetime import datetime, timezone

# Catalysts must be clear, asset-specific and prospective; order does not imply importance.
POSITIVE = {
    'regulatory_approval': [r'\b(?:sec|regulator|fda)\s+(?:approves?|approved|grants? approval)\b', r'\b(?:etf|drug)\s+(?:is\s+)?approved\b'],
    'earnings_beat': [r'\b(?:beats?|beat)\s+(?:earnings|revenue|profit)\s+(?:estimates|expectations)\b',r'\b(?:earnings|revenue)\s+(?:beat|beats)\s+estimates\b'],
    'upgrade': [r'\b(?:analysts?|brokerage)\s+upgrades?\b',r'\bupgraded\s+to\s+buy\b'],
    'buyback': [r'\b(?:announces?|authorizes?|approves?)\s+(?:a\s+)?(?:share\s+)?buyback\b'],
}
NEGATIVE = {
    'regulatory_action': [r'\b(?:sec|regulator|fda)\s+(?:sues?|charges?|rejects?|bans?)\b',r'\b(?:etf|application)\s+(?:is\s+)?rejected\b'],
    'earnings_miss': [r'\b(?:misses?|missed)\s+(?:earnings|revenue|profit)\s+(?:estimates|expectations)\b'],
    'downgrade': [r'\b(?:analysts?|brokerage)\s+downgrades?\b',r'\bdowngraded\s+to\s+sell\b'],
    'security_incident': [r'\b(?:exchange|protocol|platform)\s+(?:is\s+)?hacked\b',r'\b(?:reports?|suffers?)\s+(?:a\s+)?(?:security\s+)?breach\b'],
}
# Exclude retrospective recaps, opinion and technical-analysis articles even if they contain catalysts.
NON_CATALYST = [r'\b(?:price prediction|price forecast|outlook|technical analysis|analyst charts|what next|what\'s next)\b',
                r'\b(?:could|might|may|will)\s+(?:rise|fall|surge|drop|hit|reach)\b',
                r'\b(?:stock|shares|bitcoin|ethereum|crypto|market)\s+(?:rises?|falls?|fell|surges?|slides?|slumps?|rallies?|drops?)\b',
                r'\b(?:after|amid)\s+(?:a\s+)?(?:rally|sell-?off)\b']

def classify(title, primary_asset, published_at=None, detected_at=None, max_delay_minutes=120):
    result={'catalyst_method':'headline_rules_v3_2','catalyst_type':None,
            'hypothesis_direction':None,'hypothesis_status':'no_primary_asset' if not primary_asset else 'no_clear_catalyst',
            'detection_delay_minutes':None,'freshness_status':'unknown'}
    if published_at and detected_at:
        try:
            pub=datetime.fromisoformat(published_at.replace('Z','+00:00'))
            det=datetime.fromisoformat(detected_at.replace('Z','+00:00'))
            if pub.tzinfo and det.tzinfo:
                delay=(det-pub).total_seconds()/60
                result['detection_delay_minutes']=round(delay,1)
                result['freshness_status']='fresh' if 0<=delay<=max_delay_minutes else 'late_or_invalid'
        except (ValueError,TypeError,AttributeError): pass
    if not primary_asset:return result
    if any(re.search(p,title,re.I) for p in NON_CATALYST):
        result['hypothesis_status']='commentary_or_price_recap';return result
    positive=[key for key,patterns in POSITIVE.items() if any(re.search(p,title,re.I) for p in patterns)]
    negative=[key for key,patterns in NEGATIVE.items() if any(re.search(p,title,re.I) for p in patterns)]
    if len(positive)+len(negative)!=1:
        result['hypothesis_status']='mixed_catalysts' if positive and negative else 'no_clear_catalyst'
        return result
    result['catalyst_type']=(positive or negative)[0]
    if result['freshness_status']!='fresh':
        result['hypothesis_status']='stale_or_unverified_publication';return result
    result['hypothesis_direction']='Potentially bullish' if positive else 'Potentially bearish'
    result['hypothesis_status']='candidate'
    return result
