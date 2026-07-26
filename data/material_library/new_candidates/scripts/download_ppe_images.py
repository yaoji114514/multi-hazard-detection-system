"""
工地工人PPE图片下载器
目标：获取工地工人佩戴安全帽+反光衣+口罩的真实照片
来源：多源混合策略
"""
import hashlib
import os
import sys
import time
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
from PIL import Image

# ── 配置 ──────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).resolve().parents[2] / "new_candidates" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = RAW_DIR / "_download_log.json"

# 搜索词组合（覆盖中文和英文场景）
SEARCH_QUERIES = [
    # 英文 - 核心场景
    "construction worker wearing mask hardhat safety vest",
    "construction site worker face mask reflective vest helmet",
    "工地工人 安全帽 反光衣 口罩",
    "worker with PPE mask helmet construction site",
    "建筑工地 工人 佩戴口罩 安全帽",
    # 扩展场景
    "construction worker safety equipment full PPE",
    "工地 安全施工 防护用品 实拍",
    "workers on construction site with masks and hardhats",
    "building site worker with face mask and safety gear",
    "工事現場 作業員 マスク ヘルメット",
]

# 多源下载函数集合
DOWNLOAD_SOURCES = []


# ═══════════════════════════════════════════════════════════════
#  Source 1: 从网页 HTML 中提取图片（通用 fallback）
# ═══════════════════════════════════════════════════════════════
def _download_from_html_page(url, query, min_width=300):
    """从普通网页提取图片（用于没有 API 的图片站点）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [SKIP] 无法访问 {url}: {e}")
        return []

    # 用简单正则提取图片 URL
    import re
    img_urls = set()
    # 匹配 <img src="...">
    for m in re.finditer(r'<img[^>]+src\s*=\s*["\']([^"\']+)["\']', resp.text, re.I):
        url_str = m.group(1)
        if url_str.startswith("//"):
            url_str = "https:" + url_str
        elif url_str.startswith("/"):
            parsed = urlparse(url)
            url_str = f"{parsed.scheme}://{parsed.netloc}{url_str}"
        elif not url_str.startswith(("http://", "https://")):
            continue
        # 过滤小图标/logo
        if re.search(r'(icon|logo|banner|avatar|thumb|pixel|spacer|blank)', url_str, re.I):
            continue
        if re.search(r'\.(svg|gif|ico)$', url_str, re.I):
            continue
        img_urls.add(url_str)

    print(f"  [HTML] {url} → 发现 {len(img_urls)} 个图片链接")
    return list(img_urls)[:30]  # 最多取 30 张


# ═══════════════════════════════════════════════════════════════
#  Source 2: Wikipedia Commons / 搜索引擎直接构造
# ═══════════════════════════════════════════════════════════════
def _build_google_image_url(query, num=20):
    """构造 Google Images 搜索 URL（免费、无需 API）"""
    from urllib.parse import quote
    base = "https://www.google.com/search"
    params = f"?q={quote(query)}&tbm=isch&tbs=isz:l&num={num}"
    return base + params


def _build_bing_image_url(query, num=20):
    from urllib.parse import quote
    return f"https://www.bing.com/images/search?q={quote(query)}&count={num}"

# ═══════════════════════════════════════════════════════════════
#  Source 3: Unsplash 直接源（无需 API key）
# ═══════════════════════════════════════════════════════════════
def _download_unsplash(query, per_page=15, pages=2):
    """从 Unsplash 搜索下载"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36"
    }
    collected = []
    for page in range(1, pages + 1):
        url = (
            f"https://unsplash.com/napi/search/photos"
            f"?query={requests.utils.quote(query)}"
            f"&per_page={per_page}&page={page}&xp="
        )
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"  [UNSPLASH] page {page} returned {resp.status_code}")
                continue
            data = resp.json()
            for item in data.get("results", []):
                img_url = item.get("urls", {}).get("raw")
                if img_url:
                    # 添加参数控制分辨率为 1080p
                    img_url = img_url + "&w=1080&q=85"
                    collected.append(img_url)
            print(f"  [UNSPLASH] page {page}: +{len(data.get('results',[]))} 张")
        except Exception as e:
            print(f"  [UNSPLASH] page {page} 错误: {e}")
        time.sleep(0.5)
    return collected


