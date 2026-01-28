"""Graph builder - constructs nodes and edges from parsed .procs files."""

import json
import sqlite3
from pathlib import Path

from ..db.connection import insert_node, insert_edge
from ..parsers.procs_parser import ProcsData, extract_referenced_scripts, extract_referenced_resources
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

        # Process file setup (insert file)
        if procs_data.file_setup:
            insert_node_id = _create_resource_node(
                conn, procs_data.file_setup, "insert", snapshot_path
            )
            if insert_node_id:
                stats["nodes_created"] += 1

                evidence = {
                    "file": f"procs/{proc_name}.procs",
                    "line_no": procs_data.file_setup_line,
                    "line_text": f"__File Setup: {procs_data.file_setup}",
                }
                insert_edge(
                    conn,
                    src=proc_node_id,
                    dst=insert_node_id,
                    rel_type="READS",
                    confidence=1.0,
                    evidence_json=json.dumps(evidence),
                )
                stats["edges_created"] += 1

        # Process log file reference
        if procs_data.log_file:
            log_node_id = _create_resource_node(
                conn, procs_data.log_file, "log", snapshot_path
            )
            if log_node_id:
                stats["nodes_created"] += 1

                evidence = {
                    "file": f"procs/{proc_name}.procs",
                    "line_no": procs_data.log_file_line,
                    "line_text": f"__Log File: {procs_data.log_file}",
                }
                insert_edge(
                    conn,
                    src=proc_node_id,
                    dst=log_node_id,
                    rel_type="READS",
                    confidence=0.9,
                    evidence_json=json.dumps(evidence),
                )
                stats["edges_created"] += 1

        # Process cross-references to other .procs files
        for cross_ref in procs_data.cross_refs:
            ref_proc_name = Path(cross_ref).stem.lower()
            ref_node_id = insert_node(
                conn,
                node_type="proc",
                key=f"proc:{ref_proc_name}",
                display_name=ref_proc_name,
                canonical_path=f"procs/{ref_proc_name}.procs",
                original_path=cross_ref,
                confidence=0.8,
            )

            evidence = {
                "file": f"procs/{proc_name}.procs",
                "line_no": None,
                "line_text": f"refer to {cross_ref}",
            }
            insert_edge(
                conn,
                src=proc_node_id,
                dst=ref_node_id,
                rel_type="REFERS_TO",
                confidence=0.9,
                evidence_json=json.dumps(evidence),
            )
            stats["edges_created"] += 1

        # Process other resource references
        for resource_path, resource_type in extract_referenced_resources(procs_data):
            if resource_path == procs_data.file_setup:
                continue  # Already processed

            resource_node_id = _create_resource_node(
                conn, resource_path, resource_type, snapshot_path
            )
            if resource_node_id:
                stats["nodes_created"] += 1

                evidence = {
                    "file": f"procs/{proc_name}.procs",
                    "line_no": None,
                    "line_text": f"Referenced: {resource_path}",
                }
                insert_edge(
                    conn,
                    src=proc_node_id,
                    dst=resource_node_id,
                    rel_type="READS",
                    confidence=0.7,
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


def _create_resource_node(
    conn: sqlite3.Connection,
    resource_path: str,
    resource_type: str,
    snapshot_path: Path,
) -> int | None:
    """Create a resource node (control, insert, docdef, log)."""
    canonical, confidence = map_unix_to_snapshot(resource_path, snapshot_path)

    canonical_str = str(canonical.relative_to(snapshot_path)) if canonical else None

    # Determine node type
    node_type = resource_type
    if resource_path.endswith(".control"):
        node_type = "control"
    elif resource_path.endswith((".dfa", ".DFA")):
        node_type = "docdef"
    elif resource_path.endswith(".ins"):
        node_type = "insert"

    return insert_node(
        conn,
        node_type=node_type,
        key=f"{node_type}:{Path(resource_path).name}",
        display_name=Path(resource_path).name,
        canonical_path=canonical_str,
        original_path=resource_path,
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
