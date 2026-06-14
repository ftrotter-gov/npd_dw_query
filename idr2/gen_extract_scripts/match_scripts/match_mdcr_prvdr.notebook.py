# mdcr_prvdr

search_pattern = '%mdcr_prvdr%' # mdcr_prvdr

output_file = 'mdcr_prvdr.json'

database_name = 'IDRC_PRD'


# Run the discovery:
metadata = run_metadata_discovery(
     search_pattern=search_pattern, 
     output_file=output_file,
     database_name=database_name,
     print_inline=True
)
