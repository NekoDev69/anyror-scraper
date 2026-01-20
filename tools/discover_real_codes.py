#!/usr/bin/env python3
"""
Real Data Discovery - Find actual working district/taluka/village codes
"""

import asyncio
from playwright.sync_api import sync_playwright

BASE_URL = "https://anyror.gujarat.gov.in/LandRecordRural.aspx"

SELECTORS = {
    "record_type": "#ContentPlaceHolder1_drpLandRecord",
    "district": "#ContentPlaceHolder1_ddlDistrict",
    "taluka": "#ContentPlaceHolder1_ddlTaluka",
    "village": "#ContentPlaceHolder1_ddlVillage",
    "survey_no": "#ContentPlaceHolder1_ddlSurveyNo",
}


def discover_real_codes():
    """Discover real district/taluka/village codes from the website"""

    print("=" * 60)
    print("DISCOVERING REAL DISTRICT/ TALUKA/ VILLAGE CODES")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, slow_mo=1000
        )  # Visible for debugging
        context = browser.new_context()
        page = context.new_page()

        try:
            print("[1] Navigating to AnyROR website...")
            page.goto(BASE_URL)
            page.wait_for_load_state("networkidle", timeout=30000)

            # Select VF-7
            print("[2] Selecting VF-7 option...")
            page.locator(SELECTORS["record_type"]).select_option("1")
            page.wait_for_load_state("networkidle", timeout=15000)

            # Get districts
            print("[3] Getting available districts...")
            district_options = []
            district_elements = (
                page.locator(SELECTORS["district"]).locator("option").all()
            )

            for elem in district_elements:
                value = elem.get_attribute("value")
                text = elem.text_content()
                if (
                    value
                    and value not in ["0", "-1", ""]
                    and "select" not in text.lower()
                ):
                    district_options.append({"value": value, "text": text.strip()})

            print(f"Found {len(district_options)} districts:")
            for i, d in enumerate(district_options[:10]):  # Show first 10
                print(f"  {i + 1}. {d['text']} (code: {d['value']})")

            if district_options:
                # Select first district
                first_district = district_options[0]
                print(
                    f"\n[4] Selecting district: {first_district['text']} ({first_district['value']})"
                )
                page.locator(SELECTORS["district"]).select_option(
                    first_district["value"]
                )
                page.wait_for_load_state("networkidle", timeout=15000)

                # Get talukas
                print("[5] Getting talukas...")
                taluka_options = []
                taluka_elements = (
                    page.locator(SELECTORS["taluka"]).locator("option").all()
                )

                for elem in taluka_elements:
                    value = elem.get_attribute("value")
                    text = elem.text_content()
                    if (
                        value
                        and value not in ["0", "-1", ""]
                        and "select" not in text.lower()
                    ):
                        taluka_options.append({"value": value, "text": text.strip()})

                print(f"Found {len(taluka_options)} talukas:")
                for i, t in enumerate(taluka_options[:10]):  # Show first 10
                    print(f"  {i + 1}. {t['text']} (code: {t['value']})")

                if taluka_options:
                    # Select first taluka
                    first_taluka = taluka_options[0]
                    print(
                        f"\n[6] Selecting taluka: {first_taluka['text']} ({first_taluka['value']})"
                    )
                    page.locator(SELECTORS["taluka"]).select_option(
                        first_taluka["value"]
                    )
                    page.wait_for_load_state("networkidle", timeout=15000)

                    # Get villages
                    print("[7] Getting villages...")
                    village_options = []
                    village_elements = (
                        page.locator(SELECTORS["village"]).locator("option").all()
                    )

                    for elem in village_elements:
                        value = elem.get_attribute("value")
                        text = elem.text_content()
                        if (
                            value
                            and value not in ["0", "-1", ""]
                            and "select" not in text.lower()
                        ):
                            village_options.append(
                                {"value": value, "text": text.strip()}
                            )

                    print(f"Found {len(village_options)} villages:")
                    for i, v in enumerate(village_options[:10]):  # Show first 10
                        print(f"  {i + 1}. {v['text']} (code: {v['value']})")

                    if village_options:
                        # Select first village
                        first_village = village_options[0]
                        print(
                            f"\n[8] Selecting village: {first_village['text']} ({first_village['value']})"
                        )
                        page.locator(SELECTORS["village"]).select_option(
                            first_village["value"]
                        )
                        page.wait_for_load_state("networkidle", timeout=15000)

                        # Get survey numbers
                        print("[9] Getting survey numbers...")
                        survey_options = []
                        survey_elements = (
                            page.locator(SELECTORS["survey_no"]).locator("option").all()
                        )

                        for elem in survey_elements:
                            value = elem.get_attribute("value")
                            text = elem.text_content()
                            if (
                                value
                                and value not in ["0", "-1", ""]
                                and "select" not in text.lower()
                            ):
                                survey_options.append(
                                    {"value": value, "text": text.strip()}
                                )

                        print(f"Found {len(survey_options)} survey numbers:")
                        for i, s in enumerate(survey_options[:5]):  # Show first 5
                            print(f"  {i + 1}. {s['text']} (code: {s['value']})")

                        if survey_options:
                            # Save real codes to file
                            real_codes = {
                                "district": first_district,
                                "taluka": first_taluka,
                                "villages": village_options[
                                    :5
                                ],  # First 5 villages for testing
                                "sample_survey": survey_options[0],
                            }

                            import json

                            with open("real_codes.json", "w", encoding="utf-8") as f:
                                json.dump(real_codes, f, ensure_ascii=False, indent=2)

                            print(f"\n✅ SUCCESS: Real codes saved to real_codes.json")
                            print(
                                f"   District: {first_district['text']} ({first_district['value']})"
                            )
                            print(
                                f"   Taluka: {first_taluka['text']} ({first_taluka['value']})"
                            )
                            print(
                                f"   First Village: {first_village['text']} ({first_village['value']})"
                            )
                            print(
                                f"   Sample Survey: {survey_options[0]['text']} ({survey_options[0]['value']})"
                            )

                            return real_codes

            print(f"\n❌ Could not get complete hierarchy of codes")
            return None

        except Exception as e:
            print(f"\n❌ Error during discovery: {e}")
            import traceback

            traceback.print_exc()
            return None

        finally:
            browser.close()


if __name__ == "__main__":
    print("Starting real code discovery...")
    print("Browser will open visibly - wait for it to complete...")
    codes = discover_real_codes()

    if codes:
        print(f"\n🎯 Ready to test with real codes!")
        print(f"Update fixed_parallel_scraper.py with these codes:")
        print(f"  district_code = '{codes['district']['value']}'")
        print(f"  taluka_code = '{codes['taluka']['value']}'")
        print(f"  village_codes = {[v['value'] for v in codes['villages']]}")
    else:
        print(f"\n❌ Failed to discover real codes")
