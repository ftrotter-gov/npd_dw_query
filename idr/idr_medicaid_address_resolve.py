"""
==========
IDR Medicaid Address Resolver  --  location + address-type ladder
==========

The Medicaid counterpart to idr_provider_address_resolve.py (Medicare). Resolves
the TRUE service-location address of a Medicaid provider, implementing the same
3-step ladder shape adapted to Medicaid's data model. One SELECT, one CONFIDENCE
column, no patient identifier emitted.

WHY MEDICAID IS DIFFERENT FROM MEDICARE
  Medicare's problem is REASSIGNMENT: an individual reassigns benefits to an org
  and inherits all the org's practice locations, so the claim's billing address is
  not where the patient was seen. Medicaid has no reassignment ladder. Its problem
  is instead:
    (a) ADDRESS TYPE -- each provider LOCATION carries up to four addresses
        (1 billing / 2 mailing / 3 practice / 4 service-location). A billing or
        mailing address is not a service location, so the wrong type is the wrong
        answer; and
    (b) MANY LOCATIONS -- a provider (state + State Medicaid ID) can have several
        locations, so even after picking the right address TYPE you may have
        several candidate places and must disambiguate.
  Medicaid IDs are only unique WITHIN a submitting state, so every join and every
  grain in here carries SUBMTG_MDCD_LCL_STATE_CD. Dropping it cross-matches
  different providers in different states.

THE LADDER (each rung is more work + lower confidence than the last)
  Step 1  PICK THE RIGHT ADDRESS TYPE for each location
          V2_MDCD_PRVDR_LCTN_CRNT holds up to four address-type rows per location.
          Choose one by priority 4 (service-location) > 3 (practice) > 1 (billing)
          > 2 (mailing) -- service first, to match the claims extract's
          orientation. ADR_TYPE_GRADE records whether the winner was a real
          'service' address (4/3) or only a 'billing' fallback (1/2).
  Step 2  COUNT the provider's locations
          If EXACTLY ONE active location survives -> that is the address (high
          confidence, 'single-location'). If MANY survive -> ambiguous, go to
          step 3.
  Step 3  DISAMBIGUATE many locations by claim service-location ZIP
          V2_MDCD_CLM is a single table carrying, on the header, the submitting
          state, the billing provider's Medicaid ID, the provider LOCATION id, and
          the service-location ZIP. A candidate location whose registered ZIP5
          matches a ZIP the provider actually billed service from -- on the SAME
          (state, Medicaid ID, location) key -- is ZIP-CONFIRMED. This is a tighter
          bind than the Medicare resolver, which can only tie on rendering NPI.

JOIN CHAIN  (all in IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD)
  V2_MDCD_PRVDR_LCTN_CRNT       loc  the spine + the actual street address
    - key (SUBMTG_MDCD_LCL_STATE_CD + PRVDR_STATE_MDCD_ID + PRVDR_LCTN_ID +
      PRVDR_MDCD_ADR_TYPE_CD); one best address picked per location.
  V2_MDCD_PRVDR_ID_CRNT         npi  fold the provider's NPI (id-type 2)
    - LONG format, one row per id-type; id-type 7 (SSN) is provider PII and is
      NEVER read. NPI folded 1:1 per (state, Medicaid ID). LEFT JOIN -- atypical
      providers legitimately have no NPI.
  V2_MDCD_PRVDR_DMGRPHC_CRNT    dem  fold the provider name (context only)
    - per (state, Medicaid ID). Individual + org/legal names only. Birth date,
      death date and sex are on this view and are NEVER selected (provider PII).
  V2_MDCD_CLM                   pos  distinct (state, Medicaid ID, location, ZIP5)
    - recent final-action window; the only claims touched, and NO patient
      identifier is selected (see PII BOUNDARY).

PII BOUNDARY (IDR)
  No patient identifier is projected or referenced. V2_MDCD_CLM carries plenty
  (CLM_MBI_NUM, CLM_RCPNT_* names, CLM_RCPNT_BIRTH_DT, CLM_RCPNT_STATE_MDCD_ID) --
  the pos CTE selects NONE of them, only the billing provider's state/Medicaid-ID/
  location and the service-location ZIP. No small-cell suppression is needed
  because no beneficiary counts are emitted. Provider SSN (id-type 7) is excluded
  from the id fold, and provider birth/death/sex are never selected.

LATEST-ROW COLLAPSE
  These _CRNT views carry dated version history with NO IDR_LTST_TRANS_FLG column
  (verified 2026-09-07: V2_MDCD_PRVDR_ID_CRNT is ~2.17 dated versions per
  id-record). Every candidate is therefore collapsed to one row per natural key
  with QUALIFY ROW_NUMBER() ordered by PRVDR_SRC_EFCTV_DT DESC (tie-broken by
  IDR_UPDT_TS DESC) before it can fan out the resolved grain -- the same discipline
  the vetted idr_medicaid_id_crosswalk.py uses on these exact views.

OUTPUT GRAIN
  One row per (provider, active location):
    - provider = (SUBMTG_MDCD_LCL_STATE_CD, PRVDR_STATE_MDCD_ID), with NPI folded
      in when present;
    - one row per PRVDR_LCTN_ID, carrying that location's best-type address.
  Each row is self-describing via ADR_TYPE_GRADE + CONFIDENCE + CONFIDENCE_TIER, so
  a consumer keeps the best available rung per provider and can see why.

CONFIDENCE
  single-location     High    exactly one ADDRESSABLE location for the provider
  zip-confirmed       High    one of many locations, ZIP matches a billed service ZIP
  needs-zip-tiebreak  Medium  one of many locations, no ZIP confirmation
  no-address          Low     not addressable -- no usable ZIP and no full street
  (ADR_TYPE_GRADE = 'billing' is an orthogonal down-weight signal: the location's
   only address was a billing/mailing type, not a service/practice one.)

  ADDRESSABLE = has a ZIP, or a full street+city+state. This screens out TMSIS
  placeholder rows (e.g. Texas "ALL INCLUSIVE ADDRESS LINE 1" pseudo-locations that
  carry junk line-1 but null state/ZIP): they are flagged no-address and excluded
  from LOCATION_COUNT, so a provider with one real location + one placeholder still
  reads as single-location. Placeholder shapes are state-submission artifacts and
  vary by state; the ZIP-tiebreak also protects against them (they can never be
  zip-confirmed).

CONFIGURABLE
  CLAIM_WINDOW_MONTHS   env or constant (default 12). The service-ZIP tiebreak
                        window, ending CLAIM_WINDOW_LAG_MONTHS (2) back, on
                        CLM_THRU_DT with CLM_FINL_ACTN_IND = 'T' (Medicaid final
                        action is the T/F domain, NOT Medicare's Y/N).
  ADR_TYPE_PRIORITY     the 4>3>1>2 preference order used to pick one address per
                        location. Service-location first; billing/mailing last.

Usage (Snowflake notebook / session):
    exporter = MedicaidAddressResolveExporter()
    exporter.do_idr_output()

Get the SQL WITHOUT a database (design review / dry run):
    print(MedicaidAddressResolveExporter().getSelectQuery())
"""

