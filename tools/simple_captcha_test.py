"""
Simple test to capture and analyze captcha image
"""

from playwright.sync_api import sync_playwright
import time
from PIL import Image
import io

def test_captcha_capture():
    print("Testing captcha image capture methods...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print("\n[1] Navigating to AnyROR...")
        page.goto("https://anyror.gujarat.gov.in/LandRecordRural.aspx")
        time.sleep(3)
        
        print("[2] Selecting VF-7...")
        page.select_option("#ContentPlaceHolder1_drpLandRecord", "VF7")
        time.sleep(2)
        
        print("[3] Analyzing captcha image...")
        
        # Get captcha image element
        captcha_selector = "#ContentPlaceHolder1_imgCaptcha"
        
        # Check if element exists
        if page.locator(captcha_selector).count() > 0:
            # Get src attribute
            src = page.locator(captcha_selector).get_attribute("src")
            print(f"\nCaptcha src: {src[:200] if src else 'None'}...")
            
            # Get bounding box
            bbox = page.locator(captcha_selector).bounding_box()
            print(f"Bounding box: {bbox}")
            
            # Method 1: Screenshot the element
            print("\n[Method 1] Screenshot element...")
            img_bytes = page.locator(captcha_selector).screenshot()
            
            with open("test_captcha_element.png", "wb") as f:
                f.write(img_bytes)
            
            # Analyze
            img = Image.open(io.BytesIO(img_bytes))
            print(f"  Size: {img.size}")
            print(f"  Mode: {img.mode}")
            print(f"  Bytes: {len(img_bytes)}")
            print(f"  Saved: test_captcha_element.png")
            
            # Method 2: Try to get the actual image source
            if src:
                print(f"\n[Method 2] Image source analysis...")
                if src.startswith("Captcha.aspx"):
                    full_url = f"https://anyror.gujarat.gov.in/{src}"
                    print(f"  Full URL: {full_url}")
                    
                    # Try to fetch it
                    try:
                        response = page.request.get(full_url)
                        img_bytes_2 = response.body()
                        
                        with open("test_captcha_direct.png", "wb") as f:
                            f.write(img_bytes_2)
                        
                        img2 = Image.open(io.BytesIO(img_bytes_2))
                        print(f"  Size: {img2.size}")
                        print(f"  Mode: {img2.mode}")
                        print(f"  Bytes: {len(img_bytes_2)}")
                        print(f"  Saved: test_captcha_direct.png")
                    except Exception as e:
                        print(f"  Error fetching: {e}")
            
            # Method 3: Screenshot a region around it
            print(f"\n[Method 3] Screenshot region...")
            if bbox:
                # Add padding
                clip = {
                    "x": max(0, bbox["x"] - 10),
                    "y": max(0, bbox["y"] - 10),
                    "width": bbox["width"] + 20,
                    "height": bbox["height"] + 20
                }
                img_bytes_3 = page.screenshot(clip=clip)
                
                with open("test_captcha_region.png", "wb") as f:
                    f.write(img_bytes_3)
                
                img3 = Image.open(io.BytesIO(img_bytes_3))
                print(f"  Size: {img3.size}")
                print(f"  Mode: {img3.mode}")
                print(f"  Bytes: {len(img_bytes_3)}")
                print(f"  Saved: test_captcha_region.png")
            
            # Now test with Vision API
            print("\n" + "=" * 60)
            print("Testing with Google Vision API")
            print("=" * 60)
            
            from captcha_solver import CaptchaSolver
            solver = CaptchaSolver()
            
            print("\n[Vision Test 1] Element screenshot:")
            result1 = solver._solve_with_vision(img_bytes)
            print(f"  Result: '{result1}'")
            
            if 'img_bytes_2' in locals():
                print("\n[Vision Test 2] Direct download:")
                result2 = solver._solve_with_vision(img_bytes_2)
                print(f"  Result: '{result2}'")
            
            if 'img_bytes_3' in locals():
                print("\n[Vision Test 3] Region screenshot:")
                result3 = solver._solve_with_vision(img_bytes_3)
                print(f"  Result: '{result3}'")
            
            # Test all 3 OCR methods
            print("\n" + "=" * 60)
            print("Testing ALL OCR methods on element screenshot")
            print("=" * 60)
            result_all = solver.solve(img_bytes)
            print(f"\nFinal result: '{result_all}'")
            
            print("\n[4] Keeping browser open for 20 seconds...")
            print("    Please visually check the captcha!")
            time.sleep(20)
            
        else:
            print("[ERROR] Captcha element not found!")
        
        browser.close()
        print("\n✓ Test complete!")

if __name__ == "__main__":
    test_captcha_capture()

