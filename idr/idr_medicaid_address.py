"""
IDR Medicaid provider-address export — standalone Snowflake → local CSV (optional → S3).

Derives provider service-location addresses from one year of Medicaid claims in
IDR (V2_MDCD_CLM). Every claim contributes its admitting, billing, supervising and
service-location-org NPI, each paired with the claim's service-location address and
the recipient's State Medicaid ID; the result is aggregated per (NPI, address) with
the count of distinct Medicaid recipients and suppressed below a small-cell
threshold. See build_address_sql() for the query.

WHY THIS SHAPE: the original was a Streamlit-in-Snowflake / Snowsight worksheet
script (`get_active_session()`), which only runs *inside* Snowflake. This version
runs headless from the laptop OR from AWS using a Programmatic Access Token (PAT),
mirroring idr/idr_entity_linkage.py and idr2/aws/orchestrator.py's auth + relay:

    COPY INTO @~/<file>.csv  FROM ( <address query> )   # Snowflake internal user stage
    GET @~/<file>.csv  → local OUTPUT_DIR                # pulled out over the connector
    (optional) boto3 upload → S3                         # if S3_BUCKET is set
    REMOVE @~/<file>.csv                                 # clear the stage once materialized

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

Local (laptop) run — picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> \
    SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with Medicaid claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH \
    OUTPUT_DIR=./idr_data \
    python3 idr/idr_medicaid_address.py

    # Pull the PAT from AWS Secrets Manager instead of a local file:
    #   AWS_PROFILE=<Kion STAK> AWS_REGION=us-east-1 SNOWFLAKE_PAT_SECRET_ID=idr2/snowflake-pat ...
    # Also land the CSV in S3 (like the orchestrator):
    #   S3_BUCKET=s3://<bucket>/idr_medicaid_address/
    # PAT expired? force browser SSO:
    #   SNOWFLAKE_AUTHENTICATOR=externalbrowser

Tunables (all optional; defaults reproduce the intended behavior):
    CLAIM_WINDOW_END_DATE   ISO date; overrides the computed window end
    CLAIM_WINDOW_MONTHS     window length in months            (default 12)
    CLAIM_WINDOW_LAG_MONTHS how far before "now" the window ends (default 2)
    MIN_BENE                small-cell suppression threshold    (default 10)

NOTE (carried over from the source query, deliberately unchanged): the SELECT and
GROUP BY keep YEAR(CLM_THRU_DT) AS claim_year. With a rolling window that spans two
calendar years, a single (NPI, address) can emit up to two rows and the small-cell
suppression is applied per calendar-year half. Drop claim_year from the SELECT and
GROUP BY if you want exactly one row per (NPI, address) over the full window.
"""

import os
import sys
from calendar import monthrange
from datetime import date, datetime, timezone
from pathlib import Path

# Default local-laptop PAT file (same location the orchestrator uses), checked
# after SNOWFLAKE_PAT / SNOWFLAKE_PAT_FILE and before the AWS Secrets Manager
# fallback.
DEFAULT_PAT_FILE = Path.home() / ".config" / "idr2" / "snowflake_pat"

# Snowflake caps a SINGLE=TRUE unload file at 5 GB on an internal stage. The
# address output is aggregated (grouped, HAVING > MIN_BENE), so it is orders of
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
# MEDICAID ADDRESS QUERY
# ============================================================================

