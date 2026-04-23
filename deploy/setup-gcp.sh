#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# GCP setup for openwealthlab-pipeline
#
# Creates: Artifact Registry repo, Cloud Run Job, Cloud Scheduler trigger
# Prerequisites: gcloud CLI authenticated, billing enabled
# ──────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="openwealthlab"
REGION="europe-west1"
REPO_NAME="openwealthlab"
IMAGE="europe-west1-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/dividend-pipeline"
JOB_NAME="dividend-pipeline"
SCHEDULER_NAME="weekly-dividend-trigger"

echo "=== 1. Enable required APIs ==="
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  --project="${PROJECT_ID}"

echo "=== 2. Create Artifact Registry repository ==="
gcloud artifacts repositories describe "${REPO_NAME}" \
  --location="${REGION}" --project="${PROJECT_ID}" 2>/dev/null || \
gcloud artifacts repositories create "${REPO_NAME}" \
  --repository-format=docker \
  --location="${REGION}" \
  --project="${PROJECT_ID}"

echo "=== 3. Build & push Docker image ==="
gcloud builds submit \
  --tag "${IMAGE}:latest" \
  --project="${PROJECT_ID}"

echo "=== 4. Create secrets (if they don't exist) ==="
for SECRET in FIREBASE_SERVICE_ACCOUNT_KEY TR_PHONE_NUMBER TR_PIN TR_COOKIES_BASE64 OWL_GITHUB_TOKEN; do
  gcloud secrets describe "${SECRET}" --project="${PROJECT_ID}" 2>/dev/null || \
  echo "⚠ Secret ${SECRET} does not exist yet. Create it with:" && \
  echo "  echo -n 'value' | gcloud secrets create ${SECRET} --data-file=- --project=${PROJECT_ID}"
done

echo "=== 5. Create Cloud Run Job ==="
gcloud run jobs describe "${JOB_NAME}" \
  --region="${REGION}" --project="${PROJECT_ID}" 2>/dev/null || \
gcloud run jobs create "${JOB_NAME}" \
  --image="${IMAGE}:latest" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --memory="512Mi" \
  --cpu="1" \
  --max-retries=1 \
  --task-timeout="300s" \
  --set-env-vars="PIPELINE_ENV=prod,PIPELINE_HEADLESS=1" \
  --set-secrets="\
FIREBASE_SERVICE_ACCOUNT_KEY=FIREBASE_SERVICE_ACCOUNT_KEY:latest,\
TR_PHONE_NUMBER=TR_PHONE_NUMBER:latest,\
TR_PIN=TR_PIN:latest,\
TR_COOKIES_BASE64=TR_COOKIES_BASE64:latest,\
OWL_GITHUB_TOKEN=OWL_GITHUB_TOKEN:latest"

echo "=== 6. Create Cloud Scheduler trigger (Sunday 18:00 UTC) ==="
gcloud scheduler jobs describe "${SCHEDULER_NAME}" \
  --location="${REGION}" --project="${PROJECT_ID}" 2>/dev/null || \
gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --schedule="0 18 * * 0" \
  --time-zone="UTC" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
  --http-method=POST \
  --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com"

echo ""
echo "✓ Setup complete!"
echo ""
echo "To run the job manually:"
echo "  gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo "To update the image after code changes:"
echo "  gcloud builds submit --tag ${IMAGE}:latest --project=${PROJECT_ID}"
echo "  gcloud run jobs update ${JOB_NAME} --image=${IMAGE}:latest --region=${REGION} --project=${PROJECT_ID}"
