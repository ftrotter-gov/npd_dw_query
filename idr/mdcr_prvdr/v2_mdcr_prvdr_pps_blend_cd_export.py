"""
==========
V2_MDCR_PRVDR_PPS_BLEND_CD IDR Export (Auto-Generated)
==========

Auto-generated IDROutputter implementation for IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PPS_BLEND_CD

Table Type: VIEW
Columns: 5
Source Pattern: %mdcr_prvdr%
Table Comment: AN APPROPRIATE PERCENTAGE PAYMENT PERTAINING TO HOME HEALTH (HH) PROSPECTIVE PAYMENT SYSTEM RAPS, OR A BLEND RATIO BETWEEN FEDERAL AND FACILITY RATES.     HH PPS:   0 = PAY STANDARD PERCENTAGES  1 = PAY ZERO PERCENT    IRF PPS: ALL IRFS ARE 100% FEDERAL FOR COS

This script provides a complete IDROutputter subclass that exports all columns
from the table in their original Snowflake order. You can customize the
getSelectQuery() method to add WHERE clauses, JOINs, or modify column selection.

Usage:
    # In a Snowflake notebook environment:
    exporter = V2MdcrPrvdrPpsBlendCdExporter()
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


class V2MdcrPrvdrPpsBlendCdExporter(IDROutputter):
    """
    Exports V2_MDCR_PRVDR_PPS_BLEND_CD data using IDROutputter base class.
    
    Auto-generated from table metadata. Customize as needed for your specific requirements.
    
    Table: IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PPS_BLEND_CD (VIEW)
    Columns: 5
    """
    
    # Class properties
    version_number: str = "v01"
    file_name_stub: str = "v2_mdcr_prvdr_pps_blend_cd_idr_export"
    
    def getSelectQuery(self) -> str:
        """
        Returns the SELECT query for V2_MDCR_PRVDR_PPS_BLEND_CD export.
        
        Includes all 5 columns in their original Snowflake order.
        Customize this method to add WHERE clauses, JOINs, or modify column selection.
        """
        return """SELECT
                PRVDR_PPS_BLEND_CD, -- TEXT(1) | NOT NULL | AN IDENTIFIER OF AN APPROPRIATE PERCENTAGE PAYMENT TO BE MADE ON HOME HEALTH (HH) PROSPECTIVE PAYMENT SYSTEM RAPS, OR AN IDENTIFIER OF A BLEND RATIO BETWEEN FEDERAL AND FACILITY RATES. HH PPS: 0 = PAY STANDARD PERCENTAGES 1 = PAY ZERO PERCENT IRF PPS: ALL IRFS ARE 100% FEDERAL FOR COST REPORTING PERIODS BEGINNING ON OR AFTER 10/01/2002. LTCH PPS: 1= 20 (FEDERAL %); 80 (FACILITY %) 2= 40 (FEDERAL %); 60 (FACILITY %) 3= 60 (FEDERAL %); 40 (FACILITY %) 4= 80 (FEDERAL %); 20 (FACILITY %) 5= 100 (FEDERAL %); 00 (FACILITY %) IPF PPS: 1= 25 (FEDERAL %); 75 (FACILITY %) 2= 50 (FEDERAL %); 50 (FACILITY %) 3= 75 (FEDERAL %); 25 (FACILITY %) 4= 100 (FEDERAL %); 00 (FACILITY %)
                PRVDR_PSF_SRC_FIL_TYPE_CD, -- TEXT(3) | NOT NULL | INDICATES THE TYPE OF PROVIDER FILE.
                PRVDR_PPS_BLEND_DESC, -- TEXT(200) | NULL | DESCRIPTION OF WHAT THE FEDERAL PPS BLEND CODE VALUE REPRESENTS.
                META_SK, -- NUMBER(38) | NULL | A UNIQUE LEGACY NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR), FORMULATED WITH A DATE AND A 3-DIGIT SEQUENCE NUMBER, WHICH IDENTIFIES THE BATCH PROCESS THAT INITIALLY LOADED A ROW IN THE IDR. DUE TO THE LIMITATION OF A 3-DIGIT VALUE, THIS IS BEING REPLACED BY META_SRC_PRCSG_ID ON NEW IDR TABLES AS THE SOURCE DATA TRACKING STANDARD.
                META_SRC_SK -- NUMBER(38) | NULL | A UNIQUE NUMERIC VALUE ASSIGNED BY THE INTEGRATED DATA REPOSITORY (IDR) USED TO IDENTIFY THE SPECIFIC SOURCE OF THE DATA WHEN A ROW IS LOADED INTO THE IDR. REFERENCE TABLE: V2_MDCR_META_DCTNRY_SRC
            FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_PPS_BLEND_CD"""


if __name__ == '__main__':
    # Execute the export using the IDROutputter framework
    exporter = V2MdcrPrvdrPpsBlendCdExporter()
    exporter.do_idr_output()

# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
