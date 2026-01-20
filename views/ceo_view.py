import streamlit as st
import pandas as pd
import plotly.express as px
from database import rpc_df
from views.shared_ui import render_hint


def _plotly_template():
    return "plotly_dark" if st.session_state.get("ui_theme_v1", "dark") == "dark" else "plotly_white"


def render_ceo_dashboard(date_range, selected_markets, selected_pipelines):
    st.markdown("<h1 style='text-align:center;'>Strategic Radar</h1>", unsafe_allow_html=True)
    date_start = date_range[0] if len(date_range) == 2 else None
    date_end = date_range[1] if len(date_range) == 2 else None
    rpc_params = {
        "date_start": date_start.isoformat() if date_start else None,
        "date_end": date_end.isoformat() if date_end else None,
        "markets": selected_markets or [],
        "pipelines": selected_pipelines or [],
    }

    df_kpi = rpc_df("rpc_ceo_kpis", rpc_params)
    if df_kpi.empty:
        st.warning("No data available for current filters.")
        return

    kpi = df_kpi.iloc[0].to_dict()
    top_cols = st.columns(3)
    avg_quality = kpi.get("avg_quality")
    vague_rate = float(kpi.get("vague_rate_pct") or 0.0)
    avg_market_friction = float(kpi.get("avg_market_friction") or 0.0)

    with top_cols[0]:
        st.metric(
            "Average Quality Score",
            "—" if avg_quality in (None, "", "nan") else f"{float(avg_quality):.2f}",
            help="Overall compliance with company standards.",
        )
    with top_cols[1]:
        st.metric(
            "Vague Index (Global)",
            f"{vague_rate:.1f}%",
            help="Share of calls with a vague outcome (no clear next step).",
        )
    with top_cols[2]:
        st.metric(
            "Total Market Friction",
            f"{avg_market_friction:.2f}",
            help="Follow-up load: Flups / Primary Calls, averaged by market.",
        )

    st.markdown("---")

    st.markdown("<div id='total-friction'></div>", unsafe_allow_html=True)
    st.subheader("Total Friction")
    render_hint("Friction Index = Flups / Primary Calls. Higher values mean more follow-ups per processed lead.")

    fr_sql = rpc_df("rpc_ceo_total_friction", rpc_params)
    if fr_sql.empty:
        st.warning("No data available for Total Friction for current filters.")
        return

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
    vi = rpc_df("rpc_ceo_vague_index_by_market", rpc_params)
    vi = vi[vi["outcome_category"].isin(["Defined Next Step", "Vague"])].copy() if not vi.empty else vi
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

    st.markdown("<div id='one-call-close-rate-by-pipeline'></div>", unsafe_allow_html=True)
    st.subheader("One-Call-Close Rate by Pipeline")
    render_hint("Leads with exactly 1 Intro Call and 1 Sales Call, and no Flups.")
    occ = rpc_df("rpc_ceo_one_call_close_rate_by_pipeline", rpc_params)
    if occ.empty:
        st.warning("No data available for One-Call-Close Rate for current filters.")
    else:
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
    render_hint("100% split of total pipeline calls by call type. Hover shows averages, leads, calls, and minutes.")

    tt_sql = rpc_df("rpc_ceo_talk_time_per_lead_by_pipeline", rpc_params)
    if tt_sql.empty:
        st.warning("No data available for Talk Time chart for current filters.")
        return

    calls_total = tt_sql.groupby("pipeline_name", dropna=False)["calls_type"].sum().reset_index(name="calls_total_pipeline")
    tt_sql = tt_sql.merge(calls_total, on="pipeline_name", how="left")
    tt_sql["share_calls_pct"] = (
        tt_sql["calls_type"] / tt_sql["calls_total_pipeline"].replace(0, pd.NA) * 100
    ).fillna(0.0)

    fig_share = px.bar(
        tt_sql,
        x="pipeline_name",
        y="share_calls_pct",
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
        labels={"pipeline_name": "Pipeline", "share_calls_pct": "Share (%)"},
    )
    fig_share.update_layout(yaxis_title="Share (%)", xaxis_title="Pipeline", legend_title="")
    fig_share.update_traces(
        hovertemplate=(
            "Pipeline: %{x}<br>"
            "Type: %{fullData.name}<br>"
            "Share of Calls: %{y:.2f}%<br>"
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
    render_hint("100% split of total pipeline calls by call type. Hover shows leads, calls, and minutes.")
    fig_tot = px.bar(
        tt_sql,
        x="pipeline_name",
        y="share_calls_pct",
        color="call_type_group",
        barmode="relative",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        custom_data=["leads_total", "calls_type", "total_minutes_type", "total_minutes_pipeline"],
        labels={"pipeline_name": "Pipeline", "share_calls_pct": "Share (%)"},
    )
    fig_tot.update_layout(yaxis_title="Share (%)", xaxis_title="Pipeline", legend_title="")
    fig_tot.update_traces(
        hovertemplate=(
            "Pipeline: %{x}<br>"
            "Type: %{fullData.name}<br>"
            "Share of Calls: %{y:.2f}%<br>"
            "Leads: %{customdata[0]}<br>"
            "Calls (type): %{customdata[1]}<br>"
            "Minutes (type): %{customdata[2]:.1f}<br>"
            "Total Minutes (pipeline): %{customdata[3]:.1f}<extra></extra>"
        )
    )
    st.plotly_chart(fig_tot, use_container_width=True)
