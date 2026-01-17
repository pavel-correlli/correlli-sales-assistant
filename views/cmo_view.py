import streamlit as st
import pandas as pd
import plotly.express as px
from database import fetch_view_data, query_postgres

def render_cmo_analytics(date_range, selected_markets, selected_pipelines):
    st.title("📈 CMO Traffic Quality & Viscosity")

    with st.spinner("Loading traffic data..."):
        df = fetch_view_data("Algonova_Calls_Raw")

    if df.empty:
        st.warning("No data available.")
        return

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
    st.caption(
        "❓ Viscosity means how many calls are required to process one lead (Calls / Leads). "
        "Higher viscosity usually indicates wasted touches, poor lead quality, or weak routing. "
        "Intro Friction shows follow-up load on intro calls (Intro Flups / Intro Calls)."
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
        template="plotly_white",
        labels={"mkt_manager": "mkt_manager", "value": "Index"},
        hover_data=["total_calls", "total_leads", "intro_primaries", "intro_followups"],
    )
    fig_bar.update_layout(xaxis_title="Traffic Manager")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Intro friction vs Traffic manager")
    where_hm, params_hm = _build_where(date_range, selected_markets, selected_pipelines, market_col="mkt_market")
    by_mm_sql = query_postgres(
        f"""
        WITH base AS (
          SELECT *
          FROM v_cmo_intro_friction_vs_traffic_manager
          {where_hm}
          AND mkt_market IS NOT NULL
          AND mkt_manager IS NOT NULL
        )
        SELECT
          mkt_market,
          mkt_manager,
          SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END)::int AS intro_calls,
          SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::int AS intro_flups,
          ROUND(
            (SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::numeric)
            / NULLIF(SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END), 0),
            2
          ) AS intro_friction_index
        FROM base
        GROUP BY mkt_market, mkt_manager
        """,
        params_hm,
    )
    by_mm = by_mm_sql if not by_mm_sql.empty else df.groupby(["mkt_market", "mkt_manager"]).apply(
        lambda g: (g["call_type"].eq("intro_followup").sum()) / max(int(g["call_type"].eq("intro_call").sum()), 1)
    ).reset_index(name="intro_friction_index")

    pivot = by_mm.pivot(index="mkt_market", columns="mkt_manager", values="intro_friction_index").fillna(0)
    fig_hm = px.imshow(
        pivot,
        aspect="auto",
        color_continuous_scale="Reds",
        labels={"x": "Traffic Manager", "y": "Market", "color": "Intro Friction"},
    )
    st.plotly_chart(fig_hm, use_container_width=True)
