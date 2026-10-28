#!/bin/bash
set -e

echo "========================================================"
echo " 🚀 Deploying CampusSathi AI to Google Cloud Run"
echo "========================================================"

if ! command -v gcloud &> /dev/null; then
    echo "[ERROR] Google Cloud SDK (gcloud) is not installed."
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

SERVICE_NAME="campussathi-ai"
REGION="asia-south1"
MEMORY="2Gi"
CPU="1"

echo "Service: $SERVICE_NAME"
echo "Region:  $REGION"
echo "Memory:  $MEMORY"
echo "CPU:     $CPU"
echo ""

gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory "$MEMORY" \
    --cpu "$CPU" \
    --port 8080

echo ""
echo "========================================================"
echo " ✅ Deployment Successful!"
echo " Copy the Service URL above and paste it into:"
echo " 1. Frontend Vercel Environment Variables: VITE_API_URL"
echo " 2. Or inside the CampusSathi UI: Server Settings (⚙️)"
echo "========================================================"
