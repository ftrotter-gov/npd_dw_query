#--Step20_CreateVTIN_PUF.py----------------------------
# presume that the VEIN class from VEIN.py  in scope and assume that MAIN_KEY and MAIN_MODULUS are also defined and in the scope of this databricks notebook
# Load all TINs from PUF_TIN_LIST into a DataFrame, process VTINs in-memory, and create a new table PUF_VTIN_LIST
# spark.sql is already in scope, no need to import it.

from pyspark.sql import functions as F # type: ignore
from pyspark.sql.types import StringType # type: ignore

rif_catalog = 'extracts'
rif_database = 'rif2025'

output_catalog = 'analytics'
output_database = 'dua_000000_ftr460'


class VTINProcessor:
    """
    This class processes the PUF_TIN_LIST table to populate VTIN identifiers using in-memory DataFrame operations.
    All methods are static as this is a utility class for organizing sequential operations.
    """
    
    @staticmethod
    def _create_vtin_udf(*, main_key, main_modulus):
        """
        Create a User Defined Function (UDF) that generates VTINs for TINs.
        Returns a UDF that can be used in DataFrame operations.
        """
        def generate_vtin(tin_value):
            """
            Generate a VTIN identifier for a given TIN using the VEIN class.
            Returns the generated VTIN string or None if generation fails.
            """
            if tin_value is None:
                return None
            
            try:
                vtin_identifier = VEIN.VTIN_identifier(  # type: ignore
                    ein=tin_value,
                    main_key=main_key,
                    modulus=main_modulus
                )
                return vtin_identifier
            except Exception as e:
                print(f"Error generating VTIN for TIN {tin_value}: {str(e)}")
                return None
        
        # Register the UDF with Spark
        return F.udf(generate_vtin, StringType())
    
    @staticmethod
    def _load_tin_dataframe(*, output_catalog, output_database):
        """
        Load all TIN records from the PUF_TIN_LIST table into a DataFrame.
        Returns a Spark DataFrame with tin, vtin, cnt_bene_id, cnt_clm_id columns.
        """
        select_sql = f"""
        SELECT tin, vtin, cnt_bene_id, cnt_clm_id
        FROM {output_catalog}.{output_database}.PUF_TIN_LIST
        ORDER BY tin
        """
        
        print("Loading TIN records from PUF_TIN_LIST into DataFrame...")
        print(select_sql)
        
        df = spark.sql(select_sql)  # type: ignore
        record_count = df.count()
        print(f"Loaded {record_count} TIN records into DataFrame")
        
        return df
    
    @staticmethod
    def _process_vtins_in_memory(*, tin_df, main_key, main_modulus):
        """
        Process all TIN records in the DataFrame to generate VTINs using in-memory operations.
        Returns a new DataFrame with populated VTIN values.
        """
        print("Creating VTIN generation UDF...")
        vtin_udf = VTINProcessor._create_vtin_udf(
            main_key=main_key,
            main_modulus=main_modulus
        )
        
        print("Generating VTINs for all TINs in DataFrame...")
        # Replace the vtin column with generated VTINs
        processed_df = tin_df.withColumn("vtin", vtin_udf(F.col("tin")))
        
        # Cache the result since we'll be using it multiple times
        processed_df.cache()
        
        return processed_df
    
    @staticmethod
    def _create_vtin_table(*, processed_df, output_catalog, output_database, is_just_print):
        """
        Create the new PUF_VTIN_LIST table with processed VTIN data.
        """
        table_name = f"{output_catalog}.{output_database}.PUF_VTIN_LIST"
        
        if is_just_print:
            print(f"Would create table: {table_name}")
            print("Sample of processed data:")
            processed_df.show(10)
        else:
            print(f"Creating table: {table_name}")
            
            # Drop the table if it exists
            drop_sql = f"DROP TABLE IF EXISTS {table_name}"
            print(f"Executing: {drop_sql}")
            spark.sql(drop_sql)  # type: ignore
            
            # Create the new table
            processed_df.write \
                .mode("overwrite") \
                .option("overwriteSchema", "true") \
                .saveAsTable(table_name)
            
            print(f"Successfully created table: {table_name}")
    
    @staticmethod
    def _display_sample_results(*, output_catalog, output_database, sample_size=10):
        """
        Display a sample of the created PUF_VTIN_LIST records to verify the results.
        """
        sample_sql = f"""
        SELECT tin, vtin, cnt_bene_id, cnt_clm_id
        FROM {output_catalog}.{output_database}.PUF_VTIN_LIST
        WHERE vtin IS NOT NULL
        ORDER BY cnt_bene_id DESC
        LIMIT {sample_size}
        """
        
        print(f"\nDisplaying sample of created table records (limit {sample_size}):")
        print(sample_sql)
        
        result_df = spark.sql(sample_sql)  # type: ignore
        display(result_df)  # type: ignore
    
    @staticmethod
    def _get_processing_statistics(*, processed_df, output_catalog, output_database, is_just_print):
        """
        Get statistics on the VTIN processing results.
        """
        print("\nGetting processing statistics...")
        
        # Get statistics from the processed DataFrame
        total_records = processed_df.count()
        non_null_vtins = processed_df.filter(F.col("vtin").isNotNull()).count()
        null_vtins = processed_df.filter(F.col("vtin").isNull()).count()
        
        print(f"\nVTIN Processing Statistics:")
        print(f"Total records: {total_records}")
        print(f"Successfully processed VTINs: {non_null_vtins}")
        print(f"Failed VTIN generations: {null_vtins}")
        print(f"Success rate: {(non_null_vtins/total_records)*100:.1f}%")
        
        # If table was created, also get statistics from the table
        if not is_just_print:
            table_stats_sql = f"""
            SELECT 
                COUNT(*) as total_records,
                COUNT(vtin) as non_null_vtins,
                COUNT(CASE WHEN vtin IS NULL THEN 1 END) as null_vtins
            FROM {output_catalog}.{output_database}.PUF_VTIN_LIST
            """
            
            print(f"\nTable statistics:")
            print(table_stats_sql)
            
            result = spark.sql(table_stats_sql)  # type: ignore
            result.show()
    
    @staticmethod
    def _show_vtin_examples(*, processed_df, sample_size=5):
        """
        Show examples of TIN -> VTIN mappings for verification.
        """
        print(f"\nShowing {sample_size} examples of TIN -> VTIN mappings:")
        
        examples_df = processed_df.filter(F.col("vtin").isNotNull()) \
                                 .select("tin", "vtin") \
                                 .limit(sample_size)
        
        examples_df.show(truncate=False)
    
    @staticmethod
    def execute_vtin_processing(*, is_just_print, main_key, main_modulus):
        """
        Main execution method that orchestrates the entire VTIN processing workflow.
        Loads all TINs into memory, processes VTINs, and creates the new PUF_VTIN_LIST table.
        """
        print("Starting in-memory VTIN processing for PUF_TIN_LIST...")
        
        # Step 1: Load all TIN records into a DataFrame
        tin_df = VTINProcessor._load_tin_dataframe(
            output_catalog=output_catalog,
            output_database=output_database
        )
        
        if tin_df.count() == 0:
            print("No TIN records found in PUF_TIN_LIST. Exiting.")
            return
        
        # Step 2: Process all VTINs in memory
        processed_df = VTINProcessor._process_vtins_in_memory(
            tin_df=tin_df,
            main_key=main_key,
            main_modulus=main_modulus
        )
        
        # Step 3: Show examples of the processing results
        VTINProcessor._show_vtin_examples(processed_df=processed_df)
        
        # Step 4: Create the new PUF_VTIN_LIST table
        VTINProcessor._create_vtin_table(
            processed_df=processed_df,
            output_catalog=output_catalog,
            output_database=output_database,
            is_just_print=is_just_print
        )
        
        # Step 5: Display results and statistics
        VTINProcessor._get_processing_statistics(
            processed_df=processed_df,
            output_catalog=output_catalog,
            output_database=output_database,
            is_just_print=is_just_print
        )
        
        if not is_just_print:
            VTINProcessor._display_sample_results(
                output_catalog=output_catalog,
                output_database=output_database
            )
        
        # Clean up cached DataFrame
        processed_df.unpersist()
        
        print("\nVTIN processing completed!")


# Execute the VTIN processing workflow
if __name__ == "__main__":
    # These variables should be defined in the Databricks notebook scope
    # MAIN_KEY and MAIN_MODULUS are presumed to be available
    is_just_print = True
    
    # Note: In actual Databricks execution, MAIN_KEY and MAIN_MODULUS should be defined
    # For this example, we're showing how they would be used
    try:
        VTINProcessor.execute_vtin_processing(
            is_just_print=is_just_print,
            main_key=MAIN_KEY,  # type: ignore
            main_modulus=MAIN_MODULUS  # type: ignore
        )
    except NameError as e:
        print(f"Missing required variables: {e}")
        print("MAIN_KEY and MAIN_MODULUS must be defined in the notebook scope")