#!/usr/bin/env python3
"""
Entity Column Search and SQL Generator
========================================

This script searches for entity-related columns in Medicare Provider data and generates
CREATE TABLE statements focusing on key identifiers:

* TINs (including EIN, SSN and ITIN)
* PECOS Associate Control ID (PECOS_ASCT_CNTL_ID) / PAC ID  
* Enrollment numbers
* NPIs for both organizations and persons
* Part B assignment

The script reads from the JSON documentation cache and produces SQL DDL statements
with only the relevant columns and their comments.

Usage:
    python search_for_entity.py --input json_documentation_cache/mdcr_prvdr_columns.json --output entity_tables.sql
    
Original Instructions:
======================
I am interested in understanding the relationships between several types of columns: 

* TINs (including EIN, SSN and ITIN)
* PECOS Associate Control ID PECOS_ASCT_CNTL_ID PAC ID
* Enrollment numbers
* NPIs for both organizations and persons

I would also like to understand the phenomeon of Part B assignment. 

First, read through he atastructure found in dw_notebook_integrations/misc_scripts/gen_extract_scripts/json_documentation_cache/mdcr_prvdr_columns.json
And determine a list of which typical column names related to these data elements. 

Then create an extraction script that creates a simple file of CREATE TABLE statements for all of the tables that have these relevant columns and then just leave out all of the other columns. 
Be sure to include the column comments. 

Store the code to parse dw_notebook_integrations/misc_scripts/gen_extract_scripts/json_documentation_cache/mdcr_prvdr_columns.json and produce the SQL file in this program

Do not overwrite these instructions as you code. 

"""

import json
import argparse
import re
import sys
from typing import Dict, List, Set, Any
from pathlib import Path


# Define patterns for identifying relevant entity-related columns
ENTITY_COLUMN_PATTERNS = {
    'tin': [
        r'.*TIN(?!_TYPE).*',  # Tax Identification Number (but not TIN_TYPE)
        r'.*EMPLR_ID(?!_TYPE).*',  # Employer ID (EIN, SSN, ITIN) (but not type)
    ],
    'pac_id': [
        r'.*PAC_ID$',  # PECOS Associate Control ID (exact match at end)
        r'.*PECOS_ASCT_CNTL_ID$',  # Full PECOS Associate Control ID name
    ],
    'enrollment': [
        r'.*ENRLMT_ID$',  # Enrollment ID (must end with _ID)
        r'.*ENRLMT_NUM$',  # Enrollment Number (must end with _NUM)
    ],
    'npi': [
        r'.*NPI(?:_NUM)?$',  # NPI or NPI_NUM at end of string
    ],
    'assignment': [
        r'.*ASSGN.*',  # Assignment-related
        r'.*PART.*B.*ASSGN.*',  # Part B assignment
        r'.*ASSIGN.*',  # Alternative spelling
    ],
}

# Additional columns to always include for context
# NOTE: Keeping this minimal - only table/column name columns for identifying the table
CONTEXT_COLUMNS = [
    r'.*TABLE.*NAME$',  # Table name only
]


def matches_pattern(column_name: str, patterns: List[str]) -> bool:
    """Check if a column name matches any of the given regex patterns."""
    for pattern in patterns:
        if re.match(pattern, column_name, re.IGNORECASE):
            return True
    return False


def is_relevant_column(column_name: str) -> tuple[bool, List[str]]:
    """
    Determine if a column is relevant based on entity patterns.
    
    Returns:
        Tuple of (is_relevant, list of matching categories)
    """
    matching_categories = []
    
    # Check each category
    for category, patterns in ENTITY_COLUMN_PATTERNS.items():
        if matches_pattern(column_name, patterns):
            matching_categories.append(category)
    
    # Check context columns
    if matches_pattern(column_name, CONTEXT_COLUMNS):
        matching_categories.append('context')
    
    return len(matching_categories) > 0, matching_categories


