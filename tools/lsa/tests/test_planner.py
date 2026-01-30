"""Tests for the plan / bundle logic."""

import json
import pytest
from pathlib import Path

from lsa.db import init_db, get_connection
from lsa.db.connection import insert_node, insert_edge, insert_artifact
from lsa.db.connection import insert_proc
from lsa.analysis.planner import (
    parse_title,
    build_intent,
    generate_plan,
    format_plan_output,
    format_plan_json,
    format_cursor_prompt,
)


def _setup_db(tmp_path):
    """Create a fresh DB and return its path."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


class TestTitleParsing:
    """Tests for parse_title()."""

    def test_title_parsing_cid(self):
        """Should extract CID from title as first 4-letter uppercase token."""
        cid, _letter, _kw = parse_title("WCCU Letter 14 update")
        assert cid == "wccu"

    def test_title_parsing_cid_not_short(self):
        """Should not match tokens shorter than 4 uppercase letters."""
        cid, _, _ = parse_title("ABC something")
        assert cid is None

    def test_title_parsing_letter_number(self):
        """Should extract letter number and zero-pad to 3 digits."""
        _, letter, _ = parse_title("WCCU Letter 14")
        assert letter == "014"

    def test_title_parsing_letter_dl_format(self):
        """Should extract letter number from DL format."""
        _, letter, _ = parse_title("BKFN DL014 report")
        assert letter == "014"

    def test_title_parsing_letter_already_3_digits(self):
        """Should preserve 3-digit letter number."""
        _, letter, _ = parse_title("WCCU Letter 014")
        assert letter == "014"


class TestPlanExactMatch:
    """Test that plan prefers exact proc key when cid+jobid are given."""

    def test_plan_prefers_exact_proc_key_when_cid_jobid(self, tmp_path):
        """wccuds1 should rank above wccuds2 when jobid=ds1."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            # Create two proc nodes
            insert_node(conn, "proc", "proc:wccuds1", "WCCU - Papyrus",
                        canonical_path="procs/wccuds1.procs")
            insert_node(conn, "proc", "proc:wccuds2", "WCCU - DocExec",
                        canonical_path="procs/wccuds2.procs")

            intent, candidates = generate_plan(
                conn,
                snapshot_path=tmp_path,
                cid="WCCU",
                job_id="ds1",
            )

            assert len(candidates) >= 1
            assert candidates[0].proc_key == "proc:wccuds1"
            assert candidates[0].score > 0
            # If second candidate exists, it should score lower
            if len(candidates) > 1:
                assert candidates[0].score > candidates[1].score


class TestPlanControlByLetterNumber:
    """Test that control files matched by letter number appear in the bundle."""

    def test_plan_finds_control_by_letter_number_when_present(self, tmp_path):
        """Control file matching letter number should be in the bundle."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            # Use proc name wccudla so job-family "wccudl" matches "wccudl014"
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")

            # Create two control artifacts: one matching letter, one not
            insert_artifact(conn, kind="control",
                            path="control/wccudl014.control",
                            mtime=0.0, size=100,
                            text_content='format_dfa="WCCUDL014"')
            insert_artifact(conn, kind="control",
                            path="control/wccudl020.control",
                            mtime=0.0, size=100,
                            text_content='format_dfa="WCCUDL020"')

            intent, candidates = generate_plan(
                conn,
                snapshot_path=tmp_path,
                cid="WCCU",
                title="WCCU Letter 14 update",
            )

            assert len(candidates) >= 1
            top = candidates[0]
            control_paths = [f.path for f in top.files if f.kind == "control"]
            assert "control/wccudl014.control" in control_paths
            # The non-matching control should be excluded when letter_number is set
            assert "control/wccudl020.control" not in control_paths


class TestPlanOutputFormat:
    """Test output formatting."""

    def test_plan_outputs_files_to_open_block(self, tmp_path):
        """Output should contain a 'FILES TO OPEN' section."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccuds1", "WCCU - Papyrus",
                        canonical_path="procs/wccuds1.procs")

            intent, candidates = generate_plan(
                conn,
                snapshot_path=tmp_path,
                cid="WCCU",
                job_id="ds1",
            )

        output = format_plan_output(intent, candidates, tmp_path)
        assert "FILES TO OPEN" in output
        assert "PARSED INTENT" in output
        assert "SELECTED BUNDLE" in output


