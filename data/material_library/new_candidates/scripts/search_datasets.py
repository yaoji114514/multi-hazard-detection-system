# -*- coding: utf-8 -*-
"""Search for open datasets"""
import requests, re, json
from urllib.parse import quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# Try known dataset URLs directly
dataset_urls = [
    # Roboflow known public datasets
    ("RMANMSpN/ppe-detection-v2", "PPE Detection v2"),
    ("siabar/ppe-dataset-for-workplace-safety", "PPE Workplace Safety (already have)"),
    ("roboflow-jhu/face-mask-detection", "Face Mask Detection"),
    ("andreasfischer1982/face-mask", "Face Mask"),
    
    # Check if we can find more
]

for path, desc in dataset_urls:
    url = f"https://universe.roboflow.com/{path}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"[{r.status_code}] {desc}: {url}")
    except Exception as e:
        print(f"[ERR] {desc}: {e}")

print("\n--- Trying Kaggle search via Google ---")
# Try Kaggle datasets for face mask
url = f"https://www.kaggle.com/datasets?search=face+mask+construction"
try:
    r = requests.get(url, headers=HEADERS, timeout=15)
    print(f"Kaggle: {r.status_code}")
except Exception as e:
    print(f"Kaggle: {e}")

# Try HuggingFace datasets
print("\n--- HF Datasets ---")
hf_urls = [
    "https://huggingface.co/datasets?search=face+mask+detection",
    "https://huggingface.co/datasets?search=construction+safety+ppe",
]
for u in hf_urls:
    try:
        r = requests.get(u, headers=HEADERS, timeout=15)
        print(f"HF {r.status_code}: {u[:50]}")
    except Exception as e:
        print(f"HF error: {e}")

# Try direct known dataset download links
print("\n--- Known open datasets ---")
known = [
    ("https://github.com/prajnasb/observations/raw/master/experiements/data/with_mask/", "Face mask dataset (GitHub)"),
    ("https://github.com/X-zhangyang/Real-World-Masked-Face-Dataset", "RMFD dataset"),
]
for u, desc in known:
    try:
        r = requests.head(u, headers=HEADERS, timeout=10)
        print(f"[{r.status_code}] {desc}")
    except Exception as e:
        print(f"[ERR] {desc}: {e}")
