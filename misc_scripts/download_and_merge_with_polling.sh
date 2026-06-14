#!/bin/bash
# 
# Parallel Snowflake CSV Download with Polling
# 
# This script coordinates with the Snowflake export loop to download exported CSV files.
# It monitors the Snowflake stage (@~/) for new files and downloads them automatically.
# Files are deleted from Snowflake after successful download.
# Process stops after configurable timeout with no activity.
#
# Configuration: Loads settings from idr2/.env
# Logging: Writes to download_progress.log in the download directory
#
# Usage:
#   ./download_and_merge_with_polling.sh
#

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
IDR2_DIR="$PROJECT_DIR/idr2"

# Source .env configuration
if [ ! -f "$IDR2_DIR/.env" ]; then
    echo "ERROR: .env file not found at $IDR2_DIR/.env"
    echo "Please copy example.env to .env and configure it first:"
    echo "  cd $IDR2_DIR"
    echo "  cp example.env .env"
    echo "  nano .env"
    exit 1
fi

# Load configuration
set -a
source "$IDR2_DIR/.env"
set +a

# Expand tilde in paths
DOWNLOAD_DIR="${DOWNLOAD_DIRECTORY/#\~/$HOME}"
POLLING_INTERVAL=$((POLLING_INTERVAL_MINUTES * 60))  # Convert to seconds
TIMEOUT_SECONDS=$((QUIT_AFTER_HOURS * 3600))         # Convert to seconds

# Verify download directory exists
if [ ! -d "$DOWNLOAD_DIR" ]; then
    echo "ERROR: Download directory does not exist: $DOWNLOAD_DIR"
    echo "Please create it first:"
    echo "  mkdir -p \"$DOWNLOAD_DIR\""
    exit 1
fi

# Log file
LOG_FILE="$DOWNLOAD_DIR/download_progress.log"

# Initialize logging
log() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1" | tee -a "$LOG_FILE"
}

# Clean up old CSVs before starting
log "====== STARTING DOWNLOAD & MERGE PROCESS ======"
log "Configuration loaded from: $IDR2_DIR/.env"
log "Download directory: $DOWNLOAD_DIR"
log "Polling interval: $POLLING_INTERVAL_MINUTES minutes"
log "Timeout: $QUIT_AFTER_HOURS hours"
log "Snowflake config: $SNOWFLAKE_CONFIG"

