"""钉钉企业内部应用机器人客户端。

发送链路（已实测验证）：
- 文字/markdown：直接 POST 到机器人 webhook（robot/send?access_token=<webhook token>）。
- 图片：先用 app_key/app_secret 换取 access_token 并上传媒体拿 media_id，
  再 POST 一条 markdown 消息，用 `![图片说明](media_id)` 嵌入图片（普通大图显示；
  直接发 msgtype=image 会显示为表情包，已弃用）。

多群白名单：
- 配置支持 `webhooks` 列表，每个群一条记录：{"name": 群名, "webhook": URL, "enabled": 布尔}。
- 只向 enabled=true 的群发送；某群改为 false 即临时停用，机器人无需退出该群。
- 某个群发送失败不影响其他群（失败会记录日志，全部失败才抛异常）。

群名验证：
- webhook 不能反查群名。用户在钉钉微应用/小程序中选群后，可手工绑定
  `open_conversation_id`，再由企业内部应用查询场景群标题。
- 查询只影响管理界面的名称来源，不影响原有文字、markdown 或图片通知。
"""
import hashlib
import json
import logging
import socket
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "dingtalk.local.json"
_TOKEN_CACHE = {"token": None, "expires_at": 0}
_TOKEN_LOCK = threading.Lock()
GROUP_INFO_CACHE_TTL = 300
_GROUP_INFO_CACHE = {}
_GROUP_INFO_LOCK = threading.Lock()
_SCENE_GROUP_INFO_URL = "https://oapi.dingtalk.com/topapi/im/chat/scenegroup/get"
_LOG = logging.getLogger("dingtalk_send")


class DingTalkError(RuntimeError):
    """钉钉配置或发送失败。"""


def webhook_short_id(webhook):
    """为 webhook 生成可展示的稳定短标识，不暴露 access_token。"""
    normalized = str(webhook or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8].upper()


def _parse_webhooks(webhooks, legacy_webhook, path):
    if webhooks is None:
        webhooks = []
        wh = str(legacy_webhook or "").strip()
        if wh:
            webhooks = [{"name": "默认群", "webhook": wh, "enabled": True}]
    items = []
    for item in webhooks:
        wh = str(item.get("webhook", "")).strip()
        if not wh:
            continue
        if not wh.startswith("https://oapi.dingtalk.com/robot/send?"):
            raise DingTalkError(
                f"webhook 格式不正确（应以 https://oapi.dingtalk.com/robot/send? 开头）: {path}")
        configured_name = str(item.get("name", "")).strip()
        open_conversation_id = str(item.get("open_conversation_id", "")).strip()
        name = configured_name or "未命名群"
        enabled = bool(item.get("enabled", True))
        items.append({
            "name": name,
            "webhook": wh,
            "enabled": enabled,
            "short_id": webhook_short_id(wh),
            "name_configured": bool(configured_name),
            "open_conversation_id": open_conversation_id,
        })
    if not items:
        raise DingTalkError(f"配置中未找到 webhook: {path}")
    return items


def _load_app_credentials(config_path):
    """读取企业应用凭据，不要求存在已启用的通知群。"""
    path = Path(config_path)
    if not path.exists():
        raise DingTalkError(f"配置文件不存在: {path}")
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DingTalkError(f"无法读取钉钉配置: {exc}") from exc
    app_key = str(config.get("app_key", "")).strip()
    app_secret = str(config.get("app_secret", "")).strip()
    if not app_key or not app_secret:
        raise DingTalkError(f"请先填写配置文件中的 app_key 和 app_secret: {path}")
    return app_key, app_secret


def load_config(config_path=DEFAULT_CONFIG_PATH):
    """读取配置，返回 (app_key, app_secret, 启用的群列表)。"""
    path = Path(config_path)
    app_key, app_secret = _load_app_credentials(path)
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DingTalkError(f"无法读取钉钉配置: {exc}") from exc
    webhooks = _parse_webhooks(config.get("webhooks"), config.get("webhook"), path)
    enabled = [w for w in webhooks if w["enabled"]]
    if not enabled:
        raise DingTalkError(
            f"没有启用的机器人 webhook: {path}（请至少将一个群的 enabled 设为 true）")
    return app_key, app_secret, enabled


