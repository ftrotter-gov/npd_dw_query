"""
==========
V2_MDCR_PRVDR_HHA_AUDT IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HHA_AUDT

Table Type: VIEW
Columns: 24
Source Pattern: %mdcr_prvdr%
Table Comment: AN AUDIT OF THE PROVIDER HOME HEALTH AIDE INFORMATION

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrHhaAudtExporter()
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


class V2MdcrPrvdrHhaAudtExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_HHA_AUDT data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HHA_AUDT (VIEW)
    Columns: 24
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_hha_audt_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_HHA_AUDT export.
        
        Includes all 24 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_ENRLMT_CREAT_DT, -- DATE | NOT NULL | DATE THE RECORD WAS CREATED (MM/DD/YYYY)
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_PAC_ID, -- TEXT(10) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A PECOS ASSOCIATE.
                GEO_SK, -- NUMBER(38) | NULL | AN INTEGRATED DATA REPOSITORY (IDR) ASSIGNED NUMERIC SURROGATE KEY IDENTIFYING A PARTICULAR GEOGRAPHICAL LOCATION BY ITS FIVE-DIGIT ZIP CODE.
                GEO_ZIP4_CD, -- TEXT(4) | NULL | A FOUR-DIGIT ZIP CODE EXTENSION DEFINED BY THE UNITED STATES POSTAL SERVICE (USPS) THAT REPRESENTS A SPECIFIC DELIVERY ROUTE WITHIN A DELIVERY AREA ASSOCIATED WITH A BENEFICIARY, PROVIDER, OR CLAIM ADDRESS AND USED IN THE GEOCODING PROCESS. REFERENCE TABLE: GEO_ZIP9_CD
                PRVDR_HHA_12_MO_QTY, -- NUMBER(18) | NULL | PROJECTED NUMBER OF VISITS IN 12 MONTHS?
                PRVDR_HHA_3_MO_QTY, -- NUMBER(18) | NULL | PROJECTED NUMBER OF VISITS IN 3 MONTHS?
                PRVDR_HHA_FINCL_DOC_CD, -- TEXT(1) | NULL | FINANCIAL DOCUMENT SUBMITTED?
                PRVDR_HHA_INVLD_PLC_NAME, -- TEXT(30) | NOT NULL | CITY OF PECOS ASSOCIATE MAILING ADDRESS.
                PRVDR_HHA_INVLD_STATE_CD, -- TEXT(2) | NULL | UNIQUE VALUE THAT IDENTIFIES A STATE.
                PRVDR_HHA_INVLD_ZIP_CD, -- TEXT(15) | NULL | ZIP CODE OF PECOS ASSOCIATE MAILING ADDRESS.
                PRVDR_HHA_LGL_NAME, -- TEXT(70) | NOT NULL | NAME OF ORGANIZATION.
                PRVDR_HHA_LINE_1_ADR, -- TEXT(55) | NOT NULL | LINE 1 OF PECOS ASSOCIATE MAILING ADDRESS.
                PRVDR_HHA_LINE_2_ADR, -- TEXT(55) | NULL | LINE 2 OF PECOS ASSOCIATE MAILING ADDRESS.
                PRVDR_HHA_PHNE_NUM, -- TEXT(20) | NULL | TELEPHONE ADDRESS OF PECOS ASSOCIATE.
                PRVDR_HHA_TIN_NUM, -- TEXT(9) | NULL | TAX ID NUMBER
                PRVDR_HHA_TYPE_CD, -- TEXT(1) | NULL | TYPE OF HOME HEALTH AGENCY
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_PECOS_SK, -- NUMBER(38) | NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_ENRLMT_CNTRCTR_ID, -- TEXT(5) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A MEDICARE CONTRACTOR.
                PRVDR_RPT_SW, -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
                PRVDR_HHA_AUDT_CREAT_DT, -- DATE | NULL | DATE DATA WAS CREATED IN SOURCE
                PRVDR_HHA_AUDT_UPDT_DT -- DATE | NULL | DATE DATA WAS CORRECTED IN SOURCE
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HHA_AUDT"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrHhaAudtExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
