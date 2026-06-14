"""
Generate Snowflake Notebook Cell 2 Script

This script runs on YOUR LAPTOP and generates the complete self-contained
Python script that will be pasted into CELL 2 of the Snowflake notebook.

The generated script contains:
  - Complete metadata (no external files needed)
  - All configuration
  - Main execution code that calls the classes from Cell 1

Usage:
    python3 generate_snowflake_notebook_cell2.py
    
    Then copy the output file content and paste into Snowflake notebook cell 2
"""

import json
import csv
from pathlib import Path
from datetime import datetime


def load_table_list():
    """Load the list of tables to download from CSV."""
    csv_file = Path(__file__).parent / "list_of_tables_to_download.csv"
    
    tables = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            table_name = row.get('table_to_download', '').strip()
            if table_name:
                tables.append(table_name)
    
    print(f"✓ Loaded {len(tables)} tables from {csv_file}")
    return tables


def load_cached_metadata():
    """Load all cached metadata from JSON files."""
    cache_dir = Path(__file__).parent.parent / "misc_scripts" / "gen_extract_scripts" / "json_documentation_cache"
    
    cached = {}
    for json_file in cache_dir.glob("*.json"):
        if json_file.name.startswith("test_") or json_file.name.startswith("sample_"):
            continue
        
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                cached[json_file.stem] = data
                print(f"✓ Loaded {json_file.name}")
        except Exception as e:
            print(f"⚠ Could not load {json_file.name}: {e}")
    
    return cached


def parse_table_name(full_table_name):
    """Parse fully qualified table name into components."""
    parts = full_table_name.split('.')
    if len(parts) != 3:
        raise ValueError(f"Invalid table name format: {full_table_name}")
    
    return {
        'database': parts[0],
        'schema': parts[1],
        'table': parts[2],
        'full_table_name': full_table_name
    }


def find_table_metadata(table_name, cached_metadata):
    """Find table metadata in cached JSON files."""
    table_upper = table_name.upper()
    
    for cache_name, cache_data in cached_metadata.items():
        if 'tables' not in cache_data:
            continue
        
        for table_info in cache_data['tables']:
            if table_info.get('table_name', '').upper() == table_upper:
                return table_info
    
    return None


def build_select_from_columns(full_table_name, columns):
    """Build SELECT statement with explicit columns."""
    if not columns:
        return f"SELECT * FROM {full_table_name}"
    
    column_names = [col.get('column_name') for col in columns if col.get('column_name')]
    
    if not column_names:
        return f"SELECT * FROM {full_table_name}"
    
    column_str = ",\n                ".join(column_names)
    return f"""SELECT
                {column_str}
            FROM {full_table_name}"""


def generate_table_metadata(tables, cached_metadata):
    """Generate metadata for all tables."""
    metadata_tables = []
    
    for full_name in tables:
        try:
            table_info = parse_table_name(full_name)
            
            # Find in cached metadata
            cached_table = find_table_metadata(table_info['table'], cached_metadata)
            
            if cached_table and 'columns' in cached_table:
                columns = cached_table['columns']
                select_query = build_select_from_columns(full_name, columns)
            else:
                select_query = f"SELECT * FROM {full_name}"
                columns = []
            
            # Generate file stub
            file_stub = f"{table_info['table'].lower()}_idr_export"
            
            table_meta = {
                'database': table_info['database'],
                'schema': table_info['schema'],
                'table': table_info['table'],
                'full_table_name': full_name,
                'columns': columns,
                'file_name_stub': file_stub,
                'version_number': 'v01',
                'select_query': select_query
            }
            
            metadata_tables.append(table_meta)
            print(f"  ✓ {full_name}")
        
        except Exception as e:
            print(f"  ✗ Error processing {full_name}: {e}")
    
    return metadata_tables


def generate_notebook_cell_2_script(metadata_tables):
    """Generate the complete Snowflake notebook cell 2 script."""
    
    # Convert metadata to JSON
    metadata_json = {
        "generated": datetime.now().isoformat(),
        "source": "Generated from list_of_tables_to_download.csv and cached metadata",
        "tables": metadata_tables
    }
    
    metadata_json_str = json.dumps(metadata_json, indent=2)
    
    script = f'''"""
Snowflake Export Main Script - Cell 2

This script was auto-generated with all metadata embedded.
It requires the classes from Cell 1 (snowflake_export_classes.py).

Just run this cell to start the export loop.
"""

import json
from datetime import datetime

# ============================================================================
# EMBEDDED METADATA
# ============================================================================

METADATA_JSON = {metadata_json_str}


# ============================================================================
# CONFIGURATION
# ============================================================================

POLLING_INTERVAL_MINUTES = 5      # Check for downloads every 5 minutes
QUIT_AFTER_HOURS = 2              # Stop after 2 hours with no activity


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function - loads metadata and starts export loop."""
    
    try:
        # Get active Snowflake session
        session = get_active_session()  # noqa: F821
        
        print("Snowflake session acquired")
        print(f"\\nMetadata prepared for {{len(METADATA_JSON.get('tables', []))}} tables")
        print(f"Generated: {{METADATA_JSON.get('generated', 'Unknown')}}")
        print(f"Source: {{METADATA_JSON.get('source', 'Unknown')}}")
        
        # Print configuration
        print("\\n" + "="*60)
        print("EXPORT LOOP CONFIGURATION")
        print("="*60)
        print(f"Polling interval: {{POLLING_INTERVAL_MINUTES}} minutes")
        print(f"Timeout: {{QUIT_AFTER_HOURS}} hours with no activity")
        print(f"Total tables: {{len(METADATA_JSON.get('tables', []))}}")
        print("="*60)
        
        # Initialize and run the export loop
        metadata = ExportMetadata(METADATA_JSON)
        loop = ExportLoop(
            session,
            metadata,
            POLLING_INTERVAL_MINUTES,
            QUIT_AFTER_HOURS
        )
        loop.run()
        
        print("\\n✓ Export loop completed successfully!")
        
    except Exception as e:
        print(f"\\n✗ Fatal error in export loop: {{str(e)}}")
        print(f"Please check your configuration and try again")
        raise


# Call main() to start the export loop
main()
'''
    
    return script


def main():
    """Main execution."""
    print("="*60)
    print("Snowflake Notebook Cell 2 Generator")
    print("="*60)
    
    print("\n1. Loading table list...")
    tables = load_table_list()
    
    print(f"\n2. Loading cached metadata ({len(tables)} tables to find)...")
    cached_metadata = load_cached_metadata()
    
    print(f"\n3. Generating table metadata...")
    metadata_tables = generate_table_metadata(tables, cached_metadata)
    print(f"  ✓ Generated metadata for {len(metadata_tables)} tables")
    
    print(f"\n4. Generating Snowflake notebook cell 2 script...")
    script = generate_notebook_cell_2_script(metadata_tables)
    
    # Write to file
    output_file = Path(__file__).parent / "snowflake_notebook_cell_2.py"
    with open(output_file, 'w') as f:
        f.write(script)
    
    print(f"\n✓ Script generated successfully!")
    print(f"  Output: {output_file}")
    print(f"\n📋 Next steps:")
    print(f"  1. Open {output_file}")
    print(f"  2. Copy the entire contents")
    print(f"  3. Paste into CELL 2 of your Snowflake notebook")
    print(f"  4. Run the cell")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
