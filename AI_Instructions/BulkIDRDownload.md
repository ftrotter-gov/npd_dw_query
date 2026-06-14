Bulk IDR Download
=====================

I would like to download most, but not all, of the data that is in a whole set of matching tables
in a snowflake database. I have already written a class that understands the mechanics of downloading
IDR data given a simple SQL query. Please read that file now: idr/IDROutputter.py

Leveraging that work, I would like to be able to write a single notebook that will query the metadata for
the snowflake database in question, and generate a json file which contains the database, schema and table/view
name to query, as well as all of the column names.

Then I want another JSON file that will automatically create scripts that implement an IDROutputter subclass
with a SELECT query that downloads that IDR view/table.

These should all be seperate notebooks, so that specific SQL can be added to each one to tweak what columns specifically are downloaded by the script. All columns should be included in the generated SELECT by default. Columns should be ordered in the same order they are stored in snowflake.

Lets keep all of the python scripts simple .py files, even if they are going to run in the notebook. No .pynb please.

Also the script that generates the new notebooks from the json should be a CLI script that accepts the json file and an output directory as arguements.

The script that is going to query the metdata, sould accept a 'LIKE' string as an argument, so that matches can be made with a string like '%I_Match%' the like should not be case-sensitive.

* Put the table matching script that makes the json in misc_scripts/gen_extract_scripts/make_json_from_table_match.py
* Put the generating script that makes the new notebook programs in misc_scripts/gen_extract_scripts/make_extract_scripts_from_json.py