# Bulk IDR Download System

Automated system for generating IDROutputter scripts from Snowflake table metadata. This system discovers tables matching patterns, extracts their metadata, and generates ready-to-use Python scripts for bulk data exports.

## Usage

**Step 1: Discover table metadata** 



*Option B: Notebook usage:*
```python
# Set your parameters
search_pattern = '%PROVIDER%'
output_file = 'provider_metadata.json'
database_name = 'IDRC_PRD'  # Optional: specify database, or use current database context

# Run the discovery with inline JSON printing (recommended for notebooks)
from make_json_from_table_match import run_metadata_discovery
metadata = run_metadata_discovery(
    search_pattern=search_pattern, 
    output_file=output_file,
    database_name=database_name,
    print_inline=True  # Shows JSON output directly in notebook
)
```


**Step 2: Generate IDR export scripts**:
```bash
python make_extract_scripts_from_json.py provider_metadata.json ./generated_scripts/
```

**Step 3: Use generated scripts** in Snowflake notebook:
```python
from provider_demographics_export import ProviderDemographicsExporter
exporter = ProviderDemographicsExporter()
exporter.do_idr_output()
```

## Generated Scripts

Each generated script contains a complete IDROutputter subclass with SELECT queries including all columns in Snowflake storage order. Scripts can be customized by editing the `getSelectQuery()` method to add WHERE clauses, JOINs, or modify column selection. File naming follows `{table_name}_export.py` convention with `{TableName}Exporter` class names.

## Troubleshooting

- **"No active Snowflake session"**: Ensure you're running metadata discovery in a Snowflake notebook environment
- **"No tables found"**: Verify your LIKE pattern (use `'%TABLE%'` format, automatically case-insensitive)  
- **Import errors**: Ensure IDROutputter.py is in your Python path or copy it to the script directory
- Use `--help` flag for detailed command syntax