def list_webhooks(config_path=DEFAULT_CONFIG_PATH):
    """返回全部群及安全短标识，供管理界面区分同名群。"""
    path = Path(config_path)
    if not path.exists():
        raise DingTalkError(f"配置文件不存在: {path}")
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    return _parse_webhooks(config.get("webhooks"), config.get("webhook"), path)


def clear_group_identity_cache():
    """清空群名查询缓存，供测试或配置切换后显式调用。"""
    with _GROUP_INFO_LOCK:
        _GROUP_INFO_CACHE.clear()


def _group_identity_result(status, *, source="local", official_name="", reason=""):
    """构造不会泄露会话 ID、token 或原始接口错误的查询结果。"""
    return {
        "status": status,
        "source": source,
        "official_name": official_name,
        "reason": reason,
        "checked_at": time.time(),
    }


def _group_info_failure_result(exc):
    """将底层异常归类为可展示的脱敏状态。"""
    if isinstance(exc, HTTPError):
        if exc.code in (401, 403):
            return _group_identity_result("permission_denied", reason="群信息查询权限不足")
        return _group_identity_result("unavailable", reason="钉钉群信息接口暂不可用")
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return _group_identity_result("timeout", reason="群信息查询超时")
    if isinstance(exc, URLError):
        return _group_identity_result("network_error", reason="网络不可用，暂时无法验证")
    if isinstance(exc, DingTalkError):
        return _group_identity_result("unavailable", reason="钉钉身份验证暂不可用")
    return _group_identity_result("unavailable", reason="暂时无法验证群名")


