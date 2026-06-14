"""
==========
V2_MDCR_PRVDR_ACRDTN IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_ACRDTN

Table Type: VIEW
Columns: 17
Source Pattern: %mdcr_prvdr%
Table Comment: THE ACCREDITATION RECORD CONTAINS THE SUPPLIERS ACCREDITATION AS INDICATED IN SECTION 2G OF THE CMS 855S FORM AS WELL AS THE EFFECTIVE, EXPIRATION, AND END DATES FOR ACCREDITATION.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrAcrdtnExporter()
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


class V2MdcrPrvdrAcrdtnExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_ACRDTN data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_ACRDTN (VIEW)
    Columns: 17
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_acrdtn_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_ACRDTN export.
        
        Includes all 17 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_ACRDTN_BDY_CD, -- TEXT(5) | NULL | UNIQUE VALUE THAT IDENTIFIES AN ACCREDITING ORGANIZATION.
                PRVDR_ACRDTN_CD, -- TEXT(1) | NULL | INDICATES WHETHER PROVIDER/SUPPLIER IS ACCREDITED.
                PRVDR_ACRDTN_BGN_DT, -- DATE | NULL | DATE PROVIDER WAS ACCREDITED BY ANY ACCREDITING ORGANIZATION THAT MEDICARE HAS APPROVED FOR ACCEPTANCE IN LIEU OF A STATE SURVEY.
                PRVDR_ACRDTN_EXPRTN_DT, -- DATE | NULL | THE DATE THAT THE PROVIDERS ACCREDITATION WILL EXPIRE.
                PRVDR_ACRDTN_END_DT, -- DATE | NULL | THE DATE THAT AN ACCREDITATION IS REVOKED.
                PRVDR_ACRDTN_ID, -- TEXT(20) | NULL | A SYSTEM GENERATED UNIQUE IDENTIFIER FOR AN ENROLLMENT ACCREDITATION.
                PRVDR_PECOS_SK, -- NUMBER(38) | NOT NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_RPT_SW, -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
                PRVDR_PAC_ID, -- TEXT(10) | NULL | THE SYSTEM GENERATED PECOS ASSOCIATE CONTROL ID.
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_DRVD_END_DT, -- DATE | NOT NULL | END DATE OF INPUT FILE
                PRVDR_ACRDTN_BODY_NAME, -- TEXT(55) | NOT NULL | NAME OF ACCREDITING ORGANIZATION.
                PRVDR_ENRLMT_CNTRCTR_ID, -- TEXT(5) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A MEDICARE CONTRACTOR.
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_ENRLMT_CREAT_DT, -- DATE | NOT NULL | DATE THE RECORD WAS CREATED (MM/DD/YYYY)
                PRVDR_ACRDTN_PROD_CD -- TEXT(4) | NOT NULL | THE PRODUCTS AND SERVICES TYPE CODE ASSOCIATED TO THE SUPPIERS ACCREDITATION. THE RECORD IS REQUIRED WHEN THE PRVDR_ACRDTN_CD STATUS IS Ð‰Ò AND ÓÔ AND NOT REQUIRED FOR STATUS E. THESE VALUES ARE SOURCED FROM PECOS VMS CLAIMS EXTRACT FILE.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_ACRDTN"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrAcrdtnExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
