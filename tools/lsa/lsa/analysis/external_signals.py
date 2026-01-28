"""
External signals extractor for LSA.

Loads rules from YAML configuration and extracts signals from log text.
Designed for detecting external system / configuration failures
(InfoTrac, APIs, databases, network issues).
"""

import re
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Try to import yaml, but don't fail if not available
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class ExternalSignalEvidence:
    """Evidence line for an external signal."""
    line_no: int
    line_text: str

    def to_dict(self) -> dict:
        return {"line_no": self.line_no, "line_text": self.line_text}


@dataclass
class ExternalSignal:
    """An external signal extracted from log text."""
    id: str
    severity: str  # F, E, W, I
    category: str
    captures: dict[str, str] = field(default_factory=dict)
    evidence: list[ExternalSignalEvidence] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    hypothesis_template: str | None = None
    score: float = 0.0

    @property
    def severity_rank(self) -> int:
        """Get numeric rank for severity (higher = more severe)."""
        return {"F": 4, "E": 3, "W": 2, "I": 1}.get(self.severity, 0)

    def captures_json(self) -> str:
        """Get captures as JSON string."""
        return json.dumps(self.captures, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity,
            "category": self.category,
            "captures": self.captures,
            "evidence": [e.to_dict() for e in self.evidence],
            "hints": self.hints,
            "score": self.score,
        }


@dataclass
class _CompiledRule:
    """Internal: a compiled rule with regex patterns."""
    id: str
    severity: str
    category: str
    patterns: list[re.Pattern]
    hints: list[str]
    hypothesis_template: str | None = None


# Module-level cache for rules
_rules_cache: list[_CompiledRule] | None = None
_rules_load_error: str | None = None


def _get_rules_path() -> Path:
    """Get path to the rules YAML file."""
    return Path(__file__).parent.parent / "rules" / "external_signals.yaml"


def _load_rules() -> tuple[list[_CompiledRule], str | None]:
    """
    Load and compile rules from YAML file.

    Returns:
        Tuple of (compiled_rules, error_message_or_none)
    """
    if not YAML_AVAILABLE:
        return [], "PyYAML not installed; external signals disabled"

    rules_path = _get_rules_path()
    if not rules_path.exists():
        return [], f"Rules file not found: {rules_path}"

    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        return [], f"Failed to parse rules YAML: {e}"

    if not data or "rules" not in data:
        return [], "No 'rules' key in YAML"

    compiled = []
    for rule_data in data.get("rules", []):
        try:
            rule_id = rule_data.get("id", "UNKNOWN")
            severity = rule_data.get("severity", "I")
            category = rule_data.get("category", "UNKNOWN")
            patterns_raw = rule_data.get("patterns", [])
            hints = rule_data.get("hints", [])
            hypothesis_template = rule_data.get("hypothesis_template")

            # Compile patterns
            patterns = []
            for pat in patterns_raw:
                try:
                    compiled_pat = re.compile(pat, re.IGNORECASE)
                    patterns.append(compiled_pat)
                except re.error:
                    # Skip invalid pattern, continue with others
                    pass

            if patterns:  # Only add rule if it has at least one valid pattern
                compiled.append(_CompiledRule(
                    id=rule_id,
                    severity=severity,
                    category=category,
                    patterns=patterns,
                    hints=hints,
                    hypothesis_template=hypothesis_template,
                ))
        except Exception:
            # Skip malformed rule, continue
            pass

    return compiled, None


def get_rules() -> list[_CompiledRule]:
    """Get compiled rules (cached)."""
    global _rules_cache, _rules_load_error

    if _rules_cache is None:
        _rules_cache, _rules_load_error = _load_rules()

    return _rules_cache


def get_rules_load_error() -> str | None:
    """Get error message if rules failed to load."""
    global _rules_load_error

    if _rules_cache is None:
        get_rules()  # Trigger load

    return _rules_load_error


def reload_rules() -> None:
    """Force reload of rules (for testing)."""
    global _rules_cache, _rules_load_error
    _rules_cache = None
    _rules_load_error = None


