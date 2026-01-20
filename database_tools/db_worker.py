import psycopg2
import toml
import os
from datetime import datetime

def get_db_config():
    possible_paths = [
        os.path.join(os.getcwd(), '.streamlit', 'secrets.toml'),
        os.path.join(os.path.dirname(__file__), '..', '.streamlit', 'secrets.toml'),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            secrets = toml.load(path)
            if 'database' in secrets:
                return secrets['database']

    raise FileNotFoundError("Database configuration not found in .streamlit/secrets.toml")

def fetch_schema():
    config = get_db_config()
    conn = psycopg2.connect(
        host=config['host'],
        database=config['name'],
        user=config['user'],
        password=config['pass'],
        port=config['port']
    )
    cur = conn.cursor()

    schema_info = []
    schema_info.append(f"-- ===========================================")
    schema_info.append(f"-- DATABASE SCHEMA TRUTH FILE")
    schema_info.append(f"-- Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    schema_info.append(f"-- ===========================================\n")

    # 1. Fetch Tables and Columns
    print("Extracting tables and columns...")
    cur.execute("""
        SELECT 
            t.table_name, 
            c.column_name, 
            c.data_type, 
            c.is_nullable,
            c.column_default,
            (SELECT 'PRIMARY KEY' 
             FROM information_schema.key_column_usage kcu
             JOIN information_schema.table_constraints tc 
               ON kcu.constraint_name = tc.constraint_name 
              AND kcu.table_name = tc.table_name
             WHERE kcu.table_name = t.table_name 
               AND kcu.column_name = c.column_name 
               AND tc.constraint_type = 'PRIMARY KEY') as is_pk
        FROM information_schema.tables t
        JOIN information_schema.columns c ON t.table_name = c.table_name
        WHERE t.table_schema = 'public' 
          AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name, c.ordinal_position;
    """)
    columns = cur.fetchall()
    
    tables = {}
    for table_name, col_name, data_type, is_nullable, col_default, is_pk in columns:
        if table_name not in tables:
            tables[table_name] = []
        
        col_def = f"    {col_name} {data_type}"
        if is_pk:
            col_def += " PRIMARY KEY"
        if is_nullable == 'NO' and not is_pk:
            col_def += " NOT NULL"
        if col_default:
            col_def += f" DEFAULT {col_default}"
            
        tables[table_name].append(col_def)

    schema_info.append("-- TABLES STRUCTURE")
    for table_name, cols in tables.items():
        schema_info.append(f"CREATE TABLE {table_name} (")
        schema_info.append(",\n".join(cols))
        schema_info.append(");\n")

    # 2. Fetch Views and Definitions
    print("Extracting views and definitions...")
    cur.execute("""
        SELECT viewname, definition
        FROM pg_views
        WHERE schemaname = 'public';
    """)
    views = cur.fetchall()

    schema_info.append("-- VIEWS DEFINITIONS")
    for view_name, definition in views:
        schema_info.append(f"-- View: {view_name}")
        schema_info.append(f"CREATE OR REPLACE VIEW {view_name} AS")
        schema_info.append(f"{definition.strip()};")
        schema_info.append("")

    # 3. Fetch Functions (if any)
    print("Extracting functions...")
    cur.execute("""
        SELECT routine_name, routine_definition, data_type
        FROM information_schema.routines
        WHERE routine_schema = 'public'
          AND routine_type = 'FUNCTION';
    """)
    functions = cur.fetchall()
    if functions:
        schema_info.append("-- FUNCTIONS")
        for func_name, definition, ret_type in functions:
            schema_info.append(f"-- Function: {func_name} returns {ret_type}")
            if definition:
                schema_info.append(f"{definition.strip()};")
            schema_info.append("")

    cur.close()
    conn.close()
    
    return "\n".join(schema_info)

def main():
    try:
        print("Starting schema extraction worker...")
        schema_content = fetch_schema()
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
        
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema_truth.sql')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(schema_content)
            
        print(f"Successfully saved schema to: {output_path}")
        print("You can run this script anytime to refresh the schema_truth.sql file.")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    main()
