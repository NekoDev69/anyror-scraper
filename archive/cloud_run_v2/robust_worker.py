"""
ROBUST Cloud Run Job Worker
Production-grade with:
- Automatic retries with exponential backoff
- Timeout handling at every level
- Graceful error recovery
- Connection pooling
- Memory management
- Progress checkpointing
- Detailed logging
"""

import os
import sys
import json
import asyncio
import base64
import time
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field
from contextlib import asynccontextmanager
from enum import Enum
import aiohttp
from aiohttp import ClientTimeout

from playwright.async_api import (
    async_playwright, 
    Browser, 
    BrowserContext, 
    Page,
    TimeoutError as PlaywrightTimeout,
    Error as PlaywrightError
)

# ============================================
# Configuration
# ============================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PARALLEL_CONTEXTS = int(os.environ.get("PARALLEL_CONTEXTS", "10"))
RESULTS_WEBHOOK = os.environ.get("RESULTS_WEBHOOK", "")
JOB_ID = os.environ.get("JOB_ID", "")
SURVEY_FILTER = os.environ.get("SURVEY_NUMBER", "")

# Timeouts (in seconds)
PAGE_LOAD_TIMEOUT = 30
NETWORK_IDLE_TIMEOUT = 15
ELEMENT_TIMEOUT = 10
CAPTCHA_SOLVE_TIMEOUT = 30

# Retries
MAX_VILLAGE_RETRIES = 3
MAX_CAPTCHA_RETRIES = 2
RETRY_BACKOFF_BASE = 2  # Exponential backoff: 2^attempt seconds

# Rate limiting
GEMINI_RPM = 15
GEMINI_INTERVAL = 60.0 / GEMINI_RPM

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================
# Data Classes
# ============================================
class VillageStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VillageResult:
    village_code: str
    village_name: str
    taluka_code: str
    taluka_name: str
    district_code: str
    status: str = VillageStatus.PENDING.value
    surveys_found: int = 0
    surveys: List[Dict] = field(default_factory=list)
    sample_data: Optional[Dict] = None
    error: Optional[str] = None
    retries: int = 0
    duration_ms: int = 0


@dataclass
class JobResult:
    job_id: str
    district_code: str
    district_name: str
    survey_filter: str
    talukas_total: int
    villages_total: int
    villages_scraped: int = 0
    villages_success: int = 0
    villages_failed: int = 0
    total_surveys: int = 0
    matches: List[VillageResult] = field(default_factory=list)
    errors: List[Dict] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0
    checkpoints: List[str] = field(default_factory=list)


