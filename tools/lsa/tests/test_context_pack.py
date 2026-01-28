"""Tests for context pack generation with decoded codes."""

import pytest
from pathlib import Path

from lsa.parsers.log_parser import LogAnalysis, LogSignal
from lsa.analysis.hypotheses import Hypothesis
from lsa.analysis.similarity import SimilarCase
from lsa.output.context_pack import generate_context_pack


def make_log_analysis(
    error_codes: list[str] | None = None,
    docdef_tokens: list[str] | None = None,
    script_paths: list[str] | None = None,
    io_paths: list[str] | None = None,
) -> LogAnalysis:
    """Create a LogAnalysis for testing."""
    return LogAnalysis(
        path="/test/sample.log",
        total_lines=100,
        error_codes=error_codes or [],
        docdef_tokens=docdef_tokens or [],
        script_paths=script_paths or [],
        io_paths=io_paths or [],
    )


class TestDecodedCodesSection:
    """Test PAPYRUS/DOCEXEC CODES section in context pack."""

    def test_unknown_codes_when_kb_empty(self, tmp_path):
        """Codes should show UNKNOWN when KB is empty."""
        log_analysis = make_log_analysis(error_codes=["PPCS1001E", "PPDE2001I"])

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes={},  # Empty KB
        )

        assert "PAPYRUS/DOCEXEC CODES" in context_pack
        assert "PPCS1001E" in context_pack
        assert "UNKNOWN CODE" in context_pack

    def test_decoded_codes_shown_when_kb_populated(self, tmp_path):
        """Codes should be decoded when KB is populated."""
        log_analysis = make_log_analysis(error_codes=["PPCS1001E", "PPDE2001I"])

        decoded_codes = {
            "PPCS1001E": {
                "code": "PPCS1001E",
                "severity": "E",
                "title": "Application Error",
                "body": "The application encountered an error during processing.",
            },
            "PPDE2001I": {
                "code": "PPDE2001I",
                "severity": "I",
                "title": "Document Info",
                "body": "Document generation started successfully.",
            },
        }

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes=decoded_codes,
        )

        assert "PAPYRUS/DOCEXEC CODES" in context_pack
        assert "PPCS1001E" in context_pack
        assert "[Error]" in context_pack
        assert "Application Error" in context_pack
        assert "PPDE2001I" in context_pack
        assert "[Info]" in context_pack

    def test_mixed_known_unknown_codes(self, tmp_path):
        """Some codes decoded, some unknown."""
        log_analysis = make_log_analysis(
            error_codes=["PPCS1001E", "PPDE2001I", "AFPR9999F"]
        )

        decoded_codes = {
            "PPCS1001E": {
                "code": "PPCS1001E",
                "severity": "E",
                "title": "Known Error",
                "body": "This error is documented.",
            },
        }

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes=decoded_codes,
        )

        assert "PPCS1001E" in context_pack
        assert "Known Error" in context_pack
        assert "AFPR9999F" in context_pack
        assert "UNKNOWN CODE" in context_pack

    def test_fatal_codes_prioritized(self, tmp_path):
        """Fatal (F) codes should appear before Error (E) codes in decoded section."""
        log_analysis = make_log_analysis(
            error_codes=["PPCS1001I", "PPDE2001E", "AFPR9999F"]
        )

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes={},
        )

        # Find the decoded section specifically
        section_start = context_pack.find("3b. PAPYRUS")
        section_end = context_pack.find("3c. FILES")
        decoded_section = context_pack[section_start:section_end]

        # F should appear before E and I in the decoded section
        f_pos = decoded_section.find("AFPR9999F")
        e_pos = decoded_section.find("PPDE2001E")
        i_pos = decoded_section.find("PPCS1001I")

        # Fatal should be first in the codes section
        assert f_pos < e_pos, f"Fatal ({f_pos}) should be before Error ({e_pos})"
        assert e_pos < i_pos, f"Error ({e_pos}) should be before Info ({i_pos})"

    def test_no_codes_message(self, tmp_path):
        """Should show message when no codes found."""
        log_analysis = make_log_analysis(error_codes=[])

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes={},
        )

        assert "No Papyrus/DocExec codes found" in context_pack


