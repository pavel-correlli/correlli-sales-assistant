import os
import toml
from supabase import create_client

def discover():
    secrets_path = os.path.join(".streamlit", "secrets.toml")
    with open(secrets_path, "r") as f:
        secrets = toml.load(f)

    url = secrets["supabase"]["url"]
    key = secrets["supabase"]["key"]
    supabase = create_client(url, key)
    
    print("--- Attempting Schema Discovery ---")
    
    # 1. Try information_schema.tables (often exposed in Supabase via API if configured)
    try:
        print("Querying information_schema.tables...")
        # Note: Supabase API might expose this as a view if configured, or not at all.
        # We try 'information_schema' schema. PostgREST usually exposes 'public' by default.
        # But sometimes system tables are exposed.
        # It's unlikely to work via standard client unless 'db_schema' is set, but let's try.
        pass
    except:
        pass

    # 2. Try to guess table names with existence check
    # We will try to Select 1 row from various potential names.
    candidates = [
        "Algonova_Calls_Raw", "algonova_calls_raw", 
        "Calls", "calls", 
        "Leads", "leads", 
        "crm_calls", "crm_leads",
        "sales_calls", "sales_leads",
        "algonova_calls", "algonova_leads"
    ]
    
    print("\n--- Brute Force Table Check ---")
    for table in candidates:
        try:
            res = supabase.table(table).select("*", count="exact", head=True).execute()
            count = res.count
            print(f"Table '{table}': Exists? YES. Count: {count}")
            
            # If exists, check columns
            if count is not None:
                try:
                    res_data = supabase.table(table).select("*").limit(1).execute()
                    if res_data.data:
                        print(f"  Columns: {list(res_data.data[0].keys())}")
                    else:
                        print("  (No data returned)")
                except:
                    print("  (Could not fetch data)")
                    
        except Exception as e:
            # 404 means not found
            if "404" in str(e):
                pass # Not found
            else:
                print(f"Table '{table}': Error {e}")

if __name__ == "__main__":
    discover()
