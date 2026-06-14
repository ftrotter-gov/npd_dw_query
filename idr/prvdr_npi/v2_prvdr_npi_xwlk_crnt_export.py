"""
==========
V2_PRVDR_NPI_XWLK_CRNT IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_NPI_XWLK_CRNT

Table Type: VIEW
Columns: 11
Source Pattern: %prvdr_npi%
Table Comment: THIS VIEW REPRESENTS A CURRENT SNAPSHOT OF A CROSSWALK OF A NATIONAL PROVIDER IDENTIFIER (NPI) TO THEIR CORRESPONDING HEALTH CARE PROVIDERS OTHER IDENTIFICATION NUMBER RECEIVED FROM THE NATIONAL PLAN AND PROVIDER ENUMERATION SYSTEM (NPPES).

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2PrvdrNpiXwlkCrntExporter()
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


class V2PrvdrNpiXwlkCrntExporter(IDROutputter):
    """
    Exports V2_PRVDR_NPI_XWLK_CRNT data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_NPI_XWLK_CRNT (VIEW)
    Columns: 11
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_prvdr_npi_xwlk_crnt_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_PRVDR_NPI_XWLK_CRNT export.
        
        Includes all 11 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_NPI_NUM, -- TEXT(10) | NOT NULL | A NATIONAL PROVIDER IDENTIFIER (NPI) UNIQUELY ASSIGNED FOR COVERED HEALTH CARE PROVIDERS.
                PRVDR_ID, -- TEXT(20) | NOT NULL | A DATA ELEMENT TO CAPTURE THE VARIOUS WAYS USED TO DISTINGUISH PROVIDERS FROM ONE ANOTHER ON CLAIMS AND OTHER INTERACTIONS BETWEEN PROVIDERS AND OTHER ENTITIES.
                PRVDR_GEO_STATE_NATL_TXT, -- TEXT(10) | NOT NULL | A CODE IDENTIFYING A HEALTHCARE COMMON PROCEDURE CODING SYSTEM (HCPCS) PROCEDURE, SUPPLY, PRODUCT, OR SERVICE PROVIDED TO A MEDICARE BENEFICIARY OR AN INDIVIDUAL ENROLLED IN PRIVATE HEALTH INSURANCE PROGRAMS. REFERENCE TABLE: HCPCS_CD
                PRVDR_ID_TYPE_CD, -- TEXT(2) | NULL | A CODE IDENTIFYING THE TYPE OF PROVIDER IDENTIFIER. FOR EXAMPLE: 01 = NATIONAL PROVIDER IDENTIFIER (NPI) 09 = NATIONAL SUPPLIER CLEARINGHOUSE (NSC)
                PRVDR_ID_TYPE_SHRT_DESC, -- TEXT(25) | NULL | A DESCRIPTION OF A CODE IDENTIFYING THE TYPE OF PROVIDER IDENTIFIER.
                PRVDR_ID_TYPE_DESC, -- TEXT(100) | NULL | A DESCRIPTION OF A CODE IDENTIFYING THE TYPE OF PROVIDER IDENTIFIER.
                META_SRC_SK, -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                META_SRC_PRCSG_ID, -- NUMBER(38) | NOT NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS INSERTED.
                META_LTST_SRC_PRCSG_ID, -- NUMBER(38) | NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS SUBSEQUENTLY UPDATED.
                IDR_INSRT_TS, -- TIMESTAMP_NTZ | NOT NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHILE PERFORMING AN INSERT OPERATION.
                IDR_UPDT_TS -- TIMESTAMP_NTZ | NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHEN UPDATES ARE MADE TO ANY NON-PRIMARY KEY COLUMN.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_NPI_XWLK_CRNT"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2PrvdrNpiXwlkCrntExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
