"""AI prompt generator for lsa explain."""

from pathlib import Path

from ..parsers.log_parser import LogAnalysis

_INSTRUCTION_EN = """\
Analyze a batch job failure using the LSA context pack below. Open files from FILES TO OPEN section for full content.

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
Проанализируй падение batch job на основе LSA context pack ниже. Открой файлы из секции FILES TO OPEN для полного содержимого.

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


def generate_ai_prompt(
    context_pack: str,
    log_path: Path,
    log_analysis: LogAnalysis,
    lang: str = "en",
) -> str:
    """
    Generate a ready-to-paste AI prompt combining instruction and context pack.

    Args:
        context_pack: Output of generate_context_pack()
        log_path: Path to the analyzed log file (unused, kept for API compat)
        log_analysis: Parsed log analysis (unused, kept for API compat)
        lang: Output language instruction ('en' or 'ru')
    """
    instruction = _INSTRUCTION_RU if lang == "ru" else _INSTRUCTION_EN

    parts = [
        instruction,
        "",
        context_pack,
        "",
    ]

    return "\n".join(parts)
