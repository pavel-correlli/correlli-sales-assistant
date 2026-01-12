import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime, timedelta

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Correlli Intelligence", layout="wide", page_icon="🦅")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric { background-color: #1a1a1a; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    </style>
""", unsafe_allow_html=True)

# --- 2. SUPABASE CONNECTION ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- 3. DATA LOADING & CLEANING ---
@st.cache_data(ttl=300)
def fetch_and_clean_data():
    # Тянем данные из основной витрины
    res = supabase.table("v_sales_performance_metrics").select("*").execute()
    df = pd.DataFrame(res.data)
    
    if df.empty:
        return df

    # ЧИСТКА 1: Превращаем текст в даты (формат 12/23/2025)
    df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y')
    
    # ЧИСТКА 2: Превращаем строки в числа (из-за особенностей Postgres views)
    numeric_cols = [
        'friction_intro', 'friction_sales', 'viscosity_index', 
        'pipeline_balance', 'avg_quality_score', 'total_calls_qty'
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

df_metrics = fetch_and_clean_data()

# --- 4. SIDEBAR ---
st.sidebar.title("🦅 Correlli Intelligence")
role = st.sidebar.selectbox("Access Level:", ["CEO (Strategist)", "Data Lab (Explorer)"])

if df_metrics.empty:
    st.error("Data not found. Check your Supabase table 'v_sales_performance_metrics'")
    st.stop()

# --- 5. CEO DASHBOARD ---
if role == "CEO (Strategist)":
    st.title("Executive Intelligence Radar")
    
    # Расчет дат: Вчера vs Тот же день неделю назад
    # Используем max_date из базы, чтобы дашборд не был пустым, если данных за сегодня еще нет
    latest_date = df_metrics['date'].max()
    yesterday_date = latest_date
    last_week_date = yesterday_date - timedelta(days=7)

    st.sidebar.info(f"Analysis: {yesterday_date.strftime('%d %b')} vs {last_week_date.strftime('%d %b')}")

    # Фильтруем периоды
    current_df = df_metrics[df_metrics['date'] == yesterday_date]
    reference_df = df_metrics[df_metrics['date'] == last_week_date]

    # --- BLOCK A: GLOBAL KPI (Yesterday vs Last Week) ---
    col1, col2, col3, col4 = st.columns(4)

    def calc_metrics(target_df):
        return {
            "q": target_df['avg_quality_score'].mean(),
            "v": target_df['viscosity_index'].mean(),
            "f": (target_df['friction_intro'].mean() + target_df['friction_sales'].mean()) / 2,
            "vol": target_df['total_calls_qty'].sum()
        }

    curr = calc_metrics(current_df)
    prev = calc_metrics(reference_df)

    with col1:
        st.metric("Avg Quality", f"{curr['q']:.2f}", delta=f"{curr['q']-prev['q']:.2f}")
    with col2:
        # Вязкость (Viscosity): рост - это плохо, поэтому инвертируем цвет дельты
        st.metric("Viscosity Index", f"{curr['v']:.1f}%", delta=f"{curr['v']-prev['v']:.1f}%", delta_color="inverse")
    with col3:
        # Трение (Friction): рост - это плохо
        st.metric("Friction Index", f"{curr['f']:.2f}", delta=f"{curr['f']-prev['f']:.2f}", delta_color="inverse")
    with col4:
        st.metric("Total Volume", int(curr['vol']), delta=int(curr['vol']-prev['vol']))

    st.markdown("---")

    # --- BLOCK B: MARKET BATTLEFIELD (Relative Competition) ---
    st.subheader("🏁 Yesterday's Market Battlefield")
    
    # Агрегируем за вчера по рынкам
    m_battle = current_df.groupby('market').agg({
        'viscosity_index': 'mean',
        'pipeline_balance': 'mean',
        'avg_quality_score': 'mean'
    }).reset_index()

    c1, c2, c3 = st.columns(3)
    with c1:
        fig1 = px.bar(m_battle, x='market', y='viscosity_index', color='market', 
                     title="Viscosity % (Lower is Better)", text_auto=True, template="plotly_dark")
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        fig2 = px.bar(m_battle, x='market', y='avg_quality_score', color='market', 
                     title="Quality Score (Higher is Better)", text_auto=True, template="plotly_dark")
        st.plotly_chart(fig2, use_container_width=True)
    with c3:
        fig3 = px.bar(m_battle, x='market', y='pipeline_balance', color='market', 
                     title="Pipeline Balance (Lead/Sales Ratio)", text_auto=True, template="plotly_dark")
        st.plotly_chart(fig3, use_container_width=True)

    # --- BLOCK C: DAILY RHYTHM ---
    st.markdown("---")
    st.subheader("📈 Call Volume Rhythm (Last 14 Days)")
    
    # График динамики объемов по рынкам
    recent_days = latest_date - timedelta(days=14)
    trend_df = df_metrics[df_metrics['date'] >= pd.Timestamp(recent_days)].groupby(['date', 'market'])['total_calls_qty'].sum().reset_index()
    
    fig_line = px.line(trend_df, x='date', y='total_calls_qty', color='market', markers=True, 
                       title="Daily Call Volume Dynamics", template="plotly_dark")
    st.plotly_chart(fig_line, use_container_width=True)

# --- 6. DATA LAB ---
elif role == "Data Lab (Explorer)":
    from pygwalker.api.streamlit import StreamlitRenderer
    st.title("🧬 Data Laboratory")
    
    # Для лаборатории дадим более детальный View
    res_raw = supabase.table("v_analytics_calls").select("*").execute()
    df_raw = pd.DataFrame(res_raw.data)
    
    renderer = StreamlitRenderer(df_raw)
    renderer.explorer()

st.sidebar.markdown("---")
st.sidebar.caption(f"Last sync: {datetime.now().strftime('%H:%M:%S')}")
