"""
==========
V2_PRVDR_ENMRT_RACE_ETHNCTY_CRNT IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENMRT_RACE_ETHNCTY_CRNT

Table Type: VIEW
Columns: 8
Source Pattern: %prvdr_enmrt%
Table Comment: AN ENUMERATED PROVIDER'S RACE AND ETHNICITY. A PROVIDER CAN SELECT MULTIPLE RACES AND ETHNICITIES. CURRENTLY POPULATED BY THE NATIONAL PLAN AND PROVIDER ENUMERATION SYSTEM (NPPES).

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2PrvdrEnmrtRaceEthnctyCrntExporter()
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


class V2PrvdrEnmrtRaceEthnctyCrntExporter(IDROutputter):
    """
    Exports V2_PRVDR_ENMRT_RACE_ETHNCTY_CRNT data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENMRT_RACE_ETHNCTY_CRNT (VIEW)
    Columns: 8
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_prvdr_enmrt_race_ethncty_crnt_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_PRVDR_ENMRT_RACE_ETHNCTY_CRNT export.
        
        Includes all 8 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_NPI_NUM, -- TEXT(10) | NOT NULL | A NATIONAL PROVIDER IDENTIFIER (NPI) UNIQUELY ASSIGNED FOR COVERED HEALTH CARE PROVIDERS.
                RACE_ETHNCTY_CTGRY_CD_DESC, -- TEXT(250) | NULL | A DESCRIPTION OF THE CODE IDENTIFYING THE OFFICE OF INFORMATION AND REGULATORY AFFAIRS, OFFICE OF MANAGEMENT AND BUDGET, EXECUTIVE OFFICE OF THE PRESIDENT (OMB) MINIMUM RACE OR ETHNICITY CATEGORY.
                RACE_ETHNCTY_CD_DESC, -- TEXT(250) | NULL | A DESCRIPTION OF THE CODE IDENTIFYING AN INDIVIDUAL'S RACE OR ETHNICITY. THE DESCRIPTIONS FOLLOW GUIDANCE FROM THE OFFICE OF INFORMATION AND REGULATORY AFFAIRS, OFFICE OF MANAGEMENT AND BUDGET, EXECUTIVE OFFICE OF THE PRESIDENT (OMB).
                META_SRC_SK, -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                META_SRC_PRCSG_ID, -- NUMBER(38) | NOT NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS INSERTED.
                META_LTST_SRC_PRCSG_ID, -- NUMBER(38) | NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS SUBSEQUENTLY UPDATED.
                IDR_INSRT_TS, -- TIMESTAMP_NTZ | NOT NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHILE PERFORMING AN INSERT OPERATION.
                IDR_UPDT_TS -- TIMESTAMP_NTZ | NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHEN UPDATES ARE MADE TO ANY NON-PRIMARY KEY COLUMN.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENMRT_RACE_ETHNCTY_CRNT"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2PrvdrEnmrtRaceEthnctyCrntExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
