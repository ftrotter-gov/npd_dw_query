VRDC Entity Columns
========

I am performing entity-level analysis across multiple medical claims benefit settings. Each benefit setting has two associated tables:
 • A claim-level table
 • A claim-line-level table

 The resulting queries will always join the claim to the claim line... so as long as the columns are uniquely named, they can live in the same select statements. For convenience to add to a SQL query.. the last result in the tree should be string that looks like: 

 ```sql
    CLAIM.this_colum AS this_column
 ```

or

 ```sql
    CLINE.that_colum AS that_column
 ```

For each setting, I have documented which entity identifiers are available and how they are named. The identifiers of interest fall into four conceptual “levels”:
 • TIN / EIN (tax identifiers) — sometimes missing
 • CCN — sometimes missing
 • Organizational NPI
 • Personal NPI

Different benefit settings contain different subsets of these four levels. In addition, the available fields may appear:
 • Only at the claim level
 • Only at the claim-line level
 • On both — but sometimes under different names, requiring aliasing. For the aliasing, we will return both the original column name and its alias, every time.. and alias even when we do not need to.

I also have a detailed mapping (in Markdown) that specifies exactly which identifiers exist for each setting, where they live (claim vs. line), and what renaming rules are required.

My immediate goal is to build logic that can iterate across these settings and correctly handle:
 • Presence or absence of each of the four levels
 • Correct field name for the level when present
 • Correct table (claim or line) to read from
 • Special-case renaming when the same logical variable is named differently across tables
 • Skipping missing levels without breaking the iteration

Once that iteration logic is correct, I will build a canonical table merging data from the four columns in each of the settings.. so the structure should have five levels:
 •  Setting (all lower case please)
 • Tax ID (nullable)
 • CCN (nullable)
 • Organizational NPI
 • Personal NPI

I will then generate all valid permutations for each benefit setting and use that structure to join back to claims to build a hierarchical entity view.

For the insitutional format, when a column is missing it should just not be in the returned data structure.

I would like to have a python function in vrdc/entity_looper.py that will return a dictionary of the data below in a manner that will allow me to correctly loop over the five levels.

Lets have a class that stores the data structure and several functions on that class that return different useful iterations of the underlying data.

Do not erase or modify this file as you code.

## bcarrier

### bcarrier Claim

* TAX_NUM -> TAX_NUM
* No CCN

#### Organizational NPI

* CARR_CLM_BLG_NPI_NUM -> CARR_CLM_BLG_NPI_NUM
* CPO_ORG_NPI_NUM -> CPO_ORG_NPI_NUM
* CARR_CLM_SOS_NPI_NUM

#### Personal NPI

* PRF_PHYSN_NPI
* CARR_LINE_MDPP_NPI_NUM

### bcarrier Claim Line

#### Organizational NPI

* CARR_LINE_MDPP_NPI_NUM -> CARR_LINE_MDPP_NPI_NUM
* ORG_NPI_NUM -> ORG_NPI_NUM

#### Personal NPI

* PRF_PHYSN_NPI

## dme

* TAX_NUM -> TAX_NUM

### DME Claim

* TAX_NUM -> TAX_NUM
* PRVDR_NUM -> PRVDR_NUM

#### Personal NPI

* RFR_PHYSN_NPI -> RFR_PHYSN_NPI

### DME Claim Line

#### Organizational NPI

* PRVDR_NPI -> PRVDR_NPI

## Insitutional Format

* inpatient
* outpatient
* snf
* hospice
* hha

Each of these has a maximum of the following NPI fields.

## Claim Level

* OWNG_PRVDR_TIN_NUM ->  OWNG_PRVDR_TIN_NUM (not found in SNF, HHA, Hospice)
* PRVDR_NUM -> PRVDR_NUM

### Organizational NPIs

* ORG_NPI_NUM -> ORG_NPI_NUM
* SRVC_LOC_NPI_NUM -> SRVC_LOC_NPI_NUM

### Personal NPIs

* AT_PHYSN_NPI -> AT_PHYSN_NPI
* OP_PHYSN_NPI -> OP_PHYSN_NPI
* OT_PHYSN_NPI -> OT_PHYSN_NPI
* RNDRNG_PHYSN_NPI -> claim_RNDRNG_PHYSN_NPI

## Claim Line Level

### Personal NPIs

* RNDRNG_PHYSN_NPI -> cline_RNDRNG_PHYSN_NPI
* ORDRG_PHYSN_NPI -> ORDRG_PHYSN_NPI (not found in Inpatient, SNF)