import os
from datetime import date

# Import the IDROutputter base class (same tolerant import the other exports use).
try:
    from IDROutputter import IDROutputter
except ImportError:  # pragma: no cover - notebook path
    print("Loading IDROutputter from previous cell or add proper import path")


# ============================================================================
# CONFIGURATION
# ============================================================================

# Service-ZIP tiebreak (step 3) window. 12 months of final-action claims is
# plenty to observe where a provider bills service from; widen if a provider is
# sparse.
CLAIM_WINDOW_MONTHS = int(os.environ.get("CLAIM_WINDOW_MONTHS") or 12)

# Claims lag ~2 months for final-action settling; end the window that far back.
CLAIM_WINDOW_LAG_MONTHS = int(os.environ.get("CLAIM_WINDOW_LAG_MONTHS") or 2)

# Fully-qualified schema for every view below.
MDCD = "IDRC_PRD.CMS_VDM_VIEW_MDCD_PRD"

# Address-type domain (V2_MDCD_PRVDR_ID_TYPE_CD family, verified against
# idr_medicaid_id_crosswalk.py): 1 billing / 2 mailing / 3 practice /
# 4 service-location. We prefer a real service location, then practice, then fall
# back to billing/mailing only if that is all the location has.
ADR_TYPE_CD_SERVICE_LOCATION = "4"
ADR_TYPE_CD_PRACTICE = "3"
ADR_TYPE_CD_BILLING = "1"
ADR_TYPE_CD_MAILING = "2"

# NPI id-type in the Medicaid long-format id view. (7 = SSN is NEVER read.)
ID_TYPE_CD_NPI = "2"


