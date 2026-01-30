"""Plan / Bundle logic for LSA.

Given a CID, job ID, and/or free-text title, finds the most likely proc(s)
and collects related files (scripts, inserts, controls, DFAs) into a bundle
that can be opened in an IDE.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class PlanIntent:
    cid: str | None = None            # "wccu" (lowercased)
    job_id: str | None = None         # "ds1"
    letter_number: str | None = None  # "014" (3-digit normalized)
    title_keywords: list[str] = field(default_factory=list)
    raw_title: str | None = None


@dataclass
class BundleFile:
    path: str       # snapshot-relative ("procs/wccuds1.procs")
    kind: str       # "procs", "script", "insert", "control", "docdef"
    source: str     # "proc_file", "RUNS_edge", "READS_edge", etc.


@dataclass
class BundleCandidate:
    proc_key: str              # "proc:wccuds1"
    proc_name: str             # "wccuds1"
    display_name: str          # "WCCU - Papyrus"
    score: float = 0.0
    score_breakdown: list[tuple[str, float]] = field(default_factory=list)
    files: list[BundleFile] = field(default_factory=list)


# ── Stopwords for title keyword extraction ───────────────────────────────────

_STOPWORDS = frozenset({
    "the", "and", "for", "with", "from", "that", "this", "are", "was",
    "has", "have", "had", "not", "but", "its", "our", "all", "new",
    "update", "letter", "monthly", "daily", "weekly", "run", "job",
})


# ── Title parsing ────────────────────────────────────────────────────────────

_CID_RE = re.compile(r"\b([A-Z]{4})\b")
_LETTER_RE = re.compile(r"(?:Letter\s*|DL)(\d{2,3})\b", re.IGNORECASE)


def parse_title(title: str) -> tuple[str | None, str | None, list[str]]:
    """Parse free-text title into (cid, letter_number, keywords).

    CID: first 4-letter uppercase token → lowercase.
    Letter number: ``Letter 14`` or ``DL014`` → zero-padded to 3 digits.
    Keywords: remaining tokens ≥3 chars, excluding stopwords.
    """
    cid: str | None = None
    letter_number: str | None = None

    m = _CID_RE.search(title)
    if m:
        cid = m.group(1).lower()

    m = _LETTER_RE.search(title)
    if m:
        letter_number = m.group(1).zfill(3)

    # Keywords: split on non-alphanumeric, filter short/stopwords
    tokens = re.split(r"[^A-Za-z0-9]+", title)
    keywords = [
        t.lower()
        for t in tokens
        if len(t) >= 3 and t.lower() not in _STOPWORDS
    ]

    return cid, letter_number, keywords


# ── Intent builder ───────────────────────────────────────────────────────────

def build_intent(
    cid: str | None = None,
    job_id: str | None = None,
    title: str | None = None,
) -> PlanIntent:
    """Build a PlanIntent merging explicit args with title-parsed values.

    Explicit args always win over title-parsed values.
    """
    title_cid: str | None = None
    title_letter: str | None = None
    title_keywords: list[str] = []

    if title:
        title_cid, title_letter, title_keywords = parse_title(title)

    return PlanIntent(
        cid=(cid.lower() if cid else title_cid),
        job_id=(job_id.lower() if job_id else None),
        letter_number=title_letter,
        title_keywords=title_keywords,
        raw_title=title,
    )


# ── Candidate search ────────────────────────────────────────────────────────

def find_candidates(
    conn: sqlite3.Connection,
    intent: PlanIntent,
) -> list[BundleCandidate]:
    """Find proc nodes matching the intent."""
    candidates: list[BundleCandidate] = []

    if intent.cid and intent.job_id:
        # Exact key lookup
        exact_key = f"proc:{intent.cid}{intent.job_id}"
        rows = conn.execute(
            "SELECT id, key, display_name, canonical_path FROM nodes WHERE type='proc' AND key = ?",
            (exact_key,),
        ).fetchall()
        for row in rows:
            candidates.append(BundleCandidate(
                proc_key=row["key"],
                proc_name=row["key"].split(":", 1)[1],
                display_name=row["display_name"],
            ))

        # Also add prefix matches (other jobs for same CID)
        prefix = f"proc:{intent.cid}%"
        rows = conn.execute(
            "SELECT id, key, display_name, canonical_path FROM nodes WHERE type='proc' AND key LIKE ? AND key != ?",
            (prefix, exact_key),
        ).fetchall()
        for row in rows:
            candidates.append(BundleCandidate(
                proc_key=row["key"],
                proc_name=row["key"].split(":", 1)[1],
                display_name=row["display_name"],
            ))

    elif intent.cid:
        # Prefix match only
        prefix = f"proc:{intent.cid}%"
        rows = conn.execute(
            "SELECT id, key, display_name, canonical_path FROM nodes WHERE type='proc' AND key LIKE ?",
            (prefix,),
        ).fetchall()
        for row in rows:
            candidates.append(BundleCandidate(
                proc_key=row["key"],
                proc_name=row["key"].split(":", 1)[1],
                display_name=row["display_name"],
            ))

    if not candidates and intent.title_keywords:
        # Fallback: keyword search in procs parsed_json
        rows = conn.execute(
            "SELECT proc_name, parsed_json FROM procs",
        ).fetchall()
        for row in rows:
            pj = (row["parsed_json"] or "").lower()
            if any(kw in pj for kw in intent.title_keywords):
                # Find corresponding node
                node = conn.execute(
                    "SELECT id, key, display_name FROM nodes WHERE key = ?",
                    (f"proc:{row['proc_name']}",),
                ).fetchone()
                if node:
                    candidates.append(BundleCandidate(
                        proc_key=node["key"],
                        proc_name=row["proc_name"],
                        display_name=node["display_name"],
                    ))

    return candidates


# ── Control & DFA helpers ────────────────────────────────────────────────────

# Matches: format_dfa="WCCUDL014", ind_pdf_format_dfa = WCCUDL014, etc.
_FORMAT_DFA_RE = re.compile(
    r"\w*format_dfa\s*[=:]\s*[\"']?(\w+)[\"']?", re.IGNORECASE,
)

# DFA token: uppercase CID prefix followed by letters/digits (e.g. WCCUDL014)
_DFA_TOKEN_RE = re.compile(r"\b([A-Z]{4}[A-Z0-9]{2,})\b")


def _extract_dfa_codes_from_control(content: str) -> list[str]:
    """Extract unique DFA codes from control file content.

    Parses lines like ``format_dfa="WCCUDL014"`` and all ``*_format_dfa`` variants.
    """
    codes: list[str] = []
    seen: set[str] = set()
    for m in _FORMAT_DFA_RE.finditer(content):
        code = m.group(1).upper()
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _extract_dfa_tokens_from_procs(parsed_json: str, cid: str) -> list[str]:
    """Extract DFA-like tokens from procs parsed_json that start with CID prefix.

    E.g. for cid="wccu", finds WCCUDL014, WCCUDL015.
    """
    prefix = cid.upper()
    codes: list[str] = []
    seen: set[str] = set()
    for m in _DFA_TOKEN_RE.finditer(parsed_json):
        token = m.group(1)
        if token.startswith(prefix) and token not in seen:
            seen.add(token)
            codes.append(token)
    return codes


def _filter_dfa_by_letter(codes: list[str], letter_number: str | None) -> list[str]:
    """Keep only DFA codes matching the intended letter number.

    When letter_number is set (e.g. "014"), excludes codes that don't end
    with that 3-digit suffix — reduces noise from sibling letters mentioned
    in the same .procs file.
    """
    if not letter_number:
        return codes
    return [c for c in codes if c[-3:] == letter_number]


def _resolve_dfa(
    conn: sqlite3.Connection,
    dfa_code: str,
    source: str,
    candidate: BundleCandidate,
    seen_paths: set[str],
) -> None:
    """Resolve a DFA code to docdef artifact(s) and add to candidate files."""
    # Accept .dfa and any extension starting with .dfa (case-insensitive path match)
    rows = conn.execute(
        "SELECT path FROM artifacts WHERE kind = 'docdef' AND UPPER(path) LIKE ?",
        (f"%{dfa_code}%",),
    ).fetchall()
    for row in rows:
        if row["path"] not in seen_paths:
            seen_paths.add(row["path"])
            candidate.files.append(BundleFile(
                path=row["path"],
                kind="docdef",
                source=source,
            ))


def _select_controls(
    all_rows: list,
    proc_name: str,
    intent: PlanIntent,
) -> list:
    """Select the best-matching control files for a candidate proc.

    Priority:
    1. Controls whose basename shares the job-family prefix with the proc
       (e.g. ``wccudl`` for proc ``wccudla``).
    2. If letter_number is set, prefer controls containing that number
       (e.g. ``014``).
    3. Fall back to all CID-matched controls only if nothing better found.
    """
    if not all_rows:
        return []

    # Derive job-family prefix: proc_name minus trailing letter(s)
    # e.g. "wccudla" → "wccudl", "wccuds1" → "wccuds"
    job_family = _job_family_prefix(proc_name)

    # Tier 1: job-family prefix match
    family_rows = [r for r in all_rows if job_family and job_family in r["path"].lower()]

    # If no family match, this proc has no relevant controls — avoid noise
    if not family_rows:
        return []

    # Tier 2: within family, prefer letter_number match
    if intent.letter_number:
        letter_rows = [r for r in family_rows if intent.letter_number in r["path"]]
        if letter_rows:
            return letter_rows

    return family_rows


def _job_family_prefix(proc_name: str) -> str:
    """Derive the job-family prefix from a proc name.

    Strips the trailing variant suffix: either trailing digits,
    or (if no digits) one trailing letter.
    E.g. "wccudla" → "wccudl", "wccuds1" → "wccuds", "bkfnds1" → "bkfnds".
    If the name is <= 4 chars (just CID), return as-is.
    """
    if len(proc_name) <= 4:
        return proc_name
    # Strip trailing digits (e.g. "wccuds1" → "wccuds")
    stripped = proc_name.rstrip("0123456789")
    if stripped != proc_name and len(stripped) >= 5:
        # Digits were removed — that's the variant suffix
        return stripped
    # No digits stripped: remove one trailing letter if long enough
    # (handles variant letters like "wccudla" → "wccudl")
    if len(proc_name) > 5:
        return proc_name[:-1]
    return proc_name


# ── Bundle builder ───────────────────────────────────────────────────────────

def build_bundle(
    conn: sqlite3.Connection,
    candidate: BundleCandidate,
    snapshot_path: Path,
    intent: PlanIntent,
) -> None:
    """Populate candidate.files with all related files."""
    # 1. Add .procs file
    candidate.files.append(BundleFile(
        path=f"procs/{candidate.proc_name}.procs",
        kind="procs",
        source="proc_file",
    ))

    # Get node id
    node = conn.execute(
        "SELECT id FROM nodes WHERE key = ?", (candidate.proc_key,)
    ).fetchone()
    if not node:
        return
    node_id = node["id"]

    # 2. RUNS edges → scripts
    runs = conn.execute(
        "SELECT n.canonical_path, n.key FROM edges e JOIN nodes n ON e.dst = n.id "
        "WHERE e.src = ? AND e.rel_type = 'RUNS'",
        (node_id,),
    ).fetchall()
    for row in runs:
        if row["canonical_path"]:
            candidate.files.append(BundleFile(
                path=row["canonical_path"],
                kind="script",
                source="RUNS_edge",
            ))

    # 3. READS edges → inserts
    reads = conn.execute(
        "SELECT n.canonical_path, n.key FROM edges e JOIN nodes n ON e.dst = n.id "
        "WHERE e.src = ? AND e.rel_type = 'READS'",
        (node_id,),
    ).fetchall()
    for row in reads:
        if row["canonical_path"]:
            candidate.files.append(BundleFile(
                path=row["canonical_path"],
                kind="insert",
                source="READS_edge",
            ))

    # 4. Control files — prefer job-family prefix over bare CID
    cid = intent.cid or candidate.proc_name[:4]
    all_control_rows = conn.execute(
        "SELECT path, text_content FROM artifacts WHERE kind = 'control' AND path LIKE ?",
        (f"%{cid}%",),
    ).fetchall()

    control_rows = _select_controls(all_control_rows, candidate.proc_name, intent)

    for row in control_rows:
        candidate.files.append(BundleFile(
            path=row["path"],
            kind="control",
            source="control_match",
        ))

    # 5. DFA resolution — from control format_dfa fields + procs DFA tokens
    seen_dfa_paths: set[str] = set()

    # 5a. From control text_content: all *_format_dfa and format_dfa lines
    for row in control_rows:
        dfa_codes = _extract_dfa_codes_from_control(row["text_content"] or "")
        dfa_codes = _filter_dfa_by_letter(dfa_codes, intent.letter_number)
        for code in dfa_codes:
            _resolve_dfa(conn, code, "control_format_dfa", candidate, seen_dfa_paths)

    # 5b. From .procs parsed_json: DFA tokens (e.g. WCCUDL014)
    proc_row = conn.execute(
        "SELECT parsed_json FROM procs WHERE proc_name = ?",
        (candidate.proc_name,),
    ).fetchone()
    if proc_row:
        procs_dfa_codes = _extract_dfa_tokens_from_procs(
            proc_row["parsed_json"] or "", cid,
        )
        procs_dfa_codes = _filter_dfa_by_letter(procs_dfa_codes, intent.letter_number)
        for code in procs_dfa_codes:
            _resolve_dfa(conn, code, "procs_dfa_token", candidate, seen_dfa_paths)


# ── Title phrase extraction ───────────────────────────────────────────────────

def _extract_title_phrase(raw_title: str) -> str:
    """Extract the most distinctive phrase from a raw title.

    Strips leading CID token, "Letter NN", "DL0NN", and surrounding punctuation/spaces.
    E.g. "WCCU Letter 14 - Business Rate/Payment Change Notice"
         → "Business Rate/Payment Change Notice"
    """
    s = raw_title
    # Remove leading CID (4 uppercase letters)
    s = _CID_RE.sub("", s, count=1)
    # Remove "Letter NN" or "DL0NN"
    s = _LETTER_RE.sub("", s, count=1)
    # Strip leading/trailing separators
    s = re.sub(r"^[\s\-–—:,]+", "", s)
    s = re.sub(r"[\s\-–—:,]+$", "", s)
    return s.strip()


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_candidate(
    candidate: BundleCandidate,
    intent: PlanIntent,
    conn: sqlite3.Connection,
) -> None:
    """Calculate score for a candidate based on intent match quality."""
    breakdown: list[tuple[str, float]] = []

    # Exact proc key match (cid+jobid)
    if intent.cid and intent.job_id:
        expected_key = f"proc:{intent.cid}{intent.job_id}"
        if candidate.proc_key == expected_key:
            breakdown.append(("exact_key_match", 50.0))

    # proc_name starts with cid
    if intent.cid and candidate.proc_name.startswith(intent.cid):
        breakdown.append(("cid_prefix", 15.0))

    # Has script files
    if any(f.kind == "script" for f in candidate.files):
        breakdown.append(("has_scripts", 10.0))

    # Has insert files
    if any(f.kind == "insert" for f in candidate.files):
        breakdown.append(("has_inserts", 10.0))

    # Has control file
    if any(f.kind == "control" for f in candidate.files):
        breakdown.append(("has_control", 10.0))

    # Has DFA file
    if any(f.kind == "docdef" for f in candidate.files):
        breakdown.append(("has_dfa", 5.0))

    # Title phrase match in parsed_json (high value — exact phrase from title)
    row = conn.execute(
        "SELECT parsed_json FROM procs WHERE proc_name = ?",
        (candidate.proc_name,),
    ).fetchone()
    pj = (row["parsed_json"] or "").lower() if row else ""

    if intent.raw_title and pj:
        # Extract the most distinctive phrase: strip CID and leading/trailing noise
        phrase = _extract_title_phrase(intent.raw_title)
        if phrase and phrase.lower() in pj:
            breakdown.append(("title_phrase_match", 30.0))

    # Keyword matches in parsed_json
    if intent.title_keywords and pj:
        for kw in intent.title_keywords:
            if kw in pj:
                breakdown.append((f"keyword:{kw}", 2.0))

    candidate.score_breakdown = breakdown
    candidate.score = sum(pts for _, pts in breakdown)


# ── Orchestrator ─────────────────────────────────────────────────────────────

def generate_plan(
    conn: sqlite3.Connection,
    snapshot_path: Path,
    cid: str | None = None,
    job_id: str | None = None,
    title: str | None = None,
    limit: int = 5,
    debug: bool = False,
) -> tuple[PlanIntent, list[BundleCandidate]]:
    """Generate plan: build intent, find candidates, bundle & score.

    Returns (intent, sorted_candidates).
    """
    intent = build_intent(cid=cid, job_id=job_id, title=title)
    candidates = find_candidates(conn, intent)

    for c in candidates:
        build_bundle(conn, c, snapshot_path, intent)
        score_candidate(c, intent, conn)

    # Sort descending by score
    candidates.sort(key=lambda c: c.score, reverse=True)

    return intent, candidates[:limit]


# ── i18n ─────────────────────────────────────────────────────────────────────

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "parsed_intent": "PARSED INTENT",
        "cid": "CID",
        "job_id": "Job ID",
        "letter_number": "Letter number",
        "keywords": "Keywords",
        "raw_title": "Raw title",
        "selected_bundle": "SELECTED BUNDLE",
        "bundle_candidates": "BUNDLE CANDIDATES",
        "files_to_open": "FILES TO OPEN",
        "other_candidates": "OTHER CANDIDATES",
        "no_matching_procs": "(no matching procs found)",
        "no_files": "(no files)",
        "files": "files",
        "cursor_title": "LSA Bundle Plan",
        "cursor_intro": (
            "Analysis of a legacy Papyrus/DocExec bundle. "
            "Use ONLY files from the snapshot root below."
        ),
        "cursor_instructions": "Instructions",
        "cursor_step_1": "Open files from `selected_bundle.files` (abs_path).",
        "cursor_step_2": "Explain where the letter is defined and which files are involved.",
        "cursor_step_3": "Suggest minimal edits with code quotes.",
        "cursor_step_4": "Create an edit plan with exact code quotes.",
        "cursor_step_5": "Provide a verification checklist.",
        "cursor_step_6": "Prepare a ticket-ready change request.",
        "cursor_step_7": "Be concise.",
        "cursor_data": "Plan data",
    },
    "ru": {
        "parsed_intent": "РАЗОБРАННОЕ НАМЕРЕНИЕ",
        "cid": "CID",
        "job_id": "Job ID",
        "letter_number": "Номер письма",
        "keywords": "Ключевые слова",
        "raw_title": "Исходный заголовок",
        "selected_bundle": "ВЫБРАННЫЙ ПАКЕТ",
        "bundle_candidates": "КАНДИДАТЫ",
        "files_to_open": "ФАЙЛЫ ДЛЯ ОТКРЫТИЯ",
        "other_candidates": "ОСТАЛЬНЫЕ КАНДИДАТЫ",
        "no_matching_procs": "(подходящие proc не найдены)",
        "no_files": "(нет файлов)",
        "files": "файлов",
        "cursor_title": "LSA — план пакета",
        "cursor_intro": (
            "Анализ legacy Papyrus/DocExec пакета. "
            "Используй ТОЛЬКО файлы из snapshot root ниже."
        ),
        "cursor_instructions": "Инструкции",
        "cursor_step_1": "Открой файлы из `selected_bundle.files` (abs_path).",
        "cursor_step_2": "Объясни, где определено письмо (letter) и какие файлы участвуют.",
        "cursor_step_3": "Предложи минимальные правки с цитатами из кода.",
        "cursor_step_4": "Составь план изменений (edit plan) с точными цитатами.",
        "cursor_step_5": "Дай checklist для верификации.",
        "cursor_step_6": "Подготовь change request для тикета.",
        "cursor_step_7": "Отвечай кратко.",
        "cursor_data": "Данные плана",
    },
}


def _t(key: str, lang: str) -> str:
    """Look up a translated string, falling back to English."""
    return _TRANSLATIONS.get(lang, _TRANSLATIONS["en"]).get(
        key, _TRANSLATIONS["en"].get(key, key)
    )


# ── Output formatting ────────────────────────────────────────────────────────

def format_plan_output(
    intent: PlanIntent,
    candidates: list[BundleCandidate],
    snapshot_path: Path,
    debug: bool = False,
    show_all: bool = False,
    lang: str = "en",
) -> str:
    """Format plan results as plain text.

    Default mode: winner details + compact summary of others.
    show_all mode: full details for all candidates (legacy behavior).
    """
    lines: list[str] = []

    # ── PARSED INTENT ──
    lines.append(f"═══ {_t('parsed_intent', lang)} ═══")
    lines.append(f"  {_t('cid', lang) + ':':16s}{intent.cid or '(none)'}")
    lines.append(f"  {_t('job_id', lang) + ':':16s}{intent.job_id or '(none)'}")
    lines.append(f"  {_t('letter_number', lang) + ':':16s}{intent.letter_number or '(none)'}")
    if intent.title_keywords:
        lines.append(f"  {_t('keywords', lang) + ':':16s}{', '.join(intent.title_keywords)}")
    if intent.raw_title:
        lines.append(f"  {_t('raw_title', lang) + ':':16s}{intent.raw_title}")
    lines.append("")

    if not candidates:
        lines.append(f"═══ {_t('bundle_candidates', lang)} (0) ═══")
        lines.append(f"  {_t('no_matching_procs', lang)}")
        lines.append("")
        lines.append(f"═══ {_t('files_to_open', lang)} ═══")
        lines.append(f"  {_t('no_files', lang)}")
        return "\n".join(lines)

    if show_all:
        lines.append(f"═══ {_t('bundle_candidates', lang)} ({len(candidates)}) ═══")
        for i, c in enumerate(candidates, 1):
            _format_candidate_detail(lines, i, c, snapshot_path, debug, lang)
        lines.append("")
        lines.append(f"═══ {_t('files_to_open', lang)} ═══")
        for bf in candidates[0].files:
            lines.append(f"  {snapshot_path / bf.path}")
    else:
        top = candidates[0]
        lines.append(f"═══ {_t('selected_bundle', lang)} ═══")
        _format_candidate_detail(lines, 1, top, snapshot_path, debug, lang)

        lines.append(f"═══ {_t('files_to_open', lang)} ═══")
        for bf in top.files:
            lines.append(f"  {snapshot_path / bf.path}")

        if len(candidates) > 1:
            lines.append("")
            lines.append(f"═══ {_t('other_candidates', lang)} ({len(candidates) - 1}) ═══")
            for i, c in enumerate(candidates[1:], 2):
                lines.append(
                    f"  #{i}  {c.proc_key}  [{c.display_name}]"
                    f"  score={c.score:.0f}  {_t('files', lang)}={len(c.files)}"
                )

    return "\n".join(lines)


def _format_candidate_detail(
    lines: list[str],
    rank: int,
    candidate: BundleCandidate,
    snapshot_path: Path,
    debug: bool,
    lang: str = "en",
) -> None:
    """Append detailed candidate info to lines buffer."""
    lines.append(f"  #{rank}  {candidate.proc_key}  [{candidate.display_name}]  score={candidate.score:.0f}")
    if debug:
        for rule, pts in candidate.score_breakdown:
            lines.append(f"       +{pts:.0f}  {rule}")
    lines.append(f"       {_t('files', lang)}: {len(candidate.files)}")
    for bf in candidate.files:
        lines.append(f"         {bf.kind:8s}  {bf.path}  ({bf.source})")
    lines.append("")


def format_plan_json(
    intent: PlanIntent,
    candidates: list[BundleCandidate],
    snapshot_path: Path,
) -> dict:
    """Build machine-readable plan result."""
    intent_dict = {
        "cid": intent.cid,
        "job_id": intent.job_id,
        "letter_number": intent.letter_number,
        "keywords": intent.title_keywords,
        "raw_title": intent.raw_title,
    }

    selected: dict | None = None
    if candidates:
        top = candidates[0]
        selected = {
            "rank": 1,
            "key": top.proc_key,
            "display_name": top.display_name,
            "score": int(top.score),
            "files": [
                {
                    "kind": bf.kind,
                    "path": bf.path,
                    "abs_path": str(snapshot_path / bf.path),
                    "reason": bf.source,
                }
                for bf in top.files
            ],
        }

    others = [
        {
            "rank": i + 2,
            "key": c.proc_key,
            "display_name": c.display_name,
            "score": int(c.score),
            "file_count": len(c.files),
        }
        for i, c in enumerate(candidates[1:])
    ]

    return {
        "snapshot_root": str(snapshot_path),
        "intent": intent_dict,
        "selected_bundle": selected,
        "other_candidates_summary": others,
    }


def format_cursor_prompt(
    intent: PlanIntent,
    candidates: list[BundleCandidate],
    snapshot_path: Path,
    lang: str = "en",
) -> str:
    """Build a ready-to-paste Markdown prompt for Cursor IDE."""
    import json as _json

    data = format_plan_json(intent, candidates, snapshot_path)
    json_block = _json.dumps(data, indent=2, ensure_ascii=False)

    sections = [
        f"# {_t('cursor_title', lang)}",
        "",
        _t("cursor_intro", lang),
        "",
        f"## {_t('cursor_instructions', lang)}",
        "",
        f"1. {_t('cursor_step_1', lang)}",
        f"2. {_t('cursor_step_2', lang)}",
        f"3. {_t('cursor_step_3', lang)}",
        f"4. {_t('cursor_step_4', lang)}",
        f"5. {_t('cursor_step_5', lang)}",
        f"6. {_t('cursor_step_6', lang)}",
        f"7. {_t('cursor_step_7', lang)}",
        "",
        f"## {_t('cursor_data', lang)}",
        "",
        "```json",
        json_block,
        "```",
        "",
        f"Snapshot root: `{snapshot_path}`",
    ]
    return "\n".join(sections)
