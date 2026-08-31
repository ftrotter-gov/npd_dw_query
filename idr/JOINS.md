# IDR wide extracts + crosswalks — join guide

How the four deliverables link together. **NPI is the common spine** across both
programs and both extracts; the crosswalks turn the NPIs (and, for Medicare, the
OSCAR) carried in the extracts into names, addresses, TINs, and alternate IDs.

Datasets:

| File (prefix) | Grain | Patient count col | Small-cell suppressed |
|---|---|---|---|
| `idr_medicare_entity_link_address_wide` | 1 row per (billing TIN, billing NPI, 7 role NPIs, POS address) | `CNT_BENE` (distinct MBI) | yes — 11+ only |
| `idr_medicaid_entity_link_address_wide` | 1 row per (4 role NPIs, service-location address) | `CNT_RECIPIENTS` (distinct recipient) | yes — 11+ only |
| `idr_npi_oscar_crosswalk` | association: NPI ↔ OSCAR/CCN (+ dates) | — | n/a (reference) |
| `idr_medicaid_id_crosswalk` | long: 1 row per (provider, ID-type, location) | — | n/a (reference) |

No patient identifiers are emitted anywhere — only the aggregate counts above.

---

## Medicare crosswalk — `idr_npi_oscar_crosswalk` (NPI ↔ OSCAR/CCN)

Join keys (bold) and enrichment:

IDR-internal surrogate keys (`PRVDR_SK`, `GEO_SK`, `META_SK`, `META_SRC_SK`) are
**not emitted** — they are IDR plumbing with no join value to a consumer (joins
run on NPI and OSCAR, both business keys). `PRVDR_SK` is still used internally to
resolve the NPI; it just isn't in the output.

| Column | Meaning | Join role |
|---|---|---|
| **`PRVDR_NPI_NUM`** | Provider NPI (resolved from the source `PRVDR_SK`) | **JOIN → any NPI column in the Medicare extract** (billing/org or the 7 role NPIs) |
| **`PRVDR_OSCAR_NUM`** | OSCAR / CCN institutional identifier | **JOIN → `CLM_BLG_PRVDR_OSCAR_NUM`** in the Medicare extract |
| `PRVDR_NPI_OSCAR_BGN_DT` / `_END_DT` | NPI↔OSCAR association begin/end dates | time-scope a match |
| `CLM_CNTRCTR_NUM` | Medicare contractor number | context |
| `PRVDR_NPI_OSCAR_MDCR_BGN_DT` / `_END_DT` | Medicare enrollment begin/end dates | time-scope a match |
| `PRVDR_NPI_OSCAR_NAME` | Provider name on the OSCAR record | enrichment |
| `PRVDR_NPI_OSCAR_FED_TAX_NUM` | Federal tax number (TIN/EIN) | **cross-check → `CLM_BLG_PRVDR_TAX_NUM`** in the extract |
| `PRVDR_NPI_OSCAR_LINE_1_ADR` / `_2_ADR` | Provider street address (line 2 sparse ~29%) | enrichment |
| `PRVDR_NPI_OSCAR_INVLD_PLC_NAME` / `_ZIP_CD` / `_STATE_CD` | Legacy city/ZIP/state (kept as coarse geography) | legacy |
| `GEO_ZIP4_CD` | Geographic ZIP+4 (the real ZIP) | enrichment |
| `PRVDR_NPI_OSCAR_PHNE_NUM` | Phone | enrichment |
| `PRVDR_NPI_OSCAR_TYPE_CD` | Provider/association type (sparse ~33%) | context |
| `PRVDR_LGCY_ADR_TYPE_CD` | Legacy address type | context |

**Joining to the Medicare extract** — two paths, either direction:

- `medicare_extract.<any NPI column>` = `npi_oscar.PRVDR_NPI_NUM`
  → that provider's OSCAR, name, TIN, address, enrollment dates.
- `medicare_extract.CLM_BLG_PRVDR_OSCAR_NUM` = `npi_oscar.PRVDR_OSCAR_NUM`
  → the reverse: OSCAR → NPI / identity.

**Caveat:** this is an *association* table — one NPI can map to several OSCARs
over time, so a naive join can fan out. Dedupe, or filter on the begin/end dates
for a point-in-time match.

---

## Medicaid crosswalk — `idr_medicaid_id_crosswalk` (provider identity + alternate IDs)

Long/tall: one row per (provider, ID-type, location), so a provider appears on
many rows.

