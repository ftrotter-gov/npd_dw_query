"""
IDR Medicare COMBINED wide export -- one row per distinct claim "signature":
billing entity (TIN / OSCAR / CCN) + every provider-role NPI kept in its OWN
column + header geography + specialty/taxonomy/provider-type + type-of-bill +
payer/plan/contract + the place-of-service street-address block + the
place-of-service TYPE code, weighted by distinct beneficiaries.

WHAT THIS SUPERSEDES -- this single file replaces the former split:
  idr_medicare_entity_link_address_wide.py  (POS-address, professional only, INNER join)
  idr_medicare_header_wide.py               (all-types header, no POS)
  idr_medicare_entity_link_address.py       (long unpivot + self-join)
  idr_entity_linkage.py                     (org<->personal edges)
by unifying the header population and the professional-line POS address in one
LEFT-joined query. (idr_medicare_header_wide.py is KEPT for now as the documented
dry-run FALLBACK -- see "DRY-RUN / COST" below.)

DESIGN
  V2_MDCR_CLM (header, ALL claim types A/B/C/D, CLM_FINL_ACTN_IND='Y')
    grain spine: billing TIN + every role NPI (own column) + header OSCAR/CCN
                 identity + header geography + specialty/taxonomy/provider-type
                 + type-of-bill + plan/contract + CLM_TYPE_CD
        |  LEFT JOIN  (4-key: GEO_BENE_SK + CLM_DT_SGNTR_SK + CLM_NUM_SK + CLM_TYPE_CD)
        v
  V2_MDCR_CLM_LINE_PRFNL (professional line, where present)
    adds: POS street-address block + POS provider/org name + line
          specialty/locality
        |  + LEFT JOIN V2_MDCR_CLM_LINE (base line) on the FULL line key for the
        |    POS TYPE code (CLM_POS_CD) -- not on the prof-line view; kept on the
        |    same line as the POS address above.
        v
        |  GROUP BY the whole signature (POS cols IN-GRAIN; NULL for the
        |  non-professional population), COUNT(DISTINCT MBI) HAVING > MIN_CELL_BENE
        v
  LEFT JOIN a per-NPI-DEDUPED slice of V2_DIM_PRVDR_CRNT to FILL the billing
  provider's OSCAR/CCN (CLM_BLG_PRVDR_OSCAR_NUM is blank on the professional-line
  population, so it is sourced from the dimension instead). V2_DIM_PRVDR_CRNT is
  1:1 on PRVDR_SK, NOT on NPI -- several SK rows can share one NPI -- so it is
  collapsed to exactly one row per NPI (dim1 CTE) BEFORE the join, or the join
  would fan out the already-aggregated biller rows and re-inflate CNT_BENE after
  the 11+ suppression.

  The header->line join is LEFT (not INNER) so the institutional / MA-encounter /
  Part D population -- which has no professional line and therefore no POS street
  address -- is RECOVERED (NULL POS block), rather than dropped as the old
  INNER-join POS extract did. The 4-key join (GEO_BENE_SK + CLM_DT_SGNTR_SK +
  CLM_NUM_SK + CLM_TYPE_CD, idr-query rule #2) confines each claim's lines to that
  claim; the 2-key form fanned providers onto the POS addresses of a beneficiary's
  OTHER same-signature claims. CLM_TYPE_CD is REQUIRED: the 3-key alone is NOT
  unique on the final-action header (CLM_NUM_SK recurs across claim TYPES), so a
  3-key join would attach a professional line's POS block to a non-professional
  header sharing the 3-key.

  No patient identifier is emitted -- the MBI is consumed ONLY inside
  COUNT(DISTINCT ...) and the small-cell HAVING filter (CMS 11+ rule).

TWO GRAIN KNOBS (both are just column-set lists below, so the SELECT and GROUP BY
can never drift):
  * CLM_TYPE_CD is IN the grain -> a biller that files inpatient AND outpatient
    shows as two rows tagged by type. Drop it from TYPE_COLS to collapse.
  * PLAN_COLS (contract + PBP + plan) is IN the grain -> this is the provider<->
    payer edge, but plan/contract varies by beneficiary enrollment, so it
    FRAGMENTS a provider's beneficiaries across plans and pushes more cells under
    the 11+ suppression floor. Empty PLAN_COLS for provider/geography rows with
    maximal counts and no payer split.

CONFIGURABLE DATE SPAN
  Edit CLAIM_WINDOW_MONTHS below (or set the CLAIM_WINDOW_MONTHS env var). The
  window ends CLAIM_WINDOW_LAG_MONTHS (2) months before today and stretches back
  this many months. Filtered on CLM_THRU_DT with CLM_FINL_ACTN_IND='Y' (Medicare
  final action).

DRY-RUN / COST
  This LEFT-joined all-types + in-grain-POS pull is the LARGEST/most expensive
  extract; the old long self-join variant hit the 4-hour warehouse statement cap
  at 24 months. Run a 1-MONTH DRY-RUN first -- either flip CLAIM_WINDOW_MONTHS to
  1 (one-line change) or run with the env override:

      CLAIM_WINDOW_MONTHS=1 python3 idr/idr_medicare_combined_wide.py

  The measure-before-download size-probe guard (stage_dir_bytes -> plain / gzip /
  abort) is preserved below -- this is the large pull, so it never blindly GETs a
  result that will not fit local disk. If the 24-month run still blows the 4-hour
  cap, the documented FALLBACK is the header-primary + POS-companion split:
  idr_medicare_header_wide.py (all types, header ZIP+4, cheaper -- KEPT for this
  reason) plus a professional-only POS companion. Retire the fallback once this
  combined dry-run passes QA.

All scaffolding -- config, auth, connection, and the COPY -> GET -> optional S3
-> REMOVE user-stage relay -- lives in idr_export_common.py.

Local (laptop) run -- picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicare_combined_wide.py
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
# env override:  CLAIM_WINDOW_MONTHS=1 python3 idr/idr_medicare_combined_wide.py
CLAIM_WINDOW_MONTHS = int(os.environ.get("CLAIM_WINDOW_MONTHS") or 24)

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
# uncondensed: a single row shows the whole provider team on the claim.
ROLE_NPI_COLS = [
    "CLM_ATNDG_PRVDR_NPI_NUM",         # attending
    "CLM_OPRTG_PRVDR_NPI_NUM",         # operating
    "CLM_OTHR_PRVDR_NPI_NUM",          # other
    "CLM_RFRG_PRVDR_NPI_NUM",          # referring
    "CLM_RNDRG_PRVDR_NPI_NUM",         # rendering
    "CLM_SRVC_PRVDR_NPI_NUM",          # service
    "CLM_FAC_PRVDR_NPI_NUM",           # facility
    "CLM_FAC_PRVDR_CPO_ORG_NPI_ID",    # CPO facility org (HHA/hospice)
    "CLM_ALTRNT_SRVC_PRVDR_NPI_NUM",   # alternate service (new)
    "CLM_PRSCRBNG_PRVDR_NPI_NUM",      # prescribing (new)
    "CLM_PCP_NPI_NUM",                 # primary care physician (new)
]

# Billing-provider institutional identity that lives on the HEADER. OSCAR/CCN is
# populated on Part A here (blank on Part B professional claims). The OSCAR NUMBER
# itself (CLM_BLG_PRVDR_OSCAR_NUM) is NOT in this list -- it is filled from the
# provider dimension after aggregation (see final projection), because it is
# blank on the professional population; the full CCN, OSCAR state and OSCAR
# facility code have no dimension equivalent and are carried from the header.
OSCAR_HDR_COLS = [
    "CLM_BLG_PRVDR_FULL_CCN_NUM",      # full CCN (distinguishes multi-campus)
    "CLM_BLG_PRVDR_OSCAR_STATE_CD",    # OSCAR state
    "CLM_BLG_PRVDR_OSCAR_FAC_CD",      # OSCAR facility-type (positions 3-5)
]

# Billing-provider HEADER geography. ZIP+4 is delivery-route precise; there is no
# street line on the header (the POS block below carries the professional street).
GEO_COLS = [
    "CLM_BLG_PRVDR_USPS_STATE_CD",
    "CLM_BLG_PRVDR_ZIP5_CD",
    "CLM_BLG_PRVDR_ZIP4_CD",
    "CLM_BLG_PRVDR_LCLTY_CD",
    "CLM_BLG_PRVDR_CNTY_CD",            # county (new)
]

# Billing-provider specialty / taxonomy / provider-type (header). Functionally
# travels with the billing provider.
SPCLTY_COLS = [
    "CLM_BLG_PRVDR_TYPE_CD",           # provider type (new)
    "CLM_BLG_FED_PRVDR_SPCLTY_CD",     # federal specialty (new)
    "CLM_BLG_PRVDR_TXNMY_CD",          # taxonomy (new)
]

# Type-of-bill (header): facility type + classification + frequency.
TOB_COLS = [
    "CLM_BILL_FAC_TYPE_CD",            # (new)
    "CLM_BILL_CLSFCTN_CD",             # (new)
    "CLM_BILL_FREQ_CD",                # (new)
]

# Plan / contract identity -- the provider<->payer edge (Part C encounters +
# Part D PDEs). See the "TWO GRAIN KNOBS" note: this fragments beneficiary counts
# under the 11+ floor. Empty the list to drop payer linkage and maximize counts.
PLAN_COLS = [
    "CLM_CNTRCT_OF_REC_CNTRCT_NUM",    # Part D contract of record
    "CLM_CNTRCT_OF_REC_PBP_NUM",       # Part D plan benefit package
    "CLM_SBMTR_CNTRCT_NUM",            # submitting contract (MA encounter / PDE)
    "CLM_SBMTR_CNTRCT_PBP_NUM",        # submitting PBP
    "CLM_PLAN_CD",                     # plan code (new)
    "CLM_LCL_PLAN_CD",                 # local plan code (new)
    "CLM_SBMTR_ID",                    # submitter id (new)
]

# Place-of-service block from the professional claim line. IN-GRAIN: a claim with
# N distinct POS addresses -> N rows; NULL for the non-professional population
# (no professional line).
POS_COLS = [
    "CLM_POS_PRVDR_1ST_LINE_ADR",
    "CLM_POS_PRVDR_2ND_LINE_ADR",
    "CLM_POS_PRVDR_CITY_NAME",
    "CLM_POS_PRVDR_USPS_STATE_CD",
    "CLM_POS_PRVDR_ZIP5_CD",
    "CLM_POS_PRVDR_ZIP4_CD",
    "CLM_POS_PHYSN_ORG_NAME",          # POS physician/org name (new)
    "CLM_POS_PRVDR_1ST_NAME",          # POS provider first name (new)
    "CLM_POS_PRVDR_MDL_NAME",          # POS provider middle name (new)
]

# Place-of-service TYPE code (2-digit: 11 office, 12 home, 21 inpatient hospital,
# 31 SNF, ...). It is NOT on the professional-line view -- it lives on the base
# claim line V2_MDCR_CLM_LINE (POSL below), which shares the full line key
# (GEO_BENE_SK + CLM_DT_SGNTR_SK + CLM_NUM_SK + CLM_LINE_NUM) with the
# professional line, so it stays aligned to the SAME line as the POS street
# address above. IN-GRAIN, alongside the POS block. Emitted as the raw code --
# decode via the IDR CLM_POS_CD reference table downstream if a label is needed
# (matches CLM_TYPE_CD below and the Medicaid combined extract's raw CLM_POS_CD).
POS_CODE_COLS = [
    "CLM_POS_CD",
]

# Line-level specialty + pricing locality (professional line).
LINE_SPCLTY_COLS = [
    "CLM_PRVDR_SPCLTY_CD",
    "CLM_PRCNG_LCLTY_CD",
]

# Claim-type code (source + type of claim). In the grain so each row is tagged by
# part/type; drop to collapse across types. Emitted as the raw code (a NUMBER) --
# decode via the IDR CLM_TYPE_CD reference table downstream if a label is needed.
TYPE_COLS = [
    "CLM_TYPE_CD",
]


def _norm(qualified, alias):
    """TRIM and map '' / '~' to NULL, keeping the column (a missing role/field is
    NULL, not a dropped row). `qualified` is table-qualified (CLAIM./CLINE.);
    `alias` is the bare output name."""
    return f"NULLIF(NULLIF(TRIM({qualified}), ''), '~') AS {alias}"


# ============================================================================
# COMBINED WIDE MEDICARE QUERY
# ============================================================================

def build_medicare_combined_wide_sql(stage_target, start_sql, end_sql, min_bene):
    """
    COPY INTO {stage_target} one row per distinct (billing TIN, header OSCAR/CCN
    identity, all provider-role NPI columns, header geography, specialty/taxonomy/
    provider-type, type-of-bill, plan/contract, POS street-address block, line
    specialty/locality, claim type) with the distinct-beneficiary count, from one
    window of final-action Medicare claims of ALL types. Cells with <= min_bene
    distinct beneficiaries are suppressed.

      base   -- V2_MDCR_CLM LEFT JOIN V2_MDCR_CLM_LINE_PRFNL on the 4-key claim
                signature (GEO_BENE_SK + CLM_DT_SGNTR_SK + CLM_NUM_SK +
                CLM_TYPE_CD). The LEFT join keeps the institutional / MA-encounter /
                PDE population (NULL POS block); the 4-key confines each claim's
                lines to that claim (the 3-key is NOT unique on the final header --
                CLM_NUM_SK recurs across claim types). The POS TYPE code
                (CLM_POS_CD) is LEFT-joined from the base claim line
                V2_MDCR_CLM_LINE (POSL) on the full line key, aligned to the same
                line as the POS street address.
                Window filter is CLM_THRU_DT with CLM_FINL_ACTN_IND='Y'.

      agg    -- GROUP BY the whole signature (everything except the MBI and the
                dimension-sourced OSCAR number), COUNT(DISTINCT MBI), HAVING that
                count > min_bene (CMS 11+ small-cell suppression).

      dim1   -- V2_DIM_PRVDR_CRNT collapsed to ONE row per NPI. The dim is 1:1 on
                PRVDR_SK, not on NPI, so it is deduped with QUALIFY ROW_NUMBER()
                PARTITION BY TRIM(PRVDR_NPI_NUM), preferring a populated
                PRVDR_OSCAR_NUM and breaking ties on PRVDR_SK DESC (a unique
                surrogate key -> fully deterministic; the dim carries no source-
                effective date, and PRVDR_BIRTH_DT is PII and excluded). Shipped
                regardless of live cardinality: a "current" dim can gain a
                duplicate NPI later, and the dedup keeps the OSCAR fill from
                fanning out the aggregate.

      final  -- LEFT JOIN dim1 on the billing NPI to FILL the billing provider's
                OSCAR/CCN in position 2. The claim's own CLM_BLG_PRVDR_OSCAR_NUM
                is blank on the professional-line population, so it is sourced
                from the dimension (OSCAR populated only for institutional
                billers, NULL otherwise).

    Unloaded as gzipped multi-file parts (SINGLE=FALSE); the driver merges them
    into one CSV locally.
    """
    npi_cols = ORG_NPI_COLS + ROLE_NPI_COLS

    # base projection (table-qualified). Header cols come from CLAIM; the POS
    # address block + line specialty/locality come from the professional line
    # CLINE; the POS TYPE code comes from the base claim line POSL.
    base_select = ",\n        ".join(
        [
            # billing TIN -- also treat all-zeros as blank
            "CASE WHEN CLAIM.CLM_BLG_PRVDR_TAX_NUM IS NULL "
            "OR TRIM(CLAIM.CLM_BLG_PRVDR_TAX_NUM) IN ('', '~', '000000000') "
            "THEN NULL ELSE TRIM(CLAIM.CLM_BLG_PRVDR_TAX_NUM) END AS CLM_BLG_PRVDR_TAX_NUM",
            "CLAIM.CLM_BENE_MBI_ID",
        ]
        + [_norm(f"CLAIM.{c}", c) for c in OSCAR_HDR_COLS]
        + [_norm(f"CLAIM.{c}", c) for c in npi_cols]
        + [_norm(f"CLAIM.{c}", c) for c in GEO_COLS]
        + [_norm(f"CLAIM.{c}", c) for c in SPCLTY_COLS]
        + [_norm(f"CLAIM.{c}", c) for c in TOB_COLS]
        + [_norm(f"CLAIM.{c}", c) for c in PLAN_COLS]
        + [_norm(f"CLINE.{c}", c) for c in POS_COLS]
        + [_norm(f"POSL.{c}", c) for c in POS_CODE_COLS]
        + [_norm(f"CLINE.{c}", c) for c in LINE_SPCLTY_COLS]
        + [f"CLAIM.{c} AS {c}" for c in TYPE_COLS]
    )

    # Aggregation grain: everything except the MBI and the dimension OSCAR number.
    # Column order is preserved so the output reads TIN -> OSCAR/CCN identity ->
    # roles -> geography -> specialty -> type-of-bill -> plan -> POS address ->
    # POS type code -> line specialty -> type.
    grain_cols = (
        ["CLM_BLG_PRVDR_TAX_NUM"]
        + OSCAR_HDR_COLS
        + npi_cols
        + GEO_COLS
        + SPCLTY_COLS
        + TOB_COLS
        + PLAN_COLS
        + POS_COLS
        + POS_CODE_COLS
        + LINE_SPCLTY_COLS
        + TYPE_COLS
    )
    grain_list = ",\n        ".join(grain_cols)

    # Final projection: keep column order, with the OSCAR NUMBER back in position 2
    # sourced from the dimension (normalized '' / '~' -> NULL).
    final_cols = (
        ["agg.CLM_BLG_PRVDR_TAX_NUM",
         "NULLIF(NULLIF(TRIM(dim1.PRVDR_OSCAR_NUM), ''), '~') AS CLM_BLG_PRVDR_OSCAR_NUM"]
        + [f"agg.{c}" for c in OSCAR_HDR_COLS]
        + [f"agg.{c}" for c in npi_cols]
        + [f"agg.{c}" for c in GEO_COLS]
        + [f"agg.{c}" for c in SPCLTY_COLS]
        + [f"agg.{c}" for c in TOB_COLS]
        + [f"agg.{c}" for c in PLAN_COLS]
        + [f"agg.{c}" for c in POS_COLS]
        + [f"agg.{c}" for c in POS_CODE_COLS]
        + [f"agg.{c}" for c in LINE_SPCLTY_COLS]
        + [f"agg.{c}" for c in TYPE_COLS]
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
    LEFT JOIN IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM_LINE_PRFNL AS CLINE
        ON CLINE.GEO_BENE_SK     = CLAIM.GEO_BENE_SK
       AND CLINE.CLM_DT_SGNTR_SK = CLAIM.CLM_DT_SGNTR_SK
       AND CLINE.CLM_NUM_SK      = CLAIM.CLM_NUM_SK
       AND CLINE.CLM_TYPE_CD     = CLAIM.CLM_TYPE_CD
    LEFT JOIN IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM_LINE AS POSL
        ON POSL.GEO_BENE_SK      = CLINE.GEO_BENE_SK
       AND POSL.CLM_DT_SGNTR_SK  = CLINE.CLM_DT_SGNTR_SK
       AND POSL.CLM_NUM_SK       = CLINE.CLM_NUM_SK
       AND POSL.CLM_LINE_NUM     = CLINE.CLM_LINE_NUM
       -- POS TYPE code lives on the base claim line, keyed 1:1 with the
       -- professional line on the full line key, so it stays on the SAME line as
       -- the POS street address above. LEFT so a professional line with no
       -- base-line match (and the non-professional population, where CLINE is
       -- already NULL) keeps the row with CLM_POS_CD just NULL.
    WHERE CLAIM.CLM_THRU_DT       >= DATE '{start_sql}'
      AND CLAIM.CLM_THRU_DT        < DATE '{end_sql}'
      AND CLAIM.CLM_FINL_ACTN_IND  = 'Y'
      -- LEFT join on the 4-key claim signature (GEO_BENE_SK + CLM_DT_SGNTR_SK +
      -- CLM_NUM_SK + CLM_TYPE_CD): ALL claim types (Part A/B/C/D) are kept, the
      -- professional POS block is attached where a line exists (NULL otherwise),
      -- and each claim's lines stay confined to that claim. CLM_TYPE_CD is
      -- REQUIRED in the join: the 3-key alone is NOT unique on the final header
      -- (CLM_NUM_SK recurs across claim TYPES for a bene/date-signature -- verified
      -- live: 233,458,245 final headers vs 232,237,139 distinct 3-keys), so a
      -- 3-key join would attach a professional line's POS block to a
      -- NON-professional header that merely shares the 3-key. The 4-key is exactly
      -- unique per header row.
),

agg AS (
    SELECT
        {grain_list},
        COUNT(DISTINCT CLM_BENE_MBI_ID) AS CNT_BENE
    FROM base
    GROUP BY
        {grain_list}
    HAVING COUNT(DISTINCT CLM_BENE_MBI_ID) > {min_bene}
),

dim1 AS (
    -- V2_DIM_PRVDR_CRNT is 1:1 on PRVDR_SK, NOT on NPI: collapse to exactly one
    -- row per NPI BEFORE the fill-join so it cannot fan out the aggregate and
    -- re-inflate CNT_BENE. Prefer a populated OSCAR, then break ties on the
    -- unique surrogate key PRVDR_SK DESC -> fully deterministic (the dim carries
    -- no source-effective date; PRVDR_BIRTH_DT is PII and is not used).
    SELECT
        PRVDR_NPI_NUM,
        PRVDR_OSCAR_NUM
    FROM IDRC_PRD.CMS_VDM_VIEW_SMNTC_PRD.V2_DIM_PRVDR_CRNT
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY TRIM(PRVDR_NPI_NUM)
        ORDER BY IFF(NULLIF(TRIM(PRVDR_OSCAR_NUM), '') IS NULL, 1, 0),
                 PRVDR_SK DESC
    ) = 1
)

SELECT
    {final_list}
FROM agg
LEFT JOIN dim1
    ON TRIM(dim1.PRVDR_NPI_NUM) = agg.CLM_BLG_PRVDR_NPI_NUM

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
    banner      = "IDR Medicare combined wide provider + geography + POS export"
    file_prefix = "idr_medicare_combined_wide"

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
        f"distinct beneficiaries ({min_bene + 1}+, CMS 11+ rule)")
    log(f"Scope : ALL Medicare claim types (header LEFT JOIN professional line, POS in-grain)")
    log(f"Plan/contract in grain : {'YES' if PLAN_COLS else 'no'}  |  "
        f"Claim-type in grain : {'YES' if TYPE_COLS else 'no'}")

    window    = f"{start:%Y_%m_%d}_to_{end:%Y_%m_%d}"
    filename  = f"{file_prefix}.{window}.csv"
    stage_dir = f"{file_prefix}.{window}"
    sql = build_medicare_combined_wide_sql(
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
        # This is the largest/most expensive extract (all-types header x POS
        # in-grain). Probe the staged (gzip) size and pick a delivery that fits
        # local disk instead of blindly GETting a result that could be a TB of
        # plain CSV.
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
                "-> ZIP5, shorten the window, fall back to the header-primary + "
                "POS-companion split, or materialize as a Snowflake table. "
                "Re-run after adjusting.")
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
