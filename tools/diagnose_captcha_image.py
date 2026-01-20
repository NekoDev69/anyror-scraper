"""
Diagnose captcha image capture to see what we're actually sending to Vision API
"""

from anyror_scraper import AnyRORScraper
from captcha_solver import CaptchaSolver
import time
from PIL import Image
import io

def diagnose_captcha():
    """Diagnose captcha image capture"""
    print("=" * 80)
    print("Diagnosing Captcha Image Capture")
    print("=" * 80)
    
    scraper = AnyRORScraper(headless=False)
    
    try:
        print("\n[1] Starting browser...")
        scraper.start()
        
        print("[2] Navigating to portal...")
        scraper.navigate()
        scraper.select_vf7()
        
        print("[3] Selecting location...")
        scraper.select_district()
        scraper.select_taluka()
        scraper.select_village()
        scraper.select_survey()
        
        time.sleep(2)
        
        print("\n[4] Analyzing captcha image element...")
        
        # Find the captcha image element
        captcha_img = scraper.page.locator("#ContentPlaceHolder1_imgCaptcha")
        
        if captcha_img.count() > 0:
            # Get image attributes
            src = captcha_img.get_attribute("src")
            img_id = captcha_img.get_attribute("id")
            width = captcha_img.get_attribute("width")
            height = captcha_img.get_attribute("height")
            
            print(f"\nCaptcha Image Attributes:")
            print(f"  ID: {img_id}")
            print(f"  Width: {width}")
            print(f"  Height: {height}")
            print(f"  Source: {src[:100] if src else 'None'}...")
            
            # Check if it's a data URL or regular URL
            if src and src.startswith("data:image"):
                print(f"  Type: Data URL (embedded image)")
            elif src and src.startswith("http"):
                print(f"  Type: External URL")
            elif src and src.startswith("/"):
                print(f"  Type: Relative URL")
            else:
                print(f"  Type: Unknown")
            
            # Get bounding box
            bbox = captcha_img.bounding_box()
            print(f"\nBounding Box:")
            print(f"  X: {bbox['x']}, Y: {bbox['y']}")
            print(f"  Width: {bbox['width']}, Height: {bbox['height']}")
            
            # Method 1: Screenshot the element
            print("\n[5] Method 1: Screenshot element...")
            img_bytes_1 = captcha_img.screenshot()
            with open("captcha_method1_element_screenshot.png", "wb") as f:
                f.write(img_bytes_1)
            print(f"  Saved: captcha_method1_element_screenshot.png ({len(img_bytes_1)} bytes)")
            
            # Analyze the image
            img1 = Image.open(io.BytesIO(img_bytes_1))
            print(f"  Image size: {img1.size}")
            print(f"  Image mode: {img1.mode}")
            
            # Method 2: Download the image directly from src
            if src and not src.startswith("data:"):
                print("\n[6] Method 2: Download from src URL...")
                try:
                    # Navigate to the image URL
                    full_url = src if src.startswith("http") else f"https://anyror.gujarat.gov.in{src}"
                    print(f"  URL: {full_url}")
                    
                    # Use page.goto to download
                    response = scraper.page.request.get(full_url)
                    img_bytes_2 = response.body()
                    
                    with open("captcha_method2_direct_download.png", "wb") as f:
                        f.write(img_bytes_2)
                    print(f"  Saved: captcha_method2_direct_download.png ({len(img_bytes_2)} bytes)")
                    
                    img2 = Image.open(io.BytesIO(img_bytes_2))
                    print(f"  Image size: {img2.size}")
                    print(f"  Image mode: {img2.mode}")
                except Exception as e:
                    print(f"  Error: {e}")
            
            # Method 3: Screenshot with padding
            print("\n[7] Method 3: Screenshot with padding...")
            img_bytes_3 = captcha_img.screenshot()
            with open("captcha_method3_with_padding.png", "wb") as f:
                f.write(img_bytes_3)
            print(f"  Saved: captcha_method3_with_padding.png ({len(img_bytes_3)} bytes)")
            
            # Method 4: Get via evaluate (extract base64 from canvas if it's canvas)
            print("\n[8] Method 4: Check if it's a canvas element...")
            try:
                is_canvas = scraper.page.evaluate("""
                    () => {
                        const img = document.querySelector('#ContentPlaceHolder1_imgCaptcha');
                        return img ? img.tagName : null;
                    }
                """)
                print(f"  Element type: {is_canvas}")
            except Exception as e:
                print(f"  Error: {e}")
            
            # Now test Vision API on each method
            print("\n" + "=" * 80)
            print("Testing Vision API on each method")
            print("=" * 80)
            
            solver = CaptchaSolver()
            
            print("\n[Method 1] Element screenshot:")
            result1 = solver._solve_with_vision(img_bytes_1)
            print(f"  Result: '{result1}'")
            
            if src and not src.startswith("data:"):
                print("\n[Method 2] Direct download:")
                try:
                    result2 = solver._solve_with_vision(img_bytes_2)
                    print(f"  Result: '{result2}'")
                except:
                    print("  Skipped (download failed)")
            
            print("\n[Method 3] With padding:")
            result3 = solver._solve_with_vision(img_bytes_3)
            print(f"  Result: '{result3}'")
            
            # Keep browser open
            print("\n[9] Keeping browser open for 30 seconds for manual inspection...")
            print("     Please visually verify the captcha in the browser!")
            time.sleep(30)
            
        else:
            print("[ERROR] Captcha image not found!")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n[10] Closing browser...")
        scraper.close()
        print("\n✓ Diagnosis complete!")
        print("\nPlease check the saved images:")
        print("  - captcha_method1_element_screenshot.png")
        print("  - captcha_method2_direct_download.png")
        print("  - captcha_method3_with_padding.png")

if __name__ == "__main__":
    diagnose_captcha()

