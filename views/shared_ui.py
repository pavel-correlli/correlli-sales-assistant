import streamlit as st
from app_i18n import t


def render_hint(text: str):
    st.caption(f"{t('shared.hint_prefix')}: {text}")


def render_data_health_volume(
    total_records_loaded: int,
    records_shown: int,
    date_range_in_result: tuple | None = None,
    expanded: bool = False,
):
    with st.expander(t("shared.data_health_volume"), expanded=expanded):
        st.write(f"**{t('shared.total_records')}:** {int(total_records_loaded)}")
        st.write(f"**{t('shared.records_shown')}:** {int(records_shown)}")
        if date_range_in_result is not None:
            start, end = date_range_in_result
            st.write(f"**{t('shared.date_range_result')}:** {start} -> {end}")

