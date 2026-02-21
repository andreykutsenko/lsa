"""Generate Mermaid graph TD diagrams from LSA bundle candidates."""
import re
from pathlib import Path

from ..analysis.planner import BundleCandidate
from ..graph.call_parser import build_call_graph


def _sanitize_id(name: str) -> str:
    """Convert a filename (without extension) to a valid Mermaid node ID."""
    return re.sub(r"[^a-zA-Z0-9]", "_", name)


def _stem(path_str: str) -> str:
    """Return the stem (filename without extension) of a path string."""
    return Path(path_str).stem


def _basename(path_str: str) -> str:
    """Return the basename (filename with extension) of a path string."""
    return Path(path_str).name


def generate_mermaid(bundle: BundleCandidate, snapshot_path: Path) -> str:
    """Return a Mermaid graph TD diagram of the bundle's call structure.

    Node shapes:
    - proc:       rectangle with proc_name + display_name
    - script:     rectangle
    - insert:     stadium  [( )]
    - control:    parallelogram  [/ /]
    - docdef/dfa: hexagon  {{ }}

    Edge labels: RUNS, READS, control, dfa, calls, helper
    """
    lines: list[str] = ["graph TD"]

    # Proc node
    proc_id = _sanitize_id(bundle.proc_name)
    proc_label = f"{bundle.proc_name}\\n{bundle.display_name}"
    lines.append(f'    {proc_id}["{proc_label}"]')

    # Group files by kind
    runs_files = [f for f in bundle.files if f.source == "RUNS_edge"]
    reads_files = [f for f in bundle.files if f.kind == "insert"]
    control_files = [f for f in bundle.files if f.kind == "control"]
    docdef_files = [f for f in bundle.files if f.kind == "docdef"]
    helper_files = [f for f in bundle.files if f.source == "helper_prefix_match"]

    # Build set of all script basenames in the bundle for call graph analysis
    all_script_files = [f for f in bundle.files if f.kind == "script"]
    script_paths: dict[str, Path] = {
        _basename(f.path): snapshot_path / f.path
        for f in all_script_files
    }

    # Build call graph among scripts
    call_graph = build_call_graph(script_paths)

    # Collect all scripts reachable via call graph edges
    called_scripts: set[str] = set()
    for targets in call_graph.values():
        called_scripts.update(targets)

    # --- proc → RUNS scripts ---
    runs_basenames = {_basename(f.path) for f in runs_files}
    for f in runs_files:
        bn = _basename(f.path)
        node_id = _sanitize_id(_stem(f.path))
        lines.append(f'    {node_id}["{bn}"]')
        lines.append(f"    {proc_id} -->|RUNS| {node_id}")

    # --- proc → READS inserts ---
    for f in reads_files:
        bn = _basename(f.path)
        node_id = _sanitize_id(_stem(f.path)) + "_ins"
        lines.append(f'    {node_id}(["{bn}"])')
        lines.append(f"    {proc_id} -->|READS| {node_id}")

    # --- proc → control files ---
    for f in control_files:
        bn = _basename(f.path)
        node_id = _sanitize_id(_stem(f.path)) + "_ctl"
        lines.append(f'    {node_id}[/"{bn}"\\]')
        lines.append(f"    {proc_id} -->|control| {node_id}")

    # --- proc → DFA/docdef files ---
    for f in docdef_files:
        bn = _basename(f.path)
        node_id = _sanitize_id(_stem(f.path))
        lines.append(f'    {node_id}{{{{"{bn}"}}}}')
        lines.append(f"    {proc_id} -->|dfa| {node_id}")

    # --- call graph edges between scripts ---
    for caller_bn, targets in call_graph.items():
        caller_id = _sanitize_id(Path(caller_bn).stem)
        for target_bn in targets:
            target_id = _sanitize_id(Path(target_bn).stem)
            # Declare helper script node if it was not already declared as a RUNS script
            if target_bn not in runs_basenames:
                lines.append(f'    {target_id}["{target_bn}"]')
            lines.append(f"    {caller_id} -->|calls| {target_id}")

    # --- orphan helper scripts not reachable via call graph ---
    orphan_helpers = [
        f for f in helper_files
        if _basename(f.path) not in called_scripts
        and _basename(f.path) not in runs_basenames
    ]
    for f in orphan_helpers:
        bn = _basename(f.path)
        node_id = _sanitize_id(_stem(f.path))
        lines.append(f'    {node_id}["{bn}"]')
        lines.append(f"    {proc_id} -.->|helper| {node_id}")

    return "\n".join(lines)
