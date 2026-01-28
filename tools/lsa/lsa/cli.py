"""CLI entry point for LSA."""

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import __version__
from .config import (
    DEFAULT_SCAN_DIRS,
    HISTORIES_DIR,
    MAX_TEXT_SIZE,
    get_db_path,
)
from .db import (
    init_db,
    get_connection,
    insert_message_code,
    count_message_codes,
    get_message_codes_batch,
)
from .db.connection import (
    insert_artifact,
    insert_proc,
    insert_case_card,
    upsert_case_card,
    upsert_incident,
    get_incidents,
    count_incidents,
    count_case_cards,
)
from .utils.hasher import compute_sha256, should_store_content, try_read_text
from .parsers import parse_procs_file, parse_log_file
from .parsers.history_parser import parse_history_directory, parse_history_files
from .graph import build_graph_from_procs, match_log_to_node, get_node_neighbors
from .graph.matching import get_related_files, format_debug_candidates, MatchCandidate
from .graph.builder import get_graph_stats
from .analysis import generate_hypotheses, find_similar_cases
from .analysis.hypotheses import get_default_hypotheses
from .output import generate_context_pack

app = typer.Typer(
    name="lsa",
    help="Legacy Script Archaeologist - analyze legacy script snapshots",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"lsa version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit"
    ),
):
    """LSA - Legacy Script Archaeologist."""
    pass


