"""
Execution engine for the IDR worksheet dashboard.

Everything Snowflake-facing runs HERE, inside the Fargate task, in the prod VPC —
so the PrivateLink route to Snowflake is used and no data ever touches the laptop.

PAT HANDLING (the hard requirement): the Programmatic Access Token is supplied by
the browser at run time and held ONLY in this process's memory (see server.py's
session store). It is passed to the Snowflake connector as `password` and is never
written to disk, environment, Secrets Manager, CloudTrail, or any log line. This
module deliberately reuses idr/idr_export_common.connect() but NEVER calls
resolve_auth() (which would read the stored AWS secret) — auth_kwargs are built
here from the in-memory PAT.

Two execution paths, matching the two behaviours we want visible in the UI:

  run_inline()  — execute SQL, fetch a small result set straight over the
                  connector, optionally write it as one CSV to S3. This is the
                  path proven to WORK in-VPC (inline results, our-bucket writes).

  run_relay()   — COPY INTO @~/<file> → GET → upload to S3 → REMOVE. This is the
                  bulk path that currently HANGS in-VPC at the GET (the Path A
                  read-plane blocker). Wired now so it lights up the moment the
                  S3 interface endpoint lands; today it will visibly hang and the
                  heartbeat + Cancel make that obvious rather than silent.

Runs are serialised (one warehouse, no contention) and their stdout is captured
line-by-line into the run's queue so the websocket can stream logs — including the
log() output from idr_export_common — to the browser.
"""

import contextlib
import csv
import io
import os
import queue
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# idr/ is on sys.path (see server bootstrap); reuse the shared helpers verbatim.
import idr_export_common as ec


# ---------------------------------------------------------------------------
# Static (non-secret) config — baked into the task definition environment.
# NOTE: unlike ec.load_config(), this does NOT require any auth env var, because
# the only auth we ever use is the in-memory PAT from the browser.
# ---------------------------------------------------------------------------

def service_cfg():
    c = {
        "account":   ec._clean(os.environ.get("SNOWFLAKE_ACCOUNT")),
        "user":      ec._clean(os.environ.get("SNOWFLAKE_USER")),
        "role":      ec._clean(os.environ.get("SNOWFLAKE_ROLE")),
        "warehouse": ec._clean(os.environ.get("SNOWFLAKE_WAREHOUSE")) or ec.DEFAULT_WAREHOUSE,
        "database":  ec._clean(os.environ.get("SNOWFLAKE_DATABASE")),
        "schema":    ec._clean(os.environ.get("SNOWFLAKE_SCHEMA")),
    }
    return c


def default_output_bucket():
    return ec._clean(os.environ.get("S3_BUCKET")) or "s3://YOUR_BUCKET/idr_worksheet/"


# ---------------------------------------------------------------------------
# Connection using the in-RAM PAT only (no resolve_auth / no Secrets Manager).
# ---------------------------------------------------------------------------

def connect_with_pat(pat):
    """Open a Snowflake connection using the browser-supplied PAT (as `password`).

    The PAT lives only in the caller's memory; it is never persisted here. Returns
    a live connection the caller must close.
    """
    if not pat:
        raise RuntimeError("No PAT in session — enter your Snowflake PAT first.")
    cfg = service_cfg()
    missing = [k for k in ("account", "user", "warehouse") if not cfg[k]]
    if missing:
        raise RuntimeError("Task is missing config: "
                           + ", ".join("SNOWFLAKE_" + m.upper() for m in missing))
    # Pass the PAT exactly the way resolve_auth would have (as password), but
    # sourced from RAM instead of the AWS secret.
    return ec.connect(cfg, {"password": pat})


def probe_connection(pat):
    """Quick liveness/identity check for the status bar. Returns a dict; never raises."""
    try:
        conn = connect_with_pat(pat)
    except Exception as e:  # noqa: BLE001 - surface any failure as status text
        return {"connected": False, "error": _redact(str(e))}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT CURRENT_ACCOUNT(), CURRENT_ROLE(), "
                        "CURRENT_WAREHOUSE(), CURRENT_USER()")
            acct, role, wh, user = cur.fetchone()
        return {"connected": True, "account": acct, "role": role,
                "warehouse": wh, "user": user}
    except Exception as e:  # noqa: BLE001
        return {"connected": False, "error": _redact(str(e))}
    finally:
        with contextlib.suppress(Exception):
            conn.close()


