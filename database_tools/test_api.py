from supabase import create_client, Client
import toml
import os
import json

def get_supabase_config():
    possible_paths = [
        os.path.join(os.getcwd(), '.streamlit', 'secrets.toml'),
        os.path.join(os.path.dirname(__file__), '..', '.streamlit', 'secrets.toml'),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            secrets = toml.load(path)
            if 'supabase' in secrets:
                return secrets['supabase']['url'], secrets['supabase']['key']
    
    raise FileNotFoundError("Could not find supabase configuration in secrets.toml")

def main():
    try:
        url, key = get_supabase_config()
        supabase: Client = create_client(url, key)
        
        print("Attempting to fetch table names...")
        # PostgREST doesn't have a direct way to list tables, but we can try common ones 
        # or use a trick if the user has a specific setup.
        
        # Let's try to query the view we know exists
        print("Checking v_analytics_calls...")
        res = supabase.table("v_analytics_calls").select("*").limit(1).execute()
        if res.data:
            print("Columns in v_analytics_calls:", list(res.data[0].keys()))
            
        print("Checking Algonova_Calls_Raw...")
        res = supabase.table("Algonova_Calls_Raw").select("*").limit(1).execute()
        if res.data:
            print("Columns in Algonova_Calls_Raw:", list(res.data[0].keys()))

        # To get the full schema via API, we might need a custom RPC if RLS is off and we want SQL
        # Since I can't run arbitrary SQL, I will try to use the 'rpc' to call a function if it exists.
        # But I don't know if any exist.
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
