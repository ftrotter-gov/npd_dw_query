"""
==========
V2_MDCR_PRVDR_ENRLMT_STUS IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_ENRLMT_STUS

Table Type: VIEW
Columns: 10
Source Pattern: %mdcr_prvdr%
Table Comment: THE ENROLLMENT STATUS CHILD RECORD IS CREATED FOR SPECIFIC STATUS CODE AND REASON CODE COMBINATIONS. PECOS WILL SEND BOTH HISTORIC AND CURRENT ENROLLMENT STATUS INFORMATION. THE COMBINATION OF STATUS CODE AND REASON CODE CRITERIA MUST BE MET FOR THE CHILD RECORD TO BE SENT.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrEnrlmtStusExporter()
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


class V2MdcrPrvdrEnrlmtStusExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_ENRLMT_STUS data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_ENRLMT_STUS (VIEW)
    Columns: 10
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_enrlmt_stus_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_ENRLMT_STUS export.
        
        Includes all 10 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_RSN_CD, -- TEXT(3) | NOT NULL | THIS IS THE REASON CODE FOR THE ENROLLMENT STATUS.
                PRVDR_STUS_CD, -- TEXT(2) | NOT NULL | THIS IS THE STATUS CODE FOR ENROLLMENT DATA.
                PRVDR_STUS_BGN_DT, -- DATE | NOT NULL | EFFECTIVE DATE OF THE ENROLLMENT STATUS.
                PRVDR_STUS_END_DT, -- DATE | NOT NULL | THE TERMINATION DATE OF THE ENROLLMENT STATUS.
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_PECOS_SK, -- NUMBER(38) | NOT NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_RPT_SW, -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_DRVD_END_DT -- DATE | NOT NULL | END DATE OF INPUT FILE
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_ENRLMT_STUS"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrEnrlmtStusExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
