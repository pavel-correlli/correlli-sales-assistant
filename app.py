import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import fetch_view_data, ensure_chart_views, rpc_df, rpc_df_long
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
if "ui_theme_v1" not in st.session_state:
    st.session_state["ui_theme_v1"] = "dark"

st.set_page_config(page_title="Conversation Intelligence Analytics", layout="wide")
st.markdown(get_css(st.session_state["ui_theme_v1"]), unsafe_allow_html=True)

# --- 2. STATE & NAVIGATION ---
if 'page' not in st.session_state:
    st.session_state.page = "CEO"

def set_page(page_name):
    st.session_state.page = page_name

def render_sidebar():
    def _render_sections(section_items: list[tuple[str, str]]):
        links_html = "\n".join(
            [f'<a class="sidebar-section-link" href="#{anchor}">{label}</a>' for label, anchor in section_items]
        )
        st.sidebar.markdown(f'<div class="sidebar-sections sidebar-sections-inline">{links_html}</div>', unsafe_allow_html=True)

    st.sidebar.markdown(
        f"""
        <div class="sidebar-brand">
          <div class="sidebar-brand-inner">
            <img
              class="sidebar-logo"
              src="https://static.tildacdn.one/tild3465-3861-4835-b137-616235373932/Logo_de_Algonova_by_.svg"
              alt="Algonova"
            />
            <div class="sidebar-title">Conversation Intelligence Dashboard</div>
            <div class="sidebar-subtitle">Build: {BUILD_ID} by Correlli Engineering</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    sections_map: dict[str, list[tuple[str, str]]] = {
        "CSO": [
            ("Operations Feed", "operations-feed"),
            ("Manager Productivity Timeline", "manager-productivity-timeline"),
            ("Call Control", "call-control"),
            ("Friction & Resistance", "friction-and-resistance"),
            ("Discovery Depth Index", "discovery-depth-index"),
        ],
        "CEO": [
            ("Total Friction", "total-friction"),
            ("Vague Index by Market", "vague-index-by-market"),
            ("One-Call-Close Rate by Pipeline", "one-call-close-rate-by-pipeline"),
            ("Talk Time per Lead by Pipeline", "talk-time-per-lead-by-pipeline"),
            ("Total Talk Time by Pipeline", "total-talk-time-by-pipeline"),
        ],
        "CMO": [
            ("Traffic Viscosity vs Intro Friction", "traffic-viscosity-vs-intro-friction"),
            ("Intro Friction / Traffic Manager", "intro-friction-traffic-manager"),
            ("Goal Frequency / Pipeline", "goal-heatmap"),
            ("Objection Frequency / Pipeline", "objection-heatmap"),
            ("Fear Frequency / Pipeline", "fear-heatmap"),
        ],
    }

    if st.sidebar.button(
        "CEO",
        key="nav_btn_ceo",
        type="primary" if st.session_state.page == "CEO" else "secondary",
        use_container_width=True,
    ):
        if st.session_state.page != "CEO":
            set_page("CEO")
            st.rerun()
    if st.session_state.page == "CEO":
        _render_sections(sections_map["CEO"])

    if st.sidebar.button(
        "CMO",
        key="nav_btn_cmo",
        type="primary" if st.session_state.page == "CMO" else "secondary",
        use_container_width=True,
    ):
        if st.session_state.page != "CMO":
            set_page("CMO")
            st.rerun()
    if st.session_state.page == "CMO":
        _render_sections(sections_map["CMO"])

    if st.sidebar.button(
        "CSO",
        key="nav_btn_cso",
        type="primary" if st.session_state.page == "CSO" else "secondary",
        use_container_width=True,
    ):
        if st.session_state.page != "CSO":
            set_page("CSO")
            st.rerun()
    if st.session_state.page == "CSO":
        _render_sections(sections_map["CSO"])

    if st.sidebar.button(
        "Data Lab",
        key="nav_btn_lab",
        type="primary" if st.session_state.page == "LAB" else "secondary",
        use_container_width=True,
    ):
        if st.session_state.page != "LAB":
            set_page("LAB")
            st.rerun()
    
    st.sidebar.markdown("---")
    summary_placeholder = st.sidebar.empty()

    if st.sidebar.button("Reset Filters", use_container_width=True):
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

    all_time = st.sidebar.checkbox("All Time", value=False, key="all_time_v1")
    if all_time:
        date_range = []
    else:
        if "date_range_v2" in st.session_state:
            initial_date_range = st.session_state["date_range_v2"]
        elif st.session_state.get("page") == "CSO" and st.session_state.get("date_preset_v1") == "prev_day":
            prev_day = _get_prev_ops_day(today)
            initial_date_range = [prev_day, prev_day]
        else:
            initial_date_range = [start_of_year, today]

        date_range = st.sidebar.date_input(
            "Date Range",
            initial_date_range,
            key="date_range_v2",
        )

    def _load_sidebar_dims():
        df_mp = rpc_df_long("rpc_app_markets_pipelines")
        df_mgr = rpc_df_long("rpc_app_managers")
        if df_mp.empty and df_mgr.empty:
            df_raw_filters = fetch_view_data("Algonova_Calls_Raw")
            if df_raw_filters.empty:
                return [], {}, []
            if "market" not in df_raw_filters.columns and "pipeline_name" in df_raw_filters.columns:
                df_raw_filters = df_raw_filters.copy()
                df_raw_filters["market"] = df_raw_filters["pipeline_name"].apply(_determine_market)
            markets = sorted(df_raw_filters.get("market", pd.Series(dtype=str)).dropna().unique().tolist())
            market_pipelines_map = {}
            if "pipeline_name" in df_raw_filters.columns and "market" in df_raw_filters.columns:
                for m in markets:
                    market_pipelines_map[m] = sorted(
                        df_raw_filters[df_raw_filters["market"] == m]["pipeline_name"].dropna().unique().tolist()
                    )
            managers = sorted(df_raw_filters.get("manager", pd.Series(dtype=str)).dropna().unique().tolist())
            return markets, market_pipelines_map, managers

        if df_mp.empty or not {"market", "pipeline_name"}.issubset(df_mp.columns):
            all_markets = []
            market_pipelines_map = {}
        else:
            df_mp["market"] = df_mp["market"].astype(str)
            df_mp["pipeline_name"] = df_mp["pipeline_name"].astype(str)
            all_markets = sorted(df_mp["market"].dropna().unique().tolist())
            market_pipelines_map = {
                m: sorted(df_mp[df_mp["market"] == m]["pipeline_name"].dropna().unique().tolist())
                for m in all_markets
            }

        if df_mgr.empty or "manager" not in df_mgr.columns:
            all_managers = []
        else:
            df_mgr["manager"] = df_mgr["manager"].astype(str)
            all_managers = sorted(df_mgr["manager"].dropna().unique().tolist())

        return all_markets, market_pipelines_map, all_managers

    all_markets, market_pipelines_map, all_managers = _load_sidebar_dims()

    # --- Cascading Checkbox Logic ---
    st.sidebar.markdown("### Markets & Pipelines")
    
    selected_markets = []
    selected_pipelines = []

    default_markets = {"CZ", "RUK", "SK"}
    
    for market in all_markets:
        market_key = f"chk_market_{market}"
        if market_key not in st.session_state:
            st.session_state[market_key] = market in default_markets
        is_market_selected = st.sidebar.checkbox(
            f"Market: {market}",
            value=market in default_markets,
            key=market_key,
        )
        
        if is_market_selected:
            selected_markets.append(market)
            available_pipelines = market_pipelines_map.get(market, [])
            if available_pipelines:
                st.sidebar.markdown(f"**{market} Pipelines:**")
                for pl in available_pipelines:
                    pl_key = f"chk_pl_{market}_{pl}"
                    if pl_key not in st.session_state:
                        st.session_state[pl_key] = (
                            market in default_markets
                            and pl in {market, f"{market} | Online", f"{market} | TCM"}
                        )
                    is_pl_selected = st.sidebar.checkbox(
                        f"{pl}",
                        value=(
                            market in default_markets
                            and pl in {market, f"{market} | Online", f"{market} | TCM"}
                        ),
                        key=pl_key,
                    )
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

    date_start = date_range[0] if len(date_range) == 2 else None
    date_end = date_range[1] if len(date_range) == 2 else None
    summary_params = {
        "date_start": date_start.isoformat() if date_start else None,
        "date_end": date_end.isoformat() if date_end else None,
        "markets": selected_markets or [],
        "pipelines": selected_pipelines or [],
        "managers": selected_managers or [],
    }
    summary_df = rpc_df("rpc_app_calls_summary", summary_params)
    summary = summary_df.iloc[0].to_dict() if not summary_df.empty else {"total_rows": 0, "filtered_rows": 0, "min_call_date": None, "max_call_date": None}
    total_rows = int(summary.get("total_rows") or 0)
    filtered_rows = int(summary.get("filtered_rows") or 0)
    min_d = summary.get("min_call_date")
    max_d = summary.get("max_call_date")
    date_range_text = f"{min_d} → {max_d}" if min_d and max_d else "—"

    summary_placeholder.markdown(
        f"**Showing Calls**\n\n{filtered_rows} / {total_rows}\n\n**Date Range in Result**\n\n{date_range_text}"
    )
            
    return date_range, selected_markets, selected_pipelines, selected_managers

# --- 3. MAIN ROUTER ---
def main():
    ensure_chart_views()
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
