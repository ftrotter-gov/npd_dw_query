"""
==========
V2_MDCR_PRVDR_OF_SRVC_HHA_ASC_HOSPC_CD IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_OF_SRVC_HHA_ASC_HOSPC_CD

Table Type: VIEW
Columns: 7
Source Pattern: %mdcr_prvdr%
Table Comment: IDENTIFIES THE TYPE OF PROVIDER PARTICIPATING IN THE MEDICARE/MEDICAID PROGRAM.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrOfSrvcHhaAscHospcCdExporter()
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


class V2MdcrPrvdrOfSrvcHhaAscHospcCdExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_OF_SRVC_HHA_ASC_HOSPC_CD data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_OF_SRVC_HHA_ASC_HOSPC_CD (VIEW)
    Columns: 7
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_of_srvc_hha_asc_hospc_cd_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_OF_SRVC_HHA_ASC_HOSPC_CD export.
        
        Includes all 7 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_OF_SRVC_HHA_ASC_HOSPC_CD, -- TEXT(3) | NOT NULL | A CODE IDENTIFYING THE TYPE OF PROVIDER PARTICIPATING IN THE MEDICARE/MEDICAID PROGRAM.
                PRVDR_OF_SRVC_HHA_ASC_HOSPC_DESC, -- TEXT(200) | NOT NULL | THE DESCRIPTION OF THE CODE IDENTIFYING THE TYPE OF PROVIDER PARTICIPATING IN THE MEDICARE/MEDICAID PROGRAM.
                IDR_INSRT_TS, -- TIMESTAMP_NTZ | NOT NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHILE PERFORMING AN INSERT OPERATION.
                IDR_UPDT_TS, -- TIMESTAMP_NTZ | NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHEN UPDATES ARE MADE TO ANY NON-PRIMARY KEY COLUMN.
                META_SRC_SK, -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                META_SRC_PRCSG_ID, -- NUMBER(38) | NOT NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS INSERTED.
                META_LTST_SRC_PRCSG_ID -- NUMBER(38) | NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS SUBSEQUENTLY UPDATED.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_OF_SRVC_HHA_ASC_HOSPC_CD"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrOfSrvcHhaAscHospcCdExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
