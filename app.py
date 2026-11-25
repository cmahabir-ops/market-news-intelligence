"""Public Streamlit dashboard; refresh browser for latest committed events."""
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Market News Intelligence", page_icon="📰", layout="wide")
st.title("📰 Market News Intelligence")
st.caption("Real public RSS headlines • heuristic impact only • not a live trade signal")

st.sidebar.header("V3.5.3 — Dashboard refresh")
auto = st.sidebar.checkbox("Automatic refresh", value=True)
interval = st.sidebar.selectbox("Refresh interval (seconds)", [15, 30, 60, 300], index=2)
st.sidebar.button("Refresh now", on_click=st.rerun)
st.sidebar.caption("Automatic refresh runs while this session is active; scanner cadence is unchanged.")

def render_dashboard():
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
    st.caption(f"Dashboard refreshed (UTC): {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}")
    latest = pd.to_datetime(pd.Series([e.get("detected_at") for e in events]), utc=True, errors="coerce").max()
    if pd.notna(latest):
        age = (pd.Timestamp.now(tz="UTC") - latest).total_seconds() / 60
        st.caption(f"Latest detected headline (UTC): {latest:%Y-%m-%d %H:%M:%S} | Age: {age:.1f} min. This is not a scanner heartbeat.")
    st.caption("Reads the local deployed event file on each refresh. GitHub-to-Streamlit synchronization may introduce additional delay.")
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
    st.caption('Scan-time snapshots only, not exchange-synchronized event studies. V3.5.1 new events allow actual per-asset receipt intervals of 4.5–7 minutes for the nominal five-minute horizon; legacy records retain their original labels. Missing windows are not interpolated. Correlation does not establish news causality.')
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


    st.subheader("V3.5.1 — Observation timing audit")
    if impact_data:
        audit = pd.DataFrame(impact_data)
        if "Method" not in audit.columns:
            audit["Method"] = "Unknown / legacy schema"
            st.warning("Impact module is not reporting method labels. Verify impact.py is updated and restart the app.")
        required = ["Method", "Horizon (min)", "Status"]
        if all(c in audit.columns for c in required):
            st.dataframe(audit.groupby(required, dropna=False).size().reset_index(name="Windows"), hide_index=True)
        else:
            st.warning("Timing audit unavailable: observation columns are missing.")
        st.caption("Nominal horizons are not exact exchange-time returns. Actual per-asset elapsed times are recorded for new observations.")

    st.subheader('V3.5.2 — Catalyst quality and news relevance')
    from quality import rows as quality_rows_v352
    st.caption('Headline-only triage of new records. Feed freshness is not proof of original event freshness. No forecast-ready labels are assigned. Existing alerts and impact collection are unchanged.')
    qrows = quality_rows_v352(events)
    if qrows:
        qdf = pd.DataFrame(qrows)
        a,b,c = st.columns(3)
        a.metric('Classified headlines', len(qdf))
        b.metric('A/B candidates', int(qdf['Tier'].isin(['A','B']).sum()))
        c.metric('Priority manual review', int(qdf['Review candidate'].sum()))
        st.dataframe(qdf['Tier'].value_counts().reindex(['A','B','C','D'],fill_value=0).rename_axis('Tier').reset_index(name='Headlines'),hide_index=True)
        tier = st.selectbox('Quality tier',['All','A','B','C','D'],key='v352_tier')
        st.dataframe(qdf if tier=='All' else qdf[qdf['Tier']==tier],hide_index=True,use_container_width=True)
    else:
        st.info('Awaiting newly collected V3.5.2 headlines. Historical records are unchanged.')

    st.subheader("V3.6.3 — Scanner and source health")
    from health_v363 import archive_summary
    health_path = path.parent / "scanner_health.json"
    try:
        health = json.loads(health_path.read_text(encoding="utf-8"))
        stamp = pd.Timestamp(health["completed_at"])
        age = (pd.Timestamp.now(tz="UTC") - stamp).total_seconds()/60
        st.metric("Last completed scan age (minutes)", round(age,1))
        if age > 15: st.warning("Scanner report is stale or deployment synchronization is delayed.")
        st.dataframe(pd.DataFrame(health["feeds"]), hide_index=True)
        if health.get("edgar"): st.dataframe(pd.DataFrame(health["edgar"]),hide_index=True)
    except (OSError,ValueError,KeyError,TypeError):
        st.info("Awaiting first committed scanner health report.")
    st.caption("Latest completed scan only; not a continuous uptime measurement.")
    if st.checkbox("Load historical archive audit", key="v363_archive"):
        counts, matches = archive_summary(path.parent / "research_archive")
        st.write(counts)
        st.caption("Exact stored event-key matches only; not verified equivalent events. Snapshots are versions, not independent events.")
        if matches: st.dataframe(pd.DataFrame(matches[:500]),hide_index=True)
        else: st.info("No cross-source event-key matches yet.")

    st.subheader("V3.6.4 — Research candidates and health history")
    if st.checkbox("Load cross-source review candidates", key="v364_matches"):
        from matching_v364 import candidates
        pairs = candidates(path.parent / "research_archive")
        st.caption("Lexical candidates from up to 2,000 recent arrivals; not semantic verification or causal evidence. Positive gap means source B was detected later.")
        if pairs: st.dataframe(pd.DataFrame(pairs), hide_index=True)
        else: st.info("No qualifying cross-source candidates.")
    if st.checkbox("Load historical source health", key="v364_health"):
        reports=[]
        for f in (path.parent / "research_archive" / "health").glob("*/*.json"):
            try: reports.extend(json.loads(f.read_text(encoding="utf-8"))["feeds"])
            except (OSError, ValueError, KeyError, TypeError): continue
        if reports:
            h=pd.DataFrame(reports)
            h["ok"] = h["status"].eq("ok")
            st.dataframe(h.groupby("source").agg(scans=("ok","size"), successful=("ok","sum"), success_fraction=("ok","mean")).reset_index(),hide_index=True)
        else: st.info("Awaiting historical health reports.")
        st.caption("Completed archived scans only; not continuous uptime.")
    st.caption("Local cryptocurrency collector is independent of this hosted dashboard.")

    st.subheader("V3.5.4 — News source latency intelligence")
    from latency import summarize
    st.caption("Stored records only: reported feed timestamp to first detection, not original event latency. Publication timestamps may actually be update timestamps. Deduplication and retention limit coverage; these are not provider-wide delivery statistics.")
    period = st.selectbox("Latency audit period", ["All retained records", "Last 24 hours", "Last 7 days"], key="v354_period")
    selected = events
    if period != "All retained records":
        hours = 24 if period == "Last 24 hours" else 168
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=hours)
        selected = [e for e in events if (t := pd.to_datetime(e.get("detected_at"), utc=True, errors="coerce")) is not None and pd.notna(t) and t >= cutoff]
    if selected:
        st.dataframe(pd.DataFrame(summarize(selected)), hide_index=True, use_container_width=True)
        st.caption("Freshness uses valid nonnegative delays only; P90 uses nearest rank. A/B and priority yields use V3.5.2 classified records only; duplicate rates use assessed records only. Missing rates mean no eligible denominator. Small samples are not reliable rankings.")
        with st.expander("Reported publisher breakdown (unverified)"):
            st.dataframe(pd.DataFrame(summarize(selected, by_publisher=True)), hide_index=True, use_container_width=True)
            st.caption("Google News title suffixes are publisher hints, not verified identities. Other feeds are not independently attributed.")
    else:
        st.info("No retained records in this period.")

if hasattr(st, "fragment"):
    st.fragment(run_every=f"{interval}s" if auto else None)(render_dashboard)()
else:
    st.warning("Automatic refresh requires Streamlit 1.37 or newer. Manual refresh remains available.")
    render_dashboard()
