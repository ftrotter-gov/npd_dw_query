"""
Simple test runner for VRDC Entity Looper module (no pytest required).

This test suite validates the functionality of both the MonthRange and VRDCEntityMapper classes
using basic Python assertions.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vrdc.MonthRange import MonthRange
from vrdc.VrdcEntityMapper import VRDCEntityMapper


def test_month_range_basic():
    """Test basic MonthRange functionality."""
    print("Testing MonthRange basic functionality...")
    
    # Test creation
    month_range = MonthRange(start_year=2023, start_month=1, end_year=2023, end_month=12)
    assert month_range.start_year == 2023
    assert month_range.start_month == 1
    assert month_range.end_year == 2023
    assert month_range.end_month == 12
    print("✓ MonthRange creation works")
    
    # Test iteration
    month_range = MonthRange(start_year=2023, start_month=11, end_year=2024, end_month=2)
    months = list(month_range.iterate_months())
    expected = [(2023, 11), (2023, 12), (2024, 1), (2024, 2)]
    assert months == expected
    print("✓ MonthRange iteration works")
    
    # Test total months
    assert month_range.get_total_months() == 4
    print("✓ MonthRange total months calculation works")
    
    # Test string representation
    assert str(month_range) == "MonthRange(2023-11 to 2024-02)"
    print("✓ MonthRange string representation works")


def test_month_range_validation():
    """Test MonthRange validation."""
    print("Testing MonthRange validation...")
    
    # Test invalid months
    try:
        MonthRange(start_year=2023, start_month=0, end_year=2023, end_month=12)
        assert False, "Should have raised ValueError for invalid month"
    except ValueError as e:
        assert "Month values must be between 1 and 12" in str(e)
    print("✓ MonthRange month validation works")
    
    # Test invalid date range
    try:
        MonthRange(start_year=2024, start_month=1, end_year=2023, end_month=12)
        assert False, "Should have raised ValueError for invalid date range"
    except ValueError as e:
        assert "Start date must be before or equal to end date" in str(e)
    print("✓ MonthRange date range validation works")


def test_vrdc_entity_mapper_basic():
    """Test basic VRDCEntityMapper functionality."""
    print("Testing VRDCEntityMapper basic functionality...")
    
    # Test getting all settings
    settings = VRDCEntityMapper.get_all_settings()
    expected_settings = ['bcarrier', 'dme', 'inpatient', 'outpatient', 'snf', 'hospice', 'hha']
    assert len(settings) == 7
    for setting in expected_settings:
        assert setting in settings
    print("✓ get_all_settings works")
    
    # Test getting setting fields
    bcarrier_fields = VRDCEntityMapper.get_setting_fields(setting='bcarrier')
    assert 'tax_id' in bcarrier_fields
    assert len(bcarrier_fields['tax_id']) == 1
    assert len(bcarrier_fields['ccn']) == 0  # No CCN for bcarrier
    print("✓ get_setting_fields works")
    
    # Test getting level fields
    tax_fields = VRDCEntityMapper.get_level_fields(level='tax_id')
    assert 'bcarrier' in tax_fields
    assert 'dme' in tax_fields
    assert 'snf' not in tax_fields  # SNF should not have tax_id
    print("✓ get_level_fields works")


def test_table_naming():
    """Test database and table naming conventions."""
    print("Testing table naming conventions...")
    
    # Test database naming
    assert VRDCEntityMapper._get_database_name(year=2023) == "rif2023"
    assert VRDCEntityMapper._get_database_name(year=2025) == "rif2025"
    print("✓ Database naming works")
    
    # Test claim table naming
    assert VRDCEntityMapper._get_claim_table_name(setting='bcarrier', month=5) == "bcarrier_claims_05"
    assert VRDCEntityMapper._get_claim_table_name(setting='inpatient', month=12) == "inpatient_claims_12"
    print("✓ Claim table naming works")
    
    # Test line/revenue table naming
    assert VRDCEntityMapper._get_line_table_name(setting='bcarrier', month=5) == "bcarrier_line_05"
    assert VRDCEntityMapper._get_line_table_name(setting='inpatient', month=3) == "inpatient_revenue_03"
    print("✓ Line/revenue table naming works")
    
    # Test complete table info
    table_info = VRDCEntityMapper.get_table_names(setting='bcarrier', year=2025, month=5)
    assert table_info['database'] == 'rif2025'
    assert table_info['claim_table'] == 'bcarrier_claims_05'
    assert table_info['line_table'] == 'bcarrier_line_05'
    print("✓ Complete table naming works")


def test_sql_generation():
    """Test SQL generation."""
    print("Testing SQL generation...")
    
    # Test basic SQL generation
    sql = VRDCEntityMapper.get_sql_select_list(setting='bcarrier')
    assert 'CLAIM.TAX_NUM AS TAX_NUM' in sql
    assert 'AS' in sql  # All fields should be aliased
    assert ',' in sql  # Multiple fields should be comma-separated
    print("✓ Basic SQL generation works")
    
    # Test SQL with actual table names
    sql = VRDCEntityMapper.get_sql_with_table_names(setting='dme', year=2023, month=3)
    assert 'rif2023.dme_claims_03' in sql
    assert 'rif2023.dme_line_03' in sql
    assert 'AS TAX_NUM' in sql
    print("✓ SQL with table names works")


def test_institutional_differences():
    """Test institutional format differences."""
    print("Testing institutional format differences...")
    
    # Test institutional setting detection
    assert not VRDCEntityMapper._is_institutional_setting(setting='bcarrier')
    assert not VRDCEntityMapper._is_institutional_setting(setting='dme')
    assert VRDCEntityMapper._is_institutional_setting(setting='inpatient')
    assert VRDCEntityMapper._is_institutional_setting(setting='snf')
    print("✓ Institutional setting detection works")
    
    # Test settings that should NOT have tax_id
    no_tax_settings = ['snf', 'hospice', 'hha']
    for setting in no_tax_settings:
        fields = VRDCEntityMapper.get_setting_fields(setting=setting)
        assert len(fields['tax_id']) == 0, f"{setting} should not have tax_id fields"
    print("✓ Tax ID exclusions work correctly")
    
    # Test ORDRG_PHYSN_NPI exclusions
    no_ordrg_settings = ['inpatient', 'snf']
    for setting in no_ordrg_settings:
        fields = VRDCEntityMapper.get_setting_fields(setting=setting)
        personal_npi_fields = [f['field'] for f in fields['personal_npi']]
        assert 'ORDRG_PHYSN_NPI' not in personal_npi_fields
    print("✓ ORDRG_PHYSN_NPI exclusions work correctly")


def test_special_aliasing():
    """Test special aliasing for RNDRNG_PHYSN_NPI fields."""
    print("Testing special aliasing...")
    
    inpatient_fields = VRDCEntityMapper.get_setting_fields(setting='inpatient')
    personal_npi_fields = inpatient_fields['personal_npi']
    
    # Find RNDRNG_PHYSN_NPI fields
    rndrng_fields = [f for f in personal_npi_fields if f['field'] == 'RNDRNG_PHYSN_NPI']
    assert len(rndrng_fields) == 2  # Should have both CLAIM and CLINE versions
    
    # Check aliases
    aliases = [f['alias'] for f in rndrng_fields]
    assert 'claim_RNDRNG_PHYSN_NPI' in aliases
    assert 'cline_RNDRNG_PHYSN_NPI' in aliases
    print("✓ Special aliasing works correctly")


def test_month_range_integration():
    """Test MonthRange integration with VRDCEntityMapper."""
    print("Testing MonthRange integration...")
    
    month_range = MonthRange(start_year=2023, start_month=11, end_year=2024, end_month=1)
    
    # Test summary
    summary = VRDCEntityMapper.get_month_range_summary(
        month_range=month_range, 
        settings=['bcarrier', 'dme']
    )
    assert summary['total_months'] == 3  # Nov, Dec, Jan
    assert summary['total_settings'] == 2
    assert summary['total_combinations'] == 6
    print("✓ Month range summary works")
    
    # Test iteration
    results = list(VRDCEntityMapper.iterate_month_range(
        month_range=month_range,
        settings=['bcarrier']
    ))
    assert len(results) == 3  # 3 months * 1 setting
    
    # Check first result
    first_result = results[0]
    assert first_result['year'] == 2023
    assert first_result['month'] == 11
    assert first_result['setting'] == 'bcarrier'
    assert first_result['database'] == 'rif2023'
    assert first_result['claim_table'] == 'bcarrier_claims_11'
    assert 'sql' in first_result
    assert 'fields' in first_result
    print("✓ Month range iteration works")


def test_legacy_methods():
    """Test legacy backward compatibility methods."""
    print("Testing legacy methods...")
    
    # Test legacy time range iteration
    results = list(VRDCEntityMapper.iterate_time_range(
        start_year=2023, start_month=11,
        end_year=2023, end_month=12,
        settings=['bcarrier']
    ))
    assert len(results) == 2  # Nov and Dec
    print("✓ Legacy time range iteration works")
    
    # Test legacy summary
    summary = VRDCEntityMapper.get_time_range_summary(
        start_year=2023, start_month=1,
        end_year=2023, end_month=6,
        settings=['bcarrier', 'dme']
    )
    assert summary['total_months'] == 6
    assert summary['total_combinations'] == 12
    print("✓ Legacy summary works")


def test_validation_errors():
    """Test validation and error handling."""
    print("Testing validation and error handling...")
    
    # Test invalid setting
    try:
        VRDCEntityMapper.get_setting_fields(setting='invalid')
        assert False, "Should have raised ValueError for invalid setting"
    except ValueError as e:
        assert "Setting 'invalid' not found" in str(e)
    print("✓ Invalid setting validation works")
    
    # Test invalid level
    try:
        VRDCEntityMapper.get_level_fields(level='invalid')
        assert False, "Should have raised ValueError for invalid level"
    except ValueError as e:
        assert "Level 'invalid' not found" in str(e)
    print("✓ Invalid level validation works")


def run_all_tests():
    """Run all test functions."""
    print("=" * 60)
    print("Running VRDC Entity Looper Test Suite")
    print("=" * 60)
    
    test_functions = [
        test_month_range_basic,
        test_month_range_validation,
        test_vrdc_entity_mapper_basic,
        test_table_naming,
        test_sql_generation,
        test_institutional_differences,
        test_special_aliasing,
        test_month_range_integration,
        test_legacy_methods,
        test_validation_errors
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"FAILED: {test_func.__name__} - {e}")
            failed += 1
    
    print("=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("All tests passed!")
        return True
    else:
        print("Some tests failed!")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
