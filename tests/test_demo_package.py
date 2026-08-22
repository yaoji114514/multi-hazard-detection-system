import unittest
from pathlib import Path

from tools import make_demo_package


ROOT = Path(__file__).resolve().parents[1]


class DemoPackageTests(unittest.TestCase):
    def test_release_files_include_only_the_baseline_model(self):
        relative_paths = {
            path.relative_to(ROOT).as_posix()
            for path in make_demo_package.release_files(ROOT)
        }

        self.assertIn("models/best.pt", relative_paths)
        self.assertNotIn("models/active_model.txt", relative_paths)
        self.assertNotIn("models/partner_model.pt", relative_paths)
        self.assertIn("使用说明.md", relative_paths)
        self.assertNotIn("README.md", relative_paths)
        self.assertNotIn("run_annotate.bat", relative_paths)
        self.assertNotIn("run_annotate_macos.sh", relative_paths)
        self.assertNotIn("tools/annotate_server.py", relative_paths)
        self.assertNotIn("verify_gpu.py", relative_paths)
        self.assertNotIn("verify_install.py", relative_paths)
        self.assertNotIn("data/sample_videos/test_video_h264.mp4", relative_paths)
        self.assertNotIn("models/ppe_v5.pt", relative_paths)
        self.assertNotIn("config/dingtalk.local.json", relative_paths)
        self.assertNotIn("data/db/hazard_records.db", relative_paths)
        self.assertFalse(any("__pycache__" in path or path.endswith(".pyc") for path in relative_paths))

    def test_release_files_include_cross_platform_installers(self):
        relative_paths = {
            path.relative_to(ROOT).as_posix()
            for path in make_demo_package.release_files(ROOT)
        }

        self.assertTrue({
            "setup.bat", "run.bat", "run_v3.bat", "run_legacy.bat",
            "setup.py", "setup_macos.sh", "run_macos.sh", "run_legacy_macos.sh",
        }.issubset(relative_paths))
        self.assertIn("frontend/dist/index.html", relative_paths)
        self.assertTrue(any(path.startswith("frontend/dist/assets/") for path in relative_paths))

    def test_release_files_are_limited_to_runtime_contents(self):
        relative_paths = {
            path.relative_to(ROOT).as_posix()
            for path in make_demo_package.release_files(ROOT)
        }

        allowed_roots = {
            ".streamlit", "config", "data", "frontend", "models", "src",
            "app.py", "requirements.txt", "run.bat", "run_v3.bat", "run_legacy.bat",
            "run_macos.sh", "run_legacy_macos.sh", "setup.bat", "setup.py",
            "setup_macos.sh", "使用说明.md",
        }
        self.assertTrue(all(path.split("/", 1)[0] in allowed_roots for path in relative_paths))

    def test_archive_name_keeps_the_complete_version(self):
        target = ROOT / "build" / "多类隐患检测系统_正式测试版_v0.1.0-test1_20260811"
        archive, checksum = make_demo_package.archive_paths(target)

        self.assertEqual(
            archive.name, "多类隐患检测系统_正式测试版_v0.1.0-test1_20260811.zip"
        )
        self.assertEqual(checksum.name, archive.name + ".sha256")
