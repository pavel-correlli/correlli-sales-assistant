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


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []

    in_single = False
    in_double = False
    dollar_tag: str | None = None

    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buf.append(ch)
            i += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_single = False
            i += 1
            continue

        if in_double:
            buf.append(ch)
            if ch == '"':
                if i + 1 < n and sql[i + 1] == '"':
                    buf.append('"')
                    i += 2
                    continue
                in_double = False
            i += 1
            continue

        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue

        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue

        if ch == "$":
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            if j < n and sql[j] == "$":
                tag = sql[i : j + 1]
                dollar_tag = tag
                buf.append(tag)
                i = j + 1
                continue

        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def apply_views(sql_path: str):
    secrets = _load_secrets()
    cfg = secrets["database"]
    sql = _read_sql(sql_path)
    statements = _split_sql_statements(sql)

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
            cur.execute("SET statement_timeout TO 0;")
            for idx, stmt in enumerate(statements, start=1):
                try:
                    cur.execute(stmt)
                except Exception as e:
                    preview = stmt.replace("\n", " ")[:400]
                    raise RuntimeError(f"Failed SQL statement #{idx}/{len(statements)}: {preview}") from e
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
