"""Hypothesis generation from log signals."""

import re
from dataclasses import dataclass, field

from ..parsers.log_parser import LogSignal, LogAnalysis


@dataclass
class Hypothesis:
    """A hypothesis about the root cause."""

    hypothesis: str
    evidence: str
    line_number: int
    confirm_steps: list[str]
    confidence: float = 0.8
    is_wrapper_noise: bool = False  # True if this is the isisdisk.sh wrapper message
    is_external_signal: bool = False  # True if from external signals (InfoTrac, API, etc.)
    external_signal_id: str | None = None  # ID of external signal rule


# External signal hypothesis templates and confirm steps
EXTERNAL_SIGNAL_HYPOTHESES = {
    "INFOTRAC_MISSING_MESSAGE_ID": {
        "hypothesis_template": "Message ID {message_id} not found in InfoTrac DB for service={service}. Likely configuration/Message Manager mapping issue (not Papyrus resource).",
        "confirm": [
            "Confirm message_id exists/mapped in InfoTrac for service (estmt/paper/print)",
            "Check whether message is paper-only vs estmt",
            "If expected behavior, treat as config expectation / non-bug",
            "Review InfoTrac DB: SELECT * FROM message_map WHERE message_id = {message_id}",
        ],
        "confidence": 0.95,  # High confidence - specific external config issue
    },
    "API_SUCCESS_FALSE_JSON": {
        "hypothesis_template": "External API returned success=false. Check API payload, configuration, or upstream service.",
        "confirm": [
            "Review full API response in log for error details",
            "Check API endpoint configuration and credentials",
            "Verify upstream service health and connectivity",
        ],
        "confidence": 0.85,
    },
    "API_ERROR_MESSAGE_JSON": {
        "hypothesis_template": "API returned error: {api_message}",
        "confirm": [
            "Review the error message for root cause",
            "Check API request payload for issues",
            "Verify API configuration and permissions",
        ],
        "confidence": 0.85,
    },
    "HTTP_ERROR_STATUS": {
        "hypothesis_template": "HTTP error {status_code} detected. Check network/API configuration.",
        "confirm": [
            "Verify target URL is correct and accessible",
            "Check authentication/authorization",
            "Review server-side logs for details",
        ],
        "confidence": 0.85,
    },
    "CONNECTION_REFUSED": {
        "hypothesis_template": "Connection refused to {host}. Service may be down or unreachable.",
        "confirm": [
            "Check if target service is running",
            "Verify network/firewall configuration",
            "Check service port and host configuration",
        ],
        "confidence": 0.90,
    },
    "CONNECTION_TIMEOUT": {
        "hypothesis_template": "Network connection or read timed out.",
        "confirm": [
            "Check network latency and connectivity",
            "Verify service responsiveness",
            "Review timeout configuration",
        ],
        "confidence": 0.85,
    },
    "DB_CONNECTION_ERROR": {
        "hypothesis_template": "Database connection error detected.",
        "confirm": [
            "Check database server status",
            "Verify connection string and credentials",
            "Review database server logs",
        ],
        "confidence": 0.90,
    },
    "AUTH_FAILURE": {
        "hypothesis_template": "Authentication/authorization failure detected.",
        "confirm": [
            "Check credentials and tokens",
            "Verify user permissions",
            "Review authentication configuration",
        ],
        "confidence": 0.85,
    },
    "SERVICE_UNAVAILABLE": {
        "hypothesis_template": "Service is temporarily unavailable.",
        "confirm": [
            "Check service health and status",
            "Review service deployment and load",
            "Check for scheduled maintenance",
        ],
        "confidence": 0.85,
    },
}


