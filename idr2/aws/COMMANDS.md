# IDR2 deploy — command log

All AWS CLI commands, in order. Run from the repo root after Kion auth for
account <AWS_ACCOUNT_ID>. Values come from `idr2/aws/deploy.env` (git-ignored).

## Prereqs (every session)

```bash
# authenticate to AWS via Kion (paste its short-term CLI export block), then:
set -a; . idr2/aws/deploy.env; set +a                 # load account/region/network/snowflake vars
export ECR=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
./idr2/aws/render.sh                                   # regenerate idr2/aws/rendered/*.json from templates
aws sts get-caller-identity                            # confirm Account == $AWS_ACCOUNT_ID
```

## Network discovery (how we picked the VPC/subnets)

```bash
# interface VPC endpoints (found ecr/logs/secretsmanager in 2 VPCs; no Snowflake endpoint)
aws ec2 describe-vpc-endpoints --filters Name=vpc-endpoint-type,Values=Interface \
  --query 'VpcEndpoints[].{id:VpcEndpointId,svc:ServiceName,vpc:VpcId,subnets:SubnetIds,sgs:Groups[].GroupId}' --output json

# name the VPCs → vpc-05bd... = npd-east-dev, vpc-06299... = npd-east-test
aws ec2 describe-vpcs --vpc-ids vpc-05bd23d8f48e88a4f vpc-06299c1857118bb85 \
  --query 'Vpcs[].{id:VpcId,cidr:CidrBlock,name:Tags[?Key==`Name`]|[0].Value}' --output table

# gateway endpoints (none) + route tables (found NAT on the private subnets → S3 works)
aws ec2 describe-vpc-endpoints --filters Name=vpc-endpoint-type,Values=Gateway \
  --query 'VpcEndpoints[].{id:VpcEndpointId,svc:ServiceName,vpc:VpcId}' --output table
aws ec2 describe-route-tables --filters Name=vpc-id,Values=vpc-05bd23d8f48e88a4f \
  --query 'RouteTables[].{rt:RouteTableId,subnets:Associations[].SubnetId,routes:Routes[].{dst:DestinationCidrBlock,gw:GatewayId,nat:NatGatewayId}}' --output json
```

## 1. Verify the PAT secret (created earlier in the console)

```bash
aws secretsmanager describe-secret --secret-id "$PAT_SECRET_ID"   # metadata only (name, dates)
```

### Rotate / (re)set the PAT value — where the token goes

The PAT lives **only** in Secrets Manager (`idr2/snowflake-pat`); nothing is
stored on the laptop or in git. Both the interim laptop run and the eventual
Fargate run read it from here. When it expires, mint a fresh PAT in Snowflake and
overwrite the value **in place** (secret id stays the same, so no config changes):

```bash
# paste the fresh token when prompted (keeps it out of shell history):
read -rs SNOWFLAKE_PAT_NEW && \
aws secretsmanager put-secret-value --secret-id "$PAT_SECRET_ID" \
  --secret-string "$SNOWFLAKE_PAT_NEW" && unset SNOWFLAKE_PAT_NEW
```

## 1b. Interim: run on the laptop over VPN (until PrivateLink lands)

Snowflake isn't reachable from the dev VPC yet, but the laptop reaches it over
VPN. Same `orchestrator.py`, env-only difference. Snowflake auth = the stored
PAT; S3 auth = your Kion profile.

```bash
set -a; . idr2/aws/deploy.env; set +a
AWS_PROFILE=<AWS_PROFILE> AWS_REGION=us-east-1 \
SNOWFLAKE_PAT_SECRET_ID="$PAT_SECRET_ID" \
FORCE_EXPORT=1 ONLY_TABLES=npi_hstry \
python3 idr2/aws/orchestrator.py

# If the stored PAT has expired, fall back to browser SSO (drop the PAT var):
#   SNOWFLAKE_AUTHENTICATOR=externalbrowser  (+ the same SNOWFLAKE_*/S3_BUCKET vars)
```

## 2. Build & push the image to ECR

```bash
aws ecr create-repository --repository-name idr2-orchestrator 2>/dev/null || true
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR"
docker build --platform linux/amd64 -t idr2-orchestrator -f idr2/aws/Dockerfile .   # amd64 for Fargate
docker tag idr2-orchestrator:latest "$ECR/idr2-orchestrator:latest"
docker push "$ECR/idr2-orchestrator:latest"
```

## 3. IAM roles

