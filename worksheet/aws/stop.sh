#!/usr/bin/env bash
# Stop the running IDR Worksheet task → cost back to $0.
#
#   kion run -f npd_prod -- ./worksheet/aws/stop.sh
#
# Stops the task recorded by launch.sh, plus any other RUNNING idr-worksheet task
# (belt and braces, in case the state file was lost).
set -euo pipefail
cd "$(dirname "$0")"
set -a; . ./deploy.env; set +a
: "${AWS_REGION:?}"; : "${ECS_CLUSTER:?}"
STATE_FILE="/tmp/idr_worksheet_task.arn"

stopped=0
if [[ -f "$STATE_FILE" ]]; then
  arn=$(cat "$STATE_FILE")
  aws ecs stop-task --region "$AWS_REGION" --cluster "$ECS_CLUSTER" --task "$arn" \
    --reason "worksheet stop.sh" >/dev/null 2>&1 && { echo "stopped $arn"; stopped=1; }
  rm -f "$STATE_FILE"
fi

for arn in $(aws ecs list-tasks --region "$AWS_REGION" --cluster "$ECS_CLUSTER" \
              --started-by "worksheet-launch" --desired-status RUNNING \
              --query 'taskArns[]' --output text); do
  aws ecs stop-task --region "$AWS_REGION" --cluster "$ECS_CLUSTER" --task "$arn" \
    --reason "worksheet stop.sh sweep" >/dev/null && { echo "stopped $arn"; stopped=1; }
done

[[ "$stopped" == 1 ]] && echo "✓ idle — no worksheet tasks running (cost → \$0)" \
  || echo "no running worksheet tasks found"
