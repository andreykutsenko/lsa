"""Tests for wrapper noise (isisdisk.sh) classification."""

import pytest
from unittest.mock import MagicMock

from lsa.parsers.log_parser import LogSignal, LogAnalysis
from lsa.analysis.hypotheses import generate_hypotheses, Hypothesis


def make_log_analysis(
    has_wrapper_noise: bool = False,
    has_strong_failure: bool = False,
) -> LogAnalysis:
    """Create a mock LogAnalysis with specified flags."""
    return LogAnalysis(
        path="/test/log.log",
        total_lines=100,
        has_wrapper_noise=has_wrapper_noise,
        has_strong_failure=has_strong_failure,
    )


def make_signal(message: str, line_number: int = 1, severity: str = "E") -> LogSignal:
    """Create a LogSignal for testing."""
    return LogSignal(
        line_number=line_number,
        message=message,
        severity=severity,
    )


class TestWrapperNoiseClassification:
    """Test wrapper noise detection and handling."""

    def test_wrapper_noise_alone_not_top_hypothesis(self):
        """Wrapper noise alone should not be #1 hypothesis."""
        signals = [
            make_signal("ERROR:  Generator returns a non-zero value"),
        ]
        log_analysis = make_log_analysis(has_wrapper_noise=True, has_strong_failure=False)

        hypotheses = generate_hypotheses(signals, log_analysis=log_analysis)

        assert len(hypotheses) >= 1
        # First hypothesis should mention it's FYI/wrapper noise
        assert hypotheses[0].is_wrapper_noise or "FYI" in hypotheses[0].hypothesis or "wrapper" in hypotheses[0].hypothesis.lower()
        # Confidence should be low
        assert hypotheses[0].confidence < 0.5

    def test_wrapper_noise_with_strong_failure_is_valid(self):
        """Wrapper noise with strong failure evidence is a valid signal."""
        signals = [
            make_signal("PPDE3001E - Document generation failed"),
            make_signal("ERROR:  Generator returns a non-zero value"),
        ]
        log_analysis = make_log_analysis(has_wrapper_noise=True, has_strong_failure=True)

        hypotheses = generate_hypotheses(signals, log_analysis=log_analysis)

        assert len(hypotheses) >= 1
        # First hypothesis should NOT be wrapper noise when strong failure present
        # (it should be the PPDE error)
        assert not hypotheses[0].is_wrapper_noise

    def test_wrapper_noise_demoted_when_other_errors_present(self):
        """Wrapper noise should be demoted when other errors are present."""
        signals = [
            make_signal("ERROR:  Generator returns a non-zero value"),
            make_signal("ORA-12170 TNS connection timeout"),
        ]
        log_analysis = make_log_analysis(has_wrapper_noise=True, has_strong_failure=True)

        hypotheses = generate_hypotheses(signals, log_analysis=log_analysis)

        # Find positions
        wrapper_positions = [i for i, h in enumerate(hypotheses) if h.is_wrapper_noise]
        oracle_positions = [i for i, h in enumerate(hypotheses) if "Oracle" in h.hypothesis or "ORA-" in h.evidence]

        # Oracle error should be before wrapper noise
        if wrapper_positions and oracle_positions:
            assert min(oracle_positions) < min(wrapper_positions)

    def test_no_wrapper_noise_returns_normal_hypotheses(self):
        """Without wrapper noise, hypotheses should be generated normally."""
        signals = [
            make_signal("Permission denied: /home/data/input.csv"),
        ]
        log_analysis = make_log_analysis(has_wrapper_noise=False, has_strong_failure=True)

        hypotheses = generate_hypotheses(signals, log_analysis=log_analysis)

        assert len(hypotheses) >= 1
        assert not hypotheses[0].is_wrapper_noise
        assert "Permission" in hypotheses[0].hypothesis or "permission" in hypotheses[0].hypothesis.lower()


class TestWrapperNoisePattern:
    """Test the wrapper noise pattern detection."""

    def test_pattern_matches_exact(self):
        """Test exact wrapper noise message."""
        from lsa.parsers import patterns

        line = "ERROR:  Generator returns a non-zero value"
        assert patterns.WRAPPER_NOISE_PATTERN.search(line)

    def test_pattern_matches_variations(self):
        """Test variations of wrapper noise message."""
        from lsa.parsers import patterns

        # Different spacing
        assert patterns.WRAPPER_NOISE_PATTERN.search("ERROR: Generator returns a non-zero value")
        # Case insensitive
        assert patterns.WRAPPER_NOISE_PATTERN.search("error:  generator returns a non-zero value")

    def test_pattern_no_match_similar(self):
        """Test that similar but different messages don't match."""
        from lsa.parsers import patterns

        # Different text
        assert not patterns.WRAPPER_NOISE_PATTERN.search("Generator process completed")
        assert not patterns.WRAPPER_NOISE_PATTERN.search("ERROR: Connection timeout")


class TestStrongFailurePatterns:
    """Test strong failure indicator patterns."""

    def test_ora_error_is_strong_failure(self):
        """ORA-xxxxx should be detected as strong failure."""
        from lsa.parsers import patterns

        line = "ORA-12170: TNS connection timeout"
        for pattern in patterns.STRONG_FAILURE_PATTERNS:
            if pattern.search(line):
                return  # Found, test passes

        pytest.fail("ORA error should match strong failure pattern")

    def test_aborted_is_strong_failure(self):
        """'aborted' should be detected as strong failure."""
        from lsa.parsers import patterns

        line = "Process aborted due to error"
        for pattern in patterns.STRONG_FAILURE_PATTERNS:
            if pattern.search(line):
                return

        pytest.fail("'aborted' should match strong failure pattern")

    def test_permission_denied_is_strong_failure(self):
        """'Permission denied' should be detected as strong failure."""
        from lsa.parsers import patterns

        line = "Permission denied: /home/data/file.csv"
        for pattern in patterns.STRONG_FAILURE_PATTERNS:
            if pattern.search(line):
                return

        pytest.fail("'Permission denied' should match strong failure pattern")

    def test_missing_file_is_strong_failure(self):
        """'missing file' and 'No such file' should be strong failures."""
        from lsa.parsers import patterns

        lines = [
            "Error: missing input file",
            "No such file or directory",
            "cannot open /data/file.csv",
            "failed to open input",
        ]

        for line in lines:
            found = False
            for pattern in patterns.STRONG_FAILURE_PATTERNS:
                if pattern.search(line):
                    found = True
                    break
            if not found:
                pytest.fail(f"'{line}' should match strong failure pattern")
