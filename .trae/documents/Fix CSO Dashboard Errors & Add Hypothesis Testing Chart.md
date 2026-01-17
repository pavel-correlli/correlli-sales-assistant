I will fix the `AttributeError`, correct the `Average_quality` logic, and implement the new "Silence is Deadly" chart in `views/cso_view.py`.

### 1. Fix `AttributeError` in `cso_view.py`
The error occurs because `df['date']` or `df['call_datetime']` are not explicitly converted to datetime objects before accessing `.dt`.
*   **Fix:** I will ensure robust type conversion at the beginning of the `render_cso_dashboard` function:
    ```python
    # Robust conversion ensuring datetimelike objects
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    if 'call_datetime' in df.columns:
        df['call_datetime'] = pd.to_datetime(df['call_datetime'], errors='coerce')
    ```

### 2. Update Quality Score Logic
You mentioned `Average_quality` is out of 10.
*   **Fix:** I will update the "Top Quality Calls" threshold in the News Feed from `4.8` to `9.0` (assuming 10 is max) and the "Sudden Drops" range to `6.0-8.0` (or as appropriate based on the verified max value).
*   **Verification:** I will double-check the actual range by querying the max value from Supabase just to be precise.

### 3. Implement "Silence is Deadly" Chart (Short Calls vs No Objections vs Vague)
I will add a new visualization to test your hypothesis: "Short conversations without objections = Low interest = Vague outcome."

*   **Logic:**
    *   Filter for **Intro** and **Sales** calls only (exclude follow-ups).
    *   Identify "No Objection" calls: `main_objection_type` is None/Empty or "None".
    *   Identify "Short Calls": Duration < 3 minutes (180s).
    *   Metric: % of Vague outcomes in this specific segment vs. Normal calls.
*   **Visualization:**
    *   **Scatter Plot**:
        *   X: Call Duration (minutes).
        *   Y: Vague Rate (%).
        *   Size: Count of calls.
        *   Color: Manager.
    *   **Insight Metric**: "Vague Rate in Short Silent Calls" vs "Avg Vague Rate".

### 4. Code Structure Update
I will modify `views/cso_view.py` to include these fixes and the new chart section.
