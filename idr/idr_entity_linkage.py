"""
SQL to get one year of affiliation data from IDR, ending two months before run date.
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

WITH claims_base AS (
    SELECT
        clm.CLM_UNIQ_ID,
        clm.CLM_BLG_PRVDR_TAX_NUM,
        clm.CLM_BLG_PRVDR_OSCAR_NUM,
        clm.CLM_BENE_MBI_ID,
        clm.CLM_BLG_PRVDR_NPI_NUM,
        clm.PRVDR_BLG_PRVDR_NPI_NUM,
        clm.CLM_ATNDG_PRVDR_NPI_NUM,
        clm.CLM_OPRTG_PRVDR_NPI_NUM,
        clm.CLM_OTHR_PRVDR_NPI_NUM,
        clm.CLM_RFRG_PRVDR_NPI_NUM,
        clm.CLM_RNDRG_PRVDR_NPI_NUM,
        clm.CLM_SRVC_PRVDR_NPI_NUM,
        clm.PRVDR_RFRG_PRVDR_NPI_NUM,
        clm.PRVDR_ATNDG_PRVDR_NPI_NUM,
        clm.PRVDR_OPRTG_PRVDR_NPI_NUM,
        clm.PRVDR_OTHR_PRVDR_NPI_NUM,
        clm.PRVDR_RNDRNG_PRVDR_NPI_NUM,
        clm.PRVDR_PRSCRBNG_PRVDR_NPI_NUM,
        clm.PRVDR_SRVC_PRVDR_NPI_NUM
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM AS clm
    WHERE clm.CLM_FROM_DT >= DATE '{claim_window_start_date_sql}'
      AND clm.CLM_FROM_DT < DATE '{claim_window_end_date_sql}'
      AND clm.CLM_FINL_ACTN_IND = 'Y'
),
org_npi_long AS (
    SELECT
        CLM_UNIQ_ID,
        CASE
            WHEN CLM_BLG_PRVDR_TAX_NUM IS NULL
              OR TRIM(CLM_BLG_PRVDR_TAX_NUM) IN ('', '~', '000000000')
                THEN NULL
            ELSE TRIM(CLM_BLG_PRVDR_TAX_NUM)
        END AS CLM_BLG_PRVDR_TAX_NUM,
        TRIM(CLM_BLG_PRVDR_OSCAR_NUM) AS CLM_BLG_PRVDR_OSCAR_NUM,
        CLM_BENE_MBI_ID,
        TRIM(CLM_BLG_PRVDR_NPI_NUM) AS org_npi
    FROM claims_base
    WHERE CLM_BLG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_BLG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CASE
            WHEN CLM_BLG_PRVDR_TAX_NUM IS NULL
              OR TRIM(CLM_BLG_PRVDR_TAX_NUM) IN ('', '~', '000000000')
                THEN NULL
            ELSE TRIM(CLM_BLG_PRVDR_TAX_NUM)
        END AS CLM_BLG_PRVDR_TAX_NUM,
        TRIM(CLM_BLG_PRVDR_OSCAR_NUM) AS CLM_BLG_PRVDR_OSCAR_NUM,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_BLG_PRVDR_NPI_NUM) AS org_npi
    FROM claims_base
    WHERE PRVDR_BLG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_BLG_PRVDR_NPI_NUM) NOT IN ('', '~')
),
personal_npi_long AS (
    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_ATNDG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_ATNDG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_ATNDG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_OPRTG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_OPRTG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_OPRTG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_OTHR_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_OTHR_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_OTHR_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_RFRG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_RFRG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_RFRG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_RNDRG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_RNDRG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_RNDRG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_SRVC_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_SRVC_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_SRVC_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_RFRG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_RFRG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_RFRG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_ATNDG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_ATNDG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_ATNDG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_OPRTG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_OPRTG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_OPRTG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_OTHR_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_OTHR_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_OTHR_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_RNDRNG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_RNDRNG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_RNDRNG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_PRSCRBNG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_PRSCRBNG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_PRSCRBNG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_SRVC_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_SRVC_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_SRVC_PRVDR_NPI_NUM) NOT IN ('', '~')
),
relationship_claims AS (
    SELECT DISTINCT
        org.CLM_BLG_PRVDR_TAX_NUM,
        org.CLM_BLG_PRVDR_OSCAR_NUM,
        org.org_npi,
        person.personal_npi,
        org.CLM_BENE_MBI_ID
    FROM org_npi_long AS org
    INNER JOIN personal_npi_long AS person
        ON org.CLM_UNIQ_ID = person.CLM_UNIQ_ID
    WHERE org.CLM_BLG_PRVDR_OSCAR_NUM IS NOT NULL
      AND org.CLM_BLG_PRVDR_OSCAR_NUM NOT IN ('', '~')
)

SELECT
    CLM_BLG_PRVDR_TAX_NUM,
    CLM_BLG_PRVDR_OSCAR_NUM,
    org_npi,
    personal_npi,
    COUNT(DISTINCT CLM_BENE_MBI_ID) AS cnt_bene
FROM relationship_claims
GROUP BY
    CLM_BLG_PRVDR_TAX_NUM,
    CLM_BLG_PRVDR_OSCAR_NUM,
    org_npi,
    personal_npi
HAVING COUNT(DISTINCT CLM_BENE_MBI_ID) > 10



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
