"""Compiled regex patterns for parsing."""

import re

# =============================================================================
# .procs file patterns
# =============================================================================

# Header metadata
PROCS_FIRM = re.compile(r"^Firm:\s*(.+?)(?:\s{2,}|$)", re.MULTILINE)
PROCS_CID = re.compile(r"^CID\s*:\s*(\w+)", re.MULTILINE)
PROCS_APP_TYPE = re.compile(
    r"(?:Application Type|Production Type):\s*(.+?)(?:\s{2,}|$)", re.MULTILINE
)
PROCS_JOB_ID = re.compile(r"Job ID:\s*(\S+)", re.MULTILINE)
PROCS_LR = re.compile(r"LR:\s*(\S+)", re.MULTILINE)

# Processing fields (with __ prefix)
PROCS_SHELL_SCRIPT = re.compile(
    r"__(?:Processing\s+)?Shell Script:\s*(/\S+)", re.MULTILINE | re.IGNORECASE
)
PROCS_LOG_FILE = re.compile(r"__Log File:\s*(/\S+)", re.MULTILINE | re.IGNORECASE)
PROCS_FILE_SETUP = re.compile(
    r"__File Setup Before Processing:\s*(/\S+)", re.MULTILINE | re.IGNORECASE
)

# File references
PROCS_PRINT_FILES = re.compile(r"Print files?:\s*(/\S+)", re.MULTILINE | re.IGNORECASE)
PROCS_INPUT_LOCATION = re.compile(
    r"File Location:\s*(/\S+)", re.MULTILINE | re.IGNORECASE
)

# Cross-references to other .procs files
PROCS_CROSSREF = re.compile(
    r"refer to\s+(/home/procs/\w+\.procs)", re.IGNORECASE
)

# Absolute paths (general)
ABSOLUTE_PATH = re.compile(r"(/(?:home|d|z|download|ftpbu)/[^\s,;\"'<>()]+)")

# =============================================================================
# Log file patterns
# =============================================================================

# Timestamp: 2026-01-23/09:20:43.527
LOG_TIMESTAMP = re.compile(r"(\d{4}-\d{2}-\d{2}/\d{2}:\d{2}:\d{2}\.\d{3})")

# Papyrus codes: PPCS8005I, PPDE1001I, PPST9912I, PPCO9803I
# Also AFPR codes from AFP Resource: AFPR1234E
LOG_PP_CODE = re.compile(r"(PP(?:CS|DE|ST|CO)\d{4}[IWEF])")

# Extended message code pattern for all known prefixes (for KB extraction)
# Includes: PPCS, PPDE, PPST, PPCO, AFPR, PPAP, PPDG, PPTP, etc.
MESSAGE_CODE_PATTERN = re.compile(r"((?:PP(?:CS|DE|ST|CO|AP|DG|TP|WM|FP|EM)|AFPR)\d{4}[IWEF])")

# Oracle errors: ORA-12170
LOG_ORA_CODE = re.compile(r"(ORA-\d{5})")

# Source file reference: [pcsdll/pcs.cpp,567]
LOG_SOURCE_REF = re.compile(r"\[([^,\]]+\.cpp),(\d+)\]")

# DOCDEF reference: DOCDEF 'ACBKDS11'
LOG_DOCDEF_REF = re.compile(r"DOCDEF '(\w+)'")

# Error keywords
LOG_ERROR_KEYWORDS = re.compile(
    r"\b(ERROR|FAIL|failed|FAILED|exception|mismatch|missing|abort|aborted)\b",
    re.IGNORECASE,
)

# File:line reference in Perl/shell errors: foo.pl line 266
LOG_SCRIPT_LINE_REF = re.compile(r"(\w+\.(?:pl|sh|py))\s+line\s+(\d+)", re.IGNORECASE)

# PREFIX= token in Papyrus logs: $PREFIX=acbkds1
LOG_PREFIX_TOKEN = re.compile(r"\$PREFIX=(\w+)")

# JID= token: $JID=ds1
LOG_JID_TOKEN = re.compile(r"\$JID=(\w+)")

