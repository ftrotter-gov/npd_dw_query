# IDR2: Snowflake → S3 Export

Exports IDR tables from Snowflake to S3 as full CSV snapshots. The export runs
as **one unattended process** (`idr2/aws/orchestrator.py`) that has Snowflake
write each table's CSV **directly to S3** — no notebook, no laptop, no polling.

> **History note:** this used to be a two-machine handshake (a Snowflake
> notebook + a local laptop poller that did `GET`/merge/upload, coordinated by
> file-presence signalling). That flow — `cell1`/`cell2` and
> `local_laptop/step0,2,3,4` — has been **removed** and fully replaced by the
> orchestrator. See git history if you need the old scripts.

## Directory Layout

```
idr2/
  step1_tables_to_export.csv   ← EDIT THIS: the tables to export (db.schema.table, one per line)
  all_available_tables.csv     ← reference: all tables available in IDR

  aws/                         ← the current flow
    orchestrator.py            ← single-process Snowflake → S3 direct export
    README.md                  ← full config + AWS deploy (ECS/Fargate) + manual run
    requirements.txt

  snowflake/
    check_access.sql           ← standalone: verify role can read the IDR views
```

## How it works

For each table in `step1_tables_to_export.csv`, the orchestrator:

1. **Change-check (Approach A):** `COUNT(*)` + `MAX(<timestamp col>)`. If the
   signature matches the last run and the file is still in S3, **skip** the table
   (its existing complete file stays). Otherwise continue.
2. **Relay unload:** `COPY INTO @~/<file> FROM (SELECT * FROM <table>)` with
   `SINGLE = TRUE HEADER = TRUE` to Snowflake's internal user stage, then `GET`
   the file and upload it to S3 with the ECS task role. (No storage integration:
   the export role can't create one, so the container does the S3 write.)
3. **Validate** the uploaded object size and record the watermark in
   `<prefix>/_watermarks.json`.

Downstream always gets a **complete** file per table (no deltas).

## What do I run?

**Just `idr2/aws/orchestrator.py` — nothing else.** It is one self-contained
process that does the whole export (change-check → unload → GET → merge → S3) for
every table in `step1_tables_to_export.csv`. There are no other steps to run: the
old `cell1`/`cell2` notebook and `local_laptop/step0,2,3,4` scripts are legacy and
are **not** part of this flow. (`snowflake/check_access.sql` is an optional,
standalone sanity check that your role can read the IDR views.)

Before the first run you only need to:

1. `pip install -r idr2/aws/requirements.txt`
2. Edit `step1_tables_to_export.csv` to list the tables you want.
3. Have **Snowflake auth** (a local PAT — see below) and **AWS creds** for the S3
   write (your Kion/CloudTamer profile locally, or the ECS task role on Fargate).

## Quick start

The Snowflake PAT is read from `~/.config/idr2/snowflake_pat` automatically, so no
token env var is needed on the laptop:

```bash
pip install -r idr2/aws/requirements.txt

AWS_PROFILE=<your Kion STAK profile> AWS_REGION=us-east-1 \
SNOWFLAKE_ACCOUNT=<SNOWFLAKE_ACCOUNT> \
SNOWFLAKE_USER=<SNOWFLAKE_USER> \
SNOWFLAKE_ROLE=<SNOWFLAKE_ROLE> \
SNOWFLAKE_WAREHOUSE=<SNOWFLAKE_WAREHOUSE> \
S3_BUCKET=s3://<S3_BUCKET>/idr_bulk/ \
WATERMARK_COLUMN=IDR_UPDT_TS \
python3 idr2/aws/orchestrator.py
```

Choose tables by editing `step1_tables_to_export.csv`, or narrow a run with
`ONLY_TABLES=…`; force a full refresh with `FORCE_EXPORT=1`.

### Snowflake auth (PAT: local first, then AWS)

The orchestrator resolves the PAT in this order and uses the first one it finds:

1. `SNOWFLAKE_PAT` (or `SNOWFLAKE_PASSWORD`) — inline env
2. `SNOWFLAKE_PAT_FILE` — path to a file holding just the token
3. `~/.config/idr2/snowflake_pat` — **default local file (auto-detected)**
4. `SNOWFLAKE_PAT_SECRET_ID` — AWS Secrets Manager (`idr2/snowflake-pat`), the fallback

If none of these is set, the run exits with a message telling you to populate a
local PAT or the AWS secret. To force interactive browser SSO instead (laptop
only), set `SNOWFLAKE_AUTHENTICATOR=externalbrowser`. Keep the local PAT file
private: `chmod 600 ~/.config/idr2/snowflake_pat` (it lives outside the repo).

**For all configuration, auth options, the storage-integration/stage setup, and
AWS deployment (ECS Fargate weekly cron + manual "Run task"), see
[`aws/README.md`](aws/README.md).**
