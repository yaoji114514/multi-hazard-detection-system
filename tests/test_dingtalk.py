import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

from src import dingtalk


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self._body


class DingTalkTestCase(unittest.TestCase):
    WEBHOOK_A = "https://oapi.dingtalk.com/robot/send?access_token=test-a"
    WEBHOOK_B = "https://oapi.dingtalk.com/robot/send?access_token=test-b"
    WEBHOOK_C = "https://oapi.dingtalk.com/robot/send?access_token=test-c"

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        self.config_path = Path(self._temp_dir.name) / "dingtalk.test.json"

        self._urlopen_patch = mock.patch.object(dingtalk, "urlopen")
        self.urlopen = self._urlopen_patch.start()
        self.addCleanup(self._urlopen_patch.stop)
        self.urlopen.side_effect = AssertionError("unexpected real network request")
        self._reset_token_cache()
        dingtalk.clear_group_identity_cache()

    def tearDown(self):
        self._reset_token_cache()
        dingtalk.clear_group_identity_cache()

    @staticmethod
    def _reset_token_cache():
        dingtalk._TOKEN_CACHE.update(token=None, expires_at=0)

    def write_config(self, config, *, with_bom=False):
        encoding = "utf-8-sig" if with_bom else "utf-8"
        self.config_path.write_text(
            json.dumps(config, ensure_ascii=False), encoding=encoding
        )

    def write_standard_config(self, webhooks=None):
        if webhooks is None:
            webhooks = [
                {"name": "group-a", "webhook": self.WEBHOOK_A, "enabled": True}
            ]
        self.write_config(
            {
                "app_key": "test-app-key",
                "app_secret": "test-app-secret",
                "webhooks": webhooks,
            }
        )

    def image_path(self):
        path = Path(self._temp_dir.name) / "snapshot.jpg"
        path.write_bytes(b"fake-jpeg-bytes")
        return path


