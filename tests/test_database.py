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
            incident_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(incident_workflows)")
            }

        self.assertIn("detection_records", tables)
        self.assertIn("realtime_violations", tables)
        self.assertIn("incident_workflows", tables)
        self.assertIn("last_check_context", tables)
        self.assertIn("model_version", detection_columns)
        self.assertIn("model_version", realtime_columns)
        self.assertEqual(
            incident_columns,
            {
                "source_type", "source_id", "status", "assignee", "due_at",
                "resolution_note", "closed_at", "closed_by", "updated_at",
            },
        )

    def test_last_check_context_persists_without_affecting_detection_records(self):
        self.assertEqual(
            self.database.get_last_check_context(),
            {"project_name": "", "inspector": ""},
        )

        self.database.save_last_check_context("A 项目", "张三")
        reopened = Database(self.db_path)

        self.assertEqual(
            reopened.get_last_check_context(),
            {"project_name": "A 项目", "inspector": "张三"},
        )
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM detection_records").fetchone()[0],
                0,
            )

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

    def test_incident_defaults_are_derived_without_rewriting_source_records(self):
        compliant_id = self.database.save_record(
            self.detection_result(helmet=1, violation=False), image_name="compliant.jpg"
        )
        violation_id = self.database.save_record(
            self.detection_result(no_helmet=1, red=1, violation=True), image_name="risk.jpg"
        )
        realtime_id = self.database.save_realtime_violation("no-vest", 1)

        image_records = {record["id"]: record for record in self.database.get_recent_records(limit=10)}
        realtime_records = {record["id"]: record for record in self.database.get_realtime_violations(limit=10)}

        self.assertEqual(image_records[compliant_id]["incident_status"], "not_applicable")
        self.assertEqual(image_records[violation_id]["incident_status"], "pending")
        self.assertEqual(realtime_records[realtime_id]["incident_status"], "pending")
        with closing(sqlite3.connect(self.db_path)) as connection:
            workflow_count = connection.execute(
                "SELECT COUNT(*) FROM incident_workflows"
            ).fetchone()[0]
        self.assertEqual(workflow_count, 0)

    def test_incident_workflow_assignment_close_and_reopen(self):
        record_id = self.database.save_record(
            self.detection_result(no_helmet=1, red=1, violation=True)
        )
        with patch("src.database.datetime") as datetime_mock:
            datetime_mock.now.side_effect = [
                datetime(2026, 8, 10, 8, 0, 0),
                datetime(2026, 8, 10, 9, 0, 0),
                datetime(2026, 8, 10, 10, 0, 0),
                datetime(2026, 8, 10, 11, 0, 0),
            ]
            in_progress = self.database.update_incident_workflow(
                "image",
                record_id,
                status="in_progress",
                assignee="张三",
                due_at="2026-08-11 23:59:59",
            )
            closed = self.database.update_incident_workflow(
                "image",
                record_id,
                status="closed",
                assignee="张三",
                resolution_note="现场复核已整改",
                operator="李四",
            )
            closed_again = self.database.update_incident_workflow(
                "image",
                record_id,
                status="closed",
                assignee="张三",
                resolution_note="补充照片已确认",
                operator="王五",
            )
            reopened = self.database.update_incident_workflow(
                "image",
                record_id,
                status="in_progress",
                assignee="张三",
                resolution_note="需要再次整改",
            )

        self.assertEqual(in_progress["assignee"], "张三")
        self.assertEqual(in_progress["due_at"], "2026-08-11 23:59:59")
        self.assertEqual(closed["closed_at"], "2026-08-10 09:00:00")
        self.assertEqual(closed["closed_by"], "李四")
        self.assertEqual(closed_again["closed_at"], closed["closed_at"])
        self.assertEqual(closed_again["closed_by"], closed["closed_by"])
        self.assertIsNone(reopened["closed_at"])
        self.assertEqual(reopened["closed_by"], "")

    def test_incident_workflow_validates_source_status_and_terminal_evidence(self):
        compliant_id = self.database.save_record(
            self.detection_result(helmet=1, violation=False)
        )
        violation_id = self.database.save_record(
            self.detection_result(no_helmet=1, red=1, violation=True)
        )

        invalid_calls = (
            ("image; DROP TABLE detection_records", violation_id, "pending"),
            ("unknown", violation_id, "pending"),
            ("image", violation_id, "unknown"),
            ("image", 999999, "pending"),
            ("image", compliant_id, "pending"),
        )
        for source_type, source_id, status in invalid_calls:
            with self.subTest(source_type=source_type, source_id=source_id, status=status):
                with self.assertRaises(ValueError):
                    self.database.update_incident_workflow(
                        source_type, source_id, status=status
                    )

        with self.assertRaises(ValueError):
            self.database.update_incident_workflow(
                "image", violation_id, status="false_positive", operator="李四"
            )

    def test_incident_statistics_include_image_and_realtime_workflows(self):
        pending_image = self.database.save_record(
            self.detection_result(no_helmet=1, red=1, violation=True)
        )
        active_realtime = self.database.save_realtime_violation("no-vest", 1)
        closed_realtime = self.database.save_realtime_violation("no-helmet", 1, level="red")
        self.database.update_incident_workflow(
            "realtime",
            active_realtime,
            status="in_progress",
            assignee="张三",
            due_at="2000-01-01 23:59:59",
        )
        self.database.update_incident_workflow(
            "realtime",
            closed_realtime,
            status="closed",
            assignee="李四",
            resolution_note="整改完成",
            operator="王五",
        )

        stats = self.database.get_incident_statistics()

        self.assertGreater(pending_image, 0)
        self.assertEqual(
            stats,
            {
                "total": 3,
                "pending": 1,
                "in_progress": 1,
                "closed": 1,
                "false_positive": 0,
                "overdue": 1,
            },
        )

    def test_incident_queues_keep_every_open_item_and_limit_only_history(self):
        image_ids = [
            self.database.save_record(
                self.detection_result(no_helmet=1, red=1, violation=True),
                image_name=f"risk-{index}.jpg",
            )
            for index in range(3)
        ]
        self.database.update_incident_workflow(
            "image",
            image_ids[0],
            status="closed",
            resolution_note="整改完成",
            operator="复核人",
        )
        self.database.save_record(
            self.detection_result(helmet=1, violation=False), image_name="compliant.jpg"
        )

        image_queue = self.database.get_image_incident_queue(history_limit=1)
        image_open_ids = {
            row["id"] for row in image_queue
            if row["incident_status"] in {"pending", "in_progress"}
        }
        self.assertEqual(image_open_ids, set(image_ids[1:]))
        self.assertEqual(
            sum(row["incident_status"] not in {"pending", "in_progress"} for row in image_queue),
            1,
        )

        realtime_ids = [
            self.database.save_realtime_violation("no-vest", 1)
            for _ in range(3)
        ]
        self.database.update_incident_workflow(
            "realtime",
            realtime_ids[0],
            status="false_positive",
            resolution_note="画面遮挡导致误判",
            operator="复核人",
        )
        realtime_queue = self.database.get_realtime_incident_queue(history_limit=0)
        self.assertEqual(
            {row["id"] for row in realtime_queue},
            set(realtime_ids[1:]),
        )
        with self.assertRaises(ValueError):
            self.database.get_image_incident_queue(history_limit=-1)


if __name__ == "__main__":
    unittest.main()
