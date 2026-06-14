"""
Metadata Generator for Parallel Snowflake Export System

Reads list_of_tables_to_download.csv and existing cached metadata JSON files
from misc_scripts/gen_extract_scripts/json_documentation_cache/ and generates
consolidated export_metadata.json with explicit columns and SELECT statements.

This leverages the existing metadata infrastructure rather than querying Snowflake.

Usage:
    python3 metadata_generator.py
    # Reads: list_of_tables_to_download.csv + existing JSON cache
    # Writes: export_metadata.json with explicit columns
"""

import json
import csv
import sys
from pathlib import Path
from datetime import datetime
import os


class MetadataGenerator:
    """Generates metadata JSON by leveraging existing cached JSON metadata."""
    
    def __init__(self, csv_file="list_of_tables_to_download.csv", json_cache_dir=None):
        """
        Initialize the metadata generator.
        
        Args:
            csv_file: Path to CSV file containing tables to download
            json_cache_dir: Path to cached JSON metadata directory
        """
        self.csv_file = Path(csv_file)
        
        # Find the JSON cache directory if not provided
        if json_cache_dir is None:
            # Try to find it relative to this script
            script_dir = Path(__file__).parent
            project_dir = script_dir.parent
            json_cache_dir = project_dir / "misc_scripts" / "gen_extract_scripts" / "json_documentation_cache"
        
        self.json_cache_dir = Path(json_cache_dir)
        self.cached_metadata = {}  # Will hold loaded JSON files
        self.metadata = {
            "generated": datetime.now().isoformat(),
            "source": "Consolidated from existing cached metadata",
            "tables": []
        }
    
    def load_cached_json_files(self):
        """
        Load all cached JSON metadata files from the cache directory.
        
        Returns:
            dict: Mapping of cache file names to their loaded data
        """
        if not self.json_cache_dir.exists():
            print(f"Warning: JSON cache directory not found: {self.json_cache_dir}")
            return {}
        
        cached = {}
        for json_file in self.json_cache_dir.glob("*.json"):
            if json_file.name.startswith("test_") or json_file.name.startswith("sample_"):
                continue
            
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    cached[json_file.stem] = data
                    print(f"Loaded cached metadata: {json_file.name}")
            except Exception as e:
                print(f"Warning: Could not load {json_file.name}: {e}")
        
        self.cached_metadata = cached
        return cached
    
    def read_table_list(self):
        """
        Read table list from CSV file.
        
        Returns:
            list: List of fully qualified table names (database.schema.table)
        """
        if not self.csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_file}")
        
        tables = []
        try:
            with open(self.csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    table_name = row.get('table_to_download', '').strip()
                    if table_name:
                        tables.append(table_name)
            
            print(f"Read {len(tables)} tables from {self.csv_file}")
            return tables
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            raise
    
    def parse_table_name(self, full_table_name):
        """
        Parse fully qualified table name into components.
        
        Args:
            full_table_name: String in format "database.schema.table"
        
        Returns:
            dict: Contains 'database', 'schema', 'table', and 'full_table_name'
        """
        parts = full_table_name.split('.')
        if len(parts) != 3:
            raise ValueError(f"Invalid table name format: {full_table_name}. Expected 'database.schema.table'")
        
        return {
            'database': parts[0],
            'schema': parts[1],
            'table': parts[2],
            'full_table_name': full_table_name
        }
    
    def generate_file_name_stub(self, table_info):
        """
        Generate file name stub from table information.
        
        Converts table name to lowercase with underscores.
        Example: V2_MDCR_PRVDR -> v2_mdcr_prvdr_idr_export
        
        Args:
            table_info: Dict with table information
        
        Returns:
            str: File name stub for this table
        """
        table_name = table_info['table'].lower()
        return f"{table_name}_idr_export"
    
    def find_table_in_cached_metadata(self, database, schema, table):
        """
        Find a table in the cached JSON metadata files.
        
        Args:
            database: Database name
            schema: Schema name
            table: Table name
        
        Returns:
            dict: Table info from cached metadata, or None if not found
        """
        for cache_name, cache_data in self.cached_metadata.items():
            if 'tables' not in cache_data:
                continue
            
            for table_info in cache_data['tables']:
                if (table_info.get('database') == database and
                    table_info.get('schema') == schema and
                    table_info.get('table_name') == table):
                    return table_info
        
        return None
    
    def build_select_query_from_columns(self, full_table_name, columns):
        """
        Build a SELECT query with explicit column names.
        
        Args:
            full_table_name: Fully qualified table name
            columns: List of column dicts with 'column_name' key
        
        Returns:
            str: SELECT query with explicit columns
        """
        if not columns:
            return f"SELECT * FROM {full_table_name}"
        
        # Extract column names in order
        column_names = [col.get('column_name') for col in columns if col.get('column_name')]
        
        if not column_names:
            return f"SELECT * FROM {full_table_name}"
        
        # Build SELECT statement with proper indentation
        column_str = ",\n                ".join(column_names)
        
        return f"""SELECT
                {column_str}
            FROM {full_table_name}"""
    
    def build_select_query(self, table_info):
        """
        Build a SELECT query for the table with explicit columns.
        
        First tries to find the table in cached metadata.
        Falls back to SELECT * if not found.
        
        Args:
            table_info: Dict with table information
        
        Returns:
            tuple: (select_query: str, columns: list)
        """
        full_name = table_info['full_table_name']
        
        # Try to find table in cached metadata
        cached_table = self.find_table_in_cached_metadata(
            table_info['database'],
            table_info['schema'],
            table_info['table']
        )
        
        if cached_table and 'columns' in cached_table:
            columns = cached_table['columns']
            select_query = self.build_select_query_from_columns(full_name, columns)
            return select_query, columns
        else:
            # Fallback to SELECT * if not in cache
            return f"SELECT * FROM {full_name}", []
    
    def generate_table_metadata(self, full_table_name):
        """
        Generate metadata entry for a single table.
        
        Args:
            full_table_name: Fully qualified table name
        
        Returns:
            dict: Table metadata entry
        """
        table_info = self.parse_table_name(full_table_name)
        
        # Build select query and get columns from cached metadata
        select_query, columns = self.build_select_query(table_info)
        
        return {
            'database': table_info['database'],
            'schema': table_info['schema'],
            'table': table_info['table'],
            'full_table_name': table_info['full_table_name'],
            'columns': columns,
            'file_name_stub': self.generate_file_name_stub(table_info),
            'version_number': 'v01',
            'select_query': select_query
        }
    
    def generate_metadata(self):
        """
        Generate complete metadata for all tables.
        
        Returns:
            dict: Complete metadata structure
        """
        tables = self.read_table_list()
        
        for table_name in tables:
            try:
                table_metadata = self.generate_table_metadata(table_name)
                self.metadata['tables'].append(table_metadata)
                print(f"  Generated metadata for: {table_name}")
            except Exception as e:
                print(f"  Error generating metadata for {table_name}: {e}")
                continue
        
        print(f"\nGenerated metadata for {len(self.metadata['tables'])} tables")
        return self.metadata
    
    def write_metadata(self, output_file="export_metadata.json"):
        """
        Write metadata to JSON file.
        
        Args:
            output_file: Path to output JSON file
        """
        output_path = Path(output_file)
        try:
            with open(output_path, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            print(f"Metadata written to: {output_path}")
            print(f"Total tables: {len(self.metadata['tables'])}")
        except Exception as e:
            print(f"Error writing metadata file: {e}")
            raise


def main():
    """Main entry point for the metadata generator."""
    try:
        # Get the directory where this script is located
        script_dir = Path(__file__).parent
        
        # Use files in the same directory
        csv_file = script_dir / "list_of_tables_to_download.csv"
        output_file = script_dir / "export_metadata.json"
        
        print("=" * 60)
        print("Snowflake IDR Metadata Generator")
        print("=" * 60)
        print(f"Reading from: {csv_file}")
        print(f"Writing to: {output_file}\n")
        
        generator = MetadataGenerator(str(csv_file))
        
        # Load cached metadata from existing JSON files
        print("Loading cached metadata from misc_scripts/gen_extract_scripts/json_documentation_cache/...")
        generator.load_cached_json_files()
        print()
        
        # Generate and write metadata
        generator.generate_metadata()
        generator.write_metadata(str(output_file))
        
        print("\n" + "=" * 60)
        print("✓ Metadata generation complete!")
        print("=" * 60)
        print(f"\nMetadata with explicit columns written to: {output_file}")
        print("This metadata includes SELECT statements with all columns explicitly listed.")
        return 0
        
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        print("\nUsage: python3 metadata_generator.py")
        print("  Expects: list_of_tables_to_download.csv in same directory")
        print("  Expects: ../misc_scripts/gen_extract_scripts/json_documentation_cache/ with cached metadata")
        print("  Creates: export_metadata.json in same directory")
        return 1


if __name__ == "__main__":
    sys.exit(main())
