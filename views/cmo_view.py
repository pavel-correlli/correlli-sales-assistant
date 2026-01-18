import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import fetch_view_data
from views.shared_ui import render_hint


def _plotly_template():
    return "plotly_dark" if st.session_state.get("ui_theme_v1", "dark") == "dark" else "plotly_white"


def render_cmo_analytics(date_range, selected_markets, selected_pipelines):
    st.markdown("<h1 style='text-align:center;'>Traffic Quality & Viscosity</h1>", unsafe_allow_html=True)

    st.markdown("<div id='traffic-viscosity-vs-intro-friction'></div>", unsafe_allow_html=True)
    st.subheader("Traffic Viscosity vs Intro Friction")
    render_hint(
        "Viscosity means how many calls are required to process one lead (Calls / Leads). "
        "Higher viscosity usually indicates wasted touches, poor lead quality, or weak routing."
    )
    with st.spinner("Loading CMO chart view..."):
        df_view = fetch_view_data("v_cmo_traffic_viscosity_vs_intro_friction")

    if df_view.empty:
        st.warning("No data available from SQL view (v_cmo_traffic_viscosity_vs_intro_friction).")
        return

    df = df_view.copy()
    if "call_date" in df.columns:
        df["call_date"] = pd.to_datetime(df["call_date"], errors="coerce").dt.date
    elif "call_datetime" in df.columns:
        df["call_datetime"] = pd.to_datetime(df["call_datetime"], errors="coerce", utc=True)
        df["call_date"] = df["call_datetime"].dt.date
    else:
        df["call_date"] = pd.NaT

    def _determine_market(pipeline):
        p = str(pipeline or "").upper()
        if p.startswith("CZ"):
            return "CZ"
        if p.startswith("SK"):
            return "SK"
        if p.startswith("RUK"):
            return "RUK"
        return "Others"

    df["computed_market"] = df["pipeline_name"].apply(_determine_market) if "pipeline_name" in df.columns else "Others"
    df["market"] = df.get("market", "")
    df["market"] = df["market"].astype(str)
    df["mkt_market"] = df["market"].where(df["market"].str.strip() != "", df["computed_market"])

    mask = pd.Series([True] * len(df))
    if len(date_range) == 2 and "call_date" in df.columns:
        mask = mask & (df["call_date"] >= date_range[0]) & (df["call_date"] <= date_range[1])
    if selected_markets:
        mask = mask & df["mkt_market"].isin(selected_markets)
    if selected_pipelines and "pipeline_name" in df.columns:
        mask = mask & df["pipeline_name"].isin(selected_pipelines)
    if "mkt_manager" in df.columns:
        mask = mask & df["mkt_manager"].notna() & (df["mkt_manager"].astype(str).str.strip() != "")

    df = df[mask].copy()
    if df.empty:
        st.warning("No data matches current filters in SQL view.")
        return

    total_calls = df.groupby("mkt_manager").size().rename("total_calls")
    if "lead_id" in df.columns:
        total_leads = df.groupby("mkt_manager")["lead_id"].nunique(dropna=True).rename("total_leads")
    else:
        total_leads = (total_calls * 0).rename("total_leads")
    intro_primaries = df["call_type"].eq("intro_call").groupby(df["mkt_manager"]).sum().rename("intro_primaries")
    intro_followups = df["call_type"].eq("intro_followup").groupby(df["mkt_manager"]).sum().rename("intro_followups")

    merged_for_chart = (
        pd.concat([total_calls, total_leads, intro_primaries, intro_followups], axis=1)
        .reset_index()
        .rename(columns={"index": "mkt_manager"})
    )
    merged_for_chart["viscosity_index"] = pd.to_numeric(
        merged_for_chart["total_calls"] / merged_for_chart["total_leads"].replace(0, pd.NA),
        errors="coerce",
    ).fillna(0).round(2)
    merged_for_chart["intro_friction_index"] = pd.to_numeric(
        merged_for_chart["intro_followups"] / merged_for_chart["intro_primaries"].replace(0, pd.NA),
        errors="coerce",
    ).fillna(0).round(2)

    long_df = merged_for_chart.melt(
        id_vars=["mkt_manager", "total_calls", "total_leads", "intro_primaries", "intro_followups"],
        value_vars=["viscosity_index", "intro_friction_index"],
        var_name="metric",
        value_name="value",
    )
    long_df["metric"] = long_df["metric"].map(
        {"viscosity_index": "Viscosity Index", "intro_friction_index": "Intro Friction Index"}
    )

    fig_bar = px.bar(
        long_df,
        x="mkt_manager",
        y="value",
        color="metric",
        barmode="group",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        labels={"mkt_manager": "Traffic Manager", "value": "Index"},
        hover_data=["total_calls", "total_leads", "intro_primaries", "intro_followups"],
    )
    fig_bar.update_layout(xaxis_title="Traffic Manager", margin=dict(l=10, r=10, t=10, b=80))
    fig_bar.update_xaxes(tickangle=-35, automargin=True)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("<div id='intro-friction-traffic-manager'></div>", unsafe_allow_html=True)
    st.subheader("Intro Friction / Traffic Manager")
    render_hint("Intro Friction shows follow-up load on intro calls (Intro Flups / Intro Calls).")
    with st.spinner("Loading heatmap view..."):
        by_mm = fetch_view_data("v_cmo_intro_friction_traffic_manager_market_pipeline")

    if by_mm.empty:
        st.warning("No data available from SQL view (v_cmo_intro_friction_traffic_manager_market_pipeline).")
        return

    if "call_date" in by_mm.columns:
        by_mm["call_date"] = pd.to_datetime(by_mm["call_date"], errors="coerce").dt.date

    mask_hm = pd.Series([True] * len(by_mm))
    if len(date_range) == 2 and "call_date" in by_mm.columns:
        mask_hm = mask_hm & (by_mm["call_date"] >= date_range[0]) & (by_mm["call_date"] <= date_range[1])
    if selected_markets and "mkt_market" in by_mm.columns:
        mask_hm = mask_hm & by_mm["mkt_market"].isin(selected_markets)
    if selected_pipelines and "pipeline_name" in by_mm.columns:
        mask_hm = mask_hm & by_mm["pipeline_name"].isin(selected_pipelines)

    by_mm = by_mm[mask_hm].copy()
    if by_mm.empty:
        st.warning("No heatmap data matches current filters in SQL view.")
        return

    by_mm["intro_calls"] = pd.to_numeric(by_mm.get("intro_calls"), errors="coerce").fillna(0).astype(int)
    by_mm["intro_flups"] = pd.to_numeric(by_mm.get("intro_flups"), errors="coerce").fillna(0).astype(int)
    by_mm = (
        by_mm.groupby(["mkt_market", "mkt_manager"], dropna=False)[["intro_calls", "intro_flups"]]
        .sum()
        .reset_index()
    )
    by_mm["calls_in_calc"] = (by_mm["intro_calls"] + by_mm["intro_flups"]).astype(int)
    by_mm["intro_friction_index"] = pd.to_numeric(
        by_mm["intro_flups"] / by_mm["intro_calls"].replace(0, pd.NA),
        errors="coerce",
    ).fillna(0).round(2)

    by_mm["mkt_market"] = by_mm["mkt_market"].astype(str).str.strip()
    by_mm["mkt_manager"] = by_mm["mkt_manager"].astype(str).str.strip()
    by_mm = by_mm[
        (~by_mm["mkt_market"].isin({"", "Unknown", "0", "nan", "None"}))
        & (~by_mm["mkt_manager"].isin({"", "0", "nan", "None"}))
    ].copy()
    if by_mm.empty:
        st.warning("No valid market/manager values for heatmap after cleaning.")
        return

    friction = by_mm.pivot(index="mkt_market", columns="mkt_manager", values="intro_friction_index").fillna(0)
    calls = by_mm.pivot(index="mkt_market", columns="mkt_manager", values="intro_calls").fillna(0).astype(int)
    flups = by_mm.pivot(index="mkt_market", columns="mkt_manager", values="intro_flups").fillna(0).astype(int)
    calls_in_calc = by_mm.pivot(index="mkt_market", columns="mkt_manager", values="calls_in_calc").fillna(0).astype(int)

    calls = calls.reindex(index=friction.index, columns=friction.columns, fill_value=0)
    flups = flups.reindex(index=friction.index, columns=friction.columns, fill_value=0)
    calls_in_calc = calls_in_calc.reindex(index=friction.index, columns=friction.columns, fill_value=0)

    custom = []
    for y in friction.index:
        row = []
        for x in friction.columns:
            row.append([int(calls.loc[y, x]), int(flups.loc[y, x]), int(calls_in_calc.loc[y, x])])
        custom.append(row)

    fig_hm = go.Figure(
        data=[
            go.Heatmap(
                z=friction.values,
                x=list(friction.columns),
                y=list(friction.index),
                customdata=custom,
                colorscale="Reds",
                zmin=0,
                showscale=True,
                colorbar=dict(title="Intro Friction", tickformat=".2f"),
                hovertemplate=(
                    "Market: %{y}<br>"
                    "Traffic Manager: %{x}<br>"
                    "Intro Calls: %{customdata[0]}<br>"
                    "Intro Flups: %{customdata[1]}<br>"
                    "Calls In Calc: %{customdata[2]}<br>"
                    "Intro Friction: %{z:.2f}<br>"
                    "Formula: Intro Flups / Intro Calls<extra></extra>"
                ),
            )
        ]
    )
    fig_hm.update_layout(
        template=_plotly_template(),
        margin=dict(l=10, r=10, t=10, b=90),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Traffic Manager",
        yaxis_title="Market",
        height=max(480, 28 * len(friction.index) + 220),
    )
    fig_hm.update_xaxes(tickangle=-35, automargin=True)
    fig_hm.update_yaxes(automargin=True)
    st.plotly_chart(fig_hm, use_container_width=True)
