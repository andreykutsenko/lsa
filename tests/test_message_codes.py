"""Tests for message code extraction and severity parsing."""

import pytest
import re

from lsa.parsers import patterns
from lsa.parsers.pdf_parser import (
    parse_message_codes_from_text,
    extract_severity_from_code,
    MessageCodeEntry,
)


class TestMessageCodePattern:
    """Test message code regex patterns."""

    def test_ppcs_codes(self):
        """Test PPCS code pattern matching."""
        assert patterns.MESSAGE_CODE_PATTERN.search("PPCS1234I")
        assert patterns.MESSAGE_CODE_PATTERN.search("PPCS5678E")
        assert patterns.MESSAGE_CODE_PATTERN.search("PPCS9999W")
        assert patterns.MESSAGE_CODE_PATTERN.search("PPCS0001F")

    def test_ppde_codes(self):
        """Test PPDE code pattern matching."""
        assert patterns.MESSAGE_CODE_PATTERN.search("PPDE1001I")
        assert patterns.MESSAGE_CODE_PATTERN.search("PPDE2345E")
        assert patterns.MESSAGE_CODE_PATTERN.search("PPDE9999F")

    def test_ppco_codes(self):
        """Test PPCO code pattern matching."""
        assert patterns.MESSAGE_CODE_PATTERN.search("PPCO1234I")
        assert patterns.MESSAGE_CODE_PATTERN.search("PPCO5678W")

    def test_afpr_codes(self):
        """Test AFPR code pattern matching."""
        assert patterns.MESSAGE_CODE_PATTERN.search("AFPR1234I")
        assert patterns.MESSAGE_CODE_PATTERN.search("AFPR5678E")
        assert patterns.MESSAGE_CODE_PATTERN.search("AFPR9999F")

    def test_extract_from_log_line(self):
        """Test extracting codes from realistic log lines."""
        line = "2026-01-23/09:20:43.527  PPDE1001I Starting document generation"
        match = patterns.MESSAGE_CODE_PATTERN.search(line)
        assert match
        assert match.group(1) == "PPDE1001I"

    def test_no_match_invalid_codes(self):
        """Test that invalid codes don't match."""
        assert not patterns.MESSAGE_CODE_PATTERN.search("PPXX1234I")  # Invalid prefix
        assert not patterns.MESSAGE_CODE_PATTERN.search("PPCS12I")    # Too few digits
        assert not patterns.MESSAGE_CODE_PATTERN.search("PPCS12345I") # Too many digits
        assert not patterns.MESSAGE_CODE_PATTERN.search("PPCS1234X")  # Invalid severity


class TestSeverityExtraction:
    """Test severity extraction from message codes."""

    def test_info_severity(self):
        assert extract_severity_from_code("PPCS1234I") == "I"

    def test_warning_severity(self):
        assert extract_severity_from_code("PPDE5678W") == "W"

    def test_error_severity(self):
        assert extract_severity_from_code("PPCO9999E") == "E"

    def test_fatal_severity(self):
        assert extract_severity_from_code("AFPR1234F") == "F"

    def test_empty_code(self):
        assert extract_severity_from_code("") == "I"

    def test_lowercase(self):
        # Should handle lowercase (normalized to uppercase)
        assert extract_severity_from_code("ppcs1234e") == "E"


class TestParseMessageCodesFromText:
    """Test parsing message codes from PDF-like text."""

    SAMPLE_PDF_TEXT = """
    Papyrus/DocExec Message Codes Reference

    PPCS1001I - Application started successfully
    The application has been initialized and is ready to process documents.

    PPCS2001W - Configuration file not found
    Reason: The specified configuration file could not be located.
    Solution: Verify the path to the configuration file and ensure it exists.

    PPDE3001E - Document generation failed
    The document could not be generated due to an error in the template.
    Reason: Invalid variable reference in DOCDEF.
    Solution: Check the DOCDEF file for undefined variables.

    AFPR4001F - Fatal resource error
    A critical error occurred while loading AFP resources.
    The application will terminate.
    """

    def test_extracts_multiple_codes(self):
        """Test that multiple codes are extracted."""
        entries = parse_message_codes_from_text(self.SAMPLE_PDF_TEXT)
        codes = [e.code for e in entries]
        assert "PPCS1001I" in codes
        assert "PPCS2001W" in codes
        assert "PPDE3001E" in codes
        assert "AFPR4001F" in codes

    def test_severity_extracted_correctly(self):
        """Test that severity is extracted from code postfix."""
        entries = parse_message_codes_from_text(self.SAMPLE_PDF_TEXT)
        by_code = {e.code: e for e in entries}

        assert by_code["PPCS1001I"].severity == "I"
        assert by_code["PPCS2001W"].severity == "W"
        assert by_code["PPDE3001E"].severity == "E"
        assert by_code["AFPR4001F"].severity == "F"

    def test_body_contains_description(self):
        """Test that body contains nearby description text."""
        entries = parse_message_codes_from_text(self.SAMPLE_PDF_TEXT)
        by_code = {e.code: e for e in entries}

        # Check PPCS1001I has its description
        assert "initialized" in by_code["PPCS1001I"].body.lower() or \
               "started" in by_code["PPCS1001I"].body.lower()

    def test_extracts_reason_solution(self):
        """Test that Reason/Solution sections are extracted."""
        entries = parse_message_codes_from_text(self.SAMPLE_PDF_TEXT)
        by_code = {e.code: e for e in entries}

        # PPCS2001W should have Reason/Solution
        body = by_code["PPCS2001W"].body
        assert "Reason:" in body or "configuration" in body.lower()

    def test_handles_empty_text(self):
        """Test handling of empty input."""
        entries = parse_message_codes_from_text("")
        assert entries == []

    def test_handles_no_codes(self):
        """Test handling of text with no message codes."""
        entries = parse_message_codes_from_text("Just some random text without any codes.")
        assert entries == []

    def test_deduplicates_codes(self):
        """Test that duplicate codes are deduplicated."""
        text = """
        PPCS1001I - First occurrence
        Some text here
        PPCS1001I - Second occurrence
        More text
        """
        entries = parse_message_codes_from_text(text)
        codes = [e.code for e in entries]
        assert codes.count("PPCS1001I") == 1


