"""
CreateEntityMap.py

Leverages the EntityLooper to create the entity map from a time period in VRDC claims files. 

First, it creates a VIEW that contains a row in the data with five columns for each month of claim + claim_line data. 
These are: 

* source_setting_name
* TAX_NUM
* CCN
* onpi
* pnpi
* bene_id
* clm_id

In the end, the entity map is by querying this view with the simple query: 

```sql
CREATE TABLE {output_DBTable}
SELECT 
    COUNT(DISTINCT source_setting_name) AS setting_count,
    TAX_NUM,
    CCN,
    onpi,
    pnpi,
    COUNT(DISTINCT(bene_id)) AS bene_count,
    COUNT(DISTINCT(clm_id)) AS claim_count
FROM {vrdc_entity_map_view}
GROUP BY 
    TAX_NUM,
    CCN,
    onpi,
    pnpi
HAVING COUNT(DISTINCT(bene_id)) > 10
```

inside an f-string so that the variables can be resolved and modified without changing the code. 

The view itself should be built based on the querying each claim and claim-line pair like so: 

```sql
SELECT 
    {get_my_select_variables_for_entity_map_class}
FROM {this_claim_table} AS CLAIM
LEFT JOIN {this_claim_line_table} AS CLAIM_LINE
    ON CLAIM.CLM_ID = CLAIM_LINE.CLM_ID
WHERE {my entity columns are not NULL}
```
you will need to do a DROP VIEW IF EXISTS before creating the view.

The program should accept a start year/month and end year/month to define the time period.
As well as a list of settings to include in the entity map. If no settings are provided, all 7 settings should be included.
Then the view should be built for that time period, as a UNION of all of the monthly data within the time period

Please read the EntityLooper class for more information on how the entity map is built.

Read vrdc/EIN_CCN_NPI_gather.py for an idea of how to access the local spark connection to get this done. 

Make a persistent view here, so that we can test against it in subsequent steps. But lets go ahead and make a little log table at the end that records the number
of rows in the view, the number of distinct TAX_NUM, CCN, onpi, pnpi, bene_id and clm_id and the date/time the view was created.

The start of the file should have the variables that will determine how the file is configured and run. This view will be run in an databricks notebook context.


Do not overwrite these comments as you modify the code.

"""

try:
    from .MonthRange import MonthRange
    from .VrdcEntityMapper import VRDCEntityMapper
except ImportError:
    try:
        from MonthRange import MonthRange
        from VrdcEntityMapper import VRDCEntityMapper
    except ImportError:
        print("Loading from previous cell")


from datetime import datetime


