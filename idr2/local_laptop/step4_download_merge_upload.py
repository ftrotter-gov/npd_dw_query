"""
Snowflake Parallel CSV Downloader — Per-Table Pipeline

For each table exported by Snowflake this script runs a complete pipeline:

    DOWNLOAD parts from @~/
    → MERGE parts into single CSV on laptop
    → UPLOAD merged CSV to S3
    → VALIDATE the S3 upload (size check)
    → CLEAN UP all local files (parts + merged)
    → REMOVE parts from Snowflake stage  ← signals Snowflake: export next table
    → wait for next table ...

This design ensures the laptop never accumulates more than one table's worth
of data at a time, so disk space is not a bottleneck.

Configuration: Reads from idr2/.env
Logging: Prints with timestamps and appends to download_progress.log

Usage:
    python3 idr2/local_laptop/step4_download_merge_upload.py

Resume / restart:
    If the script was interrupted, just restart it. On startup it checks
    the download directory for pre-existing CSV parts. If found, it runs
    the full pipeline on them (merge → S3 → validate → clean → remove stage)
    before entering the main polling loop.
"""

import hashlib
import os
import re
import sys
import time
import subprocess
from collections import defaultdict
from pathlib import Path
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================

def load_env(env_file):
    """Load key=value pairs from .env file, stripping inline comments."""
    config = {}
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                value = value.split('#')[0].strip()
                config[key.strip()] = value
    return config


def find_project_root():
    """Find the repo root (the directory that contains idr2/)."""
    script_dir = Path(__file__).parent  # idr2/local_laptop/
    return script_dir.parent.parent     # repo root


def setup_config():
    """Load and validate configuration from idr2/.env."""
    project_root = find_project_root()
    idr2_dir = project_root / "idr2"
    env_file = idr2_dir / ".env"

    if not env_file.exists():
        print(f"ERROR: .env file not found at {env_file}")
        print(f"  cp {idr2_dir}/example.env {env_file}")
        print(f"  nano {env_file}")
        sys.exit(1)

    config = load_env(env_file)

    download_dir = Path(config.get('DOWNLOAD_DIRECTORY', '')).expanduser()
    merged_dir   = Path(config.get('MERGED_DIRECTORY',
                                   str(download_dir.parent / 'merged_csv_files'))).expanduser()
    snowsql_path = Path(config.get('SNOWSQL_PATH',
                                   '/Applications/SnowSQL.app/Contents/MacOS/snowsql'))
    snowflake_config         = config.get('SNOWFLAKE_CONFIG', 'cms_idr')
    s3_destination           = config.get('S3_BUCKET', '')     # e.g. s3://my-bucket/idr_exports/
    polling_interval_minutes = int(config.get('POLLING_INTERVAL_MINUTES', 5))
    quit_after_hours         = int(config.get('QUIT_AFTER_HOURS', 2))

    return {
        'project_root':             project_root,
        'idr2_dir':                 idr2_dir,
        'download_dir':             download_dir,
        'merged_dir':               merged_dir,
        'snowsql_path':             snowsql_path,
        'snowflake_config':         snowflake_config,
        's3_destination':           s3_destination,
        'polling_interval_minutes': polling_interval_minutes,
        'polling_interval_seconds': polling_interval_minutes * 60,
        'quit_after_seconds':       quit_after_hours * 3600,
        'quit_after_hours':         quit_after_hours,
    }


# ============================================================================
# LOGGING
# ============================================================================

_log_file = None


