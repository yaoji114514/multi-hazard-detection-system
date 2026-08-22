import importlib.util
import logging
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


class _FakeUI:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def text_input(self, label, value="", **kwargs):
        return value

    def radio(self, label, options, **kwargs):
        return options[0]

    def checkbox(self, label, value=False, **kwargs):
        return value

    def toggle(self, label, value=False, **kwargs):
        return value

    def file_uploader(self, *args, **kwargs):
        return None

    def button(self, *args, **kwargs):
        return False

    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [_FakeUI() for _ in range(count)]

    def expander(self, *args, **kwargs):
        return _FakeUI()

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _FakeStreamlit(types.ModuleType, _FakeUI):
    def __init__(self):
        types.ModuleType.__init__(self, "streamlit")
        self.sidebar = _FakeUI()
        self.session_state = {}

    @staticmethod
    def cache_resource(function):
        return function


class _FakeDetector:
    LABEL_CN = {
        "no-helmet": "未戴安全帽",
        "no-vest": "未穿反光衣",
        "no-mask": "未戴口罩",
    }
    ALERT_LEVELS = {
        "no-helmet": ("red",),
        "no-vest": ("yellow",),
        "no-mask": ("yellow",),
    }

    def __init__(self, model_path):
        self.model_version = Path(model_path).name
        self.fallback_used = False
        self.fallback_reason = ""

    @classmethod
    def resolve_model_path(cls):
        return ROOT / "models" / "fake.pt"


class _FakeDatabase:
    pass


class _FakeAlertEngine:
    pass


def _module(name, **members):
    module = types.ModuleType(name)
    for member_name, value in members.items():
        setattr(module, member_name, value)
    return module


def _load_app_module():
    fake_streamlit = _FakeStreamlit()
    fake_dingtalk = _module(
        "dingtalk",
        DingTalkError=RuntimeError,
        list_webhooks=lambda: [],
        send_text=lambda *args, **kwargs: None,
        send_markdown=lambda *args, **kwargs: None,
        send_image=lambda *args, **kwargs: None,
    )
    fake_torch = _module(
        "torch", cuda=types.SimpleNamespace(is_available=lambda: False)
    )
    modules = {
        "streamlit": fake_streamlit,
        "torch": fake_torch,
        "detector": _module(
            "detector", HazardDetector=_FakeDetector, select_compute_device=lambda: "cpu"
        ),
        "database": _module("database", Database=_FakeDatabase),
        "alert": _module("alert", AlertEngine=_FakeAlertEngine),
        "dingtalk": fake_dingtalk,
    }
    spec = importlib.util.spec_from_file_location(
        "_app_helpers_under_test", ROOT / "app.py"
    )
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, modules):
        with mock.patch(
            "logging.FileHandler", return_value=logging.NullHandler()
        ):
            spec.loader.exec_module(module)
    return module, fake_streamlit, fake_dingtalk


app, fake_streamlit, fake_dingtalk = _load_app_module()


