import importlib.util
import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def _load_detector_module():
    """Load detector.py with lightweight dependency doubles."""
    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(is_available=mock.Mock(return_value=False))
    fake_ultralytics = types.ModuleType("ultralytics")
    fake_ultralytics.YOLO = mock.Mock(name="YOLO")

    spec = importlib.util.spec_from_file_location(
        "_detector_under_test", ROOT / "src" / "detector.py"
    )
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(
        sys.modules,
        {"torch": fake_torch, "ultralytics": fake_ultralytics},
    ):
        spec.loader.exec_module(module)
    return module


detector_module = _load_detector_module()
HazardDetector = detector_module.HazardDetector


class _Coordinates:
    def __init__(self, *values):
        self.values = values

    def tolist(self):
        return list(self.values)


class HazardDetectorTests(unittest.TestCase):
    def test_select_compute_device_prefers_cuda_then_mps_then_cpu(self):
        with mock.patch.object(
            detector_module.torch.cuda, "is_available", return_value=True
        ):
            self.assertEqual(0, detector_module.select_compute_device())

        mps_backend = types.SimpleNamespace(is_available=mock.Mock(return_value=True))
        with mock.patch.object(
            detector_module.torch.cuda, "is_available", return_value=False
        ):
            with mock.patch.object(
                detector_module.torch,
                "backends",
                types.SimpleNamespace(mps=mps_backend),
                create=True,
            ):
                self.assertEqual("mps", detector_module.select_compute_device())

            with mock.patch.object(
                detector_module.torch,
                "backends",
                types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False)),
                create=True,
            ):
                self.assertEqual("cpu", detector_module.select_compute_device())

    def test_resolve_model_path_accepts_only_local_pt_filename(self):
        with TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            active_file = models_dir / "active_model.txt"
            with mock.patch.object(HazardDetector, "MODELS_DIR", models_dir):
                self.assertEqual(
                    HazardDetector.resolve_model_path(), models_dir / "best.pt"
                )

                active_file.write_text("\n", encoding="utf-8")
                self.assertEqual(
                    HazardDetector.resolve_model_path(), models_dir / "best.pt"
                )

                active_file.write_text("partner_model.pt\n", encoding="utf-8")
                self.assertEqual(
                    HazardDetector.resolve_model_path(),
                    models_dir / "partner_model.pt",
                )

                for invalid_name in ("../outside.pt", "model.onnx", "nested/model.pt"):
                    with self.subTest(invalid_name=invalid_name):
                        active_file.write_text(invalid_name, encoding="utf-8")
                        with redirect_stdout(io.StringIO()):
                            resolved = HazardDetector.resolve_model_path()
                        self.assertEqual(resolved, models_dir / "best.pt")

    def test_validate_class_names_rejects_wrong_order(self):
        valid_model = types.SimpleNamespace(
            names=list(HazardDetector.EXPECTED_CLASS_NAMES)
        )
        HazardDetector._validate_class_names(valid_model)

        invalid_names = list(HazardDetector.EXPECTED_CLASS_NAMES)
        invalid_names[0], invalid_names[1] = invalid_names[1], invalid_names[0]
        with self.assertRaisesRegex(ValueError, "class order mismatch"):
            HazardDetector._validate_class_names(
                types.SimpleNamespace(names=invalid_names)
            )

    def test_load_ppe_model_checks_file_and_records_model_metadata(self):
        with TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "custom.pt"
            model_path.write_bytes(b"test-double")
            loaded_model = types.SimpleNamespace(
                names=list(HazardDetector.EXPECTED_CLASS_NAMES)
            )
            fake_yolo = mock.Mock(return_value=loaded_model)
            instance = HazardDetector.__new__(HazardDetector)

            with mock.patch.object(detector_module, "YOLO", fake_yolo):
                instance._load_ppe_model(model_path)

            fake_yolo.assert_called_once_with(str(model_path))
            self.assertIs(instance.model, loaded_model)
            self.assertEqual(instance.model_type, "custom")
            self.assertEqual(instance.model_path, str(model_path))
            self.assertEqual(instance.model_version, "custom.pt")

            missing_path = Path(temp_dir) / "missing.pt"
            with mock.patch.object(detector_module, "YOLO") as unused_yolo:
                with self.assertRaisesRegex(FileNotFoundError, "does not exist"):
                    instance._load_ppe_model(missing_path)
                unused_yolo.assert_not_called()

    def test_init_loads_selected_model_or_falls_back_to_best(self):
        with TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)

            class StubDetector(HazardDetector):
                MODELS_DIR = models_dir

                def __init__(self, *args, **kwargs):
                    self.load_calls = []
                    super().__init__(*args, **kwargs)

                def _load_ppe_model(self, model_path):
                    model_path = Path(model_path)
                    self.load_calls.append(model_path)
                    if model_path.name == "selected.pt":
                        raise RuntimeError("selected model is corrupt")
                    self.model = object()
                    self.model_type = "custom"
                    self.model_path = str(model_path)
                    self.model_version = model_path.name

            with redirect_stdout(io.StringIO()):
                working_instance = StubDetector(models_dir / "working.pt")
                fallback_instance = StubDetector(models_dir / "selected.pt")

            self.assertEqual(
                working_instance.load_calls,
                [models_dir / "working.pt"],
            )
            self.assertFalse(working_instance.fallback_used)
            self.assertEqual(working_instance.fallback_reason, "")
            self.assertEqual(working_instance.model_version, "working.pt")
            self.assertEqual(
                fallback_instance.load_calls,
                [models_dir / "selected.pt", models_dir / "best.pt"],
            )
            self.assertTrue(fallback_instance.fallback_used)
            self.assertIn(
                "selected model is corrupt", fallback_instance.fallback_reason
            )
            self.assertEqual(fallback_instance.model_type, "custom")
            self.assertEqual(fallback_instance.model_version, "best.pt")

    def test_init_uses_explicit_coco_fallback_when_local_models_fail(self):
        with TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)

            class StubDetector(HazardDetector):
                MODELS_DIR = models_dir

                def __init__(self, *args, **kwargs):
                    self.load_calls = []
                    super().__init__(*args, **kwargs)

                def _load_ppe_model(self, model_path):
                    model_path = Path(model_path)
                    self.load_calls.append(model_path)
                    raise RuntimeError(f"cannot load {model_path.name}")

            coco_model = object()
            fake_yolo = mock.Mock(return_value=coco_model)
            with mock.patch.object(detector_module, "YOLO", fake_yolo):
                with redirect_stdout(io.StringIO()):
                    selected_instance = StubDetector(models_dir / "selected.pt")
                    best_instance = StubDetector(models_dir / "best.pt")

            self.assertEqual(
                selected_instance.load_calls,
                [models_dir / "selected.pt", models_dir / "best.pt"],
            )
            self.assertIn("selected.pt", selected_instance.fallback_reason)
            self.assertIn("best.pt failed", selected_instance.fallback_reason)
            self.assertEqual(best_instance.load_calls, [models_dir / "best.pt"])
            self.assertEqual(best_instance.fallback_reason, "cannot load best.pt")
            self.assertEqual(
                fake_yolo.call_args_list,
                [mock.call("yolov8n.pt"), mock.call("yolov8n.pt")],
            )
            for instance in (selected_instance, best_instance):
                self.assertIs(instance.model, coco_model)
                self.assertEqual(instance.model_type, "coco")
                self.assertEqual(instance.model_path, "yolov8n.pt")
                self.assertEqual(
                    instance.model_version, "yolov8n.pt (COCO fallback)"
                )

    def test_map_label_normalizes_supported_aliases(self):
        instance = HazardDetector.__new__(HazardDetector)
        cases = {
            "Hardhat": "helmet",
            "worker_without_helmet": "no-helmet",
            "reflective jacket": "vest",
            "NO-Safety Vest": "no-vest",
            "Mask": "mask",
            "without_mask": "no-mask",
            "worker": "person",
            "traffic cone": "safety-cone",
            "heavy equipment": "machinery",
            "truck": "vehicle",
            "Head": "head",
            "custom-class": "custom-class",
        }
        for raw_name, expected in cases.items():
            with self.subTest(raw_name=raw_name):
                self.assertEqual(instance._map_label(raw_name), expected)

    def test_detect_builds_summary_and_saves_only_to_temporary_uploads(self):
        boxes = [
            types.SimpleNamespace(
                cls=[0], conf=[0.876], xyxy=[_Coordinates(1.2, 2.6, 30.4, 40.8)]
            ),
            types.SimpleNamespace(
                cls=[2], conf=[0.734], xyxy=[_Coordinates(10, 20, 50, 60)]
            ),
            types.SimpleNamespace(
                cls=[4], conf=[0.625], xyxy=[_Coordinates(11, 21, 51, 61)]
            ),
            types.SimpleNamespace(
                cls=[3], conf=[0.511], xyxy=[_Coordinates(12, 22, 52, 62)]
            ),
            types.SimpleNamespace(
                cls=[5], conf=[0.499], xyxy=[_Coordinates(13, 23, 53, 63)]
            ),
            types.SimpleNamespace(
                cls=[7], conf=[0.955], xyxy=[_Coordinates(14, 24, 54, 64)]
            ),
        ]
        result = types.SimpleNamespace(boxes=boxes, save=mock.Mock())
        model = mock.Mock(return_value=[result])
        model.names = {
            0: "Hardhat",
            2: "NO-Hardhat",
            3: "NO-Mask",
            4: "NO-Safety Vest",
            5: "Person",
            7: "Safety Vest",
        }
        instance = HazardDetector.__new__(HazardDetector)
        instance.model = model

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_path = temp_root / "src" / "detector.py"
            image_path = temp_root / "input.jpg"
            fixed_datetime = mock.Mock()
            fixed_datetime.now.return_value.strftime.return_value = "20260804_010203"
            detector_module.torch.cuda.is_available.reset_mock(return_value=True)
            detector_module.torch.cuda.is_available.return_value = True
            with mock.patch.object(detector_module, "__file__", str(source_path)):
                with mock.patch.object(detector_module, "datetime", fixed_datetime):
                    output = instance.detect(str(image_path), conf=0.55)

            expected_output = (
                temp_root / "data" / "uploads" / "result_20260804_010203_input.jpg"
            )
            model.assert_called_once_with(str(image_path), conf=0.55, device=0)
            result.save.assert_called_once_with(filename=str(expected_output))
            self.assertEqual(output["image"], str(expected_output))
            self.assertEqual(output["alerts"], [])
            self.assertEqual(output["detections"][0]["confidence"], 0.88)
            self.assertEqual(output["detections"][0]["bbox"], [1, 3, 30, 41])
            self.assertEqual(
                output["summary"],
                {
                    "total_detections": 6,
                    "helmet_count": 1,
                    "no_helmet_count": 1,
                    "vest_count": 1,
                    "no_vest_count": 1,
                    "mask_count": 0,
                    "no_mask_count": 1,
                    "person_count": 1,
                    "red_alerts": 1,
                    "yellow_alerts": 2,
                    "has_violation": True,
                },
            )


if __name__ == "__main__":
    unittest.main()
