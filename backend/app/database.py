import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from app.config import settings
from app.trace import TraceLogger


def get_db_path() -> Path:
    db_path = settings.data_dir / "regshift.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(str(get_db_path()))
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS change_sessions (
            id TEXT PRIMARY KEY,
            business_text TEXT NOT NULL,
            domain TEXT,
            contract_yaml TEXT,
            contract_json TEXT,
            contract_approved INTEGER DEFAULT 0,
            graph_json TEXT,
            impact_json TEXT,
            risks_json TEXT,
            tests_json TEXT,
            simulation_json TEXT,
            pack_id TEXT,
            trace_json TEXT,
            governance_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS file_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            extension TEXT,
            module TEXT,
            content_snippet TEXT,
            keywords TEXT,
            python_classes TEXT,
            python_functions TEXT,
            imports TEXT,
            business_entities TEXT,
            scan_timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS index_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            source TEXT NOT NULL,
            file_count INTEGER NOT NULL,
            last_scan TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tenant_policies (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            title TEXT NOT NULL,
            domain TEXT,
            source_text TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'active',
            rules_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tenant_policies_tenant_domain
            ON tenant_policies(tenant_id, domain, status);
        """
    )
    connection.commit()
    _migrate_schema(connection)
    connection.close()


def _migrate_schema(connection: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(change_sessions)").fetchall()
    }
    if "governance_json" not in columns:
        connection.execute("ALTER TABLE change_sessions ADD COLUMN governance_json TEXT")
        connection.commit()


class SessionStore:
    def __init__(self) -> None:
        self._traces: dict[str, TraceLogger] = {}

    def get_trace(self, session_id: str) -> TraceLogger:
        if session_id not in self._traces:
            self._traces[session_id] = TraceLogger()
        return self._traces[session_id]

    def create_session(self, business_text: str, domain: str | None = None) -> str:
        session_id = str(uuid.uuid4())
        now = _now_iso()
        connection = get_connection()
        connection.execute(
            """
            INSERT INTO change_sessions (id, business_text, domain, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, business_text, domain, now, now),
        )
        connection.commit()
        connection.close()
        self._traces[session_id] = TraceLogger()
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        connection = get_connection()
        row = connection.execute(
            "SELECT * FROM change_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        connection.close()
        if row is None:
            return None
        return _row_to_dict(row)

    def get_latest_session(self) -> dict[str, Any] | None:
        connection = get_connection()
        row = connection.execute(
            "SELECT * FROM change_sessions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        connection.close()
        if row is None:
            return None
        return _row_to_dict(row)

    def update_session(self, session_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = _now_iso()
        columns = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [session_id]
        connection = get_connection()
        connection.execute(
            f"UPDATE change_sessions SET {columns} WHERE id = ?",
            values,
        )
        connection.commit()
        connection.close()

    def save_trace(self, session_id: str) -> None:
        trace = self.get_trace(session_id)
        self.update_session(
            session_id,
            trace_json=json.dumps([event.model_dump() for event in trace.get_events()]),
        )

    def load_trace(self, session_id: str) -> list[dict[str, Any]]:
        session = self.get_session(session_id)
        if session and session.get("trace_json"):
            return json.loads(session["trace_json"])
        return [event.model_dump() for event in self.get_trace(session_id).get_events()]


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


session_store = SessionStore()
