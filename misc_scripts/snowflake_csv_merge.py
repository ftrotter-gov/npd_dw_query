#!/usr/bin/env python3
"""
Written by ChatGPT in response to: 

I am going to have multiple different file patterns that I am downloading in this manner. 
Please write my a python script that will merge everything that has the same "root" 
from snowflakes download in the same directory. 

Cline used to add command line arguments afterwards. 

Optimized version by Cline to use CLI tools (cat/tail) instead of pandas for massive
performance improvement when merging hundreds of files.
"""
import os
import glob
import re
import csv
import argparse
from collections import defaultdict
import sys
import subprocess
import gzip

def print_red_warning(message):
    """
    Print a big red warning message to stderr
    """
    red_color = '\033[91m'  # ANSI red color code
    bold = '\033[1m'        # ANSI bold
    reset = '\033[0m'       # ANSI reset
    
    warning_box = f"""
{red_color}{bold}{'='*80}
🚨 WARNING: DUPLICATE COLUMN NAMES DETECTED! 🚨
{'='*80}{reset}

{red_color}{message}{reset}

{red_color}{bold}{'='*80}
This indicates your source CSV files have duplicate column headers.
Please check your source data for duplicate column names!
{'='*80}{reset}
"""
    print(warning_box, file=sys.stderr, flush=True)

def detect_duplicate_columns(column_list):
    """
    Check if any columns have pandas auto-generated suffixes (.1, .2, etc.)
    Returns list of problematic columns
    """
    duplicate_columns = []
    seen = set()
    for col in column_list:
        if col in seen:
            duplicate_columns.append(col)
        seen.add(col)
        # Also check for numbered suffixes pattern
        if re.search(r'\.\d+$', str(col)):
            duplicate_columns.append(col)
    return duplicate_columns

