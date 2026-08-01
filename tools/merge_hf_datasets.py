# -*- coding: utf-8 -*-
"""Convert HF COCO datasets to YOLO and merge into training set"""
import json, shutil, random
from pathlib import Path
from collections import Counter

random.seed(42)

ROOT = Path(__file__).resolve().parents[1]
HF = ROOT / "data" / "material_library" / "hf_extracted"
TRAIN = ROOT / "data" / "training_dataset"

# Model class names for mapping
MODEL_NAMES = {0:"Hardhat",1:"Mask",2:"NO-Hardhat",3:"NO-Mask",4:"NO-Safety Vest",
               5:"Person",6:"Safety Cone",7:"Safety Vest",8:"machinery",9:"vehicle"}

# Map HF dataset class names to our model class IDs
CLASS_MAP = {
    "hardhat": 0, "Hardhat": 0, "helmet": 0,
    "mask": 1, "Mask": 1,
    "no-hardhat": 2, "NO-Hardhat": 2, "no_hardhat": 2, "without_hardhat": 2, "No-Hardhat": 2,
    "no-mask": 3, "NO-Mask": 3, "no_mask": 3, "without_mask": 3, "No-Mask": 3,
    "no-safety vest": 4, "no_safety_vest": 4, "No-Safety Vest": 4, "no safety vest": 4, "no-vest": 4,
    "person": 5, "Person": 5, "people": 5,
    "safety cone": 6, "cone": 6, "traffic cone": 6, "traffic_cone": 6, "Safety Cone": 6,
    "safety vest": 7, "vest": 7, "Safety Vest": 7, "safety_vest": 7,
    "excavators": 8, "excavator": 8, "wheel loader": 8, "wheel_loader": 8,
    "vehicle": 9, "truck": 9, "dump truck": 9, "dump_truck": 9,
}

def convert_coco(ds_name, prefix):
    ds_dir = HF / ds_name
    coco = ds_dir / "_annotations.coco.json"
    if not coco.exists():
        # Try to find COCO files in subdirectories
        for f in ds_dir.rglob("_annotations.coco.json"):
            coco = f
            break
    if not coco.exists():
        print(f"  No COCO file for {ds_name}")
        return 0
    
    ann = json.loads(coco.read_text())
    
    # Get class names and map
    cats = {}
    for c in ann["categories"]:
        cid = c["id"]
        name = c["name"]
        mapped = CLASS_MAP.get(name, None)
        if mapped is None:
            # Try lowercase
            mapped = CLASS_MAP.get(name.lower().strip(), None)
        if mapped is not None:
            cats[cid] = mapped
    
    if not cats:
        print(f"  No mapped classes for {ds_name}")
        return 0
    
    # Create image lookup
    img_lookup = {img["id"]: img for img in ann["images"]}
    
    # Group annotations by image
    img_anns = {}
    for a in ann["annotations"]:
        img_id = a["image_id"]
        if img_id not in img_anns:
            img_anns[img_id] = []
        img_anns[img_id].append(a)
    
    copied = 0
    for img_id, img_info in img_lookup.items():
        anns = img_anns.get(img_id, [])
        if not anns:
            continue
        
        fname = img_info["file_name"]
        w, h = img_info.get("width", 640), img_info.get("height", 640)
        
        src_img = ds_dir / fname
        if not src_img.exists():
            continue
        
        # Convert annotations to YOLO
        yolo_lines = []
        for a in anns:
            cid = a["category_id"]
            if cid not in cats:
                continue
            cls_id = cats[cid]
            bbox = a["bbox"]  # COCO: x, y, w, h
            x, y, bw, bh = bbox
            x_c = (x + bw / 2) / w
            y_c = (y + bh / 2) / h
            bw_n = bw / w
            bh_n = bh / h
            x_c = max(0, min(1, x_c))
            y_c = max(0, min(1, y_c))
            bw_n = max(0.001, min(1, bw_n))
            bh_n = max(0.001, min(1, bh_n))
            yolo_lines.append(f"{cls_id} {x_c:.6f} {y_c:.6f} {bw_n:.6f} {bh_n:.6f}")
        
        if not yolo_lines:
            continue
        
        # Copy image
        shutil.copy2(src_img, TRAIN / "images" / "train" / f"{prefix}_{fname}")
        (TRAIN / "labels" / "train" / f"{prefix}_{Path(fname).stem}.txt").write_text("\n".join(yolo_lines))
        copied += 1
    
    return copied


# Process each dataset
for ds_name, prefix in [("construction_safety","hfsafe"), ("excavator","hfexc")]:
    print(f"\n=== {ds_name} ===")
    n = convert_coco(ds_name, prefix)
    print(f"  添加: {n} 张")

# Also try the traffic_cone dataset
cone_dir = HF / "traffic_cone"
if cone_dir.exists():
    print(f"\n=== traffic_cone ===")
    # Might have a different structure
    for f in cone_dir.rglob("*"):
        if f.name.endswith(".zip"):
            print(f"  Found zip: {f.name} ({f.stat().st_size/1024/1024:.0f} MB)")

# Final stats
from collections import Counter
cnt = Counter()
total_imgs = 0
for split in ["train","val"]:
    for img_f in sorted((TRAIN / "images" / split).glob("*")):
        total_imgs += 1
        lbl = TRAIN / "labels" / split / f"{img_f.stem}.txt"
        if lbl.exists():
            for l in lbl.read_text().strip().splitlines():
                if l.strip(): cnt[int(l.split()[0])] += 1

NAMES = ["Hardhat","Mask","NO-Hardhat","NO-Mask","NO-Safety Vest","Person","Safety Cone","Safety Vest","machinery","vehicle"]
print(f"\n=== Updated Training Dataset ===")
print(f"Total images: {total_imgs}")
for cid in range(10):
    print(f"  {cid}: {NAMES[cid]:20s} {cnt[cid]:6d}")
t = len(list((TRAIN/"images"/"train").glob("*")))
v = len(list((TRAIN/"images"/"val").glob("*")))
print(f"Train: {t} | Val: {v}")