class VRDCEntityMapBuilder:
    """Build VRDC entity maps using the EntityLooper functionality."""
    
    @staticmethod
    def build_entity_map(*, month_range, settings=None, extracts_catalog='extracts',
                        output_catalog='analytics', output_database='dua_000000_ftr460',
                        view_name='vrdc_entity_map_view', 
                        table_name='vrdc_entity_map',
                        log_table_name='vrdc_entity_map_log',
                        privacy_threshold=10, execute=True, is_just_print=False):
        """
        Build VRDC entity map view and table for a given time range and settings.
        
        Args:
            month_range (MonthRange): Time range to process
            settings (list): List of settings to include, None for all
            extracts_catalog (str): Source data catalog name
            output_catalog (str): Output catalog name
            output_database (str): Output database name
            view_name (str): Name for intermediate view
            table_name (str): Name for final entity map table
            log_table_name (str): Name for log table
            privacy_threshold (int): Minimum beneficiaries threshold
            execute (bool): Whether to execute SQL or just return it
            is_just_print (bool): If True, print SQL without executing (overrides execute)
            
        Returns:
            dict: SQL statements generated
        """
        
        # Get settings to process
        if settings is None:
            settings = VRDCEntityMapper.get_all_settings()
        
        # Build full table names
        entity_view_full = f"{output_catalog}.{output_database}.{view_name}"
        entity_table_full = f"{output_catalog}.{output_database}.{table_name}"
        log_table_full = f"{output_catalog}.{output_database}.{log_table_name}"
        
        # Generate SQL statements
        sql = {}
        
        # 1. Drop view if exists
        sql['DROP entity map view'] = f"DROP VIEW IF EXISTS {entity_view_full}"
        
        # 2. Create view with union of monthly data - one SELECT per NPI field
        union_queries = []
        
        for result in VRDCEntityMapper.iterate_month_range(
            month_range=month_range, settings=settings
        ):
            # Build source table names
            claim_table = f"{extracts_catalog}.{result['database']}.{result['claim_table']}"
            line_table = f"{extracts_catalog}.{result['database']}.{result['line_table']}"
            
            setting = result['setting']
            year = result['year']
            month = result['month']
            
            # Generate Cartesian product: every org NPI paired with every personal NPI
            setting_fields = VRDCEntityMapper.get_setting_fields(setting=setting)
            
            # Get TAX_NUM and CCN for this setting (can be NULL if not available)
            tax_num_sql = "NULL AS TAX_NUM"
            ccn_sql = "NULL AS CCN"
            
            if setting_fields['tax_id']:
                tax_field = setting_fields['tax_id'][0]
                tax_table_ref = "CLAIM" if tax_field['table'] == 'CLAIM' else "CLINE"
                tax_num_sql = f"{tax_table_ref}.{tax_field['field']} AS TAX_NUM"
            
            if setting_fields['ccn']:
                ccn_field = setting_fields['ccn'][0]
                ccn_table_ref = "CLAIM" if ccn_field['table'] == 'CLAIM' else "CLINE"
                ccn_sql = f"{ccn_table_ref}.{ccn_field['field']} AS CCN"
            
            # Get all organizational and personal NPI fields for this setting
            org_npi_fields = list(VRDCEntityMapper.iterate_npi_fields(setting=setting, npi_level='organizational_npi'))
            personal_npi_fields = list(VRDCEntityMapper.iterate_npi_fields(setting=setting, npi_level='personal_npi'))
            
            # Generate Cartesian product: org × personal
            for org_npi in org_npi_fields:
                for personal_npi in personal_npi_fields:
                    org_table_ref = "CLAIM" if org_npi['table'] == 'CLAIM' else "CLINE"
                    personal_table_ref = "CLAIM" if personal_npi['table'] == 'CLAIM' else "CLINE"
                    
                    # WHERE clause ensures both NPI fields exist
                    where_conditions = [
                        f"{org_table_ref}.{org_npi['field']} IS NOT NULL",
                        f"{personal_table_ref}.{personal_npi['field']} IS NOT NULL"
                    ]
                    where_clause = " AND ".join(where_conditions)
                    
                    monthly_query = f"""        SELECT 
            '{setting}' AS source_setting_name,
            CLAIM.BENE_ID AS bene_id,
            CLAIM.CLM_ID AS clm_id,
            {tax_num_sql},
            {ccn_sql},
            {org_table_ref}.{org_npi['field']} AS onpi,
            {personal_table_ref}.{personal_npi['field']} AS pnpi
        FROM {claim_table} AS CLAIM
        LEFT JOIN {line_table} AS CLINE
            ON CLAIM.CLM_ID = CLINE.CLM_ID
        WHERE {where_clause}"""
                    
                    union_queries.append(monthly_query)
        
        # Combine with UNION ALL
        view_query = "\nUNION ALL\n".join(union_queries)
        
        sql['CREATE entity map view'] = f"""
CREATE VIEW {entity_view_full} AS
{view_query}"""
        
        # 3. Drop final table if exists
        sql['DROP entity map table'] = f"DROP TABLE IF EXISTS {entity_table_full}"
        
        # 4. Create final entity map table
        sql['CREATE entity map table'] = f"""
CREATE TABLE {entity_table_full} AS 
SELECT 
    COUNT(DISTINCT source_setting_name) AS setting_count,
    TAX_NUM,
    CCN,
    onpi,
    pnpi,
    COUNT(DISTINCT bene_id) AS bene_count,
    COUNT(DISTINCT clm_id) AS claim_count
FROM {entity_view_full}
GROUP BY 
    TAX_NUM,
    CCN,
    onpi,
    pnpi
HAVING COUNT(DISTINCT bene_id) > {privacy_threshold}"""
        
        # 5. Drop log table if exists
        sql['DROP log table'] = f"DROP TABLE IF EXISTS {log_table_full}"
        
        # 6. Create log table with statistics
        sql['CREATE log table'] = f"""
CREATE TABLE {log_table_full} AS
SELECT 
    '{datetime.now().isoformat()}' AS creation_timestamp,
    '{month_range.start_year}-{month_range.start_month:02d}' AS start_period,
    '{month_range.end_year}-{month_range.end_month:02d}' AS end_period,
    {month_range.get_total_months()} AS total_months,
    {len(settings)} AS total_settings,
    '{",".join(settings)}' AS included_settings,
    {privacy_threshold} AS privacy_threshold,
    (SELECT COUNT(*) FROM {entity_view_full}) AS view_total_rows,
    (SELECT COUNT(DISTINCT TAX_NUM) FROM {entity_view_full}) AS distinct_tax_nums,
    (SELECT COUNT(DISTINCT CCN) FROM {entity_view_full}) AS distinct_ccns,
    (SELECT COUNT(DISTINCT onpi) FROM {entity_view_full}) AS distinct_onpis,
    (SELECT COUNT(DISTINCT pnpi) FROM {entity_view_full}) AS distinct_pnpis,
    (SELECT COUNT(DISTINCT bene_id) FROM {entity_view_full}) AS distinct_bene_ids,
    (SELECT COUNT(DISTINCT clm_id) FROM {entity_view_full}) AS distinct_claim_ids,
    (SELECT COUNT(*) FROM {entity_table_full}) AS final_entity_count"""
        
        # Execute SQL if requested
        if execute:
            VRDCEntityMapBuilder.execute_sql_dict(sql_dict=sql, is_just_print=is_just_print)
        
        return sql
    
    @staticmethod  
    def execute_sql_dict(*, sql_dict, is_just_print=False):
        """
        Execute a dictionary of SQL statements.
        
        Args:
            sql_dict (dict): Dictionary of description -> SQL statement
            is_just_print (bool): If True, print SQL without executing
        """
        for description, sql_statement in sql_dict.items():
            print(f"\n-- {description}:")
            print(sql_statement)
            if is_just_print:
                print("-- Just printing for now\n")
            else:
                print("-- Running:")
                spark.sql(sql_statement)  # type: ignore
