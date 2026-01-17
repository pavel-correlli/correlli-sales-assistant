import os
import toml
import psycopg2


def _load_secrets():
    candidates = [
        os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
        os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return toml.load(path)
    raise FileNotFoundError("secrets.toml not found")


def _read_sql(sql_path: str) -> str:
    with open(sql_path, "r", encoding="utf-8") as f:
        return f.read()


def apply_views(sql_path: str):
    secrets = _load_secrets()
    cfg = secrets["database"]
    sql = _read_sql(sql_path)
    conn = psycopg2.connect(
        host=cfg["host"],
        database=cfg["name"],
        user=cfg["user"],
        password=cfg["pass"],
        port=cfg["port"],
    )
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sql_path = os.path.join(repo_root, "supabase", "migrations", "20260117_ceo_cmo_chart_views.sql")
    apply_views(sql_path)
    print("OK: SQL views applied")


if __name__ == "__main__":
    main()
