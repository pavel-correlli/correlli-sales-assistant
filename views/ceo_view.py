import streamlit as st
import pandas as pd
import plotly.express as px
from database import rpc_df
from app_i18n import call_type_label, market_label, pipeline_label, t
from views.shared_ui import render_hint


def _plotly_template():
    return "plotly_dark" if st.session_state.get("ui_theme_v1", "dark") == "dark" else "plotly_white"


def render_ceo_dashboard(date_range, selected_markets, selected_pipelines):
    st.markdown(f"<h1 style='text-align:center;'>{t('ceo.title')}</h1>", unsafe_allow_html=True)
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
        st.warning(t("ceo.no_data"))
        return

    kpi = df_kpi.iloc[0].to_dict()
    top_cols = st.columns(3)
    avg_quality = kpi.get("avg_quality")
    vague_rate = float(kpi.get("vague_rate_pct") or 0.0)
    avg_market_friction = float(kpi.get("avg_market_friction") or 0.0)

    with top_cols[0]:
        st.metric(t("ceo.avg_quality"), "-" if avg_quality in (None, "", "nan") else f"{float(avg_quality):.2f}", help=t("ceo.avg_quality_help"))
    with top_cols[1]:
        st.metric(t("ceo.vague_index_global"), f"{vague_rate:.1f}%", help=t("ceo.vague_index_help"))
    with top_cols[2]:
        st.metric(t("ceo.total_market_friction"), f"{avg_market_friction:.2f}", help=t("ceo.total_market_friction_help"))

    st.markdown("---")
    st.markdown("<div id='total-friction'></div>", unsafe_allow_html=True)
    st.subheader(t("ceo.total_friction"))
    render_hint(t("ceo.total_friction_hint"))

    fr_sql = rpc_df("rpc_ceo_total_friction", rpc_params)
    if fr_sql.empty:
        st.warning(t("ceo.no_data_total_friction"))
        return

    fr_sql = fr_sql.copy()
    fr_sql["market_display"] = fr_sql["market"].apply(market_label)
    fr_sql["type_display"] = fr_sql["type"].map(
        {
            "Intro Friction": t("cso.metric.avg_intro_friction"),
            "Sales Friction": t("cso.metric.avg_sales_friction"),
        }
    ).fillna(fr_sql["type"].astype(str))
    fig_fr = px.bar(
        fr_sql,
        x="market_display",
        y="friction_index",
        color="type_display",
        barmode="group",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        custom_data=["primaries", "followups", "calls_in_calc"],
        labels={"friction_index": t("ceo.total_market_friction"), "market_display": t("label.market"), "type_display": ""},
    )
    fig_fr.update_traces(
        hovertemplate=(
            f"{t('label.market')}: "+"%{x}<br>"
            "РўРёРї: %{fullData.name}<br>"
            f"{t('ceo.total_market_friction')}: "+"%{y:.2f}<br>"
            "РџРµСЂРІРёС‡РЅС‹Рµ Р·РІРѕРЅРєРё: %{customdata[0]}<br>"
            "РџРѕРІС‚РѕСЂРЅС‹Рµ Р·РІРѕРЅРєРё: %{customdata[1]}<br>"
            "Р—РІРѕРЅРєРѕРІ РІ СЂР°СЃС‡РµС‚Рµ: %{customdata[2]}<extra></extra>"
        )
    )
    st.plotly_chart(fig_fr, use_container_width=True)

    st.markdown("<div id='vague-index-by-market'></div>", unsafe_allow_html=True)
    st.subheader(t("ceo.vague_index_market"))
    render_hint(t("ceo.vague_hint"))
    vi = rpc_df("rpc_ceo_vague_index_by_market", rpc_params)
    vi = vi[vi["outcome_category"].isin(["Defined Next Step", "Vague"])].copy() if not vi.empty else vi
    if not vi.empty:
        vi["outcome_display"] = vi["outcome_category"].map({"Defined Next Step": t("ceo.defined_next_step"), "Vague": t("ceo.vague")}).fillna(vi["outcome_category"])
        vi["market_display"] = vi["market"].apply(market_label)
    fig_vi = px.bar(
        vi,
        x="market_display" if not vi.empty else "market",
        y="count",
        color="outcome_display" if not vi.empty else "outcome_category",
        barmode="relative",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        color_discrete_map={t("ceo.defined_next_step"): "#7d3cff", t("ceo.vague"): "#e74c3c"},
    )
    fig_vi.update_layout(barnorm="percent", yaxis_title=t("label.share_pct"), xaxis_title=t("label.market"), legend_title="")
    st.plotly_chart(fig_vi, use_container_width=True)

    st.markdown("---")
    st.markdown("<div id='one-call-close-rate-by-pipeline'></div>", unsafe_allow_html=True)
    st.subheader(t("ceo.occ_rate"))
    render_hint(t("ceo.occ_hint"))
    occ = rpc_df("rpc_ceo_one_call_close_rate_by_pipeline", rpc_params)
    if occ.empty:
        st.warning(t("ceo.no_data_occ"))
    else:
        occ = occ.copy()
        occ["funnel_display"] = occ["pipeline_name"].apply(pipeline_label)
        fig_occ = px.bar(
            occ.sort_values("occ_rate_pct", ascending=False),
            x="funnel_display",
            y="occ_rate_pct",
            template=_plotly_template(),
            pattern_shape_sequence=[""],
            hover_data=["occ_leads", "total_leads"],
            labels={"funnel_display": t("label.funnel"), "occ_rate_pct": t("label.share_pct")},
        )
        st.plotly_chart(fig_occ, use_container_width=True)

    st.markdown("<div id='talk-time-per-lead-by-pipeline'></div>", unsafe_allow_html=True)
    st.subheader(t("ceo.call_type_per_lead"))
    render_hint(t("ceo.call_type_per_lead_hint"))

    tt_sql = rpc_df("rpc_ceo_talk_time_per_lead_by_pipeline", rpc_params)
    if tt_sql.empty:
        st.warning(t("ceo.no_data_talk_time"))
        return

    tt_sql = tt_sql.copy()
    tt_sql["pipeline_display"] = tt_sql["pipeline_name"].apply(pipeline_label)
    tt_sql["call_type_display"] = tt_sql["call_type_group"].apply(call_type_label)
    calls_total = tt_sql.groupby("pipeline_name", dropna=False)["calls_type"].sum().reset_index(name="calls_total_pipeline")
    tt_sql = tt_sql.merge(calls_total, on="pipeline_name", how="left")
    tt_sql["share_calls_pct"] = (tt_sql["calls_type"] / tt_sql["calls_total_pipeline"].replace(0, pd.NA) * 100).fillna(0.0)

    fig_share = px.bar(
        tt_sql,
        x="pipeline_display",
        y="share_calls_pct",
        color="call_type_display",
        barmode="relative",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        custom_data=["leads_total", "calls_type", "total_minutes_type", "avg_minutes_per_call_type", "avg_minutes_per_lead_type", "total_minutes_pipeline"],
        labels={"pipeline_display": t("label.funnel"), "share_calls_pct": t("label.share_pct")},
    )
    fig_share.update_layout(yaxis_title=t("label.share_pct"), xaxis_title=t("label.funnel"), legend_title="")
    fig_share.update_traces(
        hovertemplate=(
            f"{t('label.funnel')}: "+"%{x}<br>"
            "РўРёРї: %{fullData.name}<br>"
            f"{t('label.share_pct')}: "+"%{y:.2f}<br>"
            "РЎСЂРµРґ. РјРёРЅСѓС‚ РЅР° Р·РІРѕРЅРѕРє: %{customdata[3]:.2f}<br>"
            "РЎСЂРµРґ. РјРёРЅСѓС‚ РЅР° Р»РёРґР°: %{customdata[4]:.2f}<br>"
            "Р›РёРґРѕРІ: %{customdata[0]}<br>"
            "Р—РІРѕРЅРєРѕРІ (С‚РёРї): %{customdata[1]}<br>"
            "РњРёРЅСѓС‚ (С‚РёРї): %{customdata[2]:.1f}<br>"
            "РњРёРЅСѓС‚ РІСЃРµРіРѕ РїРѕ РІРѕСЂРѕРЅРєРµ: %{customdata[5]:.1f}<extra></extra>"
        )
    )
    st.plotly_chart(fig_share, use_container_width=True)

    st.markdown("<div id='total-talk-time-by-pipeline'></div>", unsafe_allow_html=True)
    st.subheader(t("ceo.total_talk_time"))
    render_hint(t("ceo.total_talk_time_hint"))
    fig_tot = px.bar(
        tt_sql,
        x="pipeline_display",
        y="share_calls_pct",
        color="call_type_display",
        barmode="relative",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        custom_data=["leads_total", "calls_type", "total_minutes_type", "total_minutes_pipeline"],
        labels={"pipeline_display": t("label.funnel"), "share_calls_pct": t("label.share_pct")},
    )
    fig_tot.update_layout(yaxis_title=t("label.share_pct"), xaxis_title=t("label.funnel"), legend_title="")
    fig_tot.update_traces(
        hovertemplate=(
            f"{t('label.funnel')}: "+"%{x}<br>"
            "РўРёРї: %{fullData.name}<br>"
            f"{t('label.share_pct')}: "+"%{y:.2f}<br>"
            "Р›РёРґРѕРІ: %{customdata[0]}<br>"
            "Р—РІРѕРЅРєРѕРІ (С‚РёРї): %{customdata[1]}<br>"
            "РњРёРЅСѓС‚ (С‚РёРї): %{customdata[2]:.1f}<br>"
            "РњРёРЅСѓС‚ РІСЃРµРіРѕ РїРѕ РІРѕСЂРѕРЅРєРµ: %{customdata[3]:.1f}<extra></extra>"
        )
    )
    st.plotly_chart(fig_tot, use_container_width=True)

