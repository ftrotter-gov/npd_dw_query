#!/bin/bash
# Script assumes that ~/cms_data_downloads_possible_pii/idr_data/ is exists and is devoted to this process.. it should also have sub-directory of unmerged_csv_files
# intentionally hardcoded to prevent accidental csv inclusion in github etc. 

#Can be used in SnowSql as #connect example

#assumes the following in your ~/.snowsql/config.
#[connections.cms_idr]
#accountname = cms-idr.privatelink
#username = TGDA
#authenticator = externalbrowser
#rolename = IDRSF_DATA_PRVDR_PVT_P
#warehousename = IDRC_PRD_COMM_WH
#dbname = IDRD_PROD
#schemaname = CMS_VDM_VIEW_MDCR_PRD


#This is where snowsql likes to install itself
#alias snowsql="/Applications/SnowSQL.app/Contents/MacOS/snowsql"

# Delete the previous run
rm ~/cms_data_downloads_possible_pii/idr_data/unmerged_csv_files/*.csv

# move to the download directory to being the download
pushd ~/cms_data_downloads_possible_pii/idr_data/unmerged_csv_files/

# download using snowsql. You must have cms_idr configured for snowflake
/Applications/SnowSQL.app/Contents/MacOS/snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"

# go back the main directory
popd

# merge the new csv file here. 
python3 ./snowflake_csv_merge.py ~/cms_data_downloads_possible_pii/idr_data/unmerged_csv_files/ --output-dir ~/cms_data_downloads_possible_pii/idr_data/

# Beep signal end of script
 echo -e '\a'
