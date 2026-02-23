"""Parser for .procs files."""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from . import patterns


@dataclass
class ProcsData:
    """Structured data extracted from a .procs file."""

    # Header metadata
    firm: str = "unknown"
    cid: str = "unknown"
    app_type: str = "unknown"
    job_id: str | None = None
    lr: str | None = None

    # Processing fields
    shell_script: str | None = None
    shell_script_line: int | None = None
    log_file: str | None = None
    log_file_line: int | None = None
    file_setup: str | None = None
    file_setup_line: int | None = None

    # File references
    print_files: list[str] = field(default_factory=list)
    input_location: str | None = None

    # Cross-references
    cross_refs: list[str] = field(default_factory=list)

    # All extracted paths
    all_paths: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ProcsData":
        """Deserialize from JSON."""
        data = json.loads(json_str)
        return cls(**data)


def _find_line_number(text: str, match_start: int) -> int:
    """Find line number for a regex match position."""
    return text[:match_start].count("\n") + 1


def parse_procs_file(file_path: Path) -> ProcsData:
    """
    Parse a .procs file and extract structured data.

    Args:
        file_path: Path to the .procs file

    Returns:
        ProcsData with extracted fields
    """
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ProcsData()

    data = ProcsData()

    # Extract header fields
    match = patterns.PROCS_FIRM.search(text)
    if match:
        data.firm = match.group(1).strip()

    match = patterns.PROCS_CID.search(text)
    if match:
        data.cid = match.group(1).strip().lower()

    match = patterns.PROCS_APP_TYPE.search(text)
    if match:
        data.app_type = match.group(1).strip()

    match = patterns.PROCS_JOB_ID.search(text)
    if match:
        data.job_id = match.group(1).strip()

    match = patterns.PROCS_LR.search(text)
    if match:
        data.lr = match.group(1).strip()

    # Extract processing fields with line numbers
    match = patterns.PROCS_SHELL_SCRIPT.search(text)
    if match:
        data.shell_script = match.group(1).strip()
        data.shell_script_line = _find_line_number(text, match.start())

    match = patterns.PROCS_LOG_FILE.search(text)
    if match:
        data.log_file = match.group(1).strip()
        data.log_file_line = _find_line_number(text, match.start())

    match = patterns.PROCS_FILE_SETUP.search(text)
    if match:
        data.file_setup = match.group(1).strip()
        data.file_setup_line = _find_line_number(text, match.start())

    # Extract print files (can be multiple)
    for match in patterns.PROCS_PRINT_FILES.finditer(text):
        path = match.group(1).strip()
        if path not in data.print_files:
            data.print_files.append(path)

    # Extract input location
    match = patterns.PROCS_INPUT_LOCATION.search(text)
    if match:
        data.input_location = match.group(1).strip()

    # Extract cross-references to other .procs files
    for match in patterns.PROCS_CROSSREF.finditer(text):
        ref = match.group(1).strip()
        if ref not in data.cross_refs:
            data.cross_refs.append(ref)

    # Extract all absolute paths
    seen_paths = set()
    for match in patterns.ABSOLUTE_PATH.finditer(text):
        path = match.group(1).strip().rstrip(".,;:)]}")
        if path not in seen_paths and len(path) > 5:
            seen_paths.add(path)
            data.all_paths.append(path)

    return data
