"""
==========
V2_MDCR_PRVDR_HCIDEA_ADR_PHNE IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA_ADR_PHNE

Table Type: VIEW
Columns: 11
Source Pattern: %mdcr_prvdr%
Table Comment: A LINK BETWEEN THE PRESCRIBER’S MULTIPLE PRACTICE LOCATIONS AND THEIR MULTIPLE PHONE NUMBERS AND PHONE TYPES.  HCIDEA IS THE HEALTH CARE IDENTIFIER DRUG ENFORCEMENT AGENCY DATABASE FILE STANDARD GOVERNED BY NCPDP.  NOTE: THIS TABLE IS NO LONGER BEING UPDATED BY THE SOURCE.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrHcideaAdrPhneExporter()
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


class V2MdcrPrvdrHcideaAdrPhneExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_HCIDEA_ADR_PHNE data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA_ADR_PHNE (VIEW)
    Columns: 11
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_hcidea_adr_phne_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_HCIDEA_ADR_PHNE export.
        
        Includes all 11 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_HCIDEA_ADR_ID, -- NUMBER(38) | NOT NULL | UNIQUE INTERNAL IDENTIFIER FOR AN INDIVIDUAL HEALTHCARE LOCATION. SHOULD BE USED TO JOIN THE ADDRESS, PHONE, AND MEDICAID TABLES TO RETAIN PROVIDER/ADDRESS RELATIONSHIP BETWEEN DATA VALUES.
                PRVDR_HCIDEA_ADR_PHNE_NUM, -- TEXT(15) | NOT NULL | TELEPHONE, FAX OR REFILL NUMBER ASSOCIATED WITH THIS PROVIDER AT THIS ADDRESS. VALUE IS DISPLAYED WITHOUT FORMATTING SUCH AS PARENTHESIS, SPACES, OR HYPHENS. EX: 9139045411, OR 800DENTIST
                PRVDR_HCIDEA_ADR_PHNE_TYPE_CD, -- TEXT(2) | NOT NULL | IDENTIFIES THE TYPE OF PHONE. EG. OFFICE PHONE, FAX, ETC. VALID VALUES
                PRVDR_HCIDEA_HC_ID, -- TEXT(10) | NOT NULL | UNIQUE NCPDP-ASSIGNED IDENTIFIER FOR AN INDIVIDUAL HEALTHCARE PROVIDER. THERE IS A ONE-TO-ONE RELATIONSHIP BETWEEN PROVIDERID AND HCID
                PRVDR_HCIDEA_CNFDNC_TIER_CD, -- NUMBER(38) | NOT NULL | THE CONFIDENCE TIER ASSOCIATED WITH THE PHONE VALUE FOR THE PROVIDER AT THE ADDRESS. VALID VALUES: 1, 2, 3, 99
                PRVDR_HCIDEA_CORP_CNT, -- NUMBER(38) | NOT NULL | THE TOTAL COUNT OF DATA SOURCES THAT SUPPLIED THE PHONE VALUE FOR THE PROVIDER AT THE ADDRESS.
                PRVDR_HCIDEA_RANK, -- NUMBER(38) | NOT NULL | INDICATES THE QUALITY OF THE DATA VALUE Ö THE LOWER THE RANK VALUE, THE BETTER THE QUALITY, I.E. 1 WOULD BE CONSIDERED THE BEST.
                PRVDR_HCIDEA_REC_VRFCTN_CD, -- TEXT(2) | NOT NULL | REPRESENTS THE VERIFICATION STATUS FOR THIS DATA ELEMENT FOR THIS PROVIDER BASED ON INGENIXÒ PROVIDER OFFICE OUTREACH OR ELECTRONIC VERIFICATION PROGRAMS. VALID VALUES: C- VERIFIED CORRECT, U - UNVERIFIED
                PRVDR_HCIDEA_REC_VRFCTN_DT, -- DATE | NOT NULL | FOR C VERIFICATION CODES, THIS IS THE DATE THAT THE DATA VALUE WAS VERIFIED. FOR U VERIFICATION CODES, THIS IS THE DATE THAT THE DATA VALUE WAS POPULATED INTO THE HCIDEA DATABASE. VERIFICATION CODE X INDICATES THE DATA IS NOT RECOGNIZED
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA_ADR_PHNE"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrHcideaAdrPhneExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