# ═══════════════════════════════════════════════════════════════
#  Source 4: Pexels
# ═══════════════════════════════════════════════════════════════
def _download_pexels(query, per_page=15, pages=2, api_key=None):
    """从 Pexels 搜索下载（免费 API，无需 key 也可访问搜索页）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36"
    }
    if api_key:
        headers["Authorization"] = api_key

    collected = []
    for page in range(1, pages + 1):
        url = ("https://api.pexels.com/v1/search"
               f"?query={requests.utils.quote(query)}"
               f"&per_page={per_page}&page={page}&size=large")
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"  [PEXELS] page {page} returned {resp.status_code}")
                # fallback: 搜索页HTML
                html_url = ("https://www.pexels.com/search/"
                            f"{requests.utils.quote(query)}/?size=large")
                print(f"  [PEXELS] fallback to HTML: {html_url}")
                urls = _download_from_html_page(html_url, query)
                collected.extend(urls)
                continue
            data = resp.json()
            for item in data.get("photos", []):
                src = item.get("src", {}).get("large2x") or item.get("src", {}).get("original")
                if src:
                    collected.append(src)
            print(f"  [PEXELS] page {page}: +{len(data.get('photos',[]))} 张")
        except Exception as e:
            print(f"  [PEXELS] page {page} 错误: {e}")
        time.sleep(0.5)
    return collected


# ═══════════════════════════════════════════════════════════════
#  下载 + 验证 + 去重
# ═══════════════════════════════════════════════════════════════
_seen_hashes = set()  # 全局去重


def _download_single(url, timeout=30):
    """下载一张图片并返回 (filepath, error)"""
    try:
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36"
        }, timeout=timeout, stream=True)
        resp.raise_for_status()
        content = resp.content
        if len(content) < 4096:
            return None, "too small"

        # 内容 hash 去重
        h = hashlib.md5(content).hexdigest()
        if h in _seen_hashes:
            return None, "duplicate"
        _seen_hashes.add(h)

        # 用 PIL 验证可打开
        from io import BytesIO
        try:
            img = Image.open(BytesIO(content))
            w, h_img = img.size
            if w < 300 or h_img < 300:
                return None, f"too small ({w}x{h_img})"
            # 转 RGB 保存为 JPEG
            if img.mode not in ("RGB",):
                img = img.convert("RGB")
        except Exception:
            return None, "corrupt image"

        # 保存
        fname = f"{h[:16]}.jpg"
        fpath = RAW_DIR / fname
        with open(fpath, "wb") as f:
            img.save(f, "JPEG", quality=92)
        return str(fpath), None
    except Exception as e:
        return None, str(e)


def download_all(urls, max_downloads=50, workers=4):
    """并发下载 URL 列表，直到达到 max_downloads"""
    downloaded = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_to_url = {pool.submit(_download_single, url): url for url in urls}
        done = 0
        for fut in as_completed(fut_to_url):
            url = fut_to_url[fut]
            done += 1
            fpath, err = fut.result()
            if fpath:
                downloaded.append(fpath)
                print(f"  [{len(downloaded)}/{max_downloads}] ✔ {Path(fpath).name}")
            else:
                print(f"  [  ] ✘ {url[:60]}... → {err}")
            if len(downloaded) >= max_downloads:
                # 取消剩余任务
                for f in fut_to_url:
                    if not f.done():
                        f.cancel()
                break
    return downloaded


# ═══════════════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════════════
def main():
    target = 50
    print(f"=" * 60)
    print(f"工地PPE图片下载器 | 目标: {target} 张")
    print(f"保存到: {RAW_DIR}")
    print(f"=" * 60)

    # 1. 从 Unsplash 获取
    all_urls = []
    for q in SEARCH_QUERIES[:4]:  # 前4个查询
        print(f"\n--- Unsplash: {q}")
        try:
            urls = _download_unsplash(q, per_page=15, pages=1)
            all_urls.extend(urls)
        except Exception as e:
            print(f"  [ERROR] {e}")

    # 2. Pexels
    for q in SEARCH_QUERIES[:3]:
        print(f"\n--- Pexels: {q}")
        try:
            urls = _download_pexels(q, per_page=15, pages=1)
            all_urls.extend(urls)
        except Exception as e:
            print(f"  [ERROR] {e}")

    # 3. 去重 URL
    all_urls = list(dict.fromkeys(all_urls))  # 保持顺序去重
    print(f"\n共收集 {len(all_urls)} 个不重复图片 URL，开始下载...\n")

    # 4. 下载
    if all_urls:
        result = download_all(all_urls, max_downloads=target, workers=6)
        print(f"\n✔ 下载完成: {len(result)} 张图片保存到 {RAW_DIR}")
    else:
        print("\n⚠ 没有找到任何图片 URL，尝试备用 HTML 下载...")
        # 备用：直接 HTML 抓取
        fallback_urls = []
        for q in SEARCH_QUERIES:
            html_url = _build_bing_image_url(q, 30)
            urls = _download_from_html_page(html_url, q)
            fallback_urls.extend(urls)
        fallback_urls = list(dict.fromkeys(fallback_urls))
        if fallback_urls:
            result = download_all(fallback_urls, max_downloads=target, workers=4)
            print(f"\n✔ 备用下载完成: {len(result)} 张图片")
        else:
            print("\n❌ 所有来源均未能获取图片")

    # 5. 生成摘要
    nsfw_check()
    show_summary()


def nsfw_check():
    """用 OpenCV 做基础内容检查（确保是真实照片）"""
    try:
        import cv2
        jpegs = sorted(RAW_DIR.glob("*.jpg"))
        for jpg in jpegs:
            img = cv2.imread(str(jpg))
            if img is None:
                continue
            # 拉普拉斯方差 < 30 的可能是模糊图，标记但不删除
            laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
            if laplacian_var < 30:
                print(f"  ⚠ 模糊图片: {jpg.name} (Laplacian={laplacian_var:.1f})")
    except Exception:
        pass


def show_summary():
    jpegs = sorted(RAW_DIR.glob("*.jpg"))
    print(f"\n{'='*60}")
    print(f"最终结果: {len(jpegs)} 张图片")
    total_size = sum(f.stat().st_size for f in jpegs) / (1024 * 1024)
    print(f"总大小: {total_size:.1f} MB")
    if jpegs:
        print(f"\n图片列表:")
        for jpg in jpegs:
            size_kb = jpg.stat().st_size / 1024
            print(f"  {jpg.name}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
