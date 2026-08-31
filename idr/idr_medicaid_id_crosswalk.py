"""
IDR Medicaid provider-ID crosswalk export -- the Medicaid counterpart to
idr_npi_oscar_crosswalk.py.

Medicaid has NO OSCAR/CCN (that is a Medicare institutional identifier). Its
identity crosswalk is V2_MDCD_PRVDR_ID_CRNT: a LONG-format table with one row
per (state, State Medicaid ID, location, id-type, id-value). The id-type code
decodes (V2_MDCD_PRVDR_ID_TYPE_CD) as:

    1 STATE-SPECIFIC MEDICAID PROVIDER ID    6 STATE TAX ID
    2 NPI                                    7 SSN            <-- EXCLUDED
    3 MEDICARE ID                            8 OTHER
    4 NCPDP ID                               9 OLD STATE PROVIDER ID
    5 FEDERAL TAX ID

  *** SSN (id-type 7) is provider PII and is NOT pulled -- filtered out in the
      WHERE clause. ***

This keeps the LONG format (one id per row, verbatim), and FOLDS IN two
reference attributes per provider:

  name    -- from V2_MDCD_PRVDR_DMGRPHC_CRNT, joined 1:1 on (state, Medicaid ID).
             Individual + organization/legal/DBA names only. Birth date, death
             date and sex are intentionally NOT folded in.

  address -- from V2_MDCD_PRVDR_LCTN_CRNT, joined on (state, Medicaid ID,
             location). A location carries up to four address-type rows
             (1 billing / 2 mailing / 3 practice / 4 service-location), so we
             pick ONE per location by priority 4 -> 3 -> 1 -> 2 (service-
             location first, to match the claims extract's orientation), keeping
             the join 1:1 and the long crosswalk row count unchanged.

  Verified 2026-08-30: V2_MDCD_PRVDR_ID_CRNT is 82,836,399 rows, all
  IDR_LTST_TRANS_FLG='Y' (the _CRNT view is already current-only, so no stale-
  transaction filter is needed). Excluding SSN leaves ~73.3M rows.

No date window -- this is the whole current crosswalk.

All scaffolding -- config, auth, connection, and the COPY -> GET -> optional S3
-> REMOVE user-stage relay -- lives in idr_export_common.py.

Local (laptop) run -- picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with Medicaid provider access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicaid_id_crosswalk.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import (
    load_config,
    resolve_auth,
    connect,
    unload_to_stage_multifile,
    get_and_merge_stage_dir,
    upload_and_validate,
    remove_stage_dir,
    log,
)


# ============================================================================
# CONFIGURATION
# ============================================================================

MULTI_PART_MAX_BYTES = 1_000_000_000

MD = "IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD"
ID_CRNT   = f"{MD}.V2_MDCD_PRVDR_ID_CRNT"
DMGRPHC   = f"{MD}.V2_MDCD_PRVDR_DMGRPHC_CRNT"
LCTN      = f"{MD}.V2_MDCD_PRVDR_LCTN_CRNT"


# ============================================================================
# QUERY
# ============================================================================

def build_medicaid_id_crosswalk_sql(stage_target):
    """
    COPY INTO {stage_target} the long-format Medicaid provider-ID crosswalk
    (SSN excluded), with provider name folded in 1:1 and one address per
    location folded in by priority 4 -> 3 -> 1 -> 2.
    """
    return f"""
