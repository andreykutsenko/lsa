"""Generate deep analysis AI prompt for lsa plan --deep."""
from pathlib import Path
from ..analysis.planner import BundleCandidate

_MAX_FILE_LINES = 300

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


def _read_file(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > _MAX_FILE_LINES:
            lines = lines[:_MAX_FILE_LINES]
            lines.append(f"... (truncated at {_MAX_FILE_LINES} lines)")
        return "\n".join(lines)
    except OSError:
        return "(not readable)"


def generate_deep_prompt(bundle: BundleCandidate, snapshot_path: Path, lang: str = "en") -> str:
    """Generate AI prompt for deep Papyrus flow analysis with Mermaid output."""
    instruction_tmpl = _INSTRUCTION_RU if lang == "ru" else _INSTRUCTION_EN
    instruction = instruction_tmpl.format(proc_name=bundle.proc_name, title=bundle.display_name)

    sep = "=" * 60

    parts: list[str] = [instruction, "", sep, "SOURCE FILES", sep]

    # Include: procs file, RUNS_edge scripts, control files (up to 3), insert files
    include_kinds = {"procs", "script", "control", "insert"}
    included = 0
    for f in bundle.files:
        if f.kind not in include_kinds:
            continue
        full_path = snapshot_path / f.path
        content = _read_file(full_path)
        parts.append(f"\n--- {f.path} ({f.kind}) ---")
        parts.append(content)
        if f.kind == "control":
            included += 1
            if included >= 3:  # cap control files to avoid prompt bloat
                break

    return "\n".join(parts)
