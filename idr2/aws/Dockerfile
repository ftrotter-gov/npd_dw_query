# IDR2 orchestrator image.
# Build from the REPO ROOT (context must include idr2/), targeting amd64 so it
# runs on Fargate even when built on Apple Silicon:
#
#   docker build --platform linux/amd64 -t idr2-orchestrator -f idr2/aws/Dockerfile .
#
FROM python:3.12-slim

WORKDIR /app

# Install deps first for layer caching.
COPY idr2/aws/requirements.txt /app/idr2/aws/requirements.txt
RUN pip install --no-cache-dir -r /app/idr2/aws/requirements.txt

# The orchestrator resolves the repo root as parents[2] of its own path and
# reads idr2/step1_tables_to_export.csv from there, so preserve the idr2/ tree.
COPY idr2/ /app/idr2/

# Safety net: never ship a local .env (may hold a token/PII) even if a
# non-BuildKit build ignored Dockerfile.dockerignore. Config comes from the
# task-definition environment, not a baked-in file.
RUN rm -f /app/idr2/.env

# Unbuffered stdout → CloudWatch sees logs live.
ENV PYTHONUNBUFFERED=1

CMD ["python", "/app/idr2/aws/orchestrator.py"]
