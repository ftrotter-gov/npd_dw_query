Parallel Output and Download
============================

I would like to revise this software project so that it works in an automated, parallel manner.

Read misc_scripts/ and then review the contents of idr/ to see how the current system works. The new code should be placed in idr2/

The project currently auto-generates multiple separate and distinct notebooks. These notebooks must be run separately and individually inside the Snowflake environment. Each notebook exports a CSV file. Then a separate set of scripts downloads those files to a laptop.

Instead, I would like this process to run in a more headless fashion.

Rather than having hundreds of auto-compiled notebooks based on the schemas of the data, I would like to have one large metadata JSON file that describes all of the tables to download.

This metadata JSON file should itself be generated from a list of files or tables to download and mirror using CSV.

Once that metadata file exists, it should be used as input. The metadata necessary to query the tables should follow the approach outlined in the `IDR outputter` class, but it should run inside a loop.

The loop should work as follows:

1. Export one CSV file from Snowflake into the Snowflake CSV download area.
2. Wait.
3. On the downloader side, a cron job should look for a new file that is ready to download in that folder.
4. When the downloader sees a new file, it should download it.
5. Once the file is successfully downloaded, the downloader should erase it.
6. The script running inside the Snowflake notebook should see that the download space is empty.
7. The Snowflake-side script should then move on to export the next file.

This would automate the download of multiple Snowflake files, even though the only available execution environment is the Snowflake notebook environment.

The system should copy one file at a time until all downloads are complete.

The metadata format should be simple: The database.schema.table. The column names. Should not have any WHERE generated. The SQL that will be dynamically generated should be identical to the SQL that is generated in the code generation template. The data exported should be the same. 

Write a new version of "download and merge all snowflake" that includes the polling components. 

The snowflake side should be a series of classes and an execution script that can be pasted into a single snowflake python notebook and then run continually in the browser. On both sides.. the 'checking for a file that needs to download' and 'check to see if the download area is empty' logic should simply poll every five minutes. If there is no change in two hours.. the polling should stop. 

The file download directory should be part of a .env configuration file. Which should be excluded from github. There should be an example.env file that shows how it should be configured. The retry time and the quit_after_this_many_hours should also be configured there. There should be a file that is the list_of_tables_to_download.csv which has a single column table_to_download which will list the tables to download in database.schema.table format. 
