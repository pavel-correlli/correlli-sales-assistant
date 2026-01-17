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

    def _connect(host: str):
        return psycopg2.connect(
            host=host,
            database=cfg["name"],
            user=cfg["user"],
            password=cfg["pass"],
            port=cfg["port"],
            sslmode="require",
        )

    def _connect_pooler():
        host = str(cfg.get("host", "")).strip()
        if not (host.startswith("db.") and host.endswith(".supabase.co")):
            return None
        project_ref = host.split(".")[1]
        user = str(cfg.get("user", "")).strip()
        if user and "." not in user:
            user = f"{user}.{project_ref}"
        return psycopg2.connect(
            host="aws-1-eu-west-1.pooler.supabase.com",
            port=6543,
            database=str(cfg.get("name", "postgres")),
            user=user,
            password=cfg["pass"],
            sslmode="require",
        )

    conn = None
    try:
        try:
            conn = _connect(cfg["host"])
        except Exception:
            conn = _connect_pooler()
            if conn is None:
                raise

        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        if conn is not None:
            conn.close()


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sql_path = os.path.join(repo_root, "supabase", "migrations", "20260117_ceo_cmo_chart_views.sql")
    apply_views(sql_path)
    print("OK: SQL views applied")


if __name__ == "__main__":
    main()
