import streamlit as st
from pygwalker.api.streamlit import StreamlitRenderer
from database import fetch_view_data

def render_data_lab():
    st.title("🧬 Explorer Lab")
    
    # Try importing pygwalker, handle if missing
    try:
        from pygwalker.api.streamlit import StreamlitRenderer
        HAS_PYGWALKER = True
    except ImportError:
        HAS_PYGWALKER = False
        st.error("Pygwalker is not installed. Please install it to use the Data Lab.")
        return
        
    st.markdown("Explore the raw data visually.")

    df_raw = fetch_view_data("Algonova_Calls_Raw")
    
    if not df_raw.empty:
        renderer = StreamlitRenderer(df_raw)
        renderer.explorer()
    else:
        st.warning("No data to explore.")
