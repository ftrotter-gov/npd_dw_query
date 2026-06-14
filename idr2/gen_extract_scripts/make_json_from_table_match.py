#!/usr/bin/env python3
"""
Snowflake Metadata Discovery Script
===================================

This script queries Snowflake's INFORMATION_SCHEMA to discover tables and views
matching a LIKE pattern, then generates a JSON file containing database, schema,
table/view names, and all column metadata.

Usage:
    Run this in a Snowflake notebook environment where you have an active session.
    
    python make_json_from_table_match.py --pattern '%PROVIDER%' --output metadata.json
    
Requirements:
    - Active Snowflake session
    - Access to INFORMATION_SCHEMA
    
Output JSON Structure:
    {
        "metadata": {
            "generated_timestamp": "2024-01-01T12:00:00",
            "search_pattern": "%PROVIDER%",
            "total_tables_found": 5
        },
        "tables": [
            {
                "database": "IDRC_PRD", 
                "schema": "CMS_VDM_VIEW_MDCR_PRD",
                "table_name": "V2_PROVIDER_DEMOGRAPHICS",
                "table_type": "VIEW",
                "columns": [
                    {
                        "column_name": "PRVDR_NPI_NUM",
                        "data_type": "VARCHAR",
                        "ordinal_position": 1,
                        "is_nullable": "YES",
                        "column_default": null,
                        "comment": "National Provider Identifier",
                        "character_maximum_length": 10,
                        "type_description": "VARCHAR(10)"
                    },
                    {
                        "column_name": "PRVDR_BALANCE",
                        "data_type": "DECIMAL", 
                        "ordinal_position": 2,
                        "is_nullable": "YES",
                        "column_default": "0.00",
                        "comment": "Provider account balance",
                        "numeric_precision": 15,
                        "numeric_scale": 2,
                        "type_description": "DECIMAL(15,2)"
                    }
                ]
            }
        ],
        "table_comments": {
            "IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PROVIDER_DEMOGRAPHICS": "Provider demographic information including identifiers and contact details",
            "IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PROVIDER_SPECIALTIES": "Provider specialty and taxonomy information"
        }
    }
"""

import json
import argparse
from datetime import datetime
from typing import Dict, List, Any

