from pyspark.sql import functions as F # type: ignore
from pyspark.sql.types import StringType # type: ignore

cms_privacy_threshold = 10

extracts_catalog = 'extracts'
rif_database = 'rif2025'

output_catalog = 'analytics'
output_database = 'dua_000000_ftr460' # replace with your database

aco_output_table = 'aco_output'
sql = {}

aco_table = 'provider_ssp_2025'
aco_export_DBTable = "{output_catalog}.{output_database}.{aco_output_table}"
aco_source_DBTable = "{extracts_catalog}.aco.{aco_table}"

sql['DROP aco export table'] = f"DROP TABLE IF EXISTS {aco_export_DBTable}"

sql['create ACO export table'] = f""" 
CREATE TABLE {aco_export_DBTable} AS 
SELECT 
    npi,
    prvdr_aco_year,
    tin,
    ccn,
    aco_num,
    tin_lbn,
    aco_name,
    start_date,
    aco_location
FROM {aco_source_DBTable}
"""

carrier_output_table = 'carrier_billed_together'
carrier_source_database = 'rif2025'
carrier_claim_table = 'bcarrier_claims_09'
carrier_cline_table = 'bcarrier_line_09'

carrier_export_DBTable = "{output_catalog}.{output_database}.{carrier_output_table}"
carrier_claim_DBTable = "{extracts_catalog}.{carrier_source_database}.{carrier_claim_table}"
carrier_cline_DBTable = "{extracts_catalog}.{carrier_source_database}.{carrier_cline_table}"

sql['DROP carrier analysis table'] = f"DROP TABLE IF EXISTS {carrier_export_DBTable}"

sql['CREATE carrier analysis table'] = f"""
CREATE TABLE {carrier_export_DBTable} AS 
SELECT 
    tax_num,
    COALESCE(carr_clm_sos_npi_num,carr_clm_blg_npi_num) AS org_npi_num,
    PRF_PHYSN_NPI,
    COUNT(DISTINCT(claim.bene_id)) AS cnt_bene_id,
    COUNT(DISTINCT(claim.clm_id)) AS cnt_clm_id
FROM {carrier_claim_DBTable} AS claim
JOIN {carrier_cline_DBTable} AS cline ON 
    cline.clm_id =
    claim.clm_id
GROUP BY   
    tax_num,
    COALESCE(carr_clm_sos_npi_num,carr_clm_blg_npi_num) AS org_npi_num,
    PRF_PHYSN_NPI
HAVING COUNT(DISTINCT(claim.bene_id)) > {cms_privacy_threshold}
"""

#Maybe TODO add DME?

#TODO definately expand to other benifit settings

inpatient_output_table = 'inpatient_billed_together'
inpatient_source_database = 'rif2025'
inpatient_claim_table = 'inpatient_claims_09'
inpatient_cline_table = 'inpatient_revenue_09'

inpatient_export_DBTable = "{output_catalog}.{output_database}.{inpatient_output_table}"
inpatient_claim_DBTable = "{extracts_catalog}.{inpatient_source_database}.{inpatient_claim_table}"
inpatient_cline_DBTable = "{extracts_catalog}.{inpatient_source_database}.{inpatient_cline_table}"






for description, sql in sql_dict.items():
    print(f"\n{description}:\n")
    print(sql)
    if(is_just_print):
        print("Just printing for now\n")
    else:
        print("Running:\n")
        spark.sql(sql)  # type: ignore

# Step 4: Display results using Databricks display function
print(f"\nDisplaying final PUF TIN list:")
print(display_sql)
result_df = spark.sql(display_sql)  # type: ignore
display(result_df)  # type: ignore

print("\nTIN processing completed successfully!")