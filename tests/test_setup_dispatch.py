import importlib.util
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("setup_dispatch_under_test", ROOT / "setup.py")
setup_dispatch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup_dispatch)


class SetupDispatcherTests(unittest.TestCase):
    def test_windows_dispatches_to_existing_batch_installer(self):
        completed = mock.Mock(returncode=0)
        with mock.patch.object(setup_dispatch.platform, "system", return_value="Windows"):
            with mock.patch.object(setup_dispatch.subprocess, "run", return_value=completed) as run:
                self.assertEqual(0, setup_dispatch.main())
        run.assert_called_once_with(
            ["cmd", "/c", str(ROOT / "setup.bat")], cwd=ROOT, check=False
        )

    def test_macos_dispatches_to_macos_installer(self):
        completed = mock.Mock(returncode=0)
        with mock.patch.object(setup_dispatch.platform, "system", return_value="Darwin"):
            with mock.patch.object(setup_dispatch.subprocess, "run", return_value=completed) as run:
                self.assertEqual(0, setup_dispatch.main())
        run.assert_called_once_with(
            ["/bin/bash", str(ROOT / "setup_macos.sh")], cwd=ROOT, check=False
        )

    def test_unsupported_system_returns_error_without_subprocess(self):
        with mock.patch.object(setup_dispatch.platform, "system", return_value="Linux"):
            with mock.patch.object(setup_dispatch.subprocess, "run") as run:
                self.assertEqual(1, setup_dispatch.main())
        run.assert_not_called()
