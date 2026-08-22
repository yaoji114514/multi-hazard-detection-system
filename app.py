"""
多类隐患智能检测与预警系统
基于YOLOv8 + Streamlit

使用方法:
  streamlit run app.py

功能:
  1. 上传工地照片,AI自动检测安全帽/反光衣佩戴情况
  2. 根据检测结果生成红/黄/蓝三级预警
  3. 检测记录自动存档,支持历史查询
  4. 统计图表展示隐患趋势
"""
import streamlit as st
import os
import sys
import json
import io
import html
import hashlib
import re
from collections import Counter
import cv2
import numpy as np
from PIL import Image as PILImage, ImageDraw, ImageFont

_FONT_PATH = r'C:\Windows\Fonts\msyh.ttc'
import torch
import threading
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
from PIL import Image

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from detector import HazardDetector, select_compute_device
from alert import AlertEngine
from database import Database

import logging
_LOG = logging.getLogger("dingtalk_send")
_LOG.setLevel(logging.DEBUG)
_LH = logging.FileHandler(str(Path(__file__).parent / "data" / "uploads" / "dingtalk_send.log"), encoding="utf-8")
_LH.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
_LOG.addHandler(_LH)

# 钉钉通知（配置缺失时不中断启动）
try:
    from dingtalk import DingTalkError, send_text, send_markdown
    _HAS_DINGTALK = True
except Exception:
    _HAS_DINGTALK = False


# ========== 实时检测全局统计 ==========
# WebRTC 回调在独立线程执行,无 ScriptRunContext,不能访问 st.session_state
#
# 重要: Streamlit 每次 rerun 会用新的命名空间执行脚本,模块级变量(_RT_STATS = {...})
# 会被重新创建,导致回调线程写旧字典、主线程读新字典(永远为0)
#
# 正确方案: 用 @st.cache_resource 缓存统计对象,确保所有 rerun 和所有线程引用同一对象

# 实时违规入库冷却期(秒): 同一违规类型在此期间只入库一次,避免每帧写库
ALERT_COOLDOWN = 10.0
# 红色告警(任务#4): 检测到未戴安全帽时触发声音+弹窗+画面红边框
RED_ALERT_COOLDOWN = 5.0   # 红色告警节流期(秒),避免连续轰击
RED_ALERT_DISPLAY = 2.0    # 弹窗持续显示时长(秒)
# 钉钉实时通知节流
DINGTALK_REALTIME_COOLDOWN = 60.0
DINGTALK_RETRY_DELAYS = (30.0, 60.0, 120.0)
# 目标跟踪去重(任务#11): track_id 去重 + 位置兜底(防 track 跳变误判)
POS_DEDUPE_RADIUS = 80     # 位置兜底半径(像素,bbox 中心点距离)
POS_DEDUPE_TIME = 30.0     # 位置兜底有效期(秒)
# 跳帧检测(任务#12): 每 N 帧才跑一次 YOLO,跳帧用缓存框重画(框不消失)
DETECT_INTERVAL_DEFAULT = 3
@st.cache_resource
def get_rt_stats():
    """跨 rerun 持久化的实时检测统计(st.cache_resource 确保全局唯一实例)"""
    return {
        "lock": threading.Lock(),
        "frames": 0,
        "classes": {},
        "violations": 0,
        "violation_classes": {"no-helmet": 0, "no-vest": 0, "no-mask": 0},
        "last_error": None,
        "last_storage_error": None,
        # --- 实时违规入库(任务#3) ---
        "last_alert_time": {},          # 各违规类型上次入库时间戳,用于节流
        "realtime_record_count": 0,     # 累计入库违规事件数
        "last_realtime_record_id": None,  # 最近一条实时记录，供界面直达处置
        "project_name": "",              # 主线程写入,回调线程读取(回调无 ScriptRunContext 拿不到侧边栏)
        "inspector": "",
        "db": None,                     # 主线程预热存 Database 实例引用,回调直接取(回调不能调 @st.cache_resource)
        # --- 红色告警(任务#4) ---
        "red_alert_time": 0.0,           # 最近一次红色告警触发时间戳
        "red_alert_played": True,        # 该告警是否已播放过声音(避免fragment刷新重复播放)
        # --- 实时录制(任务#9) ---
        "recording": False,              # 是否正在录制
        "rec_path": None,                # 当前录制文件路径
        "recorder": None,                # cv2.VideoWriter 实例(回调线程管理,主线程不碰)
        "rec_start": 0.0,                # 录制开始时间戳
        "last_recording_path": None,     # 最近完成录制的路径(停止后回调设,供UI展示)
        # --- 目标跟踪去重(任务#11) ---
        "recorded_tracks": set(),        # 已入库 "track_id:vtype",同一目标同类型只入一次
        "pos_dedupe": {},                # 位置兜底 {vtype:[(cx,cy,expire_ts)]} 防 track 跳变重复
        # --- 跳帧检测(任务#12) ---
        "detect_interval": DETECT_INTERVAL_DEFAULT,  # 每 N 帧检测一次(UI 可调)
        "last_boxes": [],                # 缓存最近检测帧 boxes(供跳帧重画)
        "last_has_violation": False,     # 缓存最近检测帧是否含 no-helmet(跳帧画红边框用)
        # --- 钉钉实时通知 ---
        "dingtalk_last_send": 0.0,
        "dingtalk_pending_counts": {},
        "dingtalk_crop_path": None,
        "dingtalk_crop_types": {},
        "dingtalk_batch": None,
        "dingtalk_sending": False,
        "dingtalk_retry_count": 0,
        "dingtalk_retry_at": 0.0,
    }


def _reset_rt_stats():
    rt = get_rt_stats()
    with rt["lock"]:
        # 录制状态(任务#9 + Bug#6): 重置时主动 release recorder,避免资源泄漏
        old_recorder = rt.get("recorder")
        rt["frames"] = 0
        rt["classes"] = {}
        rt["violations"] = 0
        rt["violation_classes"] = {"no-helmet": 0, "no-vest": 0, "no-mask": 0}
        rt["last_error"] = None
        rt["last_storage_error"] = None
        rt["last_alert_time"] = {}
        rt["realtime_record_count"] = 0
        rt["last_realtime_record_id"] = None
        rt["red_alert_time"] = 0.0
        rt["red_alert_played"] = True
        rt["recording"] = False
        rt["rec_path"] = None
        rt["rec_start"] = 0.0
        rt["last_recording_path"] = None
        rt["recorder"] = None
        # 跟踪去重 + 跳帧(任务#11/#12)
        rt["recorded_tracks"] = set()
        rt["pos_dedupe"] = {}
        rt["last_boxes"] = []
        rt["last_has_violation"] = False
        rt["dingtalk_last_send"] = 0.0
        rt["dingtalk_pending_counts"] = {}
        rt["dingtalk_crop_path"] = None
        rt["dingtalk_crop_types"] = {}
        rt["dingtalk_batch"] = None
        rt["dingtalk_sending"] = False
        rt["dingtalk_retry_count"] = 0
        rt["dingtalk_retry_at"] = 0.0
    # 锁外 release 旧 recorder(避免长持锁阻塞回调线程)
    if old_recorder is not None:
        try:
            old_recorder.release()
        except Exception:
            pass


def _snapshot_rt_stats():
    """主线程读取统计快照(深拷贝,避免渲染期间被回调线程修改)"""
    rt = get_rt_stats()
    with rt["lock"]:
        return {
            "frames": rt["frames"],
            "classes": dict(rt["classes"]),
            "violations": rt["violations"],
            "violation_classes": dict(rt["violation_classes"]),
            "last_error": rt["last_error"],
            "last_storage_error": rt.get("last_storage_error"),
            "realtime_record_count": rt.get("realtime_record_count", 0),
            "last_realtime_record_id": rt.get("last_realtime_record_id"),
            "red_alert_time": rt.get("red_alert_time", 0.0),
            "red_alert_played": rt.get("red_alert_played", True),
            "recording": rt.get("recording", False),
            "rec_start": rt.get("rec_start", 0.0),
            "last_recording_path": rt.get("last_recording_path"),
            "detect_interval": rt.get("detect_interval", DETECT_INTERVAL_DEFAULT),
            "dingtalk_pending_counts": dict(rt.get("dingtalk_pending_counts", {})),
            "dingtalk_sending": rt.get("dingtalk_sending", False),
            "dingtalk_retry_count": rt.get("dingtalk_retry_count", 0),
            "dingtalk_retry_at": rt.get("dingtalk_retry_at", 0.0),
        }


def _play_alert_sound():
    """播放警报音(HTML audio autoplay,依赖页面已被用户交互过以通过浏览器自动播放策略)"""
    import base64
    alert_path = Path(__file__).parent / "data" / "alert.wav"
    if alert_path.exists():
        audio_b64 = base64.b64encode(alert_path.read_bytes()).decode()
        st.markdown(
            f'<audio autoplay><source src="data:audio/wav;base64,{audio_b64}" type="audio/wav"></audio>',
            unsafe_allow_html=True,
        )


