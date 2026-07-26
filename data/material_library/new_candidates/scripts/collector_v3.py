# -*- coding: utf-8 -*-
""" 
PPE Image Collector v3
Strategy:
1. Unsplash HTML scraping (direct page access)
2. Also try raw image URLs from known free sources
"""
import hashlib, re, sys, time, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from urllib.parse import quote, urljoin

import requests
from PIL import Image

RAW_DIR = Path(__file__).resolve().parents[2] / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = RAW_DIR / "_sources.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    "Referer": "https://www.google.com/",
}

QUERIES = [
    "construction worker mask helmet safety vest",
    "construction worker PPE full body",
    "建筑工人 安全帽 口罩 反光衣",
    "工地 施工人员 防护装备",
    "worker wearing hardhat mask vest",
]


def search_unsplash(query, max_images=30):
    """从 Unsplash 搜索结果页面提取高清图片链接"""
    results = []
    url = f"https://unsplash.com/s/photos/{quote(query)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  [UNSPLASH] {r.status_code} for {query[:30]}")
            return results
        
        # Unsplash 用 JSON 数据嵌入在页面中
        for m in re.finditer(r'<img[^>]+src="([^"]+)"[^>]*>', r.text):
            src = m.group(1)
            if "images.unsplash.com" in src and "profile" not in src and "avatar" not in src \
               and "badge" not in src and "gallery" not in src:
                # 从 src 中提取 base URL
                base = src.split("?")[0] if "?" in src else src
                # 用 w=1080 获取高清版
                results.append(f"{base}?w=1080&q=80")
                if len(results) >= max_images:
                    break
        
        print(f"  [UNSPLASH] '{query[:30]}': {len(results)} 张")
    except Exception as e:
        print(f"  [UNSPLASH] Error: {e}")
    
    return results


def search_pexels_html(query, max_images=30):
    """从 Pexels 搜索结果页提取图片"""
    results = []
    url = f"https://www.pexels.com/search/{quote(query)}/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return results
        
        for m in re.finditer(r'<img[^>]+srcset="([^"]+)"', r.text):
            srcset = m.group(1)
            # 取最大分辨率
            parts = srcset.split(",")
            best = parts[-1].strip().split(" ")[0]
            if best.startswith("http") and ".pexels.com" in best:
                results.append(best)
        
        print(f"  [PEXELS] '{query[:30]}': {len(results)} 张")
    except Exception as e:
        print(f"  [PEXELS] Error: {e}")
    
    return results[:max_images]


# 下载引擎
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
            return None, "dup"
        _seen_hashes.add(h)
        img = Image.open(BytesIO(content))
        w, h_img = img.size
        if w < 300 or h_img < 300:
            return None, f"small {w}x{h_img}"
        if img.mode != "RGB":
            img = img.convert("RGB")
        fpath = RAW_DIR / f"{h[:16]}.jpg"
        img.save(fpath, "JPEG", quality=92)
        return str(fpath), None
    except Exception as e:
        return None, str(e)[:50]


def download_all(urls, max_downloads=50, workers=6):
    downloaded = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_map = {pool.submit(download_one, url): url for url in urls}
        for fut in as_completed(fut_map):
            fpath, err = fut.result()
            if fpath:
                downloaded.append(fpath)
            if len(downloaded) >= max_downloads:
                for f in fut_map:
                    if not f.done():
                        f.cancel()
                break
    return downloaded


def main():
    target = 50
    all_urls = []
    
    for q in QUERIES:
        urls = search_unsplash(q)
        all_urls.extend(urls)
        time.sleep(1)
        urls2 = search_pexels_html(q)
        all_urls.extend(urls2)
        time.sleep(1)
    
    all_urls = list(dict.fromkeys(all_urls))
    print(f"\n总计 {len(all_urls)} 个不重复 URL")
    
    if all_urls:
        result = download_all(all_urls, max_downloads=target, workers=6)
        print(f"下载成功: {len(result)} 张")
    else:
        print("未找到任何图片")
    
    jpegs = sorted(RAW_DIR.glob("*.jpg"))
    total_size = sum(f.stat().st_size for f in jpegs) / (1024 * 1024)
    print(f"\n目录总计: {len(jpegs)} 张, {total_size:.1f} MB")
    print(f"路径: {RAW_DIR}")
    
    # 保存来源记录
    json.dump({"sources": list(all_urls)}, open(LOG_PATH, "w"))


if __name__ == "__main__":
    main()
