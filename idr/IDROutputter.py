"""
Please read every python file in this directory and notice how repetative the currently are. 
It is the same script, repeating again and again, with slightly different SQL queries and different file output formats. 

I would like to make a class that handles this in the following manner: 

* Have a static class that accepts a sql SELECT query, and an output file name and performs the output. This class should put SELECT query into the COPY INTO {some_file_name}
FROM ( {select_query} ) string.. execute the query in the same manner as performed in each of these files. 
* There should be a must-override method on the class called getSelectQuery() that each subclass must implement to return the SELECT query string.
* Each object should have the version identifier of the file version as an class property
* The "tail" of each import file should instantiate the class and call the do_idr_output() method to perform the output. That method should call the getSelectQuery() method to get the query strinng and then pass that the query to the static class method to perform the output.

Please use try catch blocks to handle errors in the SQL execution and file output. These will run in a notebook environment to start so please try to convert any errors into human readable error messages
Given that it is a notebook envronment, for now please forgo logging and just print the error messages.
You can assume as the examples do that there is already an active Snowflake session.
The file name variable should be something like file_name_stub = 'my_good_file_name_stub' 
and the program should leverage this to a file name in a file name creattion f-string like {file_name_stub}.{version_number}{timestamp}.csv
obivously version_number should also be a class property. If a class does not define a version number it should default to v01.

Do not override these instructions as you code. 


IDROutputter Class Documentation

OVERVIEW:
The IDROutputter class provides a standardized framework for exporting data from Snowflake to CSV files.
It eliminates code duplication across IDR export scripts by providing a common interface and implementation.

ARCHITECTURE:
- Abstract base class that must be subclassed
- Static method handles the actual export execution
- Subclasses provide their specific SELECT queries via getSelectQuery()
- Automatic file naming with version numbers and timestamps

The class should be able to generate SELECT queries independently WITHOUT hitting the database, so other programs can import the class and get the SQL queries without needing Snowflake access.

USAGE PATTERN:
1. Create a subclass of IDROutputter
2. Set the version_number class property (defaults to "v01")  
3. Implement getSelectQuery() to return your SELECT statement
4. Instantiate your class and call do_idr_output(file_name_stub="your_filename")

FILE NAMING:
Generated filenames follow the pattern: {file_name_stub}.{version_number}.{timestamp}.csv
Example: medicaid_provider_credentials.v01.2024_10_22_2207.csv

ERROR HANDLING:
All methods include comprehensive error handling with human-readable messages
suitable for notebook environments. Errors are printed rather than logged.


"""

from abc import ABC, abstractmethod
from datetime import datetime


