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


CREATE OR REPLACE FUNCTION app_normalize_call_id(input text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT regexp_replace(
    regexp_replace(
      trim(coalesce(input, '')),
      '[{}]',
      '',
      'g'
    ),
    '^[\"'']+|[\"'']+$',
    '',
    'g'
  );
$$;


CREATE OR REPLACE VIEW v_app_calls_norm AS
SELECT
  r.call_id,
  r.lead_id,
  r.manager,
  r.pipeline_name,
  r.market,
  r.mkt_market,
  r.mkt_manager,
  r.call_datetime,
  (r.call_datetime::timestamptz)::date AS call_date,
  COALESCE(
    NULLIF(r.market, ''),
    CASE
      WHEN r.pipeline_name ILIKE 'CZ%' THEN 'CZ'
      WHEN r.pipeline_name ILIKE 'SK%' THEN 'SK'
      WHEN r.pipeline_name ILIKE 'RUK%' THEN 'RUK'
      ELSE 'Others'
    END
  ) AS computed_market,
  r.call_type,
  r.call_duration_sec,
  r."Average_quality",
  r.next_step_type,
  r.main_objection_type,
  r.audio_url,
  r.kommo_link
FROM "Algonova_Calls_Raw" r;


CREATE OR REPLACE FUNCTION rpc_ceo_total_friction(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL
)
RETURNS TABLE (
  market text,
  type text,
  primaries int,
  followups int,
  calls_in_calc int,
  friction_index numeric
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT *
    FROM v_ceo_total_friction
    WHERE (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
  )
  SELECT
    market,
    'Intro Friction' AS type,
    SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END)::int AS primaries,
    SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::int AS followups,
    SUM(CASE WHEN call_type IN ('intro_call','intro_followup') THEN 1 ELSE 0 END)::int AS calls_in_calc,
    ROUND(
      (SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END))::numeric
      / NULLIF(SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END), 0),
      2
    ) AS friction_index
  FROM base
  GROUP BY market
  UNION ALL
  SELECT
    market,
    'Sales Friction' AS type,
    SUM(CASE WHEN call_type = 'sales_call' THEN 1 ELSE 0 END)::int AS primaries,
    SUM(CASE WHEN call_type = 'sales_followup' THEN 1 ELSE 0 END)::int AS followups,
    SUM(CASE WHEN call_type IN ('sales_call','sales_followup') THEN 1 ELSE 0 END)::int AS calls_in_calc,
    ROUND(
      (SUM(CASE WHEN call_type = 'sales_followup' THEN 1 ELSE 0 END))::numeric
      / NULLIF(SUM(CASE WHEN call_type = 'sales_call' THEN 1 ELSE 0 END), 0),
      2
    ) AS friction_index
  FROM base
  GROUP BY market;
$$;


