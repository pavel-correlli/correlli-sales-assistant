-- Migration: 20260117_analytics_master_view
-- Description: Create a master view that mirrors Algonova_Calls_Raw but with correct types and calculated fields.
-- This ensures a single source of truth for all dashboards and eliminates discrepancies.

CREATE OR REPLACE VIEW v_analytics_master AS
SELECT
    -- Identifiers
    call_id,
    lead_id,
    manager,
    pipeline_name,
    market,
    
    -- Dates (Standardized)
    COALESCE(
        NULLIF(date, NULL), 
        call_datetime::date, 
        created_at::date
    ) as date_iso,
    call_datetime,
    created_at,

    -- Call Details
    call_type,
    call_duration_sec,
    Average_quality,
    
    -- Outcomes & Next Steps
    next_step_type,
    main_objection_type,
    
    -- Links
    kommo_link,
    
    -- Computed Fields (Mirrors Python Logic for Consistency)
    CASE 
        WHEN next_step_type ILIKE ANY (ARRAY['%lesson_scheduled%', '%callback_scheduled%', '%payment_pending%', '%sold%']) THEN 'Defined'
        WHEN next_step_type ILIKE '%vague%' THEN 'Vague'
        ELSE 'Other'
    END as outcome_category,
    
    CASE
        WHEN pipeline_name ILIKE 'CZ%' THEN 'CZ'
        WHEN pipeline_name ILIKE 'SK%' THEN 'SK'
        WHEN pipeline_name ILIKE 'RUK%' THEN 'RUK'
        ELSE 'Others'
    END as computed_market

FROM "Algonova_Calls_Raw";
