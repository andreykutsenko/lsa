"""Tests for connection-level commit/rollback and batched inserts."""

import pytest

from lsa.db import init_db
from lsa.db.connection import get_connection, insert_artifact


def _count(db_path):
    with get_connection(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]


def test_get_connection_commits_batched_inserts_on_success(tmp_path):
    db = tmp_path / "t.sqlite"
    init_db(db)
    with get_connection(db) as conn:
        insert_artifact(conn, kind="script", path="a.sh", mtime=0.0, size=1, commit=False)
        insert_artifact(conn, kind="script", path="b.sh", mtime=0.0, size=1, commit=False)
    assert _count(db) == 2


def test_get_connection_rolls_back_on_exception(tmp_path):
    db = tmp_path / "t.sqlite"
    init_db(db)
    with pytest.raises(RuntimeError, match="boom"):
        with get_connection(db) as conn:
            insert_artifact(conn, kind="script", path="a.sh", mtime=0.0, size=1, commit=False)
            raise RuntimeError("boom")
    assert _count(db) == 0


def test_insert_with_default_commit_persists(tmp_path):
    db = tmp_path / "t.sqlite"
    init_db(db)
    with get_connection(db) as conn:
        insert_artifact(conn, kind="script", path="a.sh", mtime=0.0, size=1)
    assert _count(db) == 1
