import requests
import toml
import os
import json

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
    
    raise FileNotFoundError("Could not find supabase configuration in secrets.toml")

def main():
    try:
        url, key = get_supabase_config()
        # PostgREST OpenAPI spec is usually at /rest/v1/
        api_url = f"{url}/rest/v1/"
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        
        print(f"Fetching OpenAPI spec from {api_url}...")
        response = requests.get(api_url, headers=headers)
        
        if response.status_code == 200:
            spec = response.json()
            output_path = os.path.join(os.path.dirname(__file__), 'openapi_spec.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(spec, f, indent=2, ensure_ascii=False)
            print(f"Successfully saved OpenAPI spec to {output_path}")
            
            # Now let's extract tables and columns from the spec
            schema_info = ["-- SCHEMA EXTRACTED FROM OPENAPI SPEC\n"]
            
            definitions = spec.get('definitions', {})
            for table_name, table_def in definitions.items():
                schema_info.append(f"CREATE TABLE {table_name} (")
                properties = table_def.get('properties', {})
                cols = []
                for prop_name, prop_def in properties.items():
                    col_type = prop_def.get('type', 'text')
                    format = prop_def.get('format', '')
                    description = prop_def.get('description', '')
                    
                    col_str = f"    {prop_name} {col_type}"
                    if format:
                        col_str += f" ({format})"
                    if description:
                        col_str += f" -- {description}"
                    cols.append(col_str)
                
                schema_info.append(",\n".join(cols))
                schema_info.append(");\n")
            
            sql_output_path = os.path.join(os.path.dirname(__file__), 'schema_truth.sql')
            with open(sql_output_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(schema_info))
            print(f"Successfully generated {sql_output_path}")
            
        else:
            print(f"Failed to fetch OpenAPI spec: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
