"""
==========
V2_MDCR_PRVDR_NCPDP_STATE IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_STATE

Table Type: VIEW
Columns: 6
Source Pattern: %mdcr_prvdr%
Table Comment: THE NATIONAL COUNCIL FOR PRESCRIPTION DRUG PROGRAMS (NCPDP) CROSS REFERENCE TABLE OF PROVIDERS TO STATE MEDICAID NUMBER.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrNcpdpStateExporter()
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


class V2MdcrPrvdrNcpdpStateExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_NCPDP_STATE data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_STATE (VIEW)
    Columns: 6
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_ncpdp_state_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_NCPDP_STATE export.
        
        Includes all 6 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_NCPDP_ID, -- TEXT(7) | NOT NULL | THE PROVIDERS NCPDP NUMBER.
                GEO_FIPS_STATE_CD, -- TEXT(2) | NOT NULL | A CODE IDENTIFYING A TWO-CHARACTER ALPHABETIC ABBREVIATION FOR A STATE DEFINED BY THE FEDERAL INFORMATION PROCESSING STANDARD (FIPS). REFERENCE TABLE: GEO_FIPS_STATE_CD
                PRVDR_NCPDP_STATE_MDCD_NUM, -- TEXT(20) | NOT NULL | THE IDENTIFICATION NUMBER ASSIGNED TO THE PROVIDER BY THE STATE MEDICAID AGENCY.
                PRVDR_NCPDP_STATE_DLT_DT, -- DATE | NULL | THE DATE STAMPED BY NCPDP THAT THIS INFORMATION IS NO LONGER ACTIVE.
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_STATE"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrNcpdpStateExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
