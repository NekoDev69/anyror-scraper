"""
Captcha Solver using Local OCR (EasyOCR)
No API calls - runs entirely locally with deep learning
"""

import io
import numpy as np
from PIL import Image, ImageFilter, ImageOps
import easyocr


class LocalCaptchaSolver:
    """Solve captcha using local EasyOCR (deep learning based)"""
    
    def __init__(self):
        print("[CAPTCHA] Initializing EasyOCR (first run downloads model ~100MB)...")
        # Initialize EasyOCR - supports English characters/digits
        # gpu=False for CPU-only, set True if you have CUDA
        self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        print("[CAPTCHA] EasyOCR ready")
    
    def solve(self, image_bytes: bytes) -> str:
        """Process captcha image and extract text using EasyOCR"""
        print("[CAPTCHA] Processing with EasyOCR...")
        
        # Load image
        img = Image.open(io.BytesIO(image_bytes))
        
        # Try multiple preprocessing approaches
        results = []
        
        # Approach 1: Original image
        text1 = self._ocr(img)
        if text1:
            results.append(text1)
        
        # Approach 2: Grayscale + contrast
        processed2 = self._preprocess_contrast(img)
        text2 = self._ocr(processed2)
        if text2:
            results.append(text2)
        
        # Approach 3: Inverted (for dark backgrounds)
        processed3 = self._preprocess_inverted(img)
        text3 = self._ocr(processed3)
        if text3:
            results.append(text3)
        
        # Approach 4: Scaled up
        processed4 = self._preprocess_scaled(img)
        text4 = self._ocr(processed4)
        if text4:
            results.append(text4)
        
        # Pick the best result (longest alphanumeric string)
        if results:
            best = max(results, key=lambda x: len(x))
            print(f"[CAPTCHA] EasyOCR says: '{best}'")
            return best
        
        print("[CAPTCHA] No text detected")
        return ""
    
    def _ocr(self, img: Image.Image) -> str:
        """Run EasyOCR on image"""
        try:
            # Convert PIL to numpy array
            img_array = np.array(img)
            
            # Run OCR - allowlist restricts to alphanumeric
            results = self.reader.readtext(
                img_array,
                allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
                detail=0,  # Just return text, not bounding boxes
                paragraph=False
            )
            
            # Combine all detected text
            text = ''.join(results)
            return self._clean_captcha(text)
        except Exception as e:
            print(f"[CAPTCHA] OCR error: {e}")
            return ""
    
    def _preprocess_contrast(self, img: Image.Image) -> Image.Image:
        """High contrast preprocessing"""
        gray = img.convert('L')
        contrasted = ImageOps.autocontrast(gray, cutoff=10)
        sharpened = contrasted.filter(ImageFilter.SHARPEN)
        return sharpened
    
    def _preprocess_inverted(self, img: Image.Image) -> Image.Image:
        """Inverted for dark backgrounds"""
        gray = img.convert('L')
        inverted = ImageOps.invert(gray)
        contrasted = ImageOps.autocontrast(inverted, cutoff=5)
        return contrasted
    
    def _preprocess_scaled(self, img: Image.Image) -> Image.Image:
        """Scale up for better recognition"""
        gray = img.convert('L')
        width, height = gray.size
        scaled = gray.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
        sharpened = scaled.filter(ImageFilter.SHARPEN)
        return sharpened
    
    def _clean_captcha(self, text: str) -> str:
        """Clean captcha text - only keep ASCII alphanumeric"""
        cleaned = ""
        for c in text:
            if c.isascii() and c.isalnum():
                cleaned += c
        return cleaned


# For testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python captcha_solver_local.py <image_path>")
        sys.exit(1)
    
    solver = LocalCaptchaSolver()
    
    with open(sys.argv[1], 'rb') as f:
        img_bytes = f.read()
    
    result = solver.solve(img_bytes)
    print(f"Result: {result}")
