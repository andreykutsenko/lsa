"""Parser for Papyrus/DocExec message codes PDF knowledge base."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from io import BytesIO

from . import patterns


@dataclass
class MessageCodeEntry:
    """A message code entry extracted from PDF."""

    code: str
    severity: str  # I, W, E, F
    title: str | None
    body: str

    @property
    def severity_name(self) -> str:
        """Get human-readable severity name."""
        return {
            "I": "Info",
            "W": "Warning",
            "E": "Error",
            "F": "Fatal",
        }.get(self.severity, "Unknown")


@dataclass
class _CodeHit:
    """Internal: a potential definition hit for scoring."""
    code: str
    position: int
    title: str | None
    body: str
    score: float = 0.0


# Severity from postfix letter
SEVERITY_MAP = {
    "I": "I",  # Informational
    "W": "W",  # Warning
    "E": "E",  # Error
    "F": "F",  # Fatal
}

# Common header/footer noise patterns to strip
NOISE_PATTERNS = [
    re.compile(r"^\d+/\d+$"),  # Page numbers like "248/392"
    re.compile(r"^Papyrus\s+Objects\s+Process\s+Control\s+System\s+Messages?$", re.IGNORECASE),
    re.compile(r"^Papyrus\s+Objects\s+.*Messages?$", re.IGNORECASE),
    re.compile(r"^DocExec\s+Messages?$", re.IGNORECASE),
    re.compile(r"^AFP\s+Resource\s+Messages?$", re.IGNORECASE),
    re.compile(r"^Chapter\s+\d+", re.IGNORECASE),
    re.compile(r"^Page\s+\d+", re.IGNORECASE),
]

# Pattern for section headers that should stop body extraction
SECTION_HEADER_PATTERN = re.compile(
    r"^(?:Chapter\s+\d+|Section\s+\d+|\d+\.\d+\s+[A-Z])",
    re.IGNORECASE | re.MULTILINE
)


def extract_severity_from_code(code: str) -> str:
    """Extract severity letter from message code postfix."""
    if code and len(code) > 0:
        last_char = code[-1].upper()
        return SEVERITY_MAP.get(last_char, "I")
    return "I"


def _is_noise_line(line: str) -> bool:
    """Check if a line is a common header/footer noise."""
    line = line.strip()
    if not line:
        return True
    for pattern in NOISE_PATTERNS:
        if pattern.match(line):
            return True
    return False


def _is_definition_position(text: str, pos: int) -> bool:
    """
    Check if code at position is a definition (start of line).

    A definition hit is when the code appears at the start of a line,
    i.e., preceded by newline, formfeed, or start of text,
    with optional leading whitespace.

    NOT a definition: "preceded by: PPCS1037F" (code inside sentence)
    """
    if pos == 0:
        return True

    # Look backwards from position to find what precedes the code
    i = pos - 1

    # Skip whitespace (but not newlines)
    while i >= 0 and text[i] in ' \t':
        i -= 1

    if i < 0:
        return True  # Start of text

    # Must be preceded by newline or formfeed
    return text[i] in '\n\r\f'


def _extract_body_from_position(
    text: str,
    code: str,
    start_pos: int,
    code_pattern: re.Pattern,
    max_body_len: int = 1500,
) -> tuple[str | None, str]:
    """
    Extract title and body starting from code position.

    Stops at:
    - Next code definition (code at start of line)
    - Section header
    - Max length

    Returns: (title, body)
    """
    # Start after the code
    body_start = start_pos + len(code)

    # Find where to stop
    end_pos = min(body_start + max_body_len, len(text))

    # Look for next code definition to stop before it
    for match in code_pattern.finditer(text[body_start:end_pos]):
        candidate_pos = body_start + match.start()
        if _is_definition_position(text, candidate_pos):
            end_pos = candidate_pos
            break

    # Extract raw body text
    raw_body = text[body_start:end_pos]

    # Clean up: split into lines, filter noise
    lines = raw_body.split('\n')
    clean_lines = []

    for line in lines:
        stripped = line.strip()

        # Skip noise lines
        if _is_noise_line(stripped):
            continue

        # Stop at section headers
        if SECTION_HEADER_PATTERN.match(stripped):
            break

        # Stop at cross-reference patterns (these are not part of the definition)
        if re.match(r"^This message is (?:preceded|followed) by:", stripped, re.IGNORECASE):
            break

        clean_lines.append(stripped)

    if not clean_lines:
        return None, ""

    # Title is first meaningful line (remove leading dashes/separators)
    title = None
    first_line = re.sub(r'^[\s\-:]+', '', clean_lines[0])
    if first_line and len(first_line) < 120:
        title = first_line

    body = '\n'.join(clean_lines)
    return title, body


def _score_hit(hit: _CodeHit) -> float:
    """
    Score a definition hit to determine quality.

    Scoring:
    - +3 if body contains "Reason:"
    - +3 if body contains "Solution:"
    - +1 if has a non-empty title
    - +min(len(body)/100, 5) for body length (capped)
    """
    score = 0.0

    body_lower = hit.body.lower()

    if "reason:" in body_lower:
        score += 3.0

    if "solution:" in body_lower:
        score += 3.0

    if hit.title:
        score += 1.0

    # Body length score, capped at 5
    score += min(len(hit.body) / 100, 5.0)

    return score


def _format_body_with_reason_solution(body: str) -> str:
    """
    If body has Reason:/Solution: sections, format them nicely.
    Otherwise return cleaned body.
    """
    # Try to extract Reason and Solution sections
    reason_match = re.search(
        r'Reason:\s*(.+?)(?=Solution:|$)',
        body,
        re.DOTALL | re.IGNORECASE
    )
    solution_match = re.search(
        r'Solution:\s*(.+?)(?=Reason:|$)',
        body,
        re.DOTALL | re.IGNORECASE
    )

    if reason_match or solution_match:
        parts = []

        # Include title/description before Reason if present
        reason_start = body.lower().find('reason:')
        solution_start = body.lower().find('solution:')

        first_section = min(
            reason_start if reason_start >= 0 else len(body),
            solution_start if solution_start >= 0 else len(body)
        )

        if first_section > 10:  # Has meaningful preamble
            preamble = body[:first_section].strip()
            preamble = re.sub(r'\s+', ' ', preamble)
            if preamble:
                parts.append(preamble[:200])

        if reason_match:
            reason_text = reason_match.group(1).strip()
            reason_text = re.sub(r'\s+', ' ', reason_text)
            parts.append(f"Reason: {reason_text[:300]}")

        if solution_match:
            solution_text = solution_match.group(1).strip()
            solution_text = re.sub(r'\s+', ' ', solution_text)
            parts.append(f"Solution: {solution_text[:300]}")

        return '\n'.join(parts)

    # No Reason/Solution, just clean up whitespace
    body = re.sub(r'\s+', ' ', body).strip()
    return body


def parse_message_codes_from_text(text: str) -> list[MessageCodeEntry]:
    """
    Parse message codes from extracted PDF text.

    Extracts codes like PPCS1234I, PPDE5678E, AFPR1234W, etc.
    Only considers "definition hits" - codes at start of line.
    When multiple hits exist for same code, picks best by scoring.

    Args:
        text: The raw text extracted from PDF

    Returns:
        List of MessageCodeEntry objects
    """
    entries = []
    code_pattern = patterns.MESSAGE_CODE_PATTERN

    # Collect all definition hits (code at start of line)
    # Group by code
    hits_by_code: dict[str, list[_CodeHit]] = {}

    for match in code_pattern.finditer(text):
        code = match.group(1)
        pos = match.start()

        # Only accept definition positions (start of line)
        if not _is_definition_position(text, pos):
            continue

        # Extract title and body
        title, body = _extract_body_from_position(
            text, code, pos, code_pattern
        )

        if not body:
            continue

        hit = _CodeHit(
            code=code,
            position=pos,
            title=title,
            body=body,
        )
        hit.score = _score_hit(hit)

        if code not in hits_by_code:
            hits_by_code[code] = []
        hits_by_code[code].append(hit)

    # For each code, pick the best hit
    for code, hits in hits_by_code.items():
        if not hits:
            continue

        # Sort by score descending, pick best
        hits.sort(key=lambda h: -h.score)
        best_hit = hits[0]

        severity = extract_severity_from_code(code)

        # Format body (handle Reason/Solution)
        formatted_body = _format_body_with_reason_solution(best_hit.body)

        # Final cleanup and truncation
        if len(formatted_body) > 800:
            formatted_body = formatted_body[:800] + "..."

        entries.append(MessageCodeEntry(
            code=code,
            severity=severity,
            title=best_hit.title,
            body=formatted_body,
        ))

    return entries


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from PDF using pdfminer.six.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text from all pages

    Raises:
        ImportError: If pdfminer.six is not installed
        OSError: If file cannot be read
    """
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text
    except ImportError:
        raise ImportError(
            "pdfminer.six is required for PDF parsing. "
            "Install it with: pip install pdfminer.six"
        )

    try:
        text = pdfminer_extract_text(str(pdf_path))
        return text
    except Exception as e:
        raise OSError(f"Failed to extract text from PDF: {e}")


def parse_pdf_file(pdf_path: Path) -> list[MessageCodeEntry]:
    """
    Parse Papyrus/DocExec message codes from a PDF file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of MessageCodeEntry objects

    Raises:
        ImportError: If pdfminer.six is not installed
        OSError: If file cannot be read
    """
    text = extract_text_from_pdf(pdf_path)
    return parse_message_codes_from_text(text)


def parse_pdf_file_safe(pdf_path: Path) -> tuple[list[MessageCodeEntry], list[str]]:
    """
    Safely parse PDF file, collecting errors without crashing.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Tuple of (entries, errors) where errors is a list of error messages
    """
    errors = []
    entries = []

    try:
        text = extract_text_from_pdf(pdf_path)
    except ImportError as e:
        errors.append(str(e))
        return entries, errors
    except OSError as e:
        errors.append(str(e))
        return entries, errors
    except Exception as e:
        errors.append(f"Unexpected error reading PDF: {e}")
        return entries, errors

    try:
        entries = parse_message_codes_from_text(text)
    except Exception as e:
        errors.append(f"Error parsing message codes from text: {e}")

    return entries, errors
