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
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts import run_eval as run_eval_mod  # noqa: E402
from scripts.generate_report import generate_html  # noqa: E402
from scripts.run_eval import (  # noqa: E402
    INHERIT_PERMISSION_MODE,
    OUTSTANDING_JOB_BUFFER,
    PERMISSION_MODE_RISK,
    PERMISSION_MODES,
    SAFE_PERMISSION_MODE,
    SAFE_PERMISSION_MODES,
    EvalSetError,
    PermissionModeError,
    ProbeArgumentError,
    ScaffoldError,
    check_permission_mode,
    check_probe_arguments,
    check_scaffold,
    check_skill_md_encoding,
    project_spend,
    read_confirmation,
    run_eval,
    run_single_query,
    validate_eval_set,
    validate_permission_mode,
    validate_probe_arguments,
    validate_scaffold,
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
    `--permission-mode` decides what a probe may do to this machine, and
    disabling partial messages is the escape hatch for a CLI whose partial
    stream is malformed -- so they get a test instead.

    `--permission-mode` is no longer passthrough. It defaults to
    SAFE_PERMISSION_MODE, and the assertion that used to live here --
    `test_permission_mode_is_absent_when_unset` -- pinned the opposite contract:
    a caller who said nothing got a session with this machine's permissions.
    Its replacements are in TestPermissionPolicy below."""

    def test_permission_mode_is_forwarded_to_claude(self):
        # `manual` rather than `plan`: an explicitly chosen mode still reaches
        # the child, and this one needs no opt-in to choose. `plan` does need
        # one -- see TestPermissionPolicy.test_plan_is_not_treated_as_safe.
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        self.probe(permission_mode="manual")
        argv = self.stub_report()["argv"]
        self.assertIn("--permission-mode", argv)
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "manual")

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


class TestPermissionPolicy(StubHarness):
    """A probe is a full Claude Code session on this machine, driven by an eval
    set's queries and by the SKILL.md under test -- both of which arrived from
    wherever the skill did. `--permission-mode` used to default to unset, which
    is the CLI's "take this machine's permission settings", and the flag's own
    help said so. Third-party text therefore ran with the host's capabilities
    unless somebody had thought to pass a flag.

    Every assertion below reads the argv the child was launched with. Nothing
    here runs a model, and nothing here proves what the CLI *does* with a mode
    -- that is documented behaviour, recorded at SAFE_PERMISSION_MODE. What is
    proved is which bytes reach the command line, which is the half this
    repository owns."""

    def test_a_probe_that_was_told_nothing_is_bounded(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        self.probe()
        argv = self.stub_report()["argv"]
        self.assertIn("--permission-mode", argv)
        self.assertEqual(
            argv[argv.index("--permission-mode") + 1], SAFE_PERMISSION_MODE
        )

    def test_none_means_no_opinion_and_lands_on_the_safe_mode(self):
        """The regression this whole change is about. `None` used to omit the
        flag, so a caller that had never considered permissions got the host's
        -- "I did not think about this" and "give it everything" were the same
        argument."""
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        self.probe(permission_mode=None)
        argv = self.stub_report()["argv"]
        self.assertEqual(
            argv[argv.index("--permission-mode") + 1], SAFE_PERMISSION_MODE
        )

    def test_inheriting_host_permissions_needs_the_opt_in(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        record = self.probe(permission_mode=INHERIT_PERMISSION_MODE)
        self.assertEqual(record["status"], "error", record)
        self.assertIn("--allow-host-permissions", record["error"])

    def test_the_opt_in_is_what_omits_the_flag(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        self.probe(
            permission_mode=INHERIT_PERMISSION_MODE, allow_host_permissions=True
        )
        self.assertNotIn("--permission-mode", self.stub_report()["argv"])

    def test_plan_is_not_treated_as_safe(self):
        """`plan` reads as the cautious choice and is not one: the published
        mode table gives `default` as "Reads only" and `plan` as "Reads, plus
        classifier-approved commands when auto mode is available". The old help
        text recommended it."""
        self.assertNotIn("plan", SAFE_PERMISSION_MODES)
        with self.assertRaises(PermissionModeError):
            validate_permission_mode("plan")
        self.assertEqual(
            validate_permission_mode("plan", allow_host_permissions=True), "plan"
        )

    def test_every_unsafe_mode_is_gated_and_every_gate_has_a_reason(self):
        for mode in PERMISSION_MODES:
            with self.subTest(mode=mode):
                if mode in SAFE_PERMISSION_MODES:
                    self.assertEqual(validate_permission_mode(mode), mode)
                    continue
                with self.assertRaises(PermissionModeError) as ctx:
                    validate_permission_mode(mode)
                # The refusal quotes the row rather than saying "unsafe": the
                # user picked the mode on purpose and is owed the reason.
                # Whitespace-flattened, because the message is wrapped to the
                # terminal and the risk string is one sentence inside it.
                flat = " ".join(str(ctx.exception).split())
                self.assertIn(" ".join(PERMISSION_MODE_RISK[mode].split()), flat)
                self.assertIn("--allow-host-permissions", str(ctx.exception))
                self.assertEqual(
                    validate_permission_mode(mode, allow_host_permissions=True), mode
                )

    def test_an_unknown_mode_is_refused_rather_than_forwarded(self):
        with self.assertRaises(PermissionModeError) as ctx:
            validate_permission_mode("readOnly", allow_host_permissions=True)
        self.assertIn("readOnly", str(ctx.exception))

    def test_the_driver_refuses_before_it_buys_a_session(self):
        """run_eval validates for itself, so a library caller that never goes
        through main() gets the same refusal -- and gets it before the pool
        exists rather than as one errored probe among many."""
        launched = []

        def fake(query, *args, **kwargs):
            launched.append(query)
            raise AssertionError("a probe was launched under a refused mode")

        with mock.patch.object(run_eval_mod, "run_single_query", fake):
            with self.assertRaises(PermissionModeError):
                run_eval(
                    eval_set=[{"query": "a", "should_trigger": True}],
                    skill_name="widget-forge", description=DESCRIPTION,
                    num_workers=1, timeout=5,
                    permission_mode=INHERIT_PERMISSION_MODE,
                )
        self.assertEqual(launched, [])

    def test_the_cli_gate_exits_one_and_names_the_way_out(self):
        with self.assertRaises(SystemExit) as ctx:
            check_permission_mode(INHERIT_PERMISSION_MODE, False)
        self.assertEqual(ctx.exception.code, 1)

    def test_the_cli_gate_says_out_loud_when_the_opt_in_was_used(self):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            mode = check_permission_mode(INHERIT_PERMISSION_MODE, True)
        self.assertEqual(mode, INHERIT_PERMISSION_MODE)
        self.assertIn("--allow-host-permissions", err.getvalue())

    def test_the_gate_runs_before_the_spend_gate_in_every_entry_point(self):
        """Refusing a mode after the projection means the user has been shown a
        bill and asked to approve it before anything checks what the sessions
        they are buying may do."""
        import ast

        for module in ("run_eval.py", "run_loop.py", "improve_description.py"):
            tree = ast.parse((SKILL_ROOT / "scripts" / module).read_text(encoding="utf-8"))
            main_fn = next(
                n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"
            )
            # Sorted by line, not by `ast.walk` order. `walk` is breadth-first,
            # so a `project_spend` nested one level inside an `if` or a `try`
            # sorts after an unnested call that really runs second -- and the
            # assertion passes while the gate is in the wrong place.
            names = [
                n.func.id
                for n in sorted(
                    (
                        n for n in ast.walk(main_fn)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    ),
                    key=lambda n: (n.lineno, n.col_offset),
                )
            ]
            self.assertIn("check_permission_mode", names, module)
            if "project_spend" in names:
                self.assertLess(
                    names.index("check_permission_mode"),
                    names.index("project_spend"),
                    f"{module}: the permission gate runs after the spend gate",
                )

    def test_the_opt_in_survives_the_trip_through_the_pool(self):
        """`run_eval` hands `run_single_query` eleven *positional* arguments
        through `executor.submit`, and this is the last of them. `run_eval`
        validates once for itself before the pool, so a forward that stops
        landing does not stop the run -- it starts, and then every probe
        re-validates without the opt-in and is recorded as `error`, which is
        also what a rate limit looks like. Asserted on the driver, because the
        worker is already pinned above and the tuple is not."""
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        out = run_eval(
            eval_set=[{"query": "i need a widget.toml manifest",
                       "should_trigger": True}],
            skill_name="widget-forge", description=DESCRIPTION,
            num_workers=1, timeout=60,
            permission_mode=INHERIT_PERMISSION_MODE,
            allow_host_permissions=True,
        )
        self.assertEqual(out["results"][0]["errored"], 0, out["results"])
        self.assertNotIn("--permission-mode", self.stub_report()["argv"])

    def test_the_projection_names_the_mode_it_is_pricing(self):
        """The banner is the one screen somebody reads before agreeing to
        spend, and `references/description-optimization.md` sends the reader
        here for the mode a number was measured under. The `inherit` branch is
        the load-bearing one: it is the only place the opt-in has a visible
        consequence at the moment money is approved."""
        def banner(mode):
            err = io.StringIO()
            with mock.patch("sys.stderr", err):
                project_spend(
                    n_queries=2, runs_per_query=1, iterations=1, model="haiku",
                    cost_per_probe=0.01, max_cost=10.0, confirm_threshold=1000.0,
                    assume_yes=True, permission_mode=mode,
                )
            return err.getvalue()

        safe = banner(SAFE_PERMISSION_MODE)
        self.assertIn(f"--permission-mode {SAFE_PERMISSION_MODE}", safe)
        self.assertIn("auto-denies", safe)
        self.assertIn("same mode", safe)
        # The text this replaced recommended `plan` here, which is looser than
        # the unset default it was offered as a bound on.
        self.assertNotIn("plan", safe)

        inherited = banner(INHERIT_PERMISSION_MODE)
        self.assertIn("no --permission-mode", inherited)
        self.assertNotIn("auto-denies", inherited)

        # `manual` prompts rather than auto-denying, and a headless probe has
        # nobody to answer -- so it must not borrow the default's sentence.
        prompting = banner("manual")
        self.assertIn("--permission-mode manual", prompting)
        self.assertNotIn("auto-denies", prompting)
        self.assertIn("error", prompting)

        for mode, risk in PERMISSION_MODE_RISK.items():
            if mode == INHERIT_PERMISSION_MODE:
                continue
            with self.subTest(mode=mode):
                named = banner(mode)
                self.assertIn(f"--permission-mode {mode}", named)

        # A caller that skipped check_permission_mode used to reach a KeyError
        # here, turning the spend gate into a traceback.
        self.assertIn(f"--permission-mode {SAFE_PERMISSION_MODE}", banner(None))

    def test_a_truthy_non_bool_does_not_open_the_gate(self):
        """A wrapper reading the opt-in out of an environment variable or a
        config file hands over the *string* "false", which is truthy. The gate
        fails closed on anything that is not the boolean itself; argparse's
        store_true gives a real bool, so no CLI path is affected."""
        for value in ("false", "0", "no", 1, [0], {"a": 1}):
            with self.subTest(value=value):
                with self.assertRaises(PermissionModeError):
                    validate_permission_mode(
                        "bypassPermissions", allow_host_permissions=value
                    )
        self.assertEqual(
            validate_permission_mode("bypassPermissions", allow_host_permissions=True),
            "bypassPermissions",
        )


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


def _fake_probe(status_by_query, cost_usd=0.01):
    """Build a run_single_query replacement driven by a query -> [status] map.

    `cost_usd` is what each record carries. It is deliberately settable to an
    int or to zero: the aggregator must treat both as measured cost, not as
    absent cost.
    """
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
            "cost_usd": cost_usd,
            "probe_root": None,
        }

    return fake


class TestAggregation(unittest.TestCase):
    """C4/C8: errored probes are excluded, never counted as non-triggers."""

    def _run(self, eval_set, status_by_query, runs=3, probe_cost=0.01, **kwargs):
        probe = _fake_probe(status_by_query, cost_usd=probe_cost)
        with mock.patch.object(run_eval_mod, "run_single_query", probe):
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

    def test_an_integer_cost_still_counts(self):
        """The sum site used to accept a bare float while the read site accepted
        (int, float). isinstance(5, float) is False, so an int-valued cost was
        dropped without a warning -- and if it were the only cost present, a
        billed run reported actual_cost_usd: None, i.e. 'nobody reported a
        cost'. Unreachable through the real worker, which coerces with float();
        reachable by any other producer of a record."""
        eval_set = [{"query": "positive", "should_trigger": True}]
        out = self._run(eval_set, {"positive": ["trigger"]}, runs=2, probe_cost=5)
        self.assertAlmostEqual(out["summary"]["actual_cost_usd"], 10.0, places=4)

    def test_a_measured_zero_reports_zero_not_none(self):
        """The have_cost latch, not `if total_cost`. Absent data is absent and
        never zero -- but the converse holds too: a cost that was measured and
        came back 0.0 is data, and must not be laundered into None."""
        eval_set = [{"query": "positive", "should_trigger": True}]
        out = self._run(eval_set, {"positive": ["trigger"]}, runs=2, probe_cost=0.0)
        self.assertIsNotNone(out["summary"]["actual_cost_usd"])
        self.assertEqual(out["summary"]["actual_cost_usd"], 0.0)


# Every wait below is bounded. A wedged driver must fail a test, never park a
# thread in CI: the worker's own gate expires on its own, the test's waits
# expire, and each test asserts the driver thread actually finished rather than
# leaving it running.
WORKER_GATE_SECONDS = 30.0
WINDOW_WAIT_SECONDS = 20.0
DRIVER_JOIN_SECONDS = 30.0
# Long enough for a driver that submits everything up front to have done so,
# short enough to cost nothing. The race-free check is `peak_outstanding` after
# the join; this one only makes the stall visible while it is happening.
WINDOW_SETTLE_SECONDS = 0.5

FAKE_PROBE_COST_USD = 0.01


class _WindowProbe:
    """A fake worker held on one event, plus an executor that counts submissions.

    Nothing here launches a `claude` subprocess. The worker is substituted for
    ``run_single_query`` as a bare module global, exactly the way the in-tree
    fakes are, and the executor is a subclass of the one ``run_eval`` reads out
    of its own module namespace, so counting submissions does not change how
    they are scheduled.

    Both counters are written on the driver thread only -- ``submit`` and
    ``on_record`` are both called from it -- so ``submitted - collected`` is
    exactly ``len(outstanding)`` at the moment a job is submitted.
    """

    def __init__(self, cost_usd: float = FAKE_PROBE_COST_USD):
        self.gate = threading.Event()
        self.lock = threading.Lock()
        self.cost_usd = cost_usd
        self.submitted = 0
        self.collected = 0
        self.peak_outstanding = 0
        self.started: list[str] = []
        self.records: list[dict] = []
        self.record_threads: set[int] = set()
        self.gate_timeouts = 0
        self._marks: dict[int, threading.Event] = {}

    # -- the worker --------------------------------------------------------

    def worker(self, query, skill_name, skill_description, timeout, *args, **kwargs):
        with self.lock:
            self.started.append(query)
        if not self.gate.wait(timeout=WORKER_GATE_SECONDS):
            with self.lock:
                self.gate_timeouts += 1
        # A float, deliberately: `isinstance(r.get("cost_usd"), float)` gates
        # cost accumulation, so an int here would be skipped silently.
        return {
            "query": query,
            "probe_id": f"{skill_name}-skill-deadbeef",
            "status": "no_trigger",
            "triggered": False,
            "stop_reason": "result",
            "error": None,
            "tools": [],
            "elapsed_seconds": 0.0,
            "cost_usd": self.cost_usd,
            "probe_root": None,
        }

    def release(self):
        self.gate.set()

    # -- the instrumented executor ----------------------------------------

    def executor_class(self):
        harness = self

        class CountingExecutor(run_eval_mod.ThreadPoolExecutor):
            def submit(self, fn, *args, **kwargs):
                harness._note_submission()
                return super().submit(fn, *args, **kwargs)

        return CountingExecutor

    def _note_submission(self):
        with self.lock:
            self.submitted += 1
            self.peak_outstanding = max(
                self.peak_outstanding, self.submitted - self.collected
            )
            mark = self._marks.get(self.submitted)
        if mark is not None:
            mark.set()

    def at_submission(self, count: int) -> threading.Event:
        """An event set the moment the *count*-th job is submitted."""
        mark = threading.Event()
        with self.lock:
            if self.submitted >= count:
                mark.set()
            else:
                self._marks[count] = mark
        return mark

    # -- collection --------------------------------------------------------

    def on_record(self, record):
        with self.lock:
            self.collected += 1
            self.records.append(record)
            self.record_threads.add(threading.get_ident())


def _probe_that_must_not_run(*args, **kwargs):
    raise AssertionError(
        "run_single_query was reached: a refused scheduling argument must never "
        "launch a billed probe"
    )


def _executor_that_must_not_exist(*args, **kwargs):
    raise AssertionError(
        "ThreadPoolExecutor was constructed: a refused scheduling argument must "
        "be refused before any job can be submitted"
    )


class _BoundedRunCase(unittest.TestCase):
    """Wiring shared by the scheduling tests. No `claude` is ever launched."""

    def harness(self, *, released: bool) -> _WindowProbe:
        probe = _WindowProbe()
        if released:
            probe.release()
        for attribute, replacement in (
            ("run_single_query", probe.worker),
            ("ThreadPoolExecutor", probe.executor_class()),
        ):
            patcher = mock.patch.object(run_eval_mod, attribute, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Registered before any driver thread exists, so it is the last thing to
        # run: a worker still parked on the gate is released even if an
        # assertion aborted the test first.
        self.addCleanup(probe.release)
        return probe

    def eval_set(self, n: int) -> list[dict]:
        # Distinct query strings: duplicates are a separate contract, and they
        # would make run_eval print a warning this test has no interest in.
        return [{"query": f"q{i:03d}", "should_trigger": i % 2 == 0} for i in range(n)]

    def drive_in_background(self, probe: _WindowProbe, **kwargs):
        """Run run_eval on its own thread and hand back (thread, outcome)."""
        outcome: dict = {}

        def drive():
            try:
                outcome["output"] = run_eval(
                    skill_name="widget-forge",
                    description=DESCRIPTION,
                    on_record=probe.on_record,
                    **kwargs,
                )
            except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
                outcome["error"] = exc

        thread = threading.Thread(target=drive, name="run-eval-driver", daemon=True)
        thread.start()
        self.addCleanup(self.finish, probe, thread)
        return thread, outcome

    def finish(self, probe: _WindowProbe, thread: threading.Thread) -> bool:
        probe.release()
        thread.join(timeout=DRIVER_JOIN_SECONDS)
        return not thread.is_alive()

    def run_bounded(self, probe: _WindowProbe, n_queries: int, runs: int, workers: int):
        """A whole run, start to finish, with every worker already released."""
        eval_set = self.eval_set(n_queries)
        thread, outcome = self.drive_in_background(
            probe,
            eval_set=eval_set,
            num_workers=workers,
            timeout=5,
            runs_per_query=runs,
        )
        self.assertTrue(
            self.finish(probe, thread), "the eval driver thread did not finish"
        )
        self.assertNotIn("error", outcome, f"run_eval raised: {outcome.get('error')!r}")
        self.assertEqual(probe.gate_timeouts, 0, "a fake worker sat on its gate")
        return eval_set, outcome["output"]


class TestOutstandingJobWindow(_BoundedRunCase):
    """The driver keeps at most `num_workers + OUTSTANDING_JOB_BUFFER` jobs
    submitted-but-not-collected, however large the eval set is.

    The previous driver built `jobs = [(i, item, r) for ...]` and submitted every
    one of them to the executor in a single dict comprehension before reading any
    result, draining with `as_completed`. The live *futures* therefore scaled with
    `len(eval_set) * runs_per_query` rather than with the worker count. Concurrent
    probe roots and billed `claude` sessions did not: those are created inside
    `run_single_query` and released in its `finally`, so they were capped at
    `num_workers` before this window existed exactly as they are after it.
    """

    def test_the_window_never_exceeds_num_workers_plus_the_buffer(self):
        """Pins the ceiling on submitted-but-not-collected jobs.

        Against the old code this fails twice over: with every worker parked on
        a cleared event, no future can complete, so nothing can legitimately be
        submitted past the window -- yet the old comprehension submitted all 40
        jobs before the first `as_completed` read, so both the stall assertion
        and the `peak_outstanding` assertion would see 40 where 5 is the bound.
        """
        workers = 3
        runs = 2
        eval_set = self.eval_set(20)
        total_jobs = len(eval_set) * runs
        window = workers + OUTSTANDING_JOB_BUFFER
        self.assertLess(window, total_jobs, "the bound must be the binding constraint")

        probe = self.harness(released=False)
        thread, outcome = self.drive_in_background(
            probe,
            eval_set=eval_set,
            num_workers=workers,
            timeout=5,
            runs_per_query=runs,
        )

        self.assertTrue(
            probe.at_submission(window).wait(timeout=WINDOW_WAIT_SECONDS),
            f"the driver never submitted {window} jobs",
        )
        # Every worker is still on the gate, so a completion -- and therefore a
        # further submission -- is impossible. A driver that submits anyway has
        # no window at all.
        time.sleep(WINDOW_SETTLE_SECONDS)
        with probe.lock:
            stalled_at = probe.submitted
        self.assertEqual(
            stalled_at, window,
            f"submission stalled at {stalled_at}, not at the {window}-job window "
            f"(total jobs: {total_jobs})",
        )
        self.assertEqual(probe.collected, 0, "nothing can be collected behind the gate")

        self.assertTrue(
            self.finish(probe, thread), "the eval driver thread did not finish"
        )
        self.assertNotIn("error", outcome, f"run_eval raised: {outcome.get('error')!r}")
        self.assertEqual(probe.gate_timeouts, 0, "a fake worker sat on its gate")
        self.assertLessEqual(
            probe.peak_outstanding, window,
            "a job was submitted while the window was already full",
        )
        self.assertEqual(probe.submitted, total_jobs, "the run did not drain")

    def test_the_window_tracks_num_workers_rather_than_the_eval_set(self):
        """A second reading of the same bound at a different worker count.

        With one worker the window is 3, not 12; the old driver submitted 12
        whatever `--num-workers` said, which is the property this separates out.
        """
        workers = 1
        runs = 3
        eval_set = self.eval_set(4)
        total_jobs = len(eval_set) * runs
        window = workers + OUTSTANDING_JOB_BUFFER

        probe = self.harness(released=False)
        thread, outcome = self.drive_in_background(
            probe,
            eval_set=eval_set,
            num_workers=workers,
            timeout=5,
            runs_per_query=runs,
        )

        self.assertTrue(
            probe.at_submission(window).wait(timeout=WINDOW_WAIT_SECONDS),
            f"the driver never submitted {window} jobs",
        )
        time.sleep(WINDOW_SETTLE_SECONDS)
        with probe.lock:
            stalled_at = probe.submitted
        self.assertEqual(stalled_at, window, f"total jobs: {total_jobs}")

        self.assertTrue(
            self.finish(probe, thread), "the eval driver thread did not finish"
        )
        self.assertNotIn("error", outcome, f"run_eval raised: {outcome.get('error')!r}")
        self.assertLessEqual(probe.peak_outstanding, window)
        self.assertEqual(probe.submitted, total_jobs)


class TestBoundedRunPreservesTheOldBehaviour(_BoundedRunCase):
    """Everything the window is *not* allowed to change.

    A refill loop that drops a job, repeats one, reorders `results`, or loses a
    record's cost is a worse defect than the unbounded queue it replaced, and
    each of those is invisible in a run whose job count fits inside one window.
    Every case here runs with jobs far exceeding workers, so the generator is
    refilled many times.
    """

    def test_every_job_runs_exactly_once_across_a_refilled_window(self):
        """Pins job conservation across `fill_window` refills.

        The old driver submitted a materialized list once, so a job could not be
        dropped or repeated by the scheduler; pulling from a generator inside a
        refill loop is exactly where an off-by-one loses or duplicates one, and
        a lost job would surface as a silently smaller denominator rather than
        as an error.
        """
        probe = self.harness(released=True)
        eval_set, output = self.run_bounded(probe, n_queries=12, runs=3, workers=4)
        total_jobs = len(eval_set) * 3

        self.assertEqual(len(probe.started), total_jobs)
        self.assertEqual(len(probe.records), total_jobs)
        for item in eval_set:
            self.assertEqual(
                probe.started.count(item["query"]), 3,
                f"{item['query']} did not run exactly 3 times",
            )
        self.assertEqual(
            sum(row["runs"] + row["errored"] for row in output["results"]), total_jobs
        )
        self.assertEqual(output["summary"]["scored_runs"], total_jobs)

    def test_results_stay_in_eval_set_order_across_a_refilled_window(self):
        """Pins the one ordering guarantee there is.

        Records are collected in completion order, so the only thing keeping
        `results` aligned with the eval set is that it is rebuilt from
        `enumerate(eval_set)` afterwards. A refill loop that indexed rows by
        submission or completion order instead would scramble every row's
        `should_trigger` against its query.
        """
        probe = self.harness(released=True)
        eval_set, output = self.run_bounded(probe, n_queries=15, runs=2, workers=3)

        rows = output["results"]
        self.assertEqual(len(rows), len(eval_set))
        self.assertEqual([row["index"] for row in rows], list(range(len(eval_set))))
        self.assertEqual(
            [row["query"] for row in rows], [item["query"] for item in eval_set]
        )
        self.assertEqual(
            [row["should_trigger"] for row in rows],
            [item["should_trigger"] for item in eval_set],
        )

    def test_cost_accounting_survives_a_bounded_run(self):
        """Pins the reported spend against a window that never holds the run.

        Cost is accumulated per record, so a job the refill loop dropped would
        under-report the bill by exactly one probe with nothing else looking
        wrong -- the number a user reads to decide whether to run again.
        """
        probe = self.harness(released=True)
        eval_set, output = self.run_bounded(probe, n_queries=10, runs=3, workers=2)
        total_jobs = len(eval_set) * 3

        self.assertAlmostEqual(
            output["summary"]["actual_cost_usd"],
            FAKE_PROBE_COST_USD * total_jobs,
            places=4,
        )

    def test_on_record_fires_once_per_job_on_one_thread(self):
        """Pins the single-threadedness the driver's unguarded state relies on.

        `completed`, the `records_by_index[idx].append` and `on_record` itself
        carry no lock; they are safe only because the driver loop is the one
        thread that touches them. Moving the refill into a done-callback -- the
        obvious way to keep the window full -- would run all three on a pool
        worker, and the corruption would be intermittent rather than a failure.
        """
        probe = self.harness(released=True)
        eval_set, _output = self.run_bounded(probe, n_queries=12, runs=3, workers=4)

        self.assertEqual(len(probe.records), len(eval_set) * 3)
        self.assertEqual(
            len(probe.record_threads), 1,
            f"on_record ran on {len(probe.record_threads)} threads",
        )
        self.assertEqual(
            sorted(record["eval_index"] for record in probe.records),
            sorted(idx for idx in range(len(eval_set)) for _ in range(3)),
        )

    def test_one_worker_remains_a_legal_run(self):
        """`--num-workers 1` is the repo's own remediation advice -- run_loop's
        zero-recall warning tells a reader to "re-run one query with
        --num-workers 1 --verbose before believing it", and this validator's
        refusal message names it too -- so the new validation must not have made
        it an error."""
        self.assertEqual(validate_probe_arguments(1, 1), (1, 1))
        self.assertIsNone(check_probe_arguments(1, 1))

        probe = self.harness(released=True)
        eval_set, output = self.run_bounded(probe, n_queries=5, runs=2, workers=1)
        self.assertEqual(len(probe.records), len(eval_set) * 2)
        self.assertEqual(output["summary"]["scored_runs"], len(eval_set) * 2)


class TestProbeArgumentValidation(unittest.TestCase):
    """`max(1, num_workers)` turned 0 and -4 into a serial run the caller never
    asked for, and `runs_per_query` was not checked at all: 0 yields an empty job
    list, so every query is scored `errored` off zero records and the summary
    reports a 100% error rate -- a bad argument that reads as a dead harness. It
    also prices at zero probes, so the spend gate waves it through on the way
    there.
    """

    BAD_COUNTS = (0, -1, -4, 1.5, "4", None, True)

    def _refuses(self, **kwargs):
        """Assert run_eval refuses without reaching a worker or an executor."""
        with mock.patch.object(
            run_eval_mod, "run_single_query", _probe_that_must_not_run
        ), mock.patch.object(
            run_eval_mod, "ThreadPoolExecutor", _executor_that_must_not_exist
        ):
            with self.assertRaises(ProbeArgumentError) as caught:
                run_eval(
                    eval_set=[{"query": "a", "should_trigger": True}],
                    skill_name="widget-forge",
                    description=DESCRIPTION,
                    timeout=5,
                    **kwargs,
                )
        return str(caught.exception)

    def test_the_library_entry_point_refuses_an_unusable_worker_count(self):
        """run_loop and any other caller reach run_eval() directly, so the CLI's
        refusal is not this function's refusal. Each bad value is refused before
        a probe is launched: the substituted worker raises AssertionError if it
        is ever reached, and the substituted executor raises if it is ever
        constructed, so reaching either fails the test rather than passing it."""
        for value in self.BAD_COUNTS:
            with self.subTest(num_workers=value):
                message = self._refuses(num_workers=value, runs_per_query=1)
                self.assertIn("num_workers", message)
                self.assertNotIn("runs_per_query", message)

    def test_the_library_entry_point_refuses_an_unusable_run_count(self):
        for value in self.BAD_COUNTS:
            with self.subTest(runs_per_query=value):
                message = self._refuses(num_workers=1, runs_per_query=value)
                self.assertIn("runs_per_query", message)

    def test_zero_workers_is_refused_rather_than_clamped_to_one(self):
        """The clamp is the defect. A caller who asked for zero workers has a bug
        in whatever computed it, and one worker is not a reading of zero."""
        message = self._refuses(num_workers=0, runs_per_query=3)
        self.assertIn("num_workers is 0", message)
        self.assertIn("cannot be fewer than 1", message)

    def test_zero_runs_per_query_is_refused_rather_than_measuring_nothing(self):
        message = self._refuses(num_workers=4, runs_per_query=0)
        self.assertIn("runs_per_query is 0", message)

    def test_a_boolean_is_not_a_count(self):
        """`True` is an int subclass, so it would otherwise pass as a one-worker,
        one-run request. Nothing that produces a boolean here meant a count."""
        with self.assertRaises(ProbeArgumentError) as caught:
            validate_probe_arguments(True, 3)
        self.assertIn("bool", str(caught.exception))

    def test_both_problems_are_reported_at_once(self):
        """The two arguments are independent, so a caller who got both wrong
        hears about both rather than fixing one and re-running to find the
        other -- and each re-run is a chance to spend money."""
        with self.assertRaises(ProbeArgumentError) as caught:
            validate_probe_arguments(0, 0)
        message = str(caught.exception)
        self.assertIn("Found 2 problem(s)", message)
        self.assertIn("num_workers is 0", message)
        self.assertIn("runs_per_query is 0", message)

    def test_the_message_names_the_value_that_would_have_worked(self):
        with self.assertRaises(ProbeArgumentError) as caught:
            validate_probe_arguments(0, 1)
        self.assertIn("--num-workers 1", str(caught.exception))

    def test_a_well_formed_pair_passes_through_unchanged(self):
        for pair in ((1, 1), (4, 3), (16, 10)):
            with self.subTest(pair=pair):
                self.assertEqual(validate_probe_arguments(*pair), pair)

    def test_the_cli_gate_exits_1_with_a_sentence_on_stderr(self):
        """`check_probe_arguments` is what each main() calls. It must exit rather
        than raise, and say what is wrong rather than traceback."""
        for pair in ((0, 3), (4, 0), (0, 0), ("4", 3)):
            with self.subTest(pair=pair):
                err = io.StringIO()
                with mock.patch("sys.stderr", err):
                    with self.assertRaises(SystemExit) as caught:
                        check_probe_arguments(*pair)
                self.assertEqual(caught.exception.code, 1)
                printed = err.getvalue()
                self.assertIn("Error:", printed)
                self.assertNotIn("Traceback", printed)

    def test_the_cli_gate_passes_a_usable_pair_silently(self):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            self.assertIsNone(check_probe_arguments(4, 3))
        self.assertEqual(err.getvalue(), "")

    def test_the_gate_runs_before_the_spend_projection_in_every_cli(self):
        """`--runs-per-query 0` prices the run at $0.00, so it passes --max-cost
        and --confirm-threshold without asking anything; in run_loop it also
        opens a browser tab and creates a results directory before the run that
        measures nothing starts. Ordered by source line, because ast.walk is
        breadth-first and not source order."""
        import ast

        for module in ("run_eval.py", "run_loop.py"):
            with self.subTest(module=module):
                tree = ast.parse(
                    (SKILL_ROOT / "scripts" / module).read_text(encoding="utf-8")
                )
                main_fn = next(
                    n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "main"
                )
                order = [
                    name
                    for _lineno, name in sorted(
                        (n.lineno, n.func.id)
                        for n in ast.walk(main_fn)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    )
                ]
                self.assertIn("check_probe_arguments", order, module)
                self.assertIn("project_spend", order, module)
                self.assertLess(
                    order.index("check_probe_arguments"),
                    order.index("project_spend"),
                    f"{module}: scheduling counts are checked after the spend gate",
                )


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

    def test_inheriting_host_permissions_refuses_before_the_projection(self):
        """This class sets no BETTER_SKILL_CREATOR_CLAUDE_ARGV, so anything that
        gets past the gates launches the real CLI. Exit 1 with no projection
        printed is what proves nothing was reached."""
        evals = self._evals([{"query": "a", "should_trigger": True}])
        proc = self._run("--eval-set", evals, "--skill-path", str(FIXTURES / "probe-skill"),
                         "--yes", "--permission-mode", INHERIT_PERMISSION_MODE)
        self.assertEqual(proc.returncode, 1, proc.stderr[-2000:])
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("--allow-host-permissions", proc.stderr)
        self.assertNotIn("Projected spend", proc.stderr)

    def test_an_unknown_permission_mode_is_a_usage_error(self):
        evals = self._evals([{"query": "a", "should_trigger": True}])
        proc = self._run("--eval-set", evals, "--skill-path", str(FIXTURES / "probe-skill"),
                         "--yes", "--permission-mode", "readOnly")
        self.assertEqual(proc.returncode, 2, proc.stderr[-2000:])
        self.assertNotIn("Traceback", proc.stderr)


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


def _symlinks_available() -> bool:
    probe = Path(tempfile.mkdtemp(prefix="scaffold-symlink-probe-"))
    try:
        target = probe / "t.txt"
        target.write_text("x", encoding="utf-8")
        os.symlink(target, probe / "l.txt")
        return True
    except (OSError, NotImplementedError):
        return False
    finally:
        shutil.rmtree(probe, ignore_errors=True)


def _make_junction(link: Path, target: Path) -> bool:
    """Create an NTFS directory junction. No elevation required, hence R29a."""
    if os.name != "nt":
        return False
    link.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0 and link.exists()


SYMLINKS_AVAILABLE = _symlinks_available()

# Distinct per route, so a byte scan can name which one leaked.
OUTSIDE_VIA_FILE_LINK = "SCAFFOLD-OUT-OF-TREE-VIA-FILE-LINK-4f1ae2"
OUTSIDE_VIA_DIR_LINK = "SCAFFOLD-OUT-OF-TREE-VIA-DIR-LINK-9c07bd"
OUTSIDE_VIA_JUNCTION = "SCAFFOLD-OUT-OF-TREE-VIA-JUNCTION-6b3d10"


class TestScaffoldCopySafety(StubHarness):
    """A --scaffold entry that redirects had its target's *content* copied into
    the probe root, where the probe subprocess then runs with that root as cwd.
    shutil.copy2 follows a file link and shutil.copytree defaults to
    symlinks=False, so all three link forms leaked; the junction leaked past
    is_symlink(), which answers False for one and needs no elevation to create.
    """

    def setUp(self):
        super().setUp()
        # The sentinel tree lives beside the scaffold, never inside it, so
        # anything of it that turns up in a probe root arrived through a link.
        self.outside = self.tmp / "outside"
        (self.outside / "dirtree" / "deep").mkdir(parents=True)
        (self.outside / "secret.txt").write_text(OUTSIDE_VIA_FILE_LINK, encoding="utf-8")
        (self.outside / "dirtree" / "leak.md").write_text(OUTSIDE_VIA_DIR_LINK, encoding="utf-8")
        (self.outside / "dirtree" / "deep" / "deeper.md").write_text(
            OUTSIDE_VIA_JUNCTION, encoding="utf-8"
        )

        self.scaffold = self.tmp / "scaffold"
        (self.scaffold / "src").mkdir(parents=True)
        (self.scaffold / "src" / "dedupe.py").write_text("def f(): pass\n", encoding="utf-8")
        (self.scaffold / "CLAUDE.md").write_text("house rules\n", encoding="utf-8")

    def probe_root(self) -> Path:
        """A real probe root, torn down the way run_single_query tears one down.

        _release_root also discards the registration, which a bare rmtree would
        leave behind in _OWNED_ROOTS.
        """
        root = run_eval_mod._make_probe_root(str(self.scaffold))
        self.addCleanup(run_eval_mod._release_root, root)
        return root

    def refusal(self) -> str:
        with self.assertRaises(ScaffoldError) as caught:
            run_eval_mod._make_probe_root(str(self.scaffold))
        return str(caught.exception)

    # -- the ordinary case still works ------------------------------------

    def test_a_scaffold_of_real_files_is_still_copied(self):
        root = self.probe_root()
        self.assertEqual(
            (root / "src" / "dedupe.py").read_text(encoding="utf-8"), "def f(): pass\n"
        )
        self.assertEqual((root / "CLAUDE.md").read_text(encoding="utf-8"), "house rules\n")
        self.assertTrue((root / ".claude" / "commands").is_dir())

    def test_a_scaffold_of_real_files_excludes_nothing(self):
        self.assertEqual(validate_scaffold(str(self.scaffold)), [])
        self.assertEqual(validate_scaffold(None), [])

    def test_an_empty_probe_root_is_unaffected(self):
        root = run_eval_mod._make_probe_root(None)
        self.addCleanup(run_eval_mod._release_root, root)
        self.assertEqual([p.name for p in root.iterdir()], [".claude"])

    # -- every redirect form is refused -----------------------------------

    @unittest.skipUnless(SYMLINKS_AVAILABLE, "symlink creation is unavailable on this machine")
    def test_a_file_symlink_out_of_the_tree_is_refused(self):
        os.symlink(self.outside / "secret.txt", self.scaffold / "notes.txt")
        self.assertIn("symlink", self.refusal())

    @unittest.skipUnless(SYMLINKS_AVAILABLE, "symlink creation is unavailable on this machine")
    def test_a_directory_symlink_out_of_the_tree_is_refused(self):
        os.symlink(
            self.outside / "dirtree", self.scaffold / "shared", target_is_directory=True
        )
        self.assertIn("symlink", self.refusal())

    @unittest.skipUnless(SYMLINKS_AVAILABLE, "symlink creation is unavailable on this machine")
    def test_a_symlink_nested_below_the_top_level_is_refused(self):
        """copytree dereferences at every depth, so a gate that inspects only
        src.iterdir()'s children passes `src` as ordinary and leaks underneath
        it."""
        os.symlink(self.outside / "secret.txt", self.scaffold / "src" / "vendored.py")
        self.assertIn("symlink", self.refusal())

    @unittest.skipUnless(SYMLINKS_AVAILABLE, "symlink creation is unavailable on this machine")
    def test_a_dangling_symlink_is_refused_rather_than_raising_from_the_copy(self):
        os.symlink(self.outside / "does-not-exist.txt", self.scaffold / "broken.txt")
        self.assertIn("symlink", self.refusal())

    @unittest.skipIf(os.name != "nt", "NTFS junctions do not exist on this platform")
    def test_a_directory_junction_is_refused(self):
        """is_symlink() answers False for a junction and mklink /J needs no
        elevation, so this is the case a symlink-only gate lets through."""
        made = _make_junction(self.scaffold / "vendor", self.outside / "dirtree")
        self.assertTrue(made, "mklink /J failed; the junction case is untested")
        self.assertFalse(
            (self.scaffold / "vendor").is_symlink(),
            "is_symlink() must be False here - that False is the whole defect",
        )
        self.assertIn("junction", self.refusal())

    @unittest.skipIf(os.name != "nt", "NTFS junctions do not exist on this platform")
    def test_a_junction_nested_below_the_top_level_is_refused(self):
        made = _make_junction(
            self.scaffold / "src" / "vendor", self.outside / "dirtree" / "deep"
        )
        self.assertTrue(made, "mklink /J failed; the nested junction case is untested")
        self.assertIn("junction", self.refusal())

    @unittest.skipIf(os.name == "nt", "os.mkfifo does not exist on Windows")
    def test_a_special_file_is_refused(self):
        os.mkfifo(self.scaffold / "pipe")
        self.assertIn("special file", self.refusal())

    # -- nothing from outside the tree reaches a probe --------------------

    def test_no_out_of_tree_sentinel_can_reach_a_probe_root(self):
        """The bytes, not just the entry name. Every link form this machine can
        build is put in at once, and the scaffold must be refused with none of
        the sentinel text anywhere under a probe root."""
        built = []
        if SYMLINKS_AVAILABLE:
            os.symlink(self.outside / "secret.txt", self.scaffold / "notes.txt")
            os.symlink(
                self.outside / "dirtree", self.scaffold / "shared", target_is_directory=True
            )
            os.symlink(self.outside / "secret.txt", self.scaffold / "src" / "vendored.py")
            built.append("symlink")
        if _make_junction(self.scaffold / "vendor", self.outside / "dirtree" / "deep"):
            built.append("junction")
        self.assertTrue(built, "no link form could be built; this test proved nothing")

        def probe_roots() -> set:
            return set(
                Path(tempfile.gettempdir()).glob(f"{run_eval_mod.PROBE_ROOT_PREFIX}*")
            )

        before = probe_roots()
        with self.assertRaises(ScaffoldError):
            run_eval_mod._make_probe_root(str(self.scaffold))

        # Scoped to roots this call created, so the scan cannot be satisfied by
        # there being nothing to scan, and a future change that validates after
        # mkdtemp is caught by the bytes rather than by the count alone.
        sentinels = (OUTSIDE_VIA_FILE_LINK, OUTSIDE_VIA_DIR_LINK, OUTSIDE_VIA_JUNCTION)
        created = probe_roots() - before
        for root in sorted(created):
            self.addCleanup(shutil.rmtree, root, True)
        for root in sorted(created):
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                body = path.read_text(encoding="utf-8", errors="replace")
                for sentinel in sentinels:
                    self.assertNotIn(sentinel, body, f"{sentinel} leaked into {path}")
        self.assertEqual(created, set(), "a refused scaffold must create no probe root")

    # -- refusing leaves nothing behind -----------------------------------

    def test_a_refused_scaffold_creates_no_probe_root_at_all(self):
        """Validation runs before mkdtemp deliberately. run_single_query binds
        probe_root from _make_probe_root's *return*, so a raise after the
        directory exists leaves it registered and unreleased until exit."""
        if not SYMLINKS_AVAILABLE and not _make_junction(
            self.scaffold / "vendor", self.outside / "dirtree"
        ):
            self.skipTest("no link form is creatable on this machine")
        if SYMLINKS_AVAILABLE:
            os.symlink(self.outside / "secret.txt", self.scaffold / "notes.txt")

        before_owned = set(run_eval_mod._OWNED_ROOTS)
        before_roots = set(
            Path(tempfile.gettempdir()).glob(f"{run_eval_mod.PROBE_ROOT_PREFIX}*")
        )

        with self.assertRaises(ScaffoldError):
            run_eval_mod._make_probe_root(str(self.scaffold))

        self.assertEqual(set(run_eval_mod._OWNED_ROOTS), before_owned)
        self.assertEqual(
            set(Path(tempfile.gettempdir()).glob(f"{run_eval_mod.PROBE_ROOT_PREFIX}*")),
            before_roots,
        )

    def test_a_refused_scaffold_is_an_error_record_never_a_non_trigger(self):
        """The status contract already covers this: any exception raised while
        setting the probe up is `error`, and an errored probe is never scored."""
        if SYMLINKS_AVAILABLE:
            os.symlink(self.outside / "secret.txt", self.scaffold / "notes.txt")
        elif not _make_junction(self.scaffold / "vendor", self.outside / "dirtree"):
            self.skipTest("no link form is creatable on this machine")

        self.control(stream=str(TRIGGER_STREAM), rename=True)
        record = self.probe(scaffold=str(self.scaffold))
        self.assertEqual(record["status"], "error", record)
        self.assertIsNone(record["triggered"])
        self.assertIn("ScaffoldError", record["error"])

    # -- the scaffold's own .claude/ is out of the copy, so out of the gate

    def test_a_link_inside_the_scaffolds_own_dot_claude_is_not_a_refusal(self):
        """A top-level .claude/ is skipped by the copy, so refusing on one would
        reject a scaffold over an entry that never reaches a probe root."""
        if not SYMLINKS_AVAILABLE:
            self.skipTest("symlink creation is unavailable on this machine")
        (self.scaffold / ".claude").mkdir()
        os.symlink(self.outside / "secret.txt", self.scaffold / ".claude" / "settings.json")

        root = self.probe_root()
        self.assertFalse((root / ".claude" / "settings.json").exists())
        self.assertEqual((root / "CLAUDE.md").read_text(encoding="utf-8"), "house rules\n")

    # -- the message, and the pre-spend gate ------------------------------

    def test_the_refusal_names_the_entry_and_where_it_points(self):
        if not SYMLINKS_AVAILABLE:
            self.skipTest("symlink creation is unavailable on this machine")
        os.symlink(self.outside / "secret.txt", self.scaffold / "src" / "vendored.py")
        message = self.refusal()
        self.assertIn("vendored.py", message)
        self.assertIn("secret.txt", message)
        self.assertIn(str(self.scaffold), message)

    def test_a_missing_scaffold_directory_is_refused_by_name(self):
        missing = self.tmp / "not-here"
        with self.assertRaises(ScaffoldError) as caught:
            validate_scaffold(str(missing))
        self.assertIn(str(missing), str(caught.exception))

    def test_the_cli_refuses_before_the_spend_projection(self):
        """A refusal from inside the copy reaches the user as a 100% probe-error
        rate, after the bill has printed. The CLIs check once, up front."""
        if not SYMLINKS_AVAILABLE:
            self.skipTest("symlink creation is unavailable on this machine")
        os.symlink(self.outside / "secret.txt", self.scaffold / "notes.txt")

        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            with self.assertRaises(SystemExit) as caught:
                check_scaffold(str(self.scaffold))
        self.assertEqual(caught.exception.code, 1)
        printed = err.getvalue()
        self.assertIn("Error:", printed)
        self.assertIn("Fix:", printed)
        self.assertIn("notes.txt", printed)

    def test_the_cli_gate_passes_a_scaffold_of_real_files(self):
        self.assertIsNone(check_scaffold(str(self.scaffold)))
        self.assertIsNone(check_scaffold(None))


OUTSIDE_VIA_DOTENV = "SCAFFOLD-SECRET-IN-DOTENV-1a72fe"
OUTSIDE_VIA_GIT_CONFIG = "SCAFFOLD-SECRET-IN-GIT-CONFIG-5e40cb"


class TestScaffoldExclusions(StubHarness):
    """`.claude` was the copy loop's only exclusion, so a scaffold's own `.env`
    and `.git/config` -- the latter carrying a credentialed remote URL -- were
    copied into every probe workspace verbatim. No link is involved, so the
    reparse gate cannot see either one.

    The list stays short deliberately. A query naming an absent path burns the
    --max-tools budget and is recorded `no_trigger`, which is scored, so an
    over-eager exclusion moves the recall number instead of protecting it.
    """

    def setUp(self):
        super().setUp()
        self.scaffold = self.tmp / "scaffold"
        (self.scaffold / "src").mkdir(parents=True)
        (self.scaffold / "src" / "dedupe.py").write_text("def f(): pass\n", encoding="utf-8")
        (self.scaffold / "CLAUDE.md").write_text("house rules\n", encoding="utf-8")

    def probe_root(self) -> Path:
        root = run_eval_mod._make_probe_root(str(self.scaffold))
        self.addCleanup(run_eval_mod._release_root, root)
        return root

    def bodies(self, root: Path) -> str:
        return "\n".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in root.rglob("*")
            if p.is_file()
        )

    def excluded_paths(self) -> list:
        return [path for path, _ in validate_scaffold(str(self.scaffold))]

    # -- the two routes actually reported ---------------------------------

    def test_a_dotenv_never_reaches_a_probe_root(self):
        (self.scaffold / ".env").write_text(
            f"API_TOKEN={OUTSIDE_VIA_DOTENV}\n", encoding="utf-8"
        )
        root = self.probe_root()
        self.assertFalse((root / ".env").exists())
        self.assertNotIn(OUTSIDE_VIA_DOTENV, self.bodies(root))

    def test_a_git_directory_never_reaches_a_probe_root(self):
        (self.scaffold / ".git").mkdir()
        (self.scaffold / ".git" / "config").write_text(
            f"[remote \"origin\"]\n\turl = https://x:{OUTSIDE_VIA_GIT_CONFIG}@example.invalid/r.git\n",
            encoding="utf-8",
        )
        root = self.probe_root()
        self.assertFalse((root / ".git").exists())
        self.assertNotIn(OUTSIDE_VIA_GIT_CONFIG, self.bodies(root))

    def test_a_git_worktree_pointer_file_never_reaches_a_probe_root(self):
        """In a `git worktree` checkout .git is a file holding an absolute
        gitdir: pointer. Copied, it makes the probe root a live and writable
        checkout of the user's real repository, and there is no link for the
        reparse gate to catch -- only the name."""
        (self.scaffold / ".git").write_text(
            "gitdir: D:/real-repo/.git/worktrees/checkout\n", encoding="utf-8"
        )
        root = self.probe_root()
        self.assertFalse((root / ".git").exists())
        self.assertIn(".git", self.excluded_paths())

    # -- depth and case ---------------------------------------------------

    def test_an_excluded_directory_nested_below_the_top_level_is_dropped(self):
        (self.scaffold / "src" / "__pycache__").mkdir()
        (self.scaffold / "src" / "__pycache__" / "dedupe.pyc").write_text(
            "bytecode\n", encoding="utf-8"
        )
        root = self.probe_root()
        self.assertTrue((root / "src" / "dedupe.py").exists())
        self.assertFalse((root / "src" / "__pycache__").exists())

    def test_a_nested_dotenv_is_dropped(self):
        (self.scaffold / "src" / ".env.local").write_text(
            f"K={OUTSIDE_VIA_DOTENV}\n", encoding="utf-8"
        )
        root = self.probe_root()
        self.assertNotIn(OUTSIDE_VIA_DOTENV, self.bodies(root))

    def test_exclusion_is_case_folded(self):
        """`.GIT` and `__PYCACHE__` name the same entries as their lowercase
        spellings on Windows and macOS. package_skill.py's exact-name tables are
        case-sensitive and miss exactly this."""
        self.assertIsNotNone(run_eval_mod._scaffold_exclusion(".GIT"))
        self.assertIsNotNone(run_eval_mod._scaffold_exclusion("__PYCACHE__"))
        self.assertIsNotNone(run_eval_mod._scaffold_exclusion("Production.ENV"))

    def test_a_nested_dot_claude_is_excluded_too(self):
        """This reverses the earlier top-level-only contract, and the reason is
        `.claude/skills/`: references/how-skills-load.md records that a skill at
        `apps/web/.claude/skills/deploy` registers as `apps/web:deploy`, so a
        scaffold carrying one puts a competing skill in the probe's own session.
        Nested `settings.json` appears not to be read -- the shipped CLI names
        four settings sources and no directory-scoped variant -- so the skills
        path is the evidenced one."""
        (self.scaffold / "src" / ".claude" / "skills" / "deploy").mkdir(parents=True)
        (self.scaffold / "src" / ".claude" / "skills" / "deploy" / "SKILL.md").write_text(
            "---\nname: deploy\n---\n", encoding="utf-8"
        )
        root = self.probe_root()
        self.assertFalse((root / "src" / ".claude").exists())
        self.assertTrue((root / "src" / "dedupe.py").exists())

    def test_the_dot_claude_exclusion_is_depth_independent(self):
        for name in (".claude", ".CLAUDE"):
            with self.subTest(name=name):
                self.assertIsNotNone(run_eval_mod._scaffold_exclusion(name))

    def test_names_sharing_the_dot_claude_prefix_survive(self):
        """`.claude-plugin` is a documented distributable shape and `CLAUDE.md`
        is deliberately copied as scaffold realism, so the rule is exact-name."""
        for name in (".claude-plugin", ".claudeignore", "CLAUDE.md", "claude_helpers.py"):
            with self.subTest(name=name):
                self.assertIsNone(run_eval_mod._scaffold_exclusion(name))

    def test_posix_environment_directories_are_excluded(self):
        """A POSIX venv symlinks bin/python, so an unexcluded environment
        directory refuses the whole run on Linux and macOS while passing on
        Windows. Bare `env` stays copyable -- it is more often content."""
        for name in (".tox", ".nox", ".direnv", ".conda", "virtualenv"):
            with self.subTest(name=name):
                self.assertIsNotNone(run_eval_mod._scaffold_exclusion(name))
        self.assertIsNone(run_eval_mod._scaffold_exclusion("env"))

    # -- over-exclusion is the failure mode this guards against -----------

    def test_names_a_query_could_resolve_are_not_excluded(self):
        """Every one of these is dropped by package_skill.py's policy, which is
        why that policy is not adopted here. A query naming any of them would be
        scored a non-trigger with no error record to explain it."""
        keep = [
            # package_skill.py's SENSITIVE_WORDS / SENSITIVE_COMPOUNDS
            "tokens.md", "token-limits.md", "counting-tokens.py",
            "api-key-reference.md", "password_policy.md", "secrets.yaml",
            "credentials.md", "keystore-design.md", "secrets.py", "env.py",
            # its *.key glob, which reads a localization file as a private key
            "translations.key",
            # its dot-prefix blanket -- and every one of these shares the .git
            # prefix or is ordinary project config a query names directly
            ".github", ".editorconfig", ".gitignore", ".gitattributes",
            ".gitmodules", ".python-version", ".nvmrc", ".eslintrc.json",
            # its ROOT_EXCLUDE_DIRS and FILE_GLOB_EXCLUSIONS
            "tests", "evals", "fixture.zip", "config.pem",
            # bare `env` is a plausible content directory, unlike `.venv`
            "env",
            # the lockfile is the right thing to keep when node_modules goes
            "package-lock.json",
            # committed on purpose, and the one file an env query can resolve
            ".env.example", ".env.sample", ".env.template",
        ]
        for name in keep:
            with self.subTest(name=name):
                self.assertIsNone(
                    run_eval_mod._scaffold_exclusion(name),
                    f"{name} must stay copyable: a query could name it",
                )

    def test_a_dotenv_template_survives_beside_a_real_dotenv(self):
        (self.scaffold / ".env").write_text(f"K={OUTSIDE_VIA_DOTENV}\n", encoding="utf-8")
        (self.scaffold / ".env.example").write_text("K=replace-me\n", encoding="utf-8")
        root = self.probe_root()
        self.assertFalse((root / ".env").exists())
        self.assertEqual(
            (root / ".env.example").read_text(encoding="utf-8"), "K=replace-me\n"
        )

    def test_the_lockfile_survives_when_node_modules_is_dropped(self):
        (self.scaffold / "node_modules").mkdir()
        (self.scaffold / "node_modules" / "left-pad.js").write_text("x\n", encoding="utf-8")
        (self.scaffold / "package-lock.json").write_text("{}\n", encoding="utf-8")
        root = self.probe_root()
        self.assertFalse((root / "node_modules").exists())
        self.assertEqual((root / "package-lock.json").read_text(encoding="utf-8"), "{}\n")

    def test_gitignore_survives_while_dot_git_is_dropped(self):
        """`.gitignore` shares the `.git` prefix, and "add build artifacts to my
        .gitignore" is exactly the file-naming query --scaffold exists for. An
        exclusion written as a prefix rather than an exact name kills it."""
        (self.scaffold / ".git").mkdir()
        (self.scaffold / ".git" / "config").write_text("[core]\n", encoding="utf-8")
        (self.scaffold / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.scaffold / ".gitattributes").write_text("* text=auto\n", encoding="utf-8")
        root = self.probe_root()
        self.assertFalse((root / ".git").exists())
        self.assertEqual((root / ".gitignore").read_text(encoding="utf-8"), "__pycache__/\n")
        self.assertTrue((root / ".gitattributes").is_file())

    def test_an_ordinary_scaffold_reports_no_exclusions(self):
        self.assertEqual(validate_scaffold(str(self.scaffold)), [])

    # -- exclusion and the link gate must agree ---------------------------

    @unittest.skipUnless(SYMLINKS_AVAILABLE, "symlink creation is unavailable on this machine")
    def test_a_link_inside_an_excluded_directory_is_not_a_refusal(self):
        """Measured before exclusions existed: a .venv holding one linked
        package, a node_modules holding a pnpm store junction, and symlinked
        .git/hooks were all refused outright, over entries that would never have
        been copied."""
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "pkg.py").write_text("x\n", encoding="utf-8")
        (self.scaffold / ".venv" / "Lib" / "site-packages").mkdir(parents=True)
        os.symlink(outside / "pkg.py", self.scaffold / ".venv" / "Lib" / "linked.py")
        (self.scaffold / ".git" / "hooks").mkdir(parents=True)
        os.symlink(outside / "pkg.py", self.scaffold / ".git" / "hooks" / "pre-commit")

        root = self.probe_root()
        self.assertFalse((root / ".venv").exists())
        self.assertFalse((root / ".git").exists())
        self.assertTrue((root / "src" / "dedupe.py").exists())

    @unittest.skipIf(os.name != "nt", "NTFS junctions do not exist on this platform")
    def test_a_junction_inside_an_excluded_directory_is_not_a_refusal(self):
        outside = self.tmp / "outside"
        (outside / "store").mkdir(parents=True)
        (outside / "store" / "index.js").write_text("x\n", encoding="utf-8")
        (self.scaffold / "node_modules").mkdir()
        made = _make_junction(self.scaffold / "node_modules" / "shared", outside / "store")
        self.assertTrue(made, "mklink /J failed; the pnpm-store case is untested")

        root = self.probe_root()
        self.assertFalse((root / "node_modules").exists())

    @unittest.skipUnless(SYMLINKS_AVAILABLE, "symlink creation is unavailable on this machine")
    def test_an_excluded_name_that_is_itself_a_link_is_not_a_refusal(self):
        """Prune-before-check, and over filenames too: a `.git` symlink lands in
        os.walk's filenames rather than its dirnames, and check-then-prune would
        refuse a .venv that is itself a junction."""
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "pointer").write_text("gitdir: elsewhere\n", encoding="utf-8")
        os.symlink(outside / "pointer", self.scaffold / ".git")

        root = self.probe_root()
        self.assertFalse((root / ".git").exists())

    # -- the exclusions are told, not silent ------------------------------

    def test_the_cli_reports_what_it_leaves_out_before_the_spend_projection(self):
        (self.scaffold / ".env").write_text("K=v\n", encoding="utf-8")
        (self.scaffold / "node_modules").mkdir()
        (self.scaffold / "node_modules" / "left-pad.js").write_text("x\n", encoding="utf-8")

        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            self.assertIsNone(check_scaffold(str(self.scaffold)))
        printed = err.getvalue()
        self.assertIn("Warning:", printed)
        self.assertIn(".env", printed)
        self.assertIn("node_modules/", printed)
        self.assertIn("scored a non-trigger", printed)

    def test_nothing_is_printed_when_nothing_is_excluded(self):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            check_scaffold(str(self.scaffold))
        self.assertEqual(err.getvalue(), "")

    def test_excluded_directories_are_reported_without_being_walked(self):
        """Reporting a file count would mean walking into the very junctions the
        gate declines to follow, so the report names the path and stops."""
        (self.scaffold / "node_modules" / "deep").mkdir(parents=True)
        (self.scaffold / "node_modules" / "deep" / "a.js").write_text("x\n", encoding="utf-8")
        excluded = validate_scaffold(str(self.scaffold))
        self.assertEqual(excluded, [("node_modules/", "installed dependencies")])


def _hard_links_available(tmp: Path) -> bool:
    src = tmp / "hl-probe-src.txt"
    src.write_text("x", encoding="utf-8")
    try:
        os.link(src, tmp / "hl-probe-link.txt")
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False


# Shape-correct and obviously fake: literal EXAMPLE/zero filler, nothing that
# could be a live value. Each proves one marker route.
FAKE_AWS_KEY = "AKIA" + "NOTAREALKEY00000"
FAKE_PEM_HEADER = "-----BEGIN RSA PRIVATE KEY-----"
AWS_DOC_PLACEHOLDER = "AKIAIOSFODNN7EXAMPLE"
OUTSIDE_VIA_HARD_LINK = "SCAFFOLD-OUT-OF-TREE-VIA-HARD-LINK-8d24c7"


class TestScaffoldDisclosures(StubHarness):
    """Two routes reach a probe workspace that exclusion cannot see: a hard
    link, which is byte-identical to an ordinary file, and a credential inside
    an innocently named file. Both are reported and copied, never withheld.

    Withholding either would move the recall number -- a query naming an absent
    path is scored `no_trigger`, which counts, not `error`, which does not --
    and the user's fix for either leaves the path and its bytes in place, so a
    report costs nothing to act on. Refusing on `st_nlink > 1` is worse than
    useless: every ext4 directory has two links (measured 18,696/18,696, against
    0/8 on NTFS), so it would refuse every Linux scaffold and pass on Windows.
    """

    def setUp(self):
        super().setUp()
        self.outside = self.tmp / "outside"
        self.outside.mkdir()
        self.scaffold = self.tmp / "scaffold"
        (self.scaffold / "src").mkdir(parents=True)
        (self.scaffold / "src" / "dedupe.py").write_text("def f(): pass\n", encoding="utf-8")
        (self.scaffold / "CLAUDE.md").write_text("house rules\n", encoding="utf-8")

    def probe_root(self) -> Path:
        root = run_eval_mod._make_probe_root(str(self.scaffold))
        self.addCleanup(run_eval_mod._release_root, root)
        return root

    def notes(self) -> list:
        return run_eval_mod.scaffold_disclosures(str(self.scaffold))

    # -- credential content -----------------------------------------------

    def test_a_credential_in_an_innocently_named_file_is_reported(self):
        (self.scaffold / "src" / "config.yaml").write_text(
            f"region: us-east-1\naccess_key: {FAKE_AWS_KEY}\n", encoding="utf-8"
        )
        notes = self.notes()
        self.assertIn(("src/config.yaml", "AWS access key id"), notes)

    def test_a_private_key_block_is_reported(self):
        (self.scaffold / "notes.md").write_text(
            f"{FAKE_PEM_HEADER}\nTk9ULUEtUkVBTC1LRVk=\n", encoding="utf-8"
        )
        self.assertIn(("notes.md", "private key block"), self.notes())

    def test_a_reported_file_is_still_copied(self):
        """The whole point of reporting rather than withholding: the path a
        query might name is still there."""
        (self.scaffold / "src" / "config.yaml").write_text(
            f"access_key: {FAKE_AWS_KEY}\n", encoding="utf-8"
        )
        root = self.probe_root()
        self.assertTrue((root / "src" / "config.yaml").is_file())

    def test_the_report_never_echoes_the_matched_bytes(self):
        """check_scaffold prints to stderr, which lands in CI logs. A report
        carrying the match would turn the detector into the leak."""
        (self.scaffold / "src" / "config.yaml").write_text(
            f"access_key: {FAKE_AWS_KEY}\n", encoding="utf-8"
        )
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            check_scaffold(str(self.scaffold))
        printed = err.getvalue()
        self.assertIn("src/config.yaml", printed)
        self.assertIn("AWS access key id", printed)
        self.assertNotIn(FAKE_AWS_KEY, printed)

    def test_the_aws_documentation_placeholder_is_not_reported(self):
        """AWS's own published example is structurally identical to a live key,
        and any scaffold documenting AWS setup carries it."""
        (self.scaffold / "docs.md").write_text(
            f"Set AWS_ACCESS_KEY_ID={AWS_DOC_PLACEHOLDER} in your shell.\n", encoding="utf-8"
        )
        self.assertEqual(self.notes(), [])

    def test_ordinary_content_is_not_reported(self):
        """Entropy scoring was rejected for firing on these: 28 of its 30 false
        positives on this repository were file paths."""
        (self.scaffold / "package-lock.json").write_text(
            '{"integrity": "sha512-' + "A" * 80 + 'abcd=="}\n', encoding="utf-8"
        )
        (self.scaffold / "version.py").write_text(
            'SHA = "9f2b1c0d4e7a8b3c5d6e0f1a2b3c4d5e6f708192"\n', encoding="utf-8"
        )
        (self.scaffold / "auth.md").write_text(
            "Set ANTHROPIC_API_KEY. Rotate the token and the password.\n", encoding="utf-8"
        )
        self.assertEqual(self.notes(), [])

    def test_a_marker_inside_an_excluded_directory_is_not_reported(self):
        (self.scaffold / "node_modules" / "aws-sdk").mkdir(parents=True)
        (self.scaffold / "node_modules" / "aws-sdk" / "fixture.js").write_text(
            f"const k = '{FAKE_AWS_KEY}';\n", encoding="utf-8"
        )
        self.assertEqual(self.notes(), [])

    def test_a_binary_file_does_not_break_the_scan(self):
        (self.scaffold / "logo.png").write_bytes(bytes(range(256)) * 8)
        self.assertEqual(self.notes(), [])

    def test_a_non_utf8_file_is_still_scanned(self):
        """A decode-first scanner raises UnicodeDecodeError here and skips the
        file, which converts a true positive into silence. Raw bytes see it."""
        (self.scaffold / "legacy.txt").write_bytes(
            "caf\xe9 ".encode("cp1252") + FAKE_AWS_KEY.encode("ascii") + b"\n"
        )
        self.assertIn(("legacy.txt", "AWS access key id"), self.notes())

    def test_a_utf16_file_is_still_scanned(self):
        """Raw bytes miss this one on NUL interleaving, so a BOM triggers a
        second decode pass."""
        (self.scaffold / "spec.txt").write_bytes(
            f"key = {FAKE_AWS_KEY}\n".encode("utf-16")
        )
        self.assertIn(("spec.txt", "AWS access key id"), self.notes())

    # -- hard links --------------------------------------------------------

    def test_a_hard_link_to_a_file_outside_the_tree_is_reported(self):
        if not _hard_links_available(self.tmp):
            self.skipTest("hard link creation is unavailable on this machine")
        target = self.outside / "creds.txt"
        target.write_text(OUTSIDE_VIA_HARD_LINK, encoding="utf-8")
        os.link(target, self.scaffold / "notes.txt")
        paths = [path for path, _ in self.notes()]
        self.assertIn("notes.txt", paths)

    def test_a_reported_hard_link_is_still_copied(self):
        if not _hard_links_available(self.tmp):
            self.skipTest("hard link creation is unavailable on this machine")
        target = self.outside / "creds.txt"
        target.write_text(OUTSIDE_VIA_HARD_LINK, encoding="utf-8")
        os.link(target, self.scaffold / "notes.txt")
        root = self.probe_root()
        self.assertEqual(
            (root / "notes.txt").read_text(encoding="utf-8"), OUTSIDE_VIA_HARD_LINK
        )

    def test_two_in_tree_names_for_one_inode_are_not_reported(self):
        """Inode accounting, not bare st_nlink: a tree's own internal duplicate
        has both names inside the scaffold and is acquitted."""
        if not _hard_links_available(self.tmp):
            self.skipTest("hard link creation is unavailable on this machine")
        first = self.scaffold / "CLAUDE.md"
        os.link(first, self.scaffold / "src" / "CLAUDE.md")
        self.assertEqual(self.notes(), [])

    def test_directories_are_never_reported_as_hard_links(self):
        """Every ext4 directory has st_nlink >= 2, so a rule reaching
        directories refuses every Linux scaffold and passes on Windows."""
        (self.scaffold / "a" / "b" / "c").mkdir(parents=True)
        (self.scaffold / "a" / "b" / "c" / "f.py").write_text("x\n", encoding="utf-8")
        self.assertEqual(self.notes(), [])

    # -- the ordinary case is silent ---------------------------------------

    def test_an_ordinary_scaffold_discloses_nothing(self):
        self.assertEqual(self.notes(), [])
        self.assertEqual(run_eval_mod.scaffold_disclosures(None), [])

    def test_nothing_is_printed_when_there_is_nothing_to_disclose(self):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            check_scaffold(str(self.scaffold))
        self.assertEqual(err.getvalue(), "")


class _SignalState(unittest.TestCase):
    """Base class that puts the process's signal disposition back afterwards.

    `run_eval` installs handlers as a side effect, so a test that exercises them
    must not leave them behind for the rest of the suite.
    """

    _SIGNALS = ("SIGINT", "SIGTERM", "SIGBREAK", "SIGHUP")

    def preserve_signal_state(self):
        saved = {}
        for name in self._SIGNALS:
            sig = getattr(signal, name, None)
            if sig is None:
                continue
            try:
                saved[sig] = signal.getsignal(sig)
            except (ValueError, OSError):
                continue
        installed = run_eval_mod._CLEANUP_INSTALLED

        def restore():
            for sig, handler in saved.items():
                # getsignal answers None for a handler not set from Python;
                # there is nothing to put back in that case.
                if handler is None:
                    continue
                try:
                    signal.signal(sig, handler)
                except (ValueError, OSError, TypeError):
                    pass
            run_eval_mod._CLEANUP_INSTALLED = installed
            run_eval_mod._INTERRUPTED.clear()

        self.addCleanup(restore)

    def install_fresh(self):
        """Install the handlers as a first call in this process would."""
        self.preserve_signal_state()
        run_eval_mod._CLEANUP_INSTALLED = False
        run_eval_mod._INTERRUPTED.clear()
        run_eval_mod.install_cleanup_handlers()


class TestCtrlCStopsSpending(_SignalState):
    """Ctrl-C must reach run_eval's cancellation path instead of being eaten.

    install_cleanup_handlers used to install its own SIGINT handler, replacing
    signal.default_int_handler -- the handler that raises KeyboardInterrupt. So
    Ctrl-C never unwound the `for future in as_completed(...)` loop and never
    reached `except BaseException: executor.shutdown(cancel_futures=True)`.
    What ran instead was cleanup_owned() on the main thread, taking tens of
    seconds (kill + wait(timeout=5) per child, then ~3s of rmtree backoff per
    root) while the pool's workers were still dequeuing -- so each one that
    finished started a fresh *billed* `claude`. Those children were registered
    after the cleanup snapshot and were still alive when os.kill landed under
    SIG_DFL, where atexit does not fire, so they were orphaned as well.
    """

    def test_sigint_is_left_to_the_handler_that_raises_keyboardinterrupt(self):
        self.install_fresh()
        self.assertIs(
            signal.getsignal(signal.SIGINT),
            signal.default_int_handler,
            "SIGINT must stay with Python's own handler; anything else makes "
            "run_eval's `except BaseException` unreachable from Ctrl-C",
        )

    def test_an_ignored_sigint_is_left_ignored(self):
        """A parent that ignored SIGINT said so. POSIX convention is to obey."""
        self.preserve_signal_state()
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        except (ValueError, OSError):  # pragma: no cover - not the main thread
            self.skipTest("cannot set SIGINT disposition here")
        run_eval_mod._CLEANUP_INSTALLED = False
        run_eval_mod.install_cleanup_handlers()
        self.assertIs(signal.getsignal(signal.SIGINT), signal.SIG_IGN)

    def test_a_caught_signal_unwinds_rather_than_cleaning_up_in_place(self):
        """SIGTERM/SIGBREAK/SIGHUP take the same path Ctrl-C does.

        cleanup_owned() must not be called from a handler at all: handlers run
        on the main thread, _OWNED_LOCK is not reentrant, and a handler that
        took it while the main thread already held it would hang the process
        rather than stop it. os.kill and cleanup_owned are patched here so this
        stays a test even against the old handler, which would otherwise take
        the test process down with SIG_DFL.
        """
        self.install_fresh()
        handler = signal.getsignal(signal.SIGTERM)
        self.assertTrue(callable(handler), "SIGTERM is not handled at all")

        with mock.patch.object(run_eval_mod, "cleanup_owned") as cleaned, \
                mock.patch.object(os, "kill") as killed:
            with self.assertRaises(KeyboardInterrupt):
                handler(signal.SIGTERM, None)

        cleaned.assert_not_called()
        killed.assert_not_called()
        self.assertTrue(
            run_eval_mod._INTERRUPTED.is_set(),
            "the handler must stop the workers spending even before the raise "
            "reaches the main thread",
        )

    def test_a_sigint_during_a_run_cancels_the_queued_probes(self):
        """The end-to-end claim, driven by a real SIGINT.

        `on_record` runs on the main thread inside the scheduling loop, which is
        where a Ctrl-C would land, and signal.raise_signal runs the installed
        handler synchronously. So this is the real delivery path, without the
        thread-timing dependence of signalling from a worker.
        """
        self.install_fresh()
        self.assertIs(
            signal.getsignal(signal.SIGINT),
            signal.default_int_handler,
            "guard: raising SIGINT below is only safe once it is Python's own "
            "handler. The old one ran os.kill under SIG_DFL and would take this "
            "test process with it.",
        )

        workers = 2
        eval_set = [{"query": f"q{i}", "should_trigger": True} for i in range(24)]
        launched: list[str] = []
        launched_after_flag: list[str] = []
        lock = threading.Lock()

        def fake(query, skill_name, skill_description, timeout, *args, **kwargs):
            with lock:
                launched.append(query)
                if run_eval_mod._INTERRUPTED.is_set():
                    launched_after_flag.append(query)
            # Long enough that the queue cannot drain before the interrupt.
            time.sleep(0.05)
            return {
                "query": query,
                "probe_id": f"{skill_name}-skill-deadbeef",
                "status": "no_trigger",
                "triggered": False,
                "stop_reason": "result",
                "error": None,
                "tools": [],
                "elapsed_seconds": 0.05,
                "cost_usd": 0.01,
                "probe_root": None,
            }

        seen: list[dict] = []
        at_interrupt: list[int] = []

        def on_record(_record):
            seen.append(_record)
            if len(seen) == 2:
                with lock:
                    at_interrupt.append(len(launched))
                signal.raise_signal(signal.SIGINT)

        with mock.patch.object(run_eval_mod, "run_single_query", fake):
            with self.assertRaises(KeyboardInterrupt):
                run_eval(
                    eval_set=eval_set,
                    skill_name="widget-forge",
                    description=DESCRIPTION,
                    num_workers=workers,
                    timeout=5,
                    runs_per_query=1,
                    on_record=on_record,
                )

        self.assertEqual(len(at_interrupt), 1, "the interrupt never fired")
        self.assertLess(
            len(launched), len(eval_set),
            "every queued probe still launched: Ctrl-C did not reach "
            "executor.shutdown(cancel_futures=True)",
        )
        self.assertLessEqual(
            len(launched), at_interrupt[0] + workers,
            "probes kept launching after the interrupt; only the ones already "
            "dequeued may finish",
        )
        self.assertEqual(
            launched_after_flag, [],
            "a probe started after the run was marked interrupted",
        )

    def test_the_interrupt_flag_is_cleared_for_the_next_run(self):
        """run_loop calls run_eval per iteration. A stale flag would turn the
        next call into a 100%-errored run, which reads as a dead harness."""
        self.install_fresh()
        run_eval_mod._INTERRUPTED.set()

        eval_set = [{"query": "positive", "should_trigger": True}]
        with mock.patch.object(
            run_eval_mod, "run_single_query", _fake_probe({"positive": ["trigger"]})
        ):
            out = run_eval(
                eval_set=eval_set,
                skill_name="widget-forge",
                description=DESCRIPTION,
                num_workers=1,
                timeout=5,
                runs_per_query=2,
            )
        self.assertFalse(run_eval_mod._INTERRUPTED.is_set())
        self.assertEqual(out["results"][0]["runs"], 2)


class TestInterruptedProbeNeverLaunches(StubHarness):
    """The spend is gated where it happens, not where the jobs are handed out.

    The main thread cannot be relied on to notice an interrupt promptly -- on
    Windows only SIGINT breaks it out of a blocking wait -- so a queued worker
    checks for itself before it starts a billed session.
    """

    def setUp(self):
        super().setUp()
        self.addCleanup(run_eval_mod._INTERRUPTED.clear)

    def test_no_claude_is_launched_once_the_run_is_interrupted(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        run_eval_mod._INTERRUPTED.set()
        record = self.probe()
        self.assertFalse(
            self.report_path.exists(),
            "a billed session was started after the run was interrupted",
        )
        self.assertEqual(record["status"], "error", record)
        self.assertEqual(record["stop_reason"], "interrupted")
        self.assertIsNone(
            record["triggered"], "an interrupted probe is not a measurement"
        )

    def test_an_interrupted_probe_creates_no_probe_root(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        before = set(run_eval_mod._OWNED_ROOTS)
        run_eval_mod._INTERRUPTED.set()
        record = self.probe()
        self.assertIsNone(record["probe_root"])
        self.assertEqual(set(run_eval_mod._OWNED_ROOTS), before)

    def test_an_uninterrupted_probe_is_unaffected(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        self.assertFalse(run_eval_mod._INTERRUPTED.is_set())
        record = self.probe()
        self.assertEqual(record["status"], "trigger", record)


class TestSurvivingProbeRootStaysRegistered(unittest.TestCase):
    """A probe root that resisted removal must stay owned, not be forgotten.

    _release_root discarded str(path) from _OWNED_ROOTS unconditionally, before
    checking whether _rmtree_retry had actually succeeded. _rmtree_retry exists
    because Windows refuses to unlink a directory that is still a just-killed
    `claude`'s cwd -- so the single root the exit sweep needed to hear about was
    the one it was told to forget, at the moment when a later retry, with the
    holding process gone, would have worked. For a --scaffold run that stranded
    a copy of the user's project under %TEMP% behind one stderr line.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="run-eval-teardown-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.scaffold = self.tmp / "scaffold"
        (self.scaffold / "src").mkdir(parents=True)
        (self.scaffold / "src" / "proprietary.py").write_text(
            "# the user's project\n", encoding="utf-8"
        )
        self.owned_before = set(run_eval_mod._OWNED_ROOTS)
        self.addCleanup(self._restore_ownership)

    def _restore_ownership(self):
        for root in set(run_eval_mod._OWNED_ROOTS) - self.owned_before:
            shutil.rmtree(root, ignore_errors=True)
            run_eval_mod._OWNED_ROOTS.discard(root)

    def make_root(self) -> Path:
        root = run_eval_mod._make_probe_root(str(self.scaffold))
        self.assertIn(str(root), run_eval_mod._OWNED_ROOTS)
        self.assertTrue((root / "src" / "proprietary.py").exists())
        return root

    def test_a_root_that_could_not_be_removed_is_still_owned(self):
        root = self.make_root()
        err = io.StringIO()
        with mock.patch.object(run_eval_mod, "_rmtree_retry", return_value=False):
            with mock.patch("sys.stderr", err):
                run_eval_mod._release_root(root)
        self.assertIn(
            str(root), run_eval_mod._OWNED_ROOTS,
            "a root that survived removal was dropped from the ownership set, "
            "so the exit sweep no longer knows it exists",
        )
        self.assertTrue(root.exists())
        self.assertIn(str(root), err.getvalue())

    def test_the_exit_sweep_removes_what_release_could_not(self):
        """The whole point of staying registered. By exit the process holding
        the directory is gone and the same retry succeeds."""
        root = self.make_root()
        with mock.patch.object(run_eval_mod, "_rmtree_retry", return_value=False):
            with mock.patch("sys.stderr", io.StringIO()):
                run_eval_mod._release_root(root)

        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            run_eval_mod._final_cleanup()

        self.assertFalse(
            root.exists(),
            "a --scaffold copy of the user's project was left under the temp dir",
        )
        self.assertNotIn(str(root), run_eval_mod._OWNED_ROOTS)
        self.assertEqual(err.getvalue(), "", "nothing was left behind to report")

    def test_the_sweep_keeps_what_it_could_not_remove(self):
        """cleanup_owned had the same defect: it difference_update'd every root
        it had walked, whether or not the rmtree worked."""
        root = self.make_root()
        with mock.patch.object(run_eval_mod, "_rmtree_retry", return_value=False):
            surviving = run_eval_mod.cleanup_owned()
        self.assertEqual(surviving, [str(root)])
        self.assertIn(str(root), run_eval_mod._OWNED_ROOTS)
        self.assertTrue(root.exists())

    def test_the_exit_sweep_names_a_root_it_had_to_leave_behind(self):
        root = self.make_root()
        err = io.StringIO()
        with mock.patch.object(run_eval_mod, "_rmtree_retry", return_value=False):
            with mock.patch("sys.stderr", err):
                run_eval_mod._final_cleanup()
        self.assertIn(str(root), err.getvalue())
        self.assertIn("scaffold", err.getvalue())

    def test_a_removed_root_is_forgotten_as_before(self):
        root = self.make_root()
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            run_eval_mod._release_root(root)
        self.assertFalse(root.exists())
        self.assertNotIn(str(root), run_eval_mod._OWNED_ROOTS)
        self.assertEqual(err.getvalue(), "")

    def test_a_root_removed_on_a_later_attempt_is_forgotten(self):
        """_rmtree_retry's own backoff still resolves the ordinary case; the
        registration must not survive a success that took more than one try."""
        root = self.make_root()
        real = run_eval_mod._rmtree_retry
        attempts = []

        def flaky(path, attempts_arg=5):
            attempts.append(path)
            if len(attempts) == 1:
                return False
            return real(path)

        err = io.StringIO()
        with mock.patch.object(run_eval_mod, "_rmtree_retry", flaky):
            with mock.patch("sys.stderr", err):
                run_eval_mod._release_root(root)
                self.assertIn(str(root), run_eval_mod._OWNED_ROOTS)
                run_eval_mod._release_root(root)
        self.assertFalse(root.exists())
        self.assertNotIn(str(root), run_eval_mod._OWNED_ROOTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
