"""
Snowflake Export Classes Library

Classes for parallel Snowflake export/download orchestration.
Paste this entire file into the FIRST cell of your Snowflake Python notebook.

Classes included:
  - ExportMetadata: Load and manage table metadata
  - SnowflakeExporter: Export a single table to stage
  - DownloadAreaWatcher: Monitor stage for file downloads
  - ExportLoop: Orchestrate the parallel export process
"""

import json
import time
from datetime import datetime, timedelta


class ExportMetadata:
    """Load and manage metadata about tables to export."""
    
    def __init__(self, metadata_json):
        """
        Initialize metadata from JSON content or file.
        
        Args:
            metadata_json: Either a dict (parsed JSON) or path string to JSON file
        """
        if isinstance(metadata_json, dict):
            self.metadata = metadata_json
        else:
            # Try to load from file path
            try:
                with open(metadata_json, 'r') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                print(f"Error loading metadata: {e}")
                raise
        
        self.tables = self.metadata.get('tables', [])
        print(f"Loaded metadata for {len(self.tables)} tables")
    
    def get_tables(self):
        """Get list of all tables to export."""
        return self.tables
    
    def get_table_index(self, table_name):
        """Get index of a table by name."""
        for i, table in enumerate(self.tables):
            if table.get('full_table_name') == table_name:
                return i
        return -1


class SnowflakeExporter:
    """Handle exporting a single table from Snowflake."""
    
    def __init__(self, session, table_metadata):
        """
        Initialize exporter for a specific table.
        
        Args:
            session: Active Snowflake session
            table_metadata: Dict with table metadata
        """
        self.session = session
        self.table_metadata = table_metadata
        self.full_table_name = table_metadata['full_table_name']
        self.file_name_stub = table_metadata['file_name_stub']
        self.version_number = table_metadata['version_number']
    
    def generate_select_query(self):
        """
        Generate SELECT query following IDROutputter pattern.
        
        Returns:
            str: SELECT query string
        """
        # Use the pre-generated select query from metadata
        # Or build one dynamically
        if 'select_query' in self.table_metadata:
            return self.table_metadata['select_query']
        
        # Fallback: generate SELECT * for the table
        return f"SELECT * FROM {self.full_table_name}"
    
    def export_table(self):
        """
        Export table to Snowflake stage following IDROutputter pattern.
        
        Returns:
            dict: Export result with file name and status
        """
        try:
            select_query = self.generate_select_query()
            
            # Generate filename with timestamp
            ts = datetime.now().strftime("%Y_%m_%d_%H%M")
            file_name = f"@~/{self.file_name_stub}.{self.version_number}.{ts}.csv"
            
            # Build COPY INTO command following IDROutputter pattern
            copy_sql = f"""
COPY INTO {file_name}
FROM (
{select_query}
) FILE_FORMAT = (
  TYPE = CSV
  FIELD_DELIMITER = ','
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  COMPRESSION = NONE
)
HEADER = TRUE
OVERWRITE = TRUE;
"""
            
            print(f"\n{'='*60}")
            print(f"Exporting: {self.full_table_name}")
            print(f"File: {file_name}")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}")
            
            # Execute the export
            result = self.session.sql(copy_sql).collect()

            # COPY INTO <location> returns one row with ROWS_UNLOADED,
            # INPUT_BYTES, OUTPUT_BYTES.  If the source table is empty,
            # ROWS_UNLOADED == 0 and NO file is written to the stage.
            # We must detect this and skip the download-wait, otherwise
            # wait_for_stage_empty Phase 1 will block for 5 minutes.
            rows_unloaded = -1  # unknown / non-parseable
            if result:
                try:
                    rows_unloaded = int(result[0]['ROWS_UNLOADED'])
                except (KeyError, TypeError):
                    try:
                        rows_unloaded = int(result[0][0])
                    except (IndexError, TypeError):
                        pass

            if rows_unloaded == 0:
                print(f"⊘ Table is empty – 0 rows exported, no file written to stage")
                return {
                    'status': 'EMPTY',
                    'table': self.full_table_name,
                    'rows_unloaded': 0,
                }

            print(f"Export completed for {self.full_table_name}"
                  + (f" ({rows_unloaded:,} rows)" if rows_unloaded > 0 else ""))

            return {
                'status': 'SUCCESS',
                'table': self.full_table_name,
                'file_name': file_name,
                'file_name_stub': self.file_name_stub,
                'timestamp': ts,
                'rows_unloaded': rows_unloaded,
                'result': str(result) if result else 'OK'
            }
        
        except Exception as e:
            print(f"ERROR exporting {self.full_table_name}: {str(e)}")
            return {
                'status': 'FAILED',
                'table': self.full_table_name,
                'error': str(e)
            }


