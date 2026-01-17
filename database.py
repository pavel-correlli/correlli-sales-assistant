import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os


def _get_nested_secret(section: str, key: str):
    try:
        return st.secrets[section][key]
    except Exception:
        return None


def _get_secret(key: str):
    try:
        return st.secrets[key]
    except Exception:
        return None


def _resolve_supabase_config():
    url = (
        _get_nested_secret("supabase", "url")
        or _get_secret("SUPABASE_URL")
        or _get_secret("supabase_url")
        or os.getenv("SUPABASE_URL")
    )
    key = (
        _get_nested_secret("supabase", "key")
        or _get_secret("SUPABASE_KEY")
        or _get_secret("SUPABASE_ANON_KEY")
        or _get_secret("supabase_key")
        or _get_secret("supabase_anon_key")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )
    return url, key

@st.cache_resource
def get_supabase_client() -> Client:
    url, key = _resolve_supabase_config()
    if not url or not key:
        st.error(
            "Supabase secrets не найдены. Добавь в Streamlit Secrets либо блок "
            "[supabase] с url/key, либо ключи SUPABASE_URL и SUPABASE_KEY."
        )
        st.stop()
    return create_client(url, key)

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
