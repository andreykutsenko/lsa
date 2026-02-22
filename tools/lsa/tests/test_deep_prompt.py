"""Tests for lsa/output/deep_prompt.py."""

from pathlib import Path

from lsa.analysis.planner import BundleCandidate, BundleFile
from lsa.output.deep_prompt import generate_deep_prompt


def _make_bundle(tmp_path: Path) -> BundleCandidate:
    """Build a minimal BundleCandidate with one procs file."""
    procs_file = tmp_path / "procs" / "idcumv1.procs"
    procs_file.parent.mkdir(parents=True, exist_ok=True)
    procs_file.write_text("JOB_SEL=s\nformat_dfa=IDCUDL001\n", encoding="utf-8")

    bundle = BundleCandidate(
        proc_key="proc:idcumv1",
        proc_name="idcumv1",
        display_name="IDCU - Monthly Statement",
    )
    bundle.files.append(BundleFile(
        path="procs/idcumv1.procs",
        kind="procs",
        source="proc_file",
    ))
    return bundle


class TestDeepPrompt:
    """Tests for generate_deep_prompt()."""

    def test_prompt_contains_proc_name(self, tmp_path):
        """Output must contain the proc name."""
        bundle = _make_bundle(tmp_path)
        result = generate_deep_prompt(bundle, tmp_path, lang="en")
        assert "idcumv1" in result

    def test_prompt_contains_instruction_keywords_en(self, tmp_path):
        """English output must mention DocExec and Mermaid."""
        bundle = _make_bundle(tmp_path)
        result = generate_deep_prompt(bundle, tmp_path, lang="en")
        assert "DocExec" in result
        assert "Mermaid" in result

    def test_prompt_contains_instruction_keywords_ru(self, tmp_path):
        """Russian output must mention Mermaid and диаграмм."""
        bundle = _make_bundle(tmp_path)
        result = generate_deep_prompt(bundle, tmp_path, lang="ru")
        assert "Mermaid" in result
        assert "диаграмм" in result

    def test_prompt_contains_file_section(self, tmp_path):
        """Output must contain the SOURCE FILES header."""
        bundle = _make_bundle(tmp_path)
        result = generate_deep_prompt(bundle, tmp_path, lang="en")
        assert "SOURCE FILES" in result
