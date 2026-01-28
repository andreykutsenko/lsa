"""Parser for log files."""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from . import patterns


@dataclass
class LogSignal:
    """A signal extracted from a log line."""

    line_number: int
    message: str
    timestamp: str | None = None
    code: str | None = None
    severity: str = "I"  # I=Info, W=Warning, E=Error
    source_file: str | None = None
    source_line: int | None = None
    docdef_ref: str | None = None
    script_ref: str | None = None
    script_line: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class LogAnalysis:
    """Analysis results from a log file."""

    path: str
    total_lines: int
    signals: list[LogSignal] = field(default_factory=list)
    error_signals: list[LogSignal] = field(default_factory=list)
    warning_signals: list[LogSignal] = field(default_factory=list)
    fatal_signals: list[LogSignal] = field(default_factory=list)  # F-severity codes
    error_codes: list[str] = field(default_factory=list)
    docdef_refs: list[str] = field(default_factory=list)
    script_refs: list[str] = field(default_factory=list)
    # New fields for improved matching
    prefix_tokens: list[str] = field(default_factory=list)  # $PREFIX=xxx values
    script_paths: list[str] = field(default_factory=list)   # /home/master/*.sh paths
    jid_tokens: list[str] = field(default_factory=list)     # $JID=xxx values
    docdef_tokens: list[str] = field(default_factory=list)  # BKFNDS11, ACBKDS21, etc.
    io_paths: list[str] = field(default_factory=list)       # input=/d/xxx, output=/d/yyy paths
    # Wrapper noise detection
    has_wrapper_noise: bool = False  # "ERROR: Generator returns a non-zero value"
    has_strong_failure: bool = False  # aborted, ORA-xxxxx, missing file, etc.
    # External signals (from rules-based extraction)
    external_signals: list = field(default_factory=list)  # list[ExternalSignal]
    # Convenience fields derived from external signals
    infotrac_missing_message_ids: list[str] = field(default_factory=list)
    services_seen: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(
            {
                "path": self.path,
                "total_lines": self.total_lines,
                "error_count": len(self.error_signals),
                "warning_count": len(self.warning_signals),
                "error_codes": self.error_codes,
                "docdef_refs": self.docdef_refs,
                "script_refs": self.script_refs,
                "top_errors": [s.to_dict() for s in self.error_signals[:10]],
            },
            ensure_ascii=False,
        )


def parse_log_line(line: str, line_number: int) -> LogSignal | None:
    """
    Parse a single log line and extract signal.

    Returns None for noise lines (empty, "is still alive", etc.)
    """
    line = line.strip()

    # Skip noise lines
    if not line:
        return None
    if "is still alive" in line:
        return None
    if "is no longer alive" in line:
        return None

    signal = LogSignal(line_number=line_number, message=line)

    # Extract timestamp
    ts_match = patterns.LOG_TIMESTAMP.search(line)
    if ts_match:
        signal.timestamp = ts_match.group(1)

    # Extract PP* codes (Papyrus) and AFPR codes
    code_match = patterns.MESSAGE_CODE_PATTERN.search(line)
    if not code_match:
        code_match = patterns.LOG_PP_CODE.search(line)
    if code_match:
        signal.code = code_match.group(1)
        signal.severity = signal.code[-1]  # Last char is I/W/E/F

    # Extract ORA- codes (Oracle errors)
    ora_match = patterns.LOG_ORA_CODE.search(line)
    if ora_match:
        signal.code = ora_match.group(1)
        signal.severity = "E"

    # Extract source file reference
    src_match = patterns.LOG_SOURCE_REF.search(line)
    if src_match:
        signal.source_file = src_match.group(1)
        signal.source_line = int(src_match.group(2))

    # Extract DOCDEF reference
    docdef_match = patterns.LOG_DOCDEF_REF.search(line)
    if docdef_match:
        signal.docdef_ref = docdef_match.group(1)

    # Extract script:line reference (Perl/shell errors)
    script_match = patterns.LOG_SCRIPT_LINE_REF.search(line)
    if script_match:
        signal.script_ref = script_match.group(1)
        signal.script_line = int(script_match.group(2))

    # Check for error keywords (upgrade severity if found)
    if patterns.LOG_ERROR_KEYWORDS.search(line):
        if signal.severity != "E":
            signal.severity = "E"

    return signal


