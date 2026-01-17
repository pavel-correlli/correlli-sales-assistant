import streamlit as st
import pandas as pd
from supabase import create_client, Client

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

@st.cache_data(ttl=600)
def fetch_view_data(view_name: str, page_size: int = 1000):
    supabase = get_supabase_client()
    try:
        rows: list[dict] = []
        offset = 0
        total_count = None

        while True:
            res = (
                supabase.table(view_name)
                .select("*", count="exact")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if total_count is None:
                total_count = getattr(res, "count", None)

            batch = res.data or []
            rows.extend(batch)

            if len(batch) < page_size:
                break

            offset += page_size
            if offset > 500_000:
                break

        df = pd.DataFrame(rows)
        df.attrs["supabase_exact_count"] = total_count
        df.attrs["supabase_rows_loaded"] = len(rows)
        return df
    except Exception as e:
        st.error(f"Error fetching {view_name}: {e}")
        return pd.DataFrame()