class ConfigTests(DingTalkTestCase):
    def test_load_config_accepts_legacy_webhook_and_utf8_bom(self):
        self.write_config(
            {
                "app_key": "  legacy-key  ",
                "app_secret": "  legacy-secret  ",
                "webhook": f"  {self.WEBHOOK_A}  ",
            },
            with_bom=True,
        )

        app_key, app_secret, webhooks = dingtalk.load_config(self.config_path)

        self.assertEqual("legacy-key", app_key)
        self.assertEqual("legacy-secret", app_secret)
        self.assertEqual(1, len(webhooks))
        self.assertEqual(self.WEBHOOK_A, webhooks[0]["webhook"])
        self.assertTrue(webhooks[0]["enabled"])
        self.assertTrue(webhooks[0]["name"])

    def test_load_config_returns_only_enabled_groups(self):
        self.write_standard_config(
            [
                {"name": "on-a", "webhook": self.WEBHOOK_A, "enabled": True},
                {"name": "off-b", "webhook": self.WEBHOOK_B, "enabled": False},
                {"name": "on-by-default", "webhook": self.WEBHOOK_C},
                {"name": "empty", "webhook": "", "enabled": True},
            ]
        )

        _, _, enabled = dingtalk.load_config(self.config_path)

        self.assertEqual(["on-a", "on-by-default"], [item["name"] for item in enabled])

    def test_list_webhooks_includes_disabled_groups_without_credentials(self):
        self.write_config(
            {
                "webhooks": [
                    {"name": "on-a", "webhook": self.WEBHOOK_A, "enabled": True},
                    {"name": "off-b", "webhook": self.WEBHOOK_B, "enabled": False},
                ]
            }
        )

        webhooks = dingtalk.list_webhooks(self.config_path)

        self.assertEqual(["on-a", "off-b"], [item["name"] for item in webhooks])
        self.assertEqual([True, False], [item["enabled"] for item in webhooks])
        self.assertEqual(8, len(webhooks[0]["short_id"]))
        self.assertNotIn("test-a", webhooks[0]["short_id"].lower())

        with self.assertRaises(dingtalk.DingTalkError):
            dingtalk.list_webhooks(Path(self._temp_dir.name) / "missing.json")

    def test_missing_group_name_uses_safe_label_and_stable_short_id(self):
        self.write_standard_config(
            [{"name": "", "webhook": self.WEBHOOK_A, "enabled": True}]
        )

        first = dingtalk.list_webhooks(self.config_path)[0]
        second = dingtalk.list_webhooks(self.config_path)[0]

        self.assertEqual("未命名群", first["name"])
        self.assertFalse(first["name_configured"])
        self.assertEqual(first["short_id"], second["short_id"])
        self.assertNotIn("test-a", first["name"])

    def test_list_webhooks_keeps_optional_bound_conversation_id(self):
        self.write_standard_config(
            [{
                "name": "bound-group",
                "webhook": self.WEBHOOK_A,
                "enabled": True,
                "open_conversation_id": "cid-test-bound",
            }]
        )

        group = dingtalk.list_webhooks(self.config_path)[0]

        self.assertEqual("cid-test-bound", group["open_conversation_id"])

    def test_load_config_rejects_missing_invalid_and_incomplete_files(self):
        missing_path = Path(self._temp_dir.name) / "missing.json"
        with self.assertRaises(dingtalk.DingTalkError):
            dingtalk.load_config(missing_path)

        self.config_path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(dingtalk.DingTalkError):
            dingtalk.load_config(self.config_path)

        self.write_config(
            {"app_key": "key", "app_secret": "secret", "webhooks": []}
        )
        with self.assertRaises(dingtalk.DingTalkError):
            dingtalk.load_config(self.config_path)

        self.write_config(
            {"app_key": "key", "app_secret": "secret", "webhook": "  "}
        )
        with self.assertRaises(dingtalk.DingTalkError):
            dingtalk.load_config(self.config_path)

        self.write_config(
            {
                "app_key": "",
                "app_secret": "secret",
                "webhook": self.WEBHOOK_A,
            }
        )
        with self.assertRaises(dingtalk.DingTalkError):
            dingtalk.load_config(self.config_path)

    def test_config_rejects_invalid_webhook_and_all_groups_disabled(self):
        self.write_standard_config(
            [{"name": "bad", "webhook": "https://example.test/hook", "enabled": True}]
        )
        with self.assertRaises(dingtalk.DingTalkError):
            dingtalk.load_config(self.config_path)

        self.write_standard_config(
            [{"name": "off", "webhook": self.WEBHOOK_A, "enabled": False}]
        )
        with self.assertRaises(dingtalk.DingTalkError):
            dingtalk.load_config(self.config_path)


class TokenTests(DingTalkTestCase):
    def test_access_token_can_support_bound_but_disabled_group(self):
        self.write_standard_config(
            [{
                "name": "paused",
                "webhook": self.WEBHOOK_A,
                "enabled": False,
                "open_conversation_id": "cid-paused",
            }]
        )
        self.urlopen.side_effect = [
            _FakeResponse({"errcode": 0, "access_token": "token", "expires_in": 7200})
        ]

        self.assertEqual("token", dingtalk.get_access_token(self.config_path))

        self.assertEqual(1, self.urlopen.call_count)

    def test_access_token_is_cached_then_refreshed_inside_safety_window(self):
        self.write_standard_config()
        self.urlopen.side_effect = [
            _FakeResponse(
                {"errcode": 0, "access_token": "token-1", "expires_in": 120}
            ),
            _FakeResponse(
                {"errcode": 0, "access_token": "token-2", "expires_in": 120}
            ),
        ]

        with mock.patch.object(dingtalk.time, "time", side_effect=[1000, 1050, 1061]):
            self.assertEqual(
                "token-1", dingtalk.get_access_token(self.config_path, timeout=3)
            )
            self.assertEqual(
                "token-1", dingtalk.get_access_token(self.config_path, timeout=3)
            )
            self.assertEqual(
                "token-2", dingtalk.get_access_token(self.config_path, timeout=3)
            )

        self.assertEqual(2, self.urlopen.call_count)
        first_request = self.urlopen.call_args_list[0].args[0]
        self.assertEqual("GET", first_request.get_method())
        self.assertIn("appkey=test-app-key", first_request.full_url)
        self.assertIn("appsecret=test-app-secret", first_request.full_url)
        self.assertEqual(3, self.urlopen.call_args_list[0].kwargs["timeout"])

    def test_access_token_wraps_http_failure(self):
        self.write_standard_config()
        self.urlopen.side_effect = HTTPError(
            "https://oapi.dingtalk.com/gettoken", 503, "unavailable", {}, None
        )

        with self.assertRaises(dingtalk.DingTalkError):
            dingtalk.get_access_token(self.config_path)

    def test_access_token_rejects_dingtalk_api_error_without_caching(self):
        self.write_standard_config()
        self.urlopen.side_effect = [
            _FakeResponse({"errcode": 40014, "errmsg": "invalid token"}),
            _FakeResponse(
                {"errcode": 0, "access_token": "recovered", "expires_in": 7200}
            ),
        ]

        with self.assertRaises(dingtalk.DingTalkError):
            dingtalk.get_access_token(self.config_path)
        self.assertEqual("recovered", dingtalk.get_access_token(self.config_path))
        self.assertEqual(2, self.urlopen.call_count)


