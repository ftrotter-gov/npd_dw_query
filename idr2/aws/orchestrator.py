"""
IDR2 AWS Orchestrator — single-process Snowflake → S3 export (ECS relay).

This collapses the old two-machine handshake (the Snowflake notebook in
cell1/cell2 + the laptop poller in step4_download_merge_upload.py) into ONE
program with NO polling, NO handshake, and NO notebook.

For each table (read from step1_tables_to_export.csv) it does, in sequence:

    COPY INTO @~/<stub>.<ver>.<ts>  FROM (SELECT * FROM <table>)   # SINGLE=FALSE, multi-part
    GET @~/<prefix>_N_N_N.csv  → local scratch/parts (over the existing connection)
    merge parts → one <prefix>.csv  (reconciled merge, misc_scripts/snowflake_csv_merge.py)
    boto3 upload   → S3   (uses the task role / local AWS creds — no Snowflake S3 access needed)
    validate object size, then REMOVE each @~/ part

Why this shape: the IDR account is locked down and the export role cannot create
a storage integration, so Snowflake itself cannot write to the external S3
bucket. Instead Snowflake unloads to its OWN internal user stage (@~/), the
container pulls the files out through the connector, and the container — which
holds the AWS credentials — does the S3 write. Snowflake never needs outbound
access to the bucket.

EXPORT SHAPE: multi-file (SINGLE=FALSE) is the DEFAULT, so tables of any size
work through one code path — Snowflake writes <prefix>_N_N_N.csv parts, we GET
them all and merge them back into a single <prefix>.csv before upload. Set
EXPORT_SINGLE_FILE=1 for the old one-file SINGLE=TRUE fast path on known-small
tables (it fails on anything over the 5 GB single-file cap). MAX_FILE_SIZE tunes
the per-part cap (default 4 GB).

WHERE IT RUNS: on the laptop TODAY (Snowflake reached over VPN), flipping to
Fargate unchanged once Snowflake PrivateLink lands in the dev VPC. See the auth
note below — the same binary runs in both places, only the auth env differs.

FRESHNESS (Approach A — full snapshot, only when changed):
    Downstream needs a COMPLETE file each run, so we never write deltas. Before
    exporting, we ask Snowflake for a cheap change-signal — COUNT(*) plus
    MAX(<timestamp column>) — and compare it to the signature stored from the
    last successful export (_watermarks.json in the S3 prefix). Unchanged +
    previous file still present → skip the table and keep the existing complete
    file. Changed → full export, then record the new signature. For the IDR
    provider-enrollment views the change column is IDR_UPDT_TS (set via
    WATERMARK_COLUMN); auto-discovery is the fallback.

MANUAL / TARGETED RUNS (for console "Run task" or local testing):
    FORCE_EXPORT=1        export everything, ignore the skip logic
    ONLY_TABLES=a,b,c     only tables whose name/stub contains one of these

Auth (precedence in resolve_auth):
    1. SNOWFLAKE_AUTHENTICATOR=externalbrowser  → interactive browser SSO.
       LAPTOP ONLY (pops a browser; cannot run headless on Fargate). Use as the
       fallback when the PAT has expired. Wins even if a PAT is also set.
    2. Programmatic Access Token (PAT) — passed to the connector as `password`.
       LOCAL laptop PAT is tried first, then AWS Secrets Manager as a fallback:
         a. LOCAL (checked in this order):
              SNOWFLAKE_PAT  (or SNOWFLAKE_PASSWORD)   the token, inline
              SNOWFLAKE_PAT_FILE                        path to a token file
              ~/.config/idr2/snowflake_pat             default token file
         b. FALLBACK:
              SNOWFLAKE_PAT_SECRET_ID   AWS Secrets Manager secret id/ARN
                  (the CMS AWS dev account already has one: "idr2/snowflake-pat")
       If neither a local PAT nor the AWS secret is available, the run exits with
       guidance to populate one.
    3. Key-pair fallback:
         SNOWFLAKE_PRIVATE_KEY_SECRET_ID / SNOWFLAKE_PRIVATE_KEY / SNOWFLAKE_PRIVATE_KEY_PATH
         (+ optional SNOWFLAKE_PRIVATE_KEY_PASSPHRASE)

All other configuration comes from environment variables (see load_config()).
Logging goes to stdout → CloudWatch Logs.

Local (laptop) run using a PAT stored locally (~/.config/idr2/snowflake_pat is
picked up automatically — no PAT env var needed):
    AWS_PROFILE=<Kion STAK profile> AWS_REGION=us-east-1 \
    SNOWFLAKE_ACCOUNT=<SNOWFLAKE_ACCOUNT> \
    SNOWFLAKE_USER=<SNOWFLAKE_USER> \
    SNOWFLAKE_ROLE=<SNOWFLAKE_ROLE> \
    SNOWFLAKE_WAREHOUSE=<SNOWFLAKE_WAREHOUSE> \
    S3_BUCKET=s3://<S3_BUCKET>/idr_bulk/ \
    WATERMARK_COLUMN=IDR_UPDT_TS \
    python3 idr2/aws/orchestrator.py

    # No local PAT? Set SNOWFLAKE_PAT_SECRET_ID=idr2/snowflake-pat to pull it from
    # AWS Secrets Manager instead (the automatic fallback).
    # If the PAT has expired, force browser SSO:
    #   SNOWFLAKE_AUTHENTICATOR=externalbrowser
"""

