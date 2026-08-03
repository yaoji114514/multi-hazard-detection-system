# -*- coding: utf-8 -*-
"""
快速复核工具 - 无需画框，只需点击确认口罩状态
显示自动标注结果，对每个工人点击"有口罩"/"无口罩"
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import streamlit as st
from PIL import Image, ImageDraw
import json

st.set_page_config(page_title="PPE标注复核 - 口罩专项", layout="wide")

RAW_DIR = ROOT / "data" / "material_library" / "new_candidates" / "raw"
LABEL_DIR = ROOT / "data" / "material_library" / "new_candidates" / "annotated" / "labels"
IMG_DIR = ROOT / "data" / "material_library" / "new_candidates" / "annotated" / "images"
REVIEW_LOG = LABEL_DIR.parent / "review_progress.json"

CLASS_NAMES = {0: "Hardhat", 1: "Mask", 2: "NO-Hardhat", 3: "NO-Mask",
               4: "NO-Safety Vest", 5: "Person", 6: "Safety Cone",
               7: "Safety Vest", 8: "machinery", 9: "vehicle"}
COLORS = {0: "#FF0000", 1: "#00CC00", 2: "#FFA500", 3: "#FF69B4",
          4: "#800080", 5: "#0000FF", 6: "#FFFF00", 7: "#00FFFF",
          8: "#808080", 9: "#8B4513"}

# 加载进度
if REVIEW_LOG.exists():
    progress = json.load(open(REVIEW_LOG, "r"))
else:
    progress = {}

images = sorted(RAW_DIR.glob("*.jpg"))
remaining = [f for f in images if str(f.stem) not in progress.get("reviewed", [])]

st.title("PPE标注复核 - 口罩专项")
st.markdown("只需确认每个工人是否戴口罩，无需画框")

col1, col2 = st.columns([3, 1])
with col2:
    st.metric("已复核", f"{len(progress.get('reviewed', []))}/{len(images)}")
    st.metric("待复核", f"{len(remaining)}")

if not remaining:
    st.success("全部复核完成！")
    # 汇总统计
    st.subheader("复核汇总")
    reviewed = progress.get("reviewed", [])
    with_mask = progress.get("with_mask", [])
    without_mask = progress.get("without_mask", [])
    st.write(f"- 有口罩: {len(with_mask)} 个工人")
    st.write(f"- 无口罩: {len(without_mask)} 个工人")
    st.write(f"- 已复核图片: {len(reviewed)} 张")
    st.stop()

current = remaining[0]
with col1:
    st.subheader(f"第 {len(progress.get('reviewed',[]))+1}/{len(images)} 张: {current.name}")
    img = Image.open(current).convert("RGB")
    w, h = img.size
    
    # 读取自动标注
    label_file = LABEL_DIR / f"{current.stem}.txt"
    detections = []
    if label_file.exists():
        for line in label_file.read_text().strip().splitlines():
            if not line.strip():
                continue
            parts = line.strip().split()
            cls_id = int(parts[0])
            x_c, y_c, bw, bh = map(float, parts[1:5])
            x1 = int((x_c - bw/2) * w)
            y1 = int((y_c - bh/2) * h)
            x2 = int((x_c + bw/2) * w)
            y2 = int((y_c + bh/2) * h)
            detections.append({
                "cls": cls_id,
                "name": CLASS_NAMES.get(cls_id, f"class_{cls_id}"),
                "bbox": (x1, y1, x2, y2),
                "raw": line.strip()
            })
    
    # 画框
    draw = ImageDraw.Draw(img)
    for d in detections:
        color = COLORS.get(d["cls"], "#FFFFFF")
        draw.rectangle(d["bbox"], outline=color, width=3)
        draw.text((d["bbox"][0], d["bbox"][1]-15), d["name"], fill=color)
    
    st.image(img, caption=f"自动标注结果 ({w}x{h})", use_container_width=True)
    
    # 检测结果表格
    st.subheader("自动检测结果")
    for d in detections:
        st.markdown(f"- **{d['name']}**  @ ({d['bbox'][0]},{d['bbox'][1]})")

with col2:
    st.markdown("### 口罩确认")
    persons = [d for d in detections if d["cls"] == 5 or d["cls"] == 1 or d["cls"] == 3]
    has_mask = st.checkbox("此图中工人**有佩戴口罩**", value=False)
    notes = st.text_input("备注（可选）", "")
    
    if st.button("✅ 提交复核", type="primary", use_container_width=True):
        if "reviewed" not in progress:
            progress["reviewed"] = []
        progress["reviewed"].append(str(current.stem))
        progress[str(current.stem)] = {"has_mask": has_mask, "notes": notes}
        json.dump(progress, open(REVIEW_LOG, "w"), ensure_ascii=False, indent=2)
        
        # 如果工人有口罩，更新标注文件
        if has_mask and persons:
            # 为每个Person添加Mask标注 (粗略: 在头部区域添加口罩框)
            existing = label_file.read_text().strip().splitlines() if label_file.exists() else []
            for p in persons:
                x1, y1, x2, y2 = p["bbox"]
                # Mask大致在Person框的上1/3区域
                mx1, my1, mx2, my2 = x1, y1, x2, y1 + (y2-y1)//3
                # 转YOLO格式
                img_w, img_h = img.size
                x_c = ((mx1 + mx2) / 2) / img_w
                y_c = ((my1 + my2) / 2) / img_h
                bw = (mx2 - mx1) / img_w
                bh = (my2 - my1) / img_h
                existing.append(f"1 {x_c:.6f} {y_c:.6f} {bw:.6f} {bh:.6f}")
            label_file.write_text("\n".join(existing))
            st.success(f"已添加Mask标注到 {current.name}")
        elif not has_mask and persons:
            # 添加NO-Mask标注
            existing = label_file.read_text().strip().splitlines() if label_file.exists() else []
            for p in persons:
                x1, y1, x2, y2 = p["bbox"]
                mx1, my1, mx2, my2 = x1, y1, x2, y1 + (y2-y1)//3
                img_w, img_h = img.size
                x_c = ((mx1 + mx2) / 2) / img_w
                y_c = ((my1 + my2) / 2) / img_h
                bw = (mx2 - mx1) / img_w
                bh = (my2 - my1) / img_h
                existing.append(f"3 {x_c:.6f} {y_c:.6f} {bw:.6f} {bh:.6f}")
            label_file.write_text("\n".join(existing))
            st.info(f"已添加NO-Mask标注到 {current.name}")
        
        st.rerun()
    
    if st.button("⏭️ 跳过", use_container_width=True):
        if "skipped" not in progress:
            progress["skipped"] = []
        progress["skipped"].append(str(current.stem))
        json.dump(progress, open(REVIEW_LOG, "w"), ensure_ascii=False, indent=2)
        st.rerun()
