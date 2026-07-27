# -*- coding: utf-8 -*-
"""Search for datasets on HuggingFace and other platforms"""
import requests, json

HEADERS = {"User-Agent": "Mozilla/5.0"}

# HuggingFace datasets search
url = "https://huggingface.co/api/datasets?search=construction+safety+ppe&sort=downloads&direction=-1&limit=10"
try:
    r = requests.get(url, headers=HEADERS, timeout=15)
    print(f"HF API: {r.status_code}")
    if r.status_code == 200:
        for item in r.json():
            did = item.get("id", "?")
            downloads = item.get("downloads", "?")
            print(f"  {did} (downloads: {downloads})")
except Exception as e:
    print(f"HF error: {e}")

# Try common dataset names directly
print("\n=== Tring direct HF dataset download ===")
ds_names = [
    "keremberke/ppe-detection",
    "keremberke/construction-machinery-detection",
    "keremberke/traffic-cone-detection",
    "jctherobot/ppe-detection-yolo",
    "Bingsu/construction-vehicle",
]
for name in ds_names:
    url = f"https://huggingface.co/api/datasets/{name}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"  [{r.status_code}] {name}")
    except:
        print(f"  [ERR] {name}")

print("\n=== Trying Google Open Images ===")
url = "https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions.csv"
try:
    r = requests.head(url, timeout=10)
    print(f"  Open Images accessible: {r.status_code}")
except Exception as e:
    print(f"  Open Images: {e}")
