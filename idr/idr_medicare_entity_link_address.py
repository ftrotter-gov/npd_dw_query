"""
IDR Medicare entity-linkage + address export -- org <-> individual-provider
affiliation graph enriched with place-of-service addresses.

Combines idr_entity_linkage.py and idr_medicare_address.py into a single
extract:

  * Derives the org <-> individual-provider affiliation graph the same way as
    idr_entity_linkage.py -- billing/OSCAR org NPIs joined to the personal NPIs
    that appear on the same claim (V2_MDCR_CLM), weighted by distinct
    beneficiaries and suppressed below a small-cell threshold.

  * Enriches each (org NPI, personal NPI) edge with the place-of-service
    address from the professional claim line (V2_MDCR_CLM_LINE_PRFNL),
    following the same join strategy as idr_medicare_address.py.

  Output grain: one row per
    (billing TIN, OSCAR, org NPI, personal NPI, address)
  with the count of distinct beneficiaries across the full claim window.

CONFIGURABLE DATE SPAN
  Edit CLAIM_WINDOW_MONTHS below to change the length of the look-back window.
  The window always ends CLAIM_WINDOW_LAG_MONTHS (2) months before today,
  so with the default of 24 it spans from ~26 months ago to ~2 months ago.

  Examples:
    CLAIM_WINDOW_MONTHS = 24   # two years   (default)
    CLAIM_WINDOW_MONTHS = 18   # 18 months
    CLAIM_WINDOW_MONTHS = 12   # one year

All other scaffolding -- config, auth, connection, and the COPY -> GET ->
  optional S3 -> REMOVE user-stage relay -- lives in idr_export_common.py.

Local (laptop) run -- picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicare_entity_link_address.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import (
    MAX_SINGLE_FILE_BYTES,
    load_config,
    compute_window,
    resolve_auth,
    connect,
    unload_to_stage,
    get_stage_file,
    upload_and_validate,
    remove_stage_file,
    log,
)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Number of months to look back in the claim window.
# The window ends 2 months before today and stretches back this many months.
# Change this number to adjust the span -- no other edits needed.
CLAIM_WINDOW_MONTHS = 24


# ============================================================================
# MERGED ENTITY-LINKAGE + ADDRESS QUERY
# ============================================================================

def build_entity_link_address_sql(stage_target, start_sql, end_sql, min_bene):
    """
    COPY INTO @~/<file>.csv the org <-> individual-provider affiliation edges
    enriched with place-of-service addresses, from one window of final-action
    Medicare professional claims.

    The query:
      1. claims_base       -- joins V2_MDCR_CLM to V2_MDCR_CLM_LINE_PRFNL so
                             every claim row carries both the provider NPI
                             columns (from the claim header) and the
                             place-of-service address fields (from the
                             professional line). Window filter is CLM_FROM_DT
                             with CLM_FINL_ACTN_IND='Y'.

      2. org_npi_long      -- unpivots the two org-NPI columns
                             (CLM_BLG_PRVDR_NPI_NUM, PRVDR_BLG_PRVDR_NPI_NUM)
                             into one row per (claim, org_npi), carrying TIN,
                             OSCAR, bene MBI, and the six address columns
                             through for later grouping.

      3. personal_npi_long -- unpivots all 13 personal-NPI columns into one
                             row per (claim, personal_npi). Only CLM_UNIQ_ID
                             is needed for the join back to org_npi_long.

      4. relationship_claims -- INNER JOIN org <-> personal on CLM_UNIQ_ID
                             (same claim), keeping only rows with a valid
                             OSCAR number and a non-blank address (street,
                             city, state, ZIP5 all required).

      5. Final SELECT      -- groups to (TIN, OSCAR, org_npi, personal_npi,
                             address), counts distinct beneficiaries, and
                             suppresses edges with <= min_bene distinct benes.

    One uncompressed, headered CSV (SINGLE=TRUE).
    """
    return f"""
