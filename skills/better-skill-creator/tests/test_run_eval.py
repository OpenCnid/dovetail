#!/usr/bin/env python3
"""Tests for scripts/run_eval.py, run_loop.py and generate_report.py.

Run from the skill root:

    python -m unittest tests.test_run_eval -v

Every case corresponds to a defect demonstrated against the previous pipeline.
Cross-references are to research/02-trigger-eval.md (F...), 16-own-description.md,
05-cost-safety-resource.md and 01-windows-encoding.md.

Nothing here spends money. `scripts/run_eval` launches whatever
BETTER_SKILL_CREATOR_CLAUDE_ARGV names, and these tests point it at
tests/fixtures/stub_claude.py, which replays two *real* captured `claude -p`
streams: one where the model invoked the probe's clone as its first tool, and
one where five identical clones were visible and the model refused to invoke any
of them ("one skill appears to be impersonating another") and Read the files to
audit them instead.
"""

from __future__ import annotations

import io
import json
import locale
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts import run_eval as run_eval_mod  # noqa: E402
from scripts.generate_report import generate_html  # noqa: E402
from scripts.run_eval import (  # noqa: E402
    EvalSetError,
    check_skill_md_encoding,
    project_spend,
    read_confirmation,
    run_eval,
    run_single_query,
    validate_eval_set,
)
from scripts.run_loop import split_eval_set  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STUB = FIXTURES / "stub_claude.py"
STREAMS = FIXTURES / "streams"

TRIGGER_STREAM = STREAMS / "trigger_skill_first.jsonl"
REFUSAL_STREAM = STREAMS / "five_clones_refusal.jsonl"

DESCRIPTION = "Use this skill whenever a widget manifest needs authoring."


