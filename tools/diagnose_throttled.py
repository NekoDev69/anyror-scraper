#!/usr/bin/env python3
"""
Anti-Rate-Limit Diagnostic Test
- Staggered worker starts
- Random delays between requests
- Lower concurrency (2 workers)
- Request throttling
"""

import json
import asyncio
import os
import random
from datetime import datetime
from playwright.async_api import async_playwright
from captcha_solver import CaptchaSolver
from vf7_extractor import VF7Extractor

DEBUG_DIR = "debug_output"
os.makedirs(DEBUG_DIR, exist_ok=True)

class ThrottledDiagnosticScraper:
    BASE_URL = "https://anyror.gujarat.gov.in/LandRecordRural.aspx"
    
    SELECTORS = {
        "record_type": "#ContentPlaceHolder1_drpLandRecord",
        "district": "#ContentPlaceHolder1_drpDistrict",
        "taluka": "#ContentPlaceHolder1_drpTaluka",
        "village": "#ContentPlaceHolder1_drpVillage",
        "survey_no": "#ContentPlaceHolder1_drpSurveyNo",
        "captcha_image": "#ContentPlaceHolder1_imgCaptcha",
        "captcha_input": "#ContentPlaceHolder1_txtCode",
        "submit_btn": "#ContentPlaceHolder1_btnSubmit",
    }
    
    def __init__(self, num_workers=2, headless=False):
        self.num_workers = num_workers
        self.headless = headless
        self.captcha_solver = CaptchaSolver()
        self.extractor = VF7Extractor()
        self.results = []
        self.request_lock = asyncio.Lock()
        self.last_request_time = 0
        
    async def _throttle(self):
        """Enforce minimum delay between requests"""
        async with self.request_lock:
            now = asyncio.get_event_loop().time()
            time_since_last = now - self.last_request_time
            
            # Minimum 1.5 second between ANY requests
            if time_since_last < 1.5:
                await asyncio.sleep(1.5 - time_since_last)
            
            # Add random jitter (0.5-1.5 seconds)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            self.last_request_time = asyncio.get_event_loop().time()
    
    async def _wait_for_options(self, page, selector, timeout=20000):
        """Wait for dropdown to have valid options"""
        try:
            await page.wait_for_function(
                f"""() => {{
                    const select = document.querySelector('{selector}');
                    return select && select.options.length > 1;
                }}""",
                timeout=timeout
            )
            return True
        except:
            return False
    
    async def _get_options(self, page, selector):
        """Get dropdown options"""
        options = await page.locator(selector).locator("option").all()
        result = []
        for opt in options:
            value = await opt.get_attribute("value")
            text = await opt.inner_text()
            if value and value.strip():
                result.append({"value": value, "text": text})
        return result
    
    async def _get_captcha_image(self, page):
        """Get captcha image bytes"""
        try:
            img_element = page.locator(self.SELECTORS["captcha_image"])
            src = await img_element.get_attribute("src")
            
            if src and src.startswith("data:image"):
                import base64
                base64_data = src.split(",")[1]
                return base64.b64decode(base64_data)
            else:
                screenshot = await img_element.screenshot()
                return screenshot
        except Exception as e:
            print(f"[ERROR] Failed to get captcha: {e}")
            return None
    
    async def scrape_village_throttled(self, context, worker_id, district_code, taluka_code, 
                                      village_code, village_name):
        """Scrape with throttling and detailed debugging"""
        
        debug_info = {
            "worker_id": worker_id,
            "village_code": village_code,
            "village_name": village_name,
            "timestamp": datetime.now().isoformat(),
            "steps": []
        }
        
        try:
            # Throttle before creating page
            await self._throttle()
            
            page = await context.new_page()
            debug_info["steps"].append("✓ Page created")
            
            # Navigate with throttling
            await self._throttle()
            await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(random.uniform(1, 2))  # Random delay
            debug_info["steps"].append("✓ Navigated")
            
            # Select VF-7
            await page.locator(self.SELECTORS["record_type"]).select_option("1")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(random.uniform(0.8, 1.5))
            debug_info["steps"].append("✓ VF-7 selected")
            
            # Select district (throttled)
            await self._throttle()
            await page.locator(self.SELECTORS["district"]).select_option(district_code)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(random.uniform(0.8, 1.5))
            debug_info["steps"].append(f"✓ District {district_code}")
            
            # Select taluka
            await page.locator(self.SELECTORS["taluka"]).select_option(taluka_code)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(random.uniform(0.8, 1.5))
            debug_info["steps"].append(f"✓ Taluka {taluka_code}")
            
            # Select village
            await self._wait_for_options(page, self.SELECTORS["village"])
            await page.locator(self.SELECTORS["village"]).select_option(village_code)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(random.uniform(1, 2))
            debug_info["steps"].append(f"✓ Village {village_code}")
            
            # Get survey options
            await self._wait_for_options(page, self.SELECTORS["survey_no"])
            survey_options = await self._get_options(page, self.SELECTORS["survey_no"])
            
            debug_info["survey_options"] = survey_options
            debug_info["survey_count"] = len(survey_options)
            debug_info["steps"].append(f"✓ {len(survey_options)} surveys found")
            
            if not survey_options:
                await page.close()
                return {
                    "success": False,
                    "village_code": village_code,
                    "village_name": village_name,
                    "error": "No surveys found in dropdown",
                    "debug_info": debug_info
                }
            
            # Select first survey
            first_survey = survey_options[0]
            debug_info["selected_survey"] = first_survey
            
            await page.locator(self.SELECTORS["survey_no"]).select_option(first_survey["value"])
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(random.uniform(1.5, 2.5))
            debug_info["steps"].append(f"✓ Survey: {first_survey['text']}")
            
            # Solve captcha
            captcha_img = await self._get_captcha_image(page)
            if not captcha_img:
                await page.close()
                return {
                    "success": False,
                    "village_code": village_code,
                    "village_name": village_name,
                    "error": "Captcha image failed",
                    "debug_info": debug_info
                }
            
            captcha_text = self.captcha_solver.solve(captcha_img)
            debug_info["captcha_solved"] = captcha_text
            
            if not captcha_text:
                await page.close()
                return {
                    "success": False,
                    "village_code": village_code,
                    "village_name": village_name,
                    "error": "Captcha solve failed",
                    "debug_info": debug_info
                }
            
            debug_info["steps"].append(f"✓ Captcha: {captcha_text}")
            
            # Submit
            captcha_input = page.locator(self.SELECTORS["captcha_input"])
            await captcha_input.fill(captcha_text)
            
            submit_btn = page.locator(self.SELECTORS["submit_btn"])
            await submit_btn.click()
            
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(2)
            debug_info["steps"].append("✓ Submitted")
            
            # Screenshot
            screenshot_path = f"{DEBUG_DIR}/w{worker_id}_{village_code}_{datetime.now().strftime('%H%M%S')}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            debug_info["screenshot"] = screenshot_path
            
            # Get HTML
            html_content = await page.content()
            
            # Check tables
            tables = await page.locator("table").all()
            debug_info["table_count"] = len(tables)
            
            if tables:
                for i, table in enumerate(tables):
                    rows = await table.locator("tr").all()
                    debug_info[f"table_{i}_rows"] = len(rows)
                    
                    # Check if table has meaningful data (not just headers)
                    if len(rows) > 1:  # More than just header
                        cells = await table.locator("td").all()
                        if cells:
                            cell_texts = []
                            for cell in cells[:5]:  # First 5 cells
                                text = await cell.inner_text()
                                cell_texts.append(text.strip())
                            debug_info[f"table_{i}_sample_cells"] = cell_texts
            
            # Extract
            data = self.extractor.extract(html_content)
            
            await page.close()
            
            if data["success"]:
                debug_info["steps"].append("✓ Extracted")
                return {
                    "success": True,
                    "village_code": village_code,
                    "village_name": village_name,
                    "data": data,
                    "debug_info": debug_info
                }
            else:
                # Save HTML for inspection
                html_path = f"{DEBUG_DIR}/w{worker_id}_{village_code}_page.html"
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                debug_info["html_saved"] = html_path
                debug_info["extraction_error"] = data.get("error")
                
                return {
                    "success": False,
                    "village_code": village_code,
                    "village_name": village_name,
                    "error": data.get("error"),
                    "debug_info": debug_info
                }
                
        except Exception as e:
            import traceback
            debug_info["exception"] = str(e)
            debug_info["traceback"] = traceback.format_exc()
            
            return {
                "success": False,
                "village_code": village_code,
                "village_name": village_name,
                "error": f"Exception: {e}",
                "debug_info": debug_info
            }
    
    async def run_test(self, district_code, district_name, talukas):
        """Run throttled test"""
        
        print(f"\n{'='*60}")
        print(f"🐌 THROTTLED DIAGNOSTIC TEST (Anti-Rate-Limit)")
        print(f"{'='*60}")
        print(f"District: {district_name}")
        print(f"Workers: {self.num_workers}")
        print(f"Throttling: 1.5s min + random jitter")
        print(f"Staggered starts: 3s delay between workers")
        print(f"{'='*60}\n")
        
        villages = []
        for taluka in talukas:
            for village in taluka['villages']:
                villages.append({
                    'district_code': district_code,
                    'taluka_code': taluka['value'],
                    'village_code': village['value'],
                    'village_name': village['label']
                })
        
        print(f"Total villages: {len(villages)}\n")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            print(f"[BROWSER] Launched\n")
            
            # Create contexts
            contexts = []
            for i in range(self.num_workers):
                context = await browser.new_context()
                contexts.append(context)
                print(f"[WORKER-{i+1}] Context created")
            
            print(f"\n{'='*60}\n")
            
            queue = asyncio.Queue()
            for v in villages:
                await queue.put(v)
            
            async def worker(context, worker_id, start_delay):
                # Stagger starts to avoid simultaneous initial requests
                print(f"[W{worker_id:02d}] Waiting {start_delay}s before starting...")
                await asyncio.sleep(start_delay)
                print(f"[W{worker_id:02d}] Starting!")
                
                while not queue.empty():
                    try:
                        village = await queue.get()
                        print(f"[W{worker_id:02d}] Processing: {village['village_name']}")
                        
                        result = await self.scrape_village_throttled(
                            context, worker_id,
                            village['district_code'],
                            village['taluka_code'],
                            village['village_code'],
                            village['village_name']
                        )
                        
                        self.results.append(result)
                        
                        status = "✓" if result['success'] else "✗"
                        error_msg = f" - {result.get('error')}" if not result['success'] else ""
                        print(f"[W{worker_id:02d}] {status} {village['village_name']}{error_msg}")
                        
                        queue.task_done()
                    except Exception as e:
                        print(f"[W{worker_id:02d}] Error: {e}")
            
            # Start workers with staggered delays
            tasks = []
            for i in range(self.num_workers):
                start_delay = i * 3  # 3 second stagger
                tasks.append(worker(contexts[i], i+1, start_delay))
            
            await asyncio.gather(*tasks)
            
            for context in contexts:
                await context.close()
            await browser.close()
        
        # Results
        print(f"\n{'='*60}")
        print("RESULTS")
        print(f"{'='*60}\n")
        
        successful = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]
        
        print(f"Total: {len(self.results)}")
        print(f"✅ Successful: {len(successful)}")
        print(f"❌ Failed: {len(failed)}")
        print(f"Success Rate: {len(successful)/len(self.results)*100:.1f}%\n")
        
        if failed:
            print(f"❌ FAILURES:\n")
            for r in failed:
                print(f"  {r['village_name']} ({r['village_code']})")
                print(f"    Error: {r['error']}")
                debug = r.get('debug_info', {})
                if 'survey_count' in debug:
                    print(f"    Surveys: {debug['survey_count']}")
                if 'selected_survey' in debug:
                    print(f"    Selected: {debug['selected_survey']}")
                if 'screenshot' in debug:
                    print(f"    📸 {debug['screenshot']}")
                print()
        
        # Save report
        report_path = f"{DEBUG_DIR}/throttled_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Report: {report_path}\n")


async def main():
    with open('gujarat-anyror-complete.json', 'r', encoding='utf-8') as f:
        zone_data = json.load(f)
    
    district = zone_data['districts'][0]
    
    # Test with fewer villages first
    test_talukas = []
    for i, taluka in enumerate(district['talukas'][:2]):  # Only 2 talukas
        test_talukas.append({
            'value': taluka['value'],
            'label': taluka['label'],
            'villages': taluka['villages'][:3]  # 3 per taluka = 6 total
        })
    
    # Use only 2 workers with throttling
    scraper = ThrottledDiagnosticScraper(num_workers=2, headless=False)
    await scraper.run_test(
        district_code=district['value'],
        district_name=district['label'],
        talukas=test_talukas
    )


if __name__ == "__main__":
    asyncio.run(main())