class GroupIdentityTests(DingTalkTestCase):
    OPEN_CONVERSATION_ID = "cid-test-bound"

    def bound_group(self):
        return {
            "name": "local-name",
            "webhook": self.WEBHOOK_A,
            "short_id": dingtalk.webhook_short_id(self.WEBHOOK_A),
            "open_conversation_id": self.OPEN_CONVERSATION_ID,
        }

    def test_resolve_group_identity_returns_verified_official_title(self):
        self.urlopen.side_effect = [_FakeResponse({
            "errcode": 0,
            "success": True,
            "result": {"title": "钉钉官方群"},
        })]

        with mock.patch.object(
            dingtalk, "get_access_token", return_value="identity-token"
        ) as get_token:
            result = dingtalk.resolve_group_identity(
                self.bound_group(), self.config_path, timeout=3
            )

        self.assertEqual("verified", result["status"])
        self.assertEqual("dingtalk", result["source"])
        self.assertEqual("钉钉官方群", result["official_name"])
        self.assertNotIn(self.OPEN_CONVERSATION_ID, json.dumps(result, ensure_ascii=False))
        get_token.assert_called_once_with(self.config_path, 3)
        request = self.urlopen.call_args.args[0]
        self.assertEqual("POST", request.get_method())
        self.assertIn("/topapi/im/chat/scenegroup/get?access_token=identity-token", request.full_url)
        self.assertEqual(
            {"open_conversation_id": self.OPEN_CONVERSATION_ID},
            json.loads(request.data.decode("utf-8")),
        )

    def test_resolve_group_identity_uses_cache_unless_explicitly_refreshed(self):
        self.urlopen.side_effect = [
            _FakeResponse({"errcode": 0, "result": {"title": "first"}}),
            _FakeResponse({"errcode": 0, "result": {"title": "refreshed"}}),
        ]
        with mock.patch.object(dingtalk, "get_access_token", return_value="token"):
            first = dingtalk.resolve_group_identity(self.bound_group(), self.config_path)
            cached = dingtalk.resolve_group_identity(self.bound_group(), self.config_path)
            refreshed = dingtalk.resolve_group_identity(
                self.bound_group(), self.config_path, refresh=True
            )

        self.assertEqual("first", first["official_name"])
        self.assertEqual("first", cached["official_name"])
        self.assertEqual("refreshed", refreshed["official_name"])
        self.assertEqual(2, self.urlopen.call_count)

    def test_resolve_group_identity_handles_missing_binding_without_network(self):
        result = dingtalk.resolve_group_identity(
            {"name": "local", "open_conversation_id": ""}, self.config_path
        )

        self.assertEqual("unbound", result["status"])
        self.assertEqual("尚未绑定钉钉会话 ID", result["reason"])
        self.urlopen.assert_not_called()

    def test_resolve_group_identity_classifies_failures_without_leaking_id(self):
        cases = [
            (socket.timeout(), "timeout", "群信息查询超时"),
            (URLError("offline"), "network_error", "网络不可用，暂时无法验证"),
            (
                HTTPError("https://api.example", 403, "forbidden", {}, None),
                "permission_denied",
                "群信息查询权限不足",
            ),
            (
                _FakeResponse({"errcode": 400020, "errmsg": "denied"}),
                "permission_denied",
                "群信息查询权限不足",
            ),
            (
                _FakeResponse({"errcode": 400001, "errmsg": "failure"}),
                "api_error",
                "钉钉群信息接口拒绝了查询",
            ),
            (
                _FakeResponse({"errcode": 0, "result": {"title": ""}}),
                "empty_title",
                "钉钉未返回可用的群名称",
            ),
            (
                _FakeResponse(["unexpected"]),
                "api_error",
                "钉钉群信息接口返回异常数据",
            ),
        ]
        with mock.patch.object(dingtalk, "get_access_token", return_value="token"):
            for response, status, reason in cases:
                with self.subTest(status=status):
                    dingtalk.clear_group_identity_cache()
                    self.urlopen.reset_mock()
                    self.urlopen.side_effect = [response]
                    result = dingtalk.resolve_group_identity(
                        self.bound_group(), self.config_path
                    )
                    self.assertEqual(status, result["status"])
                    self.assertEqual(reason, result["reason"])
                    self.assertNotIn(
                        self.OPEN_CONVERSATION_ID,
                        json.dumps(result, ensure_ascii=False),
                    )