def extract_relevant_columns(table_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract only relevant columns from a table's column list."""
    relevant_columns = []
    
    for column in table_data.get('columns', []):
        column_name = column.get('column_name', '')
        is_relevant, categories = is_relevant_column(column_name)
        
        if is_relevant:
            column_info = column.copy()
            column_info['_relevance_categories'] = categories
            relevant_columns.append(column_info)
    
    return relevant_columns


def format_column_comment(comment: str) -> str:
    """Format a column comment for SQL, escaping single quotes."""
    if not comment:
        return ''
    # Escape single quotes by doubling them
    return comment.replace("'", "''")


def generate_create_table_sql(table_data: Dict[str, Any], relevant_columns: List[Dict[str, Any]], table_comment: str = None) -> str:
    """Generate a CREATE TABLE statement with only relevant columns."""
    
    if not relevant_columns:
        return ''
    
    database = table_data.get('database', 'UNKNOWN_DB')
    schema = table_data.get('schema', 'UNKNOWN_SCHEMA')
    table_name = table_data.get('table_name', 'UNKNOWN_TABLE')
    table_type = table_data.get('table_type', 'TABLE')
    
    full_table_name = f"{database}.{schema}.{table_name}"
    
    sql_lines = []
    sql_lines.append(f"-- ========================================")
    sql_lines.append(f"-- Table: {full_table_name}")
    sql_lines.append(f"-- Type: {table_type}")
    sql_lines.append(f"-- Relevant Columns: {len(relevant_columns)} of {len(table_data.get('columns', []))}")
    if table_comment:
        sql_lines.append(f"-- Table Comment: {table_comment}")
    sql_lines.append(f"-- ========================================")
    sql_lines.append(f"")
    sql_lines.append(f"CREATE TABLE IF NOT EXISTS {full_table_name} (")
    
    # Generate column definitions
    column_defs = []
    for i, column in enumerate(relevant_columns):
        col_name = column.get('column_name', 'UNKNOWN')
        data_type = column.get('type_description', column.get('data_type', 'VARCHAR'))
        is_nullable = column.get('is_nullable', 'YES')
        comment = column.get('comment', '')
        categories = column.get('_relevance_categories', [])
        
        # Build column definition
        col_def = f"    {col_name} {data_type}"
        
        if is_nullable == 'NO':
            col_def += " NOT NULL"
        
        # Add comma if not last column
        if i < len(relevant_columns) - 1:
            col_def += ","
        
        column_defs.append(col_def)
        
        # Add comment as a SQL comment
        if comment:
            formatted_comment = format_column_comment(comment)
            column_defs.append(f"    -- {col_name}: {formatted_comment[:100]}{'...' if len(formatted_comment) > 100 else ''}")
            column_defs.append(f"    -- Categories: {', '.join(categories)}")
    
    sql_lines.extend(column_defs)
    sql_lines.append(");")
    sql_lines.append("")
    
    # Add ALTER TABLE statements for column comments (Snowflake syntax)
    for column in relevant_columns:
        col_name = column.get('column_name', 'UNKNOWN')
        comment = column.get('comment', '')
        if comment:
            formatted_comment = format_column_comment(comment)
            sql_lines.append(f"COMMENT ON COLUMN {full_table_name}.{col_name} IS '{formatted_comment}';")
    
    sql_lines.append("")
    sql_lines.append("")
    
    return '\n'.join(sql_lines)


def analyze_json_and_generate_sql(input_file: str, output_file: str = None, min_relevant_columns: int = 1):
    """
    Main function to analyze JSON and generate SQL statements.
    
    Args:
        input_file: Path to input JSON file
        output_file: Path to output SQL file (if None, prints to stdout)
        min_relevant_columns: Minimum number of relevant columns for a table to be included
    """
    
    print(f"Reading metadata from: {input_file}")
    
    # Read JSON file
    with open(input_file, 'r') as f:
        metadata = json.load(f)
    
    tables = metadata.get('tables', [])
    table_comments = metadata.get('table_comments', {})
    total_tables = len(tables)
    
    print(f"Found {total_tables} tables in metadata")
    if table_comments:
        print(f"Found {len(table_comments)} table comments")
    print(f"Analyzing for entity-related columns...")
    print("")
    
    # Statistics
    tables_with_relevant_cols = 0
    total_relevant_cols = 0
    category_counts = {cat: 0 for cat in ENTITY_COLUMN_PATTERNS.keys()}
    category_counts['context'] = 0
    
    # Generate SQL
    sql_output = []
    sql_output.append("-- ========================================")
    sql_output.append("-- Entity Column Extraction")
    sql_output.append("-- ========================================")
    sql_output.append("-- Generated from Medicare Provider metadata")
    sql_output.append(f"-- Source: {input_file}")
    sql_output.append("-- ")
    sql_output.append("-- Focus Areas:")
    sql_output.append("--   * TINs (EIN, SSN, ITIN)")
    sql_output.append("--   * PECOS Associate Control ID (PAC ID)")
    sql_output.append("--   * Enrollment Numbers")
    sql_output.append("--   * NPIs (National Provider Identifier)")
    sql_output.append("--   * Part B Assignment")
    sql_output.append("-- ========================================")
    sql_output.append("")
    sql_output.append("")
    
    # Process each table
    for table in tables:
        table_name = table.get('table_name', 'UNKNOWN')
        relevant_columns = extract_relevant_columns(table)
        
        if len(relevant_columns) >= min_relevant_columns:
            # Skip tables that only have PRVDR_ENRLMT_ID and PRVDR_PAC_ID
            column_names = {col.get('column_name', '') for col in relevant_columns}
            if column_names == {'PRVDR_ENRLMT_ID', 'PRVDR_PAC_ID'}:
                print(f"⊘ {table_name}: {len(relevant_columns)} relevant columns (skipping - only link columns)")
                continue
            
            tables_with_relevant_cols += 1
            total_relevant_cols += len(relevant_columns)
            
            # Count categories
            for col in relevant_columns:
                for cat in col.get('_relevance_categories', []):
                    if cat in category_counts:
                        category_counts[cat] += 1
            
            # Get table comment if available
            database = table.get('database', '')
            schema = table.get('schema', '')
            full_table_name = f"{database}.{schema}.{table_name}"
            table_comment = table_comments.get(full_table_name)
            
            # Generate SQL for this table
            sql = generate_create_table_sql(table, relevant_columns, table_comment)
            sql_output.append(sql)
            
            print(f"✓ {table_name}: {len(relevant_columns)} relevant columns")
    
    # Print statistics
    print("")
    print("=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total tables analyzed:           {total_tables}")
    print(f"Tables with relevant columns:    {tables_with_relevant_cols}")
    print(f"Total relevant columns found:    {total_relevant_cols}")
    print("")
    print("Columns by Category:")
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  {category:20s}: {count:4d}")
    print("=" * 60)
    
    # Write output
    final_sql = '\n'.join(sql_output)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(final_sql)
        print(f"\nSQL written to: {output_file}")
    else:
        print("\n" + final_sql)
    
    return tables_with_relevant_cols, total_relevant_cols


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description='Extract entity-related columns from Medicare Provider metadata and generate SQL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python search_for_entity.py json_documentation_cache/mdcr_prvdr_columns.json
    python search_for_entity.py /path/to/metadata.json
        """
    )
    
    parser.add_argument(
        'input_json',
        help='Input JSON file with table metadata'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    script_dir = Path(__file__).parent
    input_path = Path(args.input_json)
    
    # If relative path, resolve relative to script directory
    if not input_path.is_absolute():
        input_path = script_dir / input_path
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1
    
    try:
        # Always output to stdout (None for output_file)
        analyze_json_and_generate_sql(
            str(input_path),
            output_file=None,
            min_relevant_columns=1
        )
        return 0
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
