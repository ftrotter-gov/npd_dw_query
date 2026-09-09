#!/usr/bin/env bash
# Launch the IDR Worksheet dashboard ON DEMAND and open a tunnel to it.
#
#   kion run -f npd_prod -- ./worksheet/aws/launch.sh
#
# Flow: run ONE Fargate task → wait until it's RUNNING → find its private IP →
# open an SSM remote-host port-forward through the bastion → browse localhost.
# Nothing is left running but the task; stop it with stop.sh (or Ctrl-C here and
# answer 'y'). Idle auto-shutdown (IDLE_SHUTDOWN_MINUTES) stops a forgotten task.
set -euo pipefail
cd "$(dirname "$0")"
set -a; . ./deploy.env; set +a

: "${AWS_REGION:?}"; : "${ECS_CLUSTER:?}"; : "${SECURITY_GROUP:?}"
: "${SUBNET_A:?}"; : "${SSM_BASTION_INSTANCE_ID:?}"
LOCAL_PORT="${LOCAL_PORT:-8080}"
STATE_FILE="/tmp/idr_worksheet_task.arn"

echo "▶ starting one idr-worksheet task…"
TASK_ARN=$(aws ecs run-task \
  --region "$AWS_REGION" --cluster "$ECS_CLUSTER" \
  --task-definition idr-worksheet --launch-type FARGATE --count 1 \
  --started-by "worksheet-launch" \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_A,${SUBNET_B:-$SUBNET_A},${SUBNET_C:-$SUBNET_A}],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}" \
  --query 'tasks[0].taskArn' --output text)
echo "  task: $TASK_ARN"
echo "$TASK_ARN" > "$STATE_FILE"

echo "▶ waiting for RUNNING…"
aws ecs wait tasks-running --region "$AWS_REGION" --cluster "$ECS_CLUSTER" --tasks "$TASK_ARN"

ENI=$(aws ecs describe-tasks --region "$AWS_REGION" --cluster "$ECS_CLUSTER" --tasks "$TASK_ARN" \
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value | [0]" --output text)
IP=$(aws ec2 describe-network-interfaces --region "$AWS_REGION" --network-interface-ids "$ENI" \
  --query 'NetworkInterfaces[0].PrivateIpAddress' --output text)
echo "  task private IP: $IP  (ENI $ENI)"

cleanup() {
  echo
  read -r -p "Stop the dashboard task now? [y/N] " ans || ans="n"
  if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
    aws ecs stop-task --region "$AWS_REGION" --cluster "$ECS_CLUSTER" --task "$TASK_ARN" \
      --reason "worksheet-launch cleanup" >/dev/null && echo "  stopped."
    rm -f "$STATE_FILE"
  else
    echo "  left running — stop later with:  ./worksheet/aws/stop.sh"
  fi
}
trap cleanup EXIT

echo "▶ opening SSM tunnel  localhost:$LOCAL_PORT  →  $IP:8080"
echo "  when it says 'Waiting for connections', open:  http://localhost:$LOCAL_PORT"
echo "  (Ctrl-C to close the tunnel)"
aws ssm start-session --region "$AWS_REGION" \
  --target "$SSM_BASTION_INSTANCE_ID" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "{\"host\":[\"$IP\"],\"portNumber\":[\"8080\"],\"localPortNumber\":[\"$LOCAL_PORT\"]}"
