"""
IDR Medicaid provider-identity crosswalk — claims-derived, NO patient data.

Derives the distinct set of provider NPIs and service-location addresses seen on one
window of Medicaid claims in IDR (V2_MDCD_CLM). Every claim contributes each of its
provider NPIs (admitting, billing, supervising, and the service-location organization
NPI), each paired with the service-location address. The output is the DISTINCT
(NPI + role, address) tuple — one row per distinct provider/address combination over
the window.

NO PATIENT DATA: this extract deliberately carries no recipient identifier — the
Medicaid recipient id (CLM_RCPNT_STATE_MDCD_ID) is not projected. The result is
de-identified, provider-level data: provider NPIs are public NPPES and the addresses
are provider service locations.

CCN / TIN: V2_MDCD_CLM — unlike the Medicare V2_MDCR_CLM view — exposes no
billing-provider TIN or CCN/OSCAR column seen in this repo, so those provider
identifiers are absent here (the Medicare crosswalk carries them). Add them to the
SELECT if the view turns out to carry them under a different name.

All the scaffolding — config, auth, connection, claim window, and the
COPY → GET → optional S3 → REMOVE user-stage relay — lives in idr_export_common.py.
This file keeps only the SQL and the run_export() call that wires it up.

Local (laptop) run — picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with Medicaid claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicaid_raw.py

Row grain / volume: SELECT DISTINCT collapses to unique provider/address tuples, so
this is far smaller than a per-claim extract. The unload keeps SINGLE=TRUE because the
common runner GETs the stage file by exact name; if COPY ever errors on the 5 GB
single-file cap, narrow the window with CLAIM_WINDOW_MONTHS.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import MAX_SINGLE_FILE_BYTES, run_export


# ============================================================================
# MEDICAID PROVIDER-IDENTITY QUERY (claims-derived, no patient data)
# ============================================================================

def build_raw_sql(stage_target, start_sql, end_sql, min_bene):  # noqa: ARG001 (min_bene unused — no patient counts)
    """
    COPY INTO @~/<file>.csv the distinct provider-identity rows derived from one
    window of Medicaid claims: one row per distinct (provider NPI + role,
    service-location address). No recipient / patient data. One uncompressed, headered
    CSV (SINGLE=TRUE).

    min_bene is unused (no patient-count / small-cell logic here).
    """
    return f"""
COPY INTO {stage_target}
FROM (

WITH base_claims AS (
    SELECT
        CLM_ADMTG_PRVDR_NPI_NUM,
        CLM_BLG_PRVDR_NPI_NUM,
        CLM_SPRVSNG_PRVDR_NPI_NUM,
        CLM_SRVC_LCTN_ORG_NPI_NUM,

        CLM_SRVC_LCTN_LINE_1_ADR,
        CLM_SRVC_LCTN_LINE_2_ADR,
        CLM_SRVC_LCTN_CITY_NAME,
        CLM_SRVC_LCTN_STATE_CD,
        CLM_SRVC_LCTN_ZIP_CD

    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM

    WHERE CLM_THRU_DT >= DATE '{start_sql}'
      AND CLM_THRU_DT <  DATE '{end_sql}'
),

-- Long format: each provider-NPI slot on the claim becomes its own row, tagged with
-- the role it was drawn from, carrying the service-location address unchanged.
claim_npis AS (
    SELECT 'CLM_ADMTG'    AS NPI_ROLE, CLM_ADMTG_PRVDR_NPI_NUM    AS NPI, bc.* EXCLUDE (
        CLM_ADMTG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM,
        CLM_SPRVSNG_PRVDR_NPI_NUM, CLM_SRVC_LCTN_ORG_NPI_NUM)
    FROM base_claims bc
    UNION ALL
    SELECT 'CLM_BLG',      CLM_BLG_PRVDR_NPI_NUM,      bc.* EXCLUDE (
        CLM_ADMTG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM,
        CLM_SPRVSNG_PRVDR_NPI_NUM, CLM_SRVC_LCTN_ORG_NPI_NUM)
    FROM base_claims bc
    UNION ALL
    SELECT 'CLM_SPRVSNG',  CLM_SPRVSNG_PRVDR_NPI_NUM,  bc.* EXCLUDE (
        CLM_ADMTG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM,
        CLM_SPRVSNG_PRVDR_NPI_NUM, CLM_SRVC_LCTN_ORG_NPI_NUM)
    FROM base_claims bc
    UNION ALL
    SELECT 'CLM_SRVC_LCTN_ORG', CLM_SRVC_LCTN_ORG_NPI_NUM, bc.* EXCLUDE (
        CLM_ADMTG_PRVDR_NPI_NUM, CLM_BLG_PRVDR_NPI_NUM,
        CLM_SPRVSNG_PRVDR_NPI_NUM, CLM_SRVC_LCTN_ORG_NPI_NUM)
    FROM base_claims bc
)

SELECT DISTINCT
    NPI_ROLE,
    NPI,
    CLM_SRVC_LCTN_LINE_1_ADR,
    CLM_SRVC_LCTN_LINE_2_ADR,
    CLM_SRVC_LCTN_CITY_NAME,
    CLM_SRVC_LCTN_STATE_CD,
    CLM_SRVC_LCTN_ZIP_CD
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
        banner="IDR Medicaid provider-identity crosswalk (claims-derived, no patient data)",
        file_prefix="idr_medicaid_raw",
        sql_builder=build_raw_sql,
        min_bene_label="(unused — no patient counts)",
    ))