# Delete previous run files
log "Cleaning up old CSV files..."
rm -f "$DOWNLOAD_DIR"/*.csv
log "Cleanup complete"

# Track timing for timeout
START_TIME=$(date +%s)
LAST_ACTIVITY_TIME=$START_TIME
FIRST_FILE_TIME=""

# Verify snowsql is available
if [ ! -f "$SNOWSQL_PATH" ]; then
    log "ERROR: snowsql not found at $SNOWSQL_PATH"
    log "Please update SNOWSQL_PATH in $IDR2_DIR/.env"
    exit 1
fi

log "snowsql found at: $SNOWSQL_PATH"

# Function to list files in Snowflake stage
list_stage_files() {
    "$SNOWSQL_PATH" -c "$SNOWFLAKE_CONFIG" -q "LIST @~/ PATTERN='.*\.csv';" 2>/dev/null | grep -E "\.csv" | awk '{print $1}' || echo ""
}

# Function to download a file from Snowflake
download_file() {
    local file="$1"
    local filename=$(basename "$file")
    
    log "Downloading: $filename"
    
    pushd "$DOWNLOAD_DIR" > /dev/null
    
    if "$SNOWSQL_PATH" -c "$SNOWFLAKE_CONFIG" -q "GET @~/$filename file://. PATTERN='$filename';" > /dev/null 2>&1; then
        log "✓ Downloaded: $filename"
        
        # Delete from Snowflake after successful download
        if "$SNOWSQL_PATH" -c "$SNOWFLAKE_CONFIG" -q "REMOVE @~/$filename;" > /dev/null 2>&1; then
            log "✓ Deleted from stage: $filename"
            LAST_ACTIVITY_TIME=$(date +%s)
            return 0
        else
            log "✗ Failed to delete from stage: $filename"
            return 1
        fi
    else
        log "✗ Failed to download: $filename"
        return 1
    fi
    
    popd > /dev/null
}

# Main polling loop
log "Starting polling loop..."

while true; do
    CURRENT_TIME=$(date +%s)
    TIME_SINCE_START=$((CURRENT_TIME - START_TIME))
    TIME_SINCE_ACTIVITY=$((CURRENT_TIME - LAST_ACTIVITY_TIME))
    
    HOURS_SINCE_START=$((TIME_SINCE_START / 3600))
    MINS_SINCE_START=$(((TIME_SINCE_START % 3600) / 60))
    
    HOURS_SINCE_ACTIVITY=$((TIME_SINCE_ACTIVITY / 3600))
    MINS_SINCE_ACTIVITY=$(((TIME_SINCE_ACTIVITY % 3600) / 60))
    
    # Check timeout
    if [ $TIME_SINCE_ACTIVITY -gt $TIMEOUT_SECONDS ]; then
        log "====== TIMEOUT REACHED ======"
        log "No download activity for $QUIT_AFTER_HOURS hours"
        log "Total elapsed: ${HOURS_SINCE_START}h ${MINS_SINCE_START}m"
        log "Stopping polling loop"
        break
    fi
    
    # List files in stage
    log "Checking Snowflake stage (${HOURS_SINCE_START}h ${MINS_SINCE_START}m elapsed, ${HOURS_SINCE_ACTIVITY}h ${MINS_SINCE_ACTIVITY}m since last activity)..."
    
    STAGE_FILES=$(list_stage_files)
    
    if [ -n "$STAGE_FILES" ]; then
        FILE_COUNT=$(echo "$STAGE_FILES" | wc -l)
        log "Found $FILE_COUNT file(s) in stage"
        
        # Download each file
        while IFS= read -r file; do
            if [ -n "$file" ]; then
                download_file "$file"
            fi
        done <<< "$STAGE_FILES"
        
        LAST_ACTIVITY_TIME=$(date +%s)
        
        # Mark time of first file
        if [ -z "$FIRST_FILE_TIME" ]; then
            FIRST_FILE_TIME=$(date '+%Y-%m-%d %H:%M:%S')
            log "First file downloaded at: $FIRST_FILE_TIME"
        fi
    else
        log "No new files found in stage"
        
        # Check if we've received at least one file and stage is now empty
        if [ -n "$FIRST_FILE_TIME" ]; then
            DOWNLOADED_FILES=$(find "$DOWNLOAD_DIR" -maxdepth 1 -name "*.csv" -type f | wc -l)
            if [ $DOWNLOADED_FILES -gt 0 ]; then
                log "✓ All files downloaded ($DOWNLOADED_FILES total)"
                LAST_ACTIVITY_TIME=$(date +%s)
            fi
        fi
    fi
    
    log "Waiting $POLLING_INTERVAL_MINUTES minutes before next check..."
    
    # Sleep for polling interval, checking for interrupt
    sleep "$POLLING_INTERVAL"
done

# Merge downloaded files
log "====== MERGING CSV FILES ======"

DOWNLOADED_FILES=$(find "$DOWNLOAD_DIR" -maxdepth 1 -name "*.csv" -type f | wc -l)

if [ $DOWNLOADED_FILES -eq 0 ]; then
    log "⚠ WARNING: No CSV files found to merge"
    log "Check that Snowflake exports are running correctly"
else
    log "Found $DOWNLOADED_FILES files to merge"
    
    if python3 "$SCRIPT_DIR/snowflake_csv_merge.py" "$DOWNLOAD_DIR" --output-dir "$DOWNLOAD_DIR/.."; then
        log "✓ CSV merge completed successfully"
    else
        log "✗ CSV merge failed"
        log "Attempting manual cleanup..."
    fi
fi

# Final summary
FINAL_TIME=$(date +%s)
TOTAL_ELAPSED=$((FINAL_TIME - START_TIME))
TOTAL_HOURS=$((TOTAL_ELAPSED / 3600))
TOTAL_MINS=$(((TOTAL_ELAPSED % 3600) / 60))
TOTAL_SECS=$((TOTAL_ELAPSED % 60))

log "====== PROCESS COMPLETE ======"
log "Total duration: ${TOTAL_HOURS}h ${TOTAL_MINS}m ${TOTAL_SECS}s"
log "Downloaded: $DOWNLOADED_FILES files"
log "Output directory: $DOWNLOAD_DIR"
log "Log file: $LOG_FILE"

# Verify snowsql config for manual checks
log ""
log "To manually check remaining files in Snowflake stage:"
log "  snowsql -c $SNOWFLAKE_CONFIG -q \"LIST @~/ PATTERN='*.csv';\""
log ""
log "To manually merge again if needed:"
log "  python3 $SCRIPT_DIR/snowflake_csv_merge.py $DOWNLOAD_DIR --output-dir $DOWNLOAD_DIR/.."
log ""
log "====== DONE ======"

# Exit successfully
exit 0
