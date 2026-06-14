"""
Metadata Generator for Parallel Snowflake Export System

Reads list_of_tables_to_download.csv and generates export_metadata.json
that describes all tables to export, including their columns and file naming.

Usage:
    python3 metadata_generator.py
    # Reads: list_of_tables_to_download.csv
    # Writes: export_metadata.json
"""

import json
import csv
import sys
from pathlib import Path
from datetime import datetime


class MetadataGenerator:
    """Generates metadata JSON from a list of tables to download."""
    
    def __init__(self, csv_file="list_of_tables_to_download.csv"):
        """
        Initialize the metadata generator.
        
        Args:
            csv_file: Path to CSV file containing tables to download
        """
        self.csv_file = Path(csv_file)
        self.metadata = {
            "generated": datetime.now().isoformat(),
            "tables": []
        }
    
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
    
    def build_select_query(self, table_info):
        """
        Build a SELECT query for the table (all columns, no WHERE clause).
        
        This follows the IDROutputter pattern of selecting all columns
        from the table without any filtering.
        
        Args:
            table_info: Dict with table information
        
        Returns:
            str: SELECT query string
        """
        full_name = table_info['full_table_name']
        # Build a SELECT * query - in production, column list would come from Snowflake
        return f"SELECT * FROM {full_name}"
    
    def generate_table_metadata(self, full_table_name):
        """
        Generate metadata entry for a single table.
        
        Args:
            full_table_name: Fully qualified table name
        
        Returns:
            dict: Table metadata entry
        """
        table_info = self.parse_table_name(full_table_name)
        
        return {
            'database': table_info['database'],
            'schema': table_info['schema'],
            'table': table_info['table'],
            'full_table_name': table_info['full_table_name'],
            'columns': [],  # Would be populated by querying Snowflake
            'file_name_stub': self.generate_file_name_stub(table_info),
            'version_number': 'v01',
            'select_query': self.build_select_query(table_info)
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
        generator.generate_metadata()
        generator.write_metadata(str(output_file))
        
        print("\n" + "=" * 60)
        print("Metadata generation complete!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        print("\nUsage: python3 metadata_generator.py")
        print("  Expects: list_of_tables_to_download.csv in same directory")
        print("  Creates: export_metadata.json in same directory")
        return 1


if __name__ == "__main__":
    sys.exit(main())
