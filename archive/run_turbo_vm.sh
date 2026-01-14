#!/bin/bash
# ============================================
# Run TURBO Scraper on VM
# ============================================
# Usage:
#   ./run_turbo_vm.sh --district 30 --survey 10
#   ./run_turbo_vm.sh --district 30 --survey 10 --parallel 100
#   ./run_turbo_vm.sh --district 30  # All surveys (needs paid API)
# ============================================

PROJECT_ID="${PROJECT_ID:-anyror-scraper-2026}"
ZONE="asia-south1-a"
VM_NAME="anyror-turbo"
GEMINI_API_KEY="${GEMINI_API_KEY:-AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4}"

# Parse args
DISTRICT=""
SURVEY=""
PARALLEL=50

while [[ $# -gt 0 ]]; do
    case $1 in
        --district|-d) DISTRICT="$2"; shift 2 ;;
        --survey|-s) SURVEY="$2"; shift 2 ;;
        --parallel|-p) PARALLEL="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [ -z "$DISTRICT" ]; then
    echo "Usage: ./run_turbo_vm.sh --district <code> [--survey <num>] [--parallel <n>]"
    echo ""
    echo "Examples:"
    echo "  ./run_turbo_vm.sh --district 30 --survey 10"
    echo "  ./run_turbo_vm.sh --district 30 --survey 10 --parallel 100"
    exit 1
fi

echo "============================================"
echo "🚀 TURBO VM SCRAPER"
echo "============================================"
echo "District: $DISTRICT"
echo "Survey: ${SURVEY:-ALL}"
echo "Parallel: $PARALLEL"
echo "============================================"

# Ensure VM is running
gcloud compute instances start $VM_NAME --zone=$ZONE --project=$PROJECT_ID 2>/dev/null || true
sleep 5

# Upload latest worker
echo "📤 Uploading worker..."
gcloud compute scp turbo_vm_worker.py gujarat-anyror-complete.json \
    $VM_NAME:/opt/scraper/ \
    --zone=$ZONE --project=$PROJECT_ID

# Run scraper
echo "🏃 Starting scraper..."
gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command="
cd /opt/scraper
source venv/bin/activate
export GEMINI_API_KEY='$GEMINI_API_KEY'
export GCS_BUCKET='anyror-results'

python turbo_vm_worker.py \\
    --district $DISTRICT \\
    ${SURVEY:+--survey $SURVEY} \\
    --parallel $PARALLEL \\
    --output /opt/scraper/output
"

# Download results
echo ""
echo "📥 Downloading results..."
mkdir -p output
gcloud compute scp --recurse \
    $VM_NAME:/opt/scraper/output/* \
    ./output/ \
    --zone=$ZONE --project=$PROJECT_ID 2>/dev/null || echo "No local files to download (check GCS)"

echo ""
echo "✅ Done! Results in ./output/ and gs://anyror-results/"
