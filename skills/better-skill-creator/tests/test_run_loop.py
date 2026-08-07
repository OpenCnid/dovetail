#!/usr/bin/env python3
"""Tests for scripts/run_loop.py -- the orchestration, not just the helpers.

Run from the skill root:

    python -m unittest tests.test_run_loop -v

`run_loop.run_loop` is 293 lines and 36 branches and was **entirely
unexercised** (research/V7-verification.md A, _REMEDIATION.md R2). It gates
spend, splits the eval set, decides whether the measurement produced any signal
at all, and decides which description to hand back. `run_eval` got a stub
harness and 47 tests; the parallel component with identical exposure got none.

Nothing here spends money. Two seams are used, both of them real code paths:

* the *probes* are driven by replacing `run_eval.run_single_query` with a
  programmable fake, so `run_eval`'s own aggregation runs for real;
* the *optimizer* is driven by pointing `BETTER_SKILL_CREATOR_CLAUDE_ARGV` at
  tests/fixtures/stub_claude.py, so `improve_description` runs for real,
  subprocess and all, and records the prompt it was handed.

The CLI cases go further and run `python -m scripts.run_loop` as a subprocess
with **stdin from DEVNULL**, which is the configuration that used to kill the
run outright.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse
from urllib.request import url2pathname

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts import run_eval as run_eval_mod  # noqa: E402
from scripts import run_loop as run_loop_mod  # noqa: E402
from scripts.run_loop import run_loop, split_eval_set  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STUB = FIXTURES / "stub_claude.py"
STREAMS = FIXTURES / "streams"
TRIGGER_STREAM = STREAMS / "trigger_skill_first.jsonl"
PROBE_SKILL = FIXTURES / "probe-skill"


def tagged(text: str) -> str:
    return f"<new_description>{text}</new_description>"


def eval_set(pos: int, neg: int, prefix: str = "") -> list[dict]:
    return (
        [{"query": f"{prefix}p{i}", "should_trigger": True} for i in range(pos)]
        + [{"query": f"{prefix}n{i}", "should_trigger": False} for i in range(neg)]
    )


def scripted_probe(status_for):
    """Build a run_single_query replacement from a callable.

    `status_for(query, description, call_index)` returns one of
    "trigger" / "no_trigger" / "error", so a test can make behaviour depend on
    the description under test -- which is how "iteration 2 got better" is
    expressed without asserting on any internal.
    """
    calls: dict[tuple, int] = {}

    def fake(query, skill_name, skill_description, timeout, *args, **kwargs):
        key = (query, skill_description)
        index = calls.get(key, 0)
        calls[key] = index + 1
        status = status_for(query, skill_description, index)
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
            "clone_registered": True,
            "competing_skills": [],
        }

    return fake


class LoopHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="run-loop-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.control_path = self.tmp / "control.json"
        self.prompt_log = self.tmp / "prompts.jsonl"

        self._saved_env = {
            k: os.environ.get(k)
            for k in ("BETTER_SKILL_CREATOR_CLAUDE_ARGV", "STUB_CLAUDE_CONTROL",
                      "STUB_CLAUDE_PROMPT_LOG", "STUB_CLAUDE_REPORT")
        }
        os.environ["BETTER_SKILL_CREATOR_CLAUDE_ARGV"] = json.dumps([sys.executable, str(STUB)])
        os.environ["STUB_CLAUDE_CONTROL"] = str(self.control_path)
        os.environ["STUB_CLAUDE_PROMPT_LOG"] = str(self.prompt_log)
        os.environ.pop("STUB_CLAUDE_REPORT", None)
        self.addCleanup(self._restore_env)
        self.control()

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def control(self, **kwargs):
        self.control_path.write_text(json.dumps(kwargs), encoding="utf-8")

    def prompts(self) -> list[dict]:
        if not self.prompt_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.prompt_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def loop(self, evals, status_for, *, holdout=0.0, max_iterations=3, **kwargs):
        with mock.patch.object(run_eval_mod, "run_single_query", scripted_probe(status_for)):
            return run_loop(
                eval_set=evals,
                skill_path=PROBE_SKILL,
                description_override=kwargs.pop("description_override", None),
                num_workers=2,
                timeout=5,
                max_iterations=max_iterations,
                runs_per_query=kwargs.pop("runs_per_query", 1),
                trigger_threshold=0.5,
                holdout=holdout,
                model="haiku",
                verbose=kwargs.pop("verbose", False),
                **kwargs,
            )


# ---------------------------------------------------------------------------
# The train/test split
# ---------------------------------------------------------------------------


class TestSplitRefusesAnEmptyStratum(unittest.TestCase):
    """research/02 F11. A train set with no positives cannot fail, so the loop
    announces "all train queries passed on iteration 1" and stops -- the most
    convincing possible output from the least informative possible split."""

    def test_no_positives_left_in_train_is_refused(self):
        with self.assertRaises(ValueError) as ctx:
            split_eval_set(eval_set(1, 10), holdout=0.4)
        self.assertIn("cannot fail", str(ctx.exception))

    def test_no_negatives_left_in_train_is_refused(self):
        with self.assertRaises(ValueError) as ctx:
            split_eval_set(eval_set(10, 1), holdout=0.4)
        self.assertIn("cannot fail", str(ctx.exception))

    def test_the_refusal_names_the_counts_and_a_way_out(self):
        with self.assertRaises(ValueError) as ctx:
            split_eval_set(eval_set(1, 10), holdout=0.4)
        message = str(ctx.exception)
        self.assertIn("--holdout", message)
        self.assertIn("Add more queries", message)

    def test_both_strata_are_represented_in_the_held_out_set(self):
        _train, test = split_eval_set(eval_set(10, 10), holdout=0.4)
        self.assertTrue(any(e["should_trigger"] for e in test))
        self.assertTrue(any(not e["should_trigger"] for e in test))

    def test_the_split_is_deterministic(self):
        first = split_eval_set(eval_set(10, 10), holdout=0.4)
        second = split_eval_set(eval_set(10, 10), holdout=0.4)
        self.assertEqual(first, second)

    def test_a_refused_split_stops_the_loop_before_any_probe(self):
        launched = []

        def spy(*args, **kwargs):
            launched.append(args)
            raise AssertionError("no probe may launch after a refused split")

        with mock.patch.object(run_eval_mod, "run_single_query", spy):
            with self.assertRaises(ValueError):
                run_loop(
                    eval_set=eval_set(1, 10), skill_path=PROBE_SKILL,
                    description_override=None, num_workers=1, timeout=5,
                    max_iterations=1, runs_per_query=1, trigger_threshold=0.5,
                    holdout=0.4, model="haiku", verbose=False,
                )
        self.assertEqual(launched, [])


# ---------------------------------------------------------------------------
# The no-signal guard
# ---------------------------------------------------------------------------


class TestNoSignalGuard(LoopHarness):
    """The loop must refuse to hand back a "best" description when the
    measurement that chose it produced no signal. A harness that errors on every
    probe scores every negative as a pass, which reads as "precision 100%,
    recall 0%", which reads as a diagnosis of the description."""

    def test_zero_scored_positive_runs_withholds_the_recommendation(self):
        out = self.loop(
            eval_set(2, 2),
            lambda q, d, i: "error" if q.startswith("p") else "no_trigger",
            max_iterations=1,
        )
        self.assertFalse(out["apply_recommended"])
        self.assertTrue(
            any("measured nothing" in w for w in out["measurement_warnings"]),
            out["measurement_warnings"],
        )

    def test_zero_triggers_across_real_runs_withholds_the_recommendation(self):
        out = self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger", max_iterations=1)
        self.assertFalse(out["apply_recommended"])
        warning = " ".join(out["measurement_warnings"])
        self.assertIn("recall is 0%", warning)
        self.assertIn("signature of a broken measurement", warning)

    def test_the_zero_recall_warning_names_the_thing_to_check(self):
        out = self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger", max_iterations=1)
        warning = " ".join(out["measurement_warnings"])
        self.assertIn("shadowing the probe", warning)
        self.assertIn("--num-workers 1", warning)

    def test_a_measurement_with_signal_is_recommended(self):
        out = self.loop(
            eval_set(2, 2),
            lambda q, d, i: "trigger" if q.startswith("p") else "no_trigger",
            max_iterations=1,
        )
        self.assertTrue(out["apply_recommended"])
        self.assertEqual(out["measurement_warnings"], [])

    def test_partial_recall_still_counts_as_signal(self):
        """One positive triggering is a measurement; the guard is for zero."""
        out = self.loop(
            eval_set(2, 2),
            lambda q, d, i: "trigger" if q == "p0" else "no_trigger",
            max_iterations=1,
        )
        self.assertTrue(out["apply_recommended"])

    def test_errored_probes_are_reported_but_do_not_by_themselves_veto(self):
        out = self.loop(
            eval_set(2, 2),
            lambda q, d, i: "error" if q == "n0" else ("trigger" if q[0] == "p" else "no_trigger"),
            max_iterations=1,
        )
        self.assertTrue(out["apply_recommended"])
        self.assertTrue(any("errored" in w for w in out["measurement_warnings"]))


