import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import fetch_view_data, rpc_df
from i18n import market_label, pipeline_label, t
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
    t0 = str(attr_type or "").strip().lower()
    if t0 == "goal":
        return [(0.0, base), (0.12, "#0b3d2e"), (0.35, "#0f766e"), (0.65, "#22c55e"), (1.0, "#a3e635")]
    if t0 == "objection":
        return [(0.0, base), (0.12, "#0b2a4a"), (0.35, "#1d4ed8"), (0.65, "#60a5fa"), (1.0, "#38bdf8")]
    if t0 == "fear":
        return [(0.0, base), (0.12, "#3b0a1f"), (0.35, "#be123c"), (0.65, "#fb7185"), (1.0, "#f43f5e")]
    return "Viridis"


def _fetch_attribute_frequency_for_heatmap(attr_type: str, date_range, selected_markets, selected_pipelines) -> pd.DataFrame:
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
    if not df_attrs.empty and {"call_id", "attr_type", "attr_value"}.issubset(df_attrs.columns):
        df_attrs = df_attrs.copy()
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
            df_join = df_attrs.merge(df_calls[["call_id", "pipeline_name", "market_norm"]], on="call_id", how="inner")
            if not df_join.empty:
                if selected_markets:
                    market_attr = df_join["market"] if "market" in df_join.columns else pd.Series([""] * len(df_join))
                    market_attr = market_attr.astype(str).str.strip()
                    market_final = market_attr.where(market_attr != "", df_join["market_norm"].astype(str).str.strip())
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

    if agg.empty:
        return pd.DataFrame()
    return agg


def _render_attribute_frequency_heatmap(attr_type: str, title: str, colorscale, date_range, selected_markets, selected_pipelines):
    df = _fetch_attribute_frequency_for_heatmap(attr_type, date_range, selected_markets, selected_pipelines)
    if df.empty:
        st.warning(t("cmo.no_data_heatmap_attr", attr_type=attr_type))
        return

    df["attr_value"] = df["attr_value"].astype(str).str.strip()
    df["pipeline_name"] = df["pipeline_name"].astype(str).str.strip()
    df = df[(df["attr_value"] != "") & (df["pipeline_name"] != "")].copy()
    if df.empty:
        st.warning(t("cmo.no_valid_values_attr", attr_type=attr_type))
        return

    df["pipeline_display"] = df["pipeline_name"].apply(pipeline_label)
    df["mentions_per_call"] = (df["mentions"] / df["calls_with_attr"].replace(0, pd.NA)).fillna(0.0).round(2)
    df["mentions_total_pipeline"] = df.groupby("pipeline_display")["mentions"].transform("sum")
    df["mention_share_pipeline"] = (df["mentions"] / df["mentions_total_pipeline"].replace(0, pd.NA)).fillna(0.0)

    z = df.pivot(index="attr_value", columns="pipeline_display", values="frequency").fillna(0.0)
    calls_with_attr = df.pivot(index="attr_value", columns="pipeline_display", values="calls_with_attr").fillna(0).astype(int)
    mentions = df.pivot(index="attr_value", columns="pipeline_display", values="mentions").fillna(0).astype(int)
    total_calls = df.pivot(index="attr_value", columns="pipeline_display", values="total_calls").fillna(0).astype(int)
    mentions_per_call = df.pivot(index="attr_value", columns="pipeline_display", values="mentions_per_call").fillna(0.0)
    mention_share = df.pivot(index="attr_value", columns="pipeline_display", values="mention_share_pipeline").fillna(0.0)

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
                colorbar=dict(title=t("label.frequency"), tickformat=".0%"),
                hovertemplate=(
                    f"{attr_type}: %{{y}}<br>"
                    f"{t('label.funnel')}: "+"%{x}<br>"
                    f"{t('cmo.calls_with_entity')}: "+"%{customdata[0]}<br>"
                    "Всего звонков: %{customdata[1]}<br>"
                    f"{t('cmo.mentions')}: "+"%{customdata[2]}<br>"
                    f"{t('cmo.mentions_per_call')}: "+"%{customdata[3]:.2f}<br>"
                    f"{t('cmo.share_mentions_funnel')}: "+"%{customdata[4]:.1%}<br>"
                    f"{t('label.frequency')}: "+"%{z:.1%}<br>"
                    f"{t('cmo.formula_frequency')}<extra></extra>"
                ),
            )
        ]
    )
    fig.update_layout(
        template=_plotly_template(),
        margin=dict(l=10, r=10, t=10, b=90),
        paper_bgcolor=_traffic_chart_bgcolor(),
        plot_bgcolor=_traffic_chart_bgcolor(),
        xaxis_title=t("label.funnel"),
        yaxis_title=attr_type,
        height=max(520, 24 * len(z.index) + 260),
    )
    fig.update_xaxes(tickangle=-35, automargin=True)
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, use_container_width=True)


