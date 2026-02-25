"""Generate deep analysis AI prompt for lsa plan --deep."""
from pathlib import Path
from ..analysis.planner import BundleCandidate

_INSTRUCTION_EN = """\
You are analyzing a Papyrus/DocExec batch job processing system.
Job: {proc_name} ({title})

Read the files listed below, then generate a Mermaid diagram showing:
1. All job_sel processing paths (s/f/e/b/t or whatever exists in the scripts)
2. For each path: which scripts run and in what order
3. Every DocExec step (format_only.sh, isisdisk.sh, isisdisk_daily.sh) with the DFA docdef name used
4. Key output artifacts per path (AFP files, index files, paperless, client pickup, etc.)
5. External systems involved (ISD, InfoTrac, preprocessing servers via SSH)

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

Прочитай файлы из списка ниже, затем сгенерируй Mermaid диаграмму:
1. Все пути обработки по job_sel (s/f/e/b/t или что есть в скриптах)
2. Для каждого пути: какие скрипты вызываются и в каком порядке
3. Каждый DocExec шаг (format_only.sh, isisdisk.sh, isisdisk_daily.sh) с именем DFA docdef
4. Ключевые выходные артефакты (AFP, index, paperless, client pickup и т.д.)
5. Внешние системы (ISD, InfoTrac, preprocessing серверы через SSH)

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
    )

    sep = "=" * 60
    parts: list[str] = [instruction, "", sep, "FILES TO READ", sep]

    for f in bundle.files:
        full_path = snapshot_path / f.path
        parts.append(f"  [{f.kind}]  {full_path}")

    return "\n".join(parts)
