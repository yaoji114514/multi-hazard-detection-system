"""发送一条独立的钉钉机器人测试预警。"""
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dingtalk import DingTalkError, send_text


def main():
    message = "\n".join([
        "隐患预警 - 通信测试",
        "",
        "等级：红色预警",
        "项目：示范项目",
        "隐患：未佩戴安全帽（测试消息）",
        f"时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        "要求：立即停工整改",
        "",
        "本消息由多类隐患检测系统自动发送",
    ])
    try:
        send_text(message)
    except DingTalkError as exc:
        print(f"[失败] {exc}")
        return 1
    print("[成功] 钉钉已接受测试消息，请检查手机通知。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
