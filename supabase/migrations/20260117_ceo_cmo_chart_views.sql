CREATE OR REPLACE VIEW v_ceo_total_friction AS
SELECT
  (call_datetime::timestamptz)::date AS call_date,
  pipeline_name,
  COALESCE(
    NULLIF(market, ''),
    CASE
      WHEN pipeline_name ILIKE 'CZ%' THEN 'CZ'
      WHEN pipeline_name ILIKE 'SK%' THEN 'SK'
      WHEN pipeline_name ILIKE 'RUK%' THEN 'RUK'
      ELSE 'Others'
    END
  ) AS market,
  call_type
FROM "Algonova_Calls_Raw"
WHERE call_type IN ('intro_call', 'intro_followup', 'sales_call', 'sales_followup');


CREATE OR REPLACE VIEW v_ceo_talk_time_per_lead_by_pipeline AS
SELECT
  (call_datetime::timestamptz)::date AS call_date,
  pipeline_name,
  COALESCE(
    NULLIF(market, ''),
    CASE
      WHEN pipeline_name ILIKE 'CZ%' THEN 'CZ'
      WHEN pipeline_name ILIKE 'SK%' THEN 'SK'
      WHEN pipeline_name ILIKE 'RUK%' THEN 'RUK'
      ELSE 'Others'
    END
  ) AS market,
  lead_id,
  call_id,
  call_type,
  CASE
    WHEN call_type = 'intro_call' THEN 'Intro Call'
    WHEN call_type = 'intro_followup' THEN 'Intro Flup'
    WHEN call_type = 'sales_call' THEN 'Sales Call'
    WHEN call_type = 'sales_followup' THEN 'Sales Flup'
    ELSE 'Other'
  END AS call_type_group,
  (NULLIF(call_duration_sec::text, '')::numeric) / 60.0 AS minutes
FROM "Algonova_Calls_Raw"
WHERE call_type IN ('intro_call', 'intro_followup', 'sales_call', 'sales_followup');


CREATE OR REPLACE VIEW v_ceo_total_talk_time_by_pipeline AS
SELECT
  call_date,
  pipeline_name,
  market,
  lead_id,
  call_id,
  call_type,
  call_type_group,
  minutes
FROM v_ceo_talk_time_per_lead_by_pipeline;


CREATE OR REPLACE VIEW v_cmo_intro_friction_vs_traffic_manager AS
SELECT
  (call_datetime::timestamptz)::date AS call_date,
  COALESCE(NULLIF(mkt_market, ''), NULLIF(market, ''), 'Unknown') AS mkt_market,
  mkt_manager,
  pipeline_name,
  call_type,
  lead_id,
  call_id
FROM "Algonova_Calls_Raw"
WHERE call_type IN ('intro_call', 'intro_followup')
  AND mkt_manager IS NOT NULL
  AND mkt_manager <> '';


CREATE OR REPLACE VIEW v_cmo_traffic_viscosity_vs_intro_friction AS
SELECT
  (call_datetime::timestamptz)::date AS call_date,
  mkt_manager,
  pipeline_name,
  market,
  lead_id,
  call_id,
  call_type
FROM "Algonova_Calls_Raw"
WHERE mkt_manager IS NOT NULL
  AND mkt_manager <> '';


CREATE OR REPLACE VIEW v_cmo_intro_friction_traffic_manager_market_pipeline AS
SELECT
  (call_datetime::timestamptz)::date AS call_date,
  COALESCE(NULLIF(mkt_market, ''), NULLIF(market, ''), 'Unknown') AS mkt_market,
  mkt_manager,
  pipeline_name,
  SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END)::int AS intro_calls,
  SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::int AS intro_flups
FROM "Algonova_Calls_Raw"
WHERE call_type IN ('intro_call', 'intro_followup')
  AND mkt_manager IS NOT NULL
  AND mkt_manager <> ''
GROUP BY
  (call_datetime::timestamptz)::date,
  COALESCE(NULLIF(mkt_market, ''), NULLIF(market, ''), 'Unknown'),
  mkt_manager,
  pipeline_name;
