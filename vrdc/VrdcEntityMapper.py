"""
VrdcEntityMapper.py -- VRDC Entity Column Mapper

This module provides a class for mapping entity identifiers across different
medical claims benefit settings. It handles the complex field mappings between
claim-level and claim-line-level tables, with proper aliasing and SQL generation.

The class supports iteration across four conceptual levels:
- TIN/EIN (tax identifiers) - sometimes missing
- CCN - sometimes missing  
- Organizational NPI
- Personal NPI

Also supports time-based iteration across database years and table months with
proper database and table naming conventions:
- Database format: rif{year} (e.g., rif2025)  
- Claim table format: {setting}_claims_{month:02d} (e.g., bcarrier_claims_05)
- Line table format: {setting}_line_{month:02d} for bcarrier/dme
- Revenue table format: {setting}_revenue_{month:02d} for institutional settings
"""

try:
    from .MonthRange import MonthRange

except ImportError:
    try:
        from MonthRange import MonthRange
    except ImportError:
        print("Loading from previous cell")


class VRDCEntityMapper:
    """
    Maps entity identifiers across medical claims benefit settings.
    
    Provides methods to iterate across settings and generate SQL select statements
    with proper table prefixes and aliasing.
    """
    
    def __init__(self):
        """Initialize the mapper with all benefit setting configurations."""
        self._data = self._build_entity_mappings()
    
    @staticmethod
    def _generate_sql_string(*, table, field, alias, simplified_npi_aliases=False, level=None):
        """
        Generate SQL string from table, field, and alias.
        
        Args:
            table (str): Table name (CLAIM or CLINE)
            field (str): Field name
            alias (str): Alias name
            simplified_npi_aliases (bool): If True, use simplified aliases for NPI fields
            level (str): Entity level (for simplified aliasing)
            
        Returns:
            str: SQL string in format "table.field AS alias"
        """
        if simplified_npi_aliases and level:
            if level == 'organizational_npi':
                return f"{table}.{field} AS onpi"
            elif level == 'personal_npi':
                return f"{table}.{field} AS pnpi"
        
        return f"{table}.{field} AS {alias}"
    
    @staticmethod
    def _build_entity_mappings():
        """
        Build the complete entity mapping data structure.
        
        Returns:
            dict: Nested dictionary with setting -> level -> field mappings
        """
        mappings = {}
        
        # bcarrier settings
        mappings['bcarrier'] = {
            'tax_id': [
                {'table': 'CLINE', 'field': 'TAX_NUM', 'alias': 'TAX_NUM'}
            ],
            'ccn': [],  # No CCN for bcarrier
            'organizational_npi': [
                {'table': 'CLAIM', 'field': 'CARR_CLM_BLG_NPI_NUM', 'alias': 'CARR_CLM_BLG_NPI_NUM'},
                {'table': 'CLAIM', 'field': 'CPO_ORG_NPI_NUM', 'alias': 'CPO_ORG_NPI_NUM'},
                {'table': 'CLAIM', 'field': 'CARR_CLM_SOS_NPI_NUM', 'alias': 'CARR_CLM_SOS_NPI_NUM'},
                {'table': 'CLINE', 'field': 'CARR_LINE_MDPP_NPI_NUM', 'alias': 'CARR_LINE_MDPP_NPI_NUM'},
                {'table': 'CLINE', 'field': 'ORG_NPI_NUM', 'alias': 'ORG_NPI_NUM'}
            ],
            'personal_npi': [
                {'table': 'CLINE', 'field': 'CARR_LINE_MDPP_NPI_NUM', 'alias': 'CARR_LINE_MDPP_NPI_NUM'},
                {'table': 'CLINE', 'field': 'PRF_PHYSN_NPI', 'alias': 'PRF_PHYSN_NPI'}
            ]
        }
        
        # dme settings
        mappings['dme'] = {
            'tax_id': [
                {'table': 'CLINE', 'field': 'TAX_NUM', 'alias': 'TAX_NUM'}
            ],
            'ccn': [
                {'table': 'CLINE', 'field': 'PRVDR_NUM', 'alias': 'PRVDR_NUM'}
            ],
            'organizational_npi': [
                {'table': 'CLINE', 'field': 'PRVDR_NPI', 'alias': 'PRVDR_NPI'}
            ],
            'personal_npi': [
                {'table': 'CLAIM', 'field': 'RFR_PHYSN_NPI', 'alias': 'RFR_PHYSN_NPI'}
            ]
        }
        
        # Institutional formats - build base template
        institutional_base = {
            'tax_id': [
                {'table': 'CLAIM', 'field': 'OWNG_PRVDR_TIN_NUM', 'alias': 'OWNG_PRVDR_TIN_NUM'}
            ],
            'ccn': [
                {'table': 'CLAIM', 'field': 'PRVDR_NUM', 'alias': 'PRVDR_NUM'}
            ],
            'organizational_npi': [
                {'table': 'CLAIM', 'field': 'ORG_NPI_NUM', 'alias': 'ORG_NPI_NUM'},
                {'table': 'CLAIM', 'field': 'SRVC_LOC_NPI_NUM', 'alias': 'SRVC_LOC_NPI_NUM'}
            ],
            'personal_npi': [
                {'table': 'CLAIM', 'field': 'AT_PHYSN_NPI', 'alias': 'AT_PHYSN_NPI'},
                {'table': 'CLAIM', 'field': 'OP_PHYSN_NPI', 'alias': 'OP_PHYSN_NPI'},
                {'table': 'CLAIM', 'field': 'OT_PHYSN_NPI', 'alias': 'OT_PHYSN_NPI'},
                {'table': 'CLAIM', 'field': 'RNDRNG_PHYSN_NPI', 'alias': 'claim_RNDRNG_PHYSN_NPI'},
                {'table': 'CLINE', 'field': 'RNDRNG_PHYSN_NPI', 'alias': 'cline_RNDRNG_PHYSN_NPI'},
                {'table': 'CLINE', 'field': 'ORDRNG_PHYSN_NPI', 'alias': 'ORDRNG_PHYSN_NPI'}
            ]
        }
        
        # inpatient - institutional format without SRVC_LOC_NPI_NUM and ORDRG_PHYSN_NPI
        mappings['inpatient'] = {
            'tax_id': institutional_base['tax_id'][:],
            'ccn': institutional_base['ccn'][:],
            'organizational_npi': [field for field in institutional_base['organizational_npi'] if field['field'] != 'SRVC_LOC_NPI_NUM'],  # not found in Inpatient
            'personal_npi': [field for field in institutional_base['personal_npi'] if field['field'] != 'ORDRNG_PHYSN_NPI']  # not found in Inpatient
        }
        
        # outpatient - full institutional format
        mappings['outpatient'] = {
            'tax_id': institutional_base['tax_id'][:],
            'ccn': institutional_base['ccn'][:],
            'organizational_npi': institutional_base['organizational_npi'][:],
            'personal_npi': institutional_base['personal_npi'][:]
        }
        
        # snf - missing OWNG_PRVDR_TIN_NUM and ORDRG_PHYSN_NPI
        mappings['snf'] = {
            'tax_id': [],  # OWNG_PRVDR_TIN_NUM not found in SNF
            'ccn': institutional_base['ccn'][:],
            'organizational_npi': [field for field in institutional_base['organizational_npi'] if field['field'] != 'SRVC_LOC_NPI_NUM'],
            'personal_npi': [field for field in institutional_base['personal_npi'] if field['field'] != 'ORDRNG_PHYSN_NPI' ]  # not found in SNF
        }
        
        # hospice - missing OWNG_PRVDR_TIN_NUM
        mappings['hospice'] = {
            'tax_id': [],  # OWNG_PRVDR_TIN_NUM not found in Hospice
            'ccn': institutional_base['ccn'][:],
            'organizational_npi': institutional_base['organizational_npi'][:],
            'personal_npi': institutional_base['personal_npi'][:]
        }
        
        # hha - missing OWNG_PRVDR_TIN_NUM
        mappings['hha'] = {
            'tax_id': [],  # OWNG_PRVDR_TIN_NUM not found in HHA
            'ccn': institutional_base['ccn'][:],
            'organizational_npi': institutional_base['organizational_npi'][:],
            'personal_npi': institutional_base['personal_npi'][:]
        }
        
        return mappings
    
    @staticmethod
    def get_all_settings():
        """
        Get list of all available benefit settings.
        
        Returns:
            list: List of setting names
        """
        mapper = VRDCEntityMapper()
        return list(mapper._data.keys())
    
    @staticmethod
    def get_setting_fields(*, setting):
        """
        Get all fields for a specific benefit setting.
        
        Args:
            setting (str): Benefit setting name (e.g., 'bcarrier', 'dme', 'inpatient')
            
        Returns:
            dict: Dictionary with level -> list of field mappings
        """
        mapper = VRDCEntityMapper()
        if setting not in mapper._data:
            raise ValueError(f"Setting '{setting}' not found. Available settings: {list(mapper._data.keys())}")
        return mapper._data[setting]
    
    @staticmethod
    def get_level_fields(*, level):
        """
        Get all fields for a specific level across all settings.
        
        Args:
            level (str): Level name ('tax_id', 'ccn', 'organizational_npi', 'personal_npi')
            
        Returns:
            dict: Dictionary with setting -> list of field mappings for the level
        """
        mapper = VRDCEntityMapper()
        valid_levels = ['tax_id', 'ccn', 'organizational_npi', 'personal_npi']
        if level not in valid_levels:
            raise ValueError(f"Level '{level}' not found. Available levels: {valid_levels}")
        
        result = {}
        for setting_name, setting_data in mapper._data.items():
            if level in setting_data and setting_data[level]:
                result[setting_name] = setting_data[level]
        return result
    
    @staticmethod
    def get_sql_select_list(*, setting, simplified_npi_aliases=False):
        """
        Get comma-separated SQL select list for a specific setting.
        
        Args:
            setting (str): Benefit setting name
            simplified_npi_aliases (bool): If True, use 'onpi' and 'pnpi' for NPI fields
            
        Returns:
            str: Comma-separated SQL select statement
        """
        setting_fields = VRDCEntityMapper.get_setting_fields(setting=setting)
        
        sql_parts = []
        for level_name, field_list in setting_fields.items():
            for field_mapping in field_list:
                sql_string = VRDCEntityMapper._generate_sql_string(
                    table=field_mapping['table'],
                    field=field_mapping['field'],
                    alias=field_mapping['alias'],
                    simplified_npi_aliases=simplified_npi_aliases,
                    level=level_name
                )
                sql_parts.append(sql_string)
        
        return ',\n    '.join(sql_parts)
    
    @staticmethod
    def iterate_setting_levels(*, setting):
        """
        Generator to iterate through levels for a specific setting.
        
        Args:
            setting (str): Benefit setting name
            
        Yields:
            tuple: (level_name, field_mappings_list)
        """
        setting_fields = VRDCEntityMapper.get_setting_fields(setting=setting)
        
        for level_name, field_list in setting_fields.items():
            if field_list:  # Only yield levels that have fields
                yield level_name, field_list
    
    @staticmethod
    def get_setting_summary(*, setting):
        """
        Get a summary of available fields by level for a setting.
        
        Args:
            setting (str): Benefit setting name
            
        Returns:
            dict: Summary with counts and field names by level
        """
        setting_fields = VRDCEntityMapper.get_setting_fields(setting=setting)
        
        summary = {}
        for level_name, field_list in setting_fields.items():
            if field_list:
                summary[level_name] = {
                    'count': len(field_list),
                    'fields': [f"{field['table']}.{field['field']}" for field in field_list]
                }
            else:
                summary[level_name] = {'count': 0, 'fields': []}
        
        return summary
    
    @staticmethod
    def _get_database_name(*, year):
        """
        Get database name for a specific year.
        
        Args:
            year (int): Year
            
        Returns:
            str: Database name in format rif{year}
        """
        return f"rif{year}"
    
    @staticmethod
    def _get_claim_table_name(*, setting, month):
        """
        Get claim table name for a setting and month.
        
        Args:
            setting (str): Benefit setting name
            month (int): Month number (1-12)
            
        Returns:
            str: Claim table name in format {setting}_claims_{month:02d}
        """
        return f"{setting}_claims_{month:02d}"
    
    @staticmethod
    def _get_line_table_name(*, setting, month):
        """
        Get line/revenue table name for a setting and month.
        
        Args:
            setting (str): Benefit setting name  
            month (int): Month number (1-12)
            
        Returns:
            str: Line/revenue table name based on setting type
        """
        # Institutional settings use 'revenue', bcarrier/dme use 'line'
        institutional_settings = ['inpatient', 'outpatient', 'snf', 'hospice', 'hha']
        
        if setting in institutional_settings:
            return f"{setting}_revenue_{month:02d}"
        else:
            return f"{setting}_line_{month:02d}"
    
    @staticmethod
    def _next_month(*, year, month):
        """
        Get next month and year, handling year rollover.
        
        Args:
            year (int): Current year
            month (int): Current month (1-12)
            
        Returns:
            tuple: (next_year, next_month)
        """
        if month == 12:
            return year + 1, 1
        else:
            return year, month + 1
    
    @staticmethod
    def _is_institutional_setting(*, setting):
        """
        Check if a setting is institutional format.
        
        Args:
            setting (str): Benefit setting name
            
        Returns:
            bool: True if institutional, False otherwise
        """
        institutional_settings = ['inpatient', 'outpatient', 'snf', 'hospice', 'hha']
        return setting in institutional_settings
    
    @staticmethod
    def get_table_names(*, setting, year, month):
        """
        Get database and table names for a specific setting, year, and month.
        
        Args:
            setting (str): Benefit setting name
            year (int): Year
            month (int): Month number (1-12)
            
        Returns:
            dict: Dictionary with database, claim_table, and line_table names
        """
        return {
            'database': VRDCEntityMapper._get_database_name(year=year),
            'claim_table': VRDCEntityMapper._get_claim_table_name(setting=setting, month=month),
            'line_table': VRDCEntityMapper._get_line_table_name(setting=setting, month=month),
            'setting': setting,
            'year': year,
            'month': month
        }
    
    @staticmethod
    def get_sql_with_table_names(*, setting, year, month, simplified_npi_aliases=False):
        """
        Get SQL select list with actual database and table names.
        
        Args:
            setting (str): Benefit setting name
            year (int): Year
            month (int): Month number (1-12)
            simplified_npi_aliases (bool): If True, use 'onpi' and 'pnpi' for NPI fields
            
        Returns:
            str: SQL select statement with full table names
        """
        table_info = VRDCEntityMapper.get_table_names(setting=setting, year=year, month=month)
        setting_fields = VRDCEntityMapper.get_setting_fields(setting=setting)
        
        claim_table = f"{table_info['database']}.{table_info['claim_table']}"
        line_table = f"{table_info['database']}.{table_info['line_table']}"
        
        sql_parts = []
        for level_name, field_list in setting_fields.items():
            for field_mapping in field_list:
                if field_mapping['table'] == 'CLAIM':
                    full_table_name = claim_table
                else:  # CLINE
                    full_table_name = line_table
                
                sql_string = VRDCEntityMapper._generate_sql_string(
                    table=full_table_name,
                    field=field_mapping['field'],
                    alias=field_mapping['alias'],
                    simplified_npi_aliases=simplified_npi_aliases,
                    level=level_name
                )
                sql_parts.append(sql_string)
        
        return ',\n    '.join(sql_parts)
    
    @staticmethod
    def get_npi_loop_sql(*, setting, year, month, npi_level):
        """
        Generate SQL for looping through NPI fields with simplified aliases.
        
        Args:
            setting (str): Benefit setting name
            year (int): Year
            month (int): Month number (1-12)  
            npi_level (str): 'organizational_npi' or 'personal_npi'
            
        Returns:
            list: List of SQL strings, each with 'onpi' or 'pnpi' alias
        """
        if npi_level not in ['organizational_npi', 'personal_npi']:
            raise ValueError("npi_level must be 'organizational_npi' or 'personal_npi'")
            
        table_info = VRDCEntityMapper.get_table_names(setting=setting, year=year, month=month)
        setting_fields = VRDCEntityMapper.get_setting_fields(setting=setting)
        
        claim_table = f"{table_info['database']}.{table_info['claim_table']}"
        line_table = f"{table_info['database']}.{table_info['line_table']}"
        
        sql_statements = []
        if npi_level in setting_fields:
            for field_mapping in setting_fields[npi_level]:
                if field_mapping['table'] == 'CLAIM':
                    full_table_name = claim_table
                else:  # CLINE
                    full_table_name = line_table
                
                alias = 'onpi' if npi_level == 'organizational_npi' else 'pnpi'
                sql_statement = f"{full_table_name}.{field_mapping['field']} AS {alias}"
                sql_statements.append(sql_statement)
        
        return sql_statements
    
    @staticmethod
    def iterate_npi_fields(*, setting, npi_level):
        """
        Iterate through NPI fields for a setting with field metadata.
        
        Args:
            setting (str): Benefit setting name
            npi_level (str): 'organizational_npi' or 'personal_npi'
            
        Yields:
            dict: Field info with table, field, original_alias, and simplified_alias
        """
        if npi_level not in ['organizational_npi', 'personal_npi']:
            raise ValueError("npi_level must be 'organizational_npi' or 'personal_npi'")
            
        setting_fields = VRDCEntityMapper.get_setting_fields(setting=setting)
        simplified_alias = 'onpi' if npi_level == 'organizational_npi' else 'pnpi'
        
        if npi_level in setting_fields:
            for field_mapping in setting_fields[npi_level]:
                yield {
                    'table': field_mapping['table'],
                    'field': field_mapping['field'],
                    'original_alias': field_mapping['alias'],
                    'simplified_alias': simplified_alias,
                    'sql': f"{field_mapping['table']}.{field_mapping['field']} AS {simplified_alias}"
                }
    
    @staticmethod
    def iterate_month_range(*, month_range, settings):
        """
        Iterate over MonthRange and settings in chronological order.
        
        Args:
            month_range (MonthRange): Range of months to iterate through
            settings (list): List of setting names to include
            
        Yields:
            dict: Dictionary with setting info and table names for each month/setting combination
        """
        # Validate settings
        mapper = VRDCEntityMapper()
        valid_settings = list(mapper._data.keys())
        for setting in settings:
            if setting not in valid_settings:
                raise ValueError(f"Setting '{setting}' not found. Available settings: {valid_settings}")
        
        # Iterate through each month in the range
        for year, month in month_range.iterate_months():
            # For each month, iterate through all requested settings
            for setting in settings:
                table_info = VRDCEntityMapper.get_table_names(setting=setting, year=year, month=month)
                setting_fields = VRDCEntityMapper.get_setting_fields(setting=setting)
                
                yield {
                    'year': year,
                    'month': month,
                    'setting': setting,
                    'database': table_info['database'],
                    'claim_table': table_info['claim_table'],
                    'line_table': table_info['line_table'],
                    'fields': setting_fields,
                    'sql': VRDCEntityMapper.get_sql_with_table_names(setting=setting, year=year, month=month)
                }
    
    @staticmethod
    def get_month_range_summary(*, month_range, settings):
        """
        Get summary of MonthRange iteration without iterating through all combinations.
        
        Args:
            month_range (MonthRange): Range of months to summarize
            settings (list): List of setting names to include
            
        Returns:
            dict: Summary with total months, settings, and combinations
        """
        total_months = month_range.get_total_months()
        total_combinations = total_months * len(settings)
        
        return {
            'month_range': str(month_range),
            'start_year': month_range.start_year,
            'start_month': month_range.start_month,
            'end_year': month_range.end_year,
            'end_month': month_range.end_month,
            'settings': settings,
            'total_months': total_months,
            'total_settings': len(settings),
            'total_combinations': total_combinations
        }
    
    # Legacy methods for backward compatibility
    @staticmethod
    def iterate_time_range(*, start_year, start_month, end_year, end_month, settings):
        """
        Legacy method - use iterate_month_range instead.
        """
        month_range = MonthRange(
            start_year=start_year, start_month=start_month,
            end_year=end_year, end_month=end_month
        )
        return VRDCEntityMapper.iterate_month_range(month_range=month_range, settings=settings)
    
    @staticmethod
    def get_time_range_summary(*, start_year, start_month, end_year, end_month, settings):
        """
        Legacy method - use get_month_range_summary instead.
        """
        month_range = MonthRange(
            start_year=start_year, start_month=start_month,
            end_year=end_year, end_month=end_month
        )
        return VRDCEntityMapper.get_month_range_summary(month_range=month_range, settings=settings)
