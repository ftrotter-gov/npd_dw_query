#!/bin/zsh
# Run all four IDR pulls sequentially (no warehouse contention), zstd-compressing
# any delivered plain CSV over 1 GB. Emits STEP lines a Monitor can grep.
#
#   1) Medicare COMBINED 24mo  -> fresh run (all types, 3-key LEFT join, POS in-grain)
#   2) Medicaid COMBINED 24mo  -> fresh run (CLM_FINL_ACTN_IND='T', CLM_POS_CD)
#   3) NPI<->OSCAR             -> fresh run (+ provider-dimension enrichment)
#   4) Medicaid ID xw          -> fresh run
set -u
cd /Users/rhdm/Documents/CMS/repos/freds-snowflake/npd_dw_query

export SNOWFLAKE_ACCOUNT=cms-idr.privatelink
export SNOWFLAKE_USER=RHDM
export SNOWFLAKE_ROLE=IDRSF_PAT_USER_P
export SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH
export OUTPUT_DIR=./idr_data

PY=.venv/bin/python
STAMP=$(date -u +%Y%m%d_%H%M%SZ)
GB=1000000000

log() { echo "[$(date -u +%H:%M:%SZ)] $*"; }

# zstd a plain .csv -> .csv.zst (only if > 1GB), verify, remove plain on success.
zst_if_big() {
  local f="$1"
  [ -f "$f" ] || { log "STEP ZST-SKIP missing $f"; return 0; }
  local sz=$(stat -f%z "$f")
  if [ "$sz" -le "$GB" ]; then
    log "STEP KEEP-PLAIN $f ($(du -h "$f" | cut -f1) <=1GB)"
    return 0
  fi
  log "STEP ZST-START $f ($(du -h "$f" | cut -f1))"
  if zstd -T0 -12 -f "$f" -o "$f.zst" && zstd -t "$f.zst"; then
    rm -f "$f"
    log "STEP ZST-OK $f.zst ($(du -h "$f.zst" | cut -f1))"
  else
    log "STEP ZST-FAIL $f (kept plain)"
  fi
}

zst_prefix_if_big() {
  local pfx="$1"
  for f in idr_data/${pfx}*.csv; do
    [ -f "$f" ] || continue
    zst_if_big "$f"
  done
}

run() {
  local script="$1" tag="$2"
  local rlog="idr_data/${tag}.${STAMP}.log"
  log "STEP RUN-START $tag ($script)"
  $PY "idr/${script}" > "$rlog" 2>&1
  local rc=$?
  log "STEP RUN-DONE $tag rc=${rc} (log ${rlog})"
  return $rc
}

log "STEP CHAIN-START free=$(df -h . | tail -1 | awk '{print $4}')"

# 1) Medicare COMBINED 24mo -- all claim types, header LEFT JOIN professional line
#    on the 3-key (GEO_BENE_SK+CLM_DT_SGNTR_SK+CLM_NUM_SK), POS block in-grain,
#    CLM_THRU_DT window, CLM_FINL_ACTN_IND='Y'. The extract's own
#    COPY INTO ... OVERWRITE=TRUE replaces any stale banked stage.
#    NOTE: largest/most expensive pull -- dry-run 1 month first with
#    CLAIM_WINDOW_MONTHS=1 (see the script docstring) before the 24-month run.
run idr_medicare_combined_wide.py medicare_extract
zst_prefix_if_big idr_medicare_combined_wide.

# 2) Medicaid COMBINED extract (24mo) -- single table, CLM_FINL_ACTN_IND='T',
#    CLM_POS_CD + billing address + specialty/taxonomy/type + payer in-grain.
run idr_medicaid_combined_wide.py medicaid_extract
zst_prefix_if_big idr_medicaid_combined_wide.

# 3) Medicare crosswalk (NPI<->OSCAR + provider-dimension enrichment)
run idr_npi_oscar_crosswalk.py medicare_crosswalk
zst_prefix_if_big idr_npi_oscar_crosswalk

# 4) Medicaid crosswalk (provider id crosswalk)
run idr_medicaid_id_crosswalk.py medicaid_crosswalk
zst_prefix_if_big idr_medicaid_id_crosswalk

log "STEP CHAIN-COMPLETE free=$(df -h . | tail -1 | awk '{print $4}')"
ls -la idr_data/*.csv idr_data/*.zst 2>/dev/null
