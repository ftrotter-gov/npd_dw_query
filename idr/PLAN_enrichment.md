# PLAN — IDR claims-derived NPD extracts: enrichment + bug-fix + merge

Author: ANSHUMAN (discovery/planning). Status: ready for PO review, then Redwood build.
Date: 2026-09-07. Catalog pulled LIVE from `cms-idr.privatelink` (see section 6).

Governing rules: nash-standard, idr-query, data-pipeline, security-gate.
**Hard PII boundary: patient identifiers (MBI `CLM_BENE_MBI_ID`, recipient
`CLM_RCPNT_STATE_MDCD_ID`, `GEO_BENE_SK`) appear ONLY inside `COUNT(DISTINCT …)`
+ the small-cell `HAVING`. They are NEVER projected. No patient data leaves in
any file. Provider birth date (`PRVDR_BIRTH_DT`) and Medicaid demographic
birth/death/sex are also NOT emitted.**

---

## 1. Scope

**In scope**
1. Enrich the four deliverables (Medicare, Medicaid, entity linkage, NPI↔OSCAR /
   Medicaid-ID crosswalks) with provider-identity, geography, specialty/taxonomy,
   provider-type, type-of-bill, payer/plan/contract, and POS columns that IDR
   carries but the current SQL does not pull — **adding columns, dropping none.**
2. Fix the confirmed correctness bugs (join grain, final-action filter,
   population-dropping filter, doc drift).
3. Merge entity linkage INTO the Medicare and Medicaid extracts → **one combined
   Medicare file + one combined Medicaid file** (linkage = every role NPI in its
   own column on one row = the co-occurrence affiliation, already the wide design).
4. Deliver the crosswalks as **separate reference files** (they have no claim
   window and a different grain/key).

**Out of scope / forbidden**
- Any projection of a patient identifier; any patient-level file. (Counts only.)
- Provider SSN (Medicaid id-type 7 — already excluded), provider birth/death/sex.
- Data leaving CMS boundaries beyond the existing laptop→(optional S3) relay.
- Schema/plumbing surrogate keys with no consumer value (`PRVDR_SK`, `META_SK`,
  `GEO_*_SK`) stay internal, matching current practice.

---

## 2. Approach — output design

### 2.1 Confirmed bugs to fix first (correctness-critical)