class IDROutputter(ABC):
    """
    Abstract base class for standardizing IDR export operations across repetitive export scripts.
    
    This class provides a common framework for Snowflake COPY INTO operations, eliminating
    the code duplication found across IDR export files. Each subclass needs only to implement
    getSelectQuery() with their specific SELECT statement.
    
    Attributes:
        version_number (str): Version identifier used in output filename. Defaults to "v01".
    
    Example:
        class MyExporter(IDROutputter):
            version_number = "v02"
            
            def getSelectQuery(self):
                return "SELECT * FROM my_table"
        
        exporter = MyExporter()
        exporter.do_idr_output(file_name_stub="my_export")
    """
    
    # Class properties with defaults
    version_number: str = "v01"
    file_name_stub: str = ""  # Must be overridden by subclass
    
    @staticmethod
    def _execute_export(*, select_query: str, file_name_stub: str, version_number: str, filename_components: list[str] | None = None) -> dict:
        """
        Static method that accepts a SELECT query and file name stub, performs the output.
        Puts SELECT query into COPY INTO {some_file_name} FROM ( {select_query} ) string
        and executes the query in the same manner as performed in the existing files.
        
        Args:
            select_query: The SQL SELECT query to export
            file_name_stub: Base filename
            version_number: Version identifier
            filename_components: Optional additional components for filename
        
        Returns:
            dict: Export details including row count, file name, etc.
        """
        try:
            # Import snowflake only when actually needed for execution
            from snowflake.snowpark.context import get_active_session  # type: ignore
            session = get_active_session()
            ts = datetime.now().strftime("%Y_%m_%d_%H%M")
            
            # Build filename with optional components
            filename_parts = [file_name_stub]
            if filename_components:
                filename_parts.extend(filename_components)
            filename_parts.extend([version_number, ts])
            
            file_name = f"@~/{'.'.join(filename_parts)}.csv"
            
            copy_into_sql = f"""
COPY INTO {file_name}
FROM (
{select_query}
)""" + """
FILE_FORMAT = (
  TYPE = CSV
  FIELD_DELIMITER = ','
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  COMPRESSION = NONE
)
HEADER = TRUE
OVERWRITE = TRUE;
"""
            
            print(f"Starting export for {file_name_stub} to {file_name}")
            copy_result = session.sql(copy_into_sql).collect()
            print(f"Successfully completed export for {file_name_stub}")
            
            # Extract export details from the COPY command result
            export_details = {
                'file_name': file_name,
                'file_name_stub': file_name_stub,
                'version_number': version_number,
                'timestamp': ts,
                'rows_exported': 0,
                'status': 'SUCCESS'
            }
            
            # Parse the COPY INTO result to get row count
            if copy_result and len(copy_result) > 0:
                # The COPY INTO command typically returns a result with the file name and rows copied
                result_row = copy_result[0]
                if hasattr(result_row, '__getitem__') and len(result_row) > 1:
                    # Try to extract rows from the result (usually in the second column)
                    try:
                        export_details['rows_exported'] = int(result_row[1])
                    except (ValueError, IndexError, TypeError):
                        # If we can't parse the row count, try to get it from a different method
                        pass
            
            # If we couldn't get row count from COPY result, try counting the source query
            if export_details['rows_exported'] == 0:
                try:
                    count_query = f"SELECT COUNT(*) FROM ({select_query})"
                    count_result = session.sql(count_query).collect()
                    if count_result and len(count_result) > 0:
                        export_details['rows_exported'] = int(count_result[0][0])
                except Exception as count_error:
                    print(f"Warning: Could not determine row count - {str(count_error)}")
                    export_details['rows_exported'] = "Unknown"
            
            return export_details
            
        except Exception as e:
            print(f"IDROutputter._execute_export Error: Failed to export {file_name_stub}")
            print(f"Error details: {str(e)}")
            print(f"This could be due to invalid SQL syntax, connection issues, or permission problems")
            raise
    
    @abstractmethod
    def getSelectQuery(self) -> str:
        """
        Must-override method that each subclass must implement to return the SELECT query string.
        """
        pass
    
    def pre_export_validation(self) -> None:
        """
        Hook method that subclasses can override to perform custom validation before export.
        Called before any export operations begin.
        """
        pass
    
    def get_filename_components(self) -> list[str]:
        """
        Hook method that subclasses can override to add custom components to the filename.
        
        Returns:
            list[str]: Additional filename components to insert between file_name_stub and version.
                      Components will be joined with dots.
        
        Default implementation returns empty list for standard filename format:
        {file_name_stub}.{version_number}.{timestamp}.csv
        
        Override to customize filename format, e.g.:
        {file_name_stub}.{custom_component}.{version_number}.{timestamp}.csv
        """
        return []
        
    def do_idr_output(self) -> None:
        """
        Main method that calls getSelectQuery() to get the query string 
        and then passes that query to the static class method to perform the output.
        
        Displays export details including row count and file information after completion.
        
        Uses the file_name_stub class property which must be overridden by subclass.
        """
        try:
            # Validate that file_name_stub has been set by subclass
            if not self.file_name_stub or not self.file_name_stub.strip():
                raise ValueError(
                    f"file_name_stub class property must be set by subclass {self.__class__.__name__}. "
                    f"Set file_name_stub = 'your_filename_here' in your class definition."
                )
            
            print(f"do_idr_output: Starting process for {self.file_name_stub} (version {self.version_number})")
            
            # Call pre-export validation hook for custom validation
            self.pre_export_validation()
            
            # Call getSelectQuery() method to get the query string
            select_query = self.getSelectQuery()
            
            if not select_query or not select_query.strip():
                raise ValueError("getSelectQuery() returned empty or null query")
            
            # Get custom filename components from hook
            filename_components = self.get_filename_components()
            
            # Pass the query to the static class method to perform the output and get details
            export_details = self._execute_export(
                select_query=select_query, 
                file_name_stub=self.file_name_stub,
                version_number=self.version_number,
                filename_components=filename_components if filename_components else None
            )
            
            print(f"do_idr_output: Completed process for {self.file_name_stub}")
            
            # Display export details
            print("\n" + "=" * 50)
            print("EXPORT DETAILS")
            print("=" * 50)
            print(f"File exported: {export_details['file_name']}")
            print(f"Export stub: {export_details['file_name_stub']}")
            print(f"Version: {export_details['version_number']}")
            print(f"Timestamp: {export_details['timestamp']}")
            print(f"Rows exported: {export_details['rows_exported']:,}" if isinstance(export_details['rows_exported'], int) else f"Rows exported: {export_details['rows_exported']}")
            print(f"Status: {export_details['status']}")
            print("=" * 50)
            print("\nTo download use:")
            print('snowsql -c cms_idr -q "GET @~/ file://. PATTERN=\'*.csv\';"')
            print("Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh")
            
        except Exception as e:
            print(f"IDROutputter.do_idr_output Error: Failed to complete output for {self.file_name_stub if hasattr(self, 'file_name_stub') and self.file_name_stub else '[file_name_stub not set]'}")
            print(f"Error details: {str(e)}")
            print(f"Check your getSelectQuery() implementation, file_name_stub property, and Snowflake connection")
            raise
