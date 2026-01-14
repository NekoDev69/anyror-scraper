"""
VM Bulk Scraper - API Version
Outputs progress in format readable by vm_api.py
"""

import os
import sys
import json
import time
import re
import base64
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright, Browser, Page
from google import genai

# ============== CONFIG ==============
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4")
NUM_PARALLEL_CONTEXTS = int(os.environ.get("NUM_CONTEXTS", "4"))
MAX_CAPTCHA_ATTEMPTS = 3
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")
JOB_ID = os.environ.get("JOB_ID", "local")

# ============== SETUP ==============
os.makedirs(f"{OUTPUT_DIR}/raw", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/structured", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/reports", exist_ok=True)

client = genai.Client(api_key=GEMINI_API_KEY)
stats_lock = threading.Lock()
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
    with stats_lock:
        print(f"PROGRESS:{stats['total']}:{stats['done']}:{stats['success']}", flush=True)


def solve_captcha(image_bytes: bytes) -> str:
    """Solve captcha using Gemini"""
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


def wait_for_page(page: Page):
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    time.sleep(0.5)


def get_options(page: Page, selector: str) -> list:
    options = []
    for opt in page.locator(selector).locator("option").all():
        value = opt.get_attribute("value")
        text = opt.text_content().strip()
        if value and value not in ["0", "-1", ""] and "પસંદ" not in text:
            options.append({"value": value, "text": text})
    return options


def go_back_to_form(page: Page) -> bool:
    try:
        page.get_by_role("link", name="RURAL LAND RECORD").click()
        wait_for_page(page)
        return True
    except:
        return False


def extract_data(page: Page) -> dict:
    data = {"timestamp": datetime.now().isoformat(), "tables": [], "property_details": {}, "full_page_text": "", "success": False}
    
    tables = page.locator("table").all()
    for i, table in enumerate(tables):
        text = table.text_content()
        if len(text.strip()) > 200:
            data["tables"].append({"index": i, "text": text.strip()})
    
    try:
        data["full_page_text"] = page.locator("body").text_content()
    except:
        pass
    
    text = data.get("full_page_text", "")
    
    match = re.search(r'તા\.?\s*([0-9૦-૯/]+\s*[0-9૦-૯:]+)\s*ની સ્થિતિએ', text)
    if match:
        data["property_details"]["data_status_time"] = match.group(1)
    
    match = re.search(r'UPIN[^:]*[:：\)]\s*([A-Z]{2}[0-9]+)', text)
    if match:
        data["property_details"]["upin"] = match.group(1)
    
    if data["tables"]:
        data["success"] = True
    
    return data


