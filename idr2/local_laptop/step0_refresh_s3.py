"""
step0_refresh_s3.py  —  S3 Freshness Check & Export Queue Builder

Determines which tables from idr2/all_available_tables.csv need to be (re)exported:

  1. Lists all CSV files in S3_BUCKET using `aws s3 ls`
  2. For each table in all_available_tables.csv:
       - Computes its expected S3 filename prefix  (e.g. v2_prvdr_enrlmt_hstry_idr_export)
       - Finds the most-recent matching file in S3
       - If no file found: table is MISSING → needs download
       - If file is older than REFRESH_DAY_THRESHOLD days: table is STALE → needs refresh
  3. Prints a full status report (✓ fresh / ⚠ stale / ✗ missing)
  4. Writes a new idr2/step1_tables_to_export.csv with only the tables that need work
  5. Runs step2_generate_metadata.py  (regenerates export_metadata.json)
  6. Runs step3_generate_snowflake_cell2.py  (regenerates Snowflake Cell 2 script)

Configuration (idr2/.env):
    S3_BUCKET=s3://your-bucket/prefix/     ← required
    REFRESH_DAY_THRESHOLD=30               ← days before a file is considered stale

Usage:
    python3 idr2/local_laptop/step0_refresh_s3.py

If nothing needs refreshing the script exits cleanly without touching step1 or
running step2/step3.
"""

import csv
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ============================================================================
# CONFIGURATION
# ============================================================================

def find_project_root():
    """Repo root = directory containing idr2/."""
    return Path(__file__).parent.parent.parent   # idr2/local_laptop → idr2 → repo root


def load_env(env_file):
    """Parse key=value pairs from a .env file."""
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


def setup_config():
    project_root = find_project_root()
    idr2_dir     = project_root / "idr2"
    env_file     = idr2_dir / ".env"

    if not env_file.exists():
        print(f"ERROR: .env not found at {env_file}")
        print(f"  cp {idr2_dir}/example.env {env_file}  &&  nano {env_file}")
        sys.exit(1)

    cfg = load_env(env_file)

    s3_bucket = cfg.get('S3_BUCKET', '').rstrip('/')
    if not s3_bucket:
        print("ERROR: S3_BUCKET is not set in .env")
        sys.exit(1)

    threshold_days = int(cfg.get('REFRESH_DAY_THRESHOLD', 30))

    return {
        'project_root':    project_root,
        'idr2_dir':        idr2_dir,
        's3_bucket':       s3_bucket,
        'threshold_days':  threshold_days,
    }


# ============================================================================
# TABLE → S3 PREFIX MAPPING
# ============================================================================

def table_to_stub(full_table_name):
    """
    Convert a fully-qualified table name to the S3 filename prefix.

    e.g.  IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_HSTRY
          → v2_prvdr_enrlmt_hstry_idr_export

    This matches the logic in step2/step3 generate_file_name_stub().
    """
    table_part = full_table_name.split('.')[-1]   # 3rd component
    return f"{table_part.lower()}_idr_export"


# ============================================================================
# S3 LISTING
# ============================================================================

