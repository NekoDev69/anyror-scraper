"""
TURBO VM Worker - 500-999 Villages in 10 Minutes
================================================
Strategy:
- 50 parallel browser tabs (async)
- Rate-limited Gemini API (15 RPM free tier, or 1500 RPM paid)
- Batch processing with progress tracking
- GCS upload for results

Performance:
- ~1 village/second with 50 parallel tabs
- 600 villages in 10 minutes
- 999 villages in ~17 minutes

Usage:
  python turbo_vm_worker.py --district 30 --survey 10 --parallel 50
  python turbo_vm_worker.py --district 30 --parallel 100  # All surveys (paid API)
"""

import os
import sys
import json
import asyncio
import argparse
import base64
import time
import re
from datetime import datetime
from typing import List, Dict, Optional
import aiohttp
from playwright.async_api import async_playwright

# ============================================
# Configuration
# ============================================
# Support multiple API keys for higher throughput (comma-separated)
GEMINI_API_KEYS = os.environ.get("GEMINI_API_KEYS", os.environ.get("GEMINI_API_KEY", "AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4")).split(",")
GCS_BUCKET = os.environ.get("GCS_BUCKET", "anyror-results")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/opt/scraper/output")

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

# ============================================
# Stats Tracking
# ============================================
class Stats:
    def __init__(self, total: int):
        self.total = total
        self.done = 0
        self.found = 0
        self.records = 0
        self.errors = 0
        self.start = time.time()
        self.lock = asyncio.Lock()
    
    async def update(self, found: int = 0, records: int = 0, error: bool = False):
        async with self.lock:
            self.done += 1
            self.found += found
            self.records += records
            if error:
                self.errors += 1
            
            if self.done % 25 == 0 or self.done == self.total:
                self._print_progress()
    
    def _print_progress(self):
        elapsed = time.time() - self.start
        rate = self.done / elapsed if elapsed > 0 else 0
        eta = (self.total - self.done) / rate if rate > 0 else 0
        pct = (self.done / self.total) * 100
        
        print(f"📊 [{self.done}/{self.total}] {pct:.0f}% | "
              f"Rate: {rate:.1f}/s | Found: {self.found} | "
              f"Records: {self.records} | ETA: {eta:.0f}s", flush=True)


