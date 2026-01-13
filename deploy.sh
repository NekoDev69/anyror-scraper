#!/bin/bash
# Master Deploy Script - AnyROR Global Search
# Deploys everything to Cloud Run in one go

set -e

PROJECT_ID="anyror-scraper-2026"
REGION="asia-south1"
GEMINI_API_KEY="AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4"
JOB_NAME="anyror-worker"

echo "============================================"
echo "🚀 AnyROR Global Search - Master Deploy"
echo "============================================"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# 1. Set project
echo "📌 Setting project..."
gcloud config set project $PROJECT_ID

# 2. Enable APIs
echo "🔧 Enabling APIs..."
gcloud services enable cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com --quiet

# 3. Create Dockerfile
echo "📦 Creating Dockerfile..."
cat > Dockerfile << 'DOCKERFILE'
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /tmp/results
ENV OUTPUT_DIR=/tmp/results
CMD ["python", "-u", "cloud_worker.py"]
DOCKERFILE

# 4. Create requirements
echo "📋 Creating requirements.txt..."
cat > requirements.txt << 'REQ'
playwright==1.41.0
aiohttp==3.9.1
google-cloud-storage==2.14.0
REQ

# 5. Create the cloud worker
echo "🔨 Creating cloud worker..."
cat > cloud_worker.py << 'WORKER'
"""
AnyROR Cloud Worker - Parallel Scraper (10 concurrent)
"""
import os, sys, json, asyncio, base64, time, re
from datetime import datetime
import aiohttp
from playwright.async_api import async_playwright
from google.cloud import storage

# Unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DISTRICT_CODE = os.environ.get("DISTRICT_CODE", "")
SURVEY_NUMBER = os.environ.get("SURVEY_NUMBER", "")
PARALLEL = int(os.environ.get("PARALLEL", "10"))
OUTPUT_DIR = "/tmp/results"
GCS_BUCKET = "anyror-results"
PROJECT_ID = "anyror-scraper-2026"

