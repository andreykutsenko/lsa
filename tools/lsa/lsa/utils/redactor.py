"""PII redaction utilities for LSA."""

import re

# Patterns for common PII
PII_PATTERNS = [
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
    # Phone numbers (various formats)
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    # SSN patterns
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # Account numbers (common patterns - 8+ digits)
    (re.compile(r"\b\d{8,16}\b"), "[ACCT]"),
]


def redact_pii(text: str) -> str:
    """Redact common PII patterns from text."""
    result = text
    for pattern, replacement in PII_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_if_enabled(text: str, enabled: bool) -> str:
    """Conditionally redact PII."""
    if enabled:
        return redact_pii(text)
    return text
