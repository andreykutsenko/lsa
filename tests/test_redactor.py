"""Tests for PII redaction, including timestamp preservation."""

from lsa.utils.redactor import redact_pii


def test_account_numbers_still_redacted():
    assert redact_pii("acct 12345678 here") == "acct [ACCT] here"
    assert redact_pii("card 9876543210123456") == "card [ACCT]"


def test_date_and_timestamp_tokens_preserved():
    assert redact_pii("run 20260114 ok") == "run 20260114 ok"
    assert redact_pii("ts=20260114123456") == "ts=20260114123456"


def test_invalid_date_like_tokens_redacted():
    assert redact_pii("x 20261301 y") == "x [ACCT] y"  # month 13
    assert redact_pii("x 20260114256099 y") == "x [ACCT] y"  # hour 25


def test_email_and_ssn_unaffected():
    assert redact_pii("mail a@b.com ssn 123-45-6789") == "mail [EMAIL] ssn [SSN]"
