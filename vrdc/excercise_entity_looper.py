"""
VRDC Entity Looper Usage Demonstration

This file demonstrates how to use the MonthRange and VRDCEntityMapper classes for 
entity-level analysis across multiple medical claims benefit settings.

## Overview

The VRDC Entity Looper provides two main classes:

1. **MonthRange**: Simple container for time ranges using basic arithmetic
   - Handles start_year, start_month, end_year, end_month
   - Provides iteration over months with proper year rollover
   - No complex date libraries - just simple month/year arithmetic

2. **VRDCEntityMapper**: Maps entity identifiers across medical benefit settings
   - Supports 7 benefit settings: bcarrier, dme, inpatient, outpatient, snf, hospice, hha
   - Maps 4 entity levels: tax_id, ccn, organizational_npi, personal_npi
   - Generates ready-to-use SQL with proper database/table naming
   - Database format: rif{year} (e.g., rif2025)
   - Claim tables: {setting}_claims_{month:02d} (e.g., bcarrier_claims_05)
   - Line tables: {setting}_line_{month:02d} for bcarrier/dme
   - Revenue tables: {setting}_revenue_{month:02d} for institutional settings

## Key Features

- **Flexible Time Ranges**: Handle any month/year range with simple arithmetic
- **Proper Entity Mapping**: Correct field mappings per VRDC specification
- **SQL Generation**: Ready-to-use SQL strings with proper table prefixes
- **Special Handling**: Institutional vs non-institutional differences
- **Field Aliasing**: Proper aliasing including special cases (RNDRNG_PHYSN_NPI)
- **Missing Field Logic**: Correctly excludes unavailable fields per setting

## Use Cases

This is designed for building canonical entity tables that merge data from multiple
benefit settings across time ranges, creating hierarchical entity views for
analysis and reporting.
"""

from entity_looper import MonthRange, VRDCEntityMapper


def demonstrate_month_range():
    """Demonstrate MonthRange class functionality."""
    print("=" * 70)
    print("MONTH RANGE DEMONSTRATIONS")
    print("=" * 70)
    
    # Example 1: Single year range
    print("\n1. Single Year Range (2023 Q1)")
    print("-" * 40)
    q1_2023 = MonthRange(start_year=2023, start_month=1, end_year=2023, end_month=3)
    print(f"Range: {q1_2023}")
    print(f"Total months: {q1_2023.get_total_months()}")
    print("Months in range:")
    for year, month in q1_2023.iterate_months():
        print(f"  {year}-{month:02d}")
    
    # Example 2: Cross-year range
    print("\n2. Cross-Year Range (Nov 2023 - Feb 2024)")
    print("-" * 40)
    winter_range = MonthRange(start_year=2023, start_month=11, end_year=2024, end_month=2)
    print(f"Range: {winter_range}")
    print(f"Total months: {winter_range.get_total_months()}")
    print("Months in range:")
    for year, month in winter_range.iterate_months():
        print(f"  {year}-{month:02d}")
    
    # Example 3: Full year
    print("\n3. Full Year Range (2023)")
    print("-" * 40)
    full_year = MonthRange(start_year=2023, start_month=1, end_year=2023, end_month=12)
    print(f"Range: {full_year}")
    print(f"Total months: {full_year.get_total_months()}")
    
    # Example 4: Multi-year range
    print("\n4. Multi-Year Range (2021-2023)")
    print("-" * 40)
    multi_year = MonthRange(start_year=2021, start_month=6, end_year=2023, end_month=8)
    print(f"Range: {multi_year}")
    print(f"Total months: {multi_year.get_total_months()}")
    print("First and last few months:")
    months = list(multi_year.iterate_months())
    for i, (year, month) in enumerate(months):
        if i < 3 or i >= len(months) - 3:
            print(f"  {year}-{month:02d}")
        elif i == 3:
            print("  ... (showing first and last 3)")