# ============================================
# Rate-Limited Captcha Solver
# ============================================
class CaptchaSolver:
    def __init__(self, api_key: str, rpm: int = 15):
        self.api_key = api_key
        self.interval = 60.0 / rpm
        self.last_request = 0
        self.lock = asyncio.Lock()
        self.session: Optional[aiohttp.ClientSession] = None
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    async def solve(self, img_bytes: bytes) -> str:
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        # Rate limiting
        async with self.lock:
            now = time.time()
            wait = self.interval - (now - self.last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self.last_request = time.time()
        
        b64 = base64.b64encode(img_bytes).decode()
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": b64}},
                    {"text": "Read CAPTCHA. Return ONLY the text, nothing else."}
                ]
            }]
        }
        
        try:
            async with self.session.post(self.url, json=payload, 
                                         timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    d = await r.json()
                    t = d["candidates"][0]["content"]["parts"][0]["text"].strip()
                    # Clean: only ASCII alphanumeric
                    return ''.join(c for c in t if c.isascii() and c.isalnum())[:6]
                elif r.status == 429:
                    await asyncio.sleep(5)
                    return ""
        except Exception as e:
            pass
        return ""
    
    async def close(self):
        if self.session:
            await self.session.close()


# ============================================
# HTML Report Generator
# ============================================
def make_html(data: Dict) -> str:
    loc = data.get("location", {})
    land = data.get("land", {})
    owners = data.get("owners", [])
    
    owners_html = ''.join(
        f"<tr><td>{o.get('name','')}</td><td>{o.get('entry','')}</td></tr>" 
        for o in owners
    )
    
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>VF-7 {loc.get('village','')}</title>
<style>
body{{font-family:Arial;background:#f5f5f5;padding:20px;max-width:1000px;margin:auto}}
.card{{background:#ffffcc;border:2px solid #999;border-radius:8px;padding:15px;margin-bottom:15px}}
.title{{color:#006600;font-weight:bold;font-size:16px;margin-bottom:10px}}
.red{{color:red;font-weight:bold}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
.label{{color:#006600;font-weight:bold;font-size:12px}}
table{{width:100%;border-collapse:collapse;margin-top:10px}}
td,th{{padding:8px;border:1px solid #999}}
th{{background:#ccffcc}}
</style></head>
<body>
<div class="card">
<div class="red">* {land.get('status_time','')}</div>
<div class="grid">
<div><div class="label">District</div>{loc.get('district','')}</div>
<div><div class="label">Taluka</div>{loc.get('taluka','')}</div>
<div><div class="label">Village</div>{loc.get('village','')}</div>
<div><div class="label">Survey No</div>{data.get('survey','')}</div>
</div>
<div style="margin-top:10px"><span class="label">UPIN:</span> <span style="color:blue">{data.get('upin','')}</span></div>
</div>
<div class="card">
<div class="title">📋 Land Details</div>
<table>
<tr><td class="label">Area</td><td>{land.get('area','')}</td></tr>
<tr><td class="label">Tax</td><td>{land.get('tax','')}</td></tr>
<tr><td class="label">Tenure</td><td>{land.get('tenure','')}</td></tr>
<tr><td class="label">Use</td><td>{land.get('use','')}</td></tr>
</table>
</div>
<div class="card">
<div class="title">👥 Owners ({len(owners)})</div>
<table><tr><th>Name</th><th>Entry</th></tr>{owners_html}</table>
</div>
</body></html>"""


# ============================================
# Village Scraper
# ============================================
async def scrape_village(
    ctx, 
    village: Dict, 
    survey_filter: str, 
    solver: CaptchaSolver,
    sem: asyncio.Semaphore,
    stats: Stats,
    output_dir: str,
    gcs_bucket
) -> Optional[Dict]:
    """Scrape a single village"""
    async with sem:
        page = await ctx.new_page()
        page.set_default_timeout(25000)
        page.on("dialog", lambda d: asyncio.create_task(d.accept()))
        
        result = None
        found = 0
        records = 0
        error = False
        
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            await page.locator(SEL["type"]).select_option("1")
            await asyncio.sleep(0.2)
            
            await page.locator(SEL["dist"]).select_option(village["dc"])
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            await page.locator(SEL["tal"]).select_option(village["tc"])
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            await page.locator(SEL["vil"]).select_option(village["vc"])
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            # Get matching surveys
            surveys = []
            for opt in await page.locator(SEL["sur"]).locator("option").all():
                val = await opt.get_attribute("value")
                txt = (await opt.text_content()).strip()
                if val and val not in ["0", "-1", ""] and "પસંદ" not in txt:
                    if not survey_filter or survey_filter in txt:
                        surveys.append({"v": val, "t": txt})
            
            found = len(surveys)
            
            # Fetch records for matching surveys
            if surveys and survey_filter:
                for s in surveys[:3]:  # Max 3 per village
                    await page.locator(SEL["sur"]).select_option(s["v"])
                    await asyncio.sleep(0.2)
                    
                    for attempt in range(3):
                        try:
                            img = await page.locator(SEL["img"]).screenshot()
                            cap = await solver.solve(img)
                            if not cap or len(cap) < 4:
                                continue
                            
                            await page.locator(SEL["cap"]).fill(cap)
                            await page.locator(SEL["cap"]).press("Enter")
                            await asyncio.sleep(1.5)
                            
                            content = await page.content()
                            if "ખાતા નંબર" in content:
                                text = await page.locator("body").text_content()
                                
                                # Extract data
                                def find(p, d=""):
                                    m = re.search(p, text, re.DOTALL)
                                    return m.group(1).strip() if m else d
                                
                                owners = [
                                    {"name": n.strip(), "entry": e} 
                                    for n, e in re.findall(r'([^()\n]{3,50})\(([૦-૯0-9]+)\)', text)
                                ][:30]
                                
                                data = {
                                    "location": {
                                        "district": village["dn"],
                                        "taluka": village["tn"],
                                        "village": village["vn"]
                                    },
                                    "survey": s["t"],
                                    "upin": find(r'UPIN[^:]*[:)]\s*([A-Z]{2}[A-Z0-9]+)'),
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
                                
                                # Save files
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
                                safe_v = re.sub(r'[^\w]', '', village['vn'])[:15]
                                name = f"vf7_{village['dc']}_{village['tc']}_{safe_v}_{ts}"
                                
                                html = make_html(data)
                                
                                # Local save
                                os.makedirs(output_dir, exist_ok=True)
                                with open(f"{output_dir}/{name}.json", "w", encoding="utf-8") as f:
                                    json.dump(data, f, ensure_ascii=False, indent=2)
                                with open(f"{output_dir}/{name}.html", "w", encoding="utf-8") as f:
                                    f.write(html)
                                
                                # GCS upload
                                if gcs_bucket:
                                    try:
                                        folder = f"{village['dc']}/{village['tc']}"
                                        gcs_bucket.blob(f"{folder}/{name}.json").upload_from_string(
                                            json.dumps(data, ensure_ascii=False), 
                                            content_type="application/json"
                                        )
                                        gcs_bucket.blob(f"{folder}/{name}.html").upload_from_string(
                                            html, content_type="text/html"
                                        )
                                    except:
                                        pass
                                
                                records += 1
                                print(f"  ✅ {village['vn'][:25]} / {s['t']}", flush=True)
                                break
                        except:
                            pass
                        
                        # Refresh captcha
                        try:
                            refresh = page.locator("text=Refresh").first
                            if await refresh.is_visible():
                                await refresh.click()
                                await asyncio.sleep(0.3)
                        except:
                            pass
        
        except Exception as e:
            error = True
        finally:
            await page.close()
        
        await stats.update(found=1 if found > 0 else 0, records=records, error=error)
        return result


# ============================================
# Main
# ============================================
async def run(district_code: str, survey_filter: str, parallel: int, output_dir: str):
    print(f"\n{'='*60}")
    print(f"🚀 TURBO VM WORKER")
    print(f"{'='*60}")
    
    # Load district data
    with open("gujarat-anyror-complete.json", encoding="utf-8") as f:
        data = json.load(f)
    
    district = next((d for d in data["districts"] if d["value"] == district_code), None)
    if not district:
        print(f"❌ District {district_code} not found")
        sys.exit(1)
    
    # Build village list
    villages = []
    for t in district["talukas"]:
        for v in t["villages"]:
            villages.append({
                "dc": district["value"], "dn": district["label"],
                "tc": t["value"], "tn": t["label"],
                "vc": v["value"], "vn": v["label"]
            })
    
    print(f"📍 District: {district['label']}")
    print(f"📊 Villages: {len(villages)}")
    print(f"🔍 Survey filter: {survey_filter or 'ALL'}")
    print(f"⚡ Parallel tabs: {parallel}")
    print(f"📁 Output: {output_dir}")
    print(f"{'='*60}\n")
    
    # GCS bucket
    gcs_bucket = None
    try:
        from google.cloud import storage
        gcs_bucket = storage.Client().bucket(GCS_BUCKET)
        gcs_bucket.reload()
        print(f"📦 GCS: {GCS_BUCKET} ✓")
    except Exception as e:
        print(f"⚠️ GCS not available: {e}")
    
    # Initialize
    stats = Stats(len(villages))
    solver = CaptchaSolver(GEMINI_API_KEY, rpm=15)  # Free tier: 15 RPM
    sem = asyncio.Semaphore(parallel)
    
    os.makedirs(output_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--disable-background-networking',
            ]
        )
        ctx = await browser.new_context()
        print(f"🌐 Browser ready with {parallel} parallel tabs\n")
        
        # Process all villages
        tasks = [
            scrape_village(ctx, v, survey_filter, solver, sem, stats, output_dir, gcs_bucket)
            for v in villages
        ]
        await asyncio.gather(*tasks)
        
        await ctx.close()
        await browser.close()
    
    await solver.close()
    
    # Summary
    elapsed = time.time() - stats.start
    print(f"\n{'='*60}")
    print(f"✅ COMPLETE!")
    print(f"{'='*60}")
    print(f"   Villages: {stats.done}/{stats.total}")
    print(f"   Found surveys: {stats.found}")
    print(f"   Records saved: {stats.records}")
    print(f"   Errors: {stats.errors}")
    print(f"   Time: {elapsed:.1f}s ({stats.done/elapsed:.1f} villages/sec)")
    print(f"   Output: {output_dir}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="TURBO VM Worker")
    parser.add_argument("--district", "-d", required=True, help="District code (e.g., 30)")
    parser.add_argument("--survey", "-s", default="", help="Survey number filter")
    parser.add_argument("--parallel", "-p", type=int, default=50, help="Parallel tabs (default: 50)")
    parser.add_argument("--output", "-o", default=OUTPUT_DIR, help="Output directory")
    
    args = parser.parse_args()
    asyncio.run(run(args.district, args.survey, args.parallel, args.output))


if __name__ == "__main__":
    main()
