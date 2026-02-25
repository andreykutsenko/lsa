"""Tests for import-codes command path auto-detection."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import os


class TestFindPdfPath:
    """Test PDF path auto-detection logic."""

    def test_explicit_pdf_option_used(self, tmp_path):
        """Explicit --pdf option should be used when provided and exists."""
        from lsa.cli import _find_pdf_path

        # Create a PDF file
        pdf_file = tmp_path / "explicit.pdf"
        pdf_file.touch()

        snapshot = tmp_path / "snapshot"
        snapshot.mkdir()

        result = _find_pdf_path(snapshot, pdf_file)
        assert result == pdf_file

    def test_explicit_pdf_not_exists_returns_none(self, tmp_path):
        """Non-existent explicit --pdf should return None."""
        from lsa.cli import _find_pdf_path

        snapshot = tmp_path / "snapshot"
        snapshot.mkdir()

        nonexistent = tmp_path / "nonexistent.pdf"

        result = _find_pdf_path(snapshot, nonexistent)
        assert result is None

    def test_snapshot_refs_papyrus_detected(self, tmp_path):
        """PDF in <snapshot>/refs/papyrus/ should be detected."""
        from lsa.cli import _find_pdf_path

        snapshot = tmp_path / "snapshot"
        refs_dir = snapshot / "refs" / "papyrus"
        refs_dir.mkdir(parents=True)

        pdf_file = refs_dir / "message_codes.pdf"
        pdf_file.touch()

        result = _find_pdf_path(snapshot, None)
        assert result == pdf_file

    def test_snapshot_refs_multiple_pdfs_uses_first(self, tmp_path):
        """When multiple PDFs exist, the first one should be used."""
        from lsa.cli import _find_pdf_path

        snapshot = tmp_path / "snapshot"
        refs_dir = snapshot / "refs" / "papyrus"
        refs_dir.mkdir(parents=True)

        # Create multiple PDFs (glob order may vary)
        (refs_dir / "a_first.pdf").touch()
        (refs_dir / "b_second.pdf").touch()

        result = _find_pdf_path(snapshot, None)
        assert result is not None
        assert result.suffix == ".pdf"

    def test_global_default_path_detected(self, tmp_path):
        """Global default path should be used if snapshot has no PDFs."""
        from lsa.cli import _find_pdf_path

        snapshot = tmp_path / "snapshot"
        snapshot.mkdir()

        # Create a mock global path
        global_refs = tmp_path / "global_refs" / "papyrus"
        global_refs.mkdir(parents=True)
        global_pdf = global_refs / "Papyrus_DocExec_message_codes.pdf"
        global_pdf.touch()

        # Patch DEFAULT_PDF_PATHS to use our test path
        with patch('lsa.cli.DEFAULT_PDF_PATHS', [global_pdf]):
            result = _find_pdf_path(snapshot, None)
            assert result == global_pdf

    def test_no_pdf_found_returns_none(self, tmp_path):
        """When no PDF is found anywhere, should return None."""
        from lsa.cli import _find_pdf_path

        snapshot = tmp_path / "snapshot"
        snapshot.mkdir()

        # Patch DEFAULT_PDF_PATHS to be empty or all non-existent
        with patch('lsa.cli.DEFAULT_PDF_PATHS', []):
            result = _find_pdf_path(snapshot, None)
            assert result is None


class TestImportCodesIntegration:
    """Integration tests for import-codes command."""

    @pytest.fixture
    def mock_snapshot(self, tmp_path):
        """Create a mock snapshot directory with database."""
        snapshot = tmp_path / "snapshot"
        snapshot.mkdir()

        # Create .lsa directory and database
        lsa_dir = snapshot / ".lsa"
        lsa_dir.mkdir()

        return snapshot

    def test_import_codes_requires_pdf(self, mock_snapshot):
        """import-codes should fail gracefully when no PDF found."""
        from typer.testing import CliRunner
        from lsa.cli import app

        runner = CliRunner()

        with patch('lsa.cli.DEFAULT_PDF_PATHS', []):
            result = runner.invoke(app, ["import-codes", str(mock_snapshot)])

        assert result.exit_code != 0
        assert "PDF not found" in result.output or "Error" in result.output

    def test_import_codes_with_valid_pdf(self, mock_snapshot, tmp_path):
        """import-codes should work with a valid PDF."""
        from typer.testing import CliRunner
        from lsa.cli import app
        from lsa.db import init_db
        from lsa.parsers.pdf_parser import MessageCodeEntry

        # Initialize database
        db_path = mock_snapshot / ".lsa" / "lsa.sqlite"
        init_db(db_path)

        # Create a mock PDF (empty file)
        pdf_file = tmp_path / "codes.pdf"
        pdf_file.touch()

        runner = CliRunner()

        # Mock the PDF parser at the source module
        with patch('lsa.parsers.pdf_parser.parse_pdf_file_safe') as mock_parse:
            mock_parse.return_value = (
                [
                    MessageCodeEntry(
                        code="PPCS1001I",
                        severity="I",
                        title="Test code",
                        body="Test description",
                    ),
                ],
                [],  # No errors
            )

            result = runner.invoke(app, [
                "import-codes",
                str(mock_snapshot),
                "--pdf", str(pdf_file),
            ])

        assert result.exit_code == 0
        assert "Import complete" in result.output
        assert "Codes extracted from PDF: 1" in result.output


class TestDatabaseOperations:
    """Test database operations for message codes."""

    @pytest.fixture
    def db_connection(self, tmp_path):
        """Create a test database connection."""
        from lsa.db import init_db, get_connection

        db_path = tmp_path / ".lsa" / "lsa.sqlite"
        init_db(db_path)

        with get_connection(db_path) as conn:
            yield conn

    def test_insert_message_code(self, db_connection):
        """Test inserting a message code."""
        from lsa.db import insert_message_code, get_message_code

        insert_message_code(
            db_connection,
            code="PPCS1001I",
            severity="I",
            title="Test title",
            body="Test body",
            source_path="/test/source.pdf",
            created_at="2026-01-01T00:00:00",
        )

        result = get_message_code(db_connection, "PPCS1001I")
        assert result is not None
        assert result["code"] == "PPCS1001I"
        assert result["severity"] == "I"
        assert result["title"] == "Test title"
        assert result["body"] == "Test body"

    def test_upsert_message_code(self, db_connection):
        """Test that insert_message_code upserts on conflict."""
        from lsa.db import insert_message_code, get_message_code

        # First insert
        insert_message_code(
            db_connection,
            code="PPCS1001I",
            severity="I",
            title="Original title",
            body="Original body",
            source_path="/test/source.pdf",
            created_at="2026-01-01T00:00:00",
        )

        # Second insert (should update)
        insert_message_code(
            db_connection,
            code="PPCS1001I",
            severity="I",
            title="Updated title",
            body="Updated body",
            source_path="/test/source.pdf",
            created_at="2026-01-02T00:00:00",
        )

        result = get_message_code(db_connection, "PPCS1001I")
        assert result is not None
        assert result["title"] == "Updated title"
        assert result["body"] == "Updated body"

    def test_get_message_codes_batch(self, db_connection):
        """Test batch retrieval of message codes."""
        from lsa.db import insert_message_code, get_message_codes_batch

        # Insert multiple codes
        for i, (code, severity) in enumerate([
            ("PPCS1001I", "I"),
            ("PPDE2001E", "E"),
            ("AFPR3001F", "F"),
        ]):
            insert_message_code(
                db_connection,
                code=code,
                severity=severity,
                title=f"Title {i}",
                body=f"Body {i}",
                source_path="/test/source.pdf",
                created_at="2026-01-01T00:00:00",
            )

        result = get_message_codes_batch(
            db_connection,
            ["PPCS1001I", "PPDE2001E", "NONEXISTENT"],
        )

        assert "PPCS1001I" in result
        assert "PPDE2001E" in result
        assert "NONEXISTENT" not in result
        assert len(result) == 2

    def test_count_message_codes(self, db_connection):
        """Test counting message codes."""
        from lsa.db import insert_message_code, count_message_codes

        assert count_message_codes(db_connection) == 0

        insert_message_code(
            db_connection,
            code="PPCS1001I",
            severity="I",
            title="Test",
            body="Test",
            source_path="/test/source.pdf",
            created_at="2026-01-01T00:00:00",
        )

        assert count_message_codes(db_connection) == 1
