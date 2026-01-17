import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import fetch_view_data
from datetime import date, timedelta


def _determine_market(pipeline):
    p = str(pipeline).upper()
    if p.startswith("CZ"):
        return "CZ"
    if p.startswith("SK"):
        return "SK"
    if p.startswith("RUK"):
        return "RUK"
    return "Others"


def _get_prev_ops_day(today: date) -> date:
    d = today - timedelta(days=1)
    while d.weekday() > 4:
        d = d - timedelta(days=1)
    return d


def _get_prev_ops_week(today: date) -> tuple[date, date]:
    current_monday = today - timedelta(days=today.weekday())
    prev_monday = current_monday - timedelta(days=7)
    prev_friday = prev_monday + timedelta(days=4)
    return prev_monday, prev_friday


def _get_prev_ops_month(today: date) -> tuple[date, date]:
    first_this_month = date(today.year, today.month, 1)
    prev_month_last_day = first_this_month - timedelta(days=1)
    prev_month_first_day = date(prev_month_last_day.year, prev_month_last_day.month, 1)
    return prev_month_first_day, prev_month_last_day


def _existing_columns(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


def _is_callback_vague(val) -> bool:
    ns = str(val or "").lower()
    return ns == "callback_vague" or ("callback" in ns and "vague" in ns)


def _compute_outcome_category(df: pd.DataFrame) -> pd.Series:
    def get_outcome(row):
        ns = str(row.get("next_step_type", "")).lower()
        if any(x in ns for x in ["lesson_scheduled", "callback_scheduled", "payment_pending", "sold"]):
            return "Defined"
        if "vague" in ns:
            return "Vague"
        return "Other"

    return df.apply(get_outcome, axis=1)

def render_cso_dashboard(date_range, selected_markets, selected_pipelines, selected_managers=None):
    st.title("🎯 CSO Operations Dashboard")

    with st.spinner("Analyzing call metadata..."):
        df = fetch_view_data("Algonova_Calls_Raw")
        if df.empty:
            df = fetch_view_data("v_analytics_calls_enhanced")

    if df.empty:
        st.warning("No data available. Please check database connection.")
        return

    total_raw_rows = len(df)
    total_raw_exact = df.attrs.get("supabase_exact_count", None)

    if "call_datetime" in df.columns:
        df["call_datetime"] = pd.to_datetime(df["call_datetime"], errors="coerce", utc=True)
    else:
        df["call_datetime"] = pd.NaT

    df["call_date"] = df["call_datetime"].dt.date

    if "pipeline_name" in df.columns:
        df["computed_market"] = df["pipeline_name"].apply(_determine_market)
    else:
        df["computed_market"] = df.get("market", "Others")

    if "Average_quality" in df.columns:
        df["Average_quality"] = pd.to_numeric(df["Average_quality"], errors="coerce")

    if "call_duration_sec" in df.columns:
        df["call_duration_sec"] = pd.to_numeric(df["call_duration_sec"], errors="coerce").fillna(0)

    df["outcome_category"] = _compute_outcome_category(df)

    mask_date = pd.Series([True] * len(df))
    if len(date_range) == 2:
        mask_date = (df["call_date"] >= date_range[0]) & (df["call_date"] <= date_range[1])

    mask_pipeline = pd.Series([True] * len(df))
    if selected_pipelines:
        mask_pipeline = df["pipeline_name"].isin(selected_pipelines)

    mask_market = pd.Series([True] * len(df))
    if selected_markets:
        if "market" in df.columns:
            mask_market = df["computed_market"].isin(selected_markets) | df["market"].isin(selected_markets)
        else:
            mask_market = df["computed_market"].isin(selected_markets)

    mask_manager = pd.Series([True] * len(df))
    if selected_managers:
        mask_manager = df["manager"].isin(selected_managers)

    mask_all = mask_date & mask_pipeline & mask_market & mask_manager
    mask_no_date = mask_pipeline & mask_market & mask_manager

    df_global = df[mask_all].copy()
    df_no_date = df[mask_no_date].copy()

    if df_global.empty:
        st.warning(f"No data found for the current selection (Filtered from {total_raw_rows} raw records).")
        return

    with st.expander("📊 Data Health & Volume", expanded=False):
        dates = df_global["call_date"].dropna()
        st.write(f"**Total Records Loaded from DB:** {total_raw_rows}")
        if total_raw_exact is not None:
            st.write(f"**Supabase Exact Count (server):** {total_raw_exact}")
        st.write(f"**Records Shown (after filters):** {len(df_global)}")
        if len(dates) > 0:
            st.write(f"**Date Range in Result:** {dates.min()} → {dates.max()}")

        rows_after_date = int(mask_date.sum())
        rows_after_market = int((mask_date & mask_market).sum())
        rows_after_pipeline = int((mask_date & mask_market & mask_pipeline).sum())
        rows_after_manager = int((mask_date & mask_market & mask_pipeline & mask_manager).sum())

        st.write(f"**Rows After Date Filter:** {rows_after_date}")
        st.write(f"**Rows After Market Filter:** {rows_after_market}")
        st.write(f"**Rows After Pipeline Filter:** {rows_after_pipeline}")
        st.write(f"**Rows After Manager Filter:** {rows_after_manager}")

        if total_raw_rows > 0:
            st.progress(len(df_global) / total_raw_rows, text=f"Showing {len(df_global)} / {total_raw_rows} calls")

    if "cso_preset_initialized" not in st.session_state:
        today = date.today()
        prev_day = _get_prev_ops_day(today)
        st.session_state["date_range_v2"] = [prev_day, prev_day]
        st.session_state["all_time_v1"] = False
        st.session_state["cso_preset_initialized"] = True
        st.session_state["cso_date_preset"] = "day"
        st.rerun()

    st.markdown("<h2 style='text-align:center;'>Sales Operations Feed</h2>", unsafe_allow_html=True)

    preset_cols = st.columns(3)
    current_preset = st.session_state.get("cso_date_preset", "day")
    today = date.today()

    with preset_cols[0]:
        btn_day = st.button(
            "Prev Ops. Day",
            type="primary" if current_preset == "day" else "secondary",
        )
        if btn_day:
            prev_day = _get_prev_ops_day(today)
            st.session_state["date_range_v2"] = [prev_day, prev_day]
            st.session_state["all_time_v1"] = False
            st.session_state["cso_date_preset"] = "day"
            st.rerun()

    with preset_cols[1]:
        btn_week = st.button(
            "Prev Ops. Week",
            type="primary" if current_preset == "week" else "secondary",
        )
        if btn_week:
            start_w, end_w = _get_prev_ops_week(today)
            st.session_state["date_range_v2"] = [start_w, end_w]
            st.session_state["all_time_v1"] = False
            st.session_state["cso_date_preset"] = "week"
            st.rerun()

    with preset_cols[2]:
        btn_month = st.button(
            "Prev Ops. Month",
            type="primary" if current_preset == "month" else "secondary",
        )
        if btn_month:
            start_m, end_m = _get_prev_ops_month(today)
            st.session_state["date_range_v2"] = [start_m, end_m]
            st.session_state["all_time_v1"] = False
            st.session_state["cso_date_preset"] = "month"
            st.rerun()

    df_feed = df_global.copy()

    if df_feed.empty:
        st.warning("No data for current filters.")
    else:
        ops_cols = st.columns(5)
        total_calls = int(df_feed["call_id"].count()) if "call_id" in df_feed.columns else int(len(df_feed))
        intro_calls = 0
        intro_flup = 0
        sales_calls = 0
        sales_flup = 0
        if "call_type" in df_feed.columns:
            intro_calls = int(df_feed[df_feed["call_type"] == "intro_call"].shape[0])
            intro_flup = int(df_feed[df_feed["call_type"] == "intro_followup"].shape[0])
            sales_calls = int(df_feed[df_feed["call_type"] == "sales_call"].shape[0])
            sales_flup = int(df_feed[df_feed["call_type"] == "sales_followup"].shape[0])
        avg_quality = float(df_feed["Average_quality"].mean()) if "Average_quality" in df_feed.columns else float("nan")

        with ops_cols[0]:
            st.metric("Total Calls", f"{total_calls}")
        with ops_cols[1]:
            st.metric("Intro Calls", f"{intro_calls}")
        with ops_cols[2]:
            st.metric("Intro Follow Up", f"{intro_flup}")
        with ops_cols[3]:
            st.metric("Sales Calls", f"{sales_calls}")
        with ops_cols[4]:
            st.metric("Sales Follow Up", f"{sales_flup}")

        qual_col = st.columns(1)[0]
        with qual_col:
            if pd.isna(avg_quality):
                st.metric("Avg Quality", "—")
            else:
                st.metric("Avg Quality", f"{avg_quality:.2f}")

        if "call_duration_sec" in df_feed.columns and "manager" in df_feed.columns and "call_type" in df_feed.columns:
            mgr_group = (
                df_feed.groupby(["manager", "call_type"], dropna=False)
                .agg(
                    total_sec=("call_duration_sec", "sum"),
                    calls=("call_id", "count"),
                )
                .reset_index()
            )
            mgr_group["minutes"] = mgr_group["total_sec"] / 60.0
            type_map = {
                "intro_call": "Intro Call",
                "intro_followup": "Intro Flup",
                "sales_call": "Sales Call",
                "sales_followup": "Sales Flup",
            }
            mgr_group["call_type_group"] = mgr_group["call_type"].map(type_map).fillna("Other")
            mgr_totals = (
                mgr_group.groupby("manager")["calls"]
                .sum()
                .rename("total_calls")
                .reset_index()
            )
            mgr_group = mgr_group.merge(mgr_totals, on="manager", how="left")
            type_order = ["Intro Call", "Intro Flup", "Sales Call", "Sales Flup"]
            mgr_group["call_type_group"] = pd.Categorical(mgr_group["call_type_group"], categories=type_order, ordered=True)
            mgr_group = mgr_group.sort_values(["manager", "call_type_group"])
            last_type = type_order[-1]
            mgr_group["label_calls"] = mgr_group.apply(
                lambda r: str(r["total_calls"]) if r["call_type_group"] == last_type else "",
                axis=1,
            )
            fig_ops = px.bar(
                mgr_group,
                y="manager",
                x="minutes",
                color="call_type_group",
                orientation="h",
                template="plotly_white",
                title="Talk Time by Manager",
                hover_data=["calls", "call_type_group", "total_calls"],
                text="label_calls",
            )
            fig_ops.update_traces(
                hovertemplate="Manager: %{y}<br>Type: %{customdata[1]}<br>Minutes: %{x:.1f}<br>Calls: %{customdata[0]}<br>Total Calls: %{customdata[2]}<extra></extra>"
            )
            fig_ops.update_layout(yaxis_title="", xaxis_title="Minutes", legend_title="Call Type")
            st.plotly_chart(fig_ops, use_container_width=True)

        if "pipeline_name" in df_feed.columns and "call_duration_sec" in df_feed.columns and "call_type" in df_feed.columns:
            pipe_group = (
                df_feed.groupby(["pipeline_name", "call_type"], dropna=False)
                .agg(
                    calls=("call_id", "count"),
                    total_sec=("call_duration_sec", "sum"),
                )
                .reset_index()
            )
            pipe_group["minutes"] = pipe_group["total_sec"] / 60.0
            pipe_group["pipeline_name"] = pipe_group["pipeline_name"].fillna("Unknown")
            type_map = {
                "intro_call": "Intro Call",
                "intro_followup": "Intro Flup",
                "sales_call": "Sales Call",
                "sales_followup": "Sales Flup",
            }
            pipe_group["call_type_group"] = pipe_group["call_type"].map(type_map).fillna("Other")
            pipe_totals = (
                pipe_group.groupby("pipeline_name")["minutes"]
                .sum()
                .rename("total_minutes")
                .reset_index()
            )
            pipe_group = pipe_group.merge(pipe_totals, on="pipeline_name", how="left")
            type_order = ["Intro Call", "Intro Flup", "Sales Call", "Sales Flup"]
            pipe_group["call_type_group"] = pd.Categorical(pipe_group["call_type_group"], categories=type_order, ordered=True)
            pipe_group = pipe_group.sort_values(["pipeline_name", "call_type_group"])
            last_type = type_order[-1]
            pipe_group["label_minutes"] = pipe_group.apply(
                lambda r: f"{r['total_minutes']:.1f}" if r["call_type_group"] == last_type else "",
                axis=1,
            )
            fig_pipe = px.bar(
                pipe_group,
                y="pipeline_name",
                x="calls",
                color="call_type_group",
                orientation="h",
                template="plotly_white",
                title="Total Calls by Pipeline",
                hover_data=["minutes", "call_type_group", "total_minutes"],
                text="label_minutes",
            )
            fig_pipe.update_traces(
                hovertemplate="Pipeline: %{y}<br>Type: %{customdata[1]}<br>Calls: %{x}<br>Minutes: %{customdata[0]:.1f}<br>Total Minutes: %{customdata[2]:.1f}<extra></extra>"
            )
            fig_pipe.update_layout(yaxis_title="", xaxis_title="Calls", legend_title="Call Type")
            st.plotly_chart(fig_pipe, use_container_width=True)

        tab_a, tab_b = st.tabs(["📎 Anomalies", "⚠️ Low Quality Calls"])

        with tab_a:
            if "call_duration_sec" in df_feed.columns and "next_step_type" in df_feed.columns:
                anomalies = df_feed[
                    (df_feed["call_duration_sec"] > 600)
                    & df_feed["next_step_type"].apply(_is_callback_vague)
                ].copy()
                anomalies["duration_min"] = (anomalies["call_duration_sec"] / 60).round(1)
                show_cols = _existing_columns(
                    anomalies,
                    ["call_datetime", "manager", "pipeline_name", "duration_min", "next_step_type", "kommo_link"],
                )
                if anomalies.empty:
                    st.success("No anomalies for current filters.")
                else:
                    st.dataframe(
                        anomalies.sort_values("call_duration_sec", ascending=False)[show_cols],
                        use_container_width=True,
                        hide_index=True,
                    )
            elif "call_duration_sec" not in df_feed.columns:
                st.warning("call_duration_sec is missing, duration-based anomalies are unavailable.")
            else:
                st.warning("next_step_type is missing, vague callback anomalies are unavailable.")

        with tab_b:
            if "Average_quality" in df_feed.columns:
                low_q = df_feed[df_feed["Average_quality"] < 4.0].copy()
                show_cols = _existing_columns(
                    low_q,
                    ["call_datetime", "manager", "pipeline_name", "Average_quality", "kommo_link"],
                )
                if low_q.empty:
                    st.success("No low-quality calls for current filters.")
                else:
                    st.dataframe(
                        low_q.sort_values("Average_quality", ascending=True)[show_cols],
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.warning("Average_quality is missing, quality filter is unavailable.")

    st.markdown("---")

    st.header("2. Manager Productivity Timeline")
    if "call_duration_sec" not in df_global.columns or "manager" not in df_global.columns:
        st.warning("Not enough data for timeline (need manager and call_duration_sec).")
    else:
        timeline = df_global.dropna(subset=["manager", "call_date"]).copy()
        timeline["call_duration_sec"] = pd.to_numeric(timeline["call_duration_sec"], errors="coerce").fillna(0)

        daily = (
            timeline.groupby(["call_date", "manager", "computed_market"], dropna=False)
            .agg(
                total_minutes=("call_duration_sec", lambda s: float(s.sum()) / 60.0),
                intro_calls=("call_type", lambda s: int((s == "intro_call").sum())),
                intro_flup=("call_type", lambda s: int((s == "intro_followup").sum())),
                sales_calls=("call_type", lambda s: int((s == "sales_call").sum())),
                sales_flup=("call_type", lambda s: int((s == "sales_followup").sum())),
            )
            .reset_index()
        )
        daily["total_minutes"] = daily["total_minutes"].fillna(0)

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
            market = sub["computed_market"].iloc[0]
            fig.add_trace(
                go.Scatter(
                    x=sub["call_date"],
                    y=sub["total_minutes"],
                    mode="lines+markers",
                    name=str(manager),
                    marker={"size": 9},
                    line={"color": market_color_map.get(market, "#9467bd")},
                    customdata=sub[
                        ["computed_market", "intro_calls", "intro_flup", "sales_calls", "sales_flup"]
                    ].to_numpy(),
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
        fig.update_layout(
            template="plotly_white",
            yaxis_title="Total Minutes",
            xaxis_title="Date",
            legend_title="Manager",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    st.header("3. Call Control")
    st.info(
        "Call Control shows how well managers keep initiative and close each conversation "
        "with a specific next step instead of vague promises. Defined outcomes mean the manager "
        "secured a clear follow-up action (for example: \"You said you want to discuss this "
        "with your family, so let's talk on Wednesday to confirm if you join the trial lesson\"). "
        "Vague outcomes leave the initiative with the lead and create confusion about what happens next."
    )
    col_v1, col_v2 = st.columns([3, 2])
    mgr_stats = df_global.groupby("manager").agg(call_id=("call_id", "count"), Average_quality=("Average_quality", "mean")).reset_index()
    outcome_counts = df_global.groupby(["manager", "outcome_category"]).size().reset_index(name="count")
    defined_counts = df_global[df_global["outcome_category"] == "Defined"].groupby("manager").size()
    mgr_stats["defined_count"] = mgr_stats["manager"].map(defined_counts).fillna(0)
    mgr_stats["defined_rate"] = (mgr_stats["defined_count"] / mgr_stats["call_id"]).fillna(0)

    with col_v1:
        if not outcome_counts.empty:
            data_chart = outcome_counts[outcome_counts["outcome_category"].isin(["Defined", "Vague"])].copy()
            mgr_totals = df_global.groupby("manager")["call_id"].count().to_dict()
            data_chart["total_calls"] = data_chart["manager"].map(mgr_totals).fillna(0).astype("int64")
            fig_vague = px.bar(
                data_chart,
                x="manager",
                y="count",
                color="outcome_category",
                title="Defined vs. Vague (100% Stacked)",
                barmode="relative",
                color_discrete_map={"Defined": "#2ecc71", "Vague": "#e74c3c"},
                hover_data=["total_calls"],
            )
            fig_vague.update_layout(barnorm="percent", yaxis_title="Share (%)", xaxis_title="")
            st.plotly_chart(fig_vague, use_container_width=True)
            st.caption(
                "Defined outcomes include: lesson_scheduled, callback_scheduled, payment_pending, sold. "
                "Vague outcomes include: callback_vague and other non-committal callbacks."
            )

    with col_v2:
        lb_df = mgr_stats.sort_values("defined_rate", ascending=False).copy()
        lb_df["defined_rate_pct"] = (lb_df["defined_rate"] * 100).round(2).astype(str) + "%"
        lb_df["Avg Quality"] = lb_df["Average_quality"].round(2)
        lb_df = lb_df[["manager", "defined_rate_pct", "call_id", "Avg Quality"]]
        lb_df.columns = ["Manager", "Defined %", "Calls", "Avg Quality"]
        st.dataframe(lb_df, hide_index=True, use_container_width=True)

    st.markdown("---")

    st.header("4. Friction & Resistance")
    wtd_start = date.today() - timedelta(days=date.today().weekday())
    df_wtd = df_no_date[(df_no_date["call_date"] >= wtd_start) & (df_no_date["call_date"] <= date.today())].copy()

    if df_wtd.empty:
        st.warning("No data for current week with selected filters.")
    elif "call_type" not in df_wtd.columns or "pipeline_name" not in df_wtd.columns:
        st.warning("Not enough data for Friction & Resistance (need call_type and pipeline_name).")
    else:
        intro_prim = df_wtd[df_wtd["call_type"] == "intro_call"].groupby("pipeline_name").size()
        intro_fu = df_wtd[df_wtd["call_type"] == "intro_followup"].groupby("pipeline_name").size()
        sales_prim = df_wtd[df_wtd["call_type"] == "sales_call"].groupby("pipeline_name").size()
        sales_fu = df_wtd[df_wtd["call_type"] == "sales_followup"].groupby("pipeline_name").size()

        pipelines = df_wtd["pipeline_name"].dropna().unique()
        friction_data = []
        for p in pipelines:
            ip = int(intro_prim.get(p, 0))
            ifu = int(intro_fu.get(p, 0))
            sp = int(sales_prim.get(p, 0))
            sfu = int(sales_fu.get(p, 0))
            i_fric = ip / ifu if ifu > 0 else 0
            s_fric = sp / sfu if sfu > 0 else 0
            friction_data.append({"Pipeline": p, "Type": "Intro Friction", "Value": round(i_fric, 2), "Total Calls": ip + ifu})
            friction_data.append({"Pipeline": p, "Type": "Sales Friction", "Value": round(s_fric, 2), "Total Calls": sp + sfu})

        if friction_data:
            df_fric = pd.DataFrame(friction_data)
            col1, col2 = st.columns([2, 1])
            with col1:
                fig_friction = px.bar(
                    df_fric,
                    x="Pipeline",
                    y="Value",
                    color="Type",
                    barmode="group",
                    title="Friction Index by Pipeline (WTD)",
                    color_discrete_map={"Intro Friction": "#3498db", "Sales Friction": "#e67e22"},
                    hover_data=["Total Calls"],
                )
                fig_friction.update_layout(yaxis_title="Friction Index (Calls / Flup)", xaxis_title="")
                st.plotly_chart(fig_friction, use_container_width=True)

            with col2:
                st.metric(
                    "Avg Intro Friction (WTD)",
                    f"{df_fric[df_fric['Type'] == 'Intro Friction']['Value'].mean():.2f}",
                    help=r"$Intro\ Friction=\frac{Intro\ Calls}{Intro\ Flups}$",
                )
                st.metric(
                    "Avg Sales Friction (WTD)",
                    f"{df_fric[df_fric['Type'] == 'Sales Friction']['Value'].mean():.2f}",
                    help=r"$Sales\ Friction=\frac{Sales\ Calls}{Sales\ Flups}$",
                )

        st.subheader("Friction vs. Defined Rate (WTD)")
        df_wtd["is_primary"] = df_wtd["call_type"].isin(["intro_call", "sales_call"])
        df_wtd["is_followup"] = df_wtd["call_type"].isin(["intro_followup", "sales_followup"])
        df_wtd["is_defined_primary"] = df_wtd["is_primary"] & (df_wtd["outcome_category"] != "Vague")

        bubble_stats = (
            df_wtd.groupby(["manager", "pipeline_name", "computed_market"], dropna=False)
            .agg(
                Average_quality=("Average_quality", "mean"), 
                total_calls=("call_id", "count"),
                primaries=("is_primary", "sum"),
                followups=("is_followup", "sum"),
                defined_primaries=("is_defined_primary", "sum")
            )
            .reset_index()
        )
        bubble_stats["Average_quality"] = bubble_stats["Average_quality"].round(2)
        bubble_stats["defined_rate_pct"] = (
            (bubble_stats["defined_primaries"] / bubble_stats["primaries"]) * 100
        ).fillna(0).round(2)
        bubble_stats["friction_index"] = 0.0
        mask_f = bubble_stats["followups"] > 0
        bubble_stats.loc[mask_f, "friction_index"] = (
            bubble_stats.loc[mask_f, "primaries"] / bubble_stats.loc[mask_f, "followups"]
        ).round(2)

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
                template="plotly_white",
                size_max=60,
                color_discrete_map=market_color_map,
                labels={
                    "defined_rate_pct": "Defined Rate (%)",
                    "friction_index": "Friction Index (Calls / Flup)",
                    "total_calls": "Calls",
                    "computed_market": "Market",
                },
                hover_data=["pipeline_name", "total_calls", "Average_quality", "primaries", "followups", "defined_primaries"],
            )
            fig_bubble.add_vline(x=bubble_stats["defined_rate_pct"].mean(), line_dash="dot", annotation_text="Avg Defined")
            fig_bubble.add_hline(y=bubble_stats["friction_index"].mean(), line_dash="dot", annotation_text="Avg Friction")
            st.plotly_chart(fig_bubble, use_container_width=True)

    st.markdown("---")

    st.header("5. Discovery Depth Index")
    st.caption(
        "❓ Discovery Depth Index: Calls with no objections are not a success, they usually "
        "mean the manager failed to surface real barriers. If the lead has no objections, "
        "the manager is not in control of the deal."
    )

    if "call_type" not in df_global.columns or "main_objection_type" not in df_global.columns:
        st.warning("Not enough data for Discovery Depth Index (need call_type and main_objection_type).")
    else:
        silence_df = df_global[df_global["call_type"].isin(["intro_call", "sales_call"])].copy()

    if "call_type" in df_global.columns and "main_objection_type" in df_global.columns and not silence_df.empty:
        silence_df["is_sterile"] = silence_df["main_objection_type"].fillna("None").apply(
            lambda x: str(x).lower() in ["none", "", "nan"]
        )
        mgr_silence = (
            silence_df.groupby("manager")
            .agg(call_id=("call_id", "count"), is_sterile=("is_sterile", "sum"))
            .reset_index()
        )
        mgr_silence["sterile_rate"] = (mgr_silence["is_sterile"] / mgr_silence["call_id"] * 100).round(2)
        mgr_silence["with_objections"] = mgr_silence["call_id"] - mgr_silence["is_sterile"]

        market_quality = (
            silence_df.groupby("manager")
            .agg(
                market=("computed_market", lambda s: s.mode().iloc[0] if not s.mode().empty else "Mixed"),
                avg_quality=("Average_quality", "mean"),
            )
            .reset_index()
        )
        mgr_chart = mgr_silence.merge(market_quality, on="manager", how="left")
        chart_rows = []
        for _, row in mgr_chart.iterrows():
            chart_rows.append(
                {
                    "manager": row["manager"],
                    "Bucket": "No Objections Calls",
                    "value": row["is_sterile"],
                    "market": row["market"],
                    "avg_quality": row["avg_quality"],
                }
            )
            chart_rows.append(
                {
                    "manager": row["manager"],
                    "Bucket": "Calls With Objections",
                    "value": row["with_objections"],
                    "market": row["market"],
                    "avg_quality": row["avg_quality"],
                }
            )
        chart_df = pd.DataFrame(chart_rows)

        fig_dd = px.bar(
            chart_df,
            x="manager",
            y="value",
            color="Bucket",
            template="plotly_white",
            barmode="relative",
            labels={"value": "Share (%)"},
            hover_data=["market", "avg_quality"],
        )
        fig_dd.update_layout(barnorm="percent", yaxis_title="Share (%)", xaxis_title="", legend_title="")
        st.plotly_chart(fig_dd, use_container_width=True)

        st.subheader("No Objections Calls Rating")

        intro_calls_mgr = df_global[df_global["call_type"] == "intro_call"].groupby("manager").size()
        intro_flup_mgr = df_global[df_global["call_type"] == "intro_followup"].groupby("manager").size()
        sales_calls_mgr = df_global[df_global["call_type"] == "sales_call"].groupby("manager").size()
        sales_flup_mgr = df_global[df_global["call_type"] == "sales_followup"].groupby("manager").size()

        mgr_silence["intro_calls"] = mgr_silence["manager"].map(intro_calls_mgr).fillna(0).astype(int)
        mgr_silence["intro_flups"] = mgr_silence["manager"].map(intro_flup_mgr).fillna(0).astype(int)
        mgr_silence["sales_calls"] = mgr_silence["manager"].map(sales_calls_mgr).fillna(0).astype(int)
        mgr_silence["sales_flups"] = mgr_silence["manager"].map(sales_flup_mgr).fillna(0).astype(int)

        mgr_silence["intro_friction"] = mgr_silence.apply(
            lambda r: (r["intro_calls"] / r["intro_flups"]) if r["intro_flups"] > 0 else 0.0,
            axis=1,
        )
        mgr_silence["sales_friction"] = mgr_silence.apply(
            lambda r: (r["sales_calls"] / r["sales_flups"]) if r["sales_flups"] > 0 else 0.0,
            axis=1,
        )

        lb = mgr_silence.merge(market_quality, on="manager", how="left")
        lb = lb.sort_values("sterile_rate", ascending=False).copy()
        lb["Avg Quality"] = lb["avg_quality"].round(2)
        lb["Intro Friction"] = lb["intro_friction"].round(2)
        lb["Sales Friction"] = lb["sales_friction"].round(2)
        lb = lb[
            [
                "manager",
                "call_id",
                "is_sterile",
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

    st.markdown("---")

    with st.expander("🧰 Operational Details", expanded=False):
        tab1, tab2 = st.tabs(["⚠️ Operational Waste", "🔎 Call Inspector"])

        with tab1:
            if "call_duration_sec" in df_global.columns:
                anomalies = df_global[(df_global["call_duration_sec"] > 900) & (df_global["outcome_category"] == "Vague")].copy()
                if not anomalies.empty:
                    anomalies["duration_min"] = (anomalies["call_duration_sec"] / 60).round(1)
                    show_cols = _existing_columns(
                        anomalies,
                        ["call_datetime", "manager", "pipeline_name", "duration_min", "next_step_type", "kommo_link"],
                    )
                    st.error(f"Found {len(anomalies)} calls > 15m with Vague outcome.")
                    st.dataframe(
                        anomalies.sort_values("call_duration_sec", ascending=False)[show_cols],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.success("No operational waste detected.")
            else:
                st.warning("call_duration_sec is missing, Operational Waste block is unavailable.")

        with tab2:
            cols = _existing_columns(df_global, ["call_id", "manager", "call_date", "next_step_type"])
            if cols:
                call_options = df_global.sort_values("call_datetime", ascending=False).head(50)[cols].copy()
                call_options["label"] = call_options.apply(
                    lambda x: f"{x.get('call_date')} | {x.get('manager')} | {x.get('next_step_type')}",
                    axis=1,
                )
                selected_label = st.selectbox("Select a call:", options=call_options["label"].tolist())
                if selected_label:
                    idx = call_options[call_options["label"] == selected_label].index[0]
                    cid = call_options.loc[idx, "call_id"]
                    row = df_global[df_global["call_id"] == cid].iloc[0]
                    st.write(f"**Manager:** {row.get('manager')}")
                    st.write(f"**Outcome:** {row.get('next_step_type')}")
                    if row.get("kommo_link"):
                        st.markdown(f"[🔗 Open in Kommo]({row.get('kommo_link')})")
                    st.info(f"**Mistakes:** {row.get('mistakes_summary')}")
                    st.success(f"**Best Phrases:** {row.get('best_phrases')}")

if __name__ == "__main__":
    pass
