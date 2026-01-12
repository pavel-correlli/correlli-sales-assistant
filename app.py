import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Correlli Intelligence Platform", layout="wide", page_icon="🦅")

# Clean UI Styles
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
    .market-header {
        font-size: 32px !important;
        font-weight: 800 !important;
        color: #1a1a1a;
        margin-top: 40px !important;
        margin-bottom: 10px !important;
        border-bottom: 2px solid #4CAF50;
        padding-bottom: 5px;
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
    # Запрашиваем 10,000 строк, чтобы не обрезать данные за прошлые периоды
    res = supabase.table("v_sales_performance_metrics").select("*").limit(10000).execute()
    df = pd.DataFrame(res.data)
    
    if df.empty: return df
    
    # Фильтр рынков (только нужные)
    df = df[df['market'].isin(['CZ', 'RUK', 'SK'])]
    
    # Конвертация дат
    df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y')
    
    # Конвертация метрик в числа (принудительно)
    num_cols = [
        'friction_intro', 'friction_sales', 'viscosity_index', 'pipeline_balance', 
        'avg_quality_score', 'total_calls_qty', 'vague_qty', 'not_interested_qty',
        'intro_call_qty', 'intro_followup_qty', 'sales_call_qty', 'sales_followup_qty'
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_raw = load_data()

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.title("🦅 Navigation")
role = st.sidebar.radio("Section:", 
    ["CEO (Strategic Radar)", "CMO (Marketing)", "CSO (Sales Ops)", "Manager Lab", "Data Lab (Explorer)"])

# --- 4. CEO SECTION ---
if role == "CEO (Strategic Radar)":
    st.title("🦅 Strategic Intelligence Control")
    
    if df_raw.empty:
        st.error("No data found in Supabase View 'v_sales_performance_metrics'.")
        st.stop()

    # --- STRATEGIC CONTROL PANEL ---
    with st.container():
        c1, c2, c3 = st.columns(3)
        period_type = c1.selectbox("Analysis Period:", ["Day", "Week", "Month"], index=1)
        
        # Определяем последнюю дату в базе для дефолта
        max_db_date = df_raw['date'].max().date()
        analysis_start = c2.date_input("Analysis Start Date:", max_db_date)
        reference_start = c3.date_input("Reference Start Date:", max_db_date - timedelta(days=7))

    # Логика окон времени
    d_map = {"Day": 1, "Week": 7, "Month": 30}
    days = d_map[period_type]
    
    curr_end = pd.to_datetime(analysis_start)
    curr_start = curr_end - timedelta(days=days-1)
    
    ref_end = pd.to_datetime(reference_start)
    ref_start = ref_end - timedelta(days=days-1)

    df_curr_period = df_raw[(df_raw['date'] >= curr_start) & (df_raw['date'] <= curr_end)]
    df_ref_period = df_raw[(df_raw['date'] >= ref_start) & (df_raw['date'] <= ref_end)]

    # --- TOOLTIPS ---
    tt_quality = """**Avg Quality Score (0-10)**
    Overall call quality benchmark.  
    **Formula:** Mean of (Structure, Communication, Trust Building, Objection Handling, Engagement, Technical Quality, Scheduling Efficiency).  
    **Goal:** Higher is better."""
    
    tt_viscosity = r"""**Viscosity Index**
    Measures imprecision and inability to secure firm next steps.  
    **Formula:** $$ \frac{Vague + Not Interested}{Total Calls} \times 100\% $$  
    **Goal:** Minimize. High values indicate a loss of control in the conversation.  
    **Note:** Excludes productive outcomes like 'Trial Scheduled', 'Closed Won'."""
    
    tt_fric_intro = r"""**Intro Friction**
    Measures effort needed to successfully schedule a Trial Lesson.  
    **Formula:** $$ \frac{Intro Followup}{Intro Initial} $$  
    **Goal:** Minimize. Indicates the difficulty of getting a lead to agree to a trial."""
    
    tt_fric_sales = r"""**Sales Friction**
    Measures resistance after the Trial Lesson has been conducted.  
    **Formula:** $$ \frac{Sales Followup}{Sales Initial} $$  
    **Goal:** Minimize. High values mean clients are hesitating to close after the presentation."""

    # --- MARKET LOOPS ---
    active_m = sorted(df_curr_period['market'].unique())
    if not active_m:
        st.warning(f"No active data for the period: {curr_start.date()} - {curr_end.date()}")

    for market in active_m:
        st.markdown(f"<div class='market-header'>Market Dynamics: {market.upper()}</div>", unsafe_allow_html=True)
        
        m_curr = df_curr_period[df_curr_period['market'] == market]
        m_ref = df_ref_period[df_ref['market'] == market]
        
        # --- 1. KPI METRICS (Yesterday vs Reference) ---
        m1, m2, m3, m4 = st.columns(4)
        
        def get_p_stats(df_p):
            if df_p.empty: return {"q":0, "v":0, "fi":0, "fs":0, "vol":0}
            return {
                "q": df_p['avg_quality_score'].mean(),
                "v": df_p['viscosity_index'].mean(),
                "fi": df_p['friction_intro'].mean(),
                "fs": df_p['friction_sales'].mean(),
                "vol": df_p['total_calls_qty'].sum() # Использование суммы для объема
            }

        s_curr = get_p_stats(m_curr)
        s_ref = get_p_stats(m_ref)

        m1.metric("Avg Quality", f"{s_curr['q']:.2f}", delta=f"{s_curr['q']-s_ref['q']:.2f}", help=tt_quality)
        m2.metric("Viscosity Index", f"{s_curr['v']:.1f}%", delta=f"{s_curr['v']-s_ref['v']:.1f}%", delta_color="inverse", help=tt_viscosity)
        m3.metric("Intro Friction", f"{s_curr['fi']:.2f}", delta=f"{s_curr['fi']-s_ref['fi']:.2f}", delta_color="inverse", help=tt_fric_intro)
        m4.metric("Sales Friction", f"{s_curr['fs']:.2f}", delta=f"{s_curr['fs']-s_ref['fs']:.2f}", delta_color="inverse", help=tt_fric_sales)

        # --- 2. RELATIVE OUTCOME CHART (Ref = 100%) ---
        
        ref_vol = s_ref['vol']
        curr_vol = s_curr['vol']
        rel_vol_scale = (curr_vol / ref_vol * 100) if ref_vol > 0 else 100
        
        comp_data = [
            {"Period": "Reference", "Type": "Total Volume", "Display": f"{int(ref_vol)}", "Scale": 100},
            {"Period": "Current", "Type": "Total Volume", "Display": f"{int(curr_vol)}", "Scale": rel_vol_scale}
        ]
        
        for label, d, vol in [("Reference", m_ref, ref_vol), ("Current", m_curr, curr_vol)]:
            v_ratio = (d['vague_qty'].sum() / vol * 100) if vol > 0 else 0
            ni_ratio = (d['not_interested_qty'].sum() / vol * 100) if vol > 0 else 0
            comp_data.append({"Period": label, "Type": "Vague Ratio (%)", "Display": f"{v_ratio:.1f}%", "Scale": v_ratio})
            comp_data.append({"Period": label, "Type": "Not Interested Ratio (%)", "Display": f"{ni_ratio:.1f}%", "Scale": ni_ratio})

        fig_bar = px.bar(pd.DataFrame(comp_data), x="Type", y="Scale", color="Period", barmode="group",
                         text="Display", height=400, template="plotly_white",
                         color_discrete_map={"Current": "#4CAF50", "Reference": "#CED4DA"})
        fig_bar.update_layout(yaxis_title="Relative Scale (Ref=100%)", margin=dict(t=20))
        st.plotly_chart(fig_bar, use_container_width=True)

        # --- 3. LINE CHART (RHYTHM) ---
        
        m_trend = df_raw[df_raw['market'] == market].groupby('date').sum().reset_index()
        
        fig_line = go.Figure()
        # Intro (Green)
        fig_line.add_trace(go.Scatter(x=m_trend['date'], y=m_trend['intro_call_qty'], name='Intro Call',
                                     line=dict(color='#2E7D32', width=3)))
        fig_line.add_trace(go.Scatter(x=m_trend['date'], y=m_trend['intro_followup_qty'], name='Intro Followup',
                                     line=dict(color='#2E7D32', width=2, dash='dot')))
        # Sales (Orange)
        fig_line.add_trace(go.Scatter(x=m_trend['date'], y=m_trend['sales_call_qty'], name='Sales Call',
                                     line=dict(color='#EF6C00', width=3)))
        fig_line.add_trace(go.Scatter(x=m_trend['date'], y=m_trend['sales_followup_qty'], name='Sales Followup',
                                     line=dict(color='#EF6C00', width=2, dash='dot')))
        
        fig_line.update_layout(template="plotly_white", height=450, hovermode="x unified",
                              xaxis_title="Timeline", yaxis_title="Calls Qty",
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_line, use_container_width=True)
        st.markdown("---")

# --- 5. DATA LAB SECTION ---
elif role == "Data Lab (Explorer)":
    st.title("🧬 Explorer Lab")
    from pygwalker.api.streamlit import StreamlitRenderer
    # Используем v_analytics_calls для глубокого анализа
    res_lab = supabase.table("v_analytics_calls").select("*").limit(5000).execute()
    df_lab = pd.DataFrame(res_lab.data)
    if not df_lab.empty:
        renderer = StreamlitRenderer(df_lab)
        renderer.explorer()
    else:
        st.warning("No data found in v_analytics_calls.")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption(f"Last sync: {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.write("2026 © Correlli Intelligence")
