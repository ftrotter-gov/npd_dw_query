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
    csv_file = Path(__file__).parent.parent / "step1_tables_to_export.csv"
    
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
    """Build SELECT statement with explicit column names and inline comments."""
    if not columns:
        return f"SELECT * FROM {full_table_name}"
    
    # Build each column line with inline comment (type | nullable | description)
    column_lines = []
    for col in columns:
        col_name = col.get('column_name')
        if not col_name:
            continue
        
        # Build inline comment
        type_desc = col.get('type_description', col.get('data_type', ''))
        nullable = col.get('is_nullable', '')
        nullable_str = "NOT NULL" if nullable == "NO" else "NULL"
        comment = col.get('comment', '')
        
        if comment:
            # Truncate comment to avoid excessively long lines
            comment_text = comment.replace('\n', ' ').strip()
            if len(comment_text) > 200:
                comment_text = comment_text[:200] + '...'
            inline_comment = f" -- {type_desc} | {nullable_str} | {comment_text}"
        else:
            inline_comment = f" -- {type_desc} | {nullable_str}"
        
        column_lines.append(f"                {col_name},{inline_comment}")
    
    if not column_lines:
        return f"SELECT * FROM {full_table_name}"
    
    # Last column has no trailing comma - remove it from last line
    last = column_lines[-1]
    comma_idx = last.index(',')
    column_lines[-1] = last[:comma_idx] + last[comma_idx+1:]
    
    columns_str = "\n".join(column_lines)
    
    return f"SELECT\n{columns_str}\n            FROM {full_table_name}"


def generate_table_metadata(tables, cached_metadata):
    """Generate metadata for all tables - only table name and SQL."""
    metadata_tables = []
    
    for full_name in tables:
        try:
            table_info = parse_table_name(full_name)
            
            # Find in cached metadata
            cached_table = find_table_metadata(table_info['table'], cached_metadata)
            
            if cached_table and 'columns' in cached_table:
                columns = cached_table['columns']
                
                # Use the database/schema FROM THE CACHE - it has the real Snowflake path
                # The CSV may have the wrong schema name
                cache_db = cached_table.get('database', table_info['database'])
                cache_schema = cached_table.get('schema', table_info['schema'])
                cache_table = cached_table.get('table_name', table_info['table'])
                actual_full_name = f"{cache_db}.{cache_schema}.{cache_table}"
                
                if actual_full_name != full_name:
                    print(f"    (schema corrected: {full_name} → {actual_full_name})")
                
                select_query = build_select_from_columns(actual_full_name, columns)
            else:
                actual_full_name = full_name
                select_query = f"SELECT * FROM {full_name}"
                print(f"  ⚠ No cached metadata found for {table_info['table']} - using SELECT *")
            
            # Generate file stub
            file_stub = f"{table_info['table'].lower()}_idr_export"
            
            # Only store what we need - table name, file stub, version, and SQL
            table_meta = {
                'full_table_name': actual_full_name,
                'file_name_stub': file_stub,
                'version_number': 'v01',
                'select_query': select_query
            }
            
            metadata_tables.append(table_meta)
            print(f"  ✓ {actual_full_name}")
        
        except Exception as e:
            print(f"  ✗ Error processing {full_name}: {e}")
    
    return metadata_tables


