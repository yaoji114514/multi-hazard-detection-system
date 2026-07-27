# -*- coding: utf-8 -*-
"""PPE annotation server - no iframes, no sandbox, just works."""
from __future__ import annotations

import json, base64, io, sys, logging, traceback
from pathlib import Path
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import zipfile, io as zipio, shutil

ROOT = Path(__file__).resolve().parents[1]
if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).parent
sys.path.insert(0, str(ROOT))

DEFAULT_IMG_DIR = ROOT / "evaluation" / "datasets" / "ppe" / "images" / "val"

parser = argparse.ArgumentParser(description="YOLO annotation server - point at any image directory, labels auto-resolved")
parser.add_argument("img_dir", nargs="?", type=Path, default=DEFAULT_IMG_DIR,
                    help="Image directory. Labels resolved to ../labels/<same-name>/ or ./labels/. Default: evaluation/datasets/ppe/images/val")
parser.add_argument("--port", type=int, default=8504, help="Server port")
args = parser.parse_args()

IMG_DIR = args.img_dir.resolve()

# Auto-resolve label directory: look for parallel labels/ structure
# If IMG_DIR is .../images/val -> look for .../labels/val
# If IMG_DIR is .../images/review -> look for .../labels/review
# If IMG_DIR is .../review -> look for .../review/labels or parallel labels/
LBL_DIR = IMG_DIR / "labels"

# Try parallel labels/ with same relative path from a common parent
parts = IMG_DIR.parts
if "images" in parts:
    idx = parts.index("images")
    # Reconstruct: .../labels/<rest>
    lbl_candidate = Path(*parts[:idx]) / "labels" / Path(*parts[idx+1:])
    if lbl_candidate.exists() or not LBL_DIR.exists():
        LBL_DIR = lbl_candidate

if not IMG_DIR.exists() or not list(IMG_DIR.glob("*.jpg")):
    print(f"ERROR: No .jpg images found in {IMG_DIR}")
    sys.exit(1)

LBL_DIR.mkdir(parents=True, exist_ok=True)
PROGRESS_FILE = LBL_DIR / ".annotate_progress.json"

CLASSES = ["Hardhat","Mask","NO-Hardhat","NO-Mask","NO-Safety Vest",
           "Person","Safety Cone","Safety Vest","machinery","vehicle"]
COLORS = ["#FF0000","#00FF00","#FFA500","#FF69B4","#800080",
          "#0000FF","#FFFF00","#00FFFF","#808080","#8B4513"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stderr)])
logger = logging.getLogger("annotate_server")


def load_labels(stem):
    f = LBL_DIR / f"{stem}.txt"
    if not f.exists(): return []
    objs = []
    for line in f.read_text(encoding="utf-8-sig").splitlines():
        p = line.strip().split()
        if len(p) == 5:
            objs.append({"class": int(float(p[0])), "coords": [float(x) for x in p[1:]]})
    return objs