import os
import sys
import json
import time
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timezone


_REPO_ROOT = Path(__file__).resolve().parents[2]          # repo root (contains idr2/)

# Snowflake caps a SINGLE=TRUE unload file at 5 GB on an internal stage too.
MAX_SINGLE_FILE_BYTES = 5_000_000_000
# Default per-part cap for the multi-file (SINGLE=FALSE) path. Kept under the
# 5 GB ceiling for headroom (MAX_FILE_SIZE is a target, not a hard guarantee);
# override with MAX_FILE_SIZE. Parts are merged back into one CSV on download.
DEFAULT_PART_FILE_BYTES = 4_000_000_000
WATERMARKS_NAME = "_watermarks.json"

# Default local-laptop PAT file, checked after SNOWFLAKE_PAT / SNOWFLAKE_PAT_FILE
# and before the AWS Secrets Manager fallback.
DEFAULT_PAT_FILE = Path.home() / ".config" / "idr2" / "snowflake_pat"


# ============================================================================
# LOGGING  (plain stdout — CloudWatch friendly, no ANSI, line-buffered)
# ============================================================================

def log(message=""):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}Z] {message}", flush=True)


# ============================================================================
# CONFIG
# ============================================================================

def _clean(v):
    return v.strip().strip('"').strip("'") if v else v


def _truthy(v):
    return bool(v) and v.strip().lower() in ("1", "true", "yes", "on", "y")


def _is_externalbrowser(v):
    """True when SNOWFLAKE_AUTHENTICATOR requests interactive browser SSO."""
    return bool(v) and v.strip().lower() in ("externalbrowser", "external_browser", "sso")


