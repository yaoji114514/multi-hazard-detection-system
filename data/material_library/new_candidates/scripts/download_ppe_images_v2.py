# -*- coding: utf-8 -*-
"""
工地工人PPE图片下载器 v2
改用 Bing Images 直接 HTML 抓取（免费、无需 API key）
"""
import hashlib, os, re, sys, time, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from urllib.parse import quote, urlparse

import requests
from PIL import Image

RAW_DIR = Path(__file__).resolve().parents[2] / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# 搜索词（中英文覆盖）
SEARCH_QUERIES = [
    "construction worker wearing mask hardhat safety vest",
    "工地工人 安全帽 反光衣 口罩 实拍",
    "construction site worker with face mask and safety gear",
    "建筑工地 工人 PPE 防护用品",
    "worker with hardhat mask reflective vest construction",
    "工地 施工人员 佩戴口罩 安全帽",
    "construction worker full PPE helmet mask vest",
    "工事現場 安全帽 マスク 作業員",
    "worker wearing safety helmet mask and reflective vest",
    "construction site safety equipment real photo",
]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
}


def extract_bing_images(query, num=40):
    """从 Bing Images 搜索页提取图片 URL"""
    url = f"https://www.bing.com/images/search?q={quote(query)}&count={num}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [BING] {query[:30]}... 请求失败: {e}")
        return []

    # 从 HTML 中提取图片 URL（Bing 的图片放在 mimg 属性或 data-src 中）
    img_urls = set()
    # 尝试多种属性
    for attr in ['src', 'data-src', 'murl', 'iurl']:
        pattern = rf'{attr}\s*=\s*["\']([^"\'\s]+)["\']'
        for m in re.finditer(pattern, resp.text, re.I):
            url_str = m.group(1)
            if url_str.startswith("//"):
                url_str = "https:" + url_str
            if not url_str.startswith(("http://", "https://")):
                continue
            # 过滤小图标
            if re.search(r'(icon|logo|banner|avatar|pixel|spacer|\.svg|\.gif)', url_str, re.I):
                continue
            # 过滤 data: URI
            if url_str.startswith("data:"):
                continue
            img_urls.add(url_str)

    results = list(img_urls)
    print(f"  [BING] '{query[:30]}...' -> {len(results)} 个图片链接")
    return results


# 下载 + 去重
_seen_hashes = set()


def download_one(url, timeout=30):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
        resp.raise_for_status()
        content = resp.content
        if len(content) < 4096:
            return None, "too small"
        h = hashlib.md5(content).hexdigest()
        if h in _seen_hashes:
            return None, "duplicate"
        _seen_hashes.add(h)

        try:
            img = Image.open(BytesIO(content))
            w, h_img = img.size
            if w < 300 or h_img < 300:
                return None, f"small {w}x{h_img}"
            if img.mode != "RGB":
                img = img.convert("RGB")
        except Exception:
            return None, "corrupt"

        fpath = RAW_DIR / f"{h[:16]}.jpg"
        img.save(fpath, "JPEG", quality=92)
        return str(fpath), None
    except Exception as e:
        return None, str(e)[:60]


def download_all(urls, max_downloads=50, workers=6):
    downloaded = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_map = {pool.submit(download_one, url): url for url in urls}
        for fut in as_completed(fut_map):
            fpath, err = fut.result()
            if fpath:
                downloaded.append(fpath)
                sys.stdout.write(f"\r  [{len(downloaded)}/{max_downloads}] ok")
                sys.stdout.flush()
            else:
                if err and err != "duplicate":
                    pass  # 静默跳过失败
            if len(downloaded) >= max_downloads:
                for f in fut_map:
                    if not f.done():
                        f.cancel()
                break
    print()
    return downloaded


def main():
    target = 50

    # Step 1: Bing 搜索收集 URL
    all_urls = []
    for q in SEARCH_QUERIES[:6]:
        urls = extract_bing_images(q, num=30)
        all_urls.extend(urls)
        time.sleep(1)

    # 去重
    all_urls = list(dict.fromkeys(all_urls))
    print(f"\n总计 {len(all_urls)} 个不重复 URL，开始下载...\n")

    # Step 2: 下载
    if all_urls:
        result = download_all(all_urls, max_downloads=target, workers=6)
    else:
        print("没有找到图片链接")
        result = []

    # Step 3: 报告
    jpegs = sorted(RAW_DIR.glob("*.jpg"))
    total_size = sum(f.stat().st_size for f in jpegs) / (1024 * 1024)
    print(f"\n{'='*50}")
    print(f"下载完成: {len(result)} 张 | 目录总计: {len(jpegs)} 张")
    print(f"总大小: {total_size:.1f} MB")
    print(f"保存路径: {RAW_DIR}")


if __name__ == "__main__":
    main()