class MessageSendingTests(DingTalkTestCase):
    def test_send_text_posts_expected_utf8_payload_to_enabled_groups_only(self):
        self.write_standard_config(
            [
                {"name": "group-a", "webhook": self.WEBHOOK_A, "enabled": True},
                {"name": "group-b", "webhook": self.WEBHOOK_B, "enabled": False},
                {"name": "group-c", "webhook": self.WEBHOOK_C, "enabled": True},
            ]
        )
        self.urlopen.side_effect = [
            _FakeResponse({"errcode": 0}),
            _FakeResponse({"errcode": 0}),
        ]

        result = dingtalk.send_text("安全预警", self.config_path, timeout=4)

        self.assertEqual(["group-a", "group-c"], [name for name, _ in result])
        self.assertEqual(2, self.urlopen.call_count)
        requests = [call.args[0] for call in self.urlopen.call_args_list]
        self.assertEqual([self.WEBHOOK_A, self.WEBHOOK_C], [r.full_url for r in requests])
        for request in requests:
            self.assertEqual("POST", request.get_method())
            self.assertEqual(
                {"msgtype": "text", "text": {"content": "安全预警"}},
                json.loads(request.data.decode("utf-8")),
            )
        self.assertEqual([4, 4], [c.kwargs["timeout"] for c in self.urlopen.call_args_list])

    def test_send_markdown_builds_expected_payload(self):
        self.write_standard_config()
        self.urlopen.side_effect = [_FakeResponse({"errcode": 0})]

        dingtalk.send_markdown(
            "alert-title", "**alert-body**", self.config_path, timeout=6
        )

        request = self.urlopen.call_args.args[0]
        self.assertEqual(
            {
                "msgtype": "markdown",
                "markdown": {"title": "alert-title", "text": "**alert-body**"},
            },
            json.loads(request.data.decode("utf-8")),
        )

    def test_one_group_failure_does_not_block_other_groups(self):
        self.write_standard_config(
            [
                {"name": "failed", "webhook": self.WEBHOOK_A, "enabled": True},
                {"name": "working", "webhook": self.WEBHOOK_B, "enabled": True},
            ]
        )
        self.urlopen.side_effect = [
            _FakeResponse({"errcode": 310000, "errmsg": "keyword mismatch"}),
            _FakeResponse({"errcode": 0}),
        ]

        with self.assertLogs("dingtalk_send", level="ERROR"):
            result = dingtalk.send_text("alert", self.config_path)

        self.assertEqual(["working"], [name for name, _ in result])
        self.assertEqual(2, self.urlopen.call_count)

    def test_all_group_failures_raise_after_every_group_is_attempted(self):
        self.write_standard_config(
            [
                {"name": "http-fail", "webhook": self.WEBHOOK_A, "enabled": True},
                {"name": "api-fail", "webhook": self.WEBHOOK_B, "enabled": True},
            ]
        )
        self.urlopen.side_effect = [
            HTTPError(self.WEBHOOK_A, 500, "server error", {}, None),
            _FakeResponse({"errcode": 310000, "errmsg": "rejected"}),
        ]

        with self.assertLogs("dingtalk_send", level="ERROR"):
            with self.assertRaises(dingtalk.DingTalkError):
                dingtalk.send_text("alert", self.config_path)

        self.assertEqual(2, self.urlopen.call_count)


