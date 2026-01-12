import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, timedelta

# --- 1. CONFIG ---
st.set_page_config(page_title="Executive Analytics", layout="wide", page_icon="🦅")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric { background-color: #1a1a1a; padding: 15px; border-radius: 5px; border-left: 5px solid #4CAF50; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DB CONNECTION ---
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

@st.cache_data(ttl=300)
def load_data():
    res = supabase.table("v_sales_performance_metrics").select("*").execute()
    df = pd.DataFrame(res.data)
    df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y')
    # Convert strings to numeric
    num_cols = ['friction_intro', 'friction_sales', 'viscosity_index', 'pipeline_balance', 
                'avg_quality_score', 'total_calls_qty', 'vague_qty', 'not_interested_qty']
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_raw = load_data()

# --- 3. SIDEBAR (CONTROLS) ---
st.sidebar.title("🦅 Analytics Control")

# 1. Выбор периода (Day, Week, Month)
period_type = st.sidebar.selectbox("Analysis Period:", ["Day", "Week", "Month"])

# 2. Выбор даты (Rewind)
latest_date = df_raw['date'].max()
start_date = st.sidebar.date_input("Analysis Start Date:", latest_date)

# Логика расчета периодов
if period_type == "Day":
    delta_days = 1
elif period_type == "Week":
    delta_days = 7
else:
    delta_days = 30

curr_start = pd.to_datetime(start_date)
curr_end = curr_start + timedelta(days=delta_days - 1)
ref_start = curr_start - timedelta(days=delta_days)
ref_end = curr_start - timedelta(days=1)

st.sidebar.markdown("---")
st.sidebar.write(f"**Current:** {curr_start.strftime('%d.%m')} - {curr_end.strftime('%d.%m')}")
st.sidebar.write(f"**Reference:** {ref_start.strftime('%d.%m')} - {ref_end.strftime('%d.%m')}")

# --- 4. DATA PROCESSING ---
def get_period_data(df, start, end):
    return df[(df['date'] >= start) & (df['date'] <= end)]

df_curr = get_period_data(df_raw, curr_start, curr_end)
df_ref = get_period_data(df_raw, ref_start, ref_end)

# --- 5. MAIN UI ---
st.title("Market Performance Overview")

markets = sorted(df_raw['market'].unique())

for market in markets:
    st.header(f"Market: {market.upper()}")
    
    m_curr = df_curr[df_curr['market'] == market]
    m_ref = df_ref[df_ref['market'] == market]
    
    # KPIs for Market
    c1, c2, c3, c4 = st.columns(4)
    
    def mk_metric(label, col, is_pct=False):
        curr_val = m_curr[col].mean() if "qty" not in col else m_curr[col].sum()
        ref_val = m_ref[col].mean() if "qty" not in col else m_ref[col].sum()
        diff = curr_val - ref_val
        suffix = "%" if is_pct else ""
        return curr_val, diff, suffix

    val, diff, suf = mk_metric("Quality", "avg_quality_score")
    c1.metric("Avg Quality", f"{val:.2f}{suf}", delta=f"{diff:.2f}")

    val, diff, suf = mk_metric("Viscosity", "viscosity_index", True)
    c2.metric("Viscosity Index", f"{val:.1f}{suf}", delta=f"{diff:.1f}%", delta_color="inverse")

    val, diff, suf = mk_metric("Friction", "friction_sales")
    c3.metric("Friction (Sales)", f"{val:.2f}{suf}", delta=f"{diff:.2f}", delta_color="inverse")

    val, diff, suf = mk_metric("Balance", "pipeline_balance")
    c4.metric("Pipeline Balance", f"{val:.2f}{suf}", delta=f"{diff:.2f}", delta_color="inverse")

    # Сравнение исходов (Требование №5)
    st.subheader(f"Outcome Comparison: {market}")
    
    # Готовим данные для бокового графика (Side-by-side)
    comparison_data = []
    for period, d in [("Reference", m_ref), ("Current", m_curr)]:
        comparison_data.append({"Period": period, "Metric": "Vague", "Value": d['vague_qty'].sum()})
        comparison_data.append({"Period": period, "Metric": "Not Interested", "Value": d['not_interested_qty'].sum()})
        comparison_data.append({"Period": period, "Metric": "Total Volume", "Value": d['total_calls_qty'].sum()})
    
    df_comp = pd.DataFrame(comparison_data)
    
    fig = px.bar(df_comp, x="Metric", y="Value", color="Period", barmode="group",
                 text_auto=True, height=350, template="plotly_dark",
                 color_manual={"Current": "#4CAF50", "Reference": "#555555"})
    
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")

# --- 6. GLOBAL TRENDS ---
st.subheader("Global Rhythm (Total Calls)")
trend_data = df_raw.groupby(['date', 'market'])['total_calls_qty'].sum().reset_index()
fig_line = px.line(trend_data, x="date", y="total_calls_qty", color="market", 
                  template="plotly_dark", title="Calls Volume Trend by Market")
st.plotly_chart(fig_line, use_container_width=True)
