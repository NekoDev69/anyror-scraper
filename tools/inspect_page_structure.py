"""
Inspect the page structure to understand captcha placement
"""

from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    print("Navigating...")
    page.goto("https://anyror.gujarat.gov.in/LandRecordRural.aspx")
    time.sleep(2)
    
    print("Selecting VF-7...")
    page.select_option("#ContentPlaceHolder1_drpLandRecord", "VF7")
    time.sleep(2)
    
    # Get all images on the page
    print("\n" + "=" * 80)
    print("ALL IMAGES ON PAGE:")
    print("=" * 80)
    
    all_imgs = page.locator("img").all()
    for i, img in enumerate(all_imgs):
        try:
            img_id = img.get_attribute("id") or "no-id"
            src = img.get_attribute("src") or "no-src"
            print(f"\n[Image {i+1}]")
            print(f"  ID: {img_id}")
            print(f"  SRC: {src[:100]}")
        except:
            pass
    
    # Check captcha specifically
    print("\n" + "=" * 80)
    print("CAPTCHA IMAGE DETAILS:")
    print("=" * 80)
    
    captcha = page.locator("#ContentPlaceHolder1_imgCaptcha")
    if captcha.count() > 0:
        print(f"Count: {captcha.count()}")
        print(f"ID: {captcha.get_attribute('id')}")
        print(f"SRC: {captcha.get_attribute('src')}")
        print(f"Class: {captcha.get_attribute('class')}")
        
        # Get parent HTML
        parent_html = page.evaluate("""
            () => {
                const img = document.querySelector('#ContentPlaceHolder1_imgCaptcha');
                return img ? img.parentElement.outerHTML : null;
            }
        """)
        print(f"\nParent HTML:\n{parent_html}")
        
        # Take screenshot
        img_bytes = captcha.screenshot()
        with open("captcha_inspect.png", "wb") as f:
            f.write(img_bytes)
        print(f"\nSaved screenshot: captcha_inspect.png ({len(img_bytes)} bytes)")
    
    print("\nKeeping browser open for 30 seconds...")
    time.sleep(30)
    
    browser.close()

