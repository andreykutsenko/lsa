"""AI prompt generator for lsa explain."""

from pathlib import Path

from ..parsers.log_parser import LogAnalysis

_INSTRUCTION_EN = """\
Analyze a batch job failure using the LSA context pack and log snippet below.

Priority:
1. EXTERNAL CONFIG SIGNALS (InfoTrac, Message Manager, APIs, success:false, HTTP 4xx/5xx, "No data found")
2. Script/proc issues (missing params, file paths, permissions, wrapper noise)

Answer in English:
- Root cause (1-2 sentences)
- Evidence: exact log lines with line numbers
- Why other hypotheses are weaker
- Escalation: config issue (ISD/owners) vs code issue (developer)
- Verification checklist (commands or SQL placeholders)
- Suggested fix / change request text (short, ticket-ready)

For each hypothesis in TOP HYPOTHESES: state if valid or noise, and why.\
"""

_INSTRUCTION_RU = """\
Проанализируй падение batch job на основе LSA context pack и фрагмента лога ниже.

Приоритет:
1. EXTERNAL CONFIG SIGNALS (InfoTrac, Message Manager, API, success:false, HTTP 4xx/5xx, "No data found")
2. Проблемы в script/proc (параметры, пути, права, wrapper noise)

Ответ на русском:
- Корневая причина (1-2 предложения)
- Доказательства: точные строки лога с номерами
- Почему другие гипотезы слабее
- Эскалация: config issue (ISD/владельцы) vs code issue (разработчик)
- Чеклист проверки (команды или SQL-плейсхолдеры)
- Текст fix / change request (коротко, под тикет)

По каждой гипотезе из TOP HYPOTHESES: валидна или шум — почему.\
"""

_MAX_SNIPPET_LINES = 50


def _extract_log_snippet(log_path: Path, error_line_numbers: list[int]) -> str:
    """Extract ±50 lines around the first error evidence line."""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(log file not readable)"

    if not error_line_numbers:
        # No specific line — return last 50 lines
        snippet_lines = lines[-_MAX_SNIPPET_LINES:]
        start = max(0, len(lines) - _MAX_SNIPPET_LINES)
    else:
        center = error_line_numbers[0] - 1  # convert to 0-based
        start = max(0, center - _MAX_SNIPPET_LINES // 2)
        end = min(len(lines), center + _MAX_SNIPPET_LINES // 2)
        snippet_lines = lines[start:end]

    numbered = [f"{start + i + 1:>4}: {line}" for i, line in enumerate(snippet_lines)]
    return "\n".join(numbered)


def generate_ai_prompt(
    context_pack: str,
    log_path: Path,
    log_analysis: LogAnalysis,
    lang: str = "en",
) -> str:
    """
    Generate a ready-to-paste AI prompt combining instruction, context pack,
    and log snippet.

    Args:
        context_pack: Output of generate_context_pack()
        log_path: Path to the analyzed log file
        log_analysis: Parsed log analysis (for error line numbers)
        lang: Output language instruction ('en' or 'ru')
    """
    instruction = _INSTRUCTION_RU if lang == "ru" else _INSTRUCTION_EN

    error_line_numbers = [s.line_number for s in log_analysis.error_signals if s.line_number]
    log_snippet = _extract_log_snippet(log_path, error_line_numbers)

    parts = [
        instruction,
        "",
        "=" * 60,
        "CONTEXT PACK",
        "=" * 60,
        context_pack,
        "=" * 60,
        "LOG SNIPPET",
        "=" * 60,
        log_snippet,
        "",
    ]

    return "\n".join(parts)
