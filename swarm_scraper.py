#!/usr/bin/env python3
"""
Swarm Scraper - High-performance district-wide concurrent scraping
Uses multiple browser workers to scrape all villages in a district simultaneously
"""

import json
import time
import os
import asyncio
import base64
from datetime import datetime
from typing import Dict, List, Optional, Callable
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from src.captcha_solver import CaptchaSolver
from src.vf7_extractor import VF7Extractor
from src.persistence_manager import PersistenceManager
from src.excel_exporter import VF7ExcelExporter


class SwarmScraper:
    """
    High-performance swarm scraper for district-wide search
    - Multiple browser workers
    - Async parallel execution
    - Real-time progress updates
    - Batched village processing
    """
    
    BASE_URL = "https://anyror.gujarat.gov.in/LandRecordRural.aspx"
    
    SELECTORS = {
        "record_type": "#ContentPlaceHolder1_drpLandRecord",
        "district": "#ContentPlaceHolder1_ddlDistrict",
        "taluka": "#ContentPlaceHolder1_ddlTaluka",
        "village": "#ContentPlaceHolder1_ddlVillage",
        "survey_no": "#ContentPlaceHolder1_ddlSurveyNo",
        "captcha_input": "#ContentPlaceHolder1_txt_captcha_1",
        "captcha_image": "#ContentPlaceHolder1_i_captcha_1",
        "refresh_captcha": "#ContentPlaceHolder1_lb_refresh_1",
    }
    
    def __init__(self, num_workers: int = 10, headless: bool = True):
        self.num_workers = num_workers
        self.headless = headless
        self.captcha_solver = CaptchaSolver()
        self.extractor = VF7Extractor()
        
        # Modular Persistence
        self.persistence = PersistenceManager(
            project_name="anyror_swarm", 
            state_code="GUJ"
        )
        
        # Progress tracking
        self.progress = {
            "status": "idle",
            "district_name": "",
            "current_taluka": "",
            "villages_total": 0,
            "villages_completed": 0,
            "villages_successful": 0,
            "villages_failed": 0,
            "active_workers": 0,
            "start_time": None,
            "villages_per_minute": 0,
            "eta_seconds": 0,
        }
        
        self.results = []
        self._stop_requested = False
        
        print(f"[SWARM] Initialized with {num_workers} workers")
    
    def get_progress(self) -> Dict:
        """Get current progress for API polling"""
        return self.progress.copy()
    
    def stop(self):
        """Request stop"""
        self._stop_requested = True
        self.progress["status"] = "stopping"
    
    async def _scrape_village(self, browser, worker_id: int, 
                              district_code: str, taluka_code: str, 
                              village_code: str, village_name: str,
                              max_captcha_attempts: int = 3) -> Dict:
        """Scrape a single village"""
        context = None
        
        try:
            # Create new context
            context = await browser.new_context()
            page = await context.new_page()
            await page.set_viewport_size({"width": 1280, "height": 900})
            
            # Handle dialogs
            page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
            
            # Navigate
            await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(1.5)
            
            # Select VF-7
            await page.locator(self.SELECTORS["record_type"]).select_option("1", timeout=30000)
            await asyncio.sleep(1)
            
            # Select district
            await page.locator(self.SELECTORS["district"]).select_option(district_code, timeout=30000)
            await asyncio.sleep(1.5)
            
            # Select taluka
            await page.locator(self.SELECTORS["taluka"]).select_option(taluka_code, timeout=30000)
            await asyncio.sleep(1.5)
            
            # Select village
            await page.locator(self.SELECTORS["village"]).select_option(village_code, timeout=30000)
            await asyncio.sleep(1)
            
            # Get first survey
            survey_options = await self._get_options(page, self.SELECTORS["survey_no"])
            if not survey_options:
                return {
                    "success": False,
                    "village_code": village_code,
                    "village_name": village_name,
                    "error": "No surveys found"
                }
            
            first_survey = survey_options[0]
            await page.locator(self.SELECTORS["survey_no"]).select_option(first_survey["value"], timeout=10000)
            await asyncio.sleep(1)  # IMPORTANT: Wait for captcha image to fully load
            
            # Try captcha
            data = None
            for attempt in range(1, max_captcha_attempts + 1):
                # Get captcha image
                captcha_img = await self._get_captcha_image(page)
                if not captcha_img:
                    continue
                
                # Solve captcha
                captcha_text = self.captcha_solver.solve(captcha_img)
                if not captcha_text or len(captcha_text) < 4:
                    continue
                
                # Enter captcha
                await page.locator(self.SELECTORS["captcha_input"]).fill(captcha_text)
                
                # Submit
                await page.locator(self.SELECTORS["captcha_input"]).press("Enter")
                await asyncio.sleep(2)
                
                # Extract data
                data = await self._extract_data(page)
                
                if data["success"]:
                    break
                
                # Refresh captcha for retry
                if attempt < max_captcha_attempts:
                    try:
                        refresh_selectors = [
                            "#ContentPlaceHolder1_lb_refresh_1",
                            "text=Refresh Code",
                        ]
                        for sel in refresh_selectors:
                            if await page.locator(sel).count() > 0:
                                await page.locator(sel).click()
                                break
                        await asyncio.sleep(0.5)
                    except:
                        pass
            
            if not data or not data["success"]:
                return {
                    "success": False,
                    "village_code": village_code,
                    "village_name": village_name,
                    "error": "Captcha failed"
                }
            
            # Build result
            raw_result = {
                "district": {"value": district_code},
                "taluka": {"value": taluka_code},
                "village": {"value": village_code, "text": village_name},
                "survey": first_survey,
                "data": data
            }
            
            # Extract structured data
            structured_data = self.extractor.extract_from_scrape_result(raw_result)
            
            return {
                "success": True,
                "village_code": village_code,
                "village_name": village_name,
                "survey": first_survey["text"],
                "raw": raw_result,
                "structured": structured_data
            }
            
        except Exception as e:
            return {
                "success": False,
                "village_code": village_code,
                "village_name": village_name,
                "error": str(e)
            }
        
        finally:
            if context:
                try:
                    await context.close()
                except:
                    pass
    
    async def _get_options(self, page, selector: str) -> List[Dict]:
        """Get dropdown options"""
        options = []
        try:
            opts = await page.locator(selector).locator("option").all()
            for opt in opts:
                value = await opt.get_attribute("value")
                text = (await opt.text_content()).strip()
                if value and value not in ["0", "-1", ""] and "પસંદ" not in text and "select" not in text.lower():
                    options.append({"value": value, "text": text})
        except:
            pass
        return options
    
    async def _get_captcha_image(self, page) -> bytes:
        """Get captcha image - handles base64 data URI format"""
        try:
            selectors = [
                "#ContentPlaceHolder1_i_captcha_1",
                "#ContentPlaceHolder1_imgCaptcha",
                "img[id*='captcha']",
            ]
            
            for selector in selectors:
                if await page.locator(selector).count() > 0:
                    img = page.locator(selector)
                    
                    # Try to get base64 data first
                    src = await img.get_attribute("src")
                    if src and src.startswith("data:image"):
                        if "," in src:
                            base64_data = src.split(",", 1)[1]
                            return base64.b64decode(base64_data)
                    
                    # Fallback to screenshot
                    return await img.screenshot()
            
            return None
        except:
            return None
    
    async def _extract_data(self, page) -> Dict:
        """Extract data from page"""
        try:
            # Check for error message first
            error_elem = page.locator("[id*='lblError'], [id*='lblMsg']")
            if await error_elem.count() > 0:
                error_text = await error_elem.first.text_content()
                if error_text and "wrong" in error_text.lower():
                    return {"success": False, "error": "Wrong captcha"}
            
            # Look for result tables
            tables = await page.locator("table").all()
            if not tables:
                return {"success": False, "error": "No tables"}
            
            # Get full page text for extraction
            content = await page.locator("#ContentPlaceHolder1, .content, main, body").first.text_content()
            
            table_data = []
            for table in tables:
                text = await table.text_content()
                if len(text.strip()) > 200:
                    table_data.append({"text": text.strip()})
            
            if not table_data:
                return {"success": False, "error": "No data in tables"}
            
            return {
                "success": True,
                "tables": table_data,
                "full_page_text": content,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _worker(self, browser, worker_id: int, queue: asyncio.Queue,
                      district_code: str, results: List[Dict]):
        """Worker that processes villages from queue"""
        while not self._stop_requested:
            try:
                # Get next village from queue (non-blocking check)
                try:
                    village_info = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                
                taluka_code = village_info["taluka_code"]
                village_code = village_info["village_code"]
                village_name = village_info["village_name"]
                
                # Check if already completed (RESUME LOGIC)
                task_id = f"{district_code}_{taluka_code}_{village_code}"
                if self.persistence.is_complete(task_id):
                    print(f"[W{worker_id:02d}] ⏩ Skipping {village_name} (Already done)")
                    self.progress["villages_completed"] += 1
                    self.progress["villages_successful"] += 1
                    queue.task_done()
                    continue

                self.progress["active_workers"] = min(self.progress["active_workers"] + 1, self.num_workers)
                
                # Scrape village
                result = await self._scrape_village(
                    browser, worker_id,
                    district_code, taluka_code,
                    village_code, village_name
                )
                
                if result["success"]:
                    # SAVE RESULT IMMEDIATELY (SPOT VM SAFETY)
                    await self.persistence.save_result(task_id, result["structured"])
                    results.append(result)
                    self.progress["villages_successful"] += 1
                    print(f"[W{worker_id:02d}] ✓ {village_name[:30]}")
                else:
                    self.progress["villages_failed"] += 1
                    print(f"[W{worker_id:02d}] ✗ {village_name[:30]} - {result.get('error', 'Unknown')[:30]}")
                
                # Update progress
                self.progress["villages_completed"] += 1
                
                # Calculate stats
                if self.progress["start_time"]:
                    elapsed = (datetime.now() - self.progress["start_time"]).total_seconds()
                    if elapsed > 0:
                        self.progress["villages_per_minute"] = round(
                            (self.progress["villages_completed"] / elapsed) * 60, 1
                        )
                        remaining = self.progress["villages_total"] - self.progress["villages_completed"]
                        if self.progress["villages_per_minute"] > 0:
                            self.progress["eta_seconds"] = int(
                                (remaining / self.progress["villages_per_minute"]) * 60
                            )
                
                self.progress["active_workers"] = max(0, self.progress["active_workers"] - 1)
                queue.task_done()
                
            except Exception as e:
                print(f"[W{worker_id:02d}] Worker error: {e}")
                break
    
    async def _scrape_district_async(self, district_code: str, district_name: str,
                                     talukas: List[Dict], output_dir: str):
        """Main async scraping logic"""
        async with async_playwright() as p:
            # Calculate total villages
            total_villages = sum(len(t["villages"]) for t in talukas)
            
            self.progress["status"] = "running"
            self.progress["district_name"] = district_name
            self.progress["villages_total"] = total_villages
            self.progress["start_time"] = datetime.now()
            
            # Launch browsers (1 browser per ~2-3 workers for efficiency)
            num_browsers = min(5, (self.num_workers + 2) // 3)
            print(f"[SWARM] Starting {num_browsers} browsers for {self.num_workers} workers...")
            
            browsers = []
            for i in range(num_browsers):
                browser = await p.chromium.launch(headless=self.headless)
                browsers.append(browser)
            
            print(f"[SWARM] All browsers ready!")
            print(f"[SWARM] Processing {total_villages} villages from {len(talukas)} talukas")
            print()
            
            # Create queue with all villages
            queue = asyncio.Queue()
            for taluka in talukas:
                taluka_code = taluka["value"]
                self.progress["current_taluka"] = taluka["label"]
                
                for village in taluka["villages"]:
                    queue.put_nowait({
                        "taluka_code": taluka_code,
                        "village_code": village["value"],
                        "village_name": village["label"]
                    })
            
            # Start workers
            results = []
            tasks = []
            for i in range(self.num_workers):
                browser_idx = i % num_browsers
                task = asyncio.create_task(
                    self._worker(browsers[browser_idx], i + 1, queue, district_code, results)
                )
                tasks.append(task)
            
            # Wait for all workers to complete
            await asyncio.gather(*tasks)
            
            # Close browsers
            print()
            print("[SWARM] Closing browsers...")
            for browser in browsers:
                await browser.close()
            
            self.results = results
            return results
    
    def scrape_district(self, district_code: str, district_name: str,
                        talukas: List[Dict], output_dir: str = "output") -> Dict:
        """
        Scrape all villages in a district concurrently
        
        Args:
            district_code: District code
            district_name: District name for display
            talukas: List of taluka dicts with villages
            output_dir: Output directory
        
        Returns:
            Summary dict with results
        """
        os.makedirs(output_dir, exist_ok=True)
        self._stop_requested = False
        
        # Reset progress
        self.progress = {
            "status": "starting",
            "district_name": district_name,
            "current_taluka": "",
            "villages_total": sum(len(t["villages"]) for t in talukas),
            "villages_completed": 0,
            "villages_successful": 0,
            "villages_failed": 0,
            "active_workers": 0,
            "start_time": None,
            "villages_per_minute": 0,
            "eta_seconds": 0,
        }
        
        print("=" * 60)
        print(f"🐝 SWARM SCRAPER - {district_name}")
        print("=" * 60)
        print(f"Workers: {self.num_workers}")
        print(f"Talukas: {len(talukas)}")
        print(f"Villages: {self.progress['villages_total']}")
        print("=" * 60)
        print()
        
        # Run async scraping
        start_time = datetime.now()
        results = asyncio.run(self._scrape_district_async(
            district_code, district_name, talukas, output_dir
        ))
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = os.path.join(output_dir, f"swarm_{district_code}_{timestamp}.json")
        
        output_data = {
            "metadata": {
                "district_code": district_code,
                "district_name": district_name,
                "total_villages": len(results),
                "successful": sum(1 for r in results if r.get("success")),
                "failed": sum(1 for r in results if not r.get("success")),
                "duration_seconds": duration,
                "workers": self.num_workers,
                "timestamp": timestamp
            },
            "results": results
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        # Generate Excel report
        print()
        print("[SWARM] 📊 Generating Excel report...")
        
        try:
            # Extract structured results for Excel
            structured_results = []
            for r in results:
                if r.get("success") and "structured" in r:
                    structured = r["structured"]
                    # Add village code for reference
                    structured["village_code"] = r.get("village_code", "")
                    structured_results.append(structured)
            
            if structured_results:
                excel_file = results_file.replace('.json', '_REPORT.xlsx')
                exporter = VF7ExcelExporter()
                exporter.create_single_sheet_workbook(
                    structured_results,
                    excel_file,
                    district_name=district_name,
                    taluka_name=""
                )
                
                file_size_mb = os.path.getsize(excel_file) / (1024 * 1024)
                print(f"[SWARM] ✅ Excel report created: {excel_file}")
                print(f"[SWARM]    Size: {file_size_mb:.2f} MB")
                print(f"[SWARM]    Records: {len(structured_results)}")
            else:
                print("[SWARM] ⚠️  No successful records to export to Excel")
                excel_file = None
        
        except Exception as e:
            print(f"[SWARM] ⚠️  Excel export failed: {e}")
            excel_file = None
        
        # Update final progress
        self.progress["status"] = "completed"
        self.progress["end_time"] = datetime.now().isoformat()
        
        # Print summary
        print()
        print("=" * 60)
        print("🐝 SWARM COMPLETE")
        print("=" * 60)
        print(f"District: {district_name}")
        print(f"Villages: {output_data['metadata']['successful']}/{output_data['metadata']['total_villages']}")
        print(f"Duration: {duration:.1f}s ({duration/60:.1f} min)")
        if output_data['metadata']['successful'] > 0:
            print(f"Speed: {output_data['metadata']['successful'] / (duration/60):.1f} villages/min")
        print(f"\n📁 Output Files:")
        print(f"   JSON:  {results_file}")
        if excel_file:
            print(f"   Excel: {excel_file}")
        print("=" * 60)
        
        return {
            "total": len(results),
            "successful": output_data["metadata"]["successful"],
            "failed": output_data["metadata"]["failed"],
            "duration": duration,
            "results_file": results_file,
            "excel_file": excel_file,
            "results": results
        }


# For testing
if __name__ == "__main__":
    import sys
    
    # Load zone data
    zone_data_path = 'data/gujarat-anyror-complete.json'
    if not os.path.exists(zone_data_path):
        zone_data_path = 'gujarat-anyror-complete.json'
        
    with open(zone_data_path, 'r', encoding='utf-8') as f:
        zone_data = json.load(f)
    
    # Test with a small district or first few villages
    district = zone_data['districts'][0]  # First district
    district_code = district['value']
    district_name = district['label']
    
    # Limit to first taluka, first 5 villages for testing
    test_talukas = [{
        "value": district['talukas'][0]['value'],
        "label": district['talukas'][0]['label'],
        "villages": district['talukas'][0]['villages'][:5]
    }]
    
    print(f"Testing with {district_name}, {test_talukas[0]['label']}, 5 villages")
    
    scraper = SwarmScraper(num_workers=5, headless=True)
    result = scraper.scrape_district(district_code, district_name, test_talukas)
    
    print(f"\nResult: {result['successful']}/{result['total']} successful")
