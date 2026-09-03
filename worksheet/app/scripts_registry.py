"""
Worksheet registry for the IDR dashboard.

Two kinds of things show up in the left-hand browser:

1. WORKSHEETS — curated, editable, runnable SQL. Each is tagged with an expected
   `behavior`:
     "works" — inline result over the connector (± small CSV to S3). Proven to run
               in-VPC today.
     "hangs" — bulk COPY→GET relay. Wired, but hangs in-VPC until the S3 interface
               endpoint (Path A) is provisioned. Included on purpose so you can see
               the dashboard surface a hang clearly (heartbeat + Cancel).

2. REPO SCRIPTS — the actual idr/ and idr2/ Python files, listed for reference so
   you can browse them and copy their SQL into a worksheet. (Running the full
   parametrised .py extracts end-to-end is the relay/bulk path — same Path A gate.)
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]   # .../npd_dw_query

# Fully-qualified source tables (from idr_npi_oscar_crosswalk.py).
_NPI_OSCAR = "IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD.V2_MDCR_PRVDR_NPI_OSCAR"
_DIM_PRVDR = "IDRC_PRD.CMS_VDM_VIEW_SMNTC_PRD.V2_DIM_PRVDR_CRNT"

_SAMPLE_JOIN = f"""SELECT
    D.PRVDR_NPI_NUM,
    O.PRVDR_OSCAR_NUM,
    O.PRVDR_NPI_OSCAR_NAME,
    O.GEO_ZIP4_CD
FROM {_NPI_OSCAR} AS O
LEFT JOIN {_DIM_PRVDR} AS D
    ON D.PRVDR_SK = O.PRVDR_SK"""


def _indent(block, spaces=4):
    pad = " " * spaces
    return "\n".join(pad + ln for ln in block.splitlines())


WORKSHEETS = [
    {
        "id": "connection_check",
        "group": "① Test — works now",
        "title": "Connection check",
        "behavior": "works",
        "mode": "inline",
        "s3_default": False,
        "description": "Confirms the PrivateLink connection and shows the role / "
                       "warehouse the PAT resolves to. Inline result, no S3.",
        "sql": ("SELECT CURRENT_ACCOUNT() AS ACCOUNT,\n"
                "       CURRENT_ROLE()      AS ROLE,\n"
                "       CURRENT_WAREHOUSE() AS WAREHOUSE,\n"
                "       CURRENT_USER()      AS \"USER\",\n"
                "       CURRENT_TIMESTAMP() AS NOW;"),
    },
    {
        "id": "npi_oscar_sample_10",
        "group": "① Test — works now",
        "title": "NPI↔OSCAR sample (10 rows → S3)",
        "behavior": "works",
        "mode": "inline",
        "s3_default": True,
        "description": "The exact 10-row inline pull proven to land on S3 from the "
                       "VPC (612 B smoketest). Edit the LIMIT / columns freely. Small "
                       "results write straight to the S3 path above via boto3.",
        "sql": _SAMPLE_JOIN + "\nLIMIT 10;",
    },
    {
        "id": "npi_oscar_full_relay",
        "group": "② Test — hangs until Path A",
        "title": "NPI↔OSCAR FULL crosswalk (bulk COPY→GET)",
        "behavior": "hangs",
        "mode": "relay",
        "filename": "ws_npi_oscar_crosswalk.csv",
        "s3_default": True,
        "description": "Full ~3.46M-row crosswalk via COPY INTO @~/ then GET → S3. "
                       "This is the bulk path; it will HANG at the GET from inside the "
                       "VPC until the S3 interface endpoint (Path A ticket) is "
                       "provisioned. Use it to watch the dashboard report a hang.",
        "sql": (
            "COPY INTO @~/ws_npi_oscar_crosswalk.csv\n"
            "FROM (\n"
            f"{_indent(_SAMPLE_JOIN)}\n"
            ")\n"
            "FILE_FORMAT = (TYPE=CSV FIELD_OPTIONALLY_ENCLOSED_BY='\"' "
            "COMPRESSION=NONE)\n"
            "HEADER = TRUE\n"
            "SINGLE = TRUE MAX_FILE_SIZE = 5000000000 OVERWRITE = TRUE;"
        ),
    },
]


def list_worksheets():
    return [{k: v for k, v in w.items()} for w in WORKSHEETS]


def get_worksheet(wid):
    for w in WORKSHEETS:
        if w["id"] == wid:
            return w
    return None


# ---------------------------------------------------------------------------
# Repo script browser (reference / copy source into a worksheet).
# ---------------------------------------------------------------------------

def list_repo_scripts():
    out = []
    for sub in ("idr", "idr2"):
        d = REPO_ROOT / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.py")):
            if p.name.startswith("_") or p.name == "__init__.py":
                continue
            out.append({
                "path": f"{sub}/{p.name}",
                "group": f"{sub}/ scripts",
                "title": p.name,
                "summary": _first_docline(p),
            })
    return out


def _first_docline(p):
    try:
        txt = p.read_text(errors="replace")
    except OSError:
        return ""
    # crude module-docstring first-line grab
    for marker in ('"""', "'''"):
        if marker in txt:
            after = txt.split(marker, 2)
            if len(after) >= 2:
                body = after[1].strip().splitlines()
                if body:
                    return body[0].strip()
    return ""


def get_repo_script_source(rel_path):
    # rel_path like "idr/idr_npi_oscar_crosswalk.py" — constrained to idr/ or idr2/
    parts = Path(rel_path)
    if parts.parts[:1][0] not in ("idr", "idr2") or ".." in parts.parts:
        raise ValueError("path not allowed")
    full = (REPO_ROOT / parts).resolve()
    if not str(full).startswith(str(REPO_ROOT)) or not full.is_file():
        raise ValueError("path not found")
    return full.read_text(errors="replace")