class TestDfaFromControl:
    """Test DFA resolution from control format_dfa fields."""

    def test_dfa_included_from_control_format_dfa(self, tmp_path):
        """Bundle should include docdef/WCCUDL014.dfa when control has format_dfa."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")

            # Control with quoted format_dfa (real format from snapshot)
            insert_artifact(conn, kind="control",
                            path="control/wccudl014.control",
                            mtime=0.0, size=200,
                            text_content=(
                                'format_dfa="WCCUDL014"\n'
                                'ind_pdf_format_dfa="WCCUDL014"\n'
                                'pdf_format_dfa="WCCUDL014"\n'
                                'estmt_format_dfa="WCCUDL014"\n'
                            ))

            # Docdef artifact
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL014.dfa",
                            mtime=0.0, size=500)

            intent, candidates = generate_plan(
                conn,
                snapshot_path=tmp_path,
                cid="WCCU",
                title="WCCU Letter 14 update",
            )

            assert len(candidates) >= 1
            top = candidates[0]
            dfa_paths = [f.path for f in top.files if f.kind == "docdef"]
            assert "docdef/WCCUDL014.dfa" in dfa_paths

    def test_dfa_deduplication_across_format_dfa_variants(self, tmp_path):
        """Same DFA code in multiple *_format_dfa lines should produce one file entry."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")
            insert_artifact(conn, kind="control",
                            path="control/wccudl014.control",
                            mtime=0.0, size=200,
                            text_content=(
                                'format_dfa="WCCUDL014"\n'
                                'pdf_format_dfa="WCCUDL014"\n'
                                'estmt_format_dfa="WCCUDL014"\n'
                            ))
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL014.dfa",
                            mtime=0.0, size=500)

            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="WCCU",
                title="WCCU Letter 14 update",
            )

            top = candidates[0]
            dfa_paths = [f.path for f in top.files if f.kind == "docdef"]
            # Should appear exactly once despite 3 matching lines
            assert dfa_paths.count("docdef/WCCUDL014.dfa") == 1


class TestDfaFromProcsTokens:
    """Test DFA resolution from .procs parsed_json DFA tokens."""

    def test_procs_dfa_tokens_included_even_without_control(self, tmp_path):
        """WCCUDL014 and WCCUDL015 from .procs should resolve to docdef files."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")

            # Procs with DFA tokens in parsed_json (simulating real content)
            insert_proc(conn, proc_name="wccudla", path="procs/wccudla.procs",
                        parsed_json=(
                            '{"description": "Business Rate/Payment Change Notice '
                            'WCCUDL014 and WCCUDL015"}'
                        ))

            # Two docdef artifacts
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL014.dfa",
                            mtime=0.0, size=500)
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL015.dfa",
                            mtime=0.0, size=500)

            intent, candidates = generate_plan(
                conn,
                snapshot_path=tmp_path,
                cid="WCCU",
                title="WCCU Letter 14 - Business Rate/Payment Change Notice",
            )

            assert len(candidates) >= 1
            top = candidates[0]
            dfa_paths = [f.path for f in top.files if f.kind == "docdef"]
            assert "docdef/WCCUDL014.dfa" in dfa_paths
            assert "docdef/WCCUDL015.dfa" not in dfa_paths


class TestTitlePhraseMatchRanking:
    """Test that title phrase match gives a large scoring advantage."""

    def test_wccudla_outranks_others_when_title_matches_procs(self, tmp_path):
        """Proc whose parsed_json contains the title phrase should rank highest."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            # Two procs: wccudla has matching content, wccuds1 does not
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")
            insert_node(conn, "proc", "proc:wccuds1", "WCCU - DocExec",
                        canonical_path="procs/wccuds1.procs")

            insert_proc(conn, proc_name="wccudla", path="procs/wccudla.procs",
                        parsed_json='{"text": "Business Rate/Payment Change Notice WCCUDL014"}')
            insert_proc(conn, proc_name="wccuds1", path="procs/wccuds1.procs",
                        parsed_json='{"text": "Daily statement processing"}')

            intent, candidates = generate_plan(
                conn,
                snapshot_path=tmp_path,
                cid="WCCU",
                title="WCCU Letter 14 - Business Rate/Payment Change Notice",
            )

            assert len(candidates) >= 2
            assert candidates[0].proc_key == "proc:wccudla"
            # Should have a large margin (phrase match = +30)
            assert candidates[0].score >= candidates[1].score + 25