class ImageSendingTests(DingTalkTestCase):
    def test_send_image_uploads_once_then_sends_markdown_to_each_group(self):
        self.write_standard_config(
            [
                {"name": "group-a", "webhook": self.WEBHOOK_A, "enabled": True},
                {"name": "group-b", "webhook": self.WEBHOOK_B, "enabled": True},
            ]
        )
        self.urlopen.side_effect = [
            _FakeResponse({"errcode": 0, "media_id": "media-123"}),
            _FakeResponse({"errcode": 0}),
            _FakeResponse({"errcode": 0}),
        ]

        with mock.patch.object(
            dingtalk, "get_access_token", return_value="upload-token"
        ) as get_token:
            result = dingtalk.send_image(
                self.image_path(), self.config_path, timeout=8
            )

        get_token.assert_called_once_with(self.config_path, 8)
        self.assertEqual(["group-a", "group-b"], [name for name, _ in result])
        self.assertEqual(3, self.urlopen.call_count)

        upload_request = self.urlopen.call_args_list[0].args[0]
        self.assertIn("/media/upload?access_token=upload-token&type=image", upload_request.full_url)
        self.assertEqual("POST", upload_request.get_method())
        self.assertIn(b"fake-jpeg-bytes", upload_request.data)
        self.assertIn("multipart/form-data; boundary=", upload_request.get_header("Content-type"))

        message_requests = [call.args[0] for call in self.urlopen.call_args_list[1:]]
        self.assertEqual(
            [self.WEBHOOK_A, self.WEBHOOK_B],
            [request.full_url for request in message_requests],
        )
        for request in message_requests:
            payload = json.loads(request.data.decode("utf-8"))
            self.assertEqual("markdown", payload["msgtype"])
            self.assertIn("media-123", payload["markdown"]["text"])

    def test_send_image_wraps_upload_http_failure(self):
        self.write_standard_config()
        self.urlopen.side_effect = HTTPError(
            "https://oapi.dingtalk.com/media/upload", 502, "bad gateway", {}, None
        )

        with mock.patch.object(dingtalk, "get_access_token", return_value="token"):
            with self.assertLogs("dingtalk_send", level="ERROR"):
                with self.assertRaises(dingtalk.DingTalkError):
                    dingtalk.send_image(self.image_path(), self.config_path)

        self.assertEqual(1, self.urlopen.call_count)

    def test_send_image_rejects_upload_api_error_and_missing_media_id(self):
        self.write_standard_config()
        for upload_result in (
            {"errcode": 40014, "errmsg": "invalid token"},
            {"errcode": 0},
        ):
            with self.subTest(upload_result=upload_result):
                self.urlopen.reset_mock(side_effect=True, return_value=True)
                self.urlopen.side_effect = [_FakeResponse(upload_result)]
                with mock.patch.object(
                    dingtalk, "get_access_token", return_value="token"
                ):
                    with self.assertRaises(dingtalk.DingTalkError):
                        dingtalk.send_image(self.image_path(), self.config_path)
                self.assertEqual(1, self.urlopen.call_count)

    def test_send_image_stops_before_upload_when_token_lookup_fails(self):
        self.write_standard_config()

        with mock.patch.object(
            dingtalk,
            "get_access_token",
            side_effect=dingtalk.DingTalkError("token unavailable"),
        ):
            with self.assertRaises(dingtalk.DingTalkError):
                dingtalk.send_image(self.image_path(), self.config_path)

        self.urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
