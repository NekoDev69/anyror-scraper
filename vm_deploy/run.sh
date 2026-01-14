#!/bin/bash
# Run the bulk scraper
# Usage: ./run.sh [district_code] [taluka_code] [survey_filter] [num_contexts]

cd ~/anyror-scraper
source venv/bin/activate

# Set defaults - API key should be set in ~/.bashrc or passed as env var
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"
export DISTRICT_CODE="${1:-}"
export TALUKA_CODE="${2:-}"
export SURVEY_FILTER="${3:-}"
export NUM_CONTEXTS="${4:-4}"

echo "=========================================="
echo "AnyROR Bulk Scraper"
echo "=========================================="
echo "District: ${DISTRICT_CODE:-all}"
echo "Taluka: ${TALUKA_CODE:-all}"
echo "Survey filter: ${SURVEY_FILTER:-none}"
echo "Parallel contexts: ${NUM_CONTEXTS}"
echo "=========================================="
echo ""

python vm_bulk_scraper.py

echo ""
echo "Done! Results in ~/anyror-scraper/output/"
