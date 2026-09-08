"""
IDR Medicare wide provider + HEADER-geography export -- one row per distinct
claim "signature": billing entity (TIN / OSCAR / CCN) + every provider-role NPI
kept in its OWN column + the billing provider's header geography + the plan /
contract identifiers, weighted by distinct beneficiaries.

WHY THIS EXISTS -- it is the complement to idr_medicare_entity_link_address_wide.py.
That extract INNER-joins V2_MDCR_CLM to V2_MDCR_CLM_LINE_PRFNL, which restricts it
to the Part B PROFESSIONAL population (the only claims that carry the full
place-of-service STREET address). Everything else is dropped:

    Part A institutional (inpatient/SNF/HHA/hospice/outpatient)
    Part C Medicare Advantage encounters (EDPS)
    Part D prescription drug events (PDE)

Those dropped claims still carry provider identity, geography, and payer linkage
on the CLAIM HEADER -- no professional line required:

    * CLM_BLG_PRVDR_ZIP5_CD + _ZIP4_CD + _USPS_STATE_CD + _LCLTY_CD
        the billing provider's geography (ZIP+4 = delivery-route precise). There
        is NO street line on the header -- resolve street via the crosswalks /
        PECOS practice-location tables using the NPI/OSCAR emitted here.
    * CLM_BLG_PRVDR_OSCAR_NUM / _FULL_CCN_NUM / _OSCAR_STATE_CD / _OSCAR_FAC_CD
        OSCAR/CCN is POPULATED on Part A here (it is blank on professional claims,
        where the sibling POS extract has to source it from V2_DIM_PRVDR_CRNT).
        The full CCN distinguishes multi-campus hospitals.
    * CLM_CNTRCT_OF_REC_* / CLM_SBMTR_CNTRCT_*  (contract + PBP)
        the provider<->plan edge from Part C encounters and Part D PDEs -- feeds
        the payer overlay.

So this extract recovers the institutional + MA-encounter + Part D provider
population the POS extract structurally cannot reach, at coarse-but-precise
(ZIP+4) geography, and it is CHEAPER than the POS pull: header-grain, no line
join, so no per-line fan-out.

DESIGN (identical philosophy to the POS wide extract):
  * Locations and links stay TOGETHER in one dataset.
  * Provider types are NOT condensed -- billing, attending, operating, other,
    referring, rendering, service, facility, and the CPO facility-org NPI each
    keep their own column, so a row shows the whole provider team that co-occurred
    on the same claim(s) at the same billing geography.
  * No patient identifier is emitted -- the MBI is consumed only inside
    COUNT(DISTINCT ...) and the small-cell HAVING filter (CMS 11+ rule).

  Output grain: one row per distinct combination of
    (billing TIN, billing NPI, 8 other provider-role NPI columns, OSCAR/CCN
     identity, header geography, plan/contract identifiers, claim-type code)
  with COUNT(DISTINCT beneficiary MBI) across the window, HAVING > MIN_CELL_BENE.

TWO GRAIN KNOBS worth knowing (both are just column-set lists below, so the
SELECT and GROUP BY can never drift):
  * CLM_TYPE_CD is IN the grain -> a biller that files inpatient AND outpatient
    shows as two rows tagged by type. Drop it from TYPE_COLS to collapse across
    types.
  * PLAN_COLS (contract + PBP) is IN the grain -> this is the payer edge, but
    contract varies by beneficiary enrollment, so it FRAGMENTS a provider's
    beneficiaries across plans and pushes more cells under the 11+ suppression
    floor. Empty out PLAN_COLS if you want provider/geography rows with maximal
    counts and no payer split.

STATUS -- KEPT as the documented dry-run / cost FALLBACK for
idr_medicare_combined_wide.py. The combined extract LEFT-joins the professional
line to add the POS street-address block in-grain, which makes it the largest,
most expensive pull (the long self-join variant already hit the 4-hour warehouse
cap at 24 months). If the combined 24-month run blows that cap, fall back to this
header-primary extract (all claim types, ZIP+4 geography, header-grain, no line
join -- so no per-line fan-out and far cheaper) plus a professional-only POS
companion. Retire this file once the combined dry-run passes QA.

CONFIGURABLE DATE SPAN
  Edit CLAIM_WINDOW_MONTHS below. The window ends CLAIM_WINDOW_LAG_MONTHS (2)
  months before today and stretches back this many months. Filtered on
  CLM_THRU_DT with CLM_FINL_ACTN_IND='Y' (Medicare final action) -- matches the
  combined extract and the corrected non-wide references.

All scaffolding -- config, auth, connection, and the COPY -> GET -> optional S3
-> REMOVE user-stage relay -- lives in idr_export_common.py.

Local (laptop) run -- picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicare_header_wide.py
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

# Small-cell suppression threshold. Keep only signature cells seen by MORE THAN
# this many distinct beneficiaries -- i.e. MIN_CELL_BENE + 1 and up.
# 10 -> the CMS "11 or more" cell-size rule.
MIN_CELL_BENE = 10

# Per-part size cap for the multi-file unload (Snowflake caps SINGLE=TRUE at 5 GB).
MULTI_PART_MAX_BYTES = 1_000_000_000


# ============================================================================
# COLUMN SETS  (kept as data so the SELECT and GROUP BY can never drift apart)
# ============================================================================

# Billing / organization NPI -- the identity the OSCAR/CCN + geography hang off.
ORG_NPI_COLS = [
    "CLM_BLG_PRVDR_NPI_NUM",
]

# Every other claim-stated provider-role NPI, each its own output column. Kept
# uncondensed: a single row shows the whole provider team on the claim. The CPO
# facility-org NPI (HHA/hospice under care-plan-oversight) is included -- it is a
# header-only role the POS extract never carried.
ROLE_NPI_COLS = [
    "CLM_ATNDG_PRVDR_NPI_NUM",         # attending
    "CLM_OPRTG_PRVDR_NPI_NUM",         # operating
    "CLM_OTHR_PRVDR_NPI_NUM",          # other
    "CLM_RFRG_PRVDR_NPI_NUM",          # referring
    "CLM_RNDRG_PRVDR_NPI_NUM",         # rendering
    "CLM_SRVC_PRVDR_NPI_NUM",          # service
    "CLM_FAC_PRVDR_NPI_NUM",           # facility
    "CLM_FAC_PRVDR_CPO_ORG_NPI_ID",    # CPO facility org (HHA/hospice)
]

# Billing-provider institutional identity. Functionally determined by the billing
# NPI, so grouping on these adds no rows -- they just travel with the biller.
# OSCAR/CCN is populated on Part A here (blank on Part B professional claims).
OSCAR_COLS = [
    "CLM_BLG_PRVDR_OSCAR_NUM",         # OSCAR / CCN (6-digit)
    "CLM_BLG_PRVDR_FULL_CCN_NUM",      # full CCN (distinguishes multi-campus)
    "CLM_BLG_PRVDR_OSCAR_STATE_CD",    # OSCAR state
    "CLM_BLG_PRVDR_OSCAR_FAC_CD",      # OSCAR facility-type (positions 3-5)
]

# Billing-provider HEADER geography -- the "location" for this extract. ZIP+4 is
# delivery-route precise; there is no street line on the header.
GEO_COLS = [
    "CLM_BLG_PRVDR_USPS_STATE_CD",
    "CLM_BLG_PRVDR_ZIP5_CD",
    "CLM_BLG_PRVDR_ZIP4_CD",
    "CLM_BLG_PRVDR_LCLTY_CD",
]

# Plan / contract identity -- the provider<->payer edge (Part C encounters +
# Part D PDEs). See the "TWO GRAIN KNOBS" note: this fragments counts. Empty the
# list to drop payer linkage and maximize per-cell beneficiary counts.
PLAN_COLS = [
    "CLM_CNTRCT_OF_REC_CNTRCT_NUM",    # Part D contract of record
    "CLM_CNTRCT_OF_REC_PBP_NUM",       # Part D plan benefit package
    "CLM_SBMTR_CNTRCT_NUM",            # submitting contract (MA encounter / PDE)
    "CLM_SBMTR_CNTRCT_PBP_NUM",        # submitting PBP
]

# Claim-type code (source + type of claim). In the grain so each row is tagged by
# part/type; drop to collapse across types. Emitted as the raw code -- decode via
# the IDR CLM_TYPE_CD reference table downstream if a label is needed.
TYPE_COLS = [
    "CLM_TYPE_CD",
]


def _norm(col):
    """TRIM and map '' / '~' to NULL, keeping the column (a missing role/field is
    NULL, not a dropped row)."""
    return f"NULLIF(NULLIF(TRIM({col}), ''), '~') AS {col}"


# ============================================================================
# WIDE MEDICARE HEADER QUERY
# ============================================================================

def build_medicare_header_wide_sql(stage_target, start_sql, end_sql, min_bene):
    """
    COPY INTO {stage_target} one row per distinct (billing TIN, all provider-role
    NPI columns, OSCAR/CCN identity, header geography, plan/contract ids, claim
    type) with the distinct-beneficiary count, from one window of final-action
    Medicare claims of ALL types (no professional-line join). Cells with
    <= min_bene distinct beneficiaries are suppressed.

    Unloaded as gzipped multi-file parts (SINGLE=FALSE); the driver merges them
    into one plain CSV locally.
    """
    # NPI columns and CLM_TYPE_CD are normalized; TIN gets the all-zeros guard;
    # OSCAR / geography / plan columns are TRIM/NULLIF-normalized too.
    npi_cols = ORG_NPI_COLS + ROLE_NPI_COLS
    norm_npis = [_norm(c) for c in npi_cols]
    norm_oscar = [_norm(c) for c in OSCAR_COLS]
    norm_geo = [_norm(c) for c in GEO_COLS]
    norm_plan = [_norm(c) for c in PLAN_COLS]

    base_select = ",\n        ".join(
        [
            # billing TIN -- also treat all-zeros as blank
            "CASE WHEN CLM_BLG_PRVDR_TAX_NUM IS NULL "
            "OR TRIM(CLM_BLG_PRVDR_TAX_NUM) IN ('', '~', '000000000') "
            "THEN NULL ELSE TRIM(CLM_BLG_PRVDR_TAX_NUM) END AS CLM_BLG_PRVDR_TAX_NUM",
            "CLM_BENE_MBI_ID",
        ]
        + norm_npis
        + norm_oscar
        + norm_geo
        + norm_plan
        + TYPE_COLS
    )

    # Aggregation grain: everything except the MBI. Column order is preserved so
    # the output reads biller -> roles -> OSCAR/CCN -> geography -> plan -> type.
    grain_cols = (
        ["CLM_BLG_PRVDR_TAX_NUM"]
        + npi_cols
        + OSCAR_COLS
        + GEO_COLS
        + PLAN_COLS
        + TYPE_COLS
    )
    grain_list = ",\n    ".join(grain_cols)

    return f"""
