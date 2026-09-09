"""
IDR Medicare PROVIDER EDGE LIST -- the graph-loadable LONG form: one row per
UNORDERED provider-pair (npi_a < npi_b) that co-occurred on the SAME Medicare
claim, weighted by the count of distinct beneficiaries, with the two source-role
labels carried.

WHAT THIS RECOVERS -- this restores the graph edge list the retired
idr_entity_linkage.py produced (org<->individual affiliation edges), but as a
general provider<->provider co-occurrence edge list across ALL claim-stated
header roles, and with the count-corrupting bugs of the old file FIXED:

  Bug B (final action) -- kept: CLM_FINL_ACTN_IND='Y' (Medicare Y/N domain), so
    original/adjustment/voided rows do not double-count beneficiaries.

  Bug D (dropped population) -- FIXED: the old file filtered
    CLM_BLG_PRVDR_OSCAR_NUM IS NOT NULL, which discarded the ENTIRE professional
    (Part B) population (OSCAR is blank there). OSCAR is NOT used here at all --
    it is an institutional billing identifier, not part of a provider<->provider
    edge -- so no population is dropped on its account.

  Fan-out across a bene's OTHER claims -- FIXED: the co-occurrence key is the
    full 4-key CLAIM SIGNATURE (GEO_BENE_SK + CLM_DT_SGNTR_SK + CLM_NUM_SK +
    CLM_TYPE_CD), idr-query rule #2, NOT a 2-key. A 2-key self-join would have
    paired providers who never shared a claim, merely a beneficiary; a 3-key
    (without CLM_TYPE_CD) still pairs across distinct claims of different types
    that share a CLM_NUM_SK (the 3-key is NOT unique on the final header -- see
    CLAIM_KEY below).

DESIGN
  base   -- V2_MDCR_CLM, one window of final-action claims (CLM_THRU_DT window +
            CLM_FINL_ACTN_IND='Y'), projecting the 3-key claim signature, the MBI
            (consumed only by the count), and every header role NPI.

  roles  -- UNPIVOT the role NPI columns to long via UNION ALL: one row per
            (claim signature, MBI, source_role, npi), blank/'~'/NULL NPIs dropped.
            The role set is EXACTLY the header role NPIs idr_medicare_combined_wide
            emits: billing, attending, operating, other, referring, rendering,
            service, facility, CPO-org, alt-service, prescribing, PCP.

  pairs  -- SELF-JOIN roles to roles WITHIN the same claim signature, keeping only
            UNORDERED distinct pairs (a.npi < b.npi -> npi_a<>npi_b and each pair
            once). Both sides carry the same claim's MBI.

  final  -- GROUP BY (npi_a, npi_b, source_role_a, source_role_b),
            COUNT(DISTINCT MBI) AS CNT_BENE, HAVING > MIN_CELL_BENE (CMS 11+).

  No patient identifier is emitted -- the MBI is consumed ONLY inside
  COUNT(DISTINCT ...) and the small-cell HAVING. Emitted columns are
  npi_a, npi_b, source_role_a, source_role_b, CNT_BENE -- all patient-free.

CONFIGURABLE DATE SPAN
  Edit CLAIM_WINDOW_MONTHS below (or set the CLAIM_WINDOW_MONTHS env var). The
  window ends CLAIM_WINDOW_LAG_MONTHS (2) months before today and stretches back
  this many months. Filtered on CLM_THRU_DT with CLM_FINL_ACTN_IND='Y'.

DRY-RUN / COST  *** READ FIRST ***
  This is the MOST EXPENSIVE extract in the set: the long unpivot fans each claim
  into up to 12 role rows and the in-claim self-join is quadratic in the roles per
  claim, so the old unpivot+self-join variant blew the 4-hour warehouse statement
  cap at 24 months. RUN A 1-MONTH DRY-RUN FIRST -- either flip
  CLAIM_WINDOW_MONTHS to 1 (one-line change) or use the env override:

      CLAIM_WINDOW_MONTHS=1 python3 idr/idr_provider_edge_list.py

  The measure-before-download size-probe guard (stage_dir_bytes -> plain / gzip /
  abort, *7 plain estimate) is included below so a large result never blindly GETs
  onto local disk. If the 24-month run still blows the 4-hour cap, the fallbacks
  are: shorten the window, drop the lowest-value roles from ROLE_NPIS, raise
  MIN_CELL_BENE, or materialize the pairs as a Snowflake table and aggregate there.

All scaffolding -- config, auth, connection, and the COPY -> GET -> optional S3
-> REMOVE user-stage relay -- lives in idr_export_common.py.

Local (laptop) run -- picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_provider_edge_list.py
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
# env override:  CLAIM_WINDOW_MONTHS=1 python3 idr/idr_provider_edge_list.py
CLAIM_WINDOW_MONTHS = int(os.environ.get("CLAIM_WINDOW_MONTHS") or 24)

# Small-cell suppression threshold. Keep only edges seen by MORE THAN this many
# distinct beneficiaries -- i.e. MIN_CELL_BENE + 1 and up. 10 -> CMS "11 or more".
MIN_CELL_BENE = 10

# Per-part size cap for the multi-file unload (Snowflake caps SINGLE=TRUE at 5 GB).
MULTI_PART_MAX_BYTES = 1_000_000_000


# ============================================================================
# COLUMN SETS  (kept as data so the SELECT and the unpivot can never drift)
# ============================================================================

# Every claim-stated header provider-role NPI, paired with its edge role label.
# This is EXACTLY the set idr_medicare_combined_wide.py emits (ORG_NPI_COLS +
# ROLE_NPI_COLS) -- billing plus the 11 other roles. Each becomes one arm of the
# unpivot UNION ALL. Drop the lowest-value roles here to shrink the self-join.
ROLE_NPIS = [
    ("CLM_BLG_PRVDR_NPI_NUM",        "billing"),
    ("CLM_ATNDG_PRVDR_NPI_NUM",      "attending"),
    ("CLM_OPRTG_PRVDR_NPI_NUM",      "operating"),
    ("CLM_OTHR_PRVDR_NPI_NUM",       "other"),
    ("CLM_RFRG_PRVDR_NPI_NUM",       "referring"),
    ("CLM_RNDRG_PRVDR_NPI_NUM",      "rendering"),
    ("CLM_SRVC_PRVDR_NPI_NUM",       "service"),
    ("CLM_FAC_PRVDR_NPI_NUM",        "facility"),
    ("CLM_FAC_PRVDR_CPO_ORG_NPI_ID", "cpo_org"),
    ("CLM_ALTRNT_SRVC_PRVDR_NPI_NUM", "alt_service"),
    ("CLM_PRSCRBNG_PRVDR_NPI_NUM",   "prescribing"),
    ("CLM_PCP_NPI_NUM",              "pcp"),
]

# The claim signature (idr-query rule #2): confines a claim's role NPIs to that
# claim, so the self-join never pairs providers across a bene's OTHER claims.
# CLM_TYPE_CD is REQUIRED here: the 3-key (GEO_BENE_SK + CLM_DT_SGNTR_SK +
# CLM_NUM_SK) is NOT unique on the final-action header -- CLM_NUM_SK recurs across
# claim TYPES for the same bene/date-signature (verified live: 233,458,245 final
# headers vs 232,237,139 distinct 3-keys; ~1.16M 3-key groups carry >1 distinct
# billing NPI). Without CLM_TYPE_CD the self-join pairs providers across distinct
# claims of different types that merely share a 3-key (e.g. spurious billing<->
# billing edges). The 4-key IS exactly unique per header row (233,458,245 ==
# 233,458,245), so it is the true co-occurrence key.
CLAIM_KEY = ["GEO_BENE_SK", "CLM_DT_SGNTR_SK", "CLM_NUM_SK", "CLM_TYPE_CD"]


# ============================================================================
# PROVIDER EDGE-LIST QUERY
# ============================================================================

def build_provider_edge_list_sql(stage_target, start_sql, end_sql, min_bene):
    """
    COPY INTO {stage_target} one row per unordered co-occurring provider pair
    (npi_a < npi_b) with its two source-role labels and the count of distinct
    beneficiaries, from one window of final-action Medicare claims. Edges with
    <= min_bene distinct beneficiaries are suppressed.
    """
    key_cols = ", ".join(CLAIM_KEY)

    # base: window + final-action, projecting the claim key, the MBI, and every
    # role NPI (raw; normalized per-arm in the unpivot below).
    base_role_cols = ",\n        ".join(col for col, _ in ROLE_NPIS)

    # roles: one UNION ALL arm per role. Each arm normalizes the NPI ('' / '~' ->
    # NULL) and drops rows with no NPI, so the self-join only sees real providers.
    role_arms = "\n\n    UNION ALL\n\n".join(
        f"""    SELECT
        {key_cols},
        CLM_BENE_MBI_ID,
        '{label}' AS source_role,
        NULLIF(NULLIF(TRIM({col}), ''), '~') AS npi
    FROM base
    WHERE NULLIF(NULLIF(TRIM({col}), ''), '~') IS NOT NULL"""
        for col, label in ROLE_NPIS
    )

    join_on = "\n       AND ".join(f"a.{k} = b.{k}" for k in CLAIM_KEY)

    return f"""
