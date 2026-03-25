"""LSA Web UI — FastAPI application with API endpoints."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="LSA Web UI")

# --- App state (set by create_app before uvicorn.run) ---

_snapshot_path: Path | None = None
_snaproot: Path | None = None


def create_app(snapshot_path: Path | None = None) -> None:
    """Configure app state before server starts."""
    global _snapshot_path, _snaproot
    _snapshot_path = snapshot_path
    from lsa.config import load_user_config
    cfg = load_user_config()
    snaproot = cfg.get("snaproot")
    if snaproot:
        _snaproot = Path(snaproot).expanduser()


def _get_snapshot() -> Path:
    """Get current snapshot path or raise 400."""
    if _snapshot_path is None:
        raise HTTPException(400, "No snapshot selected")
    return _snapshot_path


def _open_connection(snapshot: Path) -> sqlite3.Connection:
    """Open a connection to snapshot DB."""
    from lsa.config import get_db_path
    db_path = get_db_path(snapshot)
    if not db_path.exists():
        raise HTTPException(404, f"No database at {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# --- Static files ---

_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (_static_dir / "index.html").read_text()


# --- Pydantic models ---

class PlanRequest(BaseModel):
    title: str | None = None
    cid: str | None = None
    jobid: str | None = None
    limit: int = 5


class MermaidRequest(BaseModel):
    candidate_index: int = 0


class PromptRequest(BaseModel):
    mode: str = "deep"  # "cursor" | "deep" | "explain"
    error_text: str | None = None
    lang: str = "en"
    candidate_index: int = 0
    scenario: str | None = None  # "incident" | "change_request"
    prompt_input: str | None = None
    include_diagram: bool = False
    save_prompt: bool = False


class NewSnapshotRequest(BaseModel):
    name: str
    pdf_path: str | None = None
    incidents_path: str | None = None
    research_path: str | None = None
    related_path: str | None = None
    prox_path: str | None = None
    control_path: str | None = None
    insert_path: str | None = None


class WorkspaceRequest(BaseModel):
    ticket: str | None = None
    title: str | None = None
    mode: str = "snap"  # "snap" | "ssh"
    candidate_index: int = 0


# --- API: Snapshots ---

@app.get("/api/snapshots")
async def list_snapshots():
    """List available snapshots from snaproot directory."""
    results = []
    seen = set()

    if _snapshot_path and _snapshot_path.is_dir():
        results.append(_build_snapshot_info(_snapshot_path))
        seen.add(_snapshot_path.resolve())

    if _snaproot and _snaproot.is_dir():
        for entry in sorted(_snaproot.iterdir()):
            if entry.is_dir() and entry.resolve() not in seen:
                results.append(_build_snapshot_info(entry))

    return results


def _build_snapshot_info(snap_dir: Path) -> dict:
    """Build snapshot info dict."""
    from lsa.config import get_db_path
    db_path = get_db_path(snap_dir)
    has_db = db_path.exists()
    stats = None
    if has_db:
        try:
            stats = _get_snapshot_stats(snap_dir)
        except Exception:
            stats = None
    # Get directory mtime as date
    try:
        mtime = snap_dir.stat().st_mtime
        date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    except Exception:
        date_str = None

    return {
        "name": snap_dir.name,
        "path": str(snap_dir),
        "has_db": has_db,
        "date": date_str,
        "stats": stats,
    }


def _normalized_contents(artifacts: dict[str, int]) -> dict[str, int]:
    """Normalize artifact kinds to operator-facing families."""
    return {
        "procs": artifacts.get("procs", 0),
        "scripts": artifacts.get("script", 0) + artifacts.get("master", 0),
        "controls": artifacts.get("control", 0),
        "inserts": artifacts.get("insert", 0),
        "docdef": artifacts.get("docdef", 0),
        "logs": artifacts.get("logs_inbox", 0),
        "refs": artifacts.get("refs", 0),
    }


def _get_snapshot_stats(snap_dir: Path) -> dict:
    """Get stats for a snapshot."""
    conn = _open_connection(snap_dir)
    try:
        rows = conn.execute(
            "SELECT kind, COUNT(*) as cnt FROM artifacts GROUP BY kind"
        ).fetchall()
        artifacts = {r["kind"]: r["cnt"] for r in rows}
        total_artifacts = sum(artifacts.values())

        from lsa.graph.builder import get_graph_stats
        graph = get_graph_stats(conn)

        from lsa.db.connection import (
            count_case_cards,
            count_incidents,
            count_message_codes,
            get_incidents,
        )
        incidents = count_incidents(conn)
        case_cards = count_case_cards(conn)
        message_codes = count_message_codes(conn)
        recent_incidents = get_incidents(conn, limit=5)
        recent_case_cards = conn.execute(
            """
            SELECT id, source_path, title, root_cause, fix_summary, created_at, updated_at
            FROM case_cards
            ORDER BY COALESCE(updated_at, created_at) DESC
            LIMIT 5
            """
        ).fetchall()
        contents = _normalized_contents(artifacts)

        return {
            "artifacts": total_artifacts,
            "artifacts_by_kind": artifacts,
            "contents": contents,
            "nodes": graph.get("total_nodes", 0),
            "edges": graph.get("total_edges", 0),
            "incidents": incidents,
            "recent_incidents": recent_incidents,
            "case_cards": case_cards,
            "recent_case_cards": [dict(row) for row in recent_case_cards],
            "message_codes": message_codes,
        }
    finally:
        conn.close()


@app.delete("/api/snapshot")
async def delete_snapshot(path: str = Query(...)):
    """Delete a snapshot directory after validation."""
    global _snapshot_path
    snap = Path(path).resolve()

    if not snap.is_dir():
        raise HTTPException(404, f"Directory not found: {snap}")

    # Safety: only allow deleting from snaproot
    if _snaproot is None:
        raise HTTPException(400, "snaproot not configured")
    if not str(snap).startswith(str(_snaproot.resolve())):
        raise HTTPException(403, "Can only delete snapshots within snaproot")

    # Don't allow deleting the currently active snapshot
    if _snapshot_path and snap == _snapshot_path.resolve():
        _snapshot_path = None

    shutil.rmtree(snap)

    return {"status": "deleted", "path": str(snap)}


@app.post("/api/snapshot/select")
async def select_snapshot(path: str = Query(...)):
    """Select a snapshot for analysis."""
    global _snapshot_path
    snap = Path(path).resolve()
    if not snap.is_dir():
        raise HTTPException(404, f"Directory not found: {snap}")
    from lsa.config import get_db_path
    if not get_db_path(snap).exists():
        raise HTTPException(400, f"No LSA database in {snap}. Run 'lsa scan' first.")
    _snapshot_path = snap
    return {"status": "ok", "snapshot": str(snap)}


_RSYNC_COMMON = [
    "rsync", "-avz", "--timeout=30",
    "--prune-empty-dirs",
    "--exclude=**/.nfs*", "--exclude=**/*.swp",
    "--exclude=**/*.swo", "--exclude=**/*~",
]


@app.post("/api/snapshot/create")
async def create_snapshot(req: NewSnapshotRequest):
    """Create a new snapshot: rsync from production, scan, import. Streams SSE progress."""
    from lsa.config import load_user_config
    cfg = load_user_config()
    rhs_host = cfg.get("rhs_host")
    rhs_user = cfg.get("rhs_user")
    snaproot = cfg.get("snaproot")

    if not rhs_host:
        raise HTTPException(400, "rhs_host not configured in ~/.lsa/config.yaml")
    if not snaproot:
        raise HTTPException(400, "snaproot not configured in ~/.lsa/config.yaml")

    snap_dir = Path(snaproot).expanduser() / f"rhs_snapshot_{req.name}"
    if snap_dir.exists():
        raise HTTPException(400, f"Snapshot 'rhs_snapshot_{req.name}' already exists")

    return StreamingResponse(
        _snapshot_create_stream(req, snap_dir, cfg),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_event(data: dict) -> str:
    """Format a single SSE event."""
    return f"data: {json.dumps(data)}\n\n"


def _copy_optional_source(source: Path, target: Path) -> None:
    """Copy a file or directory into the snapshot."""
    if target.exists():
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)


def _snapshot_create_stream(req: NewSnapshotRequest, snap_dir: Path, cfg: dict):
    """Generator that yields SSE events as snapshot creation progresses."""
    rhs_host = cfg["rhs_host"]
    rhs_user = cfg.get("rhs_user")
    ssh_target = f"{rhs_user}@{rhs_host}" if rhs_user else rhs_host
    pdf_codes = req.pdf_path or cfg.get("pdf_codes_default")
    hist_dir = req.incidents_path or cfg.get("hist_dir_default")
    hist_glob = cfg.get("hist_glob_default")
    research_path = Path(req.research_path).expanduser() if req.research_path else None
    related_path = Path(req.related_path).expanduser() if req.related_path else None
    prox_path = Path(req.prox_path).expanduser() if req.prox_path else None
    control_path = Path(req.control_path).expanduser() if req.control_path else None
    insert_path = Path(req.insert_path).expanduser() if req.insert_path else None

    # Count total steps: 5 rsync + scan + optional enrichments/imports
    total_steps = 5 + 1  # rsync dirs + scan
    if pdf_codes:
        total_steps += 1
    if hist_dir:
        total_steps += 1
    for path in (research_path, related_path, prox_path, control_path, insert_path):
        if path:
            total_steps += 1

    step = 0
    rsync_errors = []

    for subdir in ("master", "procs", "control", "insert", "docdef", "logs_inbox"):
        (snap_dir / subdir).mkdir(parents=True, exist_ok=True)

    rsync_jobs = [
        (
            "master",
            _RSYNC_COMMON + [
                "--include=*/",
                "--include=*.sh", "--include=*.bash", "--include=*.py",
                "--include=*.pl", "--include=*.pm",
                "--exclude=*",
                f"{ssh_target}:/home/master/", f"{snap_dir}/master/",
            ],
        ),
        (
            "procs",
            _RSYNC_COMMON + [
                "--exclude=**/backup/**",
                "--include=*/", "--include=*.procs", "--exclude=*",
                f"{ssh_target}:/home/procs/", f"{snap_dir}/procs/",
            ],
        ),
        (
            "control",
            _RSYNC_COMMON + [
                "--max-size=5m",
                "--exclude=**/*.tif", "--exclude=**/*.tiff", "--exclude=**/*.pdf",
                "--exclude=**/*.zip", "--exclude=**/*.gz", "--exclude=**/*.tar",
                f"{ssh_target}:/home/control/", f"{snap_dir}/control/",
            ],
        ),
        (
            "insert",
            _RSYNC_COMMON + [
                "--max-size=5m",
                "--exclude=**/*.tif", "--exclude=**/*.tiff", "--exclude=**/*.pdf",
                "--exclude=**/*.zip", "--exclude=**/*.gz", "--exclude=**/*.tar",
                f"{ssh_target}:/home/insert/", f"{snap_dir}/insert/",
            ],
        ),
        (
            "docdef",
            _RSYNC_COMMON + [
                "--include=*/", "--include=*.dfa*", "--exclude=*",
                f"{ssh_target}:/home/isis/docdef/", f"{snap_dir}/docdef/",
            ],
        ),
    ]

    for dir_name, cmd in rsync_jobs:
        step += 1
        yield _sse_event({"step": step, "total": total_steps, "label": f"Syncing {dir_name}..."})
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            rsync_errors.append({"dir": dir_name, "error": result.stderr.strip()})

    step += 1
    yield _sse_event({"step": step, "total": total_steps, "label": "Indexing (lsa scan)..."})
    scan_ok = False
    scan_error = None
    try:
        r = subprocess.run(
            ["lsa", "scan", str(snap_dir)],
            capture_output=True, text=True, timeout=600,
        )
        scan_ok = r.returncode == 0
        if not scan_ok:
            scan_error = r.stderr.strip()
    except Exception as e:
        scan_error = str(e)

    import_codes_ok = None
    if pdf_codes:
        step += 1
        yield _sse_event({"step": step, "total": total_steps, "label": "Importing message codes..."})
        try:
            r = subprocess.run(
                ["lsa", "import-codes", str(snap_dir), "--pdf", str(pdf_codes)],
                capture_output=True, text=True, timeout=600,
            )
            import_codes_ok = r.returncode == 0
        except Exception:
            import_codes_ok = False

    import_histories_ok = None
    if hist_dir:
        step += 1
        yield _sse_event({"step": step, "total": total_steps, "label": "Importing histories..."})
        cmd = ["lsa", "import-histories", str(snap_dir), "--path", str(hist_dir)]
        if hist_glob:
            cmd += ["--glob", str(hist_glob)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            import_histories_ok = r.returncode == 0
        except Exception:
            import_histories_ok = False

    optional_copy_results: list[dict[str, Any]] = []
    optional_sources = [
        ("research", research_path, snap_dir / "refs" / "research"),
        ("related", related_path, snap_dir / "refs" / "related"),
        ("prox", prox_path, snap_dir / "refs" / "prox"),
        ("control", control_path, snap_dir / "control" / "_optional"),
        ("insert", insert_path, snap_dir / "insert" / "_optional"),
    ]
    for label, source, target in optional_sources:
        if not source:
            continue
        step += 1
        yield _sse_event({"step": step, "total": total_steps, "label": f"Copying {label} source..."})
        try:
            _copy_optional_source(source, target)
            optional_copy_results.append({"label": label, "ok": True, "target": str(target)})
        except Exception as e:
            optional_copy_results.append({"label": label, "ok": False, "error": str(e)})

    yield _sse_event({
        "step": total_steps,
        "total": total_steps,
        "label": "Done",
        "done": True,
        "status": "created",
        "path": str(snap_dir),
        "path_win": _to_windows_path(str(snap_dir)),
        "name": req.name,
        "rsync_errors": rsync_errors,
        "scan_ok": scan_ok,
        "scan_error": scan_error,
        "import_codes_ok": import_codes_ok,
        "import_histories_ok": import_histories_ok,
        "optional_copy_results": optional_copy_results,
    })


# --- API: Plan ---

_last_intent: Any = None
_last_candidates: list = []


@app.post("/api/plan")
async def plan(req: PlanRequest):
    global _last_intent, _last_candidates
    snapshot = _get_snapshot()
    conn = _open_connection(snapshot)
    try:
        from lsa.analysis.planner import generate_plan, format_plan_json
        intent, candidates = generate_plan(
            conn, snapshot,
            cid=req.cid,
            job_id=req.jobid,
            title=req.title,
            limit=req.limit,
        )
        _last_intent = intent
        _last_candidates = candidates
        result = format_plan_json(intent, candidates, snapshot)
        result["all_candidates"] = [
            {
                "key": c.proc_key,
                "name": c.proc_name,
                "display_name": c.display_name,
                "score": c.score,
                "score_breakdown": c.score_breakdown,
                "files": [
                    {"kind": f.kind, "path": f.path, "abs_path": str(snapshot / f.path)}
                    for f in c.files
                ],
            }
            for c in candidates
        ]
        return result
    finally:
        conn.close()


@app.post("/api/plan/mermaid")
async def plan_mermaid(req: MermaidRequest):
    snapshot = _get_snapshot()
    if not _last_candidates:
        raise HTTPException(400, "No plan generated yet. Call /api/plan first.")
    idx = req.candidate_index
    if idx < 0 or idx >= len(_last_candidates):
        raise HTTPException(
            400, f"candidate_index {idx} out of range (0..{len(_last_candidates) - 1})"
        )
    from lsa.output.mermaid import generate_mermaid, to_mermaid_live_url
    mermaid_code = generate_mermaid(_last_candidates[idx], snapshot)
    return {"mermaid_code": mermaid_code, "live_url": to_mermaid_live_url(mermaid_code)}


# --- API: File ---

@app.get("/api/file")
async def read_file(path: str = Query(...)):
    """Read a file from the snapshot."""
    snapshot = _get_snapshot()
    file_path = (snapshot / path).resolve()
    if not str(file_path).startswith(str(snapshot.resolve())):
        raise HTTPException(403, "Path traversal not allowed")
    if not file_path.exists():
        raise HTTPException(404, f"File not found: {path}")
    if not file_path.is_file():
        raise HTTPException(400, f"Not a file: {path}")

    try:
        content = file_path.read_text(errors="replace")
    except Exception as e:
        raise HTTPException(500, f"Cannot read file: {e}")

    rel = file_path.relative_to(snapshot.resolve())
    kind = rel.parts[0] if rel.parts else "unknown"

    return {
        "path": str(rel),
        "kind": kind,
        "content": content,
        "size": file_path.stat().st_size,
    }


# --- API: Prompt ---

def _operator_scope_summary(candidate: Any) -> dict[str, Any]:
    """Build an operator-facing summary of a selected candidate."""
    files = getattr(candidate, "files", []) or []
    grouped = {
        "procs": 0,
        "scripts": 0,
        "controls": 0,
        "inserts": 0,
        "docdef": 0,
        "other": 0,
    }
    runs_scripts: list[str] = []
    controls: list[str] = []
    docdefs: list[str] = []
    for f in files:
        if f.kind == "procs":
            grouped["procs"] += 1
        elif f.kind in {"script", "master"}:
            grouped["scripts"] += 1
            if getattr(f, "source", "") == "RUNS_edge":
                runs_scripts.append(f.path)
        elif f.kind == "control":
            grouped["controls"] += 1
            controls.append(f.path)
        elif f.kind == "insert":
            grouped["inserts"] += 1
        elif f.kind == "docdef":
            grouped["docdef"] += 1
            docdefs.append(f.path)
        else:
            grouped["other"] += 1

    read_order = [
        f"proc: {getattr(candidate, 'proc_name', 'unknown')}",
        *[f"script: {Path(path).name}" for path in runs_scripts[:3]],
        *[f"control: {Path(path).name}" for path in controls[:2]],
        *[f"docdef: {Path(path).name}" for path in docdefs[:1]],
    ]
    return {
        "file_count": len(files),
        "counts": grouped,
        "runs_scripts": runs_scripts[:5],
        "controls": controls[:5],
        "docdefs": docdefs[:5],
        "read_order": read_order[:6],
    }


def _save_prompt_text(snapshot: Path, proc_name: str, scenario: str, text: str) -> str:
    """Persist a generated prompt inside the snapshot."""
    prompts_dir = snapshot / ".lsa" / "ai_prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_path = prompts_dir / f"{proc_name}_{scenario}_{ts}.md"
    saved_path.write_text(text, encoding="utf-8")
    return str(saved_path)


def _build_scenario_prompt(
    snapshot: Path,
    candidate: Any,
    *,
    lang: str,
    scenario: str,
    prompt_input: str,
    include_diagram: bool,
) -> dict[str, Any]:
    """Build an operator-oriented prompt from the current scope."""
    scope = _operator_scope_summary(candidate)
    file_lines = [f"- [{f.kind}] {snapshot / f.path}" for f in candidate.files]
    mermaid_code = None
    diagram_block = ""
    if include_diagram:
        from lsa.output.mermaid import generate_mermaid
        mermaid_code = generate_mermaid(candidate, snapshot)
        diagram_block = "\n".join([
            "",
            "## Dependency diagram (Mermaid)",
            "",
            "```mermaid",
            mermaid_code,
            "```",
        ])

    if lang == "ru":
        if scenario == "incident":
            title = "Incident analysis"
            instruction = (
                "Ты внешний инженер-аналитик. Используй snapshot, текущий scope и ключевые файлы ниже, "
                "чтобы определить наиболее вероятную корневую причину инцидента. "
                "Нужен ответ с root cause, evidence, что проверять дальше, и короткий ticket-ready fix или escalation."
            )
            input_title = "Ошибка / лог / текст тикета"
        else:
            title = "Change request analysis"
            instruction = (
                "Ты внешний инженер-аналитик. Используй snapshot, текущий scope и ключевые файлы ниже, "
                "чтобы оценить impact change request, указать затронутые области, риски, план изменений и проверки."
            )
            input_title = "Описание доработки"
    else:
        if scenario == "incident":
            title = "Incident analysis"
            instruction = (
                "You are an external engineer analyzing an incident. Use the snapshot, current scope, and key files below "
                "to determine the most probable root cause. Return root cause, evidence, next checks, and a short ticket-ready fix or escalation."
            )
            input_title = "Error / log / ticket text"
        else:
            title = "Change request analysis"
            instruction = (
                "You are an external engineer analyzing a change request. Use the snapshot, current scope, and key files below "
                "to assess impact, affected areas, implementation plan, risks, and validation steps."
            )
            input_title = "Requested change"

    prompt_text = "\n".join([
        f"# {title}",
        "",
        instruction,
        "",
        "## Current scope",
        f"- Snapshot: `{snapshot}`",
        f"- Proc: `{candidate.proc_name}`",
        f"- Candidate: `{candidate.display_name}`",
        f"- Files in scope: {scope['file_count']}",
        (
            "- Scope composition: "
            f"procs {scope['counts']['procs']}, scripts {scope['counts']['scripts']}, "
            f"controls {scope['counts']['controls']}, inserts {scope['counts']['inserts']}, "
            f"docdef {scope['counts']['docdef']}"
        ),
        "",
        "## Entry points",
        *([f"- {line}" for line in scope["read_order"]] or ["- No obvious entry points found"]),
        "",
        f"## {input_title}",
        "```",
        prompt_input.strip() or "(none provided)",
        "```",
        "",
        "## Files to open",
        *file_lines,
        diagram_block,
        "",
        "## Expected answer",
        "- Most probable root cause or main impact area",
        "- Evidence from the provided files and input",
        "- Affected files and why they matter",
        "- Verification checklist",
        "- Proposed fix or change plan",
    ])
    return {
        "prompt_text": prompt_text,
        "scope_summary": scope,
        "mermaid_code": mermaid_code,
    }

@app.post("/api/prompt")
async def generate_prompt(req: PromptRequest):
    snapshot = _get_snapshot()

    if req.scenario:
        if not _last_candidates:
            raise HTTPException(400, "No plan generated yet.")
        idx = req.candidate_index
        if idx < 0 or idx >= len(_last_candidates):
            raise HTTPException(400, "candidate_index out of range")
        candidate = _last_candidates[idx]
        scenario = req.scenario if req.scenario in {"incident", "change_request"} else "incident"
        payload = _build_scenario_prompt(
            snapshot,
            candidate,
            lang=req.lang,
            scenario=scenario,
            prompt_input=req.prompt_input or req.error_text or "",
            include_diagram=req.include_diagram,
        )
        saved_path = None
        if req.save_prompt:
            saved_path = _save_prompt_text(snapshot, candidate.proc_name, scenario, payload["prompt_text"])
        return {
            "prompt_text": payload["prompt_text"],
            "saved_path": saved_path,
            "scope_summary": payload["scope_summary"],
            "scenario": scenario,
            "impl_mode": "scope_prompt_v1",
            "mermaid_included": bool(payload["mermaid_code"]),
        }

    if req.mode == "cursor":
        if not _last_intent or not _last_candidates:
            raise HTTPException(400, "No plan generated yet.")
        from lsa.analysis.planner import format_cursor_prompt
        text = format_cursor_prompt(_last_intent, _last_candidates, snapshot, lang=req.lang)
        if req.error_text:
            text += f"\n\n---\n\n## Error from ticket\n\n```\n{req.error_text}\n```\n"
        return {"prompt_text": text, "saved_path": None}

    elif req.mode == "deep":
        if not _last_candidates:
            raise HTTPException(400, "No plan generated yet.")
        idx = req.candidate_index
        if idx < 0 or idx >= len(_last_candidates):
            raise HTTPException(400, "candidate_index out of range")
        from lsa.output.deep_prompt import generate_deep_prompt
        candidate = _last_candidates[idx]
        text = generate_deep_prompt(candidate, snapshot, lang=req.lang)
        if req.error_text:
            text += f"\n\n---\n\n## Error from ticket\n\n```\n{req.error_text}\n```\n"

        prompts_dir = snapshot / ".lsa" / "ai_prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        parts = []
        if _last_intent and _last_intent.cid:
            parts.append(_last_intent.cid)
        if _last_intent and _last_intent.job_id:
            parts.append(_last_intent.job_id)
        if not parts:
            parts.append(candidate.proc_name)
        parts.append(datetime.now().strftime("%Y%m%d_%H%M%S"))
        filename = "_".join(parts) + ".md"
        saved_path = prompts_dir / filename
        saved_path.write_text(text, encoding="utf-8")

        return {"prompt_text": text, "saved_path": str(saved_path)}

    elif req.mode == "explain":
        if not req.error_text:
            raise HTTPException(400, "error_text is required for explain mode")
        conn = _open_connection(snapshot)
        try:
            text = _run_explain_pipeline(conn, snapshot, req.error_text, req.lang)
            return {"prompt_text": text, "saved_path": None}
        finally:
            conn.close()

    else:
        raise HTTPException(400, f"Unknown mode: {req.mode}")


def _run_explain_pipeline(
    conn: sqlite3.Connection, snapshot: Path, error_text: str, lang: str,
) -> str:
    """Run the explain pipeline on raw error text."""
    from lsa.parsers import parse_log_file
    from lsa.graph import match_log_to_node, get_node_neighbors
    from lsa.graph.matching import get_related_files
    from lsa.analysis import generate_hypotheses, find_similar_cases
    from lsa.analysis.hypotheses import get_default_hypotheses
    from lsa.db.connection import get_message_codes_batch
    from lsa.output.context_pack import generate_context_pack
    from lsa.output.prompt_pack import generate_ai_prompt

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".log", delete=False, encoding="utf-8",
    ) as f:
        f.write(error_text)
        tmp_path = Path(f.name)

    try:
        log_analysis = parse_log_file(tmp_path)
        top_node, confidence, _ = match_log_to_node(conn, log_analysis, tmp_path)

        neighbors = None
        related_files = []
        if top_node:
            neighbors = get_node_neighbors(conn, top_node["id"])
            related_files = get_related_files(conn, top_node["id"], snapshot)

        hypotheses = generate_hypotheses(
            log_analysis.error_signals, log_analysis=log_analysis,
        )
        if not hypotheses:
            hypotheses = get_default_hypotheses()

        similar_cases = find_similar_cases(conn, log_analysis.error_codes, related_files)
        decoded_codes = get_message_codes_batch(conn, log_analysis.error_codes)

        context_pack = generate_context_pack(
            log_path=tmp_path,
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

        return generate_ai_prompt(context_pack, tmp_path, log_analysis, lang=lang)
    finally:
        tmp_path.unlink(missing_ok=True)


# --- API: Workspace ---

def _to_windows_path(linux_path: str) -> str | None:
    """Convert a Linux path to a Windows UNC path if running in WSL."""
    distro = os.environ.get("WSL_DISTRO_NAME")
    if not distro:
        return None
    win_subpath = linux_path.replace("/", "\\")
    return f"\\\\wsl.localhost\\{distro}{win_subpath}"


_REMOTE_BASE: dict[str, str] = {
    "procs": "/home/procs",
    "script": "/home/master",
    "master": "/home/master",
    "insert": "/home/insert",
    "control": "/home/control",
    "docdef": "/home/isis/docdef",
}

_KIND_TO_CODE_DIR: dict[str, str] = {
    "procs": "procs",
    "script": "master",
    "master": "master",
    "insert": "insert",
    "control": "control",
    "docdef": "docdef",
}


@app.post("/api/workspace/create")
async def create_workspace(req: WorkspaceRequest):
    """Create a workspace directory populated with candidate files. Streams SSE progress."""
    snapshot = _get_snapshot()

    if not _last_candidates:
        raise HTTPException(400, "No plan generated yet. Call /api/plan first.")

    idx = req.candidate_index
    if idx < 0 or idx >= len(_last_candidates):
        raise HTTPException(
            400, f"candidate_index {idx} out of range (0..{len(_last_candidates) - 1})"
        )

    from lsa.config import load_user_config
    cfg = load_user_config()
    workroot = Path(cfg.get("workroot", "~/workspaces")).expanduser()
    rhs_host = cfg.get("rhs_host")
    rhs_user = cfg.get("rhs_user")

    if req.mode == "ssh" and not rhs_host:
        raise HTTPException(400, "rhs_host not configured in ~/.lsa/config.yaml")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if req.ticket:
        ws_name = f"{req.ticket}_{timestamp}"
    elif req.title:
        ws_name = f"{req.title}_{timestamp}"
    else:
        ws_name = f"ws_{timestamp}"

    ws_path = workroot / ws_name
    candidate = _last_candidates[idx]

    return StreamingResponse(
        _workspace_create_stream(
            ws_path, ws_name, snapshot, candidate, req, cfg, rhs_host, rhs_user,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _workspace_create_stream(
    ws_path: Path, ws_name: str, snapshot: Path, candidate, req, cfg: dict,
    rhs_host: str | None, rhs_user: str | None,
):
    """Generator that yields SSE events as workspace creation progresses."""
    ssh_target = f"{rhs_user}@{rhs_host}" if rhs_user else (rhs_host or "")
    file_count = len(candidate.files)
    # Steps: create dirs (1) + copy each file + generate scripts (1)
    total_steps = 1 + file_count + 1
    step = 0

    # Step 1: create directory structure
    step += 1
    yield _sse_event({"step": step, "total": total_steps, "label": "Creating directory structure..."})

    ws_path.mkdir(parents=True, exist_ok=True)
    for subdir in ("logs", "process", "samples", "prj", "mapping", "notes", "scripts", "mermaid"):
        (ws_path / subdir).mkdir(exist_ok=True)
    code_dir = ws_path / "code"
    for subdir in ("procs", "master", "insert", "control", "docdef", "other"):
        (code_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Steps 2..N: copy files
    files_copied = 0
    copy_errors = []

    for f in candidate.files:
        step += 1
        kind = f.kind
        rel_path = f.path
        abs_path = snapshot / rel_path

        yield _sse_event({
            "step": step, "total": total_steps,
            "label": f"Copying {Path(rel_path).name}...",
        })

        code_subdir = _KIND_TO_CODE_DIR.get(kind, "other")
        dst_dir = code_dir / code_subdir
        parts = Path(rel_path).parts
        subpath = str(Path(*parts[1:])) if len(parts) > 1 else parts[0]
        dst_file = dst_dir / Path(subpath).name
        dst_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            if req.mode == "snap":
                if not abs_path.exists():
                    copy_errors.append({"file": rel_path, "error": "source not found in snapshot"})
                    continue
                shutil.copy2(abs_path, dst_file)
            else:
                remote_base = _REMOTE_BASE.get(kind, f"/home/{kind}")
                remote_src = f"{ssh_target}:{remote_base}/{subpath}"
                r = subprocess.run(
                    ["rsync", "-az", "--timeout=30", remote_src, str(dst_file)],
                    capture_output=True, text=True, timeout=600,
                )
                if r.returncode != 0:
                    copy_errors.append({"file": rel_path, "error": r.stderr.strip()})
                    continue
            files_copied += 1
        except Exception as exc:
            copy_errors.append({"file": rel_path, "error": str(exc)})

    # Final step: generate scripts and notes
    step += 1
    yield _sse_event({"step": step, "total": total_steps, "label": "Generating scripts..."})

    pull_script_path = ws_path / "scripts" / "pull_from_rhs.sh"
    pull_lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    if rhs_host:
        pull_lines.append(f'RHS="{ssh_target}"')
        pull_lines.append("")
        for f in candidate.files:
            kind = f.kind
            parts = Path(f.path).parts
            subpath = str(Path(*parts[1:])) if len(parts) > 1 else parts[0]
            remote_base = _REMOTE_BASE.get(kind, f"/home/{kind}")
            code_subdir = _KIND_TO_CODE_DIR.get(kind, "other")
            dst = f'"{ws_path}/code/{code_subdir}/{Path(subpath).name}"'
            pull_lines.append(f'rsync -az --timeout=30 "$RHS":{remote_base}/{subpath} {dst}')
    pull_script_path.write_text("\n".join(pull_lines) + "\n", encoding="utf-8")
    pull_script_path.chmod(0o755)

    note_name = req.ticket or req.title or ws_name
    note_path = ws_path / "notes" / f"{note_name}.md"
    note_lines = [
        f"# {note_name}",
        "",
        f"Workspace: `{ws_path}`",
        f"Snapshot: `{snapshot}`",
        f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Candidate: {candidate.proc_name}",
        f"Mode: {req.mode}",
        "",
        "## Files",
        "",
    ]
    for f in candidate.files:
        note_lines.append(f"- `{f.path}`")
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    plan_json_path = ws_path / "logs" / "plan.json"
    plan_data = {
        "candidate_index": req.candidate_index,
        "proc_key": candidate.proc_key,
        "proc_name": candidate.proc_name,
        "score": candidate.score,
        "files": [{"kind": f.kind, "path": f.path} for f in candidate.files],
    }
    plan_json_path.write_text(json.dumps(plan_data, indent=2), encoding="utf-8")

    win_path = _to_windows_path(str(ws_path))

    yield _sse_event({
        "step": total_steps,
        "total": total_steps,
        "label": "Done",
        "done": True,
        "status": "created",
        "workspace": str(ws_path),
        "workspace_win": win_path,
        "name": ws_name,
        "files_copied": files_copied,
        "copy_errors": copy_errors,
        "pull_script": str(pull_script_path),
    })


# --- API: Search ---

def _search_kind_clause(kind: str) -> tuple[str, tuple[Any, ...]]:
    """Map UI kind filter to SQL clause."""
    kind = (kind or "all").lower()
    if kind == "all":
        return "", ()
    if kind == "scripts":
        return " AND a.kind IN (?, ?)", ("script", "master")
    mapping = {
        "procs": ("procs",),
        "controls": ("control",),
        "inserts": ("insert",),
        "docdef": ("docdef",),
        "logs": ("logs_inbox",),
        "refs": ("refs",),
    }
    values = mapping.get(kind)
    if not values:
        return "", ()
    placeholders = ", ".join("?" for _ in values)
    return f" AND a.kind IN ({placeholders})", tuple(values)


def _current_scope_paths(snapshot: Path, candidate_index: int) -> set[str]:
    """Return the current candidate's file paths if a plan is available."""
    if not _last_candidates:
        return set()
    if candidate_index < 0 or candidate_index >= len(_last_candidates):
        return set()
    return {str((snapshot / f.path).resolve().relative_to(snapshot.resolve())) for f in _last_candidates[candidate_index].files}