# ---------------------------------------------------------------------------
# Loop control flow
# ---------------------------------------------------------------------------


class TestLoopControl(LoopHarness):
    def test_all_passing_stops_after_one_iteration_without_calling_the_optimizer(self):
        out = self.loop(
            eval_set(2, 2),
            lambda q, d, i: "trigger" if q.startswith("p") else "no_trigger",
            max_iterations=4,
        )
        self.assertTrue(out["exit_reason"].startswith("all_passed"))
        self.assertEqual(out["iterations_run"], 1)
        self.assertEqual(self.prompts(), [], "nothing to improve, so nothing was asked")

    def test_every_train_query_erroring_stops_the_loop(self):
        out = self.loop(eval_set(2, 2), lambda q, d, i: "error", max_iterations=4)
        self.assertTrue(out["exit_reason"].startswith("all_queries_errored"))
        self.assertEqual(out["iterations_run"], 1)
        self.assertEqual(self.prompts(), [],
                         "a dead harness must not be handed to the optimizer")

    def test_persistent_failure_runs_to_max_iterations(self):
        self.control(optimizer_responses=[tagged("attempt A"), tagged("attempt B")])
        out = self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger", max_iterations=3)
        self.assertEqual(out["exit_reason"], "max_iterations (3)")
        self.assertEqual(out["iterations_run"], 3)
        self.assertEqual(len(self.prompts()), 2, "n-1 optimizer calls for n iterations")

    def test_the_proposed_description_is_what_the_next_iteration_measures(self):
        self.control(optimizer_response=tagged("the second description"))
        seen: list[str] = []

        def status(query, description, index):
            seen.append(description)
            return "no_trigger"

        self.loop(eval_set(2, 2), status, max_iterations=2)
        self.assertIn("the second description", seen)

    def test_an_optimizer_failure_keeps_the_iterations_already_paid_for(self):
        self.control(optimizer_exit_code=1, optimizer_stderr="rate limited\n")
        out = self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger", max_iterations=3)
        self.assertTrue(out["exit_reason"].startswith("improve_failed"))
        self.assertEqual(out["iterations_run"], 1)
        self.assertIn("note", out["history"][0])
        self.assertIn("rate limited", out["history"][0]["note"])
        self.assertTrue(any("improve_description failed" in w
                            for w in out["measurement_warnings"]))

    def test_an_over_limit_rewrite_is_an_optimizer_failure_not_a_new_description(self):
        """A description over 1024 characters does not load at all. The loop must
        not adopt one and measure it as though it were a candidate."""
        self.control(optimizer_responses=[tagged("L" * 1100), tagged("M" * 1090)])
        out = self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger", max_iterations=3)
        self.assertTrue(out["exit_reason"].startswith("improve_failed"))
        self.assertLessEqual(len(out["best_description"]), 1024)

    def test_holdout_zero_measures_the_whole_set_as_train(self):
        out = self.loop(eval_set(3, 3), lambda q, d, i: "no_trigger",
                        holdout=0.0, max_iterations=1)
        self.assertEqual(out["train_size"], 6)
        self.assertEqual(out["test_size"], 0)
        self.assertIsNone(out["best_test_score"])


