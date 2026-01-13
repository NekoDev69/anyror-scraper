#!/bin/bash
# Deploy Optimized AnyROR Global Search System
# Cost: ~$0.05 per district, ~$1.70 for full Gujarat

set -e

PROJECT_ID="${GCP_PROJECT:-anyror-scraper-2026}"
REGION="${GCP_REGION:-asia-south1}"
ZONE="${GCP_ZONE:-asia-south1-a}"
GEMINI_API_KEY="${GEMINI_API_KEY:-}"

if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ ERROR: GEMINI_API_KEY not set"
    echo "   export GEMINI_API_KEY=your-key"
    exit 1
fi

echo "🚀 Deploying Optimized AnyROR Global Search"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Cost: ~\$0.05 per district"
echo ""

# ============================================
# 1. Build Optimized Worker Container
# ============================================
echo "📦 Building optimized worker container..."

# Copy Gujarat data if not present
cp ../gujarat-anyror-complete.json . 2>/dev/null || true

gcloud builds submit \
    --project=$PROJECT_ID \
    --config cloudbuild-worker.yaml

# ============================================
# 2. Create/Update Cloud Run Job
# ============================================
echo ""
echo "🔧 Creating Cloud Run Job (optimized)..."

# Check if job exists
if gcloud run jobs describe anyror-district-scraper-opt --region=$REGION --project=$PROJECT_ID &>/dev/null; then
    echo "   Updating existing job..."
    gcloud run jobs update anyror-district-scraper-opt \
        --project=$PROJECT_ID \
        --region=$REGION \
        --image=gcr.io/$PROJECT_ID/anyror-worker-optimized \
        --cpu=1 \
        --memory=2Gi \
        --task-timeout=30m \
        --max-retries=1 \
        --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,PARALLEL_CONTEXTS=10"
else
    echo "   Creating new job..."
    gcloud run jobs create anyror-district-scraper-opt \
        --project=$PROJECT_ID \
        --region=$REGION \
        --image=gcr.io/$PROJECT_ID/anyror-worker-optimized \
        --cpu=1 \
        --memory=2Gi \
        --task-timeout=30m \
        --max-retries=1 \
        --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,PARALLEL_CONTEXTS=10"
fi

echo "✅ Cloud Run Job ready!"

# ============================================
# 3. Setup Orchestrator VM
# ============================================
echo ""
echo "🖥️  Setting up Orchestrator VM..."

# Check if VM exists
if gcloud compute instances describe anyror-orchestrator --zone=$ZONE --project=$PROJECT_ID &>/dev/null; then
    echo "   VM already exists"
    VM_IP=$(gcloud compute instances describe anyror-orchestrator \
        --zone=$ZONE \
        --project=$PROJECT_ID \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
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
        --scopes=cloud-platform
    
    # Wait for VM to be ready
    echo "   Waiting for VM to start..."
    sleep 30
    
    VM_IP=$(gcloud compute instances describe anyror-orchestrator \
        --zone=$ZONE \
        --project=$PROJECT_ID \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
fi

echo "   VM IP: $VM_IP"

# Allow HTTP traffic
gcloud compute firewall-rules create allow-http-8080 \
    --project=$PROJECT_ID \
    --allow=tcp:8080 \
    --target-tags=http-server \
    2>/dev/null || true

# ============================================
# 4. Deploy Orchestrator Code to VM
# ============================================
echo ""
echo "📤 Deploying orchestrator to VM..."

# Create deployment package
mkdir -p /tmp/anyror-deploy
cp orchestrator.py /tmp/anyror-deploy/
cp -r templates /tmp/anyror-deploy/
cp gujarat-anyror-complete.json /tmp/anyror-deploy/
cp requirements-orchestrator.txt /tmp/anyror-deploy/

# Create startup script
cat > /tmp/anyror-deploy/start.sh << 'EOF'
#!/bin/bash
cd /home/$(whoami)/anyror
pip3 install -r requirements-orchestrator.txt --quiet
export GCP_PROJECT=$1
export GCP_REGION=$2
export ORCHESTRATOR_URL=http://$3:8080
export JOB_NAME=anyror-district-scraper-opt
pkill -f "python3 orchestrator.py" 2>/dev/null || true
nohup python3 orchestrator.py > orchestrator.log 2>&1 &
echo "Orchestrator started on port 8080"
EOF
chmod +x /tmp/anyror-deploy/start.sh

# Copy files to VM
gcloud compute scp --recurse /tmp/anyror-deploy/* \
    anyror-orchestrator:~/anyror/ \
    --zone=$ZONE \
    --project=$PROJECT_ID

# Start orchestrator
gcloud compute ssh anyror-orchestrator \
    --zone=$ZONE \
    --project=$PROJECT_ID \
    --command="cd ~/anyror && bash start.sh $PROJECT_ID $REGION $VM_IP"

# Cleanup
rm -rf /tmp/anyror-deploy

# ============================================
# Done!
# ============================================
echo ""
echo "============================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "============================================"
echo ""
echo "🌐 Web UI: http://$VM_IP:8080"
echo ""
echo "📊 Cost Estimate:"
echo "   • VM (always on): ~\$6/month"
echo "   • Per district search: ~\$0.05"
echo "   • Full Gujarat (34 districts): ~\$1.70"
echo ""
echo "🧪 Test Commands:"
echo ""
echo "   # Open Web UI"
echo "   open http://$VM_IP:8080"
echo ""
echo "   # API: List districts"
echo "   curl http://$VM_IP:8080/api/districts"
echo ""
echo "   # API: Search one district"
echo "   curl -X POST http://$VM_IP:8080/api/search/district \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"district_code\": \"01\", \"survey_number\": \"123\"}'"
echo ""
echo "   # SSH into VM for live edits"
echo "   gcloud compute ssh anyror-orchestrator --zone=$ZONE"
echo ""
