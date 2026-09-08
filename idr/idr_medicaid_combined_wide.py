"""
IDR Medicaid COMBINED wide export -- one row per distinct claim "signature":
every provider-role NPI kept in its OWN column + service-location address +
billing-provider address + specialty/taxonomy/provider-type + type-of-bill +
place-of-service + payer/plan, weighted by distinct recipients.

WHAT THIS SUPERSEDES -- this single file replaces:
  idr_medicaid_entity_link_address_wide.py  (role NPIs + service address only)
  idr_medicaid_address.py                   (long unpivot of the same roles)
by widening the signature with the billing address, specialty/taxonomy/type,
type-of-bill, place-of-service, and payer columns V2_MDCD_CLM already carries.

DESIGN
  V2_MDCD_CLM is a SINGLE table -- both the header attributes and CLM_POS_CD live
  here, so there is no header<->line fan-out risk (unlike Medicare). One query,
  no join. Provider roles are NOT condensed: admitting, billing, supervising,
  service-location-org, referring, ordering, prescribing, rx-dispensing and
  health-home each stay in their own column, so a row shows the whole provider set
  that co-occurred on the same claim(s).

  Filters (all three, verified against the fixed non-wide reference):
    * window on CLM_THRU_DT
    * CLM_FINL_ACTN_IND = 'T'  -- Medicaid final action is the T/F domain, NOT
      Y/N; omitting it double-counts recipients across original/adjustment/voided
      rows (idr-query rule #1). This is bug B.
    * CLM_RCPNT_STATE_MDCD_ID IS NOT NULL

  Output grain: one row per distinct combination of every column below, with
  COUNT(DISTINCT CLM_RCPNT_STATE_MDCD_ID) AS CNT_RECIPIENTS across the window.
  Small-cell suppression IS applied -- cells seen by MIN_CELL_BENE or fewer
  distinct recipients are dropped (the CMS "11 or more" rule at the default
  MIN_CELL_BENE=10). No recipient id is emitted -- the id is consumed ONLY inside
  COUNT(DISTINCT ...) and the small-cell HAVING.

TWO GRAIN KNOBS (both are just column-set lists below, so the SELECT and GROUP BY
can never drift):
  * TOB_POS_COLS (type-of-bill + place-of-service) is in the grain.
  * PAYER_COLS (plan + submitter) is IN the grain -> the provider<->payer edge,
    but plan varies by recipient enrollment, so it FRAGMENTS a provider's
    recipient counts across plans and pushes more cells under the 11+ floor.
    Empty PAYER_COLS for provider/geography rows with maximal counts.

CONFIGURABLE DATE SPAN
  Edit CLAIM_WINDOW_MONTHS below (or set the CLAIM_WINDOW_MONTHS env var). The
  window ends CLAIM_WINDOW_LAG_MONTHS (2) months before today and stretches back
  this many months. Filtered on CLM_THRU_DT.

All scaffolding -- config, auth, connection, and the COPY -> GET -> optional S3
-> REMOVE user-stage relay -- lives in idr_export_common.py.

Local (laptop) run -- picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with Medicaid claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicaid_combined_wide.py
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import (
    load_config,
    compute_window,
    resolve_auth,
    connect,
    unload_to_stage_multifile,
    stage_dir_bytes,
    get_and_merge_stage_dir,
    upload_and_validate,
    remove_stage_dir,
    log,
)


# ============================================================================
# CONFIGURATION
# ============================================================================

# 24-month window by default. A 1-month DRY-RUN is a one-line change here OR an
# env override:  CLAIM_WINDOW_MONTHS=1 python3 idr/idr_medicaid_combined_wide.py
CLAIM_WINDOW_MONTHS = int(os.environ.get("CLAIM_WINDOW_MONTHS") or 24)

# Small-cell suppression threshold. Keep only signature cells seen by MORE THAN
# this many distinct recipients -- i.e. MIN_CELL_BENE + 1 and up.
# 10 -> the CMS "11 or more" cell-size rule.
MIN_CELL_BENE = 10

MULTI_PART_MAX_BYTES = 1_000_000_000


# ============================================================================
# COLUMN SETS  (kept as data so the SELECT and GROUP BY can never drift apart)
# ============================================================================

# Every provider-role NPI column on V2_MDCD_CLM, each kept as its own output
# column. The first four match the former wide extract; the rest are added so a
# row shows the whole provider team on the claim.
ROLE_NPI_COLS = [
    "CLM_ADMTG_PRVDR_NPI_NUM",         # admitting
    "CLM_BLG_PRVDR_NPI_NUM",           # billing
    "CLM_SPRVSNG_PRVDR_NPI_NUM",       # supervising
    "CLM_SRVC_LCTN_ORG_NPI_NUM",       # service-location organization
    "CLM_RFRG_PRVDR_NPI_NUM",          # referring (new)
    "CLM_RFRG_PRVDR_NPI_2_NUM",        # referring #2 (new)
    "CLM_ORDRG_PRVDR_NPI_NUM",         # ordering (new)
    "CLM_PRSCRBNG_PRVDR_NPI_NUM",      # prescribing (new)
    "CLM_RX_DSPNSNG_PRVDR_NPI_NUM",    # rx dispensing (new)
    "CLM_HLTH_HOME_PRVDR_NPI_NUM",     # health home (new)
]

# Service-location address (matches the former wide extract).
SRVC_ADDR_COLS = [
    "CLM_SRVC_LCTN_LINE_1_ADR",
    "CLM_SRVC_LCTN_LINE_2_ADR",
    "CLM_SRVC_LCTN_CITY_NAME",
    "CLM_SRVC_LCTN_STATE_CD",
    "CLM_SRVC_LCTN_ZIP_CD",
]

# Billing-provider address on the claim (new).
BLG_ADDR_COLS = [
    "CLM_BLG_PRVDR_LINE_1_ADR",
    "CLM_BLG_PRVDR_LINE_2_ADR",
    "CLM_BLG_PRVDR_CITY_NAME",
    "CLM_BLG_PRVDR_STATE_CD",
    "CLM_BLG_PRVDR_ZIP_CD",
]

# Specialty / taxonomy / provider-type (new).
SPCLTY_COLS = [
    "CLM_ADMTG_PRVDR_SPCLTY_CD",
    "CLM_BLG_PRVDR_SPCLTY_CD",
    "CLM_ADMTG_PRVDR_TXNMY_CD",
    "CLM_BLG_PRVDR_TXNMY_CD",
    "CLM_OPRTG_PRVDR_TXNMY_CD",
    "CLM_ADMTG_PRVDR_TYPE_CD",
    "CLM_BLG_PRVDR_TYPE_CD",
]

# Type-of-bill + place-of-service (new). CLM_POS_CD lives on V2_MDCD_CLM (there is
# NO Medicare equivalent -- see JOINS.md).
TOB_POS_COLS = [
    "CLM_TOB_CD",
    "CLM_BILL_FCLTY_TYPE_CD",
    "CLM_BILL_CLSFCTN_CD",
    "CLM_POS_CD",
]

# Payer / plan -- the provider<->payer edge (new). See the "TWO GRAIN KNOBS" note:
# this fragments recipient counts under the 11+ floor. Empty the list to drop
# payer linkage and maximize counts.
PAYER_COLS = [
    "CLM_PLAN_NUM",
    "CLM_SBMTR_ID",
]


def _norm(col):
    """TRIM and map '' / '~' to NULL, keeping the column (a missing role/field is
    NULL, not a dropped row)."""
    return f"NULLIF(NULLIF(TRIM({col}), ''), '~') AS {col}"


# ============================================================================
# COMBINED WIDE MEDICAID QUERY
# ============================================================================

def build_medicaid_combined_wide_sql(stage_target, start_sql, end_sql, min_bene):
    """
    COPY INTO {stage_target} one row per distinct (all provider-role NPI columns,
    service-location address, billing address, specialty/taxonomy/provider-type,
    type-of-bill, place-of-service, payer/plan) with the distinct-recipient count,
    from one window of final-action Medicaid claims (V2_MDCD_CLM, single table).
    Cells with <= min_bene distinct recipients are suppressed.

      base   -- project every grain column (each normalized to NULL when blank)
                and the recipient id. Filters: CLM_THRU_DT window,
                CLM_FINL_ACTN_IND='T' (Medicaid final action, T/F domain),
                CLM_RCPNT_STATE_MDCD_ID IS NOT NULL. Addresses/codes are optional
                enrichment -- rows are kept even when they are blank/NULL.

      final  -- GROUP BY every grain column, COUNT(DISTINCT recipient id), then
                HAVING that count > min_bene (CMS 11+ small-cell suppression).

    Unloaded as gzipped multi-file parts (SINGLE=FALSE); the driver merges them
    into one plain CSV locally.
    """
    grain_cols = (
        ROLE_NPI_COLS
        + SRVC_ADDR_COLS
        + BLG_ADDR_COLS
        + SPCLTY_COLS
        + TOB_POS_COLS
        + PAYER_COLS
    )

    base_select = ",\n        ".join(
        [_norm(c) for c in grain_cols]
        + ["CLM_RCPNT_STATE_MDCD_ID"]
    )

    group_list  = ",\n    ".join(grain_cols)
    select_list = ",\n    ".join(grain_cols)

    return f"""
