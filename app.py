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
import cv2
import numpy as np
from PIL import Image as PILImage, ImageDraw, ImageFont

_FONT_PATH = r'C:\Windows\Fonts\msyh.ttc'
import torch
import threading
from pathlib import Path
from datetime import datetime
import pandas as pd
import plotly.express as px
from PIL import Image

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from detector import HazardDetector
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
        # --- 实时违规入库(任务#3) ---
        "last_alert_time": {},          # 各违规类型上次入库时间戳,用于节流
        "realtime_record_count": 0,     # 累计入库违规事件数
        "project_name": "示范项目",      # 主线程写入,回调线程读取(回调无 ScriptRunContext 拿不到侧边栏)
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
        rt["last_alert_time"] = {}
        rt["realtime_record_count"] = 0
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
            "realtime_record_count": rt.get("realtime_record_count", 0),
            "red_alert_time": rt.get("red_alert_time", 0.0),
            "red_alert_played": rt.get("red_alert_played", True),
            "recording": rt.get("recording", False),
            "rec_start": rt.get("rec_start", 0.0),
            "last_recording_path": rt.get("last_recording_path"),
            "detect_interval": rt.get("detect_interval", DETECT_INTERVAL_DEFAULT),
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
        send_text('\n'.join(lines))
    except Exception as e:
        st.caption('钉钉通知发送失败: ' + str(e))


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
    page_icon="🏗️",
    layout="wide",
)

