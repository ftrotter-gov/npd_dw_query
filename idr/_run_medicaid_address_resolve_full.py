"""
FULL LOCAL export driver for idr_medicaid_address_resolve.py (Medicaid).

Unlike _run_medicaid_address_resolve_local.py (a scoped, print-only smoke test),
this runs the resolver UNSCOPED over the full CLAIM_WINDOW_MONTHS window and lands
the whole result as a CSV on local disk -- the laptop equivalent of the resolver's
Snowpark-only MedicaidAddressResolveExporter.do_idr_output().

The resolver's build_medicaid_address_resolve_sql() returns a bare `WITH ... SELECT`
(so IDROutputter can wrap it). IDROutputter needs get_active_session() (Snowpark),
which does not exist on a laptop, so here we wrap that same SELECT in a COPY INTO
@~/<stage_dir>/ ourselves -- byte-for-byte the FILE_FORMAT the proven
idr_medicaid_combined_wide.py uses -- then unload -> size-guard -> GET/merge ->
REMOVE, all via idr_export_common's user-stage relay.

STAGE ISOLATION (important -- a 35-table idr2 bulk export may be running in another
session against the SAME per-user stage @~/): this driver writes ONLY to
@~/idr_medicaid_address_resolve.<window>/, a uniquely named stage dir that cannot
collide with that export's per-table v2_prvdr_enrlmt_* dirs, and its LIST / GET /
REMOVE are all scoped to that one dir. It never touches other stage dirs, S3, or
_watermarks.json.

PII BOUNDARY: the resolver selects no patient identifier and excludes provider
birth/death/sex; recipient ids are consumed only inside COUNT(DISTINCT) upstream.
Output is provider-directory-grade address resolution. It lands on LOCAL disk only
(no S3 unless S3_BUCKET is set explicitly).

COST: full unscoped scan of V2_MDCD_CLM over the window on IDRC_PRD_COMM_WH.

Usage:
    CLAIM_WINDOW_MONTHS=24 OUTPUT_DIR=./idr_data \
      .idrvenv/bin/python3 idr/_run_medicaid_address_resolve_full.py
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Connection identity comes from the environment -- SNOWFLAKE_ACCOUNT and
# SNOWFLAKE_USER are intentionally NOT baked into this file, so it is safe to commit.
# Set both before running (e.g. via the calling shell or a local, un-committed env).
_missing = [v for v in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER") if not os.environ.get(v)]
if _missing:
    sys.exit("set " + " and ".join(_missing) + " in the environment before running "
             "(connection identity is intentionally not hardcoded here)")

# Operational defaults (not identity/secrets). 24-month window; role/warehouse the
# combined_wide unloads use. COPY INTO @~/ targets the current user's OWN stage,
# available under any role, so this lands in the user's own stage regardless of role.
os.environ.setdefault("SNOWFLAKE_ROLE", "IDRSF_DATA_PRVDR_PVT_P")
os.environ.setdefault("SNOWFLAKE_WAREHOUSE", "IDRC_PRD_COMM_WH")
os.environ.setdefault("CLAIM_WINDOW_MONTHS", "24")   # read by R at import -> must precede it
os.environ.setdefault("OUTPUT_DIR", "./idr_data")

from idr_export_common import (  # noqa: E402
    load_config,
    resolve_auth,
    connect,
    unload_to_stage_multifile,
    stage_dir_bytes,
    get_and_merge_stage_dir,
    upload_and_validate,
    remove_stage_dir,
    log,
)
import idr_medicaid_address_resolve as R  # noqa: E402

MULTI_PART_MAX_BYTES = 1_000_000_000
FILE_PREFIX = "idr_medicaid_address_resolve"


def build_copy_into_sql(stage_target):
    """Wrap the resolver's bare SELECT in the same COPY INTO / FILE_FORMAT the
    proven idr_medicaid_combined_wide.py driver uses (gzip multi-file parts, merged
    locally by get_and_merge_stage_dir)."""
    inner = R.build_medicaid_address_resolve_sql()
    return f"""
COPY INTO {stage_target}
FROM (
{inner}
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


def main():
    banner = "IDR Medicaid ADDRESS-RESOLVE full export -- Snowflake -> local CSV"
    log("=" * 64)
    log(banner)
    log("=" * 64)

    start_sql, end_sql = R._window_bounds()
    window = f"{start_sql.replace('-', '_')}_to_{end_sql.replace('-', '_')}"
    filename = f"{FILE_PREFIX}.{window}.csv"
    stage_dir = f"{FILE_PREFIX}.{window}"          # unique -> no collision with idr2 export

    cfg = load_config()
    log(f"Claim window     : {start_sql} -> {end_sql} "
        f"({R.CLAIM_WINDOW_MONTHS}mo, lag {R.CLAIM_WINDOW_LAG_MONTHS}mo)")
    log(f"Stage dir (mine) : @~/{stage_dir}/   (LIST/GET/REMOVE scoped to this only)")
    log(f"Output dir       : {cfg['output_dir']}")

    conn = connect(cfg, resolve_auth(cfg))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_VERSION()")
            log(f"session          : {cur.fetchone()}")

        sql = build_copy_into_sql(f"@~/{stage_dir}/")
        rows = unload_to_stage_multifile(conn, stage_dir, sql)
        if rows == 0:
            log("  no rows -- nothing staged. Done.")
            return 0
        log(f"  unloaded {rows:,} rows to @~/{stage_dir}/")

        # Measure staged (gzip) size before downloading; pick a delivery that fits.
        c_bytes = stage_dir_bytes(conn, stage_dir)
        est_plain = c_bytes * 7          # gzip'd repetitive codes/ZIPs expand ~5-7x
        free = shutil.disk_usage(cfg["output_dir"]).free
        margin = 15_000_000_000
        gb = 1_000_000_000
        log(f"  staged: {c_bytes/gb:.2f} GB gzip (est ~{est_plain/gb:.0f} GB plain); "
            f"free disk {free/gb:.0f} GB")

        force_gzip = os.environ.get("DELIVER_GZIP", "").strip() in ("1", "true", "yes")
        if force_gzip and 2 * c_bytes + margin < free:
            out_name, compress = filename + ".gz", True
            log("  -> DELIVER_GZIP set; delivering GZIP CSV (.csv.gz)")
        elif not force_gzip and est_plain + margin < free:
            out_name, compress = filename, False
            log("  -> delivering PLAIN CSV (fits with headroom)")
        elif 2 * c_bytes + margin < free:
            out_name, compress = filename + ".gz", True
            log("  -> plain too large; delivering GZIP CSV (.csv.gz)")
        else:
            log(f"  ✗ too large for local disk even compressed. Compute BANKED on "
                f"@~/{stage_dir}/ ({c_bytes/gb:.2f} GB) -- NOT removed. Re-run after "
                f"freeing disk or shortening the window.")
            return 2

        local = get_and_merge_stage_dir(conn, stage_dir, out_name, cfg["output_dir"],
                                        compress=compress)
        if local is None:
            log("  GET/merge produced no local file -- leaving stage intact for retry")
            return 1
        log(f"  local file: {local}  ({local.stat().st_size:,} bytes)")

        if cfg.get("s3_bucket"):
            key = upload_and_validate(local, cfg["s3_bucket"])
            if not key:
                log("  S3 upload/validate failed -- leaving stage intact for retry")
                return 1

        remove_stage_dir(conn, stage_dir)
        log(f"  cleared @~/{stage_dir}/")
    finally:
        conn.close()

    log("=" * 64)
    log("DONE")
    log("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
