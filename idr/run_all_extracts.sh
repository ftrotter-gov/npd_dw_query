#!/bin/zsh
# Run all four IDR extractors sequentially (avoids warehouse contention).
# Medicare claims extract first, then the Medicare crosswalk, then the two
# Medicaid pulls. Each writes its CSV + a per-run log into idr_data/.
set -u
cd "$(dirname "$0")/.."

export SNOWFLAKE_ACCOUNT=cms-idr.privatelink
export SNOWFLAKE_USER=RHDM
export SNOWFLAKE_ROLE=IDRSF_PAT_USER_P
export SNOWFLAKE_WAREHOUSE=IDRC_PRD_COMM_WH
export OUTPUT_DIR=./idr_data

PY=.venv/bin/python
STAMP=$(date -u +%Y%m%d_%H%M%SZ)
MASTER=idr_data/run_all_${STAMP}.log

mkdir -p idr_data

run() {
  local script="$1" tag="$2"
  local log="idr_data/${tag}.${STAMP}.log"
  echo "=== ${tag} START $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$MASTER"
  $PY "idr/${script}" >"$log" 2>&1
  local rc=$?
  if [ $rc -eq 0 ]; then
    echo "=== ${tag} DONE  rc=0 $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$MASTER"
  else
    echo "!!! ${tag} FAILED rc=${rc} $(date -u +%Y-%m-%dT%H:%M:%SZ) (see ${log}) ===" | tee -a "$MASTER"
  fi
  return $rc
}

run idr_medicare_entity_link_address_wide.py  medicare_extract
run idr_npi_oscar_crosswalk.py                 medicare_crosswalk
run idr_medicaid_entity_link_address_wide.py   medicaid_extract
run idr_medicaid_id_crosswalk.py               medicaid_crosswalk

echo "=== ALL RUNS COMPLETE $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$MASTER"
ls -la idr_data/*.csv 2>/dev/null | tee -a "$MASTER"
