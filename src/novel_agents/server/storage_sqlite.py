"""SQLite storage for scripts, runs and trace events."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from novel_agents.server.models import Event, RunSummary, now_ms

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_DIR = PROJECT_ROOT / "output"
DB_PATH = DB_DIR / "novel.sqlite3"


def _conn() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scripts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                archived INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                chapter_num INTEGER NOT NULL,
                chapter_title TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                run_json TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_script_created ON runs(script_id, created_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_events (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                ts INTEGER NOT NULL,
                type TEXT NOT NULL,
                agent TEXT,
                message TEXT NOT NULL,
                data_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_run_ts ON run_events(run_id, ts, id)"
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO scripts(id, name, description, archived, created_at, updated_at)
            VALUES(?, ?, ?, 0, ?, ?)
            """,
            ("default", "默认剧本", "", now_ms(), now_ms()),
        )


def list_scripts(include_archived: bool = False) -> list[dict[str, Any]]:
    where = "" if include_archived else "WHERE archived=0"
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT id, name, description, archived, created_at, updated_at FROM scripts {where} ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_script(script_id: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, name, description, archived, created_at, updated_at FROM scripts WHERE id=?",
            (script_id,),
        ).fetchone()
    return dict(row) if row else None


def create_script(script_id: str, name: str, description: str = "") -> dict[str, Any]:
    ts = now_ms()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO scripts(id, name, description, archived, created_at, updated_at)
            VALUES(?, ?, ?, 0, ?, ?)
            """,
            (script_id, name, description, ts, ts),
        )
    return get_script(script_id) or {}


def update_script(
    script_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    archived: bool | None = None,
) -> dict[str, Any] | None:
    cur = get_script(script_id)
    if not cur:
        return None
    next_name = name if name is not None else str(cur["name"])
    next_desc = description if description is not None else str(cur["description"])
    next_archived = int(archived) if archived is not None else int(cur["archived"])
    with _conn() as conn:
        conn.execute(
            """
            UPDATE scripts
            SET name=?, description=?, archived=?, updated_at=?
            WHERE id=?
            """,
            (next_name, next_desc, next_archived, now_ms(), script_id),
        )
    return get_script(script_id)


def soft_delete_script(script_id: str) -> bool:
    updated = update_script(script_id, archived=True)
    return bool(updated)


def upsert_run(run: RunSummary) -> None:
    payload = json.dumps(run.model_dump(), ensure_ascii=False)
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO runs(run_id, script_id, chapter_num, chapter_title, mode, status, created_at, run_json, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                script_id=excluded.script_id,
                chapter_num=excluded.chapter_num,
                chapter_title=excluded.chapter_title,
                mode=excluded.mode,
                status=excluded.status,
                run_json=excluded.run_json,
                updated_at=excluded.updated_at
            """,
            (
                run.run_id,
                run.script_id,
                run.chapter_num,
                run.chapter_title,
                run.mode,
                run.status,
                run.created_at,
                payload,
                now_ms(),
            ),
        )


def get_run(run_id: str) -> RunSummary | None:
    with _conn() as conn:
        row = conn.execute("SELECT run_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if not row:
        return None
    return RunSummary.model_validate(json.loads(row["run_json"]))


def list_runs(script_id: str | None = None) -> list[RunSummary]:
    with _conn() as conn:
        if script_id:
            rows = conn.execute(
                "SELECT run_json FROM runs WHERE script_id=? ORDER BY created_at DESC",
                (script_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT run_json FROM runs ORDER BY created_at DESC"
            ).fetchall()
    return [RunSummary.model_validate(json.loads(row["run_json"])) for row in rows]


def append_event(event: Event) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO run_events(id, run_id, ts, type, agent, message, data_json)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.run_id,
                event.ts,
                event.type,
                event.agent,
                event.message,
                json.dumps(event.data, ensure_ascii=False),
            ),
        )


def get_events(run_id: str, limit: int = 5000, offset: int = 0) -> list[Event]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, run_id, ts, type, agent, message, data_json
            FROM run_events
            WHERE run_id=?
            ORDER BY ts ASC, id ASC
            LIMIT ? OFFSET ?
            """,
            (run_id, max(1, min(limit, 20000)), max(0, offset)),
        ).fetchall()
    events: list[Event] = []
    for row in rows:
        events.append(
            Event(
                id=row["id"],
                run_id=row["run_id"],
                ts=row["ts"],
                type=row["type"],
                agent=row["agent"],
                message=row["message"],
                data=json.loads(row["data_json"] or "{}"),
            )
        )
    return events
