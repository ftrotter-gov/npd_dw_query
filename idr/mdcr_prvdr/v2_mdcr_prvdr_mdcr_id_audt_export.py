"""
==========
V2_MDCR_PRVDR_MDCR_ID_AUDT IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_MDCR_ID_AUDT

Table Type: VIEW
Columns: 17
Source Pattern: %mdcr_prvdr%
Table Comment: AN AUDIT OF THE PROVIDER MEDICARE IDENTIFER INFORMATION.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrMdcrIdAudtExporter()
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


class V2MdcrPrvdrMdcrIdAudtExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_MDCR_ID_AUDT data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_MDCR_ID_AUDT (VIEW)
    Columns: 17
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_mdcr_id_audt_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_MDCR_ID_AUDT export.
        
        Includes all 17 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_PAC_ID, -- TEXT(10) | NULL | THE SYSTEM GENERATED PECOS ASSOCIATE CONTROL ID.
                PRVDR_MDCR_AUDT_ID, -- TEXT(10) | NULL | THIS IS THE NATIONAL SUPPLIER CLEARING HOUSE BILLING NUMBER.
                PRVDR_MDCR_ID_AUDT_TYPE_CD, -- TEXT(2) | NULL | FROM SECTION 1 OF CMS-855S, THE TYPE OF MEDICARE IDENTIFICATION.
                PRVDR_PECOS_SK, -- NUMBER(38) | NOT NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_MDCR_ID_AUDT_BGN_DT, -- DATE | NULL | THE EFFECTIVE DATE FOR A MEDICARE IDENTIFIER.
                PRVDR_MDCR_ID_AUDT_END_DT, -- DATE | NOT NULL | THE TERMINATION DATE FOR A MEDICARE IDENTIFIER.
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_SK, -- NUMBER(18) | NULL | AN IDR ASSIGNED SURROGATE KEY USED TO IDENTIFY A PARTY ENGAGED IN ACTIVITY RELATED TO CMS.
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_RPT_AUDT_SW, -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
                PRVDR_DRVD_END_DT, -- DATE | NOT NULL | END DATE OF INPUT FILE
                PRVDR_ENRLMT_CNTRCTR_ID, -- TEXT(5) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A MEDICARE CONTRACTOR.
                PRVDR_ENRLMT_CREAT_DT, -- DATE | NOT NULL | DATE THE RECORD WAS CREATED (MM/DD/YYYY)
                PRVDR_INVLD_NPI_NUM, -- TEXT(15) | NULL | AN PROVIDER NPI NUMBER THAT CANNOT BE MATCHED IN THE CURRENT PROVIDER TABLE.
                PRVDR_MDCR_ID_AUDT_CREAT_DT, -- DATE | NULL | DATE DATA WAS CREATED IN SOURCE
                PRVDR_MDCR_ID_AUDT_UPDT_DT -- DATE | NULL | DATE DATA WAS CORRECTED IN SOURCE
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_MDCR_ID_AUDT"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrMdcrIdAudtExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
