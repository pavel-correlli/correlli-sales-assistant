import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import rpc_df
from i18n import call_type_label, market_label, pipeline_label, t
from views.shared_ui import render_hint


def _plotly_template():
    return "plotly_dark" if st.session_state.get("ui_theme_v1", "dark") == "dark" else "plotly_white"


def _existing_columns(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


def render_cso_dashboard(date_range, selected_markets, selected_pipelines, selected_managers=None):
    st.markdown(f"<h1 style='text-align:center;'>{t('cso.title')}</h1>", unsafe_allow_html=True)
    date_start = date_range[0] if len(date_range) == 2 else None
    date_end = date_range[1] if len(date_range) == 2 else None
    params = {
        "date_start": date_start.isoformat() if date_start else None,
        "date_end": date_end.isoformat() if date_end else None,
        "markets": selected_markets or [],
        "pipelines": selected_pipelines or [],
        "managers": selected_managers or [],
    }

    st.markdown("<div id='operations-feed'></div>", unsafe_allow_html=True)
    df_kpi = rpc_df("rpc_cso_ops_kpis", params)
    if df_kpi.empty:
        st.warning(t("cso.no_data"))
        return

    kpi = df_kpi.iloc[0].to_dict()
    ops_cols = st.columns(6)
    ops_vals = [
        t("cso.kpi.total_calls"),
        t("cso.kpi.intro_calls"),
        t("cso.kpi.intro_flup"),
        t("cso.kpi.sales_calls"),
        t("cso.kpi.sales_flup"),
    ]
    ops_raw = [int(kpi.get("total_calls") or 0), int(kpi.get("intro_calls") or 0), int(kpi.get("intro_flup") or 0), int(kpi.get("sales_calls") or 0), int(kpi.get("sales_flup") or 0)]
    for i in range(5):
        with ops_cols[i]:
            st.metric(ops_vals[i], f"{ops_raw[i]}")
    with ops_cols[5]:
        avg_q = kpi.get("avg_quality", None)
        st.metric(t("cso.kpi.avg_quality"), "-" if avg_q in (None, "", "nan") else f"{float(avg_q):.2f}")

    tab_a, tab_b = st.tabs([t("cso.tab.anomalies"), t("cso.tab.low_quality")])
    with tab_a:
        anomalies = rpc_df("rpc_cso_anomalies", params)
        show_cols = _existing_columns(anomalies, ["call_datetime", "manager", "pipeline_name", "duration_min", "next_step_type", "audio_url", "kommo_link"])
        if anomalies.empty:
            st.success(t("cso.anomalies.empty"))
        else:
            out = anomalies.copy()
            if "pipeline_name" in out.columns:
                out["pipeline_name"] = out["pipeline_name"].apply(pipeline_label)
            st.dataframe(
                out[show_cols],
                use_container_width=True,
                hide_index=True,
                column_config={"audio_url": st.column_config.LinkColumn(t("cso.audio_url")), "kommo_link": st.column_config.LinkColumn(t("cso.kommo"))},
            )

    with tab_b:
        low_q = rpc_df("rpc_cso_low_quality", params)
        show_cols = _existing_columns(low_q, ["call_datetime", "manager", "pipeline_name", "average_quality", "audio_url", "kommo_link"])
        if low_q.empty:
            st.success(t("cso.low_quality.empty"))
        else:
            out = low_q.copy().sort_values("average_quality", ascending=True, na_position="last")
            if "pipeline_name" in out.columns:
                out["pipeline_name"] = out["pipeline_name"].apply(pipeline_label)
            st.dataframe(
                out[show_cols],
                use_container_width=True,
                hide_index=True,
                column_config={"audio_url": st.column_config.LinkColumn(t("cso.audio_url")), "kommo_link": st.column_config.LinkColumn(t("cso.kommo"))},
            )

    df_mgr = rpc_df("rpc_cso_talk_time_by_manager", params)
    if not df_mgr.empty and {"manager", "call_type_group", "minutes", "calls", "total_calls"}.issubset(df_mgr.columns):
        df_mgr = df_mgr.copy()
        df_mgr["call_type_display"] = df_mgr["call_type_group"].apply(call_type_label)
        type_order = [call_type_label("Intro Call"), call_type_label("Intro Flup"), call_type_label("Sales Call"), call_type_label("Sales Flup")]
        df_mgr["call_type_display"] = pd.Categorical(df_mgr["call_type_display"], categories=type_order, ordered=True)
        df_mgr = df_mgr.sort_values(["manager", "call_type_display"])
        df_mgr["label_calls"] = df_mgr.apply(lambda r: str(int(r["total_calls"])) if r["call_type_display"] == type_order[-1] else "", axis=1)
        fig_ops = px.bar(
            df_mgr,
            y="manager",
            x="minutes",
            color="call_type_display",
            orientation="h",
            template=_plotly_template(),
            pattern_shape_sequence=[""],
            title=t("cso.chart.talk_time_manager"),
            hover_data=["calls", "call_type_display", "total_calls"],
            text="label_calls",
        )
        fig_ops.update_traces(
            hovertemplate=(
                f"{t('label.manager')}: "+"%{y}<br>"
                "Тип: %{customdata[1]}<br>"
                f"{t('label.minutes')}: "+"%{x:.1f}<br>"
                f"{t('label.calls')}: "+"%{customdata[0]}<br>"
                f"{t('cso.kpi.total_calls')}: "+"%{customdata[2]}<extra></extra>"
            )
        )
        fig_ops.update_layout(yaxis_title="", xaxis_title=t("label.minutes"), legend_title="")
        st.plotly_chart(fig_ops, use_container_width=True)

    df_pipe = rpc_df("rpc_cso_calls_by_pipeline", params)
    if not df_pipe.empty and {"pipeline_name", "call_type_group", "calls", "minutes", "total_minutes"}.issubset(df_pipe.columns):
        df_pipe = df_pipe.copy()
        df_pipe["pipeline_display"] = df_pipe["pipeline_name"].fillna(t("cmo.unknown")).apply(pipeline_label)
        df_pipe["call_type_display"] = df_pipe["call_type_group"].apply(call_type_label)
        type_order = [call_type_label("Intro Call"), call_type_label("Intro Flup"), call_type_label("Sales Call"), call_type_label("Sales Flup")]
        df_pipe["call_type_display"] = pd.Categorical(df_pipe["call_type_display"], categories=type_order, ordered=True)
        df_pipe = df_pipe.sort_values(["pipeline_display", "call_type_display"])
        df_pipe["label_minutes"] = df_pipe.apply(lambda r: f"{float(r['total_minutes']):.1f}" if r["call_type_display"] == type_order[-1] else "", axis=1)
        fig_pipe = px.bar(
            df_pipe,
            y="pipeline_display",
            x="calls",
            color="call_type_display",
            orientation="h",
            template=_plotly_template(),
            pattern_shape_sequence=[""],
            title=t("cso.chart.total_calls_funnel"),
            hover_data=["minutes", "call_type_display", "total_minutes"],
            text="label_minutes",
        )
        fig_pipe.update_traces(
            hovertemplate=(
                f"{t('label.funnel')}: "+"%{y}<br>"
                "Тип: %{customdata[1]}<br>"
                f"{t('label.calls')}: "+"%{x}<br>"
                f"{t('label.minutes')}: "+"%{customdata[0]:.1f}<br>"
                "Минут всего: %{customdata[2]:.1f}<extra></extra>"
            )
        )
        fig_pipe.update_layout(yaxis_title="", xaxis_title=t("label.calls"), legend_title="")
        st.plotly_chart(fig_pipe, use_container_width=True)

    st.markdown("---")
    st.markdown("<div id='manager-productivity-timeline'></div>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align:center;'>{t('cso.section.manager_timeline')}</h2>", unsafe_allow_html=True)
    daily = rpc_df("rpc_cso_manager_productivity_timeline", params)
    if daily.empty:
        st.warning(t("cso.timeline.empty"))
    else:
        daily = daily.copy()
        daily["call_date"] = pd.to_datetime(daily["call_date"], errors="coerce").dt.date
        daily["total_minutes"] = pd.to_numeric(daily.get("total_minutes"), errors="coerce").fillna(0.0)
        market_color_map = {"CZ": "#1f77b4", "SK": "#d62728", "RUK": "#2ca02c", "Others": "#9467bd"}
        fig = go.Figure()
        for manager in sorted(daily["manager"].dropna().unique().tolist()):
            sub = daily[daily["manager"] == manager].sort_values("call_date")
            if sub.empty:
                continue
            market = str(sub["computed_market"].iloc[0])
            fig.add_trace(
                go.Scatter(
                    x=sub["call_date"],
                    y=sub["total_minutes"],
                    mode="lines+markers",
                    name=str(manager),
                    marker={"size": 9},
                    line={"color": market_color_map.get(market, "#9467bd")},
                    customdata=sub[["computed_market", "intro_calls", "intro_flup", "sales_calls", "sales_flup"]].to_numpy(),
                    hovertemplate=(
                        "Дата: %{x}<br>"
                        f"{t('label.manager')}: "+"%{fullData.name} (%{customdata[0]})<br>"
                        f"{t('cso.kpi.intro_calls')}: "+"%{customdata[1]}<br>"
                        f"{t('cso.kpi.intro_flup')}: "+"%{customdata[2]}<br>"
                        f"{t('cso.kpi.sales_calls')}: "+"%{customdata[3]}<br>"
                        f"{t('cso.kpi.sales_flup')}: "+"%{customdata[4]}<extra></extra>"
                    ),
                )
            )
        fig.update_layout(template=_plotly_template(), yaxis_title=t("label.minutes"), xaxis_title="Дата", legend_title=t("label.manager"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("<div id='call-control'></div>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align:center;'>{t('cso.section.call_control')}</h2>", unsafe_allow_html=True)
    render_hint(t("cso.hint.call_control"))
    col_v1, col_v2 = st.columns([3, 2])
    df_control = rpc_df("rpc_cso_call_control", params)

    with col_v1:
        if not df_control.empty:
            data_chart = df_control[df_control["outcome_category"].isin(["Defined", "Vague"])].copy()
            data_chart["outcome_display"] = data_chart["outcome_category"].map({"Defined": t("ceo.defined_next_step"), "Vague": t("ceo.vague")})
            fig_vague = px.bar(
                data_chart,
                x="manager",
                y="count",
                color="outcome_display",
                title=f"{t('ceo.defined_next_step')} vs {t('ceo.vague')}",
                barmode="relative",
                color_discrete_map={t("ceo.defined_next_step"): "#2ecc71", t("ceo.vague"): "#e74c3c"},
                pattern_shape_sequence=[""],
                hover_data=["total_calls"],
            )
            fig_vague.update_layout(barnorm="percent", yaxis_title=t("label.share_pct"), xaxis_title="")
            st.plotly_chart(fig_vague, use_container_width=True)
            st.caption(t("cso.caption.outcome_definitions"))

    with col_v2:
        if df_control.empty:
            lb_df = pd.DataFrame(columns=[t("cso.table.manager"), t("cso.table.defined_pct"), t("cso.table.calls"), t("cso.table.avg_quality")])
        else:
            mgr_stats = (
                df_control.groupby("manager", dropna=False)
                .agg(total_calls=("total_calls", "max"), avg_quality=("avg_quality", "max"), defined_rate=("defined_rate", "max"))
                .reset_index()
            )
            lb_df = mgr_stats.sort_values("defined_rate", ascending=False).copy()
            lb_df["defined_rate_pct"] = (pd.to_numeric(lb_df["defined_rate"], errors="coerce").fillna(0) * 100).round(2).astype(str) + "%"
            lb_df["avg_quality_display"] = pd.to_numeric(lb_df["avg_quality"], errors="coerce").round(2)
            lb_df = lb_df[["manager", "defined_rate_pct", "total_calls", "avg_quality_display"]]
        lb_df.columns = [t("cso.table.manager"), t("cso.table.defined_pct"), t("cso.table.calls"), t("cso.table.avg_quality")]
        st.dataframe(lb_df, hide_index=True, use_container_width=True)

    st.markdown("---")
    st.markdown("<div id='friction-and-resistance'></div>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align:center;'>{t('cso.section.friction_resistance')}</h2>", unsafe_allow_html=True)
    render_hint(t("cso.hint.friction_resistance"))

    df_fric = rpc_df("rpc_cso_friction_by_pipeline", params)
    if df_fric.empty:
        st.warning(t("cso.friction.empty"))
    else:
        df_fric = df_fric.copy()
        df_fric["funnel_display"] = df_fric["pipeline_name"].apply(pipeline_label)
        df_fric["type_display"] = df_fric["type"].map({"Intro Friction": t("cso.metric.avg_intro_friction"), "Sales Friction": t("cso.metric.avg_sales_friction")}).fillna(df_fric["type"].astype(str))
        col1, col2 = st.columns([2, 1])
        with col1:
            fig_friction = px.bar(
                df_fric,
                x="funnel_display",
                y="value",
                color="type_display",
                barmode="group",
                title=t("cso.chart.friction_by_funnel"),
                pattern_shape_sequence=[""],
                hover_data=["total_calls"],
            )
            fig_friction.update_layout(yaxis_title=t("cso.chart.friction_by_funnel"), xaxis_title="")
            st.plotly_chart(fig_friction, use_container_width=True)

        with col2:
            intro_calls_seg = int(kpi.get("intro_calls") or 0)
            intro_flups_seg = int(kpi.get("intro_flup") or 0)
            sales_calls_seg = int(kpi.get("sales_calls") or 0)
            sales_flups_seg = int(kpi.get("sales_flup") or 0)
            avg_intro_friction = (intro_flups_seg / intro_calls_seg) if intro_calls_seg > 0 else 0.0
            avg_sales_friction = (sales_flups_seg / sales_calls_seg) if sales_calls_seg > 0 else 0.0
            st.metric(t("cso.metric.avg_intro_friction"), f"{avg_intro_friction:.2f}")
            st.metric(t("cso.metric.avg_sales_friction"), f"{avg_sales_friction:.2f}")

        st.markdown(f"<h3 style='text-align:center;'>{t('cso.chart.friction_vs_defined')}</h3>", unsafe_allow_html=True)
        render_hint(t("cso.hint.friction_vs_defined"))
        bubble_stats = rpc_df("rpc_cso_friction_defined_bubble", params)
        if not bubble_stats.empty:
            bubble_stats = bubble_stats.copy()
            bubble_stats["market_display"] = bubble_stats["computed_market"].apply(market_label)
            bubble_stats["funnel_display"] = bubble_stats["pipeline_name"].apply(pipeline_label)
            fig_bubble = px.scatter(
                bubble_stats,
                x="defined_rate_pct",
                y="friction_index",
                size="total_calls",
                color="market_display",
                hover_name="manager",
                template=_plotly_template(),
                size_max=60,
                labels={"defined_rate_pct": t("cso.table.defined_pct"), "friction_index": t("cso.chart.friction_by_funnel"), "total_calls": t("label.calls"), "market_display": t("label.market")},
                hover_data=["funnel_display", "total_calls", "average_quality", "primaries", "followups", "defined_primaries"],
            )
            fig_bubble.add_vline(x=bubble_stats["defined_rate_pct"].mean(), line_dash="dot", annotation_text=t("cso.avg_defined"))
            fig_bubble.add_hline(y=bubble_stats["friction_index"].mean(), line_dash="dot", annotation_text=t("cso.avg_friction"))
            st.plotly_chart(fig_bubble, use_container_width=True)

    st.markdown("---")
    st.markdown("<div id='discovery-depth-index'></div>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align:center;'>{t('cso.section.discovery_depth')}</h2>", unsafe_allow_html=True)
    st.caption(t("cso.caption.discovery_depth"))
    df_dd = rpc_df("rpc_cso_discovery_depth", params)
    if df_dd.empty:
        st.warning(t("cso.discovery.empty"))
        return

    chart_rows = []
    for _, row in df_dd.iterrows():
        chart_rows.append({"manager": row["manager"], "Bucket": t("cso.bucket.no_objections"), "value": int(row["no_objections_calls"]), "market": row.get("market"), "avg_quality": row.get("avg_quality"), "no_objections_calls": int(row["no_objections_calls"]), "with_objections_calls": int(row["with_objections_calls"]), "total_calls": int(row["total_calls"])})
        chart_rows.append({"manager": row["manager"], "Bucket": t("cso.bucket.with_objections"), "value": int(row["with_objections_calls"]), "market": row.get("market"), "avg_quality": row.get("avg_quality"), "no_objections_calls": int(row["no_objections_calls"]), "with_objections_calls": int(row["with_objections_calls"]), "total_calls": int(row["total_calls"])})

    chart_df = pd.DataFrame(chart_rows)
    fig_dd = px.bar(
        chart_df,
        x="manager",
        y="value",
        color="Bucket",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        barmode="relative",
        labels={"value": t("label.share_pct")},
        custom_data=["no_objections_calls", "with_objections_calls", "total_calls", "market", "avg_quality"],
    )
    fig_dd.update_traces(
        hovertemplate=(
            f"{t('label.manager')}: "+"%{x}<br>"
            "Сегмент: %{fullData.name}<br>"
            f"{t('label.share_pct')}: "+"%{y:.1f}<br>"
            "Без возражений: %{customdata[0]}<br>"
            "С возражениями: %{customdata[1]}<br>"
            f"{t('cso.kpi.total_calls')}: "+"%{customdata[2]}<br>"
            f"{t('label.market')}: "+"%{customdata[3]}<br>"
            f"{t('label.avg_quality')}: "+"%{customdata[4]:.2f}<extra></extra>"
        )
    )
    fig_dd.update_layout(barnorm="percent", yaxis_title=t("label.share_pct"), xaxis_title="", legend_title="")
    st.plotly_chart(fig_dd, use_container_width=True)

    st.markdown(f"<h2 style='text-align:center;'>{t('cso.section.no_objections_rating')}</h2>", unsafe_allow_html=True)
    lb = df_dd.copy()
    lb["Avg Quality"] = pd.to_numeric(lb["avg_quality"], errors="coerce").round(2)
    lb["Intro Friction"] = pd.to_numeric(lb["intro_friction"], errors="coerce").round(2)
    lb["Sales Friction"] = pd.to_numeric(lb["sales_friction"], errors="coerce").round(2)
    if "market" in lb.columns:
        lb["market"] = lb["market"].apply(market_label)
    lb = lb[["manager", "total_calls", "no_objections_calls", "sterile_rate", "market", "Avg Quality", "Intro Friction", "Sales Friction"]]
    lb.columns = [t("cso.table.manager"), t("cso.table.total_calls"), t("cso.table.no_objections_calls"), t("cso.table.no_objections_share"), t("cso.table.market"), t("cso.table.avg_quality"), t("cso.table.intro_friction"), t("cso.table.sales_friction")]
    st.dataframe(lb, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    pass
