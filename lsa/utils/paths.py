"""Path normalization utilities for LSA."""

import re
from pathlib import Path

# Common unix path prefixes that map to snapshot directories
PATH_MAPPINGS = [
    (re.compile(r"^/home/procs/"), "procs/"),
    (re.compile(r"^/home/master/"), "master/"),
    (re.compile(r"^/home/control/"), "control/"),
    (re.compile(r"^/home/insert/"), "insert/"),
    (re.compile(r"^/home/docdef/"), "docdef/"),
    (re.compile(r"^/home/util/"), "master/"),  # util often maps to master
    # Generic /home/ paths
    (re.compile(r"^/home/([^/]+)/"), r"\1/"),
]


def normalize_path(path: str) -> str:
    """Normalize a path to canonical form (lowercase, forward slashes)."""
    return path.replace("\\", "/").lower().strip()


def map_unix_to_snapshot(
    unix_path: str, snapshot_path: Path
) -> tuple[Path | None, float]:
    """
    Map a unix path from log/procs to snapshot path.

    Returns:
        (canonical_path, confidence) where canonical_path is None if no mapping found.
    """
    normalized = normalize_path(unix_path)

    # Try direct mappings
    for pattern, replacement in PATH_MAPPINGS:
        if pattern.match(normalized):
            relative = pattern.sub(replacement, normalized)
            candidate = snapshot_path / relative
            if candidate.exists():
                return candidate, 1.0
            # Try case-insensitive match
            candidate_ci = find_case_insensitive(snapshot_path, relative)
            if candidate_ci:
                return candidate_ci, 0.9

    # Extract filename and search in known directories
    filename = Path(normalized).name
    if filename:
        for subdir in ["procs", "master", "control", "insert", "docdef"]:
            subdir_path = snapshot_path / subdir
            if subdir_path.exists():
                matches = list(subdir_path.rglob(filename))
                if len(matches) == 1:
                    return matches[0], 0.7
                elif len(matches) > 1:
                    # Multiple matches - return first with lower confidence
                    return matches[0], 0.5

    return None, 0.0


def find_case_insensitive(base: Path, relative: str) -> Path | None:
    """Find a file with case-insensitive matching."""
    parts = relative.split("/")
    current = base

    for part in parts:
        if not part:
            continue
        if not current.exists():
            return None

        # Try exact match first
        candidate = current / part
        if candidate.exists():
            current = candidate
            continue

        # Try case-insensitive
        part_lower = part.lower()
        found = None
        try:
            for child in current.iterdir():
                if child.name.lower() == part_lower:
                    found = child
                    break
        except PermissionError:
            return None

        if found:
            current = found
        else:
            return None

    return current if current != base else None


def extract_paths_from_text(text: str) -> list[str]:
    """Extract absolute unix paths from text."""
    # Match paths starting with /home/, /d/, /z/, etc.
    pattern = r"(/(?:home|d|z|download|ftpbu|backup|afp2web)/[^\s,;\"'<>()]+)"
    matches = re.findall(pattern, text)
    # Clean up trailing punctuation
    cleaned = []
    for m in matches:
        m = m.rstrip(".,;:)]}")
        if len(m) > 5:  # Skip very short matches
            cleaned.append(m)
    return list(set(cleaned))
