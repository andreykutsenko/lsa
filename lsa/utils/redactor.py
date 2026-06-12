"""PII redaction utilities for LSA."""

import re


def _is_timestamp_like(token: str) -> bool:
    """True for YYYYMMDD / YYYYMMDDHHMMSS tokens that look like real dates."""
    if len(token) not in (8, 14):
        return False
    year, month, day = int(token[0:4]), int(token[4:6]), int(token[6:8])
    if not (1970 <= year <= 2099 and 1 <= month <= 12 and 1 <= day <= 31):
        return False
    if len(token) == 14:
        hour, minute, second = int(token[8:10]), int(token[10:12]), int(token[12:14])
        if hour > 23 or minute > 59 or second > 59:
            return False
    return True


def _redact_account(match: re.Match) -> str:
    # Log timestamps (20260114123456) fall in the 8-16 digit range; redacting
    # them destroys case-card utility, so date-like tokens are kept as-is.
    token = match.group(0)
    return token if _is_timestamp_like(token) else "[ACCT]"


# Patterns for common PII
PII_PATTERNS = [
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
    # Phone numbers (various formats)
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    # SSN patterns
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # Account numbers (common patterns - 8+ digits)
    (re.compile(r"\b\d{8,16}\b"), _redact_account),
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
