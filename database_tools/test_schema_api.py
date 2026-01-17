from supabase import create_client, Client
import toml
import os

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
        
        print("Attempting to query information_schema.tables via API...")
        try:
            res = supabase.table("tables").select("*", schema="information_schema").limit(5).execute()
            print("Successfully queried information_schema.tables!")
            print(res.data)
        except Exception as e:
            print(f"Failed to query information_schema.tables: {e}")

        print("\nAttempting to query pg_views via API...")
        try:
            # Note: Some Supabase setups might expose pg_views in a specific way
            res = supabase.table("pg_views").select("*").limit(5).execute()
            print("Successfully queried pg_views!")
            print(res.data)
        except Exception as e:
            print(f"Failed to query pg_views: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
