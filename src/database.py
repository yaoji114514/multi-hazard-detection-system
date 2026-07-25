"""
数据存储模块
使用SQLite存储检测记录,支持历史查询和统计
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from contextlib import closing


DB_PATH = Path(__file__).parent.parent / "data" / "db" / "hazard_records.db"


class Database:
    """检测记录数据库"""

    def __init__(self, db_path=None):
        self.db_path = str(db_path or DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detection_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    image_name TEXT,
                    result_image_path TEXT,
                    total_detections INTEGER,
                    helmet_count INTEGER,
                    no_helmet_count INTEGER,
                    vest_count INTEGER,
                    no_vest_count INTEGER,
                    red_alerts INTEGER,
                    yellow_alerts INTEGER,
                    has_violation INTEGER,
                    detections_json TEXT,
                    alerts_json TEXT,
                    project_name TEXT,
                    inspector TEXT
                )
            """)
            # 实时违规事件表(任务#3: 实时检测违规入库)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS realtime_violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    violation_count INTEGER,
                    level TEXT,
                    snapshot_path TEXT,
                    project_name TEXT,
                    inspector TEXT
                )
            """)
            conn.commit()

    def save_record(self, detection_result, image_name="", project_name="", inspector=""):
        """保存一条检测记录"""
        summary = detection_result["summary"]
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO detection_records
                (timestamp, image_name, result_image_path, total_detections,
                 helmet_count, no_helmet_count, vest_count, no_vest_count,
                 red_alerts, yellow_alerts, has_violation,
                 detections_json, alerts_json, project_name, inspector)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                image_name,
                detection_result.get("image", ""),
                summary["total_detections"],
                summary["helmet_count"],
                summary["no_helmet_count"],
                summary["vest_count"],
                summary["no_vest_count"],
                summary["red_alerts"],
                summary["yellow_alerts"],
                1 if summary["has_violation"] else 0,
                json.dumps(detection_result["detections"], ensure_ascii=False),
                json.dumps(detection_result["alerts"], ensure_ascii=False),
                project_name,
                inspector,
            ))
            conn.commit()
            record_id = cursor.lastrowid
        return record_id

    def get_recent_records(self, limit=20):
        """获取最近的检测记录"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM detection_records
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_statistics(self):
        """获取统计信息"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            # 总检测次数
            cursor.execute("SELECT COUNT(*) FROM detection_records")
            total_checks = cursor.fetchone()[0]

            # 违规次数
            cursor.execute("SELECT COUNT(*) FROM detection_records WHERE has_violation = 1")
            violation_count = cursor.fetchone()[0]

            # 各类隐患统计
            cursor.execute("""
                SELECT SUM(no_helmet_count) as no_helmet,
                       SUM(no_vest_count) as no_vest,
                       SUM(helmet_count) as helmet,
                       SUM(vest_count) as vest
                FROM detection_records
            """)
            row = cursor.fetchone()

        stats = {
            "total_checks": total_checks,
            "violation_count": violation_count,
            "compliance_rate": round((1 - violation_count / max(total_checks, 1)) * 100, 1),
            "no_helmet_total": row[0] or 0,
            "no_vest_total": row[1] or 0,
            "helmet_total": row[2] or 0,
            "vest_total": row[3] or 0,
        }
        return stats

    def get_daily_stats(self, days=7):
        """获取最近N天的每日统计"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DATE(timestamp) as date,
                       COUNT(*) as checks,
                       SUM(has_violation) as violations
                FROM detection_records
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                LIMIT ?
            """, (days,))
            rows = cursor.fetchall()
        return [{"date": r[0], "checks": r[1], "violations": r[2] or 0} for r in rows]

    # ===== 实时检测违规入库(任务#3) =====
    def save_realtime_violation(self, violation_type, violation_count, level="yellow",
                                snapshot_path="", project_name="", inspector=""):
        """保存一条实时违规事件(经节流后入库,非每帧写)

        参数:
            violation_type: no-helmet / no-vest / no-mask
            violation_count: 本帧该类违规目标数
            level: red / yellow (由 app 回调从 detector.ALERT_LEVELS 取后传入)
            snapshot_path: 违规截图路径(任务#5 抓拍留痕用,暂留空)
        """
        with closing(sqlite3.connect(self.db_path, timeout=5)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO realtime_violations
                (timestamp, violation_type, violation_count, level, snapshot_path, project_name, inspector)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                violation_type, violation_count, level, snapshot_path, project_name, inspector,
            ))
            conn.commit()
            record_id = cursor.lastrowid
        return record_id

    def get_realtime_violations(self, limit=50):
        """获取最近的实时违规记录(供查看页展示)"""
        with closing(sqlite3.connect(self.db_path, timeout=5)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM realtime_violations
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
