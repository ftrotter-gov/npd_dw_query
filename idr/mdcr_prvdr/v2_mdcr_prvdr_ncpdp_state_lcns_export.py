"""
==========
V2_MDCR_PRVDR_NCPDP_STATE_LCNS IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_STATE_LCNS

Table Type: VIEW
Columns: 7
Source Pattern: %mdcr_prvdr%
Table Comment: THE LISTING OF STATE LICENSE INFORMATION FOR PHARMACY AND ALTERNATE DISPENSING SITE RECORDS.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrNcpdpStateLcnsExporter()
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


class V2MdcrPrvdrNcpdpStateLcnsExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_NCPDP_STATE_LCNS data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_STATE_LCNS (VIEW)
    Columns: 7
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_ncpdp_state_lcns_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_NCPDP_STATE_LCNS export.
        
        Includes all 7 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_NCPDP_ID, -- TEXT(7) | NOT NULL | THE UNIQUE NUMBER ASSIGNED BY THE NATIONAL COUNCIL FOR PRESCRIPTION DRUG PROGRAM (NCPDP) TO THE PHARMACY.
                PRVDR_NCPDP_STATE_LCNS_NUM, -- TEXT(20) | NOT NULL | THE STATE BOARD OF PHARMACY LICENSE NUMBER ASSIGNED TO THE PROVIDER.
                PRVDR_NCPDP_LCNS_EXPRTN_DT, -- DATE | NOT NULL | EXPIRATION DATE FOR THE STATE LICENSE.
                PRVDR_NCPDP_LCNS_STATE_CD, -- TEXT(2) | NOT NULL | THE TWO-DIGIT STATE CODE.
                PRVDR_NCPDP_LCNS_DLT_DT, -- DATE | NULL | THE DATE STAMPED BY NCPDP THAT THIS INFORMATION IS NO LONGER ACTIVE. IF INFORMATION IS ACTIVE, THIS FIELD WILL CONTAIN ZEROES.
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_STATE_LCNS"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrNcpdpStateLcnsExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
