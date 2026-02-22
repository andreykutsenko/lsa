"""Generate deep analysis AI prompt for lsa plan --deep."""
from pathlib import Path
from ..analysis.planner import BundleCandidate

_MAX_FILE_LINES = 300
_SECTION_WINDOW = 120  # lines of context around matched section in large scripts

_INSTRUCTION_EN = """\
You are analyzing a Papyrus/DocExec batch job processing system.
Below are the source files for job: {proc_name} ({title}).

Your task:
1. Identify all job_sel processing paths (e.g. s/f/e/b/t or similar)
2. For each path, trace which scripts run and in what order
3. Identify every DocExec step (format_only.sh, isisdisk.sh, isisdisk_daily.sh calls) and which DFA docdef is used at each step
4. Identify key output artifacts per path (AFP files, index files, paperless, client pickup, etc.)
5. Note where external systems are involved (ISD, InfoTrac, preprocessing servers via SSH)

Output ONLY a Mermaid diagram starting with "graph TD".
Use subgraphs for each job_sel path.
Label DocExec nodes with the DFA name.
No explanation text — diagram only.\
"""

_INSTRUCTION_RU = """\
Ты анализируешь систему пакетной обработки Papyrus/DocExec.
Ниже исходные файлы для job: {proc_name} ({title}).

Задача:
1. Определи все пути обработки по job_sel (например s/f/e/b/t или аналогичные)
2. Для каждого пути — какие скрипты вызываются и в каком порядке
3. Найди каждый DocExec шаг (вызовы format_only.sh, isisdisk.sh, isisdisk_daily.sh) и какой DFA docdef используется
4. Определи ключевые выходные артефакты для каждого пути (AFP, index файлы, paperless, client pickup и т.д.)
5. Отметь где задействованы внешние системы (ISD, InfoTrac, preprocessing серверы через SSH)

Выведи ТОЛЬКО Mermaid диаграмму начиная с "graph TD".
Используй subgraph для каждого пути job_sel.
Помечай DocExec ноды именем DFA.
Без пояснительного текста — только диаграмма.\
"""


def _read_file(path: Path, keywords: list[str] | None = None) -> str:
    """Read file content, extracting relevant section for large generic scripts.

    For large files (>_MAX_FILE_LINES lines): if keywords are provided,
    find the largest contiguous block of matching lines and return
    _SECTION_WINDOW lines of context around it. Falls back to first
    _MAX_FILE_LINES lines if no keyword match found.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(not readable)"

    if len(lines) <= _MAX_FILE_LINES:
        return "\n".join(lines)

    # Large file — try to find relevant section by keywords
    if keywords:
        kw_lower = [k.lower() for k in keywords]
        match_indices = [
            i for i, line in enumerate(lines)
            if any(kw in line.lower() for kw in kw_lower)
        ]
        if match_indices:
            # Find densest cluster: pick the match with most nearby matches
            best = min(match_indices, key=lambda i: abs(i - match_indices[len(match_indices) // 2]))
            start = max(0, best - 10)
            end = min(len(lines), start + _SECTION_WINDOW)
            result = []
            if start > 0:
                result.append(f"... (file has {len(lines)} lines; showing lines {start+1}-{end})")
            result.extend(lines[start:end])
            if end < len(lines):
                result.append(f"... (truncated, {len(lines) - end} more lines)")
            return "\n".join(result)

    # Fallback: first _MAX_FILE_LINES lines
    result = lines[:_MAX_FILE_LINES]
    result.append(f"... (truncated at {_MAX_FILE_LINES} lines, file has {len(lines)} total)")
    return "\n".join(result)


def generate_deep_prompt(bundle: BundleCandidate, snapshot_path: Path, lang: str = "en") -> str:
    """Generate AI prompt for deep Papyrus flow analysis with Mermaid output."""
    instruction_tmpl = _INSTRUCTION_RU if lang == "ru" else _INSTRUCTION_EN
    instruction = instruction_tmpl.format(proc_name=bundle.proc_name, title=bundle.display_name)

    sep = "=" * 60

    parts: list[str] = [instruction, "", sep, "SOURCE FILES", sep]

    # Keywords to find job-relevant section in large generic scripts (e.g. isis.sh)
    # Use CID (first 4 chars) + full proc_name + job id (last 3 chars)
    proc = bundle.proc_name
    script_keywords = [proc, proc[:4], proc[-3:]]

    # Include: procs file, RUNS_edge scripts, control files (up to 3), insert files
    include_kinds = {"procs", "script", "control", "insert"}
    included_controls = 0
    for f in bundle.files:
        if f.kind not in include_kinds:
            continue
        full_path = snapshot_path / f.path
        # For scripts, pass keywords to extract job-relevant section
        keywords = script_keywords if f.kind == "script" else None
        content = _read_file(full_path, keywords=keywords)
        parts.append(f"\n--- {f.path} ({f.kind}) ---")
        parts.append(content)
        if f.kind == "control":
            included_controls += 1
            if included_controls >= 3:  # cap control files to avoid prompt bloat
                break

    return "\n".join(parts)