CREATE OR REPLACE FUNCTION rpc_ceo_talk_time_per_lead_by_pipeline(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL
)
RETURNS TABLE (
  pipeline_name text,
  call_type_group text,
  leads_total int,
  calls_type int,
  total_minutes_type float8,
  total_minutes_pipeline float8,
  avg_minutes_per_call_type numeric,
  avg_minutes_per_lead_type numeric,
  share_pct numeric
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT *
    FROM v_ceo_talk_time_per_lead_by_pipeline
    WHERE (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND minutes IS NOT NULL
      AND lead_id IS NOT NULL
      AND trim(lead_id::text) <> ''
  ),
  leads AS (
    SELECT pipeline_name, COUNT(DISTINCT lead_id)::int AS leads_total
    FROM base
    GROUP BY pipeline_name
  ),
  agg AS (
    SELECT
      pipeline_name,
      call_type_group,
      COUNT(*)::int AS calls_type,
      SUM(minutes)::float8 AS total_minutes_type
    FROM base
    GROUP BY pipeline_name, call_type_group
  ),
  totals AS (
    SELECT pipeline_name, SUM(total_minutes_type)::float8 AS total_minutes_pipeline
    FROM agg
    GROUP BY pipeline_name
  )
  SELECT
    a.pipeline_name,
    a.call_type_group,
    l.leads_total,
    a.calls_type,
    a.total_minutes_type,
    t.total_minutes_pipeline,
    ROUND((a.total_minutes_type / NULLIF(a.calls_type, 0))::numeric, 2) AS avg_minutes_per_call_type,
    ROUND((a.total_minutes_type / NULLIF(l.leads_total, 0))::numeric, 2) AS avg_minutes_per_lead_type,
    ROUND((a.total_minutes_type / NULLIF(t.total_minutes_pipeline, 0) * 100)::numeric, 2) AS share_pct
  FROM agg a
  JOIN leads l ON l.pipeline_name = a.pipeline_name
  JOIN totals t ON t.pipeline_name = a.pipeline_name
  ORDER BY a.pipeline_name, a.call_type_group;
$$;


CREATE OR REPLACE FUNCTION rpc_ceo_kpis(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL
)
RETURNS TABLE (
  avg_quality numeric,
  vague_rate_pct numeric,
  avg_market_friction numeric
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      call_type,
      (NULLIF("Average_quality"::text, '')::numeric) AS average_quality,
      next_step_type
    FROM v_app_calls_norm
    WHERE (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
  )
  SELECT
    ROUND(AVG(average_quality), 2) AS avg_quality,
    ROUND(
      (
        SUM(CASE WHEN lower(coalesce(next_step_type, '')) LIKE '%vague%' THEN 1 ELSE 0 END)::numeric
        / NULLIF(COUNT(*)::numeric, 0)
        * 100
      ),
      1
    ) AS vague_rate_pct,
    ROUND(
      (
        SUM(CASE WHEN call_type IN ('intro_followup', 'sales_followup') THEN 1 ELSE 0 END)::numeric
        / NULLIF(SUM(CASE WHEN call_type IN ('intro_call', 'sales_call') THEN 1 ELSE 0 END)::numeric, 0)
      ),
      2
    ) AS avg_market_friction
  FROM base;
$$;


CREATE OR REPLACE FUNCTION rpc_ceo_vague_index_by_market(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL
)
RETURNS TABLE (
  market text,
  outcome_category text,
  count bigint
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      computed_market AS market,
      CASE
        WHEN lower(coalesce(next_step_type, '')) LIKE '%vague%' THEN 'Vague'
        ELSE 'Defined Next Step'
      END AS outcome_category
    FROM v_app_calls_norm
    WHERE (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
  )
  SELECT
    market,
    outcome_category,
    COUNT(*) AS count
  FROM base
  GROUP BY market, outcome_category
  ORDER BY market, outcome_category;
$$;


CREATE OR REPLACE FUNCTION rpc_ceo_one_call_close_rate_by_pipeline(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL
)
RETURNS TABLE (
  pipeline_name text,
  occ_rate_pct numeric,
  occ_leads int,
  total_leads int
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      lead_id,
      pipeline_name,
      call_type
    FROM v_app_calls_norm
    WHERE lead_id IS NOT NULL
      AND trim(lead_id::text) <> ''
      AND pipeline_name IS NOT NULL
      AND trim(pipeline_name) <> ''
      AND call_type IN ('intro_call','sales_call','intro_followup','sales_followup')
      AND (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
  ),
  lead_counts AS (
    SELECT
      lead_id,
      pipeline_name,
      SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END)::int AS intro_call,
      SUM(CASE WHEN call_type = 'sales_call' THEN 1 ELSE 0 END)::int AS sales_call,
      SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::int AS intro_followup,
      SUM(CASE WHEN call_type = 'sales_followup' THEN 1 ELSE 0 END)::int AS sales_followup
    FROM base
    GROUP BY lead_id, pipeline_name
  ),
  by_pipe AS (
    SELECT
      pipeline_name,
      SUM(CASE WHEN intro_call = 1 AND sales_call = 1 AND intro_followup = 0 AND sales_followup = 0 THEN 1 ELSE 0 END)::int AS occ_leads,
      COUNT(DISTINCT lead_id)::int AS total_leads
    FROM lead_counts
    GROUP BY pipeline_name
  )
  SELECT
    pipeline_name,
    ROUND((occ_leads::numeric / NULLIF(total_leads, 0) * 100), 2) AS occ_rate_pct,
    occ_leads,
    total_leads
  FROM by_pipe
  ORDER BY occ_rate_pct DESC;
$$;


CREATE OR REPLACE FUNCTION rpc_app_markets_pipelines()
RETURNS TABLE (
  market text,
  pipeline_name text
)
LANGUAGE sql
STABLE
AS $$
  SELECT DISTINCT
    computed_market AS market,
    pipeline_name
  FROM v_app_calls_norm
  WHERE pipeline_name IS NOT NULL
    AND trim(pipeline_name) <> ''
  ORDER BY computed_market, pipeline_name;
$$;


CREATE OR REPLACE FUNCTION rpc_app_managers()
RETURNS TABLE (
  manager text
)
LANGUAGE sql
STABLE
AS $$
  SELECT DISTINCT
    manager
  FROM v_app_calls_norm
  WHERE manager IS NOT NULL
    AND trim(manager) <> ''
  ORDER BY manager;
$$;


CREATE OR REPLACE FUNCTION rpc_app_calls_summary(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL,
  managers text[] DEFAULT NULL
)
RETURNS TABLE (
  total_rows bigint,
  filtered_rows bigint,
  min_call_date date,
  max_call_date date
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT call_date, computed_market, pipeline_name, manager
    FROM v_app_calls_norm
  ),
  filtered AS (
    SELECT *
    FROM base
    WHERE (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND (managers IS NULL OR cardinality(managers) = 0 OR manager = ANY(managers))
  )
  SELECT
    (SELECT COUNT(*) FROM base) AS total_rows,
    (SELECT COUNT(*) FROM filtered) AS filtered_rows,
    (SELECT MIN(call_date) FROM filtered) AS min_call_date,
    (SELECT MAX(call_date) FROM filtered) AS max_call_date;
$$;


CREATE OR REPLACE FUNCTION rpc_cmo_viscosity_intro_friction_by_manager(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL
)
RETURNS TABLE (
  mkt_manager text,
  mkt_market text,
  total_calls bigint,
  total_leads bigint,
  intro_primaries bigint,
  intro_followups bigint,
  viscosity_index numeric,
  intro_friction_index numeric
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      COALESCE(NULLIF(mkt_manager, ''), NULL) AS mkt_manager,
      COALESCE(NULLIF(mkt_market, ''), NULLIF(market, ''), computed_market) AS mkt_market,
      pipeline_name,
      lead_id,
      call_type
    FROM v_app_calls_norm
    WHERE (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
  ),
  filtered AS (
    SELECT *
    FROM base
    WHERE mkt_manager IS NOT NULL
      AND trim(mkt_manager) <> ''
      AND (markets IS NULL OR cardinality(markets) = 0 OR mkt_market = ANY(markets))
  )
  SELECT
    mkt_manager,
    mkt_market,
    COUNT(*) AS total_calls,
    COUNT(DISTINCT lead_id) AS total_leads,
    SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END) AS intro_primaries,
    SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END) AS intro_followups,
    ROUND((COUNT(*)::numeric / NULLIF(COUNT(DISTINCT lead_id), 0)), 2) AS viscosity_index,
    ROUND((SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::numeric / NULLIF(SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END), 0)), 2) AS intro_friction_index
  FROM filtered
  GROUP BY mkt_manager, mkt_market
  ORDER BY mkt_manager;
$$;


CREATE OR REPLACE FUNCTION rpc_cmo_intro_friction_heatmap(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL
)
RETURNS TABLE (
  mkt_market text,
  mkt_manager text,
  intro_calls int,
  intro_flups int,
  calls_in_calc int,
  intro_friction_index numeric
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      COALESCE(NULLIF(mkt_market, ''), NULLIF(market, ''), computed_market, 'Unknown') AS mkt_market,
      COALESCE(NULLIF(mkt_manager, ''), NULL) AS mkt_manager,
      pipeline_name,
      call_type
    FROM v_app_calls_norm
    WHERE call_type IN ('intro_call', 'intro_followup')
      AND (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
  ),
  filtered AS (
    SELECT *
    FROM base
    WHERE mkt_manager IS NOT NULL
      AND trim(mkt_manager) <> ''
      AND (markets IS NULL OR cardinality(markets) = 0 OR mkt_market = ANY(markets))
  )
  SELECT
    mkt_market,
    mkt_manager,
    SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END)::int AS intro_calls,
    SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::int AS intro_flups,
    SUM(CASE WHEN call_type IN ('intro_call', 'intro_followup') THEN 1 ELSE 0 END)::int AS calls_in_calc,
    ROUND(
      (SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END))::numeric
      / NULLIF(SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END), 0),
      2
    ) AS intro_friction_index
  FROM filtered
  GROUP BY mkt_market, mkt_manager
  ORDER BY mkt_market, mkt_manager;