def write_cell2_script(output_file, metadata_tables):
    """Write the Cell 2 script directly to file with actual newlines in SQL."""
    
    generated = datetime.now().isoformat()
    
    with open(output_file, 'w') as f:
        # Header
        f.write('"""\n')
        f.write('Snowflake Export Main Script - Cell 2\n')
        f.write('\n')
        f.write('This script was auto-generated with all metadata embedded.\n')
        f.write('It requires the classes from Cell 1 (snowflake_export_classes.py).\n')
        f.write('\n')
        f.write('Just run this cell to start the export loop.\n')
        f.write('"""\n')
        f.write('\n')
        f.write('from datetime import datetime\n')
        f.write('\n')
        f.write('# ============================================================================\n')
        f.write('# EMBEDDED METADATA\n')
        f.write('# ============================================================================\n')
        f.write('\n')
        f.write('METADATA_JSON = {\n')
        f.write(f'    "generated": "{generated}",\n')
        f.write('    "source": "Generated from list_of_tables_to_download.csv and cached metadata",\n')
        f.write('    "tables": [\n')
        
        # Write each table as a dict with triple-quoted SQL
        for i, t in enumerate(metadata_tables):
            is_last = (i == len(metadata_tables) - 1)
            comma = "" if is_last else ","
            
            f.write('        {\n')
            f.write(f'            "full_table_name": "{t["full_table_name"]}",\n')
            f.write(f'            "file_name_stub": "{t["file_name_stub"]}",\n')
            f.write(f'            "version_number": "{t["version_number"]}",\n')
            
            # Write select_query with actual newlines using triple-quote string
            f.write('            "select_query": """\n')
            f.write(t['select_query'])
            f.write('\n"""\n')
            
            f.write(f'        }}{comma}\n')
        
        f.write('    ]\n')
        f.write('}\n')
        f.write('\n')
        
        # Configuration and main()
        f.write('# ============================================================================\n')
        f.write('# CONFIGURATION\n')
        f.write('# ============================================================================\n')
        f.write('\n')
        f.write('POLLING_INTERVAL_MINUTES = 5      # Check for downloads every 5 minutes\n')
        f.write('QUIT_AFTER_HOURS = 2              # Stop after 2 hours with no activity\n')
        f.write('\n')
        f.write('\n')
        f.write('# ============================================================================\n')
        f.write('# MAIN EXECUTION\n')
        f.write('# ============================================================================\n')
        f.write('\n')
        f.write('def main():\n')
        f.write('    """Main execution function - loads metadata and starts export loop."""\n')
        f.write('\n')
        f.write('    try:\n')
        f.write('        # Get active Snowflake session\n')
        f.write('        session = get_active_session()  # noqa: F821\n')
        f.write('\n')
        f.write('        print("Snowflake session acquired")\n')
        f.write('        print(f"\\nMetadata prepared for {len(METADATA_JSON.get(\'tables\', []))} tables")\n')
        f.write('        print(f"Generated: {METADATA_JSON.get(\'generated\', \'Unknown\')}")\n')
        f.write('\n')
        f.write('        # Print configuration\n')
        f.write('        print("\\n" + "="*60)\n')
        f.write('        print("EXPORT LOOP CONFIGURATION")\n')
        f.write('        print("="*60)\n')
        f.write('        print(f"Polling interval: {POLLING_INTERVAL_MINUTES} minutes")\n')
        f.write('        print(f"Timeout: {QUIT_AFTER_HOURS} hours with no activity")\n')
        f.write('        print(f"Total tables: {len(METADATA_JSON.get(\'tables\', []))}")\n')
        f.write('        print("="*60)\n')
        f.write('\n')
        f.write('        # Initialize and run the export loop\n')
        f.write('        metadata = ExportMetadata(METADATA_JSON)\n')
        f.write('        loop = ExportLoop(\n')
        f.write('            session,\n')
        f.write('            metadata,\n')
        f.write('            POLLING_INTERVAL_MINUTES,\n')
        f.write('            QUIT_AFTER_HOURS\n')
        f.write('        )\n')
        f.write('        loop.run()\n')
        f.write('\n')
        f.write('        print("\\n✓ Export loop completed successfully!")\n')
        f.write('\n')
        f.write('    except Exception as e:\n')
        f.write('        print(f"\\n✗ Fatal error in export loop: {str(e)}")\n')
        f.write('        print(f"Please check your configuration and try again")\n')
        f.write('        raise\n')
        f.write('\n')
        f.write('\n')
        f.write('# Call main() to start the export loop\n')
        f.write('main()\n')


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
    
    print(f"\n4. Writing Snowflake notebook cell 2 script...")
    output_file = Path(__file__).parent.parent / "snowflake" / "cell2_snowflake_export_notebook.py"
    write_cell2_script(output_file, metadata_tables)
    
    print(f"\n✓ Script generated successfully!")
    print(f"  Output: {output_file}")
    print(f"\n📋 Next steps:")
    print(f"  1. Open {output_file}")
    print(f"  2. Copy the entire contents")
    print(f"  3. Paste into CELL 2 of your Snowflake notebook (after cell1_snowflake_export_classes.py)")
    print(f"  4. Run Cell 1 first, then run Cell 2")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
