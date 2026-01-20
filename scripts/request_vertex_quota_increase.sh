#!/bin/bash

# Vertex AI Quota Increase Request Script
# Project: anyror-scraper-2026
# Purpose: Increase CAPTCHA solving capacity for land records scraper

set -e

PROJECT_ID="anyror-scraper-2026"
SERVICE="aiplatform.googleapis.com"
METRIC="generate_content_requests_per_minute_per_project_per_base_model"
BASE_MODEL="gemini-experimental"
REQUESTED_LIMIT=500  # Start with 500 req/min (10x current limit)

echo "🚀 Vertex AI Quota Increase Request"
echo "===================================="
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE"
echo "Metric: $METRIC"
echo "Base Model: $BASE_MODEL"
echo "Requested Limit: $REQUESTED_LIMIT requests/minute"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
echo "🔐 Checking authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo "❌ Not authenticated. Running 'gcloud auth login'..."
    gcloud auth login
fi

# Set the project
echo "📦 Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Check current quotas
echo ""
echo "📊 Current Vertex AI Quotas:"
echo "----------------------------"
gcloud alpha services quota list \
    --service=$SERVICE \
    --filter="metric.name:$METRIC" \
    --format="table(metric.displayName, limit, usage)" \
    2>/dev/null || echo "⚠️  Unable to fetch current quotas (may need alpha component)"

echo ""
echo "📝 Submitting quota increase request..."
echo ""

# Submit the quota increase request
gcloud alpha services quotas update \
    --service=$SERVICE \
    --consumer=projects/$PROJECT_ID \
    --metric=$METRIC \
    --unit="1/min/{project}/{base_model}" \
    --dimensions=base_model=$BASE_MODEL \
    --preferred-value=$REQUESTED_LIMIT \
    --justification="Land records scraper for Gujarat state government data. Running 4-6 concurrent workers processing village CAPTCHA challenges. Current limit of ~60 req/min causes ResourceExhausted errors. Need 500 req/min to support 10 workers processing ~50 villages/hour. Estimated monthly usage: 720K requests (500 req/min * 60 min * 24 hours). This is a production scraper for public data extraction with 90% success rate." \
    2>&1 || {
        echo ""
        echo "⚠️  Quota update command failed. This could mean:"
        echo "   1. You need the 'serviceusage.quotas.update' permission"
        echo "   2. The gcloud alpha component is not installed"
        echo "   3. The quota doesn't support programmatic updates"
        echo ""
        echo "📋 Alternative: Use Google Cloud Console"
        echo "   See instructions in VERTEX_QUOTA_REQUEST.md"
        exit 1
    }

echo ""
echo "✅ Quota increase request submitted!"
echo ""
echo "⏰ Expected Timeline:"
echo "   - Response: 2-3 business days"
echo "   - You'll receive email notification at your GCP admin email"
echo ""
echo "📧 Check request status:"
echo "   gcloud alpha services quotas describe \\"
echo "     --service=$SERVICE \\"
echo "     --consumer=projects/$PROJECT_ID \\"
echo "     --metric=$METRIC \\"
echo "     --unit='1/min/{project}/{base_model}' \\"
echo "     --dimensions=base_model=$BASE_MODEL"
echo ""
echo "🌐 Or check in Cloud Console:"
echo "   https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID"
