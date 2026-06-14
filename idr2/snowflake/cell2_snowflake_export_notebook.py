"""
Snowflake Export Main Script - Cell 2

This script was auto-generated with all metadata embedded.
It requires the classes from Cell 1 (snowflake_export_classes.py).

Just run this cell to start the export loop.
"""

from datetime import datetime

# ============================================================================
# EMBEDDED METADATA
# ============================================================================

METADATA_JSON = {
    "generated": "2026-06-14T16:46:01.750048",
    "source": "Generated from list_of_tables_to_download.csv and cached metadata",
    "tables": [
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_FINCL_INSTN_EFT_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_fincl_instn_eft_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_FINCL_INSTN_EFT_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_MDCR_ID_DEACTVTN_RSN_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_mdcr_id_deactvtn_rsn_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_MDCR_ID_DEACTVTN_RSN_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_MDCR_ID_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_mdcr_id_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_MDCR_ID_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_MDCR_ID_XWLK_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_mdcr_id_xwlk_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_MDCR_ID_XWLK_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_NPI_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_npi_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_NPI_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_NPI_XWLK_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_npi_xwlk_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_NPI_XWLK_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_PRCTC_LCTN_AND_PAY_TO_LCTN_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_prctc_lctn_and_pay_to_lctn_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_PRCTC_LCTN_AND_PAY_TO_LCTN_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_PRCTC_LCTN_CLIA_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_prctc_lctn_clia_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_PRCTC_LCTN_CLIA_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_PRCTC_LCTN_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_prctc_lctn_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_PRCTC_LCTN_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_PRCTC_LCTN_MDCR_ID_NPI_CMBNTN_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_prctc_lctn_mdcr_id_npi_cmbntn_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_PRCTC_LCTN_MDCR_ID_NPI_CMBNTN_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_PRMRY_SPCLTY_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_prmry_spclty_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_PRMRY_SPCLTY_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_REASGNMT_ADR_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_reasgnmt_adr_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_REASGNMT_ADR_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_REASGNMT_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_reasgnmt_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_REASGNMT_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_SPCLTY_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_spclty_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_SPCLTY_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_STUS_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_stus_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_STUS_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_STUS_RSN_HSTRY",
            "file_name_stub": "v2_prvdr_enrlmt_stus_rsn_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_STUS_RSN_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENMRT.V2_PRVDR_ENMRT_HSTRY",
            "file_name_stub": "v2_prvdr_enmrt_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENMRT.V2_PRVDR_ENMRT_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENMRT.V2_PRVDR_ENMRT_NAME_HSTRY",
            "file_name_stub": "v2_prvdr_enmrt_name_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENMRT.V2_PRVDR_ENMRT_NAME_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENMRT.V2_PRVDR_ENMRT_OTHR_NAME_HSTRY",
            "file_name_stub": "v2_prvdr_enmrt_othr_name_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENMRT.V2_PRVDR_ENMRT_OTHR_NAME_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENMRT.V2_PRVDR_ENMRT_RACE_ETHNCTY_HSTRY",
            "file_name_stub": "v2_prvdr_enmrt_race_ethncty_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENMRT.V2_PRVDR_ENMRT_RACE_ETHNCTY_HSTRY
"""
        },
        {
            "full_table_name": "IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENMRT.V2_PRVDR_ENMRT_TXNMY_HSTRY",
            "file_name_stub": "v2_prvdr_enmrt_txnmy_hstry_idr_export",
            "version_number": "v01",
            "select_query": """
SELECT * FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENMRT.V2_PRVDR_ENMRT_TXNMY_HSTRY
"""
        }
    ]
}

# ============================================================================
# CONFIGURATION
# ============================================================================

POLLING_INTERVAL_MINUTES = 5      # Check for downloads every 5 minutes
QUIT_AFTER_HOURS = 2              # Stop after 2 hours with no activity


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function - loads metadata and starts export loop."""

    try:
        # Get active Snowflake session
        session = get_active_session()  # noqa: F821

        print("Snowflake session acquired")
        print(f"\nMetadata prepared for {len(METADATA_JSON.get('tables', []))} tables")
        print(f"Generated: {METADATA_JSON.get('generated', 'Unknown')}")

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
