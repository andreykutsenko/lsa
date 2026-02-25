"""Graph builder - constructs nodes and edges from parsed .procs files."""

import json
import sqlite3
from pathlib import Path

from ..db.connection import insert_node, insert_edge
from ..parsers.procs_parser import ProcsData
from ..utils.paths import map_unix_to_snapshot


def build_graph_from_procs(
    conn: sqlite3.Connection,
    procs_list: list[tuple[str, ProcsData]],
    snapshot_path: Path,
) -> dict:
    """
    Build graph nodes and edges from parsed .procs data.

    Args:
        conn: Database connection
        procs_list: List of (proc_name, ProcsData) tuples
        snapshot_path: Path to snapshot root for path resolution

    Returns:
        Stats dict with counts
    """
    stats = {
        "nodes_created": 0,
        "edges_created": 0,
        "procs_processed": 0,
    }

    for proc_name, procs_data in procs_list:
        stats["procs_processed"] += 1

        # Create proc node
        proc_node_id = insert_node(
            conn,
            node_type="proc",
            key=f"proc:{proc_name}",
            display_name=f"{procs_data.cid.upper()} - {procs_data.app_type}",
            canonical_path=f"procs/{proc_name}.procs",
            original_path=None,
            confidence=1.0,
        )
        stats["nodes_created"] += 1

        # Process shell script reference
        if procs_data.shell_script:
            script_node_id = _create_script_node(
                conn, procs_data.shell_script, snapshot_path
            )
            if script_node_id:
                stats["nodes_created"] += 1

                # Create RUNS edge
                evidence = {
                    "file": f"procs/{proc_name}.procs",
                    "line_no": procs_data.shell_script_line,
                    "line_text": f"__Shell Script: {procs_data.shell_script}",
                }
                insert_edge(
                    conn,
                    src=proc_node_id,
                    dst=script_node_id,
                    rel_type="RUNS",
                    confidence=1.0,
                    evidence_json=json.dumps(evidence),
                )
                stats["edges_created"] += 1

    conn.commit()
    return stats


def _create_script_node(
    conn: sqlite3.Connection,
    script_path: str,
    snapshot_path: Path,
) -> int | None:
    """Create a script node from a unix path."""
    canonical, confidence = map_unix_to_snapshot(script_path, snapshot_path)

    canonical_str = str(canonical.relative_to(snapshot_path)) if canonical else None

    return insert_node(
        conn,
        node_type="script",
        key=f"script:{Path(script_path).name}",
        display_name=Path(script_path).name,
        canonical_path=canonical_str,
        original_path=script_path,
        confidence=confidence,
    )


def get_graph_stats(conn: sqlite3.Connection) -> dict:
    """Get statistics about the graph."""
    stats = {}

    # Count nodes by type
    cursor = conn.execute(
        "SELECT type, COUNT(*) FROM nodes GROUP BY type"
    )
    stats["nodes_by_type"] = dict(cursor.fetchall())

    # Count edges by type
    cursor = conn.execute(
        "SELECT rel_type, COUNT(*) FROM edges GROUP BY rel_type"
    )
    stats["edges_by_type"] = dict(cursor.fetchall())

    # Total counts
    stats["total_nodes"] = sum(stats["nodes_by_type"].values())
    stats["total_edges"] = sum(stats["edges_by_type"].values())

    return stats
