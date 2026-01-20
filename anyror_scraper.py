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
from src.captcha_solver import CaptchaSolver
from src.vf7_extractor import VF7Extractor


# Gemini API Key
GEMINI_API_KEY = "AIzaSyDBkyScEIGGUm2N1JwFrW32CCoAOWTbhXw"


class AnyRORScraper:
    """Scraper for Gujarat AnyROR VF-7 Survey No Details"""

    BASE_URL = "https://anyror.gujarat.gov.in/LandRecordRural.aspx"

    SELECTORS = {
        "record_type": "#ContentPlaceHolder1_drpLandRecord",
        "district": "#ContentPlaceHolder1_ddlDistrict",
        "taluka": "#ContentPlaceHolder1_ddlTaluka",
        "village": "#ContentPlaceHolder1_ddlVillage",
        "survey_no": "#ContentPlaceHolder1_ddlSurveyNo",
        "captcha_input": "#ContentPlaceHolder1_txt_captcha_1",
        "captcha_image": "#ContentPlaceHolder1_i_captcha_1",
        "owner_name_input": "#ContentPlaceHolder1_txtownername",
        "results_table": "#ContentPlaceHolder1_gvOwner",
    }

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.captcha_solver = CaptchaSolver()
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
            if (
                value
                and value not in ["0", "-1", ""]
                and "પસંદ" not in text
                and "select" not in text.lower()
            ):
                options.append({"value": value, "text": text})
        return options

    def wait_for_page(self):
        """Wait for page to load with timeout handling"""
        try:
            self.page.wait_for_load_state("networkidle", timeout=1500)
        except:
            pass
        # Reduced from 0.1 for faster transitions
        time.sleep(0.05)

    def select_district(self, value=None):
        """Select district"""
        options = self.get_options(self.SELECTORS["district"])
        if not options:
            return None
        selected = (
            next((o for o in options if o["value"] == value), None)
            if value
            else random.choice(options)
        )
        print(f"[INFO] District: {selected['text']}")
        self.page.locator(self.SELECTORS["district"]).select_option(selected["value"])
        self.wait_for_page()
        return selected

    def select_taluka(self, value=None):
        """Select taluka"""
        options = self.get_options(self.SELECTORS["taluka"])
        if not options:
            return None
        selected = (
            next((o for o in options if o["value"] == value), None)
            if value
            else random.choice(options)
        )
        print(f"[INFO] Taluka: {selected['text']}")
        self.page.locator(self.SELECTORS["taluka"]).select_option(selected["value"])
        self.wait_for_page()
        return selected

    def select_village(self, value=None):
        """Select village"""
        options = self.get_options(self.SELECTORS["village"])
        if not options:
            return None
        selected = (
            next((o for o in options if o["value"] == value), None)
            if value
            else random.choice(options)
        )
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
            best = min(
                options,
                key=lambda o: abs(int(re.findall(r"\d+", o["text"])[0]) - target)
                if re.findall(r"\d+", o["text"])
                else 9999,
                default=None,
            )
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
        selected = next(
            (
                o
                for o in options
                if name.lower() in o["text"].lower() or name in o["text"]
            ),
            None,
        )
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
        selected = next(
            (
                o
                for o in options
                if name.lower() in o["text"].lower() or name in o["text"]
            ),
            None,
        )
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
        selected = next(
            (
                o
                for o in options
                if name.lower() in o["text"].lower() or name in o["text"]
            ),
            None,
        )
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
        selected = next(
            (o for o in options if o["text"] == value or o["value"] == value), None
        )
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
        """Get captcha image bytes with improved capture method"""
        try:
            # Try multiple selectors for AnyROR captcha (website may change them)
            captcha_selectors = [
                "#ContentPlaceHolder1_i_captcha_1",  # New format
                "#ContentPlaceHolder1_imgCaptcha",   # Old format
                "img[id*='captcha']",                # Fallback
                "img[id*='Captcha']",                # Case variant
                "img[src*='Captcha']",               # By src
            ]

            captcha_selector = None
            for selector in captcha_selectors:
                try:
                    count = self.page.locator(selector).count()
                    if count > 0:
                        captcha_selector = selector
                        print(f"[INFO] Found captcha with selector: {selector} ({count} elements)")
                        break
                except Exception as e:
                    print(f"[DEBUG] Selector '{selector}' check failed: {e}")

            if not captcha_selector:
                # Debug: print all images on page
                print("[DEBUG] No captcha found. Listing all images on page:")
                imgs = self.page.locator("img").all()
                for i, img in enumerate(imgs[:10]):
                    try:
                        img_id = img.get_attribute("id") or "no-id"
                        src = img.get_attribute("src") or "no-src"
                        print(f"[DEBUG]   [{i+1}] id='{img_id}' src='{src[:60]}...'")
                    except:
                        pass
                print("[ERROR] Captcha image element not found with any selector")
                return None

            # Wait for image to be loaded
            self.page.wait_for_selector(captcha_selector, state="visible", timeout=5000)
            time.sleep(0.1)  # Reduced from 0.5

            # Get the image source to verify it's loaded
            src = self.page.locator(captcha_selector).get_attribute("src")
            if not src:
                print("[ERROR] Captcha image has no src attribute")
                return None

            print(f"[INFO] Captcha src: {src[:80]}...")

            # Method 1: Handle base64 encoded images (data: URI)
            if src and src.startswith("data:"):
                try:
                    import base64
                    # Format: data:image/png;base64,iVBORw0KGgo...
                    # Extract the base64 part after the comma
                    if "," in src:
                        base64_data = src.split(",", 1)[1]
                        img_bytes = base64.b64decode(base64_data)
                        if img_bytes and len(img_bytes) > 100:
                            print(f"[INFO] Decoded base64 captcha ({len(img_bytes)} bytes)")
                            return img_bytes
                    else:
                        print("[WARN] Base64 src has no comma separator")
                except Exception as e:
                    print(f"[WARN] Base64 decode failed: {e}, falling back to other methods")

            # Method 2: Try to download the image directly from URL
            if src and not src.startswith("data:"):
                try:
                    # Build full URL
                    if src.startswith("http"):
                        full_url = src
                    elif src.startswith("/"):
                        full_url = f"https://anyror.gujarat.gov.in{src}"
                    else:
                        full_url = f"https://anyror.gujarat.gov.in/{src}"

                    print(f"[INFO] Downloading captcha from: {full_url[:60]}...")

                    # Download the image
                    response = self.page.request.get(full_url)
                    img_bytes = response.body()

                    if img_bytes and len(img_bytes) > 100:  # Sanity check
                        print(f"[INFO] Downloaded captcha image ({len(img_bytes)} bytes)")
                        return img_bytes
                except Exception as e:
                    print(f"[WARN] Direct download failed: {e}, falling back to screenshot")

            # Method 3: Screenshot the element (fallback)
            print("[INFO] Using element screenshot method")
            img_bytes = self.page.locator(captcha_selector).screenshot()

            if img_bytes and len(img_bytes) > 100:
                print(f"[INFO] Captured captcha screenshot ({len(img_bytes)} bytes)")
                return img_bytes

            print("[ERROR] Failed to capture captcha image")
            return None

        except Exception as e:
            print(f"[ERROR] get_captcha_image failed: {e}")
            return None

    def solve_and_enter_captcha(self, max_attempts=3) -> bool:
        """Get captcha, solve with AI, and enter it with retry"""
        print("[INFO] Getting captcha image...")

        for attempt in range(max_attempts):
            try:
                # Wait for captcha to be stable
                time.sleep(0.1) # Reduced from 0.3

                # Get captcha image
                img_bytes = self.get_captcha_image()
                if not img_bytes:
                    print(f"[ERROR] Attempt {attempt + 1}: Could not get captcha image")
                    if attempt < max_attempts - 1:
                        self.refresh_captcha()
                        continue
                    return False

                # Save for debugging
                with open("captcha_debug.png", "wb") as f:
                    f.write(img_bytes)

                # Solve with captcha solver
                print(f"[INFO] Attempt {attempt + 1}: Solving captcha...")
                captcha_text = self.captcha_solver.solve(img_bytes)

                if not captcha_text or len(captcha_text) < 3:
                    print(
                        f"[ERROR] Attempt {attempt + 1}: Empty/invalid captcha result: '{captcha_text}'"
                    )
                    if attempt < max_attempts - 1:
                        self.refresh_captcha()
                        continue
                    return False

                print(f"[INFO] Attempt {attempt + 1}: Entering captcha: {captcha_text}")

                # Enter captcha
                captcha_input = self.page.locator(self.SELECTORS["captcha_input"])
                captcha_input.fill(captcha_text)
                time.sleep(0.1) # Reduced from 0.5

                return True

            except Exception as e:
                print(f"[ERROR] Attempt {attempt + 1}: {e}")
                if attempt < max_attempts - 1:
                    self.refresh_captcha()
                    continue

        return False

    def refresh_captcha(self):
        """Refresh captcha image"""
        try:
            print("[INFO] Refreshing captcha...")
            # Try multiple refresh selectors
            refresh_selectors = [
                "#ContentPlaceHolder1_lb_refresh_1",  # New format
                "text=Refresh Code",                  # Old format
                "a[id*='refresh']",                   # Fallback
            ]
            for selector in refresh_selectors:
                if self.page.locator(selector).count() > 0:
                    self.page.locator(selector).click()
                    time.sleep(1)
                    return
            print("[WARN] No refresh button found")
        except Exception as e:
            print(f"[WARN] Could not refresh captcha: {e}")

    def submit(self) -> bool:
        """Submit the form"""
        print("[INFO] Submitting...")

        # Press Enter on captcha field (more reliable than clicking button)
        self.page.locator(self.SELECTORS["captcha_input"]).press("Enter")

        # time.sleep(1) # Removed fixed sleep

        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        return True

    def go_back_to_form(self) -> bool:
        """
        Click 'RURAL LAND RECORD' link to go back to form.
        This preserves district/taluka selection - much faster than fresh navigation!
        """
        try:
            self.page.get_by_role("link", name="RURAL LAND RECORD").click()
            self.wait_for_page()
            print("[INFO] Navigated back to form (session preserved)")
            return True
        except Exception as e:
            print(f"[WARN] Back navigation failed: {e}, will navigate fresh")
            return False

    def extract_data(self) -> dict:
        """Extract results including all property details"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "tables": [],
            "property_details": {},
            "full_page_text": "",
            "success": False,
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
            content_area = self.page.locator(
                "#ContentPlaceHolder1, .content, main, body"
            ).first
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
            error = self.page.locator(
                "[id*='lblError'], [id*='lblMsg']"
            ).first.text_content()
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
            "data_status_time": r"તા\.?\s*([0-9૦-૯/]+\s*[0-9૦-૯:]+)\s*ની સ્થિતિએ",
            "upin": r"UPIN[^:]*[:：\)]\s*([A-Z]{2}[0-9]+)",
            "old_survey_number": r"જુનો સરવે નંબર[^:]*[:：]\s*([^\n]+)",
            "tenure": r"સત્તાપ્રકાર[^:]*[:：]\s*([^\n]+)",
            "land_use": r"જમીનનો ઉપયોગ[^:]*[:：]\s*([^\n]+)",
            "farm_name": r"ખેતરનું નામ[^:]*[:：]\s*([^\n]+)",
            "remarks": r"રીમાર્ક્સ[^:]*[:：]\s*([^\n]+)",
            "total_area": r"કુલ ક્ષેત્રફળ[^:]*:\s*\n?\s*\n?\s*\n?\s*\n?\s*([૦-૯0-9]+-[૦-૯0-9]+-[૦-૯0-9]+)",
            "assessment_tax": r"કુલ આકાર[^:]*:\s*\n?\s*\n?\s*\n?\s*\n?\s*([૦-૯0-9\.]+)",
        }

        for field, pattern in patterns.items():
            if (
                field not in data["property_details"]
                or not data["property_details"][field]
            ):
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    value = match.group(1).strip()
                    if value and value != "----" and value != "-":
                        data["property_details"][field] = value

    def scrape(
        self,
        max_captcha_attempts=3,
        target_district=None,
        target_taluka=None,
        target_village=None,
        target_survey=None,
    ):
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
        self.page.screenshot(
            path=f"result_{datetime.now().strftime('%H%M%S')}.png", full_page=True
        )

        # Raw result for backward compatibility
        raw_result = {
            "district": d,
            "taluka": t,
            "village": v,
            "survey": s,
            "data": data,
        }

        # Extract structured data
        structured_data = self.extractor.extract_from_scrape_result(raw_result)

        # Save both formats
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save raw result
        raw_filename = f"vf7_raw_{timestamp}.json"
        with open(raw_filename, "w", encoding="utf-8") as f:
            json.dump(raw_result, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Raw saved: {raw_filename}")

        # Save structured result
        structured_filename = f"vf7_structured_{timestamp}.json"
        with open(structured_filename, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)

        # Print extraction summary
        print(f"[INFO] Structured saved: {structured_filename}")
        print(
            f"       Owners: {structured_data['meta'].get('owner_count', len(structured_data.get('owners', [])))}"
        )
        print(
            f"       Encumbrances: {structured_data['meta'].get('encumbrance_count', len(structured_data.get('rights_and_remarks', {}).get('entry_details', [])))}"
        )

        return {
            "raw": raw_result,
            "structured": structured_data,
            "files": {"raw": raw_filename, "structured": structured_filename},
        }

    def scrape_multiple_villages(
        self,
        district_code: str,
        taluka_code: str,
        village_codes: list,
        survey_filter: str = None,
        max_captcha_attempts: int = 3,
    ):
        """
        Scrape multiple villages efficiently by reusing browser session.
        After each record, clicks 'RURAL LAND RECORD' to go back - district/taluka stay selected!
        """
        results = []

        print(
            f"[SETUP] Setting up session for district={district_code}, taluka={taluka_code}"
        )
        self.navigate()
        self.select_vf7()

        self.page.locator(self.SELECTORS["district"]).select_option(district_code)
        self.wait_for_page()
        self.page.locator(self.SELECTORS["taluka"]).select_option(taluka_code)
        self.wait_for_page()

        print(f"[SETUP] Session ready - will scrape {len(village_codes)} villages")

        for i, village_code in enumerate(village_codes):
            print(f"\n[{i + 1}/{len(village_codes)}] Village: {village_code}")

            try:
                self.page.locator(self.SELECTORS["village"]).select_option(village_code)
                self.wait_for_page()

                village_text = ""
                try:
                    for opt in (
                        self.page.locator(self.SELECTORS["village"])
                        .locator("option")
                        .all()
                    ):
                        if opt.get_attribute("value") == village_code:
                            village_text = opt.text_content().strip()
                            break
                except:
                    pass

                if village_text:
                    print(f"  → {village_text[:40]}")

                surveys = self.get_options(self.SELECTORS["survey_no"])
                if survey_filter:
                    surveys = [s for s in surveys if survey_filter in s["text"]]

                if not surveys:
                    print(f"  ⚠️ No surveys found")
                    results.append(
                        {
                            "village_code": village_code,
                            "success": False,
                            "reason": "no_surveys",
                        }
                    )
                    continue

                survey = surveys[0]
                print(f"  Survey: {survey['text']}")
                self.page.locator(self.SELECTORS["survey_no"]).select_option(
                    survey["value"]
                )
                time.sleep(0.5)

                success = False
                data = None

                for attempt in range(max_captcha_attempts):
                    if self.solve_and_enter_captcha():
                        self.submit()
                        data = self.extract_data()

                        if data["success"]:
                            print(f"  ✅ Got record!")
                            success = True
                            break

                results.append(
                    {
                        "village_code": village_code,
                        "success": success,
                        "data": data if success else None,
                    }
                )

                # Click back to form for next village
                if i < len(village_codes) - 1:
                    self.go_back_to_form()

            except Exception as e:
                print(f"  ❌ Error processing village {village_code}: {e}")
                results.append(
                    {
                        "village_code": village_code,
                        "success": False,
                        "reason": str(e),
                    }
                )

        return results

    def scrape_by_owner(
        self,
        district_code: str,
        taluka_code: str,
        village_code: str,
        owner_name: str,
        max_captcha_attempts=3,
    ):
        """
        Search for land records by owner name
        Returns a list of matching records (Khata No, Survey No, Owner Name)
        """
        print(f"[INFO] Searching for owner '{owner_name}' in village {village_code}...")
        self.navigate()

        # Select Owner Search option (value 10)
        print("[INFO] Selecting Owner Search option...")
        self.page.locator(self.SELECTORS["record_type"]).select_option("10")
        self.wait_for_page()

        # Select District, Taluka, Village
        self.page.locator(self.SELECTORS["district"]).select_option(district_code)
        self.wait_for_page()
        self.page.locator(self.SELECTORS["taluka"]).select_option(taluka_code)
        self.wait_for_page()
        self.page.locator(self.SELECTORS["village"]).select_option(village_code)
        self.wait_for_page()

        # Enter Owner Name
        print(f"[INFO] Entering owner name: {owner_name}")
        self.page.locator(self.SELECTORS["owner_name_input"]).fill(owner_name)
        time.sleep(0.5)

        for attempt in range(1, max_captcha_attempts + 1):
            print(f"\n[ATTEMPT {attempt}/{max_captcha_attempts}]")

            # Solve and enter captcha
            if not self.solve_and_enter_captcha():
                continue

            # Submit
            self.submit()

            # Wait for results table
            try:
                self.page.wait_for_selector(self.SELECTORS["results_table"], timeout=5000)
                print("[SUCCESS] Found results table!")
                break
            except:
                # Check for error message
                try:
                    error_msg = self.page.locator("[id*='lblError'], [id*='lblMsg']").first.text_content()
                    if error_msg and "વિગતો મળેલ નથી" in error_msg: # No records found in Gujarati
                        print(f"[INFO] No records found for '{owner_name}'")
                        return {"success": True, "results": [], "count": 0}
                    print(f"[WARN] No table found, error: {error_msg}")
                except:
                    pass
                
            if attempt < max_captcha_attempts:
                self.refresh_captcha()

        # Extract matches
        results = self.extract_owner_results()
        
        # Save screenshot
        self.page.screenshot(
            path=f"owner_search_{datetime.now().strftime('%H%M%S')}.png", full_page=True
        )

        return {
            "success": len(results) > 0,
            "results": results,
            "count": len(results),
            "district": district_code,
            "taluka": taluka_code,
            "village": village_code,
            "owner_search_term": owner_name
        }

    def extract_owner_results(self) -> list:
        """Parse the results table into a list of dictionaries"""
        results = []
        try:
            table = self.page.locator(self.SELECTORS["results_table"])
            if table.count() == 0:
                return results

            # Get rows
            rows = table.locator("tr").all()
            if len(rows) <= 1: # Only header
                return results

            # Skip header (row 0)
            for row in rows[1:]:
                cells = row.locator("td").all()
                if len(cells) >= 4:
                    results.append({
                        "sr_no": cells[0].text_content().strip(),
                        "khata_no": cells[1].text_content().strip(),
                        "survey_no": cells[2].text_content().strip(),
                        "owner_name": cells[3].text_content().strip()
                    })
        except Exception as e:
            print(f"[ERROR] Extraction failed: {e}")
            
        return results

    def scrape_owner_multiple_villages(
        self,
        district_code: str,
        taluka_code: str,
        village_codes: list,
        owner_name: str,
        max_captcha_attempts: int = 3,
        callback: callable = None,
    ):
        """
        Scrape owner details for multiple villages in one session.
        Handles 'No records found' dialogs and redirects.
        """
        results = []
        print(f"[INFO] Global Owner Search: '{owner_name}' in taluka {taluka_code}")

        self.navigate()
        print("[INFO] Selecting Owner Search option...")
        self.page.locator(self.SELECTORS["record_type"]).select_option("10")
        self.wait_for_page()

        self.page.locator(self.SELECTORS["district"]).select_option(district_code)
        self.wait_for_page()
        self.page.locator(self.SELECTORS["taluka"]).select_option(taluka_code)
        self.wait_for_page()

        for i, village_code in enumerate(village_codes):
            print(f"\n[{i+1}/{len(village_codes)}] Village: {village_code}")
            
            try:
                # Ensure we are on the form page
                if self.page.locator(self.SELECTORS["owner_name_input"]).count() == 0:
                    print("[INFO] Not on form, navigating back...")
                    if not self.go_back_to_form():
                        self.page.locator(self.SELECTORS["record_type"]).select_option("10")
                        self.wait_for_page()

                # Select Village
                self.page.locator(self.SELECTORS["village"]).select_option(village_code)
                self.wait_for_page()
                
                # Fill Owner Name
                self.page.locator(self.SELECTORS["owner_name_input"]).fill(owner_name)
                
                success = False
                matches = []
                
                for attempt in range(max_captcha_attempts):
                    if self.solve_and_enter_captcha():
                        self.submit()
                        
                        # Wait for either results table or error message/dialog
                        try:
                            # If results table appears
                            self.page.wait_for_selector(self.SELECTORS["results_table"], timeout=5000)
                            matches = self.extract_owner_results()
                            print(f"  ✅ Found {len(matches)} matches!")
                            success = True
                            break
                        except:
                            # Check if still on form (No Hit/Dialog accepted)
                            if self.page.locator(self.SELECTORS["owner_name_input"]).count() > 0:
                                print(f"  ℹ️ No matches found (or Dialog appeared)")
                                success = True # We successfully confirmed no matches
                                break
                            
                            # Check for error labels
                            try:
                                error_msg = self.page.locator("[id*='lblError'], [id*='lblMsg']").first.text_content()
                                if error_msg and "વિગતો મળેલ નથી" in error_msg:
                                    print(f"  ℹ️ No matches found (Error Label)")
                                    success = True
                                    break
                            except:
                                pass

                    if attempt < max_captcha_attempts - 1:
                        self.refresh_captcha()

                res_obj = {
                    "village_code": village_code,
                    "success": success,
                    "count": len(matches),
                    "matches": matches
                }
                results.append(res_obj)
                
                # Trigger incremental save if callback exists
                if callback:
                    callback(res_obj)

                # If we are on results page, go back
                if self.page.locator(self.SELECTORS["results_table"]).count() > 0:
                    self.go_back_to_form()

            except Exception as e:
                print(f"  ❌ Error: {e}")
                results.append({
                    "village_code": village_code,
                    "success": False,
                    "error": str(e)
                })
                # Attempt recovery
                self.navigate()
                self.page.locator(self.SELECTORS["record_type"]).select_option("10")
                self.wait_for_page()
                self.page.locator(self.SELECTORS["district"]).select_option(district_code)
                self.wait_for_page()
                self.page.locator(self.SELECTORS["taluka"]).select_option(taluka_code)
                self.wait_for_page()

        return results


def main():
    print("=" * 50)
    print("Gujarat AnyROR VF-7 Scraper (Auto Captcha)")
    print("=" * 50)

    # Run scrapes
    num_scrapes = 1
    results = []

    scraper = AnyRORScraper()

    try:
        scraper.start()

        for i in range(num_scrapes):
            print(f"\n{'=' * 50}")
            print(f"SCRAPE {i + 1}/{num_scrapes}")
            print("=" * 50)

            try:
                result = scraper.scrape()
                results.append(result)

                if result["raw"]["data"]["success"]:
                    village = result["structured"]["location"]["village"]["name_local"]
                    owners = result["structured"]["meta"].get("owner_count", 0)
                    encs = result["structured"]["meta"].get("encumbrance_count", 0)
                    print(
                        f"✓ Success - {village} ({owners} owners, {encs} encumbrances)"
                    )
                else:
                    print(f"✗ Failed")

                # Brief pause between scrapes
                time.sleep(2)

            except Exception as e:
                print(f"[ERROR] Scrape {i + 1} failed: {e}")
                continue

        # Summary
        print("\n" + "=" * 50)
        print("SUMMARY")
        print("=" * 50)
        successful = sum(
            1 for r in results if r.get("raw", {}).get("data", {}).get("success", False)
        )
        print(f"Successful: {successful}/{num_scrapes}")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()

# Import parallel scraper
try:
    from parallel_scraper import ParallelAnyRORScraper
except ImportError:
    ParallelAnyRORScraper = None

__all__ = ["AnyRORScraper", "ParallelAnyRORScraper"]
