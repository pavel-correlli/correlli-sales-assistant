import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime, timedelta

# --- 1. PAGE CONFIG & CLEAN UI ---
st.set_page_config(page_title="Correlli Intelligence Platform", layout="wide", page_icon="🦅")

# Removing custom dark backgrounds for metrics to ensure readability
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stMetric"] {
        border: 1px solid #e6e9ef;
        padding: 15px;
        border-radius: 10px;
        background-color: #f8f9fb;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DB CONNECTION ---
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

@st.cache_data(ttl=300)
def load_data(view_name="v_sales_performance_metrics"):
    res = supabase.table(view_name).select("*").execute()
    df = pd.DataFrame(res.data)
    if df.empty: return df
    
    # Universal cleaning for metrics view
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y')
    
    num_cols = ['friction_intro', 'friction_sales', 'viscosity_index', 'pipeline_balance', 
                'avg_quality_score', 'total_calls_qty', 'vague_qty', 'not_interested_qty',
                'intro_call_qty', 'intro_followup_qty', 'sales_call_qty', 'sales_followup_qty']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.image("https://via.placeholder.com/150?text=CORRELLI", width=150)
st.sidebar.title("Navigation")
role = st.sidebar.radio("Go to Section:", 
    ["CEO (Strategic Radar)", "CMO (Marketing)", "CSO (Sales Ops)", "Manager Lab", "Data Lab (Explorer)"])

# --- 4. DATA PROCESSING ---
df_metrics = load_data("v_sales_performance_metrics")

# --- 5. CEO SECTION ---
if role == "CEO (Strategic Radar)":
    st.title("🦅 Strategic Intelligence Control")
    
    # --- STRATEGIC CONTROL PANEL ---
    with st.expander("📅 Period & Comparison Settings", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            period_type = st.selectbox("Analysis Window:", ["Day", "Week", "Month"], index=1)
        with c2:
            analysis_start = st.date_input("Analysis Start Date:", df_metrics['date'].max())
        with c3:
            reference_start = st.date_input("Reference Start Date:", df_metrics['date'].max() - timedelta(days=7))

    # Period logic
    d_map = {"Day": 1, "Week": 7, "Month": 30}
    days = d_map[period_type]
    
    curr_range = (pd.to_datetime(analysis_start), pd.to_datetime(analysis_start) + timedelta(days=days-1))
    ref_range = (pd.to_datetime(reference_start), pd.to_datetime(reference_start) + timedelta(days=days-1))
    
    df_curr = df_metrics[(df_metrics['date'] >= curr_range[0]) & (df_metrics['date'] <= curr_range[1])]
    df_ref = df_metrics[(df_metrics['date'] >= ref_range[0]) & (df_metrics['date'] <= ref_range[1])]

    # --- TOP METRICS ---
    st.subheader("Global Performance Benchmark")
    active_m = sorted(df_curr['market'].unique())
    
    # TOOLTIP TEXTS
    tooltip_visc = """**Viscosity Index**: % of calls with vague outcomes or no interest. 
    \n**Rising**: Process is getting 'stuck', managers are losing control of next steps. 
    \n**Falling**: High clarity, efficient movement to result."""
    
    tooltip_fric = """**Friction Index**: Ratio of follow-ups to initial calls. 
    \n**Rising**: Market resistance is high; leads require more energy to close. 
    \n**Falling**: Smooth sales cycle, fewer touches needed."""
    
    tooltip_bal = """**Pipeline Balance**: Ratio of total Intro calls to total Sales calls. 
    \n**Rising**: Funnel is 'thinning' at the bottom. 
    \n**Falling**: High conversion health; top-of-funnel leads successfully reach Sales stages."""

    for market in active_m:
        st.markdown(f"#### Market: {market.upper()}")
        m_curr = df_curr[df_curr['market'] == market]
        m_ref = df_ref[df_ref['market'] == market]
        
        m1, m2, m3, m4 = st.columns(4)
        
        # Helper for deltas
        def get_vals(curr_df, ref_df, col, is_sum=False):
            c_val = curr_df[col].sum() if is_sum else curr_df[col].mean()
            r_val = ref_df[col].sum() if is_sum else ref_df[col].mean()
            return c_val, c_val - r_val

        val, delta = get_vals(m_curr, m_ref, 'avg_quality_score')
        m1.metric("Avg Quality", f"{val:.2f}", delta=f"{delta:.2f}", help="AI-scored call quality benchmark (0-10).")
        
        val, delta = get_vals(m_curr, m_ref, 'viscosity_index')
        m2.metric("Viscosity Index", f"{val:.1f}%", delta=f"{delta:.1f}%", delta_color="inverse", help=tooltip_visc)
        
        val, delta = get_vals(m_curr, m_ref, 'friction_sales')
        m3.metric("Friction (Sales)", f"{val:.2f}", delta=f"{delta:.2f}", delta_color="inverse", help=tooltip_fric)
        
        val, delta = get_vals(m_curr, m_ref, 'pipeline_balance')
        m4.metric("Pipeline Balance", f"{val:.2f}", delta=f"{delta:.2f}", delta_color="inverse", help=tooltip_bal)

        # OUTCOME DYNAMICS
        st.write("**Outcome Comparison (Current vs Reference)**")
        comp_list = []
        for label, d in [("Current", m_curr), ("Reference", m_ref)]:
            comp_list.append({"Period": label, "Metric": "Vague", "Value": d['vague_qty'].sum()})
            comp_list.append({"Period": label, "Metric": "Not Interested", "Value": d['not_interested_qty'].sum()})
            comp_list.append({"Period": label, "Metric": "Total Calls", "Value": d['total_calls_qty'].sum()})
        
        fig_out = px.bar(pd.DataFrame(comp_list), x="Metric", y="Value", color="Period", barmode="group",
                         text_auto=True, height=300, color_discrete_map={"Current": "#4CAF50", "Reference": "#CED4DA"})
        st.plotly_chart(fig_out, use_container_width=True)

    # --- GRANULAR VOLUME TRENDS ---
    st.markdown("---")
    st.subheader("📈 Detailed Call Volume Trends")
    
    call_types = {
        "Intro Dynamics": ["intro_call_qty", "intro_followup_qty"],
        "Sales Dynamics": ["sales_call_qty", "sales_followup_qty"]
    }
    
    for title, cols in call_types.items():
        st.write(f"**{title}**")
        trend_df = df_metrics.groupby(['date', 'market'])[cols].sum().reset_index()
        # Melting for plotly
        trend_melt = trend_df.melt(id_vars=['date', 'market'], value_vars=cols, var_name='Call Type', value_name='Qty')
        
        fig_t = px.line(trend_melt, x="date", y="Qty", color="market", line_dash="Call Type",
                       markers=True, height=400, template="plotly_white")
        st.plotly_chart(fig_t, use_container_width=True)

# --- 6. DATA LAB SECTION ---
elif role == "Data Lab (Explorer)":
    from pygwalker.api.streamlit import StreamlitRenderer
    st.title("🧬 Explorer Lab")
    df_lab = load_data("v_analytics_calls")
    renderer = StreamlitRenderer(df_raw if 'df_raw' in locals() else df_lab)
    renderer.explorer()

# --- OTHER SECTIONS (Placeholders) ---
else:
    st.title(f"Section: {role}")
    st.info("This section is currently under construction. Please use CEO or Data Lab.")