# 隐藏右上角 Deploy 按钮(Streamlit Community Cloud 部署入口,参赛项目不需要)
# CSS 类名因 streamlit 版本而异,用多选择器覆盖(.stAppDeployButton 1.40+, .stDeployButton 旧版)
st.markdown(
    """
    <style>
    .stAppDeployButton, .stDeployButton, [data-testid="stHeaderActionElements"] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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


def _render_dingtalk_group_toggles():
    """侧边栏钉钉群白名单开关：勾选=启用推送，取消=停用（机器人无需退群），实时写入本地配置。"""
    if not _HAS_DINGTALK:
        return
    try:
        import dingtalk as _dt
        webhooks = _dt.list_webhooks()
    except Exception:
        return
    changed = False
    with st.sidebar.expander("钉钉群开关", expanded=False):
        st.sidebar.caption("勾选 = 启用，取消 = 停用（机器人无需退群）")
        for i, w in enumerate(webhooks):
            checked = st.sidebar.checkbox(w["name"], value=w["enabled"], key=f"dt_group_{i}")
            if checked != w["enabled"]:
                w["enabled"] = checked
                changed = True
    if changed:
        try:
            cfg_path = Path(__file__).parent / "config" / "dingtalk.local.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            for w in webhooks:
                for item in cfg.get("webhooks", []):
                    if item.get("name") == w["name"]:
                        item["enabled"] = w["enabled"]
            cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            st.sidebar.success("钉钉群开关已保存，下次推送生效")
        except Exception as exc:
            st.sidebar.error(f"钉钉群开关保存失败: {exc}")


# ========== 侧边栏 ==========
st.sidebar.title("🏗️ 隐患检测系统")
st.sidebar.markdown("---")

# 项目信息
project_name = st.sidebar.text_input("项目名称", value="示范项目")
inspector = st.sidebar.text_input("检查人", value="")

# 导航
page = st.sidebar.radio("功能导航", ["📷 隐患检测", "🎥 实时检测", "🎬 视频检测", "📋 检测记录", "📊 统计分析"])

active_detector = get_current_detector()
st.sidebar.caption(f"Current model: {active_detector.model_version}")
if active_detector.fallback_used:
    st.sidebar.warning(f"Model fallback enabled: {active_detector.fallback_reason}")

_render_dingtalk_group_toggles()

st.sidebar.markdown("---")
st.sidebar.caption("五建(环科)公司 AI应用创新大赛参赛作品")


# ========== 页面1: 隐患检测 ==========
if page == "📷 隐患检测":
    st.title("📷 多类隐患智能检测")

    st.markdown("上传工地现场照片,系统自动检测 **安全帽佩戴** 和 **反光衣穿着** 情况,并生成分级预警。")

    # 上传图片
    uploaded_file = st.file_uploader(
        "选择工地照片",
        type=["jpg", "jpeg", "png"],
        help="支持 JPG/PNG 格式"
    )

    # 示例图片
    sample_dir = Path(__file__).parent / "data" / "sample_images"
    if sample_dir.exists():
        sample_files = list(sample_dir.glob("*.jpg")) + list(sample_dir.glob("*.png"))
        if sample_files:
            st.markdown("**或选择示例图片测试:**")
            cols = st.columns(min(len(sample_files), 4))
            for i, sf in enumerate(sample_files[:4]):
                with cols[i]:
                    if st.button(f"示例 {i+1}", key=f"sample_{i}"):
                        # 用 BytesIO 包装示例图,使其具备 getbuffer()/name 接口
                        # (与 st.file_uploader 返回的 UploadedFile 兼容,避免后续 getbuffer() 崩溃)
                        buf = io.BytesIO(sf.read_bytes())
                        buf.name = sf.name
                        uploaded_file = buf

    if uploaded_file is not None:
        # 保存上传的图片
        upload_dir = Path(__file__).parent / "data" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        image_path = upload_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
        with open(image_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # 显示原图
        st.markdown("### 原始图片")
        col1, col2 = st.columns(2)
        with col1:
            st.image(str(image_path), caption="原图", width="stretch")

        # 执行检测
        with st.spinner("正在检测..."):
            detector = get_current_detector()
            result = detector.detect(str(image_path))

            alert_engine = get_alert_engine()
            alerts = alert_engine.generate_alerts(result["detections"])
            result["alerts"] = alerts

            # 保存记录
            db = get_database()
            record_id = db.save_record(
                result,
                image_name=uploaded_file.name,
                project_name=project_name,
                inspector=inspector,
                model_version=detector.model_version,
            )

            # 发送钉钉预警（仅红色/黄色预警且未通知过）
            if _HAS_DINGTALK and alerts:
                if '_notified_rids' not in st.session_state:
                    st.session_state['_notified_rids'] = set()
                if record_id not in st.session_state['_notified_rids']:
                    st.session_state['_notified_rids'].add(record_id)
                    _send_image_alert(alerts, record_id, image_path, project_name, inspector)

        # 显示检测结果
        with col2:
            st.image(result["image"], caption="检测结果", width="stretch")

        # 检测摘要
        st.markdown("---")
        st.markdown("### 检测结果摘要")

        summary = result["summary"]
        col_a, col_b, col_c, col_d, col_e, col_f = st.columns(6)
        col_a.metric("检测目标总数", summary["total_detections"])
        col_b.metric("已戴安全帽", summary["helmet_count"])
        col_c.metric("🔴 未戴安全帽", summary["no_helmet_count"])
        col_d.metric("已穿反光衣", summary["vest_count"])
        col_e.metric("🟡 未穿反光衣", summary["no_vest_count"])
        col_f.metric("🟡 未戴口罩", summary["no_mask_count"])

        # 预警信息
        if result["alerts"]:
            st.markdown("---")
            st.markdown("### ⚠️ 预警信息")

            overall = alert_engine.get_overall_level(result["alerts"])
            if overall:
                if overall["level"] == "red":
                    st.error(f"{overall['icon']} {overall['level_name']} — {overall['action']}")
                elif overall["level"] == "yellow":
                    st.warning(f"{overall['icon']} {overall['level_name']} — {overall['action']}")
                else:
                    st.info(f"{overall['icon']} {overall['level_name']} — {overall['action']}")

            # 预警详情表格
            alert_df = pd.DataFrame([{
                "时间": a["timestamp"],
                "等级": f"{a['icon']} {a['level_name']}",
                "隐患类型": a["hazard_type"],
                "描述": a["description"],
                "置信度": f"{a['confidence']*100:.0f}%",
                "处理建议": a["action"],
            } for a in result["alerts"]])
            st.dataframe(alert_df, use_container_width=True)
        else:
            st.success("✅ 未发现违规情况")

        # 检测详情
        if result["detections"]:
            with st.expander("查看详细检测结果"):
                det_df = pd.DataFrame([{
                    "检测目标": d["label"],
                    "置信度": f"{d['confidence']*100:.0f}%",
                    "预警等级": d["alert_name"],
                    "位置": f"({d['bbox'][0]},{d['bbox'][1]})-({d['bbox'][2]},{d['bbox'][3]})",
                } for d in result["detections"]])
                st.dataframe(det_df, use_container_width=True)

        st.info(f"📝 检测记录已保存(记录ID: {record_id})")


# ========== 页面2: 检测记录 ==========
elif page == "📋 检测记录":
    st.title("📋 检测记录")

    db = get_database()
    tab1, tab2 = st.tabs(["🖼️ 图片检测记录", "🎥 实时违规记录"])

    # --- Tab1: 图片检测记录 ---
    with tab1:
        records = db.get_recent_records(limit=50)
        if records:
            df = pd.DataFrame(records)
            display_cols = ["timestamp", "project_name", "inspector", "model_version", "image_name",
                            "total_detections", "no_helmet_count", "no_vest_count",
                            "red_alerts", "yellow_alerts", "has_violation"]
            display_names = {
                "timestamp": "检测时间",
                "project_name": "项目",
                "inspector": "检查人",
                "image_name": "图片",
                "total_detections": "目标数",
                "no_helmet_count": "未戴帽",
                "no_vest_count": "未穿衣",
                "red_alerts": "红色",
                "yellow_alerts": "黄色",
                "has_violation": "是否有违规",
            }
            display_names["model_version"] = "Model version"
            df_display = df[display_cols].rename(columns=display_names)
            df_display["是否有违规"] = df_display["是否有违规"].map({0: "否", 1: "是"})

            st.dataframe(df_display, use_container_width=True)

            # 查看详情
            if st.button("查看最新记录详情"):
                latest = records[0]
                st.json({
                    "时间": latest["timestamp"],
                    "检测结果": json.loads(latest["detections_json"]) if latest["detections_json"] else [],
                    "预警信息": json.loads(latest["alerts_json"]) if latest["alerts_json"] else [],
                })
        else:
            st.info("暂无图片检测记录,请先在「隐患检测」页上传照片。")

    # --- Tab2: 实时违规记录(任务#3) ---
    with tab2:
        rt_records = db.get_realtime_violations(limit=50)
        if rt_records:
            type_cn = {"no-helmet": "未戴安全帽", "no-vest": "未穿反光衣", "no-mask": "未戴口罩"}
            level_icon = {"red": "🔴 红色", "yellow": "🟡 黄色", "blue": "🔵 蓝色"}
            rt_df = pd.DataFrame(rt_records)
            rt_display = pd.DataFrame({
                "入库时间": rt_df["timestamp"],
                "违规类型": rt_df["violation_type"].map(type_cn).fillna(rt_df["violation_type"]),
                "本帧数量": rt_df["violation_count"],
                "预警等级": rt_df["level"].map(level_icon).fillna(rt_df["level"]),
                "项目": rt_df["project_name"],
                "检查人": rt_df["inspector"],
                "截图": rt_df["snapshot_path"].replace("", "—"),
            })
            rt_display.insert(6, "Model version", rt_df["model_version"])
            st.dataframe(rt_display, use_container_width=True, hide_index=True)
            st.caption(f"共 {len(rt_records)} 条实时违规记录(每 {int(ALERT_COOLDOWN)}s 节流去重入库)")
            # 任务#5: 显示最近一张违规抓拍
            latest_snap = next((r for r in rt_records if r.get("snapshot_path") and os.path.exists(r["snapshot_path"])), None)
            if latest_snap:
                st.markdown("**最近违规抓拍:**")
                st.image(latest_snap["snapshot_path"], width="stretch")
        else:
            st.info("暂无实时违规记录。实时检测发现违规(未戴安全帽/反光衣/口罩)并超过节流期后会自动入库。")


# ========== 页面3: 统计分析 ==========
elif page == "📊 统计分析":
    st.title("📊 统计分析")

    db = get_database()
    stats = db.get_statistics()

    # 概览卡片
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总检测次数", stats["total_checks"])
    col2.metric("违规次数", stats["violation_count"])
    col3.metric("合规率", f"{stats['compliance_rate']}%")
    col4.metric("未戴安全帽总人次", stats["no_helmet_total"])

    st.markdown("---")

    # 每日趋势
    daily = db.get_daily_stats(days=7)
    if daily:
        st.markdown("### 近7天检测趋势")
        df_daily = pd.DataFrame(daily)
        fig = px.bar(df_daily, x="date", y=["checks", "violations"],
                     title="每日检测次数与违规次数",
                     labels={"date": "日期", "value": "次数", "variable": "类型"},
                     color_discrete_map={"checks": "#4488FF", "violations": "#FF4444"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无统计数据")


# ========== 页面: 实时检测 ==========
elif page == "🎥 实时检测":
    st.title("🎥 实时视频检测")
    st.markdown("开启摄像头,AI 实时检测安全帽/反光衣佩戴情况")
    st.caption("💡 点击下方 **START** 启动摄像头,可随时点击 **STOP** 停止。无帧数限制,持续识别。")

    # 局部导入(WebRTC 相关,仅此页使用)
    import av
    import time
    from streamlit_webrtc import webrtc_streamer

    # ----- 控制面板 -----
    col1, col2 = st.columns([1, 3])
    with col1:
        conf = st.slider("置信度阈值", 0.2, 0.8, 0.4, 0.05)
        st.caption(f"✅ 当前生效置信度: **{conf:.2f}**")
        detect_interval = st.slider("检测间隔(帧)", 1, 5, DETECT_INTERVAL_DEFAULT, 1, help="每 N 帧检测一次,跳帧用缓存框保持画面(省性能,1=每帧)")
        st.caption(f"✅ 当前检测间隔: **{detect_interval}** 帧")
        st.markdown("#### ⚙️ 操作")
        if st.button("🔄 重置统计", help="清空累计统计,从 0 重新计数"):
            _reset_rt_stats()
            st.rerun()
        # 录制控制(任务#9)
        st.markdown("#### 🎬 录制")
        snap_ctl = _snapshot_rt_stats()
        if snap_ctl.get("recording"):
            if st.button("⏹ 停止录制", type="primary"):
                rt = get_rt_stats()
                with rt["lock"]:
                    rt["recording"] = False
                st.rerun()
        else:
            if st.button("⏺ 开始录制"):
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
    device = 0 if torch.cuda.is_available() else "cpu"

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
                        if db is not None:
                            try:
                                db.save_realtime_violation(
                                    violation_type=vtype, violation_count=vcount,
                                    level=vlevel, snapshot_path=str(snap_path),
                                    project_name=proj, inspector=insp,
                                    model_version=detector.model_version,
                                )
                            except Exception:
                                pass
                        with rt_stats["lock"]:
                            rt_stats["realtime_record_count"] += 1
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
    ctx = webrtc_streamer(
        key="ppe-realtime",
        video_frame_callback=video_frame_callback,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
        rtc_configuration={
            "iceServers": [
                {"urls": ["stun:stun.l.google.com:19302"]},
                {"urls": ["stun:stun.qq.com:3478"]},
            ]
        },
    )

    # ----- 统计面板(fragment 每0.5s局部刷新,避免全页rerun打断WebRTC画面/滑块交互) -----
    @st.fragment(run_every=0.5)
    def _render_rt_stats():
        snap = _snapshot_rt_stats()
        with col2:
            # 红色告警(任务#4): 弹窗+声音,仅 DISPLAY 秒内显示,声音每条告警只播一次
            red_t = snap.get("red_alert_time", 0.0)
            if red_t and (time.time() - red_t < RED_ALERT_DISPLAY):
                st.error("🔴🔴🔴 红色预警！检测到未戴安全帽，请立即处理！")
                if not snap.get("red_alert_played", True):
                    _play_alert_sound()
                    rt = get_rt_stats()
                    with rt["lock"]:
                        rt["red_alert_played"] = True
            # 录制状态(任务#9)
            if snap.get("recording"):
                elapsed = int(time.time() - snap.get("rec_start", time.time()))
                st.error(f"⏺ 录制中... {elapsed}秒")
            else:
                last_rec = snap.get("last_recording_path")
                if last_rec and os.path.exists(last_rec):
                    st.success(f"✅ 录制已保存: {os.path.basename(last_rec)}")
                    st.video(last_rec)

            # 错误提示(不再静默吞掉异常)
            if snap["last_error"]:
                st.error(f"⚠️ 检测异常(画面已回退为原图): {snap['last_error']}")


    _render_rt_stats()


# ========== 页面: 视频检测 ==========
elif page == "🎬 视频检测":
    st.title("🎬 视频文件检测")
    st.markdown("上传工地视频(mp4/avi),AI 逐帧检测并输出标注视频")

    uploaded_video = st.file_uploader("选择视频文件", type=["mp4", "avi", "mov"])
    conf = st.slider("置信度阈值", 0.2, 0.8, 0.4, 0.05)

    if uploaded_video is not None:
        video_dir = Path(__file__).parent / "data" / "uploads"
        video_dir.mkdir(parents=True, exist_ok=True)
        video_path = video_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_video.name}"
        with open(video_path, "wb") as f:
            f.write(uploaded_video.getbuffer())

        st.info(f"视频已上传:{uploaded_video.name},正在逐帧检测...")

        detector = get_current_detector()
        device = 0 if torch.cuda.is_available() else "cpu"
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
                status.markdown(f"已处理 {frame_count}/{total} 帧 | 累计检测 {total_detections} 个目标")

        cap.release()
        out.release()
        progress.progress(1.0)
        st.success(f"检测完成!共 {frame_count} 帧,累计检测到 {total_detections} 个目标")

        # 转码为H.264(浏览器兼容)
        import imageio_ffmpeg
        import subprocess as sp
        h264_path = str(video_dir / f"h264_{uploaded_video.name}")
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        with st.spinner("正在转码为浏览器兼容格式(H.264)..."):
            sp.run([ffmpeg_exe, '-i', str(output_path), '-c:v', 'libx264',
                    '-preset', 'fast', '-pix_fmt', 'yuv420p', h264_path, '-y'],
                   capture_output=True)

        st.markdown("### 检测统计")
        if class_total:
            stat_str = " | ".join(f"{k}: {v}" for k, v in sorted(class_total.items(), key=lambda x: -x[1]))
            st.markdown(stat_str)

        st.markdown("### 检测结果视频")
        if os.path.exists(h264_path):
            st.video(h264_path)
        else:
            st.video(str(output_path))