class FrontendRiskHelperTests(unittest.TestCase):
    def test_image_fingerprint_changes_with_content_or_model(self):
        first = app._image_fingerprint(b"image-a", "model-v1")
        self.assertEqual(first, app._image_fingerprint(b"image-a", "model-v1"))
        self.assertNotEqual(first, app._image_fingerprint(b"image-b", "model-v1"))
        self.assertNotEqual(first, app._image_fingerprint(b"image-a", "model-v2"))

    def test_dingtalk_name_confirmation_flags_ambiguous_placeholders(self):
        self.assertTrue(app._dingtalk_name_needs_confirmation("默认群"))
        self.assertTrue(app._dingtalk_name_needs_confirmation("群 2"))
        self.assertFalse(app._dingtalk_name_needs_confirmation("五建项目安全巡检群"))

    def test_dingtalk_identity_session_key_hides_and_separates_bindings(self):
        first = app._dingtalk_identity_session_key("ABCD1234", "cid-one")
        second = app._dingtalk_identity_session_key("ABCD1234", "cid-two")

        self.assertNotIn("cid-one", first)
        self.assertNotIn("cid-two", second)
        self.assertNotEqual(first, second)

    def test_last_check_context_restores_once_and_saves_input_changes(self):
        fake_streamlit.session_state.clear()
        database = mock.Mock()
        database.get_last_check_context.return_value = {
            "project_name": "南区项目",
            "inspector": "李四",
        }
        with mock.patch.object(app, "get_database", return_value=database):
            app._restore_last_check_context()
            app._restore_last_check_context()
            app._save_last_check_context()

        self.assertEqual(fake_streamlit.session_state[app._PROJECT_CONTEXT_KEY], "南区项目")
        self.assertEqual(fake_streamlit.session_state[app._INSPECTOR_CONTEXT_KEY], "李四")
        database.get_last_check_context.assert_called_once_with()
        database.save_last_check_context.assert_called_once_with("南区项目", "李四")

    def test_record_risk_prioritizes_red_then_yellow(self):
        self.assertEqual(app._record_risk({"red_alerts": 1, "yellow_alerts": 2}), "red")
        self.assertEqual(app._record_risk({"no_vest_count": 1}), "yellow")
        self.assertEqual(app._record_risk({"level": "red"}), "red")
        self.assertEqual(app._record_risk({}), "blue")

    def test_safe_json_list_degrades_invalid_or_non_list_values(self):
        self.assertEqual(app._safe_json_list('[{"id": 1}]'), [{"id": 1}])
        self.assertEqual(app._safe_json_list('{"id": 1}'), [])
        self.assertEqual(app._safe_json_list("not-json"), [])
        self.assertEqual(app._safe_json_list(None), [])

    def test_realtime_ui_state_separates_monitor_risk_and_system_error(self):
        idle = app._realtime_ui_state(
            {"violations": 0, "violation_classes": {}, "last_error": None},
            False,
        )
        self.assertEqual(idle["monitor"][0], "尚未启动监测")
        self.assertEqual(idle["risk"][0], "neutral")

        safe = app._realtime_ui_state(
            {"violations": 0, "violation_classes": {}, "last_error": None},
            True,
        )
        self.assertEqual(safe["monitor"][0], "监测运行中")
        self.assertEqual(safe["risk"][0], "blue")

        red_with_error = app._realtime_ui_state(
            {
                "violations": 2,
                "violation_classes": {"no-helmet": 1, "no-vest": 1},
                "last_error": "camera failed",
            },
            True,
        )
        self.assertEqual(red_with_error["risk"][0], "red")
        self.assertEqual(red_with_error["system"][2], "error")

        yellow = app._realtime_ui_state(
            {"violations": 1, "violation_classes": {"no-vest": 1}, "last_error": None},
            True,
        )
        self.assertEqual(yellow["risk"][0], "yellow")

    def test_queue_quick_views_keep_open_work_visible(self):
        now = __import__("datetime").datetime(2026, 8, 13, 12, 0, 0)
        records = [
            {"incident_status": "pending", "assignee": "", "level": "red", "due_at": "2026-08-12 23:59:59"},
            {"incident_status": "in_progress", "assignee": "张三", "level": "yellow", "due_at": "2026-08-14 23:59:59"},
            {"incident_status": "closed", "assignee": "张三", "level": "red", "due_at": "2026-08-11 23:59:59"},
        ]
        self.assertEqual([app._queue_matches_quick_view(r, "open", "张三", now) for r in records], [True, True, False])
        self.assertEqual([app._queue_matches_quick_view(r, "in_progress", "张三", now) for r in records], [False, True, False])
        self.assertEqual([app._queue_matches_quick_view(r, "mine", "张三", now) for r in records], [False, True, False])
        self.assertEqual([app._queue_matches_quick_view(r, "unassigned", "张三", now) for r in records], [True, False, False])
        self.assertEqual([app._queue_matches_quick_view(r, "red", "张三", now) for r in records], [True, False, False])
        self.assertEqual([app._queue_matches_quick_view(r, "overdue", "张三", now) for r in records], [True, False, False])

    def test_request_incident_focus_sets_pending_route(self):
        fake_streamlit.session_state.clear()
        app._request_incident_focus("image", 12)
        self.assertEqual(fake_streamlit.session_state["_requested_page"], "检测记录")
        self.assertEqual(fake_streamlit.session_state["_requested_queue_view"], "all")
        self.assertEqual(fake_streamlit.session_state["_incident_focus_source"], "image")
        self.assertEqual(fake_streamlit.session_state["_incident_focus_id"], 12)
        self.assertEqual(fake_streamlit.session_state["incident_queue_keyword"], "")
        self.assertEqual(fake_streamlit.session_state["incident_queue_risk"], "all")

    def test_realtime_storage_count_changes_only_after_success(self):
        rt_stats = app.get_rt_stats()
        app._reset_rt_stats()
        failing_db = mock.Mock()
        failing_db.save_realtime_violation.side_effect = RuntimeError("disk full")

        self.assertIsNone(
            app._save_realtime_incident(
                failing_db,
                rt_stats,
                violation_type="no-helmet",
                violation_count=1,
            )
        )
        self.assertEqual(rt_stats["realtime_record_count"], 0)
        self.assertIsNone(rt_stats["last_realtime_record_id"])
        self.assertIn("disk full", rt_stats["last_storage_error"])

        healthy_db = mock.Mock()
        healthy_db.save_realtime_violation.return_value = 27
        self.assertEqual(
            app._save_realtime_incident(
                healthy_db,
                rt_stats,
                violation_type="no-helmet",
                violation_count=1,
            ),
            27,
        )
        self.assertEqual(rt_stats["realtime_record_count"], 1)
        self.assertEqual(rt_stats["last_realtime_record_id"], 27)
        self.assertIn("disk full", rt_stats["last_storage_error"])


