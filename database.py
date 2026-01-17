import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
import time
import httpx
import psycopg2


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
def _derive_pooler_config(cfg: dict) -> dict | None:
    host = str(cfg.get("host", "")).strip()
    if host.startswith("db.") and host.endswith(".supabase.co"):
        parts = host.split(".")
        if len(parts) >= 3:
            project_ref = parts[1]
            user = str(cfg.get("user", "")).strip()
            if user and "." not in user:
                user = f"{user}.{project_ref}"
            return {
                "host": "aws-1-eu-west-1.pooler.supabase.com",
                "port": int(cfg.get("pooler_port", 6543)),
                "name": str(cfg.get("name", "postgres")),
                "user": user,
                "pass": str(cfg.get("pass", "")),
            }
    return None


def _connect_postgres(cfg: dict):
    def _connect(host: str, port: int, user: str):
        return psycopg2.connect(
            host=host,
            port=int(port),
            database=cfg["name"],
            user=user,
            password=cfg["pass"],
            sslmode="require",
        )

    host = str(cfg.get("host", "")).strip()
    port = int(cfg.get("port", 5432))
    user = str(cfg.get("user", "")).strip()
    try:
        return _connect(host, port, user)
    except Exception:
        pooler = _derive_pooler_config(cfg)
        if not pooler or not pooler.get("user"):
            raise
        return psycopg2.connect(
            host=pooler["host"],
            port=pooler["port"],
            database=pooler["name"],
            user=pooler["user"],
            password=pooler["pass"],
            sslmode="require",
        )


def get_supabase_client() -> Client:
    url, key = _resolve_supabase_config()
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
    rows: list[dict] = []
    offset = 0
    total_count = None
    max_retries = 3
    retry_delay = 2 # seconds

    try:
        while True:
            batch = None
            for attempt in range(max_retries):
                try:
                    res = (
                        supabase.table(view_name)
                        .select("*", count="exact")
                        .range(offset, offset + page_size - 1)
                        .execute()
                    )
                    if total_count is None:
                        total_count = getattr(res, "count", None)
                    batch = res.data or []
                    break # Success, exit retry loop
                except (httpx.ConnectError, httpx.RemoteProtocolError, Exception) as e:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1)) # Exponential-ish backoff
                        continue
                    else:
                        raise e

            if batch is None: # Should not happen if max_retries > 0
                break
                
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


def normalize_calls_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df

    out = df.copy()
    if "call_datetime" in out.columns:
        out["call_datetime"] = pd.to_datetime(out["call_datetime"], errors="coerce", utc=True)
        out["call_date"] = out["call_datetime"].dt.date
    elif "call_date" not in out.columns:
        out["call_date"] = pd.NaT

    if "Average_quality" in out.columns:
        out["Average_quality"] = pd.to_numeric(out["Average_quality"], errors="coerce")

    if "call_duration_sec" in out.columns:
        out["call_duration_sec"] = pd.to_numeric(out["call_duration_sec"], errors="coerce").fillna(0)

    return out


def add_outcome_category(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df

    out = df.copy()
    if "next_step_type" not in out.columns:
        out["outcome_category"] = "Other"
        return out

    ns = out["next_step_type"].astype(str).str.lower()
    out["outcome_category"] = "Defined Next Step"
    out.loc[ns.str.contains("vague", na=False), "outcome_category"] = "Vague"
    return out


def compute_friction_index(
    df: pd.DataFrame,
    group_cols: list[str],
    primary_types: list[str],
    followup_types: list[str],
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=[*group_cols, "primaries", "followups", "friction_index"])

    if "call_type" not in df.columns:
        base = df[group_cols].drop_duplicates().copy()
        base["primaries"] = 0
        base["followups"] = 0
        base["friction_index"] = 0.0
        return base

    g = (
        df.groupby(group_cols, dropna=False)
        .agg(
            primaries=("call_type", lambda s: int(s.isin(primary_types).sum())),
            followups=("call_type", lambda s: int(s.isin(followup_types).sum())),
        )
        .reset_index()
    )
    g["friction_index"] = 0.0
    mask = g["primaries"] > 0
    g.loc[mask, "friction_index"] = (g.loc[mask, "followups"] / g.loc[mask, "primaries"]).astype(float)
    return g


@st.cache_resource
def ensure_chart_views():
    cfg = _get_secret("database")
    if not cfg:
        return False

    sql_path = os.path.join(os.getcwd(), "supabase", "migrations", "20260117_ceo_cmo_chart_views.sql")
    if not os.path.exists(sql_path):
        return False

    try:
        with open(sql_path, "r", encoding="utf-8") as f:
            sql = f.read()
        conn = _connect_postgres(cfg)
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql)
        finally:
            conn.close()
        return True
    except Exception:
        return False


@st.cache_data(ttl=300)
def query_postgres(sql: str, params: tuple | None = None) -> pd.DataFrame:
    cfg = _get_secret("database")
    if not cfg:
        return pd.DataFrame()

    try:
        conn = _connect_postgres(cfg)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchall() if cur.description else []
            return pd.DataFrame(rows, columns=cols)
        finally:
            conn.close()
    except Exception:
        return pd.DataFrame()
