"""
系统安装验证脚本
检查所有依赖是否正确安装、模型能否加载、核心模块能否导入
"""
import sys
import importlib
from pathlib import Path

print("=" * 50)
print("  多类隐患检测系统 - 安装验证")
print("=" * 50)
print(f"Python 版本: {sys.version.split()[0]}")
print(f"Python 路径: {sys.executable}")
print()

# 1. 验证核心依赖
required = {
    "torch": "深度学习框架",
    "torchvision": "视觉模型",
    "ultralytics": "YOLOv8 检测框架",
    "fastapi": "V3 本地 API",
    "uvicorn": "V3 本地服务",
    "multipart": "文件上传解析",
    "cv2": "OpenCV 图像处理",
    "PIL": "Pillow 图像库",
    "imageio_ffmpeg": "视频转码",
}

print("[1/5] 验证核心依赖...")
all_ok = True
for mod, desc in required.items():
    try:
        m = importlib.import_module(mod)
        ver = getattr(m, "__version__", "OK")
        print(f"  [OK] {mod:20s} {ver:15s} ({desc})")
    except ImportError as e:
        print(f"  [失败] {mod:20s} 安装失败 ({desc}) - {e}")
        all_ok = False

if not all_ok:
    print("\n[错误] 部分依赖未正确安装，请检查 install_log.txt")
    sys.exit(1)

# 2. 验证 torch 可用性
print("\n[2/5] 验证 PyTorch 运行环境...")
import torch
print(f"  [OK] PyTorch 版本: {torch.__version__}")
print(f"  [OK] CUDA 可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"  [OK] GPU 设备: {torch.cuda.get_device_name(0)}")
elif getattr(getattr(torch, "backends", None), "mps", None) and torch.backends.mps.is_available():
    print("  [OK] MPS 可用: Apple Silicon GPU 推理")
else:
    print("  [信息] 使用 CPU 推理（无需独显，满足检测需求）")

# 3. 验证模型文件
print("\n[3/5] 验证 AI 模型文件...")
model_path = Path(__file__).parent / "models" / "best.pt"
if model_path.exists():
    print(f"  [OK] 模型文件存在: {model_path}")
    print(f"  [OK] 文件大小: {model_path.stat().st_size / 1024 / 1024:.1f} MB")
else:
    print(f"  [失败] 模型文件缺失: {model_path}")
    sys.exit(1)

# 4. 加载模型并执行测试检测
print("\n[4/5] 加载模型并执行测试检测...")
try:
    from ultralytics import YOLO
    model = YOLO(str(model_path))
    print("  [OK] YOLO 模型加载成功")
    print(f"  [OK] 模型类型: {getattr(model, 'task', 'detect')}")
    print(f"  [OK] 检测类别: {model.names}")

    # 用示例图片测试
    sample = Path(__file__).parent / "data" / "sample_images" / "test_helmet.jpg"
    if sample.exists():
        print(f"\n  执行测试检测: {sample.name}")
        results = model(str(sample), conf=0.4, verbose=False)
        boxes = results[0].boxes
        print(f"  [OK] 检测成功，共发现 {len(boxes)} 个目标")
        if len(boxes) > 0:
            cls_counts = {}
            for b in boxes:
                c = model.names[int(b.cls[0])]
                cls_counts[c] = cls_counts.get(c, 0) + 1
            for k, v in sorted(cls_counts.items(), key=lambda x: -x[1]):
                print(f"    - {k}: {v}")
except Exception as e:
    print(f"  [失败] 模型加载/检测失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. 验证项目源码模块
print("\n[5/5] 验证项目源码模块...")
sys.path.insert(0, str(Path(__file__).parent / "src"))
try:
    from detector import HazardDetector
    from alert import AlertEngine
    from database import Database
    from src.web_api import app as web_app
    frontend_index = Path(__file__).parent / "frontend" / "dist" / "index.html"
    alert_sound = Path(__file__).parent / "data" / "alert.wav"
    if not frontend_index.is_file():
        raise FileNotFoundError(f"V3 前端构建产物缺失: {frontend_index}")
    if not alert_sound.is_file():
        raise FileNotFoundError(f"红色风险警报音缺失: {alert_sound}")
    print("  [OK] src/detector.py (检测模块)")
    print("  [OK] src/alert.py (预警模块)")
    print("  [OK] src/database.py (数据存储模块)")
    print(f"  [OK] {web_app.title} (V3 本地 API)")
    print("  [OK] frontend/dist/index.html (V3 前端)")
    print("  [OK] data/alert.wav (红色风险警报音)")
except Exception as e:
    print(f"  [失败] 源码模块导入失败: {e}")
    sys.exit(1)

print("\n" + "=" * 50)
print("  [OK] 全部验证通过！系统已就绪")
print("=" * 50)
print("""
启动方式:
  双击 run.bat
  或命令行: .venv\\Scripts\\python.exe -m uvicorn src.web_api:app --host 127.0.0.1 --port 8501
  访问地址: http://localhost:8501
""")