def discover_tables_and_columns(*, search_pattern: str, database_name: str | None = None) -> Dict[str, Any]:
    """
    Discovers tables/views matching the search pattern and their column metadata.
    
    Args:
        search_pattern: LIKE pattern for table matching (e.g., '%PROVIDER%')
        database_name: Optional database name to search in. If None, uses current database context.
        
    Returns:
        Dictionary containing metadata and table information
    """
    try:
        from snowflake.snowpark.context import get_active_session  # type: ignore
        session = get_active_session()
        
        # Get current database if none specified
        if database_name is None:
            current_db_result = session.sql("SELECT CURRENT_DATABASE()").collect()
            if current_db_result and current_db_result[0][0]:
                database_name = current_db_result[0][0]
                print(f"Using current database: {database_name}")
            else:
                raise ValueError("No database specified and no current database is set. "
                               "Please specify database_name parameter or use USE DATABASE first.")
        else:
            print(f"Searching in specified database: {database_name}")
        
        print(f"Searching for tables matching pattern: {search_pattern}")
        
        # Query to find matching tables/views with case-insensitive LIKE in specified database
        # Include table comments
        tables_query = f"""
            SELECT DISTINCT
                table_catalog AS database_name,
                table_schema AS schema_name, 
                table_name,
                table_type,
                comment AS table_comment
            FROM {database_name}.information_schema.tables
            WHERE UPPER(table_name) LIKE UPPER('{search_pattern}')
            ORDER BY database_name, schema_name, table_name
        """
        
        print(f"Executing query: {tables_query}")
        tables_result = session.sql(tables_query).collect()
        
        if not tables_result:
            print(f"No tables found matching pattern: {search_pattern}")
            return {
                "metadata": {
                    "generated_timestamp": datetime.now().isoformat(),
                    "search_pattern": search_pattern,
                    "total_tables_found": 0
                },
                "tables": []
            }
        
        print(f"Found {len(tables_result)} tables/views matching the pattern")
        
        tables_data = []
        table_comments = {}  # Store table-level comments separately
        
        for table_row in tables_result:
            database_name = table_row[0]
            schema_name = table_row[1]
            table_name = table_row[2]
            table_type = table_row[3]
            table_comment = table_row[4] if len(table_row) > 4 and table_row[4] else None
            
            # Store table comment in separate dictionary
            full_table_name = f"{database_name}.{schema_name}.{table_name}"
            if table_comment:
                table_comments[full_table_name] = table_comment
            
            print(f"Processing: {database_name}.{schema_name}.{table_name}")
            
            # Query columns for this specific table, ordered by position in Snowflake
            # Include additional metadata like comments, character limits, numeric precision, etc.
            columns_query = f"""
                SELECT 
                    column_name,
                    data_type,
                    ordinal_position,
                    is_nullable,
                    column_default,
                    comment,
                    character_maximum_length,
                    numeric_precision,
                    numeric_scale
                FROM {database_name}.information_schema.columns
                WHERE table_catalog = '{database_name}'
                    AND table_schema = '{schema_name}'
                    AND table_name = '{table_name}'
                ORDER BY ordinal_position
            """
            
            columns_result = session.sql(columns_query).collect()
            
            columns_data = []
            for col_row in columns_result:
                # Build comprehensive column metadata
                column_info = {
                    "column_name": col_row[0],
                    "data_type": col_row[1], 
                    "ordinal_position": col_row[2],
                    "is_nullable": col_row[3],
                    "column_default": col_row[4] if col_row[4] else None,
                    "comment": col_row[5] if col_row[5] else None,
                }
                
                # Add type-specific details
                if col_row[6]:  # character_maximum_length
                    column_info["character_maximum_length"] = col_row[6]
                if col_row[7]:  # numeric_precision
                    column_info["numeric_precision"] = col_row[7]
                if col_row[8]:  # numeric_scale
                    column_info["numeric_scale"] = col_row[8]
                
                # Create a more descriptive type description
                data_type = col_row[1]
                type_description = data_type
                if col_row[6]:  # VARCHAR, CHAR, etc.
                    type_description = f"{data_type}({col_row[6]})"
                elif col_row[7]:  # NUMERIC, DECIMAL, etc.
                    if col_row[8] and col_row[8] > 0:
                        type_description = f"{data_type}({col_row[7]},{col_row[8]})"
                    else:
                        type_description = f"{data_type}({col_row[7]})"
                
                column_info["type_description"] = type_description
                columns_data.append(column_info)
            
            table_info = {
                "database": database_name,
                "schema": schema_name,
                "table_name": table_name,
                "table_type": table_type,
                "columns": columns_data
            }
            
            tables_data.append(table_info)
            print(f"  - Found {len(columns_data)} columns")
        
        result = {
            "metadata": {
                "generated_timestamp": datetime.now().isoformat(),
                "search_pattern": search_pattern,
                "total_tables_found": len(tables_data)
            },
            "tables": tables_data,
            "table_comments": table_comments
        }
        
        print(f"Discovery complete. Found {len(tables_data)} tables/views total.")
        if table_comments:
            print(f"Table comments found: {len(table_comments)}")
        return result
        
    except Exception as e:
        print(f"make_json_from_table_match Error: Failed to discover table metadata")
        print(f"Error details: {str(e)}")
        print(f"Make sure you have an active Snowflake session and access to INFORMATION_SCHEMA")
        raise