class TestMessageCodeEntry:
    """Test MessageCodeEntry dataclass."""

    def test_severity_name_info(self):
        entry = MessageCodeEntry(code="PPCS1001I", severity="I", title=None, body="test")
        assert entry.severity_name == "Info"

    def test_severity_name_warning(self):
        entry = MessageCodeEntry(code="PPCS1001W", severity="W", title=None, body="test")
        assert entry.severity_name == "Warning"

    def test_severity_name_error(self):
        entry = MessageCodeEntry(code="PPCS1001E", severity="E", title=None, body="test")
        assert entry.severity_name == "Error"

    def test_severity_name_fatal(self):
        entry = MessageCodeEntry(code="PPCS1001F", severity="F", title=None, body="test")
        assert entry.severity_name == "Fatal"


class TestDefinitionVsCrossReference:
    """Test that parser correctly distinguishes definitions from cross-references."""

    SAMPLE_TEXT_WITH_CROSSREF = """
248/392

Papyrus Objects Process Control System Messages

Some informational text here.

This message is preceded by: PPCS1037F

More text about something else.

PPCS1037F osProcessCreate(...) failed
The operating system call to create a child process failed.
Reason:
The operating system was unable to create the requested process.
Solution:
Check that system resources are available and that the process
configuration is correct.

PPCS1038I Another message
Description of another message.
"""

    def test_chooses_definition_over_crossref(self):
        """Parser should choose the definition (start of line) not the cross-reference."""
        entries = parse_message_codes_from_text(self.SAMPLE_TEXT_WITH_CROSSREF)

        # Find PPCS1037F entry
        ppcs1037f = None
        for entry in entries:
            if entry.code == "PPCS1037F":
                ppcs1037f = entry
                break

        assert ppcs1037f is not None, "PPCS1037F should be extracted"

        # Body should contain the actual definition, not "preceded by"
        assert "osProcessCreate" in ppcs1037f.body, \
            f"Body should contain 'osProcessCreate', got: {ppcs1037f.body}"
        assert "Reason:" in ppcs1037f.body, \
            f"Body should contain 'Reason:', got: {ppcs1037f.body}"
        assert "preceded by" not in ppcs1037f.body.lower(), \
            f"Body should NOT contain 'preceded by', got: {ppcs1037f.body}"

    def test_filters_noise_lines(self):
        """Parser should filter out header/footer noise lines."""
        entries = parse_message_codes_from_text(self.SAMPLE_TEXT_WITH_CROSSREF)

        for entry in entries:
            # Should not contain page numbers or document headers
            assert "248/392" not in entry.body
            assert "Papyrus Objects Process Control System Messages" not in entry.body

    def test_extracts_reason_solution(self):
        """Parser should extract Reason/Solution sections."""
        entries = parse_message_codes_from_text(self.SAMPLE_TEXT_WITH_CROSSREF)

        ppcs1037f = next((e for e in entries if e.code == "PPCS1037F"), None)
        assert ppcs1037f is not None

        assert "Reason:" in ppcs1037f.body
        assert "Solution:" in ppcs1037f.body

    def test_code_inside_sentence_not_definition(self):
        """Code mentioned inside a sentence should not be treated as definition."""
        # Text where code only appears inside sentences, never at start of line
        text = """
Some header text.

This error is related to PPCS9999F which indicates a problem.

See also PPCS9999F for more information.

The PPCS9999F code means something.
"""
        entries = parse_message_codes_from_text(text)

        # PPCS9999F should NOT be extracted because it never appears at start of line
        codes = [e.code for e in entries]
        assert "PPCS9999F" not in codes, \
            "Code inside sentence should not be extracted as definition"

    def test_code_at_start_of_line_is_definition(self):
        """Code at start of line (with optional whitespace) is a definition."""
        text = """
Some header text.

PPCS8888E First error at column 0
Description of error.

   PPCS7777W Indented error with leading spaces
Another description.
"""
        entries = parse_message_codes_from_text(text)
        codes = [e.code for e in entries]

        assert "PPCS8888E" in codes, "Code at column 0 should be extracted"
        assert "PPCS7777W" in codes, "Code with leading whitespace should be extracted"

    def test_multiple_definitions_picks_best(self):
        """When same code has multiple definitions, pick the one with Reason/Solution."""
        text = """
PPCS5555I Simple mention
Just some text here.

PPCS5555I Full definition with details
The complete explanation of what this means.
Reason:
This happens when X occurs.
Solution:
Do Y to fix it.
"""
        entries = parse_message_codes_from_text(text)

        ppcs5555i = next((e for e in entries if e.code == "PPCS5555I"), None)
        assert ppcs5555i is not None

        # Should pick the one with Reason/Solution (higher score)
        assert "Reason:" in ppcs5555i.body, \
            f"Should pick definition with Reason/Solution, got: {ppcs5555i.body}"
