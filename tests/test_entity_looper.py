"""
Test suite for VRDC Entity Looper module.

This test suite validates the functionality of both the MonthRange and VRDCEntityMapper classes,
ensuring proper field mappings, database/table naming, and time range iteration.
"""

import pytest
from vrdc.MonthRange import MonthRange
from vrdc.VrdcEntityMapper import VRDCEntityMapper


class TestMonthRange:
    """Test the MonthRange class functionality."""
    
    def test_month_range_creation(self):
        """Test creating a MonthRange object."""
        month_range = MonthRange(start_year=2023, start_month=1, end_year=2023, end_month=12)
        assert month_range.start_year == 2023
        assert month_range.start_month == 1
        assert month_range.end_year == 2023
        assert month_range.end_month == 12
    
    def test_month_range_validation(self):
        """Test MonthRange input validation."""
        # Invalid month values
        with pytest.raises(ValueError, match="Month values must be between 1 and 12"):
            MonthRange(start_year=2023, start_month=0, end_year=2023, end_month=12)
        
        with pytest.raises(ValueError, match="Month values must be between 1 and 12"):
            MonthRange(start_year=2023, start_month=1, end_year=2023, end_month=13)
        
        # Invalid date range
        with pytest.raises(ValueError, match="Start date must be before or equal to end date"):
            MonthRange(start_year=2024, start_month=1, end_year=2023, end_month=12)
        
        with pytest.raises(ValueError, match="Start date must be before or equal to end date"):
            MonthRange(start_year=2023, start_month=6, end_year=2023, end_month=5)
    
    def test_month_range_iteration(self):
        """Test MonthRange month iteration."""
        month_range = MonthRange(start_year=2023, start_month=11, end_year=2024, end_month=2)
        months = list(month_range.iterate_months())
        
        expected = [(2023, 11), (2023, 12), (2024, 1), (2024, 2)]
        assert months == expected
    
    def test_month_range_single_month(self):
        """Test MonthRange with single month."""
        month_range = MonthRange(start_year=2023, start_month=5, end_year=2023, end_month=5)
        months = list(month_range.iterate_months())
        
        assert months == [(2023, 5)]
        assert month_range.get_total_months() == 1
    
    def test_month_range_year_rollover(self):
        """Test MonthRange crossing year boundaries."""
        month_range = MonthRange(start_year=2022, start_month=10, end_year=2024, end_month=3)
        months = list(month_range.iterate_months())
        
        # Should start at 2022-10 and end at 2024-03
        assert months[0] == (2022, 10)
        assert months[-1] == (2024, 3)
        assert len(months) == 18  # Oct 2022 through Mar 2024
    
    def test_month_range_total_months(self):
        """Test get_total_months calculation."""
        # Single year
        month_range = MonthRange(start_year=2023, start_month=1, end_year=2023, end_month=6)
        assert month_range.get_total_months() == 6
        
        # Cross year boundary
        month_range = MonthRange(start_year=2023, start_month=11, end_year=2024, end_month=2)
        assert month_range.get_total_months() == 4
        
        # Full year
        month_range = MonthRange(start_year=2023, start_month=1, end_year=2023, end_month=12)
        assert month_range.get_total_months() == 12
    
    def test_month_range_string_representation(self):
        """Test MonthRange string methods."""
        month_range = MonthRange(start_year=2023, start_month=1, end_year=2023, end_month=12)
        
        assert str(month_range) == "MonthRange(2023-01 to 2023-12)"
        assert "start_year=2023" in repr(month_range)
        assert "end_month=12" in repr(month_range)


