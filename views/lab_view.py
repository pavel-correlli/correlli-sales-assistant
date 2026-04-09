import streamlit as st
from database import fetch_view_data
from i18n import t


def render_data_lab():
    st.title(t("lab.title"))

    try:
        from pygwalker.api.streamlit import StreamlitRenderer
    except ImportError:
        st.error(t("lab.pygwalker_missing"))
        return

    st.markdown(t("lab.description"))

    df_raw = fetch_view_data("Algonova_Calls_Raw")
    if not df_raw.empty:
        renderer = StreamlitRenderer(df_raw)
        renderer.explorer()
    else:
        st.warning(t("lab.no_data"))
