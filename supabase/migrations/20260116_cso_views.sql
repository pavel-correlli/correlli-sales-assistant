-- View for calculating Friction Index per Lead
-- Groups calls by lead_id to count primaries vs follow-ups
CREATE OR REPLACE VIEW v_lead_friction_metrics AS
SELECT 
    lead_id,
    MAX(manager) as manager,
    MAX(market) as market,
    MAX(date) as last_interaction_date,
    COUNT(CASE WHEN call_type = 'intro' THEN 1 END) as intro_calls,
    COUNT(CASE WHEN call_type = 'intro_followup' THEN 1 END) as intro_followups,
    COUNT(CASE WHEN call_type = 'sales' THEN 1 END) as sales_calls,
    COUNT(CASE WHEN call_type = 'sales_followup' THEN 1 END) as sales_followups,
    -- Defined outcomes: lesson_scheduled, callback_scheduled, payment_pending, sold
    BOOL_OR(next_step_type IN ('lesson_scheduled', 'callback_scheduled', 'payment_pending', 'sold')) as is_defined,
    BOOL_OR(next_step_type = 'callback_vague') as is_vague,
    COUNT(*) as total_calls,
    AVG(Average_quality) as avg_quality
FROM 
    "Algonova_Calls_Raw"
GROUP BY 
    lead_id;
