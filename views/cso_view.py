import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import rpc_df
from views.shared_ui import render_hint


def _plotly_template():
    return "plotly_dark" if st.session_state.get("ui_theme_v1", "dark") == "dark" else "plotly_white"


def _existing_columns(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


def render_cso_dashboard(date_range, selected_markets, selected_pipelines, selected_managers=None):
    st.markdown("<h1 style='text-align:center;'>Operations Dashboard</h1>", unsafe_allow_html=True)

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
        st.warning("No data available for current filters.")
        return

    kpi = df_kpi.iloc[0].to_dict()
    ops_cols = st.columns(6)
    with ops_cols[0]:
        st.metric("Total Calls", f"{int(kpi.get('total_calls') or 0)}")
    with ops_cols[1]:
        st.metric("Intro Calls", f"{int(kpi.get('intro_calls') or 0)}")
    with ops_cols[2]:
        st.metric("Intro Follow Up", f"{int(kpi.get('intro_flup') or 0)}")
    with ops_cols[3]:
        st.metric("Sales Calls", f"{int(kpi.get('sales_calls') or 0)}")
    with ops_cols[4]:
        st.metric("Sales Follow Up", f"{int(kpi.get('sales_flup') or 0)}")
    with ops_cols[5]:
        avg_q = kpi.get("avg_quality", None)
        st.metric("Avg Quality", "—" if avg_q in (None, "", "nan") else f"{float(avg_q):.2f}")

    tab_a, tab_b = st.tabs(["Anomalies", "Low Quality Calls"])
    with tab_a:
        anomalies = rpc_df("rpc_cso_anomalies", params)
        show_cols = _existing_columns(
            anomalies,
            ["call_datetime", "manager", "pipeline_name", "duration_min", "next_step_type", "audio_url", "kommo_link"],
        )
        if anomalies.empty:
            st.success("No anomalies for current filters.")
        else:
            st.dataframe(
                anomalies[show_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "audio_url": st.column_config.LinkColumn("Audio URL"),
                    "kommo_link": st.column_config.LinkColumn("Kommo"),
                },
            )

    with tab_b:
        low_q = rpc_df("rpc_cso_low_quality", params)
        show_cols = _existing_columns(
            low_q,
            ["call_datetime", "manager", "pipeline_name", "average_quality", "audio_url", "kommo_link"],
        )
        if low_q.empty:
            st.success("No low-quality calls for current filters.")
        else:
            low_q = low_q.copy()
            low_q = low_q.sort_values("average_quality", ascending=True, na_position="last")
            st.dataframe(
                low_q[show_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "audio_url": st.column_config.LinkColumn("Audio URL"),
                    "kommo_link": st.column_config.LinkColumn("Kommo"),
                },
            )

    df_mgr = rpc_df("rpc_cso_talk_time_by_manager", params)
    if not df_mgr.empty and {"manager", "call_type_group", "minutes", "calls", "total_calls"}.issubset(df_mgr.columns):
        type_order = ["Intro Call", "Intro Flup", "Sales Call", "Sales Flup"]
        df_mgr = df_mgr.copy()
        df_mgr["call_type_group"] = pd.Categorical(df_mgr["call_type_group"], categories=type_order, ordered=True)
        df_mgr = df_mgr.sort_values(["manager", "call_type_group"])
        last_type = type_order[-1]
        df_mgr["label_calls"] = df_mgr.apply(
            lambda r: str(int(r["total_calls"])) if r["call_type_group"] == last_type else "",
            axis=1,
        )
        fig_ops = px.bar(
            df_mgr,
            y="manager",
            x="minutes",
            color="call_type_group",
            orientation="h",
            template=_plotly_template(),
            pattern_shape_sequence=[""],
            title="Talk Time by Manager",
            hover_data=["calls", "call_type_group", "total_calls"],
            text="label_calls",
        )
        fig_ops.update_traces(
            hovertemplate="Manager: %{y}<br>Type: %{customdata[1]}<br>Minutes: %{x:.1f}<br>Calls: %{customdata[0]}<br>Total Calls: %{customdata[2]}<extra></extra>"
        )
        fig_ops.update_layout(yaxis_title="", xaxis_title="Minutes", legend_title="Call Type")
        st.plotly_chart(fig_ops, use_container_width=True)

    df_pipe = rpc_df("rpc_cso_calls_by_pipeline", params)
    if not df_pipe.empty and {"pipeline_name", "call_type_group", "calls", "minutes", "total_minutes"}.issubset(df_pipe.columns):
        type_order = ["Intro Call", "Intro Flup", "Sales Call", "Sales Flup"]
        df_pipe = df_pipe.copy()
        df_pipe["pipeline_name"] = df_pipe["pipeline_name"].fillna("Unknown")
        df_pipe["call_type_group"] = pd.Categorical(df_pipe["call_type_group"], categories=type_order, ordered=True)
        df_pipe = df_pipe.sort_values(["pipeline_name", "call_type_group"])
        last_type = type_order[-1]
        df_pipe["label_minutes"] = df_pipe.apply(
            lambda r: f"{float(r['total_minutes']):.1f}" if r["call_type_group"] == last_type else "",
            axis=1,
        )
        fig_pipe = px.bar(
            df_pipe,
            y="pipeline_name",
            x="calls",
            color="call_type_group",
            orientation="h",
            template=_plotly_template(),
            pattern_shape_sequence=[""],
            title="Total Calls by Pipeline",
            hover_data=["minutes", "call_type_group", "total_minutes"],
            text="label_minutes",
        )
        fig_pipe.update_traces(
            hovertemplate="Pipeline: %{y}<br>Type: %{customdata[1]}<br>Calls: %{x}<br>Minutes: %{customdata[0]:.1f}<br>Total Minutes: %{customdata[2]:.1f}<extra></extra>"
        )
        fig_pipe.update_layout(yaxis_title="", xaxis_title="Calls", legend_title="Call Type")
        st.plotly_chart(fig_pipe, use_container_width=True)

    st.markdown("---")

    st.markdown("<div id='manager-productivity-timeline'></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center;'>Manager Productivity Timeline</h2>", unsafe_allow_html=True)
    daily = rpc_df("rpc_cso_manager_productivity_timeline", params)
    if daily.empty:
        st.warning("Not enough data for timeline for current filters.")
    else:
        daily = daily.copy()
        daily["call_date"] = pd.to_datetime(daily["call_date"], errors="coerce").dt.date
        daily["total_minutes"] = pd.to_numeric(daily.get("total_minutes"), errors="coerce").fillna(0.0)
        market_color_map = {
            "CZ": "#1f77b4",
            "SK": "#d62728",
            "RUK": "#2ca02c",
            "Others": "#9467bd",
        }
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
                        "Date: %{x}<br>"
                        "Manager: %{fullData.name} (%{customdata[0]})<br>"
                        "Intro Calls: %{customdata[1]}<br>"
                        "Intro Flup: %{customdata[2]}<br>"
                        "Sales Calls: %{customdata[3]}<br>"
                        "Sales Flup: %{customdata[4]}<extra></extra>"
                    ),
                )
            )
        fig.update_layout(template=_plotly_template(), yaxis_title="Total Minutes", xaxis_title="Date", legend_title="Manager")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    st.markdown("<div id='call-control'></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center;'>Call Control</h2>", unsafe_allow_html=True)
    render_hint(
        "Tracks 'Next-Step Clarity'—the extent to which a manager dictates the rules of engagement and avoids dead-end conversations."
    )
    col_v1, col_v2 = st.columns([3, 2])
    df_control = rpc_df("rpc_cso_call_control", params)

    with col_v1:
        if not df_control.empty:
            data_chart = df_control[df_control["outcome_category"].isin(["Defined", "Vague"])].copy()
            fig_vague = px.bar(
                data_chart,
                x="manager",
                y="count",
                color="outcome_category",
                title="Defined vs. Vague (100% Stacked)",
                barmode="relative",
                color_discrete_map={"Defined": "#2ecc71", "Vague": "#e74c3c"},
                pattern_shape_sequence=[""],
                hover_data=["total_calls"],
            )
            fig_vague.update_layout(barnorm="percent", yaxis_title="Share (%)", xaxis_title="")
            st.plotly_chart(fig_vague, use_container_width=True)
            st.caption(
                "Defined outcomes include: lesson_scheduled, callback_scheduled, payment_pending, sold. "
                "Vague outcomes include: callback_vague and other non-committal callbacks."
            )

    with col_v2:
        if df_control.empty:
            lb_df = pd.DataFrame(columns=["Manager", "Defined %", "Calls", "Avg Quality"])
        else:
            mgr_stats = (
                df_control.groupby("manager", dropna=False)
                .agg(total_calls=("total_calls", "max"), avg_quality=("avg_quality", "max"), defined_rate=("defined_rate", "max"))
                .reset_index()
            )
            lb_df = mgr_stats.sort_values("defined_rate", ascending=False).copy()
            lb_df["defined_rate_pct"] = (pd.to_numeric(lb_df["defined_rate"], errors="coerce").fillna(0) * 100).round(2).astype(str) + "%"
            lb_df["Avg Quality"] = pd.to_numeric(lb_df["avg_quality"], errors="coerce").round(2)
            lb_df = lb_df[["manager", "defined_rate_pct", "total_calls", "Avg Quality"]]
        lb_df.columns = ["Manager", "Defined %", "Calls", "Avg Quality"]
        st.dataframe(lb_df, hide_index=True, use_container_width=True)

    st.markdown("---")

    st.markdown("<div id='friction-and-resistance'></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center;'>Friction & Resistance</h2>", unsafe_allow_html=True)
    render_hint("Friction & Resistance: A compact view of workload and follow-up pressure by segment.")

    df_fric = rpc_df("rpc_cso_friction_by_pipeline", params)
    if df_fric.empty:
        st.warning("No data for current selection in Friction & Resistance.")
    else:
        df_fric = df_fric.copy()
        df_fric = df_fric.rename(columns={"pipeline_name": "Pipeline", "type": "Type", "value": "Value", "total_calls": "Total Calls"})
        if not df_fric.empty:
            col1, col2 = st.columns([2, 1])
            with col1:
                fig_friction = px.bar(
                    df_fric,
                    x="Pipeline",
                    y="Value",
                    color="Type",
                    barmode="group",
                    title="Friction Index by Pipeline",
                    color_discrete_map={"Intro Friction": "#3498db", "Sales Friction": "#e67e22"},
                    pattern_shape_sequence=[""],
                    hover_data=["Total Calls"],
                )
                fig_friction.update_layout(yaxis_title="Friction Index (Flup / Primary)", xaxis_title="")
                st.plotly_chart(fig_friction, use_container_width=True)

            with col2:
                intro_calls_seg = int(kpi.get("intro_calls") or 0)
                intro_flups_seg = int(kpi.get("intro_flup") or 0)
                sales_calls_seg = int(kpi.get("sales_calls") or 0)
                sales_flups_seg = int(kpi.get("sales_flup") or 0)
                avg_intro_friction = (intro_flups_seg / intro_calls_seg) if intro_calls_seg > 0 else 0.0
                avg_sales_friction = (sales_flups_seg / sales_calls_seg) if sales_calls_seg > 0 else 0.0
                st.metric(
                    "Avg Intro Friction",
                    f"{avg_intro_friction:.2f}",
                    help=r"$Intro\ Friction=\frac{Intro\ Flups}{Intro\ Calls}$",
                )
                st.metric(
                    "Avg Sales Friction",
                    f"{avg_sales_friction:.2f}",
                    help=r"$Sales\ Friction=\frac{Sales\ Flups}{Sales\ Calls}$",
                )

        st.markdown("<h3 style='text-align:center;'>Friction vs. Defined Rate</h3>", unsafe_allow_html=True)
        render_hint("Each bubble is a manager+pipeline segment. X = Defined Rate on primaries, Y = Flups/Primary (friction).")
        bubble_stats = rpc_df("rpc_cso_friction_defined_bubble", params)
        if not bubble_stats.empty:
            market_color_map = {
                "CZ": "#1f77b4",
                "SK": "#d62728",
                "RUK": "#2ca02c",
                "Others": "#9467bd",
            }
            fig_bubble = px.scatter(
                bubble_stats,
                x="defined_rate_pct",
                y="friction_index",
                size="total_calls",
                color="computed_market",
                hover_name="manager",
                template=_plotly_template(),
                size_max=60,
                color_discrete_map=market_color_map,
                labels={
                    "defined_rate_pct": "Defined Rate (%)",
                    "friction_index": "Friction Index (Flup / Primary)",
                    "total_calls": "Calls",
                    "computed_market": "Market",
                },
                hover_data=["pipeline_name", "total_calls", "average_quality", "primaries", "followups", "defined_primaries"],
            )
            fig_bubble.add_vline(x=bubble_stats["defined_rate_pct"].mean(), line_dash="dot", annotation_text="Avg Defined")
            fig_bubble.add_hline(y=bubble_stats["friction_index"].mean(), line_dash="dot", annotation_text="Avg Friction")
            st.plotly_chart(fig_bubble, use_container_width=True)

    st.markdown("---")

    st.markdown("<div id='discovery-depth-index'></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center;'>Discovery Depth Index</h2>", unsafe_allow_html=True)
    st.caption(
        "❓ Discovery Depth Index: Calls with no objections are not a success, they usually "
        "mean the manager failed to surface real barriers. If the lead has no objections, "
        "the manager is not in control of the deal."
    )
    df_dd = rpc_df("rpc_cso_discovery_depth", params)
    if df_dd.empty:
        st.warning("Not enough data for Discovery Depth Index for current filters.")
        return

    chart_rows = []
    for _, row in df_dd.iterrows():
        chart_rows.append(
            {
                "manager": row["manager"],
                "Bucket": "No Objections Calls",
                "value": int(row["no_objections_calls"]),
                "market": row.get("market"),
                "avg_quality": row.get("avg_quality"),
                "no_objections_calls": int(row["no_objections_calls"]),
                "with_objections_calls": int(row["with_objections_calls"]),
                "total_calls": int(row["total_calls"]),
            }
        )
        chart_rows.append(
            {
                "manager": row["manager"],
                "Bucket": "Calls With Objections",
                "value": int(row["with_objections_calls"]),
                "market": row.get("market"),
                "avg_quality": row.get("avg_quality"),
                "no_objections_calls": int(row["no_objections_calls"]),
                "with_objections_calls": int(row["with_objections_calls"]),
                "total_calls": int(row["total_calls"]),
            }
        )

    chart_df = pd.DataFrame(chart_rows)
    fig_dd = px.bar(
        chart_df,
        x="manager",
        y="value",
        color="Bucket",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        barmode="relative",
        labels={"value": "Share (%)"},
        custom_data=["no_objections_calls", "with_objections_calls", "total_calls", "market", "avg_quality"],
    )
    fig_dd.update_traces(
        hovertemplate=(
            "Manager: %{x}<br>"
            "Bucket: %{fullData.name}<br>"
            "Share: %{y:.1f}%<br>"
            "No Objections: %{customdata[0]}<br>"
            "With Objections: %{customdata[1]}<br>"
            "Total Calls: %{customdata[2]}<br>"
            "Market: %{customdata[3]}<br>"
            "Avg Quality: %{customdata[4]:.2f}<extra></extra>"
        )
    )
    fig_dd.update_layout(barnorm="percent", yaxis_title="Share (%)", xaxis_title="", legend_title="")
    st.plotly_chart(fig_dd, use_container_width=True)

    st.markdown("<h2 style='text-align:center;'>No Objections Calls Rating</h2>", unsafe_allow_html=True)

    lb = df_dd.copy()
    lb["Avg Quality"] = pd.to_numeric(lb["avg_quality"], errors="coerce").round(2)
    lb["Intro Friction"] = pd.to_numeric(lb["intro_friction"], errors="coerce").round(2)
    lb["Sales Friction"] = pd.to_numeric(lb["sales_friction"], errors="coerce").round(2)
    lb = lb[
        [
            "manager",
            "total_calls",
            "no_objections_calls",
            "sterile_rate",
            "market",
            "Avg Quality",
            "Intro Friction",
            "Sales Friction",
        ]
    ]
    lb.columns = [
        "Manager",
        "Total Calls",
        "No Objections Calls",
        "No Objections Share %",
        "Market",
        "Avg Quality",
        "Intro Friction",
        "Sales Friction",
    ]
    st.dataframe(lb, hide_index=True, use_container_width=True)

if __name__ == "__main__":
    pass
