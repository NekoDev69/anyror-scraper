"""
VM Bulk Scraper - Parallel Version
5 browser contexts × 10 tabs each = 50 parallel scrapers
"""

import os
import sys
import json
import time
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from captcha_solver import CaptchaSolver

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")
NUM_CONTEXTS = int(os.environ.get("NUM_CONTEXTS", 1))
TABS_PER_CONTEXT = int(os.environ.get("TABS_PER_CONTEXT", 5))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or "AIzaSyDBkyScEIGGUm2N1JwFrW32CCoAOWTbhXw"

os.makedirs(f"{OUTPUT_DIR}/raw", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/structured", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/reports", exist_ok=True)

stats = {"total": 0, "done": 0, "success": 0}
stats_lock = asyncio.Lock()

SELECTORS = {
    "record_type": "#ContentPlaceHolder1_drpLandRecord",
    "district": "#ContentPlaceHolder1_ddlDistrict",
    "taluka": "#ContentPlaceHolder1_ddlTaluka",
    "village": "#ContentPlaceHolder1_ddlVillage",
    "survey_no": "#ContentPlaceHolder1_ddlSurveyNo",
    "captcha_input": "[placeholder='Enter Text Shown Above']",
    "captcha_image": "img[id*='captcha']",
}


def log(msg: str):
    print(f"LOG:{msg}", flush=True)


def progress():
    print(f"PROGRESS:{stats['total']}:{stats['done']}:{stats['success']}", flush=True)