@app.command()
def scan(
    snapshot: Path = typer.Argument(..., help="Path to snapshot directory"),
    include_logs: bool = typer.Option(
        False, "--include-logs", help="Also scan logs/ directory"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    Scan snapshot directory and build execution graph.

    By default scans: procs/, master/, control/, insert/, docdef/
    Use --include-logs to also scan logs/ (slower).
    """
    snapshot = snapshot.resolve()
    if not snapshot.exists():
        console.print(f"[red]Error:[/red] Snapshot path does not exist: {snapshot}")
        raise typer.Exit(1)

    db_path = get_db_path(snapshot)
    console.print(f"Scanning snapshot: {snapshot}")
    console.print(f"Database: {db_path}")

    # Initialize database
    init_db(db_path)

    # Determine directories to scan
    scan_dirs = list(DEFAULT_SCAN_DIRS)
    if include_logs:
        scan_dirs.append("logs")

    stats = {
        "files_scanned": 0,
        "files_with_content": 0,
        "procs_parsed": 0,
        "errors": 0,
    }

    procs_list = []

    with get_connection(db_path) as conn:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Scan each directory
            for subdir in scan_dirs:
                dir_path = snapshot / subdir
                if not dir_path.exists():
                    if verbose:
                        console.print(f"[yellow]Skipping (not found):[/yellow] {subdir}/")
                    continue

                task = progress.add_task(f"Scanning {subdir}/...", total=None)

                for file_path in dir_path.rglob("*"):
                    if not file_path.is_file():
                        continue

                    stats["files_scanned"] += 1

                    try:
                        relative_path = str(file_path.relative_to(snapshot))
                        stat = file_path.stat()

                        # Determine kind
                        kind = subdir
                        if file_path.suffix == ".procs":
                            kind = "procs"
                        elif file_path.suffix in (".sh", ".pl", ".py"):
                            kind = "script"
                        elif file_path.suffix == ".control":
                            kind = "control"
                        elif file_path.suffix == ".ins":
                            kind = "insert"
                        elif file_path.suffix in (".dfa", ".DFA"):
                            kind = "docdef"

                        # Determine if we should store content
                        sha256 = None
                        text_content = None

                        if should_store_content(file_path, stat.st_size):
                            text_content = try_read_text(file_path)
                            if text_content is not None:
                                sha256 = compute_sha256(file_path)
                                stats["files_with_content"] += 1

                        # Insert artifact
                        insert_artifact(
                            conn,
                            kind=kind,
                            path=relative_path,
                            mtime=stat.st_mtime,
                            size=stat.st_size,
                            sha256=sha256,
                            text_content=text_content,
                        )

                        # Parse .procs files
                        if file_path.suffix == ".procs":
                            procs_data = parse_procs_file(file_path)
                            proc_name = file_path.stem.lower()

                            insert_proc(
                                conn,
                                proc_name=proc_name,
                                path=relative_path,
                                parsed_json=procs_data.to_json(),
                                sha256=sha256,
                            )
                            procs_list.append((proc_name, procs_data))
                            stats["procs_parsed"] += 1

                    except Exception as e:
                        stats["errors"] += 1
                        if verbose:
                            console.print(f"[red]Error processing {file_path}:[/red] {e}")

                progress.remove_task(task)

            # Build graph from parsed procs
            if procs_list:
                task = progress.add_task("Building execution graph...", total=None)
                graph_stats = build_graph_from_procs(conn, procs_list, snapshot)
                progress.remove_task(task)
            else:
                graph_stats = {"nodes_created": 0, "edges_created": 0}

    # Print summary
    console.print()
    console.print("[green]Scan complete![/green]")
    console.print(f"  Files scanned: {stats['files_scanned']}")
    console.print(f"  Files with content: {stats['files_with_content']}")
    console.print(f"  Procs parsed: {stats['procs_parsed']}")
    console.print(f"  Nodes created: {graph_stats.get('nodes_created', 0)}")
    console.print(f"  Edges created: {graph_stats.get('edges_created', 0)}")
    if stats["errors"]:
        console.print(f"  [yellow]Errors: {stats['errors']}[/yellow]")


@app.command()
def explain(
    snapshot: Path = typer.Argument(..., help="Path to snapshot directory"),
    log: Path = typer.Option(..., "--log", "-l", help="Path to log file to analyze"),
    proc: str = typer.Option(None, "--proc", "-p", help="Force specific proc id/basename"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Show top 10 candidates with score breakdown"),
    no_persist: bool = typer.Option(False, "--no-persist", help="Don't persist analysis to incidents table"),
):
    """
    Generate context pack for a log file.

    Parses the specified log, matches it to graph nodes,
    generates hypotheses, and outputs a single context pack block.

    By default, persists analysis to incidents table (use --no-persist to skip).

    Use --proc to force a specific proc (e.g., --proc bkfnds1).
    Use --debug to see matching candidates and their scores.
    """
    snapshot = snapshot.resolve()
    log = log.resolve()

    if not snapshot.exists():
        console.print(f"[red]Error:[/red] Snapshot path does not exist: {snapshot}")
        raise typer.Exit(1)

    if not log.exists():
        console.print(f"[red]Error:[/red] Log file does not exist: {log}")
        raise typer.Exit(1)

    db_path = get_db_path(snapshot)
    if not db_path.exists():
        console.print(f"[red]Error:[/red] Database not found. Run 'lsa scan' first.")
        raise typer.Exit(1)

    # Parse log file
    log_analysis = parse_log_file(log)

    # Debug: show extracted signals
    if debug:
        console.print("[cyan]Extracted signals from log:[/cyan]")
        console.print(f"  PREFIX tokens: {log_analysis.prefix_tokens}")
        console.print(f"  DOCDEF refs: {log_analysis.docdef_refs}")
        console.print(f"  Script paths: {log_analysis.script_paths}")
        console.print(f"  JID tokens: {log_analysis.jid_tokens}")
        console.print(f"  Error codes: {log_analysis.error_codes[:5]}")
        console.print()

    with get_connection(db_path) as conn:
        # Match log to node
        top_node, confidence, debug_candidates = match_log_to_node(
            conn, log_analysis, log,
            forced_proc=proc,
            debug=debug
        )

        # Show debug output if requested
        if debug and debug_candidates:
            console.print(format_debug_candidates(debug_candidates))

        # Get neighbors if matched
        neighbors = None
        related_files = []
        if top_node:
            neighbors = get_node_neighbors(conn, top_node["id"])
            related_files = get_related_files(conn, top_node["id"], snapshot)

        # Generate hypotheses (pass log_analysis for wrapper noise detection)
        hypotheses = generate_hypotheses(log_analysis.error_signals, log_analysis=log_analysis)
        if not hypotheses:
            hypotheses = get_default_hypotheses()

        # Find similar cases
        signals = log_analysis.error_codes
        similar_cases = find_similar_cases(conn, signals, related_files)

        # Debug: show similar cases info
        if debug:
            console.print("[cyan]Similar cases from case_cards:[/cyan]")
            if similar_cases:
                for case in similar_cases:
                    console.print(f"  ID {case.case_id}: {case.title or 'Untitled'} (match: {case.match_score:.0%})")
                    if case.root_cause:
                        console.print(f"    Root cause: {case.root_cause[:60]}...")
            else:
                console.print("  (none found above threshold)")
            console.print()

        # Fetch decoded message codes from KB
        decoded_codes = get_message_codes_batch(conn, log_analysis.error_codes)

        # Persist to incidents table (unless --no-persist)
        if not no_persist:
            # Serialize data for storage
            hypotheses_json = json.dumps([
                {"hypothesis": h.hypothesis, "confidence": h.confidence, "line_number": h.line_number}
                for h in hypotheses[:5]
            ], ensure_ascii=False)

            similar_cases_json = json.dumps([
                {"case_id": c.case_id, "title": c.title, "match_score": c.match_score}
                for c in similar_cases
            ], ensure_ascii=False) if similar_cases else None

            upsert_incident(
                conn,
                log_path=str(log),
                parsed_json=log_analysis.to_json(),
                top_node_id=top_node["id"] if top_node else None,
                top_node_key=top_node["key"] if top_node else None,
                confidence=confidence,
                hypotheses_json=hypotheses_json,
                similar_cases_json=similar_cases_json,
                created_at=datetime.now().isoformat(),
            )

    # Generate context pack
    context_pack = generate_context_pack(
        log_path=log,
        log_analysis=log_analysis,
        top_node=top_node,
        confidence=confidence,
        neighbors=neighbors,
        hypotheses=hypotheses,
        similar_cases=similar_cases,
        related_files=related_files,
        snapshot_path=snapshot,
        decoded_codes=decoded_codes,
    )

    # Output (single block, no extra commentary)
    print(context_pack)


def _has_fts_operators(query: str) -> bool:
    """Check if query contains FTS5 operators."""
    # FTS5 operators: AND, OR, NOT, *, ^, NEAR, "phrase"
    fts_patterns = [' AND ', ' OR ', ' NOT ', '*', '^', 'NEAR', '"']
    return any(op in query for op in fts_patterns)


def _search_fts(conn, query: str, limit: int) -> list:
    """Execute FTS search."""
    try:
        return conn.execute(
            """
            SELECT a.path, a.kind, snippet(artifacts_fts, 1, '>>>', '<<<', '...', 30) as snippet
            FROM artifacts_fts
            JOIN artifacts a ON artifacts_fts.rowid = a.id
            WHERE artifacts_fts MATCH ?
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
    except Exception:
        return []


def _search_like(conn, pattern: str, limit: int) -> list:
    """Execute LIKE search on paths and content."""
    return conn.execute(
        """
        SELECT path, kind, substr(text_content, 1, 100) as snippet
        FROM artifacts
        WHERE path LIKE ? OR text_content LIKE ?
        ORDER BY
            CASE WHEN path LIKE ? THEN 0 ELSE 1 END,
            path
        LIMIT ?
        """,
        (f"%{pattern}%", f"%{pattern}%", f"%{pattern}%", limit),
    ).fetchall()


def _search_path_only(conn, pattern: str, limit: int) -> list:
    """Search only in file paths (for prefix/substring matching)."""
    return conn.execute(
        """
        SELECT path, kind, substr(text_content, 1, 100) as snippet
        FROM artifacts
        WHERE path LIKE ?
        ORDER BY path
        LIMIT ?
        """,
        (f"%{pattern}%", limit),
    ).fetchall()


@app.command()
def search(
    snapshot: Path = typer.Argument(..., help="Path to snapshot directory"),
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum results"),
    raw_fts: bool = typer.Option(False, "--raw-fts", help="Use raw FTS query (no expansion)"),
):
    """
    Search in artifacts with smart query expansion.

    By default uses smart expansion:
    1. Try exact FTS match
    2. Try prefix match (append '*')
    3. Fall back to substring LIKE search

    Use --raw-fts to disable expansion and run query as-is.

    Examples:
        lsa search $SNAP bkfnds          # finds bkfnds1.procs via expansion
        lsa search $SNAP "wabc_loan"     # exact phrase search
        lsa search $SNAP --raw-fts "loan*"  # raw FTS prefix query
    """
    snapshot = snapshot.resolve()
    db_path = get_db_path(snapshot)

    if not db_path.exists():
        console.print(f"[red]Error:[/red] Database not found. Run 'lsa scan' first.")
        raise typer.Exit(1)

    rows = []
    search_method = None

    with get_connection(db_path) as conn:
        if raw_fts or _has_fts_operators(query):
            # Raw FTS mode - use query as-is
            rows = _search_fts(conn, query, limit)
            search_method = "fts_raw"
        else:
            # Smart expansion mode - prioritize path matches
            # Step 1: Try path substring match first (most intuitive for users)
            rows = _search_path_only(conn, query, limit)
            search_method = "path_substring"

            # Step 2: If no path matches, try FTS exact
            if not rows:
                rows = _search_fts(conn, f'"{query}"', limit)
                search_method = "fts_exact"

            # Step 3: Try FTS prefix match
            if not rows:
                rows = _search_fts(conn, f"{query}*", limit)
                search_method = "fts_prefix"

            # Step 4: Fall back to full LIKE search (paths + content)
            if not rows:
                rows = _search_like(conn, query, limit)
                search_method = "like_full"

    if not rows:
        console.print(f"No results found for: {query}")
        return

    console.print(f"Found {len(rows)} result(s) for: {query} [method: {search_method}]")
    console.print()

    for row in rows:
        console.print(f"[cyan]{row['path']}[/cyan] [{row['kind']}]")
        if row["snippet"]:
            snippet = row["snippet"].replace("\n", " ")[:100]
            console.print(f"  {snippet}")
        console.print()


def _get_histories_search_paths(snapshot: Path) -> list[Path]:
    """
    Get list of paths to search for histories directory.

    Order:
    1. <snapshot>/histories/
    2. <snapshot>/refs/histories/
    3. <snapshot_parent>/histories/
    4. <snapshot_parent>/refs/histories/
    """
    snapshot_parent = snapshot.parent
    return [
        snapshot / HISTORIES_DIR,
        snapshot / "refs" / HISTORIES_DIR,
        snapshot_parent / HISTORIES_DIR,
        snapshot_parent / "refs" / HISTORIES_DIR,
    ]


def _find_histories_path(snapshot: Path, explicit_path: Path | None) -> Path | None:
    """
    Find histories directory using auto-detection logic.

    Order:
    1. Explicit --path option
    2. <snapshot>/histories/
    3. <snapshot>/refs/histories/
    4. <snapshot_parent>/histories/
    5. <snapshot_parent>/refs/histories/
    """
    if explicit_path:
        return explicit_path if explicit_path.exists() else None

    for candidate in _get_histories_search_paths(snapshot):
        if candidate.exists():
            return candidate

    return None


@app.command("import-histories")
def import_histories(
    snapshot: Path = typer.Argument(..., help="Path to snapshot directory"),
    path: Path = typer.Option(
        None, "--path", "-p",
        help="Path to histories directory (auto-detected if omitted)"
    ),
    glob_pattern: str = typer.Option(
        None, "--glob", "-g",
        help="Glob pattern for files (e.g., '*.md', '**/*.txt')"
    ),
    redact: bool = typer.Option(False, "--redact", "-r", help="Redact PII from stored content"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    Import Cursor histories into case_cards.

    Parses history files using robust heuristics (no strict delimiters required).

    Auto-detection order for --path:
      1. <snapshot>/histories/
      2. <snapshot>/refs/histories/
      3. <snapshot_parent>/histories/
      4. <snapshot_parent>/refs/histories/

    Uses upsert logic with content_hash for idempotent re-imports.
    """
    snapshot = snapshot.resolve()

    if not snapshot.exists():
        console.print(f"[red]Error:[/red] Snapshot path does not exist: {snapshot}")
        raise typer.Exit(1)

    # Find histories path
    histories_path = _find_histories_path(snapshot, path)
    if histories_path is None:
        console.print("[red]Error:[/red] Histories directory not found. Searched:")
        if path:
            console.print(f"  --path: {path}")
        for search_path in _get_histories_search_paths(snapshot):
            console.print(f"  {search_path}")
        console.print("\nUse --path to specify the directory explicitly.")
        raise typer.Exit(1)

    db_path = get_db_path(snapshot)
    if not db_path.exists():
        console.print(f"[yellow]Warning:[/yellow] Database not found. Initializing...")
        init_db(db_path)

    console.print(f"Importing histories from: {histories_path}")
    if glob_pattern:
        console.print(f"Using glob pattern: {glob_pattern}")

    # Parse histories
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing history files...", total=None)
        cards = parse_history_directory(histories_path, redact=redact, glob_pattern=glob_pattern)
        progress.remove_task(task)

    if not cards:
        console.print("[yellow]No case cards extracted from histories[/yellow]")
        return

    # Store in database with upsert logic
    with get_connection(db_path) as conn:
        inserted = 0
        updated = 0
        skipped = 0
        now = datetime.now().isoformat()

        for card in cards:
            try:
                json_fields = card.to_json_fields()
                card_id, was_inserted = upsert_case_card(
                    conn,
                    source_path=card.source_path,
                    chunk_id=card.chunk_id,
                    title=card.title,
                    signals_json=json_fields["signals_json"],
                    root_cause=card.root_cause,
                    fix_summary=card.fix_summary,
                    verify_commands_json=json_fields["verify_commands_json"],
                    related_files_json=json_fields["related_files_json"],
                    tags_json=json_fields["tags_json"],
                    created_at=now,
                    content_hash=card.content_hash,
                )
                if was_inserted:
                    inserted += 1
                elif card_id:
                    # Check if actually updated (based on upsert_case_card logic)
                    # If content_hash matched, it would have returned early
                    updated += 1
            except Exception as e:
                skipped += 1
                if verbose:
                    console.print(f"[red]Error storing card:[/red] {e}")

        total_in_db = count_case_cards(conn)

    console.print()
    console.print("[green]Import complete![/green]")
    console.print(f"  Case cards extracted: {len(cards)}")
    console.print(f"  Inserted: {inserted}")
    console.print(f"  Updated: {updated}")
    if skipped:
        console.print(f"  [yellow]Skipped (errors): {skipped}[/yellow]")
    console.print(f"  Total case cards in database: {total_in_db}")


# Default PDF paths for auto-detection
DEFAULT_PDF_PATHS = [
    # Global reference location
    Path("/mnt/c/Users/akutsenko/code/rhs_snapshot_project/refs/papyrus/Papyrus_DocExec_message_codes.pdf"),
]


def _find_pdf_path(snapshot: Path, pdf_option: Path | None) -> Path | None:
    """
    Find PDF path using auto-detection logic.

    Order:
    1. Explicit --pdf option
    2. <snapshot>/refs/papyrus/*.pdf
    3. Global default paths
    """
    if pdf_option:
        return pdf_option if pdf_option.exists() else None

    # Try snapshot-local refs/papyrus/
    snapshot_refs = snapshot / "refs" / "papyrus"
    if snapshot_refs.exists():
        pdfs = list(snapshot_refs.glob("*.pdf"))
        if pdfs:
            return pdfs[0]

    # Try default global paths
    for path in DEFAULT_PDF_PATHS:
        if path.exists():
            return path

    return None


@app.command("import-codes")
def import_codes(
    snapshot: Path = typer.Argument(..., help="Path to snapshot directory"),
    pdf: Path = typer.Option(
        None, "--pdf", "-p",
        help="Path to Papyrus/DocExec message codes PDF (auto-detected if omitted)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    Import Papyrus/DocExec message codes from PDF knowledge base.

    Parses the PDF file and populates the message_codes table in the
    snapshot database. If --pdf is omitted, auto-detects PDF from:
      1. <snapshot>/refs/papyrus/*.pdf
      2. /mnt/c/.../rhs_snapshot_project/refs/papyrus/Papyrus_DocExec_message_codes.pdf
    """
    from .parsers.pdf_parser import parse_pdf_file_safe

    snapshot = snapshot.resolve()

    if not snapshot.exists():
        console.print(f"[red]Error:[/red] Snapshot path does not exist: {snapshot}")
        raise typer.Exit(1)

    # Find PDF path
    pdf_path = _find_pdf_path(snapshot, pdf)
    if pdf_path is None:
        console.print("[red]Error:[/red] PDF not found. Searched:")
        if pdf:
            console.print(f"  --pdf: {pdf}")
        console.print(f"  <snapshot>/refs/papyrus/*.pdf")
        for p in DEFAULT_PDF_PATHS:
            console.print(f"  {p}")
        console.print("\nUse --pdf to specify the path explicitly.")
        raise typer.Exit(1)

    db_path = get_db_path(snapshot)
    if not db_path.exists():
        console.print(f"[yellow]Warning:[/yellow] Database not found. Initializing...")
        init_db(db_path)

    console.print(f"Importing message codes from: {pdf_path}")
    console.print(f"Database: {db_path}")

    # Parse PDF
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing PDF...", total=None)
        entries, errors = parse_pdf_file_safe(pdf_path)
        progress.remove_task(task)

    if errors:
        for err in errors:
            console.print(f"[yellow]Warning:[/yellow] {err}")

    if not entries:
        console.print("[yellow]No message codes extracted from PDF[/yellow]")
        return

    # Store in database
    with get_connection(db_path) as conn:
        stored = 0
        now = datetime.now().isoformat()
        source_path_str = str(pdf_path)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Storing {len(entries)} codes...", total=None)

            for entry in entries:
                try:
                    insert_message_code(
                        conn,
                        code=entry.code,
                        severity=entry.severity,
                        title=entry.title,
                        body=entry.body,
                        source_path=source_path_str,
                        created_at=now,
                    )
                    stored += 1
                except Exception as e:
                    if verbose:
                        console.print(f"[red]Error storing {entry.code}:[/red] {e}")

            progress.remove_task(task)

        total_in_db = count_message_codes(conn)

    console.print()
    console.print("[green]Import complete![/green]")
    console.print(f"  Codes extracted from PDF: {len(entries)}")
    console.print(f"  Codes stored/updated: {stored}")
    console.print(f"  Total codes in database: {total_in_db}")


@app.command()
def stats(
    snapshot: Path = typer.Argument(..., help="Path to snapshot directory"),
):
    """
    Show statistics about the scanned snapshot.
    """
    snapshot = snapshot.resolve()
    db_path = get_db_path(snapshot)

    if not db_path.exists():
        console.print(f"[red]Error:[/red] Database not found. Run 'lsa scan' first.")
        raise typer.Exit(1)

    with get_connection(db_path) as conn:
        # Artifact counts
        artifact_counts = dict(conn.execute(
            "SELECT kind, COUNT(*) FROM artifacts GROUP BY kind"
        ).fetchall())

        # Graph stats
        graph = get_graph_stats(conn)

        # Case cards count
        case_cards_count = conn.execute(
            "SELECT COUNT(*) FROM case_cards"
        ).fetchone()[0]

        # Procs count
        procs_count = conn.execute(
            "SELECT COUNT(*) FROM procs"
        ).fetchone()[0]

        # Message codes count
        message_codes_count = count_message_codes(conn)

        # Incidents count
        incidents_count = count_incidents(conn)

    console.print(f"[bold]Snapshot Statistics: {snapshot}[/bold]")
    console.print()
    console.print("[cyan]Artifacts:[/cyan]")
    for kind, count in sorted(artifact_counts.items()):
        console.print(f"  {kind}: {count}")
    console.print()
    console.print("[cyan]Graph:[/cyan]")
    console.print(f"  Nodes: {graph['total_nodes']}")
    for node_type, count in sorted(graph["nodes_by_type"].items()):
        console.print(f"    {node_type}: {count}")
    console.print(f"  Edges: {graph['total_edges']}")
    for edge_type, count in sorted(graph["edges_by_type"].items()):
        console.print(f"    {edge_type}: {count}")
    console.print()
    console.print("[cyan]Other:[/cyan]")
    console.print(f"  Procs parsed: {procs_count}")
    console.print(f"  Case cards: {case_cards_count}")
    console.print(f"  Incidents: {incidents_count}")
    console.print(f"  Message codes (KB): {message_codes_count}")


@app.command()
def incidents(
    snapshot: Path = typer.Argument(..., help="Path to snapshot directory"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum incidents to show"),
):
    """
    List analyzed log incidents.

    Shows recent incidents from the incidents table, sorted by most recent first.
    """
    snapshot = snapshot.resolve()
    db_path = get_db_path(snapshot)

    if not db_path.exists():
        console.print(f"[red]Error:[/red] Database not found. Run 'lsa scan' first.")
        raise typer.Exit(1)

    with get_connection(db_path) as conn:
        total = count_incidents(conn)
        incident_list = get_incidents(conn, limit=limit)

    if not incident_list:
        console.print("[yellow]No incidents found.[/yellow]")
        console.print("Run 'lsa explain --log <logfile>' to analyze logs and create incidents.")
        return

    console.print(f"[bold]Recent Incidents ({len(incident_list)} of {total}):[/bold]")
    console.print()

    for inc in incident_list:
        log_name = Path(inc["log_path"]).name
        node_key = inc["top_node_key"] or "unknown"
        confidence = inc["confidence"]
        conf_str = f"{confidence:.0%}" if confidence else "?"
        timestamp = inc["updated_at"] or inc["created_at"]

        # Truncate long paths
        if len(log_name) > 40:
            log_name = "..." + log_name[-37:]

        console.print(f"[cyan]{log_name}[/cyan]")
        console.print(f"  Node: {node_key} ({conf_str} confidence)")
        console.print(f"  Analyzed: {timestamp}")
        console.print()


if __name__ == "__main__":
    app()
