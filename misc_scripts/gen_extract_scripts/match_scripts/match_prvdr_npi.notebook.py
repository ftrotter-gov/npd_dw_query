# prvdr_npi

search_pattern = '%prvdr_npi%' 

output_file = 'prvdr_npi.json'

database_name = 'IDRC_PRD'


# Run the discovery:
metadata = run_metadata_discovery(
     search_pattern=search_pattern, 
     output_file=output_file,
     database_name=database_name,
     print_inline=True
)