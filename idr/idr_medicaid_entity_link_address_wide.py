"""
IDR Medicaid wide provider + address export -- one row per distinct claim
"signature": every provider-role NPI kept in its OWN column + the service-
location address, weighted by distinct recipients.

This is the Medicaid counterpart to idr_medicare_entity_link_address_wide.py and
the wide restructure of idr_medicaid_address.py (which UNPIVOTED the role NPIs
into rows). Provider types are NOT condensed: admitting, billing, supervising,
and service-location-org each stay in a separate column, so a row shows the whole
provider set that co-occurred on the same claim(s) at the same service location.
Locations and links stay together in one dataset.

  Output grain: one row per distinct combination of
    (admitting NPI, billing NPI, supervising NPI, service-location-org NPI,
     service-location address, place-of-service TYPE code [CLM_POS_CD + decoded
     description])
  with COUNT(DISTINCT recipient State Medicaid ID) across the window. Small-cell
  suppression IS applied -- signature+address cells seen by MIN_CELL_BENE or fewer
  distinct recipients are dropped (the CMS "11 or more" rule at the default
  MIN_CELL_BENE=10). No recipient id is emitted -- only the aggregated count.

Column set follows idr_medicaid_address.py exactly (the roles that view exposes).
If V2_MDCD_CLM carries additional provider-role NPI columns you want kept, add
them to ROLE_NPI_COLS below -- the SELECT and GROUP BY are generated from it.

CONFIGURABLE DATE SPAN
  Edit CLAIM_WINDOW_MONTHS below. The window ends CLAIM_WINDOW_LAG_MONTHS (2)
  months before today and stretches back this many months. Medicaid claims are
  filtered on CLM_THRU_DT (matching idr_medicaid_address.py) AND to final-action
  only (CLM_FINL_ACTN_IND='T' -- note 'T'/'F', not Medicare's 'Y'/'N'), so
  superseded original/adjustment/void versions of a claim do not double-count
  recipients or carry since-corrected provider/address combinations.

Local (laptop) run -- picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with Medicaid claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicaid_entity_link_address_wide.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import (
    load_config,
    compute_window,
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

CLAIM_WINDOW_MONTHS = 24

# Small-cell suppression threshold. Keep only signature+address cells seen by
# MORE THAN this many distinct recipients -- i.e. MIN_CELL_BENE + 1 and up.
# 10 -> the CMS "11 or more" cell-size rule.
MIN_CELL_BENE = 10

MULTI_PART_MAX_BYTES = 1_000_000_000


# ============================================================================
# COLUMN SETS  (kept as data so the SELECT and GROUP BY can never drift apart)
# ============================================================================

# Every provider-role NPI column on V2_MDCD_CLM, each kept as its own output
# column (same roles idr_medicaid_address.py unpivoted).
ROLE_NPI_COLS = [
    "CLM_ADMTG_PRVDR_NPI_NUM",     # admitting
    "CLM_BLG_PRVDR_NPI_NUM",       # billing
    "CLM_SPRVSNG_PRVDR_NPI_NUM",   # supervising
    "CLM_SRVC_LCTN_ORG_NPI_NUM",   # service-location organization
]

# Service-location address columns.
ADDR_COLS = [
    "CLM_SRVC_LCTN_LINE_1_ADR",
    "CLM_SRVC_LCTN_LINE_2_ADR",
    "CLM_SRVC_LCTN_CITY_NAME",
    "CLM_SRVC_LCTN_STATE_CD",
    "CLM_SRVC_LCTN_ZIP_CD",
]

# Place-of-service TYPE code. Unlike Medicare, the Medicaid POS code is ON the
# claim table itself (V2_MDCD_CLM.CLM_POS_CD) -- no line join needed. The decoded
# description is attached afterward from the V2_MDCD_CLM_POS_CD dimension.
POS_COL = "CLM_POS_CD"


def _norm(col):
    """TRIM and map '' / '~' to NULL, keeping the column (a missing role is NULL,
    not a dropped row)."""
    return f"NULLIF(NULLIF(TRIM({col}), ''), '~') AS {col}"


# ============================================================================
# WIDE MEDICAID QUERY
# ============================================================================

def build_medicaid_wide_sql(stage_target, start_sql, end_sql, min_bene):
    """
    COPY INTO {stage_target} one row per distinct (all provider-role NPI columns,
    service-location address) with the distinct-recipient count, from one window
    of Medicaid claims (V2_MDCD_CLM). Signature+address cells with <= min_bene
    distinct recipients are suppressed.

      base   -- project the role NPI columns (each normalized to NULL when
                blank), the service-location address, and the recipient id.
                Window filter is CLM_THRU_DT. The service-location address is
                optional -- rows are kept even when it is blank/NULL (address is
                enrichment, not a filter).

      final  -- GROUP BY all role NPI columns + the address columns,
                COUNT(DISTINCT recipient id), then HAVING that count > min_bene.
                Small-cell suppression: signature+address cells seen by
                <= min_bene distinct recipients are dropped (CMS 11+ rule at the
                default 10), so no low-count cell reaches the output.

    Unloaded as gzipped multi-file parts (SINGLE=FALSE); the driver merges them
    into one plain CSV locally.
    """
    role_norm = [_norm(c) for c in ROLE_NPI_COLS]

    base_select = ",\n        ".join(
        role_norm
        + [f"{c} AS {c}" for c in ADDR_COLS]
        + [f"NULLIF(NULLIF(TRIM({POS_COL}), ''), '~') AS {POS_COL}"]
        + ["CLM_RCPNT_STATE_MDCD_ID"]
    )

    # Grain: all role NPIs + address + POS code. The decoded POS description is
    # NOT grouped -- it is attached afterward from the dimension and is
    # functionally determined by the code, so it adds no rows.
    group_cols  = ROLE_NPI_COLS + ADDR_COLS + [POS_COL]
    group_list  = ",\n        ".join(group_cols)

    # Final projection: grain cols, then POS code + decoded description, then count.
    final_cols = (
        [f"agg.{c}" for c in ROLE_NPI_COLS]
        + [f"agg.{c}" for c in ADDR_COLS]
        + [f"agg.{POS_COL}",
           "NULLIF(TRIM(POS.CLM_POS_CD_DESC), '') AS CLM_POS_CD_DESC"]
        + ["agg.CNT_RECIPIENTS"]
    )
    final_list = ",\n    ".join(final_cols)

    return f"""
