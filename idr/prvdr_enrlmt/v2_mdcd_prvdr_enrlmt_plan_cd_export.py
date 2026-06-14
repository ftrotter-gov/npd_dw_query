"""
==========
V2_MDCD_PRVDR_ENRLMT_PLAN_CD IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_PRVDR_ENRLMT_PLAN_CD

Table Type: VIEW
Columns: 10
Source Pattern: %prvdr_enrlmt%
Table Comment: A PLAN CLASSIFICATION THAT DESCRIBES THE PROVIDER IS ENROLLED IN MEDICAID OR CHILDRENS HEALTH INSURANCE PROGRAM (CHIP) OR BOTH.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcdPrvdrEnrlmtPlanCdExporter()
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


class V2MdcdPrvdrEnrlmtPlanCdExporter(IDROutputter):
    """
    Exports V2_MDCD_PRVDR_ENRLMT_PLAN_CD data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_PRVDR_ENRLMT_PLAN_CD (VIEW)
    Columns: 10
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcd_prvdr_enrlmt_plan_cd_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCD_PRVDR_ENRLMT_PLAN_CD export.
        
        Includes all 10 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_MDCD_ENRLMT_PLAN_CD, -- TEXT(1) | NOT NULL | A CODE ASSIGNED BY THE SOURCE SYSTEM TO IDENTIFY THE MEDICAID OR CHILDRENS HEALTH INSURANCE PROGRAM (CHIP) PLAN THAT THE PROVIDER IS ENROLLED.
                PRVDR_MDCD_ENRLMT_PLAN_DESC, -- TEXT(500) | NULL | A DESCRIPTION OF THE CODE ASSIGNED BY THE SOURCE SYSTEM TO IDENTIFY THE MEDICAID OR CHILDRENS HEALTH INSURANCE PROGRAM (CHIP) PLAN THAT THE PROVIDER IS ENROLLED.
                META_SRC_SK, -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                META_SRC_PRCSG_ID, -- NUMBER(38) | NOT NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS INSERTED.
                META_LTST_SRC_PRCSG_ID, -- NUMBER(38) | NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS SUBSEQUENTLY UPDATED.
                IDR_INSRT_TS, -- TIMESTAMP_NTZ | NOT NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHILE PERFORMING AN INSERT OPERATION.
                IDR_UPDT_TS, -- TIMESTAMP_NTZ | NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHEN UPDATES ARE MADE TO ANY NON-PRIMARY KEY COLUMN.
                IDR_LTST_TRANS_FLG, -- TEXT(1) | NOT NULL | AN INDICATOR ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) THAT IDENTIFIES WHICH TRANSACTION RECORD, BASED ON PRIMARY KEY, IS CONSIDERED TO REPRESENT THE MOST RECENT RECORD RECEIVED FROM THE SOURCE. Y = LATEST VERSION OF THE RECORD N = PREVIOUS VERSION OF THE RECORD
                IDR_TRANS_EFCTV_TS, -- TIMESTAMP_NTZ | NOT NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) IDENTIFYING WHEN A RECORD IS LOADED.
                IDR_TRANS_OBSLT_TS -- TIMESTAMP_NTZ | NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHEN A RECORD WAS LAST KNOWN TO BE PRESENT IN THE SOURCE. THE CURRENT VERSION OF A RECORD WILL BE SET TO 12/31/9999 00:00:00.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_PRVDR_ENRLMT_PLAN_CD"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcdPrvdrEnrlmtPlanCdExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