def _window_bounds():
    """Return (start_iso, end_iso) for the service-ZIP window as plain date
    strings. Pure Python month arithmetic -- no dateutil, no DB, so
    getSelectQuery() stays importable without Snowflake."""
    def shift_months(d: date, months_back: int) -> date:
        total = (d.year * 12 + (d.month - 1)) - months_back
        year, month = divmod(total, 12)
        return date(year, month + 1, 1)

    today = date.today()
    end = shift_months(today, CLAIM_WINDOW_LAG_MONTHS)
    start = shift_months(end, CLAIM_WINDOW_MONTHS)
    return start.isoformat(), end.isoformat()


# ============================================================================
# RESOLVER QUERY
# ============================================================================

def build_medicaid_address_resolve_sql() -> str:
    """Build the Medicaid location/address-type resolution ladder as a single
    SELECT.

    Returned as a bare `WITH ... SELECT` (no COPY INTO) so IDROutputter can wrap it
    in `COPY INTO @~/<file> FROM ( <this> )`. Runnable stand-alone for review.
    """
    start_sql, end_sql = _window_bounds()

    # IDR normalizes missing values inconsistently: some columns are empty string,
    # others carry the '~' sentinel. Strip BOTH to NULL (matches the vetted
    # idr_medicaid_id_crosswalk.py convention on these same views). {{c}} is a raw
    # column reference.
    def scrub(c: str) -> str:
        return f"NULLIF(NULLIF(TRIM({c}), ''), '~')"

    def scrub_zip5(c: str) -> str:
        return f"LEFT({scrub(c)}, 5)"

    return f"""WITH
-- loc : STEP 1 -- one best address per provider LOCATION. Each location carries up
--       to four address-type rows; pick service-location (4) > practice (3) >
--       billing (1) > mailing (2), collapsing dated version history to the latest
--       effective row (these _CRNT views carry history with no latest flag).
loc AS (
    SELECT
        SUBMTG_MDCD_LCL_STATE_CD,
        PRVDR_STATE_MDCD_ID,
        PRVDR_LCTN_ID,
        PRVDR_MDCD_ADR_TYPE_CD,
        CASE
            WHEN PRVDR_MDCD_ADR_TYPE_CD IN ('{ADR_TYPE_CD_SERVICE_LOCATION}',
                                            '{ADR_TYPE_CD_PRACTICE}') THEN 'service'
            ELSE 'billing'
        END                                        AS ADR_TYPE_GRADE,
        {scrub('PRVDR_LINE_1_ADR')}                 AS LINE_1_ADR,
        {scrub('PRVDR_LINE_2_ADR')}                 AS LINE_2_ADR,
        {scrub('PRVDR_LINE_3_ADR')}                 AS LINE_3_ADR,
        {scrub('PRVDR_ADR_CITY_NAME')}              AS ADR_CITY_NAME,
        {scrub('PRVDR_ADR_STATE_CD')}               AS ADR_STATE_CD,
        {scrub('PRVDR_ADR_ZIP_CD')}                 AS ZIP_CD,
        {scrub_zip5('PRVDR_ADR_ZIP_CD')}            AS ZIP5_CD,
        -- Is this a resolvable service location at all? A real one has a ZIP, or a
        -- full street+city+state. This screens out TMSIS placeholder rows (e.g.
        -- Texas "ALL INCLUSIVE ADDRESS LINE 1" pseudo-locations, which carry junk
        -- line-1 but null state/ZIP) so they neither inflate the location count nor
        -- masquerade as a single-location high-confidence answer.
        CASE
            WHEN {scrub_zip5('PRVDR_ADR_ZIP_CD')} IS NOT NULL
              OR ({scrub('PRVDR_LINE_1_ADR')}   IS NOT NULL
                  AND {scrub('PRVDR_ADR_CITY_NAME')} IS NOT NULL
                  AND {scrub('PRVDR_ADR_STATE_CD')}  IS NOT NULL)
            THEN TRUE ELSE FALSE
        END                                          AS IS_ADDRESSABLE
    FROM {MDCD}.V2_MDCD_PRVDR_LCTN_CRNT
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY SUBMTG_MDCD_LCL_STATE_CD, PRVDR_STATE_MDCD_ID, PRVDR_LCTN_ID
        ORDER BY
            CASE PRVDR_MDCD_ADR_TYPE_CD
                WHEN '{ADR_TYPE_CD_SERVICE_LOCATION}' THEN 1
                WHEN '{ADR_TYPE_CD_PRACTICE}'         THEN 2
                WHEN '{ADR_TYPE_CD_BILLING}'          THEN 3
                WHEN '{ADR_TYPE_CD_MAILING}'          THEN 4
                ELSE 5
            END ASC,
            PRVDR_SRC_EFCTV_DT DESC NULLS LAST,
            IDR_UPDT_TS DESC
    ) = 1
),

-- cnt : how many ADDRESSABLE locations the provider has (placeholder rows do not
--       count). Drives single-location vs. needs-tiebreak.
cnt AS (
    SELECT SUBMTG_MDCD_LCL_STATE_CD, PRVDR_STATE_MDCD_ID,
           COUNT_IF(IS_ADDRESSABLE) AS LOCATION_COUNT
    FROM loc
    GROUP BY SUBMTG_MDCD_LCL_STATE_CD, PRVDR_STATE_MDCD_ID
),

-- npi : fold the provider's NPI (id-type 2) from the long-format id view. SSN
--       (id-type 7) is provider PII and is NEVER read. Collapse dated history to
--       one NPI per (state, Medicaid ID). LEFT-joined later -- atypical providers
--       legitimately have none.
npi AS (
    SELECT
        SUBMTG_MDCD_LCL_STATE_CD,
        PRVDR_STATE_MDCD_ID,
        {scrub('PRVDR_ID')} AS PRVDR_NPI_NUM
    FROM {MDCD}.V2_MDCD_PRVDR_ID_CRNT
    WHERE PRVDR_MDCD_ID_TYPE_CD = '{ID_TYPE_CD_NPI}'
      AND {scrub('PRVDR_ID')} IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY SUBMTG_MDCD_LCL_STATE_CD, PRVDR_STATE_MDCD_ID
        ORDER BY PRVDR_SRC_EFCTV_DT DESC NULLS LAST, IDR_UPDT_TS DESC
    ) = 1
),

-- dem : fold the provider name for context. Individual + org/legal names only;
--       birth date, death date and sex live here and are NEVER selected.
dem AS (
    SELECT
        SUBMTG_MDCD_LCL_STATE_CD,
        PRVDR_STATE_MDCD_ID,
        {scrub('PRVDR_ORG_NAME')}  AS PRVDR_ORG_NAME,
        {scrub('PRVDR_LGL_NAME')}  AS PRVDR_LGL_NAME,
        {scrub('PRVDR_LAST_NAME')} AS PRVDR_LAST_NAME,
        {scrub('PRVDR_1ST_NAME')}  AS PRVDR_1ST_NAME,
        PRVDR_FAC_GRP_INDVDL_CD
    FROM {MDCD}.V2_MDCD_PRVDR_DMGRPHC_CRNT
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY SUBMTG_MDCD_LCL_STATE_CD, PRVDR_STATE_MDCD_ID
        ORDER BY PRVDR_SRC_EFCTV_DT DESC NULLS LAST, IDR_UPDT_TS DESC
    ) = 1
),

-- pos : STEP 3 tiebreak fuel -- distinct service-location ZIP5s each provider
--       actually billed from, keyed by the SAME (state, Medicaid ID, location)
--       the location spine uses. Recent final-action claims only (T/F domain).
--       NO patient identifier is selected.
pos AS (
    SELECT DISTINCT
        SUBMTG_MDCD_LCL_STATE_CD                 AS STATE_CD,
        {scrub('CLM_BLG_PRVDR_MDCD_ID')}         AS MDCD_ID,
        {scrub('CLM_PRVDR_LCTN_ID')}             AS LCTN_ID,
        {scrub_zip5('CLM_SRVC_LCTN_ZIP_CD')}     AS SRVC_ZIP5
    FROM {MDCD}.V2_MDCD_CLM
    WHERE CLM_THRU_DT      >= DATE '{start_sql}'
      AND CLM_THRU_DT       < DATE '{end_sql}'
      AND CLM_FINL_ACTN_IND = 'T'
      AND CLM_BLG_PRVDR_MDCD_ID IS NOT NULL
      AND CLM_SRVC_LCTN_ZIP_CD  IS NOT NULL
),

resolved AS (
    SELECT
        loc.SUBMTG_MDCD_LCL_STATE_CD,
        loc.PRVDR_STATE_MDCD_ID,
        npi.PRVDR_NPI_NUM,
        loc.PRVDR_LCTN_ID,
        dem.PRVDR_ORG_NAME,
        dem.PRVDR_LGL_NAME,
        dem.PRVDR_LAST_NAME,
        dem.PRVDR_1ST_NAME,
        dem.PRVDR_FAC_GRP_INDVDL_CD,
        loc.PRVDR_MDCD_ADR_TYPE_CD,
        loc.ADR_TYPE_GRADE,
        loc.LINE_1_ADR,
        loc.LINE_2_ADR,
        loc.LINE_3_ADR,
        loc.ADR_CITY_NAME,
        loc.ADR_STATE_CD,
        loc.ZIP_CD,
        loc.IS_ADDRESSABLE,
        cnt.LOCATION_COUNT,
        CASE WHEN pos.SRVC_ZIP5 IS NOT NULL THEN 'Y' ELSE 'N' END AS ZIP_CONFIRMED
    FROM loc
    JOIN cnt
           ON cnt.SUBMTG_MDCD_LCL_STATE_CD = loc.SUBMTG_MDCD_LCL_STATE_CD
          AND cnt.PRVDR_STATE_MDCD_ID      = loc.PRVDR_STATE_MDCD_ID
    LEFT JOIN npi
           ON npi.SUBMTG_MDCD_LCL_STATE_CD = loc.SUBMTG_MDCD_LCL_STATE_CD
          AND npi.PRVDR_STATE_MDCD_ID      = loc.PRVDR_STATE_MDCD_ID
    LEFT JOIN dem
           ON dem.SUBMTG_MDCD_LCL_STATE_CD = loc.SUBMTG_MDCD_LCL_STATE_CD
          AND dem.PRVDR_STATE_MDCD_ID      = loc.PRVDR_STATE_MDCD_ID
    -- ZIP tiebreak: does THIS location's registered ZIP match a service ZIP the
    -- provider actually billed from, on the same (state, Medicaid ID, location)?
    LEFT JOIN pos
           ON pos.STATE_CD  = loc.SUBMTG_MDCD_LCL_STATE_CD
          AND pos.MDCD_ID   = loc.PRVDR_STATE_MDCD_ID
          AND pos.LCTN_ID   = loc.PRVDR_LCTN_ID
          AND pos.SRVC_ZIP5 = loc.ZIP5_CD
)

SELECT
    SUBMTG_MDCD_LCL_STATE_CD,
    PRVDR_STATE_MDCD_ID,
    PRVDR_NPI_NUM,
    PRVDR_LCTN_ID,
    PRVDR_ORG_NAME,
    PRVDR_LGL_NAME,
    PRVDR_LAST_NAME,
    PRVDR_1ST_NAME,
    PRVDR_FAC_GRP_INDVDL_CD,
    PRVDR_MDCD_ADR_TYPE_CD,
    ADR_TYPE_GRADE,
    LINE_1_ADR,
    LINE_2_ADR,
    LINE_3_ADR,
    ADR_CITY_NAME,
    ADR_STATE_CD,
    ZIP_CD,
    LOCATION_COUNT,
    ZIP_CONFIRMED,
    -- The rung that produced this row.
    CASE
        WHEN NOT IS_ADDRESSABLE  THEN 'no-address'
        WHEN LOCATION_COUNT = 1  THEN 'single-location'
        WHEN ZIP_CONFIRMED = 'Y' THEN 'zip-confirmed'
        ELSE 'needs-zip-tiebreak'
    END AS CONFIDENCE,
    CASE
        WHEN NOT IS_ADDRESSABLE  THEN 'Low'
        WHEN LOCATION_COUNT = 1  THEN 'High'
        WHEN ZIP_CONFIRMED = 'Y' THEN 'High'
        ELSE 'Medium'
    END AS CONFIDENCE_TIER
FROM resolved"""


# ============================================================================
# EXPORTER
# ============================================================================

class MedicaidAddressResolveExporter(IDROutputter):
    """Resolve Medicaid provider service-location addresses via the location /
    address-type ladder (pick service-type address -> single-location check ->
    claim service-ZIP tiebreak), emitting a CONFIDENCE column. Subclasses
    IDROutputter so the COPY INTO / GET scaffolding is inherited; only
    getSelectQuery() is custom."""

    version_number: str = "v01"
    file_name_stub: str = "idr_medicaid_address_resolve"

    def getSelectQuery(self) -> str:
        return build_medicaid_address_resolve_sql()


if __name__ == "__main__":
    # Execute the export using the IDROutputter framework.
    exporter = MedicaidAddressResolveExporter()
    exporter.do_idr_output()

# To download use:
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