# Script paths in logs: /home/master/foo.sh, /home/insert/bar.ins
LOG_SCRIPT_PATH = re.compile(r"(/home/(?:master|insert|util)/[\w\-\.]+\.(?:sh|pl|py|ins))")

# docdef= parameter: docdef=ACBKDS11
LOG_DOCDEF_PARAM = re.compile(r"docdef=(\w+)", re.IGNORECASE)

# input/output paths in logs
LOG_IO_PATH = re.compile(r"(?:input|output|profile)=([^\s]+)", re.IGNORECASE)

# DOCDEF token pattern (e.g., BKFNDS11, BKFNDS21, ACBKDS11)
# These are 4-letter CID + 2-letter type + 2 digits
LOG_DOCDEF_TOKEN = re.compile(r"\b([A-Z]{4}[A-Z]{2}\d{2})\b")

# Wrapper noise pattern from isisdisk.sh
WRAPPER_NOISE_PATTERN = re.compile(r"ERROR:\s*Generator returns a non-zero value", re.IGNORECASE)

# Strong failure indicators (to distinguish from wrapper noise)
STRONG_FAILURE_PATTERNS = [
    re.compile(r"aborted", re.IGNORECASE),
    re.compile(r"not generated", re.IGNORECASE),
    re.compile(r"ORA-\d{5}"),  # Oracle errors
    re.compile(r"missing\s+(?:input|file|docdef)", re.IGNORECASE),
    re.compile(r"Permission denied", re.IGNORECASE),
    re.compile(r"No such file", re.IGNORECASE),
    re.compile(r"cannot open", re.IGNORECASE),
    re.compile(r"failed to open", re.IGNORECASE),
    re.compile(r"[IWEF]\d{4}F\b"),  # Any Fatal (F) code
]

# =============================================================================
# History file patterns
# =============================================================================

# Session delimiters (SpecStory format)
HISTORY_SESSION_START = re.compile(
    r"^<(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}Z-[^>]+\.md)>$"
)
HISTORY_SESSION_END = re.compile(
    r"^</(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}Z-[^>]+\.md)>$"
)

# User/Assistant markers
HISTORY_USER_TURN = re.compile(r"^_\*\*User\*\*_$")
HISTORY_ASSISTANT_TURN = re.compile(r"^_\*\*Assistant\*\*_$")

# Markdown headers (for chunking)
HISTORY_HEADER = re.compile(r"^#+\s+.+$")

# Code block markers
HISTORY_CODE_BLOCK = re.compile(r"^```")

# =============================================================================
# Error signature patterns (for case_cards extraction)
# =============================================================================

ERROR_SIGNATURES = [
    # Oracle errors
    re.compile(r"ORA-\d{5}"),
    # Common error phrases
    re.compile(r"missing file_id", re.IGNORECASE),
    re.compile(r"Permission denied", re.IGNORECASE),
    re.compile(r"No such file", re.IGNORECASE),
    re.compile(r"timeout", re.IGNORECASE),
    re.compile(r"Total number of accounts do not match", re.IGNORECASE),
    # CSV/data errors
    re.compile(r"Error line \d+ has", re.IGNORECASE),
    re.compile(r"CSV file .+ is bad", re.IGNORECASE),
    # Papyrus errors (E or F severity)
    re.compile(r"PP[A-Z]{2}\d{4}[EF]"),
    # AFP Resource errors
    re.compile(r"AFPR\d{4}[EF]"),
    # Generic error patterns
    re.compile(r"Failed in \w+", re.IGNORECASE),
    re.compile(r"Error within program", re.IGNORECASE),
]

# Shell command patterns (for verify_commands extraction)
SHELL_COMMANDS = re.compile(
    r"^\s*(grep|cat|find|ls|cd|sqlplus|perl|bash|sh|wc|head|tail|awk|sed)\s+.+$",
    re.MULTILINE,
)

# File path pattern (for related_files extraction)
FILE_PATH_PATTERN = re.compile(
    r"(/[a-zA-Z0-9_/\-\.]+\.(?:pl|sh|procs|dfa|control|ins|csv|txt|sql|py))"
)