class ParallelScraper:
    def __init__(self, district_code: str, taluka_code: str, villages: list, district_label: str, taluka_label: str):
        self.district_code = district_code
        self.taluka_code = taluka_code
        self.villages = villages
        self.district_label = district_label
        self.taluka_label = taluka_label
        self.captcha_solver = CaptchaSolver(GEMINI_API_KEY)
        self.browser = None
        self.contexts = []
    
    async def start_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        log(f"Browser started - {NUM_CONTEXTS} contexts × {TABS_PER_CONTEXT} tabs = {NUM_CONTEXTS * TABS_PER_CONTEXT} parallel")
    
    async def close(self):
        for ctx in self.contexts:
            try:
                await ctx.close()
            except:
                pass
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def setup_page(self, page):
        """Setup a page with district/taluka selected"""
        await page.goto("https://anyror.gujarat.gov.in/LandRecordRural.aspx")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(0.5)
        
        # Select VF-7
        await page.locator(SELECTORS["record_type"]).select_option("1")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(0.5)
        
        # Select district
        await page.locator(SELECTORS["district"]).select_option(self.district_code)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(0.5)
        
        # Select taluka
        await page.locator(SELECTORS["taluka"]).select_option(self.taluka_code)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(0.5)
    
    async def scrape_village(self, page, village, ctx_id, tab_id):
        """Scrape a single village using existing page session"""
        village_code = village["value"]
        village_name = village["label"]
        
        try:
            # Select village
            await page.locator(SELECTORS["village"]).select_option(village_code)
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(1)  # Wait for survey dropdown to populate via AJAX
            
            # Get surveys - retry if empty (AJAX might be slow)
            surveys = []
            for retry in range(3):
                for opt in await page.locator(SELECTORS["survey_no"]).locator("option").all():
                    val = await opt.get_attribute("value")
                    txt = await opt.text_content()
                    if val and val not in ["0", "-1", ""] and "પસંદ" not in txt and "select" not in txt.lower():
                        surveys.append({"value": val, "text": txt.strip()})
                if surveys:
                    break
                await asyncio.sleep(1)  # Wait more if empty
            
            if not surveys:
                return {"village_code": village_code, "village_name": village_name, "success": False, "reason": "no_surveys"}
            
            # Select first survey
            survey = surveys[0]
            await page.locator(SELECTORS["survey_no"]).select_option(survey["value"])
            await asyncio.sleep(0.5)
            
            # Try captcha up to 5 times with better error handling
            for attempt in range(5):
                try:
                    # Clear any previous captcha input
                    await page.locator(SELECTORS["captcha_input"]).fill("")
                    await asyncio.sleep(0.3)
                    
                    # Get fresh captcha image
                    img = page.locator(SELECTORS["captcha_image"])
                    if await img.count() > 0:
                        img_bytes = await img.screenshot()
                        captcha_text = self.captcha_solver.solve(img_bytes)
                        
                        if captcha_text and len(captcha_text) >= 5:
                            await page.locator(SELECTORS["captcha_input"]).fill(captcha_text)
                            await asyncio.sleep(0.3)
                            await page.locator(SELECTORS["captcha_input"]).press("Enter")
                            
                            # Wait longer for results to load
                            await asyncio.sleep(3)
                            try:
                                await page.wait_for_load_state("networkidle", timeout=20000)
                            except:
                                pass
                            await asyncio.sleep(1)  # Extra wait for AJAX
                            
                            # Check for results - look for specific result indicators
                            has_data = False
                            table_data = []
                            
                            # Method 1: Check for result tables with actual data
                            tables = await page.locator("table").all()
                            for table in tables:
                                try:
                                    text = await table.text_content()
                                    # Look for Gujarati text or specific keywords that indicate real data
                                    if len(text.strip()) > 300 and ("ક્ષેત્રફળ" in text or "માલિક" in text or "હક્ક" in text or "જમીન" in text):
                                        has_data = True
                                        table_data.append(text.strip())
                                except:
                                    continue
                            
                            # Method 2: Check for result panel/div
                            if not has_data:
                                try:
                                    result_panel = page.locator("#ContentPlaceHolder1_pnlResult, [id*='pnlResult'], [id*='Result']")
                                    if await result_panel.count() > 0:
                                        panel_text = await result_panel.first.text_content()
                                        if len(panel_text.strip()) > 200:
                                            has_data = True
                                            table_data.append(panel_text.strip())
                                except:
                                    pass
                            
                            # Method 3: Check page content for VF-7 specific data
                            if not has_data:
                                try:
                                    page_content = await page.content()
                                    if "VF-7" in page_content or "સર્વે નંબર" in page_content:
                                        # Get all visible text
                                        body_text = await page.locator("body").text_content()
                                        if len(body_text) > 1000 and ("ક્ષેત્રફળ" in body_text or "માલિક" in body_text):
                                            has_data = True
                                            table_data.append(body_text)
                                except:
                                    pass
                            
                            if has_data:
                                # Go back for next village
                                try:
                                    await page.get_by_role("link", name="RURAL LAND RECORD").click()
                                    await page.wait_for_load_state("networkidle", timeout=10000)
                                except:
                                    await self.setup_page(page)
                                
                                return {
                                    "village_code": village_code,
                                    "village_name": village_name,
                                    "survey": survey["text"],
                                    "success": True,
                                    "data": {"tables": table_data}
                                }
                except Exception as e:
                    pass
                
                # Refresh captcha for retry
                if attempt < 4:
                    try:
                        await page.locator("text=Refresh Code").click()
                        await asyncio.sleep(1)
                    except:
                        pass
            
            # Failed after 5 attempts - go back
            try:
                await page.get_by_role("link", name="RURAL LAND RECORD").click()
                await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                await self.setup_page(page)
            
            return {"village_code": village_code, "village_name": village_name, "success": False, "reason": "captcha_failed"}
            
        except Exception as e:
            # Reset page on error
            try:
                await self.setup_page(page)
            except:
                pass
            return {"village_code": village_code, "village_name": village_name, "success": False, "error": str(e)}
    
    async def worker(self, ctx_id: int, tab_id: int, page, village_queue: asyncio.Queue):
        """Worker that processes villages from queue"""
        while True:
            try:
                village = village_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            
            result = await self.scrape_village(page, village, ctx_id, tab_id)
            
            async with stats_lock:
                stats["done"] += 1
                if result.get("success"):
                    stats["success"] += 1
                    log(f"✅ C{ctx_id}T{tab_id} {result['village_name'][:25]} - {result.get('survey', '')}")
                    
                    # Save result
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                    filename = f"{self.district_code}_{self.taluka_code}_{result['village_code']}_{ts}"
                    
                    full_result = {
                        "district": {"value": self.district_code, "label": self.district_label},
                        "taluka": {"value": self.taluka_code, "label": self.taluka_label},
                        "village": {"value": result["village_code"], "label": result["village_name"]},
                        "survey": {"text": result.get("survey")},
                        "data": result.get("data"),
                        "success": True
                    }
                    
                    with open(f"{OUTPUT_DIR}/raw/{filename}.json", 'w', encoding='utf-8') as f:
                        json.dump(full_result, f, ensure_ascii=False, indent=2)
                else:
                    reason = result.get("reason", result.get("error", "unknown"))
                    log(f"❌ C{ctx_id}T{tab_id} {result['village_name'][:25]} - {reason}")
                
                progress()
    
    async def run_context(self, ctx_id: int, village_queue: asyncio.Queue):
        """Run a single context with multiple tabs"""
        context = await self.browser.new_context()
        self.contexts.append(context)
        
        # Create tabs and setup each
        pages = []
        for tab_id in range(TABS_PER_CONTEXT):
            page = await context.new_page()
            await page.set_viewport_size({"width": 1280, "height": 900})
            
            # Handle dialogs
            page.on("dialog", lambda d: asyncio.create_task(d.accept()))
            
            try:
                await self.setup_page(page)
                pages.append((tab_id, page))
                log(f"C{ctx_id}T{tab_id} ready")
            except Exception as e:
                log(f"C{ctx_id}T{tab_id} setup failed: {e}")
        
        # Run workers for all tabs in parallel
        tasks = [self.worker(ctx_id, tab_id, page, village_queue) for tab_id, page in pages]
        await asyncio.gather(*tasks)
    
    async def run(self):
        """Main run - parallel contexts and tabs"""
        await self.start_browser()
        
        # Create village queue
        village_queue = asyncio.Queue()
        for v in self.villages:
            await village_queue.put(v)
        
        log(f"Starting {NUM_CONTEXTS} contexts for {len(self.villages)} villages")
        
        # Run all contexts in parallel
        tasks = [self.run_context(ctx_id, village_queue) for ctx_id in range(NUM_CONTEXTS)]
        await asyncio.gather(*tasks)
        
        await self.close()


