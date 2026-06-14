"""
==========
PROVIDER_ENROLLMENT_HISTORY IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.PROVIDER_ENROLLMENT_HISTORY

Table Type: TABLE
Columns: 4
Source Pattern: %PROVIDER%

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = ProviderEnrollmentHistoryExporter()
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


class ProviderEnrollmentHistoryExporter(IDROutputter):
    """
    Exports PROVIDER_ENROLLMENT_HISTORY data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.PROVIDER_ENROLLMENT_HISTORY (TABLE)
    Columns: 4
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "provider_enrollment_history_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for PROVIDER_ENROLLMENT_HISTORY export.
        
        Includes all 4 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                ENROLLMENT_ID,
                PRVDR_NPI_NUM,
                ENROLLMENT_DATE,
                STATUS
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.PROVIDER_ENROLLMENT_HISTORY"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = ProviderEnrollmentHistoryExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
