"""Conservative headline attribution. Never infer causality from keyword mentions."""
import re
PATTERNS = {
 'BTC':[r'\bbitcoin\b',r'\bbtc\b'], 'ETH':[r'\bethereum\b',r'\bether\b',r'\beth\b'],
 'SOL':[r'\bsolana\b',r'\bsol\b'], 'NVDA':[r'\bnvidia\b',r'\bnvda\b'],
 'AMD':[r'\badvanced micro devices\b',r'\bamd\b'], 'AAPL':[r'\bapple\b',r'\baapl\b'],
 'MSFT':[r'\bmicrosoft\b',r'\bmsft\b'], 'TSLA':[r'\btesla\b',r'\btsla\b'],
 'XRP':[r'\bxrp\b',r'\bripple(?: labs)?\b'], 'ADA':[r'\bcardano\b',r'\bada\b'],
 'DOGE':[r'\bdogecoin\b',r'\bdoge\b'],
 'COIN':[r'\bcoinbase\b'], 'MSTR':[r'\bmicrostrategy\b',r'\bstrategy inc\b',r'\bmstr\b']}
CRYPTO={'BTC','ETH','SOL','XRP','ADA','DOGE'}
def attribute(title, summary, watchlist):
    # Headlines are treated as stronger evidence than summaries; no claim of causality.
    title_matches=[]
    for asset in watchlist:
        if asset in PATTERNS:
            positions=[m.start() for p in PATTERNS[asset] for m in re.finditer(p,title,re.I)]
            if positions: title_matches.append((min(positions),asset))
    title_matches.sort()
    primary=title_matches[0][1] if len(title_matches)==1 else None
    secondary=[a for _,a in title_matches if a != primary]
    # Summary-only mentions are contextual and not automatically tradeable targets.
    context=[a for a in watchlist if a in PATTERNS and a not in [v for _,v in title_matches]
             and any(re.search(p,summary,re.I) for p in PATTERNS[a])]
    return {'primary_asset':primary,'secondary_assets':secondary,'context_assets':context,
            'attribution_status':'single_headline_asset' if primary else 'multi_asset_or_unspecified',
            'attribution_method':'headline_mentions_v3',
            'asset_segments':{a:('Crypto' if a in CRYPTO else 'Stocks') for a in [v for _,v in title_matches]}}
