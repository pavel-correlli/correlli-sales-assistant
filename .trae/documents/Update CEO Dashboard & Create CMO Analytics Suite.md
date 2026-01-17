I will implement the requested updates to the CEO Dashboard, create the new CMO Dashboard, and integrate the Data Lab.

### 1. Dependencies & Configuration
- **Install Packages**: `statsmodels` (to fix the `ModuleNotFoundError`) and `pygwalker` (for the Data Lab).
- **Update `app.py`**: Refactor the main application file to support the new features and UI changes.

### 2. UI/UX Refinement
- **Clean Aesthetic**: Remove emojis from titles, use professional business fonts and styling.
- **Navigation**: Replace the sidebar dropdown with "volumetric" buttons (using custom styled buttons in the sidebar) for switching between CEO, CMO, and Data Lab views.

### 3. CEO Dashboard Updates
- **Fix Error**: Ensure `statsmodels` is available for the trendline analysis.
- **Vague Index Improvement**: Replace the single gauge chart with a Bar Chart or Line Chart showing Vague Index by Market/Time for better analytical depth.

### 4. New CMO Dashboard ("Strategic Traffic Analysis")
- **Data Source**: Use `v_analytics_calls` to access `mkt_` parameters.
- **Global Filters**: Date Range, Market, Pipeline Name.
- **Block 1: Traffic Efficiency (Hard Metrics)**
    - **Dynamic Analysis**: Radio button selector for `mkt_manager`, `mkt_geo`, `mkt_type`, `mkt_region`.
    - **Visuals**:
        - Viscosity Leaderboard (Calls per Lead).
        - One-Call-Close Rate by parameter.
        - Vague Index by Region/Parameter.
- **Block 2: Customer Resonance (AI Entities)**
    - **Voice Matrix**: Frequency analysis of `parent_goals`, `parent_fears`, `objection_list`.
    - **Decision Maker**: Stacked Bar Chart of Decision Makers by Traffic Source.
- **Summary Table**: Detailed metrics breakdown by the selected traffic parameter.

### 5. Data Lab Module
- **Integration**: Restore the `pygwalker` explorer for ad-hoc data analysis.

I will proceed with these changes immediately upon confirmation.