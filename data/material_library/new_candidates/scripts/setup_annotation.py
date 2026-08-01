# -*- coding: utf-8 -*-
"""Set up annotation directory structure"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ANNO_DIR = ROOT / 'data' / 'material_library' / 'new_candidates' / 'annotated'
ANNO_DIR.mkdir(parents=True, exist_ok=True)
(ANNO_DIR / 'images').mkdir(exist_ok=True)
(ANNO_DIR / 'labels').mkdir(exist_ok=True)

yaml_content = """train: images
val: images

names:
  0: Hardhat
  1: Mask
  2: NO-Hardhat
  3: NO-Mask
  4: NO-Safety Vest
  5: Person
  6: Safety Cone
  7: Safety Vest
  8: machinery
  9: vehicle
"""
yml_path = ANNO_DIR / 'data.yaml'
yml_path.write_text(yaml_content, encoding='utf-8')

# Count classes
n = sum(1 for l in yaml_content.splitlines() if l.strip().startswith(('0:', '1:', '2:', '3:', '4:', '5:', '6:', '7:', '8:', '9:')))
print(f"Created: {yml_path}")
print(f"Classes: {n}")
print(f"Directory: {ANNO_DIR}")
