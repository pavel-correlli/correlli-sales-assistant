import os
import toml
import requests
import time
from supabase import create_client

def load_secrets():
    secrets_path = os.path.join(".streamlit", "secrets.toml")
    try:
        with open(secrets_path, "r") as f:
            return toml.load(f)
    except FileNotFoundError:
        print(f"❌ Could not find secrets file at {secrets_path}")
        return None

def get_kommo_lead(lead_id, auth_headers, base_url):
    try:
        # Note: 'with=custom_fields' is often default or needed depending on version
        url = f"https://{base_url}/api/v4/leads/{lead_id}?with=custom_fields"
        response = requests.get(url, headers=auth_headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 204:
            # 204 No Content = Lead not found or no access
            return None
        else:
            print(f"  ❌ Error fetching lead {lead_id}: {response.status_code}")
            return None
    except Exception as e:
        print(f"  ❌ Exception fetching lead {lead_id}: {e}")
        return None

def map_kommo_fields(lead_data):
    """
    Extracts ads fields from Kommo lead data and maps to Supabase columns.
    """
    if not lead_data or 'custom_fields_values' not in lead_data:
        return {}

    # Map Supabase Column -> Kommo Field Name (or Code)
    mapping = {
        "campaign_id": ["Campaign ID"],
        "campaign_name": ["Campaign name"],
        "ad_group_id": ["AD group ID"],
        "ad_group_name": ["AD group name"],
        "ad_id": ["AD ID"],
        "ad_name": ["AD name"],
        "form_id_custom": ["Form ID"],
        "form_id": ["form_id"],
        "form_name": ["Form name"],
        "utm_medium": ["utm_medium", "UTM_MEDIUM"],
        "utm_term": ["utm_term", "UTM_TERM"],
        "utm_content": ["utm_content", "UTM_CONTENT"],
        "utm_campaign": ["utm_campaign", "UTM_CAMPAIGN"],
        "utm_source": ["utm_source", "UTM_SOURCE"],
        "tran_id": ["tran_id"],
        "referer": ["Referer"],
        "input_val": ["INPUT"],
        "formname": ["FORMNAME"],
        "group_id": ["group_id"],
        "utm_underscore": ["UTM_"],
        "google_client_id": ["google_client_id"],
        "client_id": ["CLIENT_ID"],
        "date_val": ["DATE"]
    }

    updates = {}
    custom_fields = lead_data['custom_fields_values']
    
    # Create a lookup dict for custom fields by Name and Code
    cf_lookup = {}
    if custom_fields:
        for cf in custom_fields:
            name = cf.get('field_name')
            code = cf.get('field_code')
            values = cf.get('values', [])
            val = values[0].get('value') if values else None
            
            if name: cf_lookup[name] = val
            if code: cf_lookup[code] = val
        
    # Apply mapping
    for sb_col, kommo_keys in mapping.items():
        for key in kommo_keys:
            if key in cf_lookup:
                updates[sb_col] = cf_lookup[key]
                break 
    
    return updates

def backfill_data():
    secrets = load_secrets()
    if not secrets: return

    # Supabase Setup
    sb_url = secrets["supabase"]["url"]
    
    # Check for Service Role Key (preferred for admin tasks)
    sb_key = secrets["supabase"].get("service_role_key")
    if not sb_key:
        sb_key = secrets["supabase"]["key"]
        print("⚠️ Using public/anon key. If RLS is enabled, you might not see all data.")
        print("ℹ️  To fix: Add 'service_role_key' to [supabase] section in secrets.toml")
    else:
        print("✅ Using Service Role Key (RLS Bypass).")

    supabase = create_client(sb_url, sb_key)
    
    # Kommo Setup
    kommo_token = secrets["kommo"]["api_token"]
    kommo_domain = "algocz.kommo.com" 
    kommo_headers = {
        "Authorization": f"Bearer {kommo_token}",
        "Content-Type": "application/json"
    }

    table_name = "Algonova_Calls_Raw"

    print(f"--- Starting Backfill Process on table '{table_name}' ---")
    
    # 1. Fetch rows from Supabase
    try:
        # Fetch rows that need updating (or all)
        # We need a column that links to Kommo.
        # User implies there is a link. We assume 'lead_id' or 'kommo_id' or similar exists.
        # If not, we can't proceed.
        
        print(f"Fetching data...")
        res = supabase.table(table_name).select("*").execute()
        rows = res.data
        
        if not rows:
            print(f"❌ Table '{table_name}' returned 0 rows.")
            print("   Possible reasons: 1. Table is empty. 2. RLS is blocking access (use service_role_key).")
            return

        print(f"Found {len(rows)} rows.")
        
        # Identify Link Column
        link_col = None
        # Common names for the link
        candidates = ['lead_id', 'kommo_id', 'contact_id', 'Lead ID', 'kommo_lead_id']
        
        # Check first row
        first_row = rows[0]
        # Allow lead_id to be found even if value is null in first row, if key exists
        for col in candidates:
            if col in first_row:
                link_col = col
                break
        
        if not link_col:
            # Fallback: Ask user to specify if we can't guess
            print(f"❌ Could not auto-detect Kommo Link Column. Available columns: {list(first_row.keys())}")
            return
            
        print(f"✅ Using '{link_col}' as Kommo Lead ID.")

        updated_count = 0
        
        for row in rows:
            lead_id = row.get(link_col)
            # Use call_id if id is not present, as user stated call_id is unique
            row_id = row.get('id') 
            call_id = row.get('call_id')
            
            if not lead_id:
                # print(f"Skipping row with no lead_id")
                continue
                
            # print(f"Processing Lead {lead_id}...")
            
            # Fetch from Kommo
            kommo_lead = get_kommo_lead(lead_id, kommo_headers, kommo_domain)
            
            if kommo_lead:
                updates = map_kommo_fields(kommo_lead)
                
                if updates:
                    try:
                        # Update Supabase
                        if call_id:
                             supabase.table(table_name).update(updates).eq('call_id', call_id).execute()
                        elif row_id:
                            supabase.table(table_name).update(updates).eq('id', row_id).execute()
                        else:
                            # Fallback if no PK
                            supabase.table(table_name).update(updates).eq(link_col, lead_id).execute()
                        
                        updated_count += 1
                        print(f"  ✅ Updated Lead {lead_id} (Call ID: {call_id})")
                    except Exception as e:
                        print(f"  ❌ Update Error Lead {lead_id}: {e}")
            
            # Rate limit to be safe
            time.sleep(0.1)
            
        print(f"--- Backfill Complete. Updated {updated_count} rows. ---")

    except Exception as e:
        print(f"❌ Critical Error: {e}")

if __name__ == "__main__":
    backfill_data()
