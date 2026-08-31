"""
IDR NPI <-> OSCAR crosswalk export -- the full V2_MDCR_PRVDR_NPI_OSCAR table
with the real provider NPI joined in.

V2_MDCR_PRVDR_NPI_OSCAR is a ~3.46M-row dated association table between a
provider's OSCAR/CCN and its Medicare administrative record. DESPITE THE NAME it
carries NO raw NPI: its provider key is the surrogate PRVDR_SK. To make it a
usable NPI<->OSCAR crosswalk we LEFT JOIN PRVDR_SK to the current provider
dimension (V2_DIM_PRVDR_CRNT), which carries both PRVDR_SK and PRVDR_NPI_NUM.

  Verified 2026-08-30: the join is 1:1 (0 fan-out; 3,459,510 rows in and out)
  and 3,459,509 / 3,459,510 rows (100.0%) resolve a real NPI.

Output grain: one row per native V2_MDCR_PRVDR_NPI_OSCAR row (a dated
NPI/OSCAR association), with the resolved PRVDR_NPI_NUM as column 1 (the real
join key). Business columns are passed through verbatim; only the joined
PRVDR_NPI_NUM is normalized ('' / '~' -> NULL). No date window -- this is the
whole table.

  IDR-internal keys are NOT emitted -- PRVDR_SK (used only in the join to resolve
  the NPI), GEO_SK, META_SK and META_SRC_SK are IDR plumbing with no join value
  to an external consumer, and are dropped from the output.

  NOTE on geography: the INVLD_* columns (PRVDR_NPI_OSCAR_INVLD_PLC_NAME /
  _ZIP_CD / _STATE_CD) are the legacy/invalid place-name, ZIP and state, kept
  alongside the real GEO_ZIP4_CD as the usable geography. The precise geographic
  key GEO_SK is dropped; if exact city/state is needed later, resolve GEO_SK
  against the geo dimension and emit real columns rather than the surrogate key.

All scaffolding -- config, auth, connection, and the COPY -> GET -> optional S3
-> REMOVE user-stage relay -- lives in idr_export_common.py.

Local (laptop) run -- picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_npi_oscar_crosswalk.py
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

NPI_OSCAR = "IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NPI_OSCAR"
DIM       = "IDRC_PRD.CMS_VDM_VIEW_SMNTC_PRD.V2_DIM_PRVDR_CRNT"

# Business columns of V2_MDCR_PRVDR_NPI_OSCAR to pass through verbatim, in table
# order. The IDR-internal surrogate keys the source carries -- PRVDR_SK (only
# used INTERNALLY, in the join below, to resolve the real NPI), GEO_SK, META_SK,
# and META_SRC_SK -- are intentionally NOT emitted: they are IDR plumbing with no
# join value to an external consumer (joins run on NPI and OSCAR, both business
# keys). GEO_ZIP4_CD (a real ZIP+4) and the legacy INVLD place/zip/state are kept
# as the usable geography; if precise city/state is ever needed, resolve GEO_SK
# against the geo dimension and emit real columns rather than shipping the key.
NATIVE_COLS = [
    "PRVDR_OSCAR_NUM",
    "PRVDR_NPI_OSCAR_BGN_DT",
    "PRVDR_NPI_OSCAR_END_DT",
    "CLM_CNTRCTR_NUM",
    "PRVDR_NPI_OSCAR_MDCR_BGN_DT",
    "PRVDR_NPI_OSCAR_MDCR_END_DT",
    "PRVDR_NPI_OSCAR_NAME",
    "PRVDR_NPI_OSCAR_FED_TAX_NUM",
    "PRVDR_NPI_OSCAR_LINE_1_ADR",
    "PRVDR_NPI_OSCAR_LINE_2_ADR",
    "PRVDR_NPI_OSCAR_INVLD_PLC_NAME",
    "PRVDR_NPI_OSCAR_INVLD_ZIP_CD",
    "PRVDR_NPI_OSCAR_INVLD_STATE_CD",
    "GEO_ZIP4_CD",
    "PRVDR_NPI_OSCAR_PHNE_NUM",
    "PRVDR_NPI_OSCAR_TYPE_CD",
    "PRVDR_LGCY_ADR_TYPE_CD",
]


# ============================================================================
# QUERY
# ============================================================================

def build_crosswalk_sql(stage_target):
    """
    COPY INTO {stage_target} the business columns of V2_MDCR_PRVDR_NPI_OSCAR with
    PRVDR_NPI_NUM (from V2_DIM_PRVDR_CRNT, keyed on the source's PRVDR_SK) as
    column 1. LEFT JOIN so the single row that does not resolve a NPI is still
    kept (PRVDR_NPI_NUM NULL). Native columns are verbatim; the joined NPI is
    normalized ('' / '~' -> NULL). PRVDR_SK is used ONLY in the join condition and
    is never emitted; the other IDR-internal keys (GEO_SK, META_SK, META_SRC_SK)
    are dropped from NATIVE_COLS entirely.
    """
    # Resolved NPI first (the real join key), then the business native columns.
    select_cols = (
        ["NULLIF(NULLIF(TRIM(D.PRVDR_NPI_NUM), ''), '~') AS PRVDR_NPI_NUM"]
        + [f"O.{c}" for c in NATIVE_COLS]
    )
    select_list = ",\n    ".join(select_cols)

    return f"""
COPY INTO {stage_target}
FROM (
    SELECT
    {select_list}
    FROM {NPI_OSCAR} AS O
    LEFT JOIN {DIM} AS D
        ON D.PRVDR_SK = O.PRVDR_SK
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
    banner      = "IDR NPI<->OSCAR crosswalk export"
    file_prefix = "idr_npi_oscar_crosswalk"

    log("=" * 60)
    log(f"{banner} -- Snowflake -> local CSV (optional -> S3)")
    log("=" * 60)

    cfg = load_config()

    filename  = f"{file_prefix}.csv"
    stage_dir = file_prefix
    sql = build_crosswalk_sql(f"@~/{stage_dir}/")

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