def load_config():
    """Read all configuration from environment variables."""
    cfg = {
        "account":    _clean(os.environ.get("SNOWFLAKE_ACCOUNT")),
        "user":       _clean(os.environ.get("SNOWFLAKE_USER")),
        "role":       _clean(os.environ.get("SNOWFLAKE_ROLE")),
        "warehouse":  _clean(os.environ.get("SNOWFLAKE_WAREHOUSE")),
        "database":   _clean(os.environ.get("SNOWFLAKE_DATABASE")),   # optional
        "schema":     _clean(os.environ.get("SNOWFLAKE_SCHEMA")),     # optional
        "s3_bucket":  _clean(os.environ.get("S3_BUCKET")),            # s3://bucket/prefix/
        "tables_csv": _clean(os.environ.get("TABLES_CSV")) or
                      str(_REPO_ROOT / "idr2" / "step1_tables_to_export.csv"),
        "scratch_dir": _clean(os.environ.get("SCRATCH_DIR")),         # default: a tempdir
        # freshness (Approach A): skip a table when its data is unchanged
        "watermark_column": _clean(os.environ.get("WATERMARK_COLUMN")),  # e.g. IDR_UPDT_TS
        "force_export": _truthy(os.environ.get("FORCE_EXPORT")),         # bypass skip, export all
        "only_tables":  _clean(os.environ.get("ONLY_TABLES")),           # comma-sep name/stub filter
        # export shape: multi-file (default, any size) vs SINGLE=TRUE fast path
        "single_file":   _truthy(os.environ.get("EXPORT_SINGLE_FILE")),  # opt-in one-file path
        "deep_validate": not _truthy(os.environ.get("DEEP_VALIDATE_OFF")),  # merge deep check (default on)
        "part_file_bytes": int(_clean(os.environ.get("MAX_FILE_SIZE"))
                               or DEFAULT_PART_FILE_BYTES),               # per-part cap for multi-file
        # auth — interactive SSO (laptop only; not for headless/Fargate)
        "authenticator": _clean(os.environ.get("SNOWFLAKE_AUTHENTICATOR")),
        # auth — PAT sources. LOCAL laptop PAT (inline env or a local file) is
        # tried FIRST; the AWS Secrets Manager secret is the fallback.
        "pat_inline":    os.environ.get("SNOWFLAKE_PAT")
                         or os.environ.get("SNOWFLAKE_PASSWORD"),
        "pat_file":      _clean(os.environ.get("SNOWFLAKE_PAT_FILE")),
        "pat_secret_id": _clean(os.environ.get("SNOWFLAKE_PAT_SECRET_ID")),
        # auth — key-pair fallback sources
        "pk_secret_id": _clean(os.environ.get("SNOWFLAKE_PRIVATE_KEY_SECRET_ID")),
        "pk_inline":    os.environ.get("SNOWFLAKE_PRIVATE_KEY"),
        "pk_path":      _clean(os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")),
        "pk_passphrase": os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"),
    }

    missing = [k for k in ("account", "user", "warehouse", "s3_bucket") if not cfg[k]]
    if missing:
        log(f"FATAL: missing required env vars: {', '.join(v.upper() for v in missing)}")
        for v in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_WAREHOUSE", "S3_BUCKET"):
            log(f"  required: {v}")
        sys.exit(2)

    has_sso = _is_externalbrowser(cfg["authenticator"])
    has_local_pat = bool(cfg["pat_inline"] or cfg["pat_file"] or DEFAULT_PAT_FILE.exists())
    has_pat = bool(has_local_pat or cfg["pat_secret_id"])
    has_key = bool(cfg["pk_secret_id"] or cfg["pk_inline"] or cfg["pk_path"])
    if not (has_sso or has_pat or has_key):
        _fatal_no_pat("no auth configured")
    return cfg


# ============================================================================
# AUTH  →  connector kwargs
# ============================================================================

def _read_secret(secret_id):
    """Fetch a secret string from AWS Secrets Manager."""
    import boto3
    sm = boto3.client("secretsmanager")
    resp = sm.get_secret_value(SecretId=secret_id)
    return resp.get("SecretString") or resp["SecretBinary"]


def _read_pat_file(path):
    """Return the stripped token from a local PAT file, or '' if unreadable/missing."""
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        return ""
    except OSError as e:
        log(f"WARN: could not read PAT file {path}: {e}")
        return ""


def load_local_pat(cfg):
    """
    Resolve a PAT configured on the LOCAL laptop, checked in order:
      1. SNOWFLAKE_PAT / SNOWFLAKE_PASSWORD   (inline env)
      2. SNOWFLAKE_PAT_FILE                    (explicit file path)
      3. ~/.config/idr2/snowflake_pat          (default dotfile)
    Returns (token, source_label), or (None, None) when no local PAT is present.
    """
    if cfg["pat_inline"]:
        return cfg["pat_inline"].strip(), "env SNOWFLAKE_PAT"
    if cfg["pat_file"]:
        p = Path(cfg["pat_file"]).expanduser()
        tok = _read_pat_file(p)
        if tok:
            return tok, f"file {p} (SNOWFLAKE_PAT_FILE)"
        log(f"WARN: SNOWFLAKE_PAT_FILE={p} set but no token could be read from it")
    tok = _read_pat_file(DEFAULT_PAT_FILE)
    if tok:
        return tok, f"file {DEFAULT_PAT_FILE}"
    return None, None


def _fatal_no_pat(detail):
    """Log actionable guidance for a missing PAT and exit non-zero."""
    log(f"FATAL: Snowflake PAT unavailable — {detail}.")
    log("Populate ONE of the following (local laptop is tried first, then AWS):")
    log("  LOCAL laptop PAT:")
    log("    export SNOWFLAKE_PAT='<token>'")
    log("    or  export SNOWFLAKE_PAT_FILE=/path/to/pat")
    log(f"    or  write the token to {DEFAULT_PAT_FILE}")
    log("  AWS Secrets Manager (fallback):")
    log("    export SNOWFLAKE_PAT_SECRET_ID=idr2/snowflake-pat   (requires AWS creds)")
    log("  (Or force interactive SSO: SNOWFLAKE_AUTHENTICATOR=externalbrowser)")
    sys.exit(2)


def load_private_key_der(cfg):
    """Resolve the PEM private key from its configured source and return DER bytes."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    if cfg["pk_secret_id"]:
        log(f"Loading private key from Secrets Manager: {cfg['pk_secret_id']}")
        secret = _read_secret(cfg["pk_secret_id"])
        pem_bytes = secret.encode() if isinstance(secret, str) else secret
    elif cfg["pk_inline"]:
        log("Loading private key from SNOWFLAKE_PRIVATE_KEY (inline)")
        pem_bytes = cfg["pk_inline"].encode()
    else:
        path = Path(cfg["pk_path"]).expanduser()
        log(f"Loading private key from file: {path}")
        pem_bytes = path.read_bytes()

    passphrase = cfg["pk_passphrase"].encode() if cfg["pk_passphrase"] else None
    private_key = serialization.load_pem_private_key(
        pem_bytes, password=passphrase, backend=default_backend()
    )
    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def resolve_auth(cfg):
    """
    Return the connector auth kwargs. Precedence:

      1. explicit SNOWFLAKE_AUTHENTICATOR=externalbrowser → interactive browser
         SSO (LAPTOP ONLY — pops a browser; cannot run headless on Fargate).
         Wins even when a PAT is present, so you can force SSO without unsetting
         anything.
      2. PAT — a Snowflake Programmatic Access Token, passed to the Python
         connector as the `password` argument. Sources tried in order:
           a. LOCAL laptop PAT  (SNOWFLAKE_PAT / SNOWFLAKE_PASSWORD, then
              SNOWFLAKE_PAT_FILE, then ~/.config/idr2/snowflake_pat)
           b. AWS Secrets Manager  (SNOWFLAKE_PAT_SECRET_ID) — the fallback
         If a local PAT is configured it is used; only if none is found do we
         reach out to AWS. If neither is available, exit with guidance to
         populate one (see _fatal_no_pat).
      3. key-pair.
    """
    if _is_externalbrowser(cfg["authenticator"]):
        log("Auth: externalbrowser SSO (interactive — laptop only)")
        return {"authenticator": "externalbrowser"}

    # PAT — local laptop first, AWS Secrets Manager as fallback.
    local_pat, src = load_local_pat(cfg)
    if local_pat:
        log(f"Auth: PAT from local laptop ({src})")
        return {"password": local_pat}
    if cfg["pat_secret_id"]:
        log(f"Auth: no local PAT found; falling back to AWS Secrets Manager ({cfg['pat_secret_id']})")
        try:
            token = _read_secret(cfg["pat_secret_id"])
        except Exception as e:
            _fatal_no_pat(f"AWS Secrets Manager fetch failed for {cfg['pat_secret_id']}: {e}")
        if isinstance(token, (bytes, bytearray)):
            token = token.decode()
        token = (token or "").strip()
        if not token:
            _fatal_no_pat(f"AWS secret {cfg['pat_secret_id']} is empty")
        return {"password": token}

    # key-pair fallback (unchanged).
    if cfg["pk_secret_id"] or cfg["pk_inline"] or cfg["pk_path"]:
        log("Auth: key-pair")
        return {"private_key": load_private_key_der(cfg)}

    # No PAT anywhere and no key-pair → tell the user how to populate one.
    _fatal_no_pat("no local PAT and no AWS Secrets Manager PAT configured")


# ============================================================================
# TABLE LIST  →  export metadata
# ============================================================================

def read_tables(cfg):
    """
    Read step1_tables_to_export.csv (header: table_to_download) and produce a
    list of dicts with the full name, the S3/file stub, and the SELECT query.

    file_name_stub mirrors step2_generate_metadata: <table_lower>_idr_export.
    An ONLY_TABLES filter (comma-separated substrings) narrows the list for
    targeted manual runs.
    """
    import csv
    path = Path(cfg["tables_csv"])
    if not path.exists():
        log(f"FATAL: tables CSV not found: {path}")
        sys.exit(2)

    only = [s.strip().lower() for s in (cfg["only_tables"] or "").split(",") if s.strip()]

    tables = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            full = (row.get("table_to_download") or "").strip()
            if not full or full.startswith("#"):
                continue
            parts = full.split(".")
            if len(parts) != 3:
                log(f"  ⚠ skipping malformed table name (need db.schema.table): {full}")
                continue
            table = parts[2]
            stub = f"{table.lower()}_idr_export"
            if only and not any(o in full.lower() or o in stub for o in only):
                continue
            tables.append({
                "full_table_name": full,
                "file_name_stub": stub,
                "version_number": "v01",
                "select_query": f"SELECT * FROM {full}",
            })
    if only:
        log(f"ONLY_TABLES filter active ({cfg['only_tables']}) → {len(tables)} table(s) match")
    return tables


# ============================================================================
# SNOWFLAKE CONNECTION
# ============================================================================

def connect(cfg, auth_kwargs):
    import snowflake.connector
    log(f"Connecting to Snowflake account={cfg['account']} user={cfg['user']} "
        f"role={cfg['role']} warehouse={cfg['warehouse']}")
    conn_kwargs = dict(
        account=cfg["account"],
        user=cfg["user"],
        warehouse=cfg["warehouse"],
        **auth_kwargs,
    )
    if cfg["role"]:
        conn_kwargs["role"] = cfg["role"]
    if cfg["database"]:
        conn_kwargs["database"] = cfg["database"]
    if cfg["schema"]:
        conn_kwargs["schema"] = cfg["schema"]
    conn = snowflake.connector.connect(**conn_kwargs)
    log("✓ Snowflake connection established")
    return conn


# ============================================================================
# S3 URI helpers
# ============================================================================

def parse_s3_uri(s3_bucket):
    """s3://bucket/prefix/ → (bucket, prefix). prefix may be ''."""
    without = s3_bucket[len("s3://"):] if s3_bucket.startswith("s3://") else s3_bucket
    bucket, _, prefix = without.partition("/")
    return bucket, prefix


# ============================================================================
# FRESHNESS / CHANGE DETECTION  (Approach A: skip unchanged full snapshots)
# ============================================================================

# Column-name scoring for auto-picking a watermark timestamp. Higher = better.
# An update/load timestamp detects in-place changes; insert/effective/any _TS
# detects the appends that dominate the *_HSTRY tables. (For the IDR provider
# views WATERMARK_COLUMN=IDR_UPDT_TS is set explicitly, so this is a fallback.)
def _score_ts_column(name, data_type):
    u = name.upper()
    t = data_type.upper()
    if not any(k in t for k in ("TIMESTAMP", "DATETIME", "DATE")):
        return -1
    if "UPDT" in u or "UPDATE" in u:
        score = 5
    elif "LOAD" in u:
        score = 4
    elif "INSRT" in u or "INSERT" in u:
        score = 3
    elif "TRANS" in u:
        score = 2
    elif u.endswith("_TS") or u.endswith("TSTMP") or u.endswith("_TSTAMP"):
        score = 1
    else:
        score = 0
    if "TIMESTAMP" in t:          # prefer a real timestamp over a bare DATE
        score += 0.5
    return score


def discover_watermark_column(conn, table, cfg):
    """Pick the best timestamp column to use as the change-signal, or None.
    An explicit WATERMARK_COLUMN override wins if set."""
    if cfg["watermark_column"]:
        return cfg["watermark_column"]
    db, schema, tbl = table["full_table_name"].split(".")
    q = (f"SELECT COLUMN_NAME, DATA_TYPE FROM {db}.INFORMATION_SCHEMA.COLUMNS "
         f"WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{tbl}'")
    with conn.cursor() as cur:
        cur.execute(q)
        rows = cur.fetchall()
    best, best_score = None, 0
    for name, dtype in rows:
        s = _score_ts_column(name, dtype)
        if s > best_score:
            best, best_score = name, s
    return best


def freshness_signature(conn, table, cfg):
    """Return (signature, ts_column). ts_column is None if no usable timestamp
    column exists — in that case the caller must NOT skip (can't detect updates)."""
    col = discover_watermark_column(conn, table, cfg)
    full = table["full_table_name"]
    if col:
        q = f"SELECT COUNT(*), MAX({col}) FROM {full}"
    else:
        q = f"SELECT COUNT(*) FROM {full}"
    with conn.cursor() as cur:
        cur.execute(q)
        row = cur.fetchone()
    if col:
        return f"n={row[0]};max={row[1]};col={col}", col
    return f"n={row[0]};col=<none>", None


def s3_key_exists(s3_client, s3_bucket, key):
    if not key:
        return False
    bucket, _ = parse_s3_uri(s3_bucket)
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def _watermarks_key(cfg):
    _, prefix = parse_s3_uri(cfg["s3_bucket"])
    return (prefix.rstrip("/") + "/" + WATERMARKS_NAME).lstrip("/")


def read_watermarks(s3_client, cfg):
    """Load the per-table watermark map from S3, or {} if none/unreadable."""
    bucket, _ = parse_s3_uri(cfg["s3_bucket"])
    key = _watermarks_key(cfg)
    try:
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        data = json.loads(obj["Body"].read())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_watermarks(s3_client, cfg, watermarks):
    bucket, _ = parse_s3_uri(cfg["s3_bucket"])
    key = _watermarks_key(cfg)
    body = json.dumps(watermarks, indent=2, default=str).encode()
    s3_client.put_object(Bucket=bucket, Key=key, Body=body,
                         ContentType="application/json")


# ============================================================================
# UNLOAD  →  user stage  →  GET  →  S3  (the relay)
# ============================================================================

def _ci(rec, name, default=0):
    """Case-insensitive lookup into a COPY result dict."""
    for k, v in rec.items():
        if k.lower() == name.lower():
            return v
    return default


def export_to_user_stage(conn, table):
    """
    COPY INTO @~/<file> FROM (SELECT ...) as ONE uncompressed CSV with a header.
    Returns (filename, rows_unloaded). rows_unloaded == 0 means the source was
    empty and nothing was written to the stage.
    """
    ts = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M")
    filename = f"{table['file_name_stub']}.{table['version_number']}.{ts}.csv"
    sql = (
        f"COPY INTO @~/{filename}\n"
        f"FROM (\n{table['select_query']}\n)\n"
        "FILE_FORMAT = (\n"
        "  TYPE = CSV\n"
        "  FIELD_DELIMITER = ','\n"
        "  FIELD_OPTIONALLY_ENCLOSED_BY = '\"'\n"
        "  COMPRESSION = NONE\n"
        ")\n"
        "HEADER = TRUE\n"
        "SINGLE = TRUE\n"
        f"MAX_FILE_SIZE = {MAX_SINGLE_FILE_BYTES}\n"
        "OVERWRITE = TRUE\n"
        "DETAILED_OUTPUT = FALSE"
    )
    log(f"  COPY INTO @~/{filename}")
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        cols = [c[0] for c in cur.description] if cur.description else []
    rec = dict(zip(cols, row)) if row else {}
    rows_unloaded = int(_ci(rec, "rows_unloaded", 0) or 0)
    return filename, rows_unloaded


def get_stage_file(conn, filename, scratch_dir):
    """GET @~/<filename> into scratch_dir. Returns the local Path, or None."""
    uri = Path(scratch_dir).resolve().as_uri()
    log(f"  GET @~/{filename} → scratch")
    with conn.cursor() as cur:
        cur.execute(f"GET @~/{filename} '{uri}'")
    local = Path(scratch_dir) / filename
    return local if local.exists() else None


def remove_stage_file(conn, filename):
    """REMOVE @~/<filename> after the S3 upload is confirmed."""
    with conn.cursor() as cur:
        cur.execute(f"REMOVE @~/{filename}")


# ── Multi-file (SINGLE=FALSE) path — for tables that exceed the 5 GB single-file
#    unload cap. Snowflake writes <prefix>_<N>_<N>_<N>.csv parts; we GET them all,
#    merge them back into one <prefix>.csv with the reconciled merge, upload the
#    single merged file, then REMOVE each part over the one open connection. ────

def export_to_user_stage_multi(conn, table, cfg):
    """
    COPY INTO @~/<prefix> FROM (SELECT ...) with SINGLE=FALSE, so Snowflake
    splits the unload into <prefix>_N_N_N.csv parts each capped near
    cfg['part_file_bytes']. Every part carries the header (HEADER=TRUE), which
    the merge strips from all but the first.

    Returns (prefix, rows_unloaded). prefix has NO .csv suffix — it is the shared
    root the part files hang off. rows_unloaded == 0 means the source was empty.
    """
    ts = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M")
    prefix = f"{table['file_name_stub']}.{table['version_number']}.{ts}"
    sql = (
        f"COPY INTO @~/{prefix}\n"
        f"FROM (\n{table['select_query']}\n)\n"
        "FILE_FORMAT = (\n"
        "  TYPE = CSV\n"
        "  FIELD_DELIMITER = ','\n"
        "  FIELD_OPTIONALLY_ENCLOSED_BY = '\"'\n"
        "  COMPRESSION = NONE\n"
        ")\n"
        "HEADER = TRUE\n"
        "SINGLE = FALSE\n"
        f"MAX_FILE_SIZE = {int(cfg['part_file_bytes'])}\n"
        "OVERWRITE = TRUE\n"
        "DETAILED_OUTPUT = FALSE"
    )
    log(f"  COPY INTO @~/{prefix}  (SINGLE=FALSE, part≈{int(cfg['part_file_bytes']):,} B)")
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        cols = [c[0] for c in cur.description] if cur.description else []
    rec = dict(zip(cols, row)) if row else {}
    rows_unloaded = int(_ci(rec, "rows_unloaded", 0) or 0)
    return prefix, rows_unloaded


# Snowflake part-file suffix: <prefix>_<n>_<n>_<n>.csv (also allow an optional
# .gz in case COMPRESSION is ever changed). Anchored to this prefix so a stray
# file from another table can never be pulled in.
def _part_pattern(prefix):
    import re
    return f".*{re.escape(prefix)}_[0-9]+_[0-9]+_[0-9]+\\.csv(\\.gz)?"


def get_stage_files_multi(conn, prefix, parts_dir):
    """
    GET every @~/<prefix>_N_N_N.csv part into parts_dir. Returns the sorted list
    of local part Paths (empty list if none landed).
    """
    Path(parts_dir).mkdir(parents=True, exist_ok=True)
    uri = Path(parts_dir).resolve().as_uri()
    pattern = _part_pattern(prefix)
    log(f"  GET @~/ PATTERN='{pattern}' → scratch/parts")
    with conn.cursor() as cur:
        cur.execute(f"GET @~/ '{uri}' PATTERN='{pattern}'")
    parts = sorted(
        p for p in Path(parts_dir).iterdir()
        if p.is_file() and p.name.startswith(prefix + "_")
    )
    return parts


def merge_parts(prefix, parts, merged_dir, deep_validate=True):
    """
    Merge the downloaded parts into a single <prefix>.csv using the corrected,
    reconciled merge in misc_scripts/snowflake_csv_merge.py. Returns the merged
    Path. Raises on any merge/validation failure (caller treats as table-failed).

    Imports the sibling script the same way stage_tool.py imports step4 — add its
    directory to sys.path, then import — so this stays in lockstep with the one
    audited/fixed merge instead of duplicating logic.
    """
    misc = str(_REPO_ROOT / "misc_scripts")
    if misc not in sys.path:
        sys.path.insert(0, misc)
    import snowflake_csv_merge as merge

    Path(merged_dir).mkdir(parents=True, exist_ok=True)
    log(f"  merge {len(parts)} part(s) → {prefix}.csv  (deep_validate={deep_validate})")
    merge.merge_group(prefix, [str(p) for p in parts],
                      outdir=str(merged_dir), deep_validate=deep_validate)
    merged = Path(merged_dir) / f"{prefix}.csv"
    if not merged.exists():
        raise RuntimeError(f"merge produced no file at {merged}")
    return merged


def remove_stage_files_multi(conn, part_basenames):
    """
    REMOVE each @~/<part> after the merged S3 upload is confirmed. Loops over the
    ONE already-open connection (no re-auth per file — that browser-storm only
    afflicted the old snowsql-subprocess-per-file path).
    """
    with conn.cursor() as cur:
        for name in part_basenames:
            cur.execute(f"REMOVE @~/{name}")


def upload_and_validate(s3_client, local_file, s3_bucket):
    """Upload local_file to S3 and confirm the object size matches.
    Returns the S3 key on success, or None on a size mismatch."""
    bucket, prefix = parse_s3_uri(s3_bucket)
    key = (prefix.rstrip("/") + "/" + local_file.name).lstrip("/")
    size = local_file.stat().st_size
    log(f"  upload → s3://{bucket}/{key}  ({size / 1_048_576:.1f} MB)")
    s3_client.upload_file(str(local_file), bucket, key)
    head = s3_client.head_object(Bucket=bucket, Key=key)
    s3_size = head["ContentLength"]
    if s3_size != size:
        log(f"  ✗ SIZE MISMATCH local={size:,} s3={s3_size:,}")
        return None
    log(f"  ✓ validated ({s3_size:,} bytes)")
    return key


# ============================================================================
# PER-TABLE PIPELINE
# ============================================================================

def process_table(conn, s3_client, cfg, table, scratch_root, watermarks):
    """Full pipeline for one table. Returns 'done' | 'empty' | 'failed' | 'skipped'."""
    stub = table["file_name_stub"]
    log("")
    log(f"╔══ {table['full_table_name']}  ({stub}) ══╗")

    # ── Change detection (compute up front; also recorded on success) ─────────
    sig, ts_col = None, None
    try:
        sig, ts_col = freshness_signature(conn, table, cfg)
        log(f"  signature: {sig}")
    except Exception as e:
        log(f"  ⚠ change-check failed ({e}); will export to be safe")

    if not cfg["force_export"] and ts_col is not None and sig is not None:
        prev = watermarks.get(stub)
        if prev and prev.get("signature") == sig \
                and s3_key_exists(s3_client, cfg["s3_bucket"], prev.get("last_key")):
            log(f"  ⏭ unchanged since {prev.get('exported_at', '?')} — skipping "
                f"(existing file kept: {prev.get('last_key')})")
            return "skipped"
    elif ts_col is None and sig is not None:
        log("  ⚠ no timestamp column found — cannot detect in-place updates, "
            "exporting full snapshot (set WATERMARK_COLUMN to enable skip)")

    # ── Unload to the internal user stage ─────────────────────────────────────
    # Default: multi-file (SINGLE=FALSE) — correct at ANY size, one code path.
    # EXPORT_SINGLE_FILE=1 opts into the old one-file SINGLE=TRUE fast path for
    # known-small runs (fails on tables over the 5 GB single-file cap).
    single = cfg["single_file"]
    try:
        if single:
            filename, rows = export_to_user_stage(conn, table)
        else:
            prefix, rows = export_to_user_stage_multi(conn, table, cfg)
    except Exception as e:
        msg = str(e)
        if single and ("MAX_FILE_SIZE" in msg or "exceeds" in msg.lower()):
            log(f"  ✗ COPY failed — table likely exceeds the {MAX_SINGLE_FILE_BYTES:,}-byte "
                f"single-file limit; unset EXPORT_SINGLE_FILE to use multi-file: {msg}")
        else:
            log(f"  ✗ COPY failed: {msg}")
        return "failed"

    if rows == 0:
        log("  ⊘ 0 rows — table empty, nothing written to stage")
        return "empty"
    log(f"  ✓ unloaded {rows:,} rows to stage")

    # Isolated scratch subdir so cleanup is a single rmtree.
    work_dir = Path(scratch_root) / f"work_{stub}"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        if single:
            local = get_stage_file(conn, filename, work_dir)
            if local is None:
                log("  ✗ GET produced no local file — aborting table (stage NOT cleared)")
                return "failed"
            staged_names = [filename]
        else:
            parts = get_stage_files_multi(conn, prefix, work_dir / "parts")
            if not parts:
                log("  ✗ GET produced no part files — aborting table (stage NOT cleared)")
                return "failed"
            log(f"  ✓ downloaded {len(parts)} part(s)")
            try:
                local = merge_parts(prefix, parts, work_dir / "merged",
                                    deep_validate=cfg["deep_validate"])
            except Exception as e:
                log(f"  ✗ merge/validation failed — aborting table (stage NOT cleared): {e}")
                return "failed"
            staged_names = [p.name for p in parts]

        key = upload_and_validate(s3_client, local, cfg["s3_bucket"])
        if not key:
            log("  ✗ upload/validate failed — aborting table (stage NOT cleared)")
            return "failed"

        # Only clear the stage after S3 is confirmed.
        if single:
            remove_stage_file(conn, staged_names[0])
        else:
            remove_stage_files_multi(conn, staged_names)

        if sig is not None and ts_col is not None:
            watermarks[stub] = {
                "signature": sig,
                "ts_column": ts_col,
                "last_key": key,
                "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }

        log(f"╚══ {stub} DONE ══╝")
        return "done"
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ============================================================================
# MAIN
# ============================================================================

def main():
    log("=" * 60)
    log("IDR2 AWS Orchestrator — Snowflake → S3 (user-stage relay)")
    log("=" * 60)

    cfg = load_config()
    tables = read_tables(cfg)
    log(f"Tables to export : {len(tables)}  (from {cfg['tables_csv']})")
    log(f"S3 destination   : {cfg['s3_bucket']}")

    if not tables:
        log("Nothing to export — table list is empty. Exiting cleanly.")
        return 0

    auth_kwargs = resolve_auth(cfg)

    # scratch root: explicit SCRATCH_DIR or an auto temp dir (ECS ephemeral disk)
    scratch_root = cfg["scratch_dir"] or tempfile.mkdtemp(prefix="idr2_export_")
    Path(scratch_root).mkdir(parents=True, exist_ok=True)
    log(f"Scratch dir      : {scratch_root}")

    import boto3
    s3_client = boto3.client("s3")

    watermarks = read_watermarks(s3_client, cfg)
    log(f"Change detection : {'FORCED full export' if cfg['force_export'] else 'on'} "
        f"({len(watermarks)} table(s) with prior watermarks)")

    conn = connect(cfg, auth_kwargs)

    start = time.time()
    counts = {"done": 0, "empty": 0, "failed": 0, "skipped": 0}
    failed_tables = []
    try:
        for i, table in enumerate(tables, 1):
            log("")
            log(f"[{i}/{len(tables)}] {table['full_table_name']}")
            try:
                result = process_table(conn, s3_client, cfg, table, scratch_root, watermarks)
            except Exception as e:
                log(f"  ✗ unhandled error: {e}")
                result = "failed"
            counts[result] += 1
            if result == "failed":
                failed_tables.append(table["full_table_name"])
    finally:
        conn.close()
        # Persist watermarks even on partial/crashed runs so completed tables
        # can be skipped next time.
        try:
            write_watermarks(s3_client, cfg, watermarks)
            log(f"Watermarks saved → s3 ({_watermarks_key(cfg)})")
        except Exception as e:
            log(f"⚠ failed to save watermarks: {e}")
        # only remove the scratch root if we created it ourselves
        if not cfg["scratch_dir"]:
            shutil.rmtree(scratch_root, ignore_errors=True)

    elapsed = time.time() - start
    log("")
    log("=" * 60)
    log("SUMMARY")
    log(f"  exported : {counts['done']}")
    log(f"  skipped  : {counts['skipped']}  (unchanged)")
    log(f"  empty    : {counts['empty']}")
    log(f"  failed   : {counts['failed']}")
    if failed_tables:
        for t in failed_tables:
            log(f"    ✗ {t}")
    log(f"  elapsed  : {int(elapsed // 3600)}h {int((elapsed % 3600) // 60)}m")
    log("=" * 60)

    # Non-zero exit if anything failed → ECS/EventBridge marks the run failed.
    return 1 if failed_tables else 0


if __name__ == "__main__":
    sys.exit(main())