$$;


CREATE OR REPLACE FUNCTION rpc_cmo_entity_frequency(
  attr_type text,
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL
)
RETURNS TABLE (
  pipeline_name text,
  attr_value text,
  calls_with_attr int,
  mentions int,
  total_calls int,
  frequency numeric
)
LANGUAGE sql
STABLE
AS $$
  WITH calls AS (
    SELECT
      app_normalize_call_id(call_id::text) AS call_id_norm,
      pipeline_name,
      computed_market AS market_norm
    FROM v_app_calls_norm
    WHERE call_id IS NOT NULL
      AND trim(call_id::text) <> ''
      AND (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
  ),
  attrs AS (
    SELECT
      app_normalize_call_id(call_id::text) AS call_id_norm,
      attr_value
    FROM v_analytics_attributes_frequency
    WHERE attr_value IS NOT NULL
      AND trim(attr_value) <> ''
      AND call_id IS NOT NULL
      AND trim(call_id::text) <> ''
      AND lower(attr_type) = lower(rpc_cmo_entity_frequency.attr_type)
  ),
  joined AS (
    SELECT
      c.pipeline_name,
      a.attr_value,
      c.call_id_norm
    FROM calls c
    JOIN attrs a ON a.call_id_norm = c.call_id_norm
  ),
  totals AS (
    SELECT pipeline_name, COUNT(DISTINCT call_id_norm)::int AS total_calls
    FROM calls
    GROUP BY pipeline_name
  ),
  agg AS (
    SELECT
      pipeline_name,
      attr_value,
      COUNT(DISTINCT call_id_norm)::int AS calls_with_attr,
      COUNT(*)::int AS mentions
    FROM joined
    GROUP BY pipeline_name, attr_value
  )
  SELECT
    a.pipeline_name,
    a.attr_value,
    a.calls_with_attr,
    a.mentions,
    t.total_calls,
    COALESCE((a.calls_with_attr::numeric / NULLIF(t.total_calls, 0)), 0) AS frequency
  FROM agg a
  JOIN totals t ON t.pipeline_name = a.pipeline_name;
$$;


CREATE OR REPLACE FUNCTION rpc_cso_ops_kpis(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL,
  managers text[] DEFAULT NULL
)
RETURNS TABLE (
  total_calls bigint,
  intro_calls bigint,
  intro_flup bigint,
  sales_calls bigint,
  sales_flup bigint,
  avg_quality numeric
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      call_type,
      (NULLIF(call_duration_sec::text, '')::numeric) AS call_duration_sec,
      (NULLIF("Average_quality"::text, '')::numeric) AS average_quality
    FROM v_app_calls_norm
    WHERE (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND (managers IS NULL OR cardinality(managers) = 0 OR manager = ANY(managers))
  )
  SELECT
    COUNT(*) AS total_calls,
    SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END) AS intro_calls,
    SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END) AS intro_flup,
    SUM(CASE WHEN call_type = 'sales_call' THEN 1 ELSE 0 END) AS sales_calls,
    SUM(CASE WHEN call_type = 'sales_followup' THEN 1 ELSE 0 END) AS sales_flup,
    ROUND(AVG(average_quality), 2) AS avg_quality
  FROM base;
