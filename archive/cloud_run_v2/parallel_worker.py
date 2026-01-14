"""
Cloud Run Job Worker - Parallel Browser Scraping
Runs multiple browser contexts simultaneously for max speed

Each job handles one district with 5 parallel browser contexts
"""

import os
import sys
import json
import asyncio
import base64
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import aiohttp

# Playwright async
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Config
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PARALLEL_CONTEXTS = int(os.environ.get("PARALLEL_CONTEXTS", "5"))  # 5 parallel browsers
RESULTS_WEBHOOK = os.environ.get("RESULTS_WEBHOOK", "")  # VM endpoint to post results
MAX_RETRIES = 2


@dataclass
class VillageResult:
    village_code: str
    village_name: str
    surveys_found: int
    surveys: List[Dict]
    sample_data: Optional[Dict] = None
    error: Optional[str] = None


@dataclass 
class TalukaResult:
    taluka_code: str
    taluka_name: str
    villages_total: int
    villages_scraped: int
    total_surveys: int
    results: List[VillageResult]
    duration_seconds: float


@dataclass
class JobResult:
    job_id: str
    district_code: str
    district_name: str
    talukas_total: int
    talukas_scraped: int
    villages_total: int
    villages_scraped: int
    total_surveys: int
    started_at: str
    completed_at: str
    duration_seconds: float
    taluka_results: List[TalukaResult]
    errors: List[Dict]


