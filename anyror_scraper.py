"""
Gujarat AnyROR Land Records Scraper - VF-7 Survey No Details
Auto captcha solving with Gemini AI
"""

import random
import json
import time
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
from captcha_solver import CaptchaSolver
from vf7_extractor import VF7Extractor


# Gemini API Key
GEMINI_API_KEY = "AIzaSyDQ8yj7I1LOvZJQuhzPXODIDAF3ChE9YO4"


class AnyRORScraper:
    """Scraper for Gujarat AnyROR VF-7 Survey No Details"""
    
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
        self.captcha_solver = CaptchaSolver(GEMINI_API_KEY)
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
        import re
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
        # Try exact match first, then partial
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
        # Try to find captcha image with various selectors
        img_selectors = [
            "#ContentPlaceHolder1_imgCaptcha",
            "img[id*='Captcha']",
            "img[id*='captcha']", 
            "img[src*='Captcha']",
            "img[src*='captcha']",
            "img[alt*='captcha' i]",
            "#imgCaptcha",
            "img"  # Last resort - find any image near captcha input
        ]
        
        for selector in img_selectors:
            try:
                imgs = self.page.locator(selector).all()
                for img in imgs:
                    # Check if this looks like a captcha image
                    src = img.get_attribute("src") or ""
                    img_id = img.get_attribute("id") or ""
                    
                    # Skip non-captcha images
                    if "logo" in src.lower() or "icon" in src.lower():
                        continue
                    
                    # If it's a data URL or captcha-related, use it
                    if "captcha" in src.lower() or "captcha" in img_id.lower() or "data:image" in src:
                        print(f"[INFO] Found captcha image: {selector}")
                        img_bytes = img.screenshot()
                        return img_bytes
            except Exception as e:
                continue
        
        # Fallback: screenshot the area around the captcha input
        print("[INFO] Using fallback: screenshot area near captcha input")
        try:
            # Find the captcha container/parent
            captcha_input = self.page.locator(self.SELECTORS["captcha_input"])
            if captcha_input.count() > 0:
                # Get bounding box and screenshot a larger area above it
                box = captcha_input.bounding_box()
                if box:
                    # Screenshot the page and crop
                    self.page.screenshot(path="full_page_debug.png", full_page=True)
                    
                    # Try to find any image element on the page
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
        """Get captcha, solve with AI, and enter it"""
        print("[INFO] Getting captcha image...")
        
        # Wait for captcha to be stable
        time.sleep(1)
        
        # Get captcha image
        img_bytes = self.get_captcha_image()
        if not img_bytes:
            print("[ERROR] Could not get captcha image")
            return False
        
        # Save for debugging
        with open("captcha_debug.png", "wb") as f:
            f.write(img_bytes)
        
        # Solve with Gemini
        captcha_text = self.captcha_solver.solve(img_bytes)
        
        if not captcha_text:
            print("[ERROR] Gemini returned empty captcha")
            return False
        
        print(f"[INFO] Entering captcha: {captcha_text}")
        
        # Enter captcha
        captcha_input = self.page.locator(self.SELECTORS["captcha_input"])
        captcha_input.fill(captcha_text)
        time.sleep(0.5)
        
        return True
    
    def submit(self) -> bool:
        """Submit the form"""
        print("[INFO] Submitting...")
        
        # Press Enter on captcha field (more reliable than clicking button)
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
        
        # Extract tables (ownership and encumbrance data)
        tables = self.page.locator("table").all()
        for i, table in enumerate(tables):
            text = table.text_content()
            if len(text.strip()) > 200:
                data["tables"].append({"index": i, "text": text.strip()})
        
        # Extract property details section - these are in labeled spans/divs
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
                    # Try various selector patterns
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
        
        # Also try to extract from page structure by looking for label-value pairs
        try:
            # Get full page text for backup parsing
            content_area = self.page.locator("#ContentPlaceHolder1, .content, main, body").first
            if content_area.count() > 0:
                data["full_page_text"] = content_area.text_content()
        except:
            pass
        
        # Parse label-value pairs from page text
        if data["full_page_text"]:
            self._extract_labeled_values(data)
        
        if data["tables"] or data["property_details"]:
            data["success"] = True
        
        # Check for error
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
        
        # Patterns for extracting labeled values
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
    
    def scrape(self, max_captcha_attempts=3, target_district=None, target_taluka=None, target_village=None, target_survey=None):
        """Main scrape function with auto captcha"""
        self.navigate()
        self.select_vf7()
        
        # Keep trying until we get a valid district/taluka/village/survey combo
        max_location_attempts = 5
        d, t, v, s = None, None, None, None
        
        for loc_attempt in range(max_location_attempts):
            # Select district - use target if provided
            if target_district:
                d = self.select_district_by_name(target_district)
            else:
                d = self.select_district()
            if not d:
                continue
                
            # Select taluka - use target if provided
            if target_taluka:
                t = self.select_taluka_by_name(target_taluka)
            else:
                t = self.select_taluka()
            if not t:
                print("[WARN] No talukas, trying another district...")
                continue
            
            # Select village - use target if provided
            if target_village:
                v = self.select_village_by_name(target_village)
            else:
                v = self.select_village()
            if not v:
                print("[WARN] No villages, trying another district...")
                continue
            
            # Select survey - use target if provided
            if target_survey:
                s = self.select_survey_by_value(target_survey)
            else:
                s = self.select_survey(random.randint(1, 50))
            if not s:
                print("[WARN] No survey numbers, trying another village...")
                continue
            
            # Got all selections
            break
        
        if not all([d, t, v, s]):
            print("[ERROR] Could not find valid location after multiple attempts")
            return {"error": "No valid location found"}
        
        # Wait for page to settle
        print("[INFO] Waiting for page to settle...")
        time.sleep(2)
        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        
        # Try captcha multiple times
        data = {"success": False, "tables": [], "timestamp": datetime.now().isoformat()}
        
        for attempt in range(1, max_captcha_attempts + 1):
            print(f"\n[ATTEMPT {attempt}/{max_captcha_attempts}]")
            
            # Solve and enter captcha
            if not self.solve_and_enter_captcha():
                continue
            
            # Submit
            self.submit()
            
            # Check if we got results
            time.sleep(2)
            data = self.extract_data()
            
            if data["success"]:
                print("[SUCCESS] Got results!")
                break
            
            if "error" in data:
                print(f"[WARNING] Error: {data.get('error', 'Unknown')}")
            
            # Refresh captcha for retry
            if attempt < max_captcha_attempts:
                print("[INFO] Refreshing captcha...")
                try:
                    self.page.locator("text=Refresh Code").click()
                    time.sleep(1)
                except:
                    pass
        
        # Screenshot
        self.page.screenshot(path=f"result_{datetime.now().strftime('%H%M%S')}.png", full_page=True)
        
        # Raw result for backward compatibility
        raw_result = {
            "district": d,
            "taluka": t, 
            "village": v,
            "survey": s,
            "data": data
        }
        
        # Extract structured data
        structured_data = self.extractor.extract_from_scrape_result(raw_result)
        
        # Save both formats
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save raw result
        raw_filename = f"vf7_raw_{timestamp}.json"
        with open(raw_filename, 'w', encoding='utf-8') as f:
            json.dump(raw_result, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Raw saved: {raw_filename}")
        
        # Save structured result
        structured_filename = f"vf7_structured_{timestamp}.json"
        with open(structured_filename, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)
        
        # Print extraction summary
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
    print("="*50)
    print("Gujarat AnyROR VF-7 Scraper (Auto Captcha)")
    print("="*50)
    
    # Run scrapes
    num_scrapes = 1
    results = []
    
    scraper = AnyRORScraper()
    
    try:
        scraper.start()
        
        for i in range(num_scrapes):
            print(f"\n{'='*50}")
            print(f"SCRAPE {i+1}/{num_scrapes}")
            print("="*50)
            
            try:
                result = scraper.scrape()
                results.append(result)
                
                if result["raw"]["data"]["success"]:
                    village = result['structured']['location']['village']['name_local']
                    owners = result['structured']['meta'].get('owner_count', 0)
                    encs = result['structured']['meta'].get('encumbrance_count', 0)
                    print(f"✓ Success - {village} ({owners} owners, {encs} encumbrances)")
                else:
                    print(f"✗ Failed")
                
                # Brief pause between scrapes
                time.sleep(2)
                
            except Exception as e:
                print(f"[ERROR] Scrape {i+1} failed: {e}")
                continue
        
        # Summary
        print("\n" + "="*50)
        print("SUMMARY")
        print("="*50)
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
