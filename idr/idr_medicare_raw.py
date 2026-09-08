"""
IDR Medicare provider-identity crosswalk — claims-derived, NO patient data.

Derives the distinct set of provider identifiers and service-location addresses seen
on one window of Medicare professional claims in IDR (V2_MDCR_CLM joined to
V2_MDCR_CLM_LINE_PRFNL for the place-of-service address). Every claim contributes each
of its provider NPIs (attending, billing, rendering, other, operating, facility, and
the resolved service/attending/billing/operating/other provider NPIs), each paired
with the claim's billing TIN (CLM_BLG_PRVDR_TAX_NUM), CCN/OSCAR
(CLM_BLG_PRVDR_OSCAR_NUM and the full CLM_BLG_PRVDR_FULL_CCN_NUM), and the line's POS
provider address. The output is the DISTINCT (NPI + role, TIN, CCN, address) tuple —
one row per distinct provider-identity/address combination over the window.

NO PATIENT DATA: this extract deliberately carries no beneficiary identifier of any
kind — no MBI, no beneficiary surrogate key (GEO_BENE_SK), no per-claim / per-encounter
row. GEO_BENE_SK and CLM_DT_SGNTR_SK are used only to join the claim line to its claim
header and are never projected. The result is de-identified, provider-level data:
provider NPIs are public NPPES, CCN/TIN are provider business identifiers, and the
addresses are provider service locations. (TIN can be a sole proprietor's individual
tax id — it is provider PII, requested explicitly, and is not patient data.)

All the scaffolding — config, auth, connection, claim window, and the
COPY → GET → optional S3 → REMOVE user-stage relay — lives in idr_export_common.py.
This file keeps only the SQL and the run_export() call that wires it up.

Local (laptop) run — picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with Medicare claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicare_raw.py

Row grain / volume: SELECT DISTINCT collapses to unique provider-identity/address
tuples, so this is far smaller than a per-claim extract. The unload keeps SINGLE=TRUE
because the common runner GETs the stage file by exact name; if COPY ever errors on
the 5 GB single-file cap, narrow the window with CLAIM_WINDOW_MONTHS.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import MAX_SINGLE_FILE_BYTES, run_export


# ============================================================================
# MEDICARE PROVIDER-IDENTITY QUERY (claims-derived, no patient data)
# ============================================================================

def build_raw_sql(stage_target, start_sql, end_sql, min_bene):  # noqa: ARG001 (min_bene unused — no patient counts)
    """
    COPY INTO @~/<file>.csv the distinct provider-identity rows derived from one
    window of Medicare professional claims: one row per distinct (provider NPI + role,
    billing TIN, CCN/OSCAR, full CCN, POS address). No beneficiary data of any kind.
    One uncompressed, headered CSV (SINGLE=TRUE).

    min_bene is unused (no patient-count / small-cell logic here).
    """
    return f"""
