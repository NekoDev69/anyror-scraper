"""
VM Bulk Scraper - API Version
Uses AnyRORScraper class directly (same as local)
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
    
    # Use AnyRORScraper - same as local!
    scraper = AnyRORScraper(headless=True)
    
    try:
        scraper.start()
        log("Browser ready")
        
        for taluka in talukas_to_process:
            log(f"Processing taluka: {taluka['label']} ({len(taluka['villages'])} villages)")
            
            # Get village codes for this taluka
            village_codes = [v["value"] for v in taluka["villages"]]
            
            # Use the batch scrape method from AnyRORScraper
            results = scraper.scrape_multiple_villages(
                district_code=district_code,
                taluka_code=taluka["value"],
                village_codes=village_codes,
                survey_filter=survey_filter if survey_filter else None,
                max_captcha_attempts=3
            )
            
            # Process results
            for result in results:
                stats["done"] += 1
                
                if result.get("success"):
                    stats["success"] += 1
                    log(f"✅ {result.get('village_name', result.get('village_code', ''))[:30]} - {result.get('survey', '')}")
                    
                    # Save result
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{district_code}_{taluka['value']}_{result.get('village_code', '')}_{ts}"
                    
                    full_result = {
                        "district": {"value": district_code, "label": district["label"]},
                        "taluka": {"value": taluka["value"], "label": taluka["label"]},
                        "village": {"value": result.get("village_code"), "label": result.get("village_name")},
                        "survey": {"text": result.get("survey")},
                        "data": result.get("data"),
                        "success": True
                    }
                    
                    with open(f"{OUTPUT_DIR}/raw/{filename}.json", 'w', encoding='utf-8') as f:
                        json.dump(full_result, f, ensure_ascii=False, indent=2)
                else:
                    reason = result.get("reason", result.get("error", "unknown"))
                    log(f"❌ {result.get('village_name', result.get('village_code', ''))[:30]} - {reason}")
                
                progress()
        
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
