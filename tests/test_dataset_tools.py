import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools import build_partner_review_dataset as partner_review
from tools import evaluate_model
from tools import sanitize_datasets


def _sample(
    digest,
    name,
    label_text,
    classes,
    box_count,
    *,
    from_val=False,
):
    return sanitize_datasets.Sample(
        digest=digest,
        name=name,
        suffix=Path(name).suffix,
        label_text=label_text,
        classes=frozenset(classes),
        box_count=box_count,
        source_path=None,
        image_bytes=b"image",
        from_val=from_val,
    )


class LabelParsingTests(unittest.TestCase):
    def test_parse_label_normalizes_values_and_collects_classes(self):
        text = "2 0.5 0.25 0.2 0.4\n\n7 1 0 0.1 0.2\n"

        normalized, classes, box_count = sanitize_datasets.parse_label(
            text, "sample.txt"
        )

        self.assertEqual(
            normalized,
            "2 0.500000 0.250000 0.200000 0.400000\n"
            "7 1.000000 0.000000 0.100000 0.200000",
        )
        self.assertEqual(classes, frozenset({2, 7}))
        self.assertEqual(box_count, 2)

    def test_parse_label_accepts_empty_label(self):
        self.assertEqual(
            sanitize_datasets.parse_label("\n  \n", "empty.txt"),
            ("", frozenset(), 0),
        )

    def test_parse_label_rejects_malformed_rows(self):
        cases = {
            "0 0.5 0.5 0.2": "expected 5 columns",
            "zero 0.5 0.5 0.2 0.2": "invalid number",
            "10 0.5 0.5 0.2 0.2": "class 10 is invalid",
            "0 1.1 0.5 0.2 0.2": "coordinate outside [0, 1]",
            "0 0.5 0.5 0 0.2": "box size must be positive",
        }
        for text, message in cases.items():
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, message.replace("[", r"\[").replace("]", r"\]")):
                    sanitize_datasets.parse_label(text, "bad.txt")

    def test_iter_images_is_sorted_and_filters_non_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ("b.PNG", "a.jpg", "notes.txt"):
                (root / name).write_bytes(b"x")
            (root / "nested").mkdir()

            self.assertEqual(
                [path.name for path in sanitize_datasets.iter_images(root)],
                ["a.jpg", "b.PNG"],
            )


class DatasetSelectionTests(unittest.TestCase):
    def test_choose_representatives_prefers_more_boxes_and_preserves_val(self):
        train = _sample("same", "train.jpg", "0 box", {0}, 1)
        val = _sample(
            "same", "val.jpg", "0 box\n1 box", {0, 1}, 2, from_val=True
        )
        other = _sample("other", "other.jpg", "2 box", {2}, 1)

        chosen, duplicate_files, label_conflicts = (
            sanitize_datasets.choose_representatives([train, val, other])
        )

        self.assertEqual(chosen["same"].name, "val.jpg")
        self.assertTrue(chosen["same"].from_val)
        self.assertEqual(duplicate_files, 1)
        self.assertEqual(label_conflicts, 1)

    def test_class_presence_counts_each_class_once_per_image(self):
        samples = {
            "a": _sample("a", "a.jpg", "", {1, 2}, 2),
            "b": _sample("b", "b.jpg", "", {2}, 1),
        }

        counts = sanitize_datasets.class_presence(samples, {"a", "b"})

        self.assertEqual(counts[1], 1)
        self.assertEqual(counts[2], 2)

    def test_unique_output_name_avoids_case_insensitive_collisions(self):
        sample = _sample("abcdef123456", "Photo.JPG", "", set(), 0)
        used = {"photo"}

        first = sanitize_datasets.unique_output_name(sample, used)
        second = sanitize_datasets.unique_output_name(sample, used)

        self.assertEqual(first, "Photo_abcdef12.JPG")
        self.assertEqual(second, "Photo_abcdef12_2.JPG")
        self.assertIn("photo_abcdef12_2", used)


class PartnerPredictionMergeTests(unittest.TestCase):
    def test_box_iou_handles_identical_disjoint_and_zero_area_boxes(self):
        self.assertAlmostEqual(partner_review.box_iou([0.5, 0.5, 0.4, 0.4], [0.5, 0.5, 0.4, 0.4]), 1.0)
        self.assertEqual(partner_review.box_iou([0.1, 0.1, 0.1, 0.1], [0.9, 0.9, 0.1, 0.1]), 0.0)
        self.assertEqual(partner_review.box_iou([0.5, 0.5, 0.0, 0.0], [0.5, 0.5, 0.0, 0.0]), 0.0)

    def test_merge_predictions_suppresses_only_same_class_overlap(self):
        high = {"class": 2, "conf": 0.9, "coords": [0.5, 0.5, 0.4, 0.4]}
        duplicate = {"class": 2, "conf": 0.4, "coords": [0.5, 0.5, 0.4, 0.4]}
        other_class = {"class": 3, "conf": 0.8, "coords": [0.5, 0.5, 0.4, 0.4]}
        separate = {"class": 2, "conf": 0.7, "coords": [0.1, 0.1, 0.1, 0.1]}

        merged = partner_review.merge_predictions(
            [duplicate, other_class, separate, high]
        )

        self.assertEqual(merged, [high, separate, other_class])


class EvaluationDatasetTests(unittest.TestCase):
    def _write_dataset(self, root):
        dataset = root / "dataset"
        image_dir = dataset / "images" / "val"
        label_dir = dataset / "labels" / "val"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        (image_dir / "sample.jpg").write_bytes(b"not decoded by validation")
        (label_dir / "sample.txt").write_text(
            "0 0.5 0.5 0.25 0.25\n1 0.1 0.2 0.3 0.4\n",
            encoding="utf-8",
        )
        data_file = root / "data.yaml"
        data_file.write_text(
            "path: dataset\nval: images/val\nnames: [Hardhat, Mask]\n",
            encoding="utf-8",
        )
        return data_file, image_dir, label_dir

    def test_check_dataset_accepts_matching_images_and_valid_labels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file, _, _ = self._write_dataset(Path(temp_dir))

            image_count, object_count, names = evaluate_model.check_dataset(data_file)

            self.assertEqual((image_count, object_count), (1, 2))
            self.assertEqual(names, {0: "Hardhat", 1: "Mask"})

    def test_check_dataset_reports_missing_or_invalid_labels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file, image_dir, label_dir = self._write_dataset(Path(temp_dir))
            (image_dir / "missing.png").write_bytes(b"x")
            (label_dir / "sample.txt").write_text(
                "3 1.2 0.5 0 0.2\n", encoding="utf-8"
            )

            with self.assertRaises(ValueError) as context:
                evaluate_model.check_dataset(data_file)

            message = str(context.exception)
            self.assertIn("Missing label: missing.txt", message)
            self.assertIn("invalid class id 3", message)
            self.assertIn("coordinates must be within 0-1", message)
            self.assertIn("width and height must be greater than 0", message)

    def test_resolve_dataset_rejects_invalid_yaml_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file = Path(temp_dir) / "data.yaml"
            data_file.write_text("path: .\nval: [images]\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "names list or mapping"):
                evaluate_model.resolve_dataset(data_file)

    def test_check_model_classes_requires_exact_mapping(self):
        evaluate_model.check_model_classes(
            SimpleNamespace(names={0: "Hardhat"}), {0: "Hardhat"}
        )
        with self.assertRaisesRegex(ValueError, "Model classes do not match"):
            evaluate_model.check_model_classes(
                SimpleNamespace(names={0: "Mask"}), {0: "Hardhat"}
            )


if __name__ == "__main__":
    unittest.main()
