"""
==========
V2_MDCR_PRVDR_NCPDP_RLTNSHP IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_RLTNSHP

Table Type: VIEW
Columns: 10
Source Pattern: %mdcr_prvdr%
Table Comment: THE NATIONAL COUNCIL FOR PRESCRIPTION DRUG PROGRAMS (NCPDP) MAINTAINED INFORMATION DEFINING A PROVIDERS ASSOCIATION WITH ANOTHER ENTITY OR ENTITIES AND/OR WHERE THIRD PARTY PAYMENTS ARE DIRECTED FOR THAT RELATIONSHIP OR FOR THAT PROVIDER IF NO RELATIONSHIP IS SPECIFIED.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrNcpdpRltnshpExporter()
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


class V2MdcrPrvdrNcpdpRltnshpExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_NCPDP_RLTNSHP data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_RLTNSHP (VIEW)
    Columns: 10
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_ncpdp_rltnshp_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_NCPDP_RLTNSHP export.
        
        Includes all 10 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_NCPDP_ID, -- TEXT(7) | NOT NULL | THE PROVIDERS NCPDP NUMBER.
                PRVDR_NCPDP_RLTN_ID, -- TEXT(3) | NOT NULL | THE IDENTIFIER ASSIGNED TO REPRESENT THE RELATIONSHIP ASSOCIATED WITH THE PROVIDER.
                PRVDR_NCPDP_PYMT_CNTR_ID, -- TEXT(6) | NOT NULL | THE PAYMENT CENTER IDENTIFIER ASSOCIATED WITH THE PROVIDER.
                PRVDR_NCPDP_RLTNSHP_BGN_DT, -- DATE | NOT NULL | THE DATE THAT THE RELATIONSHIP ID AND/OR PAYMENT CENTER ID IS ACTIVE FOR THE PROVIDER.
                PRVDR_NCPDP_RLTNSHP_END_DT, -- DATE | NULL | THE DATE THAT THE RELATIONSHIP ID AND/OR PAYMENT CENTER ID IS NO LONGER ACTIVE FOR THE PROVIDER.
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_NCPDP_REMIT_ID, -- TEXT(6) | NOT NULL | THE REMIT AND RECONCILIATION IDENTIFIER ASSOCIATED WITH THE PROVIDER.
                PRVDR_NCPDP_PRVDR_TYPE_CD, -- TEXT(2) | NULL | THE TYPE OF BUSINESS THIS PROVIDER IS PROCESSING. ONLY RECORDS WITH TWO RELATIONSHIP IDS THAT HAVE A RELATIONSHIP TYPE OF 05 (THIRD PARTY CONTRACTING GROUP) REQUIRE PROVIDER TYPES ON THE PROVIDER RELATIONSHIP INFORMATION - DETAIL RECORD.
                PRVDR_NCPDP_PRMRY_PRVDR_SW -- TEXT(1) | NULL | (Y)ES OR (N)O INDICATOR THAT PROVIDER RELATIONSHIP IS PRIMARY. ONLY RELATIONSHIP IDS CAN BE MARKED AS PRIMARY. PAYMENT CENTER IDS AND REMIT AND RECONCILIATION IDS CANNOT BE FLAGGED AS PRIMARY. PROVIDERS ARE NOT REQUIRED TO DECLARE ANY OF THEIR RELATIONSHIPS AS PRIMARY.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NCPDP_RLTNSHP"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrNcpdpRltnshpExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