COPY INTO {stage_target}
FROM (

WITH base AS (
    SELECT
        {key_cols},
        CLM_BENE_MBI_ID,
        {base_role_cols}
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM
    WHERE CLM_THRU_DT       >= DATE '{start_sql}'
      AND CLM_THRU_DT        < DATE '{end_sql}'
      AND CLM_FINL_ACTN_IND  = 'Y'
      -- CLM_FINL_ACTN_IND='Y' : Medicare final action (Y/N domain). Also collapses
      -- each claim signature to its one final header row, so the 3-key self-join
      -- below sees a single set of roles per claim.
),

roles AS (
{role_arms}
),

pairs AS (
    -- self-join WITHIN one claim signature; a.npi < b.npi keeps each unordered
    -- pair once and guarantees npi_a <> npi_b. Both sides carry the same claim's
    -- beneficiary (the MBI is consumed only by the count downstream).
    SELECT
        a.npi          AS npi_a,
        b.npi          AS npi_b,
        a.source_role  AS source_role_a,
        b.source_role  AS source_role_b,
        a.CLM_BENE_MBI_ID AS CLM_BENE_MBI_ID
    FROM roles AS a
    JOIN roles AS b
        ON {join_on}
       AND a.npi < b.npi
)

SELECT
    npi_a,
    npi_b,
    source_role_a,
    source_role_b,
    COUNT(DISTINCT CLM_BENE_MBI_ID) AS CNT_BENE
FROM pairs
GROUP BY
    npi_a,
    npi_b,
    source_role_a,
    source_role_b
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
    banner      = "IDR Medicare provider edge list (co-occurrence graph)"
    file_prefix = "idr_provider_edge_list"

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
    else:
        log("  NOTE: this is the MOST EXPENSIVE extract (long unpivot + in-claim "
            "self-join). Run a 1-month DRY-RUN first: CLAIM_WINDOW_MONTHS=1")
    min_bene = MIN_CELL_BENE
    log(f"Small-cell suppression : ENABLED -- keep edges with > {min_bene} "
        f"distinct beneficiaries ({min_bene + 1}+, CMS 11+ rule)")
    log(f"Roles unpivoted : {len(ROLE_NPIS)}  |  co-occurrence key : {'+'.join(CLAIM_KEY)}")

    window    = f"{start:%Y_%m_%d}_to_{end:%Y_%m_%d}"
    filename  = f"{file_prefix}.{window}.csv"
    stage_dir = f"{file_prefix}.{window}"
    sql = build_provider_edge_list_sql(
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
        # The unpivot+self-join can produce a very large edge list. Probe the
        # staged (gzip) size and pick a delivery that fits local disk instead of
        # blindly GETting a result that could overrun the disk.
        c_bytes   = stage_dir_bytes(conn, stage_dir)
        # gzip'd CSV expands ~5-7x on decompress; this payload is short, repetitive
        # NPIs/role labels that gzip HARDER, so use the top of the range (7x) to
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
            log("    Reduce the grain to deliver: shorten the window, drop roles "
                "from ROLE_NPIS, raise MIN_CELL_BENE, or materialize the pairs as "
                "a Snowflake table. Re-run after adjusting.")
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
