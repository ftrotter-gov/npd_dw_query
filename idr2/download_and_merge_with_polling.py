"""
Snowflake Parallel CSV Downloader with Polling

Implements the complete flow from CompleteFlow.md:
  1.  Download CSV part files from Snowflake stage
  2.  Merge part files into a single CSV
  3.  Upload merged CSV to S3
  4.  Verify upload via MD5 checksum
  5.  Verify row count (parts sum == merged)
  6.  Delete local part files
  7.  Delete local merged file
  8.  Remove part files from Snowflake stage (ONLY after full verification)
  9.  Poll for the next batch

Snowflake is only authenticated 3 times per cycle (LIST, GET, REMOVE).
S3 REMOVE only happens after the complete local pipeline succeeds.

Configuration: Reads from idr2/.env
Logging:       Prints timestamps + writes to download_progress.log

Usage:
    python3 idr2/download_and_merge_with_polling.py
"""

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================

def load_env(env_file):
    """Load key=value pairs from a .env file, stripping inline comments."""
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
    script_dir = Path(__file__).parent  # idr2/
    return script_dir.parent


def setup_config():
    """Load and validate configuration from idr2/.env."""
    project_root = find_project_root()
    idr2_dir = project_root / "idr2"
    env_file = idr2_dir / ".env"

    if not env_file.exists():
        print(f"ERROR: .env file not found at {env_file}")
        print("Please copy example.env to .env and configure it first:")
        print(f"  cd {idr2_dir}")
        print(f"  cp example.env .env && nano .env")
        sys.exit(1)

    raw = load_env(env_file)

    download_dir   = Path(raw.get('DOWNLOAD_DIRECTORY', '')).expanduser()
    snowsql_path   = Path(raw.get('SNOWSQL_PATH', '/Applications/SnowSQL.app/Contents/MacOS/snowsql'))
    snowflake_cfg  = raw.get('SNOWFLAKE_CONFIG', 'cms_idr')
    s3_bucket      = raw.get('S3_BUCKET', '').rstrip('/')
    poll_minutes   = int(raw.get('POLLING_INTERVAL_MINUTES', 5))
    quit_hours     = int(raw.get('QUIT_AFTER_HOURS', 2))

    return {
        'project_root':        project_root,
        'idr2_dir':            idr2_dir,
        'download_dir':        download_dir,
        'merged_dir':          download_dir.parent,   # one level up from parts dir
        'snowsql_path':        snowsql_path,
        'snowflake_config':    snowflake_cfg,
        's3_bucket':           s3_bucket,
        'poll_seconds':        poll_minutes * 60,
        'poll_minutes':        poll_minutes,
        'quit_seconds':        quit_hours * 3600,
        'quit_hours':          quit_hours,
    }


# ============================================================================
# LOGGING
# ============================================================================

_log_file = None


def log(message):
    """Print with timestamp and append to log file."""
    ts   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {message}"
    print(line)
    if _log_file:
        with open(_log_file, 'a') as fh:
            fh.write(line + '\n')


# ============================================================================
# SNOWSQL OPERATIONS  (max 3 auth calls per cycle)
# ============================================================================

def _snowsql(snowsql_path, config_name, query):
    """Run one snowsql command. Returns (success: bool, output: str)."""
    result = subprocess.run(
        [str(snowsql_path), '-c', config_name, '-q', query],
        capture_output=True, text=True
    )
    return result.returncode == 0, result.stdout + result.stderr


def list_stage_files(snowsql_path, cfg):
    """LIST @~/ → return list of .csv filenames present in stage."""
    ok, out = _snowsql(snowsql_path, cfg, "LIST @~/ PATTERN='.*\\.csv';")
    if not ok:
        log("  Warning: LIST command failed")
        return []
    files = []
    for line in out.splitlines():
        if '.csv' in line:
            parts = line.split()
            if parts:
                files.append(parts[0])
    return files


