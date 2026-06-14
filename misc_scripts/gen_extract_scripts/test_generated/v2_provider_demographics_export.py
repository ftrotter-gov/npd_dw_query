"""
==========
V2_PROVIDER_DEMOGRAPHICS IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PROVIDER_DEMOGRAPHICS

Table Type: VIEW
Columns: 5
Source Pattern: %PROVIDER%

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2ProviderDemographicsExporter()
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


class V2ProviderDemographicsExporter(IDROutputter):
    """
    Exports V2_PROVIDER_DEMOGRAPHICS data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PROVIDER_DEMOGRAPHICS (VIEW)
    Columns: 5
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_provider_demographics_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_PROVIDER_DEMOGRAPHICS export.
        
        Includes all 5 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_NPI_NUM,
                PRVDR_ENT_TYPE_CD,
                PRVDR_CRTFCTN_DT,
                PRVDR_1ST_NAME,
                PRVDR_LAST_NAME
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PROVIDER_DEMOGRAPHICS"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2ProviderDemographicsExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