| # | File | Bug | Fix |
|---|---|---|---|
| A | `idr_medicare_entity_link_address_wide.py` L210-212 | header↔line join is 2-key `(GEO_BENE_SK, CLM_DT_SGNTR_SK)` → fans each claim's providers onto the POS addresses of the bene's *other* same-signature claims (idr-query rule #2) | add `AND CLINE.CLM_NUM_SK = CLAIM.CLM_NUM_SK` (both views carry `CLM_NUM_SK`, verified) |
| A2 | same + `idr_medicaid_entity_link_address_wide.py` | JOINS.md §"Both wide extracts carry `CLM_POS_CD`" is FALSE — Medicare wide has no POS column at all, Medicaid wide never pulls the `CLM_POS_CD` that exists on its table | Medicaid: add `CLM_POS_CD`. Medicare: there is **no `CLM_POS_CD`** on `V2_MDCR_CLM` or `V2_MDCR_CLM_LINE_PRFNL` — correct JOINS.md; the Medicare POS *place* is the street-address block already carried, plus line `CLM_PRCNG_LCLTY_CD`/`CLM_PRVDR_SPCLTY_CD` |
| B | `idr_medicaid_entity_link_address_wide.py` L143-145 | **no `CLM_FINL_ACTN_IND='T'`** → ~8.5% non-final (original+adjustment+voided) rows double-count recipients (idr-query rule #1; domain is T/F not Y/N) | add `AND CLM_FINL_ACTN_IND = 'T'` (matches the fixed `idr_medicaid_address.py` L137) |
| C | `idr_medicare_entity_link_address.py` (long) L158-160 | same 2-key fan-out as A | add `CLM_NUM_SK` to the join (or retire the file — see 2.4) |
| D | `idr_entity_linkage.py` L241-242 | `relationship_claims` requires `CLM_BLG_PRVDR_OSCAR_NUM IS NOT NULL` → the **entire** output is restricted to institutional billers carrying an OSCAR; the whole professional-claim population (physicians/groups, the majority of billers) is dropped | drop the OSCAR-not-null predicate; carry OSCAR as a passthrough (blank for professional), as the long address variant already does (L269-276) — or retire in favor of the combined Medicare file |
| E | window key drift | Medicare wide/header/linkage filter `CLM_FROM_DT`; Medicaid + the fixed `idr_medicare_address.py` filter `CLM_THRU_DT` | pick ONE per program and apply everywhere (recommend `CLM_THRU_DT` to match the corrected non-wide references). Low blast radius at 24mo; see open Q |

Corroboration of A/B: `run_all_pulls.sh` and `run_extracts_only.sh` comments assert
"claim-grain join fix + POS code" were applied to the wide extracts — the SQL
contains **neither**. Intent diverged from code (false-green). This is exactly the
"prove against the real artifact" scar.

### 2.2 Combined MEDICARE file (linkage merged in)

`idr_medicare_combined_wide` — supersedes the two wide Medicare extracts + the long
linkage + the non-wide address by unifying header-population and POS-address:

```
 V2_MDCR_CLM (header, ALL claim types A/B/C/D, FINAL='Y')
   grain spine: billing TIN + every role NPI (own column) + OSCAR/CCN identity
                + header geography + specialty/taxonomy/provider-type/type-of-bill
                + plan/contract + CLM_TYPE_CD
        │  LEFT JOIN  (3-key: GEO_BENE_SK + CLM_DT_SGNTR_SK + CLM_NUM_SK)
        ▼
 V2_MDCR_CLM_LINE_PRFNL (professional line, where present)
   adds: POS street address block + POS provider/org name + line specialty/locality
        │  GROUP BY the whole signature (POS cols in-grain; NULL for non-professional)
        ▼
   COUNT(DISTINCT CLM_BENE_MBI_ID) AS CNT_BENE   HAVING > 10   (CMS 11+)
        │  LEFT JOIN V2_DIM_PRVDR_CRNT on billing NPI (1:1, verified) to fill OSCAR
```

The LEFT join recovers the institutional/MA/PDE population the current INNER-join
wide drops, while still attaching the street address for professional claims. POS
columns join the grain (a claim with N distinct POS addresses → N rows), so this
is the largest/most expensive pull — see 2.6 cost + open Q on whether to keep it
as one file vs. header-primary + POS-companion.

**Proposed column order** (all patient-free): `CLM_BLG_PRVDR_TAX_NUM`,
`CLM_BLG_PRVDR_OSCAR_NUM` (from DIM), `CLM_BLG_PRVDR_FULL_CCN_NUM`,
`CLM_BLG_PRVDR_OSCAR_STATE_CD`, `CLM_BLG_PRVDR_OSCAR_FAC_CD` →
role NPIs: `CLM_BLG_PRVDR_NPI_NUM`, `CLM_ATNDG_/OPRTG_/OTHR_/RFRG_/RNDRG_/SRVC_/FAC_PRVDR_NPI_NUM`,
`CLM_FAC_PRVDR_CPO_ORG_NPI_ID`, **+ new** `CLM_ALTRNT_SRVC_PRVDR_NPI_NUM`,
`CLM_PRSCRBNG_PRVDR_NPI_NUM`, `CLM_PCP_NPI_NUM` →
geography: `CLM_BLG_PRVDR_USPS_STATE_CD`, `_ZIP5_CD`, `_ZIP4_CD`, `_LCLTY_CD`,
**+ new** `CLM_BLG_PRVDR_CNTY_CD` →
specialty/taxonomy/type **(new)**: `CLM_BLG_PRVDR_TYPE_CD`,
`CLM_BLG_FED_PRVDR_SPCLTY_CD`, `CLM_BLG_PRVDR_TXNMY_CD` (+ per-role spclty/txnmy
if kept) →
type-of-bill **(new)**: `CLM_BILL_FAC_TYPE_CD`, `CLM_BILL_CLSFCTN_CD`,
`CLM_BILL_FREQ_CD` →
payer/plan: `CLM_CNTRCT_OF_REC_CNTRCT_NUM`, `_PBP_NUM`, `CLM_SBMTR_CNTRCT_NUM`,
`_PBP_NUM`, **+ new** `CLM_PLAN_CD`, `CLM_LCL_PLAN_CD`, `CLM_SBMTR_ID` →
POS block (line): `CLM_POS_PRVDR_1ST_LINE_ADR`, `_2ND_LINE_ADR`, `_CITY_NAME`,
`_USPS_STATE_CD`, `_ZIP5_CD`, `_ZIP4_CD`, **+ new** `CLM_POS_PHYSN_ORG_NAME`,
`CLM_POS_PRVDR_1ST_NAME`, `CLM_POS_PRVDR_MDL_NAME`, line `CLM_PRVDR_SPCLTY_CD`,
`CLM_PRCNG_LCLTY_CD` → `CLM_TYPE_CD` → `CNT_BENE`.

### 2.3 Combined MEDICAID file (linkage merged in)

`idr_medicaid_combined_wide` — one query over `V2_MDCD_CLM` (single table, both
header attributes and `CLM_POS_CD` live here, so no header↔line fan-out risk):

Filters: window on `CLM_THRU_DT`, **`CLM_FINL_ACTN_IND='T'`** (bug B),
`CLM_RCPNT_STATE_MDCD_ID IS NOT NULL`. Grain = all role NPIs + addresses +
codes; `COUNT(DISTINCT CLM_RCPNT_STATE_MDCD_ID) AS CNT_RECIPIENTS  HAVING > 10`.

**Proposed columns** (patient-free): role NPIs `CLM_ADMTG_/BLG_/SPRVSNG_PRVDR_NPI_NUM`,
`CLM_SRVC_LCTN_ORG_NPI_NUM`, **+ new** `CLM_RFRG_PRVDR_NPI_NUM`,
`CLM_RFRG_PRVDR_NPI_2_NUM`, `CLM_ORDRG_PRVDR_NPI_NUM`, `CLM_PRSCRBNG_PRVDR_NPI_NUM`,
`CLM_RX_DSPNSNG_PRVDR_NPI_NUM`, `CLM_HLTH_HOME_PRVDR_NPI_NUM` →
service-location address: `CLM_SRVC_LCTN_LINE_1_ADR`, `_2_ADR`, `_CITY_NAME`,
`_STATE_CD`, `_ZIP_CD` →
**+ new** billing-provider address on claim: `CLM_BLG_PRVDR_LINE_1_ADR`, `_2_ADR`,
`CLM_BLG_PRVDR_CITY_NAME`, `_STATE_CD`, `_ZIP_CD` →
specialty/taxonomy/type **(new)**: `CLM_ADMTG_/BLG_PRVDR_SPCLTY_CD`,
`CLM_ADMTG_/BLG_/OPRTG_PRVDR_TXNMY_CD`, `CLM_ADMTG_/BLG_PRVDR_TYPE_CD` →
type-of-bill / POS **(new)**: `CLM_TOB_CD`, `CLM_BILL_FCLTY_TYPE_CD`,
`CLM_BILL_CLSFCTN_CD`, `CLM_POS_CD` →
payer **(new)**: `CLM_PLAN_NUM`, `CLM_SBMTR_ID` → `CNT_RECIPIENTS`.

### 2.4 Retire vs. keep the long/non-wide variants

The combined files subsume: `idr_medicare_entity_link_address_wide`,
`idr_medicare_header_wide`, `idr_medicare_entity_link_address` (long),
`idr_medicare_address`, `idr_entity_linkage`, `idr_medicaid_entity_link_address_wide`,
`idr_medicaid_address`. **Recommend retiring the long/duplicate ones** (subtract
before you add) — but this is a PO call (open Q 5). If any are kept, apply the
A–E fixes to them regardless.

### 2.5 Crosswalks — separate files, optionally enriched

Keep **two** reference files (no window, different grain/key; do NOT merge — a
Medicare NPI↔OSCAR association and a Medicaid state-ID long table have no common
grain):

- `idr_npi_oscar_crosswalk` — unchanged join (verified 1:1, 100% NPI resolve).
  Optional enrichment from the already-joined `V2_DIM_PRVDR_CRNT`: add provider
  type `PRVDR_TYPE_CD`, composite taxonomy `PRVDR_TXNMY_CMPST_CD`, alternate IDs
  `PRVDR_NCPDP_ID`/`PRVDR_DMEPOS_NUM`/`PRVDR_UPIN_NUM`/`PRVDR_PIN_NUM`/
  `PRVDR_EMPLR_ID_NUM`/`PRVDR_STATE_LCNS_NUM`, practice/mailing address
  `PRVDR_PRCTC_LINE_1/2_ADR`+`GEO_PRVDR_PRCTC_ZIP4_CD` / `PRVDR_MLG_*`. **Exclude
  `PRVDR_BIRTH_DT`.**
- `idr_medicaid_id_crosswalk` — unchanged (SSN excluded, `_CRNT` already latest).
  Optional: add `PRVDR_TAX_NAME` (org) if wanted; birth/death/sex stay excluded.

### 2.6 Enrichment tags (which view, adds-rows?, patient-free?)

All rows below are **patient-free**. "adds rows" = joins the aggregation grain and
can fragment/raise the row count (matters for the 11+ suppression floor).

| Column(s) | Category | View | Adds rows to grain? |
|---|---|---|---|
| `CLM_ALTRNT_SRVC_/PRSCRBNG_/PCP_NPI_NUM` (MDCR); `CLM_RFRG_/RFRG_2/ORDRG_/PRSCRBNG_/RX_DSPNSNG_/HLTH_HOME_NPI_NUM` (MDCD) | provider-identity | V2_MDCR_CLM / V2_MDCD_CLM | yes (extra role columns widen the signature) |
| `CLM_BLG_PRVDR_CNTY_CD` (MDCR); `CLM_BLG_PRVDR_*` address (MDCD) | geography | headers | yes |
| `CLM_POS_PHYSN_ORG_NAME`, `CLM_POS_PRVDR_1ST_/MDL_NAME` | provider-identity/geo | MDCR line | yes |
| `CLM_*_FED_PRVDR_SPCLTY_CD`, `CLM_PRVDR_SPCLTY_CD` (line); `CLM_*_PRVDR_SPCLTY_CD` (MDCD) | specialty | headers/line | yes |
| `CLM_*_PRVDR_TXNMY_CD` | taxonomy | headers | yes |
| `CLM_BLG_PRVDR_TYPE_CD`, `CLM_ADMTG_PRVDR_TYPE_CD` | provider-type | headers | yes |
| `CLM_BILL_FAC_TYPE_CD`/`CLSFCTN_CD`/`FREQ_CD` (MDCR); `CLM_TOB_CD`/`BILL_FCLTY_TYPE_CD`/`BILL_CLSFCTN_CD` (MDCD) | type-of-bill | headers | yes |
| `CLM_POS_CD` (MDCD only — no MDCR equivalent) | POS | V2_MDCD_CLM | yes |
| `CLM_PLAN_CD`/`CLM_LCL_PLAN_CD`/`CLM_SBMTR_ID` (MDCR); `CLM_PLAN_NUM`/`CLM_SBMTR_ID` (MDCD) | payer-plan | headers | **yes — fragments beneficiary counts, pushes cells under 11+** |
| `PRVDR_TYPE_CD`, `PRVDR_TXNMY_CMPST_CD`, alt-IDs, practice/mailing addr | identity/geo/specialty | V2_DIM_PRVDR_CRNT | crosswalk only (1:1, no fan) |

Because every added grain column fragments the distinct-beneficiary cells, more
cells fall under the 11+ floor — enrichment slightly **reduces** surviving rows
and total counts. Payer/plan fragments hardest (varies per beneficiary enrollment).

---

## 3. Acceptance criteria (numbered, each checkable against a real artifact)

1. **PII exclusion (spine):** `head -1` of every delivered CSV header contains NO
   token matching `MBI|BENE_ID|BENE_MBI|RCPNT|RECIP|GEO_BENE_SK|BIRTH|SSN|DOB`
   (grep must return zero). Only aggregate `CNT_BENE`/`CNT_RECIPIENTS` present.
2. **Medicare header↔line join uses `CLM_NUM_SK`:** the combined-Medicare SQL
   contains `CLINE.CLM_NUM_SK = CLAIM.CLM_NUM_SK` (grep); the 2-key-only form is
   absent.
3. **Medicaid final-action:** the combined-Medicaid SQL contains
   `CLM_FINL_ACTN_IND = 'T'` (grep) and does NOT contain `CLM_FINL_ACTN_IND = 'Y'`.
4. **Medicare final-action:** the combined-Medicare SQL contains
   `CLM_FINL_ACTN_IND = 'Y'` (grep).
5. **No column loss:** the combined Medicare header set ⊇ current
   `idr_medicare_entity_link_address_wide.schema.csv` ∪ `idr_medicare_header_wide`
   columns; combined Medicaid set ⊇ current
   `idr_medicaid_entity_link_address_wide.schema.csv`. Diff shows only additions.
6. **Entity-linkage population not dropped:** if `idr_entity_linkage.py` is kept,
   its SQL no longer contains `CLM_BLG_PRVDR_OSCAR_NUM IS NOT NULL` as a row
   filter; a 1-month dry-run yields **more** distinct `org_npi` than the OSCAR-only
   version (proves the professional population returned).
7. **Fan-out reduction (dry-run, 1 month):** post-`CLM_NUM_SK` combined-Medicare
   `COUNT(*)` and `SUM(CNT_BENE)` are **≤** the pre-fix 2-key values (the fix can
   only remove spurious rows, never add). Report both numbers.
8. **POS present where claimed:** combined-Medicaid header contains `CLM_POS_CD`;
   JOINS.md's "both wide extracts carry `CLM_POS_CD`" line is corrected to reflect
   that Medicare has no such column.
9. **Enrichment columns present:** each column in the 2.2/2.3 lists appears in the
   corresponding delivered header (grep per column).
10. **Crosswalks separate + keyed:** `idr_npi_oscar_crosswalk` still 1:1 on
    `PRVDR_SK` (row-in == row-out) with `PRVDR_NPI_NUM` col 1;
    `idr_medicaid_id_crosswalk` still excludes id-type 7 (no SSN rows).
11. **Compiles:** `python -m py_compile` passes on every changed `.py`.
12. **Catalog-verified columns:** every column named in the final SQL exists in
    `idr_data/_catalog/*.cols.txt` (re-run `_catalog_check.py`-style verifier;
    zero MISSING).
13. **Disk/relay guard intact:** the size-probe-before-GET path
    (`stage_dir_bytes` → plain/gzip/abort) is preserved on the combined Medicare
    extract (it is the large one).

---

## 4. Blast radius & risks

- **Prod IDR egress:** read-only `IDRSF_PAT_USER_P` on `IDRC_PRD_COMM_WH`;
  extracts unload to the internal user stage, GET to laptop, optional S3. No prod
  writes. Catalog pull was INFORMATION_SCHEMA only.
- **Row-explosion / statement timeout at 24mo:** the combined-Medicare LEFT JOIN
  (header ∪ professional line, POS in-grain) is the most expensive pull; the long
  self-join variant already hit the 4-hour cap. Mitigation: the `CLM_NUM_SK` fix
  *reduces* fan-out; keep the multi-file `SINGLE=FALSE` unload + size-probe guard;
  dry-run 1 month first. If it still blows the cap, fall back to header-primary +
  POS-companion (open Q 3).
- **Disk:** header-grain × wide signature × 24mo can be tens of GB plain; the
  existing measure-before-download + gzip/abort logic must stay.
- **PII boundary:** the ONLY risk is a projected patient id — criterion 1 grep is
  the fail-closed gate; run it on the actual delivered header, negative test first.
- **Small-cell floor:** more grain columns → more sub-11 cells suppressed;
  payer/plan in-grain fragments counts most. Correctness-safe but reduces yield.
- **Correctness-critical vs. nice-to-have:** A, B, C, D (+ E consistency) are
  correctness — they change counts/population and must ship. All section-2.6
  enrichment columns are additive nice-to-have — they cannot corrupt counts, only
  widen grain.

---

## 5. Open questions for the PO

1. **Window length + key:** keep 24 months? Standardize the filter on `CLM_THRU_DT`
   (matches the corrected non-wide references) or `CLM_FROM_DT` (current wide)?
2. **Payer/plan in-grain?** Contract/PBP/plan fragment beneficiary counts and push
   many cells under the 11+ floor. Keep them in the grain (payer overlay, fewer
   surviving rows) or emit a separate provider↔plan edge file so the main
   provider/geography rows keep maximal counts?
3. **One combined Medicare file or two?** Single LEFT-join file (all types + POS
   address, biggest/most expensive) vs. header-primary (all types, ZIP+4) + a
   POS-address companion (professional only, street). Cost may force the latter.
4. **Crosswalk enrichment:** fold the `V2_DIM_PRVDR_CRNT` taxonomy/provider-type/
   alt-IDs/practice-address into `idr_npi_oscar_crosswalk`, or leave it lean?
5. **Retire the long/duplicate extracts** (`idr_medicare_entity_link_address` long,
   `idr_entity_linkage`, the two non-wide `*_address`) once the combined files
   land, or keep them (fixed) in parallel?
6. **Medicare POS code:** confirmed there is NO `CLM_POS_CD` on Medicare views —
   the POS is represented by the street-address block + line locality/specialty.
   Acceptable, or does the PO need a decoded place-of-service *code* sourced some
   other way (e.g. a line HCPCS/POS reference not in these two views)?

---

## 6. Catalog pull — provenance

Ran LIVE 2026-09-07 via `idr/_catalog_pull.py` (throwaway, INFORMATION_SCHEMA
SELECTs only) against `cms-idr.privatelink`, role `IDRSF_PAT_USER_P`, wh
`IDRC_PRD_COMM_WH`. Connectivity over ZPA synthetic IP 100.64.x. Dumps saved to
`idr_data/_catalog/`:
- `V2_MDCR_CLM` = 231 cols, `V2_MDCR_CLM_LINE_PRFNL` = 79, `V2_MDCD_CLM` = 247,
  `V2_DIM_PRVDR_CRNT` = 39, `V2_MDCD_PRVDR_ID_CRNT` = 17,
  `V2_MDCD_PRVDR_DMGRPHC_CRNT` = 29, `V2_MDCD_PRVDR_LCTN_CRNT` = 27.
- `keyword_hits.txt` — the NPI/OSCAR/CCN/TAX/ZIP/ADR/CITY/STATE/LCLTY/PLAN/CNTRCT/
  PBP/SBMTR/SPCLTY/TXNMY/PRVDR_TYPE/BILL/POS/TOB/CNTY/GEO scan behind section 2.6.
- `CLM_NUM_SK` verified present (NUMBER) on both `V2_MDCR_CLM` and
  `V2_MDCR_CLM_LINE_PRFNL` (bug A/C fix is feasible).
- `CLM_POS_CD` verified present on `V2_MDCD_CLM`, absent on both Medicare views.

Nothing here needs further catalog confirmation before Redwood builds — every
proposed column was read from the live catalog. Verify exact `CLM_TYPE_CD` /
`CLM_POS_CD` code decodes against IDR reference tables at build time if labels are
wanted (raw codes are emitted otherwise).
