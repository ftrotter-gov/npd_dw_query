"""
==========
V2_MDCR_PRVDR_MDCR_ID IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_MDCR_ID

Table Type: VIEW
Columns: 15
Source Pattern: %mdcr_prvdr%
Table Comment: THE MEDICARE ID CHILD RECORD CONTAINS THE SUPPLIERS NSC BILLING NUMBER WHICH IS ENTERED IN SECTION 1 OF THE CMS-855S FORM. THE MEDICARE ID CHILD RECORD WILL INCLUDE THE NSC BILLING NUMBER AND THE NATIONAL PROVIDER IDENTIFIER (NPI). (SEE DA COMMENT #1) PECOS WILL SEND THE CURRENT AND HISTORIC MEDICARE IDS  PECOS: EACH INSTANCE CONTAINS THE  PECOS ASSOCIATES MEDICARE IDENTIFICATION NUMBER.  THIS NUMBER UNIQUELY IDENTIFIES THE APPLICANT AS A MEDICARE PROVIDER AND/OR SUPPLIER AND IS THE NUMBER USED ON CLAIM FORMS.  EXAMPLES OF MEDICARE NUMBERS ARE  OSCAR AND NSC.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrMdcrIdExporter()
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


class V2MdcrPrvdrMdcrIdExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_MDCR_ID data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_MDCR_ID (VIEW)
    Columns: 15
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_mdcr_id_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_MDCR_ID export.
        
        Includes all 15 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_PAC_ID, -- TEXT(10) | NOT NULL | THE SYSTEM GENERATED PECOS ASSOCIATE CONTROL ID.
                PRVDR_MDCR_ID, -- TEXT(10) | NOT NULL | THIS NUMBER UNIQUELY IDENTIFIES THE APPLICANT AS A MEDICARE PROVIDER AND/OR SUPPLIER AND IS THE NUMBER USED ON CLAIM FORMS.
                PRVDR_MDCR_ID_TYPE_CD, -- TEXT(2) | NOT NULL | UNIQUE VALUE THAT IDENTIFIES THE TYPE OF IDENTIFICATION NUMBER THAT CAN BE ASSIGNED TO MEDICAID OR MEDICARE PROVIDER.
                PRVDR_MDCR_ID_BGN_DT, -- DATE | NOT NULL | THE EFFECTIVE DATE FOR A MEDICARE IDENTIFIER.
                PRVDR_MDCR_ID_END_DT, -- DATE | NOT NULL | THE TERMINATION DATE FOR A MEDICARE IDENTIFIER.
                PRVDR_SK, -- NUMBER(18) | NULL | AN IDR ASSIGNED SURROGATE KEY USED TO IDENTIFY A PARTY ENGAGED IN ACTIVITY RELATED TO CMS.
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_PECOS_SK, -- NUMBER(38) | NOT NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_RPT_SW, -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
                PRVDR_DRVD_END_DT, -- DATE | NOT NULL | END DATE OF INPUT FILE
                PRVDR_ENRLMT_CNTRCTR_ID, -- TEXT(5) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A MEDICARE CONTRACTOR.
                PRVDR_ENRLMT_CREAT_DT, -- DATE | NOT NULL | DATE THE RECORD WAS CREATED (MM/DD/YYYY)
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_INVLD_NPI_NUM -- TEXT(15) | NULL | AN PROVIDER NPI NUMBER THAT CANNOT BE MATCHED IN THE CURRENT PROVIDER TABLE.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_MDCR_ID"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrMdcrIdExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