def demonstrate_basic_entity_mapping():
    """Demonstrate basic VRDCEntityMapper functionality."""
    print("\n\n" + "=" * 70)
    print("BASIC ENTITY MAPPING DEMONSTRATIONS")
    print("=" * 70)
    
    # Example 1: Available settings
    print("\n1. Available Benefit Settings")
    print("-" * 40)
    settings = VRDCEntityMapper.get_all_settings()
    print(f"Total settings: {len(settings)}")
    for setting in settings:
        print(f"  - {setting}")
    
    # Example 2: Setting field analysis
    print("\n2. Field Analysis by Setting")
    print("-" * 40)
    for setting in ['bcarrier', 'dme', 'inpatient', 'snf']:
        summary = VRDCEntityMapper.get_setting_summary(setting=setting)
        print(f"\n{setting.upper()}:")
        for level, info in summary.items():
            if info['count'] > 0:
                print(f"  {level}: {info['count']} fields")
                for field in info['fields'][:2]:  # Show first 2 fields
                    print(f"    - {field}")
                if info['count'] > 2:
                    print(f"    - ... and {info['count'] - 2} more")
            else:
                print(f"  {level}: No fields available")
    
    # Example 3: Level analysis across settings
    print("\n3. Entity Level Analysis")
    print("-" * 40)
    levels = ['tax_id', 'ccn', 'organizational_npi', 'personal_npi']
    for level in levels:
        level_data = VRDCEntityMapper.get_level_fields(level=level)
        settings_with_level = list(level_data.keys())
        print(f"{level.upper()}: Available in {len(settings_with_level)} settings")
        print(f"  Settings: {', '.join(settings_with_level)}")


def demonstrate_table_naming():
    """Demonstrate database and table naming conventions."""
    print("\n\n" + "=" * 70)
    print("TABLE NAMING DEMONSTRATIONS")
    print("=" * 70)
    
    # Example 1: Different settings and years
    print("\n1. Table Names by Setting and Time")
    print("-" * 40)
    examples = [
        ('bcarrier', 2025, 5),
        ('dme', 2023, 12),
        ('inpatient', 2019, 1),
        ('outpatient', 2024, 8),
        ('snf', 2022, 11),
    ]
    
    for setting, year, month in examples:
        table_info = VRDCEntityMapper.get_table_names(setting=setting, year=year, month=month)
        print(f"\n{setting.upper()} {year}-{month:02d}:")
        print(f"  Database: {table_info['database']}")
        print(f"  Claim table: {table_info['claim_table']}")
        print(f"  Line table: {table_info['line_table']}")
    
    # Example 2: Line vs Revenue distinction
    print("\n2. Line vs Revenue Table Distinction")
    print("-" * 40)
    print("NON-INSTITUTIONAL (use 'line' tables):")
    for setting in ['bcarrier', 'dme']:
        line_table = VRDCEntityMapper._get_line_table_name(setting=setting, month=6)
        print(f"  {setting}: {line_table}")
    
    print("\nINSTITUTIONAL (use 'revenue' tables):")
    for setting in ['inpatient', 'outpatient', 'snf', 'hospice', 'hha']:
        line_table = VRDCEntityMapper._get_line_table_name(setting=setting, month=6)
        print(f"  {setting}: {line_table}")


def demonstrate_sql_generation():
    """Demonstrate SQL generation capabilities."""
    print("\n\n" + "=" * 70)
    print("SQL GENERATION DEMONSTRATIONS")
    print("=" * 70)
    
    # Example 1: Basic SQL for different settings
    print("\n1. Basic SQL Generation (Abstract)")
    print("-" * 40)
    for setting in ['bcarrier', 'dme']:
        print(f"\n{setting.upper()} SQL:")
        sql = VRDCEntityMapper.get_sql_select_list(setting=setting)
        lines = sql.split('\n')
        for i, line in enumerate(lines):
            if i < 3:  # Show first 3 lines
                print(f"  {line}")
            elif i == 3:
                print(f"  ... and {len(lines) - 3} more lines")
                break
    
    # Example 2: SQL with actual table names
    print("\n2. SQL with Actual Table Names")
    print("-" * 40)
    for setting in ['bcarrier', 'inpatient']:
        print(f"\n{setting.upper()} for March 2023:")
        sql = VRDCEntityMapper.get_sql_with_table_names(setting=setting, year=2023, month=3)
        lines = sql.split('\n')
        for i, line in enumerate(lines):
            if i < 4:  # Show first 4 lines
                print(f"  {line}")
            elif i == 4:
                print(f"  ... and {len(lines) - 4} more lines")
                break


