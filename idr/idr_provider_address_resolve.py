"""
==========
IDR Provider Address Resolver  --  Medicare reassignment ladder
==========

Resolves the TRUE service-location address of a Medicare provider who has
reassigned benefits, implementing the 3-step ladder described in the PRVDR User
Forum "Reassignment Address Accuracy for NPD" recap. One SELECT, one CONFIDENCE
column, no patient identifier emitted.

WHY THIS EXISTS
  A billing address is not a service location. When an individual reassigns
  benefits to an organization (855-R), the individual inherits ALL of that org's
  practice locations, and the address that lands on the claim is the org's billing
  address -- not where the patient was actually seen. PECOS *can* carry an explicit
  reassignment practice-location address, but it is OPTIONAL and frequently blank.
  So the address has to be RESOLVED, not read. The repo already ships every raw
  ingredient as a single-table export under prvdr_enrlmt/; this is the first script
  that JOINS them into a resolved answer.

THE LADDER (each rung is more work + lower confidence than the last)
  Step 1  EXPLICIT reassignment address (optional in PECOS)
          V2_PRVDR_ENRLMT_REASGNMT_ADR_CRNT, row where
          REASGNMT_PRMRY_PRCTC_LCTN_SW = 'Y'. If present -> highest confidence,
          done. (This switch IS the forum's "is the address even in PECOS?" flag.)
  Step 2  FALLBACK to the receiving org's practice location(s)
          reassignment combination -> practice-location combination -> practice
          location -> practice-location street address. If EXACTLY ONE active
          location survives -> that is the address (high confidence). If MANY
          survive -> ambiguous, go to step 3.
  Step 3  DISAMBIGUATE many locations by claim ZIP the provider rendered at
          A candidate practice location whose ZIP5 matches a ZIP the reassigning
          NPI actually rendered at is ZIP-CONFIRMED. The rendered ZIP is taken
          POS-PREFERRED: the professional line's place-of-service ZIP
          (CLM_POS_PRVDR_ZIP5_CD, carrier/DME only -- the strong signal), falling
          back to the base line's rendering ZIP (CLM_RNDRG_PRVDR_ZIP5_CD, the
          provider's filed ZIP, carrier Part-B). ZIP_MATCH_KIND records which won.
          CRUCIAL GRAIN NOTE: the rendering NPI must come from the BASE line view
          V2_MDCR_CLM_LINE, NOT the header -- header CLM_RNDRG_PRVDR_NPI_NUM is
          populated only on institutional claims (which have no POS ZIP), so the
          old "header rendering NPI x professional-line POS ZIP" join was a dead
          join that never produced a single zip-confirmed row. See the `pos` CTE.
          Locations with no ZIP confirmation stay "needs-zip-tiebreak".

JOIN CHAIN  (all in IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD)
  V2_PRVDR_ENRLMT_REASGNMT_MDCR_ID_NPI_CMBNTN_CRNT   r    reassignment (spine)
    - one row per (reassigning NPI+MDCR_ID -> receiving NPI+MDCR_ID) combination
    - keys the whole thing: rasng identity is the provider we want an address for;
      rcvg identity is the org whose locations the individual inherited.
  V2_PRVDR_ENRLMT_REASGNMT_ADR_CRNT                  ra   step-1 explicit address
    - join on (PRVDR_RASNG_ENRLMT_ID + PRVDR_RCVG_ENRLMT_ID)
  V2_PRVDR_ENRLMT_PRCTC_LCTN_MDCR_ID_NPI_CMBNTN_CRNT c    which locations belong
    - join on the RECEIVING identity (PRVDR_ENRLMT_ID + PRVDR_MDCR_ID + PRVDR_NPI_NUM)
    - this is the table that "LINKS A MEDICARE IDENTIFIER AND NPI COMBINATION WITH
      THE PRACTICE LOCATION ADDRESS" -- it yields the PRCTC_LCTN_SK set
  V2_PRVDR_ENRLMT_PRCTC_LCTN_CRNT                    pl   location status/name
    - join on (PRVDR_ENRLMT_ID + PRCTC_LCTN_SK); keep PRCTC_LCTN_STUS_CD = 'C'
    - NOTE: this view has NO street address (only name / status / switches / phone)
  V2_PRVDR_ENRLMT_PRCTC_LCTN_AND_PAY_TO_LCTN_CRNT    pla  the ACTUAL street address
    - join on (PRVDR_ENRLMT_ID + PRCTC_LCTN_SK); this is where LINE_1_ADR / ZIP5
      actually live. It mixes PRACTICE and PAY-TO addresses distinguished by
      ADR_TYPE_CD/_DESC, so PAY-TO (a billing address, wrong for service location)
      is excluded via PRACTICE_LOCATION_ADR_TYPE_MATCH below.
  V2_MDCR_CLM (hdr) -> V2_MDCR_CLM_LINE (line) -> V2_MDCR_CLM_LINE_PRFNL (prf)  pos
    - header gates the final-action window; base line carries the line-level
      rendering NPI + rendering ZIP5; _PRFNL contributes the place-of-service ZIP
      (LEFT JOIN, 4-key + CLM_LINE_NUM, verified 1:1). Yields one (rendering NPI,
      rendered ZIP5, ZIP_MATCH_KIND) row per distinct pair. NO patient identifier
      is selected (see PII BOUNDARY).

PII BOUNDARY (IDR)
  No patient identifier is projected or even referenced. The enrollment/address
  views carry none. The claims CTE selects ONLY the line rendering NPI
  (CLM_RNDRG_PRVDR_NPI_NUM), the rendering ZIP5 (CLM_RNDRG_PRVDR_ZIP5_CD) and the
  place-of-service ZIP (CLM_POS_PRVDR_ZIP5_CD) -- no MBI, no bene-level anything.
  The GEO_BENE_SK / CLM_DT_SGNTR_SK / CLM_NUM_SK claim keys are used only inside the
  CTE to join header<->line<->prof-line and are never projected. It needs no
  small-cell suppression because it emits no beneficiary counts. Provider birth date
  is never selected.

LATEST-ROW COLLAPSE
  The _CRNT views can still carry version history with no latest-transaction flag
  (verified caveat: a _CRNT view can hold multiple effective-dated rows). Every
  candidate is therefore collapsed to one row per natural key with QUALIFY
  ROW_NUMBER() ordered by the effective/insert timestamp DESC before it can fan out
  the resolved grain.

OUTPUT GRAIN
  One row per (reassigning provider, resolved address candidate):
    - one row per reassignment that HAS a step-1 explicit address (adr_source =
      'reassignment'), PLUS
    - one row per active practice location of the receiving combination
      (adr_source = 'practice-location').
  Each row is self-describing via ADR_SOURCE + CONFIDENCE + CONFIDENCE_TIER, so a
  consumer keeps the best available rung per provider and can see why.

CONFIDENCE
  reassignment-addr   High    explicit PECOS reassignment practice-location address
  single-practice     High    exactly one active practice location for the combo
  zip-confirmed       High    one of many locations, ZIP matches a rendered claim ZIP
  needs-zip-tiebreak  Medium  one of many locations, no ZIP confirmation
  no-address          Low     combination resolves but no usable street address

  ZIP_MATCH_KIND (companion to zip-confirmed): 'pos' = confirmed by the place-of-
  service ZIP (carrier/DME, strongest); 'rendering' = confirmed by the provider's
  filed rendering ZIP (carrier Part-B); NULL on any non-zip-confirmed row.

CONFIGURABLE
  CLAIM_WINDOW_MONTHS   env or constant (default 12). The POS-ZIP tiebreak window,
                        ending CLAIM_WINDOW_LAG_MONTHS (2) back, on CLM_THRU_DT
                        with CLM_FINL_ACTN_IND = 'Y' (Medicare final action).
  PRACTICE_LOCATION_ADR_TYPE_MATCH  ILIKE pattern that keeps practice-location
                        addresses and drops pay-to. Defaults to '%PRACTICE%' on
                        ADR_TYPE_DESC -- robust to the exact ADR_TYPE_CD value.
                        Switch to a code filter once the reference value is confirmed.

Usage (Snowflake notebook / session):
    exporter = ProviderAddressResolveExporter()
    exporter.do_idr_output()

Get the SQL WITHOUT a database (design review / dry run):
    print(ProviderAddressResolveExporter().getSelectQuery())

VALIDATION TARGET
  Arkansas Heart Hospital NPI 1558653212 (the repo's canonical worked example) is a
  good smoke test: it should resolve with a single-practice / zip-confirmed rung.
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

# POS-ZIP tiebreak (step 3) window. 12 months of final-action professional lines
# is plenty to observe where a provider renders; widen if a provider is sparse.
CLAIM_WINDOW_MONTHS = int(os.environ.get("CLAIM_WINDOW_MONTHS") or 12)

# Claims lag ~2 months for final-action settling; end the window that far back.
CLAIM_WINDOW_LAG_MONTHS = int(os.environ.get("CLAIM_WINDOW_LAG_MONTHS") or 2)

# Keep practice-location addresses, drop pay-to (a billing address). The
# PRCTC_LCTN_AND_PAY_TO view mixes both, keyed by ADR_TYPE_CD/_DESC. Matching on
# the DESC is robust to the exact code; swap to `pla.ADR_TYPE_CD = '<code>'` once
# the reference value is confirmed against the IDR ADR_TYPE_CD reference table.
PRACTICE_LOCATION_ADR_TYPE_MATCH = "%PRACTICE%"

# Fully-qualified schema for every view below.
MDCR = "IDRC_PRD.CMS_VDM_VIEW_MDCR_PRD"


def _window_bounds():
    """Return (start_iso, end_iso) for the POS-ZIP window as plain date strings.
    Pure Python month arithmetic -- no dateutil, no DB, so getSelectQuery() stays
    importable without Snowflake."""
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

def build_provider_address_resolve_sql() -> str:
    """Build the reassignment address-resolution ladder as a single SELECT.

    Returned as a bare `WITH ... SELECT` (no COPY INTO) so IDROutputter can wrap it
    in `COPY INTO @~/<file> FROM ( <this> )`. Runnable stand-alone for review.
    """
    start_sql, end_sql = _window_bounds()

    return f"""WITH
