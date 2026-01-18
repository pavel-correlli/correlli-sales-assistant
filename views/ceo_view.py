import streamlit as st
import pandas as pd
import plotly.express as px
from database import fetch_view_data, normalize_calls_df, add_outcome_category, query_postgres
from views.shared_ui import render_hint


def _plotly_template():
    return "plotly_dark" if st.session_state.get("ui_theme_v1", "dark") == "dark" else "plotly_white"


def _determine_market(pipeline):
    p = str(pipeline).upper()
    if p.startswith("CZ"):
        return "CZ"
    if p.startswith("SK"):
        return "SK"
    if p.startswith("RUK"):
        return "RUK"
    return "Others"

def render_ceo_dashboard(date_range, selected_markets, selected_pipelines):
    st.markdown("<h1 style='text-align:center;'>Strategic Radar</h1>", unsafe_allow_html=True)

    with st.spinner("Loading executive view..."):
        df_raw = fetch_view_data("Algonova_Calls_Raw")

    df = normalize_calls_df(df_raw)
    df = add_outcome_category(df)

    if df.empty:
        st.warning("No data available. Please check database connection.")
        return

    if "pipeline_name" in df.columns:
        df["computed_market"] = df["pipeline_name"].apply(_determine_market)
    else:
        df["computed_market"] = df.get("market", "Others")

    if "market" not in df.columns:
        df["market"] = df["computed_market"]

    mask = pd.Series([True] * len(df))
    if selected_markets:
        mask = mask & df["market"].isin(selected_markets)
    if selected_pipelines and "pipeline_name" in df.columns:
        mask = mask & df["pipeline_name"].isin(selected_pipelines)
    if len(date_range) == 2 and "call_date" in df.columns:
        mask = mask & (df["call_date"] >= date_range[0]) & (df["call_date"] <= date_range[1])

    df = df[mask].copy()
    if df.empty:
        st.warning("No data matches current filters.")
        return

    top_cols = st.columns(3)
    avg_quality = float(df["Average_quality"].mean()) if "Average_quality" in df.columns else float("nan")
    vague_rate = (df["outcome_category"].eq("Vague").mean() * 100) if "outcome_category" in df.columns else 0.0

    with top_cols[0]:
        if pd.isna(avg_quality):
            st.metric("Average Quality Score", "—", help="Overall compliance with company standards.")
        else:
            st.metric("Average Quality Score", f"{avg_quality:.2f}", help="Overall compliance with company standards.")
    with top_cols[1]:
        st.metric(
            "Vague Index (Global)",
            f"{vague_rate:.1f}%",
            help="Share of calls with a vague outcome (no clear next step).",
        )
    with top_cols[2]:
        avg_market_friction = 0.0
        if "call_type" in df.columns and "market" in df.columns:
            followups = df["call_type"].isin(["intro_followup", "sales_followup"]).sum()
            primaries = df["call_type"].isin(["intro_call", "sales_call"]).sum()
            avg_market_friction = (followups / primaries) if primaries > 0 else 0.0
        st.metric(
            "Total Market Friction",
            f"{avg_market_friction:.2f}",
            help="Follow-up load: Flups / Primary Calls, averaged by market.",
        )

    st.markdown("---")

    st.markdown("<div id='total-friction'></div>", unsafe_allow_html=True)
    st.subheader("Total Friction")
    render_hint("Friction Index = Flups / Primary Calls. Higher values mean more follow-ups per processed lead.")

    def _build_where(date_range, selected_markets, selected_pipelines, date_col="call_date", market_col="market", pipeline_col="pipeline_name"):
        clauses = []
        params = []
        if len(date_range) == 2:
            clauses.append(f"{date_col} BETWEEN %s AND %s")
            params.extend([date_range[0], date_range[1]])
        if selected_markets:
            clauses.append(f"{market_col} = ANY(%s)")
            params.append(selected_markets)
        if selected_pipelines:
            clauses.append(f"{pipeline_col} = ANY(%s)")
            params.append(selected_pipelines)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, tuple(params)

    where_sql, where_params = _build_where(date_range, selected_markets, selected_pipelines)
    fr_sql = query_postgres(
        f"""
        WITH base AS (
          SELECT *
          FROM v_ceo_total_friction
          {where_sql}
        )
        SELECT
          market,
          'Intro Friction' AS type,
          SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END)::int AS primaries,
          SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::int AS followups,
          SUM(CASE WHEN call_type IN ('intro_call','intro_followup') THEN 1 ELSE 0 END)::int AS calls_in_calc,
          ROUND(
            (SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END))::numeric
            / NULLIF(SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END), 0),
            2
          ) AS friction_index
        FROM base
        GROUP BY market
        UNION ALL
        SELECT
          market,
          'Sales Friction' AS type,
          SUM(CASE WHEN call_type = 'sales_call' THEN 1 ELSE 0 END)::int AS primaries,
          SUM(CASE WHEN call_type = 'sales_followup' THEN 1 ELSE 0 END)::int AS followups,
          SUM(CASE WHEN call_type IN ('sales_call','sales_followup') THEN 1 ELSE 0 END)::int AS calls_in_calc,
          ROUND(
            (SUM(CASE WHEN call_type = 'sales_followup' THEN 1 ELSE 0 END))::numeric
            / NULLIF(SUM(CASE WHEN call_type = 'sales_call' THEN 1 ELSE 0 END), 0),
            2
          ) AS friction_index
        FROM base
        GROUP BY market
        """,
        where_params,
    )

    if fr_sql.empty:
        if "call_type" in df.columns and "market" in df.columns:
            fr_fallback = []
            for m, g in df.groupby("market", dropna=False):
                intro_p = int(g["call_type"].eq("intro_call").sum())
                intro_f = int(g["call_type"].eq("intro_followup").sum())
                sales_p = int(g["call_type"].eq("sales_call").sum())
                sales_f = int(g["call_type"].eq("sales_followup").sum())
                fr_fallback.append(
                    {"market": m, "type": "Intro Friction", "primaries": intro_p, "followups": intro_f, "calls_in_calc": intro_p + intro_f,
                     "friction_index": round((intro_f / intro_p) if intro_p > 0 else 0.0, 2)}
                )
                fr_fallback.append(
                    {"market": m, "type": "Sales Friction", "primaries": sales_p, "followups": sales_f, "calls_in_calc": sales_p + sales_f,
                     "friction_index": round((sales_f / sales_p) if sales_p > 0 else 0.0, 2)}
                )
            fr_sql = pd.DataFrame(fr_fallback)

    fig_fr = px.bar(
        fr_sql,
        x="market",
        y="friction_index",
        color="type",
        barmode="group",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        custom_data=["primaries", "followups", "calls_in_calc"],
        labels={"friction_index": "Friction Index (Flup / Primary)", "market": "Market"},
    )
    fig_fr.update_traces(
        hovertemplate=(
            "Market: %{x}<br>"
            "Type: %{fullData.name}<br>"
            "Friction Index: %{y:.2f}<br>"
            "Primaries: %{customdata[0]}<br>"
            "Flups: %{customdata[1]}<br>"
            "Calls in Calc: %{customdata[2]}<extra></extra>"
        )
    )
    st.plotly_chart(fig_fr, use_container_width=True)

    st.markdown("<div id='vague-index-by-market'></div>", unsafe_allow_html=True)
    st.subheader("Vague Index by Market")
    render_hint("Vague is the only negative outcome. Everything else is treated as Defined Next Step.")
    vi = df.groupby(["market", "outcome_category"]).size().reset_index(name="count")
    vi = vi[vi["outcome_category"].isin(["Defined Next Step", "Vague"])].copy()
    fig_vi = px.bar(
        vi,
        x="market",
        y="count",
        color="outcome_category",
        barmode="relative",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        color_discrete_map={"Defined Next Step": "#7d3cff", "Vague": "#e74c3c"},
    )
    fig_vi.update_layout(barnorm="percent", yaxis_title="Share (%)", xaxis_title="Market", legend_title="")
    st.plotly_chart(fig_vi, use_container_width=True)

    st.markdown("---")

    if "lead_id" in df.columns:
        lead_key = "lead_id"
    elif "deal_id" in df.columns:
        lead_key = "deal_id"
    else:
        lead_key = None

    st.markdown("<div id='one-call-close-rate-by-pipeline'></div>", unsafe_allow_html=True)
    st.subheader("One-Call-Close Rate by Pipeline")
    render_hint("Leads with exactly 1 Intro Call and 1 Sales Call, and no Flups.")
    if lead_key is None or "pipeline_name" not in df.columns or "call_type" not in df.columns:
        st.warning("Not enough data for One-Call-Close Rate (need lead_id, pipeline_name, call_type).")
    else:
        lead_counts = (
            df.groupby([lead_key, "pipeline_name"], dropna=False)["call_type"]
            .value_counts()
            .unstack(fill_value=0)
            .reset_index()
        )
        for col in ["intro_call", "sales_call", "intro_followup", "sales_followup"]:
            if col not in lead_counts.columns:
                lead_counts[col] = 0
        lead_counts["is_occ"] = (
            (lead_counts["intro_call"] == 1)
            & (lead_counts["sales_call"] == 1)
            & (lead_counts["intro_followup"] == 0)
            & (lead_counts["sales_followup"] == 0)
        )
        occ_by_pipe = lead_counts.groupby("pipeline_name")["is_occ"].sum().reset_index(name="occ_leads")
        total_leads_by_pipe = df.groupby("pipeline_name")[lead_key].nunique().reset_index(name="total_leads")
        occ = occ_by_pipe.merge(total_leads_by_pipe, on="pipeline_name", how="left").fillna(0)
        occ["occ_rate_pct"] = (occ["occ_leads"] / occ["total_leads"].replace(0, pd.NA) * 100).fillna(0).round(2)
        fig_occ = px.bar(
            occ.sort_values("occ_rate_pct", ascending=False),
            x="pipeline_name",
            y="occ_rate_pct",
            template=_plotly_template(),
            pattern_shape_sequence=[""],
            hover_data=["occ_leads", "total_leads"],
            labels={"pipeline_name": "Pipeline", "occ_rate_pct": "OCC Rate (%)"},
        )
        st.plotly_chart(fig_occ, use_container_width=True)

    st.markdown("<div id='talk-time-per-lead-by-pipeline'></div>", unsafe_allow_html=True)
    st.subheader("Talk Time per Lead by Pipeline")
    render_hint("100% split of total pipeline minutes by call type. Hover shows averages, leads, calls, and minutes.")

    where_tt, params_tt = _build_where(date_range, selected_markets, selected_pipelines)
    tt_sql = query_postgres(
        f"""
        WITH base AS (
          SELECT *
          FROM v_ceo_talk_time_per_lead_by_pipeline
          {where_tt}
          AND minutes IS NOT NULL
          AND lead_id IS NOT NULL
          AND lead_id <> ''
        ),
        leads AS (
          SELECT pipeline_name, COUNT(DISTINCT lead_id)::int AS leads_total
          FROM base
          GROUP BY pipeline_name
        ),
        agg AS (
          SELECT
            pipeline_name,
            call_type_group,
            COUNT(*)::int AS calls_type,
            SUM(minutes)::float8 AS total_minutes_type
          FROM base
          GROUP BY pipeline_name, call_type_group
        ),
        totals AS (
          SELECT pipeline_name, SUM(total_minutes_type)::float8 AS total_minutes_pipeline
          FROM agg
          GROUP BY pipeline_name
        )
        SELECT
          a.pipeline_name,
          a.call_type_group,
          l.leads_total,
          a.calls_type,
          a.total_minutes_type,
          t.total_minutes_pipeline,
          ROUND((a.total_minutes_type / NULLIF(a.calls_type, 0))::numeric, 2) AS avg_minutes_per_call_type,
          ROUND((a.total_minutes_type / NULLIF(l.leads_total, 0))::numeric, 2) AS avg_minutes_per_lead_type,
          ROUND((a.total_minutes_type / NULLIF(t.total_minutes_pipeline, 0) * 100)::numeric, 2) AS share_pct
        FROM agg a
        JOIN leads l ON l.pipeline_name = a.pipeline_name
        JOIN totals t ON t.pipeline_name = a.pipeline_name
        ORDER BY a.pipeline_name, a.call_type_group
        """,
        params_tt,
    )

    if tt_sql.empty:
        if lead_key is None or "pipeline_name" not in df.columns or "call_type" not in df.columns or "call_duration_sec" not in df.columns:
            st.warning("Not enough data for pipeline time charts.")
            return

        df["minutes"] = df["call_duration_sec"] / 60.0
        type_map = {
            "intro_call": "Intro Call",
            "intro_followup": "Intro Flup",
            "sales_call": "Sales Call",
            "sales_followup": "Sales Flup",
        }
        df["call_type_group"] = df["call_type"].map(type_map).fillna("Other")
        base = df[df["call_type"].isin(list(type_map.keys())) & df[lead_key].notna() & (df[lead_key].astype(str) != "")]
        leads_total = base.groupby("pipeline_name")[lead_key].nunique().reset_index(name="leads_total")
        agg = (
            base.groupby(["pipeline_name", "call_type_group"], dropna=False)
            .agg(total_minutes_type=("minutes", "sum"), calls_type=("call_id", "count"))
            .reset_index()
        )
        totals = agg.groupby("pipeline_name")["total_minutes_type"].sum().reset_index(name="total_minutes_pipeline")
        tt_sql = agg.merge(leads_total, on="pipeline_name", how="left").merge(totals, on="pipeline_name", how="left")
        tt_sql["avg_minutes_per_call_type"] = (tt_sql["total_minutes_type"] / tt_sql["calls_type"].replace(0, pd.NA)).fillna(0).round(2)
        tt_sql["avg_minutes_per_lead_type"] = (tt_sql["total_minutes_type"] / tt_sql["leads_total"].replace(0, pd.NA)).fillna(0).round(2)
        tt_sql["share_pct"] = (tt_sql["total_minutes_type"] / tt_sql["total_minutes_pipeline"].replace(0, pd.NA) * 100).fillna(0).round(2)

    fig_share = px.bar(
        tt_sql,
        x="pipeline_name",
        y="share_pct",
        color="call_type_group",
        barmode="relative",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        custom_data=[
            "leads_total",
            "calls_type",
            "total_minutes_type",
            "avg_minutes_per_call_type",
            "avg_minutes_per_lead_type",
            "total_minutes_pipeline",
        ],
        labels={"pipeline_name": "Pipeline", "share_pct": "Share (%)"},
    )
    fig_share.update_layout(yaxis_title="Share (%)", xaxis_title="Pipeline", legend_title="")
    fig_share.update_traces(
        hovertemplate=(
            "Pipeline: %{x}<br>"
            "Type: %{fullData.name}<br>"
            "Share of Minutes: %{y:.2f}%<br>"
            "Avg Minutes/Call: %{customdata[3]:.2f}<br>"
            "Avg Minutes/Lead: %{customdata[4]:.2f}<br>"
            "Leads: %{customdata[0]}<br>"
            "Calls (type): %{customdata[1]}<br>"
            "Minutes (type): %{customdata[2]:.1f}<br>"
            "Total Minutes (pipeline): %{customdata[5]:.1f}<extra></extra>"
        )
    )
    st.plotly_chart(fig_share, use_container_width=True)

    st.markdown("<div id='total-talk-time-by-pipeline'></div>", unsafe_allow_html=True)
    st.subheader("Total Talk Time by Pipeline")
    render_hint("100% split of total pipeline minutes by call type. Hover shows leads, calls, and minutes.")
    fig_tot = px.bar(
        tt_sql,
        x="pipeline_name",
        y="share_pct",
        color="call_type_group",
        barmode="relative",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        custom_data=["leads_total", "calls_type", "total_minutes_type", "total_minutes_pipeline"],
        labels={"pipeline_name": "Pipeline", "share_pct": "Share (%)"},
    )
    fig_tot.update_layout(yaxis_title="Share (%)", xaxis_title="Pipeline", legend_title="")
    fig_tot.update_traces(
        hovertemplate=(
            "Pipeline: %{x}<br>"
            "Type: %{fullData.name}<br>"
            "Share of Minutes: %{y:.2f}%<br>"
            "Leads: %{customdata[0]}<br>"
            "Calls (type): %{customdata[1]}<br>"
            "Minutes (type): %{customdata[2]:.1f}<br>"
            "Total Minutes (pipeline): %{customdata[3]:.1f}<extra></extra>"
        )
    )
    st.plotly_chart(fig_tot, use_container_width=True)