# Rules for hypothesis generation
HYPOTHESIS_RULES = [
    {
        "pattern": r"ORA-\d{5}",
        "hypothesis": "Database connection or query error (Oracle)",
        "confirm": [
            "Check Oracle listener status: lsnrctl status",
            "Verify TNS configuration in tnsnames.ora",
            "Check database logs for details",
        ],
        "confidence": 0.9,
    },
    {
        "pattern": r"PPDE\d{4}E",
        "hypothesis": "Document generation error (Papyrus DocExec)",
        "confirm": [
            "Check DOCDEF syntax in .dfa file",
            "Verify input data format matches expected",
            "Review variable declarations in docdef",
        ],
        "confidence": 0.85,
    },
    {
        "pattern": r"PPCS\d{4}E",
        "hypothesis": "Papyrus application/converter error",
        "confirm": [
            "Check application configuration",
            "Verify profile (.prf) file settings",
            "Review input file format",
        ],
        "confidence": 0.85,
    },
    {
        "pattern": r"failed to open|cannot open|No such file",
        "hypothesis": "Missing input file or permission issue",
        "confirm": [
            "Verify file exists at expected path",
            "Check file permissions (ls -la)",
            "Validate path in .ins configuration",
        ],
        "confidence": 0.9,
    },
    {
        "pattern": r"Permission denied",
        "hypothesis": "File or directory permission error",
        "confirm": [
            "Check file permissions: ls -la <path>",
            "Verify user has access to directory",
            "Check if file is locked by another process",
        ],
        "confidence": 0.95,
    },
    {
        "pattern": r"mismatch|do not match",
        "hypothesis": "Data validation or count mismatch",
        "confirm": [
            "Compare input vs output record counts",
            "Check for duplicate records in input",
            "Validate data format matches expected schema",
        ],
        "confidence": 0.8,
    },
    {
        "pattern": r"timeout|timed out",
        "hypothesis": "Operation timeout (network, database, or process)",
        "confirm": [
            "Check network connectivity",
            "Verify database is responding",
            "Review process resource usage",
        ],
        "confidence": 0.85,
    },
    {
        "pattern": r"missing file_id|missing operand",
        "hypothesis": "Missing required parameter or input",
        "confirm": [
            "Verify all required parameters are set in .ins file",
            "Check input file contains expected fields",
            "Review calling script for parameter passing",
        ],
        "confidence": 0.85,
    },
    {
        "pattern": r"Error line \d+ has",
        "hypothesis": "Data parsing error (CSV/input format)",
        "confirm": [
            "Check input file line N for malformed data",
            "Verify CSV quoting and escaping",
            "Compare with expected column count",
        ],
        "confidence": 0.9,
    },
    {
        "pattern": r"RC=\d+[^0]|status \[-\d+\]",
        "hypothesis": "Non-zero return code from subprocess",
        "confirm": [
            "Check logs from the failing subprocess",
            "Verify input files for subprocess exist",
            "Review subprocess configuration",
        ],
        "confidence": 0.75,
    },
    {
        "pattern": r"Generator returns a non-zero|Generator.*non-zero",
        "hypothesis": "Wrapper message from isisdisk.sh (often ignored per ops/Ya Mee)",
        "confirm": [
            "Check if there are other error codes (PP*E, ORA-*) in the same log",
            "Review preceding log lines for actual failure cause",
            "If no other errors present, this may be a false alarm",
            "Check DOCDEF and input files if Generator genuinely failed",
        ],
        "confidence": 0.4,  # Low confidence - wrapper noise
        "is_wrapper_noise": True,
    },
    {
        "pattern": r"^ERROR:|ERROR\s*:",
        "hypothesis": "Application error - review message for details",
        "confirm": [
            "Check the specific error message for root cause",
            "Review preceding log lines for context",
            "Verify input files and configuration",
        ],
        "confidence": 0.7,
    },
    {
        "pattern": r"CSV file.*is bad|CSV.*bad",
        "hypothesis": "Malformed CSV input file",
        "confirm": [
            "Check CSV file for encoding issues",
            "Verify quote/escape handling",
            "Compare column count with expected schema",
        ],
        "confidence": 0.9,
    },
    {
        "pattern": r"Failed in \w+",
        "hypothesis": "Script or process failed during execution",
        "confirm": [
            "Check the specific script mentioned in error",
            "Review script logs for details",
            "Verify input parameters and files",
        ],
        "confidence": 0.85,
    },
]


