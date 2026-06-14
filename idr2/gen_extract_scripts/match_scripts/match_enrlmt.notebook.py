# This matches against the enrollment tables

search_pattern = '%prvdr_enrlmt%' # matchs against mdcd_prvdr_enrlmt, mdcr_prvdr_enrlmt and prvdr_enrlmt

output_file = 'prvdr_enrlmt.json'

database_name = 'IDRC_PRD'


# Run the discovery:
metadata = run_metadata_discovery(
     search_pattern=search_pattern, 
     output_file=output_file,
     database_name=database_name,
     print_inline=True
)