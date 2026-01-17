import streamlit as st
import pandas as pd
import plotly.express as px
from database import fetch_view_data

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
    long_df = merged.melt(
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
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Heatmap: Market vs Manager (Intro Friction)")
    by_mm = df.groupby(["mkt_market", "mkt_manager"]).apply(
        lambda g: (
            (g["call_type"].eq("intro_followup").sum())
            / max(int(g["call_type"].eq("intro_call").sum()), 1)
        )
    ).reset_index(name="intro_friction_index")
    by_mm["intro_friction_index"] = by_mm["intro_friction_index"].round(2)

    pivot = by_mm.pivot(index="mkt_market", columns="mkt_manager", values="intro_friction_index").fillna(0)
    fig_hm = px.imshow(
        pivot,
        aspect="auto",
        color_continuous_scale="Reds",
        labels={"x": "mkt_manager", "y": "mkt_market", "color": "Intro Friction"},
    )
    st.plotly_chart(fig_hm, use_container_width=True)
