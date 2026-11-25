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
