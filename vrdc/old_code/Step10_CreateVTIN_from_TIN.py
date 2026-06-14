#--Step10_CreateVTIN_from_TIN.py-----------------------------------
# This script is designed to run in a Databricks notebook environment
# where the 'spark' object is automatically available
# Lint warnings about 'spark' not being defined can be ignored

rif_catalog = 'extracts'
rif_database = 'rif2025'

output_catalog = 'analytics'
output_database = 'dua_000000_ftr460'

columns_to_find = [
    'tax_num',
    'owng_prvdr_tin_num'
]

class TINProcessor:
    """
    This class processes TIN (Tax Identification Number) data from VRDC to create VTINs.
    All methods are static as this is a utility class for organizing sequential operations.
    """
    
    @staticmethod
    def _find_matching_tables(*, rif_catalog, rif_database):
        """
        Find all tables in the RIF database that contain our target TIN columns.
        Returns a dictionary with column names as keys and lists of tables as values.
        """
        discovery_sql = f"""
        SELECT table_name, column_name
        FROM {rif_catalog}.information_schema.columns 
        WHERE table_catalog = '{rif_catalog}'
        AND table_schema = '{rif_database}'
        AND column_name IN ('tax_num', 'owng_prvdr_tin_num')
        ORDER BY table_name, column_name
        """
        
        print("Finding tables with TIN columns...")
        print(discovery_sql)
        
        result = spark.sql(discovery_sql)  # type: ignore
        return result.collect()
    
    @staticmethod
    def _build_union_query(*, matching_records, rif_catalog, rif_database):
        """
        Build a UNION ALL query from all tables that contain TIN columns.
        Each table contributes: tin_column AS tin, bene_id, clm_id
        """
        union_parts = []
        
        for record in matching_records:
            table_name = record['table_name']
            column_name = record['column_name']
            
            select_part = f"""
            SELECT {column_name} AS tin, bene_id, clm_id 
            FROM {rif_catalog}.{rif_database}.{table_name}
            WHERE {column_name} IS NOT NULL
            """
            union_parts.append(select_part)
        
        if not union_parts:
            raise ValueError("No matching tables found with TIN columns")
        
        return " UNION ALL ".join(union_parts)
    
    
    @staticmethod
    def execute_tin_processing(*, is_just_print ):
        """
        Main execution method that orchestrates the entire TIN processing workflow.
        """
        
        # Step 1: Find all tables with TIN columns
        matching_records = TINProcessor._find_matching_tables(
            rif_catalog=rif_catalog,
            rif_database=rif_database
        )
        
        if not matching_records:
            print("No tables found with TIN columns. Exiting.")
            return
        
        print(f"Found {len(matching_records)} table-column combinations with TIN data")
        
        # Step 2: Build and execute union query
        union_query = TINProcessor._build_union_query(
            matching_records=matching_records,
            rif_catalog=rif_catalog,
            rif_database=rif_database
        )
        
        # Step 3: Create SQL statements using f-strings directly
        temp_view_sql = f"""
        CREATE OR REPLACE TEMPORARY VIEW temp_tin_records AS
        {union_query}
        """
        
        drop_x_tin_sql = f"""
        DROP TABLE IF EXISTS {output_catalog}.{output_database}.X_TIN_LIST
        """
        
        summary_sql = f"""
        CREATE TABLE {output_catalog}.{output_database}.X_TIN_LIST AS
        SELECT 
            tin,
            COUNT(DISTINCT bene_id) AS cnt_bene_id,
            COUNT(DISTINCT clm_id) AS cnt_clm_id
        FROM temp_tin_records
        GROUP BY tin
        """
        
        drop_puf_tin_sql = f"""
        DROP TABLE IF EXISTS {output_catalog}.{output_database}.PUF_TIN_LIST
        """
        
        puf_sql = f"""
        CREATE TABLE {output_catalog}.{output_database}.PUF_TIN_LIST AS
        SELECT 
            tin, 
            '                    ' AS vtin,
            cnt_bene_id,
            cnt_clm_id
        FROM {output_catalog}.{output_database}.X_TIN_LIST 
        WHERE cnt_bene_id > 10
        AND tin != '000000000'
        """
        
        display_sql = f"""
        SELECT * 
        FROM {output_catalog}.{output_database}.PUF_TIN_LIST
        ORDER BY cnt_bene_id DESC
        """
        
        # Execute all SQL commands in sequence
        sql_dict = {
            "Create temporary view from union of all TIN tables": temp_view_sql,
            "Drop X_TIN_LIST table if exists": drop_x_tin_sql,
            "Create X_TIN_LIST table with aggregated counts": summary_sql,
            "Drop PUF_TIN_LIST table if exists": drop_puf_tin_sql,
            "Create PUF_TIN_LIST table with privacy filtering": puf_sql
        }
        
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

# Execute the TIN processing workflow
if __name__ == "__main__":
    is_just_print = True
    TINProcessor.execute_tin_processing(is_just_print=is_just_print)