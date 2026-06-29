import json
import uuid
from typing import Any

from app.database import get_connection, _now_iso
from app.services.policy_constants import DEFAULT_TENANT_ID, POLICY_STATUS_ACTIVE, POLICY_STATUS_ARCHIVED


def ingest_policy(
    title: str,
    source_text: str,
    rules: dict[str, Any],
    domain: str | None = None,
    tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, Any]:
    policy_id = str(uuid.uuid4())
    now = _now_iso()
    connection = get_connection()
    if domain:
        connection.execute(
            """
            UPDATE tenant_policies
            SET status = ?, updated_at = ?
            WHERE tenant_id = ? AND domain = ? AND status = ?
            """,
            (POLICY_STATUS_ARCHIVED, now, tenant_id, domain, POLICY_STATUS_ACTIVE),
        )
    connection.execute(
        """
        INSERT INTO tenant_policies (
            id, tenant_id, title, domain, source_text, version, status, rules_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            policy_id,
            tenant_id,
            title,
            domain,
            source_text,
            _next_version(connection, tenant_id, domain),
            POLICY_STATUS_ACTIVE,
            json.dumps(rules),
            now,
            now,
        ),
    )
    connection.commit()
    connection.close()
    return get_policy(policy_id) or {}


def get_policy(policy_id: str) -> dict[str, Any] | None:
    connection = get_connection()
    row = connection.execute(
        "SELECT * FROM tenant_policies WHERE id = ?",
        (policy_id,),
    ).fetchone()
    connection.close()
    if row is None:
        return None
    return _row_to_policy(row)


def get_active_policy(
    domain: str,
    tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, Any] | None:
    connection = get_connection()
    row = connection.execute(
        """
        SELECT * FROM tenant_policies
        WHERE tenant_id = ? AND domain = ? AND status = ?
        ORDER BY version DESC, created_at DESC
        LIMIT 1
        """,
        (tenant_id, domain, POLICY_STATUS_ACTIVE),
    ).fetchone()
    connection.close()
    if row is None:
        return None
    return _row_to_policy(row)


def list_policies(tenant_id: str = DEFAULT_TENANT_ID) -> list[dict[str, Any]]:
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT * FROM tenant_policies
        WHERE tenant_id = ?
        ORDER BY created_at DESC
        """,
        (tenant_id,),
    ).fetchall()
    connection.close()
    return [_row_to_policy(row) for row in rows]


def has_active_policy(domain: str, tenant_id: str = DEFAULT_TENANT_ID) -> bool:
    return get_active_policy(domain, tenant_id) is not None


def _next_version(connection: Any, tenant_id: str, domain: str | None) -> int:
    if not domain:
        return 1
    row = connection.execute(
        """
        SELECT MAX(version) AS max_version FROM tenant_policies
        WHERE tenant_id = ? AND domain = ?
        """,
        (tenant_id, domain),
    ).fetchone()
    current = row["max_version"] if row and row["max_version"] else 0
    return int(current) + 1


def _row_to_policy(row: Any) -> dict[str, Any]:
    rules = json.loads(row["rules_json"])
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "title": row["title"],
        "domain": row["domain"],
        "source_text": row["source_text"],
        "version": row["version"],
        "status": row["status"],
        "rules": rules,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
