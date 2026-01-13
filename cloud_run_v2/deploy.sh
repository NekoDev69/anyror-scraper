#!/bin/bash
# Deploy AnyROR Global Search System
# 1. Cloud Run Job (parallel worker)
# 2. Compute Engine VM (orchestrator)

set -e

PROJECT_ID="${GCP_PROJECT:-anyror-scraper-2026}"
REGION="${GCP_REGION:-asia-south1}"
ZONE="${GCP_ZONE:-asia-south1-a}"

echo "🚀 Deploying AnyROR Global Search System"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo ""

# Copy Gujarat data
cp ../gujarat-anyror-complete.json . 2>/dev/null || true

# ============================================
# 1. Build and deploy Cloud Run Job (Worker)
# ============================================
echo "📦 Building worker container..."
gcloud builds submit \
    --project=$PROJECT_ID \
    --tag gcr.io/$PROJECT_ID/anyror-worker \
    --dockerfile Dockerfile.worker \
    .

echo "🔧 Creating Cloud Run Job..."
gcloud run jobs create anyror-district-scraper \
    --project=$PROJECT_ID \
    --region=$REGION \
    --image=gcr.io/$PROJECT_ID/anyror-worker \
    --memory=2Gi \
    --cpu=2 \
    --task-timeout=3600 \
    --max-retries=1 \
    --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,PARALLEL_CONTEXTS=5" \
    2>/dev/null || \
gcloud run jobs update anyror-district-scraper \
    --project=$PROJECT_ID \
    --region=$REGION \
    --image=gcr.io/$PROJECT_ID/anyror-worker \
    --memory=2Gi \
    --cpu=2 \
    --task-timeout=3600 \
    --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,PARALLEL_CONTEXTS=5"

echo "✅ Cloud Run Job ready!"

# ============================================
# 2. Deploy Orchestrator VM (e2-micro)
# ============================================
echo ""
echo "🖥️  Setting up Orchestrator VM..."

# Check if VM exists
if gcloud compute instances describe anyror-orchestrator --zone=$ZONE --project=$PROJECT_ID &>/dev/null; then
    echo "   VM already exists, updating..."
else
    echo "   Creating e2-micro VM..."
    gcloud compute instances create anyror-orchestrator \
        --project=$PROJECT_ID \
        --zone=$ZONE \
        --machine-type=e2-micro \
        --image-family=debian-12 \
        --image-project=debian-cloud \
        --boot-disk-size=10GB \
        --tags=http-server \
        --scopes=cloud-platform \
        --metadata=startup-script='#!/bin/bash
apt-get update
apt-get install -y python3-pip python3-venv
pip3 install fastapi uvicorn pydantic
'
fi

# Get VM external IP
VM_IP=$(gcloud compute instances describe anyror-orchestrator \
    --zone=$ZONE \
    --project=$PROJECT_ID \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "   VM IP: $VM_IP"

# Allow HTTP traffic
gcloud compute firewall-rules create allow-http-8080 \
    --project=$PROJECT_ID \
    --allow=tcp:8080 \
    --target-tags=http-server \
    2>/dev/null || true

# Copy files to VM
echo "   Copying files to VM..."
gcloud compute scp orchestrator.py gujarat-anyror-complete.json requirements-orchestrator.txt \
    anyror-orchestrator:~ \
    --zone=$ZONE \
    --project=$PROJECT_ID

# Start orchestrator
echo "   Starting orchestrator..."
gcloud compute ssh anyror-orchestrator \
    --zone=$ZONE \
    --project=$PROJECT_ID \
    --command="
pip3 install -r requirements-orchestrator.txt
export GCP_PROJECT=$PROJECT_ID
export GCP_REGION=$REGION
export ORCHESTRATOR_URL=http://$VM_IP:8080
nohup python3 orchestrator.py > orchestrator.log 2>&1 &
"

echo ""
echo "============================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "============================================"
echo ""
echo "Orchestrator API: http://$VM_IP:8080"
echo ""
echo "Test commands:"
echo "  # List districts"
echo "  curl http://$VM_IP:8080/districts"
echo ""
echo "  # Search one district"
echo "  curl -X POST http://$VM_IP:8080/search/district \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"district_code\": \"01\"}'"
echo ""
echo "  # Search ALL Gujarat (34 parallel jobs)"
echo "  curl -X POST http://$VM_IP:8080/search/all"
echo ""
echo "  # Check job status"
echo "  curl http://$VM_IP:8080/jobs"
