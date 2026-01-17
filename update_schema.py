import psycopg2
from psycopg2 import extras
import os
import toml

def update_schema():
    # Load DB config from secrets.toml
    secrets_path = os.path.join(".streamlit", "secrets.toml")
    try:
        with open(secrets_path, "r") as f:
            secrets = toml.load(f)
    except FileNotFoundError:
        print(f"❌ Could not find secrets file at {secrets_path}")
        return

    db_config = secrets["database"]
    
    # Marketing fields to add (excluding Lead ID/lead_id as requested)
    # Mapping to snake_case for Postgres columns
    # Original List:
    # "Campaign ID", "Campaign name", "AD group ID", "AD group name", 
    # "AD ID", "AD name", "Form ID", "form_id", "Form name", 
    # "Lead ID", "lead_id", "utm_medium", "utm_term", "utm_content", 
    # "utm_campaign", "utm_source", "tran_id", "Referer", "INPUT", 
    # "FORMNAME", "group_id", "UTM_", "google_client_id", "CLIENT_ID", "DATE"
    
    fields_map = {
        "Campaign ID": "campaign_id",
        "Campaign name": "campaign_name",
        "AD group ID": "ad_group_id",
        "AD group name": "ad_group_name",
        "AD ID": "ad_id",
        "AD name": "ad_name",
        "Form ID": "form_id_custom",  # Renamed to avoid collision
        "form_id": "form_id",
        "Form name": "form_name",
        # "Lead ID": "lead_id_custom", # Excluded
        # "lead_id": "lead_id",       # Excluded
        "utm_medium": "utm_medium",
        "utm_term": "utm_term",
        "utm_content": "utm_content",
        "utm_campaign": "utm_campaign",
        "utm_source": "utm_source",
        "tran_id": "tran_id",
        "Referer": "referer",
        "INPUT": "input_val",         # INPUT is a reserved keyword in some SQL dialects
        "FORMNAME": "formname",
        "group_id": "group_id",
        "UTM_": "utm_underscore",
        "google_client_id": "google_client_id",
        "CLIENT_ID": "client_id",
        "DATE": "date_val"            # DATE is a reserved keyword
    }

    try:
        print(f"Connecting to {db_config['host']}...")
        conn = psycopg2.connect(
            host=db_config["host"],
            database=db_config["name"],
            user=db_config["user"],
            password=db_config["pass"],
            port=db_config["port"]
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        table_name = "Algonova_Calls_Raw"
        
        # Verify table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            );
        """, (table_name,))
        exists = cur.fetchone()[0]
        
        if not exists:
            # Try lowercase
            table_name = "algonova_calls_raw"
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                );
            """, (table_name,))
            exists = cur.fetchone()[0]
            
        if not exists:
            print(f"❌ Table Algonova_Calls_Raw not found (checked case-sensitive and lowercase).")
            # List tables to help debug
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
            tables = cur.fetchall()
            print("Available tables:", [t[0] for t in tables])
            return

        print(f"✅ Found table: {table_name}")
        
        # Check existing columns
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s;
        """, (table_name,))
        existing_columns = {row[0] for row in cur.fetchall()}
        
        # Add missing columns
        for original_name, col_name in fields_map.items():
            if col_name not in existing_columns:
                print(f"Adding column: {col_name} (TEXT)...")
                try:
                    # Using TEXT for flexibility
                    cur.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" TEXT;')
                    print(f"  ✅ Added {col_name}")
                except Exception as e:
                    print(f"  ❌ Failed to add {col_name}: {e}")
            else:
                print(f"Skipping {col_name} (already exists)")
                
        print("\nSchema update complete.")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    update_schema()
