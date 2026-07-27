# -*- coding: utf-8 -*-
"""Try direct download from known open datasets"""
import requests, json, tempfile, zipfile, shutil
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Direct download URLs for known open datasets that don't need auth
urls = [
    # Google Open Images - class descriptions (used to filter specific classes)
    ("Open Images V7 description", "https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions.csv", "text"),
    # Roboflow public dataset - direct download (might work without API key)
    ("PPE Detection v2 (try direct)", "https://universe.roboflow.com/dataset/RMANMSpN/ppe-detection-v2/download/yolov8", "zip"),
    # Kaggle dataset direct (might work)
    ("Kaggle face mask", "https://www.kaggle.com/api/v1/datasets/andrewmvd/face-mask-detection/download", "zip"),
]

for name, url, ftype in urls:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        print(f"[{r.status_code}] {name} ({len(r.content)//1024} KB)")
    except Exception as e:
        print(f"[ERR] {name}: {str(e)[:60]}")
