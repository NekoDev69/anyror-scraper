"""
Optimized Cloud Run Job Worker with Full VF-7 Report Generation
- 1 Browser, 10 Parallel Contexts (tabs)
- Rate-limited Gemini API (15 RPM free tier)
- Full VF-7 extraction and HTML report generation
- Cost: ~$0.05 per district
"""

import os
import sys
import json
import asyncio
import base64
import time
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field
import aiohttp

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# ============================================
# Configuration
# ============================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PARALLEL_CONTEXTS = int(os.environ.get("PARALLEL_CONTEXTS", "10"))
RESULTS_WEBHOOK = os.environ.get("RESULTS_WEBHOOK", "")
JOB_ID = os.environ.get("JOB_ID", "")
SURVEY_FILTER = os.environ.get("SURVEY_NUMBER", "")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/tmp/results")

# Rate limiting: 15 requests per minute (Gemini free tier)
GEMINI_RPM = 15
GEMINI_INTERVAL = 60.0 / GEMINI_RPM


# ============================================
# VF7 Extractor (embedded for Cloud Run)
# ============================================
class VF7Extractor:
    """Extract and structure VF-7 land record data"""
    
    GUJ_DIGITS = {
        '૦': '0', '૧': '1', '૨': '2', '૩': '3', '૪': '4',
        '૫': '5', '૬': '6', '૭': '7', '૮': '8', '૯': '9',
        'પ': '5'
    }
    
    def guj_to_eng(self, text: str) -> str:
        if not text:
            return text
        result = text
        for guj, eng in self.GUJ_DIGITS.items():
            result = result.replace(guj, eng)
        return result
    
    def parse_area(self, area_str: str) -> dict:
        result = {"raw": area_str, "hectare": None, "are": None, "sqm": None, "total_sqm": None}
        if not area_str:
            return result
        area_eng = self.guj_to_eng(area_str)
        match = re.match(r'(\d+)-(\d+)-(\d+)', area_eng)
        if match:
            h, a, m = int(match.group(1)), int(match.group(2)), int(match.group(3))
            result.update({"hectare": h, "are": a, "sqm": m, "total_sqm": h*10000 + a*100 + m})
        return result
    
    def extract_from_scrape_result(self, scrape_result: dict) -> dict:
        """Convert raw scrape to structured format"""
        result = {
            "meta": {
                "portal_name": "AnyROR Rural Land Record",
                "record_type": "VF-7",
                "data_status_time_local": "",
                "scrape_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "owner_count": 0,
                "encumbrance_count": 0
            },
            "location": {
                "district": {"code": "", "name_local": ""},
                "taluka": {"code": "", "name_local": ""},
                "village": {"code": "", "name_local": ""}
            },
            "property_identity": {"khata_number": "", "survey_number": "", "upin": ""},
            "land_details": {
                "total_area_raw": "", "assessment_tax": "", "tenure_local": "",
                "land_use_local": "", "farm_name": "", "remarks": ""
            },
            "owners": [],
            "rights_and_remarks": {"entry_details": []},
            "raw_page_text_backup": ""
        }
        
        # Location from search params
        if scrape_result.get("district"):
            result["location"]["district"]["code"] = scrape_result["district"].get("value", "")
            result["location"]["district"]["name_local"] = scrape_result["district"].get("text", "")
        if scrape_result.get("taluka"):
            result["location"]["taluka"]["code"] = scrape_result["taluka"].get("value", "")
            result["location"]["taluka"]["name_local"] = scrape_result["taluka"].get("text", "")
        if scrape_result.get("village"):
            result["location"]["village"]["code"] = scrape_result["village"].get("value", "")
            result["location"]["village"]["name_local"] = scrape_result["village"].get("text", "")
        if scrape_result.get("survey"):
            result["property_identity"]["survey_number"] = scrape_result["survey"].get("text", "")
        
        # Extract from data
        data = scrape_result.get("data", {})
        prop = data.get("property_details", {})
        
        result["meta"]["data_status_time_local"] = prop.get("data_status_time", "")
        result["property_identity"]["upin"] = prop.get("upin", "")
        result["land_details"]["total_area_raw"] = prop.get("total_area", "")
        result["land_details"]["assessment_tax"] = self.guj_to_eng(prop.get("assessment_tax", ""))
        result["land_details"]["tenure_local"] = prop.get("tenure", "")
        result["land_details"]["land_use_local"] = prop.get("land_use", "")
        result["land_details"]["farm_name"] = prop.get("farm_name", "")
        result["land_details"]["remarks"] = prop.get("remarks", "")
        result["raw_page_text_backup"] = data.get("full_page_text", "")
        
        # Parse owners from tables
        tables = data.get("tables", [])
        if tables:
            result["owners"] = self._parse_owners(tables[0].get("text", ""))
            result["meta"]["owner_count"] = len(result["owners"])
        if len(tables) > 1:
            result["rights_and_remarks"]["entry_details"] = self._parse_encumbrances(tables[1].get("text", ""))
            result["meta"]["encumbrance_count"] = len(result["rights_and_remarks"]["entry_details"])
        
        return result

    def _parse_owners(self, text: str) -> List[dict]:
        owners = []
        if not text:
            return owners
        pattern = r'([^()\n]+)\(([૦-૯પ0-9]+)\)'
        for name, entry in re.findall(pattern, text):
            name = name.strip()
            if len(name) > 2:
                owners.append({
                    "owner_name": name,
                    "entry_number": self.guj_to_eng(entry),
                    "share": ""
                })
        return owners
    
    def _parse_encumbrances(self, text: str) -> List[dict]:
        encumbrances = []
        if not text:
            return encumbrances
        pattern = r'(.+?)<([૦-૯પ0-9]+)>'
        for desc, entry in re.findall(pattern, text):
            encumbrances.append({
                "entry_no": self.guj_to_eng(entry),
                "description": desc.strip(),
                "type": "બેંક બોજો" if "બેંક" in desc or "તારણ" in desc else "અન્ય"
            })
        return encumbrances


