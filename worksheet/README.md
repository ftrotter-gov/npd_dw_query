# IDR Worksheet

A Snowflake-worksheet-style dashboard that runs **in our AWS**, connects to IDR
Snowflake over **PrivateLink**, and lands query output **straight to prod S3** —
without your PAT ever being stored on AWS and without anything downloading to your
laptop.

```
  ┌── top status bar: ● Snowflake connected · account · role · warehouse ──┐
  │ browse worksheets/scripts │  edit SQL (Monaco)   │  Result / Console    │
  │  ① works now              │  output S3 path ____ │  live logs + errors  │
  │  ② hangs until Path A     │  [Run ▶] [Cancel]    │  result table        │
  └────────────────────────────────────────────────────────────────────────┘
```

## What it does

- **Browse & pick** worksheets (editable SQL) and repo scripts (reference source).
- **Edit the query** in a real editor and **execute** it.
- **Auto-connects to Snowflake via AWS** (PrivateLink); connection state shows on top.
- **Lands output to S3**, and you can **change the S3 output path** per run.
- **Clear errors**: full tracebacks + a heartbeat stream to the Console pane.
- **PAT stays in memory only** — entered per browser session, never written to disk,
  environment, Secrets Manager, CloudTrail, or logs.
- **Costs ~$0 idle**: on-demand task, no ALB, auto-stops after 30 min idle.

## Seeded test worksheets

| | worksheet | behaviour |
|---|---|---|
| ① | Connection check · NPI↔OSCAR sample (10 rows → S3) | **works now** (inline result → S3) |
| ② | NPI↔OSCAR FULL crosswalk (bulk COPY→GET) | **hangs** until the S3 endpoint (Path A) lands |

The ② worksheet is intentional — run it to see the dashboard surface a hang
(heartbeat + Cancel) rather than fail silently.

## Everyday commands

```bash
# start it + open the tunnel (then browse http://localhost:8080)
kion run -f npd_prod -- ./worksheet/aws/launch.sh

# stop it → cost back to $0
kion run -f npd_prod -- ./worksheet/aws/stop.sh
```

First-time setup (build image, roles, task def, one SG rule): see
[`aws/DEPLOY.md`](aws/DEPLOY.md).

## Run the UI locally (no Snowflake, no data — just to see the interface)

```bash
python3 -m venv .wsvenv && ./.wsvenv/bin/pip install -r worksheet/app/requirements.txt
SNOWFLAKE_ACCOUNT=cms-idr.privatelink SNOWFLAKE_ROLE=IDRSF_PAT_USER_P \
SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH SNOWFLAKE_USER=RHDM IDLE_SHUTDOWN_MINUTES=0 \
./.wsvenv/bin/python -m uvicorn server:app --app-dir worksheet/app --port 8099
# open http://localhost:8099  (Snowflake calls will fail off-VPN; the UI renders)
```

## Layout

```
worksheet/
  app/
    server.py            FastAPI: sessions (PAT in RAM), run orchestration, websocket
    engine.py            Snowflake connect (PAT from RAM) · inline + relay execution
    scripts_registry.py  seeded worksheets (works/hangs) + repo-script browser
    static/              index.html · app.js (Monaco) · style.css
    requirements.txt
  aws/
    Dockerfile           web image (uvicorn)
    ecs-task-definition.json.tmpl   on-demand task (0.5 vCPU / 1 GB, port 8080)
    iam-task-role-policy.json.tmpl  S3 write only (NO secretsmanager)
    render.sh · deploy.env.example
    launch.sh · stop.sh  the everyday commands
    DEPLOY.md
```