def render_cmo_analytics(date_range, selected_markets, selected_pipelines):
    st.markdown(f"<h1 style='text-align:center;'>{t('cmo.title')}</h1>", unsafe_allow_html=True)
    st.markdown("<div id='traffic-viscosity-vs-intro-friction'></div>", unsafe_allow_html=True)
    st.subheader(t("cmo.section.traffic_visc"))
    render_hint(t("cmo.hint.traffic_visc"))

    date_start = date_range[0] if len(date_range) == 2 else None
    date_end = date_range[1] if len(date_range) == 2 else None
    rpc_params = {
        "date_start": date_start.isoformat() if date_start else None,
        "date_end": date_end.isoformat() if date_end else None,
        "markets": selected_markets or [],
        "pipelines": selected_pipelines or [],
    }
    with st.spinner(t("cmo.loading_dataset")):
        merged_for_chart = rpc_df("rpc_cmo_viscosity_intro_friction_by_manager", rpc_params)

    if merged_for_chart.empty:
        st.warning(t("cmo.no_data_dataset"))
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
    long_df["metric"] = long_df["metric"].map({"viscosity_index": t("cmo.viscosity_index"), "intro_friction_index": t("cmo.intro_friction_index")})
    long_df["mkt_market"] = long_df["mkt_market"].fillna(t("cmo.unknown")).astype(str).str.strip()
    long_df["mkt_market_display"] = long_df["mkt_market"].apply(market_label)

    fig_bar = px.bar(
        long_df,
        x="mkt_manager",
        y="value",
        color="metric",
        barmode="group",
        text="mkt_market_display",
        template=_plotly_template(),
        pattern_shape_sequence=[""],
        labels={"mkt_manager": t("cmo.traffic_manager"), "value": t("cmo.index")},
        custom_data=["mkt_market_display", "total_calls", "total_leads", "intro_primaries", "intro_followups"],
    )
    fig_bar.update_traces(textposition="inside", texttemplate="%{text}")
    fig_bar.for_each_trace(
        lambda tr: tr.update(
            hovertemplate=(
                f"{t('cmo.traffic_manager')}: "+"%{x}<br>"
                f"{t('label.market')}: "+"%{customdata[0]}<br>"
                f"{t('cmo.viscosity_index')}: "+"%{y:.2f}<br>"
                f"{t('cmo.total_calls')}: "+"%{customdata[1]}<br>"
                f"{t('cmo.total_leads')}: "+"%{customdata[2]}<br>"
                "Формула: Звонки / Лиды<extra></extra>"
            )
            if tr.name == t("cmo.viscosity_index")
            else (
                f"{t('cmo.traffic_manager')}: "+"%{x}<br>"
                f"{t('label.market')}: "+"%{customdata[0]}<br>"
                f"{t('cmo.intro_friction_index')}: "+"%{y:.2f}<br>"
                f"{t('cmo.intro_primaries')}: "+"%{customdata[3]}<br>"
                f"{t('cmo.intro_followups')}: "+"%{customdata[4]}<br>"
                f"{t('cmo.total_calls')}: "+"%{customdata[1]}<extra></extra>"
            )
        )
    )
    fig_bar.update_layout(xaxis_title=t("cmo.traffic_manager"), margin=dict(l=10, r=10, t=10, b=80))
    fig_bar.update_xaxes(tickangle=-35, automargin=True)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("<div id='intro-friction-traffic-manager'></div>", unsafe_allow_html=True)
    st.subheader(t("cmo.section.intro_friction"))
    render_hint(t("cmo.hint.intro_friction"))
    with st.spinner(t("cmo.loading_heatmap")):
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
        st.warning(t("cmo.no_data_heatmap"))
        return

    by_mm["intro_calls"] = pd.to_numeric(by_mm.get("intro_calls"), errors="coerce").fillna(0).astype(int)
    by_mm["intro_flups"] = pd.to_numeric(by_mm.get("intro_flups"), errors="coerce").fillna(0).astype(int)
    by_mm["calls_in_calc"] = pd.to_numeric(by_mm.get("calls_in_calc"), errors="coerce").fillna(0).astype(int) if "calls_in_calc" in by_mm.columns else (by_mm["intro_calls"] + by_mm["intro_flups"]).astype(int)
    by_mm["intro_friction_index"] = pd.to_numeric(by_mm.get("intro_friction_index"), errors="coerce").fillna(0).round(2)
    by_mm["mkt_market"] = by_mm["mkt_market"].astype(str).str.strip()
    by_mm["mkt_manager"] = by_mm["mkt_manager"].astype(str).str.strip()
    by_mm = by_mm[(~by_mm["mkt_market"].isin({"", "Unknown", "0", "nan", "None"})) & (~by_mm["mkt_manager"].isin({"", "0", "nan", "None"}))].copy()
    if by_mm.empty:
        st.warning(t("cmo.no_valid_market_manager"))
        return

    by_mm["mkt_market_display"] = by_mm["mkt_market"].apply(market_label)
    friction = by_mm.pivot(index="mkt_market_display", columns="mkt_manager", values="intro_friction_index").fillna(0)
    calls = by_mm.pivot(index="mkt_market_display", columns="mkt_manager", values="intro_calls").fillna(0).astype(int)
    flups = by_mm.pivot(index="mkt_market_display", columns="mkt_manager", values="intro_flups").fillna(0).astype(int)
    calls_in_calc = by_mm.pivot(index="mkt_market_display", columns="mkt_manager", values="calls_in_calc").fillna(0).astype(int)
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
                colorbar=dict(title=t("cmo.intro_friction"), tickformat=".2f"),
                hovertemplate=(
                    f"{t('label.market')}: "+"%{y}<br>"
                    f"{t('cmo.traffic_manager')}: "+"%{x}<br>"
                    f"{t('cmo.intro_primaries')}: "+"%{customdata[0]}<br>"
                    f"{t('cmo.intro_followups')}: "+"%{customdata[1]}<br>"
                    "Звонков в расчете: %{customdata[2]}<br>"
                    f"{t('cmo.intro_friction')}: "+"%{z:.2f}<br>"
                    "Формула: Повторные звонки / Первичные звонки<extra></extra>"
                ),
            )
        ]
    )
    fig_hm.update_layout(
        template=_plotly_template(),
        margin=dict(l=10, r=10, t=10, b=90),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title=t("cmo.traffic_manager"),
        yaxis_title=t("label.market"),
        height=max(480, 28 * len(friction.index) + 220),
    )
    fig_hm.update_xaxes(tickangle=-35, automargin=True)
    fig_hm.update_yaxes(automargin=True)
    st.plotly_chart(fig_hm, use_container_width=True)

    st.markdown("<div id='attribute-frequency-heatmaps'></div>", unsafe_allow_html=True)
    render_hint(t("cmo.section.entity_heatmaps_hint"))
    st.markdown("<div id='goal-heatmap'></div>", unsafe_allow_html=True)
    _render_attribute_frequency_heatmap("Goal", t("cmo.section.goal"), _entity_heatmap_colorscale("Goal"), date_range, selected_markets, selected_pipelines)
    st.markdown("<div id='objection-heatmap'></div>", unsafe_allow_html=True)
    _render_attribute_frequency_heatmap("Objection", t("cmo.section.objection"), _entity_heatmap_colorscale("Objection"), date_range, selected_markets, selected_pipelines)
    st.markdown("<div id='fear-heatmap'></div>", unsafe_allow_html=True)
    _render_attribute_frequency_heatmap("Fear", t("cmo.section.fear"), _entity_heatmap_colorscale("Fear"), date_range, selected_markets, selected_pipelines)

