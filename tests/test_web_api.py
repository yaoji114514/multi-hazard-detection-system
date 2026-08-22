import io
import json
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException, UploadFile
from PIL import Image

from src import web_api


class FakeDatabase:
    def __init__(self):
        self.context = {"project_name": "", "inspector": ""}
        self.saved_records = []
        self.realtime_records = []
        self.fail_realtime = False

    def get_last_check_context(self):
        return dict(self.context)

    def save_last_check_context(self, project_name="", inspector=""):
        self.context = {"project_name": project_name, "inspector": inspector}

    def get_incident_statistics(self):
        return {
            "total": 2, "pending": 2, "in_progress": 0, "closed": 0,
            "false_positive": 0, "overdue": 0,
        }

    def get_statistics(self):
        return {
            "total_checks": 4, "violation_count": 2, "compliance_rate": 50.0,
            "no_helmet_total": 3, "no_vest_total": 1,
            "helmet_total": 1, "vest_total": 2,
        }

    def get_daily_stats(self, days=7):
        return [{"date": "2026-08-22", "checks": 4, "violations": 2}]

    def save_record(self, result, **metadata):
        self.saved_records.append((result, metadata))
        return len(self.saved_records)

    def save_realtime_violation(self, **record):
        if self.fail_realtime:
            raise RuntimeError("database path must never escape")
        self.realtime_records.append(record)
        return len(self.realtime_records)

    def get_image_incident_queue(self, history_limit=200):
        return [{
            "id": 11,
            "timestamp": "2026-08-22 09:00:00",
            "image_name": "现场.jpg",
            "result_image_path": str(web_api.UPLOADS_DIR / "annotated.jpg"),
            "red_alerts": 1,
            "yellow_alerts": 0,
            "has_violation": 1,
            "detections_json": "[]",
            "alerts_json": "[]",
            "project_name": "A 项目",
            "inspector": "张工",
            "incident_status": "pending",
            "assignee": "",
            "due_at": None,
            "resolution_note": "",
        }]

    def get_realtime_incident_queue(self, history_limit=200):
        return [{
            "id": 7,
            "timestamp": "2026-08-22 10:00:00",
            "violation_type": "no-vest",
            "violation_count": 1,
            "level": "yellow",
            "snapshot_path": str(web_api.SNAPSHOTS_DIR / "frame.jpg"),
            "project_name": "A 项目",
            "inspector": "张工",
            "incident_status": "in_progress",
            "assignee": "李工",
            "due_at": None,
            "resolution_note": "处理中",
        }]

    def update_incident_workflow(self, source_type, source_id, **payload):
        return {"source_type": source_type, "source_id": source_id, **payload}


class FakeDetector:
    model_version = "fake.pt"

    def __init__(self):
        self.frame_label = "no-helmet"

    def detect(self, image_path, conf=0.4):
        annotated = web_api.UPLOADS_DIR / "annotated.jpg"
        annotated.write_bytes(Path(image_path).read_bytes())
        detections = [{
            "label": "未戴安全帽",
            "label_en": "no-helmet",
            "confidence": 0.91,
            "bbox": [1, 2, 20, 30],
            "alert_level": "red",
            "alert_name": "红色预警",
            "description": "未佩戴安全帽,立即停工整改",
        }]
        return {
            "image": str(annotated),
            "detections": detections,
            "alerts": [],
            "summary": web_api._summary_from_detections(detections),
        }

    def detect_frame(self, _data, _confidence):
        if self.frame_label is None:
            return {
                "detections": [],
                "summary": web_api._summary_from_detections([]),
            }
        is_red = self.frame_label == "no-helmet"
        detections = [{
            "label": "未戴安全帽" if is_red else "未穿反光衣",
            "label_en": self.frame_label,
            "confidence": 0.88,
            "bbox": [1, 2, 20, 30],
            "alert_level": "red" if is_red else "yellow",
            "alert_name": "红色预警" if is_red else "黄色预警",
            "description": "现场存在个人防护隐患",
        }]
        return {"detections": detections, "summary": web_api._summary_from_detections(detections)}


