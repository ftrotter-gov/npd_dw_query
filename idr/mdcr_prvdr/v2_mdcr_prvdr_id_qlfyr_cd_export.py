"""
==========
V2_MDCR_PRVDR_ID_QLFYR_CD IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_ID_QLFYR_CD

Table Type: VIEW
Columns: 5
Source Pattern: %mdcr_prvdr%
Table Comment: THE DOMAIN OF PROVIDER IDENTIFIER CODES AND PROVIDES DESCRIPTIVE TEXT FOR EACH CODE.  INDICATES HOW THE PROVIDER FOR A CLAIM WAS IDENTIFIED, SUCH AS BY NCPDP, NPI, FEDERAL LICENSE NUMBER, ETC..

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrIdQlfyrCdExporter()
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


class V2MdcrPrvdrIdQlfyrCdExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_ID_QLFYR_CD data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_ID_QLFYR_CD (VIEW)
    Columns: 5
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_id_qlfyr_cd_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_ID_QLFYR_CD export.
        
        Includes all 5 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_ID_QLFYR_CD, -- TEXT(2) | NOT NULL | THE TYPE OF DATA USED TO IDENTIFY THE SERVICE PROVIDER OF THE CLAIM: 01 = NPI 07 = NCPDP NUMBER 08 = STATE LICENSE NUMBER 11 = FEDERAL TAX NUMBER 12 = DEA
                PRVDR_ID_QLFYR_CD_DESC, -- TEXT(100) | NULL | TEXT DESCRIPTION OF THE DATA USED TO IDENTIFY THE PROVIDER FOR A CLAIM.
                PRVDR_SRC_ID, -- TEXT(5) | NULL | UNIQUE IDENTIFIER OF A SOURCE.
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_ID_QLFYR_CD"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrIdQlfyrCdExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
