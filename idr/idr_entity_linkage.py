"""
IDR entity-linkage export — SQL for the org ↔ individual-provider affiliation graph.

Derives an organization ↔ individual-provider affiliation graph from one year of
Medicare claims in IDR (billing/OSCAR org NPIs joined to the individual NPIs that
appear on the same claim), weighted by distinct-beneficiary volume and suppressed
below a small-cell threshold. See build_linkage_sql() for the query.

All the scaffolding — config, auth, connection, claim window, and the
COPY → GET → optional S3 → REMOVE user-stage relay — lives in idr_export_common.py
(run there for the auth precedence, env vars, and run instructions). This file
keeps only the SQL and the run_export() call that wires it up.

Local (laptop) run — picks up ~/.config/idr2/snowflake_pat automatically:
    SNOWFLAKE_ACCOUNT=<account> SNOWFLAKE_USER=<user> \
    SNOWFLAKE_ROLE=<idr role with claims access> \
    SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH OUTPUT_DIR=./idr_data \
    python3 idr/idr_entity_linkage.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import MAX_SINGLE_FILE_BYTES, run_export


# ============================================================================
# LINKAGE QUERY
# ============================================================================

def build_linkage_sql(stage_target, start_sql, end_sql, min_bene):
    """
    COPY INTO @~/<file>.csv the org↔individual affiliation edges from one window
    of final-action Medicare claims: distinct (billing TIN, OSCAR, org NPI,
    personal NPI) with the count of distinct beneficiaries, suppressed at
    > min_bene. One uncompressed, headered CSV (SINGLE=TRUE).
    """
    return f"""