COPY INTO {stage_target}
FROM (

WITH joined_claims AS (
    SELECT
        -- provider billing identifiers (carried onto every NPI role below)
        CLAIM.CLM_BLG_PRVDR_TAX_NUM,
        CLAIM.CLM_BLG_PRVDR_OSCAR_NUM,
        CLAIM.CLM_BLG_PRVDR_FULL_CCN_NUM,

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

    -- GEO_BENE_SK / CLM_DT_SGNTR_SK are join keys only; never projected (no patient data).
    JOIN IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM AS CLAIM
        ON CLINE.GEO_BENE_SK = CLAIM.GEO_BENE_SK
       AND CLINE.CLM_DT_SGNTR_SK = CLAIM.CLM_DT_SGNTR_SK

    WHERE CLAIM.CLM_THRU_DT >= DATE '{start_sql}'
      AND CLAIM.CLM_THRU_DT <  DATE '{end_sql}'
),

-- Long format: each provider-NPI slot on the claim becomes its own row, tagged with
-- the role it was drawn from, carrying the claim's billing identifiers and the POS
-- address unchanged.
claim_npis AS (
    SELECT 'CLM_ATNDG'  AS NPI_ROLE, CLM_ATNDG_PRVDR_NPI_NUM   AS NPI, jc.* EXCLUDE (
        CLM_ATNDG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM, CLM_RNDRG_PRVDR_NPI_NUM,
        CLM_OTHR_PRVDR_NPI_NUM, CLM_OPRTG_PRVDR_NPI_NUM, CLM_FAC_PRVDR_NPI_NUM,
        PRVDR_SRVC_PRVDR_NPI_NUM, PRVDR_ATNDG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM,
        PRVDR_OPRTG_PRVDR_NPI_NUM, PRVDR_OTHR_PRVDR_NPI_NUM)
    FROM joined_claims jc
    UNION ALL
    SELECT 'CLM_BLG',    CLM_BLG_PRVDR_NPI_NUM,   jc.* EXCLUDE (
        CLM_ATNDG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM, CLM_RNDRG_PRVDR_NPI_NUM,
        CLM_OTHR_PRVDR_NPI_NUM, CLM_OPRTG_PRVDR_NPI_NUM, CLM_FAC_PRVDR_NPI_NUM,
        PRVDR_SRVC_PRVDR_NPI_NUM, PRVDR_ATNDG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM,
        PRVDR_OPRTG_PRVDR_NPI_NUM, PRVDR_OTHR_PRVDR_NPI_NUM)
    FROM joined_claims jc
    UNION ALL
    SELECT 'CLM_RNDRG',  CLM_RNDRG_PRVDR_NPI_NUM, jc.* EXCLUDE (
        CLM_ATNDG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM, CLM_RNDRG_PRVDR_NPI_NUM,
        CLM_OTHR_PRVDR_NPI_NUM, CLM_OPRTG_PRVDR_NPI_NUM, CLM_FAC_PRVDR_NPI_NUM,
        PRVDR_SRVC_PRVDR_NPI_NUM, PRVDR_ATNDG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM,
        PRVDR_OPRTG_PRVDR_NPI_NUM, PRVDR_OTHR_PRVDR_NPI_NUM)
    FROM joined_claims jc
    UNION ALL
    SELECT 'CLM_OTHR',   CLM_OTHR_PRVDR_NPI_NUM,  jc.* EXCLUDE (
        CLM_ATNDG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM, CLM_RNDRG_PRVDR_NPI_NUM,
        CLM_OTHR_PRVDR_NPI_NUM, CLM_OPRTG_PRVDR_NPI_NUM, CLM_FAC_PRVDR_NPI_NUM,
        PRVDR_SRVC_PRVDR_NPI_NUM, PRVDR_ATNDG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM,
        PRVDR_OPRTG_PRVDR_NPI_NUM, PRVDR_OTHR_PRVDR_NPI_NUM)
    FROM joined_claims jc
    UNION ALL
    SELECT 'CLM_OPRTG',  CLM_OPRTG_PRVDR_NPI_NUM, jc.* EXCLUDE (
        CLM_ATNDG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM, CLM_RNDRG_PRVDR_NPI_NUM,
        CLM_OTHR_PRVDR_NPI_NUM, CLM_OPRTG_PRVDR_NPI_NUM, CLM_FAC_PRVDR_NPI_NUM,
        PRVDR_SRVC_PRVDR_NPI_NUM, PRVDR_ATNDG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM,
        PRVDR_OPRTG_PRVDR_NPI_NUM, PRVDR_OTHR_PRVDR_NPI_NUM)
    FROM joined_claims jc
    UNION ALL
    SELECT 'CLM_FAC',    CLM_FAC_PRVDR_NPI_NUM,   jc.* EXCLUDE (
        CLM_ATNDG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM, CLM_RNDRG_PRVDR_NPI_NUM,
        CLM_OTHR_PRVDR_NPI_NUM, CLM_OPRTG_PRVDR_NPI_NUM, CLM_FAC_PRVDR_NPI_NUM,
        PRVDR_SRVC_PRVDR_NPI_NUM, PRVDR_ATNDG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM,
        PRVDR_OPRTG_PRVDR_NPI_NUM, PRVDR_OTHR_PRVDR_NPI_NUM)
    FROM joined_claims jc
    UNION ALL
    SELECT 'PRVDR_SRVC',  PRVDR_SRVC_PRVDR_NPI_NUM,  jc.* EXCLUDE (
        CLM_ATNDG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM, CLM_RNDRG_PRVDR_NPI_NUM,
        CLM_OTHR_PRVDR_NPI_NUM, CLM_OPRTG_PRVDR_NPI_NUM, CLM_FAC_PRVDR_NPI_NUM,
        PRVDR_SRVC_PRVDR_NPI_NUM, PRVDR_ATNDG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM,
        PRVDR_OPRTG_PRVDR_NPI_NUM, PRVDR_OTHR_PRVDR_NPI_NUM)
    FROM joined_claims jc
    UNION ALL
    SELECT 'PRVDR_ATNDG', PRVDR_ATNDG_PRVDR_NPI_NUM, jc.* EXCLUDE (
        CLM_ATNDG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM, CLM_RNDRG_PRVDR_NPI_NUM,
        CLM_OTHR_PRVDR_NPI_NUM, CLM_OPRTG_PRVDR_NPI_NUM, CLM_FAC_PRVDR_NPI_NUM,
        PRVDR_SRVC_PRVDR_NPI_NUM, PRVDR_ATNDG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM,
        PRVDR_OPRTG_PRVDR_NPI_NUM, PRVDR_OTHR_PRVDR_NPI_NUM)
    FROM joined_claims jc
    UNION ALL
    SELECT 'PRVDR_BLG',   PRVDR_BLG_PRVDR_NPI_NUM,   jc.* EXCLUDE (
        CLM_ATNDG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM, CLM_RNDRG_PRVDR_NPI_NUM,
        CLM_OTHR_PRVDR_NPI_NUM, CLM_OPRTG_PRVDR_NPI_NUM, CLM_FAC_PRVDR_NPI_NUM,
        PRVDR_SRVC_PRVDR_NPI_NUM, PRVDR_ATNDG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM,
        PRVDR_OPRTG_PRVDR_NPI_NUM, PRVDR_OTHR_PRVDR_NPI_NUM)
    FROM joined_claims jc
    UNION ALL
    SELECT 'PRVDR_OPRTG', PRVDR_OPRTG_PRVDR_NPI_NUM, jc.* EXCLUDE (
        CLM_ATNDG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM, CLM_RNDRG_PRVDR_NPI_NUM,
        CLM_OTHR_PRVDR_NPI_NUM, CLM_OPRTG_PRVDR_NPI_NUM, CLM_FAC_PRVDR_NPI_NUM,
        PRVDR_SRVC_PRVDR_NPI_NUM, PRVDR_ATNDG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM,
        PRVDR_OPRTG_PRVDR_NPI_NUM, PRVDR_OTHR_PRVDR_NPI_NUM)
    FROM joined_claims jc
    UNION ALL
    SELECT 'PRVDR_OTHR',  PRVDR_OTHR_PRVDR_NPI_NUM,  jc.* EXCLUDE (
        CLM_ATNDG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM, CLM_RNDRG_PRVDR_NPI_NUM,
        CLM_OTHR_PRVDR_NPI_NUM, CLM_OPRTG_PRVDR_NPI_NUM, CLM_FAC_PRVDR_NPI_NUM,
        PRVDR_SRVC_PRVDR_NPI_NUM, PRVDR_ATNDG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM,
        PRVDR_OPRTG_PRVDR_NPI_NUM, PRVDR_OTHR_PRVDR_NPI_NUM)
    FROM joined_claims jc
)

SELECT DISTINCT
    NPI_ROLE,
    NPI,
    CLM_BLG_PRVDR_TAX_NUM        AS TIN,
    CLM_BLG_PRVDR_OSCAR_NUM      AS CCN_OSCAR,
    CLM_BLG_PRVDR_FULL_CCN_NUM   AS CCN_FULL,
    CLM_POS_PRVDR_1ST_LINE_ADR,
    CLM_POS_PRVDR_2ND_LINE_ADR,
    CLM_POS_PRVDR_CITY_NAME,
    CLM_POS_PRVDR_USPS_STATE_CD,
    CLM_POS_PRVDR_ZIP5_CD,
    CLM_POS_PRVDR_ZIP4_CD
FROM claim_npis
WHERE NPI IS NOT NULL
  AND TRIM(NPI) NOT IN ('', '~')

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
        banner="IDR Medicare provider-identity crosswalk (claims-derived, no patient data)",
        file_prefix="idr_medicare_raw",
        sql_builder=build_raw_sql,
        min_bene_label="(unused — no patient counts)",
    ))