COPY INTO {stage_target}
FROM (

WITH ids AS (
    -- long crosswalk, SSN (type 7) removed
    SELECT
        PRVDR_STATE_MDCD_ID,
        SUBMTG_MDCD_LCL_STATE_CD,
        PRVDR_LCTN_ID,
        PRVDR_MDCD_ID_TYPE_CD,
        CASE PRVDR_MDCD_ID_TYPE_CD
            WHEN '1' THEN 'STATE-SPECIFIC MEDICAID PROVIDER ID'
            WHEN '2' THEN 'NPI'
            WHEN '3' THEN 'MEDICARE ID'
            WHEN '4' THEN 'NCPDP ID'
            WHEN '5' THEN 'FEDERAL TAX ID'
            WHEN '6' THEN 'STATE TAX ID'
            WHEN '8' THEN 'OTHER'
            WHEN '9' THEN 'OLD STATE PROVIDER ID'
            ELSE NULL
        END                                             AS PRVDR_MDCD_ID_TYPE_DESC,
        NULLIF(NULLIF(TRIM(PRVDR_ID), ''), '~')         AS PRVDR_ID,
        NULLIF(NULLIF(TRIM(PRVDR_ID_ISSG_ENT_ID), ''), '~') AS PRVDR_ID_ISSG_ENT_ID,
        PRVDR_SRC_EFCTV_DT,
        PRVDR_SRC_END_DT
    FROM {ID_CRNT}
    WHERE PRVDR_MDCD_ID_TYPE_CD <> '7'          -- exclude SSN (provider PII)
),

addr AS (
    -- one address per (state, mdcd_id, location): prefer service-location (4),
    -- then practice (3), billing (1), mailing (2)
    SELECT
        PRVDR_STATE_MDCD_ID,
        SUBMTG_MDCD_LCL_STATE_CD,
        PRVDR_LCTN_ID,
        PRVDR_MDCD_ADR_TYPE_CD,
        PRVDR_LINE_1_ADR,
        PRVDR_LINE_2_ADR,
        PRVDR_LINE_3_ADR,
        PRVDR_ADR_CITY_NAME,
        PRVDR_ADR_STATE_CD,
        PRVDR_ADR_ZIP_CD,
        PRVDR_ADR_CNTY_CD,
        PRVDR_PHNE_NUM
    FROM {LCTN}
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY PRVDR_STATE_MDCD_ID, SUBMTG_MDCD_LCL_STATE_CD, PRVDR_LCTN_ID
        ORDER BY CASE PRVDR_MDCD_ADR_TYPE_CD
                     WHEN '4' THEN 1 WHEN '3' THEN 2
                     WHEN '1' THEN 3 WHEN '2' THEN 4 ELSE 5 END
    ) = 1
)

SELECT
    ids.PRVDR_STATE_MDCD_ID,
    ids.SUBMTG_MDCD_LCL_STATE_CD,
    ids.PRVDR_LCTN_ID,
    ids.PRVDR_MDCD_ID_TYPE_CD,
    ids.PRVDR_MDCD_ID_TYPE_DESC,
    ids.PRVDR_ID,
    ids.PRVDR_ID_ISSG_ENT_ID,
    ids.PRVDR_SRC_EFCTV_DT,
    ids.PRVDR_SRC_END_DT,
    -- folded-in name (1:1 on state + Medicaid ID)
    NULLIF(NULLIF(TRIM(DEM.PRVDR_LAST_NAME), ''), '~')   AS PRVDR_LAST_NAME,
    NULLIF(NULLIF(TRIM(DEM.PRVDR_1ST_NAME), ''), '~')    AS PRVDR_1ST_NAME,
    NULLIF(NULLIF(TRIM(DEM.PRVDR_MDL_INITL_NAME), ''), '~') AS PRVDR_MDL_INITL_NAME,
    NULLIF(NULLIF(TRIM(DEM.PRVDR_ORG_NAME), ''), '~')    AS PRVDR_ORG_NAME,
    NULLIF(NULLIF(TRIM(DEM.PRVDR_LGL_NAME), ''), '~')    AS PRVDR_LGL_NAME,
    NULLIF(NULLIF(TRIM(DEM.PRVDR_DBA_NAME), ''), '~')    AS PRVDR_DBA_NAME,
    DEM.PRVDR_FAC_GRP_INDVDL_CD                          AS PRVDR_FAC_GRP_INDVDL_CD,
    -- folded-in address (one per location, priority-picked)
    ADDR.PRVDR_MDCD_ADR_TYPE_CD,
    NULLIF(NULLIF(TRIM(ADDR.PRVDR_LINE_1_ADR), ''), '~') AS PRVDR_LINE_1_ADR,
    NULLIF(NULLIF(TRIM(ADDR.PRVDR_LINE_2_ADR), ''), '~') AS PRVDR_LINE_2_ADR,
    NULLIF(NULLIF(TRIM(ADDR.PRVDR_LINE_3_ADR), ''), '~') AS PRVDR_LINE_3_ADR,
    NULLIF(NULLIF(TRIM(ADDR.PRVDR_ADR_CITY_NAME), ''), '~') AS PRVDR_ADR_CITY_NAME,
    NULLIF(NULLIF(TRIM(ADDR.PRVDR_ADR_STATE_CD), ''), '~')  AS PRVDR_ADR_STATE_CD,
    NULLIF(NULLIF(TRIM(ADDR.PRVDR_ADR_ZIP_CD), ''), '~')    AS PRVDR_ADR_ZIP_CD,
    NULLIF(NULLIF(TRIM(ADDR.PRVDR_ADR_CNTY_CD), ''), '~')   AS PRVDR_ADR_CNTY_CD,
    NULLIF(NULLIF(TRIM(ADDR.PRVDR_PHNE_NUM), ''), '~')      AS PRVDR_PHNE_NUM
