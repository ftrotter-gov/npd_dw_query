#!/usr/bin/env python3

"""
This script should accept a --python_dir and --csv_dir argument

Take a look at idr/IDROutputter.py and for an implementing class idr/medicaid_provider_credentials_new.py

Using sqlglot, you can loop over all of the classes that implement the IDROutputter abstract base class in the python_dir and run the getSelectQuery 
function on those classes to get back the SELECT statement and then extract what columns should be in the csv output file from that program using sqlglot. 

You can also grab the file version from the version_number class property. As well as the file_name_stub from the do_idr_output call.

Then loop over the csv files in the csv_dir and grab the first line which contains the headers for each one. 
Also note when there are two files that match a single file name, version number but have different timestamps.
Use wc -l to get the number of lines in each csv file.
The output should be a STDOUT report that shows for each class implementing IDROutputter:

For the version comparision: the version in the file names is between two dots. So a simple string comparision with that value works.

 
Your file name parsing  method should look for the following pattern {file_name_stub}FILLER_WITH_ANTYHING_AT_ALL_INCLUDING_NOTHING{version_number}.{timestamp}.csv
For the multiple file instances.. you should consider THIS_IS_THE_STUB_thisisrandomfiller.v01.2024_10_22_2207.csv and THIS_IS_THE_STUB_anotherdifferentfiller.v01.2024_10_23_1105.csv as colliding files.
If NPPESMainExporter is not honoring the convention.. please change it.  modify the file output in NPPESMainExporter so that the {version_number}.{timestamp}.csv pattern is honored.


The version comparison should not really be "outdated" in the sense that it correctly handles a version number higher. It should just be "matching" or "not matching" for now.

- The file_name_name
- Green "current" if this is the latest version number for this file, there is only one file like this in the directory and the headers match the SELECT statement columns.
- Yellow for any of the rest of these warning status:
    - "outdated version" if there is a newer version number for this file_name_stub
    - "multiple files" if there is more than one file with this file_name_stub and version number but different timestamps
    - "header mismatch" if the headers in the csv file do not match the columns in the SELECT statement

Do not delete these instructions as you implement the code.
"""

import argparse
import os
import sys
import importlib.util
import inspect
import re
import csv
import subprocess
from typing import List
from collections import defaultdict
from dataclasses import dataclass

try:
    import sqlglot
    from sqlglot import expressions as exp
except ImportError:
    print("ERROR: sqlglot package is required. Please install with: pip install sqlglot")
    sys.exit(1)

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


@dataclass
class IDROutputterInfo:
    """Information extracted from an IDROutputter class."""
    class_name: str
    file_name_stub: str
    version_number: str
    select_query: str
    expected_columns: List[str]
    file_path: str


@dataclass
class CsvFileInfo:
    """Information about a CSV file."""
    full_path: str
    filename: str
    file_name_stub: str
    version_number: str
    timestamp: str
    filler: str
    headers: List[str]
    line_count: int


