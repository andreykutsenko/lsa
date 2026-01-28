"""Case similarity scoring for LSA."""

import json
import sqlite3
from dataclasses import dataclass

from ..config import SIMILARITY_THRESHOLD


@dataclass
class SimilarCase:
    """A similar case from case_cards."""

    case_id: int
    title: str | None
    match_score: float
    matching_signals: list[str]
    root_cause: str | None
    fix_summary: str | None
    verify_commands: list[str]


def find_similar_cases(
    conn: sqlite3.Connection,
    signals: list[str],
    related_files: list[str] | None = None,
    limit: int = 3,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[SimilarCase]:
    """
    Find similar cases from case_cards based on error signals.

    Args:
        conn: Database connection
        signals: List of error codes/patterns from current log
        related_files: Optional list of file paths
        limit: Maximum number of cases to return
        threshold: Minimum match score threshold

    Returns:
        List of SimilarCase objects, sorted by match_score
    """
    if not signals:
        return []

    signal_set = set(s.lower() for s in signals)
    file_set = set(f.lower() for f in (related_files or []))

    similar = []

    # Query all case_cards
    rows = conn.execute(
        "SELECT * FROM case_cards WHERE signals_json IS NOT NULL"
    ).fetchall()

    for row in rows:
        card = dict(row)

        # Parse signals from case_card
        try:
            card_signals = json.loads(card["signals_json"] or "[]")
        except json.JSONDecodeError:
            continue

        card_signal_set = set(s.lower() for s in card_signals)

        # Compute signal overlap
        signal_overlap = signal_set & card_signal_set
        if not signal_overlap:
            continue

        # Base score from signal overlap
        score = len(signal_overlap) / max(len(signal_set), len(card_signal_set))

        # Boost for file overlap
        if file_set:
            try:
                card_files = json.loads(card["related_files_json"] or "[]")
                card_file_set = set(f.lower() for f in card_files)
                file_overlap = file_set & card_file_set
                if file_overlap:
                    score = min(1.0, score + 0.2 * len(file_overlap))
            except json.JSONDecodeError:
                pass

        if score < threshold:
            continue

        # Parse verify commands
        try:
            verify_commands = json.loads(card["verify_commands_json"] or "[]")
        except json.JSONDecodeError:
            verify_commands = []

        similar.append(SimilarCase(
            case_id=card["id"],
            title=card["title"],
            match_score=score,
            matching_signals=list(signal_overlap),
            root_cause=card["root_cause"],
            fix_summary=card["fix_summary"],
            verify_commands=verify_commands[:3],  # Limit commands
        ))

    # Sort by score and return top N
    similar.sort(key=lambda c: -c.match_score)
    return similar[:limit]


def compute_signal_similarity(signals1: list[str], signals2: list[str]) -> float:
    """
    Compute Jaccard similarity between two signal sets.

    Returns value between 0 and 1.
    """
    if not signals1 or not signals2:
        return 0.0

    set1 = set(s.lower() for s in signals1)
    set2 = set(s.lower() for s in signals2)

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    return intersection / union if union > 0 else 0.0
