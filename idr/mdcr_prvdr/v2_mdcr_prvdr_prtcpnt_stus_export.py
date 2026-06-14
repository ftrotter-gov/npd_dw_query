"""
==========
V2_MDCR_PRVDR_PRTCPNT_STUS IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PRTCPNT_STUS

Table Type: VIEW
Columns: 12
Source Pattern: %mdcr_prvdr%
Table Comment: IF A DME PROVIDER AGREES TO ACCEPT ASSIGNMENT FOR ALL COVERED SERVICES THAT IT PROVIDES TO MEDICARE PATIENTS, THE PROVIDER IS CONSIDERED PARTICIPATING.  IF THE PROVIDER IS PARTICIPATING THE PARTICIPANT STATUS INDICATOR WILL BE Y.  OTHERWISE THE INDICATOR WILL BE N   PECOS: EACH INSTANCE CONTAINS DATA ON WHETHER A PROVIDER/SUPPLIER IS PARTICIPATING IN MEDICAID/MEDICARE BILLING SCHEDULE. CMS REQUIRES THAT HISTORY OF THE PARTICIPATION STATUS BE MAINTAINED AND SENT TO THE MEDICARE CLAIMS SYSTEM (MCS) IN THE DAILY EXPORT FILE.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrPrtcpntStusExporter()
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


class V2MdcrPrvdrPrtcpntStusExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_PRTCPNT_STUS data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PRTCPNT_STUS (VIEW)
    Columns: 12
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_prtcpnt_stus_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_PRTCPNT_STUS export.
        
        Includes all 12 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_PAC_ID, -- TEXT(10) | NOT NULL
                PRVDR_PRTCPNT_BGN_DT, -- DATE | NOT NULL | IDENTIFIES THE EFFECTIVE DATE OF THE PARTICIPANT STATUS.
                PRVDR_PRTCPNT_END_DT, -- DATE | NOT NULL | IDENTIFIES THE TERMINATION DATE OF THE PARTICIPANT STATUS.
                PRVDR_PRTCPNT_IND_CD, -- TEXT(1) | NOT NULL | INDENTIFIES PROVIDERS AS PARTICIPANTS OR NON-PARTICIPANTS.
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_RPT_SW, -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
                PRVDR_PECOS_SK, -- NUMBER(38) | NOT NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_DRVD_END_DT, -- DATE | NOT NULL | END DATE OF INPUT FILE
                PRVDR_ENRLMT_CNTRCTR_ID, -- TEXT(5) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A MEDICARE CONTRACTOR.
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_ENRLMT_CREAT_DT -- DATE | NOT NULL | DATE THE RECORD WAS CREATED (MM/DD/YYYY)
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PRTCPNT_STUS"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrPrtcpntStusExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
