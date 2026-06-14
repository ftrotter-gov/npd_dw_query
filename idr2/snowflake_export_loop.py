"""
Snowflake Parallel Export Loop Script

This script is designed to run in a Snowflake Python notebook environment.
It reads metadata about tables to export and orchestrates the export process,
coordinating with the downloader via file presence/absence in the Snowflake stage.

The system uses a simple protocol:
1. Export a CSV to @~/ (Snowflake user stage)
2. Wait for the file to be downloaded and deleted
3. Repeat for the next table

Usage in Snowflake notebook:
    # Copy and paste entire file into a notebook cell
    # Adjust configuration if needed
    # Run the cell
    
The script includes automatic timeout: stops after 2 hours of no progress.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path


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
            
            print(f"Export completed for {self.full_table_name}")
            
            return {
                'status': 'SUCCESS',
                'table': self.full_table_name,
                'file_name': file_name,
                'file_name_stub': self.file_name_stub,
                'timestamp': ts,
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
        List all CSV files in the Snowflake user stage.
        
        Returns:
            list: List of file names in stage
        """
        try:
            result = self.session.sql("LIST @~/").collect()
            files = []
            for row in result:
                file_name = str(row[0]) if row else ""
                if file_name.endswith('.csv'):
                    files.append(file_name)
            return files
        except Exception as e:
            print(f"Error listing stage files: {e}")
            return []
    
    def wait_for_download(self, exported_file_name):
        """
        Wait for a file to be downloaded (deleted from stage).
        
        Polls the stage every polling_interval seconds.
        Times out after quit_after_hours of no activity.
        
        Args:
            exported_file_name: Name of file exported (e.g., @~/table.v01.timestamp.csv)
        
        Returns:
            bool: True if file was downloaded (deleted), False if timeout
        """
        # Extract just the filename part for checking
        check_name = exported_file_name.replace("@~/", "")
        
        print(f"\nWaiting for download of: {check_name}")
        print(f"Polling every {self.polling_interval // 60} minutes...")
        print(f"Timeout: {self.quit_after // 3600} hours with no activity")
        
        wait_start = datetime.now()
        
        while True:
            # Check elapsed time since task started
            elapsed_since_start = (datetime.now() - self.start_time).total_seconds()
            elapsed_since_change = (datetime.now() - self.last_change_time).total_seconds()
            
            # Timeout if no activity for specified hours
            if elapsed_since_change > self.quit_after:
                print(f"\nTIMEOUT: No download activity for {self.quit_after // 3600} hours")
                print(f"Total elapsed time: {elapsed_since_start // 3600:.1f} hours")
                return False
            
            # Check if file still exists
            files = self.list_files_in_stage()
            
            if check_name not in files:
                elapsed = (datetime.now() - wait_start).total_seconds()
                print(f"✓ Download complete! ({elapsed // 60:.0f} min, {elapsed % 60:.0f} sec)")
                self.last_change_time = datetime.now()
                return True
            
            # File still exists, wait and check again
            print(f"  Waiting... ({elapsed_since_change // 60:.0f} min, {elapsed_since_change % 60:.0f} sec elapsed)")
            
            # Sleep for polling interval
            for i in range(self.polling_interval):
                if i % 60 == 0 and i > 0:
                    print(f"  Still waiting... ({(elapsed_since_change + i) // 60:.0f} min)")
                time.sleep(1)


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
        
        for idx, table_metadata in enumerate(tables, 1):
            print(f"\n[{idx}/{total}] Processing table: {table_metadata['full_table_name']}")
            
            try:
                # Export the table
                exporter = SnowflakeExporter(self.session, table_metadata)
                export_result = exporter.export_table()
                
                if export_result['status'] == 'FAILED':
                    print(f"✗ Export failed for {table_metadata['full_table_name']}")
                    self.failed_tables.append(table_metadata['full_table_name'])
                    continue
                
                exported_file = export_result['file_name']
                
                # Wait for the file to be downloaded
                download_success = self.watcher.wait_for_download(exported_file)
                
                if download_success:
                    self.completed_tables.append(table_metadata['full_table_name'])
                    print(f"✓ Successfully exported and downloaded table {idx}/{total}")
                else:
                    self.skipped_tables.append(table_metadata['full_table_name'])
                    print(f"⊗ Download timeout for table {idx}/{total} - continuing with next")
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


# ============================================================================
# MAIN EXECUTION - Paste everything below into Snowflake notebook
# ============================================================================

def main():
    """Main execution function - call this in your Snowflake notebook."""
    
    try:
        # Get active Snowflake session
        # This should already be configured in your notebook
        session = get_active_session()  # noqa: F821
        
        print("Snowflake session acquired")
        
        # CONFIGURATION - Modify these as needed
        METADATA_JSON = {
            "generated": datetime.now().isoformat(),
            "tables": [
                {
                    "database": "IDRC_PRD",
                    "schema": "CMS_VDM_VIEW_MDCR_PRD",
                    "table": "V2_MDCR_PRVDR",
                    "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR",
                    "columns": [],
                    "file_name_stub": "v2_mdcr_prvdr_idr_export",
                    "version_number": "v01",
                    "select_query": "SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR"
                }
                # Add more tables here or load from external metadata
            ]
        }
        
        POLLING_INTERVAL_MINUTES = 5      # Check for downloads every 5 minutes
        QUIT_AFTER_HOURS = 2              # Stop after 2 hours with no activity
        
        # Initialize and run the export loop
        metadata = ExportMetadata(METADATA_JSON)
        loop = ExportLoop(session, metadata, POLLING_INTERVAL_MINUTES, QUIT_AFTER_HOURS)
        loop.run()
        
        print("\n✓ Export loop completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Fatal error in export loop: {str(e)}")
        print(f"Please check your configuration and try again")
        raise


# Uncomment the following line to run the main function:
# main()
