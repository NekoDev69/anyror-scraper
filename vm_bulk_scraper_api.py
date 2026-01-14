"""
VM Bulk Scraper - API Version (Single-threaded for stability)
Outputs progress in format readable by vm_api.py
"""

import os
import sys
import json
import time
import re
import base64
from datetime import datetime
from playwright.sync_api import sync_playwright
from google import genai

# ============== CONFIG ==============
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4")
MAX_CAPTCHA_ATTEMPTS = 3
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")

# ============== SETUP ==============
os.makedirs(f"{OUTPUT_DIR}/raw", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/structured", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/reports", exist_ok=True)

client = genai.Client(api_key=GEMINI_API_KEY)
stats = {"total": 0, "done": 0, "success": 0}

URL = "https://anyror.gujarat.gov.in/LandRecordRural.aspx"

SELECTORS = {
    "record_type": "#ContentPlaceHolder1_drpLandRecord",
    "district": "#ContentPlaceHolder1_ddlDistrict",
    "taluka": "#ContentPlaceHolder1_ddlTaluka",
    "village": "#ContentPlaceHolder1_ddlVillage",
    "survey_no": "#ContentPlaceHolder1_ddlSurveyNo",
    "captcha_input": "[placeholder='Enter Text Shown Above']",
    "captcha_image": "#ContentPlaceHolder1_imgCaptcha",
}


def log(msg: str):
    """Output log in API format"""
    print(f"LOG:{msg}", flush=True)


def progress():
    """Output progress in API format"""
    print(f"PROGRESS:{stats['total']}:{stats['done']}:{stats['success']}", flush=True)


def solve_captcha(image_bytes: bytes) -> str:
    """Solve captcha using Gemini"""
    try:
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[{
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                    {"text": "This is a CAPTCHA image. Read the numbers/letters shown. Return ONLY the plain digits and letters, nothing else."}
                ]
            }]
        )
        
        raw = response.text.strip()
        digit_map = {
            '₀':'0','₁':'1','₂':'2','₃':'3','₄':'4','₅':'5','₆':'6','₇':'7','₈':'8','₉':'9',
            '⁰':'0','¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9',
            'θ':'0','O':'0','o':'0'
        }
        cleaned = ""
        for c in raw:
            if c in digit_map:
                cleaned += digit_map[c]
            elif c.isascii() and c.isalnum():
                cleaned += c
        return cleaned
    except Exception as e:
        log(f"Captcha error: {e}")
        return ""


def wait_for_page(page):
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    time.sleep(0.5)


def get_options(page, selector: str) -> list:
    options = []
    try:
        for opt in page.locator(selector).locator("option").all():
            value = opt.get_attribute("value")
            text = opt.text_content().strip()
            if value and value not in ["0", "-1", ""] and "પસંદ" not in text:
                options.append({"value": value, "text": text})
    except:
        pass
    return options


def go_back_to_form(page) -> bool:
    """Click 'RURAL LAND RECORD' link to go back"""
    try:
        page.get_by_role("link", name="RURAL LAND RECORD").click()
        wait_for_page(page)
        return True
    except:
        return False


def extract_data(page) -> dict:
    data = {"timestamp": datetime.now().isoformat(), "tables": [], "property_details": {}, "full_page_text": "", "success": False}
    
    try:
        tables = page.locator("table").all()
        for i, table in enumerate(tables):
            text = table.text_content()
            if len(text.strip()) > 200:
                data["tables"].append({"index": i, "text": text.strip()})
    except:
        pass
    
    try:
        data["full_page_text"] = page.locator("body").text_content()
    except:
        pass
    
    if data["tables"]:
        data["success"] = True
    
    return data


