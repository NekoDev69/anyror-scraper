#!/bin/bash

# GCP Authentication Setup Script
# Sets up everything needed for Vertex AI and Vision API

set -e

PROJECT_ID="anyror-scraper-2026"
REGION="us-central1"
ZONE="us-central1-a"

echo "🔐 GCP Authentication Setup"
echo "==========================="
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found!"
    echo ""
    echo "Install it first:"
    echo "  macOS: brew install google-cloud-sdk"
    echo "  Or: curl https://sdk.cloud.google.com | bash"
    echo ""
    exit 1
fi

echo "✅ gcloud CLI found: $(gcloud --version | head -n1)"
echo ""

# Step 1: Login
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Authenticating with Google Account"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This will open your browser for authentication..."
echo ""

gcloud auth login

echo ""
echo "✅ Authentication successful!"
echo ""

# Step 2: Set project
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Setting Default Project"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

gcloud config set project $PROJECT_ID
echo ""
echo "✅ Project set to: $PROJECT_ID"
echo ""

# Step 3: Set region and zone
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Setting Default Region and Zone"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

gcloud config set compute/region $REGION
gcloud config set compute/zone $ZONE

echo ""
echo "✅ Region set to: $REGION"
echo "✅ Zone set to: $ZONE"
echo ""

# Step 4: Enable APIs
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4: Enabling Required APIs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Enabling Vertex AI API..."
gcloud services enable aiplatform.googleapis.com

echo "Enabling Vision API..."
gcloud services enable vision.googleapis.com

echo "Enabling Service Usage API..."
gcloud services enable serviceusage.googleapis.com

echo ""
echo "✅ All APIs enabled!"
echo ""

# Step 5: Setup application default credentials
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 5: Setting Up Application Default Credentials"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This allows Python scripts to authenticate automatically..."
echo ""

gcloud auth application-default login

echo ""
echo "✅ Application default credentials configured!"
echo ""

# Step 6: Install alpha component
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 6: Installing gcloud Alpha Component"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This is needed for quota management..."
echo ""

if gcloud components list --filter="id:alpha" --format="value(state)" 2>/dev/null | grep -q "Installed"; then
    echo "✅ Alpha component already installed"
else
    echo "Installing alpha component (this may take a minute)..."
    gcloud components install alpha --quiet
    echo "✅ Alpha component installed!"
fi

echo ""

# Step 7: Set environment variable for credentials
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 7: Setting Credentials Environment Variable"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "vertex-credentials.json" ]; then
    CREDS_PATH="$(pwd)/vertex-credentials.json"
    export GOOGLE_APPLICATION_CREDENTIALS="$CREDS_PATH"
    
    echo "✅ Credentials set to: $CREDS_PATH"
    echo ""
    echo "To make this permanent, add to your ~/.zshrc:"
    echo "  export GOOGLE_APPLICATION_CREDENTIALS=\"$CREDS_PATH\""
    echo ""
    
    # Ask if user wants to add to shell profile
    read -p "Add to ~/.zshrc now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "export GOOGLE_APPLICATION_CREDENTIALS=\"$CREDS_PATH\"" >> ~/.zshrc
        echo "✅ Added to ~/.zshrc"
    fi
else
    echo "⚠️  vertex-credentials.json not found in current directory"
    echo "   Using application default credentials instead"
fi

echo ""

# Step 8: Verify setup
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 8: Verifying Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Current configuration:"
gcloud config list

echo ""
echo "Authenticated as:"
gcloud auth list

echo ""
echo "Enabled APIs:"
gcloud services list --enabled --filter="name:(aiplatform OR vision)" --format="table(name, title)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "You're now authenticated and ready to:"
echo "  • Use Vertex AI API"
echo "  • Use Vision API"
echo "  • Request quota increases"
echo "  • Run your scraper"
echo ""
echo "Next steps:"
echo "  1. Test authentication: python3 test_gcp_auth.py"
echo "  2. Check quotas: python3 check_vertex_limits.py"
echo "  3. Request increase: Follow QUICK_START_QUOTA.md"
echo ""
