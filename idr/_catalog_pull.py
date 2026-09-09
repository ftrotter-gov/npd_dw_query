"""THROWAWAY read-only catalog pull (INFORMATION_SCHEMA only — no patient data).

Enumerates every column of the deliverable-relevant views and keyword-scans all
columns across the MDCR/MDCD/SMNTC view schemas for NPD-relevant fields. Writes
one <schema>.<view>.cols.txt per target view plus a keyword_hits.txt under
idr_data/_catalog/, and prints a summary. INFORMATION_SCHEMA SELECTs only."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idr_export_common import load_config, resolve_auth, connect

TARGETS = [
    ("CMS_VDM_VIEW_MDCR_PRD",  "V2_MDCR_CLM"),
    ("CMS_VDM_VIEW_MDCR_PRD",  "V2_MDCR_CLM_LINE_PRFNL"),
    ("CMS_VDM_VIEW_MDCD_PRD",  "V2_MDCD_CLM"),
    ("CMS_VDM_VIEW_SMNTC_PRD", "V2_DIM_PRVDR_CRNT"),
    ("CMS_VDM_VIEW_MDCD_PRD",  "V2_MDCD_PRVDR_ID_CRNT"),
    ("CMS_VDM_VIEW_MDCD_PRD",  "V2_MDCD_PRVDR_DMGRPHC_CRNT"),
    ("CMS_VDM_VIEW_MDCD_PRD",  "V2_MDCD_PRVDR_LCTN_CRNT"),
]

SCHEMAS = ["CMS_VDM_VIEW_MDCR_PRD", "CMS_VDM_VIEW_MDCD_PRD", "CMS_VDM_VIEW_SMNTC_PRD"]

KEYWORDS = ["NPI", "OSCAR", "CCN", "TAX", "ZIP", "ADR", "ADDR", "CITY", "STATE",
            "LCLTY", "PLAN", "CNTRCT", "PBP", "PAYER", "SBMTR", "SPCLTY", "TXNMY",
            "PRVDR_TYPE", "BILL", "POS", "TOB", "CNTY", "GEO_"]

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "idr_data", "_catalog")
os.makedirs(OUT, exist_ok=True)

cfg = load_config()
conn = connect(cfg, resolve_auth(cfg))
try:
    # Per-target full column dumps
    for schema, view in TARGETS:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME, DATA_TYPE FROM IDRC_PRD.INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
                (schema, view),
            )
            rows = cur.fetchall()
        path = os.path.join(OUT, f"{schema}.{view}.cols.txt")
        with open(path, "w") as f:
            for name, dt in rows:
                f.write(f"{name}\t{dt}\n")
        print(f"=== {schema}.{view}: {len(rows)} columns -> {path}")

    # Keyword scan across schemas (provider/geography/payer relevant only)
    hits_path = os.path.join(OUT, "keyword_hits.txt")
    with open(hits_path, "w") as hf:
        for schema in SCHEMAS:
            for view in [t[1] for t in TARGETS if t[0] == schema]:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COLUMN_NAME FROM IDRC_PRD.INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",
                        (schema, view),
                    )
                    cols = [r[0].upper() for r in cur.fetchall()]
                for kw in KEYWORDS:
                    matched = [c for c in cols if kw in c]
                    if matched:
                        line = f"[{schema}.{view}] {kw}: {matched}"
                        hf.write(line + "\n")
    print(f"=== keyword hits -> {hits_path}")
finally:
    conn.close()
