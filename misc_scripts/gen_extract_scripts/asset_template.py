"""
Asset Template for IDROutputter Classes
========================================

This module provides a template function for generating IDROutputter subclass scripts.
It accepts template values and returns the complete Python script content.

Usage:
    from asset_template import generate_idr_outputter_script
    
    values = {
        'table_name': 'V2_MDCR_PRVDR',
        'database': 'IDRC_PRD',
        'schema': 'CMS_VDM_VIEW_MDCR_PRD',
        'table_type': 'VIEW',
        'column_count': 42,
        'original_pattern': '%PROVIDER%',
        'table_comment': 'Provider master table',  # Optional
        'class_name': 'V2MdcrPrvdrExporter',
        'file_name_stub': 'v2_mdcr_prvdr_idr_export',
        'select_query': 'SELECT col1, col2 FROM ...'
    }
    
    script_content = generate_idr_outputter_script(values)
"""

from typing import Dict, Any


def generate_idr_outputter_script(template_values: Dict[str, Any]) -> str:
    """
    Generate complete IDROutputter subclass script from template values.
    
    Args:
        template_values: Dictionary containing the following keys:
            - table_name (str): Name of the table/view
            - database (str): Database name
            - schema (str): Schema name
            - table_type (str): 'TABLE' or 'VIEW'
            - column_count (int): Number of columns
            - original_pattern (str): Search pattern used
            - class_name (str): CamelCase class name
            - file_name_stub (str): snake_case file stub
            - select_query (str): Complete SELECT query
            - table_comment (str, optional): Table-level comment from Snowflake
            
    Returns:
        Complete Python script content as string
    """
    # Extract required values
    table_name = template_values['table_name']
    database = template_values['database']
    schema = template_values['schema']
    table_type = template_values['table_type']
    column_count = template_values['column_count']
    original_pattern = template_values['original_pattern']
    class_name = template_values['class_name']
    file_name_stub = template_values['file_name_stub']
    select_query = template_values['select_query']
    
    # Optional table comment
    table_comment = template_values.get('table_comment')
    table_comment_section = ""
    if table_comment:
        table_comment_section = f"\nTable Comment: {table_comment}"
    
    return f'''"""
==========
{table_name} IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for {database}.{schema}.{table_name}

Table Type: {table_type}
Columns: {column_count}
Source Pattern: {original_pattern}{table_comment_section}

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = {class_name}()
    exporter.do_idr_output()
"""

# Import python packages
import pandas as pd
from datetime import datetime

# Import the IDROutputter base class
try:
    from IDROutputter import IDROutputter
except ImportError:
    print("Loading IDROutputter from previous cell or add proper import path")


class {class_name}(IDROutputter):
    """
    Exports {table_name} data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: {database}.{schema}.{table_name} ({table_type})
    Columns: {column_count}
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "{file_name_stub}"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for {table_name} export.
        
        Includes all {column_count} columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """{select_query}"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = {class_name}()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
'''