def demonstrate_institutional_differences():
    """Demonstrate differences between institutional and non-institutional settings."""
    print("\n\n" + "=" * 70)
    print("INSTITUTIONAL FORMAT DIFFERENCES")
    print("=" * 70)
    
    # Example 1: Tax ID availability
    print("\n1. Tax ID Field Availability")
    print("-" * 40)
    all_settings = VRDCEntityMapper.get_all_settings()
    
    print("SETTINGS WITH TAX_ID:")
    tax_settings = VRDCEntityMapper.get_level_fields(level='tax_id')
    for setting in tax_settings.keys():
        print(f"  ✓ {setting}")
    
    print("\nSETTINGS WITHOUT TAX_ID:")
    no_tax_settings = [s for s in all_settings if s not in tax_settings]
    for setting in no_tax_settings:
        print(f"  ✗ {setting}")
    
    # Example 2: ORDRG_PHYSN_NPI availability
    print("\n2. ORDRG_PHYSN_NPI Field Availability")
    print("-" * 40)
    institutional_settings = ['inpatient', 'outpatient', 'snf', 'hospice', 'hha']
    
    for setting in institutional_settings:
        fields = VRDCEntityMapper.get_setting_fields(setting=setting)
        personal_npi_fields = [f['field'] for f in fields['personal_npi']]
        has_ordrg = 'ORDRG_PHYSN_NPI' in personal_npi_fields
        status = "✓" if has_ordrg else "✗"
        print(f"  {status} {setting}")
    
    # Example 3: Special aliasing
    print("\n3. Special RNDRNG_PHYSN_NPI Aliasing")
    print("-" * 40)
    inpatient_fields = VRDCEntityMapper.get_setting_fields(setting='inpatient')
    rndrng_fields = [f for f in inpatient_fields['personal_npi'] 
                     if f['field'] == 'RNDRNG_PHYSN_NPI']
    
    print("RNDRNG_PHYSN_NPI appears in both tables with different aliases:")
    for field in rndrng_fields:
        print(f"  {field['table']} table: {field['field']} → {field['alias']}")


def demonstrate_month_range_integration():
    """Demonstrate integrating MonthRange with VRDCEntityMapper."""
    print("\n\n" + "=" * 70)
    print("MONTH RANGE + ENTITY MAPPER INTEGRATION")
    print("=" * 70)
    
    # Example 1: Summary analysis
    print("\n1. Time Range Analysis Summary")
    print("-" * 40)
    month_range = MonthRange(start_year=2023, start_month=10, end_year=2024, end_month=3)
    settings = ['bcarrier', 'dme', 'inpatient']
    
    summary = VRDCEntityMapper.get_month_range_summary(
        month_range=month_range, 
        settings=settings
    )
    
    print(f"Time range: {summary['month_range']}")
    print(f"Settings: {', '.join(summary['settings'])}")
    print(f"Total months: {summary['total_months']}")
    print(f"Total settings: {summary['total_settings']}")
    print(f"Total combinations: {summary['total_combinations']}")
    
    # Example 2: Iteration examples
    print("\n2. Iteration Examples")
    print("-" * 40)
    
    # Small example for demo
    small_range = MonthRange(start_year=2023, start_month=11, end_year=2024, end_month=1)
    
    print(f"Iterating through {small_range} for bcarrier:")
    count = 0
    for result in VRDCEntityMapper.iterate_month_range(
        month_range=small_range, 
        settings=['bcarrier']
    ):
        print(f"  {result['year']}-{result['month']:02d}: "
              f"{result['database']}.{result['claim_table']} + "
              f"{result['database']}.{result['line_table']}")
        count += 1
    
    print(f"Total iterations: {count}")


