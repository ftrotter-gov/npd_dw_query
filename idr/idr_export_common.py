"""
Shared scaffolding for the IDR Snowflake → local CSV (optional → S3) extracts.

The per-extract scripts (idr_entity_linkage.py, idr_medicare_address.py,
idr_medicaid_address.py) keep ONLY their SQL builder and a tiny __main__ that
calls run_export(); everything else — env-driven config, auth, the connection,
the claim window, and the user-stage relay — lives here so all three share one
implementation.

WHY THIS SHAPE: the originals were Streamlit-in-Snowflake / Snowsight worksheet
scripts (`get_active_session()`), which only run *inside* Snowflake. These run
headless from the laptop OR from AWS using a Programmatic Access Token (PAT),
mirroring idr2/aws/orchestrator.py's auth + user-stage relay:

    COPY INTO @~/<file>.csv  FROM ( <query> )   # Snowflake internal user stage
    GET @~/<file>.csv  → local OUTPUT_DIR        # pulled out over the connector
    (optional) boto3 upload → S3                 # if S3_BUCKET is set
    REMOVE @~/<file>.csv                         # clear the stage once materialized

Snowflake never needs outbound S3 access: it unloads to its own internal user
stage, this process pulls the file out through the connector, and — if S3_BUCKET
is set — this process (which holds the AWS creds) does the S3 write.

Auth (precedence in resolve_auth, identical to the orchestrator so one PAT setup
serves both):
    1. SNOWFLAKE_AUTHENTICATOR=externalbrowser  → interactive browser SSO
       (LAPTOP ONLY; pops a browser; use when the PAT has expired). Wins if set.
    2. PAT (passed to the connector as `password`):
         a. LOCAL, in order:
              SNOWFLAKE_PAT  (or SNOWFLAKE_PASSWORD)   inline token
              SNOWFLAKE_PAT_FILE                        path to a token file
              ~/.config/idr2/snowflake_pat             default token file
         b. FALLBACK:
              SNOWFLAKE_PAT_SECRET_ID   AWS Secrets Manager id/ARN
                  (CMS AWS dev already has one: "idr2/snowflake-pat")
    3. Key-pair:
         SNOWFLAKE_PRIVATE_KEY_SECRET_ID / SNOWFLAKE_PRIVATE_KEY /
         SNOWFLAKE_PRIVATE_KEY_PATH (+ optional SNOWFLAKE_PRIVATE_KEY_PASSPHRASE)

Dependencies (NOT in requirements.txt, which targets the Snowsight runtime):
    pip install snowflake-connector-python        # always
    pip install boto3                             # only for the AWS-secret fallback or S3 upload

Tunables (all optional; defaults reproduce the original behavior):
    CLAIM_WINDOW_END_DATE   ISO date; overrides the computed window end
    CLAIM_WINDOW_MONTHS     window length in months            (default 12)
    CLAIM_WINDOW_LAG_MONTHS how far before "now" the window ends (default 2)
    MIN_BENE                small-cell suppression threshold    (default 10)

A SQL builder must have the signature
    build_sql(stage_target, start_sql, end_sql, min_bene) -> str
and emit a `COPY INTO {stage_target} FROM ( ... ) FILE_FORMAT = (...) ...`
statement. run_export() supplies stage_target = "@~/<file_prefix>.<window>.csv".
"""

import gzip
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from calendar import monthrange
from datetime import date, datetime, timezone
from pathlib import Path

# Default local-laptop PAT file (same location the orchestrator uses), checked
# after SNOWFLAKE_PAT / SNOWFLAKE_PAT_FILE and before the AWS Secrets Manager
# fallback.
DEFAULT_PAT_FILE = Path.home() / ".config" / "idr2" / "snowflake_pat"

# Snowflake caps a SINGLE=TRUE unload file at 5 GB on an internal stage. These
# outputs are aggregated (grouped, HAVING > MIN_BENE), so they are orders of
# magnitude under this — one file keeps the GET a single exact-name fetch.
MAX_SINGLE_FILE_BYTES = 5_000_000_000

DEFAULT_WAREHOUSE = "IDRC_PRD_COMM_WH"


# ============================================================================
# LOGGING  (plain stdout — CloudWatch friendly, line-buffered)
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
    return bool(v) and v.strip().lower() in ("externalbrowser", "external_browser", "sso")