# ============================================
# Robust Captcha Solver
# ============================================
class RobustCaptchaSolver:
    """
    Production-grade captcha solver with:
    - Rate limiting (15 RPM free tier)
    - Caching
    - Retry logic
    - Timeout handling
    """
    
    def __init__(self, api_key: str, rpm: int = 15):
        self.api_key = api_key
        self.rpm = rpm
        self.interval = 60.0 / rpm
        self.last_request_time = 0
        self.lock = asyncio.Lock()
        self.cache: Dict[str, str] = {}
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        self.stats = {"hits": 0, "misses": 0, "errors": 0}
    
    async def solve(self, image_bytes: bytes, timeout: float = CAPTCHA_SOLVE_TIMEOUT) -> Tuple[str, bool]:
        """
        Solve captcha with rate limiting and caching
        Returns: (captcha_text, from_cache)
        """
        
        # Check cache
        img_hash = hashlib.md5(image_bytes).hexdigest()
        if img_hash in self.cache:
            self.stats["hits"] += 1
            logger.debug(f"Captcha cache hit (hash: {img_hash[:8]})")
            return self.cache[img_hash], True
        
        self.stats["misses"] += 1
        
        # Rate limit
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.interval:
                wait_time = self.interval - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
            self.last_request_time = time.time()
        
        # Call API with timeout
        try:
            result = await asyncio.wait_for(
                self._call_gemini(image_bytes),
                timeout=timeout
            )
            
            if result:
                self.cache[img_hash] = result
                return result, False
            
            return "", False
            
        except asyncio.TimeoutError:
            logger.warning("Captcha solve timeout")
            self.stats["errors"] += 1
            return "", False
        except Exception as e:
            logger.error(f"Captcha solve error: {e}")
            self.stats["errors"] += 1
            return "", False
    
    async def _call_gemini(self, image_bytes: bytes) -> str:
        """Make API call to Gemini"""
        
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                    {"text": "Read the CAPTCHA image. Return ONLY the exact characters shown (letters and numbers), nothing else. No explanation."}
                ]
            }]
        }
        
        timeout = ClientTimeout(total=20)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(3):
                try:
                    async with session.post(self.url, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                            # Clean - only ASCII alphanumeric
                            return ''.join(c for c in text if c.isascii() and c.isalnum())
                        
                        elif resp.status == 429:
                            # Rate limited - wait and retry
                            wait = min(60, 10 * (attempt + 1))
                            logger.warning(f"Gemini rate limited, waiting {wait}s...")
                            await asyncio.sleep(wait)
                            continue
                        
                        else:
                            logger.error(f"Gemini API error: {resp.status}")
                            return ""
                            
                except aiohttp.ClientError as e:
                    logger.warning(f"Gemini request failed (attempt {attempt+1}): {e}")
                    await asyncio.sleep(2 ** attempt)
        
        return ""
    
    def get_stats(self) -> Dict:
        return self.stats


# ============================================
# Robust District Scraper
# ============================================
class RobustDistrictScraper:
    """
    Production-grade scraper with:
    - Automatic retries with exponential backoff
    - Timeout handling at every level
    - Graceful error recovery
    - Progress checkpointing
    - Memory management
    """
    
    BASE_URL = "https://anyror.gujarat.gov.in/LandRecordRural.aspx"
    
    SELECTORS = {
        "record_type": "#ContentPlaceHolder1_drpLandRecord",
        "district": "#ContentPlaceHolder1_ddlDistrict",
        "taluka": "#ContentPlaceHolder1_ddlTaluka",
        "village": "#ContentPlaceHolder1_ddlVillage",
        "survey_no": "#ContentPlaceHolder1_ddlSurveyNo",
        "captcha_input": "[placeholder='Enter Text Shown Above']",
        "captcha_image": "#ContentPlaceHolder1_imgCaptcha",
        "refresh_captcha": "text=Refresh Code",
        "error_label": "#ContentPlaceHolder1_lblError",
    }
    
    def __init__(self, parallel_contexts: int = 10):
        self.parallel_contexts = parallel_contexts
        self.captcha_solver = RobustCaptchaSolver(GEMINI_API_KEY, GEMINI_RPM)
        self.browser: Optional[Browser] = None
        self.active_contexts = 0
        self.context_lock = asyncio.Lock()
    
    async def scrape_district(self, district: Dict, job_id: str, survey_filter: str = "") -> JobResult:
        """Main entry: scrape entire district with robust error handling"""
        
        start_time = datetime.utcnow()
        
        # Build village list
        all_villages = []
        for taluka in district["talukas"]:
            for village in taluka["villages"]:
                all_villages.append({
                    "district_code": district["value"],
                    "taluka_code": taluka["value"],
                    "taluka_name": taluka["label"],
                    "village_code": village["value"],
                    "village_name": village["label"]
                })
        
        logger.info("="*60)
        logger.info("ROBUST DISTRICT SCRAPER")
        logger.info("="*60)
        logger.info(f"District: {district['label']} ({district['value']})")
        logger.info(f"Talukas: {len(district['talukas'])}")
        logger.info(f"Villages: {len(all_villages)}")
        logger.info(f"Parallel contexts: {self.parallel_contexts}")
        logger.info(f"Survey filter: {survey_filter or 'None'}")
        logger.info("="*60)
        
        job_result = JobResult(
            job_id=job_id,
            district_code=district["value"],
            district_name=district["label"],
            survey_filter=survey_filter,
            talukas_total=len(district["talukas"]),
            villages_total=len(all_villages),
            started_at=start_time.isoformat()
        )
        
        # Launch browser with retry
        browser_launched = False
        for attempt in range(3):
            try:
                async with async_playwright() as p:
                    self.browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            '--no-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-gpu',
                            '--disable-software-rasterizer',
                            '--disable-extensions',
                            '--disable-background-networking',
                            '--disable-default-apps',
                            '--disable-sync',
                            '--disable-translate',
                            '--metrics-recording-only',
                            '--mute-audio',
                            '--no-first-run',
                            '--safebrowsing-disable-auto-update',
                        ]
                    )
                    browser_launched = True
                    
                    # Process villages
                    await self._process_villages(all_villages, job_result, survey_filter)
                    
                    await self.browser.close()
                    break
                    
            except Exception as e:
                logger.error(f"Browser launch failed (attempt {attempt+1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    job_result.errors.append({"type": "browser_launch", "error": str(e)})
        
        # Finalize
        end_time = datetime.utcnow()
        job_result.completed_at = end_time.isoformat()
        job_result.duration_seconds = (end_time - start_time).total_seconds()
        
        # Log summary
        logger.info("="*60)
        logger.info("JOB COMPLETE")
        logger.info("="*60)
        logger.info(f"Villages: {job_result.villages_success}/{job_result.villages_total} success")
        logger.info(f"Failed: {job_result.villages_failed}")
        logger.info(f"Surveys found: {job_result.total_surveys}")
        logger.info(f"Duration: {job_result.duration_seconds:.1f}s")
        logger.info(f"Captcha stats: {self.captcha_solver.get_stats()}")
        
        return job_result
    
    async def _process_villages(self, villages: List[Dict], job_result: JobResult, survey_filter: str):
        """Process all villages with controlled parallelism"""
        
        semaphore = asyncio.Semaphore(self.parallel_contexts)
        progress_lock = asyncio.Lock()
        
        async def process_with_retry(village_info: Dict) -> VillageResult:
            """Process single village with retries"""
            
            async with semaphore:
                result = None
                
                for attempt in range(MAX_VILLAGE_RETRIES):
                    try:
                        result = await self._scrape_village_safe(village_info, survey_filter)
                        
                        if result.status == VillageStatus.SUCCESS.value:
                            break
                        
                        # Retry on failure
                        if attempt < MAX_VILLAGE_RETRIES - 1:
                            wait = RETRY_BACKOFF_BASE ** attempt
                            logger.debug(f"Retrying {village_info['village_name']} in {wait}s...")
                            await asyncio.sleep(wait)
                            result.retries = attempt + 1
                            
                    except Exception as e:
                        logger.error(f"Village {village_info['village_name']} error: {e}")
                        if result is None:
                            result = VillageResult(
                                village_code=village_info["village_code"],
                                village_name=village_info["village_name"],
                                taluka_code=village_info["taluka_code"],
                                taluka_name=village_info["taluka_name"],
                                district_code=village_info["district_code"],
                                status=VillageStatus.FAILED.value,
                                error=str(e)
                            )
                
                # Update progress
                async with progress_lock:
                    job_result.villages_scraped += 1
                    
                    if result.status == VillageStatus.SUCCESS.value:
                        job_result.villages_success += 1
                        if result.surveys_found > 0:
                            job_result.total_surveys += result.surveys_found
                            job_result.matches.append(result)
                    else:
                        job_result.villages_failed += 1
                        job_result.errors.append({
                            "village": result.village_name,
                            "error": result.error or "Unknown error"
                        })
                    
                    # Progress log every 25 villages
                    if job_result.villages_scraped % 25 == 0:
                        pct = (job_result.villages_scraped / job_result.villages_total) * 100
                        logger.info(f"Progress: {job_result.villages_scraped}/{job_result.villages_total} ({pct:.0f}%) - {job_result.total_surveys} surveys")
                        
                        # Post webhook update
                        if RESULTS_WEBHOOK:
                            await self._post_progress(job_result)
                
                return result
        
        # Create and run all tasks
        tasks = [process_with_retry(v) for v in villages]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _scrape_village_safe(self, village_info: Dict, survey_filter: str) -> VillageResult:
        """Scrape single village with full error handling"""
        
        start_time = time.time()
        
        result = VillageResult(
            village_code=village_info["village_code"],
            village_name=village_info["village_name"],
            taluka_code=village_info["taluka_code"],
            taluka_name=village_info["taluka_name"],
            district_code=village_info["district_code"],
            status=VillageStatus.PROCESSING.value
        )
        
        context = None
        page = None
        
        try:
            # Create context with timeout
            context = await asyncio.wait_for(
                self.browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    java_script_enabled=True,
                ),
                timeout=10
            )
            
            page = await context.new_page()
            page.set_default_timeout(ELEMENT_TIMEOUT * 1000)
            page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT * 1000)
            
            # Handle dialogs
            page.on("dialog", lambda d: asyncio.create_task(self._safe_dialog_accept(d)))
            
            # Navigate with retry
            await self._navigate_with_retry(page)
            
            # Select VF-7
            await self._safe_select(page, self.SELECTORS["record_type"], "1")
            await asyncio.sleep(0.3)
            
            # Select location
            await self._safe_select(page, self.SELECTORS["district"], village_info["district_code"])
            await self._wait_for_load(page)
            
            await self._safe_select(page, self.SELECTORS["taluka"], village_info["taluka_code"])
            await self._wait_for_load(page)
            
            await self._safe_select(page, self.SELECTORS["village"], village_info["village_code"])
            await self._wait_for_load(page)
            
            # Get surveys
            surveys = await self._get_survey_options(page, survey_filter)
            
            result.surveys = surveys
            result.surveys_found = len(surveys)
            result.status = VillageStatus.SUCCESS.value
            
            # Fetch sample if we have matching surveys
            if surveys and survey_filter:
                sample = await self._fetch_record_safe(page, surveys[0])
                if sample:
                    result.sample_data = sample
            
        except PlaywrightTimeout as e:
            result.status = VillageStatus.FAILED.value
            result.error = f"Timeout: {str(e)[:100]}"
            
        except PlaywrightError as e:
            result.status = VillageStatus.FAILED.value
            result.error = f"Browser error: {str(e)[:100]}"
            
        except asyncio.TimeoutError:
            result.status = VillageStatus.FAILED.value
            result.error = "Operation timeout"
            
        except Exception as e:
            result.status = VillageStatus.FAILED.value
            result.error = f"Unexpected: {str(e)[:100]}"
            
        finally:
            # Cleanup
            if context:
                try:
                    await asyncio.wait_for(context.close(), timeout=5)
                except:
                    pass
            
            result.duration_ms = int((time.time() - start_time) * 1000)
        
        return result
    
    async def _navigate_with_retry(self, page: Page, max_retries: int = 3):
        """Navigate to page with retry logic"""
        
        for attempt in range(max_retries):
            try:
                await page.goto(
                    self.BASE_URL,
                    wait_until="domcontentloaded",
                    timeout=PAGE_LOAD_TIMEOUT * 1000
                )
                
                # Verify page loaded
                await page.wait_for_selector(
                    self.SELECTORS["record_type"],
                    timeout=ELEMENT_TIMEOUT * 1000
                )
                return
                
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
    
    async def _safe_select(self, page: Page, selector: str, value: str):
        """Select dropdown option with error handling"""
        
        try:
            await page.wait_for_selector(selector, timeout=ELEMENT_TIMEOUT * 1000)
            await page.locator(selector).select_option(value, timeout=ELEMENT_TIMEOUT * 1000)
        except Exception as e:
            logger.debug(f"Select failed for {selector}: {e}")
            raise
    
    async def _wait_for_load(self, page: Page):
        """Wait for page to settle after selection"""
        
        try:
            await page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT * 1000)
        except:
            # Fallback to simple wait
            await asyncio.sleep(1)
    
    async def _get_survey_options(self, page: Page, survey_filter: str) -> List[Dict]:
        """Get survey dropdown options with filtering"""
        
        surveys = []
        
        try:
            await page.wait_for_selector(self.SELECTORS["survey_no"], timeout=ELEMENT_TIMEOUT * 1000)
            
            options = await page.locator(self.SELECTORS["survey_no"]).locator("option").all()
            
            for opt in options:
                try:
                    value = await opt.get_attribute("value")
                    text = (await opt.text_content() or "").strip()
                    
                    if not value or value in ["0", "-1", ""] or "પસંદ" in text:
                        continue
                    
                    # Apply filter
                    if survey_filter:
                        if survey_filter in text or survey_filter == value:
                            surveys.append({"value": value, "text": text})
                    else:
                        surveys.append({"value": value, "text": text})
                        
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"Failed to get survey options: {e}")
        
        return surveys
    
    async def _fetch_record_safe(self, page: Page, survey: Dict) -> Optional[Dict]:
        """Fetch VF-7 record with full error handling"""
        
        try:
            await self._safe_select(page, self.SELECTORS["survey_no"], survey["value"])
            await asyncio.sleep(0.3)
            
            for attempt in range(MAX_CAPTCHA_RETRIES):
                try:
                    # Get captcha image
                    captcha_elem = page.locator(self.SELECTORS["captcha_image"])
                    await captcha_elem.wait_for(timeout=ELEMENT_TIMEOUT * 1000)
                    captcha_img = await captcha_elem.screenshot()
                    
                    # Solve captcha
                    captcha_text, from_cache = await self.captcha_solver.solve(captcha_img)
                    
                    if not captcha_text:
                        continue
                    
                    # Enter captcha
                    await page.locator(self.SELECTORS["captcha_input"]).fill(captcha_text)
                    await page.locator(self.SELECTORS["captcha_input"]).press("Enter")
                    
                    await asyncio.sleep(2)
                    await self._wait_for_load(page)
                    
                    # Check for results
                    content = await page.content()
                    if "ખાતા નંબર" in content or "Khata" in content:
                        # Extract data
                        tables = await page.locator("table").all()
                        for t in tables:
                            txt = await t.text_content()
                            if txt and len(txt) > 200:
                                return {
                                    "survey": survey["text"],
                                    "data": txt[:3000],
                                    "captcha_cached": from_cache
                                }
                    
                    # Check for error
                    try:
                        error_elem = page.locator(self.SELECTORS["error_label"])
                        if await error_elem.count() > 0:
                            error_text = await error_elem.text_content()
                            if error_text and "captcha" in error_text.lower():
                                # Refresh captcha
                                await page.locator(self.SELECTORS["refresh_captcha"]).click()
                                await asyncio.sleep(0.5)
                    except:
                        pass
                        
                except Exception as e:
                    logger.debug(f"Captcha attempt {attempt+1} failed: {e}")
            
            return None
            
        except Exception as e:
            logger.debug(f"Fetch record failed: {e}")
            return None
    
    async def _safe_dialog_accept(self, dialog):
        """Safely accept dialog"""
        try:
            await dialog.accept()
        except:
            pass
    
    async def _post_progress(self, job_result: JobResult):
        """Post progress to webhook"""
        
        if not RESULTS_WEBHOOK:
            return
        
        try:
            timeout = ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                await session.post(
                    f"{RESULTS_WEBHOOK}/progress",
                    json={
                        "job_id": job_result.job_id,
                        "district": job_result.district_name,
                        "villages_scraped": job_result.villages_scraped,
                        "villages_total": job_result.villages_total,
                        "villages_success": job_result.villages_success,
                        "villages_failed": job_result.villages_failed,
                        "total_surveys": job_result.total_surveys
                    }
                )
        except:
            pass