class TestVRDCEntityMapper:
    """Test the VRDCEntityMapper class functionality."""
    
    def test_get_all_settings(self):
        """Test getting all available settings."""
        settings = VRDCEntityMapper.get_all_settings()
        expected_settings = ['bcarrier', 'dme', 'inpatient', 'outpatient', 'snf', 'hospice', 'hha']
        
        assert len(settings) == 7
        for setting in expected_settings:
            assert setting in settings
    
    def test_get_setting_fields(self):
        """Test getting fields for specific settings."""
        # Test bcarrier (has tax_id, no ccn)
        bcarrier_fields = VRDCEntityMapper.get_setting_fields(setting='bcarrier')
        assert 'tax_id' in bcarrier_fields
        assert len(bcarrier_fields['tax_id']) == 1
        assert len(bcarrier_fields['ccn']) == 0  # No CCN for bcarrier
        assert len(bcarrier_fields['organizational_npi']) > 0
        assert len(bcarrier_fields['personal_npi']) > 0
        
        # Test invalid setting
        with pytest.raises(ValueError, match="Setting 'invalid' not found"):
            VRDCEntityMapper.get_setting_fields(setting='invalid')
    
    def test_get_level_fields(self):
        """Test getting fields for specific levels."""
        # Test tax_id level
        tax_fields = VRDCEntityMapper.get_level_fields(level='tax_id')
        assert 'bcarrier' in tax_fields
        assert 'dme' in tax_fields
        assert 'inpatient' in tax_fields
        assert 'outpatient' in tax_fields
        # SNF, hospice, hha should not have tax_id
        assert 'snf' not in tax_fields
        assert 'hospice' not in tax_fields
        assert 'hha' not in tax_fields
        
        # Test invalid level
        with pytest.raises(ValueError, match="Level 'invalid' not found"):
            VRDCEntityMapper.get_level_fields(level='invalid')
    
    def test_database_naming(self):
        """Test database name generation."""
        assert VRDCEntityMapper._get_database_name(year=2023) == "rif2023"
        assert VRDCEntityMapper._get_database_name(year=2019) == "rif2019"
        assert VRDCEntityMapper._get_database_name(year=2025) == "rif2025"
    
    def test_claim_table_naming(self):
        """Test claim table name generation."""
        assert VRDCEntityMapper._get_claim_table_name(setting='bcarrier', month=5) == "bcarrier_claims_05"
        assert VRDCEntityMapper._get_claim_table_name(setting='inpatient', month=12) == "inpatient_claims_12"
        assert VRDCEntityMapper._get_claim_table_name(setting='dme', month=1) == "dme_claims_01"
    
    def test_line_table_naming(self):
        """Test line/revenue table name generation."""
        # bcarrier and dme use 'line'
        assert VRDCEntityMapper._get_line_table_name(setting='bcarrier', month=5) == "bcarrier_line_05"
        assert VRDCEntityMapper._get_line_table_name(setting='dme', month=12) == "dme_line_12"
        
        # Institutional settings use 'revenue'
        assert VRDCEntityMapper._get_line_table_name(setting='inpatient', month=3) == "inpatient_revenue_03"
        assert VRDCEntityMapper._get_line_table_name(setting='outpatient', month=8) == "outpatient_revenue_08"
        assert VRDCEntityMapper._get_line_table_name(setting='snf', month=11) == "snf_revenue_11"
    
    def test_institutional_setting_detection(self):
        """Test institutional setting detection."""
        assert not VRDCEntityMapper._is_institutional_setting(setting='bcarrier')
        assert not VRDCEntityMapper._is_institutional_setting(setting='dme')
        
        assert VRDCEntityMapper._is_institutional_setting(setting='inpatient')
        assert VRDCEntityMapper._is_institutional_setting(setting='outpatient')
        assert VRDCEntityMapper._is_institutional_setting(setting='snf')
        assert VRDCEntityMapper._is_institutional_setting(setting='hospice')
        assert VRDCEntityMapper._is_institutional_setting(setting='hha')
    
    def test_get_table_names(self):
        """Test complete table name generation."""
        # Test bcarrier
        table_info = VRDCEntityMapper.get_table_names(setting='bcarrier', year=2025, month=5)
        assert table_info['database'] == 'rif2025'
        assert table_info['claim_table'] == 'bcarrier_claims_05'
        assert table_info['line_table'] == 'bcarrier_line_05'
        assert table_info['setting'] == 'bcarrier'
        assert table_info['year'] == 2025
        assert table_info['month'] == 5
        
        # Test institutional setting
        table_info = VRDCEntityMapper.get_table_names(setting='inpatient', year=2019, month=12)
        assert table_info['database'] == 'rif2019'
        assert table_info['claim_table'] == 'inpatient_claims_12'
        assert table_info['line_table'] == 'inpatient_revenue_12'
    
    def test_sql_generation(self):
        """Test SQL select list generation."""
        sql = VRDCEntityMapper.get_sql_select_list(setting='bcarrier')
        
        # Should contain proper SQL formatting
        assert 'CLAIM.TAX_NUM AS TAX_NUM' in sql
        assert 'AS' in sql  # All fields should be aliased
        assert ',' in sql  # Multiple fields should be comma-separated
        
        # Test that it generates valid-looking SQL
        lines = sql.split('\n')
        assert len(lines) > 1  # Should be multi-line
    
    def test_sql_with_table_names(self):
        """Test SQL generation with actual table names."""
        sql = VRDCEntityMapper.get_sql_with_table_names(setting='dme', year=2023, month=3)
        
        # Should contain actual database and table names
        assert 'rif2023.dme_claims_03' in sql
        assert 'rif2023.dme_line_03' in sql
        assert 'AS TAX_NUM' in sql
        assert 'AS PRVDR_NUM' in sql
    
    def test_setting_summary(self):
        """Test setting field summary generation."""
        summary = VRDCEntityMapper.get_setting_summary(setting='bcarrier')
        
        # Should have all four levels
        assert 'tax_id' in summary
        assert 'ccn' in summary
        assert 'organizational_npi' in summary
        assert 'personal_npi' in summary
        
        # Check counts
        assert summary['tax_id']['count'] == 1
        assert summary['ccn']['count'] == 0  # No CCN for bcarrier
        assert summary['organizational_npi']['count'] > 0
        assert summary['personal_npi']['count'] > 0
        
        # Check field format
        assert len(summary['tax_id']['fields']) == 1
        assert 'CLAIM.TAX_NUM' in summary['tax_id']['fields']
    
    def test_iterate_setting_levels(self):
        """Test setting level iteration."""
        levels = list(VRDCEntityMapper.iterate_setting_levels(setting='bcarrier'))
        
        # Should only yield levels that have fields
        level_names = [level[0] for level in levels]
        assert 'tax_id' in level_names
        assert 'ccn' not in level_names  # Should be excluded (empty)
        assert 'organizational_npi' in level_names
        assert 'personal_npi' in level_names
    
    def test_month_range_integration(self):
        """Test VRDCEntityMapper integration with MonthRange."""
        month_range = MonthRange(start_year=2023, start_month=11, end_year=2024, end_month=1)
        
        # Test summary
        summary = VRDCEntityMapper.get_month_range_summary(
            month_range=month_range, 
            settings=['bcarrier', 'dme']
        )
        assert summary['total_months'] == 3  # Nov, Dec, Jan
        assert summary['total_settings'] == 2
        assert summary['total_combinations'] == 6
        assert summary['start_year'] == 2023
        assert summary['end_month'] == 1
        
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
    
    def test_legacy_methods(self):
        """Test legacy methods for backward compatibility."""
        # Test legacy time range iteration
        results = list(VRDCEntityMapper.iterate_time_range(
            start_year=2023, start_month=11,
            end_year=2023, end_month=12,
            settings=['bcarrier']
        ))
        assert len(results) == 2  # Nov and Dec
        
        # Test legacy summary
        summary = VRDCEntityMapper.get_time_range_summary(
            start_year=2023, start_month=1,
            end_year=2023, end_month=6,
            settings=['bcarrier', 'dme']
        )
        assert summary['total_months'] == 6
        assert summary['total_combinations'] == 12
    
    def test_invalid_settings_validation(self):
        """Test validation of invalid settings."""
        month_range = MonthRange(start_year=2023, start_month=1, end_year=2023, end_month=3)
        
        # Invalid setting in month range iteration
        with pytest.raises(ValueError, match="Setting 'invalid' not found"):
            list(VRDCEntityMapper.iterate_month_range(
                month_range=month_range,
                settings=['invalid']
            ))
        
        # Invalid setting in summary
        with pytest.raises(ValueError, match="Setting 'invalid' not found"):
            VRDCEntityMapper.get_month_range_summary(
                month_range=month_range,
                settings=['bcarrier', 'invalid']
            )
    
    def test_institutional_format_differences(self):
        """Test differences between institutional format settings."""
        # Test settings that should NOT have tax_id (OWNG_PRVDR_TIN_NUM)
        no_tax_settings = ['snf', 'hospice', 'hha']
        for setting in no_tax_settings:
            fields = VRDCEntityMapper.get_setting_fields(setting=setting)
            assert len(fields['tax_id']) == 0, f"{setting} should not have tax_id fields"
        
        # Test settings that should NOT have ORDRG_PHYSN_NPI
        no_ordrg_settings = ['inpatient', 'snf']
        for setting in no_ordrg_settings:
            fields = VRDCEntityMapper.get_setting_fields(setting=setting)
            personal_npi_fields = [f['field'] for f in fields['personal_npi']]
            assert 'ORDRG_PHYSN_NPI' not in personal_npi_fields, f"{setting} should not have ORDRG_PHYSN_NPI"
        
        # Test outpatient should have ORDRG_PHYSN_NPI
        outpatient_fields = VRDCEntityMapper.get_setting_fields(setting='outpatient')
        personal_npi_fields = [f['field'] for f in outpatient_fields['personal_npi']]
        assert 'ORDRG_PHYSN_NPI' in personal_npi_fields
    
    def test_special_aliasing(self):
        """Test special aliasing for RNDRNG_PHYSN_NPI fields."""
        # Test institutional setting with RNDRNG_PHYSN_NPI aliasing
        inpatient_fields = VRDCEntityMapper.get_setting_fields(setting='inpatient')
        personal_npi_fields = inpatient_fields['personal_npi']
        
        # Find RNDRNG_PHYSN_NPI fields
        rndrng_fields = [f for f in personal_npi_fields if f['field'] == 'RNDRNG_PHYSN_NPI']
        assert len(rndrng_fields) == 2  # Should have both CLAIM and CLINE versions
        
        # Check aliases
        aliases = [f['alias'] for f in rndrng_fields]
        assert 'claim_RNDRNG_PHYSN_NPI' in aliases
        assert 'cline_RNDRNG_PHYSN_NPI' in aliases


if __name__ == "__main__":
    pytest.main([__file__])
