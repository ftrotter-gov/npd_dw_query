"""
Snowflake Export Main Generator

Small script that dynamically generates METADATA_JSON from export_metadata.json
and calls main() to start the export loop.

Paste this entire script into the SECOND cell of your Snowflake Python notebook.

Prerequisites:
  - First cell must contain all classes from snowflake_export_classes.py
  - export_metadata.json must exist in the same directory
"""

import json
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

# Path to the metadata JSON file (relative to notebook execution directory)
METADATA_FILE = "export_metadata.json"

# Snowflake stage polling configuration
POLLING_INTERVAL_MINUTES = 5      # Check for downloads every 5 minutes
QUIT_AFTER_HOURS = 2              # Stop after 2 hours with no activity


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function - loads metadata and starts export loop."""
    
    try:
        # Get active Snowflake session
        # This should already be configured in your notebook
        session = get_active_session()  # noqa: F821
        
        print("Snowflake session acquired")
        print(f"\nLoading metadata from: {METADATA_FILE}")
        
        # Load metadata from JSON file
        try:
            with open(METADATA_FILE, 'r') as f:
                METADATA_JSON = json.load(f)
            print(f"✓ Metadata loaded: {len(METADATA_JSON.get('tables', []))} tables")
        except FileNotFoundError:
            print(f"✗ ERROR: {METADATA_FILE} not found")
            print("Please ensure export_metadata.json is in the notebook's working directory")
            raise
        except json.JSONDecodeError as e:
            print(f"✗ ERROR: {METADATA_FILE} is not valid JSON: {e}")
            raise
        
        print(f"\nMetadata generated: {METADATA_JSON.get('generated', 'Unknown')}")
        print(f"Metadata source: {METADATA_JSON.get('source', 'Unknown')}")
        
        # Print configuration
        print("\n" + "="*60)
        print("EXPORT LOOP CONFIGURATION")
        print("="*60)
        print(f"Polling interval: {POLLING_INTERVAL_MINUTES} minutes")
        print(f"Timeout: {QUIT_AFTER_HOURS} hours with no activity")
        print(f"Total tables: {len(METADATA_JSON.get('tables', []))}")
        print("="*60)
        
        # Initialize and run the export loop
        metadata = ExportMetadata(METADATA_JSON)
        loop = ExportLoop(
            session,
            metadata,
            POLLING_INTERVAL_MINUTES,
            QUIT_AFTER_HOURS
        )
        loop.run()
        
        print("\n✓ Export loop completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Fatal error in export loop: {str(e)}")
        print(f"Please check your configuration and try again")
        raise


# Call main() to start the export loop
main()
