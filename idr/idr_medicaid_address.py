"""
IDR Medicaid provider-address export — SQL for provider service-location addresses.

Derives provider service-location addresses from one year of Medicaid claims in
IDR (V2_MDCD_CLM). Every claim contributes its admitting, billing, supervising and
service-location-org NPI, each paired with the claim's service-location address and
the recipient's State Medicaid ID; the result is aggregated per (NPI, address) with
the count of distinct Medicaid recipients and suppressed below a small-cell
threshold. See build_address_sql() for the query.

All the scaffolding — config, auth, connection, claim window, and the
COPY → GET → optional S3 → REMOVE user-stage relay — lives in idr_export_common.py
(run there for the auth precedence, env vars, and run instructions). This file
keeps only the SQL and the run_export() call that wires it up.

Local (laptop) run — picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with Medicaid claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicaid_address.py

NOTE (carried over from the source query, deliberately unchanged): the SELECT and
GROUP BY keep YEAR(CLM_THRU_DT) AS claim_year. With a rolling window that spans two
calendar years, a single (NPI, address) can emit up to two rows and the small-cell
suppression is applied per calendar-year half. Drop claim_year from the SELECT and
GROUP BY if you want exactly one row per (NPI, address) over the full window.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import MAX_SINGLE_FILE_BYTES, run_export


# ============================================================================
# MEDICAID ADDRESS QUERY
# ============================================================================

def build_address_sql(stage_target, start_sql, end_sql, min_bene):
    """
    COPY INTO @~/<file>.csv the provider service-location addresses seen on one
    window of Medicaid claims. Each claim contributes its admitting, billing,
    supervising and service-location-org NPI, each paired with the claim's
    service-location address and the recipient's State Medicaid ID; the output is
    (claim_year, NPI, address) with the count of distinct recipients, suppressed
    at > min_bene. One uncompressed, headered CSV (SINGLE=TRUE).

    BUG FIXES vs. the Snowsight source:
      * window: the source hardcoded YEAR(CLM_THRU_DT) = 2026, ignoring the
        computed rolling window; this filters CLM_THRU_DT to [start, end).
      * output name: caller writes @~/idr_medicaid_address.* (the source reused
        the entity-linkage name, which collides with that extract on the stage
        and in the CSV merger's filename-root grouping).
    Upstream improvements kept: recipient key CLM_RCPNT_STATE_MDCD_ID (was the
    Medicare-only CLM_BENE MBI, which restricted counts to dual-eligibles) and
    the supervising-provider NPI union branch.
    """
    return f"""
COPY INTO {stage_target}
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
  AND CLM_THRU_DT >= DATE '{start_sql}'
  AND CLM_THRU_DT <  DATE '{end_sql}'
GROUP BY
    YEAR(CLM_THRU_DT),
    NPI,
    CLM_SRVC_LCTN_LINE_1_ADR,
    CLM_SRVC_LCTN_LINE_2_ADR,
    CLM_SRVC_LCTN_CITY_NAME,
    CLM_SRVC_LCTN_STATE_CD,
    CLM_SRVC_LCTN_ZIP_CD
HAVING COUNT(DISTINCT CLM_RCPNT_STATE_MDCD_ID) > {min_bene}

)
FILE_FORMAT = (
  TYPE = CSV
  FIELD_DELIMITER = ','
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  COMPRESSION = NONE
)
HEADER = TRUE
SINGLE = TRUE
MAX_FILE_SIZE = {MAX_SINGLE_FILE_BYTES}
OVERWRITE = TRUE
DETAILED_OUTPUT = FALSE
"""


if __name__ == "__main__":
    sys.exit(run_export(
        banner="IDR Medicaid provider-address export",
        file_prefix="idr_medicaid_address",
        sql_builder=build_address_sql,
        min_bene_label="Min distinct recipients",
    ))
