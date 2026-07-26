# -*- coding: utf-8 -*-
"""YOLO annotation tool using native HTML5 Canvas."""
from __future__ import annotations

import base64, io, json, logging, sys, traceback, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG_FILE = ROOT / "tools" / "annotate.log"
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stderr)])
logger = logging.getLogger("annotate")

import streamlit as st
from PIL import Image

IMG_DIR = ROOT / "evaluation" / "datasets" / "ppe" / "images" / "val"
LBL_DIR = ROOT / "evaluation" / "datasets" / "ppe" / "labels" / "val"
PROGRESS_FILE = LBL_DIR / ".annotate_progress.json"

CLASSES = ["Hardhat","Mask","NO-Hardhat","NO-Mask","NO-Safety Vest",
           "Person","Safety Cone","Safety Vest","machinery","vehicle"]
COLORS = ["#FF0000","#00FF00","#FFA500","#FF69B4","#800080",
          "#0000FF","#FFFF00","#00FFFF","#808080","#8B4513"]

st.set_page_config(page_title="PPE Annotator", layout="wide")

def load_labels(stem):
    f = LBL_DIR / f"{stem}.txt"
    if not f.exists(): return []
    objs = []
    for l in f.read_text(encoding="utf-8-sig").splitlines():
        p = l.strip().split()
        if len(p) == 5: objs.append({"class": int(float(p[0])), "coords": [float(x) for x in p[1:]]})
    return objs

