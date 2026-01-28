"""Parser for Cursor history files (robust heuristics, no strict delimiters)."""

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from . import patterns
from ..utils.redactor import redact_if_enabled


def compute_chunk_hash(text: str) -> str:
    """Compute SHA256 hash of chunk content for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass
class CaseCard:
    """A case card extracted from history."""

    source_path: str | None = None
    chunk_id: int = 0
    content_hash: str | None = None
    title: str | None = None
    signals: list[str] = field(default_factory=list)
    root_cause: str | None = None
    fix_summary: str | None = None
    verify_commands: list[str] = field(default_factory=list)
    related_files: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_json_fields(self) -> dict:
        """Get JSON-serializable fields."""
        return {
            "signals_json": json.dumps(self.signals, ensure_ascii=False) if self.signals else None,
            "verify_commands_json": json.dumps(self.verify_commands, ensure_ascii=False) if self.verify_commands else None,
            "related_files_json": json.dumps(self.related_files, ensure_ascii=False) if self.related_files else None,
            "tags_json": json.dumps(self.tags, ensure_ascii=False) if self.tags else None,
        }


def extract_error_signatures(text: str) -> list[str]:
    """Extract error signatures from text using predefined patterns."""
    signatures = []
    seen = set()

    for pattern in patterns.ERROR_SIGNATURES:
        for match in pattern.finditer(text):
            sig = match.group(0)
            if sig not in seen:
                seen.add(sig)
                signatures.append(sig)

    return signatures


def extract_shell_commands(text: str) -> list[str]:
    """Extract shell command lines from text."""
    commands = []
    seen = set()

    for match in patterns.SHELL_COMMANDS.finditer(text):
        cmd = match.group(0).strip()
        # Limit command length
        if len(cmd) > 200:
            cmd = cmd[:200] + "..."
        if cmd not in seen:
            seen.add(cmd)
            commands.append(cmd)

    return commands[:10]  # Limit to 10 commands


def extract_file_paths(text: str) -> list[str]:
    """Extract file paths from text."""
    paths = []
    seen = set()

    for match in patterns.FILE_PATH_PATTERN.finditer(text):
        path = match.group(1)
        # Clean up path
        path = path.rstrip(".,;:)]}")
        if path not in seen and len(path) > 5:
            seen.add(path)
            paths.append(path)

    return paths[:20]  # Limit to 20 paths


def extract_title_from_chunk(text: str) -> str | None:
    """Try to extract a title from chunk text."""
    lines = text.strip().split("\n")

    # Look for markdown header
    for line in lines[:5]:
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title:
                return title[:100]  # Limit length

    # Look for first non-empty line that looks like a title
    for line in lines[:3]:
        line = line.strip()
        if line and len(line) < 100 and not line.startswith(("```", "---", "_**")):
            return line

    return None


def split_into_chunks(text: str) -> list[tuple[int, str]]:
    """
    Split text into chunks using robust heuristics.

    Returns list of (chunk_id, chunk_text) tuples.
    """
    chunks = []
    current_chunk = []
    current_start = 0
    blank_count = 0
    in_code_block = False

    lines = text.split("\n")

    for i, line in enumerate(lines):
        # Track code blocks to avoid splitting inside them
        if line.strip().startswith("```"):
            in_code_block = not in_code_block

        # Detect chunk boundaries
        is_boundary = False

        if not in_code_block:
            # SpecStory session delimiter
            if patterns.HISTORY_SESSION_START.match(line) or patterns.HISTORY_SESSION_END.match(line):
                is_boundary = True
            # User/Assistant markers
            elif patterns.HISTORY_USER_TURN.match(line) or patterns.HISTORY_ASSISTANT_TURN.match(line):
                is_boundary = True
            # Major markdown header (# or ##)
            elif line.startswith("# ") or line.startswith("## "):
                is_boundary = True
            # Multiple blank lines
            elif not line.strip():
                blank_count += 1
                if blank_count >= 3:
                    is_boundary = True
            else:
                blank_count = 0

        if is_boundary and current_chunk:
            chunk_text = "\n".join(current_chunk)
            if chunk_text.strip():
                chunks.append((current_start, chunk_text))
            current_chunk = []
            current_start = i
            blank_count = 0

        current_chunk.append(line)

    # Don't forget last chunk
    if current_chunk:
        chunk_text = "\n".join(current_chunk)
        if chunk_text.strip():
            chunks.append((current_start, chunk_text))

    return chunks


def parse_chunk_to_case_card(
    chunk_text: str,
    chunk_id: int,
    source_path: str | None,
    redact: bool = False,
) -> CaseCard | None:
    """
    Parse a text chunk into a CaseCard.

    Returns None if chunk has no useful signals.
    """
    # Apply redaction if enabled
    text = redact_if_enabled(chunk_text, redact)

    # Extract signals
    signals = extract_error_signatures(text)
    commands = extract_shell_commands(text)
    files = extract_file_paths(text)

    # Skip chunks with no useful content
    if not signals and not commands and not files:
        return None

    # Compute content hash for deduplication
    content_hash = compute_chunk_hash(text)

    card = CaseCard(
        source_path=source_path,
        chunk_id=chunk_id,
        content_hash=content_hash,
        title=extract_title_from_chunk(text),
        signals=signals,
        verify_commands=commands,
        related_files=files,
    )

    # Try to extract root cause (look for specific patterns)
    root_cause_patterns = [
        r"(?:root cause|причина|problem|проблема)[:\s]+(.+?)(?:\n|$)",
        r"(?:because|потому что)[:\s]+(.+?)(?:\n|$)",
    ]
    for pattern in root_cause_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            card.root_cause = match.group(1).strip()[:200]
            break

    # Try to extract fix summary
    fix_patterns = [
        r"(?:fix|решение|solution)[:\s]+(.+?)(?:\n|$)",
        r"(?:changed|изменил|added|добавил)[:\s]+(.+?)(?:\n|$)",
    ]
    for pattern in fix_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            card.fix_summary = match.group(1).strip()[:200]
            break

    # Extract tags based on content
    tags = []
    if any("ORA-" in s for s in signals):
        tags.append("oracle")
    if any(".pl" in f for f in files):
        tags.append("perl")
    if any(".sh" in f for f in files):
        tags.append("shell")
    if any(".dfa" in f for f in files):
        tags.append("docdef")
    if any("csv" in s.lower() for s in signals):
        tags.append("csv")
    card.tags = tags

    return card


def parse_history_file(
    file_path: Path,
    redact: bool = False,
) -> list[CaseCard]:
    """
    Parse a history file into case cards.

    Uses robust heuristics to split content into chunks and extract
    useful information without requiring strict delimiters.

    Args:
        file_path: Path to history file
        redact: Whether to redact PII from stored content

    Returns:
        List of CaseCard objects
    """
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    source_path = str(file_path)
    chunks = split_into_chunks(text)
    cards = []

    for chunk_id, chunk_text in chunks:
        card = parse_chunk_to_case_card(chunk_text, chunk_id, source_path, redact)
        if card:
            cards.append(card)

    return cards


def parse_history_directory(
    dir_path: Path,
    redact: bool = False,
    glob_pattern: str | None = None,
) -> list[CaseCard]:
    """
    Parse history files in a directory.

    Args:
        dir_path: Path to histories directory
        redact: Whether to redact PII
        glob_pattern: Optional glob pattern (e.g., "*.md", "**/*.txt")
                      If None, defaults to "*.txt" and "*.md"

    Returns:
        List of all CaseCard objects
    """
    all_cards = []

    if not dir_path.exists():
        return all_cards

    if glob_pattern:
        # Use provided glob pattern
        for file_path in dir_path.glob(glob_pattern):
            if file_path.is_file():
                cards = parse_history_file(file_path, redact)
                all_cards.extend(cards)
    else:
        # Default: *.txt and *.md
        for file_path in dir_path.glob("*.txt"):
            cards = parse_history_file(file_path, redact)
            all_cards.extend(cards)

        for file_path in dir_path.glob("*.md"):
            cards = parse_history_file(file_path, redact)
            all_cards.extend(cards)

    return all_cards


def parse_history_files(
    file_paths: list[Path],
    redact: bool = False,
) -> list[CaseCard]:
    """
    Parse multiple history files.

    Args:
        file_paths: List of paths to history files
        redact: Whether to redact PII

    Returns:
        List of all CaseCard objects
    """
    all_cards = []

    for file_path in file_paths:
        if file_path.is_file():
            cards = parse_history_file(file_path, redact)
            all_cards.extend(cards)

    return all_cards
