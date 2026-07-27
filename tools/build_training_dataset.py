# -*- coding: utf-8 -*-
"""Build unified training dataset from ALL sources including HF"""
from pathlib import Path
import shutil, xml.etree.ElementTree as ET, random, json
from collections import Counter
from sanitize_datasets import sanitize_dataset

random.seed(42)

ROBO = Path(r"F:\多类隐患检测系统_可移植包\多类隐患检测系统_可移植包\data\material_library\extracted\ppe-workplace-safety-v2")
ANDREW = Path.home() / ".cache" / "kagglehub" / "datasets" / "andrewmvd" / "face-mask-detection" / "versions" / "1"
CANDIDATES = Path(r"F:\多类隐患检测系统_可移植包\多类隐患检测系统_可移植包\data\material_library\new_candidates\annotated")
HF_EXT = Path(r"F:\多类隐患检测系统_可移植包\多类隐患检测系统_可移植包\data\material_library\hf_extracted")
TRAIN = Path(r"F:\多类隐患检测系统_可移植包\多类隐患检测系统_可移植包\data\training_dataset")

NAMES = {0:"Hardhat",1:"Mask",2:"NO-Hardhat",3:"NO-Mask",4:"NO-Safety Vest",
         5:"Person",6:"Safety Cone",7:"Safety Vest",8:"machinery",9:"vehicle"}

ROBO_MAP = {4:0, 5:1, 6:5, 7:7}
ROBO_KEEP = {4,5,6,7}

ANDREW_MAP = {"with_mask":1, "without_mask":3, "mask_weared_incorrect":1}

# HF class name -> model class
HF_CLASS_MAP = {
    "hardhat":0, "Hardhat":0, "helmet":0,
    "mask":1, "Mask":1,
    "no-hardhat":2, "NO-Hardhat":2, "no_hardhat":2, "without_hardhat":2, "No-Hardhat":2,
    "no-mask":3, "NO-Mask":3, "no_mask":3, "without_mask":3, "No-Mask":3,
    "no-safety vest":4, "no_safety_vest":4, "no-vest":4,
    "person":5, "Person":5, "people":5,
    "safety cone":6, "cone":6, "Safety Cone":6,
    "safety vest":7, "vest":7, "Safety Vest":7, "safety_vest":7,
    "excavators":8, "excavator":8, "wheel loader":8, "machinery":8,
    "vehicle":9, "truck":9, "dump truck":9, "dump_truck":9, "dumpster":9,
}

def convert_roboflow():
    copied = 0
    for split in ["train","valid","test"]:
        img_dir = ROBO / split / "images"
        lbl_dir = ROBO / split / "labels"
        out = "train" if split != "valid" else "val"
        for img_f in sorted(img_dir.glob("*")):
            if img_f.suffix.lower() not in (".jpg",".jpeg",".png"): continue
            lbl_f = lbl_dir / f"{img_f.stem}.txt"
            if not lbl_f.exists(): continue
            new_lines = []
            for line in lbl_f.read_text().strip().splitlines():
                if not line.strip(): continue
                parts = line.strip().split()
                cls = int(parts[0])
                if cls in ROBO_KEEP:
                    new_lines.append(f"{ROBO_MAP[cls]} {' '.join(parts[1:])}")
            if not new_lines: continue
            shutil.copy2(img_f, TRAIN / "images" / out / f"robo_{img_f.name}")
            (TRAIN / "labels" / out / f"robo_{img_f.stem}.txt").write_text("\n".join(new_lines))
            copied += 1
    print(f"[Roboflow] {copied} imgs")
    return copied

def convert_andrewmvd():
    copied = 0
    images = sorted((ANDREW / "images").glob("*"))
    random.shuffle(images)
    split_n = int(len(images) * 0.8)
    for i, img_f in enumerate(images):
        if img_f.suffix.lower() not in (".jpg",".jpeg",".png"): continue
        xml_f = ANDREW / "annotations" / f"{img_f.stem}.xml"
        if not xml_f.exists(): continue
        tree = ET.parse(xml_f); root = tree.getroot()
        width = height = 0
        for s in root.findall(".//width"): width = int(s.text)
        for s in root.findall(".//height"): height = int(s.text)
        if width == 0 or height == 0: continue
        out = "train" if i < split_n else "val"
        new_lines = []
        for obj in root.findall(".//object"):
            name = obj.find("name").text
            if name not in ANDREW_MAP: continue
            new_cls = ANDREW_MAP[name]
            bb = obj.find("bndbox")
            if bb is None: continue
            xmin = int(bb.find("xmin").text); ymin = int(bb.find("ymin").text)
            xmax = int(bb.find("xmax").text); ymax = int(bb.find("ymax").text)
            if xmin >= xmax or ymin >= ymax: continue
            x_c = max(0,min(1,((xmin+xmax)/2)/width))
            y_c = max(0,min(1,((ymin+ymax)/2)/height))
            bw = max(0.001,min(1,(xmax-xmin)/width))
            bh = max(0.001,min(1,(ymax-ymin)/height))
            new_lines.append(f"{new_cls} {x_c:.6f} {y_c:.6f} {bw:.6f} {bh:.6f}")
        if not new_lines: continue
        shutil.copy2(img_f, TRAIN / "images" / out / f"andrew_{img_f.name}")
        (TRAIN / "labels" / out / f"andrew_{img_f.stem}.txt").write_text("\n".join(new_lines))
        copied += 1
    print(f"[AndrewMVD] {copied} imgs")
    return copied

