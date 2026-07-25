"""
分级预警模块
根据检测结果生成红/黄/蓝三级预警
"""
from datetime import datetime


class AlertEngine:
    """分级预警引擎"""

    LEVELS = {
        "red": {
            "name": "红色预警",
            "color": "#FF4444",
            "action": "立即停工整改",
            "icon": "🔴",
        },
        "yellow": {
            "name": "黄色预警",
            "color": "#FFAA00",
            "action": "限时整改(4小时内)",
            "icon": "🟡",
        },
        "blue": {
            "name": "蓝色记录",
            "color": "#4488FF",
            "action": "记录归档,纳入日报",
            "icon": "🔵",
        },
    }

    def generate_alerts(self, detections):
        """
        根据检测结果生成预警信息(仅 red/yellow 违规生成预警,blue 正常记录不作为预警)
        """
        alerts = []
        for det in detections:
            level = det.get("alert_level", "blue")
            if level not in ("red", "yellow"):
                continue  # blue 正常记录不入预警,避免"未发现违规"永不显示
            level_info = self.LEVELS.get(level, self.LEVELS["blue"])

            alert = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "level": level,
                "level_name": level_info["name"],
                "icon": level_info["icon"],
                "color": level_info["color"],
                "action": level_info["action"],
                "hazard_type": det["label"],
                "description": det["description"],
                "confidence": det["confidence"],
            }
            alerts.append(alert)

        return alerts

    def get_overall_level(self, alerts):
        """获取整体预警等级(取最高级)"""
        if not alerts:
            return None
        priority = {"red": 3, "yellow": 2, "blue": 1}
        highest = max(alerts, key=lambda a: priority.get(a["level"], 0))
        return highest
