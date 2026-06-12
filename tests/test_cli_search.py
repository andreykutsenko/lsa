"""Tests for CLI FTS search error reporting."""

import sqlite3

from lsa.cli import _search_fts


def test_search_fts_warns_and_returns_empty_on_operational_error(capsys):
    conn = sqlite3.connect(":memory:")  # no artifacts_fts table
    rows = _search_fts(conn, "anything", 10)
    assert rows == []
    out = capsys.readouterr().out
    assert "FTS query" in out
    assert "Warning" in out