def _redact(msg):
    """Belt-and-braces: never let a token-looking string reach a log or the UI."""
    if not msg:
        return msg
    out = []
    for tok in msg.split():
        out.append("***" if len(tok) > 40 and tok.isalnum() else tok)
    return " ".join(out)


# ===========================================================================
# RUN REGISTRY  — one active run at a time; stdout captured to a per-run queue.
# ===========================================================================

_run_lock = threading.Lock()        # serialise executions (one warehouse)
RUNS = {}                           # run_id -> Run


class Run:
    def __init__(self):
        self.id = uuid.uuid4().hex[:12]
        self.q = queue.Queue()
        self.status = "queued"       # queued|running|done|error|cancelled
        self.result = None           # dict: columns/rows preview or s3 summary
        self.cancel = threading.Event()
        self._cur = None             # live cursor, so cancel() can abort a query
        self._conn = None

    def emit(self, line):
        self.q.put({"t": "log", "line": line})

    def finish(self, status, result=None):
        self.status = status
        self.result = result
        self.q.put({"t": "end", "status": status, "result": result})

    def request_cancel(self):
        self.cancel.set()
        # Best-effort abort of an in-flight query / connection (helps unstick a
        # hanging GET well enough to return control to the UI).
        with contextlib.suppress(Exception):
            if self._cur is not None:
                self._cur.cancel()
        with contextlib.suppress(Exception):
            if self._conn is not None:
                self._conn.close()


class _QueueWriter(io.TextIOBase):
    """A file-like that turns writes into log events on a run's queue, so every
    print()/log() during a run streams to the browser."""
    def __init__(self, run):
        self.run = run
        self._buf = ""

    def write(self, s):
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self.run.emit(line)
        return len(s)

    def flush(self):
        if self._buf:
            self.run.emit(self._buf)
            self._buf = ""


def _ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _heartbeat(run, started):
    """Emit a 'still working' line every 15s so a HANG is visibly a hang, not a
    dead UI. Stops when the run leaves 'running'."""
    while run.status == "running" and not run.cancel.is_set():
        time.sleep(15)
        if run.status == "running" and not run.cancel.is_set():
            secs = int(time.time() - started)
            run.emit(f"[{_ts()}] … still working ({secs}s) — if this is a bulk "
                     f"COPY→GET it will hang here until the S3 endpoint (Path A) lands")


def start_run(pat, *, mode, sql=None, copy_sql=None, filename=None, s3_uri=None,
              preview_rows=200):
    """Kick off a run in a worker thread and return its Run immediately."""
    run = Run()
    RUNS[run.id] = run

    def worker():
        # Only one run executes at a time; capture stdout for the duration.
        with _run_lock:
            if run.cancel.is_set():
                run.finish("cancelled")
                return
            run.status = "running"
            started = time.time()
            threading.Thread(target=_heartbeat, args=(run, started), daemon=True).start()
            writer = _QueueWriter(run)
            try:
                with contextlib.redirect_stdout(writer):
                    if mode == "inline":
                        _do_inline(run, pat, sql, s3_uri, preview_rows)
                    elif mode == "relay":
                        _do_relay(run, pat, copy_sql, filename, s3_uri)
                    else:
                        raise RuntimeError(f"unknown run mode {mode!r}")
                writer.flush()
            except Exception as e:  # noqa: BLE001
                writer.flush()
                run.emit(f"[{_ts()}] ERROR: {_redact(type(e).__name__)}: {_redact(str(e))}")
                import traceback
                run.emit(_redact(traceback.format_exc()))
                run.finish("error")

    threading.Thread(target=worker, daemon=True).start()
    return run


# ---------------------------------------------------------------------------
# INLINE path — WORKS in-VPC. Execute, preview, optional small CSV → S3.
# ---------------------------------------------------------------------------