$$;


CREATE OR REPLACE FUNCTION rpc_cso_anomalies(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL,
  managers text[] DEFAULT NULL
)
RETURNS TABLE (
  call_datetime timestamptz,
  manager text,
  pipeline_name text,
  duration_min numeric,
  next_step_type text,
  audio_url text,
  kommo_link text
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      call_datetime::timestamptz AS call_datetime,
      manager,
      pipeline_name,
      (NULLIF(call_duration_sec::text, '')::numeric) AS call_duration_sec,
      next_step_type,
      audio_url,
      kommo_link
    FROM v_app_calls_norm
    WHERE (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND (managers IS NULL OR cardinality(managers) = 0 OR manager = ANY(managers))
  )
  SELECT
    call_datetime,
    manager,
    pipeline_name,
    ROUND((call_duration_sec / 60.0)::numeric, 1) AS duration_min,
    next_step_type,
    audio_url,
    kommo_link
  FROM base
  WHERE call_duration_sec > 600
    AND (
      lower(coalesce(next_step_type, '')) = 'callback_vague'
      OR (
        lower(coalesce(next_step_type, '')) LIKE '%callback%'
        AND lower(coalesce(next_step_type, '')) LIKE '%vague%'
      )
    )
  ORDER BY call_duration_sec DESC
  LIMIT 2000;
$$;


CREATE OR REPLACE FUNCTION rpc_cso_low_quality(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL,
  managers text[] DEFAULT NULL
)
RETURNS TABLE (
  call_datetime timestamptz,
  manager text,
  pipeline_name text,
  average_quality numeric,
  audio_url text,
  kommo_link text
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      call_datetime::timestamptz AS call_datetime,
      manager,
      pipeline_name,
      (NULLIF("Average_quality"::text, '')::numeric) AS average_quality,
      audio_url,
      kommo_link
    FROM v_app_calls_norm
    WHERE (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND (managers IS NULL OR cardinality(managers) = 0 OR manager = ANY(managers))
  )
  SELECT
    call_datetime,
    manager,
    pipeline_name,
    average_quality,
    audio_url,
    kommo_link
  FROM base
  WHERE average_quality < 4.0
  ORDER BY average_quality ASC NULLS LAST
  LIMIT 2000;
$$;


CREATE OR REPLACE FUNCTION rpc_cso_talk_time_by_manager(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL,
  managers text[] DEFAULT NULL
)
RETURNS TABLE (
  manager text,
  call_type_group text,
  minutes float8,
  calls int,
  total_calls int
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      manager,
      call_type,
      (NULLIF(call_duration_sec::text, '')::numeric) AS call_duration_sec
    FROM v_app_calls_norm
    WHERE (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND (managers IS NULL OR cardinality(managers) = 0 OR manager = ANY(managers))
      AND manager IS NOT NULL
      AND trim(manager) <> ''
  ),
  typed AS (
    SELECT
      manager,
      CASE
        WHEN call_type = 'intro_call' THEN 'Intro Call'
        WHEN call_type = 'intro_followup' THEN 'Intro Flup'
        WHEN call_type = 'sales_call' THEN 'Sales Call'
        WHEN call_type = 'sales_followup' THEN 'Sales Flup'
        ELSE 'Other'
      END AS call_type_group,
      (call_duration_sec / 60.0)::float8 AS minutes
    FROM base
  ),
  agg AS (
    SELECT
      manager,
      call_type_group,
      SUM(minutes)::float8 AS minutes,
      COUNT(*)::int AS calls
    FROM typed
    GROUP BY manager, call_type_group
  ),
  totals AS (
    SELECT manager, SUM(calls)::int AS total_calls
    FROM agg
    GROUP BY manager
  )
  SELECT
    a.manager,
    a.call_type_group,
    a.minutes,
    a.calls,
    t.total_calls
  FROM agg a
  JOIN totals t ON t.manager = a.manager
  ORDER BY a.manager, a.call_type_group;
$$;


CREATE OR REPLACE FUNCTION rpc_cso_calls_by_pipeline(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL,
  managers text[] DEFAULT NULL
)
RETURNS TABLE (
  pipeline_name text,
  call_type_group text,
  calls int,
  minutes float8,
  total_minutes float8
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      pipeline_name,
      call_type,
      (NULLIF(call_duration_sec::text, '')::numeric) AS call_duration_sec
    FROM v_app_calls_norm
    WHERE (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND (managers IS NULL OR cardinality(managers) = 0 OR manager = ANY(managers))
      AND pipeline_name IS NOT NULL
      AND trim(pipeline_name) <> ''
  ),
  typed AS (
    SELECT
      pipeline_name,
      CASE
        WHEN call_type = 'intro_call' THEN 'Intro Call'
        WHEN call_type = 'intro_followup' THEN 'Intro Flup'
        WHEN call_type = 'sales_call' THEN 'Sales Call'
        WHEN call_type = 'sales_followup' THEN 'Sales Flup'
        ELSE 'Other'
      END AS call_type_group,
      (call_duration_sec / 60.0)::float8 AS minutes
    FROM base
  ),
  agg AS (
    SELECT
      pipeline_name,
      call_type_group,
      COUNT(*)::int AS calls,
      SUM(minutes)::float8 AS minutes
    FROM typed
    GROUP BY pipeline_name, call_type_group
  ),
  totals AS (
    SELECT pipeline_name, SUM(minutes)::float8 AS total_minutes
    FROM agg
    GROUP BY pipeline_name
  )
  SELECT
    a.pipeline_name,
    a.call_type_group,
    a.calls,
    a.minutes,
    t.total_minutes
  FROM agg a
  JOIN totals t ON t.pipeline_name = a.pipeline_name
  ORDER BY a.pipeline_name, a.call_type_group;
$$;


CREATE OR REPLACE FUNCTION rpc_cso_manager_productivity_timeline(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL,
  managers text[] DEFAULT NULL
)
RETURNS TABLE (
  call_date date,
  manager text,
  computed_market text,
  total_minutes float8,
  intro_calls int,
  intro_flup int,
  sales_calls int,
  sales_flup int
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      call_date,
      manager,
      computed_market,
      call_type,
      (NULLIF(call_duration_sec::text, '')::numeric) AS call_duration_sec
    FROM v_app_calls_norm
    WHERE call_date IS NOT NULL
      AND manager IS NOT NULL
      AND trim(manager) <> ''
      AND (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND (managers IS NULL OR cardinality(managers) = 0 OR manager = ANY(managers))
  )
  SELECT
    call_date,
    manager,
    computed_market,
    (SUM(call_duration_sec) / 60.0)::float8 AS total_minutes,
    SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END)::int AS intro_calls,
    SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::int AS intro_flup,
    SUM(CASE WHEN call_type = 'sales_call' THEN 1 ELSE 0 END)::int AS sales_calls,
    SUM(CASE WHEN call_type = 'sales_followup' THEN 1 ELSE 0 END)::int AS sales_flup
  FROM base
  GROUP BY call_date, manager, computed_market
  ORDER BY call_date, manager;
$$;


CREATE OR REPLACE FUNCTION rpc_cso_call_control(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL,
  managers text[] DEFAULT NULL
)
RETURNS TABLE (
  manager text,
  outcome_category text,
  count int,
  total_calls int,
  avg_quality numeric,
  defined_rate numeric
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      manager,
      (NULLIF("Average_quality"::text, '')::numeric) AS average_quality,
      CASE
        WHEN next_step_type ILIKE ANY (ARRAY['%lesson_scheduled%', '%callback_scheduled%', '%payment_pending%', '%sold%']) THEN 'Defined'
        WHEN next_step_type ILIKE '%vague%' THEN 'Vague'
        ELSE 'Other'
      END AS outcome_category
    FROM v_app_calls_norm
    WHERE manager IS NOT NULL
      AND trim(manager) <> ''
      AND (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND (managers IS NULL OR cardinality(managers) = 0 OR manager = ANY(managers))
  ),
  totals AS (
    SELECT
      manager,
      COUNT(*)::int AS total_calls,
      ROUND(AVG(average_quality), 2) AS avg_quality,
      SUM(CASE WHEN outcome_category = 'Defined' THEN 1 ELSE 0 END)::numeric AS defined_count
    FROM base
    GROUP BY manager
  ),
  counts AS (
    SELECT
      manager,
      outcome_category,
      COUNT(*)::int AS count
    FROM base
    GROUP BY manager, outcome_category
  )
  SELECT
    c.manager,
    c.outcome_category,
    c.count,
    t.total_calls,
    t.avg_quality,
    ROUND((t.defined_count / NULLIF(t.total_calls, 0))::numeric, 4) AS defined_rate
  FROM counts c
  JOIN totals t ON t.manager = c.manager
  ORDER BY c.manager, c.outcome_category;
$$;


CREATE OR REPLACE FUNCTION rpc_cso_friction_by_pipeline(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL,
  managers text[] DEFAULT NULL
)
RETURNS TABLE (
  pipeline_name text,
  type text,
  value numeric,
  total_calls int
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      pipeline_name,
      call_type
    FROM v_app_calls_norm
    WHERE pipeline_name IS NOT NULL
      AND trim(pipeline_name) <> ''
      AND (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND (managers IS NULL OR cardinality(managers) = 0 OR manager = ANY(managers))
  ),
  by_pipe AS (
    SELECT
      pipeline_name,
      SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END)::int AS intro_calls,
      SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::int AS intro_flups,
      SUM(CASE WHEN call_type = 'sales_call' THEN 1 ELSE 0 END)::int AS sales_calls,
      SUM(CASE WHEN call_type = 'sales_followup' THEN 1 ELSE 0 END)::int AS sales_flups
    FROM base
    GROUP BY pipeline_name
  )
  SELECT
    pipeline_name,
    'Intro Friction' AS type,
    ROUND((intro_flups::numeric / NULLIF(intro_calls, 0)), 2) AS value,
    (intro_calls + intro_flups) AS total_calls
  FROM by_pipe
  UNION ALL
  SELECT
    pipeline_name,
    'Sales Friction' AS type,
    ROUND((sales_flups::numeric / NULLIF(sales_calls, 0)), 2) AS value,
    (sales_calls + sales_flups) AS total_calls
  FROM by_pipe;
$$;


CREATE OR REPLACE FUNCTION rpc_cso_friction_defined_bubble(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL,
  managers text[] DEFAULT NULL
)
RETURNS TABLE (
  manager text,
  pipeline_name text,
  computed_market text,
  average_quality numeric,
  total_calls int,
  primaries int,
  followups int,
  defined_primaries int,
  defined_rate_pct numeric,
  friction_index numeric
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      manager,
      pipeline_name,
      computed_market,
      call_type,
      (NULLIF("Average_quality"::text, '')::numeric) AS average_quality,
      CASE
        WHEN next_step_type ILIKE '%vague%' THEN 'Vague'
        WHEN next_step_type ILIKE ANY (ARRAY['%lesson_scheduled%', '%callback_scheduled%', '%payment_pending%', '%sold%']) THEN 'Defined'
        ELSE 'Other'
      END AS outcome_category
    FROM v_app_calls_norm
    WHERE manager IS NOT NULL
      AND trim(manager) <> ''
      AND pipeline_name IS NOT NULL
      AND trim(pipeline_name) <> ''
      AND (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND (managers IS NULL OR cardinality(managers) = 0 OR manager = ANY(managers))
  ),
  agg AS (
    SELECT
      manager,
      pipeline_name,
      computed_market,
      ROUND(AVG(average_quality), 2) AS average_quality,
      COUNT(*)::int AS total_calls,
      SUM(CASE WHEN call_type IN ('intro_call', 'sales_call') THEN 1 ELSE 0 END)::int AS primaries,
      SUM(CASE WHEN call_type IN ('intro_followup', 'sales_followup') THEN 1 ELSE 0 END)::int AS followups,
      SUM(CASE WHEN call_type IN ('intro_call', 'sales_call') AND outcome_category <> 'Vague' THEN 1 ELSE 0 END)::int AS defined_primaries
    FROM base
    GROUP BY manager, pipeline_name, computed_market
  )
  SELECT
    manager,
    pipeline_name,
    computed_market,
    average_quality,
    total_calls,
    primaries,
    followups,
    defined_primaries,
    ROUND((defined_primaries::numeric / NULLIF(primaries, 0) * 100), 2) AS defined_rate_pct,
    ROUND((followups::numeric / NULLIF(primaries, 0)), 2) AS friction_index
  FROM agg;
$$;


CREATE OR REPLACE FUNCTION rpc_cso_discovery_depth(
  date_start date DEFAULT NULL,
  date_end date DEFAULT NULL,
  markets text[] DEFAULT NULL,
  pipelines text[] DEFAULT NULL,
  managers text[] DEFAULT NULL
)
RETURNS TABLE (
  manager text,
  total_calls int,
  no_objections_calls int,
  with_objections_calls int,
  sterile_rate numeric,
  market text,
  avg_quality numeric,
  intro_calls int,
  intro_flups int,
  sales_calls int,
  sales_flups int,
  intro_friction numeric,
  sales_friction numeric
)
LANGUAGE sql
STABLE
AS $$
  WITH base AS (
    SELECT
      manager,
      computed_market,
      call_type,
      main_objection_type,
      (NULLIF("Average_quality"::text, '')::numeric) AS average_quality
    FROM v_app_calls_norm
    WHERE manager IS NOT NULL
      AND trim(manager) <> ''
      AND call_type IN ('intro_call', 'sales_call', 'intro_followup', 'sales_followup')
      AND (date_start IS NULL OR call_date >= date_start)
      AND (date_end IS NULL OR call_date <= date_end)
      AND (markets IS NULL OR cardinality(markets) = 0 OR computed_market = ANY(markets))
      AND (pipelines IS NULL OR cardinality(pipelines) = 0 OR pipeline_name = ANY(pipelines))
      AND (managers IS NULL OR cardinality(managers) = 0 OR manager = ANY(managers))
  ),
  primaries AS (
    SELECT *
    FROM base
    WHERE call_type IN ('intro_call', 'sales_call')
  ),
  sterile AS (
    SELECT
      manager,
      COUNT(*)::int AS total_calls,
      SUM(
        CASE
          WHEN lower(coalesce(main_objection_type, 'none')) IN ('none', '', 'nan') THEN 1
          ELSE 0
        END
      )::int AS no_objections_calls,
      ROUND(AVG(average_quality), 2) AS avg_quality,
      MAX(computed_market) AS market
    FROM primaries
    GROUP BY manager
  ),
  fr AS (
    SELECT
      manager,
      SUM(CASE WHEN call_type = 'intro_call' THEN 1 ELSE 0 END)::int AS intro_calls,
      SUM(CASE WHEN call_type = 'intro_followup' THEN 1 ELSE 0 END)::int AS intro_flups,
      SUM(CASE WHEN call_type = 'sales_call' THEN 1 ELSE 0 END)::int AS sales_calls,
      SUM(CASE WHEN call_type = 'sales_followup' THEN 1 ELSE 0 END)::int AS sales_flups
    FROM base
    GROUP BY manager
  )
  SELECT
    s.manager,
    s.total_calls,
    s.no_objections_calls,
    (s.total_calls - s.no_objections_calls) AS with_objections_calls,
    ROUND((s.no_objections_calls::numeric / NULLIF(s.total_calls, 0) * 100), 2) AS sterile_rate,
    s.market,
    s.avg_quality,
    f.intro_calls,
    f.intro_flups,
    f.sales_calls,
    f.sales_flups,
    ROUND((f.intro_flups::numeric / NULLIF(f.intro_calls, 0)), 2) AS intro_friction,
    ROUND((f.sales_flups::numeric / NULLIF(f.sales_calls, 0)), 2) AS sales_friction
  FROM sterile s
  JOIN fr f ON f.manager = s.manager
  ORDER BY sterile_rate DESC, s.total_calls DESC;
$$;
