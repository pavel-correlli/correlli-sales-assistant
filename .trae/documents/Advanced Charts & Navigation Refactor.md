I will update the dashboard with the correct metrics, new charts, and improved navigation as requested.

### 1. Data Logic & Metrics Fixes
- **Correct Quality Metric**: Replace `avg_quality` and `quality_segment` with `Average_quality` (note the capital 'A' from schema). The user specified values like `5.33`, `8.29` which matches a numeric score. I will ensure this column is cast to numeric.
- **Remove Invalid Column**: Stop using `quality_segment` entirely.
- **Fix Data Lab Error**: Replace `st.experimental_user` with `st.user` (or remove if not supported in the current version, checking docs/deprecation).

### 2. New Advanced Visualizations
I will distribute these charts across the dashboards where they fit best logically:

*   **CEO Dashboard (Strategic Radar)**
    *   **A. Scatter Plot with Marginal Histograms**: "Quality vs Touches".
        *   *X-Axis*: `Average_quality`
        *   *Y-Axis*: `call_duration_sec` (or `calls_per_lead` if available in that view).
        *   *Insight*: Shows the "core" of effective calls.
    *   **E. Bullet Chart**: Replace the Gauge chart for "One-Call-Close Rate" or "Vague Index".
        *   *Insight*: Target vs Actual performance.
    *   **D. Sunburst Chart**: "Market Segmentation".
        *   *Hierarchy*: Market -> Manager -> Result (Vague/Success).
        *   *Insight*: Deep dive into performance structure.

*   **CMO Analytics (Strategic Traffic Analysis)**
    *   **C. Treemap**: "Customer DNA".
        *   *Data*: `parent_goals` and `parent_fears`.
        *   *Insight*: Hierarchy of customer needs/fears.
    *   **B. Heatmap Matrix**: "Objection Heatmap".
        *   *X-Axis*: `main_objection_type` (or `objection_list`).
        *   *Y-Axis*: `pipeline_name`.
        *   *Color*: Frequency/Count.
        *   *Insight*: Where the friction points are per pipeline.

### 3. Navigation & Filtering Overhaul
- **Checkbox Navigation**: Replace the Sidebar dropdown/buttons with a section of Checkboxes for "Views" (CEO, CMO, CSO, Data Lab).
    - *Note*: This is unconventional for "Tabs/Pages" (usually Radio or Buttons), but I will implement a custom logic: "Show checked dashboards stacked" or "Radio-like behavior with checkboxes" if implied. *Correction*: The user likely means the **Filters** section (Market/Pipelines).
    - *Clarification*: The user said "replace dropdown menu left with sections where you can just tick what is selected... This applies only to pipelines and markets".
    - **Logic**:
        - **Markets**: Checkboxes. Unchecking a market hides its pipelines.
        - **Pipelines**: Checkboxes (nested under markets or dynamic).
        - **Dependency**: Removing a market removes its pipelines from the selection. Removing all pipelines for a market removes the market from the selection.

### 4. Implementation Steps
1.  **Update `fetch_view_data`**: Ensure `Average_quality` is fetched and cast to float.
2.  **Refactor Sidebar**: Implement the cascading Market/Pipeline checkbox logic.
3.  **Update CEO Page**: Add Scatter Marginal, Sunburst, Bullet Chart.
4.  **Update CMO Page**: Add Treemap, Heatmap.
5.  **Fix Data Lab**: Remove deprecated call.

I will proceed with these updates immediately upon confirmation.