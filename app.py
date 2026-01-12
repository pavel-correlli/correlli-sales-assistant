import streamlit as st
import pandas as pd
import plotly.express as px
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
    if df.empty:
        return df
    # Преобразование даты
    df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y')
    # Преобразование строковых метрик в числа
    num_cols = ['friction_intro', 'friction_sales', 'viscosity_index', 'pipeline_balance', 
                'avg_quality_score', 'total_calls_qty', 'vague_qty', 'not_interested_qty']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_raw = load_data()

# --- 3. SIDEBAR (CONTROLS) ---
st.sidebar.title("🦅 Analytics Control")

period_type = st.sidebar.selectbox("Analysis Period:", ["Day", "Week", "Month"])

# Выбор точки отсчета
latest_available_date = df_raw['date'].max().date() if not df_raw.empty else datetime.now().date()
start_date = st.sidebar.date_input("Analysis Start Date:", latest_available_date)

# Логика периодов
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

if df_curr.empty:
    st.warning(f"No data found for the current period: {curr_start.date()} to {curr_end.date()}")
else:
    # Показываем только те рынки, которые есть в ТЕКУЩЕМ периоде
    active_markets = sorted(df_curr['market'].unique())

    for market in active_markets:
        st.markdown(f"### Market: {market.upper()}")
        
        m_curr = df_curr[df_curr['market'] == market]
        m_ref = df_ref[df_ref['market'] == market]
        
        # KPIs
        c1, c2, c3, c4 = st.columns(4)
        
        def calc_vals(m_df, col):
            if m_df.empty: return 0
            return m_df[col].sum() if "qty" in col else m_df[col].mean()

        # Качество
        cur_q = calc_vals(m_curr, 'avg_quality_score')
        ref_q = calc_vals(m_ref, 'avg_quality_score')
        c1.metric("Avg Quality", f"{cur_q:.2f}", delta=f"{cur_q - ref_q:.2f}")

        # Вязкость
        cur_v = calc_vals(m_curr, 'viscosity_index')
        ref_v = calc_vals(m_ref, 'viscosity_index')
        c2.metric("Viscosity Index", f"{cur_v:.1f}%", delta=f"{cur_v - ref_v:.1f}%", delta_color="inverse")

        # Трение (Sales)
        cur_f = calc_vals(m_curr, 'friction_sales')
        ref_f = calc_vals(m_ref, 'friction_sales')
        c3.metric("Friction (Sales)", f"{cur_f:.2f}", delta=f"{cur_f - ref_f:.2f}", delta_color="inverse")

        # Баланс
        cur_b = calc_vals(m_curr, 'pipeline_balance')
        ref_b = calc_vals(m_ref, 'pipeline_balance')
        c4.metric("Pipeline Balance", f"{cur_b:.2f}", delta=f"{cur_b - ref_b:.2f}", delta_color="inverse")

        # График сравнения исходов
        st.write(f"**Outcome Dynamics: {market}**")
        
        comparison_data = []
        # Собираем данные для визуализации
        for label, d in [("Current", m_curr), ("Reference", m_ref)]:
            comparison_data.append({"Period": label, "Metric": "Vague", "Value": d['vague_qty'].sum() if not d.empty else 0})
            comparison_data.append({"Period": label, "Metric": "Not Interested", "Value": d['not_interested_qty'].sum() if not d.empty else 0})
            comparison_data.append({"Period": label, "Metric": "Total Calls", "Value": d['total_calls_qty'].sum() if not d.empty else 0})
        
        df_plot = pd.DataFrame(comparison_data)
        
        # Исправленный график (color_discrete_map вместо color_manual)
        fig = px.bar(
            df_plot, 
            x="Metric", 
            y="Value", 
            color="Period", 
            barmode="group",
            text_auto=True, 
            height=350, 
            template="plotly_dark",
            color_discrete_map={"Current": "#4CAF50", "Reference": "#555555"}
        )
        
        fig.update_layout(margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")

# --- 6. GLOBAL RHYTHM ---
if not df_raw.empty:
    st.subheader("Global Call Volume Trend")
    trend_df = df_raw.groupby(['date', 'market'])['total_calls_qty'].sum().reset_index()
    fig_trend = px.line(trend_df, x="date", y="total_calls_qty", color="market", 
                       template="plotly_dark", markers=True)
    st.plotly_chart(fig_trend, use_container_width=True)
