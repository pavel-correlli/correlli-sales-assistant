-- Migration: 20260115_analytics_refactor_v2
-- Description: Strict Metadata Logic, Entity Atomization, Action Logic (Success vs Vague)
-- Quote table names to handle case sensitivity if necessary, though Supabase/Postgres is usually lowercase unless quoted.
-- Based on error "relation algonova_calls_raw does not exist", likely need quotes or it's in a different schema, but schema_truth says it exists.
-- Let's try quoting "Algonova_Calls_Raw" exactly as defined in schema_truth.sql.

-- 1. Entity Atomization
-- View to explode parent_goals
CREATE OR REPLACE VIEW v_analytics_goals_atomized AS
SELECT 
    call_id,
    date,
    market,
    manager,
    pipeline_name,
    trim(goal) as goal
FROM "Algonova_Calls_Raw",
LATERAL unnest(string_to_array(parent_goals, ';')) as goal
WHERE parent_goals IS NOT NULL AND trim(goal) <> '';

-- View to explode parent_fears
CREATE OR REPLACE VIEW v_analytics_fears_atomized AS
SELECT 
    call_id,
    date,
    market,
    manager,
    pipeline_name,
    trim(fear) as fear
FROM "Algonova_Calls_Raw",
LATERAL unnest(string_to_array(parent_fears, ';')) as fear
WHERE parent_fears IS NOT NULL AND trim(fear) <> '';

-- View to explode objection_list
CREATE OR REPLACE VIEW v_analytics_objections_atomized AS
SELECT 
    call_id,
    date,
    market,
    manager,
    pipeline_name,
    trim(objection) as objection
FROM "Algonova_Calls_Raw",
LATERAL unnest(string_to_array(objection_list, ';')) as objection
WHERE objection_list IS NOT NULL AND trim(objection) <> '';

-- 2. Action Logic (Success vs Vague) & Iron Metrics Base
CREATE OR REPLACE VIEW v_analytics_calls_enhanced AS
SELECT 
    r.*,
    -- Computed call_outcome
    CASE 
        WHEN next_step_type ILIKE '%vague%' THEN 'Vague'
        ELSE 'Success'
    END as call_outcome,
    
    -- Normalized Call Type
    CASE 
        WHEN call_type ILIKE '%intro%' THEN 'Intro'
        WHEN call_type ILIKE '%sales%' THEN 'Sales'
        ELSE 'Other'
    END as call_category
FROM "Algonova_Calls_Raw" r;

-- 3. Aggregated Metrics for CEO (Iron Metrics)
CREATE OR REPLACE VIEW v_ceo_iron_metrics AS
WITH LeadStats AS (
    SELECT 
        lead_id,
        market,
        manager,
        pipeline_name,
        
        -- Counts
        COUNT(CASE WHEN call_type ILIKE '%intro%' THEN 1 END) as intro_count,
        COUNT(CASE WHEN call_type ILIKE '%sales%' THEN 1 END) as sales_count,
        
        -- Outcomes
        COUNT(CASE WHEN next_step_type ILIKE '%vague%' THEN 1 END) as vague_count,
        COUNT(*) as total_calls
    FROM "Algonova_Calls_Raw"
    GROUP BY lead_id, market, manager, pipeline_name
)
SELECT
    market,
    manager,
    pipeline_name,
    
    -- OCC Intro: Leads with exactly 1 intro call
    COUNT(CASE WHEN intro_count = 1 THEN 1 END) as occ_intro_leads,
    
    -- OCC Sales: Leads with exactly 1 sales call
    COUNT(CASE WHEN sales_count = 1 THEN 1 END) as occ_sales_leads,
    
    -- Vague Index Data
    SUM(vague_count) as total_vague_calls,
    SUM(total_calls) as total_calls_volume,
    
    -- Friction Data (Approximation: Calls > 1 implies friction)
    SUM(CASE WHEN intro_count > 1 THEN intro_count - 1 ELSE 0 END) as intro_followups,
    SUM(CASE WHEN intro_count >= 1 THEN 1 ELSE 0 END) as intro_primaries,
    
    SUM(CASE WHEN sales_count > 1 THEN sales_count - 1 ELSE 0 END) as sales_followups,
    SUM(CASE WHEN sales_count >= 1 THEN 1 ELSE 0 END) as sales_primaries

FROM LeadStats
GROUP BY market, manager, pipeline_name;
