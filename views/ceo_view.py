import streamlit as st
import pandas as pd
import plotly.express as px
from database import fetch_view_data, normalize_calls_df, add_outcome_category, compute_friction_index


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
    st.title("🧭 CEO Strategic Radar")

    with st.spinner("Loading executive view..."):
        df = fetch_view_data("Algonova_Calls_Raw")

    df = normalize_calls_df(df)
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
        fr_all = compute_friction_index(
            df,
            group_cols=["market"],
            primary_types=["intro_call", "sales_call"],
            followup_types=["intro_followup", "sales_followup"],
        )
        avg_market_friction = float(fr_all["friction_index"].mean()) if not fr_all.empty else 0.0
        st.metric(
            "Total Market Friction",
            f"{avg_market_friction:.2f}",
            help="Follow-up load: Flups / Primary Calls, averaged by market.",
        )

    st.markdown("---")

    st.subheader("Total Market Friction by Market")
    st.caption("❓ Friction Index = Flups / Primary Calls. Higher values mean more follow-ups per processed lead.")

    fr_intro = compute_friction_index(
        df,
        group_cols=["market"],
        primary_types=["intro_call"],
        followup_types=["intro_followup"],
    ).rename(columns={"friction_index": "intro_friction"})
    fr_sales = compute_friction_index(
        df,
        group_cols=["market"],
        primary_types=["sales_call"],
        followup_types=["sales_followup"],
    ).rename(columns={"friction_index": "sales_friction"})
    fr_m = fr_intro.merge(fr_sales[["market", "sales_friction"]], on="market", how="outer").fillna(0)
    fr_long = fr_m.melt(id_vars=["market"], value_vars=["intro_friction", "sales_friction"], var_name="type", value_name="value")
    fr_long["type"] = fr_long["type"].map({"intro_friction": "Intro Friction", "sales_friction": "Sales Friction"})
    fig_fr = px.bar(
        fr_long,
        x="market",
        y="value",
        color="type",
        barmode="group",
        template="plotly_white",
        labels={"value": "Friction Index (Flup / Primary)", "market": "Market"},
    )
    st.plotly_chart(fig_fr, use_container_width=True)

    st.subheader("Vague Index by Market")
    st.caption("❓ Vague is the only negative outcome. Everything else is treated as Defined Next Step.")
    vi = df.groupby(["market", "outcome_category"]).size().reset_index(name="count")
    vi = vi[vi["outcome_category"].isin(["Defined Next Step", "Vague"])].copy()
    fig_vi = px.bar(
        vi,
        x="market",
        y="count",
        color="outcome_category",
        barmode="relative",
        template="plotly_white",
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

    st.subheader("One-Call-Close Rate by Pipeline")
    st.caption("❓ Leads with exactly 1 Intro Call and 1 Sales Call, and no Flups.")
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
            template="plotly_white",
            hover_data=["occ_leads", "total_leads"],
            labels={"pipeline_name": "Pipeline", "occ_rate_pct": "OCC Rate (%)"},
        )
        st.plotly_chart(fig_occ, use_container_width=True)

    st.subheader("Talk Time per Lead by Pipeline")
    st.caption("❓ 100% split by call type. Hover shows leads, calls, and minutes.")
    if lead_key is None or "pipeline_name" not in df.columns or "call_type" not in df.columns or "call_duration_sec" not in df.columns:
        st.warning("Not enough data for pipeline time charts (need lead_id, pipeline_name, call_type, call_duration_sec).")
        return

    df["minutes"] = df["call_duration_sec"] / 60.0
    type_map = {
        "intro_call": "Intro Call",
        "intro_followup": "Intro Flup",
        "sales_call": "Sales Call",
        "sales_followup": "Sales Flup",
    }
    df["call_type_group"] = df["call_type"].map(type_map).fillna("Other")

    pipe_type = (
        df[df["call_type"].isin(list(type_map.keys()))]
        .groupby(["pipeline_name", "call_type_group"], dropna=False)
        .agg(
            total_minutes=("minutes", "sum"),
            calls=("call_id", "count"),
            leads=(lead_key, "nunique"),
        )
        .reset_index()
    )
    pipe_totals = (
        pipe_type.groupby("pipeline_name")
        .agg(
            total_minutes_all=("total_minutes", "sum"),
            calls_all=("calls", "sum"),
            leads_all=("leads", "max"),
        )
        .reset_index()
    )
    pipe_type = pipe_type.merge(pipe_totals, on="pipeline_name", how="left")
    pipe_type["avg_min_per_lead"] = (pipe_type["total_minutes"] / pipe_type["leads"].replace(0, pd.NA)).fillna(0)
    pipe_type["avg_min_per_lead_all"] = (pipe_type["total_minutes_all"] / pipe_type["leads_all"].replace(0, pd.NA)).fillna(0)

    fig_avg = px.bar(
        pipe_type,
        x="pipeline_name",
        y="avg_min_per_lead",
        color="call_type_group",
        barmode="relative",
        template="plotly_white",
        custom_data=["leads_all", "calls_all", "total_minutes_all", "avg_min_per_lead_all"],
        labels={"pipeline_name": "Pipeline", "avg_min_per_lead": "Avg Minutes per Lead"},
    )
    fig_avg.update_layout(barnorm="percent", yaxis_title="Share (%)", xaxis_title="Pipeline", legend_title="")
    fig_avg.update_traces(
        hovertemplate=(
            "Pipeline: %{x}<br>"
            "Type: %{fullData.name}<br>"
            "Avg Minutes/Lead (type): %{y:.2f}<br>"
            "Leads: %{customdata[0]}<br>"
            "Calls: %{customdata[1]}<br>"
            "Total Minutes: %{customdata[2]:.1f}<br>"
            "Avg Minutes/Lead (total): %{customdata[3]:.2f}<extra></extra>"
        )
    )
    st.plotly_chart(fig_avg, use_container_width=True)

    st.subheader("Total Talk Time by Pipeline")
    fig_tot = px.bar(
        pipe_type,
        x="pipeline_name",
        y="total_minutes",
        color="call_type_group",
        barmode="relative",
        template="plotly_white",
        custom_data=["leads_all", "calls_all", "total_minutes_all"],
        labels={"pipeline_name": "Pipeline", "total_minutes": "Total Minutes"},
    )
    fig_tot.update_layout(barnorm="percent", yaxis_title="Share (%)", xaxis_title="Pipeline", legend_title="")
    fig_tot.update_traces(
        hovertemplate=(
            "Pipeline: %{x}<br>"
            "Type: %{fullData.name}<br>"
            "Minutes (type): %{y:.1f}<br>"
            "Leads: %{customdata[0]}<br>"
            "Calls: %{customdata[1]}<br>"
            "Total Minutes: %{customdata[2]:.1f}<extra></extra>"
        )
    )
    st.plotly_chart(fig_tot, use_container_width=True)
