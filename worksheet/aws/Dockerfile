# IDR Worksheet dashboard image.
# Build from the REPO ROOT (context must include idr/ AND worksheet/), amd64 so it
# runs on Fargate even when built on Apple Silicon:
#
#   docker build --platform linux/amd64 -t idr-worksheet -f worksheet/aws/Dockerfile .
#
# The container serves a FastAPI web app. It NEVER reads a stored PAT — the PAT is
# supplied by the browser at run time and kept only in the process's memory. It
# still holds AWS creds (via the task role) to write results to S3.
FROM python:3.12-slim

WORKDIR /app

COPY worksheet/app/requirements.txt /app/worksheet/app/requirements.txt
RUN pip install --no-cache-dir -r /app/worksheet/app/requirements.txt

# idr/ provides idr_export_common (the connection + relay helpers the engine reuses)
# and the repo scripts shown in the browser. worksheet/ is the app itself.
COPY idr/ /app/idr/
COPY worksheet/ /app/worksheet/

# Safety net: never ship a local .env (may hold a token/PII).
RUN rm -f /app/idr/.env /app/.env /app/worksheet/.env

ENV PYTHONUNBUFFERED=1 \
    OUTPUT_DIR=/tmp/idr_worksheet \
    IDLE_SHUTDOWN_MINUTES=30

# server.py adds /app/idr to sys.path; running from the app dir puts engine.py and
# scripts_registry.py (plain modules) on sys.path too.
WORKDIR /app/worksheet/app
EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
