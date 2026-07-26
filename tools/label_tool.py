# -*- coding: utf-8 -*-
"""
Streamlit-based 图片标注工具
用于手动标注新下载的工地工人PPE图片
标签格式: YOLO (class x_center y_center width height)
"""
import sys
from pathlib import Path

# 将项目根目录加入路径以便复用现有配置
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import streamlit as st
from PIL import Image, ImageDraw
import json

st.set_page_config(page_title="PPE图片标注工具", layout="wide")

RAW_DIR = Path(__file__).resolve().parents[2] / "raw"
ANNO_DIR = Path(__file__).resolve().parents[2] / "annotated"
INVENTORY = RAW_DIR.parent / "inventory.json"

# 类别配置（与模型一致）
CLASSES = ["Hardhat", "Mask", "NO-Hardhat", "NO-Mask", "NO-Safety Vest",
           "Person", "Safety Cone", "Safety Vest", "machinery", "vehicle"]
COLORS = ["#FF0000", "#00FF00", "#FFA500", "#FF69B4", "#800080",
          "#0000FF", "#FFFF00", "#00FFFF", "#808080", "#8B4513"]

st.title("🧰 工地工人PPE图片标注工具")
st.markdown("---")

# 加载图片列表
inventory = json.load(open(INVENTORY, "r", encoding="utf-8")) if INVENTORY.exists() else {"images": []}
all_images = sorted(RAW_DIR.glob("*.jpg"))

if not all_images:
    st.error("没有找到待标注的图片，请先运行下载脚本。")
    st.stop()

# 已标注索引
annotated_ids = [p.stem for p in ANNO_DIR.glob("labels/*.txt")]
remaining = [f for f in all_images if f.stem not in annotated_ids]

st.sidebar.header(f"进度: {len(annotated_ids)}/{len(all_images)} 已标注")
st.sidebar.progress(len(annotated_ids) / len(all_images) if all_images else 0)

if not remaining:
    st.success("🎉 所有图片已标注完成！可以开始训练了。")
    st.stop()

# 显示当前图片
current = remaining[0]
st.sidebar.subheader("当前图片")
st.sidebar.image(str(current), use_container_width=True)
st.sidebar.text(f"{current.stem[:20]}...")
st.sidebar.text(f"剩余: {len(remaining)} 张")

st.subheader(f"标注第 {len(annotated_ids)+1}/{len(all_images)} 张: {current.name}")

img = Image.open(current).convert("RGB")
w, h = img.size
st.image(img, caption=f"原始图片 ({w}x{h})", use_container_width=True)

st.markdown("### 标注说明")
st.markdown("""
1. 仔细观察图片中的工人和PPE装备
2. 在下方选择类别，输入边界框坐标
3. 格式: `class x_center y_center width height` (归一化到0-1)
4. 每行一个目标，多行可同时提交
""")

col1, col2 = st.columns([1, 2])
with col1:
    cls_name = st.selectbox("选择类别", CLASSES, index=0)
    st.markdown(f"**类别索引**: {CLASSES.index(cls_name)}")
    st.markdown(f"**颜色**: <span style='color:{COLORS[CLASSES.index(cls_name)]}'>■</span>", unsafe_allow_html=True)

with col2:
    bbox_input = st.text_area(
        "边界框数据 (YOLO格式, 每行一个)",
        placeholder="例: 0 0.5 0.5 0.2 0.3",
        height=100
    )
    st.markdown("格式: `class_id center_x center_y width height` (数值在0-1之间)")

if st.button("✅ 保存标注", type="primary", use_container_width=True):
    labels = []
    errors = []
    for line in bbox_input.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            errors.append(f"格式错误(需要5个值): {line}")
            continue
        try:
            vals = [float(x) for x in parts]
            if not (0 <= vals[0] <= 9):
                errors.append(f"类别ID超出范围: {vals[0]}")
                continue
            for j in range(1, 5):
                if not (0 <= vals[j] <= 1):
                    errors.append(f"坐标超出[0,1]: {line}")
                    break
            else:
                labels.append(vals)
        except ValueError:
            errors.append(f"数值解析错误: {line}")

    if errors:
        for e in errors:
            st.error(e)
    elif labels:
        # 保存标签
        label_path = ANNO_DIR / "labels" / f"{current.stem}.txt"
        with open(label_path, "w") as f:
            for label in labels:
                f.write(f"{int(label[0])} {label[1]:.6f} {label[2]:.6f} {label[3]:.6f} {label[4]:.6f}\n")
        # 复制图片
        img.save(ANNO_DIR / "images" / f"{current.stem}.jpg", "JPEG", quality=92)
        # 更新库存
        inv = json.load(open(INVENTORY, "r", encoding="utf-8"))
        for item in inv["images"]:
            if item["filename"] == current.name:
                item["annotated"] = True
                item["objects"] = len(labels)
                break
        json.dump(inv, open(INVENTORY, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        st.success(f"保存成功! {len(labels)} 个目标")
        st.balloons()
        st.rerun()
    else:
        st.info("未输入标注数据 - 跳过此图片")

if st.button("⏭️ 跳过此图片", use_container_width=True):
    st.rerun()

st.markdown("---")
st.markdown("**快捷键**: Tab切换类别 | Enter确认 | Esc跳过")
