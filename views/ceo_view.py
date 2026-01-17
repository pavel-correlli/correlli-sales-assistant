import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import fetch_view_data

def render_ceo_dashboard(date_range, selected_markets, selected_pipelines):
    st.title("Strategic Strategic Radar")
    
    # Load Data
    with st.spinner("Loading strategic insights..."):
        # Use new enhanced views
        df_enhanced = fetch_view_data("v_analytics_calls_enhanced")
        df_iron = fetch_view_data("v_ceo_iron_metrics")
        
    # Apply Filters
    # For iron metrics (aggregated)
    if not df_iron.empty:
        df_iron = df_iron[
            (df_iron['market'].isin(selected_markets)) & 
            (df_iron['pipeline_name'].isin(selected_pipelines))
        ]
        
    # For enhanced calls (raw-like)
    if not df_enhanced.empty:
        if "call_datetime" in df_enhanced.columns:
            df_enhanced["call_datetime"] = pd.to_datetime(df_enhanced["call_datetime"], errors="coerce", utc=True)
            df_enhanced["call_date"] = df_enhanced["call_datetime"].dt.date
        else:
            df_enhanced["call_date"] = pd.NaT
        mask_raw = (
            (df_enhanced['market'].isin(selected_markets)) & 
            (df_enhanced['pipeline_name'].isin(selected_pipelines))
        )
        if len(date_range) == 2:
            mask_raw = mask_raw & (df_enhanced['call_date'] >= date_range[0]) & (df_enhanced['call_date'] <= date_range[1])
        df_enhanced = df_enhanced[mask_raw].copy()
        
        # Ensure Average_quality is numeric
        if 'Average_quality' in df_enhanced.columns:
            df_enhanced['Average_quality'] = pd.to_numeric(df_enhanced['Average_quality'], errors='coerce')

    # --- Iron Metrics (Top Row) ---
    m1, m2, m3, m4 = st.columns(4)
    
    if not df_iron.empty:
        # Aggregations
        occ_intro = df_iron['occ_intro_leads'].sum()
        occ_sales = df_iron['occ_sales_leads'].sum()
        
        # Calculate Friction & Vague Indices from aggregated view
        # Vague Index = Vague Calls / Total Calls * 100
        total_vague = df_iron['total_vague_calls'].sum()
        total_vol = df_iron['total_calls_volume'].sum()
        vague_index = (total_vague / total_vol * 100) if total_vol > 0 else 0
        
        # Friction Index: Followups / Primaries
        intro_fu = df_iron['intro_followups'].sum()
        intro_prim = df_iron['intro_primaries'].sum()
        friction_intro = (intro_fu / intro_prim) if intro_prim > 0 else 0
        
        sales_fu = df_iron['sales_followups'].sum()
        sales_prim = df_iron['sales_primaries'].sum()
        friction_sales = (sales_fu / sales_prim) if sales_prim > 0 else 0
        
        m1.metric("OCC Intro", f"{occ_intro}", help="Leads closed/processed after a single intro call.")
        m2.metric("OCC Sales", f"{occ_sales}", help="Leads closed/processed after a single sales call (logic: follow-ups are expected after trial lessons).")
        m3.metric("Friction Intro", f"{friction_intro:.2f}", help="Resistance level: how many follow-ups it takes to process one primary intro call.")
        m4.metric("Vague Index", f"{vague_index:.1f}%", help="Percentage of calls with no clear agreement.")
    else:
        st.warning("No data for Iron Metrics")

    st.markdown("---")

    # --- ADVANCED CHARTS ROW 1 ---
    col1, col2 = st.columns(2)
    
    # Sunburst Chart (Market Segmentation)
    # Hierarchy: market -> manager -> call_category -> call_outcome
    with col1:
        st.subheader("Market Segmentation Deep Dive")
        if not df_enhanced.empty:
            # Grouping
            sb_cols = ['market', 'manager', 'call_category', 'call_outcome']
            # Filter columns that exist
            valid_cols = [c for c in sb_cols if c in df_enhanced.columns]
            
            if len(valid_cols) == 4:
                sb_data = df_enhanced.groupby(valid_cols).size().reset_index(name='count')
                fig_sb = px.sunburst(
                    sb_data, 
                    path=valid_cols, 
                    values='count',
                    title="Market Structure: Manager -> Type -> Outcome",
                    template='plotly_white',
                    color='call_outcome',
                    color_discrete_map={'Success': '#2ecc71', 'Vague': '#e74c3c'}
                )
                st.plotly_chart(fig_sb, use_container_width=True)
            else:
                st.error("Missing columns for Sunburst")
        else:
            st.warning("No data for Sunburst")

    # Vague Index Proportional (100% Stacked Bar)
    with col2:
        st.subheader("Vague Index Proportional")
        if not df_enhanced.empty:
            # Group by Market and Outcome
            vi_data = df_enhanced.groupby(['market', 'call_outcome']).size().reset_index(name='count')
            
            fig_vi = px.bar(
                vi_data, 
                x='market', 
                y='count', 
                color='call_outcome', 
                title="Success vs Vague Ratio by Market",
                template='plotly_white',
                barmode='stack', 
                color_discrete_map={'Success': '#2ecc71', 'Vague': '#e74c3c'}
            )
            st.plotly_chart(fig_vi, use_container_width=True)
        else:
            st.warning("No data for Vague Index Chart")
