import streamlit as st
from datetime import datetime, date, timedelta
from database import fetch_view_data
from styles import get_css
from views.ceo_view import render_ceo_dashboard
from views.cmo_view import render_cmo_analytics
from views.cso_view import render_cso_dashboard
from views.lab_view import render_data_lab

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Executive Analytics Radar", layout="wide", page_icon="🦅")
st.markdown(get_css(), unsafe_allow_html=True)

# --- 2. STATE & NAVIGATION ---
if 'page' not in st.session_state:
    st.session_state.page = "CEO"

def set_page(page_name):
    st.session_state.page = page_name

def render_sidebar():
    st.sidebar.title("Algonova Calls Control")
    
    # Volumetric Buttons Navigation
    st.sidebar.markdown("### Navigation")
    
    if st.sidebar.button("CEO", type="primary" if st.session_state.page == "CEO" else "secondary"):
        set_page("CEO")
    if st.sidebar.button("CMO", type="primary" if st.session_state.page == "CMO" else "secondary"):
        set_page("CMO")
    if st.sidebar.button("CSO", type="primary" if st.session_state.page == "CSO" else "secondary"):
        set_page("CSO")
    if st.sidebar.button("Data Lab", type="primary" if st.session_state.page == "LAB" else "secondary"):
        set_page("LAB")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Global Filters")

    if st.sidebar.button("Reset filters", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        keys = list(st.session_state.keys())
        for k in keys:
            if (
                k.startswith("chk_market_")
                or k.startswith("chk_pl_")
                or k in {"date_range_v2", "all_time_v1", "selected_managers_v1"}
            ):
                st.session_state.pop(k, None)
        st.rerun()
    
    # Date range filter
    today = date.today()
    start_of_year = date(2025, 1, 1)
    all_time = st.sidebar.checkbox("All time", value=False, key="all_time_v1")
    if all_time:
        date_range = []
    else:
        date_range = st.sidebar.date_input(
            "Date Range",
            [start_of_year, today],
            key="date_range_v2",
        )
    
    # Fetch common filter data
    df_pulse = fetch_view_data("v_ceo_daily_pulse")
    
    all_markets = []
    market_pipelines_map = {}
    all_managers = []
    
    if not df_pulse.empty:
        all_markets = sorted(df_pulse['market'].unique().tolist())
        for m in all_markets:
             market_pipelines_map[m] = sorted(df_pulse[df_pulse['market'] == m]['pipeline_name'].unique().tolist())
        
        # Fetch managers from raw data or dedicated view to ensure completeness
        # Using raw table to get ALL managers regardless of recent activity
        df_raw_managers = fetch_view_data("Algonova_Calls_Raw")
        if not df_raw_managers.empty and 'manager' in df_raw_managers.columns:
            all_managers = sorted(df_raw_managers['manager'].dropna().unique().tolist())

    # --- Cascading Checkbox Logic ---
    st.sidebar.markdown("### Markets & Pipelines")
    
    selected_markets = []
    selected_pipelines = []
    
    for market in all_markets:
        market_key = f"chk_market_{market}"
        is_market_selected = st.sidebar.checkbox(f"Market: {market}", value=True, key=market_key)
        
        if is_market_selected:
            selected_markets.append(market)
            available_pipelines = market_pipelines_map.get(market, [])
            if available_pipelines:
                st.sidebar.markdown(f"**{market} Pipelines:**")
                for pl in available_pipelines:
                    pl_key = f"chk_pl_{market}_{pl}"
                    is_pl_selected = st.sidebar.checkbox(f"{pl}", value=True, key=pl_key)
                    if is_pl_selected:
                        selected_pipelines.append(pl)
            st.sidebar.markdown("---")
            
    # --- Manager Filter ---
    st.sidebar.markdown("### Managers")
    selected_managers = st.sidebar.multiselect(
        "Select Managers",
        options=all_managers,
        default=all_managers,
        key="selected_managers_v1",
        help="Filter data by specific managers. Default is ALL."
    )
            
    return date_range, selected_markets, selected_pipelines, selected_managers

# --- 3. MAIN ROUTER ---
def main():
    date_range, selected_markets, selected_pipelines, selected_managers = render_sidebar()
    
    page = st.session_state.page
    
    if page == "CEO":
        render_ceo_dashboard(date_range, selected_markets, selected_pipelines)
    elif page == "CMO":
        render_cmo_analytics(date_range, selected_markets, selected_pipelines)
    elif page == "CSO":
        render_cso_dashboard(date_range, selected_markets, selected_pipelines, selected_managers)
    elif page == "LAB":
        render_data_lab()

if __name__ == "__main__":
    main()
