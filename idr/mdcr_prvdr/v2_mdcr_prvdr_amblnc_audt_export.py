"""
==========
V2_MDCR_PRVDR_AMBLNC_AUDT IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_AMBLNC_AUDT

Table Type: VIEW
Columns: 23
Source Pattern: %mdcr_prvdr%
Table Comment: AN AUDIT OF THE PROVIDER AMBULENCE INFORMATION

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrAmblncAudtExporter()
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


class V2MdcrPrvdrAmblncAudtExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_AMBLNC_AUDT data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_AMBLNC_AUDT (VIEW)
    Columns: 23
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_amblnc_audt_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_AMBLNC_AUDT export.
        
        Includes all 23 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_PAC_ID, -- TEXT(10) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A PECOS ASSOCIATE.
                PRVDR_AMBLNC_LCNSD_SW, -- TEXT(1) | NOT NULL | INDICATES WHETHER THIS COMPANY IS LICENSED IN THE STATE WHERE SERVICES ARE RENDERED AND BILLED FOR.
                PRVDR_AMBLNC_PARAMDC_BGN_DT, -- DATE | NOT NULL | INDICATES WHETHER THIS COMPANY CURRENTLY PARTICIPATES IN A PARAMEDIC INTERCEPT SERVICE(S) ARRANGEMENT.
                PRVDR_AMBLNC_PARAMDC_SW, -- TEXT(1) | NOT NULL | INDICATES WHETHER THIS COMPANY HAS A CONTRACT WITH A BASIC LIFE SUPPORT SERVICE, SUCH AS A VOLUNTEER AMBULANCE COMPANY WHEREBY THE ADVANCED LIFE SUPPORT (ALS) SUPPLIER FURNISHES PARAMEDIC INTERCEPT SERVICE(S)
                PRVDR_AMBLNC_STATE_1_CD, -- TEXT(2) | NOT NULL | UNIQUE VALUE THAT IDENTIFIES A STATE.
                PRVDR_AMBLNC_STATE_2_CD, -- TEXT(2) | NOT NULL | UNIQUE VALUE THAT IDENTIFIES A STATE.
                PRVDR_AMBLNC_STATE_3_CD, -- TEXT(2) | NOT NULL | UNIQUE VALUE THAT IDENTIFIES A STATE.
                PRVDR_AMBLNC_STATE_4_CD, -- TEXT(2) | NOT NULL | UNIQUE VALUE THAT IDENTIFIES A STATE.
                PRVDR_AMBLNC_STATE_5_CD, -- TEXT(2) | NOT NULL | UNIQUE VALUE THAT IDENTIFIES A STATE.
                PRVDR_AMBLNC_STATE_6_CD, -- TEXT(2) | NOT NULL | UNIQUE VALUE THAT IDENTIFIES A STATE.
                PRVDR_AMBLNC_STATE_7_CD, -- TEXT(2) | NOT NULL | UNIQUE VALUE THAT IDENTIFIES A STATE.
                PRVDR_AMBLNC_STATE_8_CD, -- TEXT(2) | NOT NULL | UNIQUE VALUE THAT IDENTIFIES A STATE.
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_PECOS_SK, -- NUMBER(38) | NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_ENRLMT_CNTRCTR_ID, -- TEXT(5) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A MEDICARE CONTRACTOR.
                PRVDR_ENRLMT_CREAT_DT, -- DATE | NOT NULL | DATE THE RECORD WAS CREATED (MM/DD/YYYY)
                PRVDR_RPT_SW, -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
                PRVDR_AMBLNC_AUDT_CREAT_DT, -- DATE | NULL | DATE DATA WAS CREATED IN SOURCE
                PRVDR_AMBLNC_AUDT_UPDT_DT, -- DATE | NULL | DATE DATA WAS CORRECTED IN SOURCE
                PRVDR_AMBLNC_PARAMDC_EFCTV_DT, -- DATE | NULL | A IDR ETL DERIVED DATE THAT CAPTURES THE EFFECTIVE DATE FOR THE CERTIFIED BASIC LIFE SUPPORT INFORMATION.
                PRVDR_AMBLNC_PARAMDC_OBSLT_DT -- DATE | NULL | A IDR ETL DERIVED DATE THAT CAPTURES THE OBSOLETE DATE FOR THE CERTIFIED BASIC LIFE SUPPORT INFORMATION.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_AMBLNC_AUDT"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrAmblncAudtExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
