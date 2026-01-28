"""Tests for external signals extraction."""

import pytest

from lsa.analysis.external_signals import (
    extract_external_signals,
    extract_services_from_text,
    get_infotrac_missing_ids,
    ExternalSignal,
    get_rules,
    reload_rules,
)
from lsa.analysis.hypotheses import generate_hypotheses, Hypothesis
from lsa.parsers.log_parser import LogSignal, LogAnalysis


class TestExternalSignalsExtraction:
    """Test external signals extraction from log text."""

    SAMPLE_LOG_WITH_INFOTRAC = """
2026-01-23 10:15:32.123 INFO Starting document generation
2026-01-23 10:15:33.456 DEBUG Processing message_id=197131
2026-01-23 10:15:34.789 ERROR No data found from message_id: 197131 in infotrac db
2026-01-23 10:15:35.012 WARN Continuing with fallback
2026-01-23 10:15:36.345 INFO Process completed
"""

    SAMPLE_LOG_WITH_API_ERROR = """
2026-01-23 11:20:00.000 INFO Calling external API
2026-01-23 11:20:01.000 DEBUG Response: {"success": false, "message": "Resource not available"}
2026-01-23 11:20:02.000 ERROR API call failed
"""

    def test_detects_infotrac_missing_message_id(self):
        """Should detect INFOTRAC_MISSING_MESSAGE_ID signal."""
        signals = extract_external_signals(self.SAMPLE_LOG_WITH_INFOTRAC)

        infotrac_signals = [s for s in signals if s.id == "INFOTRAC_MISSING_MESSAGE_ID"]
        assert len(infotrac_signals) == 1

        signal = infotrac_signals[0]
        assert signal.severity == "F"
        assert signal.category == "CONFIG"
        assert signal.captures.get("message_id") == "197131"

    def test_captures_evidence_with_line_number(self):
        """Should capture evidence with correct line number."""
        signals = extract_external_signals(self.SAMPLE_LOG_WITH_INFOTRAC)

        infotrac_signals = [s for s in signals if s.id == "INFOTRAC_MISSING_MESSAGE_ID"]
        assert len(infotrac_signals) == 1

        signal = infotrac_signals[0]
        assert len(signal.evidence) >= 1

        # Line 4 contains "No data found from message_id"
        evidence = signal.evidence[0]
        assert evidence.line_no == 4
        assert "message_id: 197131" in evidence.line_text

    def test_detects_api_success_false(self):
        """Should detect API_SUCCESS_FALSE_JSON signal."""
        signals = extract_external_signals(self.SAMPLE_LOG_WITH_API_ERROR)

        api_signals = [s for s in signals if s.id == "API_SUCCESS_FALSE_JSON"]
        assert len(api_signals) == 1

        signal = api_signals[0]
        assert signal.severity == "E"
        assert signal.category == "EXTERNAL_API"

    def test_detects_api_error_message(self):
        """Should detect API_ERROR_MESSAGE_JSON signal with message capture."""
        signals = extract_external_signals(self.SAMPLE_LOG_WITH_API_ERROR)

        msg_signals = [s for s in signals if s.id == "API_ERROR_MESSAGE_JSON"]
        assert len(msg_signals) == 1

        signal = msg_signals[0]
        assert signal.captures.get("api_message") == "Resource not available"

    def test_deduplicates_same_signal(self):
        """Should deduplicate signals with same id and captures."""
        log_text = """
Line 1: No data found from message_id: 12345 in infotrac db
Line 2: No data found from message_id: 12345 in infotrac db
Line 3: No data found from message_id: 12345 in infotrac db
"""
        signals = extract_external_signals(log_text)

        infotrac_signals = [s for s in signals if s.id == "INFOTRAC_MISSING_MESSAGE_ID"]
        assert len(infotrac_signals) == 1

        # But should have multiple evidence lines
        assert len(infotrac_signals[0].evidence) == 3

    def test_different_message_ids_create_separate_signals(self):
        """Different message_ids should create separate signals."""
        log_text = """
Line 1: No data found from message_id: 111 in infotrac db
Line 2: No data found from message_id: 222 in infotrac db
"""
        signals = extract_external_signals(log_text)

        infotrac_signals = [s for s in signals if s.id == "INFOTRAC_MISSING_MESSAGE_ID"]
        assert len(infotrac_signals) == 2

        ids = {s.captures.get("message_id") for s in infotrac_signals}
        assert ids == {"111", "222"}

    def test_no_signals_in_clean_log(self):
        """Should return empty list for log with no external signals."""
        log_text = """
2026-01-23 10:00:00 INFO Application started
2026-01-23 10:00:01 INFO Processing complete
"""
        signals = extract_external_signals(log_text)
        assert len(signals) == 0

    def test_signals_sorted_by_severity(self):
        """Signals should be sorted by severity (F > E > W > I)."""
        log_text = """
{"success": false}
No data found from message_id: 123 in infotrac db
"""
        signals = extract_external_signals(log_text)

        # INFOTRAC (F) should be before API_SUCCESS_FALSE (E)
        severities = [s.severity for s in signals]
        assert severities[0] == "F"


