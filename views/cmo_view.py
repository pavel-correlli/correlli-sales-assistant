import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import fetch_view_data, rpc_df
from views.shared_ui import render_hint


def _plotly_template():
    return "plotly_dark" if st.session_state.get("ui_theme_v1", "dark") == "dark" else "plotly_white"


def _traffic_chart_bgcolor() -> str:
    return "#111111" if _plotly_template() == "plotly_dark" else "#ffffff"


def _normalize_call_id(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    s = s.str.replace(r"[{}]", "", regex=True)
    s = s.str.replace(r"^[\"']+|[\"']+$", "", regex=True)
    return s


def _entity_heatmap_colorscale(attr_type: str):
    base = _traffic_chart_bgcolor()
    t = str(attr_type or "").strip().lower()
    if t == "goal":
        return [
            (0.0, base),
            (0.12, "#0b3d2e"),
            (0.35, "#0f766e"),
            (0.65, "#22c55e"),
            (1.0, "#a3e635"),
        ]
    if t == "objection":
        return [
            (0.0, base),
            (0.12, "#0b2a4a"),
            (0.35, "#1d4ed8"),
            (0.65, "#60a5fa"),
            (1.0, "#38bdf8"),
        ]
    if t == "fear":
        return [
            (0.0, base),
            (0.12, "#3b0a1f"),
            (0.35, "#be123c"),
            (0.65, "#fb7185"),
            (1.0, "#f43f5e"),
        ]
    return "Viridis"


def _fetch_attribute_frequency_for_heatmap(
    attr_type: str,
    date_range,
    selected_markets,
    selected_pipelines,
) -> pd.DataFrame:
    date_start = date_range[0] if date_range and len(date_range) == 2 else None
    date_end = date_range[1] if date_range and len(date_range) == 2 else None
    df_rpc = rpc_df(
        "rpc_cmo_entity_frequency",
        {
            "attr_type": attr_type,
            "date_start": date_start.isoformat() if date_start else None,
            "date_end": date_end.isoformat() if date_end else None,
            "markets": selected_markets or [],
            "pipelines": selected_pipelines or [],
        },
    )
    if not df_rpc.empty:
        df_rpc.attrs["entity_source"] = "rpc_cmo_entity_frequency"
        return df_rpc

    df_calls = fetch_view_data("Algonova_Calls_Raw")
    if df_calls.empty:
        return pd.DataFrame()

    df_attrs = fetch_view_data("v_analytics_attributes_frequency")

    df_calls = df_calls.copy()

    if "pipeline_name" not in df_calls.columns or "call_id" not in df_calls.columns:
        return pd.DataFrame()
    df_calls["call_id"] = _normalize_call_id(df_calls["call_id"])
    df_calls = df_calls[df_calls["call_id"] != ""].copy()
    if df_calls.empty:
        return pd.DataFrame()

    if "call_datetime" in df_calls.columns:
        call_date = pd.to_datetime(df_calls["call_datetime"], errors="coerce", utc=True).dt.date
    elif "date" in df_calls.columns:
        call_date = pd.to_datetime(df_calls["date"], errors="coerce").dt.date
    else:
        call_date = pd.Series([pd.NaT] * len(df_calls))
    df_calls["call_date"] = call_date

    df_calls["pipeline_name"] = df_calls["pipeline_name"].astype(str).str.strip()
    market_col = df_calls["market"] if "market" in df_calls.columns else pd.Series([""] * len(df_calls))
    market_col = market_col.astype(str).str.strip()
    pipeline_col = df_calls["pipeline_name"].astype(str)
    pipeline_market = pipeline_col.str.split("|").str[0].str.split(" ").str[0].str.strip()
    df_calls["market_norm"] = market_col.where(market_col != "", pipeline_market)

    mask = pd.Series([True] * len(df_calls))
    if date_range and len(date_range) == 2:
        mask = mask & (df_calls["call_date"] >= date_range[0]) & (df_calls["call_date"] <= date_range[1])
    if selected_markets:
        mask = mask & df_calls["market_norm"].isin(selected_markets)
    if selected_pipelines:
        mask = mask & df_calls["pipeline_name"].isin(selected_pipelines)

    df_calls = df_calls[mask].copy()
    if df_calls.empty:
        return pd.DataFrame()

    agg = pd.DataFrame()
    if not df_attrs.empty:
        df_attrs = df_attrs.copy()
        if {"call_id", "attr_type", "attr_value"}.issubset(df_attrs.columns):
            df_attrs["call_id"] = _normalize_call_id(df_attrs["call_id"])
            df_attrs["attr_type"] = df_attrs["attr_type"].astype(str).str.strip()
            df_attrs["attr_value"] = df_attrs["attr_value"].astype(str).str.strip()
            if "market" in df_attrs.columns:
                df_attrs["market"] = df_attrs["market"].astype(str).str.strip()
            df_attrs = df_attrs[
                (df_attrs["attr_type"].str.lower() == str(attr_type).lower())
                & (df_attrs["attr_value"] != "")
                & (df_attrs["call_id"] != "")
            ].copy()
            if not df_attrs.empty:
                df_join = df_attrs.merge(
                    df_calls[["call_id", "pipeline_name", "market_norm"]], on="call_id", how="inner"
                )
                if not df_join.empty:
                    if selected_markets:
                        market_attr = (
                            df_join["market"] if "market" in df_join.columns else pd.Series([""] * len(df_join))
                        )
                        market_attr = market_attr.astype(str).str.strip()
                        market_final = market_attr.where(
                            market_attr != "", df_join["market_norm"].astype(str).str.strip()
                        )
                        df_join = df_join[market_final.isin(selected_markets)].copy()
                    if not df_join.empty:
                        totals = df_calls.groupby("pipeline_name")["call_id"].nunique().rename("total_calls")
                        agg = (
                            df_join.groupby(["pipeline_name", "attr_value"])
                            .agg(calls_with_attr=("call_id", "nunique"), mentions=("call_id", "size"))
                            .reset_index()
                        )
                        agg = agg.merge(totals, on="pipeline_name", how="left")
                        agg["frequency"] = (agg["calls_with_attr"] / agg["total_calls"].replace(0, pd.NA)).fillna(0.0)
                        agg.attrs["entity_source"] = "v_analytics_attributes_frequency"
                        agg.attrs["calls_in_scope"] = int(df_calls["call_id"].nunique())
                        agg.attrs["mentions_total"] = int(len(df_join))
                        agg.attrs["calls_with_any_entity"] = int(df_join["call_id"].nunique())
                        agg.attrs["unique_entities"] = int(df_join["attr_value"].nunique())

    if not agg.empty:
        return agg

    raw_map = {"Goal": "parent_goals", "Objection": "objection_list", "Fear": "parent_fears"}
    raw_col = raw_map.get(str(attr_type))
    if not raw_col or raw_col not in df_calls.columns:
        return pd.DataFrame()

    raw = df_calls[["call_id", "pipeline_name", raw_col]].copy()
    raw["attr_value"] = raw[raw_col].astype(str)
    raw["attr_value"] = raw["attr_value"].str.replace(r'[\[\]"]', "", regex=True)
    raw["attr_value"] = raw["attr_value"].str.replace("'", "", regex=False)
    raw["attr_value"] = raw["attr_value"].str.replace(",", ";", regex=False)
    raw["attr_value"] = raw["attr_value"].str.replace("\n", ";", regex=False)
    raw["attr_value"] = raw["attr_value"].str.split(";")
    raw = raw.explode("attr_value")
    raw_pre_clean = int(len(raw))

    raw["attr_value"] = raw["attr_value"].astype(str).str.strip()
    raw["attr_value"] = raw["attr_value"].str.replace(r"\s+", " ", regex=True)
    raw["attr_value"] = raw["attr_value"].str.replace(r"\s*-\s*.*$", "", regex=True)
    raw["attr_value"] = raw["attr_value"].str.replace(r"\s*:\s*.*$", "", regex=True)
    raw["attr_value"] = raw["attr_value"].str.replace(" ", "_", regex=False)
    raw["attr_value"] = raw["attr_value"].str.strip("_").str.strip()
    raw = raw[raw["attr_value"] != ""].copy()
    raw = raw[~raw["attr_value"].str.lower().isin(["nan", "none", "null"])].copy()
    if raw.empty:
        return pd.DataFrame()

    totals = df_calls.groupby("pipeline_name")["call_id"].nunique().rename("total_calls")
    agg = (
        raw.groupby(["pipeline_name", "attr_value"])
        .agg(calls_with_attr=("call_id", "nunique"), mentions=("call_id", "size"))
        .reset_index()
    )
    agg = agg.merge(totals, on="pipeline_name", how="left")
    agg["frequency"] = (agg["calls_with_attr"] / agg["total_calls"].replace(0, pd.NA)).fillna(0.0)
    agg.attrs["entity_source"] = f"Algonova_Calls_Raw.{raw_col}"
    agg.attrs["calls_in_scope"] = int(df_calls["call_id"].nunique())
    agg.attrs["mentions_total"] = int(len(raw))
    agg.attrs["mentions_pre_clean"] = int(raw_pre_clean)
    agg.attrs["mentions_removed_by_cleaning"] = int(max(raw_pre_clean - len(raw), 0))
    agg.attrs["calls_with_any_entity"] = int(raw["call_id"].nunique())
    agg.attrs["unique_entities"] = int(raw["attr_value"].nunique())
    return agg


def _render_attribute_frequency_heatmap(
    attr_type: str,
    title: str,
    colorscale,
    date_range,
    selected_markets,
    selected_pipelines,
):
    df = _fetch_attribute_frequency_for_heatmap(attr_type, date_range, selected_markets, selected_pipelines)
    if df.empty:
        st.warning(f"No data available for {attr_type} heatmap with current filters.")
        return

    df["attr_value"] = df["attr_value"].astype(str).str.strip()
    df["pipeline_name"] = df["pipeline_name"].astype(str).str.strip()
    df = df[(df["attr_value"] != "") & (df["pipeline_name"] != "")].copy()
    if df.empty:
        st.warning(f"No valid values to render {attr_type} heatmap after cleaning.")
        return

    df["mentions_per_call"] = (
        df["mentions"] / df["calls_with_attr"].replace(0, pd.NA)
    ).fillna(0.0).round(2)
    df["mentions_total_pipeline"] = df.groupby("pipeline_name")["mentions"].transform("sum")
    df["mention_share_pipeline"] = (
        df["mentions"] / df["mentions_total_pipeline"].replace(0, pd.NA)
    ).fillna(0.0)

    z = df.pivot(index="attr_value", columns="pipeline_name", values="frequency").fillna(0.0)
    calls_with_attr = df.pivot(index="attr_value", columns="pipeline_name", values="calls_with_attr").fillna(0).astype(int)
    mentions = df.pivot(index="attr_value", columns="pipeline_name", values="mentions").fillna(0).astype(int)
    total_calls = df.pivot(index="attr_value", columns="pipeline_name", values="total_calls").fillna(0).astype(int)
    mentions_per_call = df.pivot(index="attr_value", columns="pipeline_name", values="mentions_per_call").fillna(0.0)
    mention_share = df.pivot(index="attr_value", columns="pipeline_name", values="mention_share_pipeline").fillna(0.0)

    calls_with_attr = calls_with_attr.reindex(index=z.index, columns=z.columns, fill_value=0)
    mentions = mentions.reindex(index=z.index, columns=z.columns, fill_value=0)
    total_calls = total_calls.reindex(index=z.index, columns=z.columns, fill_value=0)
    mentions_per_call = mentions_per_call.reindex(index=z.index, columns=z.columns, fill_value=0.0)
    mention_share = mention_share.reindex(index=z.index, columns=z.columns, fill_value=0.0)

    zmax = float(z.values.max()) if z.size else 1.0
    zmax = min(1.0, max(0.25, zmax))

    custom = []
    for y in z.index:
        row = []
        for x in z.columns:
            row.append(
                [
                    int(calls_with_attr.loc[y, x]),
                    int(total_calls.loc[y, x]),
                    int(mentions.loc[y, x]),
                    float(mentions_per_call.loc[y, x]),
                    float(mention_share.loc[y, x]),
                ]
            )
        custom.append(row)

    st.subheader(title)
    fig = go.Figure(
        data=[
            go.Heatmap(
                z=z.values,
                x=list(z.columns),
                y=list(z.index),
                customdata=custom,
                colorscale=colorscale,
                zmin=0,
                zmax=zmax,
                showscale=True,
                colorbar=dict(title="Frequency", tickformat=".0%"),
                hovertemplate=(
                    f"{attr_type}: %{{y}}<br>"
                    "Pipeline: %{x}<br>"
                    "Calls with entity: %{customdata[0]}<br>"
                    "Total calls: %{customdata[1]}<br>"
                    "Mentions: %{customdata[2]}<br>"
                    "Mentions per call: %{customdata[3]:.2f}<br>"
                    "Share of mentions in pipeline: %{customdata[4]:.1%}<br>"
                    "Frequency: %{z:.1%}<br>"
                    "Formula: Calls with entity / Total calls<extra></extra>"
                ),
            )
        ]
    )
    fig.update_layout(
        template=_plotly_template(),
        margin=dict(l=10, r=10, t=10, b=90),
        paper_bgcolor=_traffic_chart_bgcolor(),
        plot_bgcolor=_traffic_chart_bgcolor(),
        xaxis_title="Pipeline",
        yaxis_title=attr_type,
        height=max(520, 24 * len(z.index) + 260),
    )
    fig.update_xaxes(tickangle=-35, automargin=True)
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, use_container_width=True)