def list_s3_files(s3_bucket, verbose=False):
    """
    Run `aws s3 ls {s3_bucket}/ --no-paginate` and return a list of
        (last_modified: datetime, size: int, filename: str)
    tuples for every .csv file found.

    Uses --no-paginate so all files are returned even if there are
    more than the default page size.

    aws s3 ls output format:
        2026-06-14 05:14:23      1234567 some_file.csv
    """
    url = s3_bucket + '/'
    print(f"Listing S3 files in {url} ...")
    result = subprocess.run(
        ['aws', 's3', 'ls', url, '--no-paginate'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: aws s3 ls failed:\n{result.stderr[:500]}")
        sys.exit(1)

    if verbose:
        print("  Raw aws s3 ls output:")
        for line in result.stdout.splitlines():
            print(f"    {line}")
        print()

    files = []
    skipped = []
    for line in result.stdout.splitlines():
        line = line.rstrip()
        if not line:
            continue

        # aws s3 ls format: "YYYY-MM-DD HH:MM:SS  <size>  <key>"
        # Split into at most 4 parts; key may contain spaces (join the rest)
        parts = line.split(None, 3)  # maxsplit=3 → parts[3] = entire filename
        if len(parts) < 4:
            # Might be a "PRE prefix/" directory indicator — skip
            skipped.append(line)
            continue

        date_str, time_str, size_str, filename = parts
        filename = filename.strip()

        if not filename.endswith('.csv'):
            continue

        try:
            last_modified = datetime.strptime(
                f"{date_str} {time_str}", '%Y-%m-%d %H:%M:%S'
            ).replace(tzinfo=timezone.utc)
            size = int(size_str)
            files.append((last_modified, size, filename))
        except (ValueError, IndexError) as e:
            print(f"  ⚠ Could not parse line: {line!r}  ({e})")
            continue

    if skipped and verbose:
        print(f"  Skipped {len(skipped)} non-file line(s)")

    print(f"  Found {len(files)} CSV file(s) in S3")
    return files


def build_s3_index(s3_files, verbose=False):
    """
    Build a lookup dict: stub_prefix → list of (last_modified, size, filename)

    The stub prefix is the part of the filename before the first '.v0' version tag.
    e.g. v2_prvdr_enrlmt_hstry_idr_export.v01.2026_06_14_0514.csv
         → stub = v2_prvdr_enrlmt_hstry_idr_export
    """
    index = {}
    for last_modified, size, filename in s3_files:
        # filename: stub.v01.YYYY_MM_DD_HHMM.csv
        dot_v_idx = filename.find('.v0')
        if dot_v_idx != -1:
            stub = filename[:dot_v_idx]
        else:
            # Fallback: everything before the first dot
            stub = filename.split('.')[0]
        index.setdefault(stub, []).append((last_modified, size, filename))
        if verbose:
            print(f"    S3 stub: {stub}  ← {filename}")
    return index


# ============================================================================
# FRESHNESS CHECK
# ============================================================================

def check_tables(all_tables, s3_index, threshold_days):
    """
    For each table, determine its status:
        'fresh'   — in S3 and within threshold
        'stale'   — in S3 but older than threshold
        'missing' — not found in S3 at all

    Returns:
        results  — list of dicts with keys: table, stub, status, age_days, s3_file
        to_refresh — list of table names that need (re)downloading
    """
    now = datetime.now(tz=timezone.utc)
    threshold = timedelta(days=threshold_days)

    results = []
    to_refresh = []

    for table in all_tables:
        stub = table_to_stub(table)
        matches = s3_index.get(stub, [])

        if not matches:
            results.append({
                'table':   table,
                'stub':    stub,
                'status':  'missing',
                'age_days': None,
                's3_file': None,
            })
            to_refresh.append(table)
            continue

        # Use the most-recently modified file
        most_recent = max(matches, key=lambda t: t[0])
        last_modified, size, filename = most_recent
        age = now - last_modified
        age_days = age.days

        if age <= threshold:
            status = 'fresh'
        else:
            status = 'stale'
            to_refresh.append(table)

        results.append({
            'table':    table,
            'stub':     stub,
            'status':   status,
            'age_days': age_days,
            's3_file':  filename,
        })

    return results, to_refresh


# ============================================================================
# REPORTING
# ============================================================================

def print_report(results, threshold_days):
    """Print a formatted status report for every table."""
    icons = {'fresh': '✓', 'stale': '⚠', 'missing': '✗'}
    labels = {'fresh': 'FRESH  ', 'stale': 'STALE  ', 'missing': 'MISSING'}

    fresh   = [r for r in results if r['status'] == 'fresh']
    stale   = [r for r in results if r['status'] == 'stale']
    missing = [r for r in results if r['status'] == 'missing']

    print()
    print("=" * 70)
    print(f"S3 FRESHNESS REPORT  (threshold: {threshold_days} days)")
    print("=" * 70)

    for r in results:
        icon   = icons[r['status']]
        label  = labels[r['status']]
        table  = r['table'].split('.')[-1]       # just the table name part
        if r['age_days'] is not None:
            age_str = f"{r['age_days']}d ago"
        else:
            age_str = "not in S3"
        print(f"  {icon} {label}  {table:<55}  {age_str}")

    total       = len(results)
    out_of_date = len(stale) + len(missing)

    print()
    print(f"  ✓ Fresh      : {len(fresh)}/{total}")
    print(f"  ✗ Out of date: {out_of_date}/{total}  [{len(stale)} stale + {len(missing)} missing]")
    print("=" * 70)


# ============================================================================
# WRITE step1_tables_to_export.csv
# ============================================================================

def write_step1_csv(idr2_dir, tables):
    """Overwrite idr2/step1_tables_to_export.csv with the given list of tables."""
    out_file = idr2_dir / "step1_tables_to_export.csv"
    with open(out_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['table_to_download'])
        for t in tables:
            writer.writerow([t])
    print(f"  Written: {out_file}  ({len(tables)} table(s))")
    return out_file


# ============================================================================
# RUN DOWNSTREAM STEPS
# ============================================================================

def run_step(script_path, description):
    """Run a Python script as a subprocess. Exits on failure."""
    print()
    print(f"{'=' * 60}")
    print(f"Running: {description}")
    print(f"  {script_path}")
    print(f"{'=' * 60}")
    result = subprocess.run([sys.executable, str(script_path)], capture_output=False)
    if result.returncode != 0:
        print(f"\nERROR: {description} failed (exit code {result.returncode})")
        print("Fix the error above then re-run step0 or run step2/step3 manually.")
        sys.exit(result.returncode)
    print(f"✓ {description} complete")


# ============================================================================
# MAIN
# ============================================================================

def main():
    config        = setup_config()
    project_root  = config['project_root']
    idr2_dir      = config['idr2_dir']
    s3_bucket     = config['s3_bucket']
    threshold_days = config['threshold_days']

    print("=" * 60)
    print("step0_refresh_s3.py  —  S3 Freshness Check")
    print("=" * 60)
    print(f"S3 bucket        : {s3_bucket}")
    print(f"Refresh threshold: {threshold_days} days")

    # ── 1. Read all available tables ─────────────────────────────────────────
    all_tables_csv = idr2_dir / "all_available_tables.csv"
    if not all_tables_csv.exists():
        print(f"ERROR: {all_tables_csv} not found")
        sys.exit(1)

    all_tables = []
    with open(all_tables_csv, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = row.get('table_to_download', '').strip()
            if t:
                all_tables.append(t)

    print(f"Tables in all_available_tables.csv: {len(all_tables)}")

    # ── 2. List S3 files ─────────────────────────────────────────────────────
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    s3_files = list_s3_files(s3_bucket, verbose=verbose)
    s3_index = build_s3_index(s3_files, verbose=verbose)

    if verbose:
        print(f"\n  S3 stubs found ({len(s3_index)}):")
        for stub in sorted(s3_index):
            print(f"    {stub}")
        print()

    # ── 3. Check each table ──────────────────────────────────────────────────
    results, to_refresh = check_tables(all_tables, s3_index, threshold_days)
    
    if verbose:
        print("\n  Table → stub mapping:")
        for r in results:
            print(f"    {r['table'].split('.')[-1]:<55}  →  {r['stub']}")
        print()

    # ── 4. Print report ──────────────────────────────────────────────────────
    print_report(results, threshold_days)

    if not to_refresh:
        print()
        print("✓ All tables are fresh — nothing to do.")
        print("  If you want to force a refresh, lower REFRESH_DAY_THRESHOLD in .env")
        return 0

    print()
    print(f"→ {len(to_refresh)} table(s) need (re)downloading:")
    for t in to_refresh:
        print(f"    {t.split('.')[-1]}")

    # ── 5. Write new step1_tables_to_export.csv ──────────────────────────────
    print()
    print("Writing new idr2/step1_tables_to_export.csv ...")
    write_step1_csv(idr2_dir, to_refresh)

    # ── 6. Run step2 (regenerate export_metadata.json) ───────────────────────
    step2 = project_root / "idr2" / "local_laptop" / "step2_generate_metadata.py"
    run_step(step2, "step2: Generate export metadata")

    # ── 7. Run step3 (regenerate Snowflake Cell 2 script) ────────────────────
    step3 = project_root / "idr2" / "local_laptop" / "step3_generate_snowflake_cell2.py"
    run_step(step3, "step3: Generate Snowflake Cell 2 script")

    print()
    print("=" * 60)
    print("✓ Done.  Next steps:")
    print(f"  1. Review idr2/step1_tables_to_export.csv  ({len(to_refresh)} tables)")
    print("  2. Paste idr2/snowflake/cell2_snowflake_export_notebook.py into Snowflake Cell 2")
    print("  3. Start step4 on your laptop and Cell 2 in Snowflake in parallel")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