```bash
# execution role: ECR pull + CloudWatch Logs
aws iam create-role --role-name idr2-orchestrator-execution-role \
  --assume-role-policy-document file://idr2/aws/rendered/iam-ecs-trust-policy.json
aws iam attach-role-policy --role-name idr2-orchestrator-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# task role: does the S3 write + reads the PAT at runtime
aws iam create-role --role-name idr2-orchestrator-task-role \
  --assume-role-policy-document file://idr2/aws/rendered/iam-ecs-trust-policy.json
aws iam put-role-policy --role-name idr2-orchestrator-task-role \
  --policy-name idr2-s3-and-secret --policy-document file://idr2/aws/rendered/iam-task-role-policy.json
```

## 4. Log group + cluster + task definition

```bash
aws logs create-log-group --log-group-name /ecs/idr2-orchestrator 2>/dev/null || true
aws ecs create-cluster --cluster-name "$ECS_CLUSTER"
aws ecs register-task-definition --cli-input-json file://idr2/aws/rendered/ecs-task-definition.json
```

## 5. Smoke test (one table, forced)  — currently blocked on PrivateLink DNS

```bash
aws ecs run-task --cluster "$ECS_CLUSTER" --task-definition idr2-orchestrator --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_A,$SUBNET_B],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}" \
  --overrides '{"containerOverrides":[{"name":"orchestrator","environment":[{"name":"FORCE_EXPORT","value":"1"},{"name":"ONLY_TABLES","value":"npi_hstry"}]}]}'

aws logs tail /ecs/idr2-orchestrator --follow --since 10m
```
Result so far: image/secret/IAM all OK; fails at DNS resolution of
`<SNOWFLAKE_ACCOUNT>.snowflakecomputing.com` — npd-east-dev has no Snowflake
PrivateLink endpoint / Route 53 zone. Networking-team fix required, then re-run
this same command.

## 6. NOT YET RUN — after networking wires up PrivateLink

```bash
# scheduler invoke role
aws iam create-role --role-name idr2-scheduler-invoke-role \
  --assume-role-policy-document file://idr2/aws/rendered/iam-scheduler-trust-policy.json
aws iam put-role-policy --role-name idr2-scheduler-invoke-role \
  --policy-name idr2-runtask --policy-document file://idr2/aws/rendered/iam-scheduler-invoke-policy.json

# weekly schedule (cron(23 6 ? * SUN *) UTC)
aws scheduler create-schedule --cli-input-json file://idr2/aws/rendered/eventbridge-schedule.json
aws scheduler get-schedule --name idr2-orchestrator-weekly
```

---

# Teardown (remove everything)

Reverse order. Safe to run even if some resources don't exist (errors are
harmless). Keep the PAT secret + roles unless you truly want them gone.

```bash
set -a; . idr2/aws/deploy.env; set +a

# 1. schedule (only if step 6 was run)
aws scheduler delete-schedule --name idr2-orchestrator-weekly 2>/dev/null || true

# 2. deregister all task-definition revisions
for arn in $(aws ecs list-task-definitions --family-prefix idr2-orchestrator --query 'taskDefinitionArns[]' --output text); do
  aws ecs deregister-task-definition --task-definition "$arn" >/dev/null && echo "deregistered $arn"
done

# 3. ECS cluster (empty → deletes cleanly)
aws ecs delete-cluster --cluster "$ECS_CLUSTER" 2>/dev/null || true

# 4. ECR repo + image
aws ecr delete-repository --repository-name idr2-orchestrator --force 2>/dev/null || true

# 5. CloudWatch logs
aws logs delete-log-group --log-group-name /ecs/idr2-orchestrator 2>/dev/null || true

# 6. IAM roles (detach/delete inline policies first, then the role)
aws iam detach-role-policy --role-name idr2-orchestrator-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || true
aws iam delete-role --role-name idr2-orchestrator-execution-role 2>/dev/null || true

aws iam delete-role-policy --role-name idr2-orchestrator-task-role --policy-name idr2-s3-and-secret 2>/dev/null || true
aws iam delete-role --role-name idr2-orchestrator-task-role 2>/dev/null || true

aws iam delete-role-policy --role-name idr2-scheduler-invoke-role --policy-name idr2-runtask 2>/dev/null || true
aws iam delete-role --role-name idr2-scheduler-invoke-role 2>/dev/null || true

# 7. Secret — OPTIONAL (costs ~$0.40/mo; keep it to avoid re-creating the PAT).
#    7-day recovery window (recoverable), or --force-delete-without-recovery to purge now.
# aws secretsmanager delete-secret --secret-id "$PAT_SECRET_ID" --recovery-window-in-days 7

# NOTE: we did NOT create any VPC/subnet/NAT/endpoint — nothing to remove there.
```
