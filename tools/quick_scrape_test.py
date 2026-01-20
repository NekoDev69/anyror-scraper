#!/usr/bin/env python3
"""
Quick Fix Test - Get actual data and convert to CSV
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright
from captcha_solver import CaptchaSolver

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


async def quick_scrape_one():
    """Scrape one village successfully and export to CSV"""

    print("=" * 50)
    print("QUICK SCRAPE TEST - ONE VILLAGE")
    print("=" * 50)

    # Load real codes
    with open("real_codes.json", "r", encoding="utf-8") as f:
        real_codes = json.load(f)

    district_code = real_codes["district"]["value"]
    taluka_code = real_codes["taluka"]["value"]
    village_code = real_codes["villages"][0]["value"]  # First village

    print(f"Scraping: {real_codes['villages'][0]['text']} ({village_code})")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Navigate
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)

            # Select VF-7
            await page.locator(SELECTORS["record_type"]).select_option("1")
            await asyncio.sleep(1)

            # Select district
            await page.locator(SELECTORS["district"]).select_option(district_code)
            await asyncio.sleep(2)

            # Select taluka
            await page.locator(SELECTORS["taluka"]).select_option(taluka_code)
            await asyncio.sleep(2)

            # Select village
            await page.locator(SELECTORS["village"]).select_option(village_code)
            await asyncio.sleep(2)

            # Get survey
            survey_options = (
                await page.locator(SELECTORS["survey_no"]).locator("option").all()
            )
            if survey_options:
                first_survey = await survey_options[0].get_attribute("value")
                await page.locator(SELECTORS["survey_no"]).select_option(first_survey)
                await asyncio.sleep(1)
                print(f"Selected survey: {first_survey}")

            # Solve captcha
            solver = CaptchaSolver("AIzaSyDBkyScEIGGUm2N1JwFrW32CCoAOWTbhXw")

            for attempt in range(5):
                try:
                    # Get captcha
                    img_bytes = await page.locator(
                        SELECTORS["captcha_image"]
                    ).screenshot()
                    captcha_text = solver.solve(img_bytes)

                    if captcha_text:
                        print(f"Attempt {attempt + 1}: Captcha solved: {captcha_text}")

                        # Enter captcha
                        await page.locator(SELECTORS["captcha_input"]).fill(
                            captcha_text
                        )
                        await asyncio.sleep(0.5)

                        # Submit
                        await page.locator(SELECTORS["captcha_input"]).press("Enter")
                        await asyncio.sleep(3)

                        # Extract all text from page
                        page_text = await page.locator("body").text_content()

                        if len(page_text) > 500:  # Got substantial content
                            print(
                                f"✅ SUCCESS! Got page content ({len(page_text)} chars)"
                            )

                            # Save raw data
                            raw_data = {
                                "success": True,
                                "village_code": village_code,
                                "village_name": real_codes["villages"][0]["text"],
                                "page_text": page_text,
                                "timestamp": datetime.now().isoformat(),
                            }

                            # Save raw data
                            with open(
                                "quick_scrape_result.json", "w", encoding="utf-8"
                            ) as f:
                                json.dump(raw_data, f, ensure_ascii=False, indent=2)

                            # Create simple CSV
                            csv_content = f"""village_code,village_name,scrape_timestamp,page_length,has_data
{village_code},"{real_codes["villages"][0]["text"]}",{datetime.now().isoformat()},{len(page_text)},YES
"""

                            with open(
                                "quick_scrape_result.csv", "w", encoding="utf-8"
                            ) as f:
                                f.write(csv_content)

                            print(f"✅ CSV saved: quick_scrape_result.csv")
                            print(f"✅ Raw data saved: quick_scrape_result.json")

                            return raw_data
                        else:
                            print(f"❌ Page content too short: {len(page_text)} chars")

                except Exception as e:
                    print(f"Attempt {attempt + 1} error: {e}")

                # Refresh captcha for retry
                if attempt < 4:
                    try:
                        await page.locator("text=Refresh Code").click()
                        await asyncio.sleep(1)
                    except:
                        pass

            print("❌ All captcha attempts failed")
            return None

        except Exception as e:
            print(f"❌ Scrape error: {e}")
            import traceback

            traceback.print_exc()
            return None

        finally:
            await browser.close()


async def main():
    """Run quick scrape test"""
    print("Starting quick scrape test...")
    print("Browser will open visibly - watch the process!")

    result = await quick_scrape_one()

    if result:
        print(f"\n🎉 SUCCESS! Data extracted and CSV created!")
        print(f"   Village: {result['village_name']} ({result['village_code']})")
        print(f"   Page length: {result['page_length']} chars")
        print(f"   CSV file: quick_scrape_result.csv")
        print(f"   Raw data: quick_scrape_result.json")
    else:
        print(f"\n❌ Failed to extract data")

    print(f"\nNext: Check quick_scrape_result.csv for exported data!")


if __name__ == "__main__":
    asyncio.run(main())
