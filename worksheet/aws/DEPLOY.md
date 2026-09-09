# idr-worksheet — one-time deploy (prod)

A **Snowflake-worksheet-style dashboard** that runs inside the prod VPC, connects to
Snowflake over PrivateLink, and lands results straight to prod S3 — with your PAT
held only in memory (never on AWS) and the whole thing scaled to zero when idle.

```
  laptop browser ──SSM tunnel──► Fargate task (on demand, in prod VPC)
                                   ├─ Snowflake (PrivateLink)  ← PAT from RAM
                                   └─ S3  s3://<your-bucket>/…
```

Idle cost ≈ $0 (nothing runs). In use ≈ $0.02/hr (0.5 vCPU / 1 GB). No ALB, no
stored secret.

> ⚠️ **Read-plane caveat:** small/inline queries land to S3 today. **Bulk COPY→GET
> exports still hang** until the S3 interface endpoint (Path A ticket) is
> provisioned — the seeded `②` worksheet is there to demonstrate that.

---

## 0. Prereqs (every session)

```bash
# authenticate to prod via Kion, then:
cp worksheet/aws/deploy.env.example worksheet/aws/deploy.env   # first time; fill it in
set -a; . worksheet/aws/deploy.env; set +a
export ECR=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
./worksheet/aws/render.sh
aws sts get-caller-identity           # confirm Account == $AWS_ACCOUNT_ID
```

## 1. Build & push the image

```bash
aws ecr create-repository --repository-name idr-worksheet 2>/dev/null || true
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR"
docker build --platform linux/amd64 -t idr-worksheet -f worksheet/aws/Dockerfile .
docker tag idr-worksheet:latest "$ECR/idr-worksheet:latest"
docker push "$ECR/idr-worksheet:latest"
```

## 2. IAM roles

```bash
# execution role: ECR pull + CloudWatch Logs
aws iam create-role --role-name idr-worksheet-execution-role \
  --assume-role-policy-document file://worksheet/aws/rendered/iam-ecs-trust-policy.json
aws iam attach-role-policy --role-name idr-worksheet-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# task role: S3 write ONLY (no secretsmanager — the PAT never lives on AWS)
aws iam create-role --role-name idr-worksheet-task-role \
  --assume-role-policy-document file://worksheet/aws/rendered/iam-ecs-trust-policy.json
aws iam put-role-policy --role-name idr-worksheet-task-role \
  --policy-name idr-worksheet-s3 --policy-document file://worksheet/aws/rendered/iam-task-role-policy.json
```

## 3. Log group + task definition

```bash
aws logs create-log-group --log-group-name /ecs/idr-worksheet 2>/dev/null || true
aws ecs register-task-definition --cli-input-json file://worksheet/aws/rendered/ecs-task-definition.json
```

## 4. One-time network rule — let the bastion reach the task on 8080

The SSM tunnel forwards from the bastion to the task's private IP:8080, so the task
SG must allow inbound 8080 from the bastion. If the bastion shares the task SG,
allow the SG to itself; otherwise allow the bastion's SG:

```bash
aws ec2 authorize-security-group-ingress --group-id "$SECURITY_GROUP" \
  --protocol tcp --port 8080 --source-group "<BASTION_SG_ID>" 2>/dev/null || true
```

## 5. Launch it (the everyday command)

```bash
kion run -f npd_prod -- ./worksheet/aws/launch.sh
# → opens localhost:8080 through the tunnel. Enter your PAT in the top bar.
# When done:
kion run -f npd_prod -- ./worksheet/aws/stop.sh
```

## Update the app later

Rebuild + push (step 1), then `register-task-definition` again (step 3). `launch.sh`
always runs the latest ACTIVE revision.

---

# Teardown

```bash
set -a; . worksheet/aws/deploy.env; set +a
./worksheet/aws/stop.sh || true
for arn in $(aws ecs list-task-definitions --family-prefix idr-worksheet --query 'taskDefinitionArns[]' --output text); do
  aws ecs deregister-task-definition --task-definition "$arn" >/dev/null && echo "deregistered $arn"; done
aws ecr delete-repository --repository-name idr-worksheet --force 2>/dev/null || true
aws logs delete-log-group --log-group-name /ecs/idr-worksheet 2>/dev/null || true
aws iam delete-role-policy --role-name idr-worksheet-task-role --policy-name idr-worksheet-s3 2>/dev/null || true
aws iam delete-role --role-name idr-worksheet-task-role 2>/dev/null || true
aws iam detach-role-policy --role-name idr-worksheet-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || true
aws iam delete-role --role-name idr-worksheet-execution-role 2>/dev/null || true
```