COPY INTO {stage_target}
FROM (

WITH base AS (
    SELECT
        {base_select}
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM
    WHERE CLM_THRU_DT       >= DATE '{start_sql}'
      AND CLM_THRU_DT        < DATE '{end_sql}'
      AND CLM_FINL_ACTN_IND  = 'Y'
      -- NO professional-line join: ALL claim types (Part A/B/C/D) are kept. The
      -- billing-provider geography and OSCAR/CCN live on the header, so the
      -- institutional / MA-encounter / PDE population that the POS extract drops
      -- is recovered here.
)

SELECT
    {grain_list},
    COUNT(DISTINCT CLM_BENE_MBI_ID) AS CNT_BENE
FROM base
GROUP BY
    {grain_list}
HAVING COUNT(DISTINCT CLM_BENE_MBI_ID) > {min_bene}

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
    banner      = "IDR Medicare wide provider + header-geography export"
    file_prefix = "idr_medicare_header_wide"

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
    log(f"Scope : ALL Medicare claim types (no professional-line join)")
    log(f"Plan/contract in grain : {'YES' if PLAN_COLS else 'no'}  |  "
        f"Claim-type in grain : {'YES' if TYPE_COLS else 'no'}")

    window    = f"{start:%Y_%m_%d}_to_{end:%Y_%m_%d}"
    filename  = f"{file_prefix}.{window}.csv"
    stage_dir = f"{file_prefix}.{window}"
    sql = build_medicare_header_wide_sql(
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
        # All-types header grain can be large. Probe the staged (gzip) size and
        # pick a delivery that fits local disk instead of blindly GETting it.
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
            log("    Reduce the grain to deliver: empty PLAN_COLS, coarsen ZIP4 "
                "-> ZIP5, shorten the window, or materialize as a Snowflake "
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