-- r : reassignment spine. One row per (reassigning identity -> receiving identity)
--     combination, collapsed to the latest effective row per pair (a _CRNT view can
--     still carry effective-dated history with no latest flag).
r AS (
    SELECT
        PRVDR_RASNG_ENRLMT_ID,
        PRVDR_RCVG_ENRLMT_ID,
        RASNG_PRVDR_NPI_NUM,
        RASNG_PRVDR_MDCR_ID,
        RCVG_PRVDR_NPI_NUM,
        RCVG_PRVDR_MDCR_ID,
        PRVDR_ENRLMT_REASGNMT_EFCTV_DT
    FROM {MDCR}.V2_PRVDR_ENRLMT_REASGNMT_MDCR_ID_NPI_CMBNTN_CRNT
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY PRVDR_RASNG_ENRLMT_ID, PRVDR_RCVG_ENRLMT_ID
        ORDER BY PRVDR_ENRLMT_REASGNMT_EFCTV_DT DESC NULLS LAST, IDR_INSRT_TS DESC
    ) = 1
),

-- ra : STEP 1 -- explicit reassignment practice-location address (optional).
--      Keep only the primary practice-location address row; collapse to latest.
ra AS (
    SELECT
        PRVDR_RASNG_ENRLMT_ID,
        PRVDR_RCVG_ENRLMT_ID,
        NULLIF(TRIM(REASGNMT_LINE_1_ADR), '')      AS LINE_1_ADR,
        NULLIF(TRIM(REASGNMT_LINE_2_ADR), '')      AS LINE_2_ADR,
        NULLIF(TRIM(REASGNMT_ADR_CITY_NAME), '')   AS ADR_CITY_NAME,
        NULLIF(TRIM(REASGNMT_GEO_USPS_STATE_CD),'') AS GEO_USPS_STATE_CD,
        NULLIF(TRIM(REASGNMT_ZIP5_CD), '')         AS ZIP5_CD,
        NULLIF(TRIM(REASGNMT_ZIP4_CD), '')         AS ZIP4_CD,
        REASGNMT_PRMRY_PRCTC_LCTN_SW
    FROM {MDCR}.V2_PRVDR_ENRLMT_REASGNMT_ADR_CRNT
    WHERE REASGNMT_PRMRY_PRCTC_LCTN_SW = 'Y'
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY PRVDR_RASNG_ENRLMT_ID, PRVDR_RCVG_ENRLMT_ID
        ORDER BY PRVDR_ENRLMT_REASGNMT_EFCTV_DT DESC NULLS LAST, IDR_INSRT_TS DESC
    ) = 1
),

