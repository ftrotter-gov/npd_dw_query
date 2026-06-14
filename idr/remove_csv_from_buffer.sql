-- This is the snowflake SQL code to clean out the buffer before doing a CSV export
REMOVE @~/ pattern='.*.csv'