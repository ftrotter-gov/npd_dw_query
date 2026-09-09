"""One-off: verify the columns referenced by idr_medicare_entity_link_address.py
against the real IDR view definitions. Read-only (INFORMATION_SCHEMA)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import load_config, resolve_auth, connect

VIEWS = {
    "V2_MDCR_CLM":            "CMS_VDM_VIEW_MDCR_PRD",
    "V2_MDCR_CLM_LINE_PRFNL": "CMS_VDM_VIEW_MDCR_PRD",
}

# Columns the query references, split by source view.
REFS = {
    "V2_MDCR_CLM": [
        "CLM_UNIQ_ID", "CLM_BLG_PRVDR_TAX_NUM", "CLM_BLG_PRVDR_OSCAR_NUM",
        "CLM_BENE_MBI_ID", "CLM_BLG_PRVDR_NPI_NUM", "PRVDR_BLG_PRVDR_NPI_NUM",
        "CLM_ATNDG_PRVDR_NPI_NUM", "CLM_OPRTG_PRVDR_NPI_NUM", "CLM_OTHR_PRVDR_NPI_NUM",
        "CLM_RFRG_PRVDR_NPI_NUM", "CLM_RNDRG_PRVDR_NPI_NUM", "CLM_SRVC_PRVDR_NPI_NUM",
        "PRVDR_RFRG_PRVDR_NPI_NUM", "PRVDR_ATNDG_PRVDR_NPI_NUM", "PRVDR_OPRTG_PRVDR_NPI_NUM",
        "PRVDR_OTHR_PRVDR_NPI_NUM", "PRVDR_RNDRNG_PRVDR_NPI_NUM", "PRVDR_PRSCRBNG_PRVDR_NPI_NUM",
        "PRVDR_SRVC_PRVDR_NPI_NUM", "CLM_FROM_DT", "CLM_FINL_ACTN_IND",
        "GEO_BENE_SK", "CLM_DT_SGNTR_SK",
        # --- additional header columns referenced by idr_medicare_header_wide.py
        "CLM_FAC_PRVDR_NPI_NUM", "CLM_FAC_PRVDR_CPO_ORG_NPI_ID",
        "CLM_BLG_PRVDR_OSCAR_NUM", "CLM_BLG_PRVDR_FULL_CCN_NUM",
        "CLM_BLG_PRVDR_OSCAR_STATE_CD", "CLM_BLG_PRVDR_OSCAR_FAC_CD",
        "CLM_BLG_PRVDR_USPS_STATE_CD", "CLM_BLG_PRVDR_ZIP5_CD",
        "CLM_BLG_PRVDR_ZIP4_CD", "CLM_BLG_PRVDR_LCLTY_CD",
        "CLM_CNTRCT_OF_REC_CNTRCT_NUM", "CLM_CNTRCT_OF_REC_PBP_NUM",
        "CLM_SBMTR_CNTRCT_NUM", "CLM_SBMTR_CNTRCT_PBP_NUM", "CLM_TYPE_CD",
    ],
    "V2_MDCR_CLM_LINE_PRFNL": [
        "CLM_POS_PRVDR_1ST_LINE_ADR", "CLM_POS_PRVDR_2ND_LINE_ADR",
        "CLM_POS_PRVDR_CITY_NAME", "CLM_POS_PRVDR_USPS_STATE_CD",
        "CLM_POS_PRVDR_ZIP5_CD", "CLM_POS_PRVDR_ZIP4_CD",
        "GEO_BENE_SK", "CLM_DT_SGNTR_SK",
    ],
}

cfg = load_config()
conn = connect(cfg, resolve_auth(cfg))
try:
    for view, schema in VIEWS.items():
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME FROM IDRC_PRD.INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (schema, view),
            )
            actual = {r[0].upper() for r in cur.fetchall()}
        print(f"\n=== {schema}.{view}: {len(actual)} columns ===")
        missing = [c for c in REFS[view] if c.upper() not in actual]
        if missing:
            print("  MISSING (referenced but not in view):")
            for c in missing:
                # suggest near-matches
                near = sorted(a for a in actual if a[:8] == c[:8] or c[:10] in a)[:6]
                print(f"    - {c}    near: {near}")
        else:
            print("  ✓ all referenced columns exist")
finally:
    conn.close()