def _do_inline(run, pat, sql, s3_uri, preview_rows):
    ec.log(f"mode=inline  preview_rows={preview_rows}")
    conn = connect_with_pat(pat)
    run._conn = conn
    try:
        cur = conn.cursor()
        run._cur = cur
        ec.log("executing query …")
        cur.execute(sql)
        cols = [c[0] for c in cur.description] if cur.description else []

        # Pull the whole (small) result so we can both preview AND write it to S3.
        rows = cur.fetchall()
        ec.log(f"✓ {len(rows):,} row(s) returned")

        preview = rows[:preview_rows]
        result = {
            "kind": "table",
            "columns": cols,
            "rows": [[_cell(v) for v in r] for r in preview],
            "row_count": len(rows),
            "truncated": len(rows) > len(preview),
        }

        if s3_uri:
            if run.cancel.is_set():
                run.finish("cancelled"); return
            key = _write_rows_to_s3(cols, rows, s3_uri)
            result["s3"] = key
            ec.log(f"✓ wrote result → {key}")

        run.finish("done", result)
    finally:
        with contextlib.suppress(Exception):
            conn.close()


def _cell(v):
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def _write_rows_to_s3(cols, rows, s3_uri):
    """Write cols+rows as one CSV to s3_uri (a full s3://bucket/prefix/name.csv or
    a prefix ending in '/'). Returns the s3:// key written."""
    import boto3
    bucket, prefix = ec.parse_s3_uri(s3_uri)
    if s3_uri.rstrip().endswith("/") or not prefix.lower().endswith(".csv"):
        name = f"worksheet_result_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.csv"
        key = (prefix.rstrip("/") + "/" + name).lstrip("/")
    else:
        key = prefix.lstrip("/")

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    data = buf.getvalue().encode("utf-8")

    ec.log(f"  upload → s3://{bucket}/{key}  ({len(data)/1_048_576:.2f} MB)")
    s3 = boto3.client("s3")
    s3.put_object(Bucket=bucket, Key=key, Body=data)
    head = s3.head_object(Bucket=bucket, Key=key)
    if head["ContentLength"] != len(data):
        raise RuntimeError("S3 size mismatch after upload")
    return f"s3://{bucket}/{key}"


# ---------------------------------------------------------------------------
# RELAY path — bulk COPY→GET→S3. HANGS in-VPC today (Path A blocker).
# ---------------------------------------------------------------------------

def _do_relay(run, pat, copy_sql, filename, s3_uri):
    ec.log("mode=relay  (COPY INTO @~/… → GET → S3)")
    ec.log("NOTE: the GET step reads Snowflake-owned S3 and currently HANGS from "
           "this VPC until the S3 interface endpoint (Path A) is provisioned.")
    conn = connect_with_pat(pat)
    run._conn = conn
    try:
        cur = conn.cursor(); run._cur = cur
        rows = ec.unload_to_stage(conn, filename, copy_sql)
        if rows == 0:
            ec.log("⊘ 0 rows unloaded — nothing to fetch.")
            run.finish("done", {"kind": "message", "text": "0 rows"})
            return
        ec.log(f"✓ unloaded {rows:,} rows to @~/{filename}")

        out_dir = os.environ.get("OUTPUT_DIR", "/tmp/idr_worksheet")
        ec.log(f"GET @~/{filename} → {out_dir}  (this is the step that hangs today)")
        local = ec.get_stage_file(conn, filename, out_dir)   # <-- hangs in-VPC now
        if local is None:
            ec.log("✗ GET produced no local file")
            run.finish("error"); return
        ec.log(f"✓ local file {local} ({local.stat().st_size:,} bytes)")

        bucket, prefix = ec.parse_s3_uri(s3_uri)
        key = ec.upload_and_validate(local, s3_uri)
        with contextlib.suppress(Exception):
            local.unlink()
        if not key:
            run.finish("error"); return
        ec.remove_stage_file(conn, filename)
        run.finish("done", {"kind": "message", "text": f"s3://{bucket}/{key}"})
    finally:
        with contextlib.suppress(Exception):
            conn.close()
