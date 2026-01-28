"""Log-to-node matching for LSA."""

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from ..parsers.log_parser import LogAnalysis, extract_cid_from_log_path, extract_proc_name_from_log_path, extract_base_proc_name


@dataclass
class MatchCandidate:
    """A candidate node with scoring breakdown."""
    node: dict
    total_score: float = 0.0
    strategies: list[tuple[str, float]] = field(default_factory=list)

    def add_score(self, strategy: str, score: float):
        """Add score from a strategy."""
        self.strategies.append((strategy, score))
        self.total_score += score


def match_log_to_node(
    conn: sqlite3.Connection,
    log_analysis: LogAnalysis,
    log_path: Path,
    forced_proc: str | None = None,
    debug: bool = False,
) -> tuple[dict | None, float, list[MatchCandidate] | None]:
    """
    Match a log file to the most likely proc node.

    Scoring weights:
    - PREFIX= token exact match: +2.0 (strongest signal)
    - DOCDEF reference match: +1.5
    - Script path match: +1.2
    - Proc name from log path: +1.0
    - JID token match: +0.5
    - CID match: +0.3 (weakest, too general)

    Args:
        conn: Database connection
        log_analysis: Parsed log analysis
        log_path: Path to log file
        forced_proc: If set, force this proc (bypass scoring)
        debug: If True, return all candidates with breakdown

    Returns:
        (node_dict, confidence, debug_candidates) or (None, 0.0, None)
    """
    # Handle forced proc
    if forced_proc:
        forced_proc = forced_proc.lower()
        row = conn.execute(
            "SELECT * FROM nodes WHERE type = 'proc' AND (key = ? OR key LIKE ?)",
            (f"proc:{forced_proc}", f"proc:{forced_proc}%")
        ).fetchone()
        if row:
            return dict(row), 1.0, None
        # Try partial match
        row = conn.execute(
            "SELECT * FROM nodes WHERE type = 'proc' AND key LIKE ?",
            (f"%{forced_proc}%",)
        ).fetchone()
        if row:
            return dict(row), 0.9, None
        return None, 0.0, None

    candidates: dict[int, MatchCandidate] = {}

    def add_candidate(node: dict, strategy: str, score: float):
        node_id = node["id"]
        if node_id not in candidates:
            candidates[node_id] = MatchCandidate(node=node)
        candidates[node_id].add_score(strategy, score)

    # Strategy 1: PREFIX= token match (strongest signal)
    for prefix in log_analysis.prefix_tokens:
        rows = conn.execute(
            "SELECT * FROM nodes WHERE type = 'proc' AND key = ?",
            (f"proc:{prefix}",)
        ).fetchall()
        for row in rows:
            add_candidate(dict(row), f"prefix_exact:{prefix}", 2.0)

        # Also try partial match for PREFIX
        if not rows:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE type = 'proc' AND key LIKE ?",
                (f"proc:{prefix}%",)
            ).fetchall()
            for row in rows:
                add_candidate(dict(row), f"prefix_partial:{prefix}", 1.5)

    # Strategy 2: DOCDEF reference match
    for docdef_ref in log_analysis.docdef_refs:
        # Find procs that use this docdef
        rows = conn.execute(
            """
            SELECT p.* FROM nodes p
            JOIN edges e ON p.id = e.src
            JOIN nodes d ON e.dst = d.id
            WHERE p.type = 'proc'
            AND d.type = 'docdef'
            AND (d.display_name LIKE ? OR d.key LIKE ?)
            """,
            (f"%{docdef_ref}%", f"%{docdef_ref.lower()}%")
        ).fetchall()
        for row in rows:
            add_candidate(dict(row), f"docdef:{docdef_ref}", 1.5)

    # Strategy 3: Script path match
    for script_path in log_analysis.script_paths:
        script_name = Path(script_path).name
        # Find procs that RUNS this script
        rows = conn.execute(
            """
            SELECT p.* FROM nodes p
            JOIN edges e ON p.id = e.src
            JOIN nodes s ON e.dst = s.id
            WHERE p.type = 'proc'
            AND s.type = 'script'
            AND e.rel_type = 'RUNS'
            AND (s.display_name = ? OR s.original_path LIKE ?)
            """,
            (script_name, f"%{script_name}")
        ).fetchall()
        for row in rows:
            add_candidate(dict(row), f"script:{script_name}", 1.2)

    # Strategy 4: Extract proc name from log path
    proc_name = extract_proc_name_from_log_path(log_path)
    if proc_name:
        # Exact match first
        rows = conn.execute(
            "SELECT * FROM nodes WHERE type = 'proc' AND key = ?",
            (f"proc:{proc_name}",)
        ).fetchall()
        for row in rows:
            add_candidate(dict(row), f"path_exact:{proc_name}", 1.0)

        # Try base proc name (strip cycle digits): bkfnds1122 -> bkfnds1
        if not rows:
            base_name = extract_base_proc_name(proc_name)
            if base_name and base_name != proc_name:
                rows = conn.execute(
                    "SELECT * FROM nodes WHERE type = 'proc' AND key = ?",
                    (f"proc:{base_name}",)
                ).fetchall()
                for row in rows:
                    add_candidate(dict(row), f"path_base:{base_name}", 0.9)

        # Partial match as fallback
        if not rows:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE type = 'proc' AND key LIKE ?",
                (f"proc:{proc_name}%",)
            ).fetchall()
            for row in rows:
                add_candidate(dict(row), f"path_partial:{proc_name}", 0.7)

    # Strategy 5: JID token match
    for jid in log_analysis.jid_tokens:
        rows = conn.execute(
            "SELECT * FROM nodes WHERE type = 'proc' AND key LIKE ?",
            (f"%{jid}%",)
        ).fetchall()
        for row in rows:
            add_candidate(dict(row), f"jid:{jid}", 0.5)

    # Strategy 6: CID match (lowest weight - too general)
    cid = extract_cid_from_log_path(log_path)
    if cid:
        rows = conn.execute(
            "SELECT * FROM nodes WHERE type = 'proc' AND key LIKE ?",
            (f"proc:{cid}%",)
        ).fetchall()
        for row in rows:
            add_candidate(dict(row), f"cid:{cid}", 0.3)

    if not candidates:
        return None, 0.0, [] if debug else None

    # Sort candidates by total score
    sorted_candidates = sorted(
        candidates.values(),
        key=lambda c: -c.total_score
    )

    # Normalize confidence to 0-1 range
    best = sorted_candidates[0]
    max_possible = 2.0 + 1.5 + 1.2 + 1.0  # If all strategies match
    confidence = min(1.0, best.total_score / max_possible)

    debug_result = sorted_candidates[:10] if debug else None
    return best.node, confidence, debug_result


