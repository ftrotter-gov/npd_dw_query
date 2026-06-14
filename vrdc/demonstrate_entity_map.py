"""
Demonstration script for VRDC Entity Map Builder

This script shows how to use the CreateEntityMap.VRDCEntityMapBuilder class
to generate entity maps from VRDC claims data.
"""

from CreateEntityMap import VRDCEntityMapBuilder
from MonthRange import MonthRange
from VrdcEntityMapper import VRDCEntityMapper

def demonstrate_entity_map_creation():
    """Demonstrate various ways to use the VRDCEntityMapBuilder."""
    
    print("VRDC Entity Map Builder - Usage Demonstrations")
    print("=" * 70)
    
    # Example 1: Small time range with specific settings
    print("\n1. Columnarized Entity Structure Example (January 2023, bcarrier only)")
    print("-" * 70)
    
    jan_2023_range = MonthRange(start_year=2023, start_month=1, end_year=2023, end_month=1)
    
    sql_jan = VRDCEntityMapBuilder.build_entity_map(
        month_range=jan_2023_range,
        settings=['bcarrier'],
        output_database='demo_db',
        view_name='jan_2023_entity_view',
        table_name='jan_2023_entity_map',
        execute=False  # Just generate SQL
    )
    
    view_sql = sql_jan['CREATE entity map view']
    union_count = view_sql.count('UNION ALL')
    select_count = view_sql.count('SELECT')
    
    print(f"Generated {select_count} individual SELECT statements")
    print(f"Combined with {union_count} UNION ALL operations")
    print("CRITICAL: Each SELECT has exactly ONE NPI field (onpi OR pnpi, never both)")
    
    # Show structure of first few SELECT statements
    parts = view_sql.split('UNION ALL')
    print(f"\nFirst 3 SELECT statements:")
    for i, part in enumerate(parts[:3]):
        lines = part.strip().split('\n')
        print(f"\n--- SELECT {i+1} ---")
        for line in lines[:10]:
            if line.strip():
                print(f"  {line.strip()}")
                if 'AS onpi' in line or 'AS pnpi' in line:
                    npi_type = 'organizational' if 'AS onpi' in line else 'personal'
                    print(f"    --> Individual {npi_type} NPI field!")
                    break
    
    # Example 2: Full year with all settings
    print("\n\n2. Full Year Example (2023, all settings)")
    print("-" * 50)
    
    full_year_range = MonthRange(start_year=2023, start_month=1, end_year=2023, end_month=12)
    
    sql_full = VRDCEntityMapBuilder.build_entity_map(
        month_range=full_year_range,
        settings=None,  # All settings
        privacy_threshold=25,  # Higher threshold
        execute=False
    )
    
    all_settings = VRDCEntityMapper.get_all_settings()
    total_queries = 12 * len(all_settings)  # 12 months × 7 settings
    print(f"Would process {total_queries} monthly queries (12 months × 7 settings)")
    print(f"Settings: {', '.join(all_settings)}")
    
    # Show the final aggregation query
    table_sql = sql_full['CREATE entity map table']
    print("\nFinal entity map aggregation:")
    for line in table_sql.split('\n')[:10]:
        print(f"  {line}")
    
    # Example 3: Cross-year range
    print("\n\n3. Cross-Year Range Example (Q4 2023 - Q1 2024)")
    print("-" * 50)
    
    cross_year_range = MonthRange(start_year=2023, start_month=10, end_year=2024, end_month=3)
    
    sql_cross = VRDCEntityMapBuilder.build_entity_map(
        month_range=cross_year_range,
        settings=['bcarrier', 'outpatient'],
        view_name='cross_year_entity_view',
        execute=False
    )
    
    cross_view_sql = sql_cross['CREATE entity map view']
    union_count = cross_view_sql.count('UNION ALL')
    expected_unions = (6 * 2) - 1  # 6 months × 2 settings - 1 (since UNION ALL separates)
    print(f"Cross-year processing: {union_count + 1} monthly queries")
    print(f"Covers: 2023-10, 2023-11, 2023-12, 2024-01, 2024-02, 2024-03")
    
    # Example 4: Show how entity fields are mapped
    print("\n\n4. Entity Field Mapping Example")
    print("-" * 50)
    
    print("Each monthly query includes these standardized entity fields:")
    print("- source_setting_name: Which benefit setting (bcarrier, dme, etc.)")
    print("- bene_id, clm_id: Standard claim identifiers")
    print("- TAX_NUM: Tax identification number (when available)")
    print("- CCN: Provider certification number (when available)")  
    print("- onpi: Organizational NPI (simplified alias)")
    print("- pnpi: Personal NPI (simplified alias)")
    
    # Show actual field mappings for bcarrier
    bcarrier_fields = VRDCEntityMapper.get_setting_summary(setting='bcarrier')
    print(f"\nExample - bcarrier has:")
    print(f"- {bcarrier_fields['tax_id']['count']} tax_id field")
    print(f"- {bcarrier_fields['organizational_npi']['count']} organizational NPI fields → onpi")
    print(f"- {bcarrier_fields['personal_npi']['count']} personal NPI fields → pnpi")
    
    # Example 5: Configuration options
    print("\n\n5. Configuration Options")
    print("-" * 50)
    
    print("Key configuration parameters:")
    print("- Time range: start_year/month, end_year/month")
    print("- Settings: specific list or None for all")
    print("- Database locations: extracts_catalog, output_catalog, output_database")
    print("- Table names: view_name, table_name, log_table_name")
    print("- Privacy threshold: minimum beneficiaries to include")
    print("- Execute control: execute=True/False for SQL generation vs execution")
    
    print("\n" + "=" * 70)
    print("Ready to use VRDCEntityMapBuilder in Databricks!")
    print("Set is_just_print=True in CreateEntityMap.py to preview SQL")
    print("Set is_just_print=False to execute and create tables")


if __name__ == "__main__":
    demonstrate_entity_map_creation()
