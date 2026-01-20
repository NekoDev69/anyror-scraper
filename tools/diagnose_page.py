#!/usr/bin/env python3
"""
Quick diagnostic to see what's on the AnyROR page
"""

from playwright.sync_api import sync_playwright
import time

print("="*70)
print("DIAGNOSING ANYROR PAGE")
print("="*70)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # Navigate
    print("\n1. Navigating to AnyROR...")
    page.goto("https://anyror.gujarat.gov.in/LandRecordRural.aspx")
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    
    # Select VF-7
    print("2. Selecting VF-7...")
    page.locator("#ContentPlaceHolder1_drpLandRecord").select_option("1")
    time.sleep(2)
    
    # Select random district
    print("3. Selecting district...")
    district_options = page.locator("#ContentPlaceHolder1_ddlDistrict option").all()
    valid_districts = [o for o in district_options if o.get_attribute("value") not in ["0", "-1", ""]]
    if valid_districts:
        valid_districts[5].click()  # Select 6th district
        time.sleep(2)
    
    # Select taluka
    print("4. Selecting taluka...")
    taluka_options = page.locator("#ContentPlaceHolder1_ddlTaluka option").all()
    valid_talukas = [o for o in taluka_options if o.get_attribute("value") not in ["0", "-1", ""]]
    if valid_talukas:
        valid_talukas[0].click()
        time.sleep(2)
    
    # Select village
    print("5. Selecting village...")
    village_options = page.locator("#ContentPlaceHolder1_ddlVillage option").all()
    valid_villages = [o for o in village_options if o.get_attribute("value") not in ["0", "-1", ""]]
    if valid_villages:
        valid_villages[0].click()
        time.sleep(2)
    
    # Select survey
    print("6. Selecting survey...")
    survey_options = page.locator("#ContentPlaceHolder1_ddlSurveyNo option").all()
    valid_surveys = [o for o in survey_options if o.get_attribute("value") not in ["0", "-1", ""]]
    if valid_surveys:
        valid_surveys[0].click()
        time.sleep(2)
    
    # Now look for captcha
    print("\n7. Looking for captcha elements...")
    print("-"*70)
    
    selectors = [
        "#ContentPlaceHolder1_imgCaptcha",
        "#ContentPlaceHolder1_i_captcha_1",
        "img[id*='captcha']",
        "img[id*='Captcha']",
        "img[src*='captcha']",
        "img[src*='Captcha']",
    ]
    
    found = False
    for sel in selectors:
        count = page.locator(sel).count()
        if count > 0:
            found = True
            print(f"✓ FOUND: {sel} ({count} elements)")
            src = page.locator(sel).first.get_attribute("src")
            print(f"    src: {src[:100] if src else 'None'}...")
        else:
            print(f"✗ {sel}: not found")
    
    # Check all images
    print("\n8. All images on page:")
    print("-"*70)
    imgs = page.locator("img").all()
    for i, img in enumerate(imgs):
        img_id = img.get_attribute("id") or "no-id"
        src = img.get_attribute("src") or "no-src"
        print(f"  [{i+1}] id='{img_id}' src='{src[:60]}...'")
    
    # Save screenshot
    page.screenshot(path="page_state.png", full_page=True)
    print("\n✓ Saved: page_state.png")
    
    if not found:
        print("\n❌ NO CAPTCHA FOUND - checking page HTML...")
        html = page.content()
        if "captcha" in html.lower():
            print("  'captcha' IS in the HTML somewhere")
            # Find lines with captcha
            import re
            matches = re.findall(r'.*[cC]aptcha.*', html)
            for m in matches[:5]:
                print(f"    {m[:100]}...")
        else:
            print("  'captcha' NOT in HTML at all")
    
    print("\n\nBrowser will close in 30 seconds...")
    print("Inspect the browser window to see the page state")
    time.sleep(30)
    browser.close()

print("\n" + "="*70)
print("DIAGNOSIS COMPLETE")
print("="*70)

