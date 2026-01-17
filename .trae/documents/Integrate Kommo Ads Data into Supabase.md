I have analyzed your request and the codebase. Here is the plan to integrate Kommo Ads data into Supabase.

### **Phase 1: Analyze & Prepare Schema**

1. **Map Fields:** Use `kommo_ads_fields.json` to define the list of columns to add to Supabase.

   * *Naming Convention:* Convert Kommo field names to snake\_case (e.g., `AD ID` -> `ad_id`, `utm_source` -> `utm_source`).
2. **Update Supabase Schema:**

   * Create and run a Python script (`update_schema.py`) to add these missing columns to the `Algonova_Calls_Raw` table in Supabase.

   * *Note:* I will first verify the exact table name and the existence of a linking column (like `lead_id` or `kommo_id`) which is required for the backfill.

### **Phase 2: Backfill Existing Data**

1. **Develop Backfill Script:** Create a Python script (`backfill_ads_data.py`) that:

   * Fetches rows from Supabase that are missing Ads data.

   * Extracts the Kommo Lead ID from each row.

   * Queries the Kommo API (using credentials from `secrets.toml`) to get lead details, specifically from the 'Ads' tab.

   * Updates the corresponding row in Supabase with the fetched Ads data.

   * Includes error handling and progress logging to ensure it doesn't break existing data.
2. **Execution:** Run the script to populate historical data.

### **Phase 3: n8n Workflow Guide**

1. **Analyze & Document:** Since I cannot directly modify your n8n workflows, I will provide a step-by-step text guide on how to update your existing flow.

   * **Step 1:** Configure the Kommo node to fetch `custom_fields` (specifically the Ads fields).

   * **Step 2:** Map these new fields in the final Supabase node to the newly created columns.

   * **Step 3:** Verify the data flow for new calls.

### **Verification**

* Check that new columns exist in Supabase.

* Verify that old rows now have UTM/Ads data.

* (User action) Follow the n8n guide to enable it for future calls.

