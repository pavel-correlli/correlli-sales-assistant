import os
import subprocess
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

    def _resolve_ip(host: str) -> str | None:
        cmd = [
            "powershell",
            "-Command",
            f"Resolve-DnsName {host} -Server 8.8.8.8 -Type A | Select-Object -First 1 -ExpandProperty IPAddress",
        ]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
            return out if out else None
        except Exception:
            return None

    conn = None
    try:
        try:
            conn = _connect(cfg["host"])
        except Exception:
            ip = _resolve_ip(cfg["host"])
            if not ip:
                raise
            conn = _connect(ip)

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
