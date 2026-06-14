#!/bin/bash
# Script assumes that ~/cms_data_downloads_possible_pii/idr_data/ is exists and is devoted to this process.. it should also have sub-directory of unmerged_csv_files
# intentionally hardcoded to prevent accidental csv inclusion in github etc. 

#This is where snowsql likes to install itself
alias snowsql="/Applications/SnowSQL.app/Contents/MacOS/snowsql"

# move to the download directory to being the download
pushd ~/cms_data_downloads_possible_pii/idr_data/unmerged_csv_files/

# download using snowsql. You must have cms_idr configured for snowflake
/Applications/SnowSQL.app/Contents/MacOS/snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"

# go back the main directory
popd

echo -e '\a'
