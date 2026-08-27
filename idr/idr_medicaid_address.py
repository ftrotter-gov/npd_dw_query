"""
SQL to get last year of medicaid addresses
"""

# Note: you must have an appropriate role chosen and the IDRC_PRD_COMM_WH warehouse selected

# Import python packages
import streamlit as st # type: ignore
import pandas as pd
from calendar import monthrange
from datetime import date, datetime

# We can also use Snowpark for our analyses!
from snowflake.snowpark.context import get_active_session # type: ignore
session = get_active_session()

ts = datetime.now().strftime("%Y_%m_%d_%H%M")


def add_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


now = datetime.now()
# Use the latest stable claims window: one year ending two months before run date.
claim_window_end_date = add_months(now.date(), -2)
claim_window_start_date = add_months(claim_window_end_date, -12)
claim_window_start_date_sql = claim_window_start_date.isoformat()
claim_window_end_date_sql = claim_window_end_date.isoformat()

idr_entity_linkage_file_name = (
    f"@~/idr_entity_linkage.{claim_window_start_date:%Y_%m_%d}"
    f"_to_{claim_window_end_date:%Y_%m_%d}.csv"
)

idr_entity_linkage_sql = f"""
COPY INTO {idr_entity_linkage_file_name}
FROM (
WITH claim_npis AS (
    SELECT
        CLM_THRU_DT,
        CLM_ADMTG_PRVDR_NPI_NUM AS NPI,
        CLM_SRVC_LCTN_LINE_1_ADR,
        CLM_SRVC_LCTN_LINE_2_ADR,
        CLM_SRVC_LCTN_CITY_NAME,
        CLM_SRVC_LCTN_STATE_CD,
        CLM_SRVC_LCTN_ZIP_CD,
        CLM_RCPNT_STATE_MDCD_ID
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM

    UNION ALL

    SELECT
        CLM_THRU_DT,
        CLM_BLG_PRVDR_NPI_NUM AS NPI,
        CLM_SRVC_LCTN_LINE_1_ADR,
        CLM_SRVC_LCTN_LINE_2_ADR,
        CLM_SRVC_LCTN_CITY_NAME,
        CLM_SRVC_LCTN_STATE_CD,
        CLM_SRVC_LCTN_ZIP_CD,
        CLM_RCPNT_STATE_MDCD_ID
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM

    UNION ALL

    SELECT
        CLM_THRU_DT,
        CLM_SPRVSNG_PRVDR_NPI_NUM AS NPI,
        CLM_SRVC_LCTN_LINE_1_ADR,
        CLM_SRVC_LCTN_LINE_2_ADR,
        CLM_SRVC_LCTN_CITY_NAME,
        CLM_SRVC_LCTN_STATE_CD,
        CLM_SRVC_LCTN_ZIP_CD,
        CLM_RCPNT_STATE_MDCD_ID
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM

    UNION ALL    
    
    SELECT
        CLM_THRU_DT,
        CLM_SRVC_LCTN_ORG_NPI_NUM AS NPI,
        CLM_SRVC_LCTN_LINE_1_ADR,
        CLM_SRVC_LCTN_LINE_2_ADR,
        CLM_SRVC_LCTN_CITY_NAME,
        CLM_SRVC_LCTN_STATE_CD,
        CLM_SRVC_LCTN_ZIP_CD,
        CLM_RCPNT_STATE_MDCD_ID
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM
)

SELECT
    YEAR(CLM_THRU_DT) AS claim_year,
    NPI,
    CLM_SRVC_LCTN_LINE_1_ADR,
    CLM_SRVC_LCTN_LINE_2_ADR,
    CLM_SRVC_LCTN_CITY_NAME,
    CLM_SRVC_LCTN_STATE_CD,
    CLM_SRVC_LCTN_ZIP_CD,
    COUNT(DISTINCT CLM_RCPNT_STATE_MDCD_ID) AS DISTINCT_PATIENT_COUNT
FROM claim_npis
WHERE NPI IS NOT NULL
  AND CLM_RCPNT_STATE_MDCD_ID IS NOT NULL
  AND NULLIF(TRIM(CLM_SRVC_LCTN_LINE_1_ADR), '') IS NOT NULL
  AND NULLIF(TRIM(CLM_SRVC_LCTN_CITY_NAME), '') IS NOT NULL
  AND NULLIF(TRIM(CLM_SRVC_LCTN_STATE_CD), '') IS NOT NULL
  AND NULLIF(TRIM(CLM_SRVC_LCTN_ZIP_CD), '') IS NOT NULL
  AND YEAR(CLM_THRU_DT) = 2026
GROUP BY
    YEAR(CLM_THRU_DT),
    NPI,
    CLM_SRVC_LCTN_LINE_1_ADR,
    CLM_SRVC_LCTN_LINE_2_ADR,
    CLM_SRVC_LCTN_CITY_NAME,
    CLM_SRVC_LCTN_STATE_CD,
    CLM_SRVC_LCTN_ZIP_CD
HAVING COUNT(DISTINCT CLM_RCPNT_STATE_MDCD_ID) > 10




)""" + """
FILE_FORMAT = (
  TYPE = CSV
  FIELD_DELIMITER = ','
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  COMPRESSION = NONE
)
HEADER = TRUE
OVERWRITE = TRUE;
"""

session.sql(idr_entity_linkage_sql).collect()


# To download use: 
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../idr_data/ for idr_data/download_and_merge_all_snowflake_csv.sh which downloads the data from idr and then re-merges the csv files. 
