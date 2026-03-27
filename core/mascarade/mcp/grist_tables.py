"""Foundation table definitions for Grist — mascarade operational tables.

Creates standard tables in a Grist document for agent memory,
conversation history, project tracking, clients, and battery fleet.
"""

from __future__ import annotations

import logging
from typing import Any

from mascarade.mcp.grist_mcp import GristMcpClient

logger = logging.getLogger("mascarade.mcp.grist_tables")

# ── Column type shortcuts ─────────────────────────────────────────

def _col(col_id: str, col_type: str, label: str | None = None) -> dict[str, Any]:
    fields: dict[str, Any] = {"type": col_type}
    if label:
        fields["label"] = label
    return {"id": col_id, "fields": fields}


# ── Table schemas ─────────────────────────────────────────────────

FOUNDATION_TABLES: dict[str, list[dict[str, Any]]] = {
    "agent_memory": [
        _col("agent_name", "Text", "Agent Name"),
        _col("key", "Text", "Key"),
        _col("value", "Text", "Value"),
        _col("timestamp", "DateTime", "Timestamp"),
        _col("ttl_seconds", "Int", "TTL (s)"),
    ],
    "conversation_history": [
        _col("session_id", "Text", "Session ID"),
        _col("device_id", "Text", "Device ID"),
        _col("role", "Text", "Role"),
        _col("content", "Text", "Content"),
        _col("timestamp", "DateTime", "Timestamp"),
    ],
    "project_tasks": [
        _col("project", "Text", "Project"),
        _col("task", "Text", "Task"),
        _col("status", "Choice", "Status"),
        _col("assignee", "Text", "Assignee"),
        _col("priority", "Choice", "Priority"),
        _col("due_date", "Date", "Due Date"),
        _col("notes", "Text", "Notes"),
    ],
    "clients": [
        _col("name", "Text", "Name"),
        _col("email", "Text", "Email"),
        _col("company", "Text", "Company"),
        _col("status", "Choice", "Status"),
        _col("last_contact", "Date", "Last Contact"),
        _col("notes", "Text", "Notes"),
    ],
    "battery_fleet": [
        _col("device", "Text", "Device"),
        _col("channel", "Int", "Channel"),
        _col("soh_percent", "Numeric", "SoH %"),
        _col("voltage", "Numeric", "Voltage"),
        _col("r_internal", "Numeric", "R Internal"),
        _col("last_update", "DateTime", "Last Update"),
        _col("anomaly", "Bool", "Anomaly"),
    ],
}


async def create_foundation_tables(
    api_url: str,
    api_key: str,
    doc_id: str,
) -> dict[str, bool]:
    """Create all foundation tables in a Grist document if they don't exist.

    Returns a dict of ``{table_name: created}`` where ``created`` is True
    if the table was newly created, False if it already existed.
    """
    client = GristMcpClient(api_url, api_key)
    existing = await client.list_tables(doc_id)
    existing_ids = {t["id"] for t in existing}

    results: dict[str, bool] = {}
    for table_id, columns in FOUNDATION_TABLES.items():
        if table_id in existing_ids:
            logger.info("Table '%s' already exists in doc %s", table_id, doc_id)
            results[table_id] = False
            continue
        try:
            await client.create_table(doc_id, table_id, columns)
            logger.info("Created table '%s' in doc %s", table_id, doc_id)
            results[table_id] = True
        except Exception:
            logger.exception("Failed to create table '%s' in doc %s", table_id, doc_id)
            results[table_id] = False

    return results
