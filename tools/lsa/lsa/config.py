"""Configuration constants for LSA."""

from pathlib import Path

# Maximum file size for storing text_content (1MB)
MAX_TEXT_SIZE = 1024 * 1024

# Default directories to scan (excluding logs)
DEFAULT_SCAN_DIRS = ["procs", "master", "control", "insert", "docdef"]

# Directories for histories
HISTORIES_DIR = "histories"

# Database location relative to snapshot
DB_DIR = ".lsa"
DB_NAME = "lsa.sqlite"

# File extensions considered as text (for content storage)
TEXT_EXTENSIONS = {
    ".procs", ".sh", ".pl", ".py", ".control", ".ins",
    ".txt", ".md", ".cfg", ".conf", ".ini", ".sql",
    ".dfa", ".DFA",  # docdef files are text and should be searchable
}

# Extensions that are metadata-only (no text_content)
METADATA_ONLY_EXTENSIONS = {".afp", ".pdf", ".zip", ".pgp", ".log"}

# Similarity threshold for case_cards matching
SIMILARITY_THRESHOLD = 0.3

# Maximum lines in context pack output
MAX_CONTEXT_PACK_LINES = 200

# Maximum evidence snippet length (chars)
MAX_EVIDENCE_SNIPPET = 120


def get_db_path(snapshot_path: Path) -> Path:
    """Get path to SQLite database for a snapshot."""
    return snapshot_path / DB_DIR / DB_NAME
