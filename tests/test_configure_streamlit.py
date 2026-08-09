import importlib.util
import io
import os
import runpy
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def _load_configure_module():
    spec = importlib.util.spec_from_file_location(
        "_configure_streamlit_under_test",
        ROOT / "src" / "configure_streamlit.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


configure_streamlit = _load_configure_module()


class ConfigureStreamlitTests(unittest.TestCase):
    def test_main_creates_credentials_under_userprofile(self):
        with TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                configure_streamlit.os.environ,
                {"USERPROFILE": temp_dir},
                clear=True,
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    configure_streamlit.main()

            credentials = Path(temp_dir) / ".streamlit" / "credentials.toml"
            self.assertEqual(
                credentials.read_text(encoding="utf-8"),
                '[general]\nemail = ""\n',
            )
            self.assertIn(str(credentials), output.getvalue())

    def test_main_preserves_existing_credentials(self):
        with TemporaryDirectory() as temp_dir:
            credentials = Path(temp_dir) / ".streamlit" / "credentials.toml"
            credentials.parent.mkdir()
            credentials.write_text(
                '[general]\nemail = "existing@example.test"\n',
                encoding="utf-8",
            )

            with mock.patch.dict(
                configure_streamlit.os.environ,
                {"USERPROFILE": temp_dir},
                clear=True,
            ):
                with redirect_stdout(io.StringIO()):
                    configure_streamlit.main()

            self.assertEqual(
                credentials.read_text(encoding="utf-8"),
                '[general]\nemail = "existing@example.test"\n',
            )

    def test_main_uses_expanduser_when_userprofile_is_unset(self):
        with TemporaryDirectory() as temp_dir:
            with mock.patch.dict(configure_streamlit.os.environ, {}, clear=True):
                with mock.patch.object(
                    configure_streamlit.os.path,
                    "expanduser",
                    return_value=temp_dir,
                ) as expanduser:
                    with redirect_stdout(io.StringIO()):
                        configure_streamlit.main()

            expanduser.assert_called_once_with("~")
            self.assertTrue(
                (Path(temp_dir) / ".streamlit" / "credentials.toml").is_file()
            )

    def test_main_reports_directory_creation_error_and_returns(self):
        stderr = io.StringIO()
        with mock.patch.dict(
            configure_streamlit.os.environ,
            {"USERPROFILE": "C:\\unwritable-home"},
            clear=True,
        ):
            with mock.patch.object(
                configure_streamlit.os,
                "makedirs",
                side_effect=OSError("permission denied"),
            ):
                with mock.patch("builtins.open") as open_file:
                    with redirect_stderr(stderr):
                        configure_streamlit.main()

        open_file.assert_not_called()
        self.assertIn("permission denied", stderr.getvalue())

    def test_main_reports_credentials_write_error(self):
        with TemporaryDirectory() as temp_dir:
            stderr = io.StringIO()
            with mock.patch.dict(
                configure_streamlit.os.environ,
                {"USERPROFILE": temp_dir},
                clear=True,
            ):
                with mock.patch(
                    "builtins.open", side_effect=OSError("read-only filesystem")
                ) as open_file:
                    with redirect_stderr(stderr):
                        configure_streamlit.main()

            open_file.assert_called_once()
            self.assertIn("read-only filesystem", stderr.getvalue())
            self.assertFalse(
                (Path(temp_dir) / ".streamlit" / "credentials.toml").exists()
            )

    def test_script_entry_point_runs_main(self):
        with TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                os.environ,
                {"USERPROFILE": temp_dir},
                clear=True,
            ):
                with redirect_stdout(io.StringIO()):
                    runpy.run_path(
                        str(ROOT / "src" / "configure_streamlit.py"),
                        run_name="__main__",
                    )

            self.assertTrue(
                (Path(temp_dir) / ".streamlit" / "credentials.toml").is_file()
            )


if __name__ == "__main__":
    unittest.main()
