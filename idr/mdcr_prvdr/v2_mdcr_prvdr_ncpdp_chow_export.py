"""
==========
V2_MDCR_PRVDR_NCPDP_CHOW IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_CHOW

Table Type: VIEW
Columns: 6
Source Pattern: %mdcr_prvdr%
Table Comment: INFORMATION REGARDING PHARMACEUTICAL DISPENSING SITES THAT HAVE CHANGED OWNERSHIP.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrNcpdpChowExporter()
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


class V2MdcrPrvdrNcpdpChowExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_NCPDP_CHOW data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_CHOW (VIEW)
    Columns: 6
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_ncpdp_chow_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_NCPDP_CHOW export.
        
        Includes all 6 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_NCPDP_ID, -- TEXT(7) | NOT NULL | THE UNIQUE NUMBER ASSIGNED BY THE NATIONAL COUNCIL FOR PRESCRIPTION DRUG PROGRAM (NCPDP) TO THE PHARMACY.
                PRVDR_NCPDP_OLD_ID, -- TEXT(7) | NOT NULL | THE NCPDP NUMBER ASSIGNED TO THE LOCATION UNDER THE PRIOR OWNERSHIP. THIS CAN BE THE SAME NCPDP PROVIDER ID AS THE CURRENT AND ACTIVE, IF THE NEW OWNER TRANSFERRED THE IDENTIFIERS.
                PRVDR_NCPDP_CHOW_BGN_DT, -- DATE | NOT NULL | THE DATE THE NEW OWNER TOOK OVER THE NCPDP PROVIDER ID AND DID, OR WILL, BEGIN PROCESSING WITH IT. THIS IS NOT NECESSARILY THE DATE THE OWNERSHIP OF THE FACILITY CHANGED.
                PRVDR_NCPDP_STORE_CLOSE_DT, -- DATE | NULL | THE DATE THAT THE PHARMACY STOPPED OPERATING UNDER THE PREVIOUS OWNERSHIP.
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_CHOW"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrNcpdpChowExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
