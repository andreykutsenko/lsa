from pathlib import Path
import sqlite3
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from lsa.web import server


def _candidate():
    return SimpleNamespace(
        proc_name="wccuds1",
        display_name="WCCU DS1",
        files=[
            SimpleNamespace(kind="procs", path="procs/wccuds1.procs", source="proc_match"),
            SimpleNamespace(kind="script", path="master/run_main.sh", source="RUNS_edge"),
            SimpleNamespace(kind="script", path="master/helper.sh", source="helper_prefix_match"),
            SimpleNamespace(kind="control", path="control/wccu.ctl", source="related_control"),
            SimpleNamespace(kind="docdef", path="docdef/wccu.dfa", source="related_docdef"),
            SimpleNamespace(kind="insert", path="insert/wccu.ins", source="READS_edge"),
        ],
    )


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE artifacts (
            id INTEGER PRIMARY KEY,
            path TEXT,
            kind TEXT,
            text_content TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO artifacts(path, kind, text_content) VALUES (?, ?, ?)",
        [
            ("procs/wccuds1.procs", "procs", "CID 123 and main proc"),
            ("master/run_main.sh", "script", "echo running incident path"),
            ("control/wccu.ctl", "control", "docdef=wccu"),
            ("refs/notes.md", "refs", "support note"),
        ],
    )
    conn.execute(
        """
        CREATE TABLE message_codes (
            code TEXT,
            severity TEXT,
            title TEXT,
            body TEXT,
            source_path TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE case_cards (
            id INTEGER PRIMARY KEY,
            source_path TEXT,
            title TEXT,
            root_cause TEXT,
            fix_summary TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO message_codes(code, severity, title, body, source_path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("PPCS1001E", "E", "Papyrus failure", "Reason: missing resource. Solution: update mapping.", "/refs/papyrus.pdf", "2026-03-25"),
    )
    conn.execute(
        "INSERT INTO case_cards(source_path, title, root_cause, fix_summary, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("/histories/inc-1.md", "Incident 1", "Wrong queue mapping", "Fix queue configuration", "2026-03-24", "2026-03-25"),
    )
    return conn


def test_operator_scope_summary_groups_scope():
    summary = server._operator_scope_summary(_candidate())
    assert summary["file_count"] == 6
    assert summary["counts"]["procs"] == 1
    assert summary["counts"]["scripts"] == 2
    assert summary["counts"]["controls"] == 1
    assert summary["counts"]["docdef"] == 1
    assert summary["counts"]["inserts"] == 1
    assert "script: run_main.sh" in summary["read_order"]


def test_build_scenario_prompt_includes_scope_and_diagram(monkeypatch, tmp_path):
    monkeypatch.setattr("lsa.output.mermaid.generate_mermaid", lambda candidate, snapshot: "graph TD\nA-->B")
    payload = server._build_scenario_prompt(
        tmp_path,
        _candidate(),
        lang="ru",
        scenario="incident",
        prompt_input="PPCS1001E in ticket",
        include_diagram=True,
    )
    assert "# Incident analysis" in payload["prompt_text"]
    assert "PPCS1001E in ticket" in payload["prompt_text"]
    assert "graph TD" in payload["prompt_text"]
    assert payload["scope_summary"]["counts"]["scripts"] == 2


def test_search_path_only_filters_kind_and_scope():
    conn = _conn()
    try:
        rows = server._search_path_only(
            conn,
            "wccu",
            20,
            kind="controls",
            scope_paths={"control/wccu.ctl", "master/run_main.sh"},
        )
        assert len(rows) == 1
        assert rows[0]["path"] == "control/wccu.ctl"
        assert rows[0]["match_type"] == "path"
    finally:
        conn.close()


def test_search_like_filters_snapshot_scope_and_kind():
    conn = _conn()
    try:
        rows = server._search_like(
            conn,
            "incident",
            20,
            kind="scripts",
            scope_paths={"master/run_main.sh"},
        )
        assert len(rows) == 1
        assert rows[0]["path"] == "master/run_main.sh"
        assert rows[0]["match_type"] == "content"
    finally:
        conn.close()


def test_search_message_codes_returns_preview_content():
    conn = _conn()
    try:
        rows = server._search_message_codes(conn, "PPCS1001E", 10)
        assert len(rows) == 1
        assert rows[0]["kind"] == "message_code"
        assert "missing resource" in rows[0]["preview_content"]
    finally:
        conn.close()


def test_search_case_cards_returns_preview_content():
    conn = _conn()
    try:
        rows = server._search_case_cards(conn, "queue", 10)
        assert len(rows) == 1
        assert rows[0]["kind"] == "case_card"
        assert "Wrong queue mapping" in rows[0]["preview_content"]
    finally:
        conn.close()


@pytest.mark.anyio
async def test_search_space_knowledge_returns_only_knowledge(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_get_snapshot", lambda: tmp_path)
    monkeypatch.setattr(server, "_open_connection", lambda snapshot: _conn())
    server._last_candidates = [_candidate()]
    rows = await server.search(
        q="PPCS1001E",
        limit=20,
        mode="content",
        scope="snapshot",
        kind="all",
        space="knowledge",
        candidate_index=0,
    )
    assert len(rows) == 1
    assert rows[0]["kind"] == "message_code"
    assert rows[0]["match_type"] == "knowledge"


@pytest.mark.anyio
async def test_search_space_all_keeps_knowledge_when_scope_is_current(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_get_snapshot", lambda: tmp_path)
    monkeypatch.setattr(server, "_open_connection", lambda snapshot: _conn())
    server._last_candidates = [_candidate()]
    rows = await server.search(
        q="PPCS1001E",
        limit=20,
        mode="content",
        scope="current",
        kind="all",
        space="all",
        candidate_index=0,
    )
    assert rows
    assert any(row["kind"] == "message_code" for row in rows)


def test_new_snapshot_request_accepts_control_and_insert_paths():
    req = server.NewSnapshotRequest(
        name="snap1",
        control_path="/tmp/control",
        insert_path="/tmp/insert",
    )
    assert req.control_path == "/tmp/control"
    assert req.insert_path == "/tmp/insert"


def test_app_js_parses_when_node_is_available():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available")

    app_js = Path(__file__).resolve().parents[1] / "lsa" / "web" / "static" / "app.js"
    result = subprocess.run(
        [node, "--check", str(app_js)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
