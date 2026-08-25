"""V3 browser interface API.

The module keeps the existing detector, database and DingTalk implementations as
the source of truth.  It deliberately exposes only browser-safe identifiers and
relative media URLs; local paths and notification credentials never cross the
HTTP boundary.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional, Union
from urllib.parse import quote

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from .alert import AlertEngine
from .database import Database
from .detector import HazardDetector, select_compute_device
from . import dingtalk


_LOG = logging.getLogger("hazard_web_api")

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
SNAPSHOTS_DIR = UPLOADS_DIR / "snapshots"
SAMPLE_IMAGE = DATA_DIR / "sample_images" / "test_helmet.jpg"
ALERT_SOUND = DATA_DIR / "alert.wav"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
DINGTALK_CONFIG_PATH = ROOT_DIR / "config" / "dingtalk.local.json"

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_VIDEO_BYTES = 500 * 1024 * 1024
REALTIME_COOLDOWN_SECONDS = 60.0
NOTIFICATION_RETRY_DELAYS = (30.0, 60.0, 120.0)
NOTIFICATION_INITIAL_DELAY = 0.05
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
MEDIA_SUFFIXES = IMAGE_SUFFIXES | VIDEO_SUFFIXES

app = FastAPI(
    title="多类隐患检测系统 API",
    version="3.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

_resource_lock = threading.Lock()
_inference_lock = threading.Lock()
_notification_config_lock = threading.Lock()
_detector: Optional[Any] = None
_database: Optional[Any] = None
_alert_engine: Optional[Any] = None

_realtime_lock = threading.RLock()
_realtime_sessions: dict[str, dict[str, Any]] = {}
_video_jobs_lock = threading.RLock()
_video_jobs: dict[str, dict[str, Any]] = {}


class ContextPayload(BaseModel):
    project_name: str = Field(max_length=120)
    inspector: str = Field(max_length=80)


class IncidentWorkflowPayload(BaseModel):
    status: Literal["pending", "in_progress", "closed", "false_positive"]
    assignee: str = Field(default="", max_length=80)
    due_at: Optional[str] = Field(default=None, max_length=32)
    resolution_note: str = Field(default="", max_length=2000)
    operator: str = Field(default="", max_length=80)


class NotificationGroupUpdate(BaseModel):
    short_id: str = Field(min_length=8, max_length=8, pattern=r"^[0-9A-Fa-f]{8}$")
    name: str = Field(min_length=1, max_length=60)
    enabled: bool
    new_open_conversation_id: Optional[str] = Field(default=None, max_length=200)


class NotificationGroupsPayload(BaseModel):
    groups: list[NotificationGroupUpdate] = Field(min_length=1)


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(_request, _exc):
    return JSONResponse(status_code=422, content={"detail": "请求参数无效"})


@app.exception_handler(StarletteHTTPException)
async def _http_error_handler(_request, exc):
    detail = exc.detail if isinstance(exc.detail, str) else "请求处理失败"
    if detail == "Not Found":
        detail = "接口不存在"
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(Exception)
async def _unexpected_error_handler(_request, exc):
    _LOG.error("API 未处理异常类型: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "服务器处理失败"})


def get_database():
    global _database
    if _database is None:
        with _resource_lock:
            if _database is None:
                _database = Database()
    return _database


def get_detector():
    global _detector
    if _detector is None:
        with _resource_lock:
            if _detector is None:
                _detector = HazardDetector()
    return _detector


def get_alert_engine():
    global _alert_engine
    if _alert_engine is None:
        with _resource_lock:
            if _alert_engine is None:
                _alert_engine = AlertEngine()
    return _alert_engine


def _clean_context(project_name: str, inspector: str) -> tuple[str, str]:
    project = str(project_name or "").strip()
    checker = str(inspector or "").strip()
    if not project or not checker:
        raise HTTPException(status_code=422, detail="请先填写项目名称和检查人")
    if len(project) > 120 or len(checker) > 80:
        raise HTTPException(status_code=422, detail="检查上下文过长")
    return project, checker


def _model_status() -> dict[str, Any]:
    try:
        model_path = HazardDetector.resolve_model_path()
        return {
            "status": "ready" if model_path.is_file() else "missing",
            "version": model_path.name,
            "fallback": bool(getattr(_detector, "fallback_used", False)) if _detector else False,
        }
    except Exception:
        return {"status": "unavailable", "version": "未知", "fallback": False}


def _notification_summary() -> dict[str, Any]:
    try:
        groups = dingtalk.list_webhooks(DINGTALK_CONFIG_PATH)
    except Exception:
        return {"configured": False, "total": 0, "enabled": 0, "bound": 0}
    return {
        "configured": True,
        "total": len(groups),
        "enabled": sum(bool(item.get("enabled")) for item in groups),
        "bound": sum(bool(str(item.get("open_conversation_id", "")).strip()) for item in groups),
    }


def _safe_relative(path: Path, root: Path) -> Optional[Path]:
    try:
        return path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return None


def _media_url_for_path(value: Optional[Union[str, Path]]) -> Optional[str]:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    for kind, root in (("snapshots", SNAPSHOTS_DIR), ("uploads", UPLOADS_DIR)):
        relative = _safe_relative(path, root)
        if relative is not None:
            encoded = "/".join(quote(part, safe="") for part in relative.parts)
            return f"/api/media/{kind}/{encoded}"
    return None


def _resolve_media(kind: str, filename: str) -> Path:
    roots = {"uploads": UPLOADS_DIR, "snapshots": SNAPSHOTS_DIR}
    root = roots.get(kind)
    if root is None or not filename or "\x00" in filename:
        raise HTTPException(status_code=404, detail="媒体文件不存在")
    candidate = (root / filename).resolve()
    if (
        _safe_relative(candidate, root) is None
        or candidate.suffix.lower() not in MEDIA_SUFFIXES
        or not candidate.is_file()
    ):
        raise HTTPException(status_code=404, detail="媒体文件不存在")
    return candidate


def _risk_from_summary(summary: dict[str, Any]) -> str:
    if int(summary.get("red_alerts") or 0) > 0:
        return "red"
    if int(summary.get("yellow_alerts") or 0) > 0:
        return "yellow"
    return "blue"


def _summary_from_detections(detections: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(item.get("label_en", "")) for item in detections)
    red = sum(1 for item in detections if item.get("alert_level") == "red")
    yellow = sum(1 for item in detections if item.get("alert_level") == "yellow")
    return {
        "total_detections": len(detections),
        "helmet_count": counts["helmet"],
        "no_helmet_count": counts["no-helmet"],
        "vest_count": counts["vest"],
        "no_vest_count": counts["no-vest"],
        "mask_count": counts["mask"],
        "no_mask_count": counts["no-mask"],
        "person_count": counts["person"],
        "red_alerts": red,
        "yellow_alerts": yellow,
        "has_violation": red + yellow > 0,
    }


def _parse_json_field(value: Any, default):
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default


def _image_notification_text(
    alerts: list[dict[str, Any]], project: str, inspector: str, record_id: int
) -> str:
    counts = Counter(str(item.get("hazard_type") or "未知隐患") for item in alerts)
    highest = "红色预警" if any(item.get("level") == "red" for item in alerts) else "黄色预警"
    details = "\n".join(f"- {name} × {count}" for name, count in counts.items())
    return (
        f"{highest}\n\n项目：{project}\n检查人：{inspector}\n"
        f"记录：#{record_id}\n时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
        f"隐患明细：\n{details}\n\n请及时进入系统完成处置。"
    )


def _send_image_notification(
    alerts: list[dict[str, Any]], project: str, inspector: str, record_id: int
) -> dict[str, Any]:
    if not alerts:
        return {"status": "not_needed", "sent_count": 0}
    try:
        results = dingtalk.send_text(
            _image_notification_text(alerts, project, inspector, record_id),
            DINGTALK_CONFIG_PATH,
        )
        return {"status": "sent", "sent_count": len(results or [])}
    except Exception:
        _LOG.warning("图片记录 #%s 的钉钉通知发送失败", record_id)
        return {"status": "failed", "sent_count": 0}


async def _read_upload(file: UploadFile, maximum: int) -> bytes:
    data = await file.read(maximum + 1)
    await file.close()
    if not data:
        raise HTTPException(status_code=422, detail="上传文件为空")
    if len(data) > maximum:
        raise HTTPException(status_code=413, detail="上传文件过大")
    return data


def _validate_image(data: bytes, *, jpeg_only: bool = False) -> str:
    try:
        from PIL import Image
        from io import BytesIO

        with Image.open(BytesIO(data)) as image:
            image.verify()
            image_format = str(image.format or "").upper()
    except Exception:
        raise HTTPException(status_code=422, detail="上传内容不是有效图片") from None
    if jpeg_only and image_format not in {"JPEG", "JPG"}:
        raise HTTPException(status_code=422, detail="实时帧必须是 JPEG 图片")
    suffixes = {"JPEG": ".jpg", "JPG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp"}
    suffix = suffixes.get(image_format)
    if not suffix:
        raise HTTPException(status_code=422, detail="不支持该图片格式")
    return suffix


def _safe_upload_name(original: Optional[str], suffix: str) -> str:
    stem = Path(original or "image").stem[:60]
    cleaned = "".join(char for char in stem if char.isalnum() or char in "-_ ").strip() or "image"
    return f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:10]}_{cleaned}{suffix}"


@app.get("/api/health")
def health():
    try:
        get_database().get_last_check_context()
        database_status = "ready"
    except Exception:
        database_status = "unavailable"
    return {"status": "ok", "database": database_status, "model": _model_status()}


@app.get("/api/bootstrap")
def bootstrap():
    db = get_database()
    try:
        context = db.get_last_check_context()
        workflow = db.get_incident_statistics()
    except Exception:
        raise HTTPException(status_code=503, detail="本地记录服务暂不可用") from None
    return {
        "context": context,
        "model": _model_status(),
        "workflow": workflow,
        "notifications": _notification_summary(),
    }


@app.get("/api/context")
def get_context():
    try:
        return get_database().get_last_check_context()
    except Exception:
        raise HTTPException(status_code=503, detail="无法读取检查上下文") from None


@app.put("/api/context")
def put_context(payload: ContextPayload):
    project = payload.project_name.strip()
    inspector = payload.inspector.strip()
    try:
        get_database().save_last_check_context(project, inspector)
    except Exception:
        raise HTTPException(status_code=503, detail="无法保存检查上下文") from None
    return {"project_name": project, "inspector": inspector}


@app.get("/api/sample")
def sample_image():
    if not SAMPLE_IMAGE.is_file():
        raise HTTPException(status_code=404, detail="内置示例图片不存在")
    return FileResponse(SAMPLE_IMAGE)


@app.get("/api/alert-sound")
def alert_sound():
    if not ALERT_SOUND.is_file():
        raise HTTPException(status_code=404, detail="本地警报音不存在")
    return FileResponse(ALERT_SOUND, media_type="audio/wav")


@app.get("/api/media/{kind}/{filename:path}")
def media_file(kind: str, filename: str):
    return FileResponse(_resolve_media(kind, filename))


@app.post("/api/detect/image")
async def detect_image(
    file: UploadFile = File(...),
    project_name: str = Form(...),
    inspector: str = Form(...),
    confidence: float = Form(default=0.4, ge=0.1, le=0.95),
):
    project, checker = _clean_context(project_name, inspector)
    data = await _read_upload(file, MAX_IMAGE_BYTES)
    suffix = _validate_image(data)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    upload_name = _safe_upload_name(file.filename, suffix)
    original_path = UPLOADS_DIR / upload_name
    original_path.write_bytes(data)

    try:
        detector = get_detector()
        with _inference_lock:
            result = detector.detect(str(original_path), conf=float(confidence))
        detections = list(result.get("detections") or [])
        alerts = get_alert_engine().generate_alerts(detections)
        result["alerts"] = alerts
        summary = dict(result.get("summary") or _summary_from_detections(detections))
        result["summary"] = summary
        record_id = get_database().save_record(
            result,
            image_name=Path(file.filename or upload_name).name,
            project_name=project,
            inspector=checker,
            model_version=str(getattr(detector, "model_version", "未知")),
        )
    except HTTPException:
        raise
    except Exception:
        original_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="图片检测处理失败") from None

    notification = _send_image_notification(alerts, project, checker, int(record_id))
    return {
        "record_id": int(record_id),
        "risk": _risk_from_summary(summary),
        "summary": summary,
        "detections": detections,
        "alerts": alerts,
        "original_url": _media_url_for_path(original_path),
        "annotated_url": _media_url_for_path(result.get("image")),
        "notification": notification,
    }


def _normalise_incident(record: dict[str, Any], source_type: str) -> dict[str, Any]:
    item = dict(record)
    item["source_type"] = source_type
    item["source_id"] = int(item.get("id") or 0)
    item["source_label"] = "图片检测" if source_type == "image" else "实时抓拍"
    if source_type == "image":
        red = int(item.get("red_alerts") or 0)
        yellow = int(item.get("yellow_alerts") or 0)
        item["risk"] = "red" if red else "yellow" if yellow else "blue"
        item["detections"] = _parse_json_field(item.pop("detections_json", None), [])
        item["alerts"] = _parse_json_field(item.pop("alerts_json", None), [])
        item["evidence_url"] = _media_url_for_path(item.pop("result_image_path", None))
    else:
        item["risk"] = "red" if item.get("level") == "red" else "yellow"
        item["violation_summary"] = _realtime_violation_summary(item.get("violation_type"))
        item["evidence_url"] = _media_url_for_path(item.pop("snapshot_path", None))
    item.pop("id", None)
    return item


def _incident_matches(item: dict[str, Any], quick: str, search: str, inspector: str) -> bool:
    status = str(item.get("incident_status") or "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    quick_matches = {
        "all": True,
        "open": status in {"pending", "in_progress"},
        "pending": status == "pending",
        "in_progress": status == "in_progress",
        "mine": (
            bool(inspector)
            and status in {"pending", "in_progress"}
            and str(item.get("assignee") or "").strip() == inspector.strip()
        ),
        "unassigned": status in {"pending", "in_progress"} and not item.get("assignee"),
        "red": item.get("risk") == "red" and status in {"pending", "in_progress"},
        "yellow": item.get("risk") == "yellow" and status in {"pending", "in_progress"},
        "overdue": (
            status in {"pending", "in_progress"}
            and bool(item.get("due_at"))
            and str(item["due_at"]) < now
        ),
        "closed": status == "closed",
    }
    if not quick_matches.get(quick, False):
        return False
    needle = search.strip().casefold()
    if not needle:
        return True
    haystack = " ".join(
        str(item.get(key) or "")
        for key in (
            "source_id", "source_label", "project_name", "inspector", "assignee",
            "image_name", "violation_type", "resolution_note",
        )
    ).casefold()
    return needle in haystack


@app.get("/api/incidents")
def get_incidents(
    quick: Literal[
        "all", "open", "pending", "in_progress", "mine", "unassigned",
        "red", "yellow", "overdue", "closed",
    ] = "open",
    search: str = Query(default="", max_length=120),
    inspector: str = Query(default="", max_length=80),
    history_limit: int = Query(default=200, ge=0, le=1000),
):
    try:
        db = get_database()
        image_items = [_normalise_incident(item, "image") for item in db.get_image_incident_queue(history_limit)]
        realtime_items = [_normalise_incident(item, "realtime") for item in db.get_realtime_incident_queue(history_limit)]
    except Exception:
        raise HTTPException(status_code=503, detail="无法读取处置队列") from None
    items = [
        item for item in image_items + realtime_items
        if _incident_matches(item, quick, search, inspector.strip())
    ]
    items.sort(key=lambda item: (str(item.get("timestamp") or ""), item["source_id"]), reverse=True)
    return {"items": items, "total": len(items), "quick": quick}


@app.put("/api/incidents/{source_type}/{source_id}")
def update_incident(
    source_type: Literal["image", "realtime"],
    source_id: int,
    payload: IncidentWorkflowPayload,
):
    try:
        workflow = get_database().update_incident_workflow(
            source_type,
            source_id,
            status=payload.status,
            assignee=payload.assignee,
            due_at=payload.due_at,
            resolution_note=payload.resolution_note,
            operator=payload.operator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=503, detail="无法保存处置状态") from None
    return {"source_type": source_type, "source_id": source_id, "workflow": workflow}


@app.get("/api/statistics")
def statistics(days: int = Query(default=7, ge=1, le=90)):
    try:
        db = get_database()
        checks = db.get_statistics()
        workflow = db.get_incident_statistics()
        daily = db.get_daily_stats(days)
    except Exception:
        raise HTTPException(status_code=503, detail="无法读取统计数据") from None
    ranking = [
        {"key": "no-helmet", "label": "未戴安全帽", "count": int(checks.get("no_helmet_total") or 0)},
        {"key": "no-vest", "label": "未穿反光衣", "count": int(checks.get("no_vest_total") or 0)},
    ]
    ranking.sort(key=lambda item: item["count"], reverse=True)
    return {"checks": checks, "workflow": workflow, "daily": daily, "hazard_ranking": ranking}


def _identity_for_group(group: dict[str, Any], *, refresh: bool) -> dict[str, Any]:
    if not str(group.get("open_conversation_id", "")).strip():
        return {"status": "unbound", "source": "local", "reason": "尚未绑定"}
    try:
        identity = dingtalk.resolve_group_identity(
            group, DINGTALK_CONFIG_PATH, refresh=refresh
        )
    except Exception:
        return {"status": "unavailable", "source": "local", "reason": "暂时无法验证群名"}
    public_identity = {
        "status": str(identity.get("status") or "unavailable"),
        "source": str(identity.get("source") or "local"),
        "reason": str(identity.get("reason") or ""),
        "checked_at": identity.get("checked_at"),
    }
    official_name = str(identity.get("official_name") or "")
    if official_name:
        public_identity["official_name"] = official_name
    return public_identity


def _public_notification_group(group: dict[str, Any], *, resolve_identity: bool) -> dict[str, Any]:
    identity = (
        _identity_for_group(group, refresh=False)
        if resolve_identity
        else {
            "status": "bound_unverified" if group.get("open_conversation_id") else "unbound",
            "source": "local",
            "reason": "",
        }
    )
    return {
        "short_id": str(group.get("short_id") or ""),
        "name": str(group.get("name") or "未命名群"),
        "enabled": bool(group.get("enabled")),
        "bound": bool(str(group.get("open_conversation_id", "")).strip()),
        "identity": identity,
    }


def _list_notification_groups(*, resolve_identity: bool) -> list[dict[str, Any]]:
    try:
        groups = dingtalk.list_webhooks(DINGTALK_CONFIG_PATH)
    except Exception:
        raise HTTPException(status_code=503, detail="钉钉群配置暂不可用") from None
    return [_public_notification_group(group, resolve_identity=resolve_identity) for group in groups]


@app.get("/api/notifications/groups")
def get_notification_groups():
    groups = _list_notification_groups(resolve_identity=True)
    return {"groups": groups, "enabled": sum(item["enabled"] for item in groups)}


def _load_raw_notification_config() -> dict[str, Any]:
    try:
        value = json.loads(DINGTALK_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        raise HTTPException(status_code=503, detail="钉钉群配置暂不可用") from None
    if not isinstance(value, dict):
        raise HTTPException(status_code=503, detail="钉钉群配置格式无效")
    return value


def _raw_groups(config: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    groups = config.get("webhooks")
    if isinstance(groups, list):
        return groups, False
    webhook = str(config.get("webhook") or "").strip()
    if webhook:
        return [{"name": "默认群", "webhook": webhook, "enabled": True}], True
    raise HTTPException(status_code=503, detail="钉钉群配置中没有可管理的群")


@app.put("/api/notifications/groups")
def put_notification_groups(payload: NotificationGroupsPayload):
    updates = {item.short_id.upper(): item for item in payload.groups}
    if len(updates) != len(payload.groups):
        raise HTTPException(status_code=422, detail="群标识不能重复")
    with _notification_config_lock:
        config = _load_raw_notification_config()
        groups, was_legacy = _raw_groups(config)
        known_ids: set[str] = set()
        for group in groups:
            short_id = dingtalk.webhook_short_id(str(group.get("webhook") or "").strip())
            if short_id in known_ids:
                raise HTTPException(status_code=409, detail="本地配置中存在重复群绑定")
            known_ids.add(short_id)
            update = updates.get(short_id)
            if update is None:
                continue
            name = update.name.strip()
            if not name:
                raise HTTPException(status_code=422, detail="群名称不能为空")
            group["name"] = name
            group["enabled"] = update.enabled
            if update.new_open_conversation_id is not None:
                binding = update.new_open_conversation_id.strip()
                if binding:
                    group["open_conversation_id"] = binding
                else:
                    group.pop("open_conversation_id", None)
        if set(updates) - known_ids:
            raise HTTPException(status_code=409, detail="群标识与本地配置不一致")
        if not any(bool(group.get("enabled", True)) for group in groups):
            raise HTTPException(status_code=422, detail="请至少保留一个接收群")
        bindings = [
            str(group.get("open_conversation_id") or "").strip()
            for group in groups
            if str(group.get("open_conversation_id") or "").strip()
        ]
        if len(bindings) != len(set(bindings)):
            raise HTTPException(status_code=422, detail="同一个钉钉会话不能绑定到多个群")
        if was_legacy:
            config["webhooks"] = groups
        temporary = DINGTALK_CONFIG_PATH.with_name(f".{DINGTALK_CONFIG_PATH.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(DINGTALK_CONFIG_PATH)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise HTTPException(status_code=503, detail="无法保存钉钉群设置") from None
        dingtalk.clear_group_identity_cache()
    groups_response = _list_notification_groups(resolve_identity=False)
    return {"groups": groups_response, "enabled": sum(item["enabled"] for item in groups_response)}


@app.post("/api/notifications/groups/{short_id}/refresh")
def refresh_notification_group(short_id: str):
    normalized = short_id.strip().upper()
    if len(normalized) != 8:
        raise HTTPException(status_code=404, detail="通知群不存在")
    try:
        groups = dingtalk.list_webhooks(DINGTALK_CONFIG_PATH)
    except Exception:
        raise HTTPException(status_code=503, detail="钉钉群配置暂不可用") from None
    group = next((item for item in groups if item.get("short_id") == normalized), None)
    if group is None:
        raise HTTPException(status_code=404, detail="通知群不存在")
    return {
        "short_id": normalized,
        "bound": bool(group.get("open_conversation_id")),
        "identity": _identity_for_group(group, refresh=True),
    }


def _public_video_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in job.items()
        if not key.startswith("_")
    }


def _parse_model_results(detector, results) -> tuple[list[dict[str, Any]], Optional[Any]]:
    detections: list[dict[str, Any]] = []
    plotted = None
    for result in results or []:
        if plotted is None and hasattr(result, "plot"):
            plotted = result.plot()
        for box in getattr(result, "boxes", []) or []:
            cls_id = int(box.cls[0])
            confidence = float(box.conf[0])
            raw_name = detector.model.names[cls_id]
            label_en = detector._map_label(raw_name)
            level, level_name, description = detector.ALERT_LEVELS.get(
                label_en, ("blue", "正常记录", str(raw_name))
            )
            coordinates = [round(value) for value in box.xyxy[0].tolist()]
            detections.append({
                "label": detector.LABEL_CN.get(label_en, str(raw_name)),
                "label_en": label_en,
                "confidence": round(confidence, 2),
                "bbox": coordinates,
                "alert_level": level,
                "alert_name": level_name,
                "description": description,
            })
    return detections, plotted


def _process_video_job(job_id: str):
    with _video_jobs_lock:
        job = _video_jobs.get(job_id)
        if not job:
            return
        job["status"] = "processing"
        input_path = Path(job["_input_path"])
        work_path = Path(job["_work_path"])
        output_path = Path(job["_output_path"])
        confidence = float(job["_confidence"])
    capture = writer = None
    try:
        import cv2

        detector = get_detector()
        capture = cv2.VideoCapture(str(input_path))
        if not capture.isOpened():
            raise RuntimeError("invalid video")
        total_frames = max(int(capture.get(cv2.CAP_PROP_FRAME_COUNT)), 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS)) or 20.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0:
            raise RuntimeError("invalid dimensions")
        work_path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(work_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )
        if not writer.isOpened():
            raise RuntimeError("writer unavailable")
        processed = 0
        detection_total = 0
        red_total = 0
        yellow_total = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            with _inference_lock:
                results = detector.model(
                    frame,
                    conf=confidence,
                    device=select_compute_device(),
                    verbose=False,
                )
                detections, plotted = _parse_model_results(detector, results)
            writer.write(plotted if plotted is not None else frame)
            processed += 1
            detection_total += len(detections)
            red_total += sum(item.get("alert_level") == "red" for item in detections)
            yellow_total += sum(item.get("alert_level") == "yellow" for item in detections)
            if processed % 5 == 0:
                with _video_jobs_lock:
                    job["progress"] = min(processed / max(total_frames, processed), 0.99)
        if processed == 0:
            raise RuntimeError("empty video")
        writer.release()
        writer = None
        import imageio_ffmpeg
        import subprocess

        completed = subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(work_path),
                "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(output_path), "-y",
            ],
            capture_output=True,
            timeout=1200,
            check=False,
        )
        if completed.returncode != 0 or not output_path.is_file() or output_path.stat().st_size < 1024:
            raise RuntimeError("h264 transcode failed")
        with _video_jobs_lock:
            job.update({
                "status": "completed",
                "progress": 1.0,
                "result_url": _media_url_for_path(output_path),
                "summary": {
                    "processed_frames": processed,
                    "total_detections": detection_total,
                    "red_alerts": red_total,
                    "yellow_alerts": yellow_total,
                },
                "completed_at": time.time(),
            })
    except Exception:
        output_path.unlink(missing_ok=True)
        with _video_jobs_lock:
            job.update({"status": "failed", "error": "视频处理失败", "completed_at": time.time()})
        _LOG.error("视频任务 %s 处理失败", job_id)
    finally:
        if capture is not None:
            capture.release()
        if writer is not None:
            writer.release()
        input_path.unlink(missing_ok=True)
        work_path.unlink(missing_ok=True)


@app.post("/api/video/jobs", status_code=202)
async def create_video_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    confidence: float = Form(default=0.4, ge=0.1, le=0.95),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in VIDEO_SUFFIXES:
        await file.close()
        raise HTTPException(status_code=422, detail="不支持该视频格式")
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    input_path = UPLOADS_DIR / "videos" / f"input_{job_id}{suffix}"
    work_path = UPLOADS_DIR / "videos" / f"working_{job_id}.mp4"
    output_path = UPLOADS_DIR / "videos" / f"result_{job_id}.mp4"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with input_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_VIDEO_BYTES:
                    raise HTTPException(status_code=413, detail="上传视频过大")
                output.write(chunk)
    except Exception:
        input_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    if not written:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="上传文件为空")
    job = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0.0,
        "result_url": None,
        "summary": None,
        "error": None,
        "created_at": time.time(),
        "boundary": {"creates_incident": False, "sends_notification": False},
        "_input_path": str(input_path),
        "_work_path": str(work_path),
        "_output_path": str(output_path),
        "_confidence": float(confidence),
    }
    with _video_jobs_lock:
        _video_jobs[job_id] = job
    background_tasks.add_task(_process_video_job, job_id)
    return _public_video_job(job)


@app.get("/api/video/jobs/{job_id}")
def get_video_job(job_id: str):
    with _video_jobs_lock:
        job = _video_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="视频任务不存在")
        return _public_video_job(job)


def _decode_jpeg(data: bytes):
    import cv2
    import numpy as np

    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=422, detail="实时帧无法解码")
    return image


def _detect_realtime_frame(data: bytes, confidence: float) -> dict[str, Any]:
    detector = get_detector()
    custom = getattr(detector, "detect_frame", None)
    if callable(custom):
        with _inference_lock:
            result = custom(data, confidence)
        detections = list(result.get("detections") or [])
        return {
            "detections": detections,
            "summary": dict(result.get("summary") or _summary_from_detections(detections)),
        }
    frame = _decode_jpeg(data)
    with _inference_lock:
        results = detector.model(
            frame,
            conf=float(confidence),
            device=select_compute_device(),
            verbose=False,
        )
        detections, _ = _parse_model_results(detector, results)
    return {"detections": detections, "summary": _summary_from_detections(detections)}


def _session_identifier(value: str) -> str:
    session_id = value.strip()
    if not 1 <= len(session_id) <= 80 or not all(char.isalnum() or char in "-_" for char in session_id):
        raise HTTPException(status_code=422, detail="实时会话标识无效")
    return session_id


def _new_realtime_session(session_id: str) -> dict[str, Any]:
    now = time.time()
    return {
        "session_id": session_id,
        "processed_frames": 0,
        "observed_violations": 0,
        "stored_count": 0,
        "storage_errors": 0,
        "red_alert_sequence": 0,
        "last_error": None,
        "last_risk": "neutral",
        "notification_status": "idle",
        "notification_error": None,
        "retry_count": 0,
        "retry_at": 0.0,
        "created_at": now,
        "last_seen": now,
        "_last_event": {},
        "_inflight": set(),
        "_notification_queue": [],
        "_notification_timer": None,
        "_notification_inflight": False,
    }


def _public_realtime_session(session: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in session.items() if not key.startswith("_")}


def _notification_retry_delay(retry_count: int) -> float:
    """Return the 30/60/120 second capped retry delay."""
    index = max(0, min(int(retry_count) - 1, len(NOTIFICATION_RETRY_DELAYS) - 1))
    return NOTIFICATION_RETRY_DELAYS[index]


def _realtime_violation_summary(value: Any) -> str:
    """Turn the stored comma-separated violation types into a readable summary."""
    types = [item.strip() for item in str(value or "").split(",") if item.strip()]
    return "、".join(HazardDetector.LABEL_CN.get(item, item) for item in types)


def _realtime_notification_text(batch: dict[str, Any]) -> str:
    counts = Counter()
    record_ids = []
    for event in batch["events"]:
        record_ids.append(str(event["record_id"]))
        for violation in event.get("violations", []):
            counts[str(violation["violation_type"])] += int(violation["count"])
    details = "\n".join(
        f"- {HazardDetector.LABEL_CN.get(name, name)} × {count}"
        for name, count in counts.items()
    )
    return (
        f"实时隐患预警\n\n项目：{batch['project']}\n检查人：{batch['inspector']}\n"
        f"记录：#{'、#'.join(record_ids)}\n\n隐患明细：\n{details}\n\n"
        "请及时进入系统完成处置。"
    )


def _start_notification_timer_locked(session_id: str, delay: float) -> None:
    """Schedule one daemon retry worker. Caller must hold `_realtime_lock`."""
    state = _realtime_sessions.get(session_id)
    if (
        state is None
        or state.get("_notification_timer") is not None
        or state.get("_notification_inflight")
        or not state.get("_notification_queue")
    ):
        return
    timer = threading.Timer(delay, _notification_worker, args=(session_id,))
    timer.daemon = True
    state["_notification_timer"] = timer
    try:
        timer.start()
    except Exception:
        state["_notification_timer"] = None
        state["notification_status"] = "failed"
        state["notification_error"] = "通知重试任务无法启动"


def _enqueue_realtime_notification(
    session_id: str,
    project: str,
    inspector: str,
    events: list[dict[str, Any]],
) -> None:
    if not events:
        return
    batch = {
        "project": project,
        "inspector": inspector,
        "events": [dict(event) for event in events],
        "text_sent": False,
        "image_index": 0,
    }
    with _realtime_lock:
        state = _realtime_sessions.get(session_id)
        if state is None:
            return
        queue = state["_notification_queue"]
        was_empty = not queue
        queue.append(batch)
        if was_empty:
            state["notification_status"] = "queued"
            state["notification_error"] = None
            state["retry_count"] = 0
            state["retry_at"] = 0.0
        _start_notification_timer_locked(session_id, NOTIFICATION_INITIAL_DELAY)


def _notification_worker(session_id: str) -> None:
    """Send the first retained batch, retrying only the unfinished phase."""
    with _realtime_lock:
        state = _realtime_sessions.get(session_id)
        if state is None:
            return
        state["_notification_timer"] = None
        queue = state["_notification_queue"]
        if state.get("_notification_inflight") or not queue:
            return
        state["_notification_inflight"] = True
        if state["retry_count"]:
            state["notification_status"] = "retrying"
        batch = queue[0]
        state["retry_at"] = 0.0

    phase = "文字通知"
    try:
        if not batch["text_sent"]:
            dingtalk.send_text(_realtime_notification_text(batch), DINGTALK_CONFIG_PATH)
            with _realtime_lock:
                current = _realtime_sessions.get(session_id)
                if current is None or not current["_notification_queue"] or current["_notification_queue"][0] is not batch:
                    return
                batch["text_sent"] = True

        phase = "现场截图"
        while batch["image_index"] < len(batch["events"]):
            event = batch["events"][batch["image_index"]]
            dingtalk.send_image(event["snapshot_path"], DINGTALK_CONFIG_PATH)
            with _realtime_lock:
                current = _realtime_sessions.get(session_id)
                if current is None or not current["_notification_queue"] or current["_notification_queue"][0] is not batch:
                    return
                batch["image_index"] += 1
    except Exception:
        _LOG.warning("实时%s发送失败，已保留批次等待重试", phase)
        with _realtime_lock:
            state = _realtime_sessions.get(session_id)
            if state is None or not state["_notification_queue"] or state["_notification_queue"][0] is not batch:
                return
            state["_notification_inflight"] = False
            state["retry_count"] += 1
            delay = _notification_retry_delay(state["retry_count"])
            state["retry_at"] = time.time() + delay
            state["notification_status"] = "failed"
            state["notification_error"] = f"{phase}发送失败，系统将自动重试"
            _start_notification_timer_locked(session_id, delay)
        return

    with _realtime_lock:
        state = _realtime_sessions.get(session_id)
        if state is None or not state["_notification_queue"] or state["_notification_queue"][0] is not batch:
            return
        state["_notification_queue"].pop(0)
        state["_notification_inflight"] = False
        state["retry_count"] = 0
        state["retry_at"] = 0.0
        state["notification_error"] = None
        if state["_notification_queue"]:
            state["notification_status"] = "queued"
            _start_notification_timer_locked(session_id, NOTIFICATION_INITIAL_DELAY)
        else:
            state["notification_status"] = "sent"


@app.post("/api/realtime/frame")
async def realtime_frame(
    file: UploadFile = File(...),
    project_name: str = Form(...),
    inspector: str = Form(...),
    session: str = Form(...),
    confidence: float = Form(default=0.4, ge=0.1, le=0.95),
):
    project, checker = _clean_context(project_name, inspector)
    session_id = _session_identifier(session)
    data = await _read_upload(file, MAX_IMAGE_BYTES)
    _validate_image(data, jpeg_only=True)
    try:
        detection = _detect_realtime_frame(data, float(confidence))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="实时帧检测失败") from None
    detections = detection["detections"]
    summary = detection["summary"]
    risk = _risk_from_summary(summary)
    violations = Counter(
        str(item.get("label_en"))
        for item in detections
        if item.get("label_en") in {"no-helmet", "no-vest", "no-mask"}
    )
    now = time.time()
    with _realtime_lock:
        state = _realtime_sessions.setdefault(session_id, _new_realtime_session(session_id))
        state["processed_frames"] += 1
        state["last_seen"] = now
        state["last_risk"] = risk
        eligible = [
            violation_type for violation_type in violations
            if violation_type not in state["_inflight"]
            and now - float(state["_last_event"].get(violation_type, 0.0)) >= REALTIME_COOLDOWN_SECONDS
        ]
        state["observed_violations"] += sum(violations[item] for item in eligible)
        for violation_type in eligible:
            state["_last_event"][violation_type] = now
        state["_inflight"].update(eligible)
        audible_triggered = any(
            HazardDetector.ALERT_LEVELS.get(violation_type, ("yellow",))[0] == "red"
            for violation_type in eligible
        )
        if audible_triggered:
            state["red_alert_sequence"] += 1
        audible_sequence = int(state["red_alert_sequence"])
    stored_events = []
    notification_events = []
    detector = get_detector()
    if eligible:
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_path = SNAPSHOTS_DIR / (
            f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:10]}_realtime-incident.jpg"
        )
        violation_types = list(eligible)
        violation_details = [
            {"violation_type": violation_type, "count": int(violations[violation_type])}
            for violation_type in violation_types
        ]
        level = (
            "red"
            if any(HazardDetector.ALERT_LEVELS.get(item, ("yellow",))[0] == "red" for item in violation_types)
            else "yellow"
        )
        try:
            snapshot_path.write_bytes(data)
            record_id = get_database().save_realtime_violation(
                violation_type=",".join(violation_types),
                violation_count=sum(item["count"] for item in violation_details),
                level=level,
                snapshot_path=str(snapshot_path),
                project_name=project,
                inspector=checker,
                model_version=str(getattr(detector, "model_version", "未知")),
            )
        except Exception:
            snapshot_path.unlink(missing_ok=True)
            with _realtime_lock:
                state["storage_errors"] += 1
                state["last_error"] = "证据保存失败"
        else:
            with _realtime_lock:
                state["stored_count"] += 1
            stored_events.append({
                "record_id": int(record_id),
                "violation_types": violation_types,
                "violation_summary": _realtime_violation_summary(",".join(violation_types)),
                "risk": level,
                "evidence_url": _media_url_for_path(snapshot_path),
            })
            notification_events.append({
                "record_id": int(record_id),
                "violations": violation_details,
                "snapshot_path": str(snapshot_path),
            })
        finally:
            with _realtime_lock:
                for violation_type in eligible:
                    state["_inflight"].discard(violation_type)
    _enqueue_realtime_notification(
        session_id, project, checker, notification_events
    )
    with _realtime_lock:
        session_stats = _public_realtime_session(state)
    return {
        "session": session_stats,
        "detections": detections,
        "summary": summary,
        "risk": risk,
        "audible_alert": {
            "triggered": audible_triggered,
            "sequence": audible_sequence,
        },
        "stored_events": stored_events,
        "notification": {
            "status": session_stats["notification_status"] if stored_events else "not_needed"
        },
    }


@app.get("/api/realtime/sessions/{session_id}")
def get_realtime_session(session_id: str):
    normalized = _session_identifier(session_id)
    with _realtime_lock:
        state = _realtime_sessions.get(normalized)
        return _public_realtime_session(state or _new_realtime_session(normalized))


@app.delete("/api/realtime/sessions/{session_id}")
def reset_realtime_session(session_id: str):
    normalized = _session_identifier(session_id)
    with _realtime_lock:
        state = _realtime_sessions.pop(normalized, None)
        timer = state.get("_notification_timer") if state else None
        if timer is not None:
            timer.cancel()
    return _public_realtime_session(_new_realtime_session(normalized))


def _install_spa_routes():
    """Serve a built SPA after all API routes so `/api/*` always wins."""
    if not (FRONTEND_DIST / "index.html").is_file():
        return

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def spa(frontend_path: str):
        if frontend_path == "api" or frontend_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")
        requested = (FRONTEND_DIST / frontend_path).resolve()
        if frontend_path and _safe_relative(requested, FRONTEND_DIST) is not None and requested.is_file():
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")


_install_spa_routes()