class TestServiceExtraction:
    """Test service extraction from log text."""

    def test_extracts_service_from_query_param(self):
        """Should extract service from services=xxx query param."""
        log_text = """
GET /api/documents?services=estmt&format=pdf HTTP/1.1
Processing request for services=paper|print
"""
        services = extract_services_from_text(log_text)

        assert "estmt" in services
        assert "paper" in services
        assert "print" in services

    def test_extracts_service_from_path(self):
        """Should extract service from /services/xxx/ path."""
        log_text = """
POST /services/archival/upload HTTP/1.1
GET /service/estmt/status HTTP/1.1
"""
        services = extract_services_from_text(log_text)

        assert "archival" in services
        assert "estmt" in services

    def test_extracts_service_from_json(self):
        """Should extract service from JSON keys."""
        log_text = """
{"service": "estmt", "action": "generate"}
{"service_type": "paper", "status": "ready"}
"""
        services = extract_services_from_text(log_text)

        assert "estmt" in services
        assert "paper" in services

    def test_returns_empty_for_no_services(self):
        """Should return empty list when no services found."""
        log_text = "Just some random log text without service mentions"
        services = extract_services_from_text(log_text)
        assert services == []


class TestInfotracMissingIds:
    """Test extraction of missing InfoTrac message IDs."""

    def test_gets_infotrac_missing_ids(self):
        """Should extract missing message IDs from signals."""
        log_text = """
No data found from message_id: 111 in infotrac db
No data found from message_id: 222 in infotrac db
"""
        signals = extract_external_signals(log_text)
        ids = get_infotrac_missing_ids(signals)

        assert "111" in ids
        assert "222" in ids
        assert len(ids) == 2

    def test_returns_empty_when_no_infotrac_signals(self):
        """Should return empty list when no InfoTrac signals."""
        signals = [
            ExternalSignal(
                id="API_SUCCESS_FALSE_JSON",
                severity="E",
                category="EXTERNAL_API",
            )
        ]
        ids = get_infotrac_missing_ids(signals)
        assert ids == []


class TestHypothesesRankingWithExternalSignals:
    """Test that external signals properly outrank wrapper noise."""

    def make_log_analysis(
        self,
        has_wrapper_noise: bool = False,
        has_strong_failure: bool = False,
        external_signals: list | None = None,
        services_seen: list | None = None,
    ) -> LogAnalysis:
        """Create a mock LogAnalysis."""
        return LogAnalysis(
            path="/test/log.log",
            total_lines=100,
            has_wrapper_noise=has_wrapper_noise,
            has_strong_failure=has_strong_failure,
            external_signals=external_signals or [],
            services_seen=services_seen or [],
            infotrac_missing_message_ids=[],
        )

    def make_signal(self, message: str, line_number: int = 1, severity: str = "E") -> LogSignal:
        """Create a LogSignal for testing."""
        return LogSignal(
            line_number=line_number,
            message=message,
            severity=severity,
        )

    def test_infotrac_outranks_wrapper_noise(self):
        """INFOTRAC signal should outrank wrapper noise hypothesis."""
        # Create external signal for InfoTrac
        infotrac_signal = ExternalSignal(
            id="INFOTRAC_MISSING_MESSAGE_ID",
            severity="F",
            category="CONFIG",
            captures={"message_id": "197131"},
            evidence=[],
        )

        log_analysis = self.make_log_analysis(
            has_wrapper_noise=True,
            has_strong_failure=True,  # InfoTrac is strong failure
            external_signals=[infotrac_signal],
            services_seen=["estmt"],
        )

        signals = [
            self.make_signal("ERROR:  Generator returns a non-zero value"),
        ]

        hypotheses = generate_hypotheses(signals, max_hypotheses=5, log_analysis=log_analysis)

        assert len(hypotheses) >= 1
        # First hypothesis should be external signal (InfoTrac), not wrapper noise
        assert hypotheses[0].is_external_signal or not hypotheses[0].is_wrapper_noise
        if hypotheses[0].is_external_signal:
            assert hypotheses[0].external_signal_id == "INFOTRAC_MISSING_MESSAGE_ID"

    def test_wrapper_noise_demoted_with_external_signals(self):
        """Wrapper noise should be demoted when external signals present."""
        api_signal = ExternalSignal(
            id="API_SUCCESS_FALSE_JSON",
            severity="E",
            category="EXTERNAL_API",
            captures={},
            evidence=[],
        )

        log_analysis = self.make_log_analysis(
            has_wrapper_noise=True,
            has_strong_failure=True,
            external_signals=[api_signal],
        )

        signals = [
            self.make_signal("ERROR:  Generator returns a non-zero value"),
        ]

        hypotheses = generate_hypotheses(signals, max_hypotheses=5, log_analysis=log_analysis)

        # Find wrapper noise hypothesis if it exists
        wrapper_hypotheses = [h for h in hypotheses if h.is_wrapper_noise]

        if wrapper_hypotheses:
            # Wrapper should NOT be first
            assert hypotheses[0] != wrapper_hypotheses[0]
            # Wrapper should have FYI prefix if demoted
            assert "FYI" in wrapper_hypotheses[0].hypothesis or wrapper_hypotheses[0].confidence < 0.5

    def test_external_signal_hypothesis_contains_message_id(self):
        """External signal hypothesis should contain the captured message_id."""
        infotrac_signal = ExternalSignal(
            id="INFOTRAC_MISSING_MESSAGE_ID",
            severity="F",
            category="CONFIG",
            captures={"message_id": "197131"},
            evidence=[],
        )

        log_analysis = self.make_log_analysis(
            external_signals=[infotrac_signal],
            services_seen=["estmt"],
        )

        hypotheses = generate_hypotheses([], max_hypotheses=5, log_analysis=log_analysis)

        assert len(hypotheses) >= 1
        first_hyp = hypotheses[0]
        assert "197131" in first_hyp.hypothesis
        assert first_hyp.is_external_signal