def save_labels(stem, objs):
    lines = [f"{o['class']} {o['coords'][0]:.6f} {o['coords'][1]:.6f} {o['coords'][2]:.6f} {o['coords'][3]:.6f}" for o in objs]
    (LBL_DIR / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")

# ---- Read saved data from query params (set by JS after SAVE click) ----
params = st.query_params
saved_data = params.get("data", None)
restore_idx = params.get("idx", None)

# ---- Handle requests from component iframe (save/skip with _from_component flag) ----
_from_component = params.get("_from_component", None)
if _from_component:
    if saved_data:
        try:
            decoded = urllib.parse.unquote(saved_data)
            boxes = json.loads(decoded)
            target_stem = params.get("stem", "")
            new_objs = [{"class": int(b[0]), "coords": [float(b[1]), float(b[2]), float(b[3]), float(b[4])]} for b in boxes]
            save_labels(target_stem, new_objs)
            progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
            progress[target_stem] = {"done": True, "count": len(new_objs)}
            PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Saved %d boxes for %s via component", len(new_objs), target_stem)
            if restore_idx:
                try: st.session_state.idx = int(restore_idx)
                except: pass
        except Exception as e:
            logger.error("Component save failed: %s", traceback.format_exc())
    elif params.get("clear", None):
        clear_stem = params.get("clear", "")
        save_labels(clear_stem, [])
        progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
        progress[clear_stem] = {"done": True, "count": 0}
        PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Cleared %s via component", clear_stem)
    elif params.get("skip", None):
        skip_stem = params.get("skip", "")
        progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
        existing = load_labels(skip_stem)
        progress[skip_stem] = {"done": True, "count": len(existing)}
        PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Skipped %s via component", skip_stem)
    st.query_params.clear()
    st.markdown("""<!DOCTYPE html><html><body style="background:#1e1e1e;color:#e0e0e0;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><p style="font-size:18px;margin:0 0 16px">Saved</p><a href="/" target="_parent" style="color:#4caf50;font-size:14px;text-decoration:none;border:1px solid #4caf50;padding:8px 20px;border-radius:4px">Continue</a></div><script>try{window.top.location.href=window.top.location.origin+window.top.location.pathname;}catch(e){}</script></body></html>""", unsafe_allow_html=True)
    st.stop()
if saved_data:
    try:
        decoded = urllib.parse.unquote(saved_data)
        boxes = json.loads(decoded)
        target_stem = params.get("stem", "")
        new_objs = [{"class": int(b[0]), "coords": [float(b[1]), float(b[2]), float(b[3]), float(b[4])]} for b in boxes]
        save_labels(target_stem, new_objs)
        progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
        progress[target_stem] = {"done": True, "count": len(new_objs)}
        PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved %d boxes for %s via query param", len(new_objs), target_stem)
        # Clear params and reload
        st.query_params.clear()
        if restore_idx:
            try: st.session_state.idx = int(restore_idx)
            except: pass
        st.rerun()
    except Exception as e:
        logger.error("Parse query data failed: %s", traceback.format_exc())
        st.error(f"Parse error: {e}")
        st.query_params.clear()

# Handle clear request
clear_stem = params.get("clear", None)
if clear_stem:
    save_labels(clear_stem, [])
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
    progress[clear_stem] = {"done": True, "count": 0}
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    st.query_params.clear()
    st.rerun()

# Handle skip request
skip_stem = params.get("skip", None)
if skip_stem:
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
    existing = load_labels(skip_stem)
    progress[skip_stem] = {"done": True, "count": len(existing)}
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    st.query_params.clear()
    st.session_state.idx = st.session_state.get("idx", 0) + 1
    st.rerun()

# ---- Images ----
images = sorted(list(IMG_DIR.glob("*.jpg")))
if not images: st.error("No images"); st.stop()

progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
done_set = {k for k,v in progress.items() if v.get("done")}

if "idx" not in st.session_state: st.session_state.idx = 0
idx = st.session_state.idx
if idx >= len(images): idx = 0; st.session_state.idx = 0
img_path = images[idx]
stem = img_path.stem
img = Image.open(img_path).convert("RGB")
iw, ih = img.size

# ---- Sidebar ----
st.sidebar.header(f"Progress: {len(done_set)}/{len(images)}")
st.sidebar.progress(len(done_set)/len(images))
st.sidebar.subheader(stem)
nc = st.sidebar.columns([1,2,1])
if nc[0].button("\u25c0"): st.session_state.idx = max(0, idx-1); st.rerun()
nc[1].markdown(f"**{idx+1}/{len(images)}**")
if nc[2].button("\u25b6"): st.session_state.idx = min(len(images)-1, idx+1); st.rerun()
st.sidebar.markdown("---")
cls_idx = st.sidebar.radio("Active Class", list(range(10)), format_func=lambda i: f"{i} {CLASSES[i]}", key="cls_sel")

existing = load_labels(stem)

# Encode image
buf = io.BytesIO()
img.save(buf, format="JPEG", quality=85)
img_b64 = base64.b64encode(buf.getvalue()).decode()

existing_json = json.dumps([{
    "class": o["class"], "x": o["coords"][0], "y": o["coords"][1],
    "w": o["coords"][2], "h": o["coords"][3]
} for o in existing])

display_w = 960
display_h = int(display_w * ih / iw)

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{{margin:0;padding:0;background:#222;font-family:monospace;color:#ccc}}
#wrap{{position:relative;display:inline-block}}
#img{{display:block;max-width:{display_w}px}}
canvas{{position:absolute;top:0;left:0;cursor:crosshair}}
#bar{{padding:6px 8px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
button{{padding:5px 14px;font-size:13px;cursor:pointer;border:1px solid #555;background:#444;color:#fff;border-radius:3px}}
button:hover{{background:#666}}
.btn-save{{background:#2e7d32;font-weight:bold}}
.btn-clear{{background:#c62828}}
.btn-skip{{background:#555}}
#status{{color:#4caf50;font-weight:bold}}
</style></head><body>
<div id="bar">
  <span>Class: <b>{CLASSES[cls_idx]}</b> ({cls_idx}) | Shift=square</span>
  <button onclick="undo()">Undo</button>
  <button class="btn-clear" onclick="clearAll()">Clear</button>
  <button class="btn-save" onclick="doSave()">SAVE</button>
  <button class="btn-skip" onclick="doSkip()">Skip</button>
  <span id="status"></span>
</div>
<div id="wrap">
  <img id="img" src="data:image/jpeg;base64,{img_b64}" draggable="false">
  <canvas id="cv"></canvas>
</div>
<script>
const CLASSES={json.dumps(CLASSES)};
const COLORS={json.dumps(COLORS)};
const IW={iw},IH={ih};
const STEM="{stem}";
const BASE=window.location.origin+window.location.pathname;
let clsId={cls_idx};window._CURRENT_IDX={idx};
let boxes=[];
let drawing=null;

// Init from existing
{existing_json}.forEach(o=>{{
    let l=(o.x-o.w/2)*IW,t=(o.y-o.h/2)*IH,w=o.w*IW,h=o.h*IH;
    boxes.push({{x:l,y:t,w,h,cls:o.class}});
}});

const img=document.getElementById("img"),cv=document.getElementById("cv");
const ctx=cv.getContext("2d"),st=document.getElementById("status");

function init(){{cv.width=img.clientWidth;cv.height=img.clientHeight;draw()}}
img.onload=init;if(img.complete)init();

function draw(){{
    ctx.clearRect(0,0,cv.width,cv.height);
    boxes.forEach(b=>{{
        ctx.strokeStyle=COLORS[b.cls];ctx.lineWidth=2;
        ctx.strokeRect(b.x,b.y,b.w,b.h);
        ctx.fillStyle=COLORS[b.cls];ctx.font="12px monospace";
        ctx.fillText(CLASSES[b.cls],b.x+2,b.y-4);
    }});
    if(drawing){{
        ctx.strokeStyle="rgba(255,255,255,0.7)";ctx.lineWidth=2;
        ctx.setLineDash([4,4]);ctx.strokeRect(drawing.x,drawing.y,drawing.w,drawing.h);ctx.setLineDash([]);
    }}
    st.textContent=boxes.length+" boxes";
}}

cv.onmousedown=e=>{{
    let r=cv.getBoundingClientRect(),sx=cv.width/r.width,sy=cv.height/r.height;
    drawing={{x:(e.clientX-r.left)*sx,y:(e.clientY-r.top)*sy,w:0,h:0}};
}};
cv.onmousemove=e=>{{
    if(!drawing)return;
    let r=cv.getBoundingClientRect(),sx=cv.width/r.width,sy=cv.height/r.height;
    let mx=(e.clientX-r.left)*sx,my=(e.clientY-r.top)*sy;
    if(e.shiftKey){{let s=Math.max(Math.abs(mx-drawing.x),Math.abs(my-drawing.y));drawing.w=mx>=drawing.x?s:-s;drawing.h=my>=drawing.y?s:-s}}
    else{{drawing.w=mx-drawing.x;drawing.h=my-drawing.y}}
    draw();
}};
cv.onmouseup=e=>{{
    if(!drawing)return;
    if(Math.abs(drawing.w)>3&&Math.abs(drawing.h)>3){{
        let x=drawing.w>=0?drawing.x:drawing.x+drawing.w,y=drawing.h>=0?drawing.y:drawing.y+drawing.h;
        boxes.push({{x,y,w:Math.abs(drawing.w),h:Math.abs(drawing.h),cls:clsId}});
    }}
    drawing=null;draw();
}};

function undo(){{boxes.pop();draw()}}
function clearAll(){{if(confirm("Clear all boxes?"))boxes=[];draw()}}

function boxesToYOLO(){{
    return boxes.map(b=>[b.cls,(b.x+b.w/2)/IW,(b.y+b.h/2)/IH,b.w/IW,b.h/IH]);
}}

function doSave(){{let idx=window._CURRENT_IDX||0;
    let data=encodeURIComponent(JSON.stringify(boxesToYOLO()));
    window.location.replace(BASE+"?data="+data+"&stem="+STEM+"&idx="+idx+"&_from_component=1");
}}

function doSkip(){{
    window.location.replace(BASE+"?skip="+STEM+"&_from_component=1");
}}
</script></body></html>"""

st.components.v1.html(html, height=display_h + 40, scrolling=False)

# ---- Legend ----
st.markdown("### Current Labels")
cols = st.columns(4)
class_counts = {}
for o in existing: class_counts[o["class"]] = class_counts.get(o["class"], 0) + 1
for cid, cnt in sorted(class_counts.items()):
    cols[cid % 4].markdown(f'<span style="color:{COLORS[cid]}">\u25a0</span> {CLASSES[cid]}: {cnt}', unsafe_allow_html=True)

ca, cb = st.columns(2)
if ca.button("\U0001f5d1 Clear & Save Empty", use_container_width=True):
    save_labels(stem, [])
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
    progress[stem] = {"done": True, "count": 0}
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    st.rerun()
if cb.button("\u23ed Skip (no changes)", use_container_width=True):
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
    progress[stem] = {"done": True, "count": len(existing)}
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    st.session_state.idx = min(len(images)-1, idx+1)
    st.rerun()
