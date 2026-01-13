"""
Cloud Run Job Runner - Even cheaper than Cloud Run Services
Runs district-wide searches as batch jobs, scales to 0 when idle

Usage:
  python job_runner.py --district 01 --search-type survey --search-value "123"
  
This is the CHEAPEST option:
- No always-on service
- Pay only for actual compute time
- Can run 34 parallel jobs (one per district)
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime
from typing import List, Dict
from playwright.async_api import async_playwright
import base64

# Try to import Google Cloud libs (optional for local testing)
try:
    from google.cloud import firestore
    from google import genai
    HAS_GCP = True
except ImportError:
    HAS_GCP = False
    print("[WARN] Google Cloud libs not installed, running in local mode")


# Load Gujarat data
GUJARAT_DATA_PATH = os.environ.get("GUJARAT_DATA", "gujarat-anyror-complete.json")
with open(GUJARAT_DATA_PATH, "r", encoding="utf-8") as f:
    GUJARAT_DATA = json.load(f)

DISTRICTS = {d["value"]: d for d in GUJARAT_DATA["districts"]}


class SimpleCaptchaSolver:
    """Captcha solver - uses Gemini or falls back to manual"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.client = None
        if self.api_key and HAS_GCP:
            self.client = genai.Client(api_key=self.api_key)
    
    async def solve(self, image_bytes: bytes) -> str:
        if not self.client:
            # Save for manual solving
            with open("captcha_manual.png", "wb") as f:
                f.write(image_bytes)
            return input("Enter captcha from captcha_manual.png: ")
        
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[{
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                    {"text": "Read the CAPTCHA. Return ONLY the digits/letters."}
                ]
            }]
        )
        text = response.text.strip()
        return ''.join(c for c in text if c.isascii() and c.isalnum())


