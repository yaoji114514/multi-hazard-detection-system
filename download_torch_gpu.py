"""
torch + torchvision wheel 下载脚本(支持断点续传)
用法: python download_torch_gpu.py
下载到 data/wheels/ 目录,下完后用 pip install 本地文件
"""
import os
import sys
import time
import urllib.request
from pathlib import Path

WHEELS = [
    {
        "url": "https://download.pytorch.org/whl/cu124/torch-2.6.0%2Bcu124-cp313-cp313-win_amd64.whl",
        "filename": "torch-2.6.0+cu124-cp313-cp313-win_amd64.whl",
        "size_mb": 2532,
    },
    {
        "url": "https://download.pytorch.org/whl/cu124/torchvision-0.21.0%2Bcu124-cp313-cp313-win_amd64.whl",
        "filename": "torchvision-0.21.0+cu124-cp313-cp313-win_amd64.whl",
        "size_mb": 7,
    },
]

DEST_DIR = Path(__file__).parent / "data" / "wheels"
DEST_DIR.mkdir(parents=True, exist_ok=True)
CHUNK = 1024 * 1024  # 1MB per chunk


def download_with_resume(url, filename, expected_size_mb):
    """支持断点续传的下载"""
    dest = DEST_DIR / filename
    tmp = dest.with_suffix(".whl.part")  # 临时文件,下完才改名

    # 检查已下载的大小
    if tmp.exists():
        current_size = tmp.stat().st_size
        mode = "ab"  # 追加模式
        print(f"  续传: {filename} 已有 {current_size / 1024 / 1024:.1f} MB, 从该位置继续")
    else:
        current_size = 0
        mode = "wb"
        print(f"  新建: {filename} 从头下载")

    # 如果完整文件已存在,跳过
    if dest.exists():
        print(f"  跳过: {filename} 已存在完整文件")
        return True

    # 获取文件总大小
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
    except Exception:
        total_size = expected_size_mb * 1024 * 1024  # 用预期大小兜底

    if current_size > 0 and total_size > 0 and current_size >= total_size:
        # 已下完,改名
        tmp.rename(dest)
        print(f"  完成: {filename} (续传文件已完整,直接改名)")
        return True

    # 带 Range 的下载
    headers = {}
    if current_size > 0:
        headers["Range"] = f"bytes={current_size}-"

    req = urllib.request.Request(url, headers=headers)
    last_print = time.time()
    last_size = current_size
    downloaded_this_session = 0

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            http_status = resp.status
            if current_size > 0 and http_status != 206:
                print(f"  警告: 服务器不支持续传(HTTP {http_status}),从头下载")
                current_size = 0
                mode = "wb"

            with open(tmp, mode) as f:
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
                    current_size += len(chunk)
                    downloaded_this_session += len(chunk)

                    # 每 5 秒打印一次进度
                    now = time.time()
                    if now - last_print >= 5:
                        speed = (current_size - last_size) / (now - last_print) / 1024
                        if total_size > 0:
                            pct = current_size / total_size * 100
                            print(f"  进度: {current_size / 1024 / 1024:.1f}/{total_size / 1024 / 1024:.1f} MB ({pct:.1f}%) | 速度: {speed:.0f} KB/s", flush=True)
                        else:
                            print(f"  进度: {current_size / 1024 / 1024:.1f} MB | 速度: {speed:.0f} KB/s", flush=True)
                        last_print = now
                        last_size = current_size

        # 下载完成,改名
        if total_size > 0 and current_size >= total_size:
            tmp.rename(dest)
            print(f"  完成: {filename} ({current_size / 1024 / 1024:.1f} MB)")
            return True
        elif total_size == 0 and downloaded_this_session > 0:
            # 没有总大小信息,但下载了一些数据,假设完成
            tmp.rename(dest)
            print(f"  完成(无总大小): {filename} ({current_size / 1024 / 1024:.1f} MB)")
            return True
        else:
            print(f"  未完成: {filename} 当前 {current_size / 1024 / 1024:.1f} MB (预期 {total_size / 1024 / 1024:.1f} MB)")
            return False

    except Exception as e:
        print(f"  中断: {filename} 已下 {current_size / 1024 / 1024:.1f} MB, 错误: {type(e).__name__}: {e}")
        print(f"  (部分文件已保留,重跑此脚本可从断点续传)")
        return False


def main():
    print("=" * 60)
    print("torch GPU 版 wheel 下载(支持断点续传)")
    print("=" * 60)
    print(f"下载目录: {DEST_DIR}")
    print()

    all_ok = True
    for w in WHEELS:
        print(f"--- 下载 {w['filename']} (预期 {w['size_mb']} MB) ---")
        ok = download_with_resume(w["url"], w["filename"], w["size_mb"])
        if not ok:
            all_ok = False
        print()

    if all_ok:
        print("=" * 60)
        print("全部下载完成! 现在可以本地安装:")
        print("=" * 60)
        print()
        print("安装命令:")
        for w in WHEELS:
            print(f'  .venv\\Scripts\\pip.exe install "{DEST_DIR / w["filename"]}"')
        print()
        print("或一键安装:")
        files = " ".join(f'"{DEST_DIR / w["filename"]}"' for w in WHEELS)
        print(f"  .venv\\Scripts\\pip.exe install {files}")
        return 0
    else:
        print("=" * 60)
        print("部分文件未下完,请重跑此脚本继续下载(支持断点续传)")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
