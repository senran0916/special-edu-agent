"""
SQLite数据层
存储康复训练记录及提取的行为标签
"""
import sqlite3
import json
import uuid
import os
from datetime import datetime, timedelta
from typing import List, Optional

from app.models import StoredRecord, BehaviorTag, Direction

def _default_db_path() -> str:
    """默认数据库路径: 优先项目data目录(开发模式), 不可写则用用户主目录(uvx模式)"""
    dev_path = os.path.join(os.path.dirname(__file__), "..", "data", "records.db")
    dev_dir = os.path.dirname(dev_path)
    try:
        os.makedirs(dev_dir, exist_ok=True)
        # 测试可写性
        test_file = os.path.join(dev_dir, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return dev_path
    except (OSError, PermissionError):
        # site-packages不可写, 使用用户主目录
        user_dir = os.path.join(os.path.expanduser("~"), ".special-edu-agent")
        os.makedirs(user_dir, exist_ok=True)
        return os.path.join(user_dir, "records.db")


DB_PATH = os.environ.get("DB_PATH", _default_db_path())


def get_conn() -> sqlite3.Connection:
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            record_id TEXT PRIMARY KEY,
            child_id TEXT NOT NULL,
            therapist_id TEXT DEFAULT 'anonymous',
            session_date TEXT NOT NULL,
            content TEXT NOT NULL,
            session_type TEXT DEFAULT 'individual',
            duration_minutes INTEGER,
            notes TEXT,
            behavior_tags_json TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_records_child_date
        ON records(child_id, session_date)
    """)
    conn.commit()
    conn.close()


def save_record(record: StoredRecord) -> bool:
    """保存一条记录"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO records
        (record_id, child_id, therapist_id, session_date, content,
         session_type, duration_minutes, notes, behavior_tags_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.record_id,
        record.child_id,
        record.therapist_id,
        record.session_date,
        record.content,
        record.session_type,
        record.duration_minutes,
        record.notes,
        json.dumps([t.model_dump(mode="json") for t in record.behavior_tags]),
        record.created_at,
    ))
    conn.commit()
    conn.close()
    return True


def _row_to_record(row: sqlite3.Row) -> StoredRecord:
    """数据库行转模型对象"""
    tags_raw = json.loads(row["behavior_tags_json"]) if row["behavior_tags_json"] else []
    tags = [BehaviorTag(**t) for t in tags_raw]
    return StoredRecord(
        record_id=row["record_id"],
        child_id=row["child_id"],
        therapist_id=row["therapist_id"],
        session_date=row["session_date"],
        content=row["content"],
        session_type=row["session_type"],
        duration_minutes=row["duration_minutes"],
        notes=row["notes"],
        behavior_tags=tags,
        created_at=row["created_at"],
    )


def get_records_by_child(
    child_id: str,
    days: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[StoredRecord]:
    """获取儿童的历史记录, 可按时间窗口过滤"""
    conn = get_conn()
    cursor = conn.cursor()

    query = "SELECT * FROM records WHERE child_id = ?"
    params = [child_id]

    if days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        query += " AND session_date >= ?"
        params.append(cutoff)
    if start_date:
        query += " AND session_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND session_date <= ?"
        params.append(end_date)

    query += " ORDER BY session_date ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_record(r) for r in rows]


def get_record_by_id(record_id: str) -> Optional[StoredRecord]:
    """按ID获取单条记录"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM records WHERE record_id = ?", (record_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_record(row) if row else None


def delete_record(record_id: str) -> bool:
    """删除一条记录"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records WHERE record_id = ?", (record_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def list_children() -> List[dict]:
    """列出所有有记录的儿童(用于demo)"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT child_id,
               COUNT(*) as session_count,
               MIN(session_date) as first_session,
               MAX(session_date) as last_session
        FROM records
        GROUP BY child_id
        ORDER BY last_session DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_records() -> int:
    """统计记录总数(用于启动时判断是否为空库)"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM records")
    n = cursor.fetchone()[0]
    conn.close()
    return n


def generate_record_id() -> str:
    """生成记录ID"""
    return f"rec_{uuid.uuid4().hex[:12]}"


def now_str() -> str:
    """当前时间字符串"""
    return datetime.now().isoformat()