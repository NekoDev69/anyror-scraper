#!/bin/bash

# Check Current Vertex AI Quotas and Usage

PROJECT_ID="anyror-scraper-2026"
SERVICE="aiplatform.googleapis.com"

echo "🔍 Checking Vertex AI Quotas and Usage"
echo "========================================"
echo "Project: $PROJECT_ID"
echo ""

# Set project
gcloud config set project $PROJECT_ID 2>/dev/null

echo "📊 Current Vertex AI Quotas:"
echo "----------------------------"
echo ""

# Check if alpha component is available
if gcloud components list --filter="id:alpha" --format="value(state)" 2>/dev/null | grep -q "Installed"; then
    # Method 1: Using gcloud alpha (most detailed)
    echo "Method 1: Detailed quota information"
    echo ""
    gcloud alpha services quota list \
        --service=$SERVICE \
        --filter="metric.name:generate_content_requests_per_minute" \
        --format="table(
            metric.displayName:label='Quota Name',
            limit:label='Current Limit',
            usage:label='Current Usage',
            dimensions:label='Dimensions'
        )" 2>/dev/null || echo "⚠️  Unable to fetch detailed quotas"
    
    echo ""
    echo "----------------------------"
    echo ""
else
    echo "⚠️  gcloud alpha not installed. Install with:"
    echo "   gcloud components install alpha"
    echo ""
fi

# Method 2: Using standard gcloud (basic info)
echo "Method 2: Basic quota information"
echo ""
gcloud services list --enabled --filter="name:$SERVICE" --format="table(name, title)" 2>/dev/null

echo ""
echo "----------------------------"
echo ""

# Method 3: Check via API directly
echo "Method 3: Direct API check"
echo ""
echo "Fetching quota details..."

# Get access token
TOKEN=$(gcloud auth print-access-token 2>/dev/null)

if [ -n "$TOKEN" ]; then
    # Query the Service Usage API
    curl -s -H "Authorization: Bearer $TOKEN" \
        "https://serviceusage.googleapis.com/v1/projects/$PROJECT_ID/services/$SERVICE/consumerQuotaMetrics" \
        | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'metrics' in data:
        for metric in data['metrics']:
            if 'generate_content_requests_per_minute' in metric.get('metric', ''):
                print(f\"Metric: {metric.get('displayName', 'N/A')}\")
                print(f\"Name: {metric.get('metric', 'N/A')}\")
                if 'consumerQuotaLimits' in metric:
                    for limit in metric['consumerQuotaLimits']:
                        print(f\"\\nLimit: {limit.get('metric', 'N/A')}\")
                        if 'quotaBuckets' in limit:
                            for bucket in limit['quotaBuckets']:
                                print(f\"  Effective Limit: {bucket.get('effectiveLimit', 'N/A')}\")
                                print(f\"  Default Limit: {bucket.get('defaultLimit', 'N/A')}\")
                                if 'dimensions' in bucket:
                                    print(f\"  Dimensions: {bucket['dimensions']}\")
    else:
        print('No quota metrics found or API returned unexpected format')
except Exception as e:
    print(f'Error parsing response: {e}')
" 2>/dev/null || echo "⚠️  Unable to parse API response"
else
    echo "⚠️  Unable to get access token"
fi

echo ""
echo "----------------------------"
echo ""

# Method 4: Check in Console (provide link)
echo "Method 4: View in Google Cloud Console"
echo ""
echo "🌐 Open this link to see all quotas visually:"
echo "   https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID"
echo ""
echo "Filter by:"
echo "   • Service: Vertex AI API"
echo "   • Metric: generate_content_requests_per_minute"
echo ""

echo "========================================"
echo "📋 Summary"
echo "========================================"
echo ""
echo "To see your exact current limit:"
echo "1. Open the Console link above (easiest)"
echo "2. Or install gcloud alpha: gcloud components install alpha"
echo "3. Then run this script again"
echo ""
echo "Typical limits:"
echo "   • Free/Development: 5-60 requests/minute"
echo "   • After increase: 500+ requests/minute"
echo ""