COPY INTO {stage_target}
FROM (

WITH base AS (
    SELECT
        {base_select}
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM
    WHERE CLM_THRU_DT >= DATE '{start_sql}'
      AND CLM_THRU_DT <  DATE '{end_sql}'
      AND CLM_RCPNT_STATE_MDCD_ID IS NOT NULL
      AND CLM_FINL_ACTN_IND = 'T'
      -- FINAL-ACTION ONLY. V2_MDCD_CLM carries original + adjustment + voided
      -- claim versions, each with its own CLM_UNIQ_ID (~8.5% of rows are
      -- non-final). Without this filter, superseded versions double-count
      -- recipients and attach them to since-corrected provider/address combos --
      -- the Medicaid analog of the Medicare claim-grain bug. NOTE the domain is
      -- 'T'/'F' here, NOT 'Y'/'N' as on Medicare's V2_MDCR_CLM -- filtering ='Y'
      -- would silently return zero rows.
      -- NOTE: the service-location address is NOT required. It is optional
      -- enrichment -- rows are kept even when the address columns are blank/NULL.
),

agg AS (
    SELECT
        {group_list},
        COUNT(DISTINCT CLM_RCPNT_STATE_MDCD_ID) AS CNT_RECIPIENTS
    FROM base
    GROUP BY
        {group_list}
    HAVING COUNT(DISTINCT CLM_RCPNT_STATE_MDCD_ID) > {min_bene}
)

SELECT
    {final_list}
FROM agg
LEFT JOIN (
    SELECT CLM_POS_CD, MAX(CLM_POS_CD_DESC) AS CLM_POS_CD_DESC
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM_POS_CD
    GROUP BY CLM_POS_CD
) AS POS
    ON POS.CLM_POS_CD = agg.CLM_POS_CD

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
    banner      = "IDR Medicaid wide provider + address export"
    file_prefix = "idr_medicaid_entity_link_address_wide"

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
        f"distinct recipients ({min_bene + 1}+, CMS 11+ rule)")

    window    = f"{start:%Y_%m_%d}_to_{end:%Y_%m_%d}"
    filename  = f"{file_prefix}.{window}.csv"
    stage_dir = f"{file_prefix}.{window}"
    sql = build_medicaid_wide_sql(
        f"@~/{stage_dir}/", start.isoformat(), end.isoformat(), min_bene
    )

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
