"""
Snowflake Parallel CSV Downloader with Polling

Python replacement for download_and_merge_with_polling.sh

This script coordinates with the Snowflake export loop (snowflake_notebook_cell_2.py)
to download exported CSV files. It monitors the Snowflake stage (@~/) for new files,
downloads them all at once, removes them from the stage, then waits for the next batch.

Snowflake is only authenticated 3 times per polling cycle:
  1. LIST - check for new files
  2. GET  - download all files at once
  3. REMOVE - clear stage

Configuration: Reads from idr2/.env
Logging: Prints with timestamps and writes to download_progress.log

Usage:
    python3 idr2/download_and_merge_with_polling.py
"""

import os
import sys
import time
import subprocess
import glob
from pathlib import Path
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================

def load_env(env_file):
    """Load key=value pairs from .env file."""
    config = {}
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                # Strip inline comments
                value = value.split('#')[0].strip()
                config[key.strip()] = value
    return config


def find_project_root():
    """Find the project root (directory containing idr2/)."""
    script_dir = Path(__file__).parent  # idr2/local_laptop/
    return script_dir.parent.parent     # repo root


def setup_config():
    """Load and validate configuration."""
    project_root = find_project_root()
    idr2_dir = project_root / "idr2"
    env_file = idr2_dir / ".env"

    if not env_file.exists():
        print(f"ERROR: .env file not found at {env_file}")
        print("Please copy example.env to .env and configure it first:")
        print(f"  cd {idr2_dir}")
        print(f"  cp example.env .env")
        print(f"  nano .env")
        sys.exit(1)

    config = load_env(env_file)

    # Expand ~ in paths
    download_dir = Path(config.get('DOWNLOAD_DIRECTORY', '')).expanduser()
    snowsql_path = Path(config.get('SNOWSQL_PATH', '/Applications/SnowSQL.app/Contents/MacOS/snowsql'))
    snowflake_config = config.get('SNOWFLAKE_CONFIG', 'cms_idr')
    polling_interval_minutes = int(config.get('POLLING_INTERVAL_MINUTES', 5))
    quit_after_hours = int(config.get('QUIT_AFTER_HOURS', 2))

    return {
        'project_root': project_root,
        'idr2_dir': idr2_dir,
        'download_dir': download_dir,
        'snowsql_path': snowsql_path,
        'snowflake_config': snowflake_config,
        'polling_interval_minutes': polling_interval_minutes,
        'polling_interval_seconds': polling_interval_minutes * 60,
        'quit_after_seconds': quit_after_hours * 3600,
        'quit_after_hours': quit_after_hours,
    }


# ============================================================================
# LOGGING
# ============================================================================

log_file = None


def log(message):
    """Print with timestamp and write to log file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {message}"
    print(line)
    if log_file:
        with open(log_file, 'a') as f:
            f.write(line + '\n')


# ============================================================================
# SNOWSQL OPERATIONS
# ============================================================================

def run_snowsql(snowsql_path, snowflake_config, query):
    """
    Run a single snowsql command. Returns (success, output).
    One authentication per call.
    """
    cmd = [str(snowsql_path), '-c', snowflake_config, '-q', query]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout + result.stderr


def list_stage_files(snowsql_path, snowflake_config):
    """
    List CSV files in Snowflake user stage. Returns list of filenames.
    One snowsql authentication.
    """
    success, output = run_snowsql(snowsql_path, snowflake_config, "LIST @~/ PATTERN='.*\\.csv';")
    if not success:
        log(f"  Warning: LIST command failed")
        return []

    files = []
    for line in output.splitlines():
        if '.csv' in line:
            # First column is the filename
            parts = line.split()
            if parts:
                files.append(parts[0])
    return files


def download_all_files(snowsql_path, snowflake_config, download_dir):
    """
    Download ALL csv files from stage at once.
    One snowsql authentication (like original download_and_merge_all_snowflake_csv.sh).
    """
    log("Downloading all CSV files from stage...")
    original_dir = os.getcwd()
    os.chdir(str(download_dir))

    try:
        success, output = run_snowsql(
            snowsql_path, snowflake_config,
            "GET @~/ file://. PATTERN='.*.csv';"
        )
        if success:
            log("✓ Download complete")
            return True
        else:
            log(f"✗ Failed to download files from stage")
            log(f"  Output: {output[:300]}")
            return False
    finally:
        os.chdir(original_dir)


def remove_all_stage_files(snowsql_path, snowflake_config):
    """
    Remove ALL csv files from stage at once.
    One snowsql authentication.
    """
    log("Removing downloaded files from stage...")
    success, output = run_snowsql(
        snowsql_path, snowflake_config,
        "REMOVE @~/ PATTERN='.*.csv';"
    )
    if success:
        log("✓ Stage cleared")
        return True
    else:
        log(f"✗ Failed to clear stage")
        log(f"  Output: {output[:300]}")
        return False


# ============================================================================
# CSV MERGE
# ============================================================================

def merge_csv_files(project_root, download_dir):
    """Run the snowflake_csv_merge.py script to merge downloaded CSVs."""
    merge_script = project_root / "misc_scripts" / "snowflake_csv_merge.py"
    output_dir = download_dir.parent

    if not merge_script.exists():
        log(f"⚠ Merge script not found: {merge_script}")
        return False

    log(f"Running CSV merge: {merge_script}")
    result = subprocess.run(
        [sys.executable, str(merge_script), str(download_dir), '--output-dir', str(output_dir)],
        capture_output=False
    )
    return result.returncode == 0


# ============================================================================
# MAIN POLLING LOOP
# ============================================================================

def format_elapsed(seconds):
    """Format seconds as Xh Ym."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m"