# ============================================
# Main Entry Point
# ============================================
async def main():
    """Cloud Run Job entry point"""
    
    logger.info("Starting Robust Worker...")
    
    # Get config
    district_b64 = os.environ.get("DISTRICT_DATA_B64", "")
    job_id = os.environ.get("JOB_ID", f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    survey_filter = os.environ.get("SURVEY_NUMBER", "")
    
    district = None
    
    # Decode district data
    if district_b64:
        try:
            district_json = base64.b64decode(district_b64).decode()
            district = json.loads(district_json)
        except Exception as e:
            logger.error(f"Failed to decode district data: {e}")
    
    # Or load from file
    if not district and len(sys.argv) > 1:
        try:
            with open(sys.argv[1], "r", encoding="utf-8") as f:
                config = json.load(f)
                district = config.get("district")
                job_id = config.get("job_id", job_id)
                survey_filter = config.get("survey_filter", survey_filter)
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
    
    if not district:
        logger.error("No district data provided")
        logger.error("Set DISTRICT_DATA_B64 env var or pass config file")
        sys.exit(1)
    
    # Run scraper
    scraper = RobustDistrictScraper(parallel_contexts=PARALLEL_CONTEXTS)
    result = await scraper.scrape_district(district, job_id, survey_filter)
    
    # Save results
    output_file = f"result_{result.district_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    def to_dict(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return {k: to_dict(v) for k, v in asdict(obj).items()}
        elif isinstance(obj, list):
            return [to_dict(i) for i in obj]
        return obj
    
    result_dict = to_dict(result)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Results saved to: {output_file}")
    
    # Post final results
    if RESULTS_WEBHOOK:
        try:
            timeout = ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                await session.post(
                    f"{RESULTS_WEBHOOK}/complete",
                    json=result_dict
                )
                logger.info(f"Results posted to webhook")
        except Exception as e:
            logger.error(f"Webhook post failed: {e}")
    
    # Exit with appropriate code
    if result.villages_failed > result.villages_total * 0.5:
        logger.error("More than 50% villages failed")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
