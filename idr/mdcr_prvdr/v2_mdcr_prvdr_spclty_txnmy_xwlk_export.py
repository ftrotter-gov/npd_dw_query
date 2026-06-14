"""
==========
V2_MDCR_PRVDR_SPCLTY_TXNMY_XWLK IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SPCLTY_TXNMY_XWLK

Table Type: VIEW
Columns: 9
Source Pattern: %mdcr_prvdr%
Table Comment: A CROSSWALK OF A PROVIDER OR SUPPLIER’S MEDICARE SPECIALTY CODE TO THE APPROPRIATE HEALTHCARE PROVIDER TAXONOMY CODE.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrSpcltyTxnmyXwlkExporter()
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


class V2MdcrPrvdrSpcltyTxnmyXwlkExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_SPCLTY_TXNMY_XWLK data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SPCLTY_TXNMY_XWLK (VIEW)
    Columns: 9
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_spclty_txnmy_xwlk_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_SPCLTY_TXNMY_XWLK export.
        
        Includes all 9 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_SPCLTY_CD, -- TEXT(2) | NOT NULL | A CODE IDENTIFYING THE CENTERS FOR MEDICARE AND MEDICAID SERVICES (CMS) SPECIALTY OF A PROVIDER OR SUPPLIER. FOR EXAMPLE: 11 = INTERNAL MEDICINE 49 = AMBULATORY SURGICAL CENTER REFERENCE TABLE: CLM_PRVDR_SPCLTY_CD
                PRVDR_SPCLTY_CD_DESC, -- TEXT(500) | NULL
                PRVDR_TXNMY_CD, -- TEXT(10) | NOT NULL | A CODE IDENTIFYING THE TYPE, CLASSIFICATION, AND/OR SPECIALIZATION OF A PROVIDER. FOR EXAMPLE: 207R00000X = INTERNAL MEDICINE 3416A0800X = AMBULANCE AIR TRANSPORT REFERENCE TABLE: PRVDR_NCPDP_TXNMY_CD
                PRVDR_TXNMY_CD_DESC, -- TEXT(602) | NULL
                META_LTST_SRC_PRCSG_ID, -- NUMBER(38) | NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS SUBSEQUENTLY UPDATED.
                META_SRC_PRCSG_ID, -- NUMBER(38) | NOT NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS INSERTED.
                META_SRC_SK, -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                IDR_INSRT_TS, -- TIMESTAMP_NTZ | NOT NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHILE PERFORMING AN INSERT OPERATION.
                IDR_UPDT_TS -- TIMESTAMP_NTZ | NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHEN UPDATES ARE MADE TO ANY NON-PRIMARY KEY COLUMN.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SPCLTY_TXNMY_XWLK"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrSpcltyTxnmyXwlkExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