COPY INTO {stage_target}
FROM (

WITH claims_base AS (
    SELECT
        clm.CLM_UNIQ_ID,
        clm.CLM_BLG_PRVDR_TAX_NUM,
        clm.CLM_BLG_PRVDR_OSCAR_NUM,
        clm.CLM_BENE_MBI_ID,
        clm.CLM_BLG_PRVDR_NPI_NUM,
        clm.PRVDR_BLG_PRVDR_NPI_NUM,
        clm.CLM_ATNDG_PRVDR_NPI_NUM,
        clm.CLM_OPRTG_PRVDR_NPI_NUM,
        clm.CLM_OTHR_PRVDR_NPI_NUM,
        clm.CLM_RFRG_PRVDR_NPI_NUM,
        clm.CLM_RNDRG_PRVDR_NPI_NUM,
        clm.CLM_SRVC_PRVDR_NPI_NUM,
        clm.PRVDR_RFRG_PRVDR_NPI_NUM,
        clm.PRVDR_ATNDG_PRVDR_NPI_NUM,
        clm.PRVDR_OPRTG_PRVDR_NPI_NUM,
        clm.PRVDR_OTHR_PRVDR_NPI_NUM,
        clm.PRVDR_RNDRNG_PRVDR_NPI_NUM,
        clm.PRVDR_PRSCRBNG_PRVDR_NPI_NUM,
        clm.PRVDR_SRVC_PRVDR_NPI_NUM
    FROM IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_CLM AS clm
    WHERE clm.CLM_FROM_DT >= DATE '{start_sql}'
      AND clm.CLM_FROM_DT < DATE '{end_sql}'
      AND clm.CLM_FINL_ACTN_IND = 'Y'
),
org_npi_long AS (
    SELECT
        CLM_UNIQ_ID,
        CASE
            WHEN CLM_BLG_PRVDR_TAX_NUM IS NULL
              OR TRIM(CLM_BLG_PRVDR_TAX_NUM) IN ('', '~', '000000000')
                THEN NULL
            ELSE TRIM(CLM_BLG_PRVDR_TAX_NUM)
        END AS CLM_BLG_PRVDR_TAX_NUM,
        TRIM(CLM_BLG_PRVDR_OSCAR_NUM) AS CLM_BLG_PRVDR_OSCAR_NUM,
        CLM_BENE_MBI_ID,
        TRIM(CLM_BLG_PRVDR_NPI_NUM) AS org_npi
    FROM claims_base
    WHERE CLM_BLG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_BLG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CASE
            WHEN CLM_BLG_PRVDR_TAX_NUM IS NULL
              OR TRIM(CLM_BLG_PRVDR_TAX_NUM) IN ('', '~', '000000000')
                THEN NULL
            ELSE TRIM(CLM_BLG_PRVDR_TAX_NUM)
        END AS CLM_BLG_PRVDR_TAX_NUM,
        TRIM(CLM_BLG_PRVDR_OSCAR_NUM) AS CLM_BLG_PRVDR_OSCAR_NUM,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_BLG_PRVDR_NPI_NUM) AS org_npi
    FROM claims_base
    WHERE PRVDR_BLG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_BLG_PRVDR_NPI_NUM) NOT IN ('', '~')
),
personal_npi_long AS (
    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_ATNDG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_ATNDG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_ATNDG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_OPRTG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_OPRTG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_OPRTG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_OTHR_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_OTHR_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_OTHR_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_RFRG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_RFRG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_RFRG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_RNDRG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_RNDRG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_RNDRG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(CLM_SRVC_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE CLM_SRVC_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(CLM_SRVC_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_RFRG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_RFRG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_RFRG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_ATNDG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_ATNDG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_ATNDG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_OPRTG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_OPRTG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_OPRTG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_OTHR_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_OTHR_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_OTHR_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_RNDRNG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_RNDRNG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_RNDRNG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_PRSCRBNG_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_PRSCRBNG_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_PRSCRBNG_PRVDR_NPI_NUM) NOT IN ('', '~')

    UNION ALL

    SELECT
        CLM_UNIQ_ID,
        CLM_BENE_MBI_ID,
        TRIM(PRVDR_SRVC_PRVDR_NPI_NUM) AS personal_npi
    FROM claims_base
    WHERE PRVDR_SRVC_PRVDR_NPI_NUM IS NOT NULL
      AND TRIM(PRVDR_SRVC_PRVDR_NPI_NUM) NOT IN ('', '~')
),
relationship_claims AS (
    SELECT DISTINCT
        org.CLM_BLG_PRVDR_TAX_NUM,
        org.CLM_BLG_PRVDR_OSCAR_NUM,
        org.org_npi,
        person.personal_npi,
        org.CLM_BENE_MBI_ID
    FROM org_npi_long AS org
    INNER JOIN personal_npi_long AS person
        ON org.CLM_UNIQ_ID = person.CLM_UNIQ_ID
    WHERE org.CLM_BLG_PRVDR_OSCAR_NUM IS NOT NULL
      AND org.CLM_BLG_PRVDR_OSCAR_NUM NOT IN ('', '~')
)

SELECT
    CLM_BLG_PRVDR_TAX_NUM,
    CLM_BLG_PRVDR_OSCAR_NUM,
    org_npi,
    personal_npi,
    COUNT(DISTINCT CLM_BENE_MBI_ID) AS cnt_bene
FROM relationship_claims
GROUP BY
    CLM_BLG_PRVDR_TAX_NUM,
    CLM_BLG_PRVDR_OSCAR_NUM,
    org_npi,
    personal_npi
HAVING COUNT(DISTINCT CLM_BENE_MBI_ID) > {min_bene}

)
FILE_FORMAT = (
  TYPE = CSV
  FIELD_DELIMITER = ','
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  COMPRESSION = NONE
)
HEADER = TRUE
SINGLE = TRUE
MAX_FILE_SIZE = {MAX_SINGLE_FILE_BYTES}
OVERWRITE = TRUE
DETAILED_OUTPUT = FALSE
"""


if __name__ == "__main__":
    sys.exit(run_export(
        banner="IDR entity-linkage export",
        file_prefix="idr_entity_linkage",
        sql_builder=build_linkage_sql,
        min_bene_label="Min beneficiaries",
    ))