def render_cmo_analytics(date_range, selected_markets, selected_pipelines):
    st.markdown("<h1 style='text-align:center;'>Traffic Quality & Viscosity</h1>", unsafe_allow_html=True)

    st.markdown("<div id='traffic-viscosity-vs-intro-friction'></div>", unsafe_allow_html=True)
    st.subheader("Traffic Viscosity vs Intro Friction")
    render_hint(
        "Viscosity means how many calls are required to process one lead (Calls / Leads). "
        "Higher viscosity usually indicates wasted touches, poor lead quality, or weak routing."
    )
    date_start = date_range[0] if len(date_range) == 2 else None
    date_end = date_range[1] if len(date_range) == 2 else None
    rpc_params = {
        "date_start": date_start.isoformat() if date_start else None,
        "date_end": date_end.isoformat() if date_end else None,
        "markets": selected_markets or [],
        "pipelines": selected_pipelines or [],
    }
    with st.spinner("Loading CMO dataset..."):
        merged_for_chart = rpc_df("rpc_cmo_viscosity_intro_friction_by_manager", rpc_params)

    if merged_for_chart.empty:
        st.warning("No data available for current filters (rpc_cmo_viscosity_intro_friction_by_manager).")
        return

    for col in ["total_calls", "total_leads", "intro_primaries", "intro_followups"]:
        if col in merged_for_chart.columns:
            merged_for_chart[col] = pd.to_numeric(merged_for_chart[col], errors="coerce").fillna(0).astype(int)
    for col in ["viscosity_index", "intro_friction_index"]:
        if col in merged_for_chart.columns:
            merged_for_chart[col] = pd.to_numeric(merged_for_chart[col], errors="coerce").fillna(0).round(2)

    long_df = merged_for_chart.melt(
        id_vars=["mkt_manager", "mkt_market", "total_calls", "total_leads", "intro_primaries", "intro_followups"],
        value_vars=["viscosity_index", "intro_friction_index"],
        var_name="metric",
        value_name="value",
    )
    long_df["metric"] = long_df["metric"].map(
        {"viscosity_index": "Viscosity Index", "intro_friction_index": "Intro Friction Index"}
    )
    long_df["mkt_market"] = long_df["mkt_market"].fillna("Unknown").astype(str).str.strip()

    fig_bar = px.bar(
        long_df,
        x="mkt_manager",
        y="value",
        color="metric",
        barmode="group",
        text="mkt_market",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        labels={"mkt_manager": "Traffic Manager", "value": "Index"},
        custom_data=["mkt_market", "total_calls", "total_leads", "intro_primaries", "intro_followups"],
    )
    fig_bar.update_traces(textposition="inside", texttemplate="%{text}")
    fig_bar.for_each_trace(
        lambda t: t.update(
            hovertemplate=(
                "Traffic Manager: %{x}<br>"
                "Market: %{customdata[0]}<br>"
                "Viscosity Index: %{y:.2f}<br>"
                "Total Calls: %{customdata[1]}<br>"
                "Total Leads: %{customdata[2]}<br>"
                "Formula: Calls / Leads<extra></extra>"
            )
            if t.name == "Viscosity Index"
            else (
                "Traffic Manager: %{x}<br>"
                "Market: %{customdata[0]}<br>"
                "Intro Friction Index: %{y:.2f}<br>"
                "Intro Primaries: %{customdata[3]}<br>"
                "Intro Followups: %{customdata[4]}<br>"
                "Total Calls: %{customdata[1]}<extra></extra>"
            )
        )
    )
    fig_bar.update_layout(xaxis_title="Traffic Manager", margin=dict(l=10, r=10, t=10, b=80))
    fig_bar.update_xaxes(tickangle=-35, automargin=True)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("<div id='intro-friction-traffic-manager'></div>", unsafe_allow_html=True)
    st.subheader("Intro Friction / Traffic Manager")
    render_hint("Intro Friction shows follow-up load on intro calls (Intro Flups / Intro Calls).")
    with st.spinner("Loading heatmap dataset..."):
        by_mm = rpc_df(
            "rpc_cmo_intro_friction_heatmap",
            {
                "date_start": date_start.isoformat() if date_start else None,
                "date_end": date_end.isoformat() if date_end else None,
                "markets": selected_markets or [],
                "pipelines": selected_pipelines or [],
            },
        )

    if by_mm.empty:
        st.warning("No heatmap data available for current filters (rpc_cmo_intro_friction_heatmap).")
        return

    by_mm["intro_calls"] = pd.to_numeric(by_mm.get("intro_calls"), errors="coerce").fillna(0).astype(int)
    by_mm["intro_flups"] = pd.to_numeric(by_mm.get("intro_flups"), errors="coerce").fillna(0).astype(int)
    if "calls_in_calc" not in by_mm.columns:
        by_mm["calls_in_calc"] = (by_mm["intro_calls"] + by_mm["intro_flups"]).astype(int)
    else:
        by_mm["calls_in_calc"] = pd.to_numeric(by_mm["calls_in_calc"], errors="coerce").fillna(0).astype(int)
    if "intro_friction_index" in by_mm.columns:
        by_mm["intro_friction_index"] = pd.to_numeric(by_mm["intro_friction_index"], errors="coerce").fillna(0).round(2)
    else:
        by_mm["intro_friction_index"] = (
            by_mm["intro_flups"] / by_mm["intro_calls"].replace(0, pd.NA)
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

    st.markdown("<div id='attribute-frequency-heatmaps'></div>", unsafe_allow_html=True)
    render_hint(
        "These heatmaps show how frequently an entity appears in calls within each pipeline "
        "(Calls with entity / Total calls)."
    )
    st.markdown("<div id='goal-heatmap'></div>", unsafe_allow_html=True)
    _render_attribute_frequency_heatmap(
        attr_type="Goal",
        title="Goal Frequency / Pipeline",
        colorscale=_entity_heatmap_colorscale("Goal"),
        date_range=date_range,
        selected_markets=selected_markets,
        selected_pipelines=selected_pipelines,
    )
    st.markdown("<div id='objection-heatmap'></div>", unsafe_allow_html=True)
    _render_attribute_frequency_heatmap(
        attr_type="Objection",
        title="Objection Frequency / Pipeline",
        colorscale=_entity_heatmap_colorscale("Objection"),
        date_range=date_range,
        selected_markets=selected_markets,
        selected_pipelines=selected_pipelines,
    )
    st.markdown("<div id='fear-heatmap'></div>", unsafe_allow_html=True)
    _render_attribute_frequency_heatmap(
        attr_type="Fear",
        title="Fear Frequency / Pipeline",
        colorscale=_entity_heatmap_colorscale("Fear"),
        date_range=date_range,
        selected_markets=selected_markets,
        selected_pipelines=selected_pipelines,
    )

    with st.expander("Entity heatmaps debug", expanded=False):
        debug_on = st.checkbox("Show debug", value=False, key="dbg_entity_heatmaps_v1")
        if debug_on:
            df_calls_dbg = fetch_view_data("Algonova_Calls_Raw")
            st.write(
                {
                    "calls_rows_loaded": int(df_calls_dbg.attrs.get("supabase_rows_loaded", len(df_calls_dbg)))
                    if not df_calls_dbg.empty
                    else 0,
                    "calls_columns": list(df_calls_dbg.columns) if not df_calls_dbg.empty else [],
                    "date_range": date_range,
                    "selected_markets": selected_markets,
                    "selected_pipelines": selected_pipelines,
                }
            )

            if not df_calls_dbg.empty and "call_id" in df_calls_dbg.columns and "pipeline_name" in df_calls_dbg.columns:
                df_calls_dbg = df_calls_dbg.copy()
                df_calls_dbg["call_id"] = _normalize_call_id(df_calls_dbg["call_id"])
                df_calls_dbg["pipeline_name"] = df_calls_dbg["pipeline_name"].astype(str).str.strip()

                if "call_datetime" in df_calls_dbg.columns:
                    df_calls_dbg["call_date"] = pd.to_datetime(
                        df_calls_dbg["call_datetime"], errors="coerce", utc=True
                    ).dt.date
                elif "date" in df_calls_dbg.columns:
                    df_calls_dbg["call_date"] = pd.to_datetime(df_calls_dbg["date"], errors="coerce").dt.date
                else:
                    df_calls_dbg["call_date"] = pd.NaT

                market_col = (
                    df_calls_dbg["market"] if "market" in df_calls_dbg.columns else pd.Series([""] * len(df_calls_dbg))
                )
                market_col = market_col.astype(str).str.strip()
                pipeline_col = df_calls_dbg["pipeline_name"].astype(str)
                pipeline_market = pipeline_col.str.split("|").str[0].str.split(" ").str[0].str.strip()
                df_calls_dbg["market_norm"] = market_col.where(market_col != "", pipeline_market)

                mask_dbg = pd.Series([True] * len(df_calls_dbg))
                if date_range and len(date_range) == 2:
                    mask_dbg = mask_dbg & (df_calls_dbg["call_date"] >= date_range[0]) & (
                        df_calls_dbg["call_date"] <= date_range[1]
                    )
                if selected_markets:
                    mask_dbg = mask_dbg & df_calls_dbg["market_norm"].isin(selected_markets)
                if selected_pipelines:
                    mask_dbg = mask_dbg & df_calls_dbg["pipeline_name"].isin(selected_pipelines)

                df_calls_dbg = df_calls_dbg[mask_dbg].copy()
                st.write({"calls_rows_after_filters": int(len(df_calls_dbg))})

                for col in ["parent_goals", "objection_list", "parent_fears"]:
                    if col not in df_calls_dbg.columns:
                        st.write({col: "missing"})
                        continue
                    s = df_calls_dbg[col].astype(str).str.strip()
                    s = s[~s.str.lower().isin(["", "nan", "none", "null"])].copy()
                    st.write({f"{col}_non_empty": int(len(s))})
                    if len(s) > 0:
                        st.dataframe(s.head(10).to_frame(name=col), hide_index=True, use_container_width=True)

            df_attrs_dbg = fetch_view_data("v_analytics_attributes_frequency")
            st.write(
                {
                    "attrs_rows_loaded": int(df_attrs_dbg.attrs.get("supabase_rows_loaded", len(df_attrs_dbg)))
                    if not df_attrs_dbg.empty
                    else 0,
                    "attrs_columns": list(df_attrs_dbg.columns) if not df_attrs_dbg.empty else [],
                }
            )
            if not df_attrs_dbg.empty and {"call_id", "attr_type", "attr_value"}.issubset(df_attrs_dbg.columns):
                df_attrs_dbg = df_attrs_dbg.copy()
                df_attrs_dbg["call_id"] = _normalize_call_id(df_attrs_dbg["call_id"])
                df_attrs_dbg["attr_type"] = df_attrs_dbg["attr_type"].astype(str).str.strip()
                df_attrs_dbg["attr_value"] = df_attrs_dbg["attr_value"].astype(str).str.strip()
                st.dataframe(
                    df_attrs_dbg["attr_type"]
                    .value_counts(dropna=False)
                    .rename("rows")
                    .reset_index()
                    .rename(columns={"index": "attr_type"}),
                    hide_index=True,
                    use_container_width=True,
                )

                calls_ids = (
                    set(df_calls_dbg["call_id"].dropna().astype(str).tolist())
                    if "df_calls_dbg" in locals() and not df_calls_dbg.empty
                    else set()
                )
                for t in ["Goal", "Objection", "Fear"]:
                    ids_t = set(
                        df_attrs_dbg[df_attrs_dbg["attr_type"].str.lower() == t.lower()]["call_id"]
                        .dropna()
                        .astype(str)
                        .tolist()
                    )
                    st.write({f"attrs_call_id_intersection_{t}": int(len(calls_ids & ids_t))})

            st.markdown("---")
            st.markdown("**Entity volume (used in heatmaps for current filters)**")
            for t in ["Goal", "Objection", "Fear"]:
                df_calc = _fetch_attribute_frequency_for_heatmap(t, date_range, selected_markets, selected_pipelines)
                if df_calc.empty:
                    st.write({"attr_type": t, "rows": 0})
                    continue

                st.write(
                    {
                        "attr_type": t,
                        "entity_source": df_calc.attrs.get("entity_source"),
                        "calls_in_scope": int(df_calc.attrs.get("calls_in_scope", 0)),
                        "mentions_total": int(df_calc.attrs.get("mentions_total", int(df_calc["mentions"].sum()))),
                        "mentions_pre_clean": df_calc.attrs.get("mentions_pre_clean"),
                        "mentions_removed_by_cleaning": df_calc.attrs.get("mentions_removed_by_cleaning"),
                        "calls_with_any_entity": int(df_calc.attrs.get("calls_with_any_entity", 0)),
                        "unique_entities": int(df_calc.attrs.get("unique_entities", df_calc["attr_value"].nunique())),
                        "rows_in_heatmap_table": int(len(df_calc)),
                    }
                )

                top = df_calc.sort_values("mentions", ascending=False).head(25)[
                    ["attr_value", "pipeline_name", "mentions", "calls_with_attr", "total_calls", "frequency"]
                ]
                st.dataframe(top, hide_index=True, use_container_width=True)