| Column | Meaning | Join role |
|---|---|---|
| **`PRVDR_STATE_MDCD_ID`** | State-assigned Medicaid provider ID | **provider key (part 1)** |
| **`SUBMTG_MDCD_LCL_STATE_CD`** | Submitting state code | **provider key (part 2)** — IDs are state-scoped; always pair with the ID |
| `PRVDR_LCTN_ID` | Provider location id | key part 3 (ties to the folded address) |
| **`PRVDR_MDCD_ID_TYPE_CD`** | ID type: 1 state id / **2 NPI** / 3 Medicare id / 4 NCPDP / 5 fed tax / 6 state tax / 8 other / 9 old state id (**SSN=7 excluded**) | **filter to pick which ID `PRVDR_ID` holds** |
| `PRVDR_MDCD_ID_TYPE_DESC` | Decoded ID-type description | readable label |
| **`PRVDR_ID`** | The identifier value for this ID-type | **when `TYPE_CD='2'` this is the NPI → JOIN to Medicaid extract NPIs** |
| `PRVDR_ID_ISSG_ENT_ID` | Issuing entity | context |
| `PRVDR_SRC_EFCTV_DT` / `_END_DT` | Source effective/end dates of the ID association | time-scope |
| `PRVDR_LAST_NAME` / `_1ST_NAME` / `_MDL_INITL_NAME` | Individual provider name | enrichment |
| `PRVDR_ORG_NAME` / `_LGL_NAME` / `_DBA_NAME` | Org / legal / DBA name | enrichment |
| `PRVDR_FAC_GRP_INDVDL_CD` | Facility / group / individual classification | context |
| `PRVDR_MDCD_ADR_TYPE_CD` | Folded-address type (1 billing / 2 mailing / 3 practice / 4 service-location; priority 4>3>1>2) | context |
| `PRVDR_LINE_1_ADR` / `_2_ADR` / `_3_ADR` | Provider street address | enrichment |
| `PRVDR_ADR_CITY_NAME` / `_STATE_CD` / `_ZIP_CD` / `_CNTY_CD` | City / state / ZIP / county | enrichment |
| `PRVDR_PHNE_NUM` | Phone | enrichment |

**Joining to the Medicaid extract** — the extract carries NPIs
(`CLM_ADMTG_ / CLM_BLG_ / CLM_SPRVSNG_ / CLM_SRVC_LCTN_ORG_PRVDR_NPI_NUM`) but
this crosswalk is keyed on State Medicaid ID, so bridge through the NPI rows:

1. Filter the crosswalk to `PRVDR_MDCD_ID_TYPE_CD = '2'` (NPI rows only).
2. Join `medicaid_extract.<NPI column>` = `medicaid_id.PRVDR_ID`
   → resolves the NPI to a `(PRVDR_STATE_MDCD_ID, SUBMTG_MDCD_LCL_STATE_CD)` key.
3. With that state-ID key, pull name/address/phone, and re-query the crosswalk on
   the same key with other `PRVDR_MDCD_ID_TYPE_CD` values to get the provider's
   other identifiers — Medicare id (3), NCPDP (4), tax ids (5/6), etc.

**Caveat:** always carry `SUBMTG_MDCD_LCL_STATE_CD` with `PRVDR_STATE_MDCD_ID` —
the same numeric ID can exist in different states.

---

## Cross-program bridge (Medicaid ↔ Medicare)

To link a Medicaid provider to their Medicare identity, hop across the shared NPI:

```
medicaid_id_crosswalk.PRVDR_ID   (where PRVDR_MDCD_ID_TYPE_CD = '2')   -- an NPI
      = npi_oscar_crosswalk.PRVDR_NPI_NUM
      -> npi_oscar_crosswalk.PRVDR_OSCAR_NUM                            -- OSCAR/CCN
```

And either extract's role NPIs join straight to the same NPI spine, so a provider
seen rendering in Medicare and billing in Medicaid resolves to one identity.

---

## Worked join sketches (SQL-ish)

Medicare extract → biller identity:

```sql
SELECT e.*, x.PRVDR_NPI_OSCAR_NAME, x.PRVDR_NPI_OSCAR_FED_TAX_NUM,
       x.PRVDR_OSCAR_NUM
FROM   medicare_extract        e
LEFT   JOIN npi_oscar_crosswalk x
       ON x.PRVDR_NPI_NUM = e.CLM_BLG_PRVDR_NPI_NUM
      -- optional point-in-time: AND <claim date> BETWEEN x.BGN_DT AND x.END_DT
```

Medicaid extract → rendering/billing identity (bridge on NPI rows):

```sql
SELECT e.*, x.PRVDR_LAST_NAME, x.PRVDR_1ST_NAME, x.PRVDR_ORG_NAME,
       x.PRVDR_STATE_MDCD_ID, x.SUBMTG_MDCD_LCL_STATE_CD
FROM   medicaid_extract          e
LEFT   JOIN medicaid_id_crosswalk x
       ON x.PRVDR_ID = e.CLM_BLG_PRVDR_NPI_NUM
      AND x.PRVDR_MDCD_ID_TYPE_CD = '2'          -- NPI rows only
```
