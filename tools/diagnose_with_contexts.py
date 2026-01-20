#!/usr/bin/env python3
"""
Enhanced Diagnostic Test - Browser Contexts with Deep Debugging
Uses 5 contexts per browser instead of multiple browsers
Adds detailed logging and screenshots for debugging "No data" cases
"""

import json
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright
from captcha_solver import CaptchaSolver
from vf7_extractor import VF7Extractor

# Create debug output directory
DEBUG_DIR = "debug_output"
os.makedirs(DEBUG_DIR, exist_ok=True)

class EnhancedDiagnosticScraper:
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
    
    def __init__(self, num_contexts=5, headless=False):
        self.num_contexts = num_contexts
        self.headless = headless
        self.captcha_solver = CaptchaSolver()
        self.extractor = VF7Extractor()
        self.results = []
        
    async def _wait_for_options(self, page, selector, timeout=15000):
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
    
    async def scrape_village_debug(self, context, worker_id, district_code, taluka_code, 
                                   village_code, village_name):
        """Scrape a village with extensive debugging"""
        
        debug_info = {
            "worker_id": worker_id,
            "village_code": village_code,
            "village_name": village_name,
            "timestamp": datetime.now().isoformat(),
            "steps": []
        }
        
        try:
            # Create new page in context
            page = await context.new_page()
            
            debug_info["steps"].append("✓ Page created")
            
            # Navigate
            await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(1)
            debug_info["steps"].append("✓ Navigated to portal")
            
            # Select VF-7
            await page.locator(self.SELECTORS["record_type"]).select_option("1")
            await page.wait_for_load_state("networkidle")
            debug_info["steps"].append("✓ Selected VF-7")
            
            # Select district
            await page.locator(self.SELECTORS["district"]).select_option(district_code)
            await page.wait_for_load_state("networkidle")
            debug_info["steps"].append(f"✓ Selected district {district_code}")
            
            # Select taluka
            await page.locator(self.SELECTORS["taluka"]).select_option(taluka_code)
            await page.wait_for_load_state("networkidle")
            debug_info["steps"].append(f"✓ Selected taluka {taluka_code}")
            
            # Select village
            await self._wait_for_options(page, self.SELECTORS["village"])
            await page.locator(self.SELECTORS["village"]).select_option(village_code)
            await page.wait_for_load_state("networkidle")
            debug_info["steps"].append(f"✓ Selected village {village_code}")
            
            # Wait for survey list and get ALL options
            await self._wait_for_options(page, self.SELECTORS["survey_no"])
            survey_options = await self._get_options(page, self.SELECTORS["survey_no"])
            
            debug_info["survey_options"] = survey_options
            debug_info["survey_count"] = len(survey_options)
            debug_info["steps"].append(f"✓ Found {len(survey_options)} survey options")
            
            if not survey_options:
                debug_info["error"] = "No survey numbers available"
                await page.close()
                return {
                    "success": False,
                    "village_code": village_code,
                    "village_name": village_name,
                    "error": "No surveys found",
                    "debug_info": debug_info
                }
            
            # Select first survey
            first_survey = survey_options[0]
            debug_info["selected_survey"] = first_survey
            
            await page.locator(self.SELECTORS["survey_no"]).select_option(first_survey["value"])
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1.5)
            debug_info["steps"].append(f"✓ Selected survey: {first_survey['text']}")
            
            # Solve captcha
            captcha_img = await self._get_captcha_image(page)
            if not captcha_img:
                debug_info["error"] = "Failed to get captcha"
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
            debug_info["steps"].append(f"✓ Captcha solved: {captcha_text}")
            
            if not captcha_text:
                debug_info["error"] = "Captcha solve failed"
                await page.close()
                return {
                    "success": False,
                    "village_code": village_code,
                    "village_name": village_name,
                    "error": "Captcha solve failed",
                    "debug_info": debug_info
                }
            
            # Enter captcha and submit
            captcha_input = page.locator(self.SELECTORS["captcha_input"])
            await captcha_input.fill(captcha_text)
            
            submit_btn = page.locator(self.SELECTORS["submit_btn"])
            await submit_btn.click()
            
            await page.wait_for_load_state("networkidle", timeout=10000)
            debug_info["steps"].append("✓ Form submitted")
            
            # Take screenshot of results page
            screenshot_path = f"{DEBUG_DIR}/worker{worker_id}_{village_code}_{datetime.now().strftime('%H%M%S')}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            debug_info["screenshot"] = screenshot_path
            debug_info["steps"].append(f"✓ Screenshot: {screenshot_path}")
            
            # Extract data with detailed error checking
            html_content = await page.content()
            
            # Check for error messages on page
            error_elements = await page.locator(".error, .alert, .message").all()
            if error_elements:
                error_texts = []
                for elem in error_elements:
                    text = await elem.inner_text()
                    if text.strip():
                        error_texts.append(text.strip())
                debug_info["page_errors"] = error_texts
            
            # Check if tables exist and have data
            tables = await page.locator("table").all()
            debug_info["table_count"] = len(tables)
            
            if tables:
                for i, table in enumerate(tables):
                    rows = await table.locator("tr").all()
                    debug_info[f"table_{i}_rows"] = len(rows)
                    if len(rows) > 0:
                        # Get first few rows as sample
                        sample_html = await table.inner_html()
                        debug_info[f"table_{i}_sample"] = sample_html[:500]  # First 500 chars
            
            # Try extraction
            data = self.extractor.extract(html_content)
            
            await page.close()
            
            if data["success"]:
                debug_info["steps"].append("✓ Data extracted successfully")
                return {
                    "success": True,
                    "village_code": village_code,
                    "village_name": village_name,
                    "data": data,
                    "debug_info": debug_info
                }
            else:
                debug_info["extraction_error"] = data.get("error")
                debug_info["steps"].append(f"✗ Extraction failed: {data.get('error')}")
                
                # Save HTML for manual inspection
                html_path = f"{DEBUG_DIR}/worker{worker_id}_{village_code}_page.html"
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                debug_info["html_saved"] = html_path
                
                return {
                    "success": False,
                    "village_code": village_code,
                    "village_name": village_name,
                    "error": data.get("error"),
                    "debug_info": debug_info
                }
                
        except Exception as e:
            debug_info["exception"] = str(e)
            debug_info["steps"].append(f"✗ Exception: {e}")
            
            return {
                "success": False,
                "village_code": village_code,
                "village_name": village_name,
                "error": f"Exception: {e}",
                "debug_info": debug_info
            }
    
    async def run_test(self, district_code, district_name, talukas):
        """Run diagnostic test with browser contexts"""
        
        print(f"\n{'='*60}")
        print(f"🔍 ENHANCED DIAGNOSTIC TEST")
        print(f"{'='*60}")
        print(f"District: {district_name}")
        print(f"Contexts: {self.num_contexts}")
        print(f"Headless: {self.headless}")
        print(f"{'='*60}\n")
        
        # Prepare village queue
        villages = []
        for taluka in talukas:
            for village in taluka['villages']:
                villages.append({
                    'district_code': district_code,
                    'taluka_code': taluka['value'],
                    'taluka_name': taluka['label'],
                    'village_code': village['value'],
                    'village_name': village['label']
                })
        
        print(f"Total villages to test: {len(villages)}\n")
        
        async with async_playwright() as p:
            # Launch ONE browser
            browser = await p.chromium.launch(headless=self.headless)
            print(f"[BROWSER] Launched browser\n")
            
            # Create contexts (workers)
            contexts = []
            for i in range(self.num_contexts):
                context = await browser.new_context()
                contexts.append(context)
                print(f"[CONTEXT-{i+1}] Created context {i+1}/{self.num_contexts}")
            
            print(f"\n{'='*60}")
            print("Starting parallel scraping...")
            print(f"{'='*60}\n")
            
            # Create queue
            queue = asyncio.Queue()
            for v in villages:
                await queue.put(v)
            
            # Worker coroutine
            async def worker(context, worker_id):
                while not queue.empty():
                    try:
                        village = await queue.get()
                        print(f"[W{worker_id:02d}] Processing: {village['village_name']}")
                        
                        result = await self.scrape_village_debug(
                            context,
                            worker_id,
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
            
            # Run workers
            tasks = [worker(contexts[i], i+1) for i in range(self.num_contexts)]
            await asyncio.gather(*tasks)
            
            # Cleanup
            for context in contexts:
                await context.close()
            await browser.close()
        
        # Analyze results
        print(f"\n{'='*60}")
        print("RESULTS ANALYSIS")
        print(f"{'='*60}\n")
        
        successful = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]
        
        print(f"Total: {len(self.results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        print(f"Success Rate: {len(successful)/len(self.results)*100:.1f}%")
        
        if failed:
            print(f"\n❌ FAILED CASES ({len(failed)}):\n")
            for r in failed:
                print(f"  Village: {r['village_name']} ({r['village_code']})")
                print(f"  Error: {r['error']}")
                
                debug = r.get('debug_info', {})
                if 'survey_count' in debug:
                    print(f"  Survey Count: {debug['survey_count']}")
                if 'selected_survey' in debug:
                    print(f"  Selected Survey: {debug['selected_survey']}")
                if 'screenshot' in debug:
                    print(f"  Screenshot: {debug['screenshot']}")
                if 'html_saved' in debug:
                    print(f"  HTML: {debug['html_saved']}")
                if 'table_count' in debug:
                    print(f"  Tables Found: {debug['table_count']}")
                print()
        
        # Save detailed debug report
        report_path = f"{DEBUG_DIR}/debug_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Detailed debug report: {report_path}")
        print(f"📁 Screenshots and HTML: {DEBUG_DIR}/")
        print(f"\n{'='*60}\n")


async def main():
    # Load zone data
    with open('gujarat-anyror-complete.json', 'r', encoding='utf-8') as f:
        zone_data = json.load(f)
    
    # Use same district as before
    district = zone_data['districts'][0]  # કચ્છ
    
    # Test with 15 villages across 3 talukas
    test_talukas = []
    for i, taluka in enumerate(district['talukas'][:3]):
        test_talukas.append({
            'value': taluka['value'],
            'label': taluka['label'],
            'villages': taluka['villages'][:5]  # 5 per taluka = 15 total
        })
    
    scraper = EnhancedDiagnosticScraper(num_contexts=5, headless=False)
    await scraper.run_test(
        district_code=district['value'],
        district_name=district['label'],
        talukas=test_talukas
    )


if __name__ == "__main__":
    asyncio.run(main())