def main():
    global log_file

    # Load config
    config = setup_config()
    download_dir = config['download_dir']
    snowsql_path = config['snowsql_path']
    snowflake_config = config['snowflake_config']
    polling_interval_seconds = config['polling_interval_seconds']
    polling_interval_minutes = config['polling_interval_minutes']
    quit_after_seconds = config['quit_after_seconds']
    quit_after_hours = config['quit_after_hours']
    project_root = config['project_root']

    # Validate download directory
    if not download_dir.exists():
        print(f"ERROR: Download directory does not exist: {download_dir}")
        print("Please create it first:")
        print(f"  mkdir -p '{download_dir}'")
        sys.exit(1)

    # Validate snowsql
    if not snowsql_path.exists():
        print(f"ERROR: snowsql not found at {snowsql_path}")
        print(f"Please update SNOWSQL_PATH in {config['idr2_dir']}/.env")
        sys.exit(1)

    # Set up log file
    log_file = download_dir / "download_progress.log"

    log("====== STARTING DOWNLOAD & MERGE PROCESS ======")
    log(f"Configuration loaded from: {config['idr2_dir']}/.env")
    log(f"Download directory: {download_dir}")
    log(f"Polling interval: {polling_interval_minutes} minutes")
    log(f"Timeout: {quit_after_hours} hours")
    log(f"Snowflake config: {snowflake_config}")
    log(f"snowsql found at: {snowsql_path}")

    # ── Resume detection ──────────────────────────────────────────────────────
    # If there are already CSV files in the download dir (from a previous
    # interrupted run), merge and upload them NOW before entering the poll loop.
    existing_csvs = list(download_dir.glob("*.csv"))
    if existing_csvs:
        log(f"====== RESUMING: found {len(existing_csvs)} pre-existing CSV file(s) ======")
        log("Merging and uploading leftover files from previous run...")
        if merge_csv_files(project_root, download_dir):
            log("✓ Pre-existing files merged successfully")
            # Clear the merged parts so the download dir is clean
            for f in download_dir.glob("*.csv"):
                f.unlink()
            log("✓ Download directory cleared — ready to continue polling")
        else:
            log("✗ Merge of pre-existing files failed — check the merge script")
            log("  Files left in place; continuing to poll anyway")
    else:
        log("No pre-existing CSV files found — starting fresh")
    # ─────────────────────────────────────────────────────────────────────────

    # Timing
    start_time = time.time()
    last_activity_time = start_time
    first_file_time = None

    log("Starting polling loop...")

    while True:
        now = time.time()
        elapsed_total = now - start_time
        elapsed_since_activity = now - last_activity_time

        # Check timeout
        if elapsed_since_activity > quit_after_seconds:
            log("====== TIMEOUT REACHED ======")
            log(f"No download activity for {quit_after_hours} hours")
            log(f"Total elapsed: {format_elapsed(elapsed_total)}")
            log("Stopping polling loop")
            break

        log(f"Checking Snowflake stage "
            f"({format_elapsed(elapsed_total)} elapsed, "
            f"{format_elapsed(elapsed_since_activity)} since last activity)...")

        # LIST - one snowsql auth
        stage_files = list_stage_files(snowsql_path, snowflake_config)

        if stage_files:
            log(f"Found {len(stage_files)} file(s) in stage")

            # GET all - one snowsql auth
            if download_all_files(snowsql_path, snowflake_config, download_dir):
                # REMOVE all - one snowsql auth
                remove_all_stage_files(snowsql_path, snowflake_config)
                last_activity_time = time.time()

                if first_file_time is None:
                    first_file_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log(f"First file batch downloaded at: {first_file_time}")
        else:
            log("No new files found in stage")

            if first_file_time is not None:
                downloaded = list(download_dir.glob("*.csv"))
                if downloaded:
                    log(f"✓ All files downloaded ({len(downloaded)} total)")
                    last_activity_time = time.time()

        log(f"Waiting {polling_interval_minutes} minutes before next check...")

        # Sleep in 60-second increments with heartbeat
        elapsed_wait = 0
        while elapsed_wait < polling_interval_seconds:
            time.sleep(60)
            elapsed_wait += 60
            remaining = (polling_interval_seconds - elapsed_wait) // 60
            if elapsed_wait < polling_interval_seconds:
                log(f"  ... still waiting ({remaining:.0f} min until next check)")

    # ============================================================================
    # MERGE DOWNLOADED FILES
    # ============================================================================

    log("====== MERGING CSV FILES ======")

    downloaded_files = list(download_dir.glob("*.csv"))

    if not downloaded_files:
        log("⚠ WARNING: No CSV files found to merge")
        log("Check that Snowflake exports are running correctly")
    else:
        log(f"Found {len(downloaded_files)} files to merge")

        if merge_csv_files(project_root, download_dir):
            log("✓ CSV merge completed successfully")
        else:
            log("✗ CSV merge failed")

    # Final summary
    total_elapsed = time.time() - start_time
    log("====== PROCESS COMPLETE ======")
    log(f"Total duration: {format_elapsed(total_elapsed)}")
    log(f"Downloaded: {len(downloaded_files)} files")
    log(f"Output directory: {download_dir}")
    log(f"Log file: {log_file}")
    log("")
    log("To manually check remaining files in Snowflake stage:")
    log(f"  snowsql -c {snowflake_config} -q \"LIST @~/ PATTERN='*.csv';\"")
    log("")
    log("====== DONE ======")

    # Beep
    print('\a', end='', flush=True)


if __name__ == "__main__":
    main()