# ---------------------------------------------------------------------------
# What the optimizer is allowed to see
# ---------------------------------------------------------------------------


class TestOptimizerBlinding(LoopHarness):
    def test_held_out_queries_never_reach_the_optimizer(self):
        """Selection is by held-out score. An optimizer that can see the
        held-out rows can tune against them, and the split stops meaning
        anything."""
        self.control(optimizer_response=tagged("a second attempt"))
        evals = eval_set(6, 6, prefix="TRAIN")
        for item in evals:
            item["query"] = item["query"].replace("TRAIN", "Q")
        with mock.patch.object(run_loop_mod, "split_eval_set") as split:
            split.return_value = (
                [{"query": "TRAINPOS", "should_trigger": True},
                 {"query": "TRAINNEG", "should_trigger": False}],
                [{"query": "HELDOUTPOS", "should_trigger": True},
                 {"query": "HELDOUTNEG", "should_trigger": False}],
            )
            self.loop(evals, lambda q, d, i: "no_trigger", holdout=0.4, max_iterations=2)
        prompt = self.prompts()[0]["prompt"]
        self.assertIn("TRAINPOS", prompt)
        self.assertNotIn("HELDOUT", prompt)

    def test_test_scores_are_stripped_from_the_history_block(self):
        self.control(optimizer_responses=[tagged("attempt A"), tagged("attempt B")])
        with mock.patch.object(run_loop_mod, "split_eval_set") as split:
            split.return_value = (
                [{"query": "trainpos", "should_trigger": True},
                 {"query": "trainneg", "should_trigger": False}],
                [{"query": "heldpos", "should_trigger": True},
                 {"query": "heldneg", "should_trigger": False}],
            )
            self.loop(eval_set(6, 6), lambda q, d, i: "no_trigger",
                      holdout=0.4, max_iterations=3)
        for record in self.prompts():
            self.assertNotIn("test=", record["prompt"])

    def test_unmeasured_train_rows_are_withheld_from_the_optimizer(self):
        self.control(optimizer_response=tagged("a second attempt"))
        evals = [
            {"query": "measured positive", "should_trigger": True},
            {"query": "measured negative", "should_trigger": False},
            {"query": "DEADPROBE query", "should_trigger": True},
        ]
        self.loop(
            evals,
            lambda q, d, i: "error" if q.startswith("DEADPROBE") else "no_trigger",
            max_iterations=2,
        )
        prompt = self.prompts()[0]["prompt"]
        self.assertIn("measured positive", prompt)
        self.assertNotIn("DEADPROBE", prompt)
        self.assertIn("could not be measured at all", prompt)