async def main():
    global stats
    
    district_code = os.environ.get("DISTRICT_CODE", "")
    taluka_code = os.environ.get("TALUKA_CODE", "")
    
    if not district_code:
        log("ERROR: DISTRICT_CODE not set")
        sys.exit(1)
    
    # Load data
    with open("gujarat-anyror-complete.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    district = next((d for d in data["districts"] if d["value"] == district_code), None)
    if not district:
        log(f"ERROR: District {district_code} not found")
        sys.exit(1)
    
    # Get villages
    villages = []
    taluka_label = ""
    for taluka in district["talukas"]:
        if taluka_code and taluka["value"] != taluka_code:
            continue
        taluka_label = taluka["label"]
        villages.extend(taluka["villages"])
    
    stats["total"] = len(villages)
    progress()
    
    log(f"District: {district['label']}, Taluka: {taluka_label}")
    log(f"Villages: {len(villages)}")
    
    scraper = ParallelScraper(district_code, taluka_code, villages, district["label"], taluka_label)
    
    try:
        await scraper.run()
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    log(f"Done: {stats['success']}/{stats['total']} successful")
    
    # Generate reports
    try:
        from vf7_extractor import VF7Extractor
        from vf7_report import VF7ReportGenerator
        
        extractor = VF7Extractor()
        reporter = VF7ReportGenerator()
        
        raw_files = [f for f in os.listdir(f"{OUTPUT_DIR}/raw") if f.endswith('.json')]
        log(f"Generating {len(raw_files)} reports...")
        
        for filename in raw_files:
            try:
                with open(f"{OUTPUT_DIR}/raw/{filename}", 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                
                structured = extractor.extract_from_scrape_result(raw_data)
                
                with open(f"{OUTPUT_DIR}/structured/{filename}", 'w', encoding='utf-8') as f:
                    json.dump(structured, f, ensure_ascii=False, indent=2)
                
                html = reporter.generate_html(structured)
                with open(f"{OUTPUT_DIR}/reports/{filename.replace('.json', '.html')}", 'w', encoding='utf-8') as f:
                    f.write(html)
            except Exception as e:
                log(f"Report error: {e}")
    except ImportError as e:
        log(f"Report generation skipped: {e}")


if __name__ == "__main__":
    asyncio.run(main())