class DownloadAreaWatcher:
    """Monitor the Snowflake stage for download activity."""
    
    def __init__(self, session, polling_interval_minutes=5, quit_after_hours=2):
        """
        Initialize the watcher.
        
        Args:
            session: Active Snowflake session
            polling_interval_minutes: How often to check for changes (default 5)
            quit_after_hours: Give up after this many hours of no activity (default 2)
        """
        self.session = session
        self.polling_interval = polling_interval_minutes * 60  # Convert to seconds
        self.quit_after = quit_after_hours * 3600  # Convert to seconds
        self.last_change_time = datetime.now()
        self.start_time = datetime.now()
    
    def list_files_in_stage(self):
        """
        List all CSV files currently in the Snowflake user stage.

        Snowflake's LIST @~/ returns rows whose first column is the full stage
        path, e.g. ``@~/myfile.csv`` or ``stage://~/username/myfile.csv``.
        We normalise by stripping any leading path components so the result is
        just a list of bare file names ending in ``.csv``.

        Returns:
            list[str]: Bare file names (e.g. ``["table.v01.ts.csv"]``)
        """
        try:
            result = self.session.sql("LIST @~/").collect()
            files = []
            for row in result:
                raw = str(row[0]) if row else ""
                # Keep only the final path component
                bare = raw.split("/")[-1]
                if bare.endswith(".csv"):
                    files.append(bare)
            return files
        except Exception as e:
            print(f"Error listing stage files: {e}")
            return []

    def wait_for_stage_empty(self):
        """
        Wait until the Snowflake user stage contains NO CSV files.

        This is the correct gate between exports: the laptop downloads every
        CSV file from the stage and deletes it; only when the stage is empty
        is it safe to push the next table.

        Two-phase approach:
          Phase 1 – Confirm the exported file(s) actually appear in LIST @~/.
                    COPY INTO can return before the file is visible in the
                    stage directory listing (propagation lag).  We poll every
                    10 s for up to 5 minutes.  If the file never appears we
                    log a warning and skip straight to Phase 2 (belt-and-
                    suspenders: the laptop may have already grabbed it).
          Phase 2 – Wait until the stage has ZERO CSV files.  The laptop
                    signals completion by removing every file it downloads.

        Returns:
            bool: True  – stage is now empty (safe to export next table)
                  False – timed out waiting
        """
        print(f"\nWaiting for stage to empty...")
        print(f"Polling every {self.polling_interval // 60} min | "
              f"Timeout {self.quit_after // 3600} h with no change")

        # ── Phase 1: confirm file appears in stage ───────────────────────────
        # After COPY INTO returns, Snowflake may take a few seconds to make
        # the file visible in LIST @~/. Without this check we immediately see
        # 0 files and declare "stage empty" — a false negative.
        APPEAR_TIMEOUT_S  = 300   # give up confirming after 5 minutes
        APPEAR_POLL_S     = 10    # re-check every 10 seconds
        appear_start      = datetime.now()

        print("  Phase 1: confirming export is visible in stage listing...")
        while True:
            files = self.list_files_in_stage()
            if len(files) > 0:
                print(f"  ✓ {len(files)} file(s) confirmed visible in stage — "
                      f"entering download-wait loop")
                self.last_change_time = datetime.now()
                break
            elapsed_appear = (datetime.now() - appear_start).total_seconds()
            if elapsed_appear > APPEAR_TIMEOUT_S:
                print(f"  ⚠ File never appeared in stage listing after "
                      f"{APPEAR_TIMEOUT_S}s.  Proceeding to Phase 2 anyway "
                      f"(laptop may have already downloaded it).")
                break
            print(f"  Waiting for file to appear... ({elapsed_appear:.0f}s)")
            time.sleep(APPEAR_POLL_S)

        # ── Phase 2: wait for stage to become empty ───────────────────────────
        wait_start = datetime.now()

        while True:
            elapsed_since_change = (
                datetime.now() - self.last_change_time
            ).total_seconds()
            elapsed_since_start = (
                datetime.now() - self.start_time
            ).total_seconds()

            # Hard timeout: no file was removed for quit_after hours
            if elapsed_since_change > self.quit_after:
                print(
                    f"\nTIMEOUT: no download activity for "
                    f"{self.quit_after // 3600} h "
                    f"(total elapsed {elapsed_since_start // 3600:.1f} h)"
                )
                return False

            files = self.list_files_in_stage()

            if len(files) == 0:
                elapsed = (datetime.now() - wait_start).total_seconds()
                print(
                    f"✓ Stage empty – download complete! "
                    f"({elapsed // 60:.0f} min {elapsed % 60:.0f} sec)"
                )
                self.last_change_time = datetime.now()
                return True

            # Still files present – report count only (not the full list)
            sample = files[0] if files else ""
            print(
                f"  Stage has {len(files)} file(s)  "
                f"(e.g. {sample})  "
                f"| waited {elapsed_since_change // 60:.0f} min so far – "
                f"rechecking in 1 min"
            )
            time.sleep(60)  # poll every 1 minute regardless of POLLING_INTERVAL

    def wait_for_download(self, exported_file_name):
        """
        Back-compat wrapper – delegates to wait_for_stage_empty().

        The original per-file check had a name-format mismatch that caused it
        to return True immediately without actually waiting.  Waiting for the
        whole stage to be empty is the correct semantic anyway: the laptop must
        download (and delete) every CSV before we push the next one.
        """
        return self.wait_for_stage_empty()


