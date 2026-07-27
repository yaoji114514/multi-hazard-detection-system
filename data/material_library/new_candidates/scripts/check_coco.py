# -*- coding: utf-8 -*-
"""Check COCO annotation files from HF datasets"""
import json
from pathlib import Path
from collections import Counter

BASE = Path(r"F:\多类隐患检测系统_可移植包\多类隐患检测系统_可移植包\data\material_library\hf_extracted")

for ds_name in ["construction_safety", "excavator"]:
    ds = BASE / ds_name
    cf = ds / "_annotations.coco.json"
    if not cf.exists():
        print(f"No COCO file for {ds_name}")
        continue
    ann = json.loads(cf.read_text())
    cats = {c["id"]: c["name"] for c in ann["categories"]}
    cc = Counter()
    for a in ann["annotations"]:
        cc[a["category_id"]] += 1
    
    print(f"\n=== {ds_name} ===")
    for cid, name in sorted(cats.items()):
        print(f"  {name:30s} {cc[cid]:5d}")
    print(f"  {'Images':30s} {len(ann['images']):5d}")
    print(f"  {'Total annotations':30s} {len(ann['annotations']):5d}")