class StubHarness(unittest.TestCase):
    """Base class that wires run_eval to the stub CLI."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="run-eval-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.control_path = self.tmp / "control.json"
        self.report_path = self.tmp / "stub-report.json"

        self._saved_env = {
            k: os.environ.get(k)
            for k in ("BETTER_SKILL_CREATOR_CLAUDE_ARGV", "STUB_CLAUDE_CONTROL", "STUB_CLAUDE_REPORT")
        }
        os.environ["BETTER_SKILL_CREATOR_CLAUDE_ARGV"] = json.dumps([sys.executable, str(STUB)])
        os.environ["STUB_CLAUDE_CONTROL"] = str(self.control_path)
        os.environ["STUB_CLAUDE_REPORT"] = str(self.report_path)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def control(self, **kwargs):
        self.control_path.write_text(json.dumps(kwargs), encoding="utf-8")

    def probe(self, *, skill_name="widget-forge", description=DESCRIPTION, timeout=60, **kwargs):
        return run_single_query(
            query="i need a widget.toml manifest",
            skill_name=skill_name,
            skill_description=description,
            timeout=timeout,
            **kwargs,
        )

    def stub_report(self):
        return json.loads(self.report_path.read_text(encoding="utf-8"))


class TestNoSelectOnPipes(unittest.TestCase):
    """WinError 10038: select.select on a pipe is socket-only on Windows."""

    def test_run_eval_does_not_import_select(self):
        import ast

        tree = ast.parse((SKILL_ROOT / "scripts" / "run_eval.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertNotIn("select", imported)
        self.assertIsNone(getattr(run_eval_mod, "select", None))

    def test_stream_is_read_on_a_thread(self):
        source = (SKILL_ROOT / "scripts" / "run_eval.py").read_text(encoding="utf-8")
        self.assertIn("threading.Thread", source)
        self.assertIn("queue.Queue", source)


class TestDetection(StubHarness):
    def test_skill_invocation_as_first_tool_is_a_trigger(self):
        """The real captured stream in which Skill(clone) was the first tool."""
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        record = self.probe()
        self.assertEqual(record["status"], "trigger", record)
        self.assertTrue(record["triggered"])
        self.assertEqual(record["stop_reason"], "triggered")

    def test_orientation_tool_before_skill_still_triggers(self):
        """research/02 F4: the old detector returned False the instant the first
        tool block was not Skill/Read. Same stream, one Bash prepended."""
        self.control(stream=str(TRIGGER_STREAM), rename=True, prepend_foreign_tool=True)
        record = self.probe()
        self.assertEqual(record["status"], "trigger", record)
        self.assertTrue(any(t["name"] == "Bash" for t in record["tools"]))

    def test_sibling_clone_reference_is_not_a_trigger(self):
        """research/02 F13: do not adopt prefix matching.

        This replays the real five-clone stream, in which the model declined to
        invoke anything and Read the clone files to check for impersonation.
        None of those names is this probe's clone. A prefix matcher on
        '<skill>-skill-' scores it True; the exact per-probe name does not.
        """
        self.control(stream=str(REFUSAL_STREAM), rename=False)
        record = self.probe(max_tools=0)
        self.assertEqual(record["status"], "no_trigger", record)
        self.assertFalse(record["triggered"])
        read_inputs = " ".join(t["input"] for t in record["tools"])
        self.assertIn("widget-forge-skill-", read_inputs,
                      "fixture should still contain sibling clone names")

    def test_clean_result_without_invocation_is_a_non_trigger(self):
        self.control(stream=str(REFUSAL_STREAM), rename=False)
        record = self.probe(max_tools=0)
        self.assertEqual(record["stop_reason"], "result")

    def test_tool_budget_stops_the_probe(self):
        self.control(stream=str(REFUSAL_STREAM), rename=False)
        record = self.probe(max_tools=2)
        self.assertEqual(record["stop_reason"], "max_tools")
        self.assertEqual(record["status"], "no_trigger")
        self.assertLessEqual(len(record["tools"]), 2)

    def test_output_arriving_all_at_once_is_still_parsed(self):
        """research/02 F6: the old loop appended the post-exit read to a buffer
        it then never parsed, discarding any trigger in that chunk."""
        self.control(stream=str(TRIGGER_STREAM), rename=True, delay_before=0)
        record = self.probe()
        self.assertEqual(record["status"], "trigger", record)

    def test_detection_works_without_partial_messages(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        record = self.probe(include_partial_messages=False)
        self.assertEqual(record["status"], "trigger", record)

    def test_clone_registration_is_read_off_the_init_event(self):
        """research/02 F5: an installed copy of the skill under test shadows the
        probe and pins recall at 0% with no other symptom, so the harness reads
        its own visibility out of the session's init event."""
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        record = self.probe(skill_name="widget-forge")
        self.assertTrue(record["clone_registered"])
        self.assertEqual(record["competing_skills"], [])

    def test_unregistered_clone_is_visible(self):
        # rename=False leaves the capture's own clone name, so this probe's
        # clone is not in the replayed slash_commands list.
        self.control(stream=str(TRIGGER_STREAM), rename=False)
        record = self.probe(max_tools=0)
        self.assertFalse(record["clone_registered"])

    def test_competing_installed_skill_is_detected(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        record = self.probe(skill_name="dataviz")
        self.assertIn("dataviz", record["competing_skills"])

    def test_result_cost_is_captured(self):
        self.control(stream=str(TRIGGER_STREAM), rename=False)
        record = self.probe(max_tools=0)
        self.assertIsInstance(record["cost_usd"], float)
        self.assertGreater(record["cost_usd"], 0)


class TestErrorsAreNotNonTriggers(StubHarness):
    """C8: a probe that fails for any reason other than a clean non-trigger is
    recorded as `error` and excluded from scoring."""

    def test_timeout_is_an_error(self):
        self.control(mode="silent", hang_seconds=30)
        record = self.probe(timeout=2)
        self.assertEqual(record["status"], "error", record)
        self.assertIsNone(record["triggered"])
        self.assertEqual(record["stop_reason"], "timeout")
        self.assertIn("timeout", record["error"])

    def test_missing_cli_is_an_error(self):
        os.environ["BETTER_SKILL_CREATOR_CLAUDE_ARGV"] = json.dumps(
            [str(self.tmp / "definitely-not-a-real-binary")]
        )
        record = self.probe(timeout=10)
        self.assertEqual(record["status"], "error", record)
        self.assertIsNone(record["triggered"])

    def test_nonzero_exit_without_result_is_an_error(self):
        self.control(mode="empty", exit_code=1, stderr="Invalid API key\n")
        record = self.probe(timeout=15)
        self.assertEqual(record["status"], "error", record)
        self.assertIn("returncode=1", record["error"])
        self.assertIn("Invalid API key", record["error"])

    def test_stream_that_never_reaches_result_is_an_error(self):
        self.control(stream=str(REFUSAL_STREAM), rename=False, drop_result=True)
        record = self.probe(max_tools=0, timeout=15)
        self.assertEqual(record["status"], "error", record)
        self.assertIn("without emitting a result event", record["error"])


class TestIsolation(StubHarness):
    """C8: every probe runs in its own temporary project root."""

    def test_probe_root_is_temporary_and_holds_exactly_one_clone(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        record = self.probe()
        report = self.stub_report()
        root = Path(report["cwd"])
        self.assertEqual(
            len(report["command_files"]), 1,
            "a probe must never see a sibling's clone: 1.7% vs 38.3% measured recall",
        )
        self.assertTrue(
            str(root).startswith(str(Path(tempfile.gettempdir()).resolve()))
            or str(root).startswith(tempfile.gettempdir()),
            f"probe cwd {root} is not under the OS temp dir",
        )
        self.assertIn(run_eval_mod.PROBE_ROOT_PREFIX, root.name)
        self.assertEqual(record["probe_root"], str(root))

    def test_probe_root_is_removed_afterwards(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        record = self.probe()
        self.assertFalse(Path(record["probe_root"]).exists())
        self.assertNotIn(record["probe_root"], run_eval_mod._OWNED_ROOTS)

    def test_nothing_is_written_into_the_working_directory(self):
        """find_project_root() resolved to a drive root on the audit machine and
        created D:\\.claude\\commands\\. The probe must not go near cwd."""
        project = self.tmp / "live-project"
        (project / ".claude").mkdir(parents=True)
        before = sorted(p.name for p in (project / ".claude").iterdir())
        cwd = os.getcwd()
        os.chdir(project)
        try:
            self.control(stream=str(TRIGGER_STREAM), rename=True)
            self.probe()
        finally:
            os.chdir(cwd)
        after = sorted(p.name for p in (project / ".claude").iterdir())
        self.assertEqual(before, after)
        self.assertFalse((project / ".claude" / "commands").exists())

    def test_scaffold_is_copied_without_its_dot_claude(self):
        scaffold = self.tmp / "scaffold"
        (scaffold / ".claude" / "commands").mkdir(parents=True)
        (scaffold / ".claude" / "commands" / "leftover.md").write_text("x", encoding="utf-8")
        (scaffold / "src").mkdir()
        (scaffold / "src" / "dedupe.py").write_text("def f(): pass\n", encoding="utf-8")
        (scaffold / "CLAUDE.md").write_text("house rules\n", encoding="utf-8")

        self.control(stream=str(TRIGGER_STREAM), rename=True)
        self.probe(scaffold=str(scaffold))
        report = self.stub_report()
        self.assertIn("src", report["root_entries"])
        self.assertIn("CLAUDE.md", report["root_entries"])
        self.assertEqual(report["command_files"], report["command_files"][:1])
        self.assertEqual(len(report["command_files"]), 1)
        self.assertNotIn("leftover", " ".join(report["command_files"]))

    def test_claudecode_env_is_stripped_so_nesting_works(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            self.probe()
        self.assertFalse(self.stub_report()["has_claudecode_env"])


class TestProbeFlagsReachTheChild(StubHarness):
    """V7 flagged `--permission-mode` and `--no-partial-messages` as pure
    passthrough with nothing exercising them. They are kept rather than cut --
    `--permission-mode` is the C8 blast-radius knob the spend projection points
    the reader at, and disabling partial messages is the escape hatch for a CLI
    whose partial stream is malformed -- so they get a test instead."""

    def test_permission_mode_is_forwarded_to_claude(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        self.probe(permission_mode="plan")
        argv = self.stub_report()["argv"]
        self.assertIn("--permission-mode", argv)
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "plan")

    def test_permission_mode_is_absent_when_unset(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        self.probe()
        self.assertNotIn("--permission-mode", self.stub_report()["argv"])

    def test_partial_messages_are_requested_by_default(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        self.probe()
        self.assertIn("--include-partial-messages", self.stub_report()["argv"])

    def test_no_partial_messages_removes_the_flag_but_not_the_verdict(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        record = self.probe(include_partial_messages=False)
        self.assertNotIn("--include-partial-messages", self.stub_report()["argv"])
        self.assertEqual(record["status"], "trigger", record)

    def test_setting_sources_is_forwarded(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        self.probe(setting_sources="project")
        argv = self.stub_report()["argv"]
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "project")

    def test_sessions_are_never_persisted(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        self.probe()
        self.assertIn("--no-session-persistence", self.stub_report()["argv"])


class TestCommandFileEncoding(StubHarness):
    """C7: every write specifies encoding='utf-8'."""

    def test_non_ascii_description_survives_the_round_trip(self):
        description = "Use for café reports — naïve triage → escalation. 中文测试."
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        record = self.probe(description=description)
        self.assertNotEqual(record["status"], "error", record)
        written = self.stub_report()["command_file_text"]
        self.assertIn(description, written)


class TestSkillMdEncodingGuard(unittest.TestCase):
    """research/01 F2: a locale-codec read of SKILL.md returns a description the
    author never wrote, without raising. `scripts/utils.parse_skill_md` now
    decodes UTF-8 explicitly, so this guard should be a permanent no-op — the
    tests assert both halves: that it passes today, and that it still fires if
    the parser ever regresses."""

    def test_ascii_skill_passes(self):
        check_skill_md_encoding(FIXTURES / "probe-skill")

    def test_utf8_skill_passes(self):
        # Non-ASCII whose UTF-8 bytes are all cp1252-defined: the silent case.
        check_skill_md_encoding(FIXTURES / "mojibake-skill")

    def test_undecodable_bytes_skill_passes(self):
        # Contains U+2001, whose UTF-8 bytes include 0x81 (undefined in cp1252).
        check_skill_md_encoding(FIXTURES / "nonascii-skill")

    def test_platform_default_here_would_have_corrupted_it(self):
        """Documents that this machine really is the hazardous configuration."""
        if locale.getpreferredencoding(False).lower().replace("-", "") in ("utf8", "cp65001"):
            self.skipTest("platform default is already UTF-8")
        path = FIXTURES / "mojibake-skill" / "SKILL.md"
        self.assertNotEqual(path.read_text(), path.read_bytes().decode("utf-8"))

    def test_guard_fires_if_the_parser_regresses(self):
        def locale_decoded(skill_path):
            raw = (skill_path / "SKILL.md").read_bytes()
            corrupted = raw.decode("utf-8").encode("utf-8").decode("cp1252")
            return "mojibake-skill", "", corrupted

        with mock.patch.object(run_eval_mod, "parse_skill_md", locale_decoded):
            with self.assertRaises(SystemExit) as ctx:
                check_skill_md_encoding(FIXTURES / "mojibake-skill")
        self.assertEqual(ctx.exception.code, 1)

    def test_guard_reports_a_parse_failure_instead_of_a_traceback(self):
        from scripts.utils import SkillMdError

        def boom(skill_path):
            raise SkillMdError("SKILL.md missing frontmatter (no opening ---)")

        with mock.patch.object(run_eval_mod, "parse_skill_md", boom):
            with self.assertRaises(SystemExit) as ctx:
                check_skill_md_encoding(FIXTURES / "probe-skill")
        self.assertEqual(ctx.exception.code, 1)

    def test_guard_runs_before_the_spend_gate_in_every_entry_point(self):
        """An unparseable SKILL.md must stop the run before any probe is
        launched, in all three CLIs that read one."""
        import ast

        for module, fn in (
            ("run_eval.py", "main"),
            ("run_loop.py", "main"),
            ("improve_description.py", "main"),
        ):
            tree = ast.parse((SKILL_ROOT / "scripts" / module).read_text(encoding="utf-8"))
            main_fn = next(
                n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == fn
            )
            names = [
                n.func.id
                for n in ast.walk(main_fn)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            ]
            self.assertIn("check_skill_md_encoding", names, module)
            if "project_spend" in names:
                self.assertLess(
                    names.index("check_skill_md_encoding"),
                    names.index("project_spend"),
                    f"{module}: SKILL.md is validated after the spend gate",
                )


def _fake_probe(status_by_query):
    """Build a run_single_query replacement driven by a query -> [status] map."""
    calls: dict[str, int] = {}

    def fake(query, skill_name, skill_description, timeout, *args, **kwargs):
        idx = calls.get(query, 0)
        calls[query] = idx + 1
        statuses = status_by_query[query]
        status = statuses[idx % len(statuses)]
        return {
            "query": query,
            "probe_id": f"{skill_name}-skill-deadbeef",
            "status": status,
            "triggered": {"trigger": True, "no_trigger": False, "error": None}[status],
            "stop_reason": status,
            "error": "stubbed failure" if status == "error" else None,
            "tools": [],
            "elapsed_seconds": 0.0,
            "cost_usd": 0.01,
            "probe_root": None,
        }

    return fake


class TestAggregation(unittest.TestCase):
    """C4/C8: errored probes are excluded, never counted as non-triggers."""

    def _run(self, eval_set, status_by_query, runs=3, **kwargs):
        with mock.patch.object(run_eval_mod, "run_single_query", _fake_probe(status_by_query)):
            return run_eval(
                eval_set=eval_set,
                skill_name="widget-forge",
                description=DESCRIPTION,
                num_workers=2,
                timeout=5,
                runs_per_query=runs,
                **kwargs,
            )

    def test_errored_runs_are_excluded_from_the_denominator(self):
        eval_set = [{"query": "positive", "should_trigger": True}]
        out = self._run(eval_set, {"positive": ["trigger", "error", "trigger"]})
        row = out["results"][0]
        self.assertEqual(row["runs"], 2)
        self.assertEqual(row["triggers"], 2)
        self.assertEqual(row["errored"], 1)
        self.assertEqual(row["trigger_rate"], 1.0)
        self.assertTrue(row["pass"])

    def test_a_fully_errored_query_has_no_verdict(self):
        """The whole point. A dead harness used to score every negative as a
        pass, producing precision 100% / recall 0% — which reads as a diagnosis
        of the description rather than of the harness."""
        eval_set = [
            {"query": "positive", "should_trigger": True},
            {"query": "negative", "should_trigger": False},
        ]
        out = self._run(eval_set, {"positive": ["error"], "negative": ["error"]})
        for row in out["results"]:
            self.assertIsNone(row["pass"])
            self.assertIsNone(row["trigger_rate"])
            self.assertEqual(row["runs"], 0)
            self.assertEqual(row["status"], "errored")
        self.assertEqual(out["summary"]["passed"], 0)
        self.assertEqual(out["summary"]["failed"], 0)
        self.assertEqual(out["summary"]["errored"], 2)
        self.assertEqual(out["summary"]["scored_runs"], 0)
        self.assertEqual(out["summary"]["errored_runs"], 6)

    def test_error_carries_its_message(self):
        eval_set = [{"query": "positive", "should_trigger": True}]
        out = self._run(eval_set, {"positive": ["error"]}, runs=1)
        self.assertEqual(out["results"][0]["errors"], ["stubbed failure"])

    def test_duplicate_query_strings_stay_separate_rows(self):
        """research/02 F17: keying by query text pooled duplicates into one row
        and let the last item's should_trigger win."""
        eval_set = [
            {"query": "same text", "should_trigger": True},
            {"query": "same text", "should_trigger": False},
        ]
        out = self._run(eval_set, {"same text": ["no_trigger"]}, runs=1)
        self.assertEqual(len(out["results"]), 2)
        self.assertEqual([r["should_trigger"] for r in out["results"]], [True, False])
        self.assertEqual([r["index"] for r in out["results"]], [0, 1])

    def test_actual_cost_is_reported(self):
        eval_set = [{"query": "positive", "should_trigger": True}]
        out = self._run(eval_set, {"positive": ["trigger"]}, runs=2)
        self.assertAlmostEqual(out["summary"]["actual_cost_usd"], 0.02, places=4)


class TestSpendGate(unittest.TestCase):
    """C8: print the projection and bound the run before spending anything."""

    def test_refuses_above_max_cost(self):
        with self.assertRaises(SystemExit) as ctx:
            project_spend(
                n_queries=20, runs_per_query=3, iterations=5, model="opus",
                cost_per_probe=None, max_cost=10.0, confirm_threshold=1000.0,
                assume_yes=True,
            )
        self.assertEqual(ctx.exception.code, 2)

    def test_allows_a_bounded_run(self):
        projection = project_spend(
            n_queries=2, runs_per_query=1, iterations=1, model="haiku",
            cost_per_probe=0.01, max_cost=10.0, confirm_threshold=1000.0,
            assume_yes=True,
        )
        self.assertEqual(projection["probes"], 2)
        self.assertAlmostEqual(projection["estimated_total_usd"], 0.02, places=4)

    def test_requires_confirmation_above_threshold_when_not_interactive(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            with self.assertRaises(SystemExit) as ctx:
                project_spend(
                    n_queries=100, runs_per_query=3, iterations=1, model="opus",
                    cost_per_probe=0.4, max_cost=1e9, confirm_threshold=1.0,
                    assume_yes=False,
                )
        self.assertEqual(ctx.exception.code, 2)

    def test_projection_scales_with_iterations(self):
        projection = project_spend(
            n_queries=10, runs_per_query=3, iterations=5, model="haiku",
            cost_per_probe=0.001, max_cost=10.0, confirm_threshold=1000.0,
            assume_yes=True, label="optimization loop",
        )
        self.assertEqual(projection["probes"], 150)


class _FakeTty(io.StringIO):
    """A stream that claims to be a terminal and is not.

    This is not a contrived object: it is what Windows hands you for `NUL` and
    for `subprocess.DEVNULL`, where `isatty()` returns True and the first read
    is already EOF.
    """

    def isatty(self):
        return True


class TestConfirmationIsNeverInferredFromIsatty(unittest.TestCase):
    """R26.

    `project_spend` guarded its `input()` with `if not sys.stdin.isatty()`.
    On Windows `isatty()` returns **True** for NUL and DEVNULL, so the guard
    missed and `input()` raised an uncaught EOFError -- the spend guard killed
    the run it was added to make safe, at the documented defaults, before any
    probe launched.
    """

    def test_eof_on_a_stream_claiming_to_be_a_terminal_is_not_a_confirmation(self):
        with mock.patch.object(sys, "stdin", _FakeTty("")):
            self.assertIsNone(read_confirmation("proceed? "))

    def test_a_non_terminal_stream_is_not_asked_at_all(self):
        with mock.patch.object(sys, "stdin", io.StringIO("y\n")):
            self.assertIsNone(read_confirmation("proceed? "))

    def test_a_closed_stream_is_not_a_confirmation(self):
        stream = _FakeTty("y\n")
        stream.close()
        with mock.patch.object(sys, "stdin", stream):
            self.assertIsNone(read_confirmation("proceed? "))

    def test_a_detached_stdin_is_not_a_confirmation(self):
        with mock.patch.object(sys, "stdin", None):
            self.assertIsNone(read_confirmation("proceed? "))

    def test_a_real_answer_is_returned_verbatim(self):
        with mock.patch.object(sys, "stdin", _FakeTty("Yes\n")):
            self.assertEqual(read_confirmation("proceed? "), "Yes")

    def test_eof_at_the_spend_gate_refuses_rather_than_raising(self):
        with mock.patch.object(sys, "stdin", _FakeTty("")):
            with self.assertRaises(SystemExit) as ctx:
                project_spend(
                    n_queries=100, runs_per_query=3, iterations=1, model="opus",
                    cost_per_probe=0.4, max_cost=1e9, confirm_threshold=1.0,
                    assume_yes=False,
                )
        self.assertEqual(ctx.exception.code, 2)

    def test_a_typed_yes_proceeds(self):
        for answer in ("y\n", "Y\n", "yes\n", "  YES  \n"):
            with self.subTest(answer=answer):
                with mock.patch.object(sys, "stdin", _FakeTty(answer)):
                    projection = project_spend(
                        n_queries=10, runs_per_query=1, iterations=1, model="haiku",
                        cost_per_probe=0.4, max_cost=1e9, confirm_threshold=1.0,
                        assume_yes=False,
                    )
                self.assertEqual(projection["probes"], 10)

    def test_anything_other_than_yes_aborts(self):
        for answer in ("n\n", "\n", "maybe\n", "yep\n"):
            with self.subTest(answer=answer):
                with mock.patch.object(sys, "stdin", _FakeTty(answer)):
                    with self.assertRaises(SystemExit) as ctx:
                        project_spend(
                            n_queries=10, runs_per_query=1, iterations=1, model="haiku",
                            cost_per_probe=0.4, max_cost=1e9, confirm_threshold=1.0,
                            assume_yes=False,
                        )
                self.assertEqual(ctx.exception.code, 2)

    def test_max_cost_refuses_before_any_confirmation_is_sought(self):
        asked = []
        with mock.patch.object(run_eval_mod, "read_confirmation", asked.append):
            with self.assertRaises(SystemExit):
                project_spend(
                    n_queries=100, runs_per_query=3, iterations=5, model="opus",
                    cost_per_probe=0.4, max_cost=1.0, confirm_threshold=0.5,
                    assume_yes=False,
                )
        self.assertEqual(asked, [], "--max-cost is a refusal, not a question")


class TestEvalSetShape(unittest.TestCase):
    """R27. `load_json_file` proves the file is UTF-8 and valid JSON and stops
    there, so a wrong *shape* arrived as a bare TypeError/KeyError from inside
    the driver -- and a missing `should_trigger` surfaced only at scoring time,
    with every probe already paid for."""

    def test_a_well_formed_set_passes_through_unchanged(self):
        good = [{"query": "a", "should_trigger": True},
                {"query": "b", "should_trigger": False, "id": "b-1"}]
        self.assertIs(validate_eval_set(good), good)

    def test_the_queries_wrapper_is_named_and_refused(self):
        with self.assertRaises(EvalSetError) as ctx:
            validate_eval_set({"queries": [{"query": "a", "should_trigger": True}]})
        self.assertIn('wrapped under the key "queries"', str(ctx.exception))

    def test_a_bare_string_list_is_refused(self):
        with self.assertRaises(EvalSetError) as ctx:
            validate_eval_set(["a", "b"])
        self.assertIn("item 0 is a str", str(ctx.exception))

    def test_a_missing_query_key_names_the_keys_that_are_there(self):
        with self.assertRaises(EvalSetError) as ctx:
            validate_eval_set([{"q": "a", "should_trigger": True}])
        self.assertIn('has no "query" key', str(ctx.exception))
        self.assertIn("'q'", str(ctx.exception))

    def test_a_missing_should_trigger_is_caught_before_any_probe(self):
        with self.assertRaises(EvalSetError) as ctx:
            validate_eval_set([{"query": "a"}])
        self.assertIn('has no "should_trigger" key', str(ctx.exception))

    def test_a_stringy_should_trigger_is_refused_because_it_is_truthy(self):
        """The dangerous one. "false" is a non-empty string, so a negative query
        would have been scored as a positive with no error anywhere."""
        with self.assertRaises(EvalSetError) as ctx:
            validate_eval_set([{"query": "a", "should_trigger": "false"}])
        message = str(ctx.exception)
        self.assertIn("not a boolean", message)
        self.assertIn("truthy", message)

    def test_an_empty_array_is_refused_rather_than_run(self):
        with self.assertRaises(EvalSetError) as ctx:
            validate_eval_set([])
        self.assertIn("nothing to measure", str(ctx.exception))

    def test_a_non_container_top_level_is_refused(self):
        with self.assertRaises(EvalSetError) as ctx:
            validate_eval_set("just a string")
        self.assertIn("not an array", str(ctx.exception))

    def test_every_problem_is_reported_not_only_the_first(self):
        with self.assertRaises(EvalSetError) as ctx:
            validate_eval_set([
                {"query": "ok", "should_trigger": True},
                {"should_trigger": True},
                {"query": "", "should_trigger": True},
                {"query": "c", "should_trigger": 1},
            ])
        message = str(ctx.exception)
        self.assertIn("Found 3 problem(s)", message)
        self.assertIn("item 1", message)
        self.assertIn("item 2", message)
        self.assertIn("item 3", message)

    def test_a_long_problem_list_is_capped_and_says_so(self):
        with self.assertRaises(EvalSetError) as ctx:
            validate_eval_set([{"nope": i} for i in range(30)])
        self.assertIn("and 40 more", str(ctx.exception))

    def test_the_message_shows_the_shape_that_would_have_worked(self):
        with self.assertRaises(EvalSetError) as ctx:
            validate_eval_set({"queries": []})
        message = str(ctx.exception)
        self.assertIn('"should_trigger": true', message)
        self.assertIn('"query"', message)

    def test_the_library_entry_point_refuses_too(self):
        """run_loop and any other caller reach run_eval() directly."""
        with self.assertRaises(EvalSetError):
            run_eval(
                eval_set=[{"query": "a"}], skill_name="widget-forge",
                description=DESCRIPTION, num_workers=1, timeout=5,
            )


class TestCliRefusesNonInteractively(unittest.TestCase):
    """The end-to-end shape of R26 and R27 through `python -m scripts.run_eval`,
    with stdin from DEVNULL -- the configuration that used to traceback."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="run-eval-cli-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "scripts.run_eval", *args],
            cwd=str(SKILL_ROOT), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=180,
        )

    def _evals(self, payload):
        path = self.tmp / "evals.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    def test_over_threshold_refuses_without_an_eoferror(self):
        evals = self._evals([{"query": f"q{i}", "should_trigger": i % 2 == 0}
                             for i in range(20)])
        proc = self._run("--eval-set", evals, "--skill-path", str(FIXTURES / "probe-skill"),
                         "--max-cost", "1000", "--model", "opus")
        self.assertEqual(proc.returncode, 2, proc.stderr[-2000:])
        self.assertNotIn("EOFError", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("Refusing to start", proc.stderr)

    def test_a_wrapped_eval_set_refuses_without_a_traceback(self):
        evals = self._evals({"queries": [{"query": "a", "should_trigger": True}]})
        proc = self._run("--eval-set", evals, "--skill-path", str(FIXTURES / "probe-skill"),
                         "--yes")
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn('wrapped under the key "queries"', proc.stderr)


class TestSplitGuard(unittest.TestCase):
    """research/02 F11: a train split with no positives cannot fail, so the loop
    announces success on iteration 1."""

    def _mk(self, pos, neg):
        return (
            [{"query": f"p{i}", "should_trigger": True} for i in range(pos)]
            + [{"query": f"n{i}", "should_trigger": False} for i in range(neg)]
        )

    def test_single_positive_is_refused(self):
        with self.assertRaises(ValueError) as ctx:
            split_eval_set(self._mk(1, 10), holdout=0.4)
        self.assertIn("cannot fail", str(ctx.exception))

    def test_one_of_each_is_refused(self):
        with self.assertRaises(ValueError):
            split_eval_set(self._mk(1, 1), holdout=0.4)

    def test_balanced_set_splits(self):
        train, test = split_eval_set(self._mk(10, 10), holdout=0.4)
        self.assertEqual(len(train), 12)
        self.assertEqual(len(test), 8)
        self.assertEqual(sum(1 for e in train if e["should_trigger"]), 6)


class TestReport(unittest.TestCase):
    def _payload(self, **overrides):
        data = {
            "original_description": "before —",
            "best_description": "after ✓",
            "best_score": "1/2",
            "best_test_score": "1/2",
            "best_train_score": "1/2",
            "iterations_run": 1,
            "train_size": 2,
            "test_size": 0,
            "holdout": 0,
            "history": [{
                "iteration": 1,
                "description": "after ✓",
                "train_passed": 1,
                "train_failed": 0,
                "train_total": 2,
                "train_results": [
                    {"query": "positive", "should_trigger": True, "pass": True,
                     "triggers": 3, "runs": 3, "errored": 0},
                    {"query": "unmeasured", "should_trigger": False, "pass": None,
                     "triggers": 0, "runs": 0, "errored": 3},
                ],
                "test_results": None,
                "test_passed": None,
                "test_total": None,
            }],
        }
        data.update(overrides)
        return data

    def test_errored_cell_is_not_rendered_as_a_failure(self):
        html_out = generate_html(self._payload(), skill_name="widget-forge")
        self.assertIn('class="result errored"', html_out)
        self.assertIn("3 err", html_out)
        # An unmeasured cell must not claim 0/0 or a red cross.
        self.assertNotIn(">✗<span class=\"rate\">0/0<", html_out)

    def test_warning_banner_renders(self):
        html_out = generate_html(self._payload(
            apply_recommended=False,
            measurement_warnings=["recall is 0% across all 1 iteration(s)"],
        ))
        self.assertIn("Do not apply this description", html_out)
        self.assertIn("recall is 0%", html_out)

    def test_report_writes_as_utf8(self):
        html_out = generate_html(self._payload(), skill_name="widget-forge")
        tmp = Path(tempfile.mkdtemp(prefix="report-test-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        target = tmp / "report.html"
        target.write_text(html_out, encoding="utf-8")
        self.assertEqual(target.read_text(encoding="utf-8"), html_out)
        self.assertIn("✓", target.read_bytes().decode("utf-8"))


class TestReportCli(unittest.TestCase):
    """`scripts.generate_report` is the surface the person actually reads. Its
    main() was untested, including both of its refusal paths."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="report-cli-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    PAYLOAD = {
        "original_description": "before —",
        "best_description": "after ✓ 中文",
        "best_score": "1/2",
        "iterations_run": 1,
        "train_size": 2,
        "test_size": 0,
        "holdout": 0,
        "history": [{
            "iteration": 1, "description": "after ✓ 中文",
            "train_passed": 1, "train_failed": 1, "train_total": 2,
            "train_results": [
                {"query": "positive", "should_trigger": True, "pass": True,
                 "triggers": 3, "runs": 3, "errored": 0},
                {"query": "négative — 中文", "should_trigger": False, "pass": False,
                 "triggers": 3, "runs": 3, "errored": 0},
            ],
            "test_results": None, "test_passed": None, "test_total": None,
        }],
    }

    def _run(self, *args, stdin_text=None):
        return subprocess.run(
            [sys.executable, "-m", "scripts.generate_report", *args],
            cwd=str(SKILL_ROOT),
            input=stdin_text,
            stdin=None if stdin_text is not None else subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=120,
        )

    def _payload_file(self, payload=None):
        path = self.tmp / "results.json"
        path.write_text(json.dumps(payload or self.PAYLOAD), encoding="utf-8")
        return str(path)

    def test_a_file_renders_to_stdout(self):
        proc = self._run(self._payload_file())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("<html", proc.stdout.lower())
        self.assertIn("中文", proc.stdout)

    def test_stdin_input_is_accepted(self):
        proc = self._run("-", stdin_text=json.dumps(self.PAYLOAD))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("<html", proc.stdout.lower())

    def test_the_output_file_is_written_as_utf8(self):
        target = self.tmp / "report.html"
        proc = self._run(self._payload_file(), "-o", str(target),
                         "--skill-name", "widget-forge")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = target.read_bytes().decode("utf-8")
        self.assertIn("中文", body)
        self.assertIn("widget-forge", body)
        self.assertIn("Report written to", proc.stderr)

    def test_invalid_json_is_refused_with_a_sentence(self):
        path = self.tmp / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        proc = self._run(str(path))
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("not valid JSON", proc.stderr)

    def test_the_wrong_json_file_is_refused_with_a_sentence(self):
        """`--input` is a path a person types, so pointing it at an eval set
        instead of a results file is the expected mistake. It used to raise a
        bare AttributeError from the first line of rendering."""
        path = self.tmp / "eval-set.json"
        path.write_text(json.dumps([{"query": "a", "should_trigger": True}]),
                        encoding="utf-8")
        proc = self._run(str(path))
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("not an object", proc.stderr)
        self.assertIn("run_loop", proc.stderr)

    def test_an_object_without_history_is_refused(self):
        path = self.tmp / "other.json"
        path.write_text(json.dumps({"summary": {}, "results": []}), encoding="utf-8")
        proc = self._run(str(path))
        self.assertEqual(proc.returncode, 1)
        self.assertIn('no "history" key', proc.stderr)

    def test_non_utf8_input_is_refused_with_a_sentence(self):
        """C7: UnicodeDecodeError is not caught by (JSONDecodeError, OSError)."""
        path = self.tmp / "utf16.json"
        path.write_bytes(json.dumps(self.PAYLOAD).encode("utf-16"))
        proc = self._run(str(path))
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("not valid UTF-8", proc.stderr)


class TestModuleDocumentation(unittest.TestCase):
    """The docstring used to assert the command file 'appears in Claude's
    available_skills list'. An executed probe found the name in the init event's
    slash_commands array (57 entries) and not in skills (29 entries)."""

    def test_docstring_states_the_measured_surface(self):
        doc = run_eval_mod.__doc__ or ""
        self.assertIn("slash_commands", doc)
        self.assertIn("absent from", doc)
        self.assertIn("wrong as stated", doc)
        self.assertIn("proxy", doc)

    def test_captured_init_event_still_backs_the_claim(self):
        """The capture is from a real probe: the clone is in slash_commands and
        is absent from skills."""
        first = json.loads(TRIGGER_STREAM.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(first.get("subtype"), "init")
        import re

        clone_re = re.compile(r"^[a-z0-9-]+-skill-[0-9a-f]{8}$")
        clones = [c for c in first["slash_commands"] if clone_re.match(c)]
        self.assertTrue(clones, "capture should contain the probe's clone")
        for clone in clones:
            self.assertIn(clone, first["slash_commands"])
            self.assertNotIn(clone, first["skills"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
