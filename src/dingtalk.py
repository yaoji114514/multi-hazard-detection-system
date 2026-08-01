"""钉钉企业内部应用机器人客户端(access_token 模式)。"""
import base64
import hashlib
import json
import time
import threading
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "dingtalk.local.json"
_TOKEN_CACHE = {"token": None, "expires_at": 0}
_TOKEN_LOCK = threading.Lock()


class DingTalkError(RuntimeError):
    """钉钉配置或发送失败。"""


def load_config(config_path=DEFAULT_CONFIG_PATH):
    path = Path(config_path)
    if not path.exists():
        raise DingTalkError(f"配置文件不存在: {path}")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DingTalkError(f"无法读取钉钉配置: {exc}") from exc
    app_key = config.get("app_key", "").strip()
    app_secret = config.get("app_secret", "").strip()
    if not app_key or not app_secret:
        raise DingTalkError(f"请先填写配置文件中的 app_key 和 app_secret: {path}")
    return app_key, app_secret


def get_access_token(config_path=DEFAULT_CONFIG_PATH, timeout=10):
    with _TOKEN_LOCK:
        now = time.time()
        if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"] - 60:
            return _TOKEN_CACHE["token"]
        app_key, app_secret = load_config(config_path)
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


def _send(url, payload, timeout=10):
    access_token = get_access_token()
    req = Request(
        f"{url}?access_token={access_token}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise DingTalkError(f"请求钉钉失败: {exc}") from exc
    if result.get("errcode") != 0:
        raise DingTalkError(f"钉钉拒绝: {result.get('errmsg', result)}")
    return result


def send_text(text, config_path=DEFAULT_CONFIG_PATH, timeout=10):
    return _send("https://oapi.dingtalk.com/robot/send",
                 {"msgtype": "text", "text": {"content": text}}, timeout)


def send_markdown(title, text, config_path=DEFAULT_CONFIG_PATH, timeout=10):
    return _send("https://oapi.dingtalk.com/robot/send",
                 {"msgtype": "markdown", "markdown": {"title": title, "text": text}}, timeout)


def send_image(image_path, config_path=DEFAULT_CONFIG_PATH, timeout=15):
    _LOG = __import__("logging").getLogger("dingtalk_send")
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
    upload_req = Request(upload_url, data=body,
                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
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
    return _send("https://oapi.dingtalk.com/robot/send",
                 {"msgtype": "image", "image": {"media_id": media_id}}, timeout)