def _search_message_codes(conn: sqlite3.Connection, query: str, limit: int) -> list[dict]:
    """Search imported message codes from PDF knowledge base."""
    pattern = f"%{query}%"
    rows = conn.execute(
        """
        SELECT code, severity, title, body, source_path
        FROM message_codes
        WHERE code LIKE ? OR title LIKE ? OR body LIKE ?
        ORDER BY CASE WHEN code LIKE ? THEN 0 ELSE 1 END, code
        LIMIT ?
        """,
        (pattern, pattern, pattern, pattern, limit),
    ).fetchall()
    return [
        {
            "path": f"message_codes/{row['code']}",
            "kind": "message_code",
            "snippet": row["body"][:180] if row["body"] else row["title"],
            "match_type": "knowledge",
            "preview_title": f"{row['code']} ({row['severity']})",
            "preview_content": "\n".join(filter(None, [
                f"Code: {row['code']}",
                f"Severity: {row['severity']}",
                f"Title: {row['title']}" if row["title"] else None,
                "",
                row["body"],
                "",
                f"Source PDF: {row['source_path']}",
            ])),
        }
        for row in rows
    ]


def _search_case_cards(conn: sqlite3.Connection, query: str, limit: int) -> list[dict]:
    """Search imported incident history case cards."""
    pattern = f"%{query}%"
    rows = conn.execute(
        """
        SELECT id, source_path, title, root_cause, fix_summary, updated_at, created_at
        FROM case_cards
        WHERE source_path LIKE ?
           OR title LIKE ?
           OR root_cause LIKE ?
           OR fix_summary LIKE ?
        ORDER BY COALESCE(updated_at, created_at) DESC
        LIMIT ?
        """,
        (pattern, pattern, pattern, pattern, limit),
    ).fetchall()
    return [
        {
            "path": f"case_cards/{row['id']}",
            "kind": "case_card",
            "snippet": row["root_cause"] or row["fix_summary"] or row["title"] or row["source_path"],
            "match_type": "knowledge",
            "preview_title": row["title"] or f"Case card {row['id']}",
            "preview_content": "\n".join(filter(None, [
                f"Source: {row['source_path']}" if row["source_path"] else None,
                f"Updated: {row['updated_at'] or row['created_at']}",
                "",
                f"Title: {row['title']}" if row["title"] else None,
                f"Root cause: {row['root_cause']}" if row["root_cause"] else None,
                f"Fix summary: {row['fix_summary']}" if row["fix_summary"] else None,
            ])),
        }
        for row in rows
    ]


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    mode: str = Query("content"),
    scope: str = Query("snapshot"),
    kind: str = Query("all"),
    space: str = Query("all"),
    candidate_index: int = Query(0, ge=0),
):
    """Search artifacts by path and content."""
    snapshot = _get_snapshot()
    conn = _open_connection(snapshot)
    try:
        scope_paths = _current_scope_paths(snapshot, candidate_index) if scope == "current" else set()
        file_results: list[dict[str, Any]] = []
        knowledge_results: list[dict[str, Any]] = []

        if space in {"all", "files"}:
            if mode == "path":
                file_results = _search_path_only(conn, q, limit, kind=kind, scope_paths=scope_paths)
            else:
                file_results = _search_fts(conn, q, limit, kind=kind, scope_paths=scope_paths)
                if not file_results:
                    file_results = _search_like(conn, q, limit, kind=kind, scope_paths=scope_paths)

        if space in {"all", "knowledge"}:
            knowledge_results = _search_message_codes(conn, q, limit) + _search_case_cards(conn, q, limit)

        if space == "files":
            results = file_results[:limit]
        elif space == "knowledge":
            results = knowledge_results[:limit]
        else:
            knowledge_limit = max(5, limit // 2)
            file_limit = max(5, limit - knowledge_limit)
            results = [*knowledge_results[:knowledge_limit], *file_results[:file_limit]][:limit]
        return results
    finally:
        conn.close()


def _search_fts(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    *,
    kind: str = "all",
    scope_paths: set[str] | None = None,
) -> list[dict]:
    """Full-text search using FTS5 virtual table."""
    try:
        kind_clause, kind_params = _search_kind_clause(kind)
        params: list[Any] = [query]
        scope_clause = ""
        if scope_paths:
            placeholders = ", ".join("?" for _ in scope_paths)
            scope_clause = f" AND a.path IN ({placeholders})"
            params.extend(sorted(scope_paths))
        params.extend(kind_params)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT a.path, a.kind,
                   snippet(artifacts_fts, 1, '>>>', '<<<', '...', 30) as snippet
            FROM artifacts_fts
            JOIN artifacts a ON artifacts_fts.rowid = a.id
            WHERE artifacts_fts MATCH ?
            {scope_clause}
            {kind_clause}
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        return [{"path": r["path"], "kind": r["kind"], "snippet": r["snippet"], "match_type": "content"} for r in rows]
    except Exception:
        return []


def _search_like(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    *,
    kind: str = "all",
    scope_paths: set[str] | None = None,
) -> list[dict]:
    """Fallback LIKE search on paths and content."""
    pattern = f"%{query}%"
    kind_clause, kind_params = _search_kind_clause(kind)
    params: list[Any] = [pattern, pattern]
    scope_clause = ""
    if scope_paths:
        placeholders = ", ".join("?" for _ in scope_paths)
        scope_clause = f" AND path IN ({placeholders})"
        params.extend(sorted(scope_paths))
    params.extend(kind_params)
    params.extend([pattern, limit])
    rows = conn.execute(
        f"""
        SELECT path, kind, substr(text_content, 1, 100) as snippet
        FROM artifacts
        WHERE (path LIKE ? OR text_content LIKE ?)
        {scope_clause}
        {kind_clause.replace('a.kind', 'kind')}
        ORDER BY
            CASE WHEN path LIKE ? THEN 0 ELSE 1 END,
            path
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()
    return [{"path": r["path"], "kind": r["kind"], "snippet": r["snippet"], "match_type": "content"} for r in rows]


def _search_path_only(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    *,
    kind: str = "all",
    scope_paths: set[str] | None = None,
) -> list[dict]:
    """Search only on artifact paths."""
    pattern = f"%{query}%"
    kind_clause, kind_params = _search_kind_clause(kind)
    params: list[Any] = [pattern]
    scope_clause = ""
    if scope_paths:
        placeholders = ", ".join("?" for _ in scope_paths)
        scope_clause = f" AND path IN ({placeholders})"
        params.extend(sorted(scope_paths))
    params.extend(kind_params)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT path, kind, substr(path, 1, 120) as snippet
        FROM artifacts
        WHERE path LIKE ?
        {scope_clause}
        {kind_clause.replace('a.kind', 'kind')}
        ORDER BY path
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()
    return [{"path": r["path"], "kind": r["kind"], "snippet": r["snippet"], "match_type": "path"} for r in rows]


# --- API: Stats ---

@app.get("/api/stats")
async def stats():
    """Get full snapshot statistics."""
    snapshot = _get_snapshot()
    return _get_snapshot_stats(snapshot)
