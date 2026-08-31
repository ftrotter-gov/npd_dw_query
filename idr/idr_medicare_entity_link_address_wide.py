"""
IDR Medicare wide provider + address export -- one row per distinct claim
"signature": billing entity (TIN/OSCAR) + every provider-role NPI kept in its
OWN column + the place-of-service address, weighted by distinct beneficiaries.

This is the WIDE counterpart to idr_medicare_entity_link_address.py. That script
UNPIVOTED the 13 personal-NPI columns into rows tagged with a source label, then
self-joined org<->personal to make one edge per row. This script does NOT
condense provider types: attending, operating, other, referring, rendering,
service, and facility each stay in a separate column, so a single row shows the
whole provider team that co-occurred on the same claim(s) at the same address.
Only the claim-stated NPI is kept per role -- the PRVDR_* "resolved" duplicate of
each role has been dropped (they largely echo the claim-stated NPI and doubled
the signature width). Locations and links stay together in one dataset.

  Output grain: one row per distinct combination of
    (billing TIN, OSCAR, 8 provider-role NPI columns [billing + attending,
     operating, other, referring, rendering, service, facility], place-of-service
     address)
  with COUNT(DISTINCT beneficiary MBI) across the window. Restricted to the
  professional-line population (INNER join), the only claims that carry a POS
  address. Small-cell suppression IS applied -- signature+address cells seen by
  MIN_CELL_BENE or fewer distinct beneficiaries are dropped (the CMS "11 or more"
  rule at the default MIN_CELL_BENE=10). No MBI is emitted -- only the aggregated
  count.

WHY THIS IS ALSO CHEAPER: the unpivot + org<->personal self-join in the long
version multiplied intermediate rows by (org roles x personal roles x lines) per
claim, which blew the 4-hour warehouse statement cap at 24 months. Here there is
no unpivot and no self-join -- just CLM |><| CLM_LINE_PRFNL and a GROUP BY, so it
scans fewer rows than idr_medicare_address (which succeeded) despite the wider
grain.

CONFIGURABLE DATE SPAN
  Edit CLAIM_WINDOW_MONTHS below. The window ends CLAIM_WINDOW_LAG_MONTHS (2)
  months before today and stretches back this many months.

All scaffolding -- config, auth, connection, and the COPY -> GET -> optional S3
-> REMOVE user-stage relay -- lives in idr_export_common.py.

Local (laptop) run -- picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicare_entity_link_address_wide.py
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

CLAIM_WINDOW_MONTHS = 24

# Small-cell suppression threshold. Keep only signature+address cells seen by
# MORE THAN this many distinct beneficiaries -- i.e. MIN_CELL_BENE + 1 and up.
# 10 -> the CMS "11 or more" cell-size rule.
MIN_CELL_BENE = 10

# Per-part size cap for the multi-file unload (Snowflake caps SINGLE=TRUE at
# 5 GB). ~1 GB compressed per part keeps the part count small.
MULTI_PART_MAX_BYTES = 1_000_000_000


# ============================================================================
# COLUMN SETS  (kept as data so the SELECT and GROUP BY can never drift apart)
# ============================================================================

# Billing / organization NPI column. The PRVDR_* "resolved" billing duplicate
# (PRVDR_BLG_PRVDR_NPI_NUM) has been dropped -- the claim-stated billing NPI is
# what feeds the OSCAR dimension join below and is the identity we key on.
ORG_NPI_COLS = [
    "CLM_BLG_PRVDR_NPI_NUM",
]

# The 7 claim-stated individual provider-role NPI columns, each kept as its own
# output column. The parallel PRVDR_* "resolved" duplicates (resolved attending/
# operating/other/referring/rendering/service and the resolved-only prescribing)
# have been DROPPED: they largely echo the claim-stated NPI and doubled the
# signature width, which drove the row/byte explosion. Keeping only the primary
# roles halves the signature.
ROLE_NPI_COLS = [
    "CLM_ATNDG_PRVDR_NPI_NUM",       # attending
    "CLM_OPRTG_PRVDR_NPI_NUM",       # operating
    "CLM_OTHR_PRVDR_NPI_NUM",        # other
    "CLM_RFRG_PRVDR_NPI_NUM",        # referring
    "CLM_RNDRG_PRVDR_NPI_NUM",       # rendering
    "CLM_SRVC_PRVDR_NPI_NUM",        # service
    "CLM_FAC_PRVDR_NPI_NUM",         # facility
]

# Place-of-service address columns from the professional claim line.
ADDR_COLS = [
    "CLM_POS_PRVDR_1ST_LINE_ADR",
    "CLM_POS_PRVDR_2ND_LINE_ADR",
    "CLM_POS_PRVDR_CITY_NAME",
    "CLM_POS_PRVDR_USPS_STATE_CD",
    "CLM_POS_PRVDR_ZIP5_CD",
    "CLM_POS_PRVDR_ZIP4_CD",
]


def _norm(qualified, alias):
    """Normalize an NPI/OSCAR column: TRIM, and map '' and '~' to NULL so blank
    placeholders collapse to a real NULL in that column (the row is kept -- a
    missing role is just NULL, not a dropped row)."""
    return f"NULLIF(NULLIF(TRIM({qualified}), ''), '~') AS {alias}"


# ============================================================================
# WIDE MEDICARE QUERY
# ============================================================================

def build_medicare_wide_sql(stage_target, start_sql, end_sql, min_bene):
    """
    COPY INTO {stage_target} one row per distinct (TIN, OSCAR, all provider-role
    NPI columns, place-of-service address) with the distinct-beneficiary count,
    from one window of final-action Medicare professional claims. Signature+
    address cells with <= min_bene distinct beneficiaries are suppressed.

      base   -- CLM INNER JOIN CLM_LINE_PRFNL (on GEO_BENE_SK + CLM_DT_SGNTR_SK),
                each claim carrying the billing TIN, the 8 role NPI columns
                (each normalized to NULL when blank), the MBI, and the six POS
                address columns. Window filter is CLM_FROM_DT with
                CLM_FINL_ACTN_IND='Y'. The join is INNER so only the
                professional-line population -- the claims that actually carry a
                POS address -- is scanned; institutional claims (no professional
                line, no POS address) are excluded rather than contributing
                address-less signature rows.

      agg    -- GROUP BY the TIN + all 8 NPI columns + the 6 address columns,
                COUNT(DISTINCT MBI), then HAVING that count > min_bene. Small-cell
                suppression: signature+address cells seen by <= min_bene distinct
                beneficiaries are dropped (CMS 11+ rule at the default 10), so no
                low-count cell reaches the output.

      final  -- LEFT JOIN the aggregated rows to the current provider dimension
                (V2_DIM_PRVDR_CRNT) on the billing NPI to FILL IN the billing
                provider's OSCAR/CCN. The claim's own CLM_BLG_PRVDR_OSCAR_NUM is
                blank for the professional-line population (OSCAR is a Part A
                institutional identifier, absent on Part B professional claims),
                so we source it from the dimension instead. The dimension is
                1 row per NPI (verified no fan-out), so this does not multiply
                rows; OSCAR is populated only where the biller is an
                institutional facility (sparse but real), NULL otherwise.

    Unloaded as gzipped multi-file parts (SINGLE=FALSE); the driver merges them
    into one plain CSV locally.
    """
    org_norm  = [_norm(f"CLAIM.{c}", c) for c in ORG_NPI_COLS]
    role_norm = [_norm(f"CLAIM.{c}", c) for c in ROLE_NPI_COLS]
    npi_aliases = ORG_NPI_COLS + ROLE_NPI_COLS

    base_select = ",\n        ".join(
        [
            # billing TIN -- also treat all-zeros as blank
            "CASE WHEN CLAIM.CLM_BLG_PRVDR_TAX_NUM IS NULL "
            "OR TRIM(CLAIM.CLM_BLG_PRVDR_TAX_NUM) IN ('', '~', '000000000') "
            "THEN NULL ELSE TRIM(CLAIM.CLM_BLG_PRVDR_TAX_NUM) END AS CLM_BLG_PRVDR_TAX_NUM",
            "CLAIM.CLM_BENE_MBI_ID",
        ]
        + org_norm
        + role_norm
        + [f"CLINE.{c} AS {c}" for c in ADDR_COLS]
    )

    # Aggregation grain: TIN + all NPI columns + address (OSCAR is NOT grouped --
    # it is attached afterward from the dimension, and is functionally determined
    # by the billing NPI, so it adds no rows).
    agg_cols   = ["CLM_BLG_PRVDR_TAX_NUM"] + npi_aliases + ADDR_COLS
    agg_list   = ",\n        ".join(agg_cols)

    # Final projection: keep original column order, with OSCAR back in position 2
    # sourced from the dimension (normalized '' / '~' -> NULL).
    final_cols = (
        ["agg.CLM_BLG_PRVDR_TAX_NUM",
         "NULLIF(NULLIF(TRIM(DIM.PRVDR_OSCAR_NUM), ''), '~') AS CLM_BLG_PRVDR_OSCAR_NUM"]
        + [f"agg.{c}" for c in npi_aliases]
        + [f"agg.{c}" for c in ADDR_COLS]
        + ["agg.CNT_BENE"]
    )
    final_list = ",\n    ".join(final_cols)

    return f"""
