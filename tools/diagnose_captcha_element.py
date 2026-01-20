#!/usr/bin/env python3
"""
Diagnose why captcha element is not being found
"""

from playwright.sync_api import sync_playwright
import time

print("="*70)
print("DIAGNOSING CAPTCHA ELEMENT")
print("="*70)

with sync_playwright() as p:
    print("\n1. Launching browser...")
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    print("2. Navigating to AnyROR...")
    page.goto("https://anyror.gujarat.gov.in/LandRecordRural.aspx")
    page.wait_for_load_state("networkidle")

    print("3. Selecting VF-7...")
    page.locator("#ContentPlaceHolder1_drpLandRecord").select_option("1")
    time.sleep(2)
    
    print("\n4. Checking for captcha elements...")
    print("-"*70)
    
    # Try different selectors
    selectors = [
        "#ContentPlaceHolder1_imgCaptcha",
        "img[id*='Captcha']",
        "img[id*='captcha']",
        "img[src*='Captcha']",
        "img[src*='captcha']",
        "#imgCaptcha",
    ]
    
    for selector in selectors:
        count = page.locator(selector).count()
        print(f"  {selector:40} -> {count} element(s)")
        
        if count > 0:
            try:
                src = page.locator(selector).first.get_attribute("src")
                print(f"    src: {src[:80] if src else 'None'}...")
            except:
                pass
    
    print("\n5. Checking all images on page...")
    print("-"*70)
    
    all_imgs = page.locator("img").all()
    print(f"  Total images: {len(all_imgs)}")
    
    for i, img in enumerate(all_imgs):
        try:
            img_id = img.get_attribute("id") or "no-id"
            src = img.get_attribute("src") or "no-src"
            print(f"  [{i+1}] id='{img_id}' src='{src[:60]}...'")
        except:
            pass
    
    print("\n6. Checking page HTML for captcha...")
    print("-"*70)
    
    html = page.content()
    if "captcha" in html.lower():
        print("  ✓ 'captcha' found in HTML")
        # Find lines with captcha
        lines = html.split('\n')
        captcha_lines = [line.strip() for line in lines if 'captcha' in line.lower()]
        print(f"  Found {len(captcha_lines)} lines with 'captcha'")
        for line in captcha_lines[:5]:  # Show first 5
            print(f"    {line[:100]}...")
    else:
        print("  ✗ 'captcha' NOT found in HTML")
    
    print("\n7. Waiting for user to inspect...")
    print("  Check the browser window to see the page state")
    print("  Press Ctrl+C when done")
    
    try:
        time.sleep(300)  # Wait 5 minutes
    except KeyboardInterrupt:
        print("\n  Interrupted by user")
    
    browser.close()
    
print("\n" + "="*70)
print("DIAGNOSIS COMPLETE")
print("="*70)

