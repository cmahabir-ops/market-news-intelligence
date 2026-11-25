"""Public Streamlit dashboard; refresh browser for latest committed events."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Market News Intelligence", page_icon="📰", layout="wide")
st.title("📰 Market News Intelligence")
st.caption("Real public RSS headlines • heuristic impact only • not a live trade signal")
path = Path(__file__).parent / "data" / "events.json"
if not path.exists():
    st.info("No events yet. Run the scanner workflow, then refresh this page.")
    st.stop()
try:
    events = json.loads(path.read_text(encoding="utf-8"))
except (OSError, ValueError):
    st.error("Unable to read event log.")
    st.stop()
if not events:
    st.info("Event log is empty. Await first successful scan.")
    st.stop()
df = pd.DataFrame(events)
for c in ("detected_at", "published_at"):
    df[c] = pd.to_datetime(df[c], utc=True, errors="coerce")
df["assets_display"] = df["assets"].apply(lambda a: ", ".join(a) if isinstance(a, list) else "")
a, b, c = st.columns(3)
a.metric("Events stored", len(df))
b.metric("Potential bullish", int((df["direction"] == "Potentially bullish").sum()))
c.metric("Potential bearish", int((df["direction"] == "Potentially bearish").sum()))
st.warning("Significance is a 1–5 rule-based relevance score, NOT a probability or confidence score. Direction is unvalidated and may be wrong.")
market = st.selectbox("Market", ["All"] + sorted(df["market"].dropna().unique().tolist()))
direction = st.selectbox("Direction", ["All"] + sorted(df["direction"].dropna().unique().tolist()))
asset = st.text_input("Filter asset (e.g., BTC, NVDA)").strip().upper()
filtered = df.copy()
if market != "All": filtered = filtered[filtered["market"] == market]
if direction != "All": filtered = filtered[filtered["direction"] == direction]
if asset: filtered = filtered[filtered["assets_display"].str.contains(asset, regex=False, na=False)]
filtered = filtered.sort_values("detected_at", ascending=False)
st.dataframe(filtered[["detected_at", "published_at", "source", "title", "market", "assets_display", "direction", "significance_score", "url"]], hide_index=True, use_container_width=True, column_config={"url": st.column_config.LinkColumn("Original link")})
st.caption("Detected time = first scan that saw the item; published time = timestamp reported by feed. Neither is exchange reaction time.")
st.subheader("Event details")
if len(filtered):
    selection = st.selectbox("Select event", filtered["id"].tolist(), format_func=lambda i: filtered.loc[filtered["id"] == i, "title"].iloc[0][:110])
    e = next(e for e in events if e["id"] == selection)
    st.write(e["rationale"])
    st.markdown(f"[Read source]({e['url']})")
st.button("Refresh dashboard", on_click=st.rerun)

st.subheader('Discord delivery audit')
if 'alert_status' in df.columns:
    st.dataframe(df['alert_status'].fillna('legacy / unknown').value_counts().rename_axis('Status').reset_index(name='Events'),hide_index=True)
else:
    st.info('Legacy events have no delivery audit. Audit begins after the first Version 2 scan.')
st.subheader('Observed market reactions')
st.caption('Indicative USD snapshots captured by the scanner. Baseline is first observed quote, not the price at publication. Follow-ups are first scan at or after each horizon; stocks may be stale outside market hours.')
reaction_rows=[]
for event in events:
    for symbol, record in event.get('price_reactions', {}).items():
        base=record.get('baseline', {})
        for horizon, followup in record.get('followups', {}).items():
            reaction_rows.append({'Event':event.get('title','')[:90], 'Asset':symbol,'Horizon (minutes)':int(horizon),'Baseline USD':base.get('price'),'Follow-up USD':followup.get('price'),'Change %':followup.get('change_pct'),'Observed UTC':followup.get('observed_at'),'Source':followup.get('source')})
if reaction_rows:
    st.dataframe(pd.DataFrame(reaction_rows).sort_values('Observed UTC',ascending=False),hide_index=True,use_container_width=True)
else:
    st.info('No completed observation windows yet. Price measurements appear after subsequent scans.')

st.subheader('V3 — Directional validation (experimental)')
st.caption('Only new V3 events with one headline-attributed primary asset and valid completed quote windows are included. Descriptive agreement is not trading accuracy or evidence of causality.')
from validation import completed_rows
vrows=completed_rows(events)
if vrows:
    vdf=pd.DataFrame(vrows)
    horizon=st.selectbox('Validation horizon (minutes)',sorted(vdf['horizon_min'].unique().tolist()))
    subset=vdf[vdf['horizon_min']==horizon]
    # One observation cluster is one sample; conflicting articles sharing a quote are excluded.
    clusters=[]
    for _,grp in subset.groupby('cluster'):
        if grp['direction'].nunique()!=1: continue
        clusters.append(grp.iloc[0])
    independent=pd.DataFrame(clusters) if clusters else pd.DataFrame()
    x,y,z=st.columns(3)
    x.metric('Eligible headline-event rows',len(subset))
    y.metric('Distinct nonconflicting price clusters',len(independent))
    z.metric('Directional agreement',f"{independent['direction_match'].mean():.1%}" if len(independent) else 'N/A')
    if len(independent):
        st.dataframe(independent[['asset','direction','return_pct','benchmark_return_pct','excess_return_pct','direction_match','followup_at']],hide_index=True,use_container_width=True)
    st.warning('Sample sizes may be small or correlated. These metrics exclude neutral classifications and do not account for trading costs, slippage, news arrival latency or selection bias. No causal or profitable-trading claim is implied.')
else:
    st.info('No eligible V3 observation windows yet. New V3 events need a valid baseline and a subsequent eligible quote.')


st.subheader('V3.1 — Validation eligibility diagnostics')
from diagnostics import reason
from collections import Counter
reasons = Counter(reason(e) for e in events)
st.dataframe(pd.DataFrame([{'Reason': k, 'Events': v} for k,v in reasons.most_common()]), hide_index=True, use_container_width=True)
st.caption('Diagnostics include legacy records for transparency. No existing records are reclassified.')
v3_events = [e for e in events if e.get('attribution_method') == 'headline_mentions_v3']
if v3_events:
    st.dataframe(pd.DataFrame([{'Detected UTC':e.get('detected_at'), 'Headline':e.get('title'), 'Primary asset':e.get('primary_asset'), 'Direction':e.get('direction'), 'Exclusion / status':reason(e)} for e in v3_events]).sort_values('Detected UTC', ascending=False), hide_index=True, use_container_width=True)


st.subheader('V3.2 — Catalyst quality and freshness')
st.caption('Only newly collected V3.2 headlines are assessed. A candidate is a rule-based hypothesis, not a verified prediction.')
v32 = [e for e in events if e.get('catalyst_method') == 'headline_rules_v3_2']
if v32:
    v32df = pd.DataFrame([{'Detected UTC':e.get('detected_at'), 'Headline':e.get('title'),
      'Asset':e.get('primary_asset'), 'Catalyst':e.get('catalyst_type'),
      'Status':e.get('hypothesis_status'), 'Freshness':e.get('freshness_status'),
      'Delay (min)':e.get('detection_delay_minutes'), 'Hypothesis':e.get('hypothesis_direction'),
      'Validation':reason(e)} for e in v32])
    k1,k2,k3=st.columns(3)
    k1.metric('V3.2 headlines',len(v32df))
    k2.metric('Catalyst candidates',int((v32df['Status']=='candidate').sum()))
    k3.metric('Valid directional windows',sum(1 for e in v32 if reason(e)=='Eligible for directional analysis'))
    st.dataframe(v32df['Status'].value_counts().rename_axis('Status').reset_index(name='Events'),hide_index=True)
    st.dataframe(v32df.sort_values('Detected UTC',ascending=False),hide_index=True,use_container_width=True)
else:
    st.info('Awaiting first V3.2 scan. Existing V3 and legacy events are intentionally unchanged.')


st.subheader('V3.3 — Source, macro and near-duplicate audit')
st.caption('Observational context only. Macro benchmark mappings are not directional predictions or validated event reactions. Aggregated RSS links do not verify original publishers. Near-duplicates are flagged, never removed.')
v33=[e for e in events if e.get('intelligence_method')=='observational_v3_3']
if v33:
    x,y,z=st.columns(3)
    x.metric('V3.3 events',len(v33))
    y.metric('Macro context candidates',sum(e.get('macro_status')=='candidate_context' for e in v33))
    z.metric('Possible near-duplicates',sum(e.get('duplicate_status')=='possible_duplicate' for e in v33))
    audit=pd.DataFrame([{'Detected UTC':e.get('detected_at'), 'Headline':e.get('title'),
        'Source tier':e.get('source_tier'), 'Macro context':e.get('macro_event_type'),
        'Macro benchmarks':', '.join(e.get('macro_benchmarks',[])),
        'Possible duplicate of':e.get('possible_duplicate_of')} for e in v33])
    st.dataframe(audit.sort_values('Detected UTC',ascending=False),hide_index=True,use_container_width=True)
else:
    st.info('Awaiting first V3.3 scan. Existing events are intentionally unchanged.')


st.subheader('V3.4 — Reaction validation quality audit')
st.caption('Descriptive quote observations only. No causal inference, predictive accuracy, or trading profitability is established.')
from validation import validation_funnel, independent_clusters
funnel=validation_funnel(events)
st.dataframe(pd.DataFrame(funnel),hide_index=True,use_container_width=True)
quality_rows=completed_rows(events)
if quality_rows:
    selected_horizon=st.selectbox('V3.4 horizon (minutes)',sorted({r['horizon_min'] for r in quality_rows}))
    selected_rows=[r for r in quality_rows if r['horizon_min']==selected_horizon]
    unique_rows,conflicts=independent_clusters(selected_rows)
    a,b,c=st.columns(3)
    a.metric('Eligible headline windows',len(selected_rows))
    b.metric('Nonconflicting quote clusters',len(unique_rows))
    c.metric('Conflicting clusters excluded',conflicts)
    st.dataframe(pd.DataFrame(unique_rows),hide_index=True,use_container_width=True)
    st.caption('Repeated headlines sharing a quote window are clustered. Benchmark-adjusted returns are shown only where available.')
else:
    st.info('No eligible V3.4 price windows. The funnel above identifies the exclusion reasons.')


st.subheader('V3.5 — Cross-market impact observations')
st.caption('Scan-time snapshots only, not exchange-synchronized event studies. Five-minute windows require a scan within 5–7 minutes of baseline. Missing windows are not interpolated. Correlation does not establish news causality.')
from impact import rows as impact_rows
impact_events = [e for e in events if e.get('cross_market_impact')]
i1,i2,i3 = st.columns(3)
i1.metric('Events tracked for cross-market impact', len(impact_events))
impact_data = impact_rows(events)
i2.metric('Observed windows', sum(r['Status']=='observed' for r in impact_data))
i3.metric('Missed windows', sum(r['Status']=='missed_window' for r in impact_data))
if impact_data:
    impact_df = pd.DataFrame(impact_data)
    choices = ['All'] + sorted(impact_df['Horizon (min)'].unique().tolist())
    chosen = st.selectbox('Impact horizon (minutes)', choices, key='v35_horizon')
    if chosen != 'All':
        impact_df = impact_df[impact_df['Horizon (min)']==chosen]
    st.dataframe(impact_df.sort_values('Detected UTC', ascending=False), hide_index=True, use_container_width=True)
else:
    st.info('Awaiting newly detected V3.5-eligible single-asset or macro-context events. Older events are not reclassified.')
st.warning('Market-data providers are indicative; stock quotes may be delayed or unavailable outside regular trading hours. No five-minute impact is claimed without an eligible observed window.')