def _generate_external_signal_hypotheses(
    log_analysis: LogAnalysis | None,
) -> list[Hypothesis]:
    """Generate hypotheses from external signals."""
    if not log_analysis or not log_analysis.external_signals:
        return []

    hypotheses = []
    seen_signal_ids = set()

    # Get services for hypothesis text
    services = log_analysis.services_seen
    service_str = services[0] if services else "UNKNOWN"

    for ext_signal in log_analysis.external_signals:
        if ext_signal.id in seen_signal_ids:
            continue
        seen_signal_ids.add(ext_signal.id)

        # Get hypothesis config for this signal type
        hyp_config = EXTERNAL_SIGNAL_HYPOTHESES.get(ext_signal.id)

        if hyp_config:
            # Use template with captures
            template = hyp_config["hypothesis_template"]
            captures = dict(ext_signal.captures)
            captures["service"] = service_str  # Add service to captures

            try:
                hypothesis_text = template.format(**captures)
            except KeyError:
                # Missing capture, use template as-is
                hypothesis_text = template

            confirm_steps = []
            for step in hyp_config["confirm"]:
                try:
                    confirm_steps.append(step.format(**captures))
                except KeyError:
                    confirm_steps.append(step)

            confidence = hyp_config["confidence"]
        elif ext_signal.hypothesis_template:
            # Use template from rule
            try:
                hypothesis_text = ext_signal.hypothesis_template.format(
                    **ext_signal.captures, service=service_str
                )
            except KeyError:
                hypothesis_text = ext_signal.hypothesis_template

            confirm_steps = ext_signal.hints.copy()
            # Severity-based confidence
            confidence = {
                "F": 0.95,
                "E": 0.85,
                "W": 0.70,
                "I": 0.50,
            }.get(ext_signal.severity, 0.70)
        else:
            # Generic hypothesis from hints
            hypothesis_text = f"External signal: {ext_signal.id} ({ext_signal.category})"
            if ext_signal.hints:
                hypothesis_text = ext_signal.hints[0]
            confirm_steps = ext_signal.hints[1:] if len(ext_signal.hints) > 1 else []
            confidence = 0.75

        # Get evidence from first evidence line
        if ext_signal.evidence:
            ev = ext_signal.evidence[0]
            evidence = f"L{ev.line_no}: {ev.line_text}"
            if len(evidence) > 120:
                evidence = evidence[:120] + "..."
            line_number = ev.line_no
        else:
            evidence = f"External signal: {ext_signal.id}"
            line_number = 0

        hypotheses.append(Hypothesis(
            hypothesis=hypothesis_text,
            evidence=evidence,
            line_number=line_number,
            confirm_steps=confirm_steps,
            confidence=confidence,
            is_wrapper_noise=False,
            is_external_signal=True,
            external_signal_id=ext_signal.id,
        ))

    return hypotheses


