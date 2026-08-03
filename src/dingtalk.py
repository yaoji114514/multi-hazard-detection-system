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
"""
import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "dingtalk.local.json"
_TOKEN_CACHE = {"token": None, "expires_at": 0}
_TOKEN_LOCK = threading.Lock()
_LOG = logging.getLogger("dingtalk_send")


class DingTalkError(RuntimeError):
    """钉钉配置或发送失败。"""


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
        name = str(item.get("name", "")).strip() or f"群-{wh.split('access_token=')[-1][:8]}"
        enabled = bool(item.get("enabled", True))
        items.append({"name": name, "webhook": wh, "enabled": enabled})
    if not items:
        raise DingTalkError(f"配置中未找到 webhook: {path}")
    return items


def load_config(config_path=DEFAULT_CONFIG_PATH):
    """读取配置，返回 (app_key, app_secret, 启用的群列表)。"""
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
    webhooks = _parse_webhooks(config.get("webhooks"), config.get("webhook"), path)
    enabled = [w for w in webhooks if w["enabled"]]
    if not enabled:
        raise DingTalkError(
            f"没有启用的机器人 webhook: {path}（请至少将一个群的 enabled 设为 true）")
    return app_key, app_secret, enabled


def list_webhooks(config_path=DEFAULT_CONFIG_PATH):
    """返回配置中全部群（含停用）的 {name, enabled, webhook}，供管理/界面使用。"""
    path = Path(config_path)
    if not path.exists():
        raise DingTalkError(f"配置文件不存在: {path}")
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    return _parse_webhooks(config.get("webhooks"), config.get("webhook"), path)


def get_access_token(config_path=DEFAULT_CONFIG_PATH, timeout=10):
    """用 app_key/app_secret 换取企业应用 access_token（用于上传媒体）。"""
    with _TOKEN_LOCK:
        now = time.time()
        if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"] - 60:
            return _TOKEN_CACHE["token"]
        app_key, app_secret, _ = load_config(config_path)
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
