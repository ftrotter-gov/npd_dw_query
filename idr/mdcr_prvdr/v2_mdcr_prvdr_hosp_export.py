"""
==========
V2_MDCR_PRVDR_HOSP IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HOSP

Table Type: VIEW
Columns: 19
Source Pattern: %mdcr_prvdr%
Table Comment: THE HOSPITAL TYPE CHILD RECORD IS CREATED WHEN “HOSPITAL” IS SELECTED AS THE PROVIDER TYPE ON THE CMS 855A MEDICARE ENROLLMENT FORM, OR WHEN “HOSPITAL DEPARTMENT(S)” IS SELECTED AS THE SUPPLIER TYPE ON A CMS 855B MEDICARE ENROLLMENT FORM.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrHospExporter()
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


class V2MdcrPrvdrHospExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_HOSP data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HOSP (VIEW)
    Columns: 19
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_hosp_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_HOSP export.
        
        Includes all 19 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_HOSP_TYPE_ACUTE_SW, -- TEXT(1) | NOT NULL | AN INDICATION A HOSPITAL SUBGROUP OR UNIT IS ACUTE CARE.
                PRVDR_HOSP_TYPE_CHLDRNS_SW, -- TEXT(1) | NOT NULL | AN INDICATION A HOSPITAL SUBGROUP OR UNIT IS CHILDRENS (EXCLUDED FROM PPS).
                PRVDR_HOSP_TYPE_GNRL_SW, -- TEXT(1) | NOT NULL | AN INDICATION A HOSPITAL SUBGROUP OR UNIT IS GENERAL.
                PRVDR_HOSP_TYPE_IPF_SW, -- TEXT(1) | NOT NULL | AN INDICATION A HOSPITAL SUBGROUP OR UNIT IS PSYCHIATRIC.
                PRVDR_HOSP_TYPE_LT_SW, -- TEXT(1) | NOT NULL | AN INDICATION A HOSPITAL SUBGROUP OR UNIT IS LONG TERM (EXCLUDED FROM PPS).
                PRVDR_HOSP_TYPE_OTHR_DESC, -- TEXT(60) | NOT NULL | AN INDICATION A HOSPITAL SUBGROUP OR UNIT IS OTHER SPECIFY.
                PRVDR_HOSP_TYPE_OTHR_SW, -- TEXT(1) | NOT NULL | AN INDICATION A HOSPITAL SUBGROUP OR UNIT IS OTHER.
                PRVDR_HOSP_TYPE_PSYCH_SW, -- TEXT(1) | NOT NULL | AN INDICATION A HOSPITAL SUBGROUP OR UNIT IS PSYCHIATRIC (EXCLUDED FROM PPS).
                PRVDR_HOSP_TYPE_REHAB_SW, -- TEXT(1) | NOT NULL | AN INDICATION A HOSPITAL SUBGROUP OR UNIT IS REHABILIATION (EXCLUDED FROM PPS).
                PRVDR_HOSP_TYPE_SB_SW, -- TEXT(1) | NOT NULL | AN INDICATION A HOSPITAL SUBGROUP OR UNIT IS SWING-BED APPROVED.
                PRVDR_HOSP_TYPE_SS_SW, -- TEXT(1) | NOT NULL | AN INDICATION A HOSPITAL SUBGROUP OR UNIT IS SHORT-TERM (GENERAL AND SPECIALTY).
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_PAC_ID, -- TEXT(10) | NOT NULL
                PRVDR_PECOS_SK, -- NUMBER(38) | NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_ENRLMT_CREAT_DT, -- DATE | NOT NULL | DATE THE RECORD WAS CREATED (MM/DD/YYYY)
                PRVDR_ENRLMT_CNTRCTR_ID, -- TEXT(5) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A MEDICARE CONTRACTOR.
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | THE SYSTEM GENERATED PECOS ASSOCIATE CONTROL ID.
                PRVDR_RPT_SW -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HOSP"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrHospExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
