#!/usr/bin/env python3
"""Quick test of simplified captcha solver"""

import base64
from captcha_solver import CaptchaSolver

# Read captchas
with open('base64.md', 'r') as f:
    captchas = [line.strip() for line in f if line.strip().startswith('data:image')]

print(f"Testing {len(captchas)} captchas with Vision API\n")

solver = CaptchaSolver()
results = []

for i, data_uri in enumerate(captchas, 1):
    # Decode
    b64 = data_uri.split(",", 1)[1]
    png_bytes = base64.b64decode(b64)
    
    # Solve
    result = solver.solve(png_bytes, max_attempts=2)
    
    if result:
        print(f"#{i}: ✅ '{result}'")
        results.append(result)
    else:
        print(f"#{i}: ❌ FAILED")
        results.append(None)
    print()

# Summary
print("="*50)
success = sum(1 for r in results if r)
print(f"Success: {success}/{len(captchas)}")
print(f"Results: {[r for r in results if r]}")
print("="*50)
