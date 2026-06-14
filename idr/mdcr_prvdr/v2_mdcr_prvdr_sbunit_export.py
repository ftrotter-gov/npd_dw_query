"""
==========
V2_MDCR_PRVDR_SBUNIT IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SBUNIT

Table Type: VIEW
Columns: 12
Source Pattern: %mdcr_prvdr%
Table Comment: THE SUBUNIT CONSOLIDATION CHILD RECORD IS CREATED WHEN THE END USER ENTERS CONSOLIDATION INFORMATION FOR SUBUNITS IN PECOS FOR DEPARTMENTS THAT MERGE INTO ONE ORGANIZATION.

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrSbunitExporter()
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


class V2MdcrPrvdrSbunitExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_SBUNIT data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SBUNIT (VIEW)
    Columns: 12
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_sbunit_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_SBUNIT export.
        
        Includes all 12 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_MDCR_ID, -- TEXT(15) | NOT NULL | UNIQUE MEDICARE IDENTIFIER OF SUB-UNIT OF THE PROVIDER THAT HAS SEPARATE MEDICARE IDENTIFICATION NUMBERS BUT HAVE NOT ENTERED INTO SEPARATE PROVIDER AGREEMENTS.
                PRVDR_MDCR_ID_TYPE_CD, -- TEXT(2) | NULL | UNIQUE VALUE THAT IDENTIFIES THE TYPE OF IDENTIFICATION NUMBER THAT CAN BE ASSIGNED TO MEDICAID OR MEDICARE PROVIDER.
                PRVDR_SBUNIT_DEPT_NAME, -- TEXT(70) | NULL | NAME OF SUB-UNIT OF THE PROVIDER THAT HAS A SEPARATE MEDICARE IDENTIFICATION NUMBER BUT HAS NOT ENTERED INTO SEPARATE PROVIDER AGREEMENTS, SUCH AS PPS EXCLUDED SWING BED UNITS OF A HOSPITAL.
                PRVDR_SK, -- NUMBER(18) | NOT NULL | AN IDR ASSIGNED SURROGATE KEY USED TO IDENTIFY A PARTY ENGAGED IN ACTIVITY RELATED TO CMS.
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK, -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
                PRVDR_PECOS_SK, -- NUMBER(38) | NULL | A UNIQUE IDENTIFIER ASSIGNED BY IDR
                PRVDR_ENRLMT_CNTRCTR_ID, -- TEXT(5) | NOT NULL | UNIQUE NUMBER THAT IDENTIFIES A MEDICARE CONTRACTOR.
                PRVDR_ENRLMT_CREAT_DT, -- DATE | NOT NULL | DATE THE RECORD WAS CREATED (MM/DD/YYYY)
                PRVDR_PAC_ID, -- TEXT(10) | NOT NULL | THE SYSTEM GENERATED PECOS ASSOCIATE CONTROL ID.
                PRVDR_ENRLMT_ID, -- TEXT(15) | NOT NULL | PECOS SYSTEM GENERATED ENROLLMENT IDENTIFIER.
                PRVDR_RPT_SW -- TEXT(1) | NULL | AN INDICATION THAT THERE IS A UNIQUENESS PROBLEM IN THE SOURCE DATA
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_SBUNIT"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrSbunitExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
