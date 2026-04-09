# Streamlit Redeploy (New Account)

## 1) Connect repo
1. Sign in to the new Streamlit account.
2. Click `Create app`.
3. Select GitHub repo: `pavel-correlli/correlli-sales-assistant`.
4. Select branch:
- `codex/dual-lang-demo-ru-en` for testing.
- `main` only after merge.
5. Set `Main file path` to `app.py`.

## 2) Set secrets in Streamlit UI
Open `App settings -> Secrets` and add:

```toml
SUPABASE_URL = "https://<your-project>.supabase.co"
SUPABASE_KEY = "<your-key>"

DB_HOST = "db.<your-project>.supabase.co"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "<your-password>"
DB_PORT = "5432"
```

Optional nested format (also supported):

```toml
[supabase]
url = "https://<your-project>.supabase.co"
key = "<your-key>"
```

## 3) Deploy and smoke-check
1. Click `Deploy`.
2. Validate:
- Sidebar language switcher (`English` / `Русский`).
- Role navigation labels (`Director`, `Marketer`, `ROP` in EN and localized in RU).
- Default filter state: `All Time` is enabled on first load.
- Pages load without errors: CEO/CMO/CSO/LAB.

## 4) Security after cutover
1. Rotate old Supabase and DB credentials that were previously shared.
2. Keep all active secrets only in Streamlit Secrets UI.
3. Remove stale keys from old Streamlit workspace/accounts.
