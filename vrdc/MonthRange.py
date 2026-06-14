"""
MonthRange.py avoids having lots of arguments for start and end year/months

Represents a range of months across years for iterating through VRDC data.
Simple container for start and end month/year pairs that can be used
for flexible iteration across different benefit settings and table types.
"""


class MonthRange:
    """
    Represents a range of months across years for iterating through VRDC data.
    
    Simple container for start and end month/year pairs that can be used
    for flexible iteration across different benefit settings and table types.
    """
    
    def __init__(self, *, start_year, start_month, end_year, end_month):
        """
        Initialize a month range.
        
        Args:
            start_year (int): Starting year
            start_month (int): Starting month (1-12)
            end_year (int): Ending year
            end_month (int): Ending month (1-12)
        """
        # Validate inputs
        if not (1 <= start_month <= 12) or not (1 <= end_month <= 12):
            raise ValueError("Month values must be between 1 and 12")
            
        if start_year > end_year or (start_year == end_year and start_month > end_month):
            raise ValueError("Start date must be before or equal to end date")
            
        self.start_year = start_year
        self.start_month = start_month
        self.end_year = end_year
        self.end_month = end_month
    
    def iterate_months(self):
        """
        Generator to iterate through all months in the range.
        
        Yields:
            tuple: (year, month) for each month in the range
        """
        current_year = self.start_year
        current_month = self.start_month
        
        while (current_year < self.end_year or 
               (current_year == self.end_year and current_month <= self.end_month)):
            
            yield current_year, current_month
            
            # Move to next month
            if current_month == 12:
                current_year += 1
                current_month = 1
            else:
                current_month += 1
    
    def get_total_months(self):
        """
        Calculate total number of months in the range.
        
        Returns:
            int: Total number of months
        """
        total_months = 0
        for _ in self.iterate_months():
            total_months += 1
        return total_months
    
    def __str__(self):
        """String representation of the month range."""
        return f"MonthRange({self.start_year}-{self.start_month:02d} to {self.end_year}-{self.end_month:02d})"
    
    def __repr__(self):
        """Detailed string representation."""
        return (f"MonthRange(start_year={self.start_year}, start_month={self.start_month}, "
                f"end_year={self.end_year}, end_month={self.end_month})")
