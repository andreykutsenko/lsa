"""Hashing utilities for LSA."""

import hashlib
from pathlib import Path

from ..config import MAX_TEXT_SIZE, TEXT_EXTENSIONS, METADATA_ONLY_EXTENSIONS


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def is_text_file(file_path: Path) -> bool:
    """Check if file should be treated as text (for content storage)."""
    suffix = file_path.suffix.lower()

    # Explicit metadata-only extensions
    if suffix in METADATA_ONLY_EXTENSIONS:
        return False

    # Explicit text extensions
    if suffix in TEXT_EXTENSIONS:
        return True

    # No extension - check if it's small enough to probe
    if not suffix:
        return True  # Will be validated during read

    return False


def should_store_content(file_path: Path, size: int) -> bool:
    """Check if file content should be stored (text + size limit)."""
    if size > MAX_TEXT_SIZE:
        return False
    if not is_text_file(file_path):
        return False
    return True


def try_read_text(file_path: Path, max_size: int = MAX_TEXT_SIZE) -> str | None:
    """Try to read file as UTF-8 text. Returns None if not valid text."""
    try:
        size = file_path.stat().st_size
        if size > max_size:
            return None

        content = file_path.read_text(encoding="utf-8")
        return content
    except (UnicodeDecodeError, OSError):
        return None
