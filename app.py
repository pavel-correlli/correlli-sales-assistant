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

MARKETS_ALLOWED = ["CZ", "RUK", "SK"]

# ------------------------------------------------------------------
# SUPABASE
# ------------------------------------------------------------------
@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

# ------------------------------------------------------------------
# DATA
# ------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_data():
    supabase = get_supabase()

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

    df = df[df["market"].isin(MARKETS_ALLOWED)]

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
# UI: SIDEBAR
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

    c1, c2, c3, c4 = st.columns(4)

    def kpi(col):
        return cur[col].mean(), cur[col].mean() - ref[col].mean()

    with c1:
        v, d = kpi("quality_score")
        st.metric("Avg Quality", f"{v:.2f}", f"{d:+.2f}")

    with c2:
        v, d = kpi("viscosity_index")
        st.metric("Viscosity Index", f"{v:.2%}", f"{d:+.2%}")

    with c3:
        v, d = kpi("intro_friction")
        st.metric("Intro Friction", f"{v:.2f}", f"{d:+.2f}")

    with c4:
        v, d = kpi("sales_friction")
        st.metric("Sales Friction", f"{v:.2f}", f"{d:+.2f}")

    ref_calls = ref["total_calls"].sum()
    cur_calls = cur["total_calls"].sum()

    if ref_calls > 0:
        fig = go.Figure()
        fig.add_bar(name="Reference", x=["Total Calls"], y=[100])
        fig.add_bar(name="Current", x=["Total Calls"], y=[(cur_calls / ref_calls) * 100])
        fig.update_layout(height=300, yaxis_title="% vs Reference", barmode="group")
        st.plotly_chart(fig, use_container_width=True)

    rhythm = (
        df_m
        .set_index("call_date")
        .resample("D")
        .sum(numeric_only=True)
        .reset_index()
    )

    fig = go.Figure()
    fig.add_scatter(x=rhythm["call_date"], y=rhythm["intro_calls"], mode="lines", name="Intro Fresh")
    fig.add_scatter(x=rhythm["call_date"], y=rhythm["intro_followups"], mode="lines", name="Intro Follow-up")
    fig.add_scatter(x=rhythm["call_date"], y=rhythm["sales_calls"], mode="lines", name="Sales Fresh")
    fig.add_scatter(x=rhythm["call_date"], y=rhythm["sales_followups"], mode="lines", name="Sales Follow-up")
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

# ------------------------------------------------------------------
# FOOTER
# ------------------------------------------------------------------
st.caption(f"Last sync: {datetime.utcnow():%Y-%m-%d %H:%M UTC}")