def scrape_taluka(ctx_id: int, page: Page, district: dict, taluka: dict, survey_filter: str = None) -> list:
    results = []
    
    log(f"[CTX-{ctx_id}] Setting up: {district['label']} > {taluka['label']}")
    
    page.goto(URL)
    wait_for_page(page)
    page.locator(SELECTORS["record_type"]).select_option("1")
    time.sleep(0.5)
    page.locator(SELECTORS["district"]).select_option(district["value"])
    wait_for_page(page)
    page.locator(SELECTORS["taluka"]).select_option(taluka["value"])
    wait_for_page(page)
    
    for village in taluka["villages"]:
        try:
            page.locator(SELECTORS["village"]).select_option(village["value"])
            wait_for_page(page)
            
            surveys = get_options(page, SELECTORS["survey_no"])
            if survey_filter:
                surveys = [s for s in surveys if survey_filter in s["text"]]
            
            if not surveys:
                with stats_lock:
                    stats["done"] += 1
                progress()
                continue
            
            survey = surveys[0]
            page.locator(SELECTORS["survey_no"]).select_option(survey["value"])
            time.sleep(0.5)
            
            success = False
            data = None
            
            for attempt in range(MAX_CAPTCHA_ATTEMPTS):
                try:
                    captcha_img = page.locator(SELECTORS["captcha_image"]).screenshot()
                    captcha_text = solve_captcha(captcha_img)
                    
                    if not captcha_text:
                        continue
                    
                    page.locator(SELECTORS["captcha_input"]).fill(captcha_text)
                    page.locator(SELECTORS["captcha_input"]).press("Enter")
                    time.sleep(2)
                    wait_for_page(page)
                    
                    if "ખાતા નંબર" in page.content():
                        data = extract_data(page)
                        success = True
                        break
                    
                    try:
                        page.locator("text=Refresh Code").click()
                        time.sleep(0.5)
                    except:
                        pass
                except:
                    pass
            
            with stats_lock:
                stats["done"] += 1
                if success:
                    stats["success"] += 1
            
            if success:
                log(f"[CTX-{ctx_id}] ✅ {village['label'][:25]} - {survey['text']}")
                
                result = {
                    "district": district, "taluka": taluka, "village": village,
                    "survey": survey, "data": data, "success": True
                }
                results.append(result)
                
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{district['value']}_{taluka['value']}_{village['value']}_{ts}"
                with open(f"{OUTPUT_DIR}/raw/{filename}.json", 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            else:
                log(f"[CTX-{ctx_id}] ❌ {village['label'][:25]}")
            
            progress()
            
            if not go_back_to_form(page):
                page.goto(URL)
                wait_for_page(page)
                page.locator(SELECTORS["record_type"]).select_option("1")
                time.sleep(0.5)
                page.locator(SELECTORS["district"]).select_option(district["value"])
                wait_for_page(page)
                page.locator(SELECTORS["taluka"]).select_option(taluka["value"])
                wait_for_page(page)
                
        except Exception as e:
            log(f"[CTX-{ctx_id}] ❌ {village['label'][:25]} - {str(e)[:30]}")
            with stats_lock:
                stats["done"] += 1
            progress()
            try:
                go_back_to_form(page)
            except:
                pass
    
    return results


def worker(ctx_id: int, browser: Browser, tasks: list, survey_filter: str = None) -> list:
    all_results = []
    
    context = browser.new_context()
    page = context.new_page()
    page.on("dialog", lambda d: d.accept())
    
    for task in tasks:
        results = scrape_taluka(ctx_id, page, task["district"], task["taluka"], survey_filter)
        all_results.extend(results)
    
    context.close()
    return all_results


def generate_reports():
    """Generate structured data and HTML reports"""
    try:
        from vf7_extractor import VF7Extractor
        from vf7_report import VF7ReportGenerator
        
        extractor = VF7Extractor()
        reporter = VF7ReportGenerator()
        
        raw_files = [f for f in os.listdir(f"{OUTPUT_DIR}/raw") if f.endswith('.json')]
        
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
            except:
                pass
    except ImportError:
        log("Report generation skipped (missing modules)")


def main():
    global stats
    
    district_filter = os.environ.get("DISTRICT_CODE", "")
    taluka_filter = os.environ.get("TALUKA_CODE", "")
    survey_filter = os.environ.get("SURVEY_FILTER", "")
    
    with open("gujarat-anyror-complete.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tasks = []
    total_villages = 0
    
    for district in data["districts"]:
        if district_filter and district["value"] != district_filter:
            continue
        
        for taluka in district["talukas"]:
            if taluka_filter and taluka["value"] != taluka_filter:
                continue
            
            tasks.append({
                "district": {"value": district["value"], "label": district["label"]},
                "taluka": {"value": taluka["value"], "label": taluka["label"], "villages": taluka["villages"]}
            })
            total_villages += len(taluka["villages"])
    
    if not tasks:
        log("No tasks found")
        sys.exit(1)
    
    stats["total"] = total_villages
    progress()
    
    log(f"Starting: {len(tasks)} talukas, {total_villages} villages")
    
    task_chunks = [[] for _ in range(NUM_PARALLEL_CONTEXTS)]
    for i, task in enumerate(tasks):
        task_chunks[i % NUM_PARALLEL_CONTEXTS].append(task)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        
        with ThreadPoolExecutor(max_workers=NUM_PARALLEL_CONTEXTS) as executor:
            futures = []
            for ctx_id, chunk in enumerate(task_chunks):
                if chunk:
                    future = executor.submit(worker, ctx_id, browser, chunk, survey_filter)
                    futures.append(future)
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    log(f"Worker error: {e}")
        
        browser.close()
    
    generate_reports()
    log(f"Done: {stats['success']}/{stats['total']} successful")


if __name__ == "__main__":
    main()