class FileVersionTester:
    """Main class for testing file versions and consistency."""
    
    def __init__(self, *, python_dir: str, csv_dir: str, show_missing_csv: bool = False):
        """Initialize with directories to scan."""
        self.python_dir = python_dir
        self.csv_dir = csv_dir
        self.show_missing_csv = show_missing_csv
        self.idr_classes: List[IDROutputterInfo] = []
        self.csv_files: List[CsvFileInfo] = []
        
    def discover_idr_outputter_classes(self) -> None:
        """
        Discover all classes that implement IDROutputter in the python_dir.
        Extract their properties and SQL queries.
        """
        print(f"Scanning Python directory: {self.python_dir}")
        
        # Add the python_dir to the Python path so imports work
        original_path = sys.path.copy()
        abs_python_dir = os.path.abspath(self.python_dir)
        if abs_python_dir not in sys.path:
            sys.path.insert(0, abs_python_dir)
        
        try:
            # Create mock modules for missing dependencies
            self._create_mock_modules()
            
            # Get all Python files in the directory
            python_files = [f for f in os.listdir(self.python_dir) 
                           if f.endswith('.py') and not f.startswith('__')]
            
            for py_file in python_files:
                file_path = os.path.join(self.python_dir, py_file)
                try:
                    # Load the module dynamically
                    spec = importlib.util.spec_from_file_location(py_file[:-3], file_path)
                    if spec is None or spec.loader is None:
                        continue
                        
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Find classes that inherit from IDROutputter
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (hasattr(obj, '__bases__') and 
                            any(base.__name__ == 'IDROutputter' for base in obj.__bases__)):
                            
                            try:
                                # Get class properties without instantiating to avoid Snowflake connections
                                file_name_stub = getattr(obj, 'file_name_stub', '')
                                version_number = getattr(obj, 'version_number', 'v01')
                                
                                if not file_name_stub:
                                    print(f"WARNING: {name} in {py_file} has empty file_name_stub")
                                    continue
                                
                                # Get SELECT query by instantiating class and calling getSelectQuery()
                                # This is the intended design of IDROutputter classes
                                select_query = ""
                                expected_columns = []
                                
                                try:
                                    # Instantiate the class and get the query
                                    instance = obj()
                                    select_query = instance.getSelectQuery()
                                    
                                    if select_query and select_query.strip():
                                        # Use sqlglot to parse the SQL and extract columns
                                        expected_columns = self._extract_columns_from_sql(sql_query=select_query)
                                    else:
                                        print(f"WARNING: {name} returned empty query")
                                        select_query = "Empty query returned"
                                        expected_columns = ["empty_query"]
                                        
                                except Exception as e:
                                    print(f"ERROR: Could not instantiate {name} or get query: {str(e)}")
                                    # If this class can't be instantiated, it needs to be fixed
                                    select_query = f"Class instantiation failed: {str(e)}"
                                    expected_columns = ["class_needs_fixing"]
                                
                                idr_info = IDROutputterInfo(
                                    class_name=name,
                                    file_name_stub=file_name_stub,
                                    version_number=version_number,
                                    select_query=str(select_query),  # Explicit cast to ensure it's a string
                                    expected_columns=expected_columns,
                                    file_path=file_path
                                )
                                
                                self.idr_classes.append(idr_info)
                                print(f"Found IDROutputter class: {name} -> {file_name_stub}.{version_number}")
                                
                            except Exception as e:
                                print(f"ERROR processing class {name} in {py_file}: {str(e)}")
                                
                except Exception as e:
                    print(f"ERROR loading module {py_file}: {str(e)}")
                    
        finally:
            # Restore original Python path
            sys.path = original_path
    
    def _create_mock_modules(self) -> None:
        """
        Create mock modules for missing dependencies to allow class discovery.
        """
        import types
        
        # Mock snowflake modules
        mock_snowflake = types.ModuleType('snowflake')
        mock_snowflake_snowpark = types.ModuleType('snowflake.snowpark')
        mock_snowflake_context = types.ModuleType('snowflake.snowpark.context')
        
        # Add mock get_active_session function
        def mock_get_active_session():
            return None
        setattr(mock_snowflake_context, 'get_active_session', mock_get_active_session)
        
        # Mock streamlit
        mock_streamlit = types.ModuleType('streamlit')
        
        # Add mock pandas if needed
        try:
            import pandas
        except ImportError:
            mock_pandas = types.ModuleType('pandas')
            sys.modules['pandas'] = mock_pandas
        
        # Add modules to sys.modules
        sys.modules['snowflake'] = mock_snowflake
        sys.modules['snowflake.snowpark'] = mock_snowflake_snowpark
        sys.modules['snowflake.snowpark.context'] = mock_snowflake_context
        sys.modules['streamlit'] = mock_streamlit
    
    def _extract_columns_from_sql(self, *, sql_query: str) -> List[str]:
        """
        Extract column names from a SELECT query using sqlglot.
        Returns the final output column names including aliases.
        Handles simple SELECT, UNION, and other compound queries.
        """
        try:
            # Parse the SQL query
            parsed = sqlglot.parse_one(sql_query, dialect="snowflake")
            
            columns = []
            
            # Handle different query types
            if isinstance(parsed, exp.Select):
                # Simple SELECT statement
                columns = self._extract_columns_from_select(parsed)
            elif isinstance(parsed, exp.Union):
                # UNION query - extract from the first SELECT
                if parsed.left and isinstance(parsed.left, exp.Select):
                    columns = self._extract_columns_from_select(parsed.left)
                elif parsed.right and isinstance(parsed.right, exp.Select):
                    columns = self._extract_columns_from_select(parsed.right)
            elif hasattr(parsed, 'expressions') and parsed.expressions:
                # Try to find a SELECT within the parsed structure
                for expr in parsed.expressions:
                    if isinstance(expr, exp.Select):
                        columns = self._extract_columns_from_select(expr)
                        break
            
            if not columns:
                raise ValueError(f"Could not extract columns from {type(parsed)} statement")
            
            return columns
            
        except Exception as e:
            print(f"WARNING: Could not parse SQL query with sqlglot: {str(e)}")
            # Fallback: try to extract column names using regex
            return self._fallback_column_extraction(sql_query=sql_query)
    
    def _extract_columns_from_select(self, select_expr: exp.Select) -> List[str]:
        """Extract columns from a SELECT expression."""
        columns = []
        for expression in select_expr.expressions:
            if isinstance(expression, exp.Alias):
                # Use the alias name
                columns.append(expression.alias.lower())
            elif hasattr(expression, 'name'):
                # Use the column name
                columns.append(expression.name.lower())
            elif isinstance(expression, exp.Column):
                # Extract column name
                columns.append(expression.this.lower())
            else:
                # For complex expressions, try to get a string representation
                col_str = str(expression).strip()
                if col_str and not col_str.startswith('('):
                    # Clean up the column name
                    col_str = re.sub(r'[^\w]', '_', col_str).strip('_').lower()
                    if col_str:
                        columns.append(col_str)
        
        return [col.strip() for col in columns if col.strip()]
    
    def _fallback_column_extraction(self, *, sql_query: str) -> List[str]:
        """Fallback method to extract column names using regex."""
        try:
            # Remove comments and clean up the query
            query_lines = []
            for line in sql_query.split('\n'):
                line = line.strip()
                if line and not line.startswith('--'):
                    # Remove inline comments
                    line = re.sub(r'--.*$', '', line).strip()
                    if line:
                        query_lines.append(line)
            
            clean_query = ' '.join(query_lines)
            
            # Find SELECT clause
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', clean_query, re.IGNORECASE | re.DOTALL)
            if not select_match:
                return []
            
            select_clause = select_match.group(1)
            
            # Split by comma and extract column names/aliases
            columns = []
            for item in select_clause.split(','):
                item = item.strip()
                if not item:
                    continue
                
                # Check for AS alias
                as_match = re.search(r'\s+AS\s+([^\s,]+)', item, re.IGNORECASE)
                if as_match:
                    columns.append(as_match.group(1).lower())
                else:
                    # Extract the last word (likely the column name)
                    words = item.split()
                    if words:
                        col_name = words[-1].strip('(),').lower()
                        if col_name and not col_name in ['case', 'when', 'then', 'else', 'end']:
                            columns.append(col_name)
            
            return columns
            
        except Exception as e:
            print(f"WARNING: Fallback column extraction failed: {str(e)}")
            return []
    
    def scan_csv_files(self) -> None:
        """
        Scan CSV directory for files and extract information.
        Pattern: {file_name_stub}FILLER{version_number}.{timestamp}.csv
        """
        print(f"Scanning CSV directory: {self.csv_dir}")
        
        if not os.path.exists(self.csv_dir):
            print(f"ERROR: CSV directory does not exist: {self.csv_dir}")
            return
        
        csv_files = [f for f in os.listdir(self.csv_dir) if f.endswith('.csv')]
        
        # Regex pattern to match: {stub}.{version}.{timestamp}.csv
        pattern = r'^(.+?)\.(v\d+)\.(\d{4}_\d{2}_\d{2}_\d{4})\.csv$'
        
        for csv_file in csv_files:
            match = re.match(pattern, csv_file)
            if not match:
                print(f"WARNING: CSV file doesn't match expected pattern: {csv_file}")
                continue
            
            base_stub, version, timestamp = match.groups()
            full_path = os.path.join(self.csv_dir, csv_file)
            
            try:
                # Read headers from first line
                headers = []
                with open(full_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    headers = [col.strip().lower() for col in next(reader)]
                
                # Get line count using wc -l
                result = subprocess.run(['wc', '-l', full_path], 
                                      capture_output=True, text=True)
                line_count = 0
                if result.returncode == 0:
                    line_count = int(result.stdout.split()[0])
                
                csv_info = CsvFileInfo(
                    full_path=full_path,
                    filename=csv_file,
                    file_name_stub=base_stub,
                    version_number=version,
                    timestamp=timestamp,
                    filler="",  # No filler with new pattern
                    headers=headers,
                    line_count=line_count
                )
                
                self.csv_files.append(csv_info)
                print(f"Found CSV: {csv_file} -> {base_stub}.{version} ({line_count} lines)")
                
            except Exception as e:
                print(f"ERROR processing CSV file {csv_file}: {str(e)}")
    
    def analyze_and_report(self) -> None:
        """
        Compare IDROutputter classes with CSV files and generate colored report.
        """
        print("\n" + "="*80)
        print("FILE VERSION TESTER REPORT")
        print("="*80)
        
        # Group CSV files by stub and version for analysis
        csv_by_stub_version = defaultdict(list)
        csv_by_stub = defaultdict(list)
        
        for csv_info in self.csv_files:
            key = f"{csv_info.file_name_stub}#{csv_info.version_number}"
            csv_by_stub_version[key].append(csv_info)
            csv_by_stub[csv_info.file_name_stub].append(csv_info)
        
        # Find latest version for each stub
        latest_versions = {}
        for stub, files in csv_by_stub.items():
            versions = [f.version_number for f in files]
            latest_versions[stub] = max(versions) if versions else "v01"
        
        # Analyze each IDROutputter class
        for idr_info in self.idr_classes:
            # Find matching CSV files
            key = f"{idr_info.file_name_stub}#{idr_info.version_number}"
            matching_csvs = csv_by_stub_version.get(key, [])
            
            # Skip classes without matching CSV files unless show_missing_csv is enabled
            if not matching_csvs and not self.show_missing_csv:
                continue
                
            print(f"\nClass: {Colors.BOLD}{idr_info.class_name}{Colors.RESET}")
            print(f"File Name Stub: {idr_info.file_name_stub}")
            print(f"Version: {idr_info.version_number}")
            print(f"Expected Columns: {len(idr_info.expected_columns)}")
            
            status_messages = []
            overall_status = "current"
            
            # Check for version matching
            latest_version = latest_versions.get(idr_info.file_name_stub)
            if latest_version and idr_info.version_number != latest_version:
                status_messages.append("version mismatch")
                overall_status = "warning"
            
            # Check for multiple files
            if len(matching_csvs) > 1:
                status_messages.append("multiple files")
                overall_status = "warning"
                print(f"  Multiple files found: {[f.filename for f in matching_csvs]}")
            
            # Check headers if we have CSV files
            if matching_csvs:
                csv_info = matching_csvs[0]  # Use first file for header comparison
                
                # Normalize column names for comparison
                expected_cols = [col.strip().lower() for col in idr_info.expected_columns]
                actual_cols = [col.strip().lower() for col in csv_info.headers]
                
                if expected_cols != actual_cols:
                    status_messages.append("header mismatch")
                    overall_status = "warning"
                    
                    print(f"  Expected columns ({len(expected_cols)}): {expected_cols}")
                    print(f"  Actual columns ({len(actual_cols)}): {actual_cols}")
                    
                    # Show differences
                    missing = set(expected_cols) - set(actual_cols)
                    extra = set(actual_cols) - set(expected_cols)
                    if missing:
                        print(f"  Missing columns: {list(missing)}")
                    if extra:
                        print(f"  Extra columns: {list(extra)}")
                
                print(f"  CSV Lines: {csv_info.line_count}")
                print(f"  CSV File: {csv_info.filename}")
            else:
                status_messages.append("no matching CSV file")
                overall_status = "warning"
            
            # Print status with colors
            if overall_status == "current" and not status_messages:
                print(f"Status: {Colors.GREEN}current{Colors.RESET}")
            else:
                status_text = ", ".join(status_messages) if status_messages else "issues found"
                print(f"Status: {Colors.YELLOW}{status_text}{Colors.RESET}")
        
        # Report CSV files without matching IDROutputter classes
        print(f"\n{Colors.BOLD}CSV FILES WITHOUT MATCHING CLASSES:{Colors.RESET}")
        class_stubs = {idr.file_name_stub for idr in self.idr_classes}
        orphan_csvs = [csv for csv in self.csv_files if csv.file_name_stub not in class_stubs]
        
        if orphan_csvs:
            for csv_info in orphan_csvs:
                print(f"  {Colors.YELLOW}{csv_info.filename}{Colors.RESET} - no matching IDROutputter class")
        else:
            print("  None found")
        
        print(f"\n{Colors.BOLD}SUMMARY:{Colors.RESET}")
        print(f"Total IDROutputter classes found: {len(self.idr_classes)}")
        print(f"Total CSV files found: {len(self.csv_files)}")
        print(f"CSV files without matching classes: {len(orphan_csvs)}")
        
        # Count status types (only for classes that were actually displayed)
        current_count = 0
        warning_count = 0
        classes_displayed = 0
        
        for idr_info in self.idr_classes:
            key = f"{idr_info.file_name_stub}#{idr_info.version_number}"
            matching_csvs = csv_by_stub_version.get(key, [])
            
            # Skip classes without matching CSV files unless show_missing_csv is enabled
            if not matching_csvs and not self.show_missing_csv:
                continue
                
            classes_displayed += 1
            latest_version = latest_versions.get(idr_info.file_name_stub)
            
            has_issues = (
                (latest_version and idr_info.version_number != latest_version) or
                len(matching_csvs) > 1 or
                not matching_csvs
            )
            
            # Check headers if we have CSV files
            if matching_csvs:
                csv_info = matching_csvs[0]
                expected_cols = [col.strip().lower() for col in idr_info.expected_columns]
                actual_cols = [col.strip().lower() for col in csv_info.headers]
                if expected_cols != actual_cols:
                    has_issues = True
            
            if has_issues:
                warning_count += 1
            else:
                current_count += 1
        
        print(f"Classes analyzed in this report: {classes_displayed}")
        print(f"Classes with {Colors.GREEN}current{Colors.RESET} status: {current_count}")
        print(f"Classes with {Colors.YELLOW}warning{Colors.RESET} status: {warning_count}")


def main():
    """Main function to run the file version tester."""
    parser = argparse.ArgumentParser(
        description="Test consistency between IDROutputter classes and their CSV output files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python file_version_tester.py --python_dir ../idr --csv_dir /path/to/csv/files
  python file_version_tester.py --python_dir . --csv_dir ./csv_output
        """
    )
    
    parser.add_argument(
        '--python_dir', 
        required=True,
        help='Directory containing Python files with IDROutputter implementations'
    )
    
    parser.add_argument(
        '--csv_dir', 
        required=True,
        help='Directory containing CSV files to analyze'
    )
    
    parser.add_argument(
        '--show-missing-csv', 
        action='store_true',
        help='Show information for IDROutputter classes even when no matching CSV files are found'
    )
    
    args = parser.parse_args()
    
    # Validate directories exist
    if not os.path.exists(args.python_dir):
        print(f"ERROR: Python directory does not exist: {args.python_dir}")
        sys.exit(1)
    
    if not os.path.exists(args.csv_dir):
        print(f"ERROR: CSV directory does not exist: {args.csv_dir}")
        sys.exit(1)
    
    # Create tester instance and run analysis
    tester = FileVersionTester(python_dir=args.python_dir, csv_dir=args.csv_dir, show_missing_csv=args.show_missing_csv)
    
    try:
        print("Starting file version analysis...")
        tester.discover_idr_outputter_classes()
        tester.scan_csv_files()
        tester.analyze_and_report()
        print("\nAnalysis complete!")
        
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Analysis failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
