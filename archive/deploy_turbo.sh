#!/bin/bash
# TURBO Deploy - Parallel AnyROR Scraper
# Single browser, 40 parallel tabs

set -e

PROJECT_ID="anyror-scraper-2026"
REGION="asia-south1"
GEMINI_API_KEY="AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4"
JOB_NAME="anyror-turbo"

echo "============================================"
echo "🚀 TURBO AnyROR - 40 Parallel Tabs"
echo "============================================"

gcloud config set project $PROJECT_ID
gcloud services enable cloudbuild.googleapis.com run.googleapis.com storage.googleapis.com --quiet

# Create GCS bucket
gsutil mb -p $PROJECT_ID -l $REGION gs://anyror-results 2>/dev/null || true

cat > Dockerfile << 'DOCKERFILE'
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /tmp/results
ENV PYTHONUNBUFFERED=1
CMD ["python", "-u", "turbo_worker.py"]
DOCKERFILE

cat > requirements.txt << 'REQ'
playwright==1.41.0
aiohttp==3.9.1
google-cloud-storage==2.14.0
REQ

cat > turbo_worker.py << 'PYEOF'
"""
TURBO AnyROR Worker - 40 Parallel Tabs
Single browser, single context, 40 pages
"""
import os, sys, json, asyncio, base64, time, re
from datetime import datetime
import aiohttp
from playwright.async_api import async_playwright
from google.cloud import storage

