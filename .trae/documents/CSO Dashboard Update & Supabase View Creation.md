I will update the CSO Dashboard (`views/cso_view.py`) and the database structure as requested.

### 1. Database Updates (Supabase)
*   **Create New View `v_lead_friction_metrics`**: I will create a SQL migration file (`supabase/migrations/20260116_cso_views.sql`) to define a new view that aggregates call data by `lead_id`. This view will calculate:
    *   `intro_calls`, `intro_followups`, `sales_calls`, `sales_followups` counts.
    *   `is_defined` status (based on `lesson_scheduled`, `sold`, etc.).
    *   `manager`, `market`, and `last_call_date`.
    *   This view will be used for the "Friction vs. Defined Rate" scatter plot.

### 2. CSO Dashboard Refactoring (`views/cso_view.py`)
I will apply the following changes to the code:

*   **Data Logic Fixes**:
    *   **Sorting Bug**: Add `df.sort_values(by='call_datetime')` before grouping to ensure the "Defined Commitments" rate is calculated based on the *latest* call, fixing the 0.0% issue.
    *   **Defined Rate Calculation**: Update the logic to correctly identify successful sales leads using the sorted data.

*   **Visualization Updates**:
    *   **Friction & Resistance**: Update text/tooltips as requested (English).
    *   **Operational Waste**: Update the anomaly text to "Found X calls > 15m with Vague outcome."
    *   **Commitment Breakdown**: **Remove** the Sunburst chart completely.
    *   **Manager Commitment Discipline**: Add the explanatory text:
        *   "Defined" = Clear commitments.
        *   "Vague" = Unclear/fuzzy commitments.
    *   **Friction vs. Defined Rate**: Update the scatter plot to fetch and use data from the new `v_lead_friction_metrics` view (or calculate equivalent logic if using the raw dataframe is more performant, ensuring "Friction" is per-lead based).

*   **New Features**:
    *   **Leaderboard**: Add a table showing managers ranked by Average Quality.
    *   **News Feed**: Add a section displaying:
        *   "Perfect Calls" (Quality = 5).
        *   "Sudden Drops" (Duration > 3m, Quality 3-4).
    *   **Call Detail View**: Implement a mechanism (e.g., expander or selection) to view details of a specific call:
        *   `mistakes_summary`, `recommendations`, `best_phrases`, `next_step_suggestion`.
        *   Direct link to Kommo CRM.

*   **Localization**:
    *   Translate **all** tooltips and UI explanations from Russian to English.

### 3. Documentation
*   I will ensure the new SQL view definition is saved in the project's `supabase/migrations` folder to document the table structure.
