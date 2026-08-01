import shutil
from pathlib import Path

SELECTED = [
    "93806ed5d3e071e3", "8322601df02c6b1e", "88747752a59a34a5", "b02223c2b8343a9b",
    "b5e38267f178f1a5", "0c58787c326d5ee0", "e4a2ca493a73b6a1", "b7c78ba168afec3e",
    "c2742fb9e9cdec36", "dae86d45c77e2f8d", "0051a45c58b6ea7a", "3bcc1270bc5e2d43",
    "be55327e4413d837", "0daf314f1b19d010",
    "33cde781f611e857", "23480f913f856917", "142a556efbe37943", "8cb9a749333a0230",
    "46bc66e04a4a8138", "56f844820dbd990a", "bb502e24c4dbe505", "7b952c3d1506c847",
    "9765f39ded35ef24", "29c720963c34e6ec", "884a53f8b76cdcd2", "2e10d9876739e5f9",
    "d7a6c043634af2e1", "32767c93fc4789a5", "20a90929c6e1415b", "c56de327693808d8",
    "901c523bf02204c6",
    "10b5ab5f4ac17dda", "ab8392e1aa211868", "8b4fb8f3820fcc6a", "1b567499cd86d35a",
    "7d1be7a07c5f7cc1", "026767e4cf4f3abd", "c2d5644fdddaccfd", "96405d739c73e716",
    "7fee07d795fec02d",
]

ROOT = Path(__file__).resolve().parents[1]
SRC_RAW = ROOT / "data" / "material_library" / "new_candidates" / "raw"
DST_IMG = ROOT / "evaluation" / "datasets" / "ppe" / "images" / "val"
DST_LBL = ROOT / "evaluation" / "datasets" / "ppe" / "labels" / "val"

DST_IMG.mkdir(parents=True, exist_ok=True)
DST_LBL.mkdir(parents=True, exist_ok=True)

copied = 0
missing = []
for stem in SELECTED:
    src = SRC_RAW / f"{stem}.jpg"
    if not src.is_file():
        missing.append(stem)
        continue
    shutil.copy2(src, DST_IMG / f"{stem}.jpg")
    (DST_LBL / f"{stem}.txt").write_text("", encoding="utf-8")
    copied += 1

# Clean stale files
for old in list(DST_IMG.glob("*.jpg")):
    if old.stem not in SELECTED:
        old.unlink()
for old in list(DST_LBL.glob("*.txt")):
    if old.stem not in SELECTED:
        old.unlink()

img_count = len(list(DST_IMG.glob("*.jpg")))
lbl_count = len(list(DST_LBL.glob("*.txt")))
print(f"Copied {copied}/{len(SELECTED)} images.")
if missing:
    print(f"Missing: {missing}")
print(f"Validation images: {img_count}")
print(f"Label placeholders: {lbl_count}")
print("Done.")
