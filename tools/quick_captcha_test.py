#!/usr/bin/env python3
"""Simple captcha extraction test"""

import asyncio
from playwright.async_api import async_playwright
import base64


async def quick_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("Opening website...")
        await page.goto("https://anyror.gujarat.gov.in/LandRecordRural.aspx")
        await asyncio.sleep(3)
        
        # Quick selections
        await page.locator("#ContentPlaceHolder1_drpLandRecord").select_option("1")
        await asyncio.sleep(1)
        await page.locator("#ContentPlaceHolder1_ddlDistrict").select_option("02")
        await asyncio.sleep(2)
        await page.locator("#ContentPlaceHolder1_ddlTaluka").select_option("01")
        await asyncio.sleep(2)
        await page.locator("#ContentPlaceHolder1_ddlVillage").select_option("001")
        await asyncio.sleep(1)
        
        # Get survey options
        survey_opts = await page.locator("#ContentPlaceHolder1_ddlSurveyNo option").all()
        if len(survey_opts) > 1:
            val = await survey_opts[1].get_attribute("value")
            await page.locator("#ContentPlaceHolder1_ddlSurveyNo").select_option(val)
            await asyncio.sleep(1)
        
        print("\n" + "="*60)
        print("EXTRACTING CAPTCHA IMAGE")
        print("="*60)
        
        # Get captcha
        img = page.locator("#ContentPlaceHolder1_i_captcha_1")
        src = await img.get_attribute("src")
        
        print(f"\n1. Captcha src starts with: {src[:30]}...")
        
        if src.startswith("data:image"):
            b64_data = src.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_data)
            print(f"2. Extracted from base64: {len(img_bytes)} bytes")
        else:
            img_bytes = await img.screenshot()
            print(f"2. Extracted from screenshot: {len(img_bytes)} bytes")
        
        # Save original
        with open("captcha_original.png", "wb") as f:
            f.write(img_bytes)
        print("3. Saved: captcha_original.png")
        
        # Now preprocess
        from PIL import Image, ImageEnhance, ImageFilter
        import io
        
        img_pil = Image.open(io.BytesIO(img_bytes))
        print(f"\n4. Original size: {img_pil.size} pixels, mode: {img_pil.mode}")
        
        # Apply preprocessing
        w, h = img_pil.size
        img_pil = img_pil.resize((w * 3, h * 3), Image.Resampling.LANCZOS)
        img_pil = img_pil.convert('L')
        
        enhancer = ImageEnhance.Contrast(img_pil)
        img_pil = enhancer.enhance(2.0)
        
        enhancer = ImageEnhance.Sharpness(img_pil)
        img_pil = enhancer.enhance(1.5)
        
        enhancer = ImageEnhance.Brightness(img_pil)
        img_pil = enhancer.enhance(1.1)
        
        img_pil = img_pil.point(lambda p: 255 if p > 115 else 0)
        img_pil = img_pil.filter(ImageFilter.MedianFilter(size=3))
        
        print(f"5. After preprocessing: {img_pil.size} pixels, mode: {img_pil.mode}")
        
        # Save preprocessed
        img_pil.save("captcha_preprocessed.png")
        print("6. Saved: captcha_preprocessed.png")
        
        print(f"\n7. Upscale factor: {img_pil.size[0] // w}x")
        print(f"8. Threshold used: 115 (black/white)")
        print(f"9. Contrast: 2.0x, Sharpness: 1.5x, Brightness: 1.1x")
        
        print("\n" + "="*60)
        print("DONE! Check the files:")
        print("  captcha_original.png     <- What we extract")
        print("  captcha_preprocessed.png <- What solvers get")
        print("="*60)
        
        print("\nPress Enter to close browser...")
        input()
        await browser.close()


asyncio.run(quick_test())