def generate_hypotheses(
    signals: list[LogSignal],
    max_hypotheses: int = 3,
    log_analysis: LogAnalysis | None = None,
) -> list[Hypothesis]:
    """
    Generate ranked hypotheses based on log signals.

    Args:
        signals: List of log signals (typically error signals)
        max_hypotheses: Maximum number of hypotheses to return
        log_analysis: Optional LogAnalysis for wrapper noise and external signals

    Returns:
        List of Hypothesis objects, sorted by confidence
    """
    hypotheses = []
    seen_patterns = set()

    # FIRST: Generate hypotheses from external signals (highest priority)
    external_hypotheses = _generate_external_signal_hypotheses(log_analysis)
    hypotheses.extend(external_hypotheses)

    # Focus on error signals (F > E > W > I)
    fatal_signals = [s for s in signals if s.severity == "F"]
    error_signals = [s for s in signals if s.severity == "E"]
    if fatal_signals:
        error_signals = fatal_signals + error_signals
    if not error_signals:
        error_signals = signals  # Fall back to all signals

    # Track signals that matched wrapper noise (skip them for generic patterns)
    wrapper_noise_signals = set()

    for signal in error_signals:
        # First check if this is wrapper noise
        wrapper_rule = next((r for r in HYPOTHESIS_RULES if r.get("is_wrapper_noise")), None)
        if wrapper_rule and re.search(wrapper_rule["pattern"], signal.message, re.IGNORECASE):
            wrapper_noise_signals.add(signal.line_number)
            if wrapper_rule["pattern"] not in seen_patterns:
                seen_patterns.add(wrapper_rule["pattern"])
                evidence = signal.message
                if len(evidence) > 100:
                    evidence = evidence[:100] + "..."
                hypotheses.append(Hypothesis(
                    hypothesis=wrapper_rule["hypothesis"],
                    evidence=evidence,
                    line_number=signal.line_number,
                    confirm_steps=wrapper_rule["confirm"],
                    confidence=wrapper_rule["confidence"],
                    is_wrapper_noise=True,
                ))
            continue  # Skip other patterns for this signal

        # Check other patterns
        for rule in HYPOTHESIS_RULES:
            if rule.get("is_wrapper_noise"):
                continue  # Already handled above

            pattern = rule["pattern"]
            if pattern in seen_patterns:
                continue

            if re.search(pattern, signal.message, re.IGNORECASE):
                seen_patterns.add(pattern)

                # Truncate evidence for display
                evidence = signal.message
                if len(evidence) > 100:
                    evidence = evidence[:100] + "..."

                hypotheses.append(Hypothesis(
                    hypothesis=rule["hypothesis"],
                    evidence=evidence,
                    line_number=signal.line_number,
                    confirm_steps=rule["confirm"],
                    confidence=rule["confidence"],
                    is_wrapper_noise=False,
                ))

    # Sort by confidence (external signals and other high-confidence first)
    hypotheses.sort(key=lambda h: -h.confidence)

    # Handle wrapper noise ranking:
    # 1. External signals always outrank wrapper noise
    # 2. If no strong failure and wrapper noise is #1, demote it
    if hypotheses:
        has_strong_failure = log_analysis.has_strong_failure if log_analysis else False
        has_external_signals = any(h.is_external_signal for h in hypotheses)

        # If wrapper noise is #1 and there's no strong failure evidence
        # OR if there are external signals (which should be prioritized)
        if hypotheses[0].is_wrapper_noise:
            if has_external_signals or not has_strong_failure:
                # Demote wrapper noise
                wrapper = hypotheses[0]
                hypotheses = [h for h in hypotheses if not h.is_wrapper_noise]
                if hypotheses:
                    # Add wrapper at end as FYI
                    wrapper.hypothesis = (
                        "FYI: " + wrapper.hypothesis +
                        " (demoted - external config signal or no strong failure detected)"
                    )
                    wrapper.confidence = 0.2
                    hypotheses.append(wrapper)
                else:
                    # Only wrapper noise - add clarifying note
                    wrapper.hypothesis = (
                        "FYI: Wrapper message from isisdisk.sh (no strong failure detected; "
                        "often a false alarm per ops/Ya Mee)"
                    )
                    wrapper.confidence = 0.2
                    hypotheses = [wrapper]

    return hypotheses[:max_hypotheses]


def get_default_hypotheses() -> list[Hypothesis]:
    """Return default hypotheses when no specific patterns match."""
    return [
        Hypothesis(
            hypothesis="Unknown error - review log for details",
            evidence="No specific error pattern matched",
            line_number=0,
            confirm_steps=[
                "Search log for ERROR or FAIL keywords",
                "Check timestamps for sequence of events",
                "Review input/output files",
            ],
            confidence=0.5,
        )
    ]
