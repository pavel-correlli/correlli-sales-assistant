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


def _get_smart_yesterday(today: date) -> date:
    if today.weekday() == 0:
        return today - timedelta(days=3)
    return today - timedelta(days=1)


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

    st.header("1. Daily Operations Feed")
    smart_yesterday = _get_smart_yesterday(date.today())
    st.info(f"Внимание: данные за {smart_yesterday}, игнорируя общие фильтры дат.")

    df_ops = df_no_date[df_no_date["call_date"] == smart_yesterday].copy()

    if df_ops.empty:
        st.warning("Нет данных за выбранный день по текущим фильтрам.")
    else:
        ops_cols = st.columns(4)
        total_calls_y = int(df_ops["call_id"].count()) if "call_id" in df_ops.columns else int(len(df_ops))
        intro_calls_y = int(df_ops[df_ops["call_type"].isin(["intro_call", "intro_followup"])].shape[0]) if "call_type" in df_ops.columns else 0
        sales_calls_y = int(df_ops[df_ops["call_type"].isin(["sales_call", "sales_followup"])].shape[0]) if "call_type" in df_ops.columns else 0
        avg_quality_y = float(df_ops["Average_quality"].mean()) if "Average_quality" in df_ops.columns else float("nan")

        with ops_cols[0]:
            st.metric("Total Calls Yesterday", f"{total_calls_y}")
        with ops_cols[1]:
            st.metric("Intro (Total)", f"{intro_calls_y}")
        with ops_cols[2]:
            st.metric("Sales (Total)", f"{sales_calls_y}")
        with ops_cols[3]:
            if pd.isna(avg_quality_y):
                st.metric("Avg Quality", "—")
            else:
                st.metric("Avg Quality", f"{avg_quality_y:.2f}")

        if "call_duration_sec" in df_ops.columns and "manager" in df_ops.columns:
            mgr_minutes = (
                df_ops.groupby("manager", dropna=False)["call_duration_sec"]
                .sum()
                .div(60)
                .reset_index(name="total_minutes")
                .sort_values("total_minutes", ascending=False)
            )
            fig_ops = px.bar(
                mgr_minutes,
                y="manager",
                x="total_minutes",
                orientation="h",
                title="Talk Time Yesterday (Minutes) by Manager",
                template="plotly_white",
            )
            fig_ops.update_layout(yaxis_title="", xaxis_title="Minutes")
            st.plotly_chart(fig_ops, use_container_width=True)

        if "pipeline_name" in df_ops.columns:
            calls_by_pipeline = (
                df_ops["pipeline_name"]
                .fillna("Unknown")
                .value_counts()
                .reset_index()
                .rename(columns={"index": "pipeline_name", "pipeline_name": "calls"})
            )
            calls_by_pipeline = calls_by_pipeline.head(10)
            fig_pipe = px.bar(
                calls_by_pipeline,
                x="calls",
                y="pipeline_name",
                orientation="h",
                title="Total Calls Yesterday by Pipeline (Top 10)",
                template="plotly_white",
            )
            fig_pipe.update_layout(yaxis_title="", xaxis_title="Calls")
            st.plotly_chart(fig_pipe, use_container_width=True)

        tab_a, tab_b = st.tabs(["🚨 Critical Anomalies", "⚠️ Low Quality Calls"])

        with tab_a:
            if "call_duration_sec" in df_ops.columns and "next_step_type" in df_ops.columns:
                anomalies = df_ops[
                    (df_ops["call_duration_sec"] > 600)
                    & df_ops["next_step_type"].apply(_is_callback_vague)
                ].copy()
                anomalies["duration_min"] = (anomalies["call_duration_sec"] / 60).round(1)
                show_cols = _existing_columns(
                    anomalies,
                    ["call_datetime", "manager", "pipeline_name", "duration_min", "next_step_type", "kommo_link"],
                )
                if anomalies.empty:
                    st.success("Нет критических аномалий за вчера.")
                else:
                    st.dataframe(
                        anomalies.sort_values("call_duration_sec", ascending=False)[show_cols],
                        use_container_width=True,
                        hide_index=True,
                    )
            elif "call_duration_sec" not in df_ops.columns:
                st.warning("call_duration_sec отсутствует в данных — аномалии по длительности недоступны.")
            else:
                st.warning("next_step_type отсутствует в данных — аномалии по callback_vague недоступны.")

        with tab_b:
            if "Average_quality" in df_ops.columns:
                low_q = df_ops[df_ops["Average_quality"] < 4.0].copy()
                show_cols = _existing_columns(
                    low_q,
                    ["call_datetime", "manager", "pipeline_name", "Average_quality", "kommo_link"],
                )
                if low_q.empty:
                    st.success("Нет звонков с низким качеством за вчера.")
                else:
                    st.dataframe(
                        low_q.sort_values("Average_quality", ascending=True)[show_cols],
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.warning("Average_quality отсутствует в данных — фильтр качества недоступен.")

    st.markdown("---")

    st.header("2. Manager Productivity Timeline")
    if "call_duration_sec" not in df_global.columns or "manager" not in df_global.columns:
        st.warning("Недостаточно данных для построения таймлайна (нужны manager и call_duration_sec).")
    else:
        timeline = df_global.dropna(subset=["manager", "call_date"]).copy()
        timeline["call_duration_sec"] = pd.to_numeric(timeline["call_duration_sec"], errors="coerce").fillna(0)

        daily = (
            timeline.groupby(["call_date", "manager", "computed_market"], dropna=False)
            .agg(
                total_minutes=("call_duration_sec", lambda s: float(s.sum()) / 60.0),
                total_calls=("call_id", "count"),
                intro_calls=("call_type", lambda s: int((s == "intro_call").sum())),
                followup_calls=("call_type", lambda s: int(s.isin(["intro_followup", "sales_followup"]).sum())),
                avg_quality=("Average_quality", "mean"),
                anomalies_15m=("call_duration_sec", lambda s: int((s > 900).sum())),
            )
            .reset_index()
        )
        daily["total_minutes"] = daily["total_minutes"].fillna(0)
        daily["avg_quality"] = daily["avg_quality"].fillna(0)

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
                        ["computed_market", "total_minutes", "total_calls", "intro_calls", "followup_calls", "avg_quality", "anomalies_15m"]
                    ].to_numpy(),
                    hovertemplate=(
                        "Date: %{x}<br>"
                        "Manager: %{fullData.name} (%{customdata[0]})<br>"
                        "Talk Time: %{customdata[1]:.0f} min<br>"
                        "Calls: %{customdata[2]} (Intro: %{customdata[3]} | FU: %{customdata[4]})<br>"
                        "Avg Quality: %{customdata[5]:.2f}<br>"
                        "Anomalies >15m: %{customdata[6]}<extra></extra>"
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

    st.header("3. Dialogue Steering Control")
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

    with col_v2:
        lb_df = mgr_stats.sort_values("defined_rate", ascending=False).copy()
        lb_df["defined_rate_pct"] = (lb_df["defined_rate"] * 100).round(2).astype(str) + "%"
        lb_df["Avg Quality"] = lb_df["Average_quality"].round(2)
        lb_df = lb_df[["manager", "defined_rate_pct", "call_id", "Avg Quality"]]
        lb_df.columns = ["Manager", "Defined %", "Calls", "Avg Quality"]
        st.dataframe(lb_df, hide_index=True, use_container_width=True)

    st.markdown("---")

    st.header("4. Week-to-Date (WTD) Efficiency")
    wtd_start = date.today() - timedelta(days=date.today().weekday())
    df_wtd = df_no_date[(df_no_date["call_date"] >= wtd_start) & (df_no_date["call_date"] <= date.today())].copy()

    if df_wtd.empty:
        st.warning("Нет данных за текущую неделю по текущим фильтрам.")
    elif "call_type" not in df_wtd.columns or "pipeline_name" not in df_wtd.columns:
        st.warning("Недостаточно данных для расчета WTD метрик (нужны call_type и pipeline_name).")
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
            i_fric = ifu / ip if ip > 0 else 0
            s_fric = sfu / sp if sp > 0 else 0
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
                fig_friction.update_layout(yaxis_title="Friction Index (Follow-ups / Primary)", xaxis_title="")
                st.plotly_chart(fig_friction, use_container_width=True)

            with col2:
                st.metric(
                    "Avg Intro Friction (WTD)",
                    f"{df_fric[df_fric['Type'] == 'Intro Friction']['Value'].mean():.2f}",
                    help=r"$Intro\ Friction=\frac{Intro\ Followups}{Intro\ Primaries}$",
                )
                st.metric(
                    "Avg Sales Friction (WTD)",
                    f"{df_fric[df_fric['Type'] == 'Sales Friction']['Value'].mean():.2f}",
                    help=r"$Friction=\frac{Followups}{Primaries}$",
                )

        st.subheader("Friction vs. Defined Rate (WTD)")
        bubble_stats = (
            df_wtd.groupby(["manager", "pipeline_name", "computed_market"], dropna=False)
            .agg(Average_quality=("Average_quality", "mean"), total_calls=("call_id", "count"))
            .reset_index()
        )
        bubble_stats["Average_quality"] = bubble_stats["Average_quality"].round(2)

        def get_mgr_pipe_defined(row):
            sub = df_wtd[(df_wtd["manager"] == row["manager"]) & (df_wtd["pipeline_name"] == row["pipeline_name"])].copy()
            prim = sub[sub["call_type"].isin(["intro_call", "sales_call"])]
            if len(prim) == 0:
                return 0
            non_vague = prim[prim["outcome_category"] != "Vague"]
            return len(non_vague) / len(prim)

        def get_mgr_pipe_friction(row):
            sub = df_wtd[(df_wtd["manager"] == row["manager"]) & (df_wtd["pipeline_name"] == row["pipeline_name"])]
            prim = len(sub[sub["call_type"].isin(["intro_call", "sales_call"])])
            fu = len(sub[sub["call_type"].isin(["intro_followup", "sales_followup"])])
            return fu / prim if prim > 0 else 0

        bubble_stats["defined_rate_pct"] = (bubble_stats.apply(get_mgr_pipe_defined, axis=1) * 100).round(2)
        bubble_stats["friction_index"] = bubble_stats.apply(get_mgr_pipe_friction, axis=1).round(2)

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
                    "friction_index": "Friction Index (FU / Primary)",
                    "total_calls": "Calls",
                    "computed_market": "Market",
                },
                hover_data=["pipeline_name", "total_calls", "Average_quality", "defined_rate_pct", "friction_index"],
            )
            fig_bubble.add_vline(x=bubble_stats["defined_rate_pct"].mean(), line_dash="dot", annotation_text="Avg Defined")
            fig_bubble.add_hline(y=bubble_stats["friction_index"].mean(), line_dash="dot", annotation_text="Avg Friction")
            st.plotly_chart(fig_bubble, use_container_width=True)

    st.markdown("---")

    st.header("5. Discovery Depth Index")
    st.info(
        "Note: Отсутствие возражений (Objections = None) — это не успех, а провал этапа Discovery. "
        "Если менеджер не выявил барьеры, он не управляет сделкой."
    )

    if "call_type" not in df_global.columns or "main_objection_type" not in df_global.columns:
        st.warning("Недостаточно данных для расчета Discovery Depth Index (нужны call_type и main_objection_type).")
    else:
        silence_df = df_global[df_global["call_type"].isin(["intro_call", "sales_call"])].copy()
    if "call_type" in df_global.columns and "main_objection_type" in df_global.columns and not silence_df.empty:
        silence_df["is_sterile"] = silence_df["main_objection_type"].fillna("None").apply(
            lambda x: str(x).lower() in ["none", "", "nan"]
        )
        mgr_silence = silence_df.groupby("manager").agg(call_id=("call_id", "count"), is_sterile=("is_sterile", "sum")).reset_index()
        mgr_silence["sterile_rate"] = (mgr_silence["is_sterile"] / mgr_silence["call_id"] * 100).round(2)

        total_calls = int(mgr_silence["call_id"].sum())
        total_sterile = int(mgr_silence["is_sterile"].sum())
        fig_waterfall = go.Figure(
            go.Waterfall(
                name="Discovery Depth",
                orientation="v",
                measure=["relative", "relative"],
                x=["Total Calls", "Sterile (No Obj)"],
                textposition="outside",
                text=[f"{total_calls}", f"{total_sterile}"],
                y=[total_calls, -total_sterile],
                connector={"line": {"color": "rgb(63, 63, 63)"}},
            )
        )
        fig_waterfall.update_layout(title="Sterile Calls Volume", showlegend=False)
        st.plotly_chart(fig_waterfall, use_container_width=True)

        st.subheader("Manager Sterile Ratio Leaderboard")
        silent_lb = mgr_silence.sort_values("sterile_rate", ascending=False).copy()
        silent_lb.columns = ["Manager", "Total Calls", "Sterile Calls", "Sterile Rate %"]
        st.dataframe(silent_lb, hide_index=True, use_container_width=True)

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
                st.warning("call_duration_sec отсутствует в данных — блок Operational Waste недоступен.")

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
