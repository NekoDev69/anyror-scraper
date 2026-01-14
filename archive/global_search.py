"""
Gujarat AnyROR Global Zone Search - District-wise Search
Searches all talukas/villages in a district for a given survey number
Generates full VF-7 reports matching AnyROR portal layout

Usage:
  python global_search.py --district "કચ્છ" --survey "123"
  python global_search.py --district-code 01 --survey "456"
  python global_search.py --list-districts
"""

import os
import sys
import json
import time
import re
import argparse
from datetime import datetime
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from captcha_solver import CaptchaSolver
from vf7_extractor import VF7Extractor
from vf7_report import VF7ReportGenerator

# Load Gujarat data
with open("gujarat-anyror-complete.json", "r", encoding="utf-8") as f:
    GUJARAT_DATA = json.load(f)

DISTRICTS = {d["value"]: d for d in GUJARAT_DATA["districts"]}
DISTRICT_BY_NAME = {d["label"]: d for d in GUJARAT_DATA["districts"]}

# Gemini API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4")


class GlobalZoneSearch:
    """Search across all talukas in a district - same quality as single scraper"""
    
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
    
    def __init__(self, headless: bool = True, output_dir: str = "output"):
        self.headless = headless
        self.captcha_solver = CaptchaSolver(GEMINI_API_KEY)
        self.extractor = VF7Extractor()
        self.report_generator = VF7ReportGenerator()
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def search_district(
        self,
        district_code: str,
        search_value: str,
        search_type: str = "survey",
        max_villages: int = None,
        save_results: bool = True
    ) -> Dict:
        """Search all talukas/villages in a district"""
        
        district = DISTRICTS.get(district_code)
        if not district:
            raise ValueError(f"District code {district_code} not found")
        
        print(f"\n{'='*70}")
        print(f"GLOBAL ZONE SEARCH: {district['label']}")
        print(f"Talukas: {len(district['talukas'])}")
        print(f"Total Villages: {sum(len(t['villages']) for t in district['talukas'])}")
        print(f"Searching for: {search_type} = {search_value}")
        print(f"Output: {self.output_dir}/")
        print(f"{'='*70}\n")
        
        result = {
            "district": {"code": district_code, "name": district["label"]},
            "search_type": search_type,
            "search_value": search_value,
            "started_at": datetime.now().isoformat(),
            "talukas_searched": 0,
            "villages_searched": 0,
            "matches": [],
            "errors": []
        }
        
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=self.headless)
        context = browser.new_context()
        page = context.new_page()
        
        # Handle dialogs
        page.on("dialog", lambda d: d.accept())
        
        try:
            villages_count = 0
            
            for taluka in district["talukas"]:
                print(f"\n[TALUKA] {taluka['label']} ({len(taluka['villages'])} villages)")
                
                for village in taluka["villages"]:
                    if max_villages and villages_count >= max_villages:
                        print(f"\n[INFO] Reached max villages limit ({max_villages})")
                        break
                    
                    try:
                        match = self._search_village(
                            page, district_code, district["label"],
                            taluka, village, search_type, search_value
                        )
                        
                        result["villages_searched"] += 1
                        villages_count += 1
                        
                        if match and match.get("found"):
                            result["matches"].append(match)
                            print(f"   ✓ FOUND: {village['label']} - Survey {match.get('survey', '')}")
                            if match.get("files", {}).get("html"):
                                print(f"      📄 {match['files']['html']}")
                        
                    except Exception as e:
                        result["errors"].append({
                            "taluka": taluka["label"],
                            "village": village["label"],
                            "error": str(e)
                        })
                        print(f"   ✗ Error in {village['label']}: {e}")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                
                result["talukas_searched"] += 1
                
                if max_villages and villages_count >= max_villages:
                    break
        
        finally:
            context.close()
            browser.close()
            playwright.stop()
        
        result["completed_at"] = datetime.now().isoformat()
        result["total_matches"] = len(result["matches"])
        
        # Save summary results
        if save_results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.output_dir, f"global_search_{district_code}_{timestamp}.json")
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n✅ Summary saved to: {filename}")
        
        return result
    
    def _search_village(
        self,
        page,
        district_code: str,
        district_name: str,
        taluka: Dict,
        village: Dict,
        search_type: str,
        search_value: str
    ) -> Optional[Dict]:
        """Search a single village for the target survey"""
        
        # Navigate fresh each time (more reliable)
        page.goto(self.BASE_URL)
        page.wait_for_load_state("networkidle", timeout=15000)
        
        # Select VF-7
        page.locator(self.SELECTORS["record_type"]).select_option("1")
        time.sleep(0.5)
        
        # Select district
        page.locator(self.SELECTORS["district"]).select_option(district_code)
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # Select taluka
        page.locator(self.SELECTORS["taluka"]).select_option(taluka["value"])
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # Select village
        page.locator(self.SELECTORS["village"]).select_option(village["value"])
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # Get survey options
        survey_options = []
        for opt in page.locator(self.SELECTORS["survey_no"]).locator("option").all():
            value = opt.get_attribute("value")
            text = opt.text_content().strip()
            if value and value not in ["0", "-1", ""]:
                survey_options.append({"value": value, "text": text})
        
        if not survey_options:
            return {"found": False, "village": village["label"], "reason": "no_surveys"}
        
        # Find matching survey
        if search_type == "survey":
            match = next(
                (o for o in survey_options if search_value in o["text"] or o["text"] == search_value),
                None
            )
            
            if not match:
                return {"found": False, "village": village["label"]}
            
            # Select survey
            page.locator(self.SELECTORS["survey_no"]).select_option(match["value"])
            time.sleep(0.5)
            
            # Solve captcha and submit (same as single scraper)
            for attempt in range(3):
                try:
                    # Wait for captcha image to be visible
                    captcha_loc = page.locator(self.SELECTORS["captcha_image"])
                    captcha_loc.wait_for(state="visible", timeout=10000)
                    time.sleep(0.5)  # Let image fully load
                    
                    # Get captcha image
                    captcha_img = captcha_loc.screenshot(timeout=10000)
                    captcha_text = self.captcha_solver.solve(captcha_img)
                    
                    if not captcha_text:
                        continue
                    
                    # Enter and submit
                    page.locator(self.SELECTORS["captcha_input"]).fill(captcha_text)
                    page.locator(self.SELECTORS["captcha_input"]).press("Enter")
                    
                    time.sleep(2)
                    page.wait_for_load_state("networkidle", timeout=10000)
                    
                    # Check for results
                    content = page.content()
                    if "ખાતા નંબર" in content or "Khata" in content:
                        # Extract data using same method as single scraper
                        raw_result = self._extract_raw_data(
                            page, district_code, district_name,
                            taluka, village, match["text"]
                        )
                        
                        # Structure data using VF7Extractor (same as single scraper)
                        structured_data = self.extractor.extract_from_scrape_result(raw_result)
                        
                        # Generate HTML report
                        html = self.report_generator.generate_html(structured_data)
                        
                        # Save files
                        files = self._save_results(
                            raw_result, structured_data, html,
                            district_code, village["label"]
                        )
                        
                        return {
                            "found": True,
                            "district": district_code,
                            "district_name": district_name,
                            "taluka": taluka["label"],
                            "taluka_code": taluka["value"],
                            "village": village["label"],
                            "village_code": village["value"],
                            "survey": match["text"],
                            "structured": structured_data,
                            "files": files
                        }
                    
                    # Refresh captcha for retry
                    try:
                        page.locator("text=Refresh Code").click()
                        time.sleep(0.5)
                    except:
                        pass
                        
                except Exception as e:
                    continue
        
        return {"found": False, "village": village["label"]}
    
    def _extract_raw_data(
        self, page, district_code: str, district_name: str,
        taluka: Dict, village: Dict, survey: str
    ) -> Dict:
        """Extract raw data from page - same as AnyRORScraper.extract_data()"""
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "tables": [],
            "property_details": {},
            "full_page_text": "",
            "success": False
        }
        
        # Extract tables
        tables = page.locator("table").all()
        for i, table in enumerate(tables):
            text = table.text_content()
            if len(text.strip()) > 200:
                data["tables"].append({"index": i, "text": text.strip()})
        
        # Get full page text
        try:
            content_area = page.locator("#ContentPlaceHolder1, .content, main, body").first
            if content_area.count() > 0:
                data["full_page_text"] = content_area.text_content()
        except:
            pass
        
        # Extract labeled values from page text
        if data["full_page_text"]:
            self._extract_labeled_values(data)
        
        if data["tables"] or data["property_details"]:
            data["success"] = True
        
        # Build raw result in same format as single scraper
        raw_result = {
            "district": {"value": district_code, "text": district_name},
            "taluka": {"value": taluka["value"], "text": taluka["label"]},
            "village": {"value": village["value"], "text": village["label"]},
            "survey": {"value": survey, "text": survey},
            "data": data
        }
        
        return raw_result
    
    def _extract_labeled_values(self, data: dict):
        """Extract values from labeled text patterns - same as single scraper"""
        text = data.get("full_page_text", "")
        if not text:
            return
        
        patterns = {
            "data_status_time": r'તા\.?\s*([0-9૦-૯/]+\s*[0-9૦-૯:]+)\s*ની સ્થિતિએ',
            "upin": r'UPIN[^:]*[:：\)]\s*([A-Z]{2}[0-9]+)',
            "old_survey_number": r'જુનો સરવે નંબર[^:]*[:：]\s*([^\n]+)',
            "tenure": r'સત્તાપ્રકાર[^:]*[:：]\s*([^\n]+)',
            "land_use": r'જમીનનો ઉપયોગ[^:]*[:：]\s*([^\n]+)',
            "farm_name": r'ખેતરનું નામ[^:]*[:：]\s*([^\n]+)',
            "remarks": r'રીમાર્ક્સ[^:]*[:：]\s*([^\n]+)',
            "total_area": r'કુલ ક્ષેત્રફળ[^:]*:\s*\n?\s*\n?\s*\n?\s*\n?\s*([૦-૯0-9]+-[૦-૯0-9]+-[૦-૯0-9]+)',
            "assessment_tax": r'કુલ આકાર[^:]*:\s*\n?\s*\n?\s*\n?\s*\n?\s*([૦-૯0-9\.]+)',
        }
        
        for field, pattern in patterns.items():
            if field not in data["property_details"] or not data["property_details"][field]:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    value = match.group(1).strip()
                    if value and value != '----' and value != '-':
                        data["property_details"][field] = value
    
    def _save_results(
        self, raw_result: Dict, structured_data: Dict, html: str,
        district_code: str, village_name: str
    ) -> Dict:
        """Save raw, structured JSON and HTML report"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_village = re.sub(r'[^\w\s-]', '', village_name)[:20].strip().replace(' ', '_')
        base_name = f"vf7_{district_code}_{safe_village}_{timestamp}"
        
        # Save raw
        raw_path = os.path.join(self.output_dir, f"{base_name}_raw.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_result, f, ensure_ascii=False, indent=2)
        
        # Save structured
        structured_path = os.path.join(self.output_dir, f"{base_name}.json")
        with open(structured_path, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)
        
        # Save HTML report
        html_path = os.path.join(self.output_dir, f"{base_name}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        return {
            "raw": raw_path,
            "structured": structured_path,
            "html": html_path
        }


def main():
    parser = argparse.ArgumentParser(
        description="Gujarat AnyROR Global Zone Search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python global_search.py --district "કચ્છ" --survey "123"
  python global_search.py --district-code 01 --survey "456" --max-villages 50
  python global_search.py --list-districts
        """
    )
    
    parser.add_argument("--district", "-d", help="District name (Gujarati)")
    parser.add_argument("--district-code", "-c", help="District code (01-34)")
    parser.add_argument("--survey", "-s", help="Survey number to search")
    parser.add_argument("--max-villages", "-m", type=int, help="Max villages to search (for testing)")
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory for reports (default: output)")
    parser.add_argument("--list-districts", "-l", action="store_true", help="List all districts")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", dest="headless", action="store_false")
    
    args = parser.parse_args()
    
    if args.list_districts:
        print("\nGujarat Districts:")
        print("-" * 50)
        for d in GUJARAT_DATA["districts"]:
            talukas = len(d["talukas"])
            villages = sum(len(t["villages"]) for t in d["talukas"])
            print(f"  {d['value']}: {d['label']} ({talukas} talukas, {villages} villages)")
        return
    
    if not args.survey:
        parser.error("--survey is required")
    
    # Get district code
    district_code = args.district_code
    if args.district:
        district = DISTRICT_BY_NAME.get(args.district)
        if not district:
            # Try partial match
            for name, d in DISTRICT_BY_NAME.items():
                if args.district.lower() in name.lower():
                    district = d
                    break
        if district:
            district_code = district["value"]
        else:
            print(f"District '{args.district}' not found. Use --list-districts to see options.")
            return
    
    if not district_code:
        parser.error("--district or --district-code is required")
    
    # Run search
    searcher = GlobalZoneSearch(headless=args.headless, output_dir=args.output_dir)
    result = searcher.search_district(
        district_code=district_code,
        search_value=args.survey,
        max_villages=args.max_villages
    )
    
    # Summary
    print(f"\n{'='*70}")
    print("SEARCH COMPLETE")
    print(f"{'='*70}")
    print(f"District: {result['district']['name']}")
    print(f"Talukas searched: {result['talukas_searched']}")
    print(f"Villages searched: {result['villages_searched']}")
    print(f"Matches found: {result['total_matches']}")
    print(f"Errors: {len(result['errors'])}")
    
    if result["matches"]:
        print(f"\nMatches:")
        for m in result["matches"]:
            print(f"  - {m['taluka']} > {m['village']} > Survey {m['survey']}")
            if m.get("files", {}).get("html"):
                print(f"    📄 {m['files']['html']}")


if __name__ == "__main__":
    main()
