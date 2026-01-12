import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go  # Добавлен недостающий импорт
from supabase import create_client
from datetime import datetime, timedelta

# --- 1. CONFIG ---
st.set_page_config(page_title="Executive Analytics Radar", layout="wide", page_icon="🦅")

# Чистый интерфейс без темных плашек
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
    /* Увеличенный шрифт для названий рынков */
    .market-header {
        font-size: 32px !important;
        font-weight: 800 !important;
        color: #1a1a1a;
        margin-top: 40px !important;
        margin-bottom: 20px !important;
        border-bottom: 2px solid #f0f2f6;
        padding-bottom: 10px;
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
    
    # Оставляем только нужные рынки
    df = df[df['market'].isin(['CZ', 'RUK', 'SK'])]
    df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y')
    
    num_cols = ['friction_intro', 'friction_sales', 'viscosity_index', 'pipeline_balance', 
                'avg_quality_score', 'total_calls_qty', 'vague_qty', 'not_interested_qty',
                'intro_call_qty', 'intro_followup_qty', 'sales_call_qty', 'sales_followup_qty']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_metrics = load_data()

# --- 3. SIDEBAR ---
st.sidebar.title("Correlli Platform")
role = st.sidebar.radio("Navigation:", ["CEO (Strategic Radar)", "Data Lab (Explorer)"])

# --- 4. CEO SECTION ---
if role == "CEO (Strategic Radar)":
    st.title("🦅 Strategic Intelligence Control")
    
    # ПАНЕЛЬ УПРАВЛЕНИЯ (Analysis Window перенесен сюда)
    with st.container():
        c1, c2, c3 = st.columns(3)
        period_type = c1.selectbox("Analysis Period:", ["Day", "Week", "Month"], index=1)
        analysis_start = c2.date_input("Analysis Start Date:", df_metrics['date'].max())
        reference_start = c3.date_input("Reference Start Date:", df_metrics['date'].max() - timedelta(days=7))

    d_map = {"Day": 1, "Week": 7, "Month": 30}
    days = d_map[period_type]
    
    curr_range = (pd.to_datetime(analysis_start), pd.to_datetime(analysis_start) + timedelta(days=days-1))
    ref_range = (pd.to_datetime(reference_start), pd.to_datetime(reference_start) + timedelta(days=days-1))
    
    df_curr = df_metrics[(df_metrics['date'] >= curr_range[0]) & (df_metrics['date'] <= curr_range[1])]
    df_ref = df_metrics[(df_metrics['date'] >= ref_range[0]) & (df_metrics['date'] <= ref_range[1])]

    # TOOLTIPS С ФОРМУЛАМИ LaTeX
    tt_quality = "**Avg Quality Score (0-10)**: Mean of (Structure, Communication, Trust Building, Objection Handling, Engagement, Technical Quality, Scheduling Efficiency)."
    tt_viscosity = r"**Viscosity Index**: $$ \frac{Vague + Not Interested}{Total Calls} \times 100\% $$. Measures communication imprecision."
    tt_fric_intro = r"**Intro Friction**: $$ \frac{Intro Followup}{Intro Initial} $$. Touches needed to schedule a Trial Lesson."
    tt_fric_sales = r"**Sales Friction**: $$ \frac{Sales Followup}{Sales Initial} $$. Resistance after Trial Lesson presentation."

    active_markets = sorted(df_curr['market'].unique())

    for market in active_markets:
        # Крупный заголовок рынка
        st.markdown(f"<div class='market-header'>Market Dynamics: {market.upper()}</div>", unsafe_allow_html=True)
        
        m_curr = df_curr[df_curr['market'] == market]
        m_ref = df_ref[df_ref['market'] == market]
        
        # --- МЕТРИКИ ---
        m1, m2, m3, m4 = st.columns(4)
        def get_delta(c_df, r_df, col):
            c_val = c_df[col].mean() if not c_df.empty else 0
            r_val = r_df[col].mean() if not r_df.empty else 0
            return c_val, c_val - r_val

        v, d = get_delta(m_curr, m_ref, 'avg_quality_score'); m1.metric("Avg Quality", f"{v:.2f}", delta=f"{d:.2f}", help=tt_quality)
        v, d = get_delta(m_curr, m_ref, 'viscosity_index'); m2.metric("Viscosity Index", f"{v:.1f}%", delta=f"{d:.1f}%", delta_color="inverse", help=tt_viscosity)
        v, d = get_delta(m_curr, m_ref, 'friction_intro'); m3.metric("Intro Friction", f"{v:.2f}", delta=f"{d:.2f}", delta_color="inverse", help=tt_fric_intro)
        v, d = get_delta(m_curr, m_ref, 'friction_sales'); m4.metric("Sales Friction", f"{v:.2f}", delta=f"{d:.2f}", delta_color="inverse", help=tt_fric_sales)

        # --- СРАВНИТЕЛЬНЫЙ ГРАФИК (ЛОГИКА 100%) ---
        ref_total = m_ref['total_calls_qty'].sum()
        curr_total = m_curr['total_calls_qty'].sum()
        
        # Масштабируем Current относительно Reference (100%)
        rel_scale = (curr_total / ref_total * 100) if ref_total > 0 else 100
        
        chart_data = []
        # Total Calls (Scale for height, Display for absolute numbers)
        chart_data.append({"Period": "Reference", "Metric": "Total Calls", "Display": f"{int(ref_total)}", "Value": 100})
        chart_data.append({"Period": "Current", "Metric": "Total Calls", "Display": f"{int(curr_total)}", "Value": rel_scale})
        
        # Ratios (Vague & Not Interested)
        for label, d_sub, total in [("Reference", m_ref, ref_total), ("Current", m_curr, curr_total)]:
            v_pct = (d_sub['vague_qty'].sum() / total * 100) if total > 0 else 0
            ni_pct = (d_sub['not_interested_qty'].sum() / total * 100) if total > 0 else 0
            chart_data.append({"Period": label, "Metric": "Vague Ratio (%)", "Display": f"{v_pct:.1f}%", "Value": v_pct})
            chart_data.append({"Period": label, "Metric": "Not Interested (%)", "Display": f"{ni_pct:.1f}%", "Value": ni_pct})

        df_p = pd.DataFrame(chart_data)
        fig_bar = px.bar(df_p, x="Metric", y="Value", color="Period", barmode="group",
                         text="Display", height=400, template="plotly_white",
                         color_discrete_map={"Current": "#4CAF50", "Reference": "#CED4DA"})
        fig_bar.update_layout(yaxis_title="Relative Scale (Ref=100%)", showlegend=True, margin=dict(t=10))
        st.plotly_chart(fig_bar, use_container_width=True)

        # --- ЛИНЕЙНЫЙ ГРАФИК (RHYTHM) ---
        m_trend = df_metrics[df_metrics['market'] == market].groupby('date').sum().reset_index()
        
        fig_line = go.Figure()
        # Intro: Зеленый (#2E7D32). Call - сплошная, Followup - пунктир.
        fig_line.add_trace(go.Scatter(x=m_trend['date'], y=m_trend['intro_call_qty'], name='Intro Call',
                                     line=dict(color='#2E7D32', width=3)))
        fig_line.add_trace(go.Scatter(x=m_trend['date'], y=m_trend['intro_followup_qty'], name='Intro Followup',
                                     line=dict(color='#2E7D32', width=2, dash='dot')))
        
        # Sales: Оранжевый (#EF6C00). Call - сплошная, Followup - пунктир.
        fig_line.add_trace(go.Scatter(x=m_trend['date'], y=m_trend['sales_call_qty'], name='Sales Call',
                                     line=dict(color='#EF6C00', width=3)))
        fig_line.add_trace(go.Scatter(x=m_trend['date'], y=m_trend['sales_followup_qty'], name='Sales Followup',
                                     line=dict(color='#EF6C00', width=2, dash='dot')))
        
        fig_line.update_layout(template="plotly_white", height=450, hovermode="x unified",
                              xaxis_title="Timeline", yaxis_title="Calls Qty", 
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_line, use_container_width=True)
        st.markdown("---")

elif role == "Data Lab (Explorer)":
    st.title("🧬 Explorer Lab")
    from pygwalker.api.streamlit import StreamlitRenderer
    res = supabase.table("v_analytics_calls").select("*").execute()
    renderer = StreamlitRenderer(pd.DataFrame(res.data))
    renderer.explorer()
