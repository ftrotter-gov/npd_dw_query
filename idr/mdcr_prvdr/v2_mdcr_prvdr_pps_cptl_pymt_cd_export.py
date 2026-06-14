"""
==========
V2_MDCR_PRVDR_PPS_CPTL_PYMT_CD IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PPS_CPTL_PYMT_CD

Table Type: VIEW
Columns: 4
Source Pattern: %mdcr_prvdr%
Table Comment: A TYPE OF CAPITAL PAYMENT METHODOLOGY UNDER THE PROSPECTIVE PAYMENT SYSTEM FOR HOSPITALS:  A = HOLD HARMLESS – COST PAYMENT FOR OLD CAPITAL  B = HOLD HARMLESS – 100% FEDERAL RATE  C = FULLY PROSPECTIVE BLENDED RATE

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrPpsCptlPymtCdExporter()
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


class V2MdcrPrvdrPpsCptlPymtCdExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_PPS_CPTL_PYMT_CD data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PPS_CPTL_PYMT_CD (VIEW)
    Columns: 4
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_pps_cptl_pymt_cd_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_PPS_CPTL_PYMT_CD export.
        
        Includes all 4 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_PPS_CPTL_PYMT_CD, -- TEXT(1) | NOT NULL | AN IDENTIFIER OF A CAPITAL PAYMENT METHODOLOGY UNDER THE PROSPECTIVE PAYMENT SYSTEM FOR HOSPITALS.
                PRVDR_PPS_CPTL_PYMT_DESC, -- TEXT(200) | NULL | THE DESCRIPTION OF WHAT THE PROVIDER PROSPECTIVE PAYMENT SYSTEM CAPITAL PAYMENT CODE VALUE REPRESENTS.
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PPS_CPTL_PYMT_CD"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrPpsCptlPymtCdExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