def add_candidates():
    copied = 0
    for img_f in sorted((CANDIDATES / "images").glob("*")):
        if img_f.suffix.lower() not in (".jpg",".jpeg",".png"): continue
        lbl_f = CANDIDATES / "labels" / f"{img_f.stem}.txt"
        if not lbl_f.exists(): continue
        shutil.copy2(img_f, TRAIN / "images" / "train" / f"site_{img_f.name}")
        shutil.copy2(lbl_f, TRAIN / "labels" / "train" / f"site_{img_f.stem}.txt")
        copied += 1
    print(f"[已复核工地图] {copied} imgs")
    return copied

def add_hf_datasets():
    """Add HuggingFace COCO datasets"""
    added = 0
    for ds_name, prefix in [("construction_safety","hfsafe"), ("excavator","hfexc")]:
        ds = HF_EXT / ds_name
        coco = ds / "_annotations.coco.json"
        if not coco.exists():
            for f in ds.rglob("_annotations.coco.json"): coco = f; break
        if not coco.exists(): continue
        
        ann = json.loads(coco.read_text())
        cats = {}
        for c in ann["categories"]:
            mapped = HF_CLASS_MAP.get(c["name"].lower().strip())
            if mapped is not None: cats[c["id"]] = mapped
        
        img_lookup = {img["id"]: img for img in ann["images"]}
        img_anns = {}
        for a in ann["annotations"]:
            img_anns.setdefault(a["image_id"], []).append(a)
        
        for img_id, info in img_lookup.items():
            anns = img_anns.get(img_id, [])
            if not anns: continue
            fname = info["file_name"]
            w, h = info.get("width", 640), info.get("height", 640)
            src = ds / fname
            if not src.exists(): continue
            
            yolo_lines = []
            for a in anns:
                if a["category_id"] not in cats: continue
                x, y, bw, bh = a["bbox"]
                x_c = max(0,min(1,(x+bw/2)/w))
                y_c = max(0,min(1,(y+bh/2)/h))
                bw_n = max(0.001,min(1,bw/w))
                bh_n = max(0.001,min(1,bh/h))
                yolo_lines.append(f"{cats[a['category_id']]} {x_c:.6f} {y_c:.6f} {bw_n:.6f} {bh_n:.6f}")
            if not yolo_lines: continue
            
            shutil.copy2(src, TRAIN / "images" / "train" / f"{prefix}_{fname}")
            (TRAIN / "labels" / "train" / f"{prefix}_{Path(fname).stem}.txt").write_text("\n".join(yolo_lines))
            added += 1
        
        print(f"[HF {ds_name}] {added} imgs")
    return added

def validate():
    cnt = Counter(); total_imgs = 0
    for split in ["train","val"]:
        for img_f in sorted((TRAIN/"images"/split).glob("*")):
            total_imgs += 1
            lbl_f = TRAIN / "labels" / split / f"{img_f.stem}.txt"
            if not lbl_f.exists(): continue
            for line in lbl_f.read_text().strip().splitlines():
                parts = line.strip().split()
                if parts: cnt[int(parts[0])] += 1
    print(f"\n=== Final Training Dataset ===")
    print(f"Images: {total_imgs} | Annotations: {sum(cnt.values())}")
    for cid in range(10):
        print(f"  {cid}: {NAMES[cid]:20s} {cnt[cid]:6d}")
    t = len(list((TRAIN/"images"/"train").glob("*")))
    v = len(list((TRAIN/"images"/"val").glob("*")))
    print(f"Train: {t} | Val: {v} ({v/max(t,1)*100:.1f}%)")
    return total_imgs, cnt

if __name__ == "__main__":
    print("Building training dataset...")
    # Clear previous
    for d in [TRAIN/"images"/"train", TRAIN/"images"/"val", TRAIN/"labels"/"train", TRAIN/"labels"/"val"]:
        d.mkdir(parents=True, exist_ok=True)
        for f in d.iterdir(): f.unlink()
    
    n1 = convert_roboflow()
    n2 = convert_andrewmvd()
    n3 = add_candidates()
    n4 = add_hf_datasets()
    sanitize_dataset(apply=True)
    validate()
