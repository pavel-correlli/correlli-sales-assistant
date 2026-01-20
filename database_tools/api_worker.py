from supabase import create_client, Client
import toml
import os
import json
from datetime import datetime

def get_supabase_config():
    possible_paths = [
        os.path.join(os.getcwd(), '.streamlit', 'secrets.toml'),
        os.path.join(os.path.dirname(__file__), '..', '.streamlit', 'secrets.toml'),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            secrets = toml.load(path)
            if 'supabase' in secrets:
                return secrets['supabase']['url'], secrets['supabase']['key']

    raise FileNotFoundError("Supabase configuration not found in .streamlit/secrets.toml")

def main():
    try:
        url, key = get_supabase_config()
        supabase: Client = create_client(url, key)
        
        # List of tables/views to check (common names + known ones)
        targets = [
            "Algonova_Calls_Raw",
            "v_analytics_calls",
            "v_sales_performance_metrics",
            "v_analytics_attributes_frequency",
            "v_ceo_lead_metrics",
            "v_ceo_daily_pulse",
            "v_ceo_vague_index",
            "v_ceo_manager_load",
            "v_leads_metrics",
            "v_marketing_metrics",
            "v_sales_funnel",
            "v_agent_performance",
            "v_calls_detailed",
            "v_daily_metrics",
            "v_weekly_metrics",
            "v_monthly_metrics",
            "v_market_performance",
            "Algonova_Sales_Raw"
        ]
        
        schema_info = []
        schema_info.append(f"-- ===========================================")
        schema_info.append(f"-- DATABASE SCHEMA (EXTRACTED VIA API)")
        schema_info.append(f"-- Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        schema_info.append(f"-- ===========================================\n")

        for target in targets:
            print(f"Extracting columns for {target}...")
            try:
                # Попробуем сделать запрос через .select().limit(1)
                res = supabase.table(target).select("*").limit(1).execute()
                
                columns = []
                sample_row = None
                
                if res.data:
                    sample_row = res.data[0]
                    columns = list(sample_row.keys())
                else:
                    print(f"Warning: No data in {target}, structure might be missing.")
                
                if columns:
                    schema_info.append(f"-- Table/View: {target}")
                    schema_info.append(f"CREATE TABLE {target} (")
                    
                    cols_def = []
                    for col in columns:
                        val = sample_row.get(col) if sample_row else None
                        # Простая попытка подсказать типы данных
                        if isinstance(val, (int, float)):
                            col_type = "numeric"
                        elif col.endswith('_at') or col.endswith('date') or col.endswith('datetime'):
                            col_type = "timestamp"
                        elif isinstance(val, bool):
                            col_type = "boolean"
                        else:
                            col_type = "text"
                        cols_def.append(f"    {col} {col_type}")
                    
                    schema_info.append(",\n".join(cols_def))
                    schema_info.append(");\n")
                else:
                    schema_info.append(f"-- Table/View: {target} (Empty or no access)")
                    schema_info.append(f"-- Could not extract columns automatically because the view is empty.\n")
            except Exception as e:
                print(f"Error extracting {target}: {e}")
                schema_info.append(f"-- Table/View: {target} (Error: {str(e)[:100]})\n")

        # Сохраняем результат
        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(output_dir, 'schema_truth.sql')
        
        print(f"Writing to: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(schema_info))
            
        print(f"Successfully saved full schema to: {output_path}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
