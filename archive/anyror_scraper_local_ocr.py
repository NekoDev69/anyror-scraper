"""
Gujarat AnyROR Land Records Scraper - VF-7 Survey No Details
Local OCR captcha solving (Tesseract) - NO API CALLS
"""

import random
import json
import time
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
from captcha_solver_local import LocalCaptchaSolver
from vf7_extractor import VF7Extractor


class AnyRORScraperLocalOCR:
    """Scraper for Gujarat AnyROR VF-7 Survey No Details using local OCR"""
    
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
        self.captcha_solver = LocalCaptchaSolver()  # Local OCR instead of Gemini
        self.extractor = VF7Extractor()
    
    def start(self):
        """Initialize browser"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_viewport_size({"width": 1280, "height": 900})
        
        # Handle dialogs
        def handle_dialog(dialog):
            try:
                dialog.accept()
            except:
                pass
        self.page.on("dialog", handle_dialog)
    
    def close(self):
        """Cleanup"""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def navigate(self):
        """Navigate to portal"""
        print(f"[INFO] Navigating to {self.BASE_URL}")
        self.page.goto(self.BASE_URL)
        self.wait_for_page()
    
    def select_vf7(self):
        """Select VF-7 option"""
        print("[INFO] Selecting VF-7 Survey No Details...")
        self.page.locator(self.SELECTORS["record_type"]).select_option("1")
        self.wait_for_page()
    
    def get_options(self, selector: str) -> list:
        """Get dropdown options"""
        options = []
        for opt in self.page.locator(selector).locator("option").all():
            value = opt.get_attribute("value")
            text = opt.text_content().strip()
            if value and value not in ["0", "-1", ""] and "પસંદ" not in text and "select" not in text.lower():
                options.append({"value": value, "text": text})
        return options
    
    def wait_for_page(self):
        """Wait for page to load with timeout handling"""
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        time.sleep(1)
    
    def select_district(self, value=None):
        """Select district"""
        options = self.get_options(self.SELECTORS["district"])
        if not options:
            return None
        selected = next((o for o in options if o["value"] == value), None) if value else random.choice(options)
        print(f"[INFO] District: {selected['text']}")
        self.page.locator(self.SELECTORS["district"]).select_option(selected["value"])
        self.wait_for_page()
        return selected
    
    def select_taluka(self, value=None):
        """Select taluka"""
        options = self.get_options(self.SELECTORS["taluka"])
        if not options:
            return None
        selected = next((o for o in options if o["value"] == value), None) if value else random.choice(options)
        print(f"[INFO] Taluka: {selected['text']}")
        self.page.locator(self.SELECTORS["taluka"]).select_option(selected["value"])
        self.wait_for_page()
        return selected
    
    def select_village(self, value=None):
        """Select village"""
        options = self.get_options(self.SELECTORS["village"])
        if not options:
            return None
        selected = next((o for o in options if o["value"] == value), None) if value else random.choice(options)
        print(f"[INFO] Village: {selected['text']}")
        self.page.locator(self.SELECTORS["village"]).select_option(selected["value"])
        self.wait_for_page()
        return selected
    
    def select_survey(self, target=None):
        """Select survey number"""
        options = self.get_options(self.SELECTORS["survey_no"])
        if not options:
            return None
        
        if target:
            best = min(options, key=lambda o: abs(int(re.findall(r'\d+', o["text"])[0]) - target) if re.findall(r'\d+', o["text"]) else 9999, default=None)
            selected = best or random.choice(options)
        else:
            selected = random.choice(options)
        
        print(f"[INFO] Survey: {selected['text']}")
        self.page.locator(self.SELECTORS["survey_no"]).select_option(selected["value"])
        time.sleep(1)
        return selected
    
    def select_district_by_name(self, name: str):
        """Select district by name (partial match)"""
        options = self.get_options(self.SELECTORS["district"])
        if not options:
            return None
        selected = next((o for o in options if name.lower() in o["text"].lower() or name in o["text"]), None)
        if not selected:
            print(f"[WARN] District '{name}' not found")
            return None
        print(f"[INFO] District: {selected['text']}")
        self.page.locator(self.SELECTORS["district"]).select_option(selected["value"])
        self.wait_for_page()
        return selected
    
    def select_taluka_by_name(self, name: str):
        """Select taluka by name (partial match)"""
        options = self.get_options(self.SELECTORS["taluka"])
        if not options:
            return None
        selected = next((o for o in options if name.lower() in o["text"].lower() or name in o["text"]), None)
        if not selected:
            print(f"[WARN] Taluka '{name}' not found")
            return None
        print(f"[INFO] Taluka: {selected['text']}")
        self.page.locator(self.SELECTORS["taluka"]).select_option(selected["value"])
        self.wait_for_page()
        return selected
    
    def select_village_by_name(self, name: str):
        """Select village by name (partial match)"""
        options = self.get_options(self.SELECTORS["village"])
        if not options:
            return None
        selected = next((o for o in options if name.lower() in o["text"].lower() or name in o["text"]), None)
        if not selected:
            print(f"[WARN] Village '{name}' not found")
            return None
        print(f"[INFO] Village: {selected['text']}")
        self.page.locator(self.SELECTORS["village"]).select_option(selected["value"])
        self.wait_for_page()
        return selected
    
    def select_survey_by_value(self, value: str):
        """Select survey by exact value"""
        options = self.get_options(self.SELECTORS["survey_no"])
        if not options:
            return None
        selected = next((o for o in options if o["text"] == value or o["value"] == value), None)
        if not selected:
            selected = next((o for o in options if value in o["text"]), None)
        if not selected:
            print(f"[WARN] Survey '{value}' not found")
            return None
        print(f"[INFO] Survey: {selected['text']}")
        self.page.locator(self.SELECTORS["survey_no"]).select_option(selected["value"])
        time.sleep(1)
        return selected

    def get_captcha_image(self) -> bytes:
        """Get captcha image bytes"""
        img_selectors = [
            "#ContentPlaceHolder1_imgCaptcha",
            "img[id*='Captcha']",
            "img[id*='captcha']", 
            "img[src*='Captcha']",
            "img[src*='captcha']",
            "img[alt*='captcha' i]",
            "#imgCaptcha",
            "img"
        ]
        
        for selector in img_selectors:
            try:
                imgs = self.page.locator(selector).all()
                for img in imgs:
                    src = img.get_attribute("src") or ""
                    img_id = img.get_attribute("id") or ""
                    
                    if "logo" in src.lower() or "icon" in src.lower():
                        continue
                    
                    if "captcha" in src.lower() or "captcha" in img_id.lower() or "data:image" in src:
                        print(f"[INFO] Found captcha image: {selector}")
                        img_bytes = img.screenshot()
                        return img_bytes
            except Exception:
                continue
        
        print("[INFO] Using fallback: screenshot area near captcha input")
        try:
            captcha_input = self.page.locator(self.SELECTORS["captcha_input"])
            if captcha_input.count() > 0:
                self.page.screenshot(path="full_page_debug.png", full_page=True)
                all_imgs = self.page.locator("img").all()
                print(f"[DEBUG] Found {len(all_imgs)} images on page")
                for i, img in enumerate(all_imgs):
                    try:
                        src = img.get_attribute("src") or ""
                        img_id = img.get_attribute("id") or ""
                        print(f"[DEBUG] Image {i}: id={img_id}, src={src[:50]}...")
                    except:
                        pass
        except Exception as e:
            print(f"[DEBUG] Fallback error: {e}")
        
        return None
    
    def solve_and_enter_captcha(self) -> bool:
        """Get captcha, solve with local OCR, and enter it"""
        print("[INFO] Getting captcha image...")
        
        time.sleep(1)
        
        img_bytes = self.get_captcha_image()
        if not img_bytes:
            print("[ERROR] Could not get captcha image")
            return False
        
        with open("captcha_debug.png", "wb") as f:
            f.write(img_bytes)
        
        # Solve with local Tesseract OCR
        captcha_text = self.captcha_solver.solve(img_bytes)
        
        if not captcha_text:
            print("[ERROR] Local OCR returned empty captcha")
            return False
        
        print(f"[INFO] Entering captcha: {captcha_text}")
        
        captcha_input = self.page.locator(self.SELECTORS["captcha_input"])
        captcha_input.fill(captcha_text)
        time.sleep(0.5)
        
        return True
    
    def submit(self) -> bool:
        """Submit the form"""
        print("[INFO] Submitting...")
        
        self.page.locator(self.SELECTORS["captcha_input"]).press("Enter")
        
        time.sleep(3)
        
        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        
        return True
    
    def extract_data(self) -> dict:
        """Extract results including all property details"""
        data = {
            "timestamp": datetime.now().isoformat(), 
            "tables": [], 
            "property_details": {},
            "full_page_text": "",
            "success": False
        }
        
        tables = self.page.locator("table").all()
        for i, table in enumerate(tables):
            text = table.text_content()
            if len(text.strip()) > 200:
                data["tables"].append({"index": i, "text": text.strip()})
        
        detail_fields = {
            "data_status_time": ["lblDataTime", "lblDateTime", "lblStatusTime"],
            "district": ["lblDistrict", "lblDistrictName"],
            "taluka": ["lblTaluka", "lblTalukaName"],
            "village": ["lblVillage", "lblVillageName"],
            "survey_block_number": ["lblSurveyNo", "lblBlockNo", "lblSurveyBlockNo"],
            "upin": ["lblUPIN", "lblUpin", "lblPropertyId"],
            "old_survey_number": ["lblOldSurveyNo", "lblOldSurvey"],
            "old_survey_notes": ["lblOldSurveyNotes", "lblOldNotes"],
            "total_area": ["lblArea", "lblTotalArea"],
            "assessment_tax": ["lblAssessment", "lblAakar", "lblTax"],
            "tenure": ["lblTenure", "lblSattaPrakar"],
            "land_use": ["lblLandUse", "lblUse"],
            "farm_name": ["lblFarmName", "lblKhetarName"],
            "remarks": ["lblRemarks", "lblOtherDetails"],
        }
        
        for field_name, selectors in detail_fields.items():
            for sel in selectors:
                try:
                    for pattern in [f"#{sel}", f"[id*='{sel}']", f"[id$='{sel}']"]:
                        elem = self.page.locator(pattern).first
                        if elem.count() > 0:
                            text = elem.text_content()
                            if text and text.strip():
                                data["property_details"][field_name] = text.strip()
                                break
                    if field_name in data["property_details"]:
                        break
                except:
                    continue
        
        try:
            content_area = self.page.locator("#ContentPlaceHolder1, .content, main, body").first
            if content_area.count() > 0:
                data["full_page_text"] = content_area.text_content()
        except:
            pass
        
        if data["full_page_text"]:
            self._extract_labeled_values(data)
        
        if data["tables"] or data["property_details"]:
            data["success"] = True
        
        try:
            error = self.page.locator("[id*='lblError'], [id*='lblMsg']").first.text_content()
            if error:
                data["error"] = error.strip()
        except:
            pass
        
        return data
    
    def _extract_labeled_values(self, data: dict):
        """Extract values from labeled text patterns in page"""
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
    
    def scrape(self, max_captcha_attempts=5, target_district=None, target_taluka=None, target_village=None, target_survey=None):
        """Main scrape function with local OCR captcha solving
        
        Note: Local OCR may need more attempts than Gemini API, so default is 5 attempts
        """
        self.navigate()
        self.select_vf7()
        
        max_location_attempts = 5
        d, t, v, s = None, None, None, None
        
        for loc_attempt in range(max_location_attempts):
            if target_district:
                d = self.select_district_by_name(target_district)
            else:
                d = self.select_district()
            if not d:
                continue
                
            if target_taluka:
                t = self.select_taluka_by_name(target_taluka)
            else:
                t = self.select_taluka()
            if not t:
                print("[WARN] No talukas, trying another district...")
                continue
            
            if target_village:
                v = self.select_village_by_name(target_village)
            else:
                v = self.select_village()
            if not v:
                print("[WARN] No villages, trying another district...")
                continue
            
            if target_survey:
                s = self.select_survey_by_value(target_survey)
            else:
                s = self.select_survey(random.randint(1, 50))
            if not s:
                print("[WARN] No survey numbers, trying another village...")
                continue
            
            break
        
        if not all([d, t, v, s]):
            print("[ERROR] Could not find valid location after multiple attempts")
            return {"error": "No valid location found"}
        
        print("[INFO] Waiting for page to settle...")
        time.sleep(2)
        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        
        data = {"success": False, "tables": [], "timestamp": datetime.now().isoformat()}
        
        for attempt in range(1, max_captcha_attempts + 1):
            print(f"\n[ATTEMPT {attempt}/{max_captcha_attempts}] (Local OCR)")
            
            if not self.solve_and_enter_captcha():
                continue
            
            self.submit()
            
            time.sleep(2)
            data = self.extract_data()
            
            if data["success"]:
                print("[SUCCESS] Got results!")
                break
            
            if "error" in data:
                print(f"[WARNING] Error: {data.get('error', 'Unknown')}")
            
            if attempt < max_captcha_attempts:
                print("[INFO] Refreshing captcha...")
                try:
                    self.page.locator("text=Refresh Code").click()
                    time.sleep(1)
                except:
                    pass
        
        self.page.screenshot(path=f"result_local_ocr_{datetime.now().strftime('%H%M%S')}.png", full_page=True)
        
        raw_result = {
            "district": d,
            "taluka": t, 
            "village": v,
            "survey": s,
            "data": data,
            "ocr_method": "local_tesseract"
        }
        
        structured_data = self.extractor.extract_from_scrape_result(raw_result)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        raw_filename = f"vf7_raw_local_ocr_{timestamp}.json"
        with open(raw_filename, 'w', encoding='utf-8') as f:
            json.dump(raw_result, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Raw saved: {raw_filename}")
        
        structured_filename = f"vf7_structured_local_ocr_{timestamp}.json"
        with open(structured_filename, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] Structured saved: {structured_filename}")
        print(f"       Owners: {structured_data['meta'].get('owner_count', len(structured_data.get('owners', [])))}")
        print(f"       Encumbrances: {structured_data['meta'].get('encumbrance_count', len(structured_data.get('rights_and_remarks', {}).get('entry_details', [])))}")
        
        return {
            "raw": raw_result,
            "structured": structured_data,
            "files": {
                "raw": raw_filename,
                "structured": structured_filename
            }
        }


def main():
    print("="*60)
    print("Gujarat AnyROR VF-7 Scraper (LOCAL OCR - No API)")
    print("="*60)
    print("Using Tesseract OCR instead of Gemini API")
    print()
    
    num_scrapes = 1
    results = []
    
    is_server = os.environ.get("DISPLAY") is None
    scraper = AnyRORScraperLocalOCR(headless=is_server)
    
    try:
        scraper.start()
        
        for i in range(num_scrapes):
            print(f"\n{'='*60}")
            print(f"SCRAPE {i+1}/{num_scrapes}")
            print("="*60)
            
            try:
                result = scraper.scrape()
                results.append(result)
                
                if result.get("raw", {}).get("data", {}).get("success"):
                    village = result['structured']['location']['village']['name_local']
                    owners = result['structured']['meta'].get('owner_count', 0)
                    encs = result['structured']['meta'].get('encumbrance_count', 0)
                    print(f"✓ Success - {village} ({owners} owners, {encs} encumbrances)")
                else:
                    print(f"✗ Failed")
                
                time.sleep(2)
                
            except Exception as e:
                print(f"[ERROR] Scrape {i+1} failed: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        successful = sum(1 for r in results if r.get("raw", {}).get("data", {}).get("success", False))
        print(f"Successful: {successful}/{num_scrapes}")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
