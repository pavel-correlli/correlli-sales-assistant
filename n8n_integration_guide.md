# Kommo Ads Data Integration Guide for n8n

This guide explains how to update your n8n workflow to capture marketing/ads data from Kommo and save it to Supabase.

## 1. Prerequisites
- Ensure you have run the `migration.sql` script in your Supabase SQL Editor to add the necessary columns.
- Ensure your n8n instance has access to Kommo and Supabase credentials.

## 2. n8n Workflow Updates

### Step 1: Update the "Get Lead" Node (Kommo)
Locate the node in your workflow that fetches Lead details from Kommo.
- **Action:** Open the node settings.
- **Parameter:** Look for "Return Values" or "Custom Fields".
- **Change:** Ensure that `custom_fields_values` or "All Custom Fields" is selected. We need the API to return the "Ads" tab data.
- **Verification:** Run this node manually with a test lead ID and check the JSON output. You should see fields like `UTM_SOURCE`, `Campaign ID`, etc. inside the `custom_fields_values` array.

### Step 2: Extract Ads Data (Set Node / Function Item)
Ideally, map the fields directly in the Supabase node. If that's complex, add a **Set** node before the Supabase node to flatten the structure.

**Fields to Map:**
| Kommo Field Name | Supabase Column |
|------------------|-----------------|
| Campaign ID | `campaign_id` |
| Campaign name | `campaign_name` |
| AD group ID | `ad_group_id` |
| AD group name | `ad_group_name` |
| AD ID | `ad_id` |
| AD name | `ad_name` |
| Form ID | `form_id_custom` |
| form_id | `form_id` |
| Form name | `form_name` |
| utm_medium | `utm_medium` |
| utm_term | `utm_term` |
| utm_content | `utm_content` |
| utm_campaign | `utm_campaign` |
| utm_source | `utm_source` |
| tran_id | `tran_id` |
| Referer | `referer` |
| INPUT | `input_val` |
| FORMNAME | `formname` |
| group_id | `group_id` |
| UTM_ | `utm_underscore` |
| google_client_id | `google_client_id` |
| CLIENT_ID | `client_id` |
| DATE | `date_val` |

### Step 3: Update the Supabase Node
Locate the final node that inserts/updates data in Supabase.
- **Table:** Select your raw calls table (e.g., `Algonova_Calls_Raw`).
- **Operation:** `Insert` or `Upsert`.
- **Columns:** Map the fields extracted in Step 2 to the corresponding Supabase columns.
    - Example: Set `utm_source` in Supabase to `{{ $json["utm_source"] }}` from the previous node.

## 3. Backfilling Historical Data
To populate data for existing calls:
1. Ensure the `migration.sql` has been executed.
2. Run the provided Python script `backfill_ads_data.py`:
   ```bash
   python backfill_ads_data.py
   ```
   *Note: The script attempts to auto-detect the table name. If it fails, please edit the script to specify the correct table.*

## 4. Verification
After updating the workflow:
1. Make a test call/lead.
2. Check Supabase to see if the new columns are populated.