class DistrictSearchJob:
    """Searches all talukas in a district"""
    
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
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.captcha_solver = SimpleCaptchaSolver()
        self.results = []
    
    async def run(
        self,
        district_code: str,
        search_type: str,
        search_value: str,
        output_file: str = None
    ) -> Dict:
        """Run district-wide search"""
        
        district = DISTRICTS.get(district_code)
        if not district:
            raise ValueError(f"District {district_code} not found")
        
        print(f"\n{'='*60}")
        print(f"DISTRICT SEARCH: {district['label']} ({district_code})")
        print(f"Talukas: {len(district['talukas'])}")
        print(f"Search: {search_type} = {search_value}")
        print(f"{'='*60}\n")
        
        job_result = {
            "district": {"code": district_code, "name": district["label"]},
            "search_type": search_type,
            "search_value": search_value,
            "started_at": datetime.utcnow().isoformat(),
            "talukas_searched": 0,
            "villages_searched": 0,
            "matches": [],
            "errors": []
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            
            for taluka in district["talukas"]:
                print(f"\n[TALUKA] {taluka['label']} ({len(taluka['villages'])} villages)")
                
                taluka_result = await self._search_taluka(
                    browser, district_code, taluka, search_type, search_value
                )
                
                job_result["talukas_searched"] += 1
                job_result["villages_searched"] += taluka_result.get("villages_searched", 0)
                job_result["matches"].extend(taluka_result.get("matches", []))
                job_result["errors"].extend(taluka_result.get("errors", []))
                
                # Progress
                print(f"   Searched: {taluka_result.get('villages_searched', 0)} villages")
                print(f"   Matches: {len(taluka_result.get('matches', []))}")
            
            await browser.close()
        
        job_result["completed_at"] = datetime.utcnow().isoformat()
        job_result["total_matches"] = len(job_result["matches"])
        
        # Save results
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(job_result, f, ensure_ascii=False, indent=2)
            print(f"\n✅ Results saved to: {output_file}")
        
        return job_result
    
    async def _search_taluka(
        self,
        browser,
        district_code: str,
        taluka: Dict,
        search_type: str,
        search_value: str
    ) -> Dict:
        """Search all villages in a taluka"""
        
        result = {
            "taluka": taluka["label"],
            "villages_searched": 0,
            "matches": [],
            "errors": []
        }
        
        for village in taluka["villages"]:
            try:
                match = await self._search_village(
                    browser, district_code, taluka["value"],
                    village, search_type, search_value
                )
                result["villages_searched"] += 1
                
                if match and match.get("found"):
                    result["matches"].append(match)
                    print(f"   ✓ FOUND in {village['label']}")
                    
            except Exception as e:
                result["errors"].append({
                    "village": village["label"],
                    "error": str(e)
                })
        
        return result
    
    async def _search_village(
        self,
        browser,
        district_code: str,
        taluka_code: str,
        village: Dict,
        search_type: str,
        search_value: str
    ) -> Dict:
        """Search a single village"""
        
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            await page.goto(self.BASE_URL, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            # Select VF-7
            await page.locator(self.SELECTORS["record_type"]).select_option("1")
            await asyncio.sleep(0.5)
            
            # Select location
            await page.locator(self.SELECTORS["district"]).select_option(district_code)
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            await page.locator(self.SELECTORS["taluka"]).select_option(taluka_code)
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            await page.locator(self.SELECTORS["village"]).select_option(village["value"])
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Get survey options
            survey_options = []
            for opt in await page.locator(self.SELECTORS["survey_no"]).locator("option").all():
                value = await opt.get_attribute("value")
                text = (await opt.text_content()).strip()
                if value and value not in ["0", "-1", ""]:
                    survey_options.append({"value": value, "text": text})
            
            # Find matching survey
            if search_type == "survey":
                match = next(
                    (o for o in survey_options if search_value in o["text"]),
                    None
                )
                
                if not match:
                    return {"found": False, "village": village["label"]}
                
                # Select and get details
                await page.locator(self.SELECTORS["survey_no"]).select_option(match["value"])
                await asyncio.sleep(0.5)
                
                # Solve captcha
                for attempt in range(2):
                    try:
                        captcha_img = await page.locator(self.SELECTORS["captcha_image"]).screenshot()
                        captcha_text = await self.captcha_solver.solve(captcha_img)
                        
                        await page.locator(self.SELECTORS["captcha_input"]).fill(captcha_text)
                        await page.locator(self.SELECTORS["captcha_input"]).press("Enter")
                        
                        await asyncio.sleep(2)
                        
                        # Check for results
                        content = await page.content()
                        if "ખાતા નંબર" in content:
                            # Extract basic data
                            tables = await page.locator("table").all()
                            table_text = ""
                            for t in tables:
                                txt = await t.text_content()
                                if len(txt) > 200:
                                    table_text = txt
                                    break
                            
                            return {
                                "found": True,
                                "village": village["label"],
                                "village_code": village["value"],
                                "survey": match["text"],
                                "data": table_text[:2000]  # Truncate for storage
                            }
                        
                        # Refresh captcha
                        try:
                            await page.locator("text=Refresh Code").click()
                            await asyncio.sleep(0.5)
                        except:
                            pass
                            
                    except Exception as e:
                        continue
            
            return {"found": False, "village": village["label"]}
            
        finally:
            await context.close()


def main():
    parser = argparse.ArgumentParser(description="Gujarat AnyROR District Search Job")
    parser.add_argument("--district", "-d", required=True, help="District code (01-34)")
    parser.add_argument("--search-type", "-t", default="survey", choices=["survey", "owner"])
    parser.add_argument("--search-value", "-v", required=True, help="Value to search for")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", dest="headless", action="store_false")
    
    args = parser.parse_args()
    
    # Default output file
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"search_{args.district}_{timestamp}.json"
    
    job = DistrictSearchJob(headless=args.headless)
    result = asyncio.run(job.run(
        district_code=args.district,
        search_type=args.search_type,
        search_value=args.search_value,
        output_file=args.output
    ))
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Talukas searched: {result['talukas_searched']}")
    print(f"Villages searched: {result['villages_searched']}")
    print(f"Total matches: {result['total_matches']}")
    print(f"Errors: {len(result['errors'])}")


if __name__ == "__main__":
    main()
