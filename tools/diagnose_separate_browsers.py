#!/usr/bin/env python3
"""
4 Separate Browsers Test - No Contexts
Simple, separate browser instances like your working tests
"""

import json
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright
from captcha_solver import CaptchaSolver
from vf7_extractor import VF7Extractor

DEBUG_DIR = "debug_output"
os.makedirs(DEBUG_DIR, exist_ok=True)

class SeparateBrowsersScraper:
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
    
    def __init__(self, num_browsers=4, headless=False):
        self.num_browsers = num_browsers
        self.headless = headless
        self.captcha_solver = CaptchaSolver()
        self.extractor = VF7Extractor()
        self.results = []
        
    async def _wait_for_options(self, page, selector, timeout=20000):
        """Wait for dropdown to have options"""
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
        """Get captcha image"""
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
            print(f"[ERROR] Captcha: {e}")
            return None
    
    async def scrape_village(self, browser, worker_id, district_code, taluka_code, 
                            village_code, village_name):
        """Scrape a village using a separate browser"""
        
        debug_info = {
            "worker_id": worker_id,
            "village": village_name,
            "timestamp": datetime.now().isoformat(),
        }
        
        try:
            # Create page in this browser
            page = await browser.new_page()
            
            # Navigate
            print(f"[W{worker_id:02d}] Navigating...")
            await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)  # Let page settle
            
            # Select VF-7
            print(f"[W{worker_id:02d}] Selecting VF-7...")
            await page.locator(self.SELECTORS["record_type"]).select_option("1")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # Select district
            print(f"[W{worker_id:02d}] Selecting district...")
            await page.locator(self.SELECTORS["district"]).select_option(district_code)
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # Select taluka
            print(f"[W{worker_id:02d}] Selecting taluka...")
            await page.locator(self.SELECTORS["taluka"]).select_option(taluka_code)
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # Select village
            print(f"[W{worker_id:02d}] Selecting village...")
            await self._wait_for_options(page, self.SELECTORS["village"])
            await page.locator(self.SELECTORS["village"]).select_option(village_code)
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # Get surveys
            print(f"[W{worker_id:02d}] Getting surveys...")
            await self._wait_for_options(page, self.SELECTORS["survey_no"])
            survey_options = await self._get_options(page, self.SELECTORS["survey_no"])
            
            debug_info["surveys"] = len(survey_options)
            
            if not survey_options:
                await page.close()
                return {
                    "success": False,
                    "village_name": village_name,
                    "error": "No surveys in dropdown",
                    "debug": debug_info
                }
            
            # Select first survey
            first_survey = survey_options[0]
            debug_info["selected_survey"] = first_survey["text"]
            
            print(f"[W{worker_id:02d}] Selecting survey: {first_survey['text']}")
            await page.locator(self.SELECTORS["survey_no"]).select_option(first_survey["value"])
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # Solve captcha
            print(f"[W{worker_id:02d}] Solving captcha...")
            captcha_img = await self._get_captcha_image(page)
            if not captcha_img:
                await page.close()
                return {
                    "success": False,
                    "village_name": village_name,
                    "error": "Captcha image failed",
                    "debug": debug_info
                }
            
            captcha_text = self.captcha_solver.solve(captcha_img)
            if not captcha_text:
                await page.close()
                return {
                    "success": False,
                    "village_name": village_name,
                    "error": "Captcha solve failed",
                    "debug": debug_info
                }
            
            print(f"[W{worker_id:02d}] Captcha: {captcha_text}")
            
            # Submit
            captcha_input = page.locator(self.SELECTORS["captcha_input"])
            await captcha_input.fill(captcha_text)
            
            submit_btn = page.locator(self.SELECTORS["submit_btn"])
            await submit_btn.click()
            
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(2)
            
            # Screenshot
            screenshot_path = f"{DEBUG_DIR}/sep_w{worker_id}_{village_code}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            debug_info["screenshot"] = screenshot_path
            
            # Extract
            html = await page.content()
            data = self.extractor.extract(html)
            
            await page.close()
            
            if data["success"]:
                return {
                    "success": True,
                    "village_name": village_name,
                    "data": data,
                    "debug": debug_info
                }
            else:
                # Save HTML
                html_path = f"{DEBUG_DIR}/sep_w{worker_id}_{village_code}.html"
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                debug_info["html"] = html_path
                
                return {
                    "success": False,
                    "village_name": village_name,
                    "error": data.get("error"),
                    "debug": debug_info
                }
                
        except Exception as e:
            import traceback
            return {
                "success": False,
                "village_name": village_name,
                "error": f"Exception: {e}",
                "debug": debug_info,
                "traceback": traceback.format_exc()
            }
    
    async def run_test(self, district_code, district_name, talukas):
        """Run test with separate browsers"""
        
        print(f"\n{'='*60}")
        print(f"🦅 SEPARATE BROWSERS TEST (No Contexts)")
        print(f"{'='*60}")
        print(f"District: {district_name}")
        print(f"Browsers: {self.num_browsers}")
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
        
        print(f"Testing {len(villages)} villages\n")
        
        async with async_playwright() as p:
            # Launch separate browsers
            browsers = []
            for i in range(self.num_browsers):
                browser = await p.chromium.launch(headless=self.headless)
                browsers.append(browser)
                print(f"[BROWSER-{i+1}] Launched")
            
            print(f"\n{'='*60}\n")
            
            queue = asyncio.Queue()
            for v in villages:
                await queue.put(v)
            
            async def worker(browser, worker_id):
                while not queue.empty():
                    try:
                        village = await queue.get()
                        print(f"\n[W{worker_id:02d}] === {village['village_name']} ===")
                        
                        result = await self.scrape_village(
                            browser, worker_id,
                            village['district_code'],
                            village['taluka_code'],
                            village['village_code'],
                            village['village_name']
                        )
                        
                        self.results.append(result)
                        
                        status = "✅" if result['success'] else "❌"
                        error = f" - {result.get('error')}" if not result['success'] else ""
                        print(f"\n[W{worker_id:02d}] {status} {village['village_name']}{error}\n")
                        
                        queue.task_done()
                    except Exception as e:
                        print(f"[W{worker_id:02d}] Worker error: {e}")
            
            # Run workers
            tasks = [worker(browsers[i], i+1) for i in range(self.num_browsers)]
            await asyncio.gather(*tasks)
            
            # Cleanup
            for browser in browsers:
                await browser.close()
        
        # Results
        print(f"\n{'='*60}")
        print("RESULTS")
        print(f"{'='*60}\n")
        
        successful = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]
        
        print(f"Total: {len(self.results)}")
        print(f"✅ Success: {len(successful)}")
        print(f"❌ Failed: {len(failed)}")
        print(f"Success Rate: {len(successful)/len(self.results)*100:.1f}%\n")
        
        if failed:
            print("FAILURES:\n")
            for r in failed:
                print(f"  {r['village_name']}")
                print(f"    Error: {r['error']}")
                if 'screenshot' in r.get('debug', {}):
                    print(f"    📸 {r['debug']['screenshot']}")
                if 'surveys' in r.get('debug', {}):
                    print(f"    Surveys: {r['debug']['surveys']}")
                print()
        
        # Save
        report_path = f"{DEBUG_DIR}/separate_browsers_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Report: {report_path}\n")


async def main():
    with open('gujarat-anyror-complete.json', 'r', encoding='utf-8') as f:
        zone_data = json.load(f)
    
    district = zone_data['districts'][0]
    
    # Test with 8 villages (2 per browser)
    test_talukas = []
    for taluka in district['talukas'][:2]:
        test_talukas.append({
            'value': taluka['value'],
            'label': taluka['label'],
            'villages': taluka['villages'][:4]  # 4 per taluka = 8 total
        })
    
    scraper = SeparateBrowsersScraper(num_browsers=4, headless=False)
    await scraper.run_test(
        district_code=district['value'],
        district_name=district['label'],
        talukas=test_talukas
    )


if __name__ == "__main__":
    asyncio.run(main())