# ---------------------------------------------------------------------------
# Selecting the description to hand back
# ---------------------------------------------------------------------------


class TestBestSelection(LoopHarness):
    def test_a_tie_keeps_the_earliest_description(self):
        self.control(optimizer_responses=[tagged("attempt A"), tagged("attempt B")])
        out = self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger", max_iterations=3)
        self.assertEqual(out["best_description"], out["original_description"])
        self.assertTrue(out["best_is_original"])

    def test_the_original_winning_is_reported_as_a_warning(self):
        self.control(optimizer_responses=[tagged("attempt A"), tagged("attempt B")])
        out = self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger", max_iterations=3)
        self.assertTrue(
            any("best-scoring description is the original" in w
                for w in out["measurement_warnings"]),
            out["measurement_warnings"],
        )

    def test_a_genuinely_better_iteration_is_selected(self):
        self.control(optimizer_response=tagged("the better description"))

        def status(query, description, index):
            if description == "the better description" and query.startswith("p"):
                return "trigger"
            return "no_trigger"

        out = self.loop(eval_set(2, 2), status, max_iterations=3)
        self.assertEqual(out["best_description"], "the better description")
        self.assertFalse(out["best_is_original"])
        self.assertTrue(out["apply_recommended"])

    def test_selection_uses_the_held_out_score_when_there_is_one(self):
        self.control(optimizer_response=tagged("the better description"))
        with mock.patch.object(run_loop_mod, "split_eval_set") as split:
            split.return_value = (
                [{"query": "trainpos", "should_trigger": True},
                 {"query": "trainneg", "should_trigger": False}],
                [{"query": "heldpos", "should_trigger": True},
                 {"query": "heldneg", "should_trigger": False}],
            )

            def status(query, description, index):
                if description == "the better description" and query == "heldpos":
                    return "trigger"
                return "no_trigger"

            out = self.loop(eval_set(6, 6), status, holdout=0.4, max_iterations=2)
        self.assertEqual(out["best_description"], "the better description")
        self.assertEqual(out["best_score"], out["best_test_score"])


# ---------------------------------------------------------------------------
# harness_health (R24: documented as checkable here, and absent)
# ---------------------------------------------------------------------------


