import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Strategic Intelligence Radar",
    layout="wide"
)
@st.cache_resource
def init_connection():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

supabase = init_connection()


MARKETS_ALLOWED = ["CZ", "RUK", "SK"]

# ------------------------------------------------------------------
# DATA
# ------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_data():
    resp = (
        supabase
        .table("v_sales_performance_metrics")
        .select("*")
        .limit(10000)
        .execute()
    )

    df = pd.DataFrame(resp.data)

    if df.empty:
        return df

    # --- strict filtering
    df = df[df["market"].isin(MARKETS_ALLOWED)]

    # --- typing
    df["call_date"] = pd.to_datetime(df["call_date"])
    numeric_cols = [
        "quality_score",
        "viscosity_index",
        "intro_friction",
        "sales_friction",
        "total_calls",
        "vague_calls",
        "not_interested_calls",
        "intro_calls",
        "intro_followups",
        "sales_calls",
        "sales_followups",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ------------------------------------------------------------------
# UI: STRATEGIC CONTROL PANEL
# ------------------------------------------------------------------
st.sidebar.title("Strategic Control")

scale = st.sidebar.selectbox(
    "Analysis Scale",
    ["Day", "Week", "Month"]
)

analysis_start = st.sidebar.date_input(
    "Analysis Start Date",
    datetime.today() - relativedelta(days=14)
)

reference_start = st.sidebar.date_input(
    "Reference Start Date",
    datetime.today() - relativedelta(days=28)
)

WINDOW_MAP = {
    "Day": relativedelta(days=1),
    "Week": relativedelta(weeks=1),
    "Month": relativedelta(months=1),
}

analysis_end = analysis_start + WINDOW_MAP[scale]
reference_end = reference_start + WINDOW_MAP[scale]

# ------------------------------------------------------------------
# LOAD DATA
# ------------------------------------------------------------------
df = load_data()

st.title("🦅 Strategic Intelligence Radar")

if df.empty:
    st.warning("No data available")
    st.stop()

# ------------------------------------------------------------------
# MARKET LOOP
# ------------------------------------------------------------------
for market in MARKETS_ALLOWED:
    st.markdown(f"## Market Dynamics: {market}")

    df_m = df[df["market"] == market]

    cur = df_m[
        (df_m["call_date"] >= pd.to_datetime(analysis_start)) &
        (df_m["call_date"] < pd.to_datetime(analysis_end))
    ]

    ref = df_m[
        (df_m["call_date"] >= pd.to_datetime(reference_start)) &
        (df_m["call_date"] < pd.to_datetime(reference_end))
    ]

    # --------------------------------------------------------------
    # KPI PULSE
    # --------------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)

    def kpi(col, label):
        cur_v = cur[col].mean()
        ref_v = ref[col].mean()
        delta = cur_v - ref_v
        return cur_v, delta

    with c1:
        v, d = kpi("quality_score", "Quality")
        st.metric("Avg Quality", f"{v:.2f}", f"{d:+.2f}")

    with c2:
        v, d = kpi("viscosity_index", "Viscosity")
        st.metric("Viscosity Index", f"{v:.2%}", f"{d:+.2%}")

    with c3:
        v, d = kpi("intro_friction", "Intro Friction")
        st.metric("Intro Friction", f"{v:.2f}", f"{d:+.2f}")

    with c4:
        v, d = kpi("sales_friction", "Sales Friction")
        st.metric("Sales Friction", f"{v:.2f}", f"{d:+.2f}")

    # --------------------------------------------------------------
    # OUTCOME PRECISION (100% BASELINE)
    # --------------------------------------------------------------
    ref_calls = ref["total_calls"].sum()
    cur_calls = cur["total_calls"].sum()

    if ref_calls == 0:
        st.info("Not enough reference data")
        continue

    bar = go.Figure()

    bar.add_bar(
        name="Reference",
        x=["Total Calls"],
        y=[100]
    )

    bar.add_bar(
        name="Current",
        x=["Total Calls"],
        y=[(cur_calls / ref_calls) * 100]
    )

    bar.update_layout(
        height=300,
        yaxis_title="% vs Reference",
        barmode="group"
    )

    st.plotly_chart(bar, use_container_width=True)

    # --------------------------------------------------------------
    # RHYTHM LINE
    # --------------------------------------------------------------
    rhythm = (
        df_m
        .set_index("call_date")
        .resample("D")
        .sum(numeric_only=True)
        .reset_index()
    )

    fig = go.Figure()

    fig.add_scatter(
        x=rhythm["call_date"],
        y=rhythm["intro_calls"],
        mode="lines",
        name="Intro — Fresh",
        line=dict(color="green")
    )

    fig.add_scatter(
        x=rhythm["call_date"],
        y=rhythm["intro_followups"],
        mode="lines",
        name="Intro — Follow-up",
        line=dict(color="green", dash="dot")
    )

    fig.add_scatter(
        x=rhythm["call_date"],
        y=rhythm["sales_calls"],
        mode="lines",
        name="Sales — Fresh",
        line=dict(color="orange")
    )

    fig.add_scatter(
        x=rhythm["call_date"],
        y=rhythm["sales_followups"],
        mode="lines",
        name="Sales — Follow-up",
        line=dict(color="orange", dash="dot")
    )

    fig.update_layout(
        height=350,
        margin=dict(t=30),
        showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

# ------------------------------------------------------------------
# FOOTER
# ------------------------------------------------------------------
st.caption(
    f"Last sync: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
)
