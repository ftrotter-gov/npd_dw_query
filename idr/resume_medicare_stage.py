"""
RESUME helper for the Medicare COMBINED wide extract.

The combined Medicare unload (COMPUTE) is the most expensive extract and can bank
its result on the Snowflake user stage
  @~/idr_medicare_combined_wide.<window>/
when a run is interrupted during the GET (download) step, or when the extract's
own size guard aborts because the result will not fit local disk (its "Compute is
BANKED ... NOT removed" path). The extract SOURCE has not changed since that
unload, so the banked result is still valid -- we just re-GET + merge it, no
re-query (freeing disk first if the size guard was what banked it).

This script:
  1. LISTs the expected stage dir.
  2. If it holds gzip parts -> GET + merge to a local plain CSV, then REMOVE the
     stage. Prints "RESUMED".
  3. If it is EMPTY / gone -> prints "STAGE-EMPTY" and exits non-zero, so the
     caller can fall back to a full re-run of idr_medicare_combined_wide.py
     (deterministic, identical result, just slower).

The window MUST match the run that banked the stage: set CLAIM_WINDOW_MONTHS to
the same value the extract used (default 24; a 1-month dry-run banks under a
different window dir).

No re-query, no COPY INTO here -- GET only.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import (
    load_config,
    compute_window,
    resolve_auth,
    connect,
    stage_dir_bytes,
    get_and_merge_stage_dir,
    remove_stage_dir,
    log,
)

# Must match the idr_medicare_combined_wide.py run that banked the stage.
CLAIM_WINDOW_MONTHS = int(os.environ.get("CLAIM_WINDOW_MONTHS") or 24)
FILE_PREFIX = "idr_medicare_combined_wide"


def main():
    log("=" * 60)
    log("RESUME Medicare 24mo -- re-GET banked stage (no re-query)")
    log("=" * 60)

    cfg = load_config()
    cfg["window_months"] = CLAIM_WINDOW_MONTHS
    start, end = compute_window(cfg)
    window    = f"{start:%Y_%m_%d}_to_{end:%Y_%m_%d}"
    stage_dir = f"{FILE_PREFIX}.{window}"
    filename  = f"{FILE_PREFIX}.{window}.csv"
    log(f"stage: @~/{stage_dir}/")

    conn = connect(cfg, resolve_auth(cfg))
    try:
        c_bytes = stage_dir_bytes(conn, stage_dir)
        gb = 1_000_000_000
        if c_bytes <= 0:
            log("STAGE-EMPTY -- no parts on the stage; caller should full re-run")
            return 3
        log(f"staged size: {c_bytes/gb:.2f} GB compressed across parts")

        local = get_and_merge_stage_dir(conn, stage_dir, filename, cfg["output_dir"])
        if local is None:
            log("  GET/merge produced no local file -- leaving stage intact")
            return 1
        log(f"  local file: {local}  ({local.stat().st_size:,} bytes)")

        remove_stage_dir(conn, stage_dir)
        log(f"  cleared @~/{stage_dir}/")
    finally:
        conn.close()

    log("RESUMED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