def _send_image_alert(alerts, record_id, image_path, project_name='', inspector=''):
    """将有预警的图片检测结果发送到钉钉群。失败时仅记录不抛异常。"""
    try:
        level_icons = {'red': '红色预警', 'yellow': '黄色预警'}
        highest = max(alerts, key=lambda a: {'red': 3, 'yellow': 2, 'blue': 1}.get(a['level'], 0))
        type_counts = {}
        for a in alerts:
            t = a['hazard_type']
            type_counts[t] = type_counts.get(t, 0) + 1
        lines = [level_icons.get(highest['level'], '预警'), '']
        if project_name:
            lines.append('项目：' + project_name)
        if inspector:
            lines.append('检查人：' + inspector)
        lines.append('时间：' + __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        lines.append('')
        lines.append('隐患明细：')
        for t, c in type_counts.items():
            lines.append('  - ' + t + ' x ' + str(c))
        lines.append('')
        lines.append('处理建议：' + highest['action'])
        lines.append('')
        lines.append('本消息由多类隐患检测系统自动发送')
        results = send_text('\n'.join(lines))
        sent_count = len(results or [])
        return {
            "status": "sent" if sent_count else "no_recipient",
            "sent_count": sent_count,
        }
    except Exception as e:
        st.caption('钉钉通知发送失败: ' + str(e))
        return {
            "status": "failed",
            "detail": str(e),
        }


def _send_realtime_violations(rt_stats, project_name="", inspector=""):
    if not _HAS_DINGTALK:
        _LOG.warning("_HAS_DINGTALK=False, skip")
        return
    now_ts = __import__("time").time()
    with rt_stats["lock"]:
        if rt_stats.get("dingtalk_sending", False):
            return
        if now_ts < rt_stats.get("dingtalk_retry_at", 0.0):
            return
        batch = rt_stats.get("dingtalk_batch")
        if batch is None:
            pending = rt_stats.get("dingtalk_pending_counts", {})
            last_send = rt_stats.get("dingtalk_last_send", 0.0)
            if not pending or now_ts - last_send < DINGTALK_REALTIME_COOLDOWN:
                return
            batch = {
                "counts": dict(pending),
                "crop_path": rt_stats.get("dingtalk_crop_path"),
                "project_name": project_name,
                "inspector": inspector,
                "created_at": now_ts,
                "text_sent": False,
            }
            rt_stats["dingtalk_batch"] = batch
            rt_stats["dingtalk_retry_count"] = 0
        rt_stats["dingtalk_sending"] = True

    try:
        send_counts = batch["counts"]
        crop_path = batch["crop_path"]
        _LOG.info("sending markdown, violations=%s, crop_path=%s", list(send_counts.keys()), crop_path)
        highest = "yellow"
        violation_cn = []
        for vt in send_counts:
            cn = HazardDetector.LABEL_CN.get(vt, vt)
            violation_cn.append(cn)
            lvl = HazardDetector.ALERT_LEVELS.get(vt, ("blue",))[0]
            if lvl == "red":
                highest = "red"
        cn_level = {"red": "红色预警", "yellow": "黄色预警"}
        title = cn_level.get(highest, "预警") + " - 实时检测"
        lines = ["## " + title, ""]
        if batch["project_name"]:
            lines.append("**项目：**" + batch["project_name"])
        if batch["inspector"]:
            lines.append("**检查人：**" + batch["inspector"])
        ts = __import__("datetime").datetime.fromtimestamp(batch["created_at"])
        cooldown = int(DINGTALK_REALTIME_COOLDOWN)
        lines.append(f"**时间：**{ts:%H:%M} (近{cooldown}秒汇总)")
        lines.append("")
        lines.append("**检测到以下违规：**")
        for cn in violation_cn:
            lines.append("- " + cn)
        lines.append("")
        lines.append(f"本消息由多类隐患检测系统自动发送（{cooldown}s 汇总）")
        # 先发文字
        if not batch["text_sent"]:
            send_markdown(title, "\n".join(lines))
            with rt_stats["lock"]:
                if rt_stats.get("dingtalk_batch") is not batch:
                    return
                batch["text_sent"] = True
            _LOG.info("markdown sent OK")
        # 再发裁剪图(base64直传,不做markdown内嵌)
        if crop_path and Path(crop_path).exists():
            try:
                __import__("dingtalk", fromlist=["send_image"]).send_image(crop_path)
                _LOG.info("image sent OK: %s", crop_path)
            except Exception:
                _LOG.exception("image send FAILED: %s", crop_path)
                raise
        else:
            _LOG.warning("no crop_path or file missing: %s", crop_path)

        with rt_stats["lock"]:
            if rt_stats.get("dingtalk_batch") is batch:
                pending = rt_stats.get("dingtalk_pending_counts", {})
                for violation_type, sent_count in send_counts.items():
                    remaining = pending.get(violation_type, 0) - sent_count
                    if remaining > 0:
                        pending[violation_type] = remaining
                    else:
                        pending.pop(violation_type, None)
                if rt_stats.get("dingtalk_crop_path") == crop_path:
                    rt_stats["dingtalk_crop_path"] = None
                    rt_stats["dingtalk_crop_types"] = {}
                rt_stats["dingtalk_last_send"] = __import__("time").time()
                rt_stats["dingtalk_batch"] = None
                rt_stats["dingtalk_sending"] = False
                rt_stats["dingtalk_retry_count"] = 0
                rt_stats["dingtalk_retry_at"] = 0.0
    except Exception:
        retry_delay = None
        with rt_stats["lock"]:
            if rt_stats.get("dingtalk_batch") is batch:
                retry_count = rt_stats.get("dingtalk_retry_count", 0) + 1
                retry_delay = DINGTALK_RETRY_DELAYS[min(retry_count - 1, len(DINGTALK_RETRY_DELAYS) - 1)]
                rt_stats["dingtalk_retry_count"] = retry_count
                rt_stats["dingtalk_retry_at"] = __import__("time").time() + retry_delay
                rt_stats["dingtalk_sending"] = False
        _LOG.exception("_send_realtime_violations FAILED; retry in %ss", retry_delay)



def _put_chinese_text(img, text, pos, font_size, color):
    """用 PIL 在 OpenCV 图像上绘制中文文本（cv2.putText 不支持 CJK）。"""
    pil_img = PILImage.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    try:
        font = ImageFont.truetype(_FONT_PATH, font_size)
    except Exception:
        font = ImageFont.load_default()
    draw.text(pos, text, font=font, fill=color[::-1])  # RGB→BGR
    img[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def _draw_boxes(img, boxes, detector):

    """跳帧时用缓存 boxes 在当前帧重画框(任务#12: 框不消失)

    boxes: [(x1,y1,x2,y2,cls_id,conf,track_id), ...]
    """
    for x1, y1, x2, y2, cls_id, conf_val, tid in boxes:
        raw_name = detector.model.names[cls_id]
        label_en = detector._map_label(raw_name)
        level_key = detector.ALERT_LEVELS.get(label_en, ("blue",))[0]
        color = {"red": (0, 0, 255), "yellow": (0, 255, 255), "blue": (255, 0, 0)}.get(level_key, (255, 0, 0))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = f"{detector.LABEL_CN.get(label_en, label_en)} {conf_val:.2f}"
        _put_chinese_text(img, label, (x1, max(y1 - 6, 12)), 14, color)
        # 显示 track_id(任务: 在检测框上显示追踪ID)
        if tid is not None:
            id_label = f"ID:{tid}"
            _put_chinese_text(img, id_label, (x2 - 60, max(y1 - 6, 12)), 14, (0, 255, 0))


# ========== 页面配置 ==========
st.set_page_config(
    page_title="多类隐患智能检测与预警系统",
    layout="wide",
)

# 隐藏右上角 Deploy 按钮(Streamlit Community Cloud 部署入口,参赛项目不需要)
# CSS 类名因 streamlit 版本而异,用多选择器覆盖(.stAppDeployButton 1.40+, .stDeployButton 旧版)
st.markdown(
    """
    <style>
    :root {
        --surface-0: #08111d;
        --surface-1: #0e1826;
        --surface-2: #142235;
        --surface-3: #1a2b40;
        --line: #2a3c52;
        --text: #f2f5f8;
        --muted: #a7b5c5;
        --action: #5b8ff9;
        --danger: #ff626c;
        --warning: #f4c95d;
        --safe: #6faf93;
    }
    .stAppDeployButton, .stDeployButton, [data-testid="stHeaderActionElements"] {
        display: none !important;
    }
    html, body, .stApp {
        font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    }
    ::selection {
        color: #ffffff;
        background: #2f64bd;
    }
    .block-container {
        max-width: 1440px;
        padding-top: 1.8rem;
        padding-bottom: 4rem;
    }
    [data-testid="stAppViewBlockContainer"] h1 {
        max-width: none;
        margin: 0 0 .35rem !important;
        font-size: 2rem !important;
        letter-spacing: -.025em !important;
        line-height: 1.15 !important;
    }
    [data-testid="stSidebar"] h1 {
        max-width: none;
        font-size: 1.55rem !important;
        line-height: 1.25 !important;
        letter-spacing: -.015em !important;
    }
    h2, h3 {
        margin-top: 2.25rem !important;
        margin-bottom: .65rem !important;
        letter-spacing: -.015em !important;
    }
    p, label, [data-testid="stCaptionContainer"] {
        line-height: 1.65;
    }
    [data-testid="stCaptionContainer"] {
        color: var(--muted);
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid var(--line);
        background: #0d1724;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label {
        min-height: 42px;
        padding: .32rem .45rem;
        border-radius: 8px;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
        background: var(--surface-2);
    }
    [data-testid="stMetric"] {
        padding: .8rem 0 1rem;
        border-top: 1px solid var(--line);
    }
    [data-testid="stMetricValue"] {
        font-variant-numeric: tabular-nums;
        letter-spacing: -.025em;
    }
    .metric-strip {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
        gap: 0 1rem;
        margin: .5rem 0 1.4rem;
    }
    .metric-strip > div {
        min-width: 0;
        padding: .8rem 0 1rem;
        border-top: 1px solid var(--line);
    }
    .metric-strip dt {
        margin-bottom: .2rem;
        color: var(--muted);
        font-size: .9rem;
    }
    .metric-strip dd {
        margin: 0;
        overflow-wrap: anywhere;
        color: var(--text);
        font-size: clamp(1.65rem, 3vw, 2.25rem);
        font-weight: 520;
        font-variant-numeric: tabular-nums;
        letter-spacing: -.025em;
        line-height: 1.15;
    }
    .stButton > button, .stDownloadButton > button {
        min-height: 44px;
        border-radius: 10px;
        font-weight: 650;
    }
    .stButton > button:focus-visible,
    .stDownloadButton > button:focus-visible,
    input:focus-visible,
    textarea:focus-visible,
    [role="radio"]:focus-visible,
    [role="tab"]:focus-visible {
        outline: 3px solid rgba(79, 140, 255, .55) !important;
        outline-offset: 2px !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        min-height: 132px;
        border-color: var(--line);
        border-radius: 12px;
    }
    [data-testid="stAlert"] {
        border-radius: 12px;
        border-width: 1px;
    }
    .risk-panel {
        margin: 1.1rem 0 1.4rem;
        padding: 1.1rem 1.2rem;
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--surface-1);
        animation: risk-arrive .24s cubic-bezier(.16, 1, .3, 1);
    }
    .risk-panel strong {
        display: block;
        margin-bottom: .3rem;
        font-size: 1.08rem;
    }
    .risk-panel span {
        color: var(--muted);
    }
    .risk-panel.red { border-color: rgba(255, 93, 104, .62); }
    .risk-panel.red strong { color: #ff9ba2; }
    .risk-panel.yellow { border-color: rgba(242, 193, 78, .58); }
    .risk-panel.yellow strong { color: #f8d982; }
    .risk-panel.blue { border-color: rgba(104, 166, 255, .5); }
    .risk-panel.blue strong { color: #a7c9ff; }
    .risk-panel.neutral { border-color: rgba(167, 181, 197, .32); }
    .risk-panel.neutral strong { color: var(--text); }
    .status-rail {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        margin: .35rem 0 1.75rem;
        border-top: 1px solid var(--line);
        border-bottom: 1px solid var(--line);
    }
    .status-cell {
        min-width: 0;
        padding: .9rem 1rem .95rem 0;
    }
    .status-cell + .status-cell {
        padding-left: 1rem;
        border-left: 1px solid var(--line);
    }
    .status-cell span,
    .status-cell small {
        display: block;
        color: var(--muted);
        font-size: .78rem;
        line-height: 1.35;
    }
    .status-cell strong {
        display: block;
        margin: .22rem 0;
        overflow-wrap: anywhere;
        color: var(--text);
        font-size: 1rem;
        font-weight: 650;
    }
    .system-notice {
        display: grid;
        grid-template-columns: minmax(150px, .32fr) 1fr;
        gap: 1rem;
        margin: .75rem 0 1rem;
        padding: .75rem 0;
        border-top: 1px solid var(--line);
        border-bottom: 1px solid var(--line);
    }
    .system-notice strong { color: var(--text); }
    .system-notice span { color: var(--muted); }
    .system-notice.healthy strong { color: #96cfb6; }
    .system-notice.error strong { color: #ff9aa1; }
    .command-panel {
        padding: .25rem 0 1rem 1.4rem;
        border-left: 1px solid var(--line);
    }
    .evidence-stage {
        min-height: 260px;
        padding: 1rem;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface-1);
    }
    [data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 8px;
        overflow: hidden;
    }
    .queue-note {
        margin: .25rem 0 1rem;
        color: var(--muted);
        font-size: .92rem;
    }
    @keyframes risk-arrive {
        from { transform: translateY(4px); filter: blur(2px); }
        to { transform: translateY(0); filter: blur(0); }
    }
    @media (max-width: 640px) {
        .block-container {
            padding: 1.35rem 1rem 3rem;
        }
        [data-testid="stAppViewBlockContainer"] h1 { font-size: 1.5rem !important; }
        .status-rail { grid-template-columns: 1fr 1fr; }
        .status-cell:nth-child(odd) { padding-left: 0; border-left: 0; }
        .status-cell:nth-child(even) { padding-left: .8rem; border-left: 1px solid var(--line); }
        .system-notice { grid-template-columns: 1fr; gap: .25rem; }
        .command-panel { padding-left: 0; border-left: 0; }
        .risk-panel { padding: 1rem; }
        .metric-strip {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0 .8rem;
        }
        .metric-strip dd { font-size: 1.7rem; }
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: .01ms !important;
            animation-iteration-count: 1 !important;
            scroll-behavior: auto !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


INCIDENT_STATUS_CN = {
    "pending": "待处理",
    "in_progress": "处理中",
    "closed": "已关闭",
    "false_positive": "误报",
    "not_applicable": "无需处置",
}


def _safe_json_list(value):
    """读取历史 JSON 列；损坏记录退化为空列表，避免整页中断。"""
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _image_fingerprint(file_bytes, model_version):
    """同一图片在同一模型下复用当前会话结果，避免 rerun 重复入库。"""
    digest = hashlib.sha256()
    digest.update(file_bytes)
    digest.update(b"\0")
    digest.update(str(model_version or "").encode("utf-8"))
    return digest.hexdigest()


def _record_risk(record):
    """从图片或实时记录中推导业务风险等级。"""
    if record.get("level") in {"red", "yellow", "blue"}:
        return record["level"]
    if int(record.get("red_alerts") or 0) > 0 or int(record.get("no_helmet_count") or 0) > 0:
        return "red"
    if int(record.get("yellow_alerts") or 0) > 0 or int(record.get("no_vest_count") or 0) > 0:
        return "yellow"
    return "blue"


def _risk_meta(level):
    return {
        "red": ("红色风险", "立即停工核查未戴安全帽人员", 0),
        "yellow": ("黄色风险", "限时整改并复核防护用品", 1),
        "blue": ("当前未发现违规", "保留记录并继续巡检", 2),
        "neutral": ("尚无监测结论", "启动监测后显示风险结论", 3),
    }.get(level, ("状态待复核", "人工核对检测证据", 3))


def _render_risk_banner(level, count=0, action=None):
    label, default_action, _ = _risk_meta(level)
    detail = action or default_action
    count_text = f"，涉及 {int(count)} 个违规目标" if count else ""
    st.markdown(
        f'<div class="risk-panel {level}" role="status">'
        f'<strong>{html.escape(label)}{count_text}</strong>'
        f'<span>下一步：{html.escape(str(detail))}</span></div>',
        unsafe_allow_html=True,
    )


def _render_page_header(title, description, meta=None):
    """第二版统一页头：标题、任务说明和可选上下文。"""
    st.title(title)
    st.markdown(description)
    if meta:
        st.caption(meta)


def _render_status_rail(items):
    """以连续状态轨展示本次检查上下文和系统健康。"""
    cells = "".join(
        '<div class="status-cell">'
        f'<span>{html.escape(str(label))}</span>'
        f'<strong>{html.escape(str(value))}</strong>'
        f'<small>{html.escape(str(detail))}</small></div>'
        for label, value, detail in items
    )
    st.markdown(
        f'<section class="status-rail" aria-label="值守状态">{cells}</section>',
        unsafe_allow_html=True,
    )


def _render_system_notice(title, detail, state="info"):
    """系统与监测状态使用独立通道，不占用红黄业务风险。"""
    st.markdown(
        f'<div class="system-notice {html.escape(state)}" role="status">'
        f'<strong>{html.escape(str(title))}</strong>'
        f'<span>{html.escape(str(detail))}</span></div>',
        unsafe_allow_html=True,
    )


def _realtime_ui_state(snapshot, camera_playing):
    """把监测、风险和故障状态分层，避免把未启动误报为安全。"""
    if camera_playing:
        monitor = ("监测运行中", "摄像头画面正在分析", "healthy")
    else:
        monitor = ("尚未启动监测", "启动摄像头后才会形成现场风险结论", "idle")

    violation_classes = snapshot.get("violation_classes") or {}
    violation_count = int(snapshot.get("violations") or 0)
    if not camera_playing and violation_count == 0:
        risk = ("neutral", 0, "启动监测后显示风险结论")
    elif violation_count <= 0:
        risk = ("blue", 0, "继续值守，发现风险后将自动留存证据")
    elif int(violation_classes.get("no-helmet") or 0) > 0:
        risk = ("red", violation_count, "查看最近记录并立即安排现场核查")
    else:
        risk = ("yellow", violation_count, "查看最近记录并安排限时复核")

    system = None
    if snapshot.get("last_storage_error"):
        system = (
            "实时证据保存失败",
            "本次抓拍未进入处置队列，请停止监测，检查本地数据库后重置本次统计并重新值守。",
            "error",
        )
    elif snapshot.get("last_error"):
        system = (
            "实时检测系统异常",
            "当前画面已回退为原始视频，请停止并重新启动摄像头。",
            "error",
        )
    return {"monitor": monitor, "risk": risk, "system": system}


def _save_realtime_incident(db, rt_stats, **record):
    """保存实时证据；只有成功入库才更新界面的已存记录计数。"""
    try:
        if db is None:
            raise RuntimeError("本地记录服务未就绪")
        record_id = db.save_realtime_violation(**record)
    except Exception as exc:
        _LOG.exception("实时证据保存失败: %s", exc)
        with rt_stats["lock"]:
            rt_stats["last_storage_error"] = f"{type(exc).__name__}: {exc}"
        return None

    with rt_stats["lock"]:
        rt_stats["last_realtime_record_id"] = record_id
        rt_stats["realtime_record_count"] += 1
    return record_id


def _record_is_overdue(record, now=None):
    due_at = record.get("due_at")
    current = now or datetime.now()
    if isinstance(current, datetime):
        current = current.strftime("%Y-%m-%d %H:%M:%S")
    return bool(
        due_at
        and record.get("incident_status") in {"pending", "in_progress"}
        and due_at < current
    )


def _queue_matches_quick_view(record, quick_view, inspector="", now=None):
    """记录页快捷视图的纯筛选规则。"""
    status = record.get("incident_status", "pending")
    is_open = status in {"pending", "in_progress"}
    if quick_view == "open":
        return is_open
    if quick_view == "in_progress":
        return status == "in_progress"
    if quick_view == "mine":
        return bool(inspector.strip()) and is_open and record.get("assignee", "").strip() == inspector.strip()
    if quick_view == "unassigned":
        return is_open and not record.get("assignee", "").strip()
    if quick_view == "red":
        return is_open and _record_risk(record) == "red"
    if quick_view == "overdue":
        return _record_is_overdue(record, now)
    return True


def _request_incident_focus(source_type, record_id):
    """在下一次 rerun 中打开指定处置记录。"""
    st.session_state["_requested_page"] = "检测记录"
    st.session_state["_requested_queue_view"] = "all"
    st.session_state["_incident_focus_source"] = source_type
    st.session_state["_incident_focus_id"] = int(record_id)
    st.session_state["incident_queue_keyword"] = ""
    st.session_state["incident_queue_risk"] = "all"
    st.session_state["incident_queue_status"] = "all"
    st.session_state["incident_queue_source"] = "全部来源"
    st.session_state["incident_queue_project"] = "全部项目"
    st.session_state["incident_queue_time"] = "all"


def _request_queue_view(quick_view):
    """从统计页打开指定的处置队列视图。"""
    st.session_state["_requested_page"] = "检测记录"
    st.session_state["_requested_queue_view"] = quick_view


def _render_metric_strip(items):
    """用紧凑、可响应的定义列表展示关键数值。"""
    cells = "".join(
        f"<div><dt>{html.escape(str(label))}</dt><dd>{html.escape(str(value))}</dd></div>"
        for label, value in items
    )
    st.markdown(f'<dl class="metric-strip">{cells}</dl>', unsafe_allow_html=True)


def _dingtalk_name_needs_confirmation(name):
    """识别容易混淆的占位群名，提醒用户补全钉钉中的真实名称。"""
    compact = re.sub(r"\s+", "", str(name or ""))
    return (
        not compact
        or compact in {"默认群", "未命名群", "群", "群组"}
        or re.fullmatch(r"群\d+", compact, flags=re.IGNORECASE) is not None
    )


def _dingtalk_identity_session_key(short_id, open_conversation_id):
    """为不暴露会话 ID 的群名验证结果生成会话内缓存键。"""
    fingerprint = hashlib.sha256(
        str(open_conversation_id or "").strip().encode("utf-8")
    ).hexdigest()[:12]
    return f"dt_group_identity_{short_id}_{fingerprint}"


def _notification_overview():
    """返回已启用通知群摘要；配置异常不阻断前端。"""
    if not _HAS_DINGTALK:
        return "未配置", 0
    try:
        import dingtalk as _dt
        groups = _dt.list_webhooks()
    except Exception:
        return "暂不可用", 0
    enabled = sum(bool(group.get("enabled")) for group in groups)
    if not groups:
        return "未配置", 0
    return (f"已启用 {enabled}/{len(groups)} 个群" if enabled else "全部暂停", enabled)


def _render_workspace_status(project_name, inspector, detector, workflow_stats):
    open_count = int(workflow_stats.get("pending", 0)) + int(workflow_stats.get("in_progress", 0))
    notification_text, _ = _notification_overview()
    model_state = "PPE 专用模型可用"
    if getattr(detector, "fallback_used", False):
        model_state = "模型已降级"
    _render_status_rail([
        ("本次项目", project_name.strip() or "尚未填写", "所有新证据将归入该项目"),
        ("检查人", inspector.strip() or "尚未填写", "用于记录与复核追溯"),
        ("开放事项", f"{open_count} 条", f"其中超期 {workflow_stats.get('overdue', 0)} 条"),
        ("运行状态", model_state, f"通知：{notification_text}"),
    ])


# ========== 初始化 ==========
@st.cache_resource
def get_detector(model_path):
    """Cache a detector by its resolved model path."""
    return HazardDetector(model_path)


def get_current_detector():
    return get_detector(str(HazardDetector.resolve_model_path()))


@st.cache_resource
def get_database():
    return Database()


@st.cache_resource
def get_alert_engine():
    return AlertEngine()


_PROJECT_CONTEXT_KEY = "last_check_project_name"
_INSPECTOR_CONTEXT_KEY = "last_check_inspector"


def _restore_last_check_context():
    """首次打开页面时恢复本机最近一次检查上下文。"""
    if st.session_state.get("_last_check_context_loaded"):
        return
    st.session_state["_last_check_context_loaded"] = True
    try:
        loader = getattr(get_database(), "get_last_check_context", None)
        context = loader() if callable(loader) else {}
    except Exception:
        _LOG.warning("无法读取最近检查上下文，将使用空白输入")
        return
    for state_key, field in ((_PROJECT_CONTEXT_KEY, "project_name"),
                             (_INSPECTOR_CONTEXT_KEY, "inspector")):
        if state_key not in st.session_state:
            st.session_state[state_key] = str(context.get(field, "") or "")


def _save_last_check_context():
    """输入变更后保存本机默认值；保存失败不阻断当前检查。"""
    try:
        saver = getattr(get_database(), "save_last_check_context", None)
        if callable(saver):
            saver(
                st.session_state.get(_PROJECT_CONTEXT_KEY, ""),
                st.session_state.get(_INSPECTOR_CONTEXT_KEY, ""),
            )
    except Exception:
        _LOG.warning("无法保存最近检查上下文，本次检查仍可继续")


def _render_dingtalk_group_toggles():
    """编辑群名、会话绑定与接收状态，提交后一次写回本地配置。"""
    if not _HAS_DINGTALK:
        return
    try:
        import dingtalk as _dt
        webhooks = _dt.list_webhooks()
    except Exception:
        return
    if not webhooks:
        return

    enabled_count = sum(bool(w["enabled"]) for w in webhooks)
    normalized_names = [str(w["name"]).strip().casefold() for w in webhooks]
    duplicate_names = {
        name for name, count in Counter(normalized_names).items() if name and count > 1
    }
    save_requested = False
    refresh_requested = False
    pending = []
    with st.sidebar.expander(
        f"通知设置 · 已启用 {enabled_count}/{len(webhooks)} 个群",
        expanded=False,
    ):
        st.caption("钉钉隐患通知")
        with st.container(border=True):
            st.markdown("**接收群组**")
            st.caption("Webhook 不能反查群名。绑定钉钉会话 ID 后可手动验证；安全群标识可区分同名群，不会显示密钥。")
            with st.form("dingtalk_group_settings"):
                for i, w in enumerate(webhooks):
                    short_id = w.get("short_id") or hashlib.sha256(
                        w["webhook"].encode("utf-8")
                    ).hexdigest()[:8].upper()
                    name = st.text_input(
                        f"群 {i + 1} 名称",
                        value=w["name"],
                        max_chars=60,
                        key=f"dt_group_name_{i}_{short_id}",
                        help="本机显示名；绑定并验证后会同时显示钉钉官方群名。",
                    )
                    open_conversation_id = st.text_input(
                        "绑定会话 ID（可选）",
                        value=str(w.get("open_conversation_id", "")),
                        type="password",
                        max_chars=200,
                        key=f"dt_group_binding_{i}_{short_id}",
                        help="请在有权限的钉钉微应用/小程序中选群后粘贴 openConversationId；输入内容不会展示。",
                    ).strip()
                    receives = st.toggle(
                        "接收该群通知",
                        value=bool(w["enabled"]),
                        key=f"dt_group_enabled_{i}_{short_id}",
                    )
                    state_text = "接收中" if receives else "已暂停"
                    st.caption(f"群标识 {short_id} · {state_text}")
                    identity_key = _dingtalk_identity_session_key(
                        short_id, open_conversation_id
                    )
                    identity = st.session_state.get(identity_key)
                    if identity and identity.get("status") == "verified":
                        try:
                            checked_at = datetime.fromtimestamp(
                                float(identity.get("checked_at", 0))
                            ).strftime("%Y-%m-%d %H:%M")
                        except (TypeError, ValueError, OSError):
                            checked_at = "刚刚"
                        st.caption(
                            f"钉钉官方群名：{identity['official_name']} · 名称来源：钉钉接口 · 识别状态：已验证 · 最近验证：{checked_at}"
                        )
                    elif open_conversation_id:
                        reason = (identity or {}).get(
                            "reason", "已绑定，点击“刷新群名”验证"
                        )
                        st.caption(f"名称来源：本机配置 · 识别状态：暂时无法验证（{reason}）")
                    else:
                        st.caption("名称来源：本机配置 · 识别状态：未绑定")
                    if str(w["name"]).strip().casefold() in duplicate_names:
                        st.warning("发现同名群，请核对群标识后再保存。")
                    elif _dingtalk_name_needs_confirmation(w["name"]):
                        st.info("当前群名较笼统，建议改成钉钉中的完整群名。")
                    pending.append({
                        "short_id": short_id,
                        "name": str(name).strip(),
                        "enabled": receives,
                        "open_conversation_id": open_conversation_id,
                    })
                    if i < len(webhooks) - 1:
                        st.divider()
                save_requested = st.form_submit_button(
                    "保存群组选择",
                    type="primary",
                    width="stretch",
                )
                refresh_requested = st.form_submit_button("刷新群名（不保存）")

    if refresh_requested:
        results = []
        for item in pending:
            identity_key = _dingtalk_identity_session_key(
                item["short_id"], item["open_conversation_id"]
            )
            try:
                result = _dt.resolve_group_identity(item, refresh=True)
            except Exception:
                result = {"status": "unavailable", "reason": "暂时无法验证群名"}
            st.session_state[identity_key] = result
            results.append(result)
        verified_count = sum(
            item.get("status") == "verified" for item in results
        )
        st.sidebar.info(
            f"已刷新 {len(results)} 个群：{verified_count} 个群名已由钉钉验证；刷新不会保存编辑内容。"
        )

    if save_requested:
        if any(not item["name"] for item in pending):
            st.sidebar.error("群名称不能为空，请填写后再保存。")
            return
        if any(not item["short_id"] for item in pending):
            st.sidebar.error("群标识缺失，未保存设置。")
            return
        bound_ids = [
            item["open_conversation_id"] for item in pending
            if item["open_conversation_id"]
        ]
        if len(bound_ids) != len(set(bound_ids)):
            st.sidebar.error("同一个钉钉会话 ID 不能绑定到多个群。")
            return
        if not any(item["enabled"] for item in pending):
            st.sidebar.error("请至少保留一个接收群，再保存设置。")
            return
        try:
            cfg_path = Path(__file__).parent / "config" / "dingtalk.local.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            updates = {item["short_id"]: item for item in pending}
            config_groups = cfg.get("webhooks")
            if isinstance(config_groups, list):
                matched = set()
                for item in config_groups:
                    item_id = _dt.webhook_short_id(str(item.get("webhook", "")).strip())
                    update = updates.get(item_id)
                    if update:
                        if item_id in matched:
                            raise ValueError("配置中存在重复 webhook")
                        item["name"] = update["name"]
                        item["enabled"] = update["enabled"]
                        if update["open_conversation_id"]:
                            item["open_conversation_id"] = update["open_conversation_id"]
                        else:
                            item.pop("open_conversation_id", None)
                        matched.add(item_id)
                if matched != set(updates):
                    raise ValueError("群标识与本地配置不一致")
            elif len(pending) == 1 and str(cfg.get("webhook", "")).strip():
                update = pending[0]
                legacy_group = {
                    "name": update["name"],
                    "webhook": str(cfg["webhook"]).strip(),
                    "enabled": update["enabled"],
                }
                if update["open_conversation_id"]:
                    legacy_group["open_conversation_id"] = update["open_conversation_id"]
                cfg["webhooks"] = [legacy_group]
            else:
                raise ValueError("未找到可更新的钉钉群配置")
            cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            st.sidebar.success("接收群组已保存，下一条钉钉通知起生效。")
        except Exception:
            _LOG.exception("保存钉钉接收群组失败")
            st.sidebar.error("接收群组保存失败，请检查本地配置文件是否可写后重试。")


# ========== 侧边栏 ==========
st.sidebar.title("隐患处置值守台")
st.sidebar.caption("本地值守模式 · 数据保存在本机")
st.sidebar.markdown("---")

# 项目信息
st.sidebar.markdown("**本次检查**")
_restore_last_check_context()
project_name = st.sidebar.text_input(
    "项目名称", key=_PROJECT_CONTEXT_KEY, placeholder="填写当前项目",
    help="本次新增的图片、实时抓拍和处置记录将使用该项目名称。",
    on_change=_save_last_check_context,
)
inspector = st.sidebar.text_input(
    "检查人", key=_INSPECTOR_CONTEXT_KEY, placeholder="填写姓名",
    help="用于证据追溯和处置复核。",
    on_change=_save_last_check_context,
)
st.sidebar.caption("项目名称和检查人会自动保存到本机，下次启动时恢复。")

# 导航
NAV_PAGES = ["隐患检测", "实时检测", "视频检测", "检测记录", "统计分析"]
requested_page = st.session_state.pop("_requested_page", None)
if requested_page in NAV_PAGES:
    st.session_state["_main_page"] = requested_page
page = st.sidebar.radio("功能导航", NAV_PAGES, key="_main_page")

active_detector = get_current_detector()
try:
    sidebar_workflow_stats = get_database().get_incident_statistics()
except Exception:
    sidebar_workflow_stats = {"pending": 0, "in_progress": 0, "overdue": 0}
open_incidents = int(sidebar_workflow_stats.get("pending", 0)) + int(sidebar_workflow_stats.get("in_progress", 0))
st.sidebar.caption(f"开放事项：{open_incidents} · 已超期：{sidebar_workflow_stats.get('overdue', 0)}")
st.sidebar.caption("模型状态：可用" if not active_detector.fallback_used else "模型状态：已降级")
if active_detector.fallback_used:
    if getattr(active_detector, "model_type", "") == "coco":
        st.sidebar.error("PPE 专用模型不可用，本次结果不能作为安全判定依据。请恢复模型后重新检测。")
    else:
        st.sidebar.warning("当前模型已自动回退。请复核检测结果，并尽快恢复首选模型。")
    with st.sidebar.expander("查看模型技术详情", expanded=False):
        st.code(str(active_detector.fallback_reason or "未提供回退原因"))
else:
    with st.sidebar.expander("查看模型技术详情", expanded=False):
        st.caption(f"当前模型文件：{active_detector.model_version}")

_render_dingtalk_group_toggles()


# ========== 页面1: 隐患检测 ==========
if page == "隐患检测":
    _render_page_header(
        "多类隐患智能检测",
        "上传现场照片，识别安全帽、反光衣与口罩风险，并将证据直接送入处置队列。",
        "图片证据",
    )
    _render_workspace_status(project_name, inspector, active_detector, sidebar_workflow_stats)

    evidence_col, command_col = st.columns([7, 5], vertical_alignment="top")
    with evidence_col:
        st.markdown("### 证据工作区")
        uploaded_file = st.file_uploader(
            "选择工地照片",
            type=["jpg", "jpeg", "png"],
            help="支持 JPG/PNG 格式",
        )

        sample_dir = Path(__file__).parent / "data" / "sample_images"
        sample_files = []
        if sample_dir.exists():
            sample_files = list(sample_dir.glob("*.jpg")) + list(sample_dir.glob("*.png"))
        if sample_files:
            st.markdown("#### 示例现场")
            cols = st.columns(min(len(sample_files), 2))
            for i, sf in enumerate(sample_files[:4]):
                with cols[i % len(cols)]:
                    st.image(str(sf), caption=sf.stem.replace("_", " "), width="stretch")
                    if st.button("使用该示例", key=f"sample_{i}", width="stretch"):
                        st.session_state["_selected_sample_path"] = str(sf)

    if uploaded_file is not None:
        # 实际上传优先于此前选择的示例。
        st.session_state.pop("_selected_sample_path", None)
    else:
        selected_sample_path = st.session_state.get("_selected_sample_path")
        if selected_sample_path and Path(selected_sample_path).is_file():
            sample_path = Path(selected_sample_path)
            sample_buffer = io.BytesIO(sample_path.read_bytes())
            sample_buffer.name = sample_path.name
            uploaded_file = sample_buffer
            st.caption(f"已选择示例：{sample_path.name}")

    file_bytes = bytes(uploaded_file.getbuffer()) if uploaded_file is not None else None
    file_fingerprint = (
        _image_fingerprint(file_bytes, active_detector.model_version)
        if file_bytes is not None else None
    )
    cached_detection = st.session_state.get("_image_detection_cache")
    cache_matches = bool(
        cached_detection
        and cached_detection.get("fingerprint") == file_fingerprint
    )
    context_ready = bool(project_name.strip() and inspector.strip())
    with command_col:
        st.markdown("### 检测命令")
        notification_text, _ = _notification_overview()
        _render_metric_strip([
            ("写入项目", project_name.strip() or "尚未填写"),
            ("检查人", inspector.strip() or "尚未填写"),
        ])
        model_status = "专用模型可用" if not active_detector.fallback_used else "模型已降级"
        st.caption(f"模型：{model_status} · 风险通知：{notification_text}")
        start_label = "重新检测并新建记录" if cache_matches else "开始图片检测"
        start_image = st.button(
            start_label,
            type="primary",
            disabled=uploaded_file is None or not context_ready,
            help="只有点击后才会执行推理、保存记录和发送预警；普通页面刷新不会重复入库。",
            width="stretch",
        )

        if uploaded_file is None:
            st.info("先在左侧选择一张现场照片或示例，再确认开始检测。")
        elif not context_ready:
            st.warning("开始检测前，请先在左侧填写真实的项目名称和检查人。")
        elif not cache_matches and not start_image:
            st.info("现场照片与检查上下文已就绪，可以开始检测。")

    if start_image and uploaded_file is not None:
        try:
            with st.spinner("正在识别现场风险并保存证据..."):
                upload_dir = Path(__file__).parent / "data" / "uploads"
                upload_dir.mkdir(parents=True, exist_ok=True)
                image_path = upload_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
                with open(image_path, "wb") as f:
                    f.write(file_bytes)

                detector = get_current_detector()
                result = detector.detect(str(image_path))

                alert_engine = get_alert_engine()
                alerts = alert_engine.generate_alerts(result["detections"])
                result["alerts"] = alerts
                overall = alert_engine.get_overall_level(alerts) if alerts else None

                # 保存记录
                db = get_database()
                record_id = db.save_record(
                    result,
                    image_name=uploaded_file.name,
                    project_name=project_name,
                    inspector=inspector,
                    model_version=detector.model_version,
                )

                notification_result = {"status": "not_needed"}
                if alerts and not _HAS_DINGTALK:
                    notification_result = {"status": "unavailable"}

                # 发送钉钉预警（仅红色/黄色预警且未通知过）
                if _HAS_DINGTALK and alerts:
                    if '_notified_rids' not in st.session_state:
                        st.session_state['_notified_rids'] = set()
                    if record_id not in st.session_state['_notified_rids']:
                        st.session_state['_notified_rids'].add(record_id)
                        notification_result = _send_image_alert(
                            alerts, record_id, image_path, project_name, inspector,
                        )

                cached_detection = {
                    "fingerprint": file_fingerprint,
                    "image_path": str(image_path),
                    "result": result,
                    "record_id": record_id,
                    "overall": overall,
                    "project_name": project_name,
                    "inspector": inspector,
                    "model_version": detector.model_version,
                    "notification_result": notification_result,
                }
                st.session_state["_image_detection_cache"] = cached_detection
                cache_matches = True
        except Exception as exc:
            _LOG.exception("图片检测失败: %s", exc)
            st.error("本次图片检测未完成，文件未形成可用结论。请确认图片可正常打开后重试；若问题持续，请重启应用。")
            with st.expander("查看技术详情", expanded=False):
                st.code(f"{type(exc).__name__}: {exc}")
            st.stop()

    if cache_matches:
        image_path = cached_detection["image_path"]
        result = cached_detection["result"]
        record_id = cached_detection["record_id"]
        overall = cached_detection.get("overall")
        summary = result["summary"]
        risk_level = overall["level"] if overall else "blue"
        violation_total = int(summary.get("red_alerts", 0)) + int(summary.get("yellow_alerts", 0))

        st.markdown("### 检测结论")
        _render_risk_banner(
            risk_level,
            violation_total,
            overall.get("action") if overall else None,
        )
        risk_name, _, _ = _risk_meta(risk_level)
        _render_metric_strip([
            ("最高风险", risk_name),
            ("需处置目标", violation_total),
            ("检测目标", summary["total_detections"]),
        ])

        notification_result = cached_detection.get("notification_result") or {}
        notification_status = notification_result.get("status")
        if violation_total and notification_status == "sent":
            _render_system_notice(
                "风险通知已送达",
                f"本次预警已发送至 {notification_result.get('sent_count', 0)} 个接收群。",
                "healthy",
            )
        elif violation_total and notification_status in {"failed", "no_recipient", "unavailable"}:
            recovery = {
                "failed": "记录已保存，但通知发送失败；请在左侧检查群配置或网络后人工补报。",
                "no_recipient": "记录已保存，但当前没有启用的接收群；请人工补报并检查群配置。",
                "unavailable": "记录已保存，但通知模块当前不可用；请人工补报。",
            }[notification_status]
            _render_system_notice("风险通知未送达", recovery, "error")

        if violation_total:
            action_cols = st.columns([2, 1])
            with action_cols[0]:
                if st.button(
                    f"立即处置记录 #{record_id}",
                    type="primary",
                    key=f"open_image_incident_{record_id}",
                    width="stretch",
                ):
                    _request_incident_focus("image", record_id)
                    st.rerun()
            with action_cols[1]:
                if st.button("检测下一张", key=f"next_image_{record_id}", width="stretch"):
                    st.session_state.pop("_image_detection_cache", None)
                    st.session_state.pop("_selected_sample_path", None)
                    st.rerun()

        st.markdown("### 现场证据")
        col1, col2 = st.columns(2)
        with col1:
            st.image(str(image_path), caption="原始现场照片（供人工复核）", width="stretch")
        with col2:
            st.image(result["image"], caption="AI 标注结果（以文字结论和人工复核为准）", width="stretch")

        with st.expander("查看预警与检测明细", expanded=False):
            detail_cols = st.columns(5)
            detail_cols[0].metric("已戴安全帽", summary.get("helmet_count", 0))
            detail_cols[1].metric("未戴安全帽", summary.get("no_helmet_count", 0))
            detail_cols[2].metric("已穿反光衣", summary.get("vest_count", 0))
            detail_cols[3].metric("未穿反光衣", summary.get("no_vest_count", 0))
            detail_cols[4].metric("未戴口罩", summary.get("no_mask_count", 0))

            if result["alerts"]:
                st.markdown("#### 预警明细")
                alert_df = pd.DataFrame([{
                    "时间": a["timestamp"],
                    "等级": f"{a['level_name']}",
                    "隐患类型": a["hazard_type"],
                    "描述": a["description"],
                    "置信度": f"{a['confidence']*100:.0f}%",
                    "处理建议": a["action"],
                } for a in result["alerts"]])
                st.dataframe(alert_df, width="stretch", hide_index=True)

            if result["detections"]:
                st.markdown("#### 目标明细")
                det_df = pd.DataFrame([{
                    "检测目标": d["label"],
                    "置信度": f"{d['confidence']*100:.0f}%",
                    "预警等级": d["alert_name"],
                    "位置": f"({d['bbox'][0]},{d['bbox'][1]})-({d['bbox'][2]},{d['bbox'][3]})",
                } for d in result["detections"]])
                st.dataframe(det_df, width="stretch", hide_index=True)

        if violation_total:
            st.warning(f"记录 #{record_id} 已进入处置队列。原始证据保持不变，请尽快认领并跟踪关闭。")
        else:
            st.info(f"记录 #{record_id} 已归档，本次未发现需要处置的违规目标。")
        st.caption(
            f"检测时项目：{cached_detection.get('project_name') or '未填写'} · "
            f"检查人：{cached_detection.get('inspector') or '未填写'} · "
            f"模型：{cached_detection.get('model_version') or '未记录'}"
        )


# ========== 页面2: 检测记录 ==========
elif page == "检测记录":
    _render_page_header(
        "检测记录",
        "以风险、责任人和整改期限组织全部证据，逐项完成认领、复核与关闭。",
        "隐患处置队列",
    )
    db = get_database()
    workflow_stats = db.get_incident_statistics()
    _render_workspace_status(project_name, inspector, active_detector, workflow_stats)
    _render_metric_strip([
        ("待处理", workflow_stats["pending"]),
        ("处理中", workflow_stats["in_progress"]),
        ("已超期", workflow_stats["overdue"]),
        ("已关闭", workflow_stats["closed"]),
    ])
    if st.session_state.pop("incident_saved", None):
        st.success("处置详情已保存。原始检测记录保持不变。")

    status_options = ["all", "pending", "in_progress", "closed", "false_positive", "not_applicable"]
    status_labels = {"all": "全部状态", **INCIDENT_STATUS_CN}
    risk_labels = {"all": "全部风险", "red": "红色风险", "yellow": "黄色风险", "blue": "无违规/蓝色"}
    time_labels = {"all": "全部时间", "today": "今天", "7d": "近 7 天", "30d": "近 30 天"}

    def _next_action(record):
        status = record.get("incident_status", "pending")
        if status == "closed":
            return "已完成复核"
        if status == "false_positive":
            return "误报已归档"
        if status == "in_progress":
            return "跟踪整改并复核"
        if status == "not_applicable":
            return "留档"
        return _risk_meta(_record_risk(record))[1]

    def _queue_action(record):
        status = record.get("incident_status", "pending")
        if status == "closed":
            return "复核完成"
        if status == "false_positive":
            return "误报归档"
        if status == "in_progress":
            return "跟踪复核"
        if status == "not_applicable":
            return "留档"
        return "立即核查" if _record_risk(record) == "red" else "限时复核"

    def _queue_filters(records, key_prefix):
        quick_labels = {
            "open": "全部待办",
            "in_progress": "处理中",
            "mine": "待我处理",
            "unassigned": "未分配",
            "red": "红色待办",
            "overdue": "已超期",
            "all": "全部记录",
        }
        requested_queue_view = st.session_state.pop("_requested_queue_view", None)
        quick_key = f"{key_prefix}_quick"
        if requested_queue_view in quick_labels:
            st.session_state[quick_key] = requested_queue_view
        quick_view = st.radio(
            "快捷视图",
            list(quick_labels),
            format_func=quick_labels.get,
            horizontal=True,
            key=quick_key,
        )
        keyword = st.text_input(
            "搜索记录", placeholder="输入记录 ID、项目、检查人或文件名",
            key=f"{key_prefix}_keyword",
        ).strip().lower()
        projects = sorted({(r.get("project_name") or "未填写项目") for r in records})
        with st.expander("更多筛选", expanded=False):
            cols = st.columns(5)
            with cols[0]:
                risk_filter = st.selectbox(
                    "风险等级", list(risk_labels), format_func=risk_labels.get,
                    key=f"{key_prefix}_risk",
                )
            with cols[1]:
                status_filter = st.selectbox(
                    "处置状态", status_options, format_func=status_labels.get,
                    key=f"{key_prefix}_status",
                )
            with cols[2]:
                source_filter = st.selectbox(
                    "证据来源", ["全部来源", "图片检测", "实时检测"],
                    key=f"{key_prefix}_source",
                )
            with cols[3]:
                project_filter = st.selectbox(
                    "项目", ["全部项目", *projects], key=f"{key_prefix}_project",
                )
            with cols[4]:
                time_filter = st.selectbox(
                    "时间范围", list(time_labels), format_func=time_labels.get,
                    key=f"{key_prefix}_time",
                )

        cutoff = None
        if time_filter == "today":
            cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_filter == "7d":
            cutoff = datetime.now() - timedelta(days=7)
        elif time_filter == "30d":
            cutoff = datetime.now() - timedelta(days=30)

        filtered = []
        for record in records:
            if not _queue_matches_quick_view(record, quick_view, inspector):
                continue
            project_value = record.get("project_name") or "未填写项目"
            if risk_filter != "all" and _record_risk(record) != risk_filter:
                continue
            if status_filter != "all" and record.get("incident_status") != status_filter:
                continue
            if source_filter != "全部来源" and record.get("_source_label") != source_filter:
                continue
            if project_filter != "全部项目" and project_value != project_filter:
                continue
            if cutoff:
                try:
                    record_time = datetime.strptime(record.get("timestamp", ""), "%Y-%m-%d %H:%M:%S")
                except (TypeError, ValueError):
                    record_time = datetime.min
                if record_time < cutoff:
                    continue
            haystack = " ".join(str(record.get(field, "")) for field in (
                "id", "project_name", "inspector", "image_name", "violation_type",
            )).lower()
            if keyword and keyword not in haystack:
                continue
            filtered.append(record)
        filtered.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        filtered.sort(key=lambda r: 0 if _record_is_overdue(r) else 1)
        filtered = sorted(filtered, key=lambda r: _risk_meta(_record_risk(r))[2])
        focus_source = st.session_state.get("_incident_focus_source")
        focus_id = st.session_state.get("_incident_focus_id")
        if focus_source and focus_id is not None:
            filtered.sort(
                key=lambda record: 0
                if record.get("_source_type") == focus_source
                and int(record.get("id") or 0) == int(focus_id)
                else 1
            )
        return filtered

    def _render_incident_editor(record, source_type):
        status = record.get("incident_status", "pending")
        if status == "not_applicable":
            st.info("该记录未发现违规，无需创建处置任务。")
            return

        st.markdown("#### 处置详情")
        st.caption("这里保存的是当前处置状态，不会修改 AI 检测事实。关闭和误报必须填写复核人及说明。")
        status_values = ["pending", "in_progress", "closed", "false_positive"]
        default_due = datetime.now().date() + timedelta(days=1)
        if record.get("due_at"):
            try:
                default_due = datetime.strptime(record["due_at"], "%Y-%m-%d %H:%M:%S").date()
            except (TypeError, ValueError):
                pass
        with st.form(f"incident_{source_type}_{record['id']}"):
            form_cols = st.columns(2)
            with form_cols[0]:
                new_status = st.selectbox(
                    "处置状态",
                    status_values,
                    index=status_values.index(status) if status in status_values else 0,
                    format_func=INCIDENT_STATUS_CN.get,
                )
                assignee = st.text_input(
                    "负责人",
                    value=record.get("assignee") or inspector,
                    placeholder="填写整改负责人",
                )
            with form_cols[1]:
                use_due = st.checkbox("设置整改期限", value=bool(record.get("due_at")))
                due_date = st.date_input("截止日期", value=default_due, disabled=not use_due)
                operator = st.text_input(
                    "本次复核人",
                    value=record.get("closed_by") or inspector,
                    placeholder="关闭或误报时必填",
                )
            note = st.text_area(
                "处置说明",
                value=record.get("resolution_note") or "",
                placeholder="记录整改结果、复核依据；关闭或误报时必填",
            )
            submitted = st.form_submit_button("保存处置详情", type="primary", width="stretch")

        if submitted:
            if new_status == "in_progress" and not assignee.strip():
                st.error("进入“处理中”前，请填写负责人。")
                return
            try:
                db.update_incident_workflow(
                    source_type,
                    int(record["id"]),
                    status=new_status,
                    assignee=assignee,
                    due_at=f"{due_date:%Y-%m-%d} 23:59:59" if use_due else None,
                    resolution_note=note,
                    operator=operator,
                )
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                _LOG.exception("保存处置详情失败: %s", exc)
                st.error("处置详情未保存，请稍后重试。检测记录未受影响。")
                with st.expander("查看技术详情", expanded=False):
                    st.code(f"{type(exc).__name__}: {exc}")
            else:
                st.session_state["incident_saved"] = True
                st.rerun()

    type_cn = {"no-helmet": "未戴安全帽", "no-vest": "未穿反光衣", "no-mask": "未戴口罩"}
    image_records = db.get_image_incident_queue(history_limit=200)
    realtime_records = db.get_realtime_incident_queue(history_limit=200)
    combined_records = []
    for record in image_records:
        item = dict(record)
        item["_source_type"] = "image"
        item["_source_label"] = "图片检测"
        combined_records.append(item)
    for record in realtime_records:
        item = dict(record)
        item["_source_type"] = "realtime"
        item["_source_label"] = "实时检测"
        combined_records.append(item)

    if combined_records:
        filtered = _queue_filters(combined_records, "incident_queue")
        st.markdown(
            f'<p class="queue-note">当前视图显示 {len(filtered)} 条；开放事项全部可达，红色与超期事项优先。</p>',
            unsafe_allow_html=True,
        )
        if filtered:
            queue_rows = []
            for record in filtered:
                status_name = INCIDENT_STATUS_CN.get(record.get("incident_status"), "待复核")
                if _record_is_overdue(record):
                    status_name += "（已超期）"
                queue_rows.append({
                    "风险": _risk_meta(_record_risk(record))[0],
                    "状态": status_name,
                    "时间": record.get("timestamp"),
                    "来源": record.get("_source_label"),
                    "项目": record.get("project_name") or "未填写",
                    "负责人": record.get("assignee") or "未分配",
                    "期限": record.get("due_at") or "未设置",
                })

            focus_source = st.session_state.get("_incident_focus_source")
            focus_id = st.session_state.get("_incident_focus_id")
            focused_index = next(
                (
                    index for index, record in enumerate(filtered)
                    if record.get("_source_type") == focus_source
                    and focus_id is not None
                    and int(record["id"]) == int(focus_id)
                ),
                0,
            )

            queue_col, detail_col = st.columns([5, 7], vertical_alignment="top")
            with queue_col:
                st.markdown("### 风险队列")
                st.caption("单击一行，在右侧查看证据并完成处置。")
                table_event = st.dataframe(
                    pd.DataFrame(queue_rows),
                    width="stretch",
                    hide_index=True,
                    height=480,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="incident_queue_table",
                )
            selected_index = focused_index
            if not focus_source:
                selection = getattr(table_event, "selection", None)
                selected_rows = list(getattr(selection, "rows", []) or [])
                if selected_rows and 0 <= int(selected_rows[0]) < len(filtered):
                    selected_index = int(selected_rows[0])
            selected = filtered[selected_index]
            if (
                focus_source == selected["_source_type"]
                and focus_id is not None
                and int(focus_id) == int(selected["id"])
            ):
                st.session_state.pop("_incident_focus_source", None)
                st.session_state.pop("_incident_focus_id", None)

            with detail_col:
                st.markdown("### 证据与处置")
                risk_count = (
                    int(selected.get("red_alerts") or 0) + int(selected.get("yellow_alerts") or 0)
                    if selected["_source_type"] == "image"
                    else int(selected.get("violation_count") or 0)
                )
                _render_risk_banner(_record_risk(selected), risk_count, _next_action(selected))
                _render_status_rail([
                    ("记录编号", f"#{selected['id']}", selected["_source_label"]),
                    ("处置状态", INCIDENT_STATUS_CN.get(selected.get("incident_status"), "待复核"), _queue_action(selected)),
                    ("项目", selected.get("project_name") or "未填写", selected.get("inspector") or "检查人未填写"),
                ])
                if selected["_source_type"] == "image":
                    result_path = selected.get("result_image_path")
                    if isinstance(result_path, str) and result_path and os.path.exists(result_path):
                        st.image(result_path, caption="AI 标注结果（历史记录未保存原图完整路径）", width="stretch")
                    else:
                        st.warning("标注图片已移动或删除，结构化检测记录仍保留。")
                    with st.expander("查看结构化检测证据", expanded=False):
                        alerts_data = [
                            {key: value for key, value in item.items() if key != "icon"}
                            for item in _safe_json_list(selected.get("alerts_json"))
                            if isinstance(item, dict)
                        ]
                        detections_data = _safe_json_list(selected.get("detections_json"))
                        st.markdown("**预警信息**")
                        st.dataframe(pd.DataFrame(alerts_data), width="stretch", hide_index=True) if alerts_data else st.caption("无预警明细")
                        st.markdown("**检测目标**")
                        st.dataframe(pd.DataFrame(detections_data), width="stretch", hide_index=True) if detections_data else st.caption("无检测目标明细")
                else:
                    snapshot_path = selected.get("snapshot_path")
                    if snapshot_path and os.path.exists(snapshot_path):
                        st.image(snapshot_path, caption="实时违规抓拍（供人工复核）", width="stretch")
                    else:
                        st.warning("抓拍文件已移动或删除，违规记录仍保留。")
                    st.caption(f"违规类型：{type_cn.get(selected.get('violation_type'), selected.get('violation_type') or '未记录')} · 模型：{selected.get('model_version') or '未记录'}")
                _render_incident_editor(selected, selected["_source_type"])
        else:
            st.info("没有符合当前视图与筛选条件的记录。")
    else:
        st.info("暂无检测记录。完成图片检测或实时值守后，风险证据会进入这里。")


# ========== 页面3: 统计分析 ==========
elif page == "统计分析":
    _render_page_header(
        "统计分析",
        "从处置积压、近期风险与图片检测质量三个角度复盘当前安全态势。",
        "值守复盘",
    )

    db = get_database()
    stats = db.get_statistics()
    workflow_stats = db.get_incident_statistics() if hasattr(db, "get_incident_statistics") else {
        "pending": 0, "in_progress": 0, "closed": 0, "overdue": 0,
    }
    _render_workspace_status(project_name, inspector, active_detector, workflow_stats)

    st.markdown("### 处置进度")
    _render_metric_strip([
        ("待处理", workflow_stats["pending"]),
        ("处理中", workflow_stats["in_progress"]),
        ("已超期", workflow_stats["overdue"]),
        ("已关闭", workflow_stats["closed"]),
    ])
    queue_actions = st.columns(4)
    for column, label, quick_view in zip(
        queue_actions,
        ("查看全部待办", "查看处理中", "查看已超期", "查看全部记录"),
        ("open", "in_progress", "overdue", "all"),
    ):
        with column:
            if st.button(label, key=f"stats_queue_{quick_view}_{label}", width="stretch"):
                _request_queue_view(quick_view)
                st.rerun()

    st.markdown("### 检测概览")
    _render_metric_strip([
        ("总检测次数", stats["total_checks"]),
        ("违规次数", stats["violation_count"]),
        ("图片检测合规率", f"{stats['compliance_rate']}%"),
        ("未戴安全帽总人次", stats["no_helmet_total"]),
    ])
    st.caption("合规率仅基于图片检测记录，不包含实时抓拍和视频逐帧结果。")

    issue_rows = [
        {"隐患类型": "未戴安全帽", "检测人次": int(stats.get("no_helmet_total", 0))},
        {"隐患类型": "未穿反光衣", "检测人次": int(stats.get("no_vest_total", 0))},
    ]
    if any(row["检测人次"] for row in issue_rows):
        st.markdown("### 主要隐患分布")
        issue_fig = px.bar(
            pd.DataFrame(issue_rows),
            x="检测人次",
            y="隐患类型",
            orientation="h",
            color="隐患类型",
            text="检测人次",
            color_discrete_map={"未戴安全帽": "#FF626C", "未穿反光衣": "#F4C95D"},
        )
        issue_fig.update_layout(
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "#DCE6F2"},
            margin={"l": 12, "r": 12, "t": 12, "b": 12},
        )
        issue_fig.update_xaxes(gridcolor="rgba(169,183,202,.16)", rangemode="tozero")
        issue_fig.update_yaxes(showgrid=False)
        st.plotly_chart(issue_fig, width="stretch", config={"displayModeBar": False})
        st.caption("按图片检测目标人次统计，同一人员在不同照片中可能重复计数。")

    # 每日趋势
    daily = db.get_daily_stats(days=7)
    if daily:
        st.markdown("### 近 7 天检测趋势")
        df_daily = pd.DataFrame(daily).rename(columns={
            "date": "日期", "checks": "检测次数", "violations": "违规次数",
        })
        fig = px.bar(
            df_daily,
            x="日期",
            y=["检测次数", "违规次数"],
            labels={"value": "次数", "variable": "类型"},
            color_discrete_map={"检测次数": "#4F8CFF", "违规次数": "#FF5D68"},
            barmode="group",
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "#DCE6F2"},
            legend_title_text="",
            margin={"l": 12, "r": 12, "t": 24, "b": 12},
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(gridcolor="rgba(169,183,202,.16)")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    else:
        st.info("暂无检测数据。完成一次图片检测后，这里会显示趋势。")


# ========== 页面: 实时检测 ==========
elif page == "实时检测":
    _render_page_header(
        "实时视频检测",
        "以摄像头画面为中心持续值守，风险事件自动抓拍入库并进入处置队列。",
        "实时值守",
    )
    _render_workspace_status(project_name, inspector, active_detector, sidebar_workflow_stats)
    context_ready = bool(project_name.strip() and inspector.strip())
    if not context_ready:
        st.warning("启动实时值守前，请先在左侧填写真实的项目名称和检查人。")
        _render_system_notice(
            "实时值守尚未启动",
            "补全项目名称和检查人后，摄像头入口才会开放，避免生成无法追溯的证据。",
        )
        st.stop()
    st.caption("浏览器首次使用时需要允许摄像头权限；停止后不会继续采集画面。")

    # 局部导入(WebRTC 相关,仅此页使用)
    import av
    import time
    from streamlit_webrtc import webrtc_streamer

    # ----- 控制面板 -----
    col2, col1 = st.columns([8, 4], vertical_alignment="top")
    with col1:
        st.markdown("### 值守命令")
        snap_ctl = _snapshot_rt_stats()
        _render_metric_strip([
            ("本次会话累计违规", snap_ctl.get("violations", 0)),
            ("已存记录", snap_ctl.get("realtime_record_count", 0)),
        ])
        notification_text, _ = _notification_overview()
        st.caption(f"风险通知：{notification_text}")
        with st.expander("高级设置", expanded=False):
            conf = st.slider("置信度阈值", 0.2, 0.8, 0.4, 0.05)
            detect_interval = st.slider("检测间隔（帧）", 1, 5, DETECT_INTERVAL_DEFAULT, 1, help="每 N 帧检测一次；数值越小，计算占用越高。")
            auto_refresh = st.checkbox(
                "自动刷新统计",
                value=True,
                help="关闭后保留当前数值，可减少值守时的界面变化。",
            )
            st.divider()
            if st.button("重置本次统计", help="清空本次会话累计统计，从 0 重新计数"):
                _reset_rt_stats()
                st.rerun()
            if snap_ctl.get("recording"):
                if st.button("停止录制", type="primary"):
                    rt = get_rt_stats()
                    with rt["lock"]:
                        rt["recording"] = False
                    st.rerun()
            elif st.button("开始录制"):
                rec_dir = Path(__file__).parent / "data" / "uploads" / "recordings"
                rec_dir.mkdir(parents=True, exist_ok=True)
                rec_path = rec_dir / f"rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                rt = get_rt_stats()
                with rt["lock"]:
                    rt["recording"] = True
                    rt["rec_path"] = str(rec_path)
                    rt["recorder"] = None
                    rt["rec_start"] = time.time()
                    rt["last_recording_path"] = None
                st.rerun()

    # ----- 检测器与设备 -----
    detector = get_current_detector()
    device = select_compute_device()

    # ----- 获取跨 rerun 持久化的统计对象(st.cache_resource 确保全局唯一) -----
    rt_stats = get_rt_stats()
    # 主线程把侧边栏的项目/检查人同步到 rt_stats,供回调线程读取(回调无 ScriptRunContext)
    with rt_stats["lock"]:
        rt_stats["project_name"] = project_name
        rt_stats["inspector"] = inspector
        rt_stats["detect_interval"] = detect_interval
    # 预热 Database 实例并存引用: 回调线程不能调 @st.cache_resource(无 ScriptRunContext 会抛异常)
    rt_stats["db"] = get_database()

    # ----- 帧处理回调(WebRTC 在独立线程异步调用,不能访问 st.session_state) -----
    def video_frame_callback(frame):
        img = frame.to_ndarray(format="bgr24")
        try:
            now = time.time()
            frame_counts = {}
            frame_violations = []  # [(vtype, track_id, cx, cy)]
            # 跳帧判断(任务#12): 每 detect_interval 帧才检测一次
            with rt_stats["lock"]:
                rt_stats["frames"] += 1
                fc = rt_stats["frames"]
                interval = rt_stats.get("detect_interval", DETECT_INTERVAL_DEFAULT)
            do_detect = (fc % interval == 0)
            if do_detect:
                # 检测帧: 跑 track(任务#11: persist=True 跨帧保持 track_id)
                results = detector.model.track(img, persist=True, tracker="bytetrack.yaml",
                                                conf=conf, device=device, verbose=False, iou=0.5)
                annotated = img.copy()  # 不用 plot()(英文标签),改 _draw_boxes 画中文,与跳帧一致避免闪烁
                last_boxes = []
                has_helmet_violation = False
                if results[0].boxes is not None and results[0].boxes.id is not None:
                    for b in results[0].boxes:
                        cls_id = int(b.cls[0])
                        conf_val = float(b.conf[0])
                        raw_name = detector.model.names[cls_id]
                        label_en = detector._map_label(raw_name)
                        x1, y1, x2, y2 = b.xyxy[0].tolist()
                        tid = int(b.id[0]) if b.id is not None else None
                        last_boxes.append((int(x1), int(y1), int(x2), int(y2), cls_id, conf_val, tid))
                        frame_counts[label_en] = frame_counts.get(label_en, 0) + 1
                        if label_en == "no-helmet":
                            has_helmet_violation = True
                        if label_en in ("no-helmet", "no-vest", "no-mask"):
                            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                            frame_violations.append((label_en, tid, cx, cy, int(x1), int(y1), int(x2), int(y2)))
                _draw_boxes(annotated, last_boxes, detector)  # 画中文框(与跳帧一致)
                # 缓存 last_boxes + has_violation(供跳帧重画用)
                with rt_stats["lock"]:
                    rt_stats["last_boxes"] = last_boxes
                    rt_stats["last_has_violation"] = has_helmet_violation
                # 红边框(任务#4): 检测帧画
                if has_helmet_violation:
                    h, w = annotated.shape[:2]
                    cv2.rectangle(annotated, (0, 0), (w-1, h-1), (0, 0, 255), 8)
            else:
                # 跳帧(任务#12): 用缓存 boxes 重画,框不消失
                with rt_stats["lock"]:
                    last_boxes = rt_stats.get("last_boxes", [])
                    has_helmet_violation = rt_stats.get("last_has_violation", False)
                annotated = img.copy()
                _draw_boxes(annotated, last_boxes, detector)
                if has_helmet_violation:
                    h, w = annotated.shape[:2]
                    cv2.rectangle(annotated, (0, 0), (w-1, h-1), (0, 0, 255), 8)
            # 锁内: 统计 + 去重判断(任务#11: track_id 去重 + 位置兜底)
            to_record = []
            with rt_stats["lock"]:
                if do_detect:
                    for label_en, cnt in frame_counts.items():
                        rt_stats["classes"][label_en] = rt_stats["classes"].get(label_en, 0) + cnt
                    for vtype, tid, cx, cy, bx1, by1, bx2, by2 in frame_violations:
                        # 任务#11: track_id 去重(主) — 已记录目标不再统计/入库
                        key = f"{tid}:{vtype}" if tid is not None else None
                        if key and key in rt_stats["recorded_tracks"]:
                            continue
                        # 位置兜底(辅): 同区域 N 秒内同类型,防 track 跳变误判
                        pos_list = rt_stats["pos_dedupe"].setdefault(vtype, [])
                        pos_list[:] = [(x, y, exp) for (x, y, exp) in pos_list if exp > now]
                        if any((cx - x) ** 2 + (cy - y) ** 2 < POS_DEDUPE_RADIUS ** 2 for (x, y, exp) in pos_list):
                            continue
                        # 通过去重后才统计违规(避免同一人反复计数) + 入库
                        rt_stats["violations"] += 1
                        rt_stats["violation_classes"][vtype] = rt_stats["violation_classes"].get(vtype, 0) + 1
                        if key:
                            rt_stats["recorded_tracks"].add(key)
                        pos_list.append((cx, cy, now + POS_DEDUPE_TIME))
                        level = detector.ALERT_LEVELS.get(vtype, ("blue",))[0]
                        to_record.append((vtype, 1, level, bx1, by1, bx2, by2))
                        rt_stats["dingtalk_pending_counts"][vtype] = rt_stats["dingtalk_pending_counts"].get(vtype, 0) + 1
                        # 红色告警(任务#4): no-helmet 节流触发
                        if vtype == "no-helmet" and now - rt_stats.get("red_alert_time", 0) >= RED_ALERT_COOLDOWN:
                            rt_stats["red_alert_time"] = now
                            rt_stats["red_alert_played"] = False
                rt_stats["last_error"] = None
            # 锁外: 入库 + 抓拍(任务#3/#5)
            proj = rt_stats.get("project_name", "")
            insp = rt_stats.get("inspector", "")
            if to_record:
                _LOG.info("to_record=%d items, annotated.shape=%s", len(to_record), annotated.shape)
                db = rt_stats.get("db")
                snap_dir = Path(__file__).parent / "data" / "uploads" / "snapshots"
                snap_dir.mkdir(parents=True, exist_ok=True)
                for vtype, vcount, vlevel, bx1, by1, bx2, by2 in to_record:
                    try:
                        snap_path = snap_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{vtype}.jpg"
                        cv2.imwrite(str(snap_path), annotated)
                        # 裁剪违规区域(带边距),用于钉钉推送
                        PAD = 120
                        h_img, w_img = annotated.shape[:2]
                        cropped = annotated[max(0, by1 - PAD):min(h_img, by2 + PAD),
                                            max(0, bx1 - PAD):min(w_img, bx2 + PAD)]
                        crop_path = snap_dir / f"crop_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{vtype}.jpg"
                        cv2.imwrite(str(crop_path), cropped)
                        _LOG.info("crop saved: %s (%dx%d)", crop_path.name, cropped.shape[1], cropped.shape[0])
                        with rt_stats["lock"]:
                            rt_stats["dingtalk_crop_path"] = str(crop_path)
                        _save_realtime_incident(
                            db,
                            rt_stats,
                            violation_type=vtype,
                            violation_count=vcount,
                            level=vlevel,
                            snapshot_path=str(snap_path),
                            project_name=proj,
                            inspector=insp,
                            model_version=detector.model_version,
                        )
                    except Exception as e:
                        with rt_stats["lock"]:
                            rt_stats["last_error"] = f"入库/抓拍失败 {vtype}: {e}"
            if _HAS_DINGTALK:
                _send_realtime_violations(rt_stats, proj, insp)
        except Exception as e:
            annotated = img
            with rt_stats["lock"]:
                rt_stats["last_error"] = f"{type(e).__name__}: {e}"
        # 录制(任务#9, Bug#4-6): 锁内读标志,锁外操作 recorder + 清理无效文件
        with rt_stats["lock"]:
            is_recording = rt_stats.get("recording", False)
            rec_path = rt_stats.get("rec_path")
        if is_recording:
            rec = rt_stats.get("recorder")
            if rec is None and rec_path:
                h, w = annotated.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                rec = cv2.VideoWriter(rec_path, fourcc, 15.0, (w, h))
                rt_stats["recorder"] = rec
            if rec is not None:
                rec.write(annotated)
        else:
            rec = rt_stats.get("recorder")
            rec_path_snap = rt_stats.get("rec_path")
            if rec is not None:
                rec.release()
            valid = False
            if rec is not None and rec_path_snap and os.path.exists(rec_path_snap):
                if os.path.getsize(rec_path_snap) >= 1024:
                    valid = True
                else:
                    try:
                        os.remove(rec_path_snap)
                    except OSError:
                        pass
            with rt_stats["lock"]:
                rt_stats["last_recording_path"] = rec_path_snap if valid else None
                rt_stats["rec_path"] = None
                rt_stats["recorder"] = None
        return av.VideoFrame.from_ndarray(annotated, format="bgr24")

    # ----- WebRTC 实时流(浏览器原生推流,UI 不阻塞) -----
    with col2:
        ctx = webrtc_streamer(
            key="ppe-realtime",
            video_frame_callback=video_frame_callback,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
            translations={
                "start": "启动摄像头",
                "stop": "停止摄像头",
                "select_device": "选择摄像头",
                "media_api_not_available": "当前浏览器不支持摄像头访问，请使用最新版 Chrome 或 Edge。",
                "device_ask_permission": "请允许浏览器访问摄像头。",
                "device_not_available": "未找到可用摄像头，请检查连接后重试。",
                "device_access_denied": "摄像头权限被拒绝，请在浏览器地址栏中允许后重试。",
                "turn_camera_on": "打开摄像头",
                "turn_camera_off": "关闭摄像头",
                "mute_microphone": "静音",
                "unmute_microphone": "取消静音",
            },
            rtc_configuration={
                "iceServers": [
                    {"urls": ["stun:stun.l.google.com:19302"]},
                    {"urls": ["stun:stun.qq.com:3478"]},
                ]
            },
        )

    # ----- 统计面板(fragment 每0.5s局部刷新,避免全页rerun打断WebRTC画面/滑块交互) -----
    @st.fragment(run_every=0.5 if auto_refresh else None)
    def _render_rt_stats():
        snap = _snapshot_rt_stats()
        camera_playing = bool(getattr(ctx.state, "playing", False))
        presentation = _realtime_ui_state(snap, camera_playing)
        _render_system_notice(*presentation["monitor"])
        if presentation["system"]:
            _render_system_notice(*presentation["system"])
        risk_level, risk_count, risk_action = presentation["risk"]
        _render_risk_banner(risk_level, risk_count, risk_action)

        latest_record_id = snap.get("last_realtime_record_id")
        if latest_record_id and st.button(
            f"处置最新记录 #{latest_record_id}",
            type="primary",
            key=f"open_realtime_incident_{latest_record_id}",
            width="stretch",
        ):
            _request_incident_focus("realtime", latest_record_id)
            st.rerun()

        retry_count = int(snap.get("dingtalk_retry_count") or 0)
        if retry_count:
            retry_at = float(snap.get("dingtalk_retry_at") or 0.0)
            wait_seconds = max(0, int(retry_at - time.time()))
            _render_system_notice(
                "风险通知等待重试",
                f"已失败 {retry_count} 次，约 {wait_seconds} 秒后自动重试；记录与抓拍已保留。",
                "error",
            )
        elif snap.get("dingtalk_sending"):
            _render_system_notice("正在发送风险通知", "记录与抓拍已保留，请稍候查看送达结果。")
        elif snap.get("dingtalk_pending_counts"):
            pending_total = sum(int(value) for value in snap["dingtalk_pending_counts"].values())
            _render_system_notice(
                "风险通知待汇总",
                f"已保留 {pending_total} 条待发送风险，达到发送窗口后自动通知。",
            )

        # 红色告警(任务#4): 弹窗+声音,仅 DISPLAY 秒内显示,声音每条告警只播一次
        red_t = snap.get("red_alert_time", 0.0)
        if red_t and (time.time() - red_t < RED_ALERT_DISPLAY):
            st.error("红色风险：检测到未戴安全帽。请立即停止相关作业并现场核查。")
            if not snap.get("red_alert_played", True):
                _play_alert_sound()
                rt = get_rt_stats()
                with rt["lock"]:
                    rt["red_alert_played"] = True
        # 录制状态(任务#9)
        if snap.get("recording"):
            elapsed = int(time.time() - snap.get("rec_start", time.time()))
            _render_system_notice("正在录制", f"已持续 {elapsed} 秒，停止后文件保存在本机。", "healthy")
        else:
            last_rec = snap.get("last_recording_path")
            if last_rec and os.path.exists(last_rec):
                st.success(f"录制已保存：{os.path.basename(last_rec)}")
                st.video(last_rec)

        technical_error = snap.get("last_storage_error") or snap.get("last_error")
        if technical_error:
            with st.expander("查看技术详情", expanded=False):
                st.code(str(technical_error))


    with col2:
        _render_rt_stats()


# ========== 页面: 视频检测 ==========
elif page == "视频检测":
    _render_page_header(
        "视频文件检测",
        "对本地视频逐帧分析并生成标注结果，用于离线复核和演示。",
        "离线分析",
    )
    _render_workspace_status(project_name, inspector, active_detector, sidebar_workflow_stats)
    st.info("当前仅生成标注视频，不创建检测记录、不进入隐患处置队列，也不发送钉钉通知。逐帧累计次数可能包含同一人员在多帧中的重复检测。")

    upload_col, command_col = st.columns([7, 5], vertical_alignment="top")
    with upload_col:
        uploaded_video = st.file_uploader("选择视频文件", type=["mp4", "avi", "mov"])
        if uploaded_video is not None:
            size_mb = len(uploaded_video.getbuffer()) / 1024 / 1024
            _render_status_rail([
                ("文件", uploaded_video.name, "本机临时保存"),
                ("大小", f"{size_mb:.1f} MB", "支持 MP4、AVI、MOV"),
            ])
    with command_col:
        st.markdown("### 分析命令")
        conf = 0.4
        with st.expander("高级设置", expanded=False):
            conf = st.slider("置信度阈值", 0.2, 0.8, 0.4, 0.05)
        start_video = st.button(
            "开始视频检测",
            type="primary",
            disabled=uploaded_video is None,
            help="上传文件后由你确认开始，避免选择文件后立即占用计算资源。",
            width="stretch",
        )

    if uploaded_video is None:
        st.info("请选择 MP4、AVI 或 MOV 文件；文件只保存在本机运行目录。")
    elif start_video:
        video_dir = Path(__file__).parent / "data" / "uploads"
        video_dir.mkdir(parents=True, exist_ok=True)
        video_path = video_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_video.name}"
        with open(video_path, "wb") as f:
            f.write(uploaded_video.getbuffer())

        st.info(f"已开始处理：{uploaded_video.name}。请保持本页打开。")

        detector = get_current_detector()
        device = select_compute_device()
        cap = cv2.VideoCapture(str(video_path))
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 25
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        output_path = video_dir / f"result_{uploaded_video.name}"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

        progress = st.progress(0)
        status = st.empty()
        frame_count = 0
        total_detections = 0
        class_total = {}

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            results = detector.model(frame, conf=conf, device=device, verbose=False, iou=0.5)
            annotated = results[0].plot()
            out.write(annotated)
            total_detections += len(results[0].boxes)
            for b in results[0].boxes:
                c = detector.model.names[int(b.cls[0])]
                class_total[c] = class_total.get(c, 0) + 1
            if frame_count % 10 == 0 or frame_count == total:
                progress.progress(min(frame_count / total, 1.0) if total else 0)
                status.markdown(f"已处理 {frame_count}/{total} 帧 | 逐帧累计检测 {total_detections} 次")

        cap.release()
        out.release()
        progress.progress(1.0)
        st.success(f"视频检测完成：共处理 {frame_count} 帧，逐帧累计检测 {total_detections} 次（同一目标可能重复）。")

        # 转码为H.264(浏览器兼容)
        import imageio_ffmpeg
        import subprocess as sp
        h264_path = str(video_dir / f"h264_{uploaded_video.name}")
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        with st.spinner("正在转码为浏览器兼容格式(H.264)..."):
            sp.run([ffmpeg_exe, '-i', str(output_path), '-c:v', 'libx264',
                    '-preset', 'fast', '-pix_fmt', 'yuv420p', h264_path, '-y'],
                   capture_output=True)

        st.markdown("### 逐帧检测统计")
        st.caption("以下是各帧检测次数的累计，不代表独立人员或独立隐患事件数量。")
        if class_total:
            stat_str = " · ".join(
                f"{detector.LABEL_CN.get(detector._map_label(k), k)}：{v}"
                for k, v in sorted(class_total.items(), key=lambda x: -x[1])
            )
            st.markdown(stat_str)

        st.markdown("### 检测结果视频")
        if os.path.exists(h264_path):
            st.video(h264_path)
        else:
            st.video(str(output_path))
