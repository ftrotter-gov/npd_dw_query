"""
==========
V2_MDCR_PRVDR_HCIDEA_BIRTH IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA_BIRTH

Table Type: VIEW
Columns: 8
Source Pattern: %mdcr_prvdr%
Table Comment: THIS ENTITY STORES THE PRESCRIBERS BIRTH DATE INFORMATION OBTAINED FROM VARIOUS SOURCES BY THE NCPDP COUNCIL FOR HCIDEA (HEALTH CARE IDENTIFIER DRUG ENFORCEMENT AGENCY) DATABASE FILE STANDARD.  NOTE: THIS TABLE IS NO LONGER BEING UPDATED BY THE SOURCE.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrHcideaBirthExporter()
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


class V2MdcrPrvdrHcideaBirthExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_HCIDEA_BIRTH data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA_BIRTH (VIEW)
    Columns: 8
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_hcidea_birth_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_HCIDEA_BIRTH export.
        
        Includes all 8 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_HCIDEA_HC_ID, -- TEXT(10) | NOT NULL | UNIQUE NCPDP-ASSIGNED IDENTIFIER FOR AN INDIVIDUAL HEALTHCARE PROVIDER. THERE IS A ONE-TO-ONE RELATIONSHIP BETWEEN PROVIDERID AND HCID
                PRVDR_HCIDEA_BIRTH_DT, -- DATE | NOT NULL | BIRTH DATE OF THE PROVIDER OBTAINED FROM VARIOUS SOURCES
                PRVDR_HCIDEA_CNFDNC_TIER_CD, -- NUMBER(38) | NOT NULL | THE CONFIDENCE TIER ASSOCIATED WITH THE BIRTH DATE VALUE. VALID VALUES: 1, 2, 3, 99
                PRVDR_HCIDEA_CORP_CNT, -- NUMBER(38) | NOT NULL | THE TOTAL COUNT OF DATA SOURCES THAT SUPPLIED THE BIRTH DATE VALUE.
                PRVDR_HCIDEA_REC_VRFCTN_CD, -- TEXT(2) | NOT NULL | REPRESENTS THE VERIFICATION STATUS FOR THIS DATA ELEMENT FOR THIS PROVIDER BASED ON INGENIXÒ PROVIDER OFFICE OUTREACH OR ELECTRONIC VERIFICATION PROGRAMS. VALID VALUES: C- VERIFIED CORRECT, U - UNVERIFIED
                PRVDR_HCIDEA_REC_VRFCTN_DT, -- DATE | NOT NULL | FOR C VERIFICATION CODES, THIS IS THE DATE THAT THE DATA VALUE WAS VERIFIED. FOR U VERIFICATION CODES, THIS IS THE DATE THAT THE DATA VALUE WAS POPULATED INTO THE HCIDEA DATABASE. VERIFICATION CODE X INDICATES THE DATA IS NOT RECOGNIZED.
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA_BIRTH"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrHcideaBirthExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
