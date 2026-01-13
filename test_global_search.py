"""
Local Test - Global Search with Full Report Generation
Tests on 5 villages only before scaling up

Run: python test_global_search.py
"""

import os
import sys
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# Import existing modules
from captcha_solver import CaptchaSolver
from vf7_extractor import VF7Extractor

# Config
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4")

# Load Gujarat data
with open("gujarat-anyror-complete.json", "r", encoding="utf-8") as f:
    GUJARAT_DATA = json.load(f)


class LocalGlobalSearchTest:
    """Test global search on small scale"""
    
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
        self.extractor = VF7Extractor()
        self.results = []
    
    def run_test(self, num_villages: int = 5):
        """Run test on limited villages"""
        
        # Pick first district, first taluka
        district = GUJARAT_DATA["districts"][0]  # કચ્છ
        taluka = district["talukas"][0]  # લખપત
        villages = taluka["villages"][:num_villages]
        
        print(f"\n{'='*60}")
        print(f"LOCAL TEST - Global Search")
        print(f"{'='*60}")
        print(f"District: {district['label']} ({district['value']})")
        print(f"Taluka: {taluka['label']} ({taluka['value']})")
        print(f"Testing {num_villages} villages: {[v['label'].split(' - ')[0] for v in villages]}")
        print(f"{'='*60}\n")
        
        results = {
            "test_info": {
                "district": district["label"],
                "taluka": taluka["label"],
                "villages_tested": num_villages,
                "started_at": datetime.now().isoformat()
            },
            "village_results": [],
            "all_surveys_found": [],
            "errors": []
        }
        
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=False)  # Show browser for testing
        context = browser.new_context()
        page = context.new_page()
        page.on("dialog", lambda d: d.accept())
        
        try:
            for i, village in enumerate(villages):
                print(f"\n[{i+1}/{num_villages}] Village: {village['label']}")
                
                try:
                    village_data = self._scrape_village(
                        page, 
                        district["value"], 
                        taluka["value"], 
                        village
                    )
                    results["village_results"].append(village_data)
                    
                    if village_data.get("surveys"):
                        print(f"   ✓ Found {len(village_data['surveys'])} surveys")
                        results["all_surveys_found"].extend(village_data["surveys"])
                    else:
                        print(f"   - No surveys or error")
                        
                except Exception as e:
                    print(f"   ✗ Error: {e}")
                    results["errors"].append({
                        "village": village["label"],
                        "error": str(e)
                    })
                
                time.sleep(1)  # Be nice to the server
        
        finally:
            context.close()
            browser.close()
            playwright.stop()
        
        results["test_info"]["completed_at"] = datetime.now().isoformat()
        results["test_info"]["total_surveys"] = len(results["all_surveys_found"])
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_results_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # Generate HTML report
        self._generate_report(results, f"test_report_{timestamp}.html")
        
        # Print summary
        print(f"\n{'='*60}")
        print("TEST COMPLETE")
        print(f"{'='*60}")
        print(f"Villages tested: {num_villages}")
        print(f"Total surveys found: {len(results['all_surveys_found'])}")
        print(f"Errors: {len(results['errors'])}")
        print(f"\nResults saved: {filename}")
        print(f"Report saved: test_report_{timestamp}.html")
        
        return results
    
    def _scrape_village(self, page, district_code: str, taluka_code: str, village: dict) -> dict:
        """Scrape all surveys in a village (just list them, don't fetch details)"""
        
        result = {
            "village": village["label"],
            "village_code": village["value"],
            "surveys": [],
            "sample_record": None
        }
        
        # Navigate
        page.goto(self.BASE_URL)
        page.wait_for_load_state("networkidle", timeout=15000)
        
        # Select VF-7
        page.locator(self.SELECTORS["record_type"]).select_option("1")
        time.sleep(0.5)
        
        # Select location
        page.locator(self.SELECTORS["district"]).select_option(district_code)
        page.wait_for_load_state("networkidle", timeout=10000)
        
        page.locator(self.SELECTORS["taluka"]).select_option(taluka_code)
        page.wait_for_load_state("networkidle", timeout=10000)
        
        page.locator(self.SELECTORS["village"]).select_option(village["value"])
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # Get all survey numbers
        for opt in page.locator(self.SELECTORS["survey_no"]).locator("option").all():
            value = opt.get_attribute("value")
            text = opt.text_content().strip()
            if value and value not in ["0", "-1", ""] and "પસંદ" not in text:
                result["surveys"].append({"value": value, "text": text})
        
        # Fetch one sample record (first survey)
        if result["surveys"]:
            sample = self._fetch_record(page, result["surveys"][0])
            if sample:
                result["sample_record"] = sample
        
        return result
    
    def _fetch_record(self, page, survey: dict) -> dict:
        """Fetch a single VF-7 record"""
        
        try:
            # Select survey
            page.locator(self.SELECTORS["survey_no"]).select_option(survey["value"])
            time.sleep(0.5)
            
            # Solve captcha
            for attempt in range(2):
                captcha_img = page.locator(self.SELECTORS["captcha_image"]).screenshot()
                captcha_text = self.captcha_solver.solve(captcha_img)
                
                if not captcha_text:
                    continue
                
                page.locator(self.SELECTORS["captcha_input"]).fill(captcha_text)
                page.locator(self.SELECTORS["captcha_input"]).press("Enter")
                
                time.sleep(2)
                page.wait_for_load_state("networkidle", timeout=10000)
                
                # Check for results
                content = page.content()
                if "ખાતા નંબર" in content:
                    # Extract data
                    data = {"survey": survey["text"], "tables": []}
                    
                    tables = page.locator("table").all()
                    for table in tables:
                        text = table.text_content()
                        if len(text.strip()) > 200:
                            data["tables"].append(text.strip()[:2000])
                    
                    # Take screenshot
                    page.screenshot(path=f"sample_record.png", full_page=True)
                    
                    return data
                
                # Refresh captcha
                try:
                    page.locator("text=Refresh Code").click()
                    time.sleep(0.5)
                except:
                    pass
            
            return None
            
        except Exception as e:
            print(f"      Error fetching record: {e}")
            return None
    
    def _generate_report(self, results: dict, filename: str):
        """Generate HTML report"""
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Global Search Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .summary {{ background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .summary span {{ font-weight: bold; color: #2980b9; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ border: 1px solid #bdc3c7; padding: 10px; text-align: left; }}
        th {{ background: #3498db; color: white; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        .success {{ color: #27ae60; }}
        .error {{ color: #e74c3c; }}
        .village-card {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .village-card h3 {{ margin: 0 0 10px 0; color: #2c3e50; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Global Search Test Report</h1>
        
        <div class="summary">
            <p><span>District:</span> {results['test_info']['district']}</p>
            <p><span>Taluka:</span> {results['test_info']['taluka']}</p>
            <p><span>Villages Tested:</span> {results['test_info']['villages_tested']}</p>
            <p><span>Total Surveys Found:</span> {results['test_info'].get('total_surveys', 0)}</p>
            <p><span>Errors:</span> {len(results['errors'])}</p>
        </div>
        
        <h2>📊 Village Results</h2>
"""
        
        for v in results["village_results"]:
            survey_count = len(v.get("surveys", []))
            status = "success" if survey_count > 0 else "error"
            
            html += f"""
        <div class="village-card">
            <h3>{v['village']}</h3>
            <p class="{status}">Surveys: {survey_count}</p>
"""
            
            if v.get("surveys"):
                html += "<table><tr><th>#</th><th>Survey Number</th></tr>"
                for i, s in enumerate(v["surveys"][:10]):  # Show first 10
                    html += f"<tr><td>{i+1}</td><td>{s['text']}</td></tr>"
                if len(v["surveys"]) > 10:
                    html += f"<tr><td colspan='2'>... and {len(v['surveys'])-10} more</td></tr>"
                html += "</table>"
            
            if v.get("sample_record"):
                html += f"<p><strong>Sample Record:</strong> {v['sample_record'].get('survey', 'N/A')}</p>"
            
            html += "</div>"
        
        if results["errors"]:
            html += "<h2>❌ Errors</h2><ul>"
            for e in results["errors"]:
                html += f"<li><strong>{e['village']}:</strong> {e['error']}</li>"
            html += "</ul>"
        
        html += """
    </div>
</body>
</html>"""
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)


def main():
    print("\n" + "="*60)
    print("GLOBAL SEARCH - LOCAL TEST")
    print("Testing on 5 villages before scaling up")
    print("="*60)
    
    test = LocalGlobalSearchTest()
    results = test.run_test(num_villages=5)
    
    print("\n✅ Test complete! Check the HTML report for details.")
    print("\nNext steps:")
    print("  1. Review the report")
    print("  2. If working, scale up: python global_search.py --district-code 01 --survey '1'")
    print("  3. Then deploy to GCP e2-micro")


if __name__ == "__main__":
    main()
