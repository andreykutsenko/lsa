"""Tests for Mermaid diagram generation."""
from pathlib import Path

from lsa.graph.call_parser import find_script_calls, build_call_graph
from lsa.analysis.planner import BundleCandidate, BundleFile
from lsa.output.mermaid import generate_mermaid


class TestFindScriptCalls:
    """Tests for find_script_calls()."""

    def test_basic_basename_detection(self):
        """Should return basenames of known scripts that appear in content."""
        content = "#!/bin/sh\n./helper_convert.pl --mode batch\n"
        known = {"helper_convert.pl", "other_script.sh", "unrelated.py"}
        result = find_script_calls(content, known)
        assert "helper_convert.pl" in result
        assert "other_script.sh" not in result
        assert "unrelated.py" not in result

    def test_no_matches_returns_empty(self):
        """Should return empty list when no known basenames appear in content."""
        content = "echo hello world"
        known = {"missing.sh", "absent.pl"}
        result = find_script_calls(content, known)
        assert result == []

    def test_multiple_matches(self):
        """Should return all matching basenames when several appear in content."""
        content = "run_a.sh && run_b.pl || fallback.py"
        known = {"run_a.sh", "run_b.pl", "fallback.py", "gone.sh"}
        result = find_script_calls(content, known)
        assert set(result) == {"run_a.sh", "run_b.pl", "fallback.py"}


class TestBuildCallGraph:
    """Tests for build_call_graph()."""

    def test_simple_a_calls_b(self, tmp_path):
        """Script A that mentions script B's name should produce A->B edge."""
        a = tmp_path / "script_a.sh"
        b = tmp_path / "helper_b.pl"
        a.write_text("#!/bin/sh\nperl helper_b.pl\n", encoding="utf-8")
        b.write_text("#!/usr/bin/perl\n# helper\n", encoding="utf-8")

        script_paths = {
            "script_a.sh": a,
            "helper_b.pl": b,
        }
        graph = build_call_graph(script_paths)

        assert "script_a.sh" in graph
        assert "helper_b.pl" in graph["script_a.sh"]

    def test_no_calls_produces_empty_graph(self, tmp_path):
        """Scripts with no cross-references should produce empty graph."""
        a = tmp_path / "a.sh"
        b = tmp_path / "b.sh"
        a.write_text("echo a\n", encoding="utf-8")
        b.write_text("echo b\n", encoding="utf-8")

        graph = build_call_graph({"a.sh": a, "b.sh": b})
        assert graph == {}

    def test_missing_file_is_skipped(self, tmp_path):
        """Non-existent script paths should not raise and are silently skipped."""
        a = tmp_path / "real.sh"
        a.write_text("perl ghost.pl\n", encoding="utf-8")

        graph = build_call_graph({
            "real.sh": a,
            "ghost.pl": tmp_path / "ghost.pl",  # does not exist
        })
        # real.sh mentions ghost.pl but ghost.pl doesn't exist — no further recursion
        assert "real.sh" in graph
        assert "ghost.pl" in graph["real.sh"]


class TestGenerateMermaid:
    """Tests for generate_mermaid()."""

    def _make_bundle(self, proc_name: str, display_name: str, files: list[BundleFile]) -> BundleCandidate:
        return BundleCandidate(
            proc_key=f"proc:{proc_name}",
            proc_name=proc_name,
            display_name=display_name,
            score=100.0,
            files=files,
        )

    def test_generate_mermaid_contains_proc_name(self, tmp_path):
        """Output should contain the proc name as a node."""
        bundle = self._make_bundle("idcumv1", "IDCU - Visa Stmt", [])
        result = generate_mermaid(bundle, tmp_path)
        assert "graph TD" in result
        assert "idcumv1" in result

    def test_generate_mermaid_contains_script_and_insert(self, tmp_path):
        """Output should contain script and insert nodes with correct edge labels."""
        files = [
            BundleFile(path="master/idcu_visa_process.sh", kind="script", source="RUNS_edge"),
            BundleFile(path="insert/idcumv1.ins", kind="insert", source="READS_edge"),
        ]
        bundle = self._make_bundle("idcumv1", "IDCU - Visa Stmt", files)
        result = generate_mermaid(bundle, tmp_path)

        assert "idcu_visa_process" in result
        assert "RUNS" in result
        assert "idcumv1" in result
        assert "READS" in result

    def test_generate_mermaid_starts_with_graph_td(self, tmp_path):
        """First line of output must be 'graph TD'."""
        bundle = self._make_bundle("testproc", "Test Proc", [])
        result = generate_mermaid(bundle, tmp_path)
        assert result.startswith("graph TD")

    def test_generate_mermaid_control_and_dfa_nodes(self, tmp_path):
        """Control and docdef files should appear with correct edge labels."""
        files = [
            BundleFile(path="control/idcumv1.control", kind="control", source="control_match"),
            BundleFile(path="docdef/IDCUMV11.dfa", kind="docdef", source="procs_dfa_token"),
        ]
        bundle = self._make_bundle("idcumv1", "IDCU - Visa Stmt", files)
        result = generate_mermaid(bundle, tmp_path)

        assert "control" in result
        assert "dfa" in result
        assert "IDCUMV11" in result

    def test_generate_mermaid_calls_edges_from_real_files(self, tmp_path):
        """Scripts that reference each other should produce 'calls' edges."""
        # Create two real script files where A calls B
        master_dir = tmp_path / "master"
        master_dir.mkdir()
        script_a = master_dir / "main_job.sh"
        script_b = master_dir / "helper_util.pl"
        script_a.write_text("#!/bin/sh\nperl helper_util.pl\n", encoding="utf-8")
        script_b.write_text("#!/usr/bin/perl\n# utility\n", encoding="utf-8")

        files = [
            BundleFile(path="master/main_job.sh", kind="script", source="RUNS_edge"),
            BundleFile(path="master/helper_util.pl", kind="script", source="helper_prefix_match"),
        ]
        bundle = self._make_bundle("testproc", "Test Proc", files)
        result = generate_mermaid(bundle, tmp_path)

        assert "calls" in result
        assert "helper_util" in result
