import streamlit as st
from datetime import datetime, date, timedelta
from database import fetch_view_data
from styles import get_css
from views.ceo_view import render_ceo_dashboard
from views.cmo_view import render_cmo_analytics
from views.cso_view import render_cso_dashboard
from views.lab_view import render_data_lab

BUILD_ID = "2026-01-17-deploy-02"


def _get_prev_ops_day(today: date) -> date:
    d = today - timedelta(days=1)
    while d.weekday() > 4:
        d = d - timedelta(days=1)
    return d


def _get_prev_ops_week(today: date) -> tuple[date, date]:
    current_monday = today - timedelta(days=today.weekday())
    prev_monday = current_monday - timedelta(days=7)
    prev_friday = prev_monday + timedelta(days=4)
    return prev_monday, prev_friday


def _get_prev_ops_month(today: date) -> tuple[date, date]:
    first_this_month = date(today.year, today.month, 1)
    prev_month_last_day = first_this_month - timedelta(days=1)
    prev_month_first_day = date(prev_month_last_day.year, prev_month_last_day.month, 1)
    return prev_month_first_day, prev_month_last_day


def _get_ops_today(today: date) -> date:
    d = today
    while d.weekday() > 4:
        d = d - timedelta(days=1)
    return d


def _get_this_week(today: date) -> tuple[date, date]:
    end_d = _get_ops_today(today)
    start_d = today - timedelta(days=today.weekday())
    return start_d, end_d


def _get_this_month(today: date) -> tuple[date, date]:
    end_d = _get_ops_today(today)
    start_d = date(today.year, today.month, 1)
    return start_d, end_d


def _determine_market(pipeline):
    p = str(pipeline).upper()
    if p.startswith("CZ"):
        return "CZ"
    if p.startswith("SK"):
        return "SK"
    if p.startswith("RUK"):
        return "RUK"
    return "Others"

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
    st.sidebar.caption(f"Build: {BUILD_ID}")
    
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

    if st.session_state.page == "CSO":
        st.sidebar.markdown("### CSO Sections")
        st.sidebar.markdown("- [Operations Feed](#operations-feed)")
        st.sidebar.markdown("- [Manager Productivity Timeline](#manager-productivity-timeline)")
        st.sidebar.markdown("- [Call Control](#call-control)")
        st.sidebar.markdown("- [Friction & Resistance](#friction-and-resistance)")
        st.sidebar.markdown("- [Discovery Depth Index](#discovery-depth-index)")
    
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
                or k in {
                    "date_range_v2",
                    "all_time_v1",
                    "selected_managers_v1",
                    "date_preset_v1",
                }
            ):
                st.session_state.pop(k, None)
        st.rerun()
    
    # Date range filter
    today = date.today()
    start_of_year = date(2025, 1, 1)

    if st.session_state.get("page") == "CSO" and "date_preset_v1" not in st.session_state:
        prev_day = _get_prev_ops_day(today)
        st.session_state["date_range_v2"] = [prev_day, prev_day]
        st.session_state["all_time_v1"] = False
        st.session_state["date_preset_v1"] = "prev_day"

    st.sidebar.markdown("### Quick Date Presets")
    left_col, right_col = st.sidebar.columns(2)
    current_preset = st.session_state.get("date_preset_v1", None)

    with left_col:
        if st.button("Prev Day", use_container_width=True, type="primary" if current_preset == "prev_day" else "secondary"):
            prev_day = _get_prev_ops_day(today)
            st.session_state["date_range_v2"] = [prev_day, prev_day]
            st.session_state["all_time_v1"] = False
            st.session_state["date_preset_v1"] = "prev_day"
            st.rerun()
        if st.button("Prev Week", use_container_width=True, type="primary" if current_preset == "prev_week" else "secondary"):
            start_w, end_w = _get_prev_ops_week(today)
            st.session_state["date_range_v2"] = [start_w, end_w]
            st.session_state["all_time_v1"] = False
            st.session_state["date_preset_v1"] = "prev_week"
            st.rerun()
        if st.button("Prev Month", use_container_width=True, type="primary" if current_preset == "prev_month" else "secondary"):
            start_m, end_m = _get_prev_ops_month(today)
            st.session_state["date_range_v2"] = [start_m, end_m]
            st.session_state["all_time_v1"] = False
            st.session_state["date_preset_v1"] = "prev_month"
            st.rerun()

    with right_col:
        if st.button("Today", use_container_width=True, type="primary" if current_preset == "today" else "secondary"):
            d = _get_ops_today(today)
            st.session_state["date_range_v2"] = [d, d]
            st.session_state["all_time_v1"] = False
            st.session_state["date_preset_v1"] = "today"
            st.rerun()
        if st.button("This Week", use_container_width=True, type="primary" if current_preset == "this_week" else "secondary"):
            start_d, end_d = _get_this_week(today)
            st.session_state["date_range_v2"] = [start_d, end_d]
            st.session_state["all_time_v1"] = False
            st.session_state["date_preset_v1"] = "this_week"
            st.rerun()
        if st.button("This Month", use_container_width=True, type="primary" if current_preset == "this_month" else "secondary"):
            start_d, end_d = _get_this_month(today)
            st.session_state["date_range_v2"] = [start_d, end_d]
            st.session_state["all_time_v1"] = False
            st.session_state["date_preset_v1"] = "this_month"
            st.rerun()

    all_time = st.sidebar.checkbox("All time", value=False, key="all_time_v1")
    if all_time:
        date_range = []
    else:
        date_range = st.sidebar.date_input(
            "Date Range",
            [start_of_year, today],
            key="date_range_v2",
        )
    
    df_raw_filters = fetch_view_data("Algonova_Calls_Raw")
    
    all_markets = []
    market_pipelines_map = {}
    all_managers = []
    
    if not df_raw_filters.empty:
        if "market" not in df_raw_filters.columns and "pipeline_name" in df_raw_filters.columns:
            df_raw_filters = df_raw_filters.copy()
            df_raw_filters["market"] = df_raw_filters["pipeline_name"].apply(_determine_market)

        if "market" in df_raw_filters.columns:
            all_markets = sorted(df_raw_filters["market"].dropna().unique().tolist())
            if "pipeline_name" in df_raw_filters.columns:
                for m in all_markets:
                    market_pipelines_map[m] = sorted(
                        df_raw_filters[df_raw_filters["market"] == m]["pipeline_name"].dropna().unique().tolist()
                    )

        if "manager" in df_raw_filters.columns:
            all_managers = sorted(df_raw_filters["manager"].dropna().unique().tolist())

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
