import os, sys, json, shutil, hashlib
from pathlib import Path
from collections import Counter

BASE = Path(__file__).resolve().parents[1]
TRAIN_IMG = BASE / 'data' / 'training_dataset' / 'images' / 'train'
TRAIN_LBL = BASE / 'data' / 'training_dataset' / 'labels' / 'train'

NAMES = ['Hardhat','Mask','NO-Hardhat','NO-Mask','NO-Safety Vest','Person','Safety Cone','Safety Vest','machinery','vehicle']

def merge_ppe_vincent():
    src_img = BASE / 'data' / 'material_library' / 'hf_datasets' / 'ppe_vincent' / 'train' / 'images'
    src_lbl = BASE / 'data' / 'material_library' / 'hf_datasets' / 'ppe_vincent' / 'train' / 'labels'
    if not src_img.exists() or not src_lbl.exists():
        print('[ppe_vincent] Source not found, skipping.')
        return 0, 0
    remap = {0: 0, 1: 2, 2: 4, 3: 5, 4: 7}
    count_img = 0; count_lbl = 0
    for lbl_file in src_lbl.glob('*.txt'):
        stem = lbl_file.stem
        img_file = None
        for ext in ('.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'):
            candidate = src_img / f'{stem}{ext}'
            if candidate.exists():
                img_file = candidate; break
        if img_file is None: continue
        new_lines = []
        with open(lbl_file) as f:
            for line in f:
                parts = line.strip().split()
                if not parts: continue
                src_cls = int(parts[0])
                if src_cls in remap:
                    parts[0] = str(remap[src_cls])
                    new_lines.append(' '.join(parts))
                    count_lbl += 1
        if not new_lines: continue
        h = hashlib.md5(stem.encode()).hexdigest()[:12]
        new_stem = f'ppe_v_{h}'
        ext = img_file.suffix
        shutil.copy2(img_file, TRAIN_IMG / f'{new_stem}{ext}')
        with open(TRAIN_LBL / f'{new_stem}.txt', 'w') as f:
            f.write('\n'.join(new_lines) + '\n')
        count_img += 1
    print(f'[ppe_vincent] Merged {count_img} images, {count_lbl} labels')
    return count_img, count_lbl

print('merge_new_materials.py part 1 OK')