def resolve_group_identity(group, config_path=DEFAULT_CONFIG_PATH, *, refresh=False, timeout=5):
    """查询已绑定群的官方标题，失败时返回脱敏的可解释状态。

    此函数不发送任何钉钉消息，也不会修改群或本地配置。结果按配置路径和
    会话 ID 的摘要缓存；传入 ``refresh=True`` 可绕过缓存主动重试。
    """
    open_conversation_id = str(group.get("open_conversation_id", "")).strip()
    if not open_conversation_id:
        return _group_identity_result("unbound", reason="尚未绑定钉钉会话 ID")

    path = Path(config_path)
    cache_key = (str(path.resolve()), hashlib.sha256(
        open_conversation_id.encode("utf-8")
    ).hexdigest())
    now = time.time()
    if not refresh:
        with _GROUP_INFO_LOCK:
            cached = _GROUP_INFO_CACHE.get(cache_key)
            if cached and now < cached["expires_at"]:
                return dict(cached["result"])

    try:
        access_token = get_access_token(path, timeout)
        request = Request(
            f"{_SCENE_GROUP_INFO_URL}?{urlencode({'access_token': access_token})}",
            data=json.dumps(
                {"open_conversation_id": open_conversation_id}, ensure_ascii=False
            ).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        result = _group_info_failure_result(exc)
    else:
        if not isinstance(payload, dict):
            result = _group_identity_result(
                "api_error", reason="钉钉群信息接口返回异常数据"
            )
        elif payload.get("errcode") not in (None, 0) or payload.get("success") is False:
            if payload.get("errcode") == 400020:
                result = _group_identity_result(
                    "permission_denied", reason="群信息查询权限不足"
                )
            else:
                result = _group_identity_result(
                    "api_error", reason="钉钉群信息接口拒绝了查询"
                )
        else:
            title = str((payload.get("result") or {}).get("title", "")).strip()
            if title:
                result = _group_identity_result(
                    "verified", source="dingtalk", official_name=title
                )
            else:
                result = _group_identity_result(
                    "empty_title", reason="钉钉未返回可用的群名称"
                )

    with _GROUP_INFO_LOCK:
        _GROUP_INFO_CACHE[cache_key] = {
            "expires_at": now + GROUP_INFO_CACHE_TTL,
            "result": dict(result),
        }
    return result


def get_access_token(config_path=DEFAULT_CONFIG_PATH, timeout=10):
    """用 app_key/app_secret 换取企业应用 access_token（用于上传媒体）。"""
    with _TOKEN_LOCK:
        now = time.time()
        if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"] - 60:
            return _TOKEN_CACHE["token"]
        app_key, app_secret = _load_app_credentials(config_path)
        url = f"https://oapi.dingtalk.com/gettoken?appkey={app_key}&appsecret={app_secret}"
        try:
            with urlopen(Request(url, method="GET"), timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise DingTalkError(f"获取 access_token 失败: {exc}") from exc
        if result.get("errcode") != 0:
            raise DingTalkError(f"获取 token 被拒: {result.get('errmsg', result)}")
        _TOKEN_CACHE["token"] = result["access_token"]
        _TOKEN_CACHE["expires_at"] = now + result.get("expires_in", 7200)
        return _TOKEN_CACHE["token"]


def _send(payload, config_path=DEFAULT_CONFIG_PATH, timeout=10):
    """向所有启用的群发送；单个群失败只记录日志，全部失败才抛异常。"""
    _, _, webhooks = load_config(config_path)
    results, errors = [], []
    for w in webhooks:
        name, webhook = w["name"], w["webhook"]
        req = Request(
            webhook,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            if result.get("errcode") != 0:
                raise DingTalkError(f"钉钉拒绝: {result.get('errmsg', result)}")
            results.append((name, result))
            _LOG.info("sent ok -> %s (errcode=%s)", name, result.get("errcode"))
        except Exception as exc:
            errors.append((name, exc))
            _LOG.error("send FAILED -> %s: %s", name, exc)
    if not results and errors:
        raise DingTalkError(f"所有群发送失败: {errors[0][0]} -> {errors[0][1]}")
    return results


def send_text(text, config_path=DEFAULT_CONFIG_PATH, timeout=10):
    return _send({"msgtype": "text", "text": {"content": text}}, config_path, timeout)


def send_markdown(title, text, config_path=DEFAULT_CONFIG_PATH, timeout=10):
    return _send(
        {"msgtype": "markdown", "markdown": {"title": title, "text": text}},
        config_path, timeout)


def send_image(image_path, config_path=DEFAULT_CONFIG_PATH, timeout=15):
    """上传图片拿 media_id（一次上传），再向所有启用群发 markdown 嵌入图片。"""
    # 保留原有“没有启用群则不上传”的行为；群名查询本身不受此限制。
    load_config(config_path)
    access_token = get_access_token(config_path, timeout)
    with open(image_path, "rb") as f:
        img_data = f.read()
    boundary = "----Up" + hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    body = b""
    body += f"--{boundary}\r\n".encode("utf-8")
    body += b"Content-Disposition: form-data; name=\"media\"; filename=\"crop.jpg\"\r\n"
    body += b"Content-Type: image/jpeg\r\n\r\n"
    body += img_data
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")
    upload_url = f"https://oapi.dingtalk.com/media/upload?access_token={access_token}&type=image"
    upload_req = Request(
        upload_url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(upload_req, timeout=timeout) as resp:
            upload_result = json.loads(resp.read().decode("utf-8"))
        _LOG.info("media upload: errcode=%s", upload_result.get("errcode"))
    except Exception as exc:
        _LOG.exception("media upload FAILED")
        raise DingTalkError(f"上传图片失败: {exc}") from exc
    if upload_result.get("errcode") != 0:
        raise DingTalkError(f"上传被拒: {upload_result.get('errmsg', upload_result)}")
    media_id = upload_result.get("media_id", "")
    if not media_id:
        raise DingTalkError("未获取到 media_id")
    return _send(
        {"msgtype": "markdown",
         "markdown": {"title": "违规图片", "text": f"![违规图片]({media_id})"}},
        config_path, timeout)