COPY INTO {stage_target}
FROM (

WITH base AS (
    SELECT
        {base_select}
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM AS CLAIM
    INNER JOIN IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM_LINE_PRFNL AS CLINE
        ON CLINE.GEO_BENE_SK     = CLAIM.GEO_BENE_SK
       AND CLINE.CLM_DT_SGNTR_SK = CLAIM.CLM_DT_SGNTR_SK
    WHERE CLAIM.CLM_FROM_DT       >= DATE '{start_sql}'
      AND CLAIM.CLM_FROM_DT        < DATE '{end_sql}'
      AND CLAIM.CLM_FINL_ACTN_IND  = 'Y'
      -- NOTE: INNER join -- restricted to the professional-line population, the
      -- only claims that carry a place-of-service address. Non-professional
      -- (institutional) claims have no professional line and therefore no POS
      -- address, so including them (LEFT join) only added address-less signature
      -- rows and blew up the row/byte count. The address is the point of this
      -- extract, so we keep exactly the population that has one.
),

agg AS (
    SELECT
        {agg_list},
        COUNT(DISTINCT CLM_BENE_MBI_ID) AS CNT_BENE
    FROM base
    GROUP BY
        {agg_list}
    HAVING COUNT(DISTINCT CLM_BENE_MBI_ID) > {min_bene}
)

SELECT
    {final_list}
FROM agg
LEFT JOIN IDRC_PRD.CMS_VDM_VIEW_SMNTC_PRD.V2_DIM_PRVDR_CRNT AS DIM
    ON TRIM(DIM.PRVDR_NPI_NUM) = agg.CLM_BLG_PRVDR_NPI_NUM

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
    banner      = "IDR Medicare wide provider + address export"
    file_prefix = "idr_medicare_entity_link_address_wide"

    log("=" * 60)
    log(f"{banner} -- Snowflake -> local CSV (optional -> S3)")
    log("=" * 60)

    cfg = load_config()
    cfg["window_months"] = CLAIM_WINDOW_MONTHS

    start, end = compute_window(cfg)
    log(f"Claim window : {start.isoformat()} -> {end.isoformat()} "
        f"({cfg['window_months']}mo ending {cfg['window_lag_months']}mo back)")
    min_bene = MIN_CELL_BENE
    log(f"Small-cell suppression : ENABLED -- keep cells with > {min_bene} "
        f"distinct beneficiaries ({min_bene + 1}+, CMS 11+ rule)")

    window    = f"{start:%Y_%m_%d}_to_{end:%Y_%m_%d}"
    filename  = f"{file_prefix}.{window}.csv"
    stage_dir = f"{file_prefix}.{window}"
    sql = build_medicare_wide_sql(
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
        # This extract can be huge. Probe the staged (gzip) size and pick a
        # delivery that fits local disk, instead of blindly GETting a result
        # that could be a TB of plain CSV (the failure mode of the prior run).
        c_bytes  = stage_dir_bytes(conn, stage_dir)
        est_plain = c_bytes * 6           # gzip'd CSV expands ~5-7x on decompress
        free      = shutil.disk_usage(cfg["output_dir"]).free
        margin    = 15_000_000_000        # keep ~15 GB headroom
        gb = 1_000_000_000
        log(f"  staged size: {c_bytes/gb:.1f} GB compressed across parts "
            f"(est. ~{est_plain/gb:.0f} GB plain CSV); free disk {free/gb:.0f} GB")

        if est_plain + margin < free:
            # Plain CSV fits -- deliver in the same form as the other extracts.
            out_name, compress = filename, False
            log("  -> delivering as PLAIN CSV (fits with headroom)")
        elif 2 * c_bytes + margin < free:
            # Plain won't fit but the compressed result will -- deliver .csv.gz.
            out_name, compress = filename + ".gz", True
            log("  -> plain CSV too large; delivering as GZIP CSV (.csv.gz)")
        else:
            # Not even the compressed result fits. Do NOT download; the compute
            # is banked on the stage and the delivery is retriable.
            log("  ✗ staged result too large to land on local disk even compressed.")
            log(f"    Compute is BANKED on @~/{stage_dir}/ ({c_bytes/gb:.1f} GB) "
                f"-- NOT removed.")
            log("    Reduce the grain to deliver: coarsen the address to "
                "city/ZIP5, shorten the window, or materialize as a Snowflake "
                "table. Re-run after adjusting.")
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
