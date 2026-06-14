# Selective CSV Merge Tool

The Selective CSV Merge Tool (`selective_csv_merge.py`) replaces the original batch processing script to enable parallel processing. Instead of merging all CSV file groups at once, users can selectively choose individual file groups to merge. This allows multiple instances to run simultaneously on different file groups, dramatically improving processing efficiency.

The tool scans `~/cms_data_downloads_possible_pii/idr_data/unmerged_csv_files/` for CSV part files, groups them by root name (e.g., `provider_data_0_0_0.csv` → `provider_data`), and only shows unmerged file groups as options. It skips incomplete sets (single-part files) and already-merged files. The interactive interface displays file counts and sizes, with confirmation prompts for safety. Simply run `python3 selective_csv_merge.py` and select from the numbered list of available file groups to merge.