print(f"🚀 Worker | Parallel: {PARALLEL}", flush=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# GCS
try:
    bucket = storage.Client(project=PROJECT_ID).bucket(GCS_BUCKET)
    bucket.reload()
    print(f"📦 GCS: {GCS_BUCKET} ✓", flush=True)
except:
    bucket = None

URL = "https://anyror.gujarat.gov.in/LandRecordRural.aspx"
SEL = {
    "type": "#ContentPlaceHolder1_drpLandRecord",
    "dist": "#ContentPlaceHolder1_ddlDistrict",
    "tal": "#ContentPlaceHolder1_ddlTaluka",
    "vil": "#ContentPlaceHolder1_ddlVillage",
    "sur": "#ContentPlaceHolder1_ddlSurveyNo",
    "cap": "[placeholder='Enter Text Shown Above']",
    "img": "#ContentPlaceHolder1_imgCaptcha",
}

stats = {"done": 0, "found": 0, "records": 0, "errors": 0, "total": 0}
stats_lock = asyncio.Lock()

async def update_stats(found=0, records=0, error=False):
    async with stats_lock:
        stats["done"] += 1
        stats["found"] += found
        stats["records"] += records
        if error: stats["errors"] += 1
        if stats["done"] % 10 == 0:
            print(f"📊 {stats['done']}/{stats['total']} | Found: {stats['found']} | Records: {stats['records']} | Err: {stats['errors']}", flush=True)

class CaptchaSolver:
    def __init__(self):
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        self.session = None
    
    async def solve(self, img_bytes):
        if not self.session:
            self.session = aiohttp.ClientSession()
        b64 = base64.b64encode(img_bytes).decode()
        payload = {"contents": [{"parts": [
            {"inline_data": {"mime_type": "image/png", "data": b64}},
            {"text": "Read CAPTCHA. Return ONLY the text."}
        ]}]}
        try:
            async with self.session.post(self.url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    d = await r.json()
                    t = d["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return ''.join(c for c in t if c.isascii() and c.isalnum())
        except: pass
        return ""
    
    async def close(self):
        if self.session: await self.session.close()

def make_html(data):
    loc, prop, land = data.get("location",{}), data.get("property",{}), data.get("land",{})
    owners_html = ''.join(f"<tr><td>{o.get('name','')}</td><td>{o.get('entry','')}</td></tr>" for o in data.get('owners',[]))
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>VF-7 {loc.get('village','')}</title>
<style>body{{font-family:Arial;background:#f0f0f0;padding:20px}}.box{{background:#ffffcc;border:2px solid #999;padding:15px;margin-bottom:10px;max-width:1000px}}.title{{color:#006600;font-weight:bold}}.red{{color:red;font-weight:bold}}.grid{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px}}.label{{color:#006600;font-weight:bold}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border:1px solid #999}}th{{background:#ccffcc}}</style></head>
<body><div class="box"><div class="red">* {land.get('status_time','')}</div>
<div class="grid"><div><div class="label">District</div>{loc.get('district','')}</div><div><div class="label">Taluka</div>{loc.get('taluka','')}</div><div><div class="label">Village</div>{loc.get('village','')}</div><div><div class="label">Survey No</div>{prop.get('survey','')}</div></div>
<div style="margin-top:10px"><span class="label">UPIN:</span> <span style="color:blue">{prop.get('upin','')}</span></div></div>
<div class="box"><div class="title">Land Details</div><table><tr><td class="label">Area</td><td>{land.get('area','')}</td></tr><tr><td class="label">Tax</td><td>{land.get('tax','')}</td></tr><tr><td class="label">Tenure</td><td>{land.get('tenure','')}</td></tr><tr><td class="label">Use</td><td>{land.get('use','')}</td></tr></table></div>
<div class="box"><div class="title">Owners</div><table><tr><th>Name</th><th>Entry</th></tr>{owners_html}</table></div></body></html>"""

async def scrape_village(browser, v, survey_filter, solver):
    ctx = await browser.new_context()
    page = await ctx.new_page()
    page.set_default_timeout(25000)
    page.on("dialog", lambda d: asyncio.create_task(d.accept()))
    
    found, recs = 0, 0
    try:
        await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        await page.locator(SEL["type"]).select_option("1")
        await asyncio.sleep(0.3)
        await page.locator(SEL["dist"]).select_option(v["dc"])
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.locator(SEL["tal"]).select_option(v["tc"])
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.locator(SEL["vil"]).select_option(v["vc"])
        await page.wait_for_load_state("networkidle", timeout=15000)
        
        surveys = []
        for opt in await page.locator(SEL["sur"]).locator("option").all():
            val = await opt.get_attribute("value")
            txt = (await opt.text_content()).strip()
            if val and val not in ["0", "-1", ""] and "પસંદ" not in txt:
                if not survey_filter or survey_filter in txt:
                    surveys.append({"v": val, "t": txt})
        
        found = len(surveys)
        if surveys and survey_filter:
            for s in surveys[:3]:
                await page.locator(SEL["sur"]).select_option(s["v"])
                await asyncio.sleep(0.3)
                
                for attempt in range(2):
                    try:
                        img = await page.locator(SEL["img"]).screenshot()
                        cap = await solver.solve(img)
                        if not cap: continue
                        
                        await page.locator(SEL["cap"]).fill(cap)
                        await page.locator(SEL["cap"]).press("Enter")
                        await asyncio.sleep(1.5)
                        
                        if "ખાતા નંબર" in await page.content():
                            text = await page.locator("body").text_content()
                            def find(p, d=""): 
                                m = re.search(p, text, re.DOTALL)
                                return m.group(1).strip() if m else d
                            
                            owners = [{"name": n.strip(), "entry": e} for n, e in re.findall(r'([^()\n]{3,})\(([૦-૯0-9]+)\)', text)][:20]
                            
                            data = {
                                "location": {"district": v["dn"], "taluka": v["tn"], "village": v["vn"]},
                                "property": {"survey": s["t"], "upin": find(r'UPIN[^:]*[:)]\s*([A-Z]{2}\d+)')},
                                "land": {
                                    "status_time": find(r'તા\.?\s*([0-9૦-૯/:\s]+)\s*ની'),
                                    "area": find(r'([૦-૯0-9]+-[૦-૯0-9]+-[૦-૯0-9]+)'),
                                    "tax": find(r'કુલ આકાર[^:]*:\s*\n?\s*([૦-૯0-9\.]+)'),
                                    "tenure": find(r'સત્તાપ્રકાર[^:]*:\s*([^\n]+)'),
                                    "use": find(r'જમીનનો ઉપયોગ[^:]*:\s*([^\n]+)'),
                                },
                                "owners": owners
                            }
                            
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
                            name = f"vf7_{v['dc']}_{v['vn'][:15].replace(' ','')}_{ts}"
                            html = make_html(data)
                            
                            with open(f"{OUTPUT_DIR}/{name}.json", "w") as f: json.dump(data, f, ensure_ascii=False)
                            with open(f"{OUTPUT_DIR}/{name}.html", "w") as f: f.write(html)
                            
                            if bucket:
                                try:
                                    bucket.blob(f"{DISTRICT_CODE}/{name}.json").upload_from_string(json.dumps(data, ensure_ascii=False), content_type="application/json")
                                    bucket.blob(f"{DISTRICT_CODE}/{name}.html").upload_from_string(html, content_type="text/html")
                                except: pass
                            
                            recs += 1
                            print(f"  ✓ {v['vn']}/{s['t']}", flush=True)
                            break
                    except: pass
                    try: await page.locator("text=Refresh").first.click()
                    except: pass
        
        await update_stats(found=1 if found > 0 else 0, records=recs)
    except:
        await update_stats(error=True)
    finally:
        await ctx.close()

async def main():
    if not DISTRICT_CODE:
        print("ERROR: Set DISTRICT_CODE", flush=True)
        sys.exit(1)
    
    with open("gujarat-anyror-complete.json") as f:
        data = json.load(f)
    
    district = next((d for d in data["districts"] if d["value"] == DISTRICT_CODE), None)
    if not district:
        print(f"ERROR: District {DISTRICT_CODE} not found", flush=True)
        sys.exit(1)
    
    villages = []
    for t in district["talukas"]:
        for v in t["villages"]:
            villages.append({"dc": district["value"], "dn": district["label"],
                "tc": t["value"], "tn": t["label"], "vc": v["value"], "vn": v["label"]})
    
    stats["total"] = len(villages)
    print(f"📍 District: {district['label']} | Villages: {len(villages)} | Survey: {SURVEY_NUMBER or 'ALL'}", flush=True)
    
    solver = CaptchaSolver()
    sem = asyncio.Semaphore(PARALLEL)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        print(f"🌐 Browser ready, {PARALLEL} parallel", flush=True)
        
        async def process(v):
            async with sem:
                await scrape_village(browser, v, SURVEY_NUMBER, solver)
        
        await asyncio.gather(*[process(v) for v in villages])
        await browser.close()
    
    await solver.close()
    print(f"\n✅ DONE! Villages: {stats['done']} | Found: {stats['found']} | Records: {stats['records']} | Errors: {stats['errors']}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
WORKER

# 6. Build and push
echo ""
echo "🏗️  Building container..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$JOB_NAME --quiet

# 7. Create/Update Cloud Run Job
echo ""
echo "☁️  Creating Cloud Run Job..."
if gcloud run jobs describe $JOB_NAME --region=$REGION &>/dev/null; then
    gcloud run jobs update $JOB_NAME \
        --region=$REGION \
        --image=gcr.io/$PROJECT_ID/$JOB_NAME \
        --cpu=2 --memory=4Gi \
        --task-timeout=60m \
        --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,PARALLEL=10" \
        --quiet
else
    gcloud run jobs create $JOB_NAME \
        --region=$REGION \
        --image=gcr.io/$PROJECT_ID/$JOB_NAME \
        --cpu=2 --memory=4Gi \
        --task-timeout=60m \
        --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,PARALLEL=10" \
        --quiet
fi

# Cleanup temp files
rm -f Dockerfile requirements.txt cloud_worker.py

echo ""
echo "============================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "============================================"
echo ""
echo "Run a search:"
echo "  gcloud run jobs execute $JOB_NAME --region=$REGION \\"
echo "    --update-env-vars='DISTRICT_CODE=30,SURVEY_NUMBER=10'"
echo ""
