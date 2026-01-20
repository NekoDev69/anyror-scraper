#!/usr/bin/env python3
"""
Captcha Image Diagnostic Tool
Shows what we extract and send to captcha solvers
"""

import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright
from captcha_solver import CaptchaSolver


async def diagnose_captcha():
    """Extract and analyze captcha images"""
    
    print("=" * 70)
    print("🔍 CAPTCHA IMAGE DIAGNOSTIC TOOL")
    print("=" * 70)
    print()
    
    # Create output directory
    output_dir = "captcha_debug"
    os.makedirs(output_dir, exist_ok=True)
    
    async with async_playwright() as p:
        print("[1/5] Launching browser...")
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("[2/5] Navigating to AnyROR...")
        await page.goto("https://anyror.gujarat.gov.in/LandRecordRural.aspx")
        await asyncio.sleep(2)
        
        # Select VF-7
        print("[3/5] Selecting VF-7 form...")
        await page.locator("#ContentPlaceHolder1_drpLandRecord").select_option("1")
        await asyncio.sleep(1)
        
        # Select district
        await page.locator("#ContentPlaceHolder1_ddlDistrict").select_option("02")
        await asyncio.sleep(2)
        
        # Select taluka
        await page.locator("#ContentPlaceHolder1_ddlTaluka").select_option("01")
        await asyncio.sleep(2)
        
        # Select village
        await page.locator("#ContentPlaceHolder1_ddlVillage").select_option("001")
        await asyncio.sleep(1)
        
        # Select survey
        await page.locator("#ContentPlaceHolder1_ddlSurveyNo").select_option(value="1")
        await asyncio.sleep(1)  # Wait for captcha to load
        
        print("[4/5] Extracting captcha image...")
        
        # Get captcha image
        captcha_selector = "#ContentPlaceHolder1_i_captcha_1"
        img = page.locator(captcha_selector)
        
        # Method 1: Get base64 from src attribute
        src = await img.get_attribute("src")
        print(f"   Captcha src attribute type: {src[:20]}...")
        
        if src and src.startswith("data:image"):
            import base64
            base64_data = src.split(",", 1)[1]
            original_bytes = base64.b64decode(base64_data)
            print(f"   ✓ Extracted {len(original_bytes)} bytes from base64")
            
            # Save original
            original_file = f"{output_dir}/01_original.png"
            with open(original_file, "wb") as f:
                f.write(original_bytes)
            print(f"   ✓ Saved: {original_file}")
        else:
            # Fallback: Screenshot
            original_bytes = await img.screenshot()
            original_file = f"{output_dir}/01_original.png"
            with open(original_file, "wb") as f:
                f.write(original_bytes)
            print(f"   ✓ Saved screenshot: {original_file}")
        
        print()
        print("[5/5] Processing with captcha solver...")
        print()
        
        # Initialize solver
        solver = CaptchaSolver()
        
        # Show what preprocessing does
        from PIL import Image
        import io
        
        # Save preprocessed version
        preprocessed_bytes = solver._preprocess_image(original_bytes)
        preprocessed_file = f"{output_dir}/02_preprocessed.png"
        with open(preprocessed_file, "wb") as f:
            f.write(preprocessed_bytes)
        print(f"   ✓ Preprocessed image: {preprocessed_file}")
        
        # Show image properties
        img_orig = Image.open(io.BytesIO(original_bytes))
        img_proc = Image.open(io.BytesIO(preprocessed_bytes))
        
        print()
        print("=" * 70)
        print("📊 IMAGE ANALYSIS")
        print("=" * 70)
        print()
        print(f"Original Image:")
        print(f"  Size: {img_orig.size[0]}x{img_orig.size[1]} pixels")
        print(f"  Mode: {img_orig.mode}")
        print(f"  Bytes: {len(original_bytes)}")
        print()
        print(f"Preprocessed Image:")
        print(f"  Size: {img_proc.size[0]}x{img_proc.size[1]} pixels")
        print(f"  Mode: {img_proc.mode}")
        print(f"  Bytes: {len(preprocessed_bytes)}")
        print(f"  Upscale: {img_proc.size[0] // img_orig.size[0]}x")
        print()
        
        # Try solving with each method
        print("=" * 70)
        print("🔬 TESTING CAPTCHA SOLVERS")
        print("=" * 70)
        print()
        
        # Test Vision API
        if solver.vision_client:
            print("Vision API:")
            result = solver._solve_with_vision(original_bytes)
            print(f"  Raw result: '{result}'")
            print(f"  Length: {len(result)}")
            print(f"  Is alphanumeric: {result.replace(' ', '').isalnum()}")
            print(f"  Valid (4-8 chars): {4 <= len(result) <= 8}")
            print()
        
        # Test EasyOCR
        if solver.easyocr_reader:
            print("EasyOCR:")
            result = solver._solve_with_easyocr(original_bytes)
            print(f"  Raw result: '{result}'")
            print(f"  Length: {len(result)}")
            print(f"  Is alphanumeric: {result.replace(' ', '').isalnum()}")
            print(f"  Valid (4-8 chars): {4 <= len(result) <= 8}")
            print()
        
        # Test Gemini
        if solver.gemini_api_key:
            print("Gemini AI:")
            result = solver._solve_with_gemini(original_bytes)
            print(f"  Raw result: '{result}'")
            print(f"  Length: {len(result)}")
            print(f"  Is alphanumeric: {result.replace(' ', '').isalnum()}")
            print(f"  Valid (4-8 chars): {4 <= len(result) <= 8}")
            print()
        
        # Final solve method (uses validation)
        print("=" * 70)
        print("Final Solver (with validation):")
        final_result = solver.solve(original_bytes)
        print(f"  Selected result: '{final_result}'")
        print()
        
        print("=" * 70)
        print("✅ DIAGNOSTIC COMPLETE")
        print("=" * 70)
        print()
        print(f"Check {output_dir}/ folder for images:")
        print(f"  - 01_original.png (What we extracted)")
        print(f"  - 02_preprocessed.png (What Vision/EasyOCR receive)")
        print()
        print("Open these images to see:")
        print("  1. If captcha is being extracted correctly")
        print("  2. If preprocessing is preserving text")
        print("  3. If text is readable after processing")
        print()
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(diagnose_captcha())
