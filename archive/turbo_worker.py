"""
Cloud Worker - Direct copy of working local code
"""
import os, sys, json, time, re, base64
from datetime import datetime
from playwright.sync_api import sync_playwright
import requests

TASK_INDEX = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
TASK_COUNT = int(os.environ.get("CLOUD_RUN_TASK_COUNT", "1"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DISTRICT_CODE = os.environ.get("DISTRICT_CODE", "")
SURVEY_NUMBER = os.environ.get("SURVEY_NUMBER", "")

print(f"🚀 Task {TASK_INDEX+1}/{TASK_COUNT}", flush=True)

# GCS
from google.cloud import storage
try:
    bucket = storage.Client().bucket("anyror-results")
    bucket.reload()
    HAS_GCS = True
    print("📦 GCS ✓", flush=True)
except:
    HAS_GCS = False

URL = "https://anyror.gujarat.gov.in/LandRecordRural.aspx"

def solve_captcha(img_bytes):
    """Same as local captcha_solver.py"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    b64 = base64.b64encode(img_bytes).decode()
    prompt = "This is a CAPTCHA image. Read the numbers/letters shown. Return ONLY the plain digits and letters, nothing else. Use regular ASCII characters only (0-9, a-z, A-Z). No subscripts, superscripts, or special characters. Just the raw captcha text."
    
    try:
        r = requests.post(url, json={"contents":[{"parts":[
            {"inline_data":{"mime_type":"image/png","data":b64}},
            {"text": prompt}]}]}, timeout=15)
        if r.status_code == 200:
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Clean
            digit_map = {'₀':'0','₁':'1','₂':'2','₃':'3','₄':'4','₅':'5','₆':'6','₇':'7','₈':'8','₉':'9',
                        '⁰':'0','¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9','θ':'0','O':'0','o':'0'}
            cleaned = ''.join(digit_map.get(c, c) for c in raw if c in digit_map or (c.isascii() and c.isalnum()))
            print(f"    [CAPTCHA] {raw} -> {cleaned}", flush=True)
            return cleaned
    except Exception as e:
        print(f"    [CAPTCHA ERROR] {e}", flush=True)
    return ""

def scrape_village(page, v, survey_filter):
    """Same logic as global_search.py"""
    print(f"  → {v['vn'][:25]}...", flush=True)
    
    try:
        page.goto(URL, timeout=60000)
        page.wait_for_load_state("networkidle", timeout=30000)
        
        # Select VF-7
        page.locator("#ContentPlaceHolder1_drpLandRecord").select_option("1")
        time.sleep(0.5)
        
        # Select district
        page.locator("#ContentPlaceHolder1_ddlDistrict").select_option(v["dc"])
        page.wait_for_load_state("networkidle", timeout=30000)
        
        # Select taluka
        page.locator("#ContentPlaceHolder1_ddlTaluka").select_option(v["tc"])
        page.wait_for_load_state("networkidle", timeout=30000)
        
        # Select village
        page.locator("#ContentPlaceHolder1_ddlVillage").select_option(v["vc"])
        page.wait_for_load_state("networkidle", timeout=30000)
        
        # Get surveys
        surveys = []
        for opt in page.locator("#ContentPlaceHolder1_ddlSurveyNo option").all():
            val = opt.get_attribute("value")
            txt = opt.text_content().strip()
            if val and val not in ["0", "-1", ""] and "પસંદ" not in txt:
                if not survey_filter or survey_filter in txt:
                    surveys.append({"v": val, "t": txt})
        
        if not surveys:
            return {"found": False}
        
        print(f"    Found {len(surveys)} surveys matching '{survey_filter}'", flush=True)
        
        # Try first matching survey
        s = surveys[0]
        page.locator("#ContentPlaceHolder1_ddlSurveyNo").select_option(s["v"])
        time.sleep(0.5)
        
        # Solve captcha (3 attempts)
        for attempt in range(3):
            try:
                # Debug: check if captcha element exists
                captcha_el = page.locator("#ContentPlaceHolder1_imgCaptcha")
                print(f"    Captcha element count: {captcha_el.count()}", flush=True)
                
                # Wait for captcha image to be visible
                captcha_el.wait_for(state="visible", timeout=15000)
                print(f"    Captcha visible!", flush=True)
                time.sleep(1)
                
                captcha_img = captcha_el.screenshot(timeout=15000)
                print(f"    Captcha screenshot: {len(captcha_img)} bytes", flush=True)
                
                captcha_text = solve_captcha(captcha_img)
                
                if not captcha_text or len(captcha_text) < 4:
                    print(f"    Attempt {attempt+1}: Bad captcha, retrying...", flush=True)
                    try:
                        page.locator("text=Refresh Code").click()
                        time.sleep(0.5)
                    except:
                        pass
                    continue
                
                # Enter captcha
                page.locator("[placeholder='Enter Text Shown Above']").fill(captcha_text)
                page.locator("[placeholder='Enter Text Shown Above']").press("Enter")
                time.sleep(2)
                page.wait_for_load_state("networkidle", timeout=30000)
                
                # Check for results
                content = page.content()
                if "ખાતા નંબર" in content or "Khata" in content:
                    text = page.locator("body").text_content()
                    owners = re.findall(r'([^()\n]{3,50})\(([૦-૯0-9]+)\)', text)[:20]
                    
                    data = {
                        "district": v["dn"], "taluka": v["tn"], "village": v["vn"],
                        "survey": s["t"], 
                        "owners": [{"name": n.strip(), "entry": e} for n, e in owners],
                        "scraped_at": datetime.now().isoformat()
                    }
                    
                    # Save to GCS
                    name = f"vf7_{v['dc']}_{v['tc']}_{int(time.time()*1000)}"
                    if HAS_GCS:
                        try:
                            bucket.blob(f"{DISTRICT_CODE}/{name}.json").upload_from_string(
                                json.dumps(data, ensure_ascii=False), content_type="application/json")
                            print(f"    ✅ SAVED: {s['t']} - {len(owners)} owners", flush=True)
                        except Exception as e:
                            print(f"    GCS Error: {e}", flush=True)
                    
                    return {"found": True, "survey": s["t"], "owners": len(owners)}
                
                # Wrong captcha, refresh
                print(f"    Attempt {attempt+1}: Wrong captcha", flush=True)
                try:
                    page.locator("text=Refresh Code").click()
                    time.sleep(0.5)
                except:
                    pass
                    
            except Exception as e:
                print(f"    Attempt {attempt+1} error: {e}", flush=True)
        
        return {"found": False, "reason": "captcha_failed"}
        
    except Exception as e:
        print(f"    ❌ Error: {e}", flush=True)
        return {"found": False, "error": str(e)}

def main():
    if not DISTRICT_CODE:
        print("ERROR: Set DISTRICT_CODE", flush=True)
        sys.exit(1)
    
    with open("gujarat-anyror-complete.json") as f:
        data = json.load(f)
    
    district = next((d for d in data["districts"] if d["value"] == DISTRICT_CODE), None)
    if not district:
        print(f"ERROR: District {DISTRICT_CODE} not found", flush=True)
        sys.exit(1)
    
    # Build village list
    all_villages = []
    for t in district["talukas"]:
        for v in t["villages"]:
            all_villages.append({
                "dc": district["value"], "dn": district["label"],
                "tc": t["value"], "tn": t["label"],
                "vc": v["value"], "vn": v["label"]
            })
    
    # Split by task
    my_villages = [v for i, v in enumerate(all_villages) if i % TASK_COUNT == TASK_INDEX]
    
    print(f"📍 {district['label']} | Task {TASK_INDEX}: {len(my_villages)}/{len(all_villages)} villages", flush=True)
    print(f"🔍 Survey: {SURVEY_NUMBER}", flush=True)
    
    stats = {"done": 0, "found": 0, "records": 0}
    start = time.time()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context()
        page = context.new_page()
        page.on("dialog", lambda d: d.accept())
        
        print("🌐 Browser ready", flush=True)
        
        for i, v in enumerate(my_villages):
            result = scrape_village(page, v, SURVEY_NUMBER)
            stats["done"] += 1
            if result.get("found"):
                stats["found"] += 1
                stats["records"] += 1
            
            if (i + 1) % 5 == 0:
                elapsed = time.time() - start
                rate = stats["done"] / elapsed if elapsed > 0 else 0
                print(f"📊 {stats['done']}/{len(my_villages)} ({rate:.1f}/s) | Found: {stats['found']} | Records: {stats['records']}", flush=True)
        
        context.close()
        browser.close()
    
    elapsed = time.time() - start
    print(f"\n✅ Task {TASK_INDEX} DONE!", flush=True)
    print(f"   Villages: {stats['done']}", flush=True)
    print(f"   Found: {stats['found']}", flush=True)
    print(f"   Records: {stats['records']}", flush=True)
    print(f"   Time: {elapsed:.0f}s", flush=True)

if __name__ == "__main__":
    main()
