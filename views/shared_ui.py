import streamlit as st


def render_hint(text: str):
    st.caption(f"❓ {text}")


def render_data_health_volume(
    total_records_loaded: int,
    records_shown: int,
    date_range_in_result: tuple | None = None,
    expanded: bool = False,
):
    with st.expander("Data Health & Volume", expanded=expanded):
        st.write(f"**Total Records Loaded from DB:** {int(total_records_loaded)}")
        st.write(f"**Records Shown (after filters):** {int(records_shown)}")
        if date_range_in_result is not None:
            start, end = date_range_in_result
            st.write(f"**Date Range in Result:** {start} → {end}")
