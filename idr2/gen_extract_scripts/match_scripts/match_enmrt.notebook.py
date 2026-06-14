# This matches against the enumeration tables

search_pattern = '%prvdr_enmrt%' # matchs against nppes tables

output_file = 'prvdr_enmrt.json'

database_name = 'IDRC_PRD'


# Run the discovery:
metadata = run_metadata_discovery(
     search_pattern=search_pattern, 
     output_file=output_file,
     database_name=database_name,
     print_inline=True
)