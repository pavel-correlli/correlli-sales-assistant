import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime, timedelta

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Executive Analytics Radar", layout="wide", page_icon="🦅")

# Clean UI without dark backgrounds for metrics
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stMetric"] {
        border: 1px solid #e6e9ef;
        padding: 15px;
        border-radius: 10px;
        background-color: #fcfcfc;
    }
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
    if df.empty: return df
    
    # STRICT MARKET FILTER
    df = df[df['market'].isin(['CZ', 'RUK', 'SK'])]
    
    # Data Cleaning
    df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y')
    num_cols = ['friction_intro', 'friction_sales', 'viscosity_index', 'pipeline_balance', 
                'avg_quality_score', 'total_calls_qty', 'vague_qty', 'not_interested_qty',
                'intro_call_qty', 'intro_followup_qty', 'sales_call_qty', 'sales_followup_qty']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_metrics = load_data()

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.title("Correlli Platform")
role = st.sidebar.radio("Navigation:", ["CEO (Strategic Radar)", "Data Lab (Explorer)"])

# --- 4. CEO SECTION ---
if role == "CEO (Strategic Radar)":
    st.title("🦅 Strategic Intelligence Control")
    
    # CONTROL PANEL
    with st.container():
        st.subheader("Strategic Control Panel")
        c1, c2, c3 = st.columns(3)
        period_type = c1.selectbox("Analysis Window:", ["Day", "Week", "Month"], index=1)
        analysis_start = c2.date_input("Analysis Start Date:", df_metrics['date'].max())
        reference_start = c3.date_input("Reference Start Date:", df_metrics['date'].max() - timedelta(days=7))

    d_map = {"Day": 1, "Week": 7, "Month": 30}
    days = d_map[period_type]
    
    curr_range = (pd.to_datetime(analysis_start), pd.to_datetime(analysis_start) + timedelta(days=days-1))
    ref_range = (pd.to_datetime(reference_start), pd.to_datetime(reference_start) + timedelta(days=days-1))
    
    df_curr = df_metrics[(df_metrics['date'] >= curr_range[0]) & (df_metrics['date'] <= curr_range[1])]
    df_ref = df_metrics[(df_metrics['date'] >= ref_range[0]) & (df_metrics['date'] <= ref_range[1])]

    # --- TOOLTIP DEFINITIONS ---
    tt_quality = """**Avg Quality Score (0-10)** Overall benchmark of call standards.  
    **Components:** Structure, Communication, Trust Building, Objection Handling, Engagement, Technical Quality, Scheduling Efficiency.  
    **Goal:** Higher is better."""
    
    tt_viscosity = r"""**Viscosity Index** Measures "imprecise" or "vague" communication results.  
    **Formula:** $$ \frac{Vague + Not Interested}{Total Calls} \times 100\% $$  
    **Goal:** Minimize. High values indicate a lack of control and inability to secure firm next steps.  
    **Note:** Productive outcomes (Trials, Closed Won, Scheduled Callbacks) are excluded from this penalty."""
    
    tt_fric_intro = r"""**Intro Friction** Effort required to schedule a Trial Lesson.  
    **Formula:** $$ \frac{Intro Followup}{Intro Initial} $$  
    **Goal:** Minimize. Shows extra touches needed to move a lead from first contact to a scheduled Trial Lesson."""
    
    tt_fric_sales = r"""**Sales Friction** Resistance encountered after a Trial Lesson.  
    **Formula:** $$ \frac{Sales Followup}{Sales Initial} $$  
    **Goal:** Minimize. Measures the difficulty in closing the deal after the product (Trial) has been presented."""

    # --- TOP METRICS BY MARKET ---
    st.subheader("Global Performance Benchmark")
    active_markets = sorted(df_curr['market'].unique())

    for market in active_markets:
        st.markdown(f"#### Market: {market.upper()}")
        m_curr = df_curr[df_curr['market'] == market]
        m_ref = df_ref[df_ref['market'] == market]
        
        m1, m2, m3, m4 = st.columns(4)

        def get_delta(c_df, r_df, col):
            c_val = c_df[col].mean() if not c_df.empty else 0
            r_val = r_df[col].mean() if not r_df.empty else 0
            return c_val, c_val - r_val

        val, delta = get_delta(m_curr, m_ref, 'avg_quality_score')
        m1.metric("Avg Quality", f"{val:.2f}", delta=f"{delta:.2f}", help=tt_quality)
        
        val, delta = get_delta(m_curr, m_ref, 'viscosity_index')
        m2.metric("Viscosity Index", f"{val:.1f}%", delta=f"{delta:.1f}%", delta_color="inverse", help=tt_viscosity)
        
        val, delta = get_delta(m_curr, m_ref, 'friction_intro')
        m3.metric("Intro Friction", f"{val:.2f}", delta=f"{delta:.2f}", delta_color="inverse", help=tt_fric_intro)
        
        val, delta = get_delta(m_curr, m_ref, 'friction_sales')
        m4.metric("Sales Friction", f"{val:.2f}", delta=f"{delta:.2f}", delta_color="inverse", help=tt_fric_sales)

        # --- CALL OUTCOME PRECISION ---
        st.write(f"**Call Outcome Precision: {market}**")
        
        
        chart_data = []
        for label, d in [("Current", m_curr), ("Reference", m_ref)]:
            total = d['total_calls_qty'].sum()
            vague = d['vague_qty'].sum()
            ni = d['not_interested_qty'].sum()
            
            chart_data.append({"Period": label, "Metric": "Total Calls (Qty)", "Value": total})
            chart_data.append({"Period": label, "Metric": "Vague Ratio (%)", "Value": (vague/total*100) if total > 0 else 0})
            chart_data.append({"Period": label, "Metric": "Not Interested Ratio (%)", "Value": (ni/total*100) if total > 0 else 0})

        fig_out = px.bar(pd.DataFrame(chart_data), x="Metric", y="Value", color="Period", barmode="group",
                         text_auto=".1f", height=350, template="plotly_white",
                         color_discrete_map={"Current": "#4CAF50", "Reference": "#CED4DA"})
        st.plotly_chart(fig_out, use_container_width=True)
        st.markdown("---")

    # --- DETAILED VOLUME DYNAMICS (PER MARKET) ---
    st.subheader("📈 Detailed Volume Dynamics")
    
    
    call_cols = ['intro_call_qty', 'intro_followup_qty', 'sales_call_qty', 'sales_followup_qty']
    
    for market in active_markets:
        st.write(f"**Market Dynamics: {market.upper()}**")
        m_trend = df_metrics[df_metrics['market'] == market].groupby('date')[call_cols].sum().reset_index()
        m_melt = m_trend.melt(id_vars=['date'], value_vars=call_cols, var_name='Call Type', value_name='Qty')
        
        fig_l = px.line(m_melt, x="date", y="Qty", color='Call Type', markers=True, 
                       height=400, template="plotly_white", title=f"All Call Types Rhythm - {market}")
        st.plotly_chart(fig_l, use_container_width=True)

elif role == "Data Lab (Explorer)":
    from pygwalker.api.streamlit import StreamlitRenderer
    st.title("🧬 Explorer Lab")
    df_lab = supabase.table("v_analytics_calls").select("*").execute()
    renderer = StreamlitRenderer(pd.DataFrame(df_lab.data))
    renderer.explorer()
