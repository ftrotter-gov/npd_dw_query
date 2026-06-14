"""
==========
V2_MDCR_PRVDR_PSF_TYPE_CD IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PSF_TYPE_CD

Table Type: VIEW
Columns: 6
Source Pattern: %mdcr_prvdr%
Table Comment: A TYPE OF PROVIDER AS DEFINED IN THE PROVIDER SPECIFIC FILE.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrPsfTypeCdExporter()
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


class V2MdcrPrvdrPsfTypeCdExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_PSF_TYPE_CD data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PSF_TYPE_CD (VIEW)
    Columns: 6
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_psf_type_cd_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_PSF_TYPE_CD export.
        
        Includes all 6 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_PSF_PRVDR_TYPE_CD, -- TEXT(2) | NOT NULL | AN IDENTIFIER OF A TYPE OF PROVIDER AS DEFINED IN THE PROVIDER SPECIFIC FILE. NOTE: PROVIDER TYPE VALUES 49-54 REFER TO SPECIAL UNIT DESIGNATIONS THAT ARE ASSIGNED TO THE THIRD POSITION OF THE OSCAR NUMBER
                PRVDR_PSF_PRVDR_TYPE_DESC, -- TEXT(300) | NULL | DESCRIPTION OF WHAT THE PROVIDER SPECIFIC FILE PROVIDER TYPE CODE VALUE REPRESENTS.
                PRVDR_PSF_PRVDR_TYPE_EFCTV_DT, -- DATE | NOT NULL | THE FIRST DATE ON WHICH THE PROVIDER TYPE CODE VALUE IS VALID.
                PRVDR_PSF_PRVDR_TYPE_OBSLT_DT, -- DATE | NOT NULL | THE DATE UPON WHICH THE PROVIDER TYPE CODE VALUE IS NO LONGER VALID.
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PSF_TYPE_CD"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrPsfTypeCdExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