class TestHarnessHealthIsReported(LoopHarness):
    """references/description-optimization.md tells the reader to check
    `harness_health` after a loop run. It was folded into prose warnings and the
    key was dropped, so the documented check had nothing to read."""

    def test_results_carry_a_harness_health_block(self):
        out = self.loop(
            eval_set(2, 2),
            lambda q, d, i: "trigger" if q.startswith("p") else "no_trigger",
            max_iterations=1,
        )
        self.assertIn("harness_health", out)
        self.assertEqual(out["harness_health"]["probes_where_clone_was_not_registered"], 0)
        self.assertEqual(out["harness_health"]["competing_installed_skills"], [])

    def test_each_iteration_carries_its_own_health(self):
        self.control(optimizer_responses=[tagged("A"), tagged("B")])
        out = self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger", max_iterations=3)
        self.assertEqual(len(out["harness_health"]["per_iteration"]), 3)
        self.assertEqual([h["iteration"] for h in out["harness_health"]["per_iteration"]],
                         [1, 2, 3])
        for entry in out["history"]:
            self.assertIn("harness_health", entry)

    def test_unregistered_clones_are_counted_across_iterations(self):
        def fake(query, skill_name, skill_description, timeout, *args, **kwargs):
            return {
                "query": query, "probe_id": "x", "status": "no_trigger",
                "triggered": False, "stop_reason": "result", "error": None,
                "tools": [], "elapsed_seconds": 0.0, "cost_usd": None,
                "probe_root": None, "clone_registered": False,
                "competing_skills": ["widget-forge"],
            }

        self.control(optimizer_responses=[tagged("A")])
        with mock.patch.object(run_eval_mod, "run_single_query", fake):
            out = run_loop(
                eval_set=eval_set(2, 2), skill_path=PROBE_SKILL,
                description_override=None, num_workers=2, timeout=5,
                max_iterations=2, runs_per_query=1, trigger_threshold=0.5,
                holdout=0.0, model="haiku", verbose=False,
            )
        health = out["harness_health"]
        self.assertEqual(health["probes_where_clone_was_not_registered"], 8)
        self.assertEqual(health["competing_installed_skills"], ["widget-forge"])

    def test_no_registration_signal_reports_none_not_zero(self):
        """C4: absent data is absent. "No probe told us" and "zero probes were
        unregistered" are different facts and must not render alike."""
        def fake(query, skill_name, skill_description, timeout, *args, **kwargs):
            return {
                "query": query, "probe_id": "x", "status": "no_trigger",
                "triggered": False, "stop_reason": "result", "error": None,
                "tools": [], "elapsed_seconds": 0.0, "cost_usd": None,
                "probe_root": None, "clone_registered": None, "competing_skills": [],
            }

        with mock.patch.object(run_eval_mod, "run_single_query", fake):
            out = run_loop(
                eval_set=eval_set(2, 2), skill_path=PROBE_SKILL,
                description_override=None, num_workers=2, timeout=5,
                max_iterations=1, runs_per_query=1, trigger_threshold=0.5,
                holdout=0.0, model="haiku", verbose=False,
            )
        self.assertEqual(out["harness_health"]["probes_reporting_registration"], 0)


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


