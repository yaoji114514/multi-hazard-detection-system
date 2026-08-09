import unittest
from datetime import datetime
from unittest.mock import patch

from src.alert import AlertEngine


class AlertEngineTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = AlertEngine()

    @patch("src.alert.datetime")
    def test_generate_alerts_keeps_only_actionable_levels(self, datetime_mock):
        datetime_mock.now.return_value = datetime(2026, 8, 4, 12, 34, 56)
        detections = [
            {
                "alert_level": "red",
                "label": "no-helmet",
                "description": "未佩戴安全帽",
                "confidence": 0.97,
            },
            {
                "alert_level": "blue",
                "label": "helmet",
                "description": "已佩戴安全帽",
                "confidence": 0.95,
            },
            {
                "alert_level": "yellow",
                "label": "no-vest",
                "description": "未穿反光衣",
                "confidence": 0.88,
            },
            {
                "alert_level": "unexpected",
                "label": "other",
                "description": "未知级别",
                "confidence": 0.50,
            },
            {
                "label": "person",
                "description": "默认蓝色记录",
                "confidence": 0.99,
            },
        ]

        alerts = self.engine.generate_alerts(detections)

        self.assertEqual([alert["level"] for alert in alerts], ["red", "yellow"])
        self.assertEqual(
            [alert["hazard_type"] for alert in alerts], ["no-helmet", "no-vest"]
        )
        self.assertEqual(
            [alert["description"] for alert in alerts],
            ["未佩戴安全帽", "未穿反光衣"],
        )
        self.assertEqual([alert["confidence"] for alert in alerts], [0.97, 0.88])
        for alert in alerts:
            level_info = self.engine.LEVELS[alert["level"]]
            self.assertEqual(alert["timestamp"], "2026-08-04 12:34:56")
            self.assertEqual(alert["level_name"], level_info["name"])
            self.assertEqual(alert["icon"], level_info["icon"])
            self.assertEqual(alert["color"], level_info["color"])
            self.assertEqual(alert["action"], level_info["action"])

    def test_generate_alerts_returns_empty_for_normal_or_empty_detections(self):
        normal_detection = {
            "alert_level": "blue",
            "label": "helmet",
            "description": "normal",
            "confidence": 0.9,
        }

        self.assertEqual(self.engine.generate_alerts([]), [])
        self.assertEqual(self.engine.generate_alerts([normal_detection]), [])

    def test_get_overall_level_returns_none_without_alerts(self):
        self.assertIsNone(self.engine.get_overall_level([]))

    def test_get_overall_level_returns_original_highest_priority_alert(self):
        yellow = {"level": "yellow", "id": "yellow"}
        blue = {"level": "blue", "id": "blue"}
        red = {"level": "red", "id": "red"}

        highest = self.engine.get_overall_level([yellow, blue, red])

        self.assertIs(highest, red)

    def test_get_overall_level_treats_unknown_level_as_lower_priority(self):
        unknown = {"level": "custom", "id": "custom"}
        blue = {"level": "blue", "id": "blue"}

        highest = self.engine.get_overall_level([unknown, blue])

        self.assertIs(highest, blue)


if __name__ == "__main__":
    unittest.main()
