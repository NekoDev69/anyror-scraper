"""
Taluka Worker - Scrapes all villages in a taluka
Runs as Cloud Run Job or Cloud Function
"""

import os
import json
import asyncio
import base64
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright
from google.cloud import firestore
from google import genai

# Config
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MAX_CONCURRENT_VILLAGES = 3  # Limit concurrent scrapes to avoid rate limiting
MAX_RETRIES = 2


class CaptchaSolver:
    """Async captcha solver using Gemini"""
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
    
    async def solve(self, image_bytes: bytes) -> str:
        """Solve captcha image"""
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[{
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                    {"text": "Read the CAPTCHA. Return ONLY the digits/letters, nothing else."}
                ]
            }]
        )
        
        text = response.text.strip()
        # Clean - only ASCII alphanumeric
        return ''.join(c for c in text if c.isascii() and c.isalnum())


class TalukaScraper:
    """Scrapes VF-7 records for a taluka"""
    
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
    
    def __init__(self):
        self.captcha_solver = CaptchaSolver(GEMINI_API_KEY)
        self.db = firestore.Client()
    
    async def search_taluka(
        self,
        district_code: str,
        district_name: str,
        taluka_code: str,
        taluka_name: str,
        villages: List[Dict],
        search_type: str,
        search_value: str,
        job_id: Optional[str] = None
    ) -> Dict:
        """Search all villages in a taluka"""
        
        results = {
            "district": {"code": district_code, "name": district_name},
            "taluka": {"code": taluka_code, "name": taluka_name},
            "search_type": search_type,
            "search_value": search_value,
            "villages_searched": 0,
            "matches": [],
            "errors": [],
            "started_at": datetime.utcnow().isoformat(),
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            # Process villages in batches
            for i in range(0, len(villages), MAX_CONCURRENT_VILLAGES):
                batch = villages[i:i + MAX_CONCURRENT_VILLAGES]
                tasks = [
                    self._search_village(
                        browser, district_code, taluka_code, 
                        village, search_type, search_value
                    )
                    for village in batch
                ]
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for village, result in zip(batch, batch_results):
                    results["villages_searched"] += 1
                    
                    if isinstance(result, Exception):
                        results["errors"].append({
                            "village": village["label"],
                            "error": str(result)
                        })
                    elif result and result.get("found"):
                        results["matches"].append(result)
                
                # Update job progress if tracking
                if job_id:
                    await self._update_job_progress(job_id, results)
            
            await browser.close()
        
        results["completed_at"] = datetime.utcnow().isoformat()
        return results
    
    async def _search_village(
        self,
        browser,
        district_code: str,
        taluka_code: str,
        village: Dict,
        search_type: str,
        search_value: str
    ) -> Optional[Dict]:
        """Search a single village for the target"""
        
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            await page.goto(self.BASE_URL, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            # Select VF-7
            await page.locator(self.SELECTORS["record_type"]).select_option("1")
            await asyncio.sleep(1)
            
            # Select district
            await page.locator(self.SELECTORS["district"]).select_option(district_code)
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Select taluka
            await page.locator(self.SELECTORS["taluka"]).select_option(taluka_code)
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Select village
            await page.locator(self.SELECTORS["village"]).select_option(village["value"])
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Check if survey exists (for survey search)
            if search_type == "survey":
                survey_options = await self._get_options(page, self.SELECTORS["survey_no"])
                
                # Find matching survey
                match = next(
                    (o for o in survey_options if search_value in o["text"]),
                    None
                )
                
                if not match:
                    return {"found": False, "village": village["label"]}
                
                # Select survey and get details
                await page.locator(self.SELECTORS["survey_no"]).select_option(match["value"])
                await asyncio.sleep(1)
                
                # Solve captcha and submit
                for attempt in range(MAX_RETRIES):
                    captcha_img = await page.locator(self.SELECTORS["captcha_image"]).screenshot()
                    captcha_text = await self.captcha_solver.solve(captcha_img)
                    
                    await page.locator(self.SELECTORS["captcha_input"]).fill(captcha_text)
                    await page.locator(self.SELECTORS["captcha_input"]).press("Enter")
                    
                    await asyncio.sleep(3)
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    
                    # Check for results
                    page_text = await page.content()
                    if "ખાતા નંબર" in page_text or "Khata" in page_text:
                        # Extract data
                        data = await self._extract_data(page)
                        return {
                            "found": True,
                            "village": village["label"],
                            "village_code": village["value"],
                            "survey": match["text"],
                            "data": data
                        }
                    
                    # Refresh captcha for retry
                    try:
                        await page.locator("text=Refresh Code").click()
                        await asyncio.sleep(1)
                    except:
                        pass
                
                return {"found": False, "village": village["label"], "reason": "captcha_failed"}
            
            return {"found": False, "village": village["label"]}
            
        except Exception as e:
            return {"found": False, "village": village["label"], "error": str(e)}
        
        finally:
            await context.close()
    
    async def _get_options(self, page, selector: str) -> List[Dict]:
        """Get dropdown options"""
        options = []
        for opt in await page.locator(selector).locator("option").all():
            value = await opt.get_attribute("value")
            text = (await opt.text_content()).strip()
            if value and value not in ["0", "-1", ""]:
                options.append({"value": value, "text": text})
        return options
    
    async def _extract_data(self, page) -> Dict:
        """Extract VF-7 data from results page"""
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "tables": [],
            "property_details": {}
        }
        
        # Extract tables
        tables = await page.locator("table").all()
        for i, table in enumerate(tables):
            text = await table.text_content()
            if len(text.strip()) > 200:
                data["tables"].append({"index": i, "text": text.strip()})
        
        # Extract key fields
        field_selectors = {
            "upin": ["#ContentPlaceHolder1_lblUPIN", "[id*='UPIN']"],
            "total_area": ["#ContentPlaceHolder1_lblArea", "[id*='Area']"],
            "tenure": ["#ContentPlaceHolder1_lblTenure", "[id*='Tenure']"],
        }
        
        for field, selectors in field_selectors.items():
            for sel in selectors:
                try:
                    elem = page.locator(sel).first
                    if await elem.count() > 0:
                        text = await elem.text_content()
                        if text and text.strip():
                            data["property_details"][field] = text.strip()
                            break
                except:
                    continue
        
        return data
    
    async def _update_job_progress(self, job_id: str, results: Dict):
        """Update job progress in Firestore"""
        try:
            self.db.collection("search_jobs").document(job_id).update({
                "completed_talukas": firestore.Increment(1),
                "results": firestore.ArrayUnion(results.get("matches", []))
            })
        except:
            pass


# Cloud Function entry point
def scrape_taluka(request):
    """Cloud Function handler for taluka scraping"""
    import asyncio
    
    data = request.get_json()
    
    scraper = TalukaScraper()
    results = asyncio.run(scraper.search_taluka(
        district_code=data["district_code"],
        district_name=data.get("district_name", ""),
        taluka_code=data["taluka_code"],
        taluka_name=data.get("taluka_name", ""),
        villages=data["villages"],
        search_type=data["search_type"],
        search_value=data["search_value"],
        job_id=data.get("job_id")
    ))
    
    return results


# Cloud Run Job entry point
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python worker.py <job_config.json>")
        sys.exit(1)
    
    with open(sys.argv[1]) as f:
        config = json.load(f)
    
    scraper = TalukaScraper()
    results = asyncio.run(scraper.search_taluka(**config))
    
    print(json.dumps(results, ensure_ascii=False, indent=2))
