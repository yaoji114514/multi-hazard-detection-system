import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from src.database import Database


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "nested" / "records.sqlite3"
        self.database = Database(self.db_path)

    @staticmethod
    def detection_result(
        *,
        total=1,
        helmet=0,
        no_helmet=0,
        vest=0,
        no_vest=0,
        red=0,
        yellow=0,
        violation=False,
    ):
        return {
            "image": "results/annotated.jpg",
            "detections": [
                {"label": "no-helmet", "confidence": 0.91, "note": "安全帽"}
            ],
            "alerts": [{"level": "red", "description": "立即整改"}],
            "summary": {
                "total_detections": total,
                "helmet_count": helmet,
                "no_helmet_count": no_helmet,
                "vest_count": vest,
                "no_vest_count": no_vest,
                "red_alerts": red,
                "yellow_alerts": yellow,
                "has_violation": violation,
            },
        }

    def test_initialization_creates_parent_directory_and_tables(self):
        self.assertTrue(self.db_path.is_file())

        with closing(sqlite3.connect(self.db_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            detection_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(detection_records)")
            }
            realtime_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(realtime_violations)")
            }

        self.assertIn("detection_records", tables)
        self.assertIn("realtime_violations", tables)
        self.assertIn("model_version", detection_columns)
        self.assertIn("model_version", realtime_columns)

    def test_initialization_migrates_legacy_tables_with_model_version(self):
        legacy_path = Path(self.temp_dir.name) / "legacy.sqlite3"
        with closing(sqlite3.connect(legacy_path)) as connection:
            connection.execute("CREATE TABLE detection_records (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE realtime_violations (id INTEGER PRIMARY KEY)")
            connection.commit()

        Database(legacy_path)

        with closing(sqlite3.connect(legacy_path)) as connection:
            for table_name in ("detection_records", "realtime_violations"):
                columns = {
                    row[1]
                    for row in connection.execute(f"PRAGMA table_info({table_name})")
                }
                self.assertIn("model_version", columns)

    @patch("src.database.datetime")
    def test_save_record_round_trips_payload_and_metadata(self, datetime_mock):
        datetime_mock.now.return_value = datetime(2026, 8, 4, 9, 10, 11)
        result = self.detection_result(
            total=4,
            helmet=1,
            no_helmet=2,
            vest=1,
            red=1,
            yellow=1,
            violation=True,
        )

        record_id = self.database.save_record(
            result,
            image_name="现场.jpg",
            project_name="A 项目",
            inspector="张三",
            model_version="ppe-v4",
        )
        record = self.database.get_recent_records(limit=1)[0]

        self.assertEqual(record_id, record["id"])
        self.assertEqual(record["timestamp"], "2026-08-04 09:10:11")
        self.assertEqual(record["image_name"], "现场.jpg")
        self.assertEqual(record["result_image_path"], "results/annotated.jpg")
        self.assertEqual(record["total_detections"], 4)
        self.assertEqual(record["has_violation"], 1)
        self.assertEqual(record["project_name"], "A 项目")
        self.assertEqual(record["inspector"], "张三")
        self.assertEqual(record["model_version"], "ppe-v4")
        self.assertEqual(json.loads(record["detections_json"]), result["detections"])
        self.assertEqual(json.loads(record["alerts_json"]), result["alerts"])

    @patch("src.database.datetime")
    def test_recent_records_are_newest_first_and_respect_limit(self, datetime_mock):
        datetime_mock.now.side_effect = [
            datetime(2026, 8, 4, 8, 0, 0),
            datetime(2026, 8, 4, 9, 0, 0),
            datetime(2026, 8, 4, 10, 0, 0),
        ]
        for name in ("first.jpg", "second.jpg", "third.jpg"):
            self.database.save_record(self.detection_result(), image_name=name)

        records = self.database.get_recent_records(limit=2)

        self.assertEqual(
            [record["image_name"] for record in records],
            ["third.jpg", "second.jpg"],
        )

    def test_statistics_cover_empty_and_aggregated_records(self):
        self.assertEqual(
            self.database.get_statistics(),
            {
                "total_checks": 0,
                "violation_count": 0,
                "compliance_rate": 100.0,
                "no_helmet_total": 0,
                "no_vest_total": 0,
                "helmet_total": 0,
                "vest_total": 0,
            },
        )

        self.database.save_record(
            self.detection_result(helmet=2, vest=2, violation=False)
        )
        self.database.save_record(
            self.detection_result(no_helmet=2, no_vest=1, violation=True)
        )
        self.database.save_record(
            self.detection_result(helmet=1, no_vest=3, violation=True)
        )

        self.assertEqual(
            self.database.get_statistics(),
            {
                "total_checks": 3,
                "violation_count": 2,
                "compliance_rate": 33.3,
                "no_helmet_total": 2,
                "no_vest_total": 4,
                "helmet_total": 3,
                "vest_total": 2,
            },
        )

    @patch("src.database.datetime")
    def test_daily_statistics_group_by_day_and_limit_newest_days(self, datetime_mock):
        datetime_mock.now.side_effect = [
            datetime(2026, 8, 1, 8, 0, 0),
            datetime(2026, 8, 2, 8, 0, 0),
            datetime(2026, 8, 2, 9, 0, 0),
            datetime(2026, 8, 3, 8, 0, 0),
        ]
        for violation in (False, True, False, True):
            self.database.save_record(
                self.detection_result(violation=violation)
            )

        self.assertEqual(
            self.database.get_daily_stats(days=2),
            [
                {"date": "2026-08-03", "checks": 1, "violations": 1},
                {"date": "2026-08-02", "checks": 2, "violations": 1},
            ],
        )

    @patch("src.database.datetime")
    def test_realtime_violations_round_trip_and_return_newest_first(
        self, datetime_mock
    ):
        datetime_mock.now.side_effect = [
            datetime(2026, 8, 4, 11, 0, 0),
            datetime(2026, 8, 4, 11, 0, 1),
        ]
        first_id = self.database.save_realtime_violation(
            "no-helmet", 1, snapshot_path="snapshots/one.jpg"
        )
        second_id = self.database.save_realtime_violation(
            "no-vest",
            2,
            level="red",
            snapshot_path="snapshots/two.jpg",
            project_name="B 项目",
            inspector="李四",
            model_version="ppe-v5",
        )

        latest = self.database.get_realtime_violations(limit=1)

        self.assertNotEqual(first_id, second_id)
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]["id"], second_id)
        self.assertEqual(latest[0]["timestamp"], "2026-08-04 11:00:01")
        self.assertEqual(latest[0]["violation_type"], "no-vest")
        self.assertEqual(latest[0]["violation_count"], 2)
        self.assertEqual(latest[0]["level"], "red")
        self.assertEqual(latest[0]["snapshot_path"], "snapshots/two.jpg")
        self.assertEqual(latest[0]["project_name"], "B 项目")
        self.assertEqual(latest[0]["inspector"], "李四")
        self.assertEqual(latest[0]["model_version"], "ppe-v5")


if __name__ == "__main__":
    unittest.main()