class RealtimeStatsTests(unittest.TestCase):
    def test_reset_clears_runtime_state_and_releases_recorder(self):
        rt_stats = app.get_rt_stats()
        recorder = mock.Mock()
        rt_stats.update(
            frames=10,
            classes={"person": 4},
            violations=2,
            recorder=recorder,
            recording=True,
            recorded_tracks={"1:no-helmet"},
            pos_dedupe={"no-helmet": [(1, 2, 3)]},
            last_boxes=[(1, 2, 3, 4, 0, 0.9, 1)],
            dingtalk_pending_counts={"no-helmet": 1},
            dingtalk_crop_path="crop.jpg",
            dingtalk_batch={"counts": {"no-helmet": 1}},
            dingtalk_sending=True,
            dingtalk_retry_count=2,
            dingtalk_retry_at=99.0,
        )

        with mock.patch.object(app, "get_rt_stats", return_value=rt_stats):
            app._reset_rt_stats()

        recorder.release.assert_called_once_with()
        self.assertEqual(rt_stats["frames"], 0)
        self.assertEqual(rt_stats["classes"], {})
        self.assertEqual(rt_stats["violations"], 0)
        self.assertFalse(rt_stats["recording"])
        self.assertIsNone(rt_stats["recorder"])
        self.assertEqual(rt_stats["recorded_tracks"], set())
        self.assertEqual(rt_stats["pos_dedupe"], {})
        self.assertEqual(rt_stats["last_boxes"], [])
        self.assertEqual(rt_stats["dingtalk_pending_counts"], {})
        self.assertIsNone(rt_stats["dingtalk_crop_path"])
        self.assertIsNone(rt_stats["dingtalk_batch"])
        self.assertFalse(rt_stats["dingtalk_sending"])
        self.assertEqual(rt_stats["dingtalk_retry_count"], 0)
        self.assertEqual(rt_stats["dingtalk_retry_at"], 0.0)

    def test_reset_tolerates_recorder_release_failure(self):
        rt_stats = app.get_rt_stats()
        rt_stats["recorder"] = mock.Mock()
        rt_stats["recorder"].release.side_effect = RuntimeError("already closed")

        with mock.patch.object(app, "get_rt_stats", return_value=rt_stats):
            app._reset_rt_stats()

        self.assertIsNone(rt_stats["recorder"])

    def test_snapshot_copies_mutable_counters_and_uses_defaults(self):
        rt_stats = app.get_rt_stats()
        rt_stats["classes"] = {"person": 2}
        rt_stats["violation_classes"] = {"no-helmet": 1}
        rt_stats.pop("detect_interval")

        with mock.patch.object(app, "get_rt_stats", return_value=rt_stats):
            snapshot = app._snapshot_rt_stats()

        rt_stats["classes"]["person"] = 99
        rt_stats["violation_classes"]["no-helmet"] = 99
        self.assertEqual(snapshot["classes"], {"person": 2})
        self.assertEqual(snapshot["violation_classes"], {"no-helmet": 1})
        self.assertEqual(snapshot["detect_interval"], app.DETECT_INTERVAL_DEFAULT)


