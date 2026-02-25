"""Database connection management for LSA."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from .schema import SCHEMA


def init_db(db_path: Path) -> None:
    """Initialize database with schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


@contextmanager
def get_connection(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()


def insert_artifact(
    conn: sqlite3.Connection,
    kind: str,
    path: str,
    mtime: float,
    size: int,
    sha256: str | None = None,
    text_content: str | None = None,
    original_path: str | None = None,
) -> int:
    """Insert an artifact and return its ID."""
    cursor = conn.execute(
        """
        INSERT OR REPLACE INTO artifacts (kind, path, original_path, sha256, mtime, size, text_content)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (kind, path, original_path, sha256, mtime, size, text_content),
    )
    conn.commit()
    return cursor.lastrowid


def insert_proc(
    conn: sqlite3.Connection,
    proc_name: str,
    path: str,
    parsed_json: str,
    sha256: str | None = None,
) -> int:
    """Insert a parsed proc and return its ID."""
    cursor = conn.execute(
        """
        INSERT OR REPLACE INTO procs (proc_name, path, parsed_json, sha256)
        VALUES (?, ?, ?, ?)
        """,
        (proc_name, path, parsed_json, sha256),
    )
    conn.commit()
    return cursor.lastrowid


def insert_node(
    conn: sqlite3.Connection,
    node_type: str,
    key: str,
    display_name: str,
    canonical_path: str | None = None,
    original_path: str | None = None,
    confidence: float = 1.0,
) -> int:
    """Insert or get existing node, return its ID."""
    # Try to get existing
    row = conn.execute(
        "SELECT id FROM nodes WHERE key = ?", (key,)
    ).fetchone()
    if row:
        return row[0]

    cursor = conn.execute(
        """
        INSERT INTO nodes (type, key, display_name, canonical_path, original_path, confidence)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (node_type, key, display_name, canonical_path, original_path, confidence),
    )
    conn.commit()
    return cursor.lastrowid


def insert_edge(
    conn: sqlite3.Connection,
    src: int,
    dst: int,
    rel_type: str,
    confidence: float = 1.0,
    evidence_json: str | None = None,
) -> int:
    """Insert an edge and return its ID."""
    # Check if edge already exists
    row = conn.execute(
        "SELECT id FROM edges WHERE src = ? AND dst = ? AND rel_type = ?",
        (src, dst, rel_type),
    ).fetchone()
    if row:
        return row[0]

    cursor = conn.execute(
        """
        INSERT INTO edges (src, dst, rel_type, confidence, evidence_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (src, dst, rel_type, confidence, evidence_json),
    )
    conn.commit()
    return cursor.lastrowid


def insert_case_card(
    conn: sqlite3.Connection,
    source_path: str | None,
    chunk_id: int | None,
    title: str | None,
    signals_json: str | None,
    root_cause: str | None,
    fix_summary: str | None,
    verify_commands_json: str | None,
    related_files_json: str | None,
    tags_json: str | None,
    created_at: str,
    content_hash: str | None = None,
) -> int:
    """Insert a case card and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO case_cards (
            source_path, chunk_id, content_hash, title, signals_json, root_cause,
            fix_summary, verify_commands_json, related_files_json, tags_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_path, chunk_id, content_hash, title, signals_json, root_cause,
            fix_summary, verify_commands_json, related_files_json, tags_json, created_at,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def upsert_case_card(
    conn: sqlite3.Connection,
    source_path: str | None,
    chunk_id: int | None,
    title: str | None,
    signals_json: str | None,
    root_cause: str | None,
    fix_summary: str | None,
    verify_commands_json: str | None,
    related_files_json: str | None,
    tags_json: str | None,
    created_at: str,
    content_hash: str | None = None,
) -> tuple[int, bool]:
    """
    Insert or update a case card.

    Returns (id, was_inserted) tuple.
    """
    # Check if exists by source_path + chunk_id
    existing = conn.execute(
        "SELECT id, content_hash FROM case_cards WHERE source_path = ? AND chunk_id = ?",
        (source_path, chunk_id),
    ).fetchone()

    if existing:
        # Skip update if content hash matches (idempotent)
        if content_hash and existing["content_hash"] == content_hash:
            return existing["id"], False

        # Update existing record
        conn.execute(
            """
            UPDATE case_cards SET
                content_hash = ?,
                title = ?,
                signals_json = ?,
                root_cause = ?,
                fix_summary = ?,
                verify_commands_json = ?,
                related_files_json = ?,
                tags_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                content_hash, title, signals_json, root_cause, fix_summary,
                verify_commands_json, related_files_json, tags_json, created_at,
                existing["id"],
            ),
        )
        conn.commit()
        return existing["id"], False

    # Insert new record
    cursor = conn.execute(
        """
        INSERT INTO case_cards (
            source_path, chunk_id, content_hash, title, signals_json, root_cause,
            fix_summary, verify_commands_json, related_files_json, tags_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_path, chunk_id, content_hash, title, signals_json, root_cause,
            fix_summary, verify_commands_json, related_files_json, tags_json, created_at,
        ),
    )
    conn.commit()
    return cursor.lastrowid, True


def upsert_incident(
    conn: sqlite3.Connection,
    log_path: str,
    parsed_json: str,
    top_node_id: int | None,
    top_node_key: str | None,
    confidence: float | None,
    hypotheses_json: str | None,
    similar_cases_json: str | None,
    created_at: str,
) -> tuple[int, bool]:
    """
    Insert or update an incident by log_path.

    Returns (id, was_inserted) tuple.
    """
    existing = conn.execute(
        "SELECT id FROM incidents WHERE log_path = ?",
        (log_path,),
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE incidents SET
                parsed_json = ?,
                top_node_id = ?,
                top_node_key = ?,
                confidence = ?,
                hypotheses_json = ?,
                similar_cases_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                parsed_json, top_node_id, top_node_key, confidence,
                hypotheses_json, similar_cases_json, created_at,
                existing["id"],
            ),
        )
        conn.commit()
        return existing["id"], False

    cursor = conn.execute(
        """
        INSERT INTO incidents (
            log_path, parsed_json, top_node_id, top_node_key, confidence,
            hypotheses_json, similar_cases_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            log_path, parsed_json, top_node_id, top_node_key, confidence,
            hypotheses_json, similar_cases_json, created_at,
        ),
    )
    conn.commit()
    return cursor.lastrowid, True


def get_incidents(
    conn: sqlite3.Connection,
    limit: int = 20,
) -> list[dict]:
    """Get recent incidents."""
    rows = conn.execute(
        """
        SELECT id, log_path, top_node_key, confidence, created_at, updated_at
        FROM incidents
        ORDER BY COALESCE(updated_at, created_at) DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_incident_by_log_path(
    conn: sqlite3.Connection,
    log_path: str,
) -> dict | None:
    """Get incident by log path."""
    row = conn.execute(
        "SELECT * FROM incidents WHERE log_path = ?",
        (log_path,),
    ).fetchone()
    return dict(row) if row else None


def count_incidents(conn: sqlite3.Connection) -> int:
    """Count total incidents in database."""
    row = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()
    return row[0] if row else 0


def count_case_cards(conn: sqlite3.Connection) -> int:
    """Count total case cards in database."""
    row = conn.execute("SELECT COUNT(*) FROM case_cards").fetchone()
    return row[0] if row else 0


def insert_message_code(
    conn: sqlite3.Connection,
    code: str,
    severity: str,
    title: str | None,
    body: str,
    source_path: str,
    created_at: str,
) -> None:
    """Insert or replace a message code entry."""
    conn.execute(
        """
        INSERT OR REPLACE INTO message_codes (code, severity, title, body, source_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (code, severity, title, body, source_path, created_at),
    )
    conn.commit()


def get_message_code(conn: sqlite3.Connection, code: str) -> dict | None:
    """Get message code entry by code (returns first match across all sources)."""
    row = conn.execute(
        "SELECT code, severity, title, body, source_path, created_at FROM message_codes WHERE code = ? LIMIT 1",
        (code,),
    ).fetchone()
    if row:
        return {
            "code": row[0],
            "severity": row[1],
            "title": row[2],
            "body": row[3],
            "source_path": row[4],
            "created_at": row[5],
        }
    return None


def get_message_codes_batch(conn: sqlite3.Connection, codes: list[str]) -> dict[str, dict]:
    """Get multiple message codes at once, returns dict keyed by code."""
    if not codes:
        return {}
    placeholders = ",".join("?" for _ in codes)
    rows = conn.execute(
        f"SELECT code, severity, title, body, source_path, created_at FROM message_codes WHERE code IN ({placeholders})",
        codes,
    ).fetchall()
    result = {}
    for row in rows:
        result[row[0]] = {
            "code": row[0],
            "severity": row[1],
            "title": row[2],
            "body": row[3],
            "source_path": row[4],
            "created_at": row[5],
        }
    return result


def count_message_codes(conn: sqlite3.Connection) -> int:
    """Count total message codes in database."""
    row = conn.execute("SELECT COUNT(*) FROM message_codes").fetchone()
    return row[0] if row else 0
