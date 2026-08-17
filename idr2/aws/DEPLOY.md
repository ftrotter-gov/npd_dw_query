# IDR2 Orchestrator — AWS CLI deploy runbook

Run every command from the **repo root**. Your account / region / network live in
`idr2/aws/deploy.env` (git-ignored) — nothing account-specific is committed.

## 0. Configure + authenticate

```bash
# one-time: create your local, git-ignored config
cp idr2/aws/deploy.env.example idr2/aws/deploy.env
$EDITOR idr2/aws/deploy.env         # fill in AWS_ACCOUNT_ID, region, subnets, SG, SNOWFLAKE_USER

# load it into your shell for the commands below
set -a; . idr2/aws/deploy.env; set +a
export ECR=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# render the AWS JSON from templates → idr2/aws/rendered/ (also git-ignored)
./idr2/aws/render.sh
```

Authenticate to AWS via **Kion** (Kion console → account → "CLI / short-term
access" → paste the export block into this shell), then confirm:

```bash
aws sts get-caller-identity      # Account must equal your $AWS_ACCOUNT_ID
```

## 1. Verify the PAT secret (already created)

```bash
aws secretsmanager get-secret-value --secret-id "$PAT_SECRET_ID" \
  --query SecretString --output text
```
Should print the raw token and nothing else.

## 2. Build & push the image to ECR

```bash
aws ecr create-repository --repository-name idr2-orchestrator >/dev/null 2>&1 || true

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ECR"

# build from the REPO ROOT so the idr2/ tree is in context:
docker build --platform linux/amd64 -t idr2-orchestrator -f idr2/aws/Dockerfile .

docker tag idr2-orchestrator:latest "$ECR/idr2-orchestrator:latest"
docker push "$ECR/idr2-orchestrator:latest"
```

## 3. IAM roles (rendered policy files)

```bash
# 3a. Execution role (ECR pull + CloudWatch Logs)
aws iam create-role --role-name idr2-orchestrator-execution-role \
  --assume-role-policy-document file://idr2/aws/rendered/iam-ecs-trust-policy.json
aws iam attach-role-policy --role-name idr2-orchestrator-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# 3b. Task role (does the S3 write + reads the PAT secret at runtime)
aws iam create-role --role-name idr2-orchestrator-task-role \
  --assume-role-policy-document file://idr2/aws/rendered/iam-ecs-trust-policy.json
aws iam put-role-policy --role-name idr2-orchestrator-task-role \
  --policy-name idr2-s3-and-secret \
  --policy-document file://idr2/aws/rendered/iam-task-role-policy.json

# 3c. Scheduler invoke role (lets EventBridge Scheduler RunTask + pass the roles)
aws iam create-role --role-name idr2-scheduler-invoke-role \
  --assume-role-policy-document file://idr2/aws/rendered/iam-scheduler-trust-policy.json
aws iam put-role-policy --role-name idr2-scheduler-invoke-role \
  --policy-name idr2-runtask \
  --policy-document file://idr2/aws/rendered/iam-scheduler-invoke-policy.json
```

## 4. CloudWatch log group

```bash
aws logs create-log-group --log-group-name /ecs/idr2-orchestrator 2>/dev/null || true
aws logs put-retention-policy --log-group-name /ecs/idr2-orchestrator --retention-in-days 90
```

## 5. ECS cluster

```bash
aws ecs create-cluster --cluster-name "$ECS_CLUSTER"
```

## 6. Register the task definition

```bash
aws ecs register-task-definition --cli-input-json file://idr2/aws/rendered/ecs-task-definition.json
```

Find your network values if you don't have them yet (put them in `deploy.env`,
then re-run `./idr2/aws/render.sh` so the schedule renders in step 8). The most
reliable source is the Snowflake PrivateLink endpoint itself — it lists the
subnets and SG already cleared to reach Snowflake:

```bash
# Snowflake endpoint → SUBNET_A/B and a 443-cleared SG:
aws ec2 describe-vpc-endpoints \
  --query 'VpcEndpoints[?contains(to_string(DnsEntries),`snowflakecomputing`)].{id:VpcEndpointId,vpc:VpcId,subnets:SubnetIds,sgs:Groups[].GroupId}' \
  --output json

# Confirm that VPC also has S3/ECR/Logs/SecretsManager endpoints (task has no public IP):
aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=<THAT_VPC_ID> \
  --query 'VpcEndpoints[].ServiceName' --output text
# expect: ...s3 (gateway), ...ecr.api, ...ecr.dkr, ...logs, ...secretsmanager
```

If the Snowflake endpoint query returns nothing, or you can't read/modify VPC
endpoints, ask whoever owns IDR PrivateLink for "the VPC, private subnets, and
security group that reach IDR Snowflake."

## 7. Smoke test — one table, forced, on demand

Prove the whole relay end-to-end with a single small table before scheduling:

```bash
aws ecs run-task \
  --cluster "$ECS_CLUSTER" \
  --task-definition idr2-orchestrator \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_A,$SUBNET_B],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}" \
  --overrides '{"containerOverrides":[{"name":"orchestrator","environment":[{"name":"FORCE_EXPORT","value":"1"},{"name":"ONLY_TABLES","value":"npi_hstry"}]}]}'

aws logs tail /ecs/idr2-orchestrator --follow --since 10m
aws s3 ls "$S3_BUCKET" | grep npi_hstry
```

## 8. Create the weekly schedule

Ensure `deploy.env` has `ECS_CLUSTER`/`SUBNET_A`/`SUBNET_B`/`SECURITY_GROUP`, then:

```bash
./idr2/aws/render.sh    # now also renders the schedule
aws scheduler create-schedule --cli-input-json file://idr2/aws/rendered/eventbridge-schedule.json
aws scheduler get-schedule --name idr2-orchestrator-weekly
```

Fires `cron(23 6 ? * SUN *)` UTC (Sunday ~06:23).

---

### ⚠️ Private-subnet networking gotcha

With `assignPublicIp=DISABLED`, the task has no internet route, so image pull and
AWS API calls must reach their services privately. Ensure the VPC has either a
**NAT gateway** or these **VPC endpoints**, and that your security group allows
egress to them:

- `com.amazonaws.<region>.ecr.api` and `...ecr.dkr` (interface) — image pull
- `com.amazonaws.<region>.s3` (gateway) — image layers **and** the export upload
- `com.amazonaws.<region>.logs` (interface) — CloudWatch Logs
- `com.amazonaws.<region>.secretsmanager` (interface) — the PAT secret

If the smoke test hangs on startup or times out pulling the image, a missing
endpoint/NAT is the usual cause.

### Updating the image later

```bash
set -a; . idr2/aws/deploy.env; set +a
export ECR=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
docker build --platform linux/amd64 -t idr2-orchestrator -f idr2/aws/Dockerfile .
docker tag idr2-orchestrator:latest "$ECR/idr2-orchestrator:latest"
docker push "$ECR/idr2-orchestrator:latest"
# task def uses :latest, so the next run picks it up; no re-register needed
```
