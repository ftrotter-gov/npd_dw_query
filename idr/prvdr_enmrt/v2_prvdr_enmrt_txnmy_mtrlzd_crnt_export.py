"""
==========
V2_PRVDR_ENMRT_TXNMY_MTRLZD_CRNT IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENMRT_TXNMY_MTRLZD_CRNT

Table Type: VIEW
Columns: 18
Source Pattern: %prvdr_enmrt%

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2PrvdrEnmrtTxnmyMtrlzdCrntExporter()
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


class V2PrvdrEnmrtTxnmyMtrlzdCrntExporter(IDROutputter):
    """
    Exports V2_PRVDR_ENMRT_TXNMY_MTRLZD_CRNT data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENMRT_TXNMY_MTRLZD_CRNT (VIEW)
    Columns: 18
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_prvdr_enmrt_txnmy_mtrlzd_crnt_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_PRVDR_ENMRT_TXNMY_MTRLZD_CRNT export.
        
        Includes all 18 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_NPI_NUM, -- TEXT(10) | NOT NULL
                PRVDR_PRMRY_TXNMY_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_1_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_2_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_3_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_4_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_5_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_6_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_7_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_8_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_9_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_10_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_11_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_12_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_13_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_14_CD, -- TEXT(10) | NULL
                PRVDR_TXNMY_15_CD, -- TEXT(10) | NULL
                META_SRC_SK -- NUMBER(38) | NOT NULL
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENMRT_TXNMY_MTRLZD_CRNT"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2PrvdrEnmrtTxnmyMtrlzdCrntExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
