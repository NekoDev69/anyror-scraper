#!/bin/bash

# Check if you have permissions to request quota increases

PROJECT_ID="anyror-scraper-2026"

echo "🔍 Checking Quota Management Permissions"
echo "========================================"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not installed"
    echo "   Install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check authentication
echo "1️⃣  Checking authentication..."
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null)
if [ -z "$ACTIVE_ACCOUNT" ]; then
    echo "   ❌ Not authenticated"
    echo "   Run: gcloud auth login"
    exit 1
else
    echo "   ✅ Authenticated as: $ACTIVE_ACCOUNT"
fi

# Set project
echo ""
echo "2️⃣  Setting project..."
gcloud config set project $PROJECT_ID 2>/dev/null
echo "   ✅ Project: $PROJECT_ID"

# Check IAM permissions
echo ""
echo "3️⃣  Checking IAM roles..."
ROLES=$(gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:user:$ACTIVE_ACCOUNT" \
    --format="value(bindings.role)" 2>/dev/null)

if [ -z "$ROLES" ]; then
    echo "   ⚠️  No roles found for $ACTIVE_ACCOUNT"
    echo "   You may need to use a service account or different user"
else
    echo "   Your roles:"
    echo "$ROLES" | while read role; do
        echo "   - $role"
    done
fi

# Check for quota admin role
if echo "$ROLES" | grep -q "roles/owner\|roles/serviceusage.quotaAdmin"; then
    echo ""
    echo "   ✅ You have quota management permissions!"
else
    echo ""
    echo "   ⚠️  You may not have quota management permissions"
    echo "   Required roles:"
    echo "   - roles/owner (full access)"
    echo "   - roles/serviceusage.quotaAdmin (quota only)"
fi

# Check if Vertex AI API is enabled
echo ""
echo "4️⃣  Checking Vertex AI API status..."
if gcloud services list --enabled --filter="name:aiplatform.googleapis.com" --format="value(name)" 2>/dev/null | grep -q "aiplatform"; then
    echo "   ✅ Vertex AI API is enabled"
else
    echo "   ❌ Vertex AI API is NOT enabled"
    echo "   Enable it: gcloud services enable aiplatform.googleapis.com"
fi

# Check billing
echo ""
echo "5️⃣  Checking billing status..."
BILLING_ACCOUNT=$(gcloud billing projects describe $PROJECT_ID --format="value(billingAccountName)" 2>/dev/null)
if [ -z "$BILLING_ACCOUNT" ]; then
    echo "   ⚠️  No billing account linked"
    echo "   Quota increases require billing to be enabled"
    echo "   Link billing: https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID"
else
    echo "   ✅ Billing enabled: $BILLING_ACCOUNT"
fi

# Check if alpha component is installed
echo ""
echo "6️⃣  Checking gcloud components..."
if gcloud components list --filter="id:alpha" --format="value(state)" 2>/dev/null | grep -q "Installed"; then
    echo "   ✅ gcloud alpha component installed"
else
    echo "   ⚠️  gcloud alpha component not installed"
    echo "   Install: gcloud components install alpha"
fi

echo ""
echo "=========================================="
echo "📋 Summary"
echo "=========================================="
echo ""

# Final recommendation
if echo "$ROLES" | grep -q "roles/owner\|roles/serviceusage.quotaAdmin" && \
   gcloud services list --enabled --filter="name:aiplatform.googleapis.com" --format="value(name)" 2>/dev/null | grep -q "aiplatform" && \
   [ -n "$BILLING_ACCOUNT" ]; then
    echo "✅ You're ready to request quota increase!"
    echo ""
    echo "Run: ./request_vertex_quota_increase.sh"
else
    echo "⚠️  Some requirements are missing:"
    echo ""
    if ! echo "$ROLES" | grep -q "roles/owner\|roles/serviceusage.quotaAdmin"; then
        echo "❌ Need quota management permissions"
        echo "   Ask project owner to grant you 'roles/serviceusage.quotaAdmin'"
    fi
    if ! gcloud services list --enabled --filter="name:aiplatform.googleapis.com" --format="value(name)" 2>/dev/null | grep -q "aiplatform"; then
        echo "❌ Vertex AI API not enabled"
        echo "   Run: gcloud services enable aiplatform.googleapis.com"
    fi
    if [ -z "$BILLING_ACCOUNT" ]; then
        echo "❌ Billing not enabled"
        echo "   Link billing account in Cloud Console"
    fi
    echo ""
    echo "Alternative: Use Google Cloud Console method"
    echo "See: VERTEX_QUOTA_REQUEST.md (Method 2)"
fi

echo ""
