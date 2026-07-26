# -*- coding: utf-8 -*-
"""Debug Bing image download"""
import requests, re, time
from urllib.parse import quote
from pathlib import Path
from io import BytesIO
from PIL import Image

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

query = "construction worker hardhat mask safety vest"
url = f"https://www.bing.com/images/search?q={quote(query)}&count=20"
r = requests.get(url, headers=HEADERS, timeout=15)
print(f"Status: {r.status_code}, Content length: {len(r.text)}")

# Save HTML for analysis
out = Path(__file__).resolve().parent / "bing_debug.html"
out.write_text(r.text, encoding="utf-8")
print(f"Saved debug HTML to {out}")

# Extract URLs from multiple patterns
found = set()
for pattern in [r'"murl":"([^"]+)"', r'mediaurl":"([^"]+)"', r'"contentUrl":"([^"]+)"', r'"src":"([^"]+)"']:
    for m in re.finditer(pattern, r.text):
        u = m.group(1).replace("\\", "").replace("u0026", "&")
        if u.startswith("http"):
            found.add(u)

print(f"\nFound {len(found)} image URLs")

# Try downloading each
downloaded = 0
for i, img_url in enumerate(list(found)[:10]):
    time.sleep(0.5)
    try:
        ir = requests.get(img_url, headers=HEADERS, timeout=15)
        if ir.status_code == 200 and len(ir.content) > 4096:
            img = Image.open(BytesIO(ir.content))
            w, h = img.size
            print(f"  [{i+1}] OK {img_url[:60]}... {w}x{h} {len(ir.content)//1024}KB")
            fname = f"test_{i}.jpg"
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(str(RAW_DIR / fname), "JPEG", quality=92)
            downloaded += 1
        else:
            print(f"  [{i+1}] FAIL {img_url[:60]}... status={ir.status_code} size={len(ir.content)}")
    except Exception as e:
        print(f"  [{i+1}] ERR {img_url[:60]}... {e}")

print(f"\nDownloaded: {downloaded} images to {RAW_DIR}")
