"""
==========
V2_MDCR_PRVDR_SPRVSNG_AUDT IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SPRVSNG_AUDT

Table Type: VIEW
Columns: 18
Source Pattern: %mdcr_prvdr%
Table Comment: AN AUDIT OF THE PROVIDER INDEPENDENT DIAGNOSTIC TESTING FACILITY SUPERVISING HCPCS INFORMATION

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrSprvsngAudtExporter()
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


class V2MdcrPrvdrSprvsngAudtExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_SPRVSNG_AUDT data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SPRVSNG_AUDT (VIEW)
    Columns: 18
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_sprvsng_audt_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_SPRVSNG_AUDT export.
        
        Includes all 18 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_IDTF_STD_CD, -- TEXT(1) | NOT NULL | DOES THIS IDTF MEET ALL CURRENT CMS IDTF STANDARDS?
                PRVDR_IDTF_BGN_DT, -- DATE | NOT NULL | DATE THAT THE IDTF STARTED USING THE CPT-4 OR HCPCS EQUIPMENT
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                PRVDR_ENRLMT_CREAT_DT, -- DATE | NOT NULL | DATE THE RECORD WAS CREATED (MM/DD/YYYY)
                PRVDR_ENRLMT_CNTRCTR_ID, -- TEXT(5) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A MEDICARE CONTRACTOR.
                PRVDR_IDTF_PHYSN_1ST_NAME, -- TEXT(25) | NOT NULL | FIRST NAME OF PECOS ASSOCIATE.
                PRVDR_IDTF_PHYSN_MDL_NAME, -- TEXT(25) | NULL | MIDDLE NAME OF PECOS ASSOCIATE.
                PRVDR_IDTF_PHYSN_LAST_NAME, -- TEXT(35) | NOT NULL | LAST NAME OF PECOS ASSOCIATE.
                PRVDR_IDTF_PHYSN_ASCT_DT, -- DATE | NULL | DATE THE SUPERVISING PHYSICIAN WAS ASSOCIATED WITH THIS INDEPENDENT DIAGNOSTIC TESTING FACILITY(IDTF).
                HCPCS_CD, -- TEXT(20) | NULL | HEALTHCARE COMMON PROCEDURE CODING SYSTEM (HCPCS) IS A COLLECTION OF CODES THAT REPRESENT PROCEDURES, SUPPLIES, PRODUCTS AND SERVICES WHICH MAY BE PROVIDED TO MEDICARE BENEFICIARIES AND TO INDIVIDUALS ENROLLED IN PRIVATE HEALTH INSURANCE PROGRAMS. THE CODES ARE DIVIDED INTO THREE LEVELS, OR GROUPS.
                CLNDR_HCPCS_YR_NUM, -- NUMBER(38) | NULL | THE CALENDAR YEAR OF A HEALTHCARE COMMON PROCEDURE CODING SYSTEM (HCPCS)
                PRVDR_PAC_ID, -- TEXT(10) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A PECOS ASSOCIATE.
                PRVDR_PECOS_SK, -- NUMBER(38) | NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_RPT_SW, -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
                PRVDR_SPRVSNG_AUDT_CREAT_DT, -- DATE | NULL | DATE DATA WAS CREATED IN SOURCE
                PRVDR_SPRVSNG_AUDT_UPDT_DT, -- DATE | NULL | DATE DATA WAS CORRECTED IN SOURCE
                META_SRC_SK -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SPRVSNG_AUDT"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrSprvsngAudtExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