def build_address_sql(stage_target, start_sql, end_sql, min_bene):
    """
    COPY INTO @~/<file>.csv the provider service-location addresses seen on one
    window of Medicaid claims. Each claim contributes its admitting, billing,
    supervising and service-location-org NPI, each paired with the claim's
    service-location address and the recipient's State Medicaid ID; the output is
    (claim_year, NPI, address) with the count of distinct recipients, suppressed
    at > min_bene. One uncompressed, headered CSV (SINGLE=TRUE).

    BUG FIXES vs. the Snowsight source:
      * window: the source hardcoded YEAR(CLM_THRU_DT) = 2026, ignoring the
        computed rolling window; this filters CLM_THRU_DT to [start, end).
      * output name: caller writes @~/idr_medicaid_address.* (the source reused
        the entity-linkage name, which collides with that extract on the stage
        and in the CSV merger's filename-root grouping).
    Upstream improvements kept: recipient key CLM_RCPNT_STATE_MDCD_ID (was the
    Medicare-only CLM_BENE MBI, which restricted counts to dual-eligibles) and
    the supervising-provider NPI union branch.
    """
    return f"""
COPY INTO {stage_target}
FROM (
WITH claim_npis AS (
    SELECT
        CLM_THRU_DT,
        CLM_ADMTG_PRVDR_NPI_NUM AS NPI,
        CLM_SRVC_LCTN_LINE_1_ADR,
        CLM_SRVC_LCTN_LINE_2_ADR,
        CLM_SRVC_LCTN_CITY_NAME,
        CLM_SRVC_LCTN_STATE_CD,
        CLM_SRVC_LCTN_ZIP_CD,
        CLM_RCPNT_STATE_MDCD_ID
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM

    UNION ALL

    SELECT
        CLM_THRU_DT,
        CLM_BLG_PRVDR_NPI_NUM AS NPI,
        CLM_SRVC_LCTN_LINE_1_ADR,
        CLM_SRVC_LCTN_LINE_2_ADR,
        CLM_SRVC_LCTN_CITY_NAME,
        CLM_SRVC_LCTN_STATE_CD,
        CLM_SRVC_LCTN_ZIP_CD,
        CLM_RCPNT_STATE_MDCD_ID
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM

    UNION ALL

    SELECT
        CLM_THRU_DT,
        CLM_SPRVSNG_PRVDR_NPI_NUM AS NPI,
        CLM_SRVC_LCTN_LINE_1_ADR,
        CLM_SRVC_LCTN_LINE_2_ADR,
        CLM_SRVC_LCTN_CITY_NAME,
        CLM_SRVC_LCTN_STATE_CD,
        CLM_SRVC_LCTN_ZIP_CD,
        CLM_RCPNT_STATE_MDCD_ID
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM

    UNION ALL

    SELECT
        CLM_THRU_DT,
        CLM_SRVC_LCTN_ORG_NPI_NUM AS NPI,
        CLM_SRVC_LCTN_LINE_1_ADR,
        CLM_SRVC_LCTN_LINE_2_ADR,
        CLM_SRVC_LCTN_CITY_NAME,
        CLM_SRVC_LCTN_STATE_CD,
        CLM_SRVC_LCTN_ZIP_CD,
        CLM_RCPNT_STATE_MDCD_ID
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD.V2_MDCD_CLM
)

SELECT
    YEAR(CLM_THRU_DT) AS claim_year,
    NPI,
    CLM_SRVC_LCTN_LINE_1_ADR,
    CLM_SRVC_LCTN_LINE_2_ADR,
    CLM_SRVC_LCTN_CITY_NAME,
    CLM_SRVC_LCTN_STATE_CD,
    CLM_SRVC_LCTN_ZIP_CD,
    COUNT(DISTINCT CLM_RCPNT_STATE_MDCD_ID) AS DISTINCT_PATIENT_COUNT
FROM claim_npis
WHERE NPI IS NOT NULL
  AND CLM_RCPNT_STATE_MDCD_ID IS NOT NULL
  AND NULLIF(TRIM(CLM_SRVC_LCTN_LINE_1_ADR), '') IS NOT NULL
  AND NULLIF(TRIM(CLM_SRVC_LCTN_CITY_NAME), '') IS NOT NULL
  AND NULLIF(TRIM(CLM_SRVC_LCTN_STATE_CD), '') IS NOT NULL
  AND NULLIF(TRIM(CLM_SRVC_LCTN_ZIP_CD), '') IS NOT NULL
  AND CLM_THRU_DT >= DATE '{start_sql}'
  AND CLM_THRU_DT <  DATE '{end_sql}'
GROUP BY
    YEAR(CLM_THRU_DT),
    NPI,
    CLM_SRVC_LCTN_LINE_1_ADR,
    CLM_SRVC_LCTN_LINE_2_ADR,
    CLM_SRVC_LCTN_CITY_NAME,
    CLM_SRVC_LCTN_STATE_CD,
    CLM_SRVC_LCTN_ZIP_CD
HAVING COUNT(DISTINCT CLM_RCPNT_STATE_MDCD_ID) > {min_bene}

)
FILE_FORMAT = (
  TYPE = CSV
  FIELD_DELIMITER = ','
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  COMPRESSION = NONE
)
HEADER = TRUE
SINGLE = TRUE
MAX_FILE_SIZE = {MAX_SINGLE_FILE_BYTES}
OVERWRITE = TRUE
DETAILED_OUTPUT = FALSE
"""


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
# MAIN
# ============================================================================

def main():
    log("=" * 60)
    log("IDR Medicaid provider-address export — Snowflake → local CSV (optional → S3)")
    log("=" * 60)

    cfg = load_config()
    start, end = compute_window(cfg)
    log(f"Claim window : {start.isoformat()} → {end.isoformat()} "
        f"({cfg['window_months']}mo ending {cfg['window_lag_months']}mo back)")
    log(f"Min distinct recipients (small-cell) : > {cfg['min_bene']}")

    filename = f"idr_medicaid_address.{start:%Y_%m_%d}_to_{end:%Y_%m_%d}.csv"
    sql = build_address_sql(f"@~/{filename}", start.isoformat(), end.isoformat(), cfg["min_bene"])

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


if __name__ == "__main__":
    sys.exit(main())