class TestControlNotAttachedToUnrelatedProcs:
    """Test that job-family filtering prevents noisy control attachment."""

    def test_control_not_attached_to_unrelated_proc(self, tmp_path):
        """wccudl014.control should NOT be attached to wccuds1 (different job family)."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccuds1", "WCCU - DocExec",
                        canonical_path="procs/wccuds1.procs")

            # Control for wccudl family
            insert_artifact(conn, kind="control",
                            path="control/wccudl014.control",
                            mtime=0.0, size=200,
                            text_content='format_dfa="WCCUDL014"')

            intent, candidates = generate_plan(
                conn,
                snapshot_path=tmp_path,
                cid="WCCU",
                title="WCCU Letter 14 update",
            )

            # wccuds1 should NOT have wccudl014.control in its bundle
            ds1 = next((c for c in candidates if c.proc_key == "proc:wccuds1"), None)
            assert ds1 is not None
            control_paths = [f.path for f in ds1.files if f.kind == "control"]
            assert "control/wccudl014.control" not in control_paths


class TestDfaLetterFiltering:
    """Test DFA filtering by letter number from title."""

    def test_letter_14_excludes_dl015_from_procs(self, tmp_path):
        """When title says Letter 14, DL015 from procs parsed_json is excluded."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")
            insert_proc(conn, proc_name="wccudla", path="procs/wccudla.procs",
                        parsed_json='{"text": "WCCUDL014 and WCCUDL015"}')
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL014.dfa", mtime=0.0, size=500)
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL015.dfa", mtime=0.0, size=500)

            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="WCCU",
                title="WCCU Letter 14 - Business Rate/Payment Change Notice",
            )

            top = candidates[0]
            dfa_paths = [f.path for f in top.files if f.kind == "docdef"]
            assert "docdef/WCCUDL014.dfa" in dfa_paths
            assert "docdef/WCCUDL015.dfa" not in dfa_paths

    def test_letter_15_excludes_dl014(self, tmp_path):
        """When title says Letter 15, DL014 from procs is excluded."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")
            insert_proc(conn, proc_name="wccudla", path="procs/wccudla.procs",
                        parsed_json='{"text": "WCCUDL014 and WCCUDL015"}')
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL014.dfa", mtime=0.0, size=500)
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL015.dfa", mtime=0.0, size=500)

            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="WCCU",
                title="WCCU Letter 15 - something",
            )

            top = candidates[0]
            dfa_paths = [f.path for f in top.files if f.kind == "docdef"]
            assert "docdef/WCCUDL015.dfa" in dfa_paths
            assert "docdef/WCCUDL014.dfa" not in dfa_paths

    def test_no_letter_number_keeps_all_dfas(self, tmp_path):
        """Without letter number in title, all DFA codes are kept."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")
            insert_proc(conn, proc_name="wccudla", path="procs/wccudla.procs",
                        parsed_json='{"text": "WCCUDL014 and WCCUDL015"}')
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL014.dfa", mtime=0.0, size=500)
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL015.dfa", mtime=0.0, size=500)

            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="WCCU",
            )

            top = candidates[0]
            dfa_paths = [f.path for f in top.files if f.kind == "docdef"]
            assert "docdef/WCCUDL014.dfa" in dfa_paths
            assert "docdef/WCCUDL015.dfa" in dfa_paths

    def test_control_dfa_also_filtered_by_letter(self, tmp_path):
        """DFA codes from control format_dfa are also filtered by letter number."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")
            # Control has both DL014 and DL015 format_dfa entries
            insert_artifact(conn, kind="control",
                            path="control/wccudl014.control",
                            mtime=0.0, size=200,
                            text_content='format_dfa="WCCUDL014"\nind_pdf_format_dfa="WCCUDL015"')
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL014.dfa", mtime=0.0, size=500)
            insert_artifact(conn, kind="docdef",
                            path="docdef/WCCUDL015.dfa", mtime=0.0, size=500)

            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="WCCU",
                title="WCCU Letter 14 update",
            )

            top = candidates[0]
            dfa_paths = [f.path for f in top.files if f.kind == "docdef"]
            assert "docdef/WCCUDL014.dfa" in dfa_paths
            assert "docdef/WCCUDL015.dfa" not in dfa_paths


class TestJsonOutput:
    """Test JSON output format."""

    def test_json_output_is_valid_and_has_required_keys(self, tmp_path):
        """format_plan_json should return dict with correct schema."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")

            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="WCCU",
                title="WCCU Letter 14 update",
            )

        data = format_plan_json(intent, candidates, tmp_path)

        # Verify JSON serializable
        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)

        assert "snapshot_root" in parsed
        assert "intent" in parsed
        assert "selected_bundle" in parsed
        assert "other_candidates_summary" in parsed

        # Intent fields
        assert parsed["intent"]["cid"] == "wccu"
        assert parsed["intent"]["letter_number"] == "014"

        # Selected bundle
        bundle = parsed["selected_bundle"]
        assert bundle is not None
        assert bundle["rank"] == 1
        assert bundle["key"] == "proc:wccudla"
        assert isinstance(bundle["files"], list)
        assert len(bundle["files"]) >= 1

        # Files have required fields
        for f in bundle["files"]:
            assert "kind" in f
            assert "path" in f
            assert "abs_path" in f
            assert "reason" in f

    def test_json_output_no_candidates(self, tmp_path):
        """JSON output with no candidates should have null selected_bundle."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="ZZZZ",
            )

        data = format_plan_json(intent, candidates, tmp_path)
        assert data["selected_bundle"] is None
        assert data["other_candidates_summary"] == []


class TestCursorOutput:
    """Test Cursor prompt output format."""

    def test_cursor_output_contains_markdown_and_json(self, tmp_path):
        """format_cursor_prompt should return Markdown with embedded JSON."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")

            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="WCCU",
                title="WCCU Letter 14 update",
            )

        prompt = format_cursor_prompt(intent, candidates, tmp_path)

        assert "# LSA Bundle Plan" in prompt
        assert "## Instructions" in prompt
        assert "```json" in prompt
        assert "```" in prompt
        assert "Snapshot root:" in prompt

        # Extract and verify embedded JSON is valid
        json_start = prompt.index("```json") + len("```json\n")
        json_end = prompt.index("```", json_start)
        json_str = prompt[json_start:json_end].strip()
        data = json.loads(json_str)
        assert data["selected_bundle"]["key"] == "proc:wccudla"

    def test_cursor_output_russian(self, tmp_path):
        """format_cursor_prompt with lang='ru' should produce Russian text."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")

            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="WCCU",
                title="WCCU Letter 14 update",
            )

        prompt = format_cursor_prompt(intent, candidates, tmp_path, lang="ru")
        assert "## Инструкции" in prompt
        assert "Данные плана" in prompt


class TestDefaultOutputFormat:
    """Test the new default output format (winner + compact others)."""

    def test_default_shows_selected_bundle_not_all(self, tmp_path):
        """Default output should show SELECTED BUNDLE, not full details for all."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")
            insert_node(conn, "proc", "proc:wccuds1", "WCCU - DocExec",
                        canonical_path="procs/wccuds1.procs")

            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="WCCU",
            )

        output = format_plan_output(intent, candidates, tmp_path)
        assert "SELECTED BUNDLE" in output
        assert "OTHER CANDIDATES" in output

    def test_show_all_uses_legacy_format(self, tmp_path):
        """show_all=True should use legacy 'BUNDLE CANDIDATES' format."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")

            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="WCCU",
            )

        output = format_plan_output(intent, candidates, tmp_path, show_all=True)
        assert "BUNDLE CANDIDATES" in output

    def test_russian_output(self, tmp_path):
        """lang='ru' should produce Russian section headers."""
        db_path = _setup_db(tmp_path)

        with get_connection(db_path) as conn:
            insert_node(conn, "proc", "proc:wccudla", "WCCU - Papyrus",
                        canonical_path="procs/wccudla.procs")

            intent, candidates = generate_plan(
                conn, snapshot_path=tmp_path, cid="WCCU",
            )

        output = format_plan_output(intent, candidates, tmp_path, lang="ru")
        assert "ВЫБРАННЫЙ ПАКЕТ" in output
        assert "РАЗОБРАННОЕ НАМЕРЕНИЕ" in output
