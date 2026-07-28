"""
隐患检测核心模块
调用YOLOv8 PPE检测模型,一次检测覆盖安全帽、反光衣、口罩、人员等10类目标
模型来源: Hansung-Cho/yolov8-ppe-detection (HuggingFace, 10类)
"""
import os
from pathlib import Path
from datetime import datetime
import torch
from ultralytics import YOLO


class HazardDetector:
    """多类隐患检测器(PPE检测)"""

    EXPECTED_CLASS_NAMES = (
        "Hardhat", "Mask", "NO-Hardhat", "NO-Mask", "NO-Safety Vest",
        "Person", "Safety Cone", "Safety Vest", "machinery", "vehicle",
    )
    MODELS_DIR = Path(__file__).parent.parent / "models"

    # 检测类别中文名称映射
    LABEL_CN = {
        "helmet": "安全帽",
        "no-helmet": "未戴安全帽",
        "vest": "反光衣",
        "no-vest": "未穿反光衣",
        "mask": "口罩",
        "no-mask": "未戴口罩",
        "person": "人员",
        "safety-cone": "安全锥",
        "machinery": "施工机械",
        "vehicle": "车辆",
        "head": "头部",
    }

    # 隐患类型 -> 预警等级映射
    ALERT_LEVELS = {
        "no-helmet": ("red", "红色预警", "未佩戴安全帽,立即停工整改"),
        "no-vest": ("yellow", "黄色预警", "未穿反光衣,限时整改"),
        "no-mask": ("yellow", "黄色预警", "未戴口罩,限时整改"),
        "helmet": ("blue", "正常记录", "已佩戴安全帽"),
        "vest": ("blue", "正常记录", "已穿反光衣"),
        "mask": ("blue", "正常记录", "已戴口罩"),
        "person": ("blue", "正常记录", "检测到人员"),
        "safety-cone": ("blue", "正常记录", "安全锥"),
        "machinery": ("blue", "正常记录", "施工机械"),
        "vehicle": ("blue", "正常记录", "车辆"),
    }

    @classmethod
    def resolve_model_path(cls):
        """Read active_model.txt and return the selected local model path."""
        active_file = cls.MODELS_DIR / "active_model.txt"
        model_name = "best.pt"
        try:
            configured_name = active_file.read_text(encoding="utf-8").strip()
            if configured_name:
                model_name = configured_name
        except OSError:
            pass
        # Only a single .pt filename below models/ is valid.
        if Path(model_name).name != model_name or not model_name.lower().endswith(".pt"):
            print(f"[model] invalid active_model.txt value: {model_name!r}; using best.pt")
            model_name = "best.pt"
        return cls.MODELS_DIR / model_name

    @classmethod
    def _validate_class_names(cls, model):
        names = model.names
        actual_names = tuple(names[index] for index in range(len(names)))
        if actual_names != cls.EXPECTED_CLASS_NAMES:
            raise ValueError(
                f"class order mismatch: expected {cls.EXPECTED_CLASS_NAMES}, got {actual_names}"
            )

    def _load_ppe_model(self, model_path):
        model_path = Path(model_path)
        if not model_path.is_file():
            raise FileNotFoundError(f"model file does not exist: {model_path}")
        model = YOLO(str(model_path))
        self._validate_class_names(model)
        self.model = model
        self.model_type = "custom"
        self.model_path = str(model_path)
        self.model_version = model_path.name

    def __init__(self, model_path=None):
        """Initialize the selected PPE model and safely fall back to models/best.pt."""
        fallback_model = self.MODELS_DIR / "best.pt"
        requested_model = Path(model_path) if model_path else self.resolve_model_path()
        self.fallback_used = False
        self.fallback_reason = ""
        try:
            self._load_ppe_model(requested_model)
        except Exception as error:
            if requested_model.resolve() != fallback_model.resolve():
                self.fallback_used = True
                self.fallback_reason = str(error)
                print(f"[model] failed to load {requested_model.name}: {error}; falling back to {fallback_model.name}")
                try:
                    self._load_ppe_model(fallback_model)
                except Exception as fallback_error:
                    self.fallback_reason += f"; {fallback_model.name} failed: {fallback_error}"
                else:
                    print(f"[model] loaded fallback {self.model_version}")
                    return
            else:
                self.fallback_used = True
                self.fallback_reason = str(error)
                print(f"[model] failed to load {fallback_model.name}: {error}; falling back to COCO yolov8n.pt")

            # Final fallback is explicit in state and UI; it is not a silent PPE substitute.
            self.model = YOLO("yolov8n.pt")
            self.model_type = "coco"
            self.model_path = "yolov8n.pt"
            self.model_version = "yolov8n.pt (COCO fallback)"
            print(f"[model] loaded fallback {self.model_version}")
        else:
            print(f"[model] loaded {self.model_version}: {self.model_path}")

    def detect(self, image_path, conf=0.4):
        """
        检测图片中的隐患,返回检测结果、预警信息和统计摘要
        """
        device = 0 if torch.cuda.is_available() else "cpu"
        results = self.model(image_path, conf=conf, device=device)

        detections = []
        alert_count = {"red": 0, "yellow": 0, "blue": 0}

        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                conf_val = float(box.conf[0])
                class_name = self.model.names[cls_id]

                label_en = self._map_label(class_name)
                label_cn = self.LABEL_CN.get(label_en, class_name)

                level_key, level_name, desc = self.ALERT_LEVELS.get(
                    label_en, ("blue", "正常记录", class_name)
                )

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detection = {
                    "label": label_cn,
                    "label_en": label_en,
                    "confidence": round(conf_val, 2),
                    "bbox": [round(x1), round(y1), round(x2), round(y2)],
                    "alert_level": level_key,
                    "alert_name": level_name,
                    "description": desc,
                }
                detections.append(detection)
                alert_count[level_key] += 1

        # 保存标注后的图片(统一存到 data/uploads/, 避免污染源图目录; 含时间戳避免同名覆盖)
        uploads_dir = Path(__file__).parent.parent / "data" / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        annotated_path = str(uploads_dir / f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{Path(image_path).name}")
        for result in results:
            result.save(filename=annotated_path)

        # 统计摘要
        summary = {
            "total_detections": len(detections),
            "helmet_count": sum(1 for d in detections if d["label_en"] == "helmet"),
            "no_helmet_count": sum(1 for d in detections if d["label_en"] == "no-helmet"),
            "vest_count": sum(1 for d in detections if d["label_en"] == "vest"),
            "no_vest_count": sum(1 for d in detections if d["label_en"] == "no-vest"),
            "mask_count": sum(1 for d in detections if d["label_en"] == "mask"),
            "no_mask_count": sum(1 for d in detections if d["label_en"] == "no-mask"),
            "person_count": sum(1 for d in detections if d["label_en"] == "person"),
            "red_alerts": alert_count["red"],
            "yellow_alerts": alert_count["yellow"],
            "has_violation": alert_count["red"] + alert_count["yellow"] > 0,
        }

        return {
            "image": annotated_path,
            "detections": detections,
            "alerts": [],  # 由 AlertEngine 生成(app.py 调用),此处留空保持返回结构兼容
            "summary": summary,
        }

    def _map_label(self, class_name):
        """将模型输出的类别名映射为统一标签"""
        name_lower = class_name.lower()
        # 安全帽(hardhat/helmet)
        if "hardhat" in name_lower or "helmet" in name_lower:
            if "no" in name_lower or "without" in name_lower:
                return "no-helmet"
            return "helmet"
        # 反光衣(vest)
        if "vest" in name_lower or "reflective" in name_lower:
            if "no" in name_lower or "without" in name_lower:
                return "no-vest"
            return "vest"
        # 口罩(mask)
        if "mask" in name_lower:
            if "no" in name_lower or "without" in name_lower:
                return "no-mask"
            return "mask"
        # 人员
        if "person" in name_lower or "people" in name_lower or "worker" in name_lower:
            return "person"
        # 安全锥
        if "cone" in name_lower:
            return "safety-cone"
        # 施工机械
        if "machiner" in name_lower or "equipment" in name_lower:
            return "machinery"
        # 车辆
        if "vehicle" in name_lower or "truck" in name_lower:
            return "vehicle"
        if "head" in name_lower:
            return "head"
        return class_name
