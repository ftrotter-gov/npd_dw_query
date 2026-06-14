"""
==========
V2_MDCR_PRVDR_SPCLTY_TYPE_AUDT IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SPCLTY_TYPE_AUDT

Table Type: VIEW
Columns: 14
Source Pattern: %mdcr_prvdr%
Table Comment: AN AUDIT OF THE PROVIDER SPECIALTY TYPE INFORMATION.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrSpcltyTypeAudtExporter()
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


class V2MdcrPrvdrSpcltyTypeAudtExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_SPCLTY_TYPE_AUDT data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SPCLTY_TYPE_AUDT (VIEW)
    Columns: 14
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_spclty_type_audt_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_SPCLTY_TYPE_AUDT export.
        
        Includes all 14 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_SPCLTY_AUDT_CD, -- TEXT(2) | NULL | INDICATES THE SPECIALTIES OF A PROVIDER.
                PRVDR_PECOS_SK, -- NUMBER(38) | NOT NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_SPCLTY_AUDT_BGN_DT, -- DATE | NULL | INDICATES THE DATE THAT A SPECIALTY BECAME EFFECTIVE.
                PRVDR_SPCLTY_AUDT_END_DT, -- DATE | NOT NULL | INDICATES THE TERMINATION DATE OF A SPECIALTY.
                PRVDR_SPCLTY_AUDT_IND_CD, -- TEXT(1) | NOT NULL | INDICATOR IDENTIFYING CODES AS PRIMARY OR SECONDARY.
                META_SK, -- NUMBER(38) | NOT NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_RPT_AUDT_SW, -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
                PRVDR_DRVD_END_DT, -- DATE | NOT NULL | END DATE OF INPUT FILE
                PRVDR_SPCLTY_AUDT_CREAT_DT, -- DATE | NULL | DATE DATA WAS CREATED IN SOURCE
                PRVDR_SPCLTY_AUDT_UPDT_DT, -- DATE | NULL | DATE DATA WAS CORRECTED IN SOURCE
                PRVDR_SPCLTY_PRMRY_SW, -- TEXT(1) | NOT NULL | INDICATES WHETHER THE PHYSICIAN TYPE SPECIALTY IS A PRIMARY OR SECONDARY
                PRVDR_PAC_ID -- TEXT(10) | NULL | UNIQUE NUMBER THAT IDENTIFIES A PECOS ASSOCIATE.
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SPCLTY_TYPE_AUDT"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrSpcltyTypeAudtExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