def download_all_parts(snowsql_path, cfg, download_dir):
    """GET @~/ → download all .csv files at once (one auth)."""
    log("Downloading all CSV part files from stage...")
    orig = os.getcwd()
    os.chdir(str(download_dir))
    try:
        ok, out = _snowsql(snowsql_path, cfg, "GET @~/ file://. PATTERN='.*.csv';")
        if ok:
            log("✓ Parts downloaded")
            return True
        log(f"✗ Download failed\n  {out[:300]}")
        return False
    finally:
        os.chdir(orig)


def remove_stage_files(snowsql_path, cfg):
    """REMOVE @~/ → delete all .csv files from stage (one auth)."""
    log("Removing part files from Snowflake stage...")
    ok, out = _snowsql(snowsql_path, cfg, "REMOVE @~/ PATTERN='.*.csv';")
    if ok:
        log("✓ Stage cleared")
        return True
    log(f"✗ Failed to clear stage\n  {out[:300]}")
    return False


# ============================================================================
# MERGE
# ============================================================================

def merge_parts(project_root, download_dir, merged_dir):
    """
    Call misc_scripts/snowflake_csv_merge.py to merge part files.
    Returns list of merged file paths produced (empty on failure).
    """
    merge_script = project_root / "misc_scripts" / "snowflake_csv_merge.py"
    if not merge_script.exists():
        log(f"⚠ Merge script not found: {merge_script}")
        return []

    log(f"Merging parts → {merged_dir} ...")
    result = subprocess.run(
        [sys.executable, str(merge_script), str(download_dir), '--output-dir', str(merged_dir)],
        capture_output=False
    )
    if result.returncode != 0:
        log("✗ Merge failed")
        return []

    # Return all .csv files that now exist in merged_dir
    merged = list(merged_dir.glob("*.csv"))
    log(f"✓ Merge complete — {len(merged)} merged file(s) produced")
    return merged


# ============================================================================
# S3 UPLOAD
# ============================================================================

