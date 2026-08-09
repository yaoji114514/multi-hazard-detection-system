import sys
import unittest
from unittest import mock

from tools import make_portable


class PortablePackageTests(unittest.TestCase):
    def test_ignore_excludes_rebuildable_and_cache_content(self):
        ignored = make_portable._ignore(
            make_portable.PROJECT_ROOT,
            [
                ".venv", "__pycache__", ".vscode", "compiled.PYC", "keep.py",
                ".coverage", ".coverage.worker-1", "htmlcov",
            ],
        )

        self.assertEqual(
            ignored,
            {
                ".venv", "__pycache__", ".vscode", "compiled.PYC",
                ".coverage", ".coverage.worker-1", "htmlcov",
            },
        )

    def test_ignore_excludes_large_dataset_and_git_lfs_temp(self):
        material_library = make_portable.PROJECT_ROOT / "data" / "material_library"
        self.assertEqual(
            make_portable._ignore(material_library, ["hf_datasets", "keep"]),
            {"hf_datasets"},
        )
        self.assertEqual(
            make_portable._ignore(
                make_portable.PROJECT_ROOT / ".git" / "lfs", ["tmp", "objects"]
            ),
            {"tmp"},
        )
        self.assertEqual(
            make_portable._ignore(
                make_portable.PROJECT_ROOT / ".git",
                ["tmp_obj_123", "objects"],
            ),
            {"tmp_obj_123"},
        )

    def test_generated_manifest_stays_outside_copied_worktree(self):
        target = make_portable.PROJECT_ROOT.parent / "migration" / "project"

        manifest = make_portable._manifest_path(target)

        self.assertEqual(manifest, target.parent / "project_package_manifest.txt")
        self.assertNotEqual(manifest.parent, target)

    def test_main_rejects_project_root_and_nested_targets_before_copying(self):
        targets = (
            make_portable.PROJECT_ROOT,
            make_portable.PROJECT_ROOT / "nested-portable-target",
        )
        for target in targets:
            with self.subTest(target=target):
                with mock.patch.object(
                    sys, "argv", ["make_portable.py", "--target", str(target)]
                ):
                    with mock.patch.object(make_portable.shutil, "copytree") as copytree:
                        with self.assertRaisesRegex(SystemExit, "目标目录不能"):
                            make_portable.main()
                copytree.assert_not_called()


if __name__ == "__main__":
    unittest.main()