def demonstrate_real_world_use_case():
    """Demonstrate a real-world use case scenario."""
    print("\n\n" + "=" * 70)
    print("REAL-WORLD USE CASE: ENTITY ANALYSIS PIPELINE")
    print("=" * 70)
    
    print("""
Scenario: Building a comprehensive entity analysis across all benefit settings
for Q4 2023, focusing on organizations with both Tax IDs and NPIs.

This would be used to create canonical entity tables for downstream analysis.
    """)
    
    # Step 1: Define time range
    print("\nStep 1: Define Analysis Time Range")
    print("-" * 40)
    q4_2023 = MonthRange(start_year=2023, start_month=10, end_year=2023, end_month=12)
    print(f"Analysis period: {q4_2023}")
    print(f"Total months: {q4_2023.get_total_months()}")
    
    # Step 2: Select relevant settings
    print("\nStep 2: Select Benefit Settings")
    print("-" * 40)
    # Focus on settings that have tax_id for organizational analysis
    tax_settings = list(VRDCEntityMapper.get_level_fields(level='tax_id').keys())
    print(f"Settings with Tax ID: {', '.join(tax_settings)}")
    
    # Step 3: Analyze scope
    print("\nStep 3: Analysis Scope")
    print("-" * 40)
    summary = VRDCEntityMapper.get_month_range_summary(
        month_range=q4_2023, 
        settings=tax_settings
    )
    print(f"Total table combinations to process: {summary['total_combinations']}")
    print(f"Total months: {summary['total_months']}")
    print(f"Total settings: {summary['total_settings']}")
    
    # Step 4: Show sample iteration
    print("\nStep 4: Sample Processing Loop")
    print("-" * 40)
    print("Example of how you'd process each combination:")
    
    count = 0
    for result in VRDCEntityMapper.iterate_month_range(
        month_range=q4_2023, 
        settings=['bcarrier', 'dme']  # Just show first 2 settings for demo
    ):
        if count < 4:  # Show first 4 iterations
            print(f"  Process: {result['database']}.{result['claim_table']} + "
                  f"{result['database']}.{result['line_table']}")
            print(f"    SQL ready: {len(result['sql'].split(','))} entity fields")
        count += 1
        if count == 4:
            print(f"  ... and {summary['total_combinations'] - 4} more combinations")
            break
    
    # Step 5: Show entity field breakdown
    print("\nStep 5: Entity Field Breakdown")
    print("-" * 40)
    for setting in tax_settings[:3]:  # Show first 3 settings
        setting_summary = VRDCEntityMapper.get_setting_summary(setting=setting)
        total_fields = sum(info['count'] for info in setting_summary.values())
        print(f"{setting}: {total_fields} total entity fields")
        for level, info in setting_summary.items():
            if info['count'] > 0:
                print(f"  - {level}: {info['count']} fields")


def main():
    """Run all demonstrations."""
    print("VRDC Entity Looper - Usage Demonstrations")
    print("This comprehensive demo shows how to use the MonthRange and VRDCEntityMapper classes")
    print("for entity-level analysis across multiple medical claims benefit settings.")
    
    try:
        # Run all demonstration functions
        demonstrate_month_range()
        demonstrate_basic_entity_mapping()
        demonstrate_table_naming()
        demonstrate_sql_generation()
        demonstrate_institutional_differences()
        demonstrate_month_range_integration()
        demonstrate_real_world_use_case()
        
        print("\n\n" + "=" * 70)
        print("DEMONSTRATION COMPLETE")
        print("=" * 70)
        print("\nAll demonstrations completed successfully!")
        print("\nKey takeaways:")
        print("- MonthRange handles time ranges with simple arithmetic")
        print("- VRDCEntityMapper provides comprehensive entity field mapping")
        print("- Ready-to-use SQL generation with proper table naming")
        print("- Flexible iteration supports various analysis patterns")
        print("- Proper handling of institutional vs non-institutional differences")
        
    except Exception as e:
        print(f"\nError during demonstration: {e}")
        print("Make sure the entity_looper module is properly installed.")


if __name__ == "__main__":
    main()
