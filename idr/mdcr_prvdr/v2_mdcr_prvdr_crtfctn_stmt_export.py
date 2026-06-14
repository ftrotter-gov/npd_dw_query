"""
==========
V2_MDCR_PRVDR_CRTFCTN_STMT IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_CRTFCTN_STMT

Table Type: VIEW
Columns: 15
Source Pattern: %mdcr_prvdr%
Table Comment: THE AUTHORIZED/DELEGATED OFFICIAL AND CERTIFICATION STATEMENT CHILD RECORD IS CREATED TO COLLECT INFORMATION FOR BOTH THE AUTHORIZED/DELEGATED OFFICIAL, AND THE INDIVIDUAL CERTIFICATION RECORD.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrCrtfctnStmtExporter()
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


class V2MdcrPrvdrCrtfctnStmtExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_CRTFCTN_STMT data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_CRTFCTN_STMT (VIEW)
    Columns: 15
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_crtfctn_stmt_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_CRTFCTN_STMT export.
        
        Includes all 15 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_CRTFCTN_ROLE_CD, -- TEXT(2) | NOT NULL | UNIQUE VALUE THAT IDENTIFIES A ROLE.
                PRVDR_CRTFCTN_1ST_NAME, -- TEXT(25) | NOT NULL | FIRST NAME OF AUTHORIZED OFFICIAL.
                PRVDR_CRTFCTN_BGN_DT, -- DATE | NOT NULL | ASSOCIATE DATE
                PRVDR_CRTFCTN_LAST_NAME, -- TEXT(35) | NOT NULL | LAST NAME OF AUTHORIZED OFFICIAL.
                PRVDR_CRTFCTN_MDL_NAME, -- TEXT(25) | NOT NULL | MIDDLE NAME OF AUTHORIZED OFFICIAL.
                PRVDR_CRTFCTN_SGNTR_DT, -- DATE | NOT NULL | THE DATE THAT THE ENROLLMENT FORM WAS SIGNED.
                PRVDR_CRTFCTN_TITLE_NAME, -- TEXT(35) | NOT NULL | NAME OF THE TITLE OR POSITION OF AN INDIVIDUAL AUTHORIZED TO SIGN AN ENROLLMENT CERTIFICATION STATEMENT.
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_PAC_ID, -- TEXT(10) | NOT NULL
                PRVDR_PECOS_SK, -- NUMBER(38) | NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_ENRLMT_CNTRCTR_ID, -- TEXT(5) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A MEDICARE CONTRACTOR.
                PRVDR_ENRLMT_CREAT_DT, -- DATE | NOT NULL | DATE THE RECORD WAS CREATED (MM/DD/YYYY)
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_RPT_SW -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_CRTFCTN_STMT"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrCrtfctnStmtExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