def load_config():
    """Read all configuration from environment variables."""
    cfg = {
        "account":   _clean(os.environ.get("SNOWFLAKE_ACCOUNT")),
        "user":      _clean(os.environ.get("SNOWFLAKE_USER")),
        "role":      _clean(os.environ.get("SNOWFLAKE_ROLE")),               # recommended
        "warehouse": _clean(os.environ.get("SNOWFLAKE_WAREHOUSE")) or DEFAULT_WAREHOUSE,
        "database":  _clean(os.environ.get("SNOWFLAKE_DATABASE")),           # optional (query is fully-qualified)
        "schema":    _clean(os.environ.get("SNOWFLAKE_SCHEMA")),             # optional
        # output
        "output_dir": _clean(os.environ.get("OUTPUT_DIR")) or ".",
        "s3_bucket":  _clean(os.environ.get("S3_BUCKET")),                   # optional s3://bucket/prefix/
        # query window / threshold (defaults reproduce the original script)
        "window_end_date":  _clean(os.environ.get("CLAIM_WINDOW_END_DATE")),
        "window_months":    int(_clean(os.environ.get("CLAIM_WINDOW_MONTHS")) or 12),
        "window_lag_months": int(_clean(os.environ.get("CLAIM_WINDOW_LAG_MONTHS")) or 2),
        "min_bene":         int(_clean(os.environ.get("MIN_BENE")) or 10),
        # auth — interactive SSO (laptop only)
        "authenticator": _clean(os.environ.get("SNOWFLAKE_AUTHENTICATOR")),
        # auth — PAT sources (local first, AWS Secrets Manager fallback)
        "pat_inline":    os.environ.get("SNOWFLAKE_PAT") or os.environ.get("SNOWFLAKE_PASSWORD"),
        "pat_file":      _clean(os.environ.get("SNOWFLAKE_PAT_FILE")),
        "pat_secret_id": _clean(os.environ.get("SNOWFLAKE_PAT_SECRET_ID")),
        # auth — key-pair fallback
        "pk_secret_id":  _clean(os.environ.get("SNOWFLAKE_PRIVATE_KEY_SECRET_ID")),
        "pk_inline":     os.environ.get("SNOWFLAKE_PRIVATE_KEY"),
        "pk_path":       _clean(os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")),
        "pk_passphrase": os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"),
    }

    missing = [k for k in ("account", "user", "warehouse") if not cfg[k]]
    if missing:
        log(f"FATAL: missing required env vars: {', '.join('SNOWFLAKE_' + v.upper() for v in missing)}")
        sys.exit(2)

    has_sso = _is_externalbrowser(cfg["authenticator"])
    has_local_pat = bool(cfg["pat_inline"] or cfg["pat_file"] or DEFAULT_PAT_FILE.exists())
    has_pat = bool(has_local_pat or cfg["pat_secret_id"])
    has_key = bool(cfg["pk_secret_id"] or cfg["pk_inline"] or cfg["pk_path"])
    if not (has_sso or has_pat or has_key):
        _fatal_no_pat("no auth configured")
    return cfg


# ============================================================================
# AUTH  →  connector kwargs   (mirrors idr2/aws/orchestrator.py)
# ============================================================================

def _read_secret(secret_id):
    """Fetch a secret string from AWS Secrets Manager (boto3 imported lazily)."""
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
    """Return the connector auth kwargs (externalbrowser → PAT local → PAT AWS → key-pair)."""
    if _is_externalbrowser(cfg["authenticator"]):
        log("Auth: externalbrowser SSO (interactive — laptop only)")
        return {"authenticator": "externalbrowser"}

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

    if cfg["pk_secret_id"] or cfg["pk_inline"] or cfg["pk_path"]:
        log("Auth: key-pair")
        return {"private_key": load_private_key_der(cfg)}

    _fatal_no_pat("no local PAT and no AWS Secrets Manager PAT configured")


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
# CLAIM WINDOW
# ============================================================================

def add_months(base_date, months):
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def compute_window(cfg):
    """One year (window_months) ending window_lag_months before now, unless
    CLAIM_WINDOW_END_DATE pins the end explicitly."""
    if cfg["window_end_date"]:
        end = date.fromisoformat(cfg["window_end_date"])
    else:
        end = add_months(datetime.now().date(), -cfg["window_lag_months"])
    start = add_months(end, -cfg["window_months"])
    return start, end


# ============================================================================
# USER-STAGE RELAY  (COPY → GET → optional S3 → REMOVE)
# ============================================================================

def _ci(rec, name, default=0):
    """Case-insensitive lookup into a COPY result dict."""
    for k, v in rec.items():
        if k.lower() == name.lower():
            return v
    return default


def unload_to_stage(conn, filename, sql):
    """Run the COPY INTO @~/<filename>. Returns rows_unloaded (0 == empty)."""
    log(f"  COPY INTO @~/{filename}")
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        cols = [c[0] for c in cur.description] if cur.description else []
    rec = dict(zip(cols, row)) if row else {}
    return int(_ci(rec, "rows_unloaded", 0) or 0)


def get_stage_file(conn, filename, output_dir):
    """GET @~/<filename> into output_dir. Returns the local Path, or None."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    uri = Path(output_dir).resolve().as_uri()
    log(f"  GET @~/{filename} → {output_dir}")
    with conn.cursor() as cur:
        cur.execute(f"GET @~/{filename} '{uri}'")
    local = Path(output_dir) / filename
    return local if local.exists() else None


def remove_stage_file(conn, filename):
    """REMOVE @~/<filename> after the local (and S3, if any) copy is confirmed."""
    with conn.cursor() as cur:
        cur.execute(f"REMOVE @~/{filename}")


# ----------------------------------------------------------------------------
# MULTI-FILE RELAY  (for unloads too big for a 5 GB SINGLE=TRUE file)
#
# Snowflake caps a SINGLE=TRUE unload at 5 GB. For larger result sets, unload
# with SINGLE=FALSE to a stage "directory" prefix (@~/<dir>/); Snowflake writes
# N part files (each <= MAX_FILE_SIZE, optionally gzipped). We GET them all, then
# concatenate locally into ONE plain CSV — keeping the header from the first part
# and dropping the repeated header line from every subsequent part. The result is
# byte-for-byte the same rows a single-file unload would have produced (the query
# still applies SELECT DISTINCT / GROUP BY globally; SINGLE=FALSE only changes how
# the one result set is split across output files).
# ----------------------------------------------------------------------------

def unload_to_stage_multifile(conn, stage_dir, sql):
    """Run a multi-file COPY INTO @~/<stage_dir>/. Returns rows_unloaded (0 == empty)."""
    log(f"  COPY INTO @~/{stage_dir}/  (multi-file)")
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        cols = [c[0] for c in cur.description] if cur.description else []
    rec = dict(zip(cols, row)) if row else {}
    return int(_ci(rec, "rows_unloaded", 0) or 0)


def stage_dir_bytes(conn, stage_dir):
    """Sum the byte size of every part under @~/<stage_dir>/ (0 if empty). Used to
    measure a staged result BEFORE downloading it, so a caller can pick a delivery
    that fits local disk instead of blindly GETting a multi-hundred-GB result."""
    total = 0
    with conn.cursor() as cur:
        cur.execute(f"LIST @~/{stage_dir}/")
        # LIST columns: name, size, md5, last_modified
        for row in cur.fetchall():
            try:
                total += int(row[1])
            except (TypeError, ValueError, IndexError):
                pass
    return total


def _merge_parts_gzip(parts, final):
    """Merge gzipped part files into ONE clean gzip CSV at `final`, keeping the
    header once and stripping the repeated header from parts 2..N, recompressing
    with the system `gzip` (streamed, low memory). Each part is deleted right
    after it is merged so peak disk stays near the compressed part total rather
    than doubling it. The output is a valid multi-member gzip that decompresses to
    the concatenated CSV with a single header line."""
    if final.exists():
        final.unlink()
    for i, p in enumerate(parts):
        decompress = f"gzip -dc {shlex.quote(str(p))}" if p.suffix == ".gz" \
                     else f"cat {shlex.quote(str(p))}"
        strip = "cat" if i == 0 else "tail -n +2"   # drop the repeated header row
        cmd = f"{decompress} | {strip} | gzip -1 >> {shlex.quote(str(final))}"
        rc = subprocess.run(["/bin/sh", "-c", cmd]).returncode
        if rc != 0:
            raise RuntimeError(f"gzip merge failed on {p.name} (rc={rc})")
        p.unlink()   # free each part immediately


def get_and_merge_stage_dir(conn, stage_dir, final_filename, output_dir, compress=False):
    """
    GET every part under @~/<stage_dir>/ into a temp dir, then concatenate them
    into <output_dir>/<final_filename> (header written once, repeated part headers
    dropped). Handles gzipped parts transparently.

    compress=False -> one plain CSV (default; original behavior).
    compress=True  -> one gzip-compressed CSV (final_filename should end in .gz);
                      recompressed with system gzip and each part deleted as it is
                      merged, so a very large result lands at ~its compressed size
                      instead of the full plain-CSV size.

    Returns the local Path, or None.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    # temp dir lives beside the output so the GET and the final file share a volume
    tmp = Path(tempfile.mkdtemp(prefix=".idr_parts_", dir=str(out)))
    try:
        uri = tmp.resolve().as_uri()
        log(f"  GET @~/{stage_dir}/ → {tmp}")
        with conn.cursor() as cur:
            cur.execute(f"GET @~/{stage_dir}/ '{uri}'")

        parts = sorted(p for p in tmp.iterdir() if p.is_file())
        if not parts:
            log("  ✗ GET produced no part files")
            return None
        log(f"  merging {len(parts)} part file(s) → {final_filename}"
            f"{' (gzip output)' if compress else ''}")

        final = out / final_filename
        if compress:
            _merge_parts_gzip(parts, final)
        else:
            wrote_header = False
            with open(final, "wb") as fout:
                for p in parts:
                    opener = gzip.open if p.suffix == ".gz" else open
                    with opener(p, "rb") as fin:
                        header = fin.readline()      # each part repeats the header
                        if not wrote_header:
                            fout.write(header)
                            wrote_header = True
                        shutil.copyfileobj(fin, fout)  # stream the data rows
                    p.unlink()                        # free each part immediately
        return final if final.exists() else None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def remove_stage_dir(conn, stage_dir):
    """REMOVE @~/<stage_dir>/ (all parts) after the local/S3 copy is confirmed."""
    with conn.cursor() as cur:
        cur.execute(f"REMOVE @~/{stage_dir}/")


def parse_s3_uri(s3_bucket):
    """s3://bucket/prefix/ → (bucket, prefix). prefix may be ''."""
    without = s3_bucket[len("s3://"):] if s3_bucket.startswith("s3://") else s3_bucket
    bucket, _, prefix = without.partition("/")
    return bucket, prefix


def upload_and_validate(local_file, s3_bucket):
    """Upload local_file to S3 and confirm the object size matches (boto3 lazy)."""
    import boto3
    s3_client = boto3.client("s3")
    bucket, prefix = parse_s3_uri(s3_bucket)
    key = (prefix.rstrip("/") + "/" + local_file.name).lstrip("/")
    size = local_file.stat().st_size
    log(f"  upload → s3://{bucket}/{key}  ({size / 1_048_576:.1f} MB)")
    s3_client.upload_file(str(local_file), bucket, key)
    head = s3_client.head_object(Bucket=bucket, Key=key)
    if head["ContentLength"] != size:
        log(f"  ✗ SIZE MISMATCH local={size:,} s3={head['ContentLength']:,}")
        return None
    log(f"  ✓ validated ({size:,} bytes)")
    return key


# ============================================================================
# DRIVER  — the shared main() the per-extract scripts call
# ============================================================================

def run_export(*, banner, file_prefix, sql_builder, min_bene_label="Min beneficiaries"):
    """
    Drive one extract end to end: config → window → COPY → GET → optional S3 →
    REMOVE. The per-extract script supplies:
      banner        one-line description logged at the top
      file_prefix   output basename prefix; the stage/local file is
                    "<file_prefix>.<start>_to_<end>.csv"
      sql_builder   build_sql(stage_target, start_sql, end_sql, min_bene) -> str
      min_bene_label  wording for the small-cell threshold log line
    Returns a process exit code (0 ok / empty, 1 relay failure).
    """
    log("=" * 60)
    log(f"{banner} — Snowflake → local CSV (optional → S3)")
    log("=" * 60)

    cfg = load_config()
    start, end = compute_window(cfg)
    log(f"Claim window : {start.isoformat()} → {end.isoformat()} "
        f"({cfg['window_months']}mo ending {cfg['window_lag_months']}mo back)")
    log(f"{min_bene_label} (small-cell) : > {cfg['min_bene']}")

    filename = f"{file_prefix}.{start:%Y_%m_%d}_to_{end:%Y_%m_%d}.csv"
    sql = sql_builder(f"@~/{filename}", start.isoformat(), end.isoformat(), cfg["min_bene"])

    auth_kwargs = resolve_auth(cfg)
    conn = connect(cfg, auth_kwargs)
    try:
        rows = unload_to_stage(conn, filename, sql)
        if rows == 0:
            log("  ⊘ 0 rows — nothing written to the stage. Done.")
            return 0
        log(f"  ✓ unloaded {rows:,} rows to @~/{filename}")

        local = get_stage_file(conn, filename, cfg["output_dir"])
        if local is None:
            log("  ✗ GET produced no local file — leaving the stage intact for retry")
            return 1
        log(f"  ✓ local file: {local}  ({local.stat().st_size:,} bytes)")

        if cfg["s3_bucket"]:
            key = upload_and_validate(local, cfg["s3_bucket"])
            if not key:
                log("  ✗ S3 upload/validate failed — leaving the stage intact for retry")
                return 1

        remove_stage_file(conn, filename)
        log(f"  ✓ cleared @~/{filename}")
    finally:
        conn.close()

    log("=" * 60)
    log("DONE")
    log("=" * 60)
    return 0