COPY INTO {stage_target}
FROM (

WITH claims_base AS (
    SELECT
        CLAIM.CLM_UNIQ_ID,
        CLAIM.CLM_BLG_PRVDR_TAX_NUM,
        CLAIM.CLM_BLG_PRVDR_OSCAR_NUM,
        CLAIM.CLM_BENE_MBI_ID,

        -- org-level NPI columns (billing entity)
        CLAIM.CLM_BLG_PRVDR_NPI_NUM,
        CLAIM.PRVDR_BLG_PRVDR_NPI_NUM,

        -- personal (individual-provider) NPI columns
        CLAIM.CLM_ATNDG_PRVDR_NPI_NUM,
        CLAIM.CLM_OPRTG_PRVDR_NPI_NUM,
        CLAIM.CLM_OTHR_PRVDR_NPI_NUM,
        CLAIM.CLM_RFRG_PRVDR_NPI_NUM,
        CLAIM.CLM_RNDRG_PRVDR_NPI_NUM,
        CLAIM.CLM_SRVC_PRVDR_NPI_NUM,
        CLAIM.PRVDR_RFRG_PRVDR_NPI_NUM,
        CLAIM.PRVDR_ATNDG_PRVDR_NPI_NUM,
        CLAIM.PRVDR_OPRTG_PRVDR_NPI_NUM,
        CLAIM.PRVDR_OTHR_PRVDR_NPI_NUM,
        CLAIM.PRVDR_RNDRNG_PRVDR_NPI_NUM,
        CLAIM.PRVDR_PRSCRBNG_PRVDR_NPI_NUM,
        CLAIM.PRVDR_SRVC_PRVDR_NPI_NUM,

        -- place-of-service address from the professional claim line
        CLINE.CLM_POS_PRVDR_1ST_LINE_ADR,
        CLINE.CLM_POS_PRVDR_2ND_LINE_ADR,
        CLINE.CLM_POS_PRVDR_CITY_NAME,
        CLINE.CLM_POS_PRVDR_USPS_STATE_CD,
        CLINE.CLM_POS_PRVDR_ZIP5_CD,
        CLINE.CLM_POS_PRVDR_ZIP4_CD

    FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM AS CLAIM
    JOIN IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM_LINE_PRFNL AS CLINE
        ON CLINE.GEO_BENE_SK     = CLAIM.GEO_BENE_SK
       AND CLINE.CLM_DT_SGNTR_SK = CLAIM.CLM_DT_SGNTR_SK

    WHERE CLAIM.CLM_FROM_DT       >= DATE '{start_sql}'
      AND CLAIM.CLM_FROM_DT        < DATE '{end_sql}'
      AND CLAIM.CLM_FINL_ACTN_IND  = 'Y'
),

-- Org-NPI side: two billing NPI columns unpivoted.
-- Address columns are carried here so relationship_claims can group on them
-- without a second join to claims_base.
org_npi_long AS (
    SELECT
        CLM_UNIQ_ID,
        CASE
            WHEN CLM_BLG_PRVDR_TAX_NUM IS NULL
              OR TRIM(CLM_BLG_PRVDR_TAX_NUM) IN ('', '~', '000000000')
                THEN NULL
            ELSE TRIM(CLM_BLG_PRVDR_TAX_NUM)
        END AS CLM_BLG_PRVDR_TAX_NUM,
        TRIM(CLM_BLG_PRVDR_OSCAR_NUM)  AS CLM_BLG_PRVDR_OSCAR_NUM,
        CLM_BENE_MBI_ID,
        TRIM(CLM_BLG_PRVDR_NPI_NUM)    AS org_npi,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
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
        TRIM(CLM_BLG_PRVDR_OSCAR_NUM)  AS CLM_BLG_PRVDR_OSCAR_NUM,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_BLG_PRVDR_NPI_NUM)  AS org_npi,
        CLM_POS_PRVDR_1ST_LINE_ADR,
        CLM_POS_PRVDR_2ND_LINE_ADR,
        CLM_POS_PRVDR_CITY_NAME,
        CLM_POS_PRVDR_USPS_STATE_CD,
        CLM_POS_PRVDR_ZIP5_CD,
        CLM_POS_PRVDR_ZIP4_CD
    FROM claims_base
    WHERE PRVDR_BLG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_BLG_PRVDR_NPI_NUM) NOT IN ('', '~')
),

