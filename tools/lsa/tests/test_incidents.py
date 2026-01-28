"""Tests for incidents persistence and import-histories improvements."""

import json
import pytest
from datetime import datetime
from pathlib import Path

from lsa.db import init_db, get_connection
from lsa.db.connection import (
    upsert_case_card,
    upsert_incident,
    get_incidents,
    get_incident_by_log_path,
    count_incidents,
    count_case_cards,
)
from lsa.parsers.history_parser import (
    parse_history_directory,
    parse_history_files,
    CaseCard,
    compute_chunk_hash,
)


class TestUpsertCaseCard:
    """Test upsert logic for case_cards."""

    def test_insert_new_card(self, tmp_path):
        """Should insert a new case card."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with get_connection(db_path) as conn:
            card_id, was_inserted = upsert_case_card(
                conn,
                source_path="/test/history.txt",
                chunk_id=0,
                title="Test Card",
                signals_json='["ORA-12345"]',
                root_cause="Test root cause",
                fix_summary="Test fix",
                verify_commands_json='["ls -la"]',
                related_files_json='["/path/to/file.sh"]',
                tags_json='["oracle"]',
                created_at=datetime.now().isoformat(),
                content_hash="abc123",
            )

            assert was_inserted is True
            assert card_id > 0
            assert count_case_cards(conn) == 1

    def test_update_existing_card(self, tmp_path):
        """Should update an existing case card by source_path+chunk_id."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with get_connection(db_path) as conn:
            # Insert first time
            card_id1, was_inserted1 = upsert_case_card(
                conn,
                source_path="/test/history.txt",
                chunk_id=0,
                title="Original Title",
                signals_json='["ORA-12345"]',
                root_cause=None,
                fix_summary=None,
                verify_commands_json=None,
                related_files_json=None,
                tags_json=None,
                created_at=datetime.now().isoformat(),
                content_hash="abc123",
            )

            # Update with different content_hash
            card_id2, was_inserted2 = upsert_case_card(
                conn,
                source_path="/test/history.txt",
                chunk_id=0,
                title="Updated Title",
                signals_json='["ORA-12345", "PPCS0001E"]',
                root_cause="Found root cause",
                fix_summary=None,
                verify_commands_json=None,
                related_files_json=None,
                tags_json=None,
                created_at=datetime.now().isoformat(),
                content_hash="def456",  # Different hash
            )

            assert was_inserted1 is True
            assert was_inserted2 is False
            assert card_id1 == card_id2
            assert count_case_cards(conn) == 1

            # Verify title was updated
            row = conn.execute(
                "SELECT title FROM case_cards WHERE id = ?",
                (card_id1,)
            ).fetchone()
            assert row["title"] == "Updated Title"

    def test_skip_update_when_hash_matches(self, tmp_path):
        """Should skip update if content_hash matches."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with get_connection(db_path) as conn:
            # Insert
            card_id1, _ = upsert_case_card(
                conn,
                source_path="/test/history.txt",
                chunk_id=0,
                title="Title",
                signals_json='["ORA-12345"]',
                root_cause=None,
                fix_summary=None,
                verify_commands_json=None,
                related_files_json=None,
                tags_json=None,
                created_at=datetime.now().isoformat(),
                content_hash="abc123",
            )

            # Try to update with same hash
            card_id2, was_inserted = upsert_case_card(
                conn,
                source_path="/test/history.txt",
                chunk_id=0,
                title="New Title",  # Different title
                signals_json='["ORA-12345"]',
                root_cause=None,
                fix_summary=None,
                verify_commands_json=None,
                related_files_json=None,
                tags_json=None,
                created_at=datetime.now().isoformat(),
                content_hash="abc123",  # Same hash
            )

            assert was_inserted is False
            assert card_id1 == card_id2

            # Verify title was NOT updated
            row = conn.execute(
                "SELECT title FROM case_cards WHERE id = ?",
                (card_id1,)
            ).fetchone()
            assert row["title"] == "Title"


class TestUpsertIncident:
    """Test upsert logic for incidents."""

    def test_insert_new_incident(self, tmp_path):
        """Should insert a new incident."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with get_connection(db_path) as conn:
            inc_id, was_inserted = upsert_incident(
                conn,
                log_path="/d/test/test.log",
                parsed_json='{"total_lines": 100}',
                top_node_id=None,
                top_node_key="proc:bkfnds1",
                confidence=0.85,
                hypotheses_json='[{"hypothesis": "Test"}]',
                similar_cases_json=None,
                created_at=datetime.now().isoformat(),
            )

            assert was_inserted is True
            assert inc_id > 0
            assert count_incidents(conn) == 1

    def test_update_existing_incident_by_log_path(self, tmp_path):
        """Should update an existing incident by log_path."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with get_connection(db_path) as conn:
            # Insert
            inc_id1, _ = upsert_incident(
                conn,
                log_path="/d/test/test.log",
                parsed_json='{"total_lines": 100}',
                top_node_id=None,
                top_node_key="proc:bkfnds1",
                confidence=0.85,
                hypotheses_json='[]',
                similar_cases_json=None,
                created_at=datetime.now().isoformat(),
            )

            # Update
            inc_id2, was_inserted = upsert_incident(
                conn,
                log_path="/d/test/test.log",  # Same log path
                parsed_json='{"total_lines": 200}',
                top_node_id=None,
                top_node_key="proc:bkfnds2",  # Different node
                confidence=0.95,
                hypotheses_json='[{"hypothesis": "New"}]',
                similar_cases_json=None,
                created_at=datetime.now().isoformat(),
            )

            assert was_inserted is False
            assert inc_id1 == inc_id2
            assert count_incidents(conn) == 1

            # Verify update
            inc = get_incident_by_log_path(conn, "/d/test/test.log")
            assert inc["top_node_key"] == "proc:bkfnds2"
            assert inc["confidence"] == 0.95

    def test_get_incidents_sorted_by_date(self, tmp_path):
        """Should return incidents sorted by most recent first."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with get_connection(db_path) as conn:
            upsert_incident(
                conn,
                log_path="/d/test/old.log",
                parsed_json='{}',
                top_node_id=None,
                top_node_key="proc:old",
                confidence=0.5,
                hypotheses_json=None,
                similar_cases_json=None,
                created_at="2026-01-01T00:00:00",
            )
            upsert_incident(
                conn,
                log_path="/d/test/new.log",
                parsed_json='{}',
                top_node_id=None,
                top_node_key="proc:new",
                confidence=0.9,
                hypotheses_json=None,
                similar_cases_json=None,
                created_at="2026-01-27T00:00:00",
            )

            incidents = get_incidents(conn, limit=10)

            assert len(incidents) == 2
            assert incidents[0]["log_path"] == "/d/test/new.log"
            assert incidents[1]["log_path"] == "/d/test/old.log"


