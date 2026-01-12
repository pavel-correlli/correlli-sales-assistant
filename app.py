import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, timedelta

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

    res = supabase.table("v_sales_performance_metrics").select("*").execute()
    df = pd.DataFrame(res.data)

    if df.empty:
        return df

    # ✅ РЕАЛЬНОЕ ИМЯ КОЛОНКИ
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y")

    df = df[df["market"].isin(MARKETS_ALLOWED)]

    numeric_cols = [
        "friction_intro",
        "friction_sales",
        "viscosity_index",
        "pipeline_balance",
        "avg_quality_score",
        "total_calls_qty",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df

# ------------------------------------------------------------------
# LOAD DATA
# ------------------------------------------------------------------
df = load_data()

st.title("🦅 Strategic Intelligence Radar")

if df.empty:
    st.warning("No data available")
    st.stop()

# ------------------------------------------------------------------
# DATE LOGIC (как в рабочей версии)
# ------------------------------------------------------------------
latest_date = df["date"].max()
current_date = latest_date
reference_date = latest_date - timedelta(days=7)

st.sidebar.info(
    f"Analysis: {current_date.strftime('%d %b')} vs {reference_date.strftime('%d %b')}"
)

cur = df[df["date"] == current_date]
ref = df[df["date"] == reference_date]

# ------------------------------------------------------------------
# KPI
# ------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

def kpi(col):
    return cur[col].mean(), cur[col].mean() - ref[col].mean()

with c1:
    v, d = kpi("avg_quality_score")
    st.metric("Avg Quality", f"{v:.2f}", f"{d:+.2f}")

with c2:
    v, d = kpi("viscosity_index")
    st.metric("Viscosity Index", f"{v:.1f}%", f"{d:+.1f}%", delta_color="inverse")

with c3:
    v = (cur["friction_intro"].mean() + cur["friction_sales"].mean()) / 2
    d = v - ((ref["friction_intro"].mean() + ref["friction_sales"].mean()) / 2)
    st.metric("Friction Index", f"{v:.2f}", f"{d:+.2f}", delta_color="inverse")

with c4:
    v, d = kpi("total_calls_qty")
    st.metric("Total Calls", int(v), int(d))

# ------------------------------------------------------------------
# FOOTER
# ------------------------------------------------------------------
st.caption(f"Last sync: {datetime.utcnow():%Y-%m-%d %H:%M UTC}")
