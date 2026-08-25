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
                    inspector TEXT,
                    model_version TEXT
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
                    inspector TEXT,
                    model_version TEXT
                )
            """)
            for table_name in ("detection_records", "realtime_violations"):
                columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})")}
                if "model_version" not in columns:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN model_version TEXT")
            # 处置状态与检测事实分表保存：旧版本可直接忽略此表，回滚不影响检测记录。
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS incident_workflows (
                    source_type TEXT NOT NULL,
                    source_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    assignee TEXT NOT NULL DEFAULT '',
                    due_at TEXT,
                    resolution_note TEXT NOT NULL DEFAULT '',
                    closed_at TEXT,
                    closed_by TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source_type, source_id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_incident_workflows_status
                ON incident_workflows(status, due_at)
            """)
            # 仅保存当前工作区的本机输入默认值；不改写任何检测事实或处置记录。
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS last_check_context (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    project_name TEXT NOT NULL DEFAULT '',
                    inspector TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def get_last_check_context(self):
        """返回本机最近使用的项目和检查人，首次使用时均为空。"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT project_name, inspector FROM last_check_context WHERE id = 1"
            ).fetchone()
        if not row:
            return {"project_name": "", "inspector": ""}
        return {"project_name": row[0] or "", "inspector": row[1] or ""}

    def save_last_check_context(self, project_name="", inspector=""):
        """保存本机最近使用的检查上下文，供下次启动恢复。"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("""
                INSERT INTO last_check_context (id, project_name, inspector, updated_at)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_name = excluded.project_name,
                    inspector = excluded.inspector,
                    updated_at = excluded.updated_at
            """, (
                str(project_name or "").strip(),
                str(inspector or "").strip(),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            conn.commit()

    def save_record(self, detection_result, image_name="", project_name="", inspector="", model_version=""):
        """保存一条检测记录"""
        summary = detection_result["summary"]
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO detection_records
                (timestamp, image_name, result_image_path, total_detections,
                 helmet_count, no_helmet_count, vest_count, no_vest_count,
                 red_alerts, yellow_alerts, has_violation,
                 detections_json, alerts_json, project_name, inspector, model_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                model_version,
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
                SELECT r.*,
                       CASE
                           WHEN r.has_violation = 0 THEN 'not_applicable'
                           ELSE COALESCE(w.status, 'pending')
                       END AS incident_status,
                       COALESCE(w.assignee, '') AS assignee,
                       w.due_at,
                       COALESCE(w.resolution_note, '') AS resolution_note,
                       w.closed_at,
                       COALESCE(w.closed_by, '') AS closed_by,
                       w.updated_at
                FROM detection_records AS r
                LEFT JOIN incident_workflows AS w
                  ON w.source_type = 'image' AND w.source_id = r.id
                ORDER BY r.timestamp DESC, r.id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_image_incident_queue(self, history_limit=200):
        """返回全部开放图片事项，并附带最近的已结项/合规历史。"""
        if not isinstance(history_limit, int) or isinstance(history_limit, bool) or history_limit < 0:
            raise ValueError("历史记录数量无效")
        with closing(sqlite3.connect(self.db_path, timeout=5)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                WITH joined AS (
                    SELECT r.*,
                           CASE
                               WHEN r.has_violation = 0 THEN 'not_applicable'
                               ELSE COALESCE(w.status, 'pending')
                           END AS incident_status,
                           COALESCE(w.assignee, '') AS assignee,
                           w.due_at,
                           COALESCE(w.resolution_note, '') AS resolution_note,
                           w.closed_at,
                           COALESCE(w.closed_by, '') AS closed_by,
                           w.updated_at
                    FROM detection_records AS r
                    LEFT JOIN incident_workflows AS w
                      ON w.source_type = 'image' AND w.source_id = r.id
                ), history AS (
                    SELECT * FROM joined
                    WHERE incident_status NOT IN ('pending', 'in_progress')
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                )
                SELECT * FROM (
                    SELECT * FROM joined
                    WHERE incident_status IN ('pending', 'in_progress')
                    UNION ALL
                    SELECT * FROM history
                ) AS queue
                ORDER BY
                    CASE WHEN incident_status IN ('pending', 'in_progress') THEN 0 ELSE 1 END,
                    timestamp DESC,
                    id DESC
            """, (history_limit,))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def update_incident_workflow(self, source_type, source_id, *, status,
                                 assignee="", due_at=None, resolution_note="", operator=""):
        """新增或更新一条处置详情，并保留原始检测记录不变。"""
        source_tables = {
            "image": ("detection_records", True),
            "realtime": ("realtime_violations", False),
        }
        valid_statuses = {"pending", "in_progress", "closed", "false_positive"}
        if source_type not in source_tables:
            raise ValueError("不支持的记录来源")
        if status not in valid_statuses:
            raise ValueError("不支持的处置状态")
        if not isinstance(source_id, int) or isinstance(source_id, bool) or source_id <= 0:
            raise ValueError("记录 ID 无效")

        assignee = (assignee or "").strip()
        due_at = (due_at or "").strip() or None
        resolution_note = (resolution_note or "").strip()
        operator = (operator or "").strip()
        is_terminal = status in {"closed", "false_positive"}
        if is_terminal and (not operator or not resolution_note):
            raise ValueError("关闭或误报必须填写复核人和处置说明")

        table_name, must_be_violation = source_tables[source_type]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with closing(sqlite3.connect(self.db_path, timeout=5)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT id, has_violation FROM {table_name} WHERE id = ?"
                if must_be_violation else f"SELECT id FROM {table_name} WHERE id = ?",
                (source_id,),
            )
            source_row = cursor.fetchone()
            if source_row is None:
                raise ValueError("检测记录不存在")
            if must_be_violation and not source_row["has_violation"]:
                raise ValueError("合规记录无需处置")

            closed_at = now if is_terminal else None
            closed_by = operator if is_terminal else ""
            cursor.execute("""
                INSERT INTO incident_workflows
                    (source_type, source_id, status, assignee, due_at,
                     resolution_note, closed_at, closed_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_type, source_id) DO UPDATE SET
                    status = excluded.status,
                    assignee = excluded.assignee,
                    due_at = excluded.due_at,
                    resolution_note = excluded.resolution_note,
                    closed_at = CASE
                        WHEN incident_workflows.status = excluded.status
                         AND excluded.status IN ('closed', 'false_positive')
                        THEN incident_workflows.closed_at
                        ELSE excluded.closed_at
                    END,
                    closed_by = CASE
                        WHEN incident_workflows.status = excluded.status
                         AND excluded.status IN ('closed', 'false_positive')
                        THEN incident_workflows.closed_by
                        ELSE excluded.closed_by
                    END,
                    updated_at = excluded.updated_at
            """, (
                source_type, source_id, status, assignee, due_at,
                resolution_note, closed_at, closed_by, now,
            ))
            conn.commit()
            cursor.execute("""
                SELECT * FROM incident_workflows
                WHERE source_type = ? AND source_id = ?
            """, (source_type, source_id))
            workflow = dict(cursor.fetchone())
        return workflow

    def get_incident_statistics(self):
        """统计图片违规与实时违规的当前处置状态。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with closing(sqlite3.connect(self.db_path, timeout=5)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                WITH incidents AS (
                    SELECT COALESCE(w.status, 'pending') AS status, w.due_at
                    FROM detection_records AS r
                    LEFT JOIN incident_workflows AS w
                      ON w.source_type = 'image' AND w.source_id = r.id
                    WHERE r.has_violation = 1
                    UNION ALL
                    SELECT COALESCE(w.status, 'pending') AS status, w.due_at
                    FROM realtime_violations AS r
                    LEFT JOIN incident_workflows AS w
                      ON w.source_type = 'realtime' AND w.source_id = r.id
                )
                SELECT status, COUNT(*)
                FROM incidents
                GROUP BY status
            """)
            counts = dict(cursor.fetchall())
            cursor.execute("""
                WITH incidents AS (
                    SELECT COALESCE(w.status, 'pending') AS status, w.due_at
                    FROM detection_records AS r
                    LEFT JOIN incident_workflows AS w
                      ON w.source_type = 'image' AND w.source_id = r.id
                    WHERE r.has_violation = 1
                    UNION ALL
                    SELECT COALESCE(w.status, 'pending') AS status, w.due_at
                    FROM realtime_violations AS r
                    LEFT JOIN incident_workflows AS w
                      ON w.source_type = 'realtime' AND w.source_id = r.id
                )
                SELECT COUNT(*) FROM incidents
                WHERE status IN ('pending', 'in_progress')
                  AND due_at IS NOT NULL AND due_at < ?
            """, (now,))
            overdue = cursor.fetchone()[0]
        return {
            "total": sum(counts.values()),
            "pending": counts.get("pending", 0),
            "in_progress": counts.get("in_progress", 0),
            "closed": counts.get("closed", 0),
            "false_positive": counts.get("false_positive", 0),
            "overdue": overdue,
        }

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
                                snapshot_path="", project_name="", inspector="", model_version=""):
        """保存一条实时违规事件(经节流后入库,非每帧写)

        参数:
            violation_type: 单类或逗号分隔的同帧违规组合，例如 no-helmet,no-vest
            violation_count: 本帧该事件内的违规目标总数
            level: red / yellow (由 app 回调从 detector.ALERT_LEVELS 取后传入)
            snapshot_path: 违规截图路径(任务#5 抓拍留痕用,暂留空)
        """
        with closing(sqlite3.connect(self.db_path, timeout=5)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO realtime_violations
                (timestamp, violation_type, violation_count, level, snapshot_path, project_name, inspector, model_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                violation_type, violation_count, level, snapshot_path, project_name, inspector, model_version,
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
                SELECT r.*,
                       COALESCE(w.status, 'pending') AS incident_status,
                       COALESCE(w.assignee, '') AS assignee,
                       w.due_at,
                       COALESCE(w.resolution_note, '') AS resolution_note,
                       w.closed_at,
                       COALESCE(w.closed_by, '') AS closed_by,
                       w.updated_at
                FROM realtime_violations AS r
                LEFT JOIN incident_workflows AS w
                  ON w.source_type = 'realtime' AND w.source_id = r.id
                ORDER BY r.timestamp DESC, r.id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_realtime_incident_queue(self, history_limit=200):
        """返回全部开放实时事项，并附带最近的已结项历史。"""
        if not isinstance(history_limit, int) or isinstance(history_limit, bool) or history_limit < 0:
            raise ValueError("历史记录数量无效")
        with closing(sqlite3.connect(self.db_path, timeout=5)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                WITH joined AS (
                    SELECT r.*,
                           COALESCE(w.status, 'pending') AS incident_status,
                           COALESCE(w.assignee, '') AS assignee,
                           w.due_at,
                           COALESCE(w.resolution_note, '') AS resolution_note,
                           w.closed_at,
                           COALESCE(w.closed_by, '') AS closed_by,
                           w.updated_at
                    FROM realtime_violations AS r
                    LEFT JOIN incident_workflows AS w
                      ON w.source_type = 'realtime' AND w.source_id = r.id
                ), history AS (
                    SELECT * FROM joined
                    WHERE incident_status NOT IN ('pending', 'in_progress')
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                )
                SELECT * FROM (
                    SELECT * FROM joined
                    WHERE incident_status IN ('pending', 'in_progress')
                    UNION ALL
                    SELECT * FROM history
                ) AS queue
                ORDER BY
                    CASE WHEN incident_status IN ('pending', 'in_progress') THEN 0 ELSE 1 END,
                    timestamp DESC,
                    id DESC
            """, (history_limit,))
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
