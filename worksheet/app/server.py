"""
IDR worksheet dashboard — FastAPI backend.

Runs inside the on-demand Fargate task in the prod VPC. Serves the single-page UI,
holds each browser session's PAT in memory only, executes queries via engine.py,
and streams logs/results back over a websocket.

PAT: stored in SESSIONS[sid]["pat"] (process RAM) keyed by an httponly session
cookie. Never written to disk/env/Secrets Manager/logs. Cleared on logout, on idle
expiry, and when the task exits.

Cost control: an idle watchdog exits the process after IDLE_SHUTDOWN_MINUTES with no
HTTP activity, so a forgotten task stops the Fargate run (→ $0) on its own.
"""

import os
import sys
import threading
import time
import uuid
from pathlib import Path

# Put idr/ on the path so engine.py can `import idr_export_common`.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "idr"))

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import engine
import scripts_registry as reg

STATIC_DIR = Path(__file__).resolve().parent / "static"
IDLE_MIN = int(os.environ.get("IDLE_SHUTDOWN_MINUTES", "30"))
SESSION_TTL = int(os.environ.get("SESSION_TTL_MINUTES", "60")) * 60

app = FastAPI(title="IDR Worksheet")

SESSIONS = {}                 # sid -> {"pat": str|None, "last": float}
_last_activity = time.time()  # for the idle watchdog


# ---------------------------------------------------------------------------
# session helpers
# ---------------------------------------------------------------------------

def _now():
    return time.time()


def _get_sid(request: Request):
    return request.cookies.get("ws_sid")


def _session(request: Request):
    sid = _get_sid(request)
    if not sid or sid not in SESSIONS:
        return None
    s = SESSIONS[sid]
    if _now() - s["last"] > SESSION_TTL:
        s["pat"] = None                      # expire the PAT, keep the shell
    s["last"] = _now()
    return s


def _require_pat(request: Request):
    s = _session(request)
    if not s or not s.get("pat"):
        raise HTTPException(status_code=401, detail="No PAT in session — enter your PAT.")
    return s["pat"]


@app.middleware("http")
async def _touch(request: Request, call_next):
    global _last_activity
    _last_activity = _now()
    return await call_next(request)


# ---------------------------------------------------------------------------
# static UI
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ---------------------------------------------------------------------------
# PAT (in-RAM) + status
# ---------------------------------------------------------------------------

@app.post("/api/pat")
async def set_pat(request: Request, response: Response):
    body = await request.json()
    pat = (body or {}).get("pat", "").strip()
    if not pat:
        raise HTTPException(status_code=400, detail="empty PAT")
    sid = _get_sid(request) or uuid.uuid4().hex
    SESSIONS[sid] = {"pat": pat, "last": _now()}
    response.set_cookie("ws_sid", sid, httponly=True, samesite="lax")
    status = engine.probe_connection(pat)     # verify immediately
    if not status.get("connected"):
        # keep the PAT (maybe warehouse is asleep) but report the failure
        return JSONResponse({"stored": True, **status})
    return {"stored": True, **status}


@app.delete("/api/pat")
def clear_pat(request: Request):
    sid = _get_sid(request)
    if sid and sid in SESSIONS:
        SESSIONS[sid]["pat"] = None
    return {"cleared": True}


@app.get("/api/status")
def status(request: Request):
    s = _session(request)
    cfg = engine.service_cfg()
    base = {
        "account_cfg": cfg["account"],
        "role_cfg": cfg["role"],
        "warehouse_cfg": cfg["warehouse"],
        "default_output": engine.default_output_bucket(),
        "idle_shutdown_minutes": IDLE_MIN,
    }
    if not s or not s.get("pat"):
        return {"pat_loaded": False, "connected": False, **base}
    probe = engine.probe_connection(s["pat"])
    return {"pat_loaded": True, **probe, **base}


# ---------------------------------------------------------------------------
# scripts / worksheets
# ---------------------------------------------------------------------------

@app.get("/api/worksheets")
def worksheets():
    return {"worksheets": reg.list_worksheets(),
            "default_output": engine.default_output_bucket()}


@app.get("/api/scripts")
def scripts():
    return {"scripts": reg.list_repo_scripts()}


@app.get("/api/scripts/source")
def script_source(path: str):
    try:
        return {"path": path, "source": reg.get_repo_script_source(path)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

@app.post("/api/run")
async def run(request: Request):
    pat = _require_pat(request)
    body = await request.json()
    mode = body.get("mode")                    # "inline" | "relay"
    sql = body.get("sql")
    s3_uri = (body.get("s3_uri") or "").strip() or None
    save = bool(body.get("save_to_s3"))
    if not mode:
        raise HTTPException(status_code=400, detail="mode required")

    if mode == "inline":
        r = engine.start_run(pat, mode="inline", sql=sql,
                             s3_uri=s3_uri if save else None)
    elif mode == "relay":
        filename = body.get("filename") or "ws_export.csv"
        if not s3_uri:
            raise HTTPException(status_code=400, detail="relay needs an S3 output path")
        r = engine.start_run(pat, mode="relay", copy_sql=sql,
                             filename=filename, s3_uri=s3_uri)
    else:
        raise HTTPException(status_code=400, detail=f"bad mode {mode}")
    return {"run_id": r.id}


@app.post("/api/run/{run_id}/cancel")
def cancel(run_id: str):
    r = engine.RUNS.get(run_id)
    if not r:
        raise HTTPException(status_code=404, detail="no such run")
    r.request_cancel()
    return {"cancelled": True}


@app.websocket("/api/run/{run_id}/ws")
async def run_ws(ws: WebSocket, run_id: str):
    await ws.accept()
    r = engine.RUNS.get(run_id)
    if not r:
        await ws.send_json({"t": "end", "status": "error",
                            "result": {"kind": "message", "text": "no such run"}})
        await ws.close()
        return
    import asyncio
    try:
        while True:
            try:
                evt = r.q.get_nowait()
            except Exception:
                await asyncio.sleep(0.2)
                if r.status in ("done", "error", "cancelled") and r.q.empty():
                    break
                continue
            await ws.send_json(evt)
            if evt.get("t") == "end":
                break
    except WebSocketDisconnect:
        return
    finally:
        with __import__("contextlib").suppress(Exception):
            await ws.close()


# ---------------------------------------------------------------------------
# idle watchdog → scale to zero
# ---------------------------------------------------------------------------

def _idle_watchdog():
    if IDLE_MIN <= 0:
        return
    while True:
        time.sleep(60)
        if _now() - _last_activity > IDLE_MIN * 60:
            print(f"[idle] no activity for {IDLE_MIN} min — exiting so the task "
                  f"stops (cost → $0).", flush=True)
            os._exit(0)


threading.Thread(target=_idle_watchdog, daemon=True).start()