COPY INTO {stage_target}
FROM (

WITH base AS (
    SELECT
        {base_select}
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM
    WHERE CLM_THRU_DT           >= DATE '{start_sql}'
      AND CLM_THRU_DT            <  DATE '{end_sql}'
      AND CLM_FINL_ACTN_IND       = 'T'
      AND CLM_RCPNT_STATE_MDCD_ID IS NOT NULL
      -- CLM_FINL_ACTN_IND='T' : Medicaid final action is the T/F domain (NOT the
      -- Medicare Y/N). The addresses/codes are optional enrichment, not filters.
)

SELECT
    {select_list},
    COUNT(DISTINCT CLM_RCPNT_STATE_MDCD_ID) AS CNT_RECIPIENTS
FROM base
GROUP BY
    {group_list}
HAVING COUNT(DISTINCT CLM_RCPNT_STATE_MDCD_ID) > {min_bene}

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
    banner      = "IDR Medicaid combined wide provider + address + payer export"
    file_prefix = "idr_medicaid_combined_wide"

    log("=" * 60)
    log(f"{banner} -- Snowflake -> local CSV (optional -> S3)")
    log("=" * 60)

    cfg = load_config()
    cfg["window_months"] = CLAIM_WINDOW_MONTHS

    start, end = compute_window(cfg)
    log(f"Claim window : {start.isoformat()} -> {end.isoformat()} "
        f"({cfg['window_months']}mo ending {cfg['window_lag_months']}mo back)")
    if cfg["window_months"] <= 1:
        log("  (1-month DRY-RUN window -- flip CLAIM_WINDOW_MONTHS to 24 for the full pull)")
    min_bene = MIN_CELL_BENE
    log(f"Small-cell suppression : ENABLED -- keep cells with > {min_bene} "
        f"distinct recipients ({min_bene + 1}+, CMS 11+ rule)")
    log(f"Final action : CLM_FINL_ACTN_IND='T' (Medicaid T/F domain)")
    log(f"Payer/plan in grain : {'YES' if PAYER_COLS else 'no'}")

    window    = f"{start:%Y_%m_%d}_to_{end:%Y_%m_%d}"
    filename  = f"{file_prefix}.{window}.csv"
    stage_dir = f"{file_prefix}.{window}"
    sql = build_medicaid_combined_wide_sql(
        f"@~/{stage_dir}/", start.isoformat(), end.isoformat(), min_bene
    )

    conn = connect(cfg, resolve_auth(cfg))
    try:
        rows = unload_to_stage_multifile(conn, stage_dir, sql)
        if rows == 0:
            log("  no rows -- nothing written to the stage. Done.")
            return 0
        log(f"  unloaded {rows:,} rows to @~/{stage_dir}/")

        # --- MEASURE BEFORE DOWNLOADING ------------------------------------
        # This is a wide 24-month aggregate; probe the staged (gzip) size and
        # pick a delivery that fits local disk instead of blindly GETting a
        # result that could overrun the disk. (Mirrors the Medicare combined
        # extract's guard.)
        c_bytes   = stage_dir_bytes(conn, stage_dir)
        # gzip'd CSV expands ~5-7x on decompress; this payload is short, repetitive
        # codes/NPIs/ZIPs that gzip HARDER, so use the top of the range (7x) to
        # avoid under-estimating and picking PLAIN for a result that fills the disk.
        est_plain = c_bytes * 7
        free      = shutil.disk_usage(cfg["output_dir"]).free
        margin    = 15_000_000_000        # keep ~15 GB headroom
        gb = 1_000_000_000
        log(f"  staged size: {c_bytes/gb:.1f} GB compressed across parts "
            f"(est. ~{est_plain/gb:.0f} GB plain CSV); free disk {free/gb:.0f} GB")

        if est_plain + margin < free:
            out_name, compress = filename, False
            log("  -> delivering as PLAIN CSV (fits with headroom)")
        elif 2 * c_bytes + margin < free:
            out_name, compress = filename + ".gz", True
            log("  -> plain CSV too large; delivering as GZIP CSV (.csv.gz)")
        else:
            log("  ✗ staged result too large to land on local disk even compressed.")
            log(f"    Compute is BANKED on @~/{stage_dir}/ ({c_bytes/gb:.1f} GB) "
                f"-- NOT removed.")
            log("    Reduce the grain to deliver: empty PAYER_COLS, shorten the "
                "window, or materialize as a Snowflake table. Re-run after "
                "adjusting.")
            return 2

        local = get_and_merge_stage_dir(conn, stage_dir, out_name, cfg["output_dir"], compress=compress)
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
