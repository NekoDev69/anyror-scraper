"""
VM Bulk Scraper - API Version
Uses AnyRORScraper class directly with real-time progress updates
"""

import os
import sys
import json
import time
from datetime import datetime

# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anyror_scraper import AnyRORScraper

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")

os.makedirs(f"{OUTPUT_DIR}/raw", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/structured", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/reports", exist_ok=True)

stats = {"total": 0, "done": 0, "success": 0}


def log(msg: str):
    print(f"LOG:{msg}", flush=True)


def progress():
    print(f"PROGRESS:{stats['total']}:{stats['done']}:{stats['success']}", flush=True)


def scrape_village(scraper: AnyRORScraper, village_code: str, village_name: str, survey_filter: str = None, max_captcha_attempts: int = 3):
    """Scrape a single village - assumes district/taluka already selected"""
    try:
        # Select village
        scraper.page.locator(scraper.SELECTORS["village"]).select_option(village_code)
        scraper.wait_for_page()
        
        # Get survey options
        surveys = scraper.get_options(scraper.SELECTORS["survey_no"])
        if survey_filter:
            surveys = [s for s in surveys if survey_filter in s["text"]]
        
        if not surveys:
            return {"village_code": village_code, "village_name": village_name, "success": False, "reason": "no_surveys"}
        
        # Select first survey
        survey = surveys[0]
        scraper.page.locator(scraper.SELECTORS["survey_no"]).select_option(survey["value"])
        time.sleep(0.5)
        
        # Try captcha
        for attempt in range(max_captcha_attempts):
            if scraper.solve_and_enter_captcha():
                scraper.submit()
                data = scraper.extract_data()
                
                if data["success"]:
                    return {
                        "village_code": village_code,
                        "village_name": village_name,
                        "survey": survey["text"],
                        "success": True,
                        "data": data
                    }
            
            # Refresh captcha for retry
            if attempt < max_captcha_attempts - 1:
                try:
                    scraper.page.locator("text=Refresh Code").click()
                    time.sleep(0.5)
                except:
                    pass
        
        return {"village_code": village_code, "village_name": village_name, "success": False, "reason": "captcha_failed"}
        
    except Exception as e:
        return {"village_code": village_code, "village_name": village_name, "success": False, "error": str(e)}


def main():
    global stats
    
    district_code = os.environ.get("DISTRICT_CODE", "")
    taluka_code = os.environ.get("TALUKA_CODE", "")
    survey_filter = os.environ.get("SURVEY_FILTER", "")
    
    if not district_code:
        log("ERROR: DISTRICT_CODE not set")
        sys.exit(1)
    
    # Load data
    with open("gujarat-anyror-complete.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Find district
    district = next((d for d in data["districts"] if d["value"] == district_code), None)
    if not district:
        log(f"ERROR: District {district_code} not found")
        sys.exit(1)
    
    # Build task list
    talukas_to_process = []
    for taluka in district["talukas"]:
        if taluka_code and taluka["value"] != taluka_code:
            continue
        talukas_to_process.append(taluka)
    
    # Count total villages
    total_villages = sum(len(t["villages"]) for t in talukas_to_process)
    stats["total"] = total_villages
    progress()
    
    log(f"Starting: {len(talukas_to_process)} talukas, {total_villages} villages")
    log(f"District: {district['label']}")
    if survey_filter:
        log(f"Survey filter: {survey_filter}")
    
    # Use AnyRORScraper
    scraper = AnyRORScraper(headless=True)
    
    try:
        scraper.start()
        log("Browser started")
        
        for taluka in talukas_to_process:
            log(f"Taluka: {taluka['label']} ({len(taluka['villages'])} villages)")
            
            # Navigate and setup session for this taluka
            scraper.navigate()
            scraper.select_vf7()
            
            # Select district
            scraper.page.locator(scraper.SELECTORS["district"]).select_option(district_code)
            scraper.wait_for_page()
            
            # Select taluka
            scraper.page.locator(scraper.SELECTORS["taluka"]).select_option(taluka["value"])
            scraper.wait_for_page()
            
            log(f"Session ready for {taluka['label']}")
            
            # Process each village with real-time updates
            for village in taluka["villages"]:
                village_code = village["value"]
                village_name = village["label"]
                
                log(f"[{stats['done']+1}/{stats['total']}] {village_name[:35]}")
                
                result = scrape_village(scraper, village_code, village_name, survey_filter)
                
                stats["done"] += 1
                
                if result.get("success"):
                    stats["success"] += 1
                    log(f"✅ {village_name[:30]} - {result.get('survey', '')}")
                    
                    # Save result
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{district_code}_{taluka['value']}_{village_code}_{ts}"
                    
                    full_result = {
                        "district": {"value": district_code, "label": district["label"]},
                        "taluka": {"value": taluka["value"], "label": taluka["label"]},
                        "village": {"value": village_code, "label": village_name},
                        "survey": {"text": result.get("survey")},
                        "data": result.get("data"),
                        "success": True
                    }
                    
                    with open(f"{OUTPUT_DIR}/raw/{filename}.json", 'w', encoding='utf-8') as f:
                        json.dump(full_result, f, ensure_ascii=False, indent=2)
                else:
                    reason = result.get("reason", result.get("error", "unknown"))
                    log(f"❌ {village_name[:30]} - {reason}")
                
                progress()
                
                # Go back to form for next village (preserves district/taluka)
                if not scraper.go_back_to_form():
                    # Reset session if back fails
                    log("Resetting session...")
                    scraper.navigate()
                    scraper.select_vf7()
                    scraper.page.locator(scraper.SELECTORS["district"]).select_option(district_code)
                    scraper.wait_for_page()
                    scraper.page.locator(scraper.SELECTORS["taluka"]).select_option(taluka["value"])
                    scraper.wait_for_page()
        
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()
    
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
                log(f"Report error for {filename}: {e}")
    except ImportError as e:
        log(f"Report generation skipped: {e}")


if __name__ == "__main__":
    main()