class TestImportHistoriesGlob:
    """Test import-histories with glob patterns."""

    def test_parse_with_default_patterns(self, tmp_path):
        """Should parse *.txt and *.md by default."""
        histories_dir = tmp_path / "histories"
        histories_dir.mkdir()

        # Create test files
        (histories_dir / "case1.txt").write_text("ORA-12345: error occurred")
        (histories_dir / "case2.md").write_text("PPCS0001E: message code error")
        (histories_dir / "ignored.log").write_text("should be ignored")

        cards = parse_history_directory(histories_dir)

        # Should parse txt and md, not log
        assert len(cards) >= 2
        sources = {card.source_path for card in cards}
        assert str(histories_dir / "case1.txt") in sources
        assert str(histories_dir / "case2.md") in sources

    def test_parse_with_glob_pattern(self, tmp_path):
        """Should respect glob pattern when provided."""
        histories_dir = tmp_path / "histories"
        histories_dir.mkdir()

        # Create test files
        (histories_dir / "case1.txt").write_text("ORA-12345")
        (histories_dir / "case2.md").write_text("ORA-54321")

        # Parse only .md files
        cards = parse_history_directory(histories_dir, glob_pattern="*.md")

        sources = {card.source_path for card in cards}
        assert str(histories_dir / "case2.md") in sources
        assert str(histories_dir / "case1.txt") not in sources

    def test_parse_recursive_glob(self, tmp_path):
        """Should support recursive glob patterns."""
        histories_dir = tmp_path / "histories"
        subdir = histories_dir / "subdir"
        subdir.mkdir(parents=True)

        # Create nested files
        (histories_dir / "root.txt").write_text("ORA-11111")
        (subdir / "nested.txt").write_text("ORA-22222")

        # Parse with recursive pattern
        cards = parse_history_directory(histories_dir, glob_pattern="**/*.txt")

        sources = {card.source_path for card in cards}
        assert str(histories_dir / "root.txt") in sources
        assert str(subdir / "nested.txt") in sources


class TestContentHash:
    """Test content hash computation and idempotent imports."""

    def test_compute_chunk_hash(self):
        """Should compute deterministic hash."""
        text = "ORA-12345: sample error"
        hash1 = compute_chunk_hash(text)
        hash2 = compute_chunk_hash(text)

        assert hash1 == hash2
        assert len(hash1) == 16  # First 16 chars of SHA256

    def test_different_content_different_hash(self):
        """Should produce different hashes for different content."""
        hash1 = compute_chunk_hash("ORA-12345")
        hash2 = compute_chunk_hash("ORA-54321")

        assert hash1 != hash2

    def test_case_card_has_content_hash(self, tmp_path):
        """CaseCard should have content_hash populated."""
        histories_dir = tmp_path / "histories"
        histories_dir.mkdir()
        (histories_dir / "test.txt").write_text("ORA-12345: error")

        cards = parse_history_directory(histories_dir)

        assert len(cards) >= 1
        assert cards[0].content_hash is not None
        assert len(cards[0].content_hash) == 16


