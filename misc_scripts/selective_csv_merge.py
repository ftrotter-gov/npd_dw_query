#!/usr/bin/env python3
"""
Selective CSV Merge Tool for Snowflake Downloads

Allows users to selectively merge individual CSV file groups from the unmerged_csv_files
directory, enabling parallel processing by choosing specific files to merge.

This tool:
- Scans unmerged_csv_files directory for CSV part files
- Groups files by root name and filters incomplete sets
- Only shows unmerged file groups as options
- Provides interactive numbered selection interface
- Reuses existing merge logic with validation
"""

import os
import glob
import re
import pandas as pd
import sys
from collections import defaultdict
from pathlib import Path

# Import merge functionality from existing script
sys.path.append(os.path.dirname(__file__))
from snowflake_csv_merge import group_files, merge_group, print_red_warning, detect_duplicate_columns


class FileGroupScanner:
    """Scans and validates CSV part files in the unmerged directory"""
    
    @staticmethod
    def scan_unmerged_directory(*, unmerged_dir):
        """
        Scan directory for CSV files and return grouped file sets
        
        Args:
            unmerged_dir: Path to directory containing CSV part files
            
        Returns:
            dict: Groups of files keyed by root name
        """
        if not os.path.isdir(unmerged_dir):
            raise FileNotFoundError(f"Unmerged directory does not exist: {unmerged_dir}")
        
        # Look for all csv/csv.gz files
        csv_pattern = os.path.join(unmerged_dir, "*.csv")
        gz_pattern = os.path.join(unmerged_dir, "*.csv.gz")
        files = glob.glob(csv_pattern) + glob.glob(gz_pattern)
        
        if not files:
            return {}
        
        return group_files(files)

    @staticmethod 
    def filter_incomplete_sets(*, file_groups):
        """
        Filter out incomplete file sets (single parts only)
        
        Args:
            file_groups: Dict of file groups from group_files()
            
        Returns:
            dict: File groups with only complete sets (multiple parts)
        """
        complete_groups = {}
        for root_name, file_list in file_groups.items():
            if len(file_list) > 1:  # Only keep groups with multiple parts
                complete_groups[root_name] = file_list
        
        return complete_groups


class MergeStatusChecker:
    """Checks which file groups have already been merged"""
    
    @staticmethod
    def get_unmerged_groups(*, file_groups, output_dir):
        """
        Filter file groups to only those that haven't been merged yet
        
        Args:
            file_groups: Dict of available file groups
            output_dir: Directory where merged files are stored
            
        Returns:
            dict: File groups that don't have corresponding merged files
        """
        unmerged_groups = {}
        
        for root_name, file_list in file_groups.items():
            # Ensure we don't create double .csv extensions
            output_filename = f"{root_name}.csv" if not root_name.endswith('.csv') else root_name
            merged_file_path = os.path.join(output_dir, output_filename)
            
            if not os.path.exists(merged_file_path):
                unmerged_groups[root_name] = file_list
        
        return unmerged_groups


class InteractiveCLI:
    """Handles interactive user selection interface"""
    
    @staticmethod
    def _get_file_size_info(*, file_list):
        """
        Get size information for a list of files
        
        Args:
            file_list: List of file paths
            
        Returns:
            tuple: (total_size_bytes, formatted_size_string)
        """
        total_size = 0
        for file_path in file_list:
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)
        
        # Format size for display
        if total_size < 1024:
            size_str = f"{total_size} B"
        elif total_size < 1024 * 1024:
            size_str = f"{total_size / 1024:.1f} KB"
        elif total_size < 1024 * 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{total_size / (1024 * 1024 * 1024):.1f} GB"
            
        return total_size, size_str

    @staticmethod
    def display_available_groups(*, unmerged_groups):
        """
        Display numbered list of available file groups with size information
        
        Args:
            unmerged_groups: Dict of unmerged file groups
            
        Returns:
            list: Ordered list of group names for selection
        """
        if not unmerged_groups:
            print("\n No unmerged CSV file groups found.")
            print(" All available file groups have already been merged.")
            return []
        
        print(f"\n Found {len(unmerged_groups)} unmerged file groups:")
        print(" " + "=" * 70)
        
        group_list = list(unmerged_groups.keys())
        
        for i, group_name in enumerate(group_list, 1):
            file_count = len(unmerged_groups[group_name])
            _, size_str = InteractiveCLI._get_file_size_info(file_list=unmerged_groups[group_name])
            print(f" {i:2d}. {group_name} ({file_count} parts, {size_str})")
        
        print(" " + "=" * 70)
        return group_list

    @staticmethod
    def get_user_selection(*, group_list):
        """
        Get and validate user selection with confirmation
        
        Args:
            group_list: List of available group names
            
        Returns:
            str: Selected group name, or None if cancelled
        """
        if not group_list:
            return None
        
        while True:
            try:
                print(f"\n Enter selection (1-{len(group_list)}), 'q' to quit, or 'h' for help: ", end='')
                user_input = input().strip()
                
                if user_input.lower() == 'q':
                    print(" Cancelled by user.")
                    return None
                    
                if user_input.lower() == 'h':
                    print("\n Help:")
                    print(" - Enter a number (1-{}) to select a file group to merge".format(len(group_list)))
                    print(" - Enter 'q' to quit the program")
                    print(" - Enter 'h' to show this help message")
                    print(" - The tool will merge all parts of the selected group into a single CSV")
                    continue
                
                selection = int(user_input)
                
                if 1 <= selection <= len(group_list):
                    selected_group = group_list[selection - 1]
                    
                    # Show confirmation with details
                    print(f"\n Selected: {selected_group}")
                    print(f" Proceed with merging this file group? (y/N): ", end='')
                    confirm = input().strip().lower()
                    
                    if confirm in ['y', 'yes']:
                        return selected_group
                    else:
                        print(" Selection cancelled, please choose again.")
                        continue
                else:
                    print(f" Invalid selection. Please enter 1-{len(group_list)}, 'q', or 'h'")
                    
            except ValueError:
                print(" Invalid input. Please enter a number, 'q', or 'h'")
            except KeyboardInterrupt:
                print("\n\n Cancelled by user.")
                return None


