g# IDR2: Parallel Snowflake Export & Download System

This system automates the export of multiple Snowflake tables and downloads them to your local machine without requiring manual intervention. It uses file presence/absence as a synchronization mechanism between the Snowflake exporter and the downloader.

## Architecture

The system consists of two main components running in parallel:

### 1. **Snowflake Side** (Notebook)
- Reads metadata about all tables to export
- Exports one CSV file at a time using COPY INTO
- Waits for each file to be downloaded (detected by its absence from the stage)
- Moves to the next file after confirmation
- Automatically stops after 2 hours of inactivity

### 2. **Downloader Side** (Your Machine)
- Continuously polls Snowflake stage for new CSV files
- Downloads new files to local directory
- Deletes downloaded files from Snowflake stage
- Merges all CSVs into consolidated output
- Automatically stops after 2 hours of inactivity

## Setup Instructions

### Prerequisites

- Python 3.8+
- Snowflake configured with snowsql (`/Applications/SnowSQL.app/Contents/MacOS/snowsql`)
- Directory created: `~/cms_data_downloads_possible_pii/idr_data/unmerged_csv_files/`

### Step 1: Configure Environment

```bash
cd idr2/

# Copy example configuration
cp example.env .env

# Edit .env with your settings
nano .env
```

**Configuration Options (.env):**
```
DOWNLOAD_DIRECTORY=~/cms_data_downloads_possible_pii/idr_data/unmerged_csv_files
POLLING_INTERVAL_MINUTES=5          # Check every 5 minutes (configurable)
QUIT_AFTER_HOURS=2                  # Stop after 2 hours with no activity
SNOWFLAKE_CONFIG=cms_idr            # From ~/.snowsql/config
SNOWSQL_PATH=/Applications/SnowSQL.app/Contents/MacOS/snowsql
```

### Step 2: Create List of Tables to Download

Edit `list_of_tables_to_download.csv` with the tables you want to export:

```csv
table_to_download
IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR
IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_HCIDEA
IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_HSTRY
```

Format: `database.schema.table` (one per line)

### Step 3: Generate Metadata

```bash
python3 metadata_generator.py
```

This reads `list_of_tables_to_download.csv` and generates `export_metadata.json` with all table information including:
- Explicit SELECT statements with all columns named (not SELECT *)
- Proper file naming stubs
- Version information

The metadata is now ready to use in the Snowflake notebook.

### Step 4: Start Downloader (Terminal 1)

```bash
cd misc_scripts/
./download_and_merge_with_polling.sh
```

The downloader will:
- Load configuration from `idr2/.env`
- Start polling for files every 5 minutes
- Download any new CSV files
- Delete them from Snowflake after successful download
- Continue until all files are downloaded or 2 hours elapse

### Step 5: Start Snowflake Exporter (Terminal 2)

In your Snowflake notebook:

1. Copy the entire contents of `snowflake_export_loop.py`
2. Paste into a Python cell
3. Update the `METADATA_JSON` with your table configuration (or load from the generated metadata)
4. Run the cell with: `main()`

The exporter will:
- Load metadata
- Export tables one at a time to `@~/` (Snowflake user stage)
- Wait 5 minutes between checks for download confirmation
- Move to next table once current file is deleted
- Stop after 2 hours with no activity

## File Naming Convention

Exported files follow this pattern:
```
{table_name_stub}.{version_number}.{timestamp}.csv
```

Example: `v2_mdcr_prvdr_idr_export.v01.2024_06_14_0130.csv`

Components:
- `table_name_stub`: Lowercase table name with "_idr_export" suffix
- `version_number`: Defaults to "v01"
- `timestamp`: Year_Month_Day_Hour+Minute (UTC)

## Monitoring Progress

### Snowflake Notebook Output
You'll see:
- Export start/finish messages
- File names being exported
- Polling messages while waiting
- Summary at end with success/failure counts

### Downloader Output
The downloader logs to:
- `download_progress.log` - Progress and activity
- Terminal - Real-time status messages

## Handling Issues

### Downloader Timeout
If downloader exits due to timeout (2 hours with no new files):
- Check Snowflake notebook for export errors
- Verify network connectivity
- Check `DOWNLOAD_DIRECTORY` permissions
- Increase `QUIT_AFTER_HOURS` in .env if needed

### Exporter Timeout
If exporter stops waiting for download:
- Check that downloader is still running
- Verify `DOWNLOAD_DIRECTORY` exists and is accessible
- Check Snowflake connection is still active
- Ensure `.env` file has correct paths

### Stuck Files in Snowflake Stage
If files remain in `@~/` after process completes:
```bash
# List files in stage
snowsql -c cms_idr -q "LIST @~/ PATTERN='*.csv';"

# Remove stuck files manually
snowsql -c cms_idr -q "REMOVE @~/ PATTERN='v2_mdcr_prvdr*.csv';"
```

## File Organization

```
idr2/
├── list_of_tables_to_download.csv   # Input: tables to export
├── export_metadata.json             # Generated: table metadata
├── example.env                      # Template for configuration
├── .env                            # Your configuration (not in git)
├── metadata_generator.py           # Script to generate metadata
├── snowflake_export_loop.py        # Notebook script for export
└── README.md                       # This file

misc_scripts/
├── download_and_merge_with_polling.sh  # Updated downloader
├── snowflake_csv_merge.py             # CSV merge utility
└── ... (other utilities)
```

## Performance Tuning

### Reduce Download Time
- Lower `POLLING_INTERVAL_MINUTES` to check more frequently (default: 5)
- Ensure network connection is stable
- Check Snowflake warehouse performance

### Increase Reliability
- Set `QUIT_AFTER_HOURS` higher if downloads are slow (default: 2)
- Monitor `download_progress.log` for patterns
- Test with a small subset of tables first

## Troubleshooting

### CSV Files Not Merging
The merger combines all downloaded CSVs into consolidated files. If this fails:
```bash
# Check if files were actually downloaded
ls -la ~/cms_data_downloads_possible_pii/idr_data/unmerged_csv_files/

# Manually merge if needed
python3 misc_scripts/snowflake_csv_merge.py ~/cms_data_downloads_possible_pii/idr_data/unmerged_csv_files/ --output-dir ~/cms_data_downloads_possible_pii/idr_data/
```

### Snowflake Stage Issues
```bash
# Verify you can access the stage
snowsql -c cms_idr -q "LIST @~/ LIMIT 1;"

# Check snowsql config
cat ~/.snowsql/config | grep -A 5 "cms_idr"
```

## Reference

- **IDROutputter**: Base class for exports (see `idr/IDROutputter.py`)
- **Original Downloader**: `misc_scripts/download_and_merge_all_snowflake_csv.sh`
- **Auto-Generated Exports**: Examples in `idr/mdcr_prvdr/v2_*.py`

## Support

For issues:
1. Check the README in main project directory
2. Review logs in `misc_scripts/download_progress.log`
3. Verify `.env` configuration
4. Test with `metadata_generator.py` first
5. Run Snowflake tests with a single table
