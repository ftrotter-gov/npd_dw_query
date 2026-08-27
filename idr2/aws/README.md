# IDR2 AWS Orchestrator

Runs the entire IDR export unattended in **one process, with no polling and no
notebook**. Snowflake unloads each table to its **own internal user stage**, the
container pulls the file out over the existing connection, and the **container**
writes it to S3 with its **ECS task role**:

```
for each table in step1_tables_to_export.csv:
    change-check: COUNT(*) + MAX(IDR_UPDT_TS)   → skip if unchanged (Approach A)
    COPY INTO @~/<stub>.<ts>  FROM (SELECT * FROM <table>)   # SINGLE=FALSE, multi-part (default)
    GET  @~/<prefix>_N_N_N.csv → local scratch/parts  (over the connection)
    merge parts → one <prefix>.csv              (reconciled merge, validated)
    boto3 upload    → S3                         (task role / local AWS creds — not Snowflake)
    validate size, then REMOVE each @~/ part
    record watermark
```

> **Where it runs today:** the dev VPC has **no Snowflake PrivateLink endpoint**
> yet (a networking request is filed), so the Fargate path can't reach Snowflake.
> The **laptop reaches Snowflake over VPN today**, so run it there for now — see
> [Run on the laptop (interim)](#run-on-the-laptop-interim-until-privatelink-lands).
> Flipping to Fargate later is an **env-only** change, no code edit.

## Why the relay (and not Snowflake → S3 directly)

Writing straight from Snowflake to S3 needs a **storage integration**, and the
export role `<SNOWFLAKE_ROLE>` **cannot create one** (`CREATE INTEGRATION` is not
granted, and none exists to grant `USAGE` on). Rather than block on a governance
request, the container does the S3 write:

- Snowflake only ever writes to its **internal** user stage `@~/` — no outbound
  access to the external bucket is required, which suits the locked-down,
  PrivateLink-only IDR account.
- The **ECS task role** (or, on the laptop, your Kion profile) holds the AWS
  credentials and does the `PutObject`.
- **Multi-file unload (`SINGLE = FALSE`) is the default**, so a table of *any*
  size works through one code path: Snowflake writes `<prefix>_N_N_N.csv` parts,
  the container GETs them all and merges them back into a single `<prefix>.csv`
  (reconciled + validated) before upload. `EXPORT_SINGLE_FILE=1` opts into the
  old one-file `SINGLE=TRUE` fast path for known-small tables. Only one table's
  files are on disk at a time.

## Why this replaces the old flow

| Old (two machines, manual, polling)           | New (this script)                          |
|-----------------------------------------------|--------------------------------------------|
| Notebook `COPY INTO @~/`, waits for laptop    | `COPY INTO @~/` then the script GETs it    |
| Laptop `snowsql GET` / 5-min poll loop        | one process, no handshake, no polling      |
| `snowflake_csv_merge.py` run as a manual step | same merge, called **inline** after GET    |
| `aws s3 cp` from a laptop                      | `boto3` from the task role / Kion profile  |
| `REMOVE @~/` handshake, `QUIT_AFTER_HOURS`    | `REMOVE` is just cleanup after upload      |
| re-export everything every time               | **skip unchanged tables** (Approach A)     |
| `externalbrowser` SSO only                     | **PAT** (headless) **or** SSO (laptop)     |

## Freshness — Approach A (full snapshot, only when changed)

Downstream needs a **complete** file each run, so we never write deltas. Before
each table we ask Snowflake a cheap change-signal — `COUNT(*)` plus
`MAX(IDR_UPDT_TS)` — and compare it to the signature stored from the last
successful export (`_watermarks.json` in the S3 prefix):

- **unchanged** and the previous file is still in S3 → **skip**, leave the
  existing complete file in place.
- **changed** → full `SELECT *` export, then record the new signature.

`IDR_UPDT_TS` is present in all IDR provider-enrollment views and moves on both
inserts and in-place updates, so it's set as a fixed `WATERMARK_COLUMN`. If it's
ever unset, the script auto-discovers a timestamp column; if none is found it
**always exports** (never skips a full snapshot on a guess).

## Manual / targeted runs

Both work from the AWS console ("Run task", see below) or locally, via env vars:

| Variable | Effect |
|---|---|
| `FORCE_EXPORT=1` | export everything, ignore the skip logic (e.g. first run / full refresh) |
| `ONLY_TABLES=npi_hstry,reasgnmt` | only tables whose full name or stub contains one of these substrings |

## Prerequisites

1. **Snowflake auth** for role `<SNOWFLAKE_ROLE>` (which can read the IDR views
   and use the `@~/` user stage). Two options:
   - **PAT** (preferred; works headless on Fargate *and* on the laptop over VPN).
     One is already stored in the CMS dev account's **Secrets Manager** as
     `idr2/snowflake-pat` — point `SNOWFLAKE_PAT_SECRET_ID=idr2/snowflake-pat`
     at it (the orchestrator reads it at runtime with your AWS creds; never bake
     it into the image or copy it to disk). PATs **expire** (max 1 year) — rotate
     the secret in place when it lapses.
   - **Browser SSO** (`SNOWFLAKE_AUTHENTICATOR=externalbrowser`) — laptop only,
     interactive. Use it as the fallback when the PAT has expired.

2. **No Snowflake-side S3 setup.** There is intentionally **no** storage
   integration or external stage — the container writes to S3 itself. All the S3
   permission lives in the ECS **task role** (see `iam-task-role-policy.json`).

3. **Network placement.** The account is `<SNOWFLAKE_ACCOUNT>` — reachable only
   over AWS PrivateLink. The container must run in the VPC/subnets that have the
   IDR PrivateLink endpoint (the CMS AWS account that also hosts the S3 bucket).

## Configuration (environment variables)

| Variable | Required | Notes |
|---|---|---|
| `SNOWFLAKE_ACCOUNT` | ✅ | e.g. `<SNOWFLAKE_ACCOUNT>` |
| `SNOWFLAKE_USER` | ✅ | e.g. `<SNOWFLAKE_USER>` |
| `SNOWFLAKE_WAREHOUSE` | ✅ | e.g. `<SNOWFLAKE_WAREHOUSE>` |
| `S3_BUCKET` | ✅ | `s3://<S3_BUCKET>/idr_bulk/` |
| `SNOWFLAKE_ROLE` | – | `<SNOWFLAKE_ROLE>` |
| `WATERMARK_COLUMN` | – | `IDR_UPDT_TS` (set in the task def) |
| `SCRATCH_DIR` | – | defaults to an auto temp dir on the ECS ephemeral disk |
| `SNOWFLAKE_DATABASE` / `SNOWFLAKE_SCHEMA` | – | optional session defaults |
| `TABLES_CSV` | – | defaults to `idr2/step1_tables_to_export.csv` |
| `FORCE_EXPORT` | – | `1` = export all, ignore skip |
| `ONLY_TABLES` | – | comma-separated name/stub filter |
| `EXPORT_SINGLE_FILE` | – | `1` = old `SINGLE=TRUE` one-file fast path (fails >5 GB); default off = multi-file |
| `MAX_FILE_SIZE` | – | per-part byte cap for multi-file (default `4000000000`) |
| `DEEP_VALIDATE_OFF` | – | `1` = skip the merge's logical-record reconciliation (faster, less safe) |

**Auth** — provide one (SSO wins if set; otherwise PAT — **local laptop first, then AWS**; checked in this order):

| Variable | Use |
|---|---|
| `SNOWFLAKE_AUTHENTICATOR=externalbrowser` | interactive browser SSO — **laptop only**; wins even if a PAT is also set |
| `SNOWFLAKE_PAT` (or `SNOWFLAKE_PASSWORD`) | **local PAT (1st)** — inline env |
| `SNOWFLAKE_PAT_FILE` | **local PAT (2nd)** — path to a token file |
| `~/.config/idr2/snowflake_pat` | **local PAT (3rd)** — default token file, picked up automatically |
| `SNOWFLAKE_PAT_SECRET_ID` | **AWS fallback** — PAT from Secrets Manager id/ARN (`idr2/snowflake-pat` exists) |
| `SNOWFLAKE_PRIVATE_KEY_SECRET_ID` | key-pair fallback: PEM from Secrets Manager |
| `SNOWFLAKE_PRIVATE_KEY` | key-pair fallback: inline PEM |
| `SNOWFLAKE_PRIVATE_KEY_PATH` | key-pair fallback: `.p8` file |
| `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` | if the key is encrypted |

## Run on the laptop (interim, until PrivateLink lands)

The same `orchestrator.py` runs on the laptop over the existing CMS VPN while the
dev VPC's Snowflake PrivateLink endpoint is being provisioned. **Snowflake auth =
a local PAT (`~/.config/idr2/snowflake_pat`), falling back to the PAT in Secrets
Manager, or browser SSO**; **S3 auth = your Kion profile**. No code differs from
the eventual Fargate run — only the env.

```bash
pip install -r idr2/aws/requirements.txt

# Snowflake via the local PAT at ~/.config/idr2/snowflake_pat (picked up
# automatically — no PAT env var needed):
AWS_PROFILE=<AWS_PROFILE> AWS_REGION=us-east-1 \
SNOWFLAKE_ACCOUNT=<SNOWFLAKE_ACCOUNT> \
SNOWFLAKE_USER=<SNOWFLAKE_USER> \
SNOWFLAKE_ROLE=<SNOWFLAKE_ROLE> \
SNOWFLAKE_WAREHOUSE=<SNOWFLAKE_WAREHOUSE> \
S3_BUCKET=s3://<S3_BUCKET>/idr_bulk/ \
WATERMARK_COLUMN=IDR_UPDT_TS \
ONLY_TABLES=npi_hstry FORCE_EXPORT=1 \
python3 idr2/aws/orchestrator.py

# No local PAT? Add SNOWFLAKE_PAT_SECRET_ID=idr2/snowflake-pat to pull it from
# Secrets Manager instead (read at runtime with your AWS creds — not copied to disk).
```

If the PAT has **expired**, fall back to browser SSO (one popup for the whole run):

```bash
AWS_PROFILE=<AWS_PROFILE> AWS_REGION=us-east-1 \
SNOWFLAKE_AUTHENTICATOR=externalbrowser \
SNOWFLAKE_ACCOUNT=<SNOWFLAKE_ACCOUNT> SNOWFLAKE_USER=<SNOWFLAKE_USER> \
SNOWFLAKE_ROLE=<SNOWFLAKE_ROLE> SNOWFLAKE_WAREHOUSE=<SNOWFLAKE_WAREHOUSE> \
S3_BUCKET=s3://<S3_BUCKET>/idr_bulk/ WATERMARK_COLUMN=IDR_UPDT_TS \
ONLY_TABLES=npi_hstry FORCE_EXPORT=1 \
python3 idr2/aws/orchestrator.py
```

The GET + merge steps write to local disk, so run where you have VPN reach to
Snowflake and scratch space for **≈2× the largest table** (parts + merged copy;
set `SCRATCH_DIR` to a roomy volume). Exit code is `0` if all tables
succeeded/skipped/were empty, `1` if any failed.

**Flip to Fargate later:** keep `SNOWFLAKE_PAT_SECRET_ID`, drop
`SNOWFLAKE_AUTHENTICATOR`, and place the task in the PrivateLink subnets — no code
change.

> **Any size handled:** multi-file (`SINGLE=FALSE`) is the default, so tables over
> the 5 GB single-file cap export as parts and are merged back to one CSV. Use
> `EXPORT_SINGLE_FILE=1` only for known-small tables (it fails past 5 GB).

## Deploy on AWS — weekly cron

Lambda is **not** used: a full run issues ~30 `COPY`/`GET`/upload cycles and
waits on Snowflake compute, which routinely exceeds Lambda's hard **15-minute**
timeout (with no partial-safety). Fargate has no such cap.

**Full step-by-step CLI runbook: [`DEPLOY.md`](DEPLOY.md).** The short version:

Config is not hard-coded — your account / region / network live in a git-ignored
`deploy.env`, and the AWS JSON is generated from `*.json.tmpl` templates:

```bash
cp idr2/aws/deploy.env.example idr2/aws/deploy.env   # fill in YOUR values
./idr2/aws/render.sh                                  # → idr2/aws/rendered/*.json (git-ignored)
```

| Committed template | Renders to | What it is |
|---|---|---|
| `ecs-task-definition.json.tmpl` | `rendered/ecs-task-definition.json` | Fargate task def (env, log group, roles, 50 GiB ephemeral) |
| `iam-task-role-policy.json.tmpl` | `rendered/iam-task-role-policy.json` | task-role policy — S3 write + read the PAT secret |
| `iam-scheduler-*.json.tmpl` | `rendered/iam-scheduler-*.json` | scheduler role trust + `RunTask`/`PassRole` |
| `eventbridge-schedule.json.tmpl` | `rendered/eventbridge-schedule.json` | weekly EventBridge Scheduler → ECS `RunTask` |
| `iam-ecs-trust-policy.json` | copied as-is | ECS task/execution role trust |

Then, with `deploy.env` sourced (`set -a; . idr2/aws/deploy.env; set +a`): store
the PAT → build/push image → create the three roles → log group → cluster →
`register-task-definition` → smoke test → `create-schedule`. Commands in
`DEPLOY.md`. Schedule fires `cron(23 6 ? * SUN *)` UTC; logs → `/ecs/idr2-orchestrator`.

### Ephemeral storage

The GET lands one table's **parts** on the task's disk and the merge writes a
combined copy alongside them, so budget **≈2× the largest table**. The task def
sets **50 GiB** ephemeral storage (Fargate default 20, max 200). Only one table
is on disk at a time — bump it in the template if your largest table needs more.

### Run it manually from the browser

Any time, without waiting for the schedule:

1. **ECS console → Clusters → your cluster → Run task.**
2. Pick the same **task definition**, launch type **Fargate**, and the
   PrivateLink subnets + security group.
3. (Optional) under **Container overrides → Environment variables**, add
   `FORCE_EXPORT=1` for a full refresh, or `ONLY_TABLES=…` to target specific
   tables.
4. **Run** — output streams to the same CloudWatch log group.

## Notes

- **Old snapshots accumulate.** Each export writes a new timestamped file and
  doesn't delete prior ones; downstream picks the most recent by prefix. Add an
  S3 lifecycle rule (or a cleanup step) if you want to prune old versions.
- **Watermarks** live at `<prefix>/_watermarks.json` and are rewritten every run
  (even on partial/crashed runs), so completed tables skip next time.
