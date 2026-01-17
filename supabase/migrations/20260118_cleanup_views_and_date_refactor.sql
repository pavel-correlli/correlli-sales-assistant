DROP VIEW IF EXISTS v_analytics_goals_atomized;
DROP VIEW IF EXISTS v_analytics_fears_atomized;
DROP VIEW IF EXISTS v_analytics_objections_atomized;
DROP VIEW IF EXISTS v_analytics_calls;
DROP VIEW IF EXISTS v_sales_performance_metrics;
DROP VIEW IF EXISTS v_analytics_attributes_frequency;
DROP VIEW IF EXISTS v_analytics_master;
DROP VIEW IF EXISTS v_cso_clarity_chart;
DROP VIEW IF EXISTS v_cso_friction_chart;
DROP VIEW IF EXISTS v_cso_efficiency_bubble;
DROP VIEW IF EXISTS v_cso_silence_chart;

CREATE OR REPLACE VIEW v_analytics_calls_enhanced AS
SELECT
  r.*,
  (NULLIF(r.call_datetime, '')::timestamptz)::date AS call_date,
  CASE
    WHEN r.next_step_type ILIKE '%vague%' THEN 'Vague'
    ELSE 'Success'
  END AS call_outcome,
  CASE
    WHEN r.call_type ILIKE '%intro%' THEN 'Intro'
    WHEN r.call_type ILIKE '%sales%' THEN 'Sales'
    ELSE 'Other'
  END AS call_category
FROM "Algonova_Calls_Raw" r;