-- cmb : STEP 2 -- the receiving org's practice locations for THIS Medicare-ID+NPI
--       combination, joined to location status/name and to the actual street
--       address. Active only (combination not terminated + location status 'C' +
--       a practice-type address). Collapsed to one row per practice location.
cmb AS (
    SELECT
        c.PRVDR_ENRLMT_ID,
        c.PRVDR_MDCR_ID,
        c.PRVDR_NPI_NUM,
        c.PRCTC_LCTN_SK,
        pl.PRCTC_LCTN_NAME,
        pl.PRCTC_LCTN_PRMRY_SW,
        NULLIF(TRIM(pla.LINE_1_ADR), '')       AS LINE_1_ADR,
        NULLIF(TRIM(pla.LINE_2_ADR), '')       AS LINE_2_ADR,
        NULLIF(TRIM(pla.ADR_CITY_NAME), '')    AS ADR_CITY_NAME,
        NULLIF(TRIM(pla.GEO_USPS_STATE_CD),'') AS GEO_USPS_STATE_CD,
        NULLIF(TRIM(pla.ZIP5_CD), '')          AS ZIP5_CD,
        NULLIF(TRIM(pla.ZIP4_CD), '')          AS ZIP4_CD
    FROM {MDCR}.V2_PRVDR_ENRLMT_PRCTC_LCTN_MDCR_ID_NPI_CMBNTN_CRNT c
    JOIN {MDCR}.V2_PRVDR_ENRLMT_PRCTC_LCTN_CRNT pl
           ON pl.PRVDR_ENRLMT_ID = c.PRVDR_ENRLMT_ID
          AND pl.PRCTC_LCTN_SK   = c.PRCTC_LCTN_SK
    JOIN {MDCR}.V2_PRVDR_ENRLMT_PRCTC_LCTN_AND_PAY_TO_LCTN_CRNT pla
           ON pla.PRVDR_ENRLMT_ID = c.PRVDR_ENRLMT_ID
          AND pla.PRCTC_LCTN_SK   = c.PRCTC_LCTN_SK
    WHERE c.IDR_DRVD_LCTN_MDCR_ID_NPI_CMBNTN_TRMNTN_DT_SW = 'N'   -- combination still active
      AND pl.PRCTC_LCTN_STUS_CD = 'C'                             -- location current
      AND pla.ADR_TYPE_DESC ILIKE '{PRACTICE_LOCATION_ADR_TYPE_MATCH}'  -- practice, not pay-to
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY c.PRVDR_ENRLMT_ID, c.PRVDR_MDCR_ID, c.PRVDR_NPI_NUM, c.PRCTC_LCTN_SK
        ORDER BY pla.PRVDR_LCTN_ADR_BGN_DT DESC NULLS LAST, pla.IDR_INSRT_TS DESC
    ) = 1
),