def scrape_village(page, village, survey_filter=None):
    """Scrape a single village - assumes district/taluka already selected"""
    try:
        # Select village
        page.locator(SELECTORS["village"]).select_option(village["value"])
        wait_for_page(page)
        time.sleep(1)  # Extra wait for dropdown to populate
        
        # Get surveys
        surveys = get_options(page, SELECTORS["survey_no"])
        if survey_filter:
            surveys = [s for s in surveys if survey_filter in s["text"]]
        
        if not surveys:
            return {"success": False, "reason": "no_surveys"}
        
        # Select first survey
        survey = surveys[0]
        page.locator(SELECTORS["survey_no"]).select_option(survey["value"])
        time.sleep(1)  # Wait for captcha to load
        
        # Try captcha
        for attempt in range(MAX_CAPTCHA_ATTEMPTS):
            try:
                # Wait for captcha image to be visible
                captcha_locator = page.locator(SELECTORS["captcha_image"])
                captcha_locator.wait_for(state="visible", timeout=10000)
                time.sleep(0.5)  # Let image fully render
                
                captcha_img = captcha_locator.screenshot(timeout=10000)
                captcha_text = solve_captcha(captcha_img)
                
                if not captcha_text:
                    log(f"Empty captcha response, retrying...")
                    try:
                        page.locator("text=Refresh Code").click()
                        time.sleep(1)
                    except:
                        pass
                    continue
                
                page.locator(SELECTORS["captcha_input"]).fill(captcha_text)
                page.locator(SELECTORS["captcha_input"]).press("Enter")
                
                time.sleep(2)
                wait_for_page(page)
                
                content = page.content()
                if "ખાતા નંબર" in content or "Khata" in content:
                    data = extract_data(page)
                    return {"success": True, "survey": survey, "data": data}
                
                # Check for error message (wrong captcha)
                if "Invalid" in content or "ખોટો" in content:
                    log(f"Wrong captcha, refreshing...")
                
                # Refresh captcha
                try:
                    page.locator("text=Refresh Code").click()
                    time.sleep(1)
                except:
                    pass
            except Exception as e:
                log(f"Captcha attempt {attempt+1} error: {str(e)[:80]}")
                time.sleep(1)
        
        return {"success": False, "reason": "captcha_failed"}
        
    except Exception as e:
        return {"success": False, "error": str(e)[:100]}


def setup_session(page, district_code, taluka_code):
    """Setup browser session with district/taluka"""
    log(f"Setting up session: district={district_code}, taluka={taluka_code}")
    
    page.goto(URL)
    wait_for_page(page)
    
    # Select VF-7
    page.locator(SELECTORS["record_type"]).select_option("1")
    time.sleep(0.5)
    
    # Select district
    page.locator(SELECTORS["district"]).select_option(district_code)
    wait_for_page(page)
    
    # Select taluka
    page.locator(SELECTORS["taluka"]).select_option(taluka_code)
    wait_for_page(page)
    
    log("Session ready")


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
    
    # Start browser
    with sync_playwright() as p:
        log("Launching browser...")
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        
        context = browser.new_context()
        page = context.new_page()
        page.on("dialog", lambda d: d.accept())
        
        log("Browser ready")
        
        for taluka in talukas_to_process:
            log(f"Processing taluka: {taluka['label']} ({len(taluka['villages'])} villages)")
            
            # Setup session for this taluka
            try:
                setup_session(page, district_code, taluka["value"])
            except Exception as e:
                log(f"Setup failed: {e}")
                continue
            
            for village in taluka["villages"]:
                village_name = village["label"][:30]
                
                result = scrape_village(page, village, survey_filter)
                
                stats["done"] += 1
                
                if result.get("success"):
                    stats["success"] += 1
                    log(f"✅ {village_name} - {result['survey']['text']}")
                    
                    # Save result
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{district_code}_{taluka['value']}_{village['value']}_{ts}"
                    
                    full_result = {
                        "district": {"value": district_code, "label": district["label"]},
                        "taluka": {"value": taluka["value"], "label": taluka["label"]},
                        "village": village,
                        "survey": result["survey"],
                        "data": result["data"],
                        "success": True
                    }
                    
                    with open(f"{OUTPUT_DIR}/raw/{filename}.json", 'w', encoding='utf-8') as f:
                        json.dump(full_result, f, ensure_ascii=False, indent=2)
                else:
                    reason = result.get("reason", result.get("error", "unknown"))
                    log(f"❌ {village_name} - {reason}")
                
                progress()
                
                # Go back for next village
                if not go_back_to_form(page):
                    # Re-setup if back fails
                    try:
                        setup_session(page, district_code, taluka["value"])
                    except:
                        pass
        
        context.close()
        browser.close()
    
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