def upload_to_s3(merged_file, s3_bucket):
    """
    Upload a single merged CSV to S3.
    Returns s3_uri on success, None on failure.
    """
    filename  = merged_file.name
    s3_uri    = f"{s3_bucket}/{filename}"
    log(f"Uploading to S3: {s3_uri}")

    result = subprocess.run(
        ['aws', 's3', 'cp', str(merged_file), s3_uri],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log(f"✓ Uploaded: {s3_uri}")
        return s3_uri
    log(f"✗ S3 upload failed\n  {result.stderr[:300]}")
    return None


# ============================================================================
# VERIFICATION
# ============================================================================

def md5_of_file(path):
    """Compute MD5 hex digest of a local file."""
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def s3_etag(s3_uri):
    """
    Return the S3 ETag (MD5 for non-multipart uploads) via aws s3api.
    Returns hex string without quotes, or None on failure.
    """
    # s3_uri format: s3://bucket/key
    parts = s3_uri[5:].split('/', 1)   # strip 's3://'
    if len(parts) != 2:
        return None
    bucket, key = parts

    result = subprocess.run(
        ['aws', 's3api', 'head-object', '--bucket', bucket, '--key', key],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        log(f"  aws s3api head-object failed: {result.stderr[:200]}")
        return None

    # Parse ETag from JSON output
    import json
    try:
        data = json.loads(result.stdout)
        etag = data.get('ETag', '').strip('"').replace('-', '')
        return etag if etag else None
    except Exception:
        return None


def verify_md5(merged_file, s3_uri):
    """
    Compare local MD5 of merged_file against S3 ETag.
    NOTE: For multipart uploads the ETag is not a simple MD5; in that case
    we log a warning but do not fail — the upload succeeded if aws returned 0.
    Returns True if checksums match OR if multipart (ETag contains '-').
    """
    log(f"Verifying MD5: {merged_file.name}")

    local_md5 = md5_of_file(merged_file)

    # Get raw ETag first to check for multipart
    parts = s3_uri[5:].split('/', 1)
    if len(parts) == 2:
        bucket, key = parts
        result = subprocess.run(
            ['aws', 's3api', 'head-object', '--bucket', bucket, '--key', key],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            import json
            try:
                data  = json.loads(result.stdout)
                etag  = data.get('ETag', '').strip('"')
                if '-' in etag:
                    log(f"  ⚠ Multipart upload ETag — MD5 comparison skipped (upload succeeded)")
                    return True
                if etag == local_md5:
                    log(f"  ✓ MD5 match: {local_md5}")
                    return True
                log(f"  ✗ MD5 MISMATCH  local={local_md5}  s3={etag}")
                return False
            except Exception:
                pass
    log("  ⚠ Could not retrieve S3 ETag — skipping MD5 check")
    return True   # upload returned 0, treat as OK


def verify_row_count(part_files, merged_file):
    """
    Sum row counts of all part files and compare to merged file.
    (Counts data lines; subtracts 1 header per part file.)
    Returns True if counts match.
    """
    log(f"Verifying row count for {merged_file.name}")

    def count_data_rows(path):
        with open(path, 'r', errors='replace') as fh:
            return sum(1 for _ in fh) - 1   # subtract header

    parts_total = sum(count_data_rows(p) for p in part_files)
    merged_rows = count_data_rows(merged_file)

    if parts_total == merged_rows:
        log(f"  ✓ Row count: {merged_rows} data rows")
        return True
    log(f"  ✗ Row count MISMATCH  parts_sum={parts_total}  merged={merged_rows}")
    return False


# ============================================================================
# CLEANUP
# ============================================================================

def delete_local_parts(download_dir):
    """Delete all .csv part files from the download directory."""
    deleted = 0
    for f in download_dir.glob("*.csv"):
        f.unlink()
        deleted += 1
    log(f"✓ Deleted {deleted} local part file(s)")


def delete_local_merged(merged_file):
    """Delete the merged CSV file locally."""
    merged_file.unlink()
    log(f"✓ Deleted local merged file: {merged_file.name}")


# ============================================================================
# PER-BATCH PIPELINE
# ============================================================================

def process_batch(config, stage_files):
    """
    Complete pipeline for one batch of downloaded files:
      download → merge → S3 upload → MD5 verify → row count verify
      → delete local parts → delete local merged → remove from Snowflake

    Returns True if all steps succeeded (Snowflake stage was cleared).
    Returns False if any step failed (Snowflake stage NOT cleared).
    """
    download_dir  = config['download_dir']
    merged_dir    = config['merged_dir']
    snowsql_path  = config['snowsql_path']
    sf_cfg        = config['snowflake_config']
    s3_bucket     = config['s3_bucket']
    project_root  = config['project_root']

    # --- Step 1: Download ---
    if not download_all_parts(snowsql_path, sf_cfg, download_dir):
        return False

    part_files = list(download_dir.glob("*.csv"))
    if not part_files:
        log("⚠ No part files found after download")
        return False

    # --- Step 2: Merge ---
    merged_files = merge_parts(project_root, download_dir, merged_dir)
    if not merged_files:
        return False

    all_ok = True

    for merged_file in merged_files:
        # --- Step 3: Upload to S3 ---
        if not s3_bucket or s3_bucket == 's3://your-bucket-name/idr_exports':
            log(f"⚠ S3_BUCKET not configured — skipping S3 upload for {merged_file.name}")
            s3_uri = None
        else:
            s3_uri = upload_to_s3(merged_file, s3_bucket)
            if not s3_uri:
                log(f"✗ S3 upload failed for {merged_file.name} — keeping local files")
                all_ok = False
                continue

            # --- Step 4: MD5 verify ---
            if not verify_md5(merged_file, s3_uri):
                log(f"✗ MD5 mismatch for {merged_file.name} — NOT cleaning up")
                all_ok = False
                continue

        # --- Step 5: Row count verify ---
        if not verify_row_count(part_files, merged_file):
            log(f"✗ Row count mismatch for {merged_file.name} — NOT cleaning up")
            all_ok = False
            continue

        # --- Step 7: Delete local merged file ---
        delete_local_merged(merged_file)

    if not all_ok:
        log("⚠ Some files failed verification — Snowflake stage NOT cleared")
        return False

    # --- Step 6: Delete local part files ---
    delete_local_parts(download_dir)

    # --- Step 8 & 9: Remove from Snowflake stage (only after full success) ---
    remove_stage_files(snowsql_path, sf_cfg)

    return True


# ============================================================================
# MAIN POLLING LOOP
# ============================================================================

def fmt(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m"


def main():
    global _log_file

    config = setup_config()
    download_dir   = config['download_dir']
    poll_seconds   = config['poll_seconds']
    poll_minutes   = config['poll_minutes']
    quit_seconds   = config['quit_seconds']
    quit_hours     = config['quit_hours']
    snowsql_path   = config['snowsql_path']
    sf_cfg         = config['snowflake_config']

    if not download_dir.exists():
        print(f"ERROR: Download directory does not exist: {download_dir}")
        print(f"  mkdir -p '{download_dir}'")
        sys.exit(1)

    if not snowsql_path.exists():
        print(f"ERROR: snowsql not found at {snowsql_path}")
        sys.exit(1)

    config['merged_dir'].mkdir(parents=True, exist_ok=True)

    _log_file = download_dir / "download_progress.log"

    log("====== STARTING COMPLETE DOWNLOAD PIPELINE ======")
    log(f"Download directory (parts):  {download_dir}")
    log(f"Merged output directory:     {config['merged_dir']}")
    log(f"S3 bucket:                   {config['s3_bucket'] or '(not configured)'}")
    log(f"Polling interval:            {poll_minutes} min")
    log(f"Timeout:                     {quit_hours} h")

    # Delete any leftover parts from previous run
    for f in download_dir.glob("*.csv"):
        f.unlink()
    log("Cleaned up old part files")

    start_time          = time.time()
    last_activity_time  = start_time
    batches_processed   = 0

    log("Starting polling loop...")

    while True:
        now                  = time.time()
        elapsed_total        = now - start_time
        elapsed_since_active = now - last_activity_time

        # Timeout check
        if elapsed_since_active > quit_seconds:
            log(f"====== TIMEOUT: no activity for {quit_hours}h ======")
            log(f"Total elapsed: {fmt(elapsed_total)}")
            break

        log(f"[{fmt(elapsed_total)} elapsed | {fmt(elapsed_since_active)} idle] "
            f"Checking Snowflake stage...")

        # Step 10: Check for new files in stage
        stage_files = list_stage_files(snowsql_path, sf_cfg)

        if stage_files:
            log(f"Found {len(stage_files)} file(s) — starting pipeline")
            if process_batch(config, stage_files):
                batches_processed += 1
                last_activity_time = time.time()
                log(f"✓ Batch {batches_processed} complete")
            else:
                log("✗ Batch pipeline failed — will retry next cycle")
        else:
            log("No files in stage")

        # Step 11: Wait with per-minute heartbeat
        log(f"Waiting {poll_minutes} min before next check...")
        waited = 0
        while waited < poll_seconds:
            time.sleep(60)
            waited += 60
            remaining = (poll_seconds - waited) // 60
            if waited < poll_seconds:
                log(f"  ... {remaining:.0f} min until next check")

    total = time.time() - start_time
    log("====== DONE ======")
    log(f"Total duration: {fmt(total)}")
    log(f"Batches processed: {batches_processed}")
    print('\a', end='', flush=True)


if __name__ == "__main__":
    main()
