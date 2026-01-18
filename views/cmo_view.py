import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import fetch_view_data, query_postgres
from views.shared_ui import render_data_health_volume, render_hint


def _plotly_template():
    return "plotly_dark" if st.session_state.get("ui_theme_v1", "dark") == "dark" else "plotly_white"


def render_cmo_analytics(date_range, selected_markets, selected_pipelines):
    st.title("CMO Traffic Quality & Viscosity")

    with st.spinner("Loading traffic data..."):
        df_raw = fetch_view_data("Algonova_Calls_Raw")

    if df_raw.empty:
        st.warning("No data available.")
        return

    total_raw_rows = int(df_raw.attrs.get("supabase_rows_loaded", len(df_raw)))

    df = df_raw.copy()
    if "call_datetime" in df.columns:
        df["call_datetime"] = pd.to_datetime(df["call_datetime"], errors="coerce", utc=True)
    else:
        df["call_datetime"] = pd.NaT

    df["call_date"] = df["call_datetime"].dt.date

    if "Average_quality" in df.columns:
        df["Average_quality"] = pd.to_numeric(df["Average_quality"], errors="coerce")

    mask = pd.Series([True] * len(df))
    if len(date_range) == 2:
        mask = mask & (df["call_date"] >= date_range[0]) & (df["call_date"] <= date_range[1])
    if selected_markets:
        mask = mask & df["market"].isin(selected_markets)
    if selected_pipelines:
        mask = mask & df["pipeline_name"].isin(selected_pipelines)

    df = df[mask].copy()

    if df.empty:
        st.warning("No data matches current filters.")
        return

    dates = df["call_date"].dropna() if "call_date" in df.columns else []
    date_range_in_result = None
    if hasattr(dates, "__len__") and len(dates) > 0:
        date_range_in_result = (dates.min(), dates.max())
    render_data_health_volume(total_raw_rows, len(df), date_range_in_result=date_range_in_result, expanded=False)

    if "mkt_manager" not in df.columns:
        st.warning("Missing column: mkt_manager")
        return

    df["mkt_market"] = df.get("mkt_market", df.get("market", "Unknown"))

    total_calls = df.groupby("mkt_manager").size().reset_index(name="total_calls")
    total_leads = df.groupby("mkt_manager")["lead_id"].nunique().reset_index(name="total_leads")

    intro_prim = df[df["call_type"] == "intro_call"].groupby("mkt_manager").size().reset_index(name="intro_primaries")
    intro_fu = df[df["call_type"] == "intro_followup"].groupby("mkt_manager").size().reset_index(name="intro_followups")

    merged = total_calls.merge(total_leads, on="mkt_manager", how="left")
    merged = merged.merge(intro_prim, on="mkt_manager", how="left")
    merged = merged.merge(intro_fu, on="mkt_manager", how="left")
    merged = merged.fillna(0)

    merged["viscosity_index"] = (merged["total_calls"] / merged["total_leads"].replace(0, pd.NA)).astype(float)
    merged["intro_friction_index"] = (merged["intro_followups"] / merged["intro_primaries"].replace(0, pd.NA)).astype(float)

    merged["viscosity_index"] = merged["viscosity_index"].fillna(0).round(2)
    merged["intro_friction_index"] = merged["intro_friction_index"].fillna(0).round(2)

    st.subheader("Traffic Viscosity vs Intro Friction")
    render_hint(
        "Viscosity means how many calls are required to process one lead (Calls / Leads). "
        "Higher viscosity usually indicates wasted touches, poor lead quality, or weak routing."
    )
    def _build_where(
        date_range,
        selected_markets,
        selected_pipelines,
        date_col="call_date",
        market_col="market",
        pipeline_col="pipeline_name",
    ):
        clauses = [f"{date_col} IS NOT NULL"]
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
        return f"WHERE {' AND '.join(clauses)}", tuple(params)

    where_sql, params = _build_where(date_range, selected_markets, selected_pipelines)
    merged_sql = query_postgres(
        f"""
        WITH base AS (
          SELECT *
          FROM v_cmo_traffic_viscosity_vs_intro_friction
          {where_sql}
        )
        SELECT
          mkt_manager,
          COUNT(*)::int AS total_calls,
          COUNT(DISTINCT lead_id)::int AS total_leads,
          SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END)::int AS intro_primaries,
          SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::int AS intro_followups,
          ROUND((COUNT(*)::numeric / NULLIF(COUNT(DISTINCT lead_id), 0))::numeric, 2) AS viscosity_index,
          ROUND(
            (SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::numeric)
            / NULLIF(SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END), 0),
            2
          ) AS intro_friction_index
        FROM base
        GROUP BY mkt_manager
        """,
        params,
    )
    merged_for_chart = merged_sql if not merged_sql.empty else merged

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
        labels={"mkt_manager": "Traffic Manager", "value": "Index"},
        hover_data=["total_calls", "total_leads", "intro_primaries", "intro_followups"],
    )
    fig_bar.update_layout(xaxis_title="Traffic Manager", margin=dict(l=10, r=10, t=10, b=80))
    fig_bar.update_xaxes(tickangle=-35, automargin=True)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Intro Friction / Traffic Manager")
    render_hint("Intro Friction shows follow-up load on intro calls (Intro Flups / Intro Calls).")
    where_hm, params_hm = _build_where(
        date_range,
        selected_markets,
        selected_pipelines,
        market_col="mkt_market",
        pipeline_col="pipeline_name",
    )
    by_mm_sql = query_postgres(
        f"""
        WITH base AS (
          SELECT *
          FROM v_cmo_intro_friction_traffic_manager_market_pipeline
          {where_hm}
          AND mkt_market IS NOT NULL
          AND mkt_manager IS NOT NULL
        )
        SELECT
          mkt_market,
          mkt_manager,
          SUM(intro_calls)::int AS intro_calls,
          SUM(intro_flups)::int AS intro_flups,
          ROUND(
            (SUM(intro_flups)::numeric) / NULLIF(SUM(intro_calls), 0),
            2
          ) AS intro_friction_index,
          (SUM(intro_calls) + SUM(intro_flups))::int AS calls_in_calc
        FROM base
        GROUP BY mkt_market, mkt_manager
        """,
        params_hm,
    )

    if not by_mm_sql.empty:
        by_mm = by_mm_sql
    else:
        intro_calls = (
            df[df["call_type"] == "intro_call"]
            .groupby(["mkt_market", "mkt_manager"], dropna=False)
            .size()
            .reset_index(name="intro_calls")
        )
        intro_flups = (
            df[df["call_type"] == "intro_followup"]
            .groupby(["mkt_market", "mkt_manager"], dropna=False)
            .size()
            .reset_index(name="intro_flups")
        )
        by_mm = intro_calls.merge(intro_flups, on=["mkt_market", "mkt_manager"], how="outer").fillna(0)
        by_mm["intro_friction_index"] = (
            by_mm["intro_flups"] / by_mm["intro_calls"].replace(0, pd.NA)
        ).fillna(0).round(2)
        by_mm["calls_in_calc"] = (by_mm["intro_calls"] + by_mm["intro_flups"]).astype(int)

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
