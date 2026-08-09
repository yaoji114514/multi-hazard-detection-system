import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class _FakeDetector:
    LABEL_CN = {}
    ALERT_LEVELS = {}

    def __init__(self, model_path):
        self.model_version = Path(model_path).name
        self.fallback_used = False
        self.fallback_reason = ""

    @classmethod
    def resolve_model_path(cls):
        return APP_PATH.parent / "models" / "fake.pt"


class _FakeDatabase:
    def get_recent_records(self, limit=50):
        return []

    def get_realtime_violations(self, limit=50):
        return []

    def get_statistics(self):
        return {
            "total_checks": 0,
            "violation_count": 0,
            "compliance_rate": 100.0,
            "no_helmet_total": 0,
        }

    def get_daily_stats(self, days=7):
        return []


class _FakeAlertEngine:
    pass


def _module(name, **members):
    module = types.ModuleType(name)
    for member_name, value in members.items():
        setattr(module, member_name, value)
    return module


class StreamlitAppSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        modules = {
            "detector": _module("detector", HazardDetector=_FakeDetector),
            "database": _module("database", Database=_FakeDatabase),
            "alert": _module("alert", AlertEngine=_FakeAlertEngine),
            "dingtalk": _module(
                "dingtalk",
                DingTalkError=RuntimeError,
                list_webhooks=lambda: [],
                send_text=lambda *args, **kwargs: None,
                send_markdown=lambda *args, **kwargs: None,
            ),
        }
        cls.module_patcher = patch.dict(sys.modules, modules)
        cls.module_patcher.start()
        cls.addClassCleanup(cls.module_patcher.stop)
        cls.app = AppTest.from_file(str(APP_PATH)).run(timeout=30)

    def assert_app_has_no_exception(self):
        self.assertEqual(
            list(self.app.exception),
            [],
            "Streamlit reported an exception while rendering the page",
        )

    def test_default_page_starts_with_expected_navigation(self):
        self.assert_app_has_no_exception()
        self.assertIn("📷 多类隐患智能检测", [item.value for item in self.app.title])
        self.assertEqual(
            self.app.sidebar.radio[0].options,
            ["📷 隐患检测", "🎥 实时检测", "🎬 视频检测", "📋 检测记录", "📊 统计分析"],
        )

    def test_non_camera_pages_render_without_exceptions(self):
        for page, expected_title in (
            ("📋 检测记录", "📋 检测记录"),
            ("📊 统计分析", "📊 统计分析"),
            ("🎬 视频检测", "🎬 视频文件检测"),
        ):
            with self.subTest(page=page):
                self.app.sidebar.radio[0].set_value(page).run(timeout=30)
                self.assert_app_has_no_exception()
                self.assertIn(expected_title, [item.value for item in self.app.title])


if __name__ == "__main__":
    unittest.main()
