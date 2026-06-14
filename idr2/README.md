# IDR2: Parallel Snowflake Export & Download System

This system exports multiple Snowflake tables to your local machine and to S3,
coordinating between a Snowflake notebook and a local downloader that run in parallel.

## Directory Layout

```
idr2/
  step1_tables_to_export.csv        ← EDIT THIS: list the tables you want
  all_available_tables.csv          ← reference: all tables available to download

  example.env                       ← copy to .env and fill in your settings
  .env                              ← your local config (not in git)

  local_laptop/                     ← scripts that run on YOUR machine
    step2_generate_metadata.py      ← generates metadata from the table list
    step3_generate_snowflake_cell2.py ← generates the Snowflake Cell 2 script
    step4_download_merge_upload.py  ← polls Snowflake, downloads, merges, uploads to S3

  snowflake/                        ← scripts that run INSIDE Snowflake
    cell1_snowflake_export_classes.py ← paste into Cell 1 of your Snowflake notebook
    cell2_snowflake_export_notebook.py ← paste into Cell 2 (re-generate with step3)
```

---

## How It Works

The system uses file presence/absence as a synchronization signal:

1. **Snowflake** exports one table at a time to `@~/` (the Snowflake user stage)
2. **Your laptop** detects the new file, downloads it, merges part files, uploads to S3, then removes it from the stage
3. **Snowflake** sees the file is gone → exports the next table

Steps 4 and 5 below run **simultaneously in two separate terminals/windows**.

---

## Setup (one time)

### Step 0: Configure

```bash
cd idr2/
cp example.env .env
nano .env
```

Key settings in `.env`:

```ini
DOWNLOAD_DIRECTORY=~/cms_data_downloads_possible_pii/idr_data/unmerged_csv_files
SNOWFLAKE_CONFIG=cms_idr
SNOWSQL_PATH=/Applications/SnowSQL.app/Contents/MacOS/snowsql
S3_BUCKET=s3://your-bucket-name/idr_exports/
POLLING_INTERVAL_MINUTES=5
QUIT_AFTER_HOURS=2
```

---

## Running an Export (every time)

### Step 1: Choose tables

Edit `step1_tables_to_export.csv`:

```csv
table_to_download
IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR
IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA
```

Format: `database.schema.table` — one per line. See `all_available_tables.csv` for the full list.

### Step 2: Generate metadata

```bash
python3 idr2/local_laptop/step2_generate_metadata.py
```

Reads `step1_tables_to_export.csv` and produces `export_metadata.json` with SELECT statements for every column.

### Step 3: Generate the Snowflake Cell 2 script

```bash
python3 idr2/local_laptop/step3_generate_snowflake_cell2.py
```

Reads the metadata and writes `idr2/snowflake/cell2_snowflake_export_notebook.py` with all table metadata embedded directly (no external files needed inside Snowflake).

---

## ▶ Start BOTH of these in parallel

### Step 4 — Terminal 1 (your laptop)

```bash
python3 idr2/local_laptop/step4_download_merge_upload.py
```

This will:
- Poll the Snowflake stage every 5 minutes for new CSV files
- Download all part files
- Merge them into a single CSV
- Upload the merged CSV to S3
- Verify MD5 checksum and row count
- Remove the parts from the Snowflake stage (signals Snowflake to export the next table)
- Stop after 2 hours of no activity

### Step 5 — Terminal 2 (Snowflake notebook)

1. Open your Snowflake Python notebook
2. In **Cell 1**: paste the entire contents of `idr2/snowflake/cell1_snowflake_export_classes.py`
3. In **Cell 2**: paste the entire contents of `idr2/snowflake/cell2_snowflake_export_notebook.py`
4. Run **Cell 1** first (defines the classes)
5. Run **Cell 2** (starts the export loop)

The Snowflake notebook will:
- Export tables one at a time to `@~/`
- Wait until each file disappears from the stage (i.e., your laptop downloaded it)
- Move to the next table
- Stop after 2 hours of no activity

---

## Monitoring

### Laptop output
- Real-time status printed to terminal
- Full log written to `$DOWNLOAD_DIRECTORY/download_progress.log`

### Snowflake output
- Export start/finish messages per table
- Polling messages while waiting for download
- Summary at the end

---

## Resume / Restart

If step 4 was interrupted mid-run, **just restart it**:

```bash
python3 idr2/local_laptop/step4_download_merge_upload.py
```

On startup the script checks the download directory for pre-existing CSV files.
If any are found (from the interrupted run), it **merges and uploads them immediately**
before entering the polling loop — so no downloaded data is lost or re-downloaded.

---

## Troubleshooting

### Files stuck in Snowflake stage
```bash
# List
snowsql -c cms_idr -q "LIST @~/ PATTERN='*.csv';"

# Remove manually
snowsql -c cms_idr -q "REMOVE @~/ PATTERN='*.csv';"
```

### Downloader times out before Snowflake finishes
Increase `QUIT_AFTER_HOURS` in `.env` and restart step 4.

### CSV merge fails
```bash
# Manual merge
python3 misc_scripts/snowflake_csv_merge.py \
    ~/cms_data_downloads_possible_pii/idr_data/unmerged_csv_files/ \
    --output-dir ~/cms_data_downloads_possible_pii/idr_data/
```

### Regenerate Cell 2 after changing table list
Re-run steps 1–3, then replace Cell 2 content in your Snowflake notebook.
