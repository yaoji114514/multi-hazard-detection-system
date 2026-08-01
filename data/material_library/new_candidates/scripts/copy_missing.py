# -*- coding: utf-8 -*-
"""Copy new missing-class images to raw and auto-label"""
from pathlib import Path
from PIL import Image
import hashlib

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "data" / "material_library" / "missing_classes"
RAW = ROOT / "data" / "material_library" / "new_candidates" / "raw"

seen = set(f.stem[:16] for f in RAW.glob("*.jpg"))
copied = 0
cats = 0

for f in sorted(SRC.rglob("*")):
    if f.suffix.lower() not in (".jpg",".jpeg",".png",".webp"):
        continue
    try:
        data = f.read_bytes()
        if len(data) < 4096:
            cats += 1
            print(f"  太小: {f.parent.name[:15]}/{f.name[:25]}")
            continue
        h = hashlib.md5(data).hexdigest()[:16]
        if h in seen:
            continue
        seen.add(h)
        img = Image.open(f)
        w, h_img = img.size
        if w < 300 or h_img < 300:
            cats += 1
            print(f"  太小: {f.parent.name[:15]}/{f.name[:25]} ({w}x{h_img})")
            continue
        img = img.convert("RGB")
        img.save(RAW / f"{h}.jpg", "JPEG", quality=92)
        copied += 1
        print(f"  OK: {f.parent.name[:15]}/{f.name[:25]} ({w}x{h_img})")
    except:
        pass

total = len(list(RAW.glob("*.jpg")))
print(f"\n新增: {copied} 张 | 总计 raw: {total} 张")