class TestArtifacts(LoopHarness):
    def test_the_live_report_is_written_during_the_run_not_only_at_the_end(self):
        self.control(optimizer_responses=[tagged("A"), tagged("B")])
        live = self.tmp / "live.html"
        seen: list[int] = []

        def status(query, description, index):
            if live.exists():
                seen.append(len(live.read_text(encoding="utf-8")))
            return "no_trigger"

        self.loop(eval_set(2, 2), status, max_iterations=3, live_report_path=live)
        self.assertTrue(live.exists())
        self.assertTrue(seen, "the report should exist before the final iteration ends")

    def test_a_non_ascii_description_survives_into_the_live_report(self):
        self.control(optimizer_response=tagged("Utilisez — 中文 ✓"))
        live = self.tmp / "live.html"
        self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger",
                  max_iterations=2, live_report_path=live)
        self.assertIn("Utilisez", live.read_bytes().decode("utf-8"))

    def test_transcripts_are_logged_per_iteration(self):
        self.control(optimizer_responses=[tagged("A"), tagged("B")])
        logs = self.tmp / "logs"
        self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger",
                  max_iterations=3, log_dir=logs)
        written = sorted(p.name for p in logs.glob("improve_iter_*.json"))
        self.assertEqual(written, ["improve_iter_1.json", "improve_iter_2.json"])

    def test_cost_is_summed_across_iterations(self):
        self.control(optimizer_responses=[tagged("A")])
        out = self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger",
                        max_iterations=2, runs_per_query=1)
        # 4 queries x 1 run x 2 iterations x $0.01
        self.assertAlmostEqual(out["actual_cost_usd"], 0.08, places=4)

    def test_a_bad_skill_md_is_attributed_to_the_file(self):
        broken = self.tmp / "broken-skill"
        broken.mkdir()
        (broken / "SKILL.md").write_text("no frontmatter here\n", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            run_loop(
                eval_set=eval_set(2, 2), skill_path=broken,
                description_override=None, num_workers=1, timeout=5,
                max_iterations=1, runs_per_query=1, trigger_threshold=0.5,
                holdout=0.0, model="haiku", verbose=False,
            )
        self.assertIn("SKILL.md", str(ctx.exception))


# ---------------------------------------------------------------------------
# The CLI, non-interactively
# ---------------------------------------------------------------------------


class TestCliNonInteractive(LoopHarness):
    """C14 / R26. `project_spend` guarded its `input()` with
    `if not sys.stdin.isatty()`. On Windows `isatty()` returns **True** for NUL
    and for `subprocess.DEVNULL`, so the guard missed, `input()` ran against a
    stream at EOF, and an uncaught EOFError killed the run at the documented
    defaults before a single probe launched.

    Every case here runs the real CLI with stdin from DEVNULL -- the exact
    configuration that used to fail -- and with a redirected-file stdin, which
    is the POSIX shape of the same thing.
    """

    def _eval_file(self, pos=2, neg=2):
        path = self.tmp / "evals.json"
        path.write_text(json.dumps(eval_set(pos, neg)), encoding="utf-8")
        return path

    def _run(self, args, stdin=subprocess.DEVNULL):
        return subprocess.run(
            [sys.executable, "-m", "scripts.run_loop", *args],
            cwd=str(SKILL_ROOT),
            stdin=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=300,
        )

    def _base_args(self, evals=None):
        return [
            "--eval-set", str(evals or self._eval_file()),
            "--skill-path", str(PROBE_SKILL),
            "--model", "haiku",
            "--report", "none",
            "--holdout", "0",
            "--runs-per-query", "1",
            "--max-iterations", "1",
            "--timeout", "60",
        ]

    def test_isatty_alone_does_not_detect_a_redirected_stdin(self):
        """The platform fact the guard was built on, asserted directly. If this
        ever starts failing, the isatty()-only guard would have been fine and
        this whole class is over-cautious -- which is worth knowing."""
        probe = subprocess.run(
            [sys.executable, "-c", "import sys; print(sys.stdin.isatty())"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
        )
        if os.name == "nt":
            self.assertEqual(probe.stdout.strip(), "True",
                             "on Windows, NUL/DEVNULL reports as a tty")

    def test_a_full_run_completes_with_stdin_from_devnull(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True,
                     optimizer_response=tagged("a second description"))
        proc = self._run(self._base_args())
        self.assertNotIn("EOFError", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
        out = json.loads(proc.stdout)
        self.assertEqual(out["iterations_run"], 1)
        self.assertTrue(out["apply_recommended"])
        self.assertIn("harness_health", out)

    def test_a_full_run_completes_with_stdin_from_a_redirected_file(self):
        empty = self.tmp / "empty.txt"
        empty.write_text("", encoding="utf-8")
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        with open(empty, "r", encoding="utf-8") as handle:
            proc = self._run(self._base_args(), stdin=handle)
        self.assertNotIn("EOFError", proc.stderr)
        self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])

    def test_over_threshold_refuses_cleanly_instead_of_raising_eoferror(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        proc = self._run(self._base_args() + ["--confirm-threshold", "0.0001",
                                              "--max-cost", "1000"])
        self.assertEqual(proc.returncode, 2, proc.stderr[-3000:])
        self.assertNotIn("EOFError", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("Refusing to start", proc.stderr)
        self.assertIn("--yes", proc.stderr)

    def test_yes_bypasses_the_confirmation(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        proc = self._run(self._base_args() + ["--confirm-threshold", "0.0001",
                                              "--max-cost", "1000", "--yes"])
        self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])

    def test_max_cost_still_refuses_before_the_confirmation_gate(self):
        proc = self._run(self._base_args() + ["--max-cost", "0.0001", "--yes"])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("exceeds --max-cost", proc.stderr)

    def test_a_wrong_shaped_eval_set_is_refused_with_a_sentence(self):
        """R27: the file is hand-authored or exported from the review page, so a
        wrong shape is the expected error, not an exotic one."""
        path = self.tmp / "wrapped.json"
        path.write_text(json.dumps({"queries": eval_set(2, 2)}), encoding="utf-8")
        proc = self._run(self._base_args(evals=path))
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn('wrapped under the key "queries"', proc.stderr)

    def test_a_missing_skill_md_is_refused_before_the_spend_gate(self):
        missing = self.tmp / "not-a-skill"
        missing.mkdir()
        proc = self._run([
            "--eval-set", str(self._eval_file()), "--skill-path", str(missing),
            "--model", "haiku", "--report", "none",
        ])
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("No SKILL.md found", proc.stderr)
        self.assertNotIn("Projected spend", proc.stderr)

    def test_a_no_signal_run_exits_nonzero(self):
        self.control(mode="empty", exit_code=1, stderr="boom\n")
        proc = self._run(self._base_args() + ["--max-error-rate", "1.0"])
        self.assertEqual(proc.returncode, 4, proc.stderr[-2000:])
        self.assertIn("DO NOT APPLY", proc.stderr)

    def test_results_dir_receives_the_json(self):
        self.control(stream=str(TRIGGER_STREAM), rename=True)
        results_dir = self.tmp / "results"
        proc = self._run(self._base_args() + ["--results-dir", str(results_dir)])
        self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
        written = list(results_dir.glob("*/results.json"))
        self.assertEqual(len(written), 1, list(results_dir.glob("*")))
        json.loads(written[0].read_text(encoding="utf-8"))


class TestMainWiring(LoopHarness):
    """main()'s own branches, in-process so the browser can be held shut."""

    def _argv(self, *extra):
        path = self.tmp / "evals.json"
        path.write_text(json.dumps(eval_set(2, 2)), encoding="utf-8")
        return [
            "run_loop", "--eval-set", str(path), "--skill-path", str(PROBE_SKILL),
            "--model", "haiku", "--holdout", "0", "--runs-per-query", "1",
            "--max-iterations", "1", "--yes", *extra,
        ]

    def _main(self, *extra):
        opened: list[str] = []
        fake = scripted_probe(
            lambda q, d, i: "trigger" if q.startswith("p") else "no_trigger"
        )
        with mock.patch.object(run_eval_mod, "run_single_query", fake), \
                mock.patch.object(run_loop_mod.webbrowser, "open", opened.append), \
                mock.patch.object(sys, "argv", self._argv(*extra)):
            run_loop_mod.main()
        return opened

    def test_an_html_report_is_written_and_opened(self):
        report = self.tmp / "report.html"
        opened = self._main("--report", str(report))
        self.assertTrue(report.exists())
        body = report.read_bytes().decode("utf-8")
        self.assertIn("<html", body.lower())
        self.assertEqual(len(opened), 1)

    def test_report_none_writes_nothing_and_opens_nothing(self):
        opened = self._main("--report", "none")
        self.assertEqual(opened, [])
        self.assertEqual(list(self.tmp.glob("*.html")), [])

    def test_results_dir_receives_report_and_results(self):
        results_dir = self.tmp / "out"
        self._main("--report", str(self.tmp / "r.html"), "--results-dir", str(results_dir))
        stamped = list(results_dir.iterdir())
        self.assertEqual(len(stamped), 1)
        self.assertTrue((stamped[0] / "results.json").exists())
        self.assertTrue((stamped[0] / "report.html").exists())

    def test_report_auto_lands_in_the_os_temp_dir_not_a_literal_tmp(self):
        """C7: no bare /tmp. The path has to come from tempfile.gettempdir()."""
        opened = self._main("--report", "auto")
        self.assertEqual(len(opened), 1)
        # run_loop hands webbrowser.open a Path.as_uri(), and url2pathname is that
        # call's exact inverse on both platforms. Stripping "file:///" textually
        # instead drops the leading slash of a POSIX path -- "file:///tmp/r.html"
        # became the *relative* "tmp/r.html" -- so this passed on Windows, where
        # the URI carries a drive letter, and failed on Linux. It also decodes the
        # percent-escapes that a temp directory containing a space would produce.
        target = Path(url2pathname(urlparse(opened[0]).path))
        self.addCleanup(lambda: target.exists() and target.unlink())
        self.assertTrue(
            str(target).lower().startswith(str(Path(tempfile.gettempdir())).lower()),
            f"{target} is not under {tempfile.gettempdir()}",
        )
        self.assertTrue(target.exists())

    def test_a_refused_split_exits_one_with_a_sentence(self):
        path = self.tmp / "lopsided.json"
        path.write_text(json.dumps(eval_set(1, 10)), encoding="utf-8")
        argv = [
            "run_loop", "--eval-set", str(path), "--skill-path", str(PROBE_SKILL),
            "--model", "haiku", "--holdout", "0.4", "--runs-per-query", "1",
            "--max-iterations", "1", "--yes", "--report", "none",
        ]
        err = io.StringIO()
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(sys, "stderr", err):
            with self.assertRaises(SystemExit) as ctx:
                run_loop_mod.main()
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("cannot fail", err.getvalue())


class TestVerboseOutput(LoopHarness):
    """The progress stream is the only thing a person watching a long run sees,
    and C6 puts it on stderr so a machine consumer reading stdout is never
    corrupted by it."""

    def _verbose(self, **kwargs):
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            out = self.loop(
                eval_set(6, 6),
                lambda q, d, i: "trigger" if q.startswith("p") else "no_trigger",
                verbose=True,
                **kwargs,
            )
        return out, err.getvalue()

    def test_the_split_sizes_are_announced(self):
        with mock.patch.object(run_loop_mod, "split_eval_set") as split:
            split.return_value = (
                [{"query": "trainpos", "should_trigger": True},
                 {"query": "trainneg", "should_trigger": False}],
                [{"query": "heldpos", "should_trigger": True}],
            )
            _out, err = self._verbose(holdout=0.4, max_iterations=1)
        self.assertIn("Split: 2 train, 1 test", err)

    def test_progress_names_the_iteration_and_the_exit_reason(self):
        _out, err = self._verbose(max_iterations=2)
        self.assertIn("Iteration 1/2", err)
        self.assertIn("Exit reason: all_passed", err)
        self.assertIn("Best score:", err)

    def test_train_and_test_stats_are_both_printed(self):
        with mock.patch.object(run_loop_mod, "split_eval_set") as split:
            split.return_value = (
                [{"query": "trainpos", "should_trigger": True},
                 {"query": "trainneg", "should_trigger": False}],
                [{"query": "heldpos", "should_trigger": True}],
            )
            _out, err = self._verbose(holdout=0.4, max_iterations=1)
        self.assertIn("Train:", err)
        self.assertIn("Test :", err)

    def test_the_proposed_description_is_echoed_before_the_next_iteration(self):
        self.control(optimizer_response=tagged("a visibly different description"))
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger",
                      verbose=True, max_iterations=2)
        text = err.getvalue()
        self.assertIn("Improving description", text)
        self.assertIn("a visibly different description", text)
        self.assertIn("Max iterations reached (2)", text)

    def test_a_withheld_recommendation_is_stated_in_plain_words(self):
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger",
                      verbose=True, max_iterations=1)
        self.assertIn("DO NOT APPLY", err.getvalue())

    def test_a_fully_errored_iteration_says_why_it_stopped(self):
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            self.loop(eval_set(2, 2), lambda q, d, i: "error",
                      verbose=True, max_iterations=3)
        self.assertIn("nothing here measures the description", err.getvalue())