def parse_log_file(file_path: Path) -> LogAnalysis:
    """
    Parse a log file and extract all signals.

    Args:
        file_path: Path to the log file

    Returns:
        LogAnalysis with all extracted signals and summary
    """
    analysis = LogAnalysis(path=str(file_path), total_lines=0)

    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        analysis.signals.append(
            LogSignal(line_number=0, message=f"Error reading file: {e}", severity="E")
        )
        return analysis

    lines = text.splitlines()
    analysis.total_lines = len(lines)

    error_codes = set()
    docdef_refs = set()
    script_refs = set()
    prefix_tokens = set()
    script_paths = set()
    jid_tokens = set()
    docdef_tokens = set()
    io_paths = set()
    has_wrapper_noise = False
    has_strong_failure = False

    for line_num, line in enumerate(lines, 1):
        signal = parse_log_line(line, line_num)
        if signal is None:
            continue

        analysis.signals.append(signal)

        if signal.severity == "F":
            analysis.fatal_signals.append(signal)
            analysis.error_signals.append(signal)  # F is also an error
        elif signal.severity == "E":
            analysis.error_signals.append(signal)
        elif signal.severity == "W":
            analysis.warning_signals.append(signal)

        if signal.code:
            error_codes.add(signal.code)
        if signal.docdef_ref:
            docdef_refs.add(signal.docdef_ref)
        if signal.script_ref:
            script_refs.add(signal.script_ref)

        # Extract PREFIX= tokens (strong signal for proc matching)
        for match in patterns.LOG_PREFIX_TOKEN.finditer(line):
            prefix_tokens.add(match.group(1).lower())

        # Extract JID= tokens
        for match in patterns.LOG_JID_TOKEN.finditer(line):
            jid_tokens.add(match.group(1).lower())

        # Extract script paths (/home/master/*.sh)
        for match in patterns.LOG_SCRIPT_PATH.finditer(line):
            script_paths.add(match.group(1))

        # Extract docdef from docdef= parameter
        for match in patterns.LOG_DOCDEF_PARAM.finditer(line):
            docdef_refs.add(match.group(1).upper())

        # Extract DOCDEF tokens (e.g., BKFNDS11, ACBKDS21)
        for match in patterns.LOG_DOCDEF_TOKEN.finditer(line):
            docdef_tokens.add(match.group(1).upper())

        # Extract input/output paths
        for match in patterns.LOG_IO_PATH.finditer(line):
            io_paths.add(match.group(1))

        # Check for wrapper noise
        if patterns.WRAPPER_NOISE_PATTERN.search(line):
            has_wrapper_noise = True

        # Check for strong failure indicators
        if not has_strong_failure:
            for pattern in patterns.STRONG_FAILURE_PATTERNS:
                if pattern.search(line):
                    has_strong_failure = True
                    break

    analysis.error_codes = sorted(error_codes)
    analysis.docdef_refs = sorted(docdef_refs)
    analysis.script_refs = sorted(script_refs)
    analysis.prefix_tokens = sorted(prefix_tokens)
    analysis.script_paths = sorted(script_paths)
    analysis.jid_tokens = sorted(jid_tokens)
    analysis.docdef_tokens = sorted(docdef_tokens)
    analysis.io_paths = sorted(io_paths)
    analysis.has_wrapper_noise = has_wrapper_noise
    analysis.has_strong_failure = has_strong_failure

    # Extract external signals (rules-based)
    try:
        from ..analysis.external_signals import (
            extract_external_signals,
            extract_services_from_text,
            get_infotrac_missing_ids,
        )
        analysis.external_signals = extract_external_signals(text)
        analysis.infotrac_missing_message_ids = get_infotrac_missing_ids(
            analysis.external_signals
        )
        analysis.services_seen = extract_services_from_text(text)

        # External signals with F severity also count as strong failure
        if not analysis.has_strong_failure:
            for ext_sig in analysis.external_signals:
                if ext_sig.severity == "F":
                    analysis.has_strong_failure = True
                    break
    except Exception:
        # External signals extraction failed; continue without it
        pass

    return analysis


def extract_cid_from_log_path(log_path: Path) -> str | None:
    """
    Try to extract CID from log file path.

    Examples:
        /d/acbk/acbkds1/sample/acbkds1.log -> acbk
        /d/daily/aabkdn1/aabkdn1.log -> aabk
    """
    import re

    path_str = str(log_path).lower()

    # Try /d/{cid}/ pattern
    match = re.search(r"/d/(\w{4})/", path_str)
    if match:
        return match.group(1)

    # Try /d/daily/{cid}dn1/ pattern
    match = re.search(r"/d/daily/(\w{4})dn\d/", path_str)
    if match:
        return match.group(1)

    # Try extracting from filename
    stem = log_path.stem.lower()
    if len(stem) >= 4:
        # First 4 chars often are CID
        candidate = stem[:4]
        if candidate.isalnum():
            return candidate

    return None


def extract_proc_name_from_log_path(log_path: Path) -> str | None:
    """
    Try to extract proc name from log file path.

    Examples:
        /d/acbk/acbkds1/sample/acbkds1.log -> acbkds1
        /d/daily/aabkdn1/aabkdn1.log -> aabkdn1
        bkfnds1122.c1bmcok.fgnrs.log -> bkfnds1122
    """
    stem = log_path.stem.lower()

    # Handle multi-extension filenames: take first part before any dot
    if '.' in stem:
        stem = stem.split('.')[0]

    # Remove common suffixes (repeat until no more matches)
    suffixes = ["_process", "_msg", "_portal", "_timestamp", "_count"]
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                changed = True
                break

    return stem if stem else None


def extract_base_proc_name(name: str) -> str | None:
    """
    Extract base proc name by stripping cycle/segment numbers.

    Examples:
        bkfnds1122 -> bkfnds1
        acbkds1 -> acbkds1
        bkfncl1122 -> bkfncl1
    """
    import re
    # Pattern: base name (cid + type + number) + optional cycle digits
    # e.g., bkfnds1 + 122, acbkcl1 + 22
    match = re.match(r'^(\w{4}[a-z]{2}\d)(\d{2,})?$', name)
    if match:
        return match.group(1)
    return name