-- Personal-NPI side: 13 NPI columns unpivoted.
-- Each branch records both the NPI value (personal_npi) and the exact source
-- column name as a string literal (personal_npi_column_source), so every output
-- row identifies which field the NPI came from.
personal_npi_long AS (
    SELECT CLM_UNIQ_ID, TRIM(CLM_ATNDG_PRVDR_NPI_NUM)      AS personal_npi, 'CLM_ATNDG_PRVDR_NPI_NUM'      AS personal_npi_column_source FROM claims_base WHERE CLM_ATNDG_PRVDR_NPI_NUM      IS NOT NULL AND TRIM(CLM_ATNDG_PRVDR_NPI_NUM)      NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(CLM_OPRTG_PRVDR_NPI_NUM)      AS personal_npi, 'CLM_OPRTG_PRVDR_NPI_NUM'      AS personal_npi_column_source FROM claims_base WHERE CLM_OPRTG_PRVDR_NPI_NUM      IS NOT NULL AND TRIM(CLM_OPRTG_PRVDR_NPI_NUM)      NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(CLM_OTHR_PRVDR_NPI_NUM)       AS personal_npi, 'CLM_OTHR_PRVDR_NPI_NUM'       AS personal_npi_column_source FROM claims_base WHERE CLM_OTHR_PRVDR_NPI_NUM       IS NOT NULL AND TRIM(CLM_OTHR_PRVDR_NPI_NUM)       NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(CLM_RFRG_PRVDR_NPI_NUM)       AS personal_npi, 'CLM_RFRG_PRVDR_NPI_NUM'       AS personal_npi_column_source FROM claims_base WHERE CLM_RFRG_PRVDR_NPI_NUM       IS NOT NULL AND TRIM(CLM_RFRG_PRVDR_NPI_NUM)       NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(CLM_RNDRG_PRVDR_NPI_NUM)      AS personal_npi, 'CLM_RNDRG_PRVDR_NPI_NUM'      AS personal_npi_column_source FROM claims_base WHERE CLM_RNDRG_PRVDR_NPI_NUM      IS NOT NULL AND TRIM(CLM_RNDRG_PRVDR_NPI_NUM)      NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(CLM_SRVC_PRVDR_NPI_NUM)       AS personal_npi, 'CLM_SRVC_PRVDR_NPI_NUM'       AS personal_npi_column_source FROM claims_base WHERE CLM_SRVC_PRVDR_NPI_NUM       IS NOT NULL AND TRIM(CLM_SRVC_PRVDR_NPI_NUM)       NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(PRVDR_RFRG_PRVDR_NPI_NUM)     AS personal_npi, 'PRVDR_RFRG_PRVDR_NPI_NUM'     AS personal_npi_column_source FROM claims_base WHERE PRVDR_RFRG_PRVDR_NPI_NUM     IS NOT NULL AND TRIM(PRVDR_RFRG_PRVDR_NPI_NUM)     NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(PRVDR_ATNDG_PRVDR_NPI_NUM)    AS personal_npi, 'PRVDR_ATNDG_PRVDR_NPI_NUM'    AS personal_npi_column_source FROM claims_base WHERE PRVDR_ATNDG_PRVDR_NPI_NUM    IS NOT NULL AND TRIM(PRVDR_ATNDG_PRVDR_NPI_NUM)    NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(PRVDR_OPRTG_PRVDR_NPI_NUM)    AS personal_npi, 'PRVDR_OPRTG_PRVDR_NPI_NUM'    AS personal_npi_column_source FROM claims_base WHERE PRVDR_OPRTG_PRVDR_NPI_NUM    IS NOT NULL AND TRIM(PRVDR_OPRTG_PRVDR_NPI_NUM)    NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(PRVDR_OTHR_PRVDR_NPI_NUM)     AS personal_npi, 'PRVDR_OTHR_PRVDR_NPI_NUM'     AS personal_npi_column_source FROM claims_base WHERE PRVDR_OTHR_PRVDR_NPI_NUM     IS NOT NULL AND TRIM(PRVDR_OTHR_PRVDR_NPI_NUM)     NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(PRVDR_RNDRNG_PRVDR_NPI_NUM)   AS personal_npi, 'PRVDR_RNDRNG_PRVDR_NPI_NUM'   AS personal_npi_column_source FROM claims_base WHERE PRVDR_RNDRNG_PRVDR_NPI_NUM   IS NOT NULL AND TRIM(PRVDR_RNDRNG_PRVDR_NPI_NUM)   NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(PRVDR_PRSCRBNG_PRVDR_NPI_NUM) AS personal_npi, 'PRVDR_PRSCRBNG_PRVDR_NPI_NUM' AS personal_npi_column_source FROM claims_base WHERE PRVDR_PRSCRBNG_PRVDR_NPI_NUM IS NOT NULL AND TRIM(PRVDR_PRSCRBNG_PRVDR_NPI_NUM) NOT IN (''', '~')
    UNION ALL
    SELECT CLM_UNIQ_ID, TRIM(PRVDR_SRVC_PRVDR_NPI_NUM)     AS personal_npi, 'PRVDR_SRVC_PRVDR_NPI_NUM'     AS personal_npi_column_source FROM claims_base WHERE PRVDR_SRVC_PRVDR_NPI_NUM     IS NOT NULL AND TRIM(PRVDR_SRVC_PRVDR_NPI_NUM)     NOT IN (''', '~')
),

