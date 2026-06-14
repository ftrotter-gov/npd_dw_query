Complete Flow
=================

The end-to-end flow is from Snowflake to S3. We have the S3 command-line tools enabled, and we need to identify a specific S3 bucket in the `.env` file.
Add this as a new parameter to the example.env

The full flow is as follows:

1. Pull and download the component CSV files.
2. Merge them into a single CSV file.
3. Copy that merged CSV file to S3 using the aws command line tool (aws s3 cp etc)
4. Confirm, using MD5, that the file uploaded to S3 is the same as the merged local file.
5. Use `wc -l` to confirm that the merged file has the same number of rows of data as the constituent CSV files.
6. Erase the constituent CSV files locally.
7. Erase the merged file locally to clean up the hard drive and make space for the next file.
8. Once the split files have been erased locally, erase them on the Snowflake side using `snowsql`.
9. Only erase the Snowflake files that have already been processed.
10. Check whether there is a set of files available in Snowflake that has not yet been processed.
11. Poll every 5 minutes until a new file is available.

On the laptop side, we completely merge, upload to S3, and verify before cleaning up and starting to look for the next file to process.

On the Snowflake side, we wait for the files to fully process before sending more.

On the Snowflake side, we are also polling every 3 minutes to see if the