# ============================================
# VF7 Report Generator (embedded for Cloud Run)
# ============================================
class VF7ReportGenerator:
    """Generate HTML reports matching AnyROR portal layout"""
    
    def generate_html(self, data: dict) -> str:
        location = data.get("location", {})
        prop = data.get("property_identity", {})
        land = data.get("land_details", {})
        meta = data.get("meta", {})
        
        css = self._get_css()
        ownership_html = self._build_ownership_table(data)
        boja_html = self._build_boja_table(data)
        
        return f"""<!DOCTYPE html>
<html lang="gu">
<head>
    <meta charset="UTF-8">
    <title>VF-7 - {location.get('village', {}).get('name_local', '')}</title>
    <style>{css}</style>
</head>
<body>
<div class="container">
    <div class="header-section">
        <div class="status-time">* તા.{meta.get('data_status_time_local', '')} ની સ્થિતિએ</div>
        <div class="location-grid">
            <div class="location-item"><div class="label">District</div><div class="value">{location.get('district', {}).get('name_local', '')}</div></div>
            <div class="location-item"><div class="label">Taluka</div><div class="value">{location.get('taluka', {}).get('name_local', '')}</div></div>
            <div class="location-item"><div class="label">Village</div><div class="value">{location.get('village', {}).get('name_local', '')}</div></div>
            <div class="location-item"><div class="label">Survey No</div><div class="value">{prop.get('survey_number', '')}</div></div>
        </div>
        <div class="upin-row"><span class="upin-label">UPIN:</span> <span class="upin-value">{prop.get('upin', '')}</span></div>
    </div>
    <div class="land-section">
        <div class="section-title">Land Details</div>
        <table class="land-table">
            <tr><td class="label">Total Area (H.Are.SqMt.):</td><td class="value">{land.get('total_area_raw', '')}</td></tr>
            <tr><td class="label">Assessment Rs.:</td><td class="value">{land.get('assessment_tax', '')}</td></tr>
            <tr><td class="label">Tenure:</td><td class="value">{land.get('tenure_local', '')}</td></tr>
            <tr><td class="label">Land Use:</td><td class="value">{land.get('land_use_local', '')}</td></tr>
            <tr><td class="label">Farm Name:</td><td class="value">{land.get('farm_name', '')}</td></tr>
        </table>
    </div>
    <div class="tables-section">
        <div class="tables-grid">
            <div class="table-box"><div class="table-title">Ownership Details</div>{ownership_html}</div>
            <div class="table-box"><div class="table-title">Boja and Other Rights</div>{boja_html}</div>
        </div>
    </div>
</div>
</body>
</html>"""

    def _get_css(self) -> str:
        return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f0f0f0; padding: 20px; font-size: 13px; }
        .container { max-width: 1050px; margin: 0 auto; }
        .header-section, .land-section, .tables-section { background: #ffffcc; border: 2px solid #999; padding: 15px; margin-bottom: 10px; }
        .status-time { color: red; font-weight: bold; margin-bottom: 15px; }
        .location-grid { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 15px; }
        .location-item .label { font-weight: bold; color: #006600; font-size: 12px; }
        .location-item .value { color: #000; margin-top: 3px; }
        .upin-row { margin-top: 15px; }
        .upin-label { font-weight: bold; color: #006600; }
        .upin-value { color: blue; font-weight: bold; }
        .section-title { font-weight: bold; color: #006600; margin-bottom: 15px; }
        .land-table { width: 100%; }
        .land-table td { padding: 5px 10px 5px 0; }
        .land-table .label { font-weight: bold; white-space: nowrap; }
        .tables-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .table-box { border: 1px solid #999; background: white; }
        .table-title { background: #ccffcc; padding: 8px 10px; font-weight: bold; border-bottom: 1px solid #999; }
        .data-table { width: 100%; border-collapse: collapse; }
        .data-table th { background: #e6ffe6; padding: 8px; border: 1px solid #999; font-weight: bold; }
        .data-table td { padding: 8px; border: 1px solid #999; vertical-align: top; }
        .owner-line { margin: 3px 0; }
        .owner-line a { color: blue; text-decoration: underline; }
        """
    
    def _build_ownership_table(self, data: dict) -> str:
        owners = data.get("owners", [])
        if not owners:
            raw = data.get("raw_page_text_backup", "")
            # Try to extract from raw text
            return f'<table class="data-table"><tr><td>{raw[:500] if raw else "No data"}</td></tr></table>'
        
        owners_html = ""
        for o in owners:
            name = o.get("owner_name", "")
            entry = o.get("entry_number", "")
            owners_html += f'<div class="owner-line"><a href="#">{name}</a> ({entry})</div>'
        
        return f'<table class="data-table"><tr><th>Owners</th></tr><tr><td>{owners_html}</td></tr></table>'
    
    def _build_boja_table(self, data: dict) -> str:
        entries = data.get("rights_and_remarks", {}).get("entry_details", [])
        if not entries:
            return '<table class="data-table"><tr><th>Details</th></tr><tr><td>-</td></tr></table>'
        
        html = ""
        for e in entries:
            html += f'<div style="margin:5px 0;padding-bottom:5px;border-bottom:1px dashed #ccc;">{e.get("description", "")} &lt;{e.get("entry_no", "")}&gt;</div>'
        
        return f'<table class="data-table"><tr><th>Details</th></tr><tr><td>{html}</td></tr></table>'


# ============================================
# Data Classes
# ============================================
@dataclass
class VillageResult:
    village_code: str
    village_name: str
    taluka_name: str
    surveys_found: int
    surveys: List[Dict] = field(default_factory=list)
    records: List[Dict] = field(default_factory=list)  # Full VF-7 records
    files: Dict = field(default_factory=dict)  # Saved file paths
    error: Optional[str] = None


@dataclass
class JobResult:
    job_id: str
    district_code: str
    district_name: str
    survey_filter: str
    talukas_total: int
    talukas_scraped: int
    villages_total: int
    villages_scraped: int
    total_surveys: int
    total_records: int = 0
    matches: List[VillageResult] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0
    errors: List[Dict] = field(default_factory=list)


# ============================================
# Rate-Limited Captcha Solver
# ============================================
class RateLimitedCaptchaSolver:
    def __init__(self, api_key: str, rpm: int = 15):
        self.api_key = api_key
        self.interval = 60.0 / rpm
        self.last_request_time = 0
        self.lock = asyncio.Lock()
        self.cache: Dict[str, str] = {}
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    async def solve(self, image_bytes: bytes) -> str:
        import hashlib
        img_hash = hashlib.md5(image_bytes).hexdigest()
        if img_hash in self.cache:
            return self.cache[img_hash]
        
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self.last_request_time = time.time()
        
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                    {"text": "Read the CAPTCHA. Return ONLY the digits/letters, nothing else."}
                ]
            }]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        result = ''.join(c for c in text if c.isascii() and c.isalnum())
                        self.cache[img_hash] = result
                        return result
                    elif resp.status == 429:
                        await asyncio.sleep(60)
                        return await self.solve(image_bytes)
        except Exception as e:
            print(f"[CAPTCHA] Error: {e}")
        return ""


# ============================================
# Optimized District Scraper with Full Reports
# ============================================
class OptimizedDistrictScraper:
    BASE_URL = "https://anyror.gujarat.gov.in/LandRecordRural.aspx"
    
    SELECTORS = {
        "record_type": "#ContentPlaceHolder1_drpLandRecord",
        "district": "#ContentPlaceHolder1_ddlDistrict",
        "taluka": "#ContentPlaceHolder1_ddlTaluka",
        "village": "#ContentPlaceHolder1_ddlVillage",
        "survey_no": "#ContentPlaceHolder1_ddlSurveyNo",
        "captcha_input": "[placeholder='Enter Text Shown Above']",
        "captcha_image": "#ContentPlaceHolder1_imgCaptcha",
    }
    
    def __init__(self, parallel_contexts: int = 10, output_dir: str = OUTPUT_DIR):
        self.parallel_contexts = parallel_contexts
        self.captcha_solver = RateLimitedCaptchaSolver(GEMINI_API_KEY, GEMINI_RPM)
        self.extractor = VF7Extractor()
        self.report_generator = VF7ReportGenerator()
        self.output_dir = output_dir
        self.browser: Optional[Browser] = None
        os.makedirs(output_dir, exist_ok=True)
    
    async def scrape_district(self, district: Dict, job_id: str, survey_filter: str = "") -> JobResult:
        start_time = datetime.utcnow()
        
        all_villages = []
        for taluka in district["talukas"]:
            for village in taluka["villages"]:
                all_villages.append({
                    "district_code": district["value"],
                    "district_name": district["label"],
                    "taluka_code": taluka["value"],
                    "taluka_name": taluka["label"],
                    "village_code": village["value"],
                    "village_name": village["label"]
                })
        
        print(f"\n{'='*60}")
        print(f"DISTRICT SCRAPER WITH FULL VF-7 REPORTS")
        print(f"{'='*60}")
        print(f"District: {district['label']} ({district['value']})")
        print(f"Villages: {len(all_villages)}")
        print(f"Survey filter: {survey_filter or 'None'}")
        print(f"Output: {self.output_dir}")
        print(f"{'='*60}\n")
        
        job_result = JobResult(
            job_id=job_id,
            district_code=district["value"],
            district_name=district["label"],
            survey_filter=survey_filter,
            talukas_total=len(district["talukas"]),
            talukas_scraped=0,
            villages_total=len(all_villages),
            villages_scraped=0,
            total_surveys=0,
            started_at=start_time.isoformat()
        )
        
        async with async_playwright() as p:
            self.browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            
            try:
                semaphore = asyncio.Semaphore(self.parallel_contexts)
                
                async def process_village(village_info: Dict) -> VillageResult:
                    async with semaphore:
                        return await self._scrape_village(village_info, survey_filter)
                
                tasks = [process_village(v) for v in all_villages]
                
                completed = 0
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    completed += 1
                    job_result.villages_scraped = completed
                    
                    if result.error:
                        job_result.errors.append({"village": result.village_name, "error": result.error})
                    elif result.surveys_found > 0:
                        job_result.total_surveys += result.surveys_found
                        job_result.total_records += len(result.records)
                        job_result.matches.append(result)
                        print(f"[{completed}/{len(all_villages)}] ✓ {result.village_name}: {result.surveys_found} surveys, {len(result.records)} records")
                    
                    if completed % 50 == 0:
                        print(f"[PROGRESS] {completed}/{len(all_villages)} ({job_result.total_records} records)")
                        if RESULTS_WEBHOOK:
                            await self._post_progress(job_result)
            finally:
                await self.browser.close()
        
        end_time = datetime.utcnow()
        job_result.completed_at = end_time.isoformat()
        job_result.duration_seconds = (end_time - start_time).total_seconds()
        job_result.talukas_scraped = len(district["talukas"])
        
        return job_result

    async def _scrape_village(self, village_info: Dict, survey_filter: str) -> VillageResult:
        context = await self.browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(30000)
        page.on("dialog", lambda d: asyncio.create_task(d.accept()))
        
        result = VillageResult(
            village_code=village_info["village_code"],
            village_name=village_info["village_name"],
            taluka_name=village_info["taluka_name"],
            surveys_found=0
        )
        
        try:
            await page.goto(self.BASE_URL, wait_until="networkidle", timeout=30000)
            await page.locator(self.SELECTORS["record_type"]).select_option("1")
            await asyncio.sleep(0.3)
            
            await page.locator(self.SELECTORS["district"]).select_option(village_info["district_code"])
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            await page.locator(self.SELECTORS["taluka"]).select_option(village_info["taluka_code"])
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            await page.locator(self.SELECTORS["village"]).select_option(village_info["village_code"])
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            # Get matching surveys
            surveys = []
            for opt in await page.locator(self.SELECTORS["survey_no"]).locator("option").all():
                value = await opt.get_attribute("value")
                text = (await opt.text_content()).strip()
                if value and value not in ["0", "-1", ""] and "પસંદ" not in text:
                    if survey_filter:
                        if survey_filter in text or survey_filter == value:
                            surveys.append({"value": value, "text": text})
                    else:
                        surveys.append({"value": value, "text": text})
            
            result.surveys = surveys
            result.surveys_found = len(surveys)
            
            # Fetch full records for matching surveys
            if surveys and survey_filter:
                for survey in surveys[:5]:  # Limit to 5 per village
                    record = await self._fetch_full_record(page, village_info, survey)
                    if record:
                        result.records.append(record)
        
        except Exception as e:
            result.error = str(e)
        finally:
            await context.close()
        
        return result
    
    async def _fetch_full_record(self, page: Page, village_info: Dict, survey: Dict) -> Optional[Dict]:
        """Fetch full VF-7 record and generate HTML report"""
        try:
            await page.locator(self.SELECTORS["survey_no"]).select_option(survey["value"])
            await asyncio.sleep(0.3)
            
            for attempt in range(3):
                captcha_img = await page.locator(self.SELECTORS["captcha_image"]).screenshot()
                captcha_text = await self.captcha_solver.solve(captcha_img)
                
                if not captcha_text:
                    continue
                
                await page.locator(self.SELECTORS["captcha_input"]).fill(captcha_text)
                await page.locator(self.SELECTORS["captcha_input"]).press("Enter")
                await asyncio.sleep(2)
                
                content = await page.content()
                if "ખાતા નંબર" in content:
                    # Extract raw data
                    raw_result = await self._extract_raw_data(page, village_info, survey)
                    
                    # Structure data
                    structured = self.extractor.extract_from_scrape_result(raw_result)
                    
                    # Generate HTML
                    html = self.report_generator.generate_html(structured)
                    
                    # Save files
                    files = self._save_files(raw_result, structured, html, village_info, survey)
                    
                    return {
                        "survey": survey["text"],
                        "structured": structured,
                        "files": files
                    }
                
                try:
                    await page.locator("text=Refresh Code").click()
                    await asyncio.sleep(0.3)
                except:
                    pass
        except:
            pass
        return None

    async def _extract_raw_data(self, page: Page, village_info: Dict, survey: Dict) -> Dict:
        """Extract raw data from page - same as local scraper"""
        data = {"timestamp": datetime.now().isoformat(), "tables": [], "property_details": {}, "full_page_text": "", "success": False}
        
        # Extract tables
        tables = await page.locator("table").all()
        for i, table in enumerate(tables):
            text = await table.text_content()
            if len(text.strip()) > 200:
                data["tables"].append({"index": i, "text": text.strip()})
        
        # Get full page text
        try:
            content_area = page.locator("#ContentPlaceHolder1, body").first
            if await content_area.count() > 0:
                data["full_page_text"] = await content_area.text_content()
        except:
            pass
        
        # Extract labeled values
        text = data.get("full_page_text", "")
        patterns = {
            "data_status_time": r'તા\.?\s*([0-9૦-૯/]+\s*[0-9૦-૯:]+)\s*ની સ્થિતિએ',
            "upin": r'UPIN[^:]*[:：\)]\s*([A-Z]{2}[0-9]+)',
            "tenure": r'સત્તાપ્રકાર[^:]*[:：]\s*([^\n]+)',
            "land_use": r'જમીનનો ઉપયોગ[^:]*[:：]\s*([^\n]+)',
            "farm_name": r'ખેતરનું નામ[^:]*[:：]\s*([^\n]+)',
            "total_area": r'કુલ ક્ષેત્રફળ[^:]*:\s*\n?\s*([૦-૯0-9]+-[૦-૯0-9]+-[૦-૯0-9]+)',
            "assessment_tax": r'કુલ આકાર[^:]*:\s*\n?\s*([૦-૯0-9\.]+)',
        }
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                data["property_details"][field] = match.group(1).strip()
        
        if data["tables"]:
            data["success"] = True
        
        return {
            "district": {"value": village_info["district_code"], "text": village_info["district_name"]},
            "taluka": {"value": village_info["taluka_code"], "text": village_info["taluka_name"]},
            "village": {"value": village_info["village_code"], "text": village_info["village_name"]},
            "survey": {"value": survey["value"], "text": survey["text"]},
            "data": data
        }
    
    def _save_files(self, raw: Dict, structured: Dict, html: str, village_info: Dict, survey: Dict) -> Dict:
        """Save raw JSON, structured JSON, and HTML report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_village = re.sub(r'[^\w\s-]', '', village_info["village_name"])[:15].replace(' ', '_')
        safe_survey = re.sub(r'[^\w-]', '', survey["text"])[:10]
        base = f"vf7_{village_info['district_code']}_{safe_village}_{safe_survey}_{timestamp}"
        
        raw_path = os.path.join(self.output_dir, f"{base}_raw.json")
        struct_path = os.path.join(self.output_dir, f"{base}.json")
        html_path = os.path.join(self.output_dir, f"{base}.html")
        
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        with open(struct_path, "w", encoding="utf-8") as f:
            json.dump(structured, f, ensure_ascii=False, indent=2)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        print(f"      📄 {html_path}")
        return {"raw": raw_path, "structured": struct_path, "html": html_path}
    
    async def _post_progress(self, job_result: JobResult):
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{RESULTS_WEBHOOK}/progress",
                    json={"job_id": job_result.job_id, "villages_scraped": job_result.villages_scraped,
                          "total_surveys": job_result.total_surveys, "total_records": job_result.total_records},
                    timeout=aiohttp.ClientTimeout(total=5)
                )
        except:
            pass


# ============================================
# Main Entry Point
# ============================================
async def main():
    district_code = os.environ.get("DISTRICT_CODE", "")
    district_b64 = os.environ.get("DISTRICT_DATA_B64", "")
    job_id = os.environ.get("JOB_ID", f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    survey_filter = os.environ.get("SURVEY_NUMBER", "")
    
    district = None
    
    # Option 1: Load from bundled JSON using district code
    if district_code:
        try:
            with open("gujarat-anyror-complete.json", "r", encoding="utf-8") as f:
                gujarat_data = json.load(f)
            district = next((d for d in gujarat_data["districts"] if d["value"] == district_code), None)
            if not district:
                print(f"ERROR: District code {district_code} not found")
                sys.exit(1)
        except Exception as e:
            print(f"ERROR loading district data: {e}")
            sys.exit(1)
    # Option 2: Base64 encoded district data
    elif district_b64:
        district_json = base64.b64decode(district_b64).decode()
        district = json.loads(district_json)
    # Option 3: Config file
    elif len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            config = json.load(f)
            district = config.get("district")
            job_id = config.get("job_id", job_id)
            survey_filter = config.get("survey_filter", survey_filter)
    else:
        print("ERROR: No district data. Set DISTRICT_CODE or DISTRICT_DATA_B64")
        sys.exit(1)
    
    scraper = OptimizedDistrictScraper(parallel_contexts=PARALLEL_CONTEXTS)
    result = await scraper.scrape_district(district, job_id, survey_filter)
    
    # Save summary
    output_file = os.path.join(OUTPUT_DIR, f"result_{result.district_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    def to_dict(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return {k: to_dict(v) for k, v in asdict(obj).items()}
        elif isinstance(obj, list):
            return [to_dict(i) for i in obj]
        return obj
    
    result_dict = to_dict(result)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print("JOB COMPLETE")
    print(f"{'='*60}")
    print(f"District: {result.district_name}")
    print(f"Villages: {result.villages_scraped}/{result.villages_total}")
    print(f"Surveys found: {result.total_surveys}")
    print(f"Records fetched: {result.total_records}")
    print(f"Duration: {result.duration_seconds:.1f}s")
    print(f"Output: {output_file}")
    
    if RESULTS_WEBHOOK:
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(f"{RESULTS_WEBHOOK}/complete", json=result_dict, timeout=aiohttp.ClientTimeout(total=30))
                print(f"[WEBHOOK] Posted to {RESULTS_WEBHOOK}")
        except Exception as e:
            print(f"[WEBHOOK] Failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
