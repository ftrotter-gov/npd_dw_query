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
    Count the number of lines (records, including header) in a CSV file.

    Uses ONE consistent, byte-accurate method for both .csv and .csv.gz:
    count newline bytes, then add 1 if the file is non-empty and does NOT end
    with a trailing newline (that final partial line is still a record).

    The previous implementation used `wc -l` for plain files (counts '\n'
    bytes) but `len(stdout.strip().split('\n'))` for gzip (counts segments).
    Those two methods disagree by one on a file whose last line has no
    trailing newline, which could either mask a real truncation or trip a
    false "row count mismatch". This single path removes that inconsistency.

    Streams in 1 MiB chunks, so memory is constant regardless of file size.
    """
    opener = gzip.open if filepath.endswith('.gz') else open
    newline_count = 0
    last_byte = b''
    with opener(filepath, 'rb') as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            newline_count += chunk.count(b'\n')
            last_byte = chunk[-1:]
    if last_byte not in (b'\n', b''):
        newline_count += 1  # non-empty file with no trailing newline
    return newline_count


def _file_ends_with_newline(path):
    """Return True if the file is empty or its last byte is '\\n'."""
    with open(path, 'rb') as f:
        if f.seek(0, os.SEEK_END) == 0:
            return True  # empty file — nothing to guard against
        f.seek(-1, os.SEEK_END)
        return f.read(1) == b'\n'


def count_csv_records(filepath):
    """
    Count LOGICAL CSV records (rows as a real CSV parser sees them) and check
    column consistency.

    Unlike count_csv_lines() — which counts physical '\\n' bytes — this treats a
    quoted field containing embedded newlines/commas as ONE record, matching
    how Snowflake unloads with FIELD_OPTIONALLY_ENCLOSED_BY='"'. Physical-line
    counting silently miscounts such rows; logical-record counting is what
    actually proves no row was dropped, split, or merged.

    Returns (total_records_incl_header, num_columns, first_bad_row) where
    first_bad_row is None, or (record_number, got_fields, expected_fields) for
    the first row whose field count differs from the header. Streams one row at
    a time — constant memory regardless of file size.
    """
    opener = gzip.open if filepath.endswith('.gz') else open
    with opener(filepath, 'rt', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return 0, 0, None
        ncols = len(header)
        total = 1
        first_bad = None
        for row in reader:
            total += 1
            if len(row) != ncols and first_bad is None:
                first_bad = (total, len(row), ncols)
        return total, ncols, first_bad


def deep_validate_records(outname, files, expected_headers):
    """
    Strongest anti-data-gap check. Parse the merged output AND every source
    part as real CSV (honouring quotes / embedded newlines) and verify:
      • the merged header column count matches the source header,
      • every row in the merged file has exactly len(header) columns,
      • every row in every source part has exactly len(header) columns,
      • sum of source DATA records == merged DATA records (nothing lost/added).

    This catches gaps the physical-line arithmetic cannot: a row swallowed
    inside a mis-quoted field, a truncated/ragged row, or an embedded-newline
    row that would otherwise be miscounted.

    Raises ValueError on any discrepancy. Returns the merged data-record count.
    """
    print("  Deep validation (logical CSV records + column consistency)...")
    ncols_expected = len(expected_headers)

    merged_total, merged_cols, merged_bad = count_csv_records(outname)
    if merged_total == 0:
        raise ValueError(f"Deep check FAILED: merged output {outname} has no rows at all")
    if merged_cols != ncols_expected:
        raise ValueError(
            f"Deep check FAILED: merged header has {merged_cols} columns, "
            f"source header has {ncols_expected}"
        )
    if merged_bad:
        rownum, got, want = merged_bad
        raise ValueError(
            f"Deep check FAILED: ragged row in merged output {outname} — record "
            f"{rownum} has {got} fields, expected {want} "
            f"(data gap / corruption / bad quoting)"
        )

    total_source_data = 0
    empty_parts = []
    for f in files:
        rec_total, rec_cols, rec_bad = count_csv_records(f)
        if rec_cols != ncols_expected:
            raise ValueError(
                f"Deep check FAILED: source part {f} has {rec_cols} columns, "
                f"expected {ncols_expected}"
            )
        if rec_bad:
            rownum, got, want = rec_bad
            raise ValueError(
                f"Deep check FAILED: ragged row in source part {f} — record "
                f"{rownum} has {got} fields, expected {want}"
            )
        data_records = rec_total - 1  # minus header
        if data_records == 0:
            empty_parts.append(os.path.basename(f))
        total_source_data += data_records

    merged_data = merged_total - 1
    if merged_data != total_source_data:
        diff = merged_data - total_source_data
        raise ValueError(
            f"Deep check FAILED: record-count GAP — source parts hold "
            f"{total_source_data:,} data records but merged file has "
            f"{merged_data:,} ({diff:+,}). Rows were lost or duplicated."
        )

    if empty_parts:
        print(f"  ⚠ {len(empty_parts)} part(s) contained 0 data rows: "
              f"{empty_parts[:5]}{' ...' if len(empty_parts) > 5 else ''}")
    print(f"  ✓ Deep validation passed: {merged_data:,} logical records, "
          f"every row has {ncols_expected} columns, no rows lost")
    return merged_data

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

def merge_group(root, files, outdir=".", deep_validate=True):
    """
    Merge multiple CSV files efficiently using CLI tools.
    Validates headers match across all files, then uses cat/tail for fast merging.

    When deep_validate is True (default) a full logical-record + column
    consistency pass runs after the merge to guarantee no data gaps.
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
    
    # Write the first file completely (includes header).
    # Stream to disk — never read the whole file into a Python string. The old
    # code did out_file.write(tail_proc.stdout.read()), which buffered the
    # ENTIRE part in RAM; a multi-GB part needed multi-GB of memory and could
    # OOM on exactly the large tables this tool exists to merge. Redirecting
    # the child's stdout straight to the file lets the kernel stream it.
    first_file = files[0]
    if first_file.endswith('.gz'):
        # Decompress first file straight to output (streamed)
        with open(outname, 'wb') as f_out:
            subprocess.run(['gunzip', '-c', first_file], stdout=f_out, check=True)
    else:
        # Copy first file to output (cp streams natively)
        subprocess.run(['cp', first_file, outname], check=True)

    # Append remaining files without their headers
    for idx, f in enumerate(files[1:], start=2):
        # Guard: if the current output does not end in a newline, the next
        # part's first data row would be concatenated onto the previous last
        # row. Snowflake normally terminates the final record, but this makes
        # the merge robust to a part that does not.
        if not _file_ends_with_newline(outname):
            with open(outname, 'ab') as out_file:
                out_file.write(b'\n')

        with open(outname, 'ab') as out_file:
            if f.endswith('.gz'):
                # gunzip -c file.csv.gz | tail -n +2 >> output.csv   (streamed)
                gunzip_proc = subprocess.Popen(['gunzip', '-c', f],
                                               stdout=subprocess.PIPE)
                tail_proc = subprocess.Popen(['tail', '-n', '+2'],
                                             stdin=gunzip_proc.stdout,
                                             stdout=out_file)
                gunzip_proc.stdout.close()  # allow gunzip to get SIGPIPE
                tail_rc = tail_proc.wait()
                gunzip_rc = gunzip_proc.wait()
                if gunzip_rc != 0 or tail_rc != 0:
                    raise RuntimeError(
                        f"Failed to append {f} "
                        f"(gunzip exit={gunzip_rc}, tail exit={tail_rc})"
                    )
            else:
                # tail -n +2 file.csv >> output.csv   (streamed)
                subprocess.run(['tail', '-n', '+2', f], stdout=out_file, check=True)

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

    # ── Series of final post-merge integrity checks ─────────────────────────
    # Row-count arithmetic above proves totals line up; these checks prove the
    # merged file is actually well-formed before anything uploads it.
    print("  Running final post-merge checks...")

    # (a) Output exists and is non-empty
    if not os.path.exists(outname) or os.path.getsize(outname) == 0:
        raise ValueError(f"Final check FAILED: merged output {outname} is missing or empty")

    # (b) Merged header matches the validated source header exactly
    merged_header = get_csv_header(outname)
    if merged_header != expected_headers:
        raise ValueError(
            f"Final check FAILED: merged header does not match source header!\n"
            f"Expected: {expected_headers}\nGot: {merged_header}"
        )

    # (c) Merged file ends with a newline (final record is well-formed)
    if not _file_ends_with_newline(outname):
        raise ValueError(
            f"Final check FAILED: merged output {outname} does not end with a newline"
        )

    # NOTE: an earlier "the header line must appear EXACTLY once" check was
    # removed. It grepped the whole file for the header STRING (grep -F -x),
    # which false-failed on two legitimate inputs:
    #   • a real data row that serializes to exactly the header line
    #     (e.g. a code column whose value equals a column name) → counted as a
    #     second header → abort on valid data; and
    #   • CRLF line endings → the CR-stripped header never matches the whole
    #     line → counted as zero → abort.
    # A leaked/un-stripped header is a DATA-COUNT problem, and that is caught
    # precisely (no false positives) by deep_validate_records below: if a header
    # survived into the body, merged data-records would exceed the sum of source
    # data-records. Phase-1 header validation + check (b) cover the rest.

    print(f"  ✓ Final checks passed: non-empty, header matches source, "
          f"well-formed trailing newline")

    # ── Deep validation: logical records + column consistency (no data gaps) ─
    if deep_validate:
        deep_validate_records(outname, files, expected_headers)
    else:
        print("  ⚠ Deep validation SKIPPED (--no-deep-validate) — "
              "physical-line checks only")
    
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
    parser.add_argument(
        "--no-deep-validate",
        dest="deep_validate",
        action="store_false",
        default=True,
        help="Skip the logical-record + column-consistency validation pass "
             "(faster on very large trusted tables; physical-line checks still run)"
    )

    args = parser.parse_args()
    
    # Validate directory exists
    if not os.path.isdir(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist")
        return 1
    
    # Set output directory (create it if it does not exist)
    output_dir = args.output_dir if args.output_dir else args.directory
    os.makedirs(output_dir, exist_ok=True)
    
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
        merge_group(root, flist, outdir=output_dir,
                    deep_validate=args.deep_validate)
    
    print("\n✓ Merge process completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())