def save_metadata_json(*, metadata: Dict[str, Any], output_file: str, print_inline: bool = False) -> None:
    """
    Saves metadata dictionary to JSON file with pretty formatting and optionally prints inline.
    
    Args:
        metadata: The metadata dictionary to save
        output_file: Path to output JSON file
        print_inline: Whether to print the JSON content inline to console
    """
    try:
        with open(output_file, 'w') as f:
            json.dump(metadata, f, indent=2, sort_keys=False)
        print(f"Metadata saved to: {output_file}")
        
        # Print JSON inline if requested
        if print_inline:
            print(f"\nJSON OUTPUT:")
            print(f"============")
            print(json.dumps(metadata, indent=2, sort_keys=False))
            print(f"============")
        
        # Print summary
        table_count = metadata["metadata"]["total_tables_found"]
        total_columns = sum(len(table["columns"]) for table in metadata["tables"])
        
        print(f"\nSUMMARY:")
        print(f"========")
        print(f"Tables/Views Found: {table_count}")
        print(f"Total Columns: {total_columns}")
        print(f"Search Pattern: {metadata['metadata']['search_pattern']}")
        print(f"Generated: {metadata['metadata']['generated_timestamp']}")
        
        if table_count > 0:
            print(f"\nTables Found:")
            for table in metadata["tables"]:
                print(f"  - {table['database']}.{table['schema']}.{table['table_name']} ({table['table_type']}) - {len(table['columns'])} columns")
        
    except Exception as e:
        print(f"make_json_from_table_match Error: Failed to save JSON file")
        print(f"Error details: {str(e)}")
        raise


def run_metadata_discovery(*, search_pattern: str, output_file: str, database_name: str | None = None, print_inline: bool = False) -> Dict[str, Any]:
    """
    Main function for notebook usage.
    
    Args:
        search_pattern: LIKE pattern for table matching (e.g., '%PROVIDER%')
        output_file: Path to output JSON file
        database_name: Optional database name to search in. If None, uses current database context.
        print_inline: Whether to print the JSON content inline to console
        
    Returns:
        Dictionary containing metadata and table information
    """
    print("Snowflake Metadata Discovery")
    print("===========================")
    print(f"Search Pattern: {search_pattern}")
    print(f"Output File: {output_file}")
    if database_name:
        print(f"Database: {database_name}")
    else:
        print("Database: [Using current database context]")
    print(f"Print Inline: {'Yes' if print_inline else 'No'}")
    print("")
    
    try:
        # Discover tables and columns
        metadata = discover_tables_and_columns(search_pattern=search_pattern, database_name=database_name)
        
        # Save to JSON file and optionally print inline
        save_metadata_json(metadata=metadata, output_file=output_file, print_inline=print_inline)
        
        print(f"\nSuccess! Metadata discovery completed.")
        return metadata
        
    except Exception as e:
        print(f"\nFailed to complete metadata discovery: {str(e)}")
        raise


def main():
    """Main function for CLI usage"""
    parser = argparse.ArgumentParser(
        description="Discover Snowflake table metadata matching a LIKE pattern",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python make_json_from_table_match.py --pattern '%PROVIDER%' --output provider_metadata.json --database IDRC_PRD
    python make_json_from_table_match.py --pattern '%MEDICAID%' --output medicaid_metadata.json
    python make_json_from_table_match.py --pattern 'V2_%' --output v2_tables.json --database ANALYTICS_DB
        """
    )
    
    parser.add_argument(
        '--pattern', 
        required=True,
        help="LIKE pattern for table matching (e.g., '%%PROVIDER%%'). Case-insensitive."
    )
    
    parser.add_argument(
        '--output',
        required=True, 
        help="Output JSON file path"
    )
    
    parser.add_argument(
        '--database',
        help="Database name to search in. If not specified, uses current database context."
    )
    
    parser.add_argument(
        '--print-inline',
        action='store_true',
        help="Print JSON output inline to console in addition to saving to file."
    )
    
    args = parser.parse_args()
    
    try:
        # Run the metadata discovery
        metadata = run_metadata_discovery(
            search_pattern=args.pattern, 
            output_file=args.output,
            database_name=args.database,
            print_inline=args.print_inline
        )
        
    except Exception as e:
        print(f"\nFailed to complete metadata discovery: {str(e)}")
        exit(1)


# Example usage in notebook:
# 
# Set your parameters here:
# search_pattern = '%PROVIDER%'
# output_file = 'provider_metadata.json'
# database_name = 'IDRC_PRD'  # Optional
#
# Run the discovery:
# metadata = run_metadata_discovery(
#     search_pattern=search_pattern, 
#     output_file=output_file,
#     database_name=database_name,
#     print_inline=True
# )

# see the dw_notebook_integrations/misc_scripts/gen_extract_scripts/make_extract_scripts_from_json.py for the specific exports we have made. 
