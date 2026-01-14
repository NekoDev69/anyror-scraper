"""
VM Bulk Scraper - Parallel scraping with multiple browser contexts
Uses session reuse pattern for maximum speed
Generates structured data + HTML reports
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
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from google import genai

# ============== CONFIG ==============
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4")
NUM_PARALLEL_CONTEXTS = int(os.environ.get("NUM_CONTEXTS", "4"))
MAX_CAPTCHA_ATTEMPTS = 3
OUTPUT_DIR = "output"

# ============== SETUP ==============
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/raw", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/structured", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/reports", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/screenshots", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/debug", exist_ok=True)

client = genai.Client(api_key=GEMINI_API_KEY)
print_lock = threading.Lock()

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


def log(ctx_id: int, msg: str):
    """Thread-safe logging"""
    with print_lock:
        print(f"[CTX-{ctx_id}] {msg}", flush=True)


def solve_captcha(image_bytes: bytes) -> str:
    """Solve captcha using Gemini"""
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[{
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                {"text": "This is a CAPTCHA image. Read the numbers/letters shown. Return ONLY the plain digits and letters, nothing else. Use regular ASCII characters only (0-9, a-z, A-Z). No subscripts, superscripts, or special characters. Just the raw captcha text."}
            ]
        }]
    )
    
    raw = response.text.strip()
    
    # Clean
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
    """Wait for page to load"""
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    time.sleep(0.5)


def get_options(page: Page, selector: str) -> list:
    """Get dropdown options"""
    options = []
    for opt in page.locator(selector).locator("option").all():
        value = opt.get_attribute("value")
        text = opt.text_content().strip()
        if value and value not in ["0", "-1", ""] and "પસંદ" not in text and "select" not in text.lower():
            options.append({"value": value, "text": text})
    return options


def go_back_to_form(page: Page) -> bool:
    """Click 'RURAL LAND RECORD' link to go back - preserves district/taluka!"""
    try:
        page.get_by_role("link", name="RURAL LAND RECORD").click()
        wait_for_page(page)
        return True
    except:
        return False


def extract_data(page: Page) -> dict:
    """Extract results from page"""
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
    
    # Extract property details from page
    text = data.get("full_page_text", "")
    
    # Data status time
    match = re.search(r'તા\.?\s*([0-9૦-૯/]+\s*[0-9૦-૯:]+)\s*ની સ્થિતિએ', text)
    if match:
        data["property_details"]["data_status_time"] = match.group(1)
    
    # UPIN
    match = re.search(r'UPIN[^:]*[:：\)]\s*([A-Z]{2}[0-9]+)', text)
    if match:
        data["property_details"]["upin"] = match.group(1)
    
    # Total area
    match = re.search(r'કુલ ક્ષેત્રફળ[^:]*:\s*\n?\s*([૦-૯0-9]+-[૦-૯0-9]+-[૦-૯0-9]+)', text, re.DOTALL)
    if match:
        data["property_details"]["total_area"] = match.group(1)
    
    # Assessment tax
    match = re.search(r'કુલ આકાર[^:]*:\s*\n?\s*([૦-૯0-9\.]+)', text, re.DOTALL)
    if match:
        data["property_details"]["assessment_tax"] = match.group(1)
    
    # Tenure
    match = re.search(r'સત્તાપ્રકાર[^:]*[:：]\s*([^\n]+)', text)
    if match:
        data["property_details"]["tenure"] = match.group(1).strip()
    
    # Land use
    match = re.search(r'જમીનનો ઉપયોગ[^:]*[:：]\s*([^\n]+)', text)
    if match:
        data["property_details"]["land_use"] = match.group(1).strip()
    
    if data["tables"] or data["property_details"]:
        data["success"] = True
    
    return data



def scrape_taluka_villages(ctx_id: int, page: Page, district: dict, taluka: dict, survey_filter: str = None) -> list:
    """
    Scrape all villages in a taluka using session reuse.
    Sets up district/taluka ONCE, then iterates villages.
    """
    results = []
    
    log(ctx_id, f"Setting up: {district['label']} > {taluka['label']}")
    
    # Navigate and setup
    page.goto(URL)
    wait_for_page(page)
    
    # Select VF-7
    page.locator(SELECTORS["record_type"]).select_option("1")
    time.sleep(0.5)
    
    # Select district
    page.locator(SELECTORS["district"]).select_option(district["value"])
    wait_for_page(page)
    
    # Select taluka
    page.locator(SELECTORS["taluka"]).select_option(taluka["value"])
    wait_for_page(page)
    
    log(ctx_id, f"Session ready - {len(taluka['villages'])} villages")
    
    for v_idx, village in enumerate(taluka["villages"]):
        village_start = time.time()
        
        try:
            # Select village (district/taluka already set!)
            page.locator(SELECTORS["village"]).select_option(village["value"])
            wait_for_page(page)
            
            # Get surveys
            surveys = get_options(page, SELECTORS["survey_no"])
            if survey_filter:
                surveys = [s for s in surveys if survey_filter in s["text"]]
            
            if not surveys:
                log(ctx_id, f"  {village['label'][:25]} - no surveys")
                results.append({
                    "district": district, "taluka": taluka, "village": village,
                    "success": False, "reason": "no_surveys"
                })
                continue
            
            # Select first survey
            survey = surveys[0]
            page.locator(SELECTORS["survey_no"]).select_option(survey["value"])
            time.sleep(0.5)
            
            # Try captcha
            success = False
            data = None
            
            for attempt in range(MAX_CAPTCHA_ATTEMPTS):
                try:
                    # Get and solve captcha
                    captcha_img = page.locator(SELECTORS["captcha_image"]).screenshot()
                    captcha_text = solve_captcha(captcha_img)
                    
                    if not captcha_text:
                        continue
                    
                    # Enter and submit
                    page.locator(SELECTORS["captcha_input"]).fill(captcha_text)
                    page.locator(SELECTORS["captcha_input"]).press("Enter")
                    
                    time.sleep(2)
                    wait_for_page(page)
                    
                    # Check results
                    content = page.content()
                    if "ખાતા નંબર" in content or "Khata" in content:
                        data = extract_data(page)
                        success = True
                        break
                    
                    # Refresh captcha
                    try:
                        page.locator("text=Refresh Code").click()
                        time.sleep(0.5)
                    except:
                        pass
                        
                except Exception as e:
                    log(ctx_id, f"  Captcha attempt {attempt+1} error: {e}")
            
            elapsed = time.time() - village_start
            
            if success:
                log(ctx_id, f"  ✅ {village['label'][:25]} - {survey['text']} ({elapsed:.1f}s)")
                
                # Save results
                result = {
                    "district": district,
                    "taluka": taluka,
                    "village": village,
                    "survey": survey,
                    "data": data,
                    "success": True
                }
                results.append(result)
                
                # Save raw JSON
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{district['value']}_{taluka['value']}_{village['value']}_{ts}"
                
                with open(f"{OUTPUT_DIR}/raw/{filename}.json", 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                # Screenshot
                page.screenshot(path=f"{OUTPUT_DIR}/screenshots/{filename}.png", full_page=True)
            else:
                log(ctx_id, f"  ❌ {village['label'][:25]} - captcha failed ({elapsed:.1f}s)")
                results.append({
                    "district": district, "taluka": taluka, "village": village,
                    "success": False, "reason": "captcha_failed"
                })
            
            # GO BACK - key optimization!
            if not go_back_to_form(page):
                # Reset session if back fails
                page.goto(URL)
                wait_for_page(page)
                page.locator(SELECTORS["record_type"]).select_option("1")
                time.sleep(0.5)
                page.locator(SELECTORS["district"]).select_option(district["value"])
                wait_for_page(page)
                page.locator(SELECTORS["taluka"]).select_option(taluka["value"])
                wait_for_page(page)
                
        except Exception as e:
            log(ctx_id, f"  ❌ {village['label'][:25]} - error: {e}")
            results.append({
                "district": district, "taluka": taluka, "village": village,
                "success": False, "error": str(e)
            })
            # Try to recover
            try:
                go_back_to_form(page)
            except:
                pass
    
    return results


def worker(ctx_id: int, browser: Browser, tasks: list, survey_filter: str = None) -> list:
    """Worker thread - processes assigned talukas"""
    all_results = []
    
    context = browser.new_context()
    page = context.new_page()
    page.on("dialog", lambda d: d.accept())
    
    log(ctx_id, f"Started - {len(tasks)} talukas assigned")
    
    for task in tasks:
        district = task["district"]
        taluka = task["taluka"]
        
        results = scrape_taluka_villages(ctx_id, page, district, taluka, survey_filter)
        all_results.extend(results)
    
    context.close()
    log(ctx_id, f"Done - {len(all_results)} villages processed")
    
    return all_results



def generate_reports():
    """Generate structured data and HTML reports from raw files"""
    from vf7_extractor import VF7Extractor
    from vf7_report import VF7ReportGenerator
    
    extractor = VF7Extractor()
    reporter = VF7ReportGenerator()
    
    raw_files = [f for f in os.listdir(f"{OUTPUT_DIR}/raw") if f.endswith('.json')]
    
    print(f"\n📊 Generating reports for {len(raw_files)} records...")
    
    for filename in raw_files:
        try:
            with open(f"{OUTPUT_DIR}/raw/{filename}", 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            # Extract structured data
            structured = extractor.extract_from_scrape_result(raw_data)
            
            # Save structured JSON
            struct_file = filename.replace('.json', '_structured.json')
            with open(f"{OUTPUT_DIR}/structured/{struct_file}", 'w', encoding='utf-8') as f:
                json.dump(structured, f, ensure_ascii=False, indent=2)
            
            # Generate HTML report
            html = reporter.generate_html(structured)
            html_file = filename.replace('.json', '.html')
            with open(f"{OUTPUT_DIR}/reports/{html_file}", 'w', encoding='utf-8') as f:
                f.write(html)
                
        except Exception as e:
            print(f"  Error processing {filename}: {e}")
    
    print(f"✅ Reports generated in {OUTPUT_DIR}/reports/")


def generate_summary(all_results: list):
    """Generate summary report"""
    total = len(all_results)
    success = sum(1 for r in all_results if r.get("success"))
    failed = total - success
    
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_villages": total,
        "successful": success,
        "failed": failed,
        "success_rate": f"{(success/total*100):.1f}%" if total > 0 else "0%",
        "results": all_results
    }
    
    with open(f"{OUTPUT_DIR}/summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"SUMMARY")
    print(f"{'='*50}")
    print(f"Total villages: {total}")
    print(f"Successful: {success}")
    print(f"Failed: {failed}")
    print(f"Success rate: {summary['success_rate']}")
    print(f"Output: {OUTPUT_DIR}/")


def main():
    """Main entry point"""
    print("="*50)
    print("Gujarat AnyROR Bulk Scraper")
    print(f"Parallel contexts: {NUM_PARALLEL_CONTEXTS}")
    print("="*50)
    
    # Parse args
    district_filter = os.environ.get("DISTRICT_CODE", "")
    taluka_filter = os.environ.get("TALUKA_CODE", "")
    survey_filter = os.environ.get("SURVEY_FILTER", "")
    
    # Load data
    with open("gujarat-anyror-complete.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Build task list (district + taluka pairs)
    tasks = []
    
    for district in data["districts"]:
        if district_filter and district["value"] != district_filter:
            continue
        
        for taluka in district["talukas"]:
            if taluka_filter and taluka["value"] != taluka_filter:
                continue
            
            tasks.append({
                "district": {
                    "value": district["value"],
                    "label": district["label"]
                },
                "taluka": {
                    "value": taluka["value"],
                    "label": taluka["label"],
                    "villages": taluka["villages"]
                }
            })
    
    if not tasks:
        print("No tasks found. Check DISTRICT_CODE/TALUKA_CODE filters.")
        sys.exit(1)
    
    total_villages = sum(len(t["taluka"]["villages"]) for t in tasks)
    print(f"Tasks: {len(tasks)} talukas, {total_villages} villages")
    print(f"Survey filter: {survey_filter or 'none'}")
    
    # Distribute tasks across workers
    task_chunks = [[] for _ in range(NUM_PARALLEL_CONTEXTS)]
    for i, task in enumerate(tasks):
        task_chunks[i % NUM_PARALLEL_CONTEXTS].append(task)
    
    start_time = time.time()
    all_results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        
        print(f"\n🌐 Browser launched, starting {NUM_PARALLEL_CONTEXTS} workers...")
        
        with ThreadPoolExecutor(max_workers=NUM_PARALLEL_CONTEXTS) as executor:
            futures = []
            for ctx_id, chunk in enumerate(task_chunks):
                if chunk:
                    future = executor.submit(worker, ctx_id, browser, chunk, survey_filter)
                    futures.append(future)
            
            for future in as_completed(futures):
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as e:
                    print(f"Worker error: {e}")
        
        browser.close()
    
    elapsed = time.time() - start_time
    
    # Generate reports
    generate_reports()
    
    # Generate summary
    generate_summary(all_results)
    
    print(f"\n⏱️ Total time: {elapsed:.1f}s ({elapsed/60:.1f}m)")
    print(f"📁 Output directory: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
