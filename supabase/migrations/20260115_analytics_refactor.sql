-- Migration: 20260115_analytics_refactor
-- Description: Strict Metadata Logic, Entity Atomization, Action Logic (Success vs Vague)

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
FROM Algonova_Calls_Raw,
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
FROM Algonova_Calls_Raw,
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
FROM Algonova_Calls_Raw,
LATERAL unnest(string_to_array(objection_list, ';')) as objection
WHERE objection_list IS NOT NULL AND trim(objection) <> '';

-- 2. Action Logic (Success vs Vague) & Iron Metrics Base
-- We need to identify 'intro_call' and 'sales_call' from call_type or similar logic
-- Assuming call_type column exists and has values like 'intro', 'sales' etc.
-- If not, we might need to infer from pipeline_stage_before_call or other.
-- Based on previous schema, call_type exists.

CREATE OR REPLACE VIEW v_analytics_calls_enhanced AS
SELECT 
    r.*,
    -- Computed call_outcome
    CASE 
        WHEN next_step_type ILIKE '%vague%' THEN 'Vague'
        ELSE 'Success'
    END as call_outcome,
    
    -- Normalized Call Type (simplify if needed)
    CASE 
        WHEN call_type ILIKE '%intro%' THEN 'Intro'
        WHEN call_type ILIKE '%sales%' THEN 'Sales'
        ELSE 'Other'
    END as call_category
FROM Algonova_Calls_Raw r;

-- 3. Aggregated Metrics for CEO (Iron Metrics)
-- OCC Logic: Count leads with EXACTLY 1 call of type Intro/Sales which is NOT Vague (implied success if closed? Or just processed?)
-- Definition: "Leads closed/processed after a single intro call."
-- This usually means: Count(calls) where lead_id = X AND type = Intro is 1.
-- And result was successful (moved stage? or just not vague?)
-- Let's stick to the prompt: "Кол-во лидов с ровно 1 первичным intro_call" (Count leads with exactly 1 primary intro call).
-- Does not explicitly say "Won", but "One-Call-Close" implies success.
-- Let's assume for "OCC Metric" we count leads where:
-- 1. Total Intro Calls = 1
-- 2. The Outcome of that call was 'Success' (not Vague)
-- 3. (Optional) They moved to next stage? Prompt says "Success: Any action NOT Vague". So we use that.

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
        
        -- Followups (assuming >1 implies followup, or explicit 'followup' type?)
        -- Prompt: "Friction Index: (Count of Follow-up calls) / (Count of Primary calls)"
        -- We need to distinguish Primary vs Followup.
        -- Often 'call_type' or 'pipeline_stage' helps. 
        -- If call_type contains 'followup' or if count > 1.
        -- Let's assume we can count total vs unique leads.
        
        -- Outcomes
        COUNT(CASE WHEN next_step_type ILIKE '%vague%' THEN 1 END) as vague_count,
        COUNT(*) as total_calls
    FROM Algonova_Calls_Raw
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
    
    -- Friction Data (Approximation if we don't have explicit 'followup' tag)
    -- If we treat 1st call as Primary and others as Followup:
    -- Followups = Total - 1 (if > 0)
    SUM(CASE WHEN intro_count > 1 THEN intro_count - 1 ELSE 0 END) as intro_followups,
    SUM(CASE WHEN intro_count >= 1 THEN 1 ELSE 0 END) as intro_primaries,
    
    SUM(CASE WHEN sales_count > 1 THEN sales_count - 1 ELSE 0 END) as sales_followups,
    SUM(CASE WHEN sales_count >= 1 THEN 1 ELSE 0 END) as sales_primaries

FROM LeadStats
GROUP BY market, manager, pipeline_name;
