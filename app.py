import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime, timedelta

# 1. Page Configuration
st.set_page_config(page_title="Correlli Intelligence", layout="wide", page_icon="🦅")

# CSS for Dark Mode & Clean UI
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric { background-color: #1e1e1e; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    </style>
""", unsafe_allow_html=True)

# 2. Supabase Connection
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# 3. Data Loading Logic
@st.cache_data(ttl=300)
def fetch_performance_data():
    # Fetching from our unified View
    response = supabase.table("v_sales_performance_metrics").select("*").execute()
    df = pd.DataFrame(response.data)
    df['date'] = pd.to_datetime(df['date'])
    return df

df_main = fetch_performance_data()

# 4. Sidebar Navigation
st.sidebar.title("🦅 Correlli Intelligence")
role = st.sidebar.selectbox("Access Level:", ["CEO (Strategist)", "Data Lab (Explorer)"])
st.sidebar.markdown("---")

# 5. CEO Dashboard Logic
if role == "CEO (Strategist)":
    st.title("Executive Intelligence Radar")
    
    # --- TIME CALCULATIONS ---
    # We compare Yesterday vs Same Day Last Week
    yesterday = (datetime.now() - timedelta(days=1)).date()
    last_week_sdw = yesterday - timedelta(days=7)
    
    # Filter Data
    df_yesterday = df_main[df_main['date'].dt.date == yesterday]
    df_last_week = df_main[df_main['date'].dt.date == last_week_sdw]

    # --- TOP KPI ROW (Pulse) ---
    col1, col2, col3, col4 = st.columns(4)

    def get_delta(curr, prev):
        if prev == 0: return 0
        return ((curr - prev) / prev) * 100

    # Metrics Calculations
    q_curr = df_yesterday['avg_quality_score'].mean()
    q_prev = df_last_week['avg_quality_score'].mean()
    
    v_curr = df_yesterday['viscosity_index'].mean()
    v_prev = df_last_week['viscosity_index'].mean()

    f_curr = (df_yesterday['friction_intro'].mean() + df_yesterday['friction_sales'].mean()) / 2
    f_prev = (df_last_week['friction_intro'].mean() + df_last_week['friction_sales'].mean()) / 2

    vol_curr = df_yesterday['total_calls_qty'].sum()
    vol_prev = df_last_week['total_calls_qty'].sum()

    with col1:
        st.metric("Avg Quality Score", f"{q_curr:.2f}", delta=f"{q_curr-q_prev:.2f}", help="AI-based quality benchmark")
    with col2:
        st.metric("Viscosity Index", f"{v_curr:.1f}%", delta=f"{v_curr-v_prev:.1f}%", delta_color="inverse", help="% of vague/undefined outcomes")
    with col3:
        st.metric("Friction Index", f"{f_curr:.2f}", delta=f"{f_curr-f_prev:.2f}", delta_color="inverse", help="Follow-ups per initial call")
    with col4:
        st.metric("Total Call Volume", int(vol_curr), delta=int(vol_curr-vol_prev), help="Absolute call count yesterday")

    st.markdown("---")

    # --- MARKET BATTLEFIELD (Competition) ---
    st.subheader("🏁 Yesterday's Market Battlefield")
    st.info("Relative performance comparison across active markets.")
    
    # Group by market for yesterday
    battle_df = df_yesterday.groupby('market').agg({
        'viscosity_index': 'mean',
        'pipeline_balance': 'mean',
        'avg_quality_score': 'mean'
    }).reset_index()

    c1, c2, c3 = st.columns(3)
    
    with c1:
        # Lower Viscosity is better
        fig_v = px.bar(battle_df.sort_values('viscosity_index'), x='market', y='viscosity_index', 
                       title="Viscosity (Lower is Better)", color='market', text_auto=True)
        st.plotly_chart(fig_v, use_container_width=True)
        
    with c2:
        # Higher Quality is better
        fig_q = px.bar(battle_df.sort_values('avg_quality_score', ascending=False), x='market', y='avg_quality_score', 
                       title="Quality Score (Higher is Better)", color='market', text_auto=True)
        st.plotly_chart(fig_q, use_container_width=True)

    with c3:
        # Pipeline Balance (Lower ratio means more efficient transition to Sales)
        fig_b = px.bar(battle_df.sort_values('pipeline_balance'), x='market', y='pipeline_balance', 
                       title="Pipeline Balance Ratio", color='market', text_auto=True)
        st.plotly_chart(fig_b, use_container_width=True)

    # --- RHYTHM COMPARISON ---
    st.markdown("---")
    st.subheader("📈 Call Volume Rhythm: Yesterday vs Last Week")
    
    # Create a trend for the last 14 days to see the rhythm
    recent_trend = df_main[df_main['date'].dt.date >= last_week_sdw].groupby(['date', 'market'])['total_calls_qty'].sum().reset_index()
    fig_trend = px.line(recent_trend, x='date', y='total_calls_qty', color='market', 
                        title="Daily Volume Dynamics", markers=True)
    st.plotly_chart(fig_trend, use_container_width=True)

elif role == "Data Lab (Explorer)":
    from pygwalker.api.streamlit import StreamlitRenderer
    st.title("🧬 Data Laboratory")
    st.markdown("Custom analysis and raw metric exploration.")
    renderer = StreamlitRenderer(df_main)
    renderer.explorer()

# Footer
st.sidebar.markdown("---")
st.sidebar.write(f"Refreshed: {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.write("2026 © Correlli Intelligence")