def save_labels(stem, objs):
    lines = [f"{o['class']} {o['coords'][0]:.6f} {o['coords'][1]:.6f} {o['coords'][2]:.6f} {o['coords'][3]:.6f}" for o in objs]
    (LBL_DIR / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.info(fmt % args)

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_image(self, stem):
        img_path = IMG_DIR / f"{stem}.jpg"
        if not img_path.exists():
            self.send_error(404)
            return
        data = img_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", len(data))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path.rstrip("/")

        if path == "/" or path == "":
            self._serve_page()
        elif path.startswith("/api/image/"):
            self._send_image(path.split("/")[-1])
        elif path == "/api/images":
            self._list_images()
        elif path == "/api/export":
            self._export_dataset()
        elif path.startswith("/api/labels/"):
            stem = path.split("/")[-1]
            self._send_json(load_labels(stem))
        elif path == "/api/progress":
            progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
            self._send_json(progress)
        else:
            self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path)
        path = p.path.rstrip("/")

        if path == "/api/save":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            stem = body.get("stem", "")
            boxes = body.get("boxes", [])

            objs = [{"class": int(b[0]), "coords": [float(b[1]), float(b[2]), float(b[3]), float(b[4])]} for b in boxes]
            save_labels(stem, objs)

            progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
            progress[stem] = {"done": True, "count": len(objs)}
            PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Saved %d boxes for %s", len(objs), stem)
            self._send_json({"ok": True, "count": len(objs)})
        elif path == "/api/skip":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            stem = body.get("stem", "")
            progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
            existing = load_labels(stem)
            progress[stem] = {"done": True, "count": len(existing)}
            PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Skipped %s", stem)
            self._send_json({"ok": True})
        else:
            self.send_error(404)

    def _list_images(self):
        images = sorted(IMG_DIR.glob("*.jpg"))
        progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
        result = []
        for img in images:
            p = progress.get(img.stem, {})
            result.append({"stem": img.stem, "done": p.get("done", False), "count": p.get("count", 0)})
        self._send_json(result)

    def _export_dataset(self):
        images = sorted(IMG_DIR.glob("*.jpg"))
        buf = zipio.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for img in images:
                zf.write(img, f"images/{img.name}")
                lbl = LBL_DIR / f"{img.stem}.txt"
                if lbl.exists():
                    zf.write(lbl, f"labels/{lbl.name}")
            # Include progress
            if PROGRESS_FILE.exists():
                zf.write(PROGRESS_FILE, ".annotate_progress.json")
        data = buf.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", "attachment; filename=ppe_annotated.zip")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _serve_page(self):
        images = sorted(IMG_DIR.glob("*.jpg"))
        progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
        stems = [img.stem for img in images]
        done = {s for s in stems if progress.get(s, {}).get("done")}
        html = PAGE_HTML.replace("__STEMS__", json.dumps(stems))
        html = html.replace("__DONE__", json.dumps(list(done)))
        html = html.replace("__CLASSES__", json.dumps(CLASSES))
        html = html.replace("__COLORS__", json.dumps(COLORS))
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