def get_node_neighbors(
    conn: sqlite3.Connection,
    node_id: int,
    hops: int = 1,
) -> dict:
    """
    Get neighboring nodes (upstream and downstream).

    Args:
        conn: Database connection
        node_id: ID of the center node
        hops: Number of hops to traverse (default 1)

    Returns:
        Dict with 'upstream' and 'downstream' lists
    """
    upstream = []
    downstream = []

    # Get upstream (nodes that point TO this node)
    rows = conn.execute(
        """
        SELECT n.*, e.rel_type, e.confidence, e.evidence_json
        FROM nodes n
        JOIN edges e ON n.id = e.src
        WHERE e.dst = ?
        """,
        (node_id,)
    ).fetchall()
    for row in rows:
        upstream.append({
            "node": dict(row),
            "rel_type": row["rel_type"],
            "confidence": row["confidence"],
            "evidence": row["evidence_json"],
        })

    # Get downstream (nodes that this node points TO)
    rows = conn.execute(
        """
        SELECT n.*, e.rel_type, e.confidence, e.evidence_json
        FROM nodes n
        JOIN edges e ON n.id = e.dst
        WHERE e.src = ?
        """,
        (node_id,)
    ).fetchall()
    for row in rows:
        downstream.append({
            "node": dict(row),
            "rel_type": row["rel_type"],
            "confidence": row["confidence"],
            "evidence": row["evidence_json"],
        })

    return {
        "upstream": upstream,
        "downstream": downstream,
    }


def get_node_by_id(conn: sqlite3.Connection, node_id: int) -> dict | None:
    """Get a node by its ID."""
    row = conn.execute(
        "SELECT * FROM nodes WHERE id = ?",
        (node_id,)
    ).fetchone()
    return dict(row) if row else None


def get_node_by_key(conn: sqlite3.Connection, key: str) -> dict | None:
    """Get a node by its key."""
    row = conn.execute(
        "SELECT * FROM nodes WHERE key = ?",
        (key,)
    ).fetchone()
    return dict(row) if row else None


def get_related_files(
    conn: sqlite3.Connection,
    node_id: int,
    snapshot_path: Path,
) -> list[str]:
    """
    Get list of files related to a node.

    Returns actual file paths in the snapshot.
    """
    files = []

    # Get the node itself
    node = get_node_by_id(conn, node_id)
    if node and node["canonical_path"]:
        file_path = snapshot_path / node["canonical_path"]
        if file_path.exists():
            files.append(str(file_path))

    # Get downstream resources
    neighbors = get_node_neighbors(conn, node_id)
    for neighbor in neighbors["downstream"]:
        n = neighbor["node"]
        if n["canonical_path"]:
            file_path = snapshot_path / n["canonical_path"]
            if file_path.exists():
                files.append(str(file_path))

    return list(set(files))[:10]  # Limit to 10 files


def format_debug_candidates(candidates: list[MatchCandidate]) -> str:
    """Format debug output for candidates."""
    lines = ["", "=== MATCHING DEBUG (top 10 candidates) ==="]
    for i, c in enumerate(candidates, 1):
        lines.append(f"\n{i}. {c.node['key']} (score: {c.total_score:.2f})")
        lines.append(f"   Display: {c.node['display_name']}")
        for strategy, score in c.strategies:
            lines.append(f"   +{score:.1f} {strategy}")
    lines.append("\n" + "=" * 45)
    return "\n".join(lines)