def extract_external_signals(
    text: str,
    max_evidence_per_signal: int = 5,
    max_line_length: int = 200,
) -> list[ExternalSignal]:
    """
    Extract external signals from log text.

    Args:
        text: Log text to scan
        max_evidence_per_signal: Max evidence lines to keep per signal
        max_line_length: Max length for evidence line snippets

    Returns:
        List of ExternalSignal objects, sorted by severity (F > E > W > I)
    """
    rules = get_rules()
    if not rules:
        return []

    # Track signals by (id, captures_key) for deduplication
    # captures_key is a hashable representation of captures
    signals_map: dict[tuple[str, str], ExternalSignal] = {}

    lines = text.split('\n')

    for line_no, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        for rule in rules:
            for pattern in rule.patterns:
                match = pattern.search(line_stripped)
                if match:
                    # Extract captures from named groups
                    captures = {
                        k: v for k, v in match.groupdict().items()
                        if v is not None
                    }

                    # Create dedup key
                    captures_key = json.dumps(captures, sort_keys=True)
                    signal_key = (rule.id, captures_key)

                    # Truncate line for evidence
                    evidence_line = line_stripped
                    if len(evidence_line) > max_line_length:
                        evidence_line = evidence_line[:max_line_length] + "..."

                    evidence = ExternalSignalEvidence(
                        line_no=line_no,
                        line_text=evidence_line,
                    )

                    if signal_key in signals_map:
                        # Add evidence to existing signal (up to max)
                        existing = signals_map[signal_key]
                        if len(existing.evidence) < max_evidence_per_signal:
                            existing.evidence.append(evidence)
                    else:
                        # Create new signal
                        signal = ExternalSignal(
                            id=rule.id,
                            severity=rule.severity,
                            category=rule.category,
                            captures=captures,
                            evidence=[evidence],
                            hints=rule.hints.copy(),
                            hypothesis_template=rule.hypothesis_template,
                        )
                        # Calculate score based on severity and category
                        signal.score = _calculate_signal_score(signal)
                        signals_map[signal_key] = signal

                    break  # One match per rule per line is enough

    # Sort by severity (F > E > W > I), then by score
    signals = list(signals_map.values())
    signals.sort(key=lambda s: (-s.severity_rank, -s.score))

    return signals


def _calculate_signal_score(signal: ExternalSignal) -> float:
    """Calculate score for a signal based on severity and category."""
    score = 0.0

    # Severity score
    score += signal.severity_rank * 10

    # Category bonuses
    category_scores = {
        "CONFIG": 5,  # Configuration issues are often root causes
        "DATABASE": 4,
        "EXTERNAL_API": 3,
        "NETWORK": 3,
        "AUTH": 2,
        "RESOURCE": 2,
    }
    score += category_scores.get(signal.category, 1)

    # Bonus for having captures (more specific)
    if signal.captures:
        score += len(signal.captures) * 2

    return score


# Service extraction patterns (for best-effort service detection)
SERVICE_PATTERNS = [
    # Query param: services=estmt|paper|print
    re.compile(r"services?=(?P<service>[\w|]+)", re.IGNORECASE),
    # Path segment: /services/estmt/ or /service/paper/
    re.compile(r"/services?/(?P<service>\w+)", re.IGNORECASE),
    # JSON key: "service": "estmt" or "service_type": "paper"
    re.compile(r"[\"']service(?:_type)?[\"']\s*:\s*[\"'](?P<service>\w+)[\"']", re.IGNORECASE),
    # service=estmt in various formats
    re.compile(r"service\s*[=:]\s*[\"']?(?P<service>\w+)[\"']?", re.IGNORECASE),
]


def extract_services_from_text(text: str) -> list[str]:
    """
    Extract service names from log text (best-effort).

    Looks for patterns like services=estmt, /services/paper/, etc.

    Returns:
        List of unique service names found (lowercased)
    """
    services = set()

    for pattern in SERVICE_PATTERNS:
        for match in pattern.finditer(text):
            service = match.group("service")
            if service:
                # Handle pipe-separated services like "estmt|paper|print"
                for svc in service.lower().split('|'):
                    svc = svc.strip()
                    if svc and len(svc) > 1:
                        services.add(svc)

    return sorted(services)


def get_infotrac_missing_ids(signals: list[ExternalSignal]) -> list[str]:
    """
    Extract missing message IDs from INFOTRAC_MISSING_MESSAGE_ID signals.

    Args:
        signals: List of ExternalSignal objects

    Returns:
        List of message IDs (as strings)
    """
    ids = []
    for signal in signals:
        if signal.id == "INFOTRAC_MISSING_MESSAGE_ID":
            msg_id = signal.captures.get("message_id")
            if msg_id and msg_id not in ids:
                ids.append(msg_id)
    return ids
