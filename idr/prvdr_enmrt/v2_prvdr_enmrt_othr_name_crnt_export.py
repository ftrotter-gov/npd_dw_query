"""
==========
V2_PRVDR_ENMRT_OTHR_NAME_CRNT IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENMRT_OTHR_NAME_CRNT

Table Type: VIEW
Columns: 21
Source Pattern: %prvdr_enmrt%
Table Comment: A COMPILATION OF ALTERNATE CONTACT INFORMATION USED TO LINK A NATIONAL PROVIDER IDENTIFIER (NPI) WITH THE ORGANIZATION OR INDIVIDUAL NAME OF THE ENUMERATED PROVIDER.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2PrvdrEnmrtOthrNameCrntExporter()
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


class V2PrvdrEnmrtOthrNameCrntExporter(IDROutputter):
    """
    Exports V2_PRVDR_ENMRT_OTHR_NAME_CRNT data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENMRT_OTHR_NAME_CRNT (VIEW)
    Columns: 21
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_prvdr_enmrt_othr_name_crnt_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_PRVDR_ENMRT_OTHR_NAME_CRNT export.
        
        Includes all 21 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_NPI_NUM, -- TEXT(10) | NOT NULL | A NATIONAL PROVIDER IDENTIFIER (NPI) UNIQUELY ASSIGNED FOR COVERED HEALTH CARE PROVIDERS.
                NAME_ROLE_CD, -- TEXT(2) | NOT NULL | AN INTEGRATED DATA REPOSITORY (IDR) DERIVED CODE IDENTIFYING THE ROLE TYPE FOR A NAME SENT . REFERENCE TABLE: NAME_ROLE_CD
                NAME_ROLE_DESC, -- TEXT(500) | NULL | A DESCRIPTION OF A CODE IDENTIFYING THE ROLE TYPE FOR A NAME SENT.
                NAME_TYPE_CD, -- TEXT(2) | NOT NULL | A CODE IDENTIFYING ANOTHER TYPE OF NAME USED. REFERENCE TABLE: NAME_TYPE_CD
                NAME_TYPE_DESC, -- TEXT(500) | NULL | A DESCRIPTION OF A CODE IDENTIFYING ANOTHER TYPE OF NAME USED.
                PRVDR_PREX_NAME, -- TEXT(20) | NULL | A DESIGNATION INDICATING EITHER THE SEX OR MARITAL STATUS OF THE INDIVIDUAL.
                PRVDR_1ST_NAME, -- TEXT(35) | NULL | A PERSONAL NAME THAT IDENTIFIES THE INDIVIDUAL THAT PRECEDES THE LAST NAME.
                PRVDR_MDL_NAME, -- TEXT(20) | NULL | A PERSONAL NAME THAT IDENTIFIES THE INDIVIDUAL THAT IS PLACED AFTER THE FIRST NAME AND BEFORE THE SURNAME
                PRVDR_LAST_NAME, -- TEXT(35) | NULL | A SURNAME OF THE INDIVIDUAL.
                PRVDR_SFX_NAME, -- TEXT(20) | NULL | AN IDENTIFIER OF A PHRASE AT THE END OF A NAME THAT FURTHER DESCRIBES AN INDIVIDUAL, E.G.JR, SR, ETC.
                ORG_NAME, -- TEXT(100) | NULL | AN OFFICIAL NAME UNDER WHICH A BUSINESS OPERATES AND HOLDS ITSELF OUT TO THE PUBLIC.
                CRDNTL_TXT, -- TEXT(20) | NULL | A UNIQUE VALUE IDENTIFYING A QUALIFICATION, ACHIEVEMENT, QUALITY, OR ASPECT OF A PERSONS BACKGROUND, ESPECIALLY WHEN USED TO INDICATE THEIR SUITABILITY FOR SOMETHING.
                TITLE_NAME, -- TEXT(35) | NULL | A DESIGNATION ASSOCIATED WITH THE INDIVIDUAL.
                PHNE_NUM, -- TEXT(20) | NULL | A NUMBER THAT REPRESENTS THE TELEPHONE NUMBER OF THE ENTITY OR PERSON.
                PHNE_EXTNSN_NUM, -- TEXT(5) | NULL | A 5 DIGIT NUMBER IN ADDITION TO THE TELEPHONE NUMBER OF THE ENTITY OR PERSON.
                EMAIL_ADR, -- TEXT(100) | NULL | AN ELECTRONIC MAILING ADDRESS USED TO ELECTRONICALLY COMMUNICATE WITH THE ENTITY OR PERSON.
                META_SRC_SK, -- NUMBER(38) | NOT NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                META_SRC_PRCSG_ID, -- NUMBER(38) | NOT NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS INSERTED.
                META_LTST_SRC_PRCSG_ID, -- NUMBER(38) | NULL | A VALUE ASSIGNED BASED ON A BATCH IDENTIFICATION IN ORDER TO TRACE IT BACK TO ITS ORIGINAL SOURCE. IT WILL ONLY BE POPULATED WHEN A RECORD IS SUBSEQUENTLY UPDATED.
                IDR_INSRT_TS, -- TIMESTAMP_NTZ | NOT NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHILE PERFORMING AN INSERT OPERATION.
                IDR_UPDT_TS -- TIMESTAMP_NTZ | NULL | THE SYSTEM DATE AND TIME ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) WHEN UPDATES ARE MADE TO ANY NON-PRIMARY KEY COLUMN.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_PRVDR_ENMRT_OTHR_NAME_CRNT"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2PrvdrEnmrtOthrNameCrntExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