def get_csv_header(filepath):
    """
    Efficiently read just the header (first line) from a CSV file.
    Handles both .csv and .csv.gz files.
    Returns list of column names.
    """
    if filepath.endswith('.gz'):
        with gzip.open(filepath, 'rt', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            return header
    else:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            return header

def count_csv_lines(filepath):
    """
    Count lines in a CSV file (including header).
    Handles both .csv and .csv.gz files.
    """
    if filepath.endswith('.gz'):
        result = subprocess.run(
            ['gunzip', '-c', filepath],
            capture_output=True,
            text=True
        )
        return len(result.stdout.strip().split('\n')) if result.stdout else 0
    else:
        result = subprocess.run(
            ['wc', '-l', filepath],
            capture_output=True,
            text=True
        )
        return int(result.stdout.strip().split()[0])

def group_files(files):
    """
    Group files by their root before the Snowflake part suffix (_0_0_0, etc.).
    E.g. 'foo_0_0_0.csv' and 'foo_0_0_1.csv' -> root 'foo'
    Also handles 'foo.csv_0_0_0.csv' -> root 'foo'
    """
    groups = defaultdict(list)
    for f in files:
        base = os.path.basename(f)
        # strip compression extension first
        if base.endswith(".gz"):
            base = base[:-3]
        if base.endswith(".csv"):
            base = base[:-4]

        # remove the trailing Snowflake suffix if present
        root = re.sub(r'(_\d+_\d+_\d+)$', '', base)
        
        # Handle case where root already ends with .csv (from files like filename.csv_0_0_0.csv)
        if root.endswith('.csv'):
            root = root[:-4]
        
        groups[root].append(f)
    return groups

def merge_group(root, files, outdir="."):
    """
    Merge multiple CSV files efficiently using CLI tools.
    Validates headers match across all files, then uses cat/tail for fast merging.
    """
    # Sort files so order is consistent
    files = sorted(files)

    outname = os.path.join(outdir, f"{root}.csv")
    print(f"Merging {len(files)} files into {outname}")

    # Phase 1: Validate all headers match (fast - only reads first line of each file)
    print("  Validating headers...")
    expected_headers = get_csv_header(files[0])
    
    # Check for duplicate column indicators in the first file
    duplicate_cols = detect_duplicate_columns(expected_headers)
    if duplicate_cols:
        warning_msg = f"""
File: {files[0]}
Problematic columns detected: {duplicate_cols}

This suggests duplicate column names exist in your source CSV files.
"""
        print_red_warning(warning_msg)
    
    # Validate all other files have matching headers
    for f in files[1:]:
        file_headers = get_csv_header(f)
        
        # Check for duplicate column indicators in this file too
        file_duplicate_cols = detect_duplicate_columns(file_headers)
        if file_duplicate_cols and file_duplicate_cols != duplicate_cols:
            warning_msg = f"""
File: {f}
Additional problematic columns detected: {file_duplicate_cols}

This file has different duplicate column patterns than the first file.
"""
            print_red_warning(warning_msg)
        
        # Validate headers match exactly
        if file_headers != expected_headers:
            raise ValueError(f"Header mismatch in file {f}.\nExpected: {expected_headers}\nGot: {file_headers}")
    
    print(f"  ✓ All {len(files)} files have matching headers")
    
    # Phase 2: Fast merge using CLI tools
    print("  Merging data...")
    
    # Write the first file completely (includes header)
    first_file = files[0]
    if first_file.endswith('.gz'):
        # Decompress first file to output
        with gzip.open(first_file, 'rt') as f_in, open(outname, 'w') as f_out:
            f_out.write(f_in.read())
    else:
        # Copy first file to output
        subprocess.run(['cp', first_file, outname], check=True)
    
    # Append remaining files without their headers
    for idx, f in enumerate(files[1:], start=2):
        if f.endswith('.gz'):
            # Decompress, skip header, append
            # gunzip -c file.csv.gz | tail -n +2 >> output.csv
            with subprocess.Popen(['gunzip', '-c', f], stdout=subprocess.PIPE) as gunzip_proc:
                with subprocess.Popen(['tail', '-n', '+2'], 
                                    stdin=gunzip_proc.stdout, 
                                    stdout=subprocess.PIPE,
                                    text=True) as tail_proc:
                    with open(outname, 'a') as out_file:
                        out_file.write(tail_proc.stdout.read())
        else:
            # Skip header line (line 1), append rest
            # tail -n +2 file.csv >> output.csv
            with subprocess.Popen(['tail', '-n', '+2', f], 
                                stdout=subprocess.PIPE,
                                text=True) as tail_proc:
                with open(outname, 'a') as out_file:
                    out_file.write(tail_proc.stdout.read())
        
        # Show progress - print a dot every 10 files
        if idx % 10 == 0:
            print('.', end='', flush=True)
    
    # Add newline after progress dots if any were printed
    if len(files) > 10:
        print()
    
    # Verify row count is correct
    print("  Verifying row count...")
    
    # Count lines in each input file
    input_line_counts = []
    for f in files:
        line_count = count_csv_lines(f)
        input_line_counts.append(line_count)
    
    # Expected: sum of all input rows - (num_files - 1) for removed headers
    # OR equivalently: sum of all input rows - num_files + 1
    expected_total_lines = sum(input_line_counts) - len(files) + 1
    
    # Count actual lines in output
    actual_total_lines = count_csv_lines(outname)
    
    # Verify they match
    if actual_total_lines != expected_total_lines:
        raise ValueError(
            f"Row count mismatch!\n"
            f"Expected: {expected_total_lines:,} lines (including header)\n"
            f"Actual: {actual_total_lines:,} lines\n"
            f"Input files had: {sum(input_line_counts):,} total lines\n"
            f"After removing {len(files) - 1} extra headers, should have: {expected_total_lines:,} lines"
        )
    
    total_data_rows = actual_total_lines - 1  # Subtract header
    print(f"  ✓ Successfully merged {len(files)} files with {total_data_rows:,} total data rows")
    print(f"  ✓ Row count verified: {actual_total_lines:,} lines (including header)")
    
    # Final warning if duplicates were detected
    if duplicate_cols:
        warning_msg = f"""
Final merged file: {outname}
Final problematic columns: {duplicate_cols}

The merged output contains duplicate or problematic column names.
Review your source data to eliminate duplicate column names.
"""
        print_red_warning(warning_msg)

def main():
    parser = argparse.ArgumentParser(
        description="Merge CSV files with the same root name from Snowflake downloads"
    )
    parser.add_argument(
        "directory", 
        help="Directory location containing CSV files to merge"
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for merged files (defaults to input directory)",
        default=None
    )
    
    args = parser.parse_args()
    
    # Validate directory exists
    if not os.path.isdir(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist")
        return 1
    
    # Set output directory
    output_dir = args.output_dir if args.output_dir else args.directory
    
    # Look for all csv/csv.gz files in specified directory
    csv_pattern = os.path.join(args.directory, "*.csv")
    gz_pattern = os.path.join(args.directory, "*.csv.gz")
    files = glob.glob(csv_pattern) + glob.glob(gz_pattern)
    
    if not files:
        print(f"No CSV files found in directory: {args.directory}")
        return 1
    
    print(f"Found {len(files)} CSV files in {args.directory}")
    groups = group_files(files)
    
    print(f"Identified {len(groups)} file groups to merge")
    for root, flist in groups.items():
        merge_group(root, flist, outdir=output_dir)
    
    print("\n✓ Merge process completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())
