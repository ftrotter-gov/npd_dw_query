"""
==========
V2_MDCR_PRVDR_DMEPOS_SPCLTY IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_DMEPOS_SPCLTY

Table Type: VIEW
Columns: 6
Source Pattern: %mdcr_prvdr%
Table Comment: SPECIALITY CODES ASSOCIATED TO AN INDIVIDUAL DMEPOS (DURABLE MEDICAL EQUIPMENT, PROSTHETICS, AND ORTHOTICS SUPPLIES) PROVIDER

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrDmeposSpcltyExporter()
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


class V2MdcrPrvdrDmeposSpcltyExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_DMEPOS_SPCLTY data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_DMEPOS_SPCLTY (VIEW)
    Columns: 6
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_dmepos_spclty_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_DMEPOS_SPCLTY export.
        
        Includes all 6 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_SK, -- NUMBER(18) | NOT NULL | AN IDR ASSIGNED SURROGATE KEY USED TO IDENTIFY A PARTY ENGAGED IN ACTIVITY RELATED TO CMS.
                PRVDR_DMEPOS_NUM, -- TEXT(13) | NOT NULL | A DURABLE MEDICAL EQUIPMENT, PROSTHETICS, ORTHOTICS, AND SUPPLIES (DMEPOS) NUMBER ASSIGNED TO A PROVIDER BY A MEDICARE ADMINISTRATIVE CONTRACTOR (MAC).
                PRVDR_LGCY_ADR_TYPE_CD, -- TEXT(1) | NOT NULL | INDICATES THE TYPE OF ADDRESS FROM THE LEGACY SYSTEM: 1 = MASTER 2 = REMITTANCE 3 = CHECK 4 = MSP 5 = MR 6 = OTHER 7 = PAYEE B = BILLING M = MAILING P = PRACTICE
                PRVDR_NPI_DMEPOS_SPCLTY_CD, -- TEXT(2) | NOT NULL | NOT DEFINED, BECAUSE THIS COLUMN IS CURRENTLY NOT POPULATED IN THE IDR AND THE DATA IS NOT PROVIDED BY THE SOURCE.
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_DMEPOS_SPCLTY"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrDmeposSpcltyExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
