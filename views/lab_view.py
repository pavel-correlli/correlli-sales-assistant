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

    with st.expander("🔎 Data Consistency Check (Raw vs v_ceo_iron_metrics)", expanded=True):
        df_raw_all = fetch_view_data("Algonova_Calls_Raw")
        df_iron = fetch_view_data("v_ceo_iron_metrics")

        if df_raw_all.empty:
            st.warning("Algonova_Calls_Raw returned no rows via API.")
        else:
            raw_counts = (
                df_raw_all.groupby("manager")
                .size()
                .reset_index(name="raw_calls")
                .sort_values("raw_calls", ascending=False)
            )

            if not df_iron.empty and "total_calls_volume" in df_iron.columns:
                iron_counts = (
                    df_iron.groupby("manager")["total_calls_volume"]
                    .sum()
                    .reset_index(name="iron_calls_volume")
                )
                iron_counts["iron_calls_volume"] = iron_counts["iron_calls_volume"].fillna(0).astype(int)

                comp = raw_counts.merge(iron_counts, on="manager", how="outer")
                comp["raw_calls"] = comp["raw_calls"].fillna(0).astype(int)
                comp["iron_calls_volume"] = comp["iron_calls_volume"].fillna(0).astype(int)
                comp["delta_raw_minus_iron"] = comp["raw_calls"] - comp["iron_calls_volume"]
                comp = comp.sort_values(["raw_calls", "iron_calls_volume"], ascending=False)

                st.write(
                    f"Total Raw Calls: {int(comp['raw_calls'].sum())} | "
                    f"Total Iron Calls Volume: {int(comp['iron_calls_volume'].sum())}"
                )
                st.dataframe(comp, hide_index=True, use_container_width=True)
            else:
                st.write(f"Total Raw Calls: {len(df_raw_all)}")
                st.dataframe(raw_counts, hide_index=True, use_container_width=True)

    df_raw = fetch_view_data("Algonova_Calls_Raw")
    
    if not df_raw.empty:
        renderer = StreamlitRenderer(df_raw)
        renderer.explorer()
    else:
        st.warning("No data to explore.")