-- cnt : how many active practice locations survived per receiving combination.
--       Drives single-practice vs. needs-tiebreak.
cnt AS (
    SELECT PRVDR_ENRLMT_ID, PRVDR_MDCR_ID, PRVDR_NPI_NUM,
           COUNT(*) AS PRACTICE_LOCATION_COUNT
    FROM cmb
    GROUP BY PRVDR_ENRLMT_ID, PRVDR_MDCR_ID, PRVDR_NPI_NUM
),

-- pos : STEP 3 tiebreak fuel -- distinct ZIP5s each provider actually rendered at,
--       from recent final-action carrier/DME lines. NO patient identifier selected.
--
-- GRAIN GOTCHA (the reason this CTE looks the way it does): the rendering NPI and
-- the place-of-service ZIP live on DIFFERENT tables at DIFFERENT grains, and the
-- obvious "header rendering NPI x professional-line POS ZIP" join is a DEAD JOIN --
-- header CLM_RNDRG_PRVDR_NPI_NUM is populated ONLY on institutional claims
-- (40/60/62/63/30/50/10) which have NO professional lines, while POS ZIP exists ONLY
-- on carrier/DME lines (71/72/81/82) whose header rendering NPI is NULL. The two
-- predicates never co-occur on one claim, so it produced zero rows at any window
-- width. The rendering IDENTITY at line grain is on the BASE line view
-- V2_MDCR_CLM_LINE (CLM_RNDRG_PRVDR_NPI_NUM + CLM_RNDRG_PRVDR_ZIP5_CD on the same
-- row); the true PLACE-OF-SERVICE ZIP is on the professional line V2_..._PRFNL.
--
-- So: header (window/final-action gate) -> base line (rendering NPI + rendering
-- ZIP5) -> LEFT JOIN _PRFNL (POS ZIP) on the 4-key + CLM_LINE_NUM (verified 1:1, no
-- fan-out). Per line the tiebreak ZIP is POS-PREFERRED, rendering-ZIP fallback:
-- COALESCE(POS ZIP, rendering ZIP5), with ZIP_MATCH_KIND recording which won --
-- 'pos' is the strong place-of-service signal (carrier/DME), 'rendering' is the
-- provider's filed ZIP (near practice, carrier Part-B only). The inner select is
-- then collapsed to one row per (NPI, ZIP5); MIN(ZIP_MATCH_KIND) keeps the stronger
-- kind ('pos' sorts before 'rendering') and guarantees the tiebreak LEFT JOIN below
-- cannot fan out a practice location into duplicate rows.
pos AS (
    SELECT
        RNDRG_NPI,
        RNDRG_ZIP5,
        MIN(ZIP_MATCH_KIND) AS ZIP_MATCH_KIND
    FROM (
        SELECT
            NULLIF(TRIM(line.CLM_RNDRG_PRVDR_NPI_NUM), '') AS RNDRG_NPI,
            LEFT(COALESCE(
                NULLIF(TRIM(prf.CLM_POS_PRVDR_ZIP5_CD), ''),
                NULLIF(TRIM(line.CLM_RNDRG_PRVDR_ZIP5_CD), '')
            ), 5)                                          AS RNDRG_ZIP5,
            CASE
                WHEN NULLIF(TRIM(prf.CLM_POS_PRVDR_ZIP5_CD), '') IS NOT NULL
                    THEN 'pos'
                ELSE 'rendering'
            END                                            AS ZIP_MATCH_KIND
        FROM {MDCR}.V2_MDCR_CLM hdr
        JOIN {MDCR}.V2_MDCR_CLM_LINE line
               ON line.GEO_BENE_SK     = hdr.GEO_BENE_SK
              AND line.CLM_DT_SGNTR_SK = hdr.CLM_DT_SGNTR_SK
              AND line.CLM_NUM_SK      = hdr.CLM_NUM_SK
              AND line.CLM_TYPE_CD     = hdr.CLM_TYPE_CD
        LEFT JOIN {MDCR}.V2_MDCR_CLM_LINE_PRFNL prf
               ON prf.GEO_BENE_SK     = line.GEO_BENE_SK
              AND prf.CLM_DT_SGNTR_SK = line.CLM_DT_SGNTR_SK
              AND prf.CLM_NUM_SK      = line.CLM_NUM_SK
              AND prf.CLM_TYPE_CD     = line.CLM_TYPE_CD
              AND prf.CLM_LINE_NUM    = line.CLM_LINE_NUM
        WHERE hdr.CLM_THRU_DT      >= DATE '{start_sql}'
          AND hdr.CLM_THRU_DT       < DATE '{end_sql}'
          AND hdr.CLM_FINL_ACTN_IND = 'Y'
          AND line.CLM_RNDRG_PRVDR_NPI_NUM IS NOT NULL
          AND COALESCE(
                NULLIF(TRIM(prf.CLM_POS_PRVDR_ZIP5_CD), ''),
                NULLIF(TRIM(line.CLM_RNDRG_PRVDR_ZIP5_CD), '')
              ) IS NOT NULL
    ) per_line
    GROUP BY RNDRG_NPI, RNDRG_ZIP5
),

