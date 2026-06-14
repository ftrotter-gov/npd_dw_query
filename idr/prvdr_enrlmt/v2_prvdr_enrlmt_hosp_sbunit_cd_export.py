"""
==========
V2_PRVDR_ENRLMT_HOSP_SBUNIT_CD IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENRLMT_HOSP_SBUNIT_CD

Table Type: VIEW
Columns: 7
Source Pattern: %prvdr_enrlmt%

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2PrvdrEnrlmtHospSbunitCdExporter()
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


class V2PrvdrEnrlmtHospSbunitCdExporter(IDROutputter):
    """
    Exports V2_PRVDR_ENRLMT_HOSP_SBUNIT_CD data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENRLMT_HOSP_SBUNIT_CD (VIEW)
    Columns: 7
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_prvdr_enrlmt_hosp_sbunit_cd_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_PRVDR_ENRLMT_HOSP_SBUNIT_CD export.
        
        Includes all 7 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_ENRLMT_HOSP_SBUNIT_CD, -- TEXT(3) | NOT NULL | A UNIQUE VALUE THAT IDENTIFIES THE SUBGROUP OR UNIT ASSOCIATED TO A HOSPITAL PROVIDER. REFERENCE TABLE: PRVDR_PECOS_ENRLMT_HOSP_SBUNIT_CD
                PRVDR_ENRLMT_HOSP_SBUNIT_DESC, -- TEXT(200) | NULL | A DESCRIPTION OF A UNIQUE VALUE THAT IDENTIFIES THE SUBGROUP OR UNIT ASSOCIATED TO A HOSPITAL PROVIDER.
                IDR_INSRT_TS, -- TIMESTAMP_NTZ | NOT NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHILE PERFORMING AN INSERT OPERATION.
                IDR_UPDT_TS, -- TIMESTAMP_NTZ | NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHEN UPDATES ARE MADE TO ANY NON-PRIMARY KEY COLUMN.
                META_SRC_SK, -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                META_SRC_PRCSG_ID, -- NUMBER(38) | NOT NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS INSERTED.
                META_LTST_SRC_PRCSG_ID -- NUMBER(38) | NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS SUBSEQUENTLY UPDATED.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENRLMT_HOSP_SBUNIT_CD"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2PrvdrEnrlmtHospSbunitCdExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