class AsyncCaptchaSolver:
    """Async Gemini captcha solver"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    async def solve(self, image_bytes: bytes) -> str:
        """Solve captcha via Gemini API"""
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                    {"text": "Read the CAPTCHA. Return ONLY the digits/letters, nothing else."}
                ]
            }]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    # Clean - only ASCII alphanumeric
                    return ''.join(c for c in text if c.isascii() and c.isalnum())
                return ""


class ParallelDistrictScraper:
    """Scrapes entire district with parallel browser contexts"""
    
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
    
    def __init__(self, parallel_contexts: int = 5):
        self.parallel_contexts = parallel_contexts
        self.captcha_solver = AsyncCaptchaSolver(GEMINI_API_KEY)
        self.browser: Optional[Browser] = None
    
    async def scrape_district(self, district: Dict, job_id: str = None, survey_filter: str = "") -> JobResult:
        """Scrape entire district with parallel contexts"""
        
        start_time = datetime.utcnow()
        
        print(f"\n{'='*60}")
        print(f"DISTRICT: {district['label']} ({district['value']})")
        print(f"Talukas: {len(district['talukas'])}")
        print(f"Parallel contexts: {self.parallel_contexts}")
        if survey_filter:
            print(f"Survey filter: {survey_filter}")
        print(f"{'='*60}\n")
        
        job_result = JobResult(
            job_id=job_id or f"job_{district['value']}_{start_time.strftime('%Y%m%d_%H%M%S')}",
            district_code=district["value"],
            district_name=district["label"],
            talukas_total=len(district["talukas"]),
            talukas_scraped=0,
            villages_total=sum(len(t["villages"]) for t in district["talukas"]),
            villages_scraped=0,
            total_surveys=0,
            started_at=start_time.isoformat(),
            completed_at="",
            duration_seconds=0,
            taluka_results=[],
            errors=[]
        )
        
        async with async_playwright() as p:
            # Launch browser with optimized settings
            self.browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--single-process'
                ]
            )
            
            try:
                for taluka in district["talukas"]:
                    print(f"\n[TALUKA] {taluka['label']} ({len(taluka['villages'])} villages)")
                    
                    taluka_result = await self._scrape_taluka_parallel(
                        district["value"], taluka, survey_filter
                    )
                    
                    job_result.taluka_results.append(taluka_result)
                    job_result.talukas_scraped += 1
                    job_result.villages_scraped += taluka_result.villages_scraped
                    job_result.total_surveys += taluka_result.total_surveys
                    
                    print(f"   ✓ Scraped {taluka_result.villages_scraped} villages, {taluka_result.total_surveys} surveys")
                    
                    # Post progress to webhook if configured
                    if RESULTS_WEBHOOK:
                        await self._post_progress(job_result)
            
            finally:
                await self.browser.close()
        
        end_time = datetime.utcnow()
        job_result.completed_at = end_time.isoformat()
        job_result.duration_seconds = (end_time - start_time).total_seconds()
        
        return job_result
    
    async def _scrape_taluka_parallel(self, district_code: str, taluka: Dict, survey_filter: str = "") -> TalukaResult:
        """Scrape all villages in taluka using parallel contexts"""
        
        start_time = datetime.utcnow()
        villages = taluka["villages"]
        
        # Create semaphore to limit concurrent contexts
        semaphore = asyncio.Semaphore(self.parallel_contexts)
        
        async def scrape_with_semaphore(village: Dict) -> VillageResult:
            async with semaphore:
                return await self._scrape_village(district_code, taluka["value"], village, survey_filter)
        
        # Run all villages in parallel (limited by semaphore)
        tasks = [scrape_with_semaphore(v) for v in villages]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        village_results = []
        total_surveys = 0
        
        for village, result in zip(villages, results):
            if isinstance(result, Exception):
                village_results.append(VillageResult(
                    village_code=village["value"],
                    village_name=village["label"],
                    surveys_found=0,
                    surveys=[],
                    error=str(result)
                ))
            else:
                village_results.append(result)
                total_surveys += result.surveys_found
        
        end_time = datetime.utcnow()
        
        return TalukaResult(
            taluka_code=taluka["value"],
            taluka_name=taluka["label"],
            villages_total=len(villages),
            villages_scraped=len([r for r in village_results if not r.error]),
            total_surveys=total_surveys,
            results=village_results,
            duration_seconds=(end_time - start_time).total_seconds()
        )
    
    async def _scrape_village(self, district_code: str, taluka_code: str, village: Dict, survey_filter: str = "") -> VillageResult:
        """Scrape single village - get all survey numbers"""
        
        context = await self.browser.new_context()
        page = await context.new_page()
        
        # Handle dialogs
        page.on("dialog", lambda d: asyncio.create_task(d.accept()))
        
        try:
            await page.goto(self.BASE_URL, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            # Select VF-7
            await page.locator(self.SELECTORS["record_type"]).select_option("1")
            await asyncio.sleep(0.3)
            
            # Select location
            await page.locator(self.SELECTORS["district"]).select_option(district_code)
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            await page.locator(self.SELECTORS["taluka"]).select_option(taluka_code)
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            await page.locator(self.SELECTORS["village"]).select_option(village["value"])
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Get all survey numbers
            surveys = []
            for opt in await page.locator(self.SELECTORS["survey_no"]).locator("option").all():
                value = await opt.get_attribute("value")
                text = (await opt.text_content()).strip()
                if value and value not in ["0", "-1", ""] and "પસંદ" not in text:
                    # Apply survey filter if provided
                    if survey_filter:
                        if survey_filter in text or survey_filter == value:
                            surveys.append({"value": value, "text": text})
                    else:
                        surveys.append({"value": value, "text": text})
            
            # Optionally fetch sample record for matching surveys
            sample_data = None
            if surveys and len(surveys) > 0:
                sample_data = await self._fetch_sample_record(page, surveys[0])
            
            return VillageResult(
                village_code=village["value"],
                village_name=village["label"],
                surveys_found=len(surveys),
                surveys=surveys,
                sample_data=sample_data
            )
            
        except Exception as e:
            return VillageResult(
                village_code=village["value"],
                village_name=village["label"],
                surveys_found=0,
                surveys=[],
                error=str(e)
            )
        
        finally:
            await context.close()
    
    async def _fetch_sample_record(self, page: Page, survey: Dict) -> Optional[Dict]:
        """Fetch one sample VF-7 record"""
        
        try:
            await page.locator(self.SELECTORS["survey_no"]).select_option(survey["value"])
            await asyncio.sleep(0.3)
            
            for attempt in range(MAX_RETRIES):
                # Get captcha
                captcha_img = await page.locator(self.SELECTORS["captcha_image"]).screenshot()
                captcha_text = await self.captcha_solver.solve(captcha_img)
                
                if not captcha_text:
                    continue
                
                await page.locator(self.SELECTORS["captcha_input"]).fill(captcha_text)
                await page.locator(self.SELECTORS["captcha_input"]).press("Enter")
                
                await asyncio.sleep(2)
                
                content = await page.content()
                if "ખાતા નંબર" in content:
                    # Extract table data
                    tables = await page.locator("table").all()
                    table_text = ""
                    for t in tables:
                        txt = await t.text_content()
                        if len(txt) > 200:
                            table_text = txt[:2000]
                            break
                    
                    return {
                        "survey": survey["text"],
                        "data": table_text
                    }
                
                # Refresh captcha
                try:
                    await page.locator("text=Refresh Code").click()
                    await asyncio.sleep(0.3)
                except:
                    pass
            
            return None
            
        except:
            return None
    
    async def _post_progress(self, job_result: JobResult):
        """Post progress to orchestrator VM"""
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{RESULTS_WEBHOOK}/progress",
                    json={
                        "job_id": job_result.job_id,
                        "district": job_result.district_name,
                        "talukas_scraped": job_result.talukas_scraped,
                        "villages_scraped": job_result.villages_scraped,
                        "total_surveys": job_result.total_surveys
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                )
        except:
            pass  # Don't fail job if webhook fails


# Entry point for Cloud Run Job
async def main():
    """Main entry point"""
    
    # Get job config from environment or args
    district_json = os.environ.get("DISTRICT_DATA")
    district_b64 = os.environ.get("DISTRICT_DATA_B64")
    job_id = os.environ.get("JOB_ID", "")
    survey_number = os.environ.get("SURVEY_NUMBER", "")
    
    district = None
    
    # Try base64 encoded data first
    if district_b64:
        import base64
        district_json = base64.b64decode(district_b64).decode()
        district = json.loads(district_json)
    elif district_json:
        district = json.loads(district_json)
    elif len(sys.argv) > 1:
        # Load from file
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            config = json.load(f)
            district = config.get("district")
            job_id = config.get("job_id", job_id)
            survey_number = config.get("survey_number", survey_number)
    
    if not district:
        print("ERROR: No district data provided")
        print("Usage: python parallel_worker.py <config.json>")
        print("Or set DISTRICT_DATA_B64 environment variable")
        sys.exit(1)
    
    print(f"[CONFIG] Job ID: {job_id}")
    print(f"[CONFIG] Survey Number Filter: {survey_number or 'None (all surveys)'}")
    
    # Run scraper
    scraper = ParallelDistrictScraper(parallel_contexts=PARALLEL_CONTEXTS)
    result = await scraper.scrape_district(district, job_id, survey_number)
    
    # Save results
    output_file = f"result_{result.district_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Convert dataclasses to dict for JSON
    def to_dict(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return {k: to_dict(v) for k, v in asdict(obj).items()}
        elif isinstance(obj, list):
            return [to_dict(i) for i in obj]
        return obj
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(to_dict(result), f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print("JOB COMPLETE")
    print(f"{'='*60}")
    print(f"District: {result.district_name}")
    print(f"Talukas: {result.talukas_scraped}/{result.talukas_total}")
    print(f"Villages: {result.villages_scraped}/{result.villages_total}")
    print(f"Total Surveys: {result.total_surveys}")
    print(f"Duration: {result.duration_seconds:.1f} seconds")
    print(f"Output: {output_file}")
    
    # Post final results to webhook
    if RESULTS_WEBHOOK:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{RESULTS_WEBHOOK}/complete",
                json=to_dict(result),
                timeout=aiohttp.ClientTimeout(total=30)
            )


if __name__ == "__main__":
    asyncio.run(main())
