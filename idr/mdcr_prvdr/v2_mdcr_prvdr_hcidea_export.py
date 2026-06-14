"""
==========
V2_MDCR_PRVDR_HCIDEA IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA

Table Type: VIEW
Columns: 8
Source Pattern: %mdcr_prvdr%
Table Comment: PRESCRIBER RECORDS AND RECORD TYPES. THE PROVIDER ENTITY CONTAINS THE UNIQUE PROVIDER ID THAT IS ASSIGNED BY INGENIX  AND USED AS THE PRIMARY IDENTIFIER IN NCPDPS HCIDEA  (HEALTH CARE IDENTIFIER DRUG ENFORCEMENT AGENCY) PRESCRIBER DATABASE FILE STANDARD.  NOTE: THIS TABLE IS NO LONGER BEING UPDATED BY THE SOURCE.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrHcideaExporter()
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


class V2MdcrPrvdrHcideaExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_HCIDEA data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA (VIEW)
    Columns: 8
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_hcidea_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_HCIDEA export.
        
        Includes all 8 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_HCIDEA_HC_ID, -- TEXT(10) | NOT NULL | UNIQUE NCPDP-ASSIGNED IDENTIFIER FOR AN INDIVIDUAL HEALTHCARE PROVIDER. THERE IS A ONE-TO-ONE RELATIONSHIP BETWEEN PROVIDERID AND HCID
                IDR_TRANS_EFCTV_TS, -- TIMESTAMP_NTZ | NOT NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) IDENTIFYING WHEN A RECORD IS LOADED.
                IDR_TRANS_OBSLT_TS, -- TIMESTAMP_NTZ | NOT NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHEN A RECORD WAS LAST KNOWN TO BE PRESENT IN THE SOURCE. THE CURRENT VERSION OF A RECORD WILL BE SET TO 12/31/9999 00:00:00.
                IDR_LTST_TRANS_FLG, -- TEXT(1) | NOT NULL | AN INDICATOR ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) THAT IDENTIFIES WHICH TRANSACTION RECORD, BASED ON PRIMARY KEY, IS CONSIDERED TO REPRESENT THE MOST RECENT RECORD RECEIVED FROM THE SOURCE. Y = LATEST VERSION OF THE RECORD N = PREVIOUS VERSION OF THE RECORD
                PRVDR_HCIDEA_CORP_CNT, -- NUMBER(38) | NOT NULL | THE TOTAL COUNT OF DATA SOURCES THAT SUPPLIED ANY DATA VALUES FOR THE INDIVIDUAL PROVIDER. COMPANY COUNT MEASURES THE DEGREE OF CONSENSUS AMONG OUR MYRIAD SOURCES THAT THIS DATA VALUE IS VALID. COMPANY COUNT ALSO APPLIES TO PROVIDER IDS, INDICATING THE NUMBER OF SOURCES FROM WHICH WE RECEIVED THIS SAME PROVIDER.
                PRVDR_HCIDEA_ID, -- NUMBER(38) | NULL | UNIQUE INTERNAL IDENTIFIER FOR AN HCIDEA INDIVIDUAL HEALTHCARE PROVIDER ASSIGNED BY INGENIX.
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrHcideaExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