class ExportLoop:
    """Main orchestrator for the parallel export/download process."""
    
    def __init__(self, session, metadata, polling_interval_minutes=5, quit_after_hours=2):
        """
        Initialize the export loop.
        
        Args:
            session: Active Snowflake session
            metadata: ExportMetadata instance
            polling_interval_minutes: Polling interval from config
            quit_after_hours: Timeout from config
        """
        self.session = session
        self.metadata = metadata
        self.polling_interval = polling_interval_minutes
        self.quit_after = quit_after_hours
        self.watcher = DownloadAreaWatcher(session, polling_interval_minutes, quit_after_hours)
        self.completed_tables = []
        self.failed_tables = []
        self.skipped_tables = []
    
    def run(self):
        """
        Main loop: export tables one at a time, waiting for download after each.
        """
        tables = self.metadata.get_tables()
        total = len(tables)
        
        print("\n" + "="*60)
        print("SNOWFLAKE PARALLEL EXPORT LOOP")
        print("="*60)
        print(f"Starting export loop: {total} tables to download")
        print(f"Polling interval: {self.polling_interval} minutes")
        print(f"Timeout: {self.quit_after} hours")
        print("="*60)

        start_time = datetime.now()

        # ── Pre-flight: ensure stage is empty before we start ───────────────
        existing = self.watcher.list_files_in_stage()
        if existing:
            print(f"\n⚠ Stage already has {len(existing)} file(s) from a previous run.")
            print("  Waiting for them to be downloaded before starting exports...")
            if not self.watcher.wait_for_stage_empty():
                print("✗ Stage never emptied – aborting export loop.")
                return
        else:
            print("\n✓ Stage is empty – ready to begin.")

        for idx, table_metadata in enumerate(tables, 1):
            print(f"\n[{idx}/{total}] Processing table: {table_metadata['full_table_name']}")
            
            try:
                # Export the table
                exporter = SnowflakeExporter(self.session, table_metadata)
                export_result = exporter.export_table()
                
                status = export_result['status']

                if status == 'FAILED':
                    print(f"✗ Export failed for {table_metadata['full_table_name']}")
                    self.failed_tables.append(table_metadata['full_table_name'])
                    continue

                if status == 'EMPTY':
                    # Source table had 0 rows – COPY INTO wrote no file to the
                    # stage, so there is nothing to download.  Skip the wait.
                    print(f"⊘ Table is empty – skipping download wait, moving to next table")
                    self.completed_tables.append(table_metadata['full_table_name'])
                    continue

                # status == 'SUCCESS' — file was written; wait for download
                exported_file = export_result['file_name']
                download_success = self.watcher.wait_for_download(exported_file)

                if download_success:
                    self.completed_tables.append(table_metadata['full_table_name'])
                    print(f"✓ Successfully exported and downloaded table {idx}/{total}")
                else:
                    self.skipped_tables.append(table_metadata['full_table_name'])
                    print(f"⊗ Download timeout for table {idx}/{total} - stopping loop")
                    break  # Stop processing if timeout reached
            
            except Exception as e:
                print(f"✗ Error processing {table_metadata['full_table_name']}: {str(e)}")
                self.failed_tables.append(table_metadata['full_table_name'])
                continue
        
        # Print final summary
        self.print_summary(start_time)
    
    def print_summary(self, start_time):
        """Print summary of export process."""
        elapsed = (datetime.now() - start_time).total_seconds()
        total_processed = len(self.completed_tables) + len(self.failed_tables) + len(self.skipped_tables)
        
        print("\n" + "="*60)
        print("EXPORT LOOP SUMMARY")
        print("="*60)
        print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total elapsed: {elapsed // 3600:.1f} hours ({elapsed // 60:.0f} minutes)")
        print()
        print(f"Completed:  {len(self.completed_tables)} tables")
        print(f"Failed:     {len(self.failed_tables)} tables")
        print(f"Skipped:    {len(self.skipped_tables)} tables")
        print(f"Total:      {total_processed} tables processed")
        print("="*60)
        
        if self.failed_tables:
            print("\nFailed tables:")
            for table in self.failed_tables:
                print(f"  - {table}")
        
        if self.skipped_tables:
            print("\nSkipped tables (timeout):")
            for table in self.skipped_tables:
                print(f"  - {table}")
