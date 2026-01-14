#!/bin/bash
# Deploy Gujarat AnyROR Global Search to Cloud Run
# CHEAP MODE: Uses minimal resources, scales to 0

set -e

PROJECT_ID="${GCP_PROJECT:-anyror-scraper}"
REGION="${GCP_REGION:-asia-south1}"
SERVICE_NAME="anyror-search"

echo "🚀 Deploying to Cloud Run..."
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"

# Copy Gujarat data to cloud_run folder
cp ../gujarat-anyror-complete.json .

# Build and deploy
gcloud run deploy $SERVICE_NAME \
    --source . \
    --project $PROJECT_ID \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 5 \
    --timeout 300 \
    --concurrency 10 \
    --set-env-vars "GCP_PROJECT=$PROJECT_ID,GCP_REGION=$REGION,GEMINI_API_KEY=$GEMINI_API_KEY"

echo ""
echo "✅ Deployed! Service URL:"
gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'

# Create Cloud Tasks queue for async processing
echo ""
echo "📋 Creating Cloud Tasks queue..."
gcloud tasks queues create scraper-queue \
    --location $REGION \
    --max-concurrent-dispatches 10 \
    --max-dispatches-per-second 5 \
    2>/dev/null || echo "   Queue already exists"

echo ""
echo "🎉 Done! Test with:"
echo "   curl \$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')/districts"