class TestParseHistoryFiles:
    """Test parse_history_files function."""

    def test_parse_multiple_files(self, tmp_path):
        """Should parse list of specific files."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("ORA-11111: error 1")
        file2.write_text("ORA-22222: error 2")

        cards = parse_history_files([file1, file2])

        assert len(cards) >= 2
        sources = {card.source_path for card in cards}
        assert str(file1) in sources
        assert str(file2) in sources

    def test_skips_nonexistent_files(self, tmp_path):
        """Should skip files that don't exist."""
        existing = tmp_path / "exists.txt"
        existing.write_text("ORA-12345")
        nonexistent = tmp_path / "missing.txt"

        cards = parse_history_files([existing, nonexistent])

        # Should only parse existing file
        sources = {card.source_path for card in cards}
        assert str(existing) in sources
        assert str(nonexistent) not in sources


class TestHistoriesPathAutoDetection:
    """Test histories path auto-detection logic."""

    def test_chooses_snapshot_local_when_present(self, tmp_path):
        """Should choose snapshot-local histories over parent."""
        from lsa.cli import _find_histories_path

        # Setup: both snapshot/histories and parent/histories exist
        parent = tmp_path / "project"
        snapshot = parent / "snapshot"
        snapshot.mkdir(parents=True)

        snapshot_histories = snapshot / "histories"
        snapshot_histories.mkdir()
        (snapshot_histories / "local.txt").write_text("local content")

        parent_histories = parent / "histories"
        parent_histories.mkdir()
        (parent_histories / "shared.txt").write_text("shared content")

        # Should choose snapshot-local
        result = _find_histories_path(snapshot, None)
        assert result == snapshot_histories

    def test_falls_back_to_parent_histories(self, tmp_path):
        """Should fall back to parent/histories when snapshot-local missing."""
        from lsa.cli import _find_histories_path

        # Setup: only parent/histories exists
        parent = tmp_path / "project"
        snapshot = parent / "snapshot"
        snapshot.mkdir(parents=True)

        parent_histories = parent / "histories"
        parent_histories.mkdir()
        (parent_histories / "shared.txt").write_text("shared content")

        # Should fall back to parent
        result = _find_histories_path(snapshot, None)
        assert result == parent_histories

    def test_falls_back_to_parent_refs_histories(self, tmp_path):
        """Should fall back to parent/refs/histories."""
        from lsa.cli import _find_histories_path

        # Setup: only parent/refs/histories exists
        parent = tmp_path / "project"
        snapshot = parent / "snapshot"
        snapshot.mkdir(parents=True)

        parent_refs_histories = parent / "refs" / "histories"
        parent_refs_histories.mkdir(parents=True)
        (parent_refs_histories / "shared.txt").write_text("shared content")

        # Should fall back to parent/refs/histories
        result = _find_histories_path(snapshot, None)
        assert result == parent_refs_histories

    def test_snapshot_refs_histories_before_parent(self, tmp_path):
        """Should prefer snapshot/refs/histories over parent/histories."""
        from lsa.cli import _find_histories_path

        # Setup: snapshot/refs/histories and parent/histories both exist
        parent = tmp_path / "project"
        snapshot = parent / "snapshot"
        snapshot.mkdir(parents=True)

        snapshot_refs_histories = snapshot / "refs" / "histories"
        snapshot_refs_histories.mkdir(parents=True)
        (snapshot_refs_histories / "local.txt").write_text("local refs")

        parent_histories = parent / "histories"
        parent_histories.mkdir()
        (parent_histories / "shared.txt").write_text("shared content")

        # Should choose snapshot/refs/histories (precedence 2 > 3)
        result = _find_histories_path(snapshot, None)
        assert result == snapshot_refs_histories

    def test_explicit_path_overrides_all(self, tmp_path):
        """Explicit --path should override auto-detection."""
        from lsa.cli import _find_histories_path

        # Setup: snapshot/histories exists
        parent = tmp_path / "project"
        snapshot = parent / "snapshot"
        snapshot.mkdir(parents=True)

        snapshot_histories = snapshot / "histories"
        snapshot_histories.mkdir()

        # Create explicit path
        explicit = tmp_path / "custom_histories"
        explicit.mkdir()

        # Explicit path should win
        result = _find_histories_path(snapshot, explicit)
        assert result == explicit

    def test_returns_none_when_nothing_found(self, tmp_path):
        """Should return None when no histories directory found."""
        from lsa.cli import _find_histories_path

        snapshot = tmp_path / "empty_snapshot"
        snapshot.mkdir()

        result = _find_histories_path(snapshot, None)
        assert result is None

    def test_search_paths_list_correct_order(self, tmp_path):
        """Should list search paths in correct precedence order."""
        from lsa.cli import _get_histories_search_paths

        parent = tmp_path / "project"
        snapshot = parent / "snapshot"
        snapshot.mkdir(parents=True)

        paths = _get_histories_search_paths(snapshot)

        assert len(paths) == 4
        assert paths[0] == snapshot / "histories"
        assert paths[1] == snapshot / "refs" / "histories"
        assert paths[2] == parent / "histories"
        assert paths[3] == parent / "refs" / "histories"
