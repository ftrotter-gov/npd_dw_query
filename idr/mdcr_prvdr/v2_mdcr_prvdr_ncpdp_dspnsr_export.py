"""
==========
V2_MDCR_PRVDR_NCPDP_DSPNSR IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_DSPNSR

Table Type: VIEW
Columns: 4
Source Pattern: %mdcr_prvdr%
Table Comment: NCPDP DISPENSER INFORMATION BASED ON A PROVIDERS TAXONOMY.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrNcpdpDspnsrExporter()
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


class V2MdcrPrvdrNcpdpDspnsrExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_NCPDP_DSPNSR data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_DSPNSR (VIEW)
    Columns: 4
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_ncpdp_dspnsr_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_NCPDP_DSPNSR export.
        
        Includes all 4 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_NCPDP_ID, -- TEXT(7) | NOT NULL | THE PROVIDERS NCPDP NUMBER.
                PRVDR_NCPDP_TXNMY_CD, -- TEXT(10) | NOT NULL | A CODE IDENTIFYING THE TYPE, CLASSIFICATION, AND/OR SPECIALIZATION OF A PROVIDER. FOR EXAMPLE: 207R00000X = INTERNAL MEDICINE 3416A0800X = AMBULANCE AIR TRANSPORT REFERENCE TABLE: PRVDR_NCPDP_TXNMY_CD
                PRVDR_NCPDP_DSPNSR_TYPE_CD, -- TEXT(2) | NULL | THIS FIELD CONTAINS THE PROVIDERÒ² DISPENSER TYPE CODE. PRIMARY DISPENSER TYPE CANNOT BE BLANK. SECONDARY THROUGH TERTIARY MAY CONTAIN BLANK (MEANING NONE / NOT SPECIFIED OR NOT APPLICABLE ).
                PRVDR_NCPDP_DSPNSR_DLT_DT -- DATE | NULL | THE DATE STAMPED BY NCPDP THAT THIS INFORMATION IS NO LONGER ACTIVE.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_DSPNSR"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrNcpdpDspnsrExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