-- ROW-SET B : one row per active practice location (step 2 / step 3).
locations AS (
    SELECT
        r.RASNG_PRVDR_NPI_NUM,
        r.RASNG_PRVDR_MDCR_ID,
        r.PRVDR_RASNG_ENRLMT_ID,
        r.RCVG_PRVDR_NPI_NUM,
        r.RCVG_PRVDR_MDCR_ID,
        r.PRVDR_RCVG_ENRLMT_ID,
        r.PRVDR_ENRLMT_REASGNMT_EFCTV_DT,
        cmb.PRCTC_LCTN_SK,
        cmb.PRCTC_LCTN_NAME,
        cmb.PRCTC_LCTN_PRMRY_SW              AS REASSIGNMENT_PRIMARY_SW,
        cmb.LINE_1_ADR,
        cmb.LINE_2_ADR,
        cmb.ADR_CITY_NAME,
        cmb.GEO_USPS_STATE_CD,
        cmb.ZIP5_CD,
        cmb.ZIP4_CD,
        'practice-location'                  AS ADR_SOURCE,
        cnt.PRACTICE_LOCATION_COUNT,
        CASE WHEN pos.RNDRG_ZIP5 IS NOT NULL THEN 'Y' ELSE 'N' END AS ZIP_CONFIRMED,
        pos.ZIP_MATCH_KIND
    FROM r
    JOIN cmb
           ON cmb.PRVDR_ENRLMT_ID = r.PRVDR_RCVG_ENRLMT_ID
          AND cmb.PRVDR_MDCR_ID   = r.RCVG_PRVDR_MDCR_ID
          AND cmb.PRVDR_NPI_NUM   = r.RCVG_PRVDR_NPI_NUM
    JOIN cnt
           ON cnt.PRVDR_ENRLMT_ID = cmb.PRVDR_ENRLMT_ID
          AND cnt.PRVDR_MDCR_ID   = cmb.PRVDR_MDCR_ID
          AND cnt.PRVDR_NPI_NUM   = cmb.PRVDR_NPI_NUM
    -- ZIP tiebreak: does THIS location's ZIP match a ZIP the reassigning provider
    -- actually rendered at? (rendering NPI = the individual, not the billing org.)
    -- pos is unique per (NPI, ZIP5), so this LEFT JOIN cannot fan out the location.
    LEFT JOIN pos
           ON pos.RNDRG_NPI  = r.RASNG_PRVDR_NPI_NUM
          AND pos.RNDRG_ZIP5 = cmb.ZIP5_CD
),

