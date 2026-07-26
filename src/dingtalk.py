"""钉钉自定义机器人通知客户端。"""
import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "dingtalk.local.json"


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

    webhook = config.get("webhook", "").strip()
    secret = config.get("secret", "").strip()
    if not webhook or not secret:
        raise DingTalkError(f"请先填写配置文件中的 webhook 和 secret: {path}")
    if not webhook.startswith("https://oapi.dingtalk.com/robot/send?"):
        raise DingTalkError("webhook 格式不正确")
    if not secret.startswith("SEC"):
        raise DingTalkError("加签密钥应以 SEC 开头")
    return webhook, secret


def build_signed_url(webhook, secret, timestamp=None):
    timestamp = timestamp or int(time.time() * 1000)
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
    signature = quote_plus(base64.b64encode(digest).decode("utf-8"))
    separator = "&" if "?" in webhook else "?"
    return f"{webhook}{separator}timestamp={timestamp}&sign={signature}"


def send_text(text, config_path=DEFAULT_CONFIG_PATH, timeout=10):
    webhook, secret = load_config(config_path)
    payload = json.dumps({"msgtype": "text", "text": {"content": text}}, ensure_ascii=False).encode("utf-8")
    request = Request(
        build_signed_url(webhook, secret),
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise DingTalkError(f"请求钉钉失败: {exc}") from exc

    if result.get("errcode") != 0:
        raise DingTalkError(f"钉钉拒绝发送: {result.get('errmsg', result)}")
    return result