class TestPermissionPolicy(LoopHarness):
    """The loop launches two kinds of `claude -p`: the probes, and the
    improvement call. The improvement call is the looser of the two -- it runs
    in the caller's own working directory with every settings scope loaded --
    and `--model` already gives it a model of its own, so a posture of its own
    is the plausible drift. `scripted_probe` binds `*args` and discards them,
    so the probe leg is not observable here; the optimizer leg is, through the
    stub's prompt log."""

    def test_the_optimizer_call_carries_the_loops_permission_posture(self):
        self.control(optimizer_response="<new_description>a second one</new_description>")
        self.loop(eval_set(2, 2), lambda q, d, i: "no_trigger", max_iterations=2)
        argv = self.prompts()[0]["argv"]
        self.assertIn("--permission-mode", argv)
        self.assertEqual(
            argv[argv.index("--permission-mode") + 1], run_eval_mod.SAFE_PERMISSION_MODE
        )

    def test_the_opt_in_reaches_the_optimizer_too(self):
        """Dropping `allow_host_permissions=` from the improve call alone is
        the expensive half: `improve_description` then refuses the mode
        `run_eval` just accepted, the blanket handler records it as
        `improve_failed`, and the loop stops on an iteration already paid for."""
        self.control(optimizer_response="<new_description>a second one</new_description>")
        out = self.loop(
            eval_set(2, 2), lambda q, d, i: "no_trigger", max_iterations=2,
            permission_mode=run_eval_mod.INHERIT_PERMISSION_MODE,
            allow_host_permissions=True,
        )
        self.assertNotIn(
            "improve_failed", out["exit_reason"], out.get("measurement_warnings")
        )
        self.assertNotIn("--permission-mode", self.prompts()[0]["argv"])

    def test_the_loop_refuses_an_unopted_mode_before_any_probe(self):
        with self.assertRaises(run_eval_mod.PermissionModeError):
            self.loop(
                eval_set(2, 2), lambda q, d, i: "no_trigger",
                permission_mode=run_eval_mod.INHERIT_PERMISSION_MODE,
            )
        self.assertEqual(self.prompts(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