-- ROW-SET A : the explicit step-1 reassignment address, when present.
explicit AS (
    SELECT
        r.RASNG_PRVDR_NPI_NUM,
        r.RASNG_PRVDR_MDCR_ID,
        r.PRVDR_RASNG_ENRLMT_ID,
        r.RCVG_PRVDR_NPI_NUM,
        r.RCVG_PRVDR_MDCR_ID,
        r.PRVDR_RCVG_ENRLMT_ID,
        r.PRVDR_ENRLMT_REASGNMT_EFCTV_DT,
        CAST(NULL AS NUMBER)                 AS PRCTC_LCTN_SK,
        CAST(NULL AS TEXT)                   AS PRCTC_LCTN_NAME,
        ra.REASGNMT_PRMRY_PRCTC_LCTN_SW      AS REASSIGNMENT_PRIMARY_SW,
        ra.LINE_1_ADR,
        ra.LINE_2_ADR,
        ra.ADR_CITY_NAME,
        ra.GEO_USPS_STATE_CD,
        ra.ZIP5_CD,
        ra.ZIP4_CD,
        'reassignment'                       AS ADR_SOURCE,
        COALESCE(cnt.PRACTICE_LOCATION_COUNT, 0) AS PRACTICE_LOCATION_COUNT,
        'N'                                  AS ZIP_CONFIRMED,
        CAST(NULL AS TEXT)                   AS ZIP_MATCH_KIND
    FROM r
    JOIN ra
           ON ra.PRVDR_RASNG_ENRLMT_ID = r.PRVDR_RASNG_ENRLMT_ID
          AND ra.PRVDR_RCVG_ENRLMT_ID  = r.PRVDR_RCVG_ENRLMT_ID
    LEFT JOIN cnt
           ON cnt.PRVDR_ENRLMT_ID = r.PRVDR_RCVG_ENRLMT_ID
          AND cnt.PRVDR_MDCR_ID   = r.RCVG_PRVDR_MDCR_ID
          AND cnt.PRVDR_NPI_NUM   = r.RCVG_PRVDR_NPI_NUM
),

