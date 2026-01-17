I have verified the database access and schema.

**Findings:**

1. **Table Name:** The correct table is `Algonova_Calls_Raw` (it has 1742 rows). The table `Algonova_Sales_Raw` mentioned in your request does not exist or is not accessible, so I will proceed with `Algonova_Calls_Raw`.
2. **Schema:** The table `Algonova_Calls_Raw` already contains the `lead_id` column and the new marketing columns (`campaign_id`, `ad_id`, etc.), so the structure is ready.
3. **Permissions:** I can now access the data (1742 rows found), confirming RLS is disabled or the key has sufficient permissions.

**Plan:**

1. **Update Backfill Script:** I will refine the `backfill_ads_data.py` script to:

   * Connect to `Algonova_Calls_Raw`.

   * Iterate through all 1742 rows.

   * For each row, extract the `lead_id`.

   * Query the Kommo API to get the Ads fields.

   * Update the specific row in Supabase with the fetched data.

   * Handle duplicates: The script will process each row individually (using `id` or `call_id` to target the specific row for update), ensuring that even if multiple calls share a `lead_id`, all of them get updated.
2. **Execution:** Run the script to populate the database.

