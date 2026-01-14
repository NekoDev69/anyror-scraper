#!/bin/bash
# VM Setup and Run Script

PROJECT="anyror-scraper-2026"
ZONE="asia-south1-a"
VM="anyror-scraper"

echo "📦 Copying files to VM..."
gcloud compute scp --recurse \
  global_search.py \
  captcha_solver.py \
  vf7_extractor.py \
  vf7_report.py \
  gujarat-anyror-complete.json \
  requirements.txt \
  $VM:/opt/scraper/ \
  --zone=$ZONE --project=$PROJECT

echo "🚀 Running scraper..."
gcloud compute ssh $VM --zone=$ZONE --project=$PROJECT --command="
cd /opt/scraper
export GEMINI_API_KEY='AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4'
python3 global_search.py --district-code 30 --survey 10 --max-villages 50
"
