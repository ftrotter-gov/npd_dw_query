-- ============================================================
-- check_access.sql
-- Diagnostic queries to confirm Snowflake access to IDR tables
--
-- Paste this into a Snowflake SQL worksheet and run the
-- statements one at a time, top to bottom.
-- ============================================================


-- ── 1. What role / user are you running as? ──────────────────
SELECT CURRENT_USER(),
       CURRENT_ROLE(),
       CURRENT_DATABASE(),
       CURRENT_SCHEMA(),
       CURRENT_WAREHOUSE();


-- TGDA	PUBLIC	USER$TGDA	PUBLIC	IDRC_PRD_COMM_WH


-- ── 2. What databases can you see? ───────────────────────────
-- Should include IDRC_PRD in the list
SHOW DATABASES;

-- Expected output:
-- 0	2023-06-07 15:25:06-04:00	AMS_PRD	N	N	
-- 1	2021-11-10 09:05:44-05:00	IDRC_PRD	N	N	
-- 2	2021-08-12 10:19:53-04:00	SNOWFLAKE	N	N	SNOWFLAKE.ACCOUNT_USAGE
-- 3	2021-11-05 09:21:09-04:00	SNOWFLAKE_SAMPLE_DATA	N	N	SFSALESSHARED.SFC_SAMPLES_AWSUSEAST1GOV.SAMPLE_DATA
-- 4	2025-09-10 21:18:14-04:00	USER$TGDA	N	Y	

-- ── 3. What schemas exist inside IDRC_PRD? ───────────────────
-- Should include CMS_VDM_VIEW_PRVDR_ENRLMT
SHOW SCHEMAS IN DATABASE IDRC_PRD;


-- 0	2026-03-10 23:22:36-04:00	CMS_CMN_SAS2PY_PRD	N	N	IDRC_PRD
-- 1	2022-06-14 13:46:17-04:00	CMS_SASTEMP_COMM_PRD	N	N	IDRC_PRD
-- 2	2026-02-24 22:12:21-05:00	CMS_SHRD_WORKSPAC_PRD	N	N	IDRC_PRD
-- 3	2023-03-27 22:53:36-04:00	CMS_UDF_COMM_PRD	N	N	IDRC_PRD
-- 4	2022-06-07 21:26:26-04:00	CMS_VDM_VIEW_ACO_PRD	N	N	IDRC_PRD
-- 5	2022-04-08 15:49:35-04:00	CMS_VDM_VIEW_MDCD_PRD	N	N	IDRC_PRD
-- 6	2022-04-08 15:49:35-04:00	CMS_VDM_VIEW_MDCR_PRD	N	N	IDRC_PRD
-- 7	2022-04-08 15:49:35-04:00	CMS_VDM_VIEW_RFRNC_AL_PRD	N	N	IDRC_PRD
-- 8	2022-04-08 15:49:35-04:00	CMS_VDM_VIEW_SMNTC_PRD	N	N	IDRC_PRD
-- 9	2026-06-14 17:09:27-04:00	INFORMATION_SCHEMA	N	N	IDRC_PRD

-- ── 4. Narrow search for the exact schema we need ────────────
SHOW SCHEMAS LIKE '%PRVDR_ENRLMT%' IN DATABASE IDRC_PRD;

-- Everything from here down failes. 


-- ── 5. What tables are in that schema? ───────────────────────
SHOW TABLES IN SCHEMA IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT;


-- ── 6. Quick sanity-check row count on one target table ──────
SELECT COUNT(*)
FROM IDRC_PRD.CMS_VDM_VIEW_PRVDR_ENRLMT.V2_PRVDR_ENRLMT_MDCR_ID_DEACTVTN_RSN_HSTRY
LIMIT 1;
