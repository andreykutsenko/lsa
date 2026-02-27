"""Generate deep analysis AI prompt for lsa plan --deep."""
from pathlib import Path
from ..analysis.planner import BundleCandidate

_INSTRUCTION_EN = """\
You are analyzing a Papyrus/DocExec batch job processing system.
Job: {proc_name} ({title})

Read the files listed in FILES TO READ below. If you need additional files
(helper scripts, DFAs, control files) that are not listed — read them directly
from the snapshot. All production scripts are available locally at:
  {snapshot_path}

Generate a comprehensive Mermaid diagram showing:
1. All job_sel processing paths. Determine ALL values the scripts actually accept —
   check case statements in every script. Common values: s=print, e=archival, f=esite.
   Include test/dev paths (t, k, etc.) if they apply to this job.
2. For each path: which scripts run and in what order
   (include secondary helper scripts involved in formatting)
3. Every DocExec step (format_only.sh, isisdisk.sh, isisdisk_daily.sh) with the
   exact DFA docdef name for that step (read from .control or .procs files)
4. Key output artifacts per path (AFP files, index files, paperless, client pickup, etc.)
5. External systems involved (ISD, InfoTrac, preprocessing servers via SSH)
6. Level of detail: each script invocation or significant shell function call is a
   separate node. For multi-step helper scripts (archival, processing shells), show
   their internal pipeline (e.g., convert→compress→encrypt→copy), not just the script name.
7. Paperless/suppression: if .procs or .ins references suppression lists (ESUP, paperless),
   show them as data inputs with dotted arrows (-.->).
8. Styling — add style directives:
   - DocExec nodes (format/print steps): fill:#e8d5b7
   - Decision nodes (job_sel branches): fill:#f5a623
   - Start/End nodes: fill:#4a90d9,color:#fff
   - Each job_sel subgraph uses a distinct fill color for visual distinction

Output:
1. Save the diagram to: {diagrams_dir}/{proc_name}.mmd
2. Output the raw Mermaid source in a code block (for copy-paste into mermaid.live)

Mermaid syntax rules:
- Diagram must start with "graph TD"
- All node labels must be in double quotes: A["my label"]
- No spaces around arrows: A-->B (not A --> B)
- Subgraph titles must be in double quotes: subgraph S["title"]
- Use subgraphs for each job_sel path
- Label DocExec nodes with DFA name
- The .mmd file must begin with these comment lines:
  %% {proc_name} processing flow diagram
  %% To view: open https://mermaid.live and paste this into the Code panel
  %% Also works in: VS Code (ext: "Markdown Preview Mermaid Support"),
  %%   GitHub/GitLab (renders .mmd natively), Confluence Cloud, Notion (/mermaid block)

No explanation — diagram only.\
"""

_INSTRUCTION_RU = """\
Ты анализируешь систему пакетной обработки Papyrus/DocExec.
Job: {proc_name} ({title})

Прочитай файлы из раздела FILES TO READ ниже. Если тебе нужны дополнительные
файлы (вспомогательные скрипты, DFA, control-файлы) которых нет в списке —
читай их напрямую из снапшота. Все production-скрипты доступны локально:
  {snapshot_path}

Сгенерируй подробную Mermaid диаграмму:
1. Все пути обработки по job_sel. Определи ВСЕ значения, которые реально
   обрабатываются скриптами — проверь case-операторы в каждом скрипте.
   Типичные значения: s=print, e=archival, f=esite.
   Включи тестовые/dev пути (t, k и др.), если они применимы к этому job.
2. Для каждого пути: какие скрипты вызываются и в каком порядке
   (включая второстепенные скрипты, участвующие в форматировании)
3. Каждый DocExec шаг (format_only.sh, isisdisk.sh, isisdisk_daily.sh) с точным
   именем DFA docdef для этого шага (читай из .control или .procs файлов)
4. Ключевые выходные артефакты (AFP, index, paperless, client pickup и т.д.)
5. Внешние системы (ISD, InfoTrac, preprocessing серверы через SSH)
6. Уровень детализации: каждый вызов скрипта или значимый вызов shell-функции —
   отдельная нода. Для многошаговых вспомогательных скриптов (архивирование,
   обработка) показывай внутренний pipeline (например, convert→compress→encrypt→copy),
   а не просто имя скрипта.
7. Paperless/suppression: если .procs или .ins ссылается на списки подавления
   (ESUP, paperless), показывай их как входные данные с пунктирными стрелками (-.->).
8. Стилизация — добавь style-директивы:
   - DocExec ноды (шаги формата/печати): fill:#e8d5b7
   - Decision ноды (ветвления по job_sel): fill:#f5a623
   - Start/End ноды: fill:#4a90d9,color:#fff
   - Каждый subgraph job_sel использует свой отличительный fill-цвет

Вывод:
1. Сохрани диаграмму в: {diagrams_dir}/{proc_name}.mmd
2. Выведи исходный код Mermaid в блоке кода (для копирования в mermaid.live)

Правила синтаксиса Mermaid:
- Диаграмма начинается с "graph TD"
- Все подписи узлов в двойных кавычках: A["подпись"]
- Без пробелов вокруг стрелок: A-->B (не A --> B)
- Заголовки subgraph в двойных кавычках: subgraph S["заголовок"]
- Используй subgraph для каждого пути job_sel
- Помечай DocExec ноды именем DFA
- Файл .mmd должен начинаться с комментариев:
  %% {proc_name} processing flow diagram
  %% To view: open https://mermaid.live and paste this into the Code panel
  %% Also works in: VS Code (ext: "Markdown Preview Mermaid Support"),
  %%   GitHub/GitLab (renders .mmd natively), Confluence Cloud, Notion (/mermaid block)

Без пояснений — только диаграмма.\
"""


def generate_deep_prompt(bundle: BundleCandidate, snapshot_path: Path, lang: str = "en") -> str:
    """Generate AI prompt for deep Papyrus flow analysis.

    Provides file paths only — the AI reads what it needs directly.
    No file contents embedded; no truncation issues.
    """
    diagrams_dir = snapshot_path / ".lsa" / "diagrams"
    instruction_tmpl = _INSTRUCTION_RU if lang == "ru" else _INSTRUCTION_EN
    instruction = instruction_tmpl.format(
        proc_name=bundle.proc_name,
        title=bundle.display_name,
        diagrams_dir=diagrams_dir,
        snapshot_path=snapshot_path,
    )

    sep = "=" * 60
    parts: list[str] = [instruction, "", sep, "FILES TO READ", sep]

    for f in bundle.files:
        full_path = snapshot_path / f.path
        parts.append(f"  [{f.kind}]  {full_path}")

    return "\n".join(parts)