class TestFilesFromLogEvidence:
    """Test FILES FROM LOG EVIDENCE section."""

    def test_docdef_tokens_shown(self, tmp_path):
        """DOCDEF tokens should be listed."""
        log_analysis = make_log_analysis(
            docdef_tokens=["BKFNDS11", "ACBKDS21"]
        )

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes={},
        )

        assert "FILES FROM LOG EVIDENCE" in context_pack
        assert "BKFNDS11" in context_pack
        assert "ACBKDS21" in context_pack
        assert "DOCDEF tokens" in context_pack

    def test_script_paths_shown(self, tmp_path):
        """Script paths should be listed."""
        log_analysis = make_log_analysis(
            script_paths=["/home/master/process.sh", "/home/master/validate.pl"]
        )

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes={},
        )

        assert "Script paths" in context_pack
        assert "/home/master/process.sh" in context_pack
        assert "/home/master/validate.pl" in context_pack

    def test_io_paths_shown(self, tmp_path):
        """I/O paths should be listed."""
        log_analysis = make_log_analysis(
            io_paths=["/d/acbk/input/data.csv", "/d/acbk/output/report.afp"]
        )

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes={},
        )

        assert "Input/Output paths" in context_pack
        assert "/d/acbk/input/data.csv" in context_pack
        assert "/d/acbk/output/report.afp" in context_pack

    def test_no_files_message(self, tmp_path):
        """Should show message when no file references found."""
        log_analysis = make_log_analysis()

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes={},
        )

        assert "No file references extracted" in context_pack

    def test_docdef_mapped_to_snapshot(self, tmp_path):
        """DOCDEF tokens should be mapped to snapshot paths when found."""
        # Create docdef directory and file
        docdef_dir = tmp_path / "docdef"
        docdef_dir.mkdir()
        (docdef_dir / "bkfnds11.dfa").touch()

        log_analysis = make_log_analysis(docdef_tokens=["BKFNDS11"])

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes={},
        )

        assert "BKFNDS11" in context_pack
        assert "bkfnds11.dfa" in context_pack


class TestContextPackStructure:
    """Test overall context pack structure."""

    def test_all_sections_present(self, tmp_path):
        """All required sections should be present."""
        log_analysis = make_log_analysis(error_codes=["PPCS1001E"])

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes={},
        )

        required_sections = [
            "LSA CONTEXT PACK",
            "MOST LIKELY FAILING NODE",
            "EXECUTION CHAIN",
            "EVIDENCE",
            "PAPYRUS/DOCEXEC CODES",
            "FILES FROM LOG EVIDENCE",
            "TOP HYPOTHESES",
            "FILES TO OPEN",
            "SUGGESTED COMMANDS",
            "SIMILAR PAST CASES",
            "END OF CONTEXT PACK",
        ]

        for section in required_sections:
            assert section in context_pack, f"Missing section: {section}"

    def test_sections_in_order(self, tmp_path):
        """Sections should appear in expected order."""
        log_analysis = make_log_analysis(error_codes=["PPCS1001E"])

        context_pack = generate_context_pack(
            log_path=Path("/test/sample.log"),
            log_analysis=log_analysis,
            top_node=None,
            confidence=0.0,
            neighbors=None,
            hypotheses=[],
            similar_cases=[],
            related_files=[],
            snapshot_path=tmp_path,
            decoded_codes={},
        )

        # Check order of key sections
        positions = {
            "EVIDENCE": context_pack.find("3. EVIDENCE"),
            "CODES": context_pack.find("3b. PAPYRUS/DOCEXEC"),
            "FILES_LOG": context_pack.find("3c. FILES FROM LOG"),
            "HYPOTHESES": context_pack.find("4. TOP HYPOTHESES"),
        }

        assert positions["EVIDENCE"] < positions["CODES"]
        assert positions["CODES"] < positions["FILES_LOG"]
        assert positions["FILES_LOG"] < positions["HYPOTHESES"]