class NotificationHelperTests(unittest.TestCase):
    def test_image_alert_summarizes_counts_and_highest_action(self):
        alerts = [
            {"level": "yellow", "hazard_type": "未穿反光衣", "action": "限时整改"},
            {"level": "red", "hazard_type": "未戴安全帽", "action": "立即停工"},
            {"level": "red", "hazard_type": "未戴安全帽", "action": "立即停工"},
        ]
        with mock.patch.object(app, "send_text", return_value=[("A群", {"errcode": 0})]) as send_text:
            result = app._send_image_alert(
                alerts,
                record_id=12,
                image_path="unused.jpg",
                project_name="A项目",
                inspector="张三",
            )

        message = send_text.call_args.args[0]
        self.assertIn("红色预警", message)
        self.assertIn("项目：A项目", message)
        self.assertIn("检查人：张三", message)
        self.assertIn("未穿反光衣 x 1", message)
        self.assertIn("未戴安全帽 x 2", message)
        self.assertIn("处理建议：立即停工", message)
        self.assertEqual(result, {"status": "sent", "sent_count": 1})

    def test_image_alert_reports_send_failure_without_raising(self):
        alert = {"level": "red", "hazard_type": "未戴安全帽", "action": "停工"}
        with mock.patch.object(app, "send_text", side_effect=RuntimeError("offline")):
            with mock.patch.object(app.st, "caption") as caption:
                result = app._send_image_alert([alert], 1, "unused.jpg")

        caption.assert_called_once()
        self.assertIn("offline", caption.call_args.args[0])
        self.assertEqual(result["status"], "failed")

    def test_realtime_notification_keeps_every_type_and_clears_pending(self):
        rt_stats = app.get_rt_stats()
        rt_stats["dingtalk_pending_counts"] = {
            "no-helmet": 1,
            "no-vest": 2,
            "no-mask": 1,
        }
        rt_stats["dingtalk_last_send"] = 0.0

        with mock.patch("time.time", return_value=120.0):
            with mock.patch.object(app, "send_markdown") as send_markdown:
                app._send_realtime_violations(rt_stats, "A项目", "张三")

        title, message = send_markdown.call_args.args
        self.assertEqual(title, "红色预警 - 实时检测")
        self.assertIn("未戴安全帽", message)
        self.assertIn("未穿反光衣", message)
        self.assertIn("未戴口罩", message)
        self.assertEqual(rt_stats["dingtalk_pending_counts"], {})
        self.assertEqual(rt_stats["dingtalk_last_send"], 120.0)
        self.assertIsNone(rt_stats["dingtalk_batch"])

    def test_realtime_notification_respects_cooldown(self):
        rt_stats = app.get_rt_stats()
        rt_stats["dingtalk_pending_counts"] = {"no-vest": 1}
        rt_stats["dingtalk_last_send"] = 100.0

        with mock.patch("time.time", return_value=120.0):
            with mock.patch.object(app, "send_markdown") as send_markdown:
                app._send_realtime_violations(rt_stats)

        send_markdown.assert_not_called()
        self.assertEqual(rt_stats["dingtalk_pending_counts"], {"no-vest": 1})

    def test_realtime_notification_failure_keeps_data_and_uses_capped_backoff(self):
        rt_stats = app.get_rt_stats()
        rt_stats["dingtalk_pending_counts"] = {"no-helmet": 1}
        rt_stats["dingtalk_last_send"] = 0.0

        for now_ts, retry_at in (
            (120.0, 150.0),
            (150.0, 210.0),
            (210.0, 330.0),
            (330.0, 450.0),
        ):
            with mock.patch("time.time", return_value=now_ts):
                with mock.patch.object(
                    app, "send_markdown", side_effect=RuntimeError("offline")
                ):
                    with self.assertLogs("dingtalk_send", level="ERROR"):
                        app._send_realtime_violations(rt_stats)
            self.assertEqual(rt_stats["dingtalk_pending_counts"], {"no-helmet": 1})
            self.assertEqual(rt_stats["dingtalk_batch"]["counts"], {"no-helmet": 1})
            self.assertEqual(rt_stats["dingtalk_last_send"], 0.0)
            self.assertEqual(rt_stats["dingtalk_retry_at"], retry_at)
            self.assertFalse(rt_stats["dingtalk_sending"])

        self.assertEqual(rt_stats["dingtalk_retry_count"], 4)

    def test_realtime_notification_success_preserves_new_events(self):
        rt_stats = app.get_rt_stats()
        rt_stats["dingtalk_pending_counts"] = {"no-helmet": 1}

        def add_new_event(*args):
            with rt_stats["lock"]:
                rt_stats["dingtalk_pending_counts"]["no-helmet"] += 1

        with mock.patch("time.time", return_value=120.0):
            with mock.patch.object(app, "send_markdown", side_effect=add_new_event):
                app._send_realtime_violations(rt_stats)

        self.assertEqual(rt_stats["dingtalk_pending_counts"], {"no-helmet": 1})
        self.assertIsNone(rt_stats["dingtalk_batch"])

    def test_realtime_image_failure_retries_only_image(self):
        rt_stats = app.get_rt_stats()
        rt_stats["dingtalk_pending_counts"] = {"no-helmet": 1}
        with tempfile.TemporaryDirectory() as temp_dir:
            crop_path = Path(temp_dir) / "crop.jpg"
            crop_path.write_bytes(b"image")
            rt_stats["dingtalk_crop_path"] = str(crop_path)

            with mock.patch.dict(sys.modules, {"dingtalk": fake_dingtalk}):
                with mock.patch.object(app, "send_markdown") as send_markdown:
                    with mock.patch.object(
                        fake_dingtalk,
                        "send_image",
                        side_effect=[RuntimeError("upload failed"), None],
                    ) as send_image:
                        with mock.patch("time.time", return_value=120.0):
                            with self.assertLogs("dingtalk_send", level="ERROR"):
                                app._send_realtime_violations(rt_stats)
                        with mock.patch("time.time", return_value=150.0):
                            app._send_realtime_violations(rt_stats)

        send_markdown.assert_called_once()
        self.assertEqual(send_image.call_count, 2)
        self.assertEqual(rt_stats["dingtalk_pending_counts"], {})
        self.assertIsNone(rt_stats["dingtalk_crop_path"])
        self.assertIsNone(rt_stats["dingtalk_batch"])

    def test_realtime_notification_is_disabled_without_configuration(self):
        rt_stats = app.get_rt_stats()
        rt_stats["dingtalk_pending_counts"] = {"no-helmet": 1}
        with mock.patch.object(app, "_HAS_DINGTALK", False):
            with mock.patch.object(app, "send_markdown") as send_markdown:
                app._send_realtime_violations(rt_stats)
        send_markdown.assert_not_called()


class DrawingHelperTests(unittest.TestCase):
    def test_draw_boxes_uses_alert_color_and_renders_track_id(self):
        detector = types.SimpleNamespace(
            model=types.SimpleNamespace(names={2: "NO-Hardhat"}),
            ALERT_LEVELS=_FakeDetector.ALERT_LEVELS,
            LABEL_CN=_FakeDetector.LABEL_CN,
            _map_label=lambda name: "no-helmet",
        )
        image = np.zeros((40, 60, 3), dtype=np.uint8)
        boxes = [(1, 10, 31, 35, 2, 0.91, 7)]

        with mock.patch.object(app.cv2, "rectangle") as rectangle:
            with mock.patch.object(app, "_put_chinese_text") as draw_text:
                app._draw_boxes(image, boxes, detector)

        rectangle.assert_called_once_with(image, (1, 10), (31, 35), (0, 0, 255), 2)
        self.assertEqual(draw_text.call_count, 2)
        self.assertIn("未戴安全帽 0.91", draw_text.call_args_list[0].args[1])
        self.assertEqual(draw_text.call_args_list[1].args[1], "ID:7")


if __name__ == "__main__":
    unittest.main()
