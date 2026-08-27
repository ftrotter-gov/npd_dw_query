"""
IDR Medicare provider-address export — SQL for provider service-location addresses.

Derives provider service-location addresses from one year of Medicare professional
claims in IDR (V2_MDCR_CLM joined to V2_MDCR_CLM_LINE_PRFNL). Every claim contributes
its provider NPIs (attending, billing, rendering, operating, other, facility, and the
resolved service/attending/billing/operating/other provider NPIs), each paired with
the claim line's place-of-service provider address; the result is aggregated per
(NPI, address) with the count of distinct beneficiaries (GEO_BENE_SK) and suppressed
below a small-cell threshold. See build_address_sql() for the query.

All the scaffolding — config, auth, connection, claim window, and the
COPY → GET → optional S3 → REMOVE user-stage relay — lives in idr_export_common.py
(run there for the auth precedence, env vars, and run instructions). This file
keeps only the SQL and the run_export() call that wires it up.

Local (laptop) run — picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with Medicare claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicare_address.py

NOTE: the output grain is one row per (NPI, address) over the full window.
CLM_THRU_DT is carried through the CTEs only to filter the claim window in the WHERE
clause — it is not projected or grouped. Add YEAR(CLM_THRU_DT) AS claim_year to both
the SELECT and GROUP BY if you instead want per-calendar-year rows (small-cell
suppression then applies per year).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import MAX_SINGLE_FILE_BYTES, run_export


# ============================================================================
# MEDICARE ADDRESS QUERY
# ============================================================================

def build_address_sql(stage_target, start_sql, end_sql, min_bene):
    """
    COPY INTO @~/<file>.csv the provider service-location addresses seen on one
    window of Medicare professional claims. Each claim contributes its provider
    NPIs (attending, billing, rendering, operating, other, facility, and the
    resolved service/attending/billing/operating/other provider NPIs), each paired
    with the claim line's place-of-service provider address; the output is
    (NPI, address) with the count of distinct beneficiaries (GEO_BENE_SK),
    suppressed at > min_bene. One uncompressed, headered CSV (SINGLE=TRUE).

    BUG FIXES vs. the source:
      * CLM_THRU_DT was referenced by the outer SELECT/WHERE but never projected
        through joined_claims / claim_npis, so the query would not compile; it is
        now carried through the CTEs and used only in the WHERE window filter.
      * the claim-line NPI columns were qualified CLINE.PRVDR_*_NPI_NUM, which do
        not exist on V2_MDCR_CLM_LINE_PRFNL; those NPIs live on V2_MDCR_CLM and are
        now read from CLAIM.
      * output name: caller writes @~/idr_medicare_address.* (the source reused the
        Medicaid / entity-linkage name, which collides with those extracts on the
        stage and in the CSV merger's filename-root grouping).
    """
    return f"""
COPY INTO {stage_target}
FROM (


WITH joined_claims AS (
    SELECT
        CLAIM.GEO_BENE_SK,
        CLAIM.CLM_THRU_DT,

        CLAIM.CLM_ATNDG_PRVDR_NPI_NUM,
        CLAIM.CLM_BLG_PRVDR_NPI_NUM,
        CLAIM.CLM_RNDRG_PRVDR_NPI_NUM,
        CLAIM.CLM_OTHR_PRVDR_NPI_NUM,
        CLAIM.CLM_OPRTG_PRVDR_NPI_NUM,
        CLAIM.CLM_FAC_PRVDR_NPI_NUM,

        CLAIM.PRVDR_SRVC_PRVDR_NPI_NUM,
        CLAIM.PRVDR_ATNDG_PRVDR_NPI_NUM,
        CLAIM.PRVDR_BLG_PRVDR_NPI_NUM,
        CLAIM.PRVDR_OPRTG_PRVDR_NPI_NUM,
        CLAIM.PRVDR_OTHR_PRVDR_NPI_NUM,

        CLINE.CLM_POS_PRVDR_1ST_LINE_ADR,
        CLINE.CLM_POS_PRVDR_2ND_LINE_ADR,
        CLINE.CLM_POS_PRVDR_CITY_NAME,
        CLINE.CLM_POS_PRVDR_USPS_STATE_CD,
        CLINE.CLM_POS_PRVDR_ZIP5_CD,
        CLINE.CLM_POS_PRVDR_ZIP4_CD

    FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM_LINE_PRFNL AS CLINE

    JOIN IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM AS CLAIM
        ON CLINE.GEO_BENE_SK = CLAIM.GEO_BENE_SK
       AND CLINE.CLM_DT_SGNTR_SK = CLAIM.CLM_DT_SGNTR_SK
),

claim_npis AS (
    SELECT
        GEO_BENE_SK,
        CLM_THRU_DT,
        CLM_ATNDG_PRVDR_NPI_NUM AS NPI,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM joined_claims

    UNION ALL

    SELECT
        GEO_BENE_SK,
        CLM_THRU_DT,
        CLM_BLG_PRVDR_NPI_NUM AS NPI,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM joined_claims

    UNION ALL

    SELECT
        GEO_BENE_SK,
        CLM_THRU_DT,
        CLM_RNDRG_PRVDR_NPI_NUM AS NPI,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM joined_claims

    UNION ALL

    SELECT
        GEO_BENE_SK,
        CLM_THRU_DT,
        CLM_OTHR_PRVDR_NPI_NUM AS NPI,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM joined_claims

    UNION ALL

    SELECT
        GEO_BENE_SK,
        CLM_THRU_DT,
        CLM_OPRTG_PRVDR_NPI_NUM AS NPI,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM joined_claims

    UNION ALL

    SELECT
        GEO_BENE_SK,
        CLM_THRU_DT,
        CLM_FAC_PRVDR_NPI_NUM AS NPI,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM joined_claims

    UNION ALL

    SELECT
        GEO_BENE_SK,
        CLM_THRU_DT,
        PRVDR_SRVC_PRVDR_NPI_NUM AS NPI,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM joined_claims

    UNION ALL

    SELECT
        GEO_BENE_SK,
        CLM_THRU_DT,
        PRVDR_ATNDG_PRVDR_NPI_NUM AS NPI,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM joined_claims

    UNION ALL

    SELECT
        GEO_BENE_SK,
        CLM_THRU_DT,
        PRVDR_BLG_PRVDR_NPI_NUM AS NPI,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM joined_claims

    UNION ALL

    SELECT
        GEO_BENE_SK,
        CLM_THRU_DT,
        PRVDR_OPRTG_PRVDR_NPI_NUM AS NPI,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM joined_claims

    UNION ALL

    SELECT
        GEO_BENE_SK,
        CLM_THRU_DT,
        PRVDR_OTHR_PRVDR_NPI_NUM AS NPI,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM joined_claims
)

SELECT
    NPI,
    CLM_POS_PRVDR_1ST_LINE_ADR,
    CLM_POS_PRVDR_2ND_LINE_ADR,
    CLM_POS_PRVDR_CITY_NAME,
    CLM_POS_PRVDR_USPS_STATE_CD,
    CLM_POS_PRVDR_ZIP5_CD,
    CLM_POS_PRVDR_ZIP4_CD,
    COUNT(DISTINCT GEO_BENE_SK) AS DISTINCT_PATIENT_COUNT
FROM claim_npis
WHERE NPI IS NOT NULL
  AND GEO_BENE_SK IS NOT NULL
  AND NULLIF(TRIM(CLM_POS_PRVDR_1ST_LINE_ADR), '') IS NOT NULL
  AND NULLIF(TRIM(CLM_POS_PRVDR_CITY_NAME), '') IS NOT NULL
  AND NULLIF(TRIM(CLM_POS_PRVDR_USPS_STATE_CD), '') IS NOT NULL
  AND NULLIF(TRIM(CLM_POS_PRVDR_ZIP5_CD), '') IS NOT NULL
  AND CLM_THRU_DT >= DATE '{start_sql}'
  AND CLM_THRU_DT <  DATE '{end_sql}'
GROUP BY
    NPI,
    CLM_POS_PRVDR_1ST_LINE_ADR,
    CLM_POS_PRVDR_2ND_LINE_ADR,
    CLM_POS_PRVDR_CITY_NAME,
    CLM_POS_PRVDR_USPS_STATE_CD,
    CLM_POS_PRVDR_ZIP5_CD,
    CLM_POS_PRVDR_ZIP4_CD
HAVING COUNT(DISTINCT GEO_BENE_SK) > {min_bene}



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
        banner="IDR Medicare provider-address export",
        file_prefix="idr_medicare_address",
        sql_builder=build_address_sql,
        min_bene_label="Min distinct beneficiaries",
    ))