-- Affiliation edges with address.
-- INNER JOIN on CLM_UNIQ_ID links org <-> personal from the same claim.
-- Address validity enforced here so HAVING suppression applies only to
-- rows that will appear in the output.
relationship_claims AS (
    SELECT DISTINCT
        org.CLM_BLG_PRVDR_TAX_NUM,
        org.CLM_BLG_PRVDR_OSCAR_NUM,
        org.org_npi,
        person.personal_npi,
        person.personal_npi_column_source,
        org.CLM_BENE_MBI_ID,
        org.CLM_POS_PRVDR_1ST_LINE_ADR,
        org.CLM_POS_PRVDR_2ND_LINE_ADR,
        org.CLM_POS_PRVDR_CITY_NAME,
        org.CLM_POS_PRVDR_USPS_STATE_CD,
        org.CLM_POS_PRVDR_ZIP5_CD,
        org.CLM_POS_PRVDR_ZIP4_CD
    FROM org_npi_long AS org
    INNER JOIN personal_npi_long AS person
        ON org.CLM_UNIQ_ID = person.CLM_UNIQ_ID
    WHERE org.CLM_BLG_PRVDR_OSCAR_NUM IS NOT NULL
      AND org.CLM_BLG_PRVDR_OSCAR_NUM NOT IN ('', '~')
      AND NULLIF(TRIM(org.CLM_POS_PRVDR_1ST_LINE_ADR), '') IS NOT NULL
      AND NULLIF(TRIM(org.CLM_POS_PRVDR_CITY_NAME),    '') IS NOT NULL
      AND NULLIF(TRIM(org.CLM_POS_PRVDR_USPS_STATE_CD),'') IS NOT NULL
      AND NULLIF(TRIM(org.CLM_POS_PRVDR_ZIP5_CD),      '') IS NOT NULL
)

SELECT
    CLM_BLG_PRVDR_TAX_NUM,
    CLM_BLG_PRVDR_OSCAR_NUM,
    org_npi,
    personal_npi,
    personal_npi_column_source,
    CLM_POS_PRVDR_1ST_LINE_ADR,
    CLM_POS_PRVDR_2ND_LINE_ADR,
    CLM_POS_PRVDR_CITY_NAME,
    CLM_POS_PRVDR_USPS_STATE_CD,
    CLM_POS_PRVDR_ZIP5_CD,
    CLM_POS_PRVDR_ZIP4_CD,
    COUNT(DISTINCT CLM_BENE_MBI_ID) AS cnt_bene
FROM relationship_claims
GROUP BY
    CLM_BLG_PRVDR_TAX_NUM,
    CLM_BLG_PRVDR_OSCAR_NUM,
    org_npi,
    personal_npi,
    personal_npi_column_source,
    CLM_POS_PRVDR_1ST_LINE_ADR,
    CLM_POS_PRVDR_2ND_LINE_ADR,
    CLM_POS_PRVDR_CITY_NAME,
    CLM_POS_PRVDR_USPS_STATE_CD,
    CLM_POS_PRVDR_ZIP5_CD,
    CLM_POS_PRVDR_ZIP4_CD
HAVING COUNT(DISTINCT CLM_BENE_MBI_ID) > {min_bene}

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


# ============================================================================
# DRIVER
# ============================================================================

def main():
    """
    Same flow as idr_export_common.run_export(), but overrides window_months
    with the CLAIM_WINDOW_MONTHS constant defined at the top of this file
    before computing the date window -- no environment variable needed.
    """
    banner    = "IDR Medicare entity-linkage + address export"
    file_prefix = "idr_medicare_entity_link_address"
    min_bene_label = "Min distinct beneficiaries"

    log("=" * 60)
    log(f"{banner} -- Snowflake -> local CSV (optional -> S3)")
    log("=" * 60)

    cfg = load_config()

    # Override the window length with our module-level constant.
    # This is the only difference from a plain run_export() call.
    cfg["window_months"] = CLAIM_WINDOW_MONTHS

    start, end = compute_window(cfg)
    log(f"Claim window : {start.isoformat()} -> {end.isoformat()} "
        f"({cfg['window_months']}mo ending {cfg['window_lag_months']}mo back)")
    log(f"{min_bene_label} (small-cell) : > {cfg['min_bene']}")

    filename = f"{file_prefix}.{start:%Y_%m_%d}_to_{end:%Y_%m_%d}.csv"
    sql = build_entity_link_address_sql(
        f"@~/{filename}", start.isoformat(), end.isoformat(), cfg["min_bene"]
    )

    auth_kwargs = resolve_auth(cfg)
    conn = connect(cfg, auth_kwargs)
    try:
        rows = unload_to_stage(conn, filename, sql)
        if rows == 0:
            log("  no rows -- nothing written to the stage. Done.")
            return 0
        log(f"  unloaded {rows:,} rows to @~/{filename}")

        local = get_stage_file(conn, filename, cfg["output_dir"])
        if local is None:
            log("  GET produced no local file -- leaving the stage intact for retry")
            return 1
        log(f"  local file: {local}  ({local.stat().st_size:,} bytes)")

        if cfg["s3_bucket"]:
            key = upload_and_validate(local, cfg["s3_bucket"])
            if not key:
                log("  S3 upload/validate failed -- leaving the stage intact for retry")
                return 1

        remove_stage_file(conn, filename)
        log(f"  cleared @~/{filename}")
    finally:
        conn.close()

    log("=" * 60)
    log("DONE")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