def jpeg_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (24, 16), "#8fa1b5").save(stream, format="JPEG")
    return stream.getvalue()


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.uploads = self.root / "data" / "uploads"
        self.snapshots = self.uploads / "snapshots"
        self.config = self.root / "config" / "dingtalk.local.json"
        self.uploads.mkdir(parents=True)
        self.snapshots.mkdir(parents=True)
        self.config.parent.mkdir(parents=True)
        self.database = FakeDatabase()
        self.detector = FakeDetector()
        self.path_patchers = [
            patch.object(web_api, "ROOT_DIR", self.root),
            patch.object(web_api, "DATA_DIR", self.root / "data"),
            patch.object(web_api, "UPLOADS_DIR", self.uploads),
            patch.object(web_api, "SNAPSHOTS_DIR", self.snapshots),
            patch.object(web_api, "DINGTALK_CONFIG_PATH", self.config),
            patch.object(web_api, "_database", self.database),
            patch.object(web_api, "_detector", self.detector),
            patch.object(web_api, "_alert_engine", None),
            patch.object(web_api, "_start_notification_timer_locked"),
        ]
        for patcher in self.path_patchers:
            patcher.start()
        with web_api._realtime_lock:
            web_api._realtime_sessions.clear()
        with web_api._video_jobs_lock:
            web_api._video_jobs.clear()
    def tearDown(self):
        for patcher in reversed(self.path_patchers):
            patcher.stop()
        self.temp.cleanup()

    def write_notification_config(self):
        groups = [
            {
                "name": "现场一群",
                "webhook": "https://oapi.dingtalk.com/robot/send?access_token=secret-a",
                "enabled": True,
                "open_conversation_id": "cid-a",
                "custom_credential": "keep-a",
            },
            {
                "name": "现场二群",
                "webhook": "https://oapi.dingtalk.com/robot/send?access_token=secret-b",
                "enabled": True,
                "open_conversation_id": "cid-b",
                "custom_credential": "keep-b",
            },
        ]
        config = {"app_key": "key", "app_secret": "secret", "webhooks": groups}
        self.config.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return config

    def test_media_rejects_path_traversal(self):
        outside = self.root / "secret.txt"
        outside.write_text("private", encoding="utf-8")
        safe = self.uploads / "safe.jpg"
        safe.write_bytes(jpeg_bytes())

        self.assertEqual(safe.resolve(), web_api._resolve_media("uploads", "safe.jpg"))
        with self.assertRaises(HTTPException) as caught:
            web_api._resolve_media("uploads", "../secret.txt")
        self.assertEqual(404, caught.exception.status_code)
        self.assertNotIn(str(self.root), caught.exception.detail)
        self.assertNotIn("private", caught.exception.detail)

    def test_context_is_trimmed_and_allows_partial_or_empty_values(self):
        response = web_api.put_context(
            web_api.ContextPayload(project_name="  一标段  ", inspector="  王工 ")
        )
        self.assertEqual(
            {"project_name": "一标段", "inspector": "王工"},
            web_api.get_context(),
        )
        self.assertEqual("一标段", response["project_name"])
        partial = web_api.put_context(
            web_api.ContextPayload(project_name="", inspector="  王工 ")
        )
        self.assertEqual({"project_name": "", "inspector": "王工"}, partial)
        with self.assertRaises(HTTPException):
            web_api._clean_context("", "王工")

    def test_incidents_combines_sources_without_exposing_paths(self):
        body = web_api.get_incidents(quick="open", search="", inspector="", history_limit=200)
        self.assertEqual({"image", "realtime"}, {item["source_type"] for item in body["items"]})
        self.assertEqual(2, body["total"])
        self.assertNotIn(str(self.root), json.dumps(body, ensure_ascii=False))
        self.assertTrue(all(item["evidence_url"].startswith("/api/media/") for item in body["items"]))

    def test_image_notification_failure_does_not_remove_record(self):
        with patch.object(
            web_api.dingtalk, "send_text", side_effect=RuntimeError("secret failure")
        ), patch.object(web_api._LOG, "warning"):
            response = asyncio.run(
                web_api.detect_image(
                    UploadFile(io.BytesIO(jpeg_bytes()), filename="site.jpg"),
                    project_name="一标段",
                    inspector="王工",
                    confidence=0.4,
                )
            )

        self.assertEqual(1, response["record_id"])
        self.assertEqual("failed", response["notification"]["status"])
        self.assertEqual(1, len(self.database.saved_records))
        self.assertNotIn("secret failure", json.dumps(response, ensure_ascii=False))

    def test_notification_save_rejects_all_disabled_and_duplicate_binding(self):
        original = self.write_notification_config()
        listed = web_api.dingtalk.list_webhooks(self.config)
        all_disabled = {
            "groups": [
                {"short_id": item["short_id"], "name": item["name"], "enabled": False}
                for item in listed
            ]
        }
        with self.assertRaises(HTTPException) as response:
            web_api.put_notification_groups(web_api.NotificationGroupsPayload(**all_disabled))
        self.assertEqual(422, response.exception.status_code)
        self.assertEqual(original, json.loads(self.config.read_text(encoding="utf-8")))

        duplicated = {
            "groups": [
                {
                    "short_id": item["short_id"],
                    "name": item["name"],
                    "enabled": True,
                    "new_open_conversation_id": "same-id",
                }
                for item in listed
            ]
        }
        with self.assertRaises(HTTPException) as response:
            web_api.put_notification_groups(web_api.NotificationGroupsPayload(**duplicated))
        self.assertEqual(422, response.exception.status_code)
        self.assertEqual(original, json.loads(self.config.read_text(encoding="utf-8")))

    def test_notification_save_preserves_credentials(self):
        original = self.write_notification_config()
        listed = web_api.dingtalk.list_webhooks(self.config)
        payload = {
            "groups": [{
                "short_id": listed[0]["short_id"],
                "name": "已核对的一群",
                "enabled": False,
                "new_open_conversation_id": None,
            }]
        }

        response = web_api.put_notification_groups(web_api.NotificationGroupsPayload(**payload))

        saved = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(original["app_secret"], saved["app_secret"])
        self.assertEqual(original["webhooks"][0]["webhook"], saved["webhooks"][0]["webhook"])
        self.assertEqual("keep-a", saved["webhooks"][0]["custom_credential"])
        self.assertEqual("cid-a", saved["webhooks"][0]["open_conversation_id"])
        self.assertEqual("已核对的一群", saved["webhooks"][0]["name"])
        self.assertFalse(saved["webhooks"][0]["enabled"])
        response_text = json.dumps(response, ensure_ascii=False)
        self.assertNotIn("access_token", response_text)
        self.assertNotIn("cid-a", response_text)

    def test_notification_read_and_refresh_never_expose_or_save_binding(self):
        self.write_notification_config()
        original = self.config.read_bytes()
        first = web_api.dingtalk.list_webhooks(self.config)[0]
        identity = {
            "status": "verified", "source": "dingtalk", "official_name": "官方一群",
            "reason": "", "checked_at": 1.0,
        }
        with patch.object(web_api.dingtalk, "resolve_group_identity", return_value=identity):
            groups = web_api.get_notification_groups()
            refreshed = web_api.refresh_notification_group(first["short_id"])

        public_text = json.dumps({"groups": groups, "refreshed": refreshed}, ensure_ascii=False)
        self.assertIn("官方一群", public_text)
        self.assertNotIn("access_token", public_text)
        self.assertNotIn("cid-a", public_text)
        self.assertEqual(original, self.config.read_bytes())

    def test_realtime_storage_failure_does_not_increment_stored_count(self):
        self.database.fail_realtime = True
        with patch.object(web_api.dingtalk, "send_text") as send_text:
            response = asyncio.run(
                web_api.realtime_frame(
                    UploadFile(io.BytesIO(jpeg_bytes()), filename="frame.jpg"),
                    project_name="一标段",
                    inspector="王工",
                    session="camera-1",
                    confidence=0.4,
                )
            )

        session = response["session"]
        self.assertEqual(0, session["stored_count"])
        self.assertEqual(1, session["storage_errors"])
        self.assertEqual([], response["stored_events"])
        send_text.assert_not_called()
        self.assertNotIn("database path", json.dumps(response, ensure_ascii=False))

        # 同一类型仍在冷却期，不会按帧反复累计或反复尝试写库。
        repeated = asyncio.run(
            web_api.realtime_frame(
                UploadFile(io.BytesIO(jpeg_bytes()), filename="frame.jpg"),
                project_name="一标段",
                inspector="王工",
                session="camera-1",
                confidence=0.4,
            )
        )
        self.assertEqual(1, repeated["session"]["observed_violations"])
        self.assertEqual(1, repeated["session"]["storage_errors"])

        # 另一类新事件可保存，但不能抹掉之前持续展示的存储错误。
        self.database.fail_realtime = False
        self.detector.frame_label = "no-vest"
        recovered = asyncio.run(
            web_api.realtime_frame(
                UploadFile(io.BytesIO(jpeg_bytes()), filename="frame.jpg"),
                project_name="一标段",
                inspector="王工",
                session="camera-1",
                confidence=0.4,
            )
        )
        self.assertEqual(1, recovered["session"]["stored_count"])
        self.assertEqual("证据保存失败", recovered["session"]["last_error"])
        self.assertEqual("queued", recovered["session"]["notification_status"])

    def test_realtime_inference_without_violation_is_blue(self):
        self.detector.frame_label = None
        response = asyncio.run(
            web_api.realtime_frame(
                UploadFile(io.BytesIO(jpeg_bytes()), filename="frame.jpg"),
                project_name="一标段",
                inspector="王工",
                session="camera-safe",
                confidence=0.4,
            )
        )
        self.assertEqual("blue", response["risk"])
        self.assertEqual("blue", response["session"]["last_risk"])
        self.assertEqual(0, response["session"]["observed_violations"])
        self.assertEqual(0, response["session"]["stored_count"])

    def test_realtime_notification_failure_is_visible_on_session_poll(self):
        response = asyncio.run(
            web_api.realtime_frame(
                UploadFile(io.BytesIO(jpeg_bytes()), filename="frame.jpg"),
                project_name="一标段",
                inspector="王工",
                session="camera-2",
                confidence=0.4,
            )
        )
        self.assertEqual("queued", response["session"]["notification_status"])
        with patch.object(web_api.dingtalk, "send_text", return_value=[("群", {})]) as send_text, patch.object(
            web_api.dingtalk, "send_image", side_effect=RuntimeError("private")
        ), patch.object(web_api._LOG, "warning"):
            web_api._notification_worker("camera-2")
        polled = web_api.get_realtime_session("camera-2")
        self.assertEqual("failed", polled["notification_status"])
        self.assertEqual(1, polled["retry_count"])
        self.assertGreater(polled["retry_at"], 0)
        self.assertIn("现场截图", polled["notification_error"])
        self.assertNotIn("private", json.dumps(polled, ensure_ascii=False))

        # 文字已经成功，下一轮只重试尚未送达的截图。
        retry_states = []

        def successful_retry(*_args, **_kwargs):
            retry_states.append(
                web_api.get_realtime_session("camera-2")["notification_status"]
            )
            return [("群", {})]

        with patch.object(web_api.dingtalk, "send_text") as retried_text, patch.object(
            web_api.dingtalk, "send_image", side_effect=successful_retry
        ) as retried_image:
            web_api._notification_worker("camera-2")
        final = web_api.get_realtime_session("camera-2")
        self.assertEqual("sent", final["notification_status"])
        self.assertEqual(0, final["retry_count"])
        self.assertEqual(0.0, final["retry_at"])
        self.assertIsNone(final["notification_error"])
        send_text.assert_called_once()
        retried_text.assert_not_called()
        retried_image.assert_called_once()
        self.assertEqual(["retrying"], retry_states)

        self.assertEqual(30.0, web_api._notification_retry_delay(1))
        self.assertEqual(60.0, web_api._notification_retry_delay(2))
        self.assertEqual(120.0, web_api._notification_retry_delay(3))
        self.assertEqual(120.0, web_api._notification_retry_delay(20))

    def test_video_job_contract_never_claims_incident_or_notification(self):
        tasks = BackgroundTasks()
        response = asyncio.run(
            web_api.create_video_job(
                tasks,
                UploadFile(io.BytesIO(b"fake-mp4"), filename="clip.mp4"),
                confidence=0.4,
            )
        )
        self.assertEqual("queued", response["status"])
        self.assertEqual(
            {"creates_incident": False, "sends_notification": False},
            response["boundary"],
        )
        self.assertFalse(any(key.startswith("_") for key in response))
        self.assertEqual(response, web_api.get_video_job(response["job_id"]))

    def test_bootstrap_and_statistics_have_frontend_contract(self):
        bootstrap = web_api.bootstrap()
        statistics = web_api.statistics(days=7)

        self.assertEqual(2, bootstrap["workflow"]["pending"])
        self.assertEqual("no-helmet", statistics["hazard_ranking"][0]["key"])


if __name__ == "__main__":
    unittest.main()