def log(message):
    """Print with timestamp and append to log file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {message}"
    print(line)
    if _log_file:
        with open(_log_file, 'a') as f:
            f.write(line + '\n')


# ============================================================================
# SNOWSQL HELPERS
# ============================================================================

def run_snowsql(snowsql_path, snowflake_config, query):
    """Run one snowsql command. Returns (success, stdout+stderr)."""
    cmd = [str(snowsql_path), '-c', snowflake_config, '-q', query]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr


def list_stage_files(snowsql_path, snowflake_config):
    """Return list of CSV filenames currently in the user stage @~/."""
    success, output = run_snowsql(
        snowsql_path, snowflake_config,
        "LIST @~/ PATTERN='.*\\.csv';"
    )
    if not success:
        log("  Warning: LIST @~/ failed")
        return []
    files = []
    for line in output.splitlines():
        if '.csv' in line:
            parts = line.split()
            if parts:
                files.append(parts[0])
    return files


def download_stage_files(snowsql_path, snowflake_config, download_dir):
    """GET all CSV files from @~/ into download_dir. Returns True on success."""
    log("  Downloading CSV parts from Snowflake stage...")
    original_dir = os.getcwd()
    os.chdir(str(download_dir))
    try:
        success, output = run_snowsql(
            snowsql_path, snowflake_config,
            "GET @~/ file://. PATTERN='.*.csv';"
        )
        if success:
            log("  ✓ Download complete")
            return True
        log(f"  ✗ GET failed: {output[:300]}")
        return False
    finally:
        os.chdir(original_dir)


def remove_stage_files(snowsql_path, snowflake_config):
    """REMOVE all CSV files from @~/. Returns True on success."""
    log("  Removing files from Snowflake stage...")
    success, output = run_snowsql(
        snowsql_path, snowflake_config,
        "REMOVE @~/ PATTERN='.*.csv';"
    )
    if success:
        log("  ✓ Stage cleared — Snowflake will export the next table")
        return True
    log(f"  ✗ REMOVE failed: {output[:300]}")
    return False


# ============================================================================
# MERGE  (calls misc_scripts/snowflake_csv_merge.py)
# ============================================================================

def identify_groups(directory):
    """
    Scan directory for CSV part files and group them by table root name.
    Uses the same regex as snowflake_csv_merge.py:
        foo_0_0_0.csv, foo_0_0_1.csv  →  group 'foo'

    Returns dict: { root_name: [Path, ...] }
    Skip the download_progress.log file.
    """
    groups = defaultdict(list)
    for f in sorted(directory.glob("*.csv")) + sorted(directory.glob("*.csv.gz")):
        if f.name == "download_progress.log":
            continue
        base = f.name
        if base.endswith('.gz'):
            base = base[:-3]
        if base.endswith('.csv'):
            base = base[:-4]
        root = re.sub(r'(_\d+_\d+_\d+)$', '', base)
        if root.endswith('.csv'):
            root = root[:-4]
        groups[root].append(f)
    return dict(groups)


def merge_one_group(project_root, part_files, merged_dir):
    """
    Merge a single list of part files into one CSV in merged_dir.

    Strategy:
      1. Move part files into an isolated temp subdirectory (instantaneous rename,
         no data copy, no extra disk space).
      2. Call snowflake_csv_merge.py on that temp dir.
      3. Return the list of newly created merged files.
         The temp dir and its part files are NOT deleted here — caller is
         responsible for cleanup so parts survive if something goes wrong.

    Returns (merged_files, temp_dir) — temp_dir must be cleaned up by caller.
    """
    merge_script = project_root / "misc_scripts" / "snowflake_csv_merge.py"
    if not merge_script.exists():
        log(f"  ✗ Merge script not found: {merge_script}")
        return [], None

    merged_dir.mkdir(parents=True, exist_ok=True)

    # Create an isolated temp dir inside the same directory as the part files
    # so rename() stays on the same filesystem (zero disk cost).
    parent_dir = part_files[0].parent
    temp_dir = parent_dir / f"_merge_tmp_{part_files[0].name[:40]}"
    temp_dir.mkdir(exist_ok=True)

    log(f"  Moving {len(part_files)} part file(s) into temp dir for isolated merge...")
    for f in part_files:
        f.rename(temp_dir / f.name)

    before = set(merged_dir.glob("*.csv"))

    log(f"  Merging → {merged_dir} ...")
    result = subprocess.run(
        [sys.executable, str(merge_script),
         str(temp_dir), '--output-dir', str(merged_dir)],
        capture_output=False
    )

    if result.returncode != 0:
        log("  ✗ Merge script returned non-zero exit code")
        return [], temp_dir

    after = set(merged_dir.glob("*.csv"))
    new_files = sorted(after - before)

    if not new_files:
        log("  ⚠ Merge script ran but produced no new files")
        return [], temp_dir

    for f in new_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        log(f"  ✓ Merged: {f.name}  ({size_mb:.1f} MB)")
    return new_files, temp_dir


# ============================================================================
# S3 UPLOAD + VALIDATION
# ============================================================================

def compute_local_md5(filepath):
    """Return the hex MD5 digest of a local file."""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def upload_to_s3(local_file, s3_destination):
    """
    Upload local_file to s3_destination using the AWS CLI.
    Prints file name, size, destination, and upload result.
    Returns True on success.
    """
    if not s3_destination:
        log("  ⚠ S3_BUCKET not configured in .env — skipping upload")
        return True  # treat as non-fatal so local cleanup still runs

    dest = s3_destination.rstrip('/') + '/' + local_file.name
    size_mb = local_file.stat().st_size / (1024 * 1024)

    log(f"  Upload source : {local_file}")
    log(f"  Upload size   : {size_mb:.2f} MB  ({local_file.stat().st_size:,} bytes)")
    log(f"  Upload dest   : {dest}")
    log(f"  Uploading...")

    result = subprocess.run(
        ['aws', 's3', 'cp', str(local_file), dest],
        capture_output=False
    )
    if result.returncode == 0:
        log(f"  ✓ Upload complete → {dest}")
        return True
    log(f"  ✗ Upload FAILED for {local_file.name}  (aws exit code {result.returncode})")
    return False


def validate_s3_upload(local_file, s3_destination):
    """
    Validate the S3 upload by comparing:
      - file size  (aws s3 ls)
      - MD5 digest (aws s3api head-object ETag vs local MD5)

    Prints each check with pass/fail. Returns True only if both match.
    Note: S3 ETags for multipart uploads are NOT a plain MD5; in that case
    only the size check applies and the MD5 step is skipped with a warning.
    """
    if not s3_destination:
        return True  # no S3 configured — nothing to validate

    dest = s3_destination.rstrip('/') + '/' + local_file.name
    log(f"  Validating : {dest}")

    # ── Size check ────────────────────────────────────────────────────────────
    ls_result = subprocess.run(
        ['aws', 's3', 'ls', dest],
        capture_output=True, text=True
    )
    if ls_result.returncode != 0 or not ls_result.stdout.strip():
        log(f"  ✗ SIZE CHECK FAILED — file not found in S3")
        return False

    local_size = local_file.stat().st_size
    ls_parts = ls_result.stdout.strip().split()
    try:
        s3_size = int(ls_parts[2])
    except (IndexError, ValueError):
        log(f"  ⚠ Could not parse 'aws s3 ls' output: {ls_result.stdout.strip()}")
        s3_size = None

    if s3_size is not None:
        if s3_size == local_size:
            log(f"  ✓ SIZE  match : {s3_size:,} bytes")
        else:
            log(f"  ✗ SIZE MISMATCH : local={local_size:,} bytes  S3={s3_size:,} bytes")
            return False

    # ── MD5 / ETag check ──────────────────────────────────────────────────────
    # Parse bucket and key from the destination URI
    # dest looks like:  s3://bucket-name/prefix/filename.csv
    without_scheme = dest[len('s3://'):]
    bucket, _, key = without_scheme.partition('/')

    etag_result = subprocess.run(
        ['aws', 's3api', 'head-object',
         '--bucket', bucket,
         '--key', key,
         '--query', 'ETag',
         '--output', 'text'],
        capture_output=True, text=True
    )

    if etag_result.returncode != 0:
        log(f"  ⚠ MD5  check  : could not retrieve ETag from S3 — skipping")
    else:
        etag = etag_result.stdout.strip().strip('"')
        if '-' in etag:
            # Multipart upload — ETag is not a plain MD5
            log(f"  ⚠ MD5  check  : S3 ETag '{etag}' is a multipart checksum — "
                f"size match is sufficient")
        else:
            local_md5 = compute_local_md5(local_file)
            log(f"  Local MD5     : {local_md5}")
            log(f"  S3 ETag (MD5) : {etag}")
            if local_md5 == etag:
                log(f"  ✓ MD5   match : checksums identical")
            else:
                log(f"  ✗ MD5 MISMATCH : local={local_md5}  S3={etag}")
                return False

    log(f"  ✓ Validation passed for {local_file.name}")
    return True


# ============================================================================
# PER-BATCH PIPELINE
# ============================================================================

def run_pipeline(project_root, download_dir, merged_dir,
                 snowsql_path, snowflake_config, s3_destination,
                 remove_from_stage=True):
    """
    Run the full pipeline for every table group found in download_dir.

    For EACH group independently (one at a time):
        MERGE that group's parts → single CSV
        UPLOAD merged CSV → S3
        VALIDATE S3 upload (size + MD5)
        DELETE merged CSV from laptop
        DELETE part files from laptop
        → only then move on to the next group

    This ensures the laptop never holds more than one table's merged data
    at any time, regardless of how many groups are in download_dir.

    Finally (optionally) signals Snowflake by removing files from stage.
    """
    groups = identify_groups(download_dir)

    if not groups:
        log("  ✗ No CSV part files found in download directory")
        return False

    total_groups = len(groups)
    log(f"  Found {total_groups} table group(s) to process")

    for group_idx, (root, part_files) in enumerate(sorted(groups.items()), 1):
        log("")
        log(f"  ╔══ Group {group_idx}/{total_groups}: {root}  ({len(part_files)} parts) ══╗")

        # ── MERGE ─────────────────────────────────────────────────────────────
        log(f"--- Pipeline [{group_idx}/{total_groups}]: MERGE ---")
        merged_files, temp_dir = merge_one_group(project_root, part_files, merged_dir)

        if not merged_files:
            log(f"  ✗ Merge failed for group '{root}' — stopping pipeline")
            # Move parts back to download_dir so they're visible for inspection
            if temp_dir and temp_dir.exists():
                for f in temp_dir.glob("*.csv"):
                    f.rename(download_dir / f.name)
                temp_dir.rmdir()
            return False

        # ── For each merged file: upload → validate → delete ─────────────────
        upload_ok = True
        for merged_file in merged_files:

            log(f"--- Pipeline [{group_idx}/{total_groups}]: UPLOAD  {merged_file.name} ---")
            if not upload_to_s3(merged_file, s3_destination):
                log(f"  ✗ Upload failed — stopping pipeline")
                upload_ok = False
                break

            log(f"--- Pipeline [{group_idx}/{total_groups}]: VALIDATE {merged_file.name} ---")
            if not validate_s3_upload(merged_file, s3_destination):
                log(f"  ✗ Validation failed — stopping pipeline")
                upload_ok = False
                break

            log(f"--- Pipeline [{group_idx}/{total_groups}]: CLEAN MERGED {merged_file.name} ---")
            size_mb = merged_file.stat().st_size / (1024 * 1024)
            merged_file.unlink()
            log(f"  ✓ Deleted merged file : {merged_file.name}  ({size_mb:.2f} MB)")
            log(f"    disk space reclaimed : {size_mb:.2f} MB")

        if not upload_ok:
            # Leave parts in temp_dir for inspection; abort
            return False

        # ── DELETE part files (only after merged file is confirmed in S3) ─────
        log(f"--- Pipeline [{group_idx}/{total_groups}]: CLEAN PARTS ---")
        if temp_dir and temp_dir.exists():
            part_files_in_temp = sorted(temp_dir.glob("*.csv")) + sorted(temp_dir.glob("*.csv.gz"))
            log(f"  Deleting {len(part_files_in_temp)} part file(s):")
            for f in part_files_in_temp:
                size_mb = f.stat().st_size / (1024 * 1024)
                f.unlink()
                log(f"    deleted: {f.name}  ({size_mb:.2f} MB)")
            temp_dir.rmdir()
            log(f"  ✓ All parts deleted for '{root}'")

        log(f"  ╚══ Group {group_idx}/{total_groups}: '{root}' DONE ══╝")

    # All groups processed — verify download_dir is clean
    leftover = [f for f in download_dir.glob("*.csv") if f.name != "download_progress.log"]
    if leftover:
        log(f"  ⚠ {len(leftover)} unexpected file(s) remain in download dir")
    else:
        log("  ✓ Download directory is empty — all tables processed")

    # Signal Snowflake to export the next table
    if remove_from_stage:
        log("--- Pipeline: REMOVE FROM STAGE ---")
        remove_stage_files(snowsql_path, snowflake_config)

    log("--- Pipeline: ALL COMPLETE ---")
    return True


# ============================================================================
# MAIN
# ============================================================================

def format_elapsed(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m"


def main():
    global _log_file

    config = setup_config()
    download_dir             = config['download_dir']
    merged_dir               = config['merged_dir']
    snowsql_path             = config['snowsql_path']
    snowflake_config         = config['snowflake_config']
    s3_destination           = config['s3_destination']
    polling_interval_seconds = config['polling_interval_seconds']
    polling_interval_minutes = config['polling_interval_minutes']
    quit_after_seconds       = config['quit_after_seconds']
    quit_after_hours         = config['quit_after_hours']
    project_root             = config['project_root']

    # Validate paths
    if not download_dir.exists():
        print(f"ERROR: DOWNLOAD_DIRECTORY does not exist: {download_dir}")
        print(f"  mkdir -p '{download_dir}'")
        sys.exit(1)
    if not snowsql_path.exists():
        print(f"ERROR: snowsql not found at {snowsql_path}")
        print(f"  Update SNOWSQL_PATH in {config['idr2_dir']}/.env")
        sys.exit(1)

    _log_file = download_dir / "download_progress.log"

    log("=" * 60)
    log("STARTING: Snowflake → Laptop → S3 Pipeline")
    log("=" * 60)
    log(f"Download dir  : {download_dir}")
    log(f"Merged dir    : {merged_dir}")
    log(f"S3 destination: {s3_destination or '(not configured)'}")
    log(f"Polling       : every {polling_interval_minutes} min")
    log(f"Timeout       : {quit_after_hours} h with no activity")

    # ──────────────────────────────────────────────────────────────────────────
    # RESUME: process any leftover parts from a previous interrupted run
    # ──────────────────────────────────────────────────────────────────────────
    existing_parts = list(download_dir.glob("*.csv"))
    if existing_parts:
        log("=" * 60)
        log(f"RESUME: found {len(existing_parts)} pre-existing part file(s)")
        log("Running pipeline on leftover files before entering poll loop...")
        # Do NOT remove from stage for the resume case — the stage was already
        # cleared (or never had files). We just need to process the local parts.
        run_pipeline(project_root, download_dir, merged_dir,
                     snowsql_path, snowflake_config, s3_destination,
                     remove_from_stage=False)
        log("Resume processing complete. Entering poll loop.")
    else:
        log("No pre-existing parts found — starting fresh poll loop.")
    # ──────────────────────────────────────────────────────────────────────────

    start_time = time.time()
    last_activity_time = start_time
    tables_processed = 0

    log("=" * 60)
    log("POLLING LOOP STARTED")
    log("=" * 60)

    while True:
        now = time.time()
        elapsed_total          = now - start_time
        elapsed_since_activity = now - last_activity_time

        if elapsed_since_activity > quit_after_seconds:
            log("=" * 60)
            log(f"TIMEOUT: no activity for {quit_after_hours} h")
            log(f"Total elapsed: {format_elapsed(elapsed_total)}")
            log(f"Tables processed: {tables_processed}")
            log("=" * 60)
            break

        log(f"Checking stage "
            f"(elapsed={format_elapsed(elapsed_total)}, "
            f"since activity={format_elapsed(elapsed_since_activity)})...")

        stage_files = list_stage_files(snowsql_path, snowflake_config)

        if stage_files:
            log(f"Found {len(stage_files)} file(s) in stage")

            # Step 1: Download
            if download_stage_files(snowsql_path, snowflake_config, download_dir):
                last_activity_time = time.time()
                tables_processed += 1

                # Steps 2-5: merge → S3 → validate → clean local → remove stage
                log(f"[Table {tables_processed}] Running full pipeline...")
                ok = run_pipeline(
                    project_root, download_dir, merged_dir,
                    snowsql_path, snowflake_config, s3_destination,
                    remove_from_stage=True
                )
                if ok:
                    log(f"[Table {tables_processed}] ✓ Pipeline complete — "
                        f"laptop disk space reclaimed, Snowflake signalled")
                    last_activity_time = time.time()
                else:
                    log(f"[Table {tables_processed}] ✗ Pipeline failed — "
                        f"check errors above. Files left in {download_dir}")
                    log("  Stopping to avoid data loss.")
                    break
            else:
                log("  ✗ Download failed — will retry next poll")
        else:
            log("  No files in stage — waiting for Snowflake to export next table...")

        log(f"Sleeping {polling_interval_minutes} min until next check...")
        elapsed_wait = 0
        while elapsed_wait < polling_interval_seconds:
            time.sleep(60)
            elapsed_wait += 60
            remaining = (polling_interval_seconds - elapsed_wait) // 60
            if elapsed_wait < polling_interval_seconds:
                log(f"  ... {remaining:.0f} min until next check")

    total_elapsed = time.time() - start_time
    log("=" * 60)
    log("DONE")
    log(f"Total duration   : {format_elapsed(total_elapsed)}")
    log(f"Tables processed : {tables_processed}")
    log(f"Log file         : {_log_file}")
    log("=" * 60)
    print('\a', end='', flush=True)   # terminal bell


if __name__ == "__main__":
    main()