FROM ids
LEFT JOIN {DMGRPHC} AS DEM
    ON  DEM.PRVDR_STATE_MDCD_ID      = ids.PRVDR_STATE_MDCD_ID
    AND DEM.SUBMTG_MDCD_LCL_STATE_CD = ids.SUBMTG_MDCD_LCL_STATE_CD
LEFT JOIN addr AS ADDR
    ON  ADDR.PRVDR_STATE_MDCD_ID      = ids.PRVDR_STATE_MDCD_ID
    AND ADDR.SUBMTG_MDCD_LCL_STATE_CD = ids.SUBMTG_MDCD_LCL_STATE_CD
    AND ADDR.PRVDR_LCTN_ID            = ids.PRVDR_LCTN_ID

)
FILE_FORMAT = (
  TYPE = CSV
  FIELD_DELIMITER = ','
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  COMPRESSION = GZIP
)
HEADER = TRUE
SINGLE = FALSE
MAX_FILE_SIZE = {MULTI_PART_MAX_BYTES}
OVERWRITE = TRUE
DETAILED_OUTPUT = FALSE
"""


# ============================================================================
# DRIVER
# ============================================================================

def main():
    banner      = "IDR Medicaid provider-ID crosswalk export"
    file_prefix = "idr_medicaid_id_crosswalk"

    log("=" * 60)
    log(f"{banner} -- Snowflake -> local CSV (optional -> S3)")
    log("=" * 60)
    log("SSN (id-type 7) : EXCLUDED (provider PII, not pulled)")

    cfg = load_config()

    filename  = f"{file_prefix}.csv"
    stage_dir = file_prefix
    sql = build_medicaid_id_crosswalk_sql(f"@~/{stage_dir}/")

    conn = connect(cfg, resolve_auth(cfg))
    try:
        rows = unload_to_stage_multifile(conn, stage_dir, sql)
        if rows == 0:
            log("  no rows -- nothing written to the stage. Done.")
            return 0
        log(f"  unloaded {rows:,} rows to @~/{stage_dir}/")

        local = get_and_merge_stage_dir(conn, stage_dir, filename, cfg["output_dir"])
        if local is None:
            log("  GET/merge produced no local file -- leaving the stage intact for retry")
            return 1
        log(f"  local file: {local}  ({local.stat().st_size:,} bytes)")

        if cfg["s3_bucket"]:
            key = upload_and_validate(local, cfg["s3_bucket"])
            if not key:
                log("  S3 upload/validate failed -- leaving the stage intact for retry")
                return 1

        remove_stage_dir(conn, stage_dir)
        log(f"  cleared @~/{stage_dir}/")
    finally:
        conn.close()

    log("=" * 60)
    log("DONE")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
