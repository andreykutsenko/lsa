"""Context pack generator for LSA."""

from datetime import datetime
from pathlib import Path

from ..config import MAX_CONTEXT_PACK_LINES, MAX_EVIDENCE_SNIPPET
from ..parsers.log_parser import LogAnalysis
from ..analysis.hypotheses import Hypothesis
from ..analysis.similarity import SimilarCase


def generate_context_pack(
    log_path: Path,
    log_analysis: LogAnalysis,
    top_node: dict | None,
    confidence: float,
    neighbors: dict | None,
    hypotheses: list[Hypothesis],
    similar_cases: list[SimilarCase],
    related_files: list[str],
    snapshot_path: Path,
    decoded_codes: dict[str, dict] | None = None,
) -> str:
    """
    Generate a context pack for debugging.

    Output is a single block of text, max ~200 lines,
    suitable for pasting into Cursor.

    Args:
        log_path: Path to the analyzed log file
        log_analysis: Parsed log analysis
        top_node: Best matching node (or None)
        confidence: Match confidence
        neighbors: Dict with 'upstream' and 'downstream' nodes
        hypotheses: Generated hypotheses
        similar_cases: Similar past cases
        related_files: List of related file paths
        snapshot_path: Path to snapshot root

    Returns:
        Formatted context pack string
    """
    lines = []

    # Header
    lines.append("=" * 60)
    lines.append("LSA CONTEXT PACK")
    lines.append("=" * 60)
    lines.append(f"Log: {log_path}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # 1. Most likely failing node
    lines.append("-" * 40)
    lines.append("1. MOST LIKELY FAILING NODE")
    lines.append("-" * 40)
    if top_node:
        lines.append(f"Node: {top_node['display_name']} (confidence: {confidence:.0%})")
        lines.append(f"Type: {top_node['type']}")
        lines.append(f"Key: {top_node['key']}")
        if top_node.get("canonical_path"):
            lines.append(f"Path: {snapshot_path / top_node['canonical_path']}")
    else:
        lines.append("NOT FOUND - could not determine failing node")
    lines.append("")

    # 2. Execution chain
    lines.append("-" * 40)
    lines.append("2. EXECUTION CHAIN")
    lines.append("-" * 40)
    if neighbors:
        if neighbors["upstream"]:
            lines.append("Upstream (dependencies):")
            for n in neighbors["upstream"][:5]:
                node = n["node"]
                lines.append(f"  [{node['type']}] {node['display_name']} --{n['rel_type']}--> (this)")
        else:
            lines.append("Upstream: (none)")

        if neighbors["downstream"]:
            lines.append("Downstream (dependents):")
            for n in neighbors["downstream"][:5]:
                node = n["node"]
                lines.append(f"  (this) --{n['rel_type']}--> [{node['type']}] {node['display_name']}")
        else:
            lines.append("Downstream: (none)")
    else:
        lines.append("NOT FOUND in snapshot")
    lines.append("")

    # 3. Evidence
    lines.append("-" * 40)
    lines.append("3. EVIDENCE (error log lines)")
    lines.append("-" * 40)
    error_signals = log_analysis.error_signals[:8]
    if error_signals:
        for signal in error_signals:
            msg = signal.message
            if len(msg) > MAX_EVIDENCE_SNIPPET:
                msg = msg[:MAX_EVIDENCE_SNIPPET] + "..."
            lines.append(f"L{signal.line_number}: {msg}")
    else:
        lines.append("No error signals found in log")

    if log_analysis.error_codes:
        lines.append(f"Error codes: {', '.join(log_analysis.error_codes[:10])}")
    lines.append("")

    # 3b. PAPYRUS/DOCEXEC CODES (decoded)
    lines.append("-" * 40)
    lines.append("3b. PAPYRUS/DOCEXEC CODES (decoded)")
    lines.append("-" * 40)

    # Get codes to decode - prefer F/E severity, limit to 10
    fatal_codes = [c for c in log_analysis.error_codes if c.endswith('F')]
    error_codes = [c for c in log_analysis.error_codes if c.endswith('E')]
    other_codes = [c for c in log_analysis.error_codes if not c.endswith('F') and not c.endswith('E')]
    codes_to_show = fatal_codes + error_codes + other_codes
    codes_to_show = codes_to_show[:10]

    if codes_to_show:
        for code in codes_to_show:
            if decoded_codes and code in decoded_codes:
                entry = decoded_codes[code]
                severity_name = {"I": "Info", "W": "Warning", "E": "Error", "F": "Fatal"}.get(
                    entry.get("severity", "I"), "Unknown"
                )
                title = entry.get("title") or ""
                body = entry.get("body", "")[:150]
                if len(entry.get("body", "")) > 150:
                    body += "..."
                lines.append(f"{code} [{severity_name}]")
                if title:
                    lines.append(f"  Title: {title}")
                lines.append(f"  {body}")
            else:
                lines.append(f"{code} - UNKNOWN CODE (not in KB yet)")
    else:
        lines.append("No Papyrus/DocExec codes found in log")
    lines.append("")

    # 3c. FILES FROM LOG EVIDENCE
    lines.append("-" * 40)
    lines.append("3c. FILES FROM LOG EVIDENCE")
    lines.append("-" * 40)

    # DOCDEF tokens
    if log_analysis.docdef_tokens:
        lines.append("DOCDEF tokens found:")
        for token in log_analysis.docdef_tokens[:5]:
            # Try to map to snapshot docdef path
            docdef_path = snapshot_path / "docdef" / f"{token.lower()}.dfa"
            if docdef_path.exists():
                lines.append(f"  {token} -> {docdef_path}")
            else:
                lines.append(f"  {token} (docdef not found in snapshot)")

    # Script paths
    if log_analysis.script_paths:
        lines.append("Script paths:")
        for script_path in log_analysis.script_paths[:5]:
            # Map to snapshot (support both /home/master/ and /home/test/master/)
            mapped = False
            for prefix in ["/home/master/", "/home/test/master/"]:
                if prefix in script_path:
                    local_path = script_path.replace(prefix, "master/")
                    full_path = snapshot_path / local_path
                    if full_path.exists():
                        lines.append(f"  {script_path} -> {full_path}")
                        mapped = True
                        break
            if not mapped:
                lines.append(f"  {script_path} (not in snapshot)")

    # I/O paths (show as-is, don't dump content)
    if log_analysis.io_paths:
        lines.append("Input/Output paths (from log):")
        for io_path in log_analysis.io_paths[:5]:
            lines.append(f"  {io_path}")

    if not (log_analysis.docdef_tokens or log_analysis.script_paths or log_analysis.io_paths):
        lines.append("No file references extracted from log")
    lines.append("")

    # 3d. EXTERNAL CONFIG SIGNALS
    lines.append("-" * 40)
    lines.append("3d. EXTERNAL CONFIG SIGNALS")
    lines.append("-" * 40)

    if log_analysis.external_signals:
        # Sort by severity (F > E > W > I) and show top 5
        sorted_signals = sorted(
            log_analysis.external_signals,
            key=lambda s: -s.severity_rank
        )[:5]

        for ext_signal in sorted_signals:
            severity_name = {
                "F": "FATAL",
                "E": "ERROR",
                "W": "WARNING",
                "I": "INFO",
            }.get(ext_signal.severity, "UNKNOWN")

            lines.append(f"[{severity_name}] {ext_signal.id} ({ext_signal.category})")

            # Show captures if any
            if ext_signal.captures:
                captures_str = ", ".join(
                    f"{k}={v}" for k, v in ext_signal.captures.items()
                )
                lines.append(f"  Captures: {captures_str}")

            # Show evidence lines (max 3)
            for ev in ext_signal.evidence[:3]:
                line_text = ev.line_text
                if len(line_text) > 100:
                    line_text = line_text[:100] + "..."
                lines.append(f"  L{ev.line_no}: {line_text}")

        # Show services detected
        if log_analysis.services_seen:
            lines.append(f"Services detected: {', '.join(log_analysis.services_seen)}")

        # Show InfoTrac missing message IDs summary
        if log_analysis.infotrac_missing_message_ids:
            lines.append(
                f"InfoTrac missing message IDs: {', '.join(log_analysis.infotrac_missing_message_ids)}"
            )
    else:
        lines.append("None found")
    lines.append("")

    # 4. Hypotheses
    lines.append("-" * 40)
    lines.append("4. TOP HYPOTHESES")
    lines.append("-" * 40)
    if hypotheses:
        for i, hyp in enumerate(hypotheses, 1):
            lines.append(f"{i}. {hyp.hypothesis}")
            lines.append(f"   Evidence (L{hyp.line_number}): {hyp.evidence}")
            lines.append("   How to confirm:")
            for step in hyp.confirm_steps:
                lines.append(f"   - {step}")
            lines.append("")
    else:
        lines.append("No specific hypotheses - review log for details")
    lines.append("")

    # 5. Files to open
    lines.append("-" * 40)
    lines.append("5. FILES TO OPEN")
    lines.append("-" * 40)
    if related_files:
        for f in related_files[:8]:
            lines.append(f"  {f}")
    else:
        lines.append("NOT FOUND in snapshot")
    lines.append("")

    # 6. Suggested commands
    lines.append("-" * 40)
    lines.append("6. SUGGESTED COMMANDS")
    lines.append("-" * 40)
    lines.append(f"# View full log")
    lines.append(f"less {log_path}")
    lines.append(f"# Search for errors")
    lines.append(f"grep -n 'ERROR\\|FAIL\\|ORA-' {log_path}")
    if log_analysis.error_codes:
        first_code = log_analysis.error_codes[0]
        lines.append(f"# Search for specific error")
        lines.append(f"grep -n '{first_code}' {log_path}")
    lines.append("")

    # 7. Similar past cases
    lines.append("-" * 40)
    lines.append("7. SIMILAR PAST CASES")
    lines.append("-" * 40)
    if similar_cases:
        for case in similar_cases:
            lines.append(f"[{case.title or 'Untitled'}] (match: {case.match_score:.0%})")
            if case.root_cause:
                cause = case.root_cause
                if len(cause) > 80:
                    cause = cause[:80] + "..."
                lines.append(f"  Root cause: {cause}")
            if case.fix_summary:
                fix = case.fix_summary
                if len(fix) > 80:
                    fix = fix[:80] + "..."
                lines.append(f"  Fix: {fix}")
            if case.verify_commands:
                lines.append("  Verify commands:")
                for cmd in case.verify_commands[:2]:
                    if len(cmd) > 60:
                        cmd = cmd[:60] + "..."
                    lines.append(f"    {cmd}")
            lines.append("")
    else:
        lines.append("No similar cases found (or below threshold)")
    lines.append("")

    lines.append("=" * 60)
    lines.append("END OF CONTEXT PACK")
    lines.append("=" * 60)

    # Truncate if too long
    result = "\n".join(lines)
    result_lines = result.split("\n")
    if len(result_lines) > MAX_CONTEXT_PACK_LINES:
        result_lines = result_lines[:MAX_CONTEXT_PACK_LINES - 3]
        result_lines.append("...")
        result_lines.append(f"[Truncated - {len(lines)} total lines]")
        result_lines.append("=" * 60)
        result = "\n".join(result_lines)

    return result