class SelectiveMergeProcessor:
    """Processes the merge operation for selected file group"""
    
    @staticmethod
    def merge_selected_group(*, group_name, file_list, output_dir):
        """
        Merge the selected file group using existing merge logic
        
        Args:
            group_name: Name of the file group
            file_list: List of files to merge
            output_dir: Output directory for merged file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"\n Processing merge for: {group_name}")
            print(f" Input files: {len(file_list)} parts")
            print(f" Output directory: {output_dir}")
            print(" " + "-" * 50)
            
            # Use existing merge_group function
            merge_group(group_name, file_list, outdir=output_dir)
            
            # Ensure we don't create double .csv extensions
            output_filename = f"{group_name}.csv" if not group_name.endswith('.csv') else group_name
            output_file = os.path.join(output_dir, output_filename)
            
            if os.path.exists(output_file):
                print(f" ✓ Successfully created: {output_file}")
                return True
            else:
                print(f" ✗ Failed to create output file: {output_file}")
                return False
                
        except Exception as e:
            print(f" ✗ Error during merge: {str(e)}")
            return False


def main():
    """Main entry point for selective CSV merge tool"""
    
    # Define directory paths (matching existing bash script structure)
    base_dir = os.path.expanduser("~/cms_data_downloads_possible_pii/idr_data")
    unmerged_dir = os.path.join(base_dir, "unmerged_csv_files")
    output_dir = base_dir
    
    print("Selective CSV Merge Tool")
    print("=" * 50)
    print(f"Scanning: {unmerged_dir}")
    print(f"Output to: {output_dir}")
    
    try:
        # Step 1: Scan for CSV part files
        all_file_groups = FileGroupScanner.scan_unmerged_directory(unmerged_dir=unmerged_dir)
        
        if not all_file_groups:
            print(f"\n No CSV files found in: {unmerged_dir}")
            return 1
        
        print(f"\n Found {len(all_file_groups)} total file groups")
        
        # Step 2: Filter out incomplete sets
        complete_groups = FileGroupScanner.filter_incomplete_sets(file_groups=all_file_groups)
        skipped_count = len(all_file_groups) - len(complete_groups)
        
        if skipped_count > 0:
            print(f" Skipped {skipped_count} incomplete file groups")
        
        if not complete_groups:
            print(" No complete file groups available for merging.")
            return 1
        
        # Step 3: Check merge status
        unmerged_groups = MergeStatusChecker.get_unmerged_groups(
            file_groups=complete_groups, 
            output_dir=output_dir
        )
        
        already_merged = len(complete_groups) - len(unmerged_groups)
        if already_merged > 0:
            print(f" Skipped {already_merged} already-merged file groups")
        
        # Step 4: Display selection interface
        group_list = InteractiveCLI.display_available_groups(unmerged_groups=unmerged_groups)
        
        if not group_list:
            return 0
        
        # Step 5: Get user selection
        selected_group = InteractiveCLI.get_user_selection(group_list=group_list)
        
        if not selected_group:
            return 0
        
        # Step 6: Process the merge
        success = SelectiveMergeProcessor.merge_selected_group(
            group_name=selected_group,
            file_list=unmerged_groups[selected_group],
            output_dir=output_dir
        )
        
        if success:
            print(f"\n ✓ Merge completed successfully for: {selected_group}")
            return 0
        else:
            print(f"\n ✗ Merge failed for: {selected_group}")
            return 1
            
    except Exception as e:
        print(f"\n Error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main())