class TestContextPackExternalSignals:
    """Test that context pack includes external signals section."""

    def test_context_pack_includes_external_signals_section(self, tmp_path):
        """Context pack should include EXTERNAL CONFIG SIGNALS section."""
        from lsa.output.context_pack import generate_context_pack
        from pathlib import Path

        infotrac_signal = ExternalSignal(
            id="INFOTRAC_MISSING_MESSAGE_ID",
            severity="F",
            category="CONFIG",
            captures={"message_id": "197131"},
            evidence=[],
        )
        infotrac_signal.evidence.append(
            type(infotrac_signal).evidence.default_factory()[0].__class__(
                line_no=10,
                line_text="No data found from message_id: 197131 in infotrac db"
            ) if False else None
        )
        # Manually add evidence
        from lsa.analysis.external_signals import ExternalSignalEvidence
        infotrac_signal.evidence = [
            ExternalSignalEvidence(
                line_no=10,
                line_text="No data found from message_id: 197131 in infotrac db"
            )
        ]

        log_analysis = LogAnalysis(
            path="/test/log.log",
            total_lines=100,
            external_signals=[infotrac_signal],
            services_seen=["estmt"],
            infotrac_missing_message_ids=["197131"],
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

        assert "EXTERNAL CONFIG SIGNALS" in context_pack
        assert "INFOTRAC_MISSING_MESSAGE_ID" in context_pack
        assert "197131" in context_pack
        assert "estmt" in context_pack

    def test_context_pack_shows_none_when_no_signals(self, tmp_path):
        """Context pack should show 'None found' when no external signals."""
        from lsa.output.context_pack import generate_context_pack
        from pathlib import Path

        log_analysis = LogAnalysis(
            path="/test/log.log",
            total_lines=100,
            external_signals=[],
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

        assert "EXTERNAL CONFIG SIGNALS" in context_pack
        assert "None found" in context_pack


class TestRulesLoading:
    """Test YAML rules loading."""

    def test_rules_load_successfully(self):
        """Rules should load from YAML file."""
        reload_rules()  # Force fresh load
        rules = get_rules()

        assert len(rules) > 0

        # Check INFOTRAC rule exists
        infotrac_rules = [r for r in rules if r.id == "INFOTRAC_MISSING_MESSAGE_ID"]
        assert len(infotrac_rules) == 1
        assert infotrac_rules[0].severity == "F"
        assert infotrac_rules[0].category == "CONFIG"

    def test_rules_have_compiled_patterns(self):
        """Rules should have compiled regex patterns."""
        rules = get_rules()

        for rule in rules:
            assert len(rule.patterns) > 0
            # Each pattern should be a compiled regex
            for pattern in rule.patterns:
                assert hasattr(pattern, 'search')