PAGE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PPE Annotator</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a1a;color:#e0e0e0;font-family:system-ui,sans-serif;display:flex;flex-direction:column;height:100vh;overflow:hidden}
#topbar{display:flex;align-items:center;gap:10px;padding:8px 12px;background:#252525;flex-shrink:0;flex-wrap:wrap;min-height:44px}
#topbar select,#topbar button{padding:6px 12px;font-size:13px;border-radius:4px;border:1px solid #555;background:#3a3a3a;color:#fff;cursor:pointer}
#topbar button:hover{background:#555}
#topbar select{min-width:140px}
.btn-del{background:#444}.btn-del.active{background:#c62828;font-weight:bold}
.btn-save{background:#2e7d32;font-weight:bold}
.btn-clear{background:#b71c1c}
.btn-nav{min-width:36px;font-size:16px}
#info{font-size:13px;color:#aaa;margin-left:auto}
#canvasWrap{flex:1;display:flex;align-items:center;justify-content:center;position:relative;overflow:auto;background:#111}
canvas{cursor:crosshair}
#progress{display:flex;align-items:center;gap:6px;padding:6px 12px;background:#252525;flex-shrink:0;font-size:12px;color:#aaa}
#progress .bar{flex:1;height:6px;background:#333;border-radius:3px;overflow:hidden}
#progress .bar div{height:100%;background:#4caf50;transition:width .2s}
</style></head>
<body>
<div id="topbar">
  <select id="clsSel"></select>
  <button id="delBtn" class="btn-del" title="Toggle delete mode">Edit</button>
  <button onclick="undo()" title="Undo last box">Undo</button>
  <button class="btn-clear" onclick="clearAll()">Clear</button>
  <button onclick="resetZoom()" title="Reset zoom (0)">1:1</button>
  <button class="btn-save" onclick="doSave()">SAVE</button>
  <button id="exportBtn" onclick="doExport()" style="display:none;background:#1565c0;font-weight:bold" title="Download annotated dataset as ZIP">Export</button>
  <button onclick="doSkip()">Skip</button>
  <span id="info"></span>
</div>
<div id="canvasWrap"><canvas id="cv"></canvas></div>
<div id="progress">
  <span id="progText"></span>
  <div class="bar"><div id="progBar"></div></div>
</div>
<script>
const STEMS=__STEMS__, DONE=new Set(__DONE__);
const CLASSES=__CLASSES__, COLORS=__COLORS__;
let curIdx=0, boxes=[], drawing=null, deleteMode=false;
let scale=1, panX=0, panY=0, panning=false, panStart=null;
let img=null, iw=0, ih=0;

// Init class selector
const clsSel=document.getElementById('clsSel');
CLASSES.forEach((c,i)=>clsSel.add(new Option(i+' '+c,i)));
clsSel.value='5'; // default Person

const cv=document.getElementById('cv'), ctx=cv.getContext('2d');
const info=document.getElementById('info');
const progText=document.getElementById('progText'), progBar=document.getElementById('progBar');

function updateProgress(){
  let d=0; STEMS.forEach(s=>{if(DONE.has(s))d++});
  progText.textContent=d+'/'+STEMS.length+' done';
  progBar.style.width=(d/STEMS.length*100)+'%';
  let btn=document.getElementById('exportBtn');
  if(d===STEMS.length){btn.style.display=''; progBar.style.background='#1565c0'}
  else{btn.style.display='none'}
}

async function loadImage(stem){
  boxes=[];drawing=null;
  img=new Image();
  img.onload=()=>{
    iw=img.naturalWidth; ih=img.naturalHeight;
    cv.width=iw; cv.height=ih;
    let maxW=window.innerWidth-20, maxH=window.innerHeight-120;
    scale=Math.min(maxW/iw, maxH/ih, 1);
    panX=0; panY=0;
    cv.style.width=(iw*scale)+'px'; cv.style.height=(ih*scale)+'px';
    loadLabels(stem).then(draw);
  };
  img.src='/api/image/'+stem;
  info.textContent=stem;
}

async function loadLabels(stem){
  try{
    let resp=await fetch('/api/labels/'+stem);
    let objs=await resp.json();
    boxes=objs.map(o=>{
      let l=(o.coords[0]-o.coords[2]/2)*iw, t=(o.coords[1]-o.coords[3]/2)*ih;
      let w=o.coords[2]*iw, h=o.coords[3]*ih;
      return {x:l,y:t,w,h,cls:o.class};
    });
  }catch(e){boxes=[];}
}

function draw(){
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.save();
  ctx.translate(panX,panY);
  ctx.scale(scale,scale);
  if(img)ctx.drawImage(img,0,0,cv.width,cv.height);
  boxes.forEach(b=>{
    ctx.strokeStyle=COLORS[b.cls];ctx.lineWidth=Math.max(2,cv.width/400);
    ctx.strokeRect(b.x,b.y,b.w,b.h);
    ctx.fillStyle=COLORS[b.cls];
    let fs=Math.max(12,cv.width/60);
    ctx.font=fs+'px monospace';
    ctx.fillText(CLASSES[b.cls],b.x+2,b.y-fs/3);
  });
  if(drawing){
    ctx.strokeStyle='rgba(255,255,255,0.7)';ctx.lineWidth=2;
    ctx.setLineDash([4,4]);
    ctx.strokeRect(drawing.x,drawing.y,drawing.w,drawing.h);
    ctx.setLineDash([]);
  }
  ctx.restore();
  info.textContent=(STEMS[curIdx]||'')+' - '+boxes.length+' boxes';
}

cv.addEventListener('wheel',e=>{
  e.preventDefault();
  let r=cv.getBoundingClientRect();
  let mx=(e.clientX-r.left), my=(e.clientY-r.top);
  let oldScale=scale;
  scale*=e.deltaY<0?1.1:0.9;
  scale=Math.max(0.2,Math.min(10,scale));
  panX=mx-(mx-panX)*(scale/oldScale);
  panY=my-(my-panY)*(scale/oldScale);
  draw();
},{passive:false});

cv.onmousedown=e=>{
  if(e.button===1||(e.button===0&&e.ctrlKey)){
    panning=true; panStart={x:e.clientX,y:e.clientY};
    cv.style.cursor='grabbing';
    return;
  }
  let r=cv.getBoundingClientRect(), sx=cv.width/r.width, sy=cv.height/r.height;
  let mx=((e.clientX-r.left)*sx-panX)/scale, my=((e.clientY-r.top)*sy-panY)/scale;
  if(deleteMode){
    for(let i=boxes.length-1;i>=0;i--){
      let b=boxes[i];
      if(mx>=b.x&&mx<=b.x+b.w&&my>=b.y&&my<=b.y+b.h){boxes.splice(i,1);draw();return;}
    }
    return;
  }
  drawing={x:mx,y:my,w:0,h:0};
};
cv.onmousemove=e=>{
  if(panning){
    panX+=e.clientX-panStart.x; panY+=e.clientY-panStart.y;
    panStart={x:e.clientX,y:e.clientY};
    draw(); return;
  }
  if(!drawing)return;
  let r=cv.getBoundingClientRect(), sx=cv.width/r.width, sy=cv.height/r.height;
  let mx=((e.clientX-r.left)*sx-panX)/scale, my=((e.clientY-r.top)*sy-panY)/scale;
  if(e.shiftKey){let s=Math.max(Math.abs(mx-drawing.x),Math.abs(my-drawing.y));drawing.w=mx>=drawing.x?s:-s;drawing.h=my>=drawing.y?s:-s}
  else{drawing.w=mx-drawing.x;drawing.h=my-drawing.y}
  draw();
};
cv.onmouseup=e=>{
  if(panning){panning=false;cv.style.cursor=deleteMode?'pointer':'crosshair';return;}
  if(!drawing)return;
  if(Math.abs(drawing.w)>3&&Math.abs(drawing.h)>3){
    let x=drawing.w>=0?drawing.x:drawing.x+drawing.w, y=drawing.h>=0?drawing.y:drawing.y+drawing.h;
    boxes.push({x,y,w:Math.abs(drawing.w),h:Math.abs(drawing.h),cls:parseInt(clsSel.value)});
  }
  drawing=null;draw();
};

function undo(){boxes.pop();draw()}
function clearAll(){if(confirm('Clear all boxes?')){boxes=[];draw()}}

function boxesToYOLO(){
  return boxes.map(b=>[b.cls,(b.x+b.w/2)/iw,(b.y+b.h/2)/ih,b.w/iw,b.h/ih]);
}

async function doSave(){
  let data={stem:STEMS[curIdx],boxes:boxesToYOLO()};
  let resp=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  let result=await resp.json();
  DONE.add(STEMS[curIdx]); updateProgress();
  info.textContent='Saved '+result.count+' boxes';
  setTimeout(()=>navigate(1),300);
}

function resetZoom(){scale=1;panX=0;panY=0;draw()}

async function doExport(){
  window.location.href='/api/export';
}

async function doSkip(){
  await fetch('/api/skip',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stem:STEMS[curIdx]})});
  DONE.add(STEMS[curIdx]); updateProgress();
  navigate(1);
}

function navigate(dir){
  curIdx=Math.max(0,Math.min(STEMS.length-1,curIdx+dir));
  loadImage(STEMS[curIdx]); updateProgress();
}

document.getElementById('delBtn').onclick=function(){
  deleteMode=!deleteMode;
  this.textContent=deleteMode?'Delete':'Edit';
  this.classList.toggle('active',deleteMode);
  cv.style.cursor=deleteMode?'pointer':'crosshair';
};

document.addEventListener('keydown',e=>{
  if(e.key==='ArrowLeft')navigate(-1);
  if(e.key==='ArrowRight')navigate(1);
  if(e.key==='s'&&e.ctrlKey){e.preventDefault();doSave();}
});

// Find first un-annotated
let first=STEMS.findIndex(s=>!DONE.has(s));
curIdx=first>=0?first:0;
loadImage(STEMS[curIdx]); updateProgress();
</script></body></html>"""

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    PORT = args.port
    print(f"Annotation server: http://localhost:{PORT}")
    print(f"Images: {len(list(IMG_DIR.glob('*.jpg')))}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()
