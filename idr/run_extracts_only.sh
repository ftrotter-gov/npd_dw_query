#!/bin/zsh
# Re-run ONLY the two COMBINED wide extracts (Medicare + Medicaid). The two
# crosswalks (npi_oscar, medicaid_id) are reference data, so they are NOT
# re-pulled here. Use run_all_pulls.sh for a full four-dataset refresh.
#
#   1) Medicare COMBINED 24mo  -> all types, 3-key LEFT join, POS in-grain
#   2) Medicaid COMBINED 24mo  -> CLM_FINL_ACTN_IND='T', CLM_POS_CD
#
# zstd-compresses any delivered plain CSV over 1 GB. Emits STEP lines a Monitor
# can grep.
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

# 1) Medicare COMBINED 24mo -- all types, 3-key LEFT join, POS in-grain.
#    OVERWRITE=TRUE replaces any stale banked stage. Dry-run 1 month first with
#    CLAIM_WINDOW_MONTHS=1 (see the script docstring) before the 24-month run.
run idr_medicare_combined_wide.py medicare_extract
zst_prefix_if_big idr_medicare_combined_wide.

# 2) Medicaid COMBINED extract (24mo) -- CLM_FINL_ACTN_IND='T', CLM_POS_CD added
run idr_medicaid_combined_wide.py medicaid_extract
zst_prefix_if_big idr_medicaid_combined_wide.

log "STEP CHAIN-COMPLETE free=$(df -h . | tail -1 | awk '{print $4}')"
ls -la idr_data/idr_medicare_combined_wide.* idr_data/idr_medicaid_combined_wide.* 2>/dev/null
