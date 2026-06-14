"""
==========
V2_MDCR_PRVDR_IDTF_EQUIP IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_IDTF_EQUIP

Table Type: VIEW
Columns: 13
Source Pattern: %mdcr_prvdr%
Table Comment: THE IDTF EQUIPMENT CHILD RECORD CONTAINS INFORMATION GATHERED FROM ATTACHMENT 2 WHEN IDTF HAS BEEN SELECTED AS THE SUPPLIER TYPE ON CMS FORM 855B.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrIdtfEquipExporter()
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


class V2MdcrPrvdrIdtfEquipExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_IDTF_EQUIP data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_IDTF_EQUIP (VIEW)
    Columns: 13
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_idtf_equip_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_IDTF_EQUIP export.
        
        Includes all 13 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_IDTF_BGN_DT, -- DATE | NOT NULL | DATE THAT THE IDTF STARTED USING THE CPT-4 OR HCPCS EQUIPMENT
                PRVDR_IDTF_EQUIP_DESC, -- TEXT(60) | NULL | NAME AND TYPE OF EQUIPMENT USED TO PERFORM THE REPORTED CPT/HCPCS CODE.
                PRVDR_IDTF_EQUIP_MODEL_NUM, -- TEXT(20) | NOT NULL | A NUMBER IDENTIFYING THE MODEL OF THE INDEPENDENT DIAGNOSTIC TESTING FACILITY (IDTF) EQUIPMENT.
                PRVDR_IDTF_STD_CD, -- TEXT(1) | NULL | INDICATES WHETHER THE INDEPENDENT DIAGNOSTIC TESTING FACILITY MEETS ALL CURRENT CMS STANDARDS FOR IDTFS.
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_PAC_ID, -- TEXT(10) | NOT NULL
                PRVDR_PECOS_SK, -- NUMBER(38) | NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_ENRLMT_CNTRCTR_ID, -- TEXT(5) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A MEDICARE CONTRACTOR.
                PRVDR_ENRLMT_CREAT_DT, -- DATE | NOT NULL | DATE THE RECORD WAS CREATED (MM/DD/YYYY)
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_RPT_SW, -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
                PRVDR_IDTF_SRVC_DT -- DATE | NULL | DATE THE INDEPENDENT DIAGNOSTIC TESTING FACILITY COMMENCED SERVICE FOR IDTFS.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_IDTF_EQUIP"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrIdtfEquipExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