PARALLEL = int(os.environ.get("PARALLEL", "40"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DISTRICT_CODE = os.environ.get("DISTRICT_CODE", "")
TALUKA_CODE = os.environ.get("TALUKA_CODE", "")
SURVEY_NUMBER = os.environ.get("SURVEY_NUMBER", "")
OUTPUT_DIR = "/tmp/results"
GCS_BUCKET = "anyror-results"
PROJECT_ID = "anyror-scraper-2026"

print(f"🚀 TURBO Worker | {PARALLEL} parallel tabs", flush=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# GCS
try:
    bucket = storage.Client(project=PROJECT_ID).bucket(GCS_BUCKET)
    bucket.reload()
    print(f"📦 GCS: {GCS_BUCKET} ✓", flush=True)
except Exception as e:
    print(f"⚠️ GCS: {e}", flush=True)
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

stats = {"done": 0, "found": 0, "records": 0, "errors": 0, "total": 0, "start": time.time()}
stats_lock = asyncio.Lock()
results = []
results_lock = asyncio.Lock()

async def update_stats(found=0, records=0, error=False):
    async with stats_lock:
        stats["done"] += 1
        stats["found"] += found
        stats["records"] += records
        if error: stats["errors"] += 1
        
        if stats["done"] % 20 == 0 or stats["done"] == stats["total"]:
            elapsed = time.time() - stats["start"]
            rate = stats["done"] / elapsed if elapsed > 0 else 0
            eta = (stats["total"] - stats["done"]) / rate if rate > 0 else 0
            print(f"📊 {stats['done']}/{stats['total']} ({rate:.1f}/s) | Found: {stats['found']} | Records: {stats['records']} | ETA: {eta:.0f}s", flush=True)

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
            {"text": "Read CAPTCHA. Return ONLY the text, nothing else."}
        ]}]}
        
        try:
            async with self.session.post(self.url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    d = await r.json()
                    t = d["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return ''.join(c for c in t if c.isascii() and c.isalnum())[:6]
        except: pass
        return ""
    
    async def close(self):
        if self.session: await self.session.close()

def make_html(data):
    loc = data.get("location", {})
    prop = data.get("property", {})
    land = data.get("land", {})
    owners_html = ''.join(f"<tr><td>{o.get('name','')}</td><td>{o.get('entry','')}</td></tr>" for o in data.get('owners', []))
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>VF-7 {loc.get('village','')}</title>
<style>body{{font-family:Arial;background:#f5f5f5;padding:20px;max-width:1000px;margin:auto}}
.card{{background:#ffffcc;border:2px solid #999;border-radius:8px;padding:15px;margin-bottom:15px}}
.title{{color:#006600;font-weight:bold;font-size:16px;margin-bottom:10px}}
.red{{color:red;font-weight:bold}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
.label{{color:#006600;font-weight:bold;font-size:12px}}
table{{width:100%;border-collapse:collapse;margin-top:10px}}
td,th{{padding:8px;border:1px solid #999}}
th{{background:#ccffcc}}</style></head>
<body>
<div class="card"><div class="red">* {land.get('status_time','')}</div>
<div class="grid">
<div><div class="label">District</div>{loc.get('district','')}</div>
<div><div class="label">Taluka</div>{loc.get('taluka','')}</div>
<div><div class="label">Village</div>{loc.get('village','')}</div>
<div><div class="label">Survey No</div>{prop.get('survey','')}</div>
</div>
<div style="margin-top:10px"><span class="label">UPIN:</span> <span style="color:blue">{prop.get('upin','')}</span></div></div>
<div class="card"><div class="title">📋 Land Details</div>
<table><tr><td class="label">Area</td><td>{land.get('area','')}</td></tr>
<tr><td class="label">Tax</td><td>{land.get('tax','')}</td></tr>
<tr><td class="label">Tenure</td><td>{land.get('tenure','')}</td></tr>
<tr><td class="label">Use</td><td>{land.get('use','')}</td></tr></table></div>
<div class="card"><div class="title">👥 Owners ({len(data.get('owners',[]))})</div>
<table><tr><th>Name</th><th>Entry</th></tr>{owners_html}</table></div>
</body></html>"""

async def scrape_village(ctx, v, survey_filter, solver, sem):
    """Scrape a single village"""
    async with sem:
        page = await ctx.new_page()
        page.set_default_timeout(20000)
        page.on("dialog", lambda d: asyncio.create_task(d.accept()))
        
        found, recs = 0, 0
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            await page.locator(SEL["type"]).select_option("1")
            await asyncio.sleep(0.2)
            
            await page.locator(SEL["dist"]).select_option(v["dc"])
            await page.wait_for_load_state("networkidle", timeout=12000)
            
            await page.locator(SEL["tal"]).select_option(v["tc"])
            await page.wait_for_load_state("networkidle", timeout=12000)
            
            await page.locator(SEL["vil"]).select_option(v["vc"])
            await page.wait_for_load_state("networkidle", timeout=12000)
            
            # Get surveys
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
                    await asyncio.sleep(0.2)
                    
                    for attempt in range(3):
                        try:
                            img = await page.locator(SEL["img"]).screenshot()
                            cap = await solver.solve(img)
                            if not cap or len(cap) < 4: continue
                            
                            await page.locator(SEL["cap"]).fill(cap)
                            await page.locator(SEL["cap"]).press("Enter")
                            await asyncio.sleep(1)
                            
                            content = await page.content()
                            if "ખાતા નંબર" in content:
                                text = await page.locator("body").text_content()
                                
                                def find(p, d=""):
                                    m = re.search(p, text, re.DOTALL)
                                    return m.group(1).strip() if m else d
                                
                                owners = [{"name": n.strip(), "entry": e} for n, e in re.findall(r'([^()\n]{3,50})\(([૦-૯0-9]+)\)', text)][:30]
                                
                                data = {
                                    "location": {"district": v["dn"], "taluka": v["tn"], "village": v["vn"]},
                                    "property": {"survey": s["t"], "upin": find(r'UPIN[^:]*[:)]\s*([A-Z]{2}[A-Z0-9]+)')},
                                    "land": {
                                        "status_time": find(r'તા\.?\s*([0-9૦-૯/:\s]+)\s*ની'),
                                        "area": find(r'([૦-૯0-9]+-[૦-૯0-9]+-[૦-૯0-9]+)'),
                                        "tax": find(r'કુલ આકાર[^:]*:\s*\n?\s*([૦-૯0-9\.]+)'),
                                        "tenure": find(r'સત્તાપ્રકાર[^:]*:\s*([^\n]+)'),
                                        "use": find(r'જમીનનો ઉપયોગ[^:]*:\s*([^\n]+)'),
                                    },
                                    "owners": owners,
                                    "scraped_at": datetime.now().isoformat()
                                }
                                
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
                                safe_village = re.sub(r'[^\w]', '', v['vn'])[:15]
                                name = f"vf7_{v['dc']}_{v['tc']}_{safe_village}_{ts}"
                                
                                html = make_html(data)
                                
                                # Save locally
                                with open(f"{OUTPUT_DIR}/{name}.json", "w", encoding="utf-8") as f:
                                    json.dump(data, f, ensure_ascii=False, indent=2)
                                with open(f"{OUTPUT_DIR}/{name}.html", "w", encoding="utf-8") as f:
                                    f.write(html)
                                
                                # Upload to GCS
                                if bucket:
                                    try:
                                        folder = f"{DISTRICT_CODE}/{v['tc']}"
                                        bucket.blob(f"{folder}/{name}.json").upload_from_string(
                                            json.dumps(data, ensure_ascii=False), content_type="application/json")
                                        bucket.blob(f"{folder}/{name}.html").upload_from_string(
                                            html, content_type="text/html")
                                    except: pass
                                
                                async with results_lock:
                                    results.append(data)
                                
                                recs += 1
                                print(f"  ✅ {v['vn'][:20]} / {s['t']}", flush=True)
                                break
                        except: pass
                        
                        try:
                            refresh = page.locator("text=Refresh").first
                            if await refresh.is_visible():
                                await refresh.click()
                                await asyncio.sleep(0.3)
                        except: pass
            
            await update_stats(found=1 if found > 0 else 0, records=recs)
            
        except Exception as e:
            await update_stats(error=True)
        finally:
            await page.close()

async def main():
    if not DISTRICT_CODE:
        print("ERROR: Set DISTRICT_CODE", flush=True)
        sys.exit(1)
    
    with open("gujarat-anyror-complete.json", encoding="utf-8") as f:
        data = json.load(f)
    
    district = next((d for d in data["districts"] if d["value"] == DISTRICT_CODE), None)
    if not district:
        print(f"ERROR: District {DISTRICT_CODE} not found", flush=True)
        sys.exit(1)
    
    villages = []
    for t in district["talukas"]:
        if TALUKA_CODE and t["value"] != TALUKA_CODE:
            continue
        for v in t["villages"]:
            villages.append({
                "dc": district["value"], "dn": district["label"],
                "tc": t["value"], "tn": t["label"],
                "vc": v["value"], "vn": v["label"]
            })
    
    stats["total"] = len(villages)
    print(f"📍 District: {district['label']}", flush=True)
    print(f"   Villages: {len(villages)} | Survey: {SURVEY_NUMBER or 'ALL'}", flush=True)
    
    solver = CaptchaSolver()
    sem = asyncio.Semaphore(PARALLEL)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--single-process']
        )
        ctx = await browser.new_context()
        print(f"🌐 Browser ready, {PARALLEL} parallel tabs", flush=True)
        
        tasks = [scrape_village(ctx, v, SURVEY_NUMBER, solver, sem) for v in villages]
        await asyncio.gather(*tasks)
        
        await ctx.close()
        await browser.close()
    
    await solver.close()
    
    elapsed = time.time() - stats["start"]
    print(f"\n{'='*50}", flush=True)
    print(f"✅ COMPLETE!", flush=True)
    print(f"   Villages: {stats['done']}/{stats['total']}", flush=True)
    print(f"   Found surveys: {stats['found']}", flush=True)
    print(f"   Records saved: {stats['records']}", flush=True)
    print(f"   Errors: {stats['errors']}", flush=True)
    print(f"   Time: {elapsed:.1f}s ({stats['done']/elapsed:.1f} villages/sec)", flush=True)
    print(f"{'='*50}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
PYEOF

echo "🏗️  Building..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$JOB_NAME --quiet

echo "☁️  Updating job..."
gcloud run jobs update $JOB_NAME \
    --region=$REGION \
    --image=gcr.io/$PROJECT_ID/$JOB_NAME \
    --cpu=4 --memory=8Gi \
    --task-timeout=60m \
    --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,PARALLEL=40" \
    --quiet 2>/dev/null || \
gcloud run jobs create $JOB_NAME \
    --region=$REGION \
    --image=gcr.io/$PROJECT_ID/$JOB_NAME \
    --cpu=4 --memory=8Gi \
    --task-timeout=60m \
    --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,PARALLEL=40" \
    --quiet

rm -f Dockerfile requirements.txt turbo_worker.py

echo ""
echo "✅ TURBO DEPLOYED!"
echo ""
echo "Run: gcloud run jobs execute $JOB_NAME --region=$REGION --update-env-vars='DISTRICT_CODE=30,SURVEY_NUMBER=10'"
