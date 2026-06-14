"""
==========
MULTILINE_COMMENT_TABLE IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for TEST_DB.TEST_SCHEMA.MULTILINE_COMMENT_TABLE

Table Type: TABLE
Columns: 2
Source Pattern: %MULTILINE%

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = MultilineCommentTableExporter()
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


class MultilineCommentTableExporter(IDROutputter):
    """
    Exports MULTILINE_COMMENT_TABLE data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: TEST_DB.TEST_SCHEMA.MULTILINE_COMMENT_TABLE (TABLE)
    Columns: 2
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "multiline_comment_table_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for MULTILINE_COMMENT_TABLE export.
        
        Includes all 2 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                FIELD_WITH_MULTILINE_COMMENT, -- VARCHAR(100): This is a comment that spans multiple lines with various formatting issues and extra spaces
                NORMAL_FIELD -- NUMBER: Single line comment works fine
            FROM TEST_DB.TEST_SCHEMA.MULTILINE_COMMENT_TABLE"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = MultilineCommentTableExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
