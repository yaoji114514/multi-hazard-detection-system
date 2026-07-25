"""
GPU 推理验证脚本
验证 torch CUDA 是否可用,并跑一帧检测确认 GPU 推理正常工作
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

print("=" * 50)
print("GPU 推理验证")
print("=" * 50)

# 1. 检查 torch CUDA
import torch
print(f"\n[1] torch 版本: {torch.__version__}")
print(f"    CUDA 可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"    CUDA 版本: {torch.version.cuda}")
    print(f"    GPU 设备: {torch.cuda.get_device_name(0)}")
    print(f"    GPU 显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
else:
    print("\n[错误] CUDA 不可用,请检查:")
    print("  1. 是否安装了 CUDA 版 torch(非 +cpu 后缀)")
    print("  2. 显卡驱动是否 ≥ 525")
    print("  3. nvidia-smi 是否能正常输出")
    sys.exit(1)

# 2. 加载检测器
print("\n[2] 加载 YOLOv8 检测器...")
from detector import HazardDetector
detector = HazardDetector()
print(f"    模型类型: {detector.model_type}")

# 3. CPU vs GPU 速度对比
print("\n[3] CPU vs GPU 推理速度对比:")
test_image = str(Path(__file__).parent / "data" / "sample_images" / "test_helmet.jpg")
if not Path(test_image).exists():
    print(f"    [跳过] 测试图片不存在: {test_image}")
    sys.exit(0)

# CPU 推理
print(f"    测试图片: {Path(test_image).name}")
print(f"    CPU 推理中...", end=" ", flush=True)
t0 = time.time()
results_cpu = detector.model(test_image, conf=0.4, device="cpu", verbose=False)
t_cpu = time.time() - t0
print(f"{t_cpu*1000:.0f} ms, 检测到 {len(results_cpu[0].boxes)} 个目标")

# GPU 推理
print(f"    GPU 推理中...", end=" ", flush=True)
torch.cuda.synchronize() if torch.cuda.is_available() else None
t0 = time.time()
results_gpu = detector.model(test_image, conf=0.4, device=0, verbose=False)
torch.cuda.synchronize() if torch.cuda.is_available() else None
t_gpu = time.time() - t0
print(f"{t_gpu*1000:.0f} ms, 检测到 {len(results_gpu[0].boxes)} 个目标")

# 4. 速度对比
if t_gpu > 0:
    speedup = t_cpu / t_gpu
    print(f"\n[4] 加速比: {speedup:.1f}x (CPU {t_cpu*1000:.0f}ms → GPU {t_gpu*1000:.0f}ms)")
    if speedup > 1:
        print(f"    ✅ GPU 加速生效,速度提升 {speedup:.1f} 倍")
    else:
        print(f"    ⚠️ GPU 反而更慢(可能首帧初始化开销,多帧后会变快)")

# 5. 多帧 GPU 推理(模拟实时检测)
print("\n[5] GPU 连续推理 10 帧(模拟实时检测):")
import cv2
img = cv2.imread(test_image)
times = []
for i in range(10):
    torch.cuda.synchronize()
    t0 = time.time()
    detector.model(img, conf=0.4, device=0, verbose=False)
    torch.cuda.synchronize()
    t = time.time() - t0
    times.append(t)
    print(f"    帧 {i+1}: {t*1000:.0f} ms", flush=True)

avg_ms = sum(times[1:]) / len(times[1:])  # 跳过首帧
fps = 1 / avg_ms if avg_ms > 0 else 0
print(f"\n    平均(跳过首帧): {avg_ms*1000:.0f} ms/帧")
print(f"    预计实时帧率: {fps:.1f} FPS")

print("\n" + "=" * 50)
print("✅ GPU 推理验证通过")
print("=" * 50)
