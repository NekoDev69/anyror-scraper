#!/bin/bash

# Quick Quota Increase Request (No Pre-checks)
# Submits directly to speed up the process

set -e

PROJECT_ID="anyror-scraper-2026"
SERVICE="aiplatform.googleapis.com"
METRIC="generate_content_requests_per_minute_per_project_per_base_model"
BASE_MODEL="gemini-experimental"
REQUESTED_LIMIT=500

echo "🚀 Submitting Vertex AI Quota Increase Request"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "Requested: $REQUESTED_LIMIT requests/minute"
echo ""

gcloud config set project $PROJECT_ID

echo "📝 Submitting request..."
echo ""

gcloud alpha services quotas update \
    --service=$SERVICE \
    --consumer=projects/$PROJECT_ID \
    --metric=$METRIC \
    --unit="1/min/{project}/{base_model}" \
    --dimensions=base_model=$BASE_MODEL \
    --preferred-value=$REQUESTED_LIMIT \
    --justification="Land records scraper for Gujarat state government data. Running 4-6 concurrent workers processing village CAPTCHA challenges. Current limit of ~60 req/min causes ResourceExhausted errors. Need 500 req/min to support 10 workers processing ~50 villages/hour. Estimated monthly usage: 720K requests (500 req/min * 60 min * 24 hours). This is a production scraper for public data extraction with 90% success rate." \
    && echo "" && echo "✅ Request submitted successfully!" \
    || {
        echo ""
        echo "⚠️  Request failed. Trying alternative method..."
        echo ""
        echo "📋 Please submit manually via Console:"
        echo "   https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID"
        echo ""
        echo "Filter for:"
        echo "   Service: Vertex AI API"
        echo "   Metric: generate_content_requests_per_minute_per_project_per_base_model"
        echo "   Dimensions: base_model=gemini-experimental"
        echo ""
        echo "Request: 500 requests/minute"
        echo ""
        exit 1
    }

echo ""
echo "⏰ Expected Timeline: 2-3 business days"
echo "📧 Check email for approval notification"
echo ""
echo "🔍 Track status:"
echo "   https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID"