resolved AS (
    SELECT * FROM explicit
    UNION ALL
    SELECT * FROM locations
)

SELECT
    RASNG_PRVDR_NPI_NUM,
    RASNG_PRVDR_MDCR_ID,
    PRVDR_RASNG_ENRLMT_ID,
    RCVG_PRVDR_NPI_NUM,
    RCVG_PRVDR_MDCR_ID,
    PRVDR_RCVG_ENRLMT_ID,
    PRVDR_ENRLMT_REASGNMT_EFCTV_DT,
    ADR_SOURCE,
    PRCTC_LCTN_SK,
    PRCTC_LCTN_NAME,
    REASSIGNMENT_PRIMARY_SW,
    LINE_1_ADR,
    LINE_2_ADR,
    ADR_CITY_NAME,
    GEO_USPS_STATE_CD,
    ZIP5_CD,
    ZIP4_CD,
    PRACTICE_LOCATION_COUNT,
    ZIP_CONFIRMED,
    -- Which claim ZIP confirmed this location: 'pos' = place-of-service ZIP
    -- (carrier/DME, strong); 'rendering' = provider's filed rendering ZIP (near
    -- practice, carrier Part-B); NULL when this row was not zip-confirmed.
    ZIP_MATCH_KIND,
    -- The rung that produced this row.
    CASE
        WHEN ADR_SOURCE = 'reassignment'                        THEN 'reassignment-addr'
        WHEN PRACTICE_LOCATION_COUNT = 1                        THEN 'single-practice'
        WHEN ZIP_CONFIRMED = 'Y'                                THEN 'zip-confirmed'
        WHEN LINE_1_ADR IS NULL AND ZIP5_CD IS NULL            THEN 'no-address'
        ELSE 'needs-zip-tiebreak'
    END AS CONFIDENCE,
    CASE
        WHEN ADR_SOURCE = 'reassignment'                        THEN 'High'
        WHEN PRACTICE_LOCATION_COUNT = 1                        THEN 'High'
        WHEN ZIP_CONFIRMED = 'Y'                                THEN 'High'
        WHEN LINE_1_ADR IS NULL AND ZIP5_CD IS NULL            THEN 'Low'
        ELSE 'Medium'
    END AS CONFIDENCE_TIER
FROM resolved"""


# ============================================================================
# EXPORTER
# ============================================================================

class ProviderAddressResolveExporter(IDROutputter):
    """Resolve Medicare provider service-location addresses via the reassignment
    ladder (explicit reassignment address -> practice-location join -> claim
    POS-ZIP tiebreak), emitting a CONFIDENCE column. Subclasses IDROutputter so the
    COPY INTO / GET scaffolding is inherited; only getSelectQuery() is custom."""

    version_number: str = "v01"
    file_name_stub: str = "idr_provider_address_resolve"

    def getSelectQuery(self) -> str:
        return build_provider_address_resolve_sql()


if __name__ == "__main__":
    # Execute the export using the IDROutputter framework.
    exporter = ProviderAddressResolveExporter()
    exporter.do_idr_output()

# To download use:
# snowsql -c cms_idr -q "GET @~/ file://. PATTERN='.*.csv';"
# Or look in ../misc_scripts/ for download_and_merge_all_snowflake_csv.sh
