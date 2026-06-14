"""
==========
V2_MDCR_PRVDR_HCIDEA_DEA_WVR IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA_DEA_WVR

Table Type: VIEW
Columns: 6
Source Pattern: %mdcr_prvdr%
Table Comment: DATE WAIVER APPROVED PRESCRIBER’S STATUS WITH THE DRUG ENFORCEMENT ADMINISTRATION (DEA), A DIVISION OF THE UNITED STATES DEPARTMENT OF JUSTICE THAT REGULATES THE USE AND SALE OF CONTROLLED SUBSTANCES.  HCIDEA IS THE HEALTH CARE IDENTIFIER DRUG ENFORCEMENT AGENCY DATABASE FILE STANDARD GOVERNED BY NCPDP.  NOTE: THIS TABLE IS NO LONGER BEING UPDATED BY THE SOURCE.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrHcideaDeaWvrExporter()
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


class V2MdcrPrvdrHcideaDeaWvrExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_HCIDEA_DEA_WVR data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA_DEA_WVR (VIEW)
    Columns: 6
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_hcidea_dea_wvr_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_HCIDEA_DEA_WVR export.
        
        Includes all 6 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_HCIDEA_DEA_NUM, -- TEXT(20) | NOT NULL | DEA REGISTRATION NUMBER OF PROVIDER.
                PRVDR_HCIDEA_HC_ID, -- TEXT(10) | NOT NULL | UNIQUE NCPDP-ASSIGNED IDENTIFIER FOR AN INDIVIDUAL HEALTHCARE PROVIDER. THERE IS A ONE-TO-ONE RELATIONSHIP BETWEEN PROVIDERID AND HCID
                PRVDR_HCIDEA_ACTVTY_CD, -- TEXT(5) | NOT NULL | CODED VALUE FROM THE NTIS DEA THAT IDENTIFIES PROVIDERS WHO HAVE REQUESTED AND RECEIVED A DATA WAIVER (DW) FROM DEA, AFTER APPROVAL IS GRANTED BY THE CENTER FOR SUBSTANCE ABUSE TREATMENT (CSAT) WITHIN SUBSTANCE ABUSE AND MENTAL HEALTH SERVICES ADMINISTRATION (SAMHSA) OF THE DEPARTMENT OF HEALTH AND HUMAN SERVICES (HHS) AND ANY APPLICABLE STATE METHADONE AUTHORITY. C1 Ö DATA WAIVER Ö 30 PATIENTS C4 Ö DATA WAIVER Ö 100 PATIENTS C5 Ö DATA WAIVER Ö 30 PATIENTS
                PRVDR_HCIDEA_REC_VRFCTN_DT, -- DATE | NOT NULL | FOR C VERIFICATION CODES, THIS IS THE DATE THAT THE DATA VALUE WAS VERIFIED. FOR U VERIFICATION CODES, THIS IS THE DATE THAT THE DATA VALUE WAS POPULATED INTO THE HCIDEA DATABASE. VERIFICATION CODE X INDICATES THE DATA IS NOT RECOGNIZED
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA_DEA_WVR"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrHcideaDeaWvrExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
