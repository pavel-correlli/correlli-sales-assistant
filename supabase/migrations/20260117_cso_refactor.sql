-- Migration: 20260117_cso_refactor
-- Description: Refactor CSO Analytics to use dedicated SQL views for better performance and consistency.
-- Replaces heavy Python processing with SQL aggregation.

-- 1. Clarity & Commitment Chart View
-- Aggregates defined/vague outcomes by manager/date.
-- Logic: Defined matches specific keywords, Vague matches 'vague'.
CREATE OR REPLACE VIEW v_cso_clarity_chart AS
SELECT
    date,
    manager,
    market,
    pipeline_name,
    COUNT(*) as total_calls,
    COUNT(CASE 
        WHEN next_step_type ILIKE ANY (ARRAY['%lesson_scheduled%', '%callback_scheduled%', '%payment_pending%', '%sold%']) THEN 1 
        ELSE NULL 
    END) as defined_count,
    COUNT(CASE 
        WHEN next_step_type ILIKE '%vague%' THEN 1 
        ELSE NULL 
    END) as vague_count
FROM "Algonova_Calls_Raw"
GROUP BY date, manager, market, pipeline_name;

-- 2. Friction Chart View (Pipeline Level)
-- Aggregates primary vs followup calls by pipeline/date.
CREATE OR REPLACE VIEW v_cso_friction_chart AS
SELECT
    date,
    pipeline_name,
    market,
    COUNT(CASE WHEN call_type = 'intro_call' THEN 1 END) as intro_primaries,
    COUNT(CASE WHEN call_type = 'intro_followup' THEN 1 END) as intro_followups,
    COUNT(CASE WHEN call_type = 'sales_call' THEN 1 END) as sales_primaries,
    COUNT(CASE WHEN call_type = 'sales_followup' THEN 1 END) as sales_followups
FROM "Algonova_Calls_Raw"
GROUP BY date, pipeline_name, market;

-- 3. Efficiency Bubble Chart View (Manager Level)
-- Aggregates Quality, Defined Rate, and Friction components.
CREATE OR REPLACE VIEW v_cso_efficiency_bubble AS
SELECT
    date,
    manager,
    market,
    pipeline_name,
    AVG(Average_quality) as avg_quality,
    COUNT(*) as total_calls,
    COUNT(CASE 
        WHEN next_step_type ILIKE ANY (ARRAY['%lesson_scheduled%', '%callback_scheduled%', '%payment_pending%', '%sold%']) THEN 1 
        ELSE NULL 
    END) as defined_count,
    COUNT(CASE WHEN call_type IN ('intro_call', 'sales_call') THEN 1 END) as primary_calls,
    COUNT(CASE WHEN call_type IN ('intro_followup', 'sales_followup') THEN 1 END) as followup_calls
FROM "Algonova_Calls_Raw"
GROUP BY date, manager, market, pipeline_name;

-- 4. Silence Chart View
-- Aggregates Sterile (No Objection) calls.
-- Filtered to only Intro/Sales calls usually, but let's keep it broad and filter in query if needed, 
-- or stick to the logic: Silence matters most in Intro/Sales.
CREATE OR REPLACE VIEW v_cso_silence_chart AS
SELECT
    date,
    manager,
    market,
    pipeline_name,
    COUNT(*) as total_calls,
    COUNT(CASE 
        WHEN main_objection_type IS NULL 
          OR main_objection_type ILIKE 'none' 
          OR trim(main_objection_type) = '' 
          OR main_objection_type ILIKE 'nan'
        THEN 1 
    END) as sterile_count,
    COUNT(CASE WHEN next_step_type ILIKE '%vague%' THEN 1 END) as vague_count
FROM "Algonova_Calls_Raw"
WHERE call_type IN ('intro_call', 'sales_call')
GROUP BY date, manager, market, pipeline_name;

-- Cleanup unused views
DROP VIEW IF EXISTS v_lead_friction_metrics;
