#!/usr/bin/env python3
"""Tests for the benchmark pipeline: preflight -> validate_grading -> aggregate.

Run from the skill root:

    python -m unittest tests.test_benchmark_contracts -v
    python -m tests.test_benchmark_contracts

Every case corresponds to a defect demonstrated against the previous scripts in
research/00-orchestrator-repro.md, research/03-viewer-benchmark.md,
research/11-schema-consistency.md, research/14-workflow-design.md, and
research/15-end-to-end.md, or to a clause of research/_CONTRACT.md.

The fixture workspaces are defined in tests/make_workspace_fixtures.py and are
rebuilt into a temporary directory for each run - `aggregate_benchmark` writes
benchmark.json and benchmark.md into the iteration directory it is pointed at,
so it must never be pointed at the committed copy.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.aggregate_benchmark import (  # noqa: E402
    ABSTAIN_REASON_REPAIRS,
    METRIC_POLARITY,
    calculate_stats,
    resolve_roles,
)
from scripts.validate_grading import (  # noqa: E402
    ABSTAIN_REASON_MEANINGS,
    ABSTAIN_REASONS,
    classify_grading_path,
    compute_pass_rate,
    validate_grading_file,
)
from tests.make_workspace_fixtures import build  # noqa: E402


# --------------------------------------------------------------------------
# Harness
# --------------------------------------------------------------------------

class WorkspaceCase(unittest.TestCase):
    """Base class: a private copy of every workspace fixture."""

    root: Path

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="better-skillcreator-bench-")
        cls.root = build(Path(cls._tmp))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    # -- helpers ----------------------------------------------------------

    def iteration(self, fixture: str) -> Path:
        return self.root / fixture / "iteration-1"

    def script(self, module: str, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", f"scripts.{module}", *[str(a) for a in args]],
            cwd=str(SKILL_ROOT),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

    def aggregate(self, fixture: str, *args) -> subprocess.CompletedProcess:
        return self.script("aggregate_benchmark", self.iteration(fixture),
                           "--skill-name", "demo", *args)

    def benchmark(self, fixture: str) -> dict:
        path = self.iteration(fixture) / "benchmark.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def benchmark_md(self, fixture: str) -> str:
        return (self.iteration(fixture) / "benchmark.md").read_text(encoding="utf-8")

    def combined(self, proc: subprocess.CompletedProcess) -> str:
        return (proc.stdout or "") + (proc.stderr or "")


# --------------------------------------------------------------------------
# The flagship reproduction
# --------------------------------------------------------------------------

class TestFlagshipRepro(WorkspaceCase):
    """research/00-orchestrator-repro.md.

    Two configurations graded 4/4 in the layout SKILL.md documented. The old
    aggregator printed `Delta: +0.00` over `"runs": []` and exited 0. The
    contract requires this to now either aggregate correctly or refuse loudly -
    never silence, never zeros.
    """

    def test_aggregates_the_real_data(self):
        proc = self.aggregate("repro-flat")
        self.assertEqual(proc.returncode, 0, self.combined(proc))

        data = self.benchmark("repro-flat")
        self.assertEqual(len(data["runs"]), 2,
                         "both graded runs must reach the benchmark")
        self.assertEqual(data["metadata"]["evals_run"], [0])

        for config in ("with_skill", "without_skill"):
            stats = data["run_summary"][config]["pass_rate"]
            self.assertIsNotNone(stats, f"{config} aggregated to nothing")
            self.assertEqual(stats["mean"], 1.0,
                             f"{config} graded 4/4 and must report 1.0, not 0.0")
            self.assertEqual(stats["n"], 1)

    def test_delta_of_zero_is_a_measurement_not_an_empty_table(self):
        self.aggregate("repro-flat")
        delta = self.benchmark("repro-flat")["run_summary"]["delta"]["pass_rate"]
        # +0.00 is the right answer here - both configurations really did score
        # 1.0. What must not survive is +0.00 computed from no data at all.
        self.assertEqual(delta["value"], 0.0)
        self.assertEqual(delta["formatted"], "+0.00")
        self.assertIsNone(delta["better"], "a zero delta is neither better nor worse")

    def test_legacy_layout_is_announced_not_silently_accepted(self):
        proc = self.aggregate("repro-flat")
        self.assertIn("DEPRECATED LAYOUT", self.combined(proc))
        warnings = self.benchmark("repro-flat")["layout_warnings"]
        self.assertTrue(any("DEPRECATED LAYOUT" in w for w in warnings))
        self.assertTrue(any("run-1" in w for w in warnings))

    def test_preflight_refuses_the_layout_before_any_spend(self):
        proc = self.script("preflight", self.root / "repro-flat")
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        out = self.combined(proc)
        self.assertIn("canonical layout requires a run level", out)
        self.assertIn("run-1", out, "the message must name the path expected")
        self.assertIn("with_skill", out, "the message must name the path found")


# --------------------------------------------------------------------------
# C4: zero discovered runs
# --------------------------------------------------------------------------

class TestZeroRuns(WorkspaceCase):
    """An eval directory named descriptively, which nothing discovers."""

    def test_exits_non_zero(self):
        proc = self.aggregate("zero-runs")
        self.assertNotEqual(proc.returncode, 0)

    def test_writes_no_benchmark(self):
        self.aggregate("zero-runs")
        self.assertFalse((self.iteration("zero-runs") / "benchmark.json").exists())
        self.assertFalse((self.iteration("zero-runs") / "benchmark.md").exists())

    def test_reports_paths_searched_and_layout_expected(self):
        out = self.combined(self.aggregate("zero-runs"))
        self.assertIn("Searched:", out)
        self.assertIn(str(self.iteration("zero-runs")), out)
        self.assertIn("eval-<ID>-<descriptive-slug>", out)
        self.assertIn("run-<K>", out)

    def test_names_the_undiscoverable_directory(self):
        out = self.combined(self.aggregate("zero-runs"))
        self.assertIn("csv-totals", out)
        self.assertIn("eval-<ID>-csv-totals", out,
                      "the fix must be spelled out, not just the problem")

    def test_preflight_projects_the_same_failure(self):
        proc = self.script("preflight", self.root / "zero-runs")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("aggregates to nothing", self.combined(proc))


# --------------------------------------------------------------------------
# C5: comparison direction
# --------------------------------------------------------------------------

class TestComparisonDirection(WorkspaceCase):
    """`old_skill` sorts before `with_skill`; role must beat sorted()."""

    def test_delta_is_not_inverted_for_old_skill_baseline(self):
        proc = self.aggregate("inverted-delta")
        self.assertEqual(proc.returncode, 0, self.combined(proc))

        data = self.benchmark("inverted-delta")
        self.assertEqual(data["primary"], "with_skill")
        self.assertEqual(data["baseline"], "old_skill")

        delta = data["run_summary"]["delta"]["pass_rate"]
        self.assertEqual(delta["value"], 0.75,
                         "25% -> 100% is a +0.75 improvement, not -0.75")
        self.assertTrue(delta["better"])

    def test_primary_column_comes_first_in_the_markdown(self):
        self.aggregate("inverted-delta")
        md = self.benchmark_md("inverted-delta")
        header = next(line for line in md.splitlines() if line.startswith("| Metric"))
        self.assertLess(header.index("With Skill"), header.index("Old Skill"))

    def test_polarity_is_declared_and_goodness_is_not_the_sign(self):
        self.aggregate("inverted-delta")
        delta = self.benchmark("inverted-delta")["run_summary"]["delta"]

        self.assertEqual(delta["pass_rate"]["polarity"], "higher_is_better")
        self.assertEqual(delta["time_seconds"]["polarity"], "lower_is_better")
        self.assertEqual(delta["tokens"]["polarity"], "lower_is_better")

        # The skill is slower and costlier: a positive number that is worse.
        self.assertGreater(delta["time_seconds"]["value"], 0)
        self.assertFalse(delta["time_seconds"]["better"])
        self.assertGreater(delta["tokens"]["value"], 0)
        self.assertFalse(delta["tokens"]["better"])

    def test_roles_are_emitted_in_exactly_one_place(self):
        self.aggregate("inverted-delta")
        data = self.benchmark("inverted-delta")
        self.assertNotIn("primary", data["metadata"])
        self.assertNotIn("baseline", data["metadata"])

    def test_polarity_is_emitted_in_exactly_one_place(self):
        self.aggregate("inverted-delta")
        data = self.benchmark("inverted-delta")
        self.assertNotIn("metric_polarity", data,
                         "a top-level map would have to agree with the "
                         "per-delta fields, and nothing would check that")
        for entry in data["run_summary"]["delta"].values():
            self.assertIn(entry["polarity"],
                          ("higher_is_better", "lower_is_better"))

    def test_roles_can_be_overridden(self):
        proc = self.aggregate("inverted-delta",
                              "--primary", "old_skill", "--baseline", "with_skill")
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        data = self.benchmark("inverted-delta")
        self.assertEqual(data["primary"], "old_skill")
        self.assertEqual(data["run_summary"]["delta"]["pass_rate"]["value"], -0.75)

    def test_unresolvable_roles_refuse_rather_than_guess(self):
        primary, baseline, error = resolve_roles(
            ["config_a", "config_b"], None, None)
        self.assertIsNone(primary)
        self.assertIsNone(baseline)
        self.assertIn("--primary", error)

    def test_role_inference_by_name(self):
        self.assertEqual(
            resolve_roles(["old_skill", "with_skill"], None, None)[:2],
            ("with_skill", "old_skill"))
        self.assertEqual(
            resolve_roles(["without_skill", "with_skill"], None, None)[:2],
            ("with_skill", "without_skill"))
        self.assertEqual(
            resolve_roles(["with_skill"], None, None)[:2],
            ("with_skill", None))


# --------------------------------------------------------------------------
# C4: absent data is absent, never zero
# --------------------------------------------------------------------------

class TestAbsentNotZero(WorkspaceCase):

    def test_unmeasured_configuration_is_null_not_zero(self):
        proc = self.aggregate("missing-timing")
        self.assertEqual(proc.returncode, 0, self.combined(proc))

        summary = self.benchmark("missing-timing")["run_summary"]
        self.assertIsNone(summary["without_skill"]["time_seconds"])
        self.assertIsNone(summary["without_skill"]["tokens"])
        self.assertIsNotNone(summary["without_skill"]["pass_rate"],
                             "grading was present; only timing was not")

    def test_unmeasured_runs_are_excluded_from_the_mean_not_zeroed(self):
        self.aggregate("missing-timing")
        stats = self.benchmark("missing-timing")["run_summary"]["with_skill"]["tokens"]
        self.assertEqual(stats["n"], 1)
        self.assertEqual(stats["missing"], 1)
        self.assertEqual(stats["mean"], 80000,
                         "averaging in a 0 would have halved this")

    def test_delta_against_an_unmeasured_baseline_is_absent(self):
        self.aggregate("missing-timing")
        delta = self.benchmark("missing-timing")["run_summary"]["delta"]
        self.assertIsNone(delta["tokens"]["value"])
        self.assertEqual(delta["tokens"]["formatted"], "—")
        self.assertIsNone(delta["time_seconds"]["value"])

    def test_run_level_values_are_null(self):
        self.aggregate("missing-timing")
        runs = self.benchmark("missing-timing")["runs"]
        untimed = [r for r in runs if r["configuration"] == "without_skill"]
        self.assertTrue(untimed)
        for run in untimed:
            self.assertIsNone(run["result"]["tokens"])
            self.assertIsNone(run["result"]["time_seconds"])

    def test_markdown_renders_em_dash_never_zero(self):
        self.aggregate("missing-timing")
        md = self.benchmark_md("missing-timing")
        self.assertIn("—", md)
        self.assertNotIn("0.0s ± 0.0s", md,
                         "an unmeasured duration must not read as instantaneous")
        self.assertNotIn("| 0 ± 0 ", md)

    def test_permanently_unmeasurable_keys_are_absent_not_null(self):
        """Nothing produces these, so the requirement is gone.

        `output_chars`, `tool_calls`, and `errors` were sourced from
        `execution_metrics`, fed by a `metrics.json` no agent ever wrote. A
        column that is null on every path forever reads as "measured, and the
        answer was nothing" - the ambiguity this rewrite exists to remove.
        """
        self.aggregate("canonical")
        result = self.benchmark("canonical")["runs"][0]["result"]
        for key in ("output_chars", "tool_calls", "errors"):
            self.assertNotIn(key, result)
        self.assertEqual(sorted(result),
                         ["abstained", "failed", "pass_rate", "passed",
                          "time_seconds", "tokens", "total"])

    def test_tokens_come_from_timing_json(self):
        self.aggregate("canonical")
        result = self.benchmark("canonical")["runs"][0]["result"]
        self.assertEqual(result["tokens"], 80000,
                         "tokens come from timing.json unconditionally")

    def test_timing_json_wins_over_a_grader_written_timing_block(self):
        """research/15 F4 - the gate that discarded every real token count."""
        proc = self.aggregate("grader-timing-block")
        self.assertEqual(proc.returncode, 0, self.combined(proc))

        result = next(r["result"] for r in self.benchmark("grader-timing-block")["runs"]
                      if r["configuration"] == "with_skill")
        self.assertEqual(result["tokens"], 84852,
                         "the character count 12450 must not appear here")
        self.assertEqual(result["time_seconds"], 23.332,
                         "191.0 is executor+grader from the grading block")
        self.assertNotIn(12450, result.values(),
                         "output_chars must not leak into any emitted field")

    def test_execution_metrics_is_read_by_nothing(self):
        """The fixture's grading.json carries a full execution_metrics block."""
        self.aggregate("grader-timing-block")
        for run in self.benchmark("grader-timing-block")["runs"]:
            self.assertEqual(sorted(run["result"]),
                             ["abstained", "failed", "pass_rate", "passed",
                              "time_seconds", "tokens", "total"])

    def test_grader_written_timing_block_is_warned_about_not_failed(self):
        proc = self.script("validate_grading",
                           self.iteration("grader-timing-block"))
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertIn("carries a 'timing' block", self.combined(proc))

    def test_benchmark_md_is_utf8(self):
        self.aggregate("canonical")
        path = self.iteration("canonical") / "benchmark.md"
        text = path.read_bytes().decode("utf-8")  # raises if written in cp1252
        self.assertIn("±", text)


# --------------------------------------------------------------------------
# Sample size
# --------------------------------------------------------------------------

class TestSampleSize(WorkspaceCase):

    def test_single_run_reports_no_stddev(self):
        proc = self.aggregate("single-run")
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        summary = self.benchmark("single-run")["run_summary"]
        for config in ("with_skill", "without_skill"):
            stats = summary[config]["pass_rate"]
            self.assertEqual(stats["n"], 1)
            self.assertIsNone(stats["stddev"],
                              "one sample has no sample standard deviation")

    def test_runs_per_configuration_is_measured_not_hardcoded(self):
        self.aggregate("single-run")
        metadata = self.benchmark("single-run")["metadata"]
        self.assertEqual(metadata["runs_per_configuration"], 1)
        self.assertEqual(metadata["runs_per_configuration_by_config"],
                         {"with_skill": 1, "without_skill": 1})

        self.aggregate("canonical")
        self.assertEqual(
            self.benchmark("canonical")["metadata"]["runs_per_configuration"], 2)

    def test_uneven_run_counts_report_no_single_number(self):
        self.aggregate("missing-timing")
        metadata = self.benchmark("missing-timing")["metadata"]
        self.assertIsNone(metadata["runs_per_configuration"])
        self.assertEqual(metadata["runs_per_configuration_by_config"],
                         {"with_skill": 2, "without_skill": 1})

    def test_markdown_shows_n_and_an_absent_stddev(self):
        self.aggregate("single-run")
        md = self.benchmark_md("single-run")
        self.assertIn("(n=1)", md)
        self.assertIn("± —", md)


# --------------------------------------------------------------------------
# C3 schema enforcement and exclusion
# --------------------------------------------------------------------------

class TestSchemaEnforcement(WorkspaceCase):

    def test_pass_rate_string_is_rejected(self):
        proc = self.script("validate_grading",
                           self.iteration("pass-rate-string"))
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        out = self.combined(proc)
        self.assertIn("pass_rate", out)
        self.assertIn("str", out)
        self.assertIn("100%", out)

    def test_bad_grading_is_named_counted_and_excluded(self):
        """The excluded run is named, and it does not quietly move the delta.

        Exit was 0 here until the pairing check reached run level. The
        exclusion was listed, which is necessary and was treated as
        sufficient - but the delta was silently recomputed over `with_skill`'s
        one surviving run against `without_skill`'s untouched run, so an
        excluded run changed the answer instead of invalidating it.
        """
        proc = self.aggregate("pass-rate-string")
        self.assertEqual(proc.returncode, 1, self.combined(proc))

        data = self.benchmark("pass-rate-string")
        schema = [e for e in data["exclusions"] if "run-1" in e["path"]]
        self.assertEqual(len(schema), 1)
        self.assertTrue(schema[0]["errors"])
        self.assertIn("C12:schema_invalid=error", schema[0]["reason"])

        # The good sibling run still counts toward with_skill's own column...
        self.assertEqual(data["run_summary"]["with_skill"]["pass_rate"]["n"], 1)
        # ...and not toward a delta whose two sides no longer match.
        self.assertIsNone(data["run_summary"]["delta"]["pass_rate"]["value"])
        self.assertTrue(any("C12:unpaired_evals=error" in e["reason"]
                            for e in data["exclusions"]))

    def test_exclusion_is_visible_in_the_rendered_benchmark(self):
        self.aggregate("pass-rate-string")
        md = self.benchmark_md("pass-rate-string")
        self.assertIn("## Excluded from aggregation", md)
        self.assertIn("run-1", md)

    def test_summary_failed_is_cross_checked(self):
        """research/11 F13.2 - the check that was missing entirely."""
        proc = self.script("validate_grading", self.iteration("summary-failed"))
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        self.assertIn('summary.failed is 0 but 2 expectation(s) have verdict="fail"',
                      self.combined(proc))

    def test_passed_plus_failed_must_equal_total(self):
        errors, _ = validate_grading_file(
            self.iteration("summary-failed")
            / "eval-0-counts-rows" / "with_skill" / "run-1" / "grading.json")
        self.assertTrue(any("but total is 3" in e for e in errors))

    def test_configuration_with_no_usable_runs_is_absent_and_fatal(self):
        proc = self.aggregate("summary-failed")
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        self.assertIn("no usable runs for: with_skill", self.combined(proc))

        summary = self.benchmark("summary-failed")["run_summary"]
        self.assertIsNone(summary["with_skill"]["pass_rate"],
                          "an unusable configuration is unknown, not 0%")
        self.assertEqual(summary["with_skill"]["runs"], 0)
        self.assertIsNone(summary["delta"]["pass_rate"]["value"])

    def test_canonical_workspace_validates_clean(self):
        proc = self.script("validate_grading", self.iteration("canonical"))
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertIn("All 4 grading file(s) valid.", self.combined(proc))


# --------------------------------------------------------------------------
# C1: placement
# --------------------------------------------------------------------------

class TestPlacement(WorkspaceCase):

    def test_grading_the_aggregator_cannot_reach_is_an_error(self):
        proc = self.script("validate_grading",
                           self.iteration("unreachable-grading"))
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        out = self.combined(proc)
        self.assertIn("placement:", out)
        self.assertIn("found:", out)
        self.assertIn("expected:", out)
        self.assertIn("<config>", out)
        self.assertIn("run-<K>", out)

    def test_legacy_flat_placement_warns_but_does_not_fail(self):
        proc = self.script("validate_grading", self.iteration("repro-flat"))
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        out = self.combined(proc)
        self.assertIn("legacy flat layout", out)
        self.assertIn("legacy-flat", out)

    def test_aggregation_names_a_stray_eval_root_grading(self):
        """Undiscoverable grading is an error, everywhere.

        This used to be a layout *warning* at exit 0 in the aggregator while
        `validate_grading` failed the identical tree - one condition, two
        verdicts. It is now an exclusion of error severity in both, and
        preflight (which said nothing at all about it) reports it too.
        """
        proc = self.aggregate("unreachable-grading")
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        out = self.combined(proc)
        self.assertIn("sits at the eval-directory root", out)
        exclusions = self.benchmark("unreachable-grading")["exclusions"]
        self.assertTrue(
            any("eval-directory root" in e["reason"] for e in exclusions),
            "invisible is worse than excluded")
        self.assertTrue(
            any("C12:undiscoverable_grading=error" in e["reason"]
                for e in exclusions))

    def test_classifier_recognises_the_three_shapes(self):
        root = self.iteration("canonical")
        canonical = (root / "eval-0-handles-empty-csv" / "with_skill"
                     / "run-1" / "grading.json")
        self.assertEqual(classify_grading_path(canonical, root)["kind"],
                         "canonical")

        flat_root = self.iteration("repro-flat")
        flat = flat_root / "eval-0" / "with_skill" / "grading.json"
        self.assertEqual(classify_grading_path(flat, flat_root)["kind"],
                         "legacy_flat")

        stray = root / "eval-0-handles-empty-csv" / "grading.json"
        self.assertEqual(classify_grading_path(stray, root)["kind"],
                         "unreachable")


# --------------------------------------------------------------------------
# Partially populated workspaces
# --------------------------------------------------------------------------

class TestMixedMetadata(WorkspaceCase):
    """One eval directory with eval_metadata.json and one without."""

    def test_does_not_crash(self):
        proc = self.aggregate("mixed-metadata")
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertNotIn("Traceback", self.combined(proc))

    def test_missing_metadata_is_named(self):
        out = self.combined(self.aggregate("mixed-metadata"))
        self.assertIn("eval_metadata.json is missing", out)
        self.assertIn("eval-1-beta-case", out)

    def test_eval_ids_resolve_from_the_directory_name(self):
        self.aggregate("mixed-metadata")
        data = self.benchmark("mixed-metadata")
        self.assertEqual(data["metadata"]["evals_run"], [0, 1])
        self.assertEqual({r["eval_id"] for r in data["runs"]}, {0, 1})

    def test_eval_name_is_carried_when_present_and_null_when_not(self):
        self.aggregate("mixed-metadata")
        names = {r["eval_id"]: r["eval_name"] for r in self.benchmark("mixed-metadata")["runs"]}
        self.assertEqual(names[0], "alpha-case")
        self.assertIsNone(names[1], "an unknown name is null, not 'Eval 1'")

    def test_preflight_flags_the_missing_metadata(self):
        proc = self.script("preflight", self.root / "mixed-metadata")
        self.assertEqual(proc.returncode, 1)
        out = self.combined(proc)
        self.assertIn("no eval_metadata.json", out)
        self.assertIn("eval-1-beta-case", out)


# --------------------------------------------------------------------------
# Statistics - the arithmetic that was verified correct and must stay so
# --------------------------------------------------------------------------

class TestStatistics(unittest.TestCase):

    def test_mean_and_sample_stddev_preserved(self):
        stats = calculate_stats([1.0, 0.75])
        self.assertEqual(stats["mean"], 0.875)
        self.assertEqual(stats["stddev"], 0.1768)  # n-1, not n (0.125)
        self.assertEqual(stats["min"], 0.75)
        self.assertEqual(stats["max"], 1.0)
        self.assertEqual(stats["n"], 2)

    def test_three_sample_stddev_matches_hand_computation(self):
        stats = calculate_stats([1.0, 0.75, 1.0])
        self.assertEqual(stats["mean"], 0.9167)
        self.assertEqual(stats["stddev"], 0.1443)  # n form would be 0.1179

    def test_none_is_excluded_not_zeroed(self):
        stats = calculate_stats([10.0, None, 20.0])
        self.assertEqual(stats["mean"], 15.0)
        self.assertEqual(stats["n"], 2)
        self.assertEqual(stats["missing"], 1)

    def test_all_unmeasured_returns_none(self):
        self.assertIsNone(calculate_stats([None, None]))
        self.assertIsNone(calculate_stats([]))

    def test_single_sample_has_no_stddev(self):
        stats = calculate_stats([0.5])
        self.assertEqual(stats["mean"], 0.5)
        self.assertIsNone(stats["stddev"])

    def test_every_metric_declares_a_polarity(self):
        self.assertEqual(METRIC_POLARITY["pass_rate"], "higher_is_better")
        self.assertEqual(METRIC_POLARITY["time_seconds"], "lower_is_better")
        self.assertEqual(METRIC_POLARITY["tokens"], "lower_is_better")


# --------------------------------------------------------------------------
# C6: CLI surface
# --------------------------------------------------------------------------

class TestCliSurface(WorkspaceCase):

    def test_validate_grading_json_goes_to_stdout_alone(self):
        proc = self.script("validate_grading",
                           self.iteration("summary-failed"), "--json")
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertGreater(payload["counts"]["errors"], 0)
        self.assertTrue(proc.stderr.strip(),
                        "human-readable progress belongs on stderr")

    def test_preflight_json_goes_to_stdout_alone(self):
        proc = self.script("preflight", self.root / "repro-flat", "--json")
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertTrue(any(f["expected"] for f in payload["findings"]),
                        "every failure names the path expected")

    def test_preflight_passes_a_conforming_workspace(self):
        proc = self.script("preflight", self.root / "canonical")
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertIn("conforms to the expected layout, naming and fields",
                      self.combined(proc))

    def test_preflight_accepts_an_iteration_directory_directly(self):
        proc = self.script("preflight", self.iteration("canonical"))
        self.assertEqual(proc.returncode, 0, self.combined(proc))

    def test_aggregate_keeps_stdout_clean(self):
        proc = self.aggregate("canonical")
        self.assertEqual(proc.stdout, "",
                         "this script's product is files; progress is stderr")

    def test_benchmark_json_key_tree_is_pinned(self):
        """The schemas document diffs this exactly; it must not drift silently."""
        self.aggregate("canonical")
        data = self.benchmark("canonical")
        self.assertEqual(sorted(data), [
            "baseline", "exclusions", "layout_warnings", "metadata", "notes",
            "primary", "run_summary", "runs",
        ])
        self.assertEqual(sorted(data["metadata"]), [
            "analyzer_model", "evals_run", "executor_model",
            "runs_per_configuration", "runs_per_configuration_by_config",
            "skill_name", "skill_path", "timestamp",
        ])
        self.assertEqual(sorted(data["runs"][0]), [
            "configuration", "eval_id", "eval_name", "expectations", "notes",
            "result", "run_number",
        ])
        self.assertEqual(sorted(data["run_summary"]["delta"]["pass_rate"]),
                         ["better", "formatted", "polarity", "value"])
        self.assertEqual(sorted(data["run_summary"]["with_skill"]),
                         ["abstention", "pass_rate", "runs", "time_seconds",
                          "tokens"])
        self.assertEqual(sorted(data["run_summary"]["with_skill"]["pass_rate"]),
                         ["max", "mean", "min", "missing", "n", "stddev"])
        self.assertEqual(sorted(data["run_summary"]["with_skill"]["abstention"]),
                         ["abstained", "graded", "rate", "reasons", "runs",
                          "runs_without_pass_rate", "total"])

    def test_missing_directory_exits_non_zero(self):
        proc = self.script("aggregate_benchmark", self.root / "nope",
                           "--skill-name", "demo")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not found", self.combined(proc))


# --------------------------------------------------------------------------
# Verdicts are ternary
# --------------------------------------------------------------------------

class TestTernaryVerdicts(unittest.TestCase):
    """The schema half: the enum, the conditional reason, and the arithmetic."""

    def errors_for(self, payload) -> list:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "grading.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors, _warnings = validate_grading_file(path)
        return errors

    @staticmethod
    def grading(expectations, **summary_overrides):
        counts = {"pass": 0, "fail": 0, "abstain": 0}
        for exp in expectations:
            if exp.get("verdict") in counts:
                counts[exp["verdict"]] += 1
        graded = counts["pass"] + counts["fail"]
        summary = {
            "passed": counts["pass"], "failed": counts["fail"],
            "abstained": counts["abstain"], "total": len(expectations),
            "pass_rate": (counts["pass"] / graded) if graded else None,
        }
        summary.update(summary_overrides)
        return {"expectations": expectations, "summary": summary}

    P = {"text": "a", "verdict": "pass", "abstainReason": None, "evidence": "e"}
    F = {"text": "b", "verdict": "fail", "abstainReason": None, "evidence": "e"}
    A = {"text": "c", "verdict": "abstain", "abstainReason": "evidence",
         "evidence": "e"}

    # -- the enum ---------------------------------------------------------

    def test_all_three_verdicts_are_accepted(self):
        self.assertEqual(self.errors_for(self.grading([self.P, self.F, self.A])), [])

    def test_a_fourth_verdict_is_rejected(self):
        errors = self.errors_for(self.grading(
            [dict(self.P, verdict="partial")]))
        self.assertTrue(any("not one of" in e for e in errors), errors)

    def test_a_boolean_verdict_is_rejected_and_named_as_the_old_shape(self):
        errors = self.errors_for(self.grading([dict(self.P, verdict=True)]))
        self.assertTrue(any("previous contract's shape" in e for e in errors),
                        errors)

    def test_a_stringified_boolean_is_pointed_at_the_right_member(self):
        errors = self.errors_for(self.grading([dict(self.P, verdict="false")]))
        joined = "\n".join(errors)
        self.assertIn('did you mean "fail"', joined)
        # And told that "could not tell" is no longer a fail. This sentence is
        # the entire contract change; a message that only fixed the spelling
        # would preserve the defect in the next run.
        self.assertIn("that is \"abstain\", not \"fail\"", joined)

    # -- abstainReason is conditional --------------------------------------

    def test_an_abstention_without_a_reason_is_an_error(self):
        errors = self.errors_for(self.grading(
            [{"text": "c", "verdict": "abstain", "evidence": "e"}]))
        self.assertTrue(any("required when the verdict is 'abstain'" in e
                            for e in errors), errors)

    def test_a_null_reason_on_an_abstention_is_an_error(self):
        errors = self.errors_for(self.grading([dict(self.A, abstainReason=None)]))
        self.assertTrue(any("abstainReason" in e for e in errors), errors)

    def test_an_unrecognised_reason_is_an_error(self):
        errors = self.errors_for(self.grading([dict(self.A, abstainReason="busy")]))
        self.assertTrue(any("not one of 'jurisdiction', 'evidence'" in e
                            for e in errors), errors)

    def test_a_reason_beside_a_pass_or_a_fail_is_an_error(self):
        for verdict in ("pass", "fail"):
            with self.subTest(verdict=verdict):
                errors = self.errors_for(self.grading(
                    [{"text": "a", "verdict": verdict,
                      "abstainReason": "evidence", "evidence": "e"}]))
                self.assertTrue(
                    any("required when and only when" in e for e in errors),
                    errors)

    def test_an_omitted_reason_on_a_pass_is_fine(self):
        self.assertEqual(
            self.errors_for(self.grading(
                [{"text": "a", "verdict": "pass", "evidence": "e"}])), [])

    def test_both_typed_reasons_are_accepted(self):
        for reason in ("jurisdiction", "evidence"):
            with self.subTest(reason=reason):
                self.assertEqual(
                    self.errors_for(self.grading(
                        [dict(self.A, abstainReason=reason)])), [])

    # -- the arithmetic ----------------------------------------------------

    def test_passed_plus_failed_plus_abstained_must_equal_total(self):
        errors = self.errors_for(self.grading([self.P, self.F, self.A], total=2))
        self.assertTrue(any("but total is 2" in e for e in errors), errors)

    def test_abstained_is_cross_checked_against_the_verdicts(self):
        errors = self.errors_for(self.grading([self.P, self.A],
                                              abstained=0, total=1))
        self.assertTrue(
            any('summary.abstained is 0 but 1 expectation(s) have verdict="abstain"'
                in e for e in errors), errors)

    def test_abstained_is_a_required_field(self):
        payload = self.grading([self.P])
        del payload["summary"]["abstained"]
        errors = self.errors_for(payload)
        self.assertTrue(any("missing required field 'abstained'" in e
                            for e in errors), errors)

    def test_the_denominator_excludes_abstentions(self):
        # 1 pass, 1 fail, 9 abstentions is 50%, not 1/11.
        payload = self.grading([self.P, self.F] + [dict(self.A)] * 9)
        self.assertEqual(payload["summary"]["pass_rate"], 0.5)
        self.assertEqual(self.errors_for(payload), [])

    def test_using_passed_over_total_is_rejected_and_explained(self):
        payload = self.grading([self.P, self.F, self.A], pass_rate=1 / 3)
        errors = self.errors_for(payload)
        joined = "\n".join(errors)
        self.assertIn("this is passed/total", joined)
        self.assertIn("abstentions leave the denominator", joined)

    # -- the null rate -----------------------------------------------------

    def test_an_all_abstain_run_must_report_a_null_rate(self):
        self.assertEqual(self.errors_for(self.grading([self.A, self.A])), [])

    def test_zero_point_zero_over_an_empty_denominator_is_rejected(self):
        errors = self.errors_for(self.grading([self.A, self.A], pass_rate=0.0))
        self.assertTrue(any("nothing was graded" in e for e in errors), errors)

    def test_a_null_rate_over_a_nonempty_denominator_is_rejected(self):
        errors = self.errors_for(self.grading([self.P, self.A], pass_rate=None))
        self.assertTrue(any("pass_rate is null but 1 expectation(s) were graded"
                            in e for e in errors), errors)

    def test_compute_pass_rate_returns_none_not_zero(self):
        """The one implementation every component shares."""
        self.assertIsNone(compute_pass_rate(0, 0))
        self.assertEqual(compute_pass_rate(1, 1), 0.5)
        self.assertEqual(compute_pass_rate(2, 0), 1.0)

    # -- the previous contract ---------------------------------------------

    def test_a_boolean_passed_is_diagnosed_as_the_previous_contract(self):
        errors = self.errors_for({
            "expectations": [{"text": "a", "passed": True, "evidence": "e"}],
            "summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0},
        })
        joined = "\n".join(errors)
        # Not a type error. The reader's file is not malformed, it is last
        # version's format, and what they need is the mapping.
        self.assertIn("PREVIOUS grading contract, not a malformed file", joined)
        self.assertIn('{"passed": true}', joined)
        self.assertIn('"verdict": "pass"', joined)
        self.assertIn('"abstainReason": "evidence"', joined)
        self.assertIn('"abstainReason": "jurisdiction"', joined)
        self.assertIn("add `abstained`", joined)

    def test_the_migration_note_warns_against_mapping_every_false_to_fail(self):
        errors = self.errors_for({
            "expectations": [{"text": "a", "passed": False, "evidence": "e"}],
            "summary": {"passed": 0, "failed": 1, "total": 1, "pass_rate": 0.0},
        })
        joined = "\n".join(errors)
        self.assertIn("but only where the evidence actually showed the "
                      "expectation false", joined)
        self.assertIn("could not tell", joined)

    def test_the_migration_note_is_printed_once_not_per_entry(self):
        errors = self.errors_for({
            "expectations": [{"text": "e%d" % i, "passed": True,
                              "evidence": "e"} for i in range(40)],
            "summary": {"passed": 40, "failed": 0, "total": 40,
                        "pass_rate": 1.0},
        })
        joined = "\n".join(errors)
        self.assertEqual(joined.count("PREVIOUS grading contract"), 1,
                         "40 copies of the migration is not a diagnosis")

    def test_keeping_passed_alongside_verdict_is_an_error(self):
        errors = self.errors_for(self.grading([dict(self.P, passed=True)]))
        self.assertTrue(any("REMOVED 'passed'" in e for e in errors), errors)

    def test_a_verdict_alias_is_told_that_renaming_is_not_enough(self):
        for alias in ("met", "result", "success"):
            with self.subTest(alias=alias):
                payload = self.grading(
                    [{"text": "a", alias: True, "evidence": "e"}],
                    passed=0, failed=0, abstained=0, total=1, pass_rate=None)
                errors = self.errors_for(payload)
                self.assertTrue(
                    any("Renaming is not the whole fix" in e for e in errors),
                    errors)


class TestAbstentionReachesTheBenchmark(WorkspaceCase):
    """Ternary verdicts' consequence for the artifact carrying the number."""

    def test_an_all_abstain_workspace_produces_null_everywhere_a_rate_appears(self):
        proc = self.aggregate("all-abstained")
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        data = self.benchmark("all-abstained")

        for run in data["runs"]:
            self.assertIsNone(run["result"]["pass_rate"],
                              "a run nothing was ruled on has no pass rate")
            self.assertEqual(run["result"]["passed"], 0)
            self.assertEqual(run["result"]["failed"], 0)
            self.assertGreater(run["result"]["abstained"], 0)

        for config in ("with_skill", "without_skill"):
            self.assertIsNone(data["run_summary"][config]["pass_rate"],
                              "a configuration with no rate must be null, not 0")

        delta = data["run_summary"]["delta"]["pass_rate"]
        self.assertIsNone(delta["value"])
        self.assertIsNone(delta["better"])
        self.assertEqual(delta["formatted"], "—")

    def test_the_rendered_benchmark_shows_no_zero_pass_rate(self):
        """C15: assert on the rendered artifact, not on the JSON that fed it."""
        self.aggregate("all-abstained")
        md = self.benchmark_md("all-abstained")
        summary = md[md.index("| Metric |"):md.index("## Abstentions")]
        self.assertIn("—", summary)
        self.assertNotIn("0%", summary,
                         "a percentage over nothing reached the table:\n" + summary)

    def test_abstention_counts_are_emitted_beside_every_rate(self):
        self.aggregate("all-abstained")
        data = self.benchmark("all-abstained")
        block = data["run_summary"]["with_skill"]["abstention"]
        self.assertEqual(block["abstained"], 5)
        self.assertEqual(block["graded"], 0)
        self.assertEqual(block["total"], 5)
        self.assertEqual(block["rate"], 1.0)
        # Two reasons, and they are counted separately: one says fix the eval
        # set, the other says fix the run.
        self.assertEqual(block["reasons"]["jurisdiction"], 2)
        self.assertEqual(block["reasons"]["evidence"], 3)
        self.assertEqual(block["reasons"]["untyped"], 0)
        self.assertEqual(block["runs_without_pass_rate"], 2)

    def test_a_thin_pass_rate_carries_its_abstentions_into_the_markdown(self):
        """100% over 2 ruled-on checks must not read like 100% over 11."""
        self.aggregate("partly-abstained")
        md = self.benchmark_md("partly-abstained")
        self.assertIn("## Abstentions", md)
        self.assertIn("9 of 11 checks (82%); 2 graded", md)
        self.assertIn("0 of 11 checks (0%); 11 graded", md)
        # And per eval, beside the rate itself.
        self.assertIn("| 100% | 9/11 | 100% | 0/11 |", md)

    def test_abstention_is_not_a_delta_metric(self):
        """It has no honest polarity, so it declares none."""
        self.assertNotIn("abstention", METRIC_POLARITY)
        self.assertNotIn("abstained", METRIC_POLARITY)
        self.aggregate("partly-abstained")
        delta = self.benchmark("partly-abstained")["run_summary"]["delta"]
        self.assertNotIn("abstention", delta)

    def test_the_markdown_states_the_two_sided_risk(self):
        self.aggregate("partly-abstained")
        md = self.benchmark_md("partly-abstained")
        self.assertIn("no delta on this row and no polarity", md)
        self.assertIn("abstains freely", md)
        self.assertIn("never abstains", md)

    def test_an_eval_both_sides_ran_with_no_rate_is_not_called_unpaired(self):
        """`no` would say the baseline never attempted it. It did."""
        self.aggregate("all-abstained")
        md = self.benchmark_md("all-abstained")
        rows = [l for l in md.splitlines() if l.startswith("| 0 |")]
        self.assertTrue(rows, md)
        self.assertIn("no rate", rows[0])

    def test_the_console_summary_never_says_zero_percent(self):
        proc = self.aggregate("all-abstained")
        out = self.combined(proc)
        self.assertIn("no pass rate", out)
        self.assertIn("This is not 0%", out)
        self.assertNotIn("0.0% pass rate", out)

    def test_a_previous_contract_workspace_is_excluded_with_the_migration(self):
        proc = self.aggregate("previous-contract")
        # Every grading failed schema validation, so nothing survives.
        self.assertNotEqual(proc.returncode, 0, self.combined(proc))
        out = self.combined(proc)
        self.assertIn("PREVIOUS grading contract", out)


class TestEveryReasonIsDefinedWhereItIsCounted(WorkspaceCase):
    """The legend and the counts are one reason set.

    `_fmt_abstention` has always printed whatever the `reasons` block held,
    and the `## Abstentions` legend under it was a hand-written sentence
    naming two. When the contract's enum went to three, `underspecified`
    appeared in the Detail column with nothing underneath defining it - a
    count with no meaning attached, in the one section of the file whose
    entire job is attaching meanings to counts. Worse, it was the one reason
    whose repair belongs to the person reading the benchmark.

    Both halves now walk `validate_grading.ABSTAIN_REASONS`, so the tests below
    are keyed off the enum too: adding a fourth reason makes them require a
    fourth legend entry without anyone editing this file.
    """

    def test_the_legend_defines_every_reason_the_counts_can_contain(self):
        self.aggregate("every-reason")
        md = self.benchmark_md("every-reason")
        legend = md[md.index("## Abstentions"):md.index("## By eval")]
        for reason in ABSTAIN_REASONS:
            self.assertIn(
                f"- `{reason}`", legend,
                f"`{reason}` is in the enum and can be counted in the Detail "
                f"column, but the legend does not define it:\n" + legend)
            self.assertIn(ABSTAIN_REASON_MEANINGS[reason], legend, reason)

    def test_the_legend_names_the_repair_and_therefore_who_acts(self):
        """The reason a third reason earns a slot at all.

        `evidence` is fixed by supplying an artifact and `jurisdiction` by
        reassigning the judge; `underspecified` is fixed by rewriting the
        sentence, and only the eval's author can do that. A legend that
        defines the three without saying which is which sends the reader to
        change their panel when they need to change their assertion.
        """
        self.aggregate("every-reason")
        legend = self.benchmark_md("every-reason")
        for reason in ABSTAIN_REASONS:
            self.assertIn(ABSTAIN_REASON_REPAIRS[reason], legend, reason)
        self.assertIn("rewrite the assertion", ABSTAIN_REASON_REPAIRS["underspecified"])

    def test_every_reason_in_the_enum_has_a_repair(self):
        """The divergence guard on this side of the boundary.

        `_abstention_legend` walks the enum, so a reason with no repair here is
        still listed with its meaning - it can go unexplained, never missing.
        This is what turns "unexplained" into a failure rather than something
        somebody eventually notices.
        """
        self.assertEqual(sorted(ABSTAIN_REASON_REPAIRS), sorted(ABSTAIN_REASONS))

    def test_untyped_is_defined_too_and_is_not_presented_as_a_reason(self):
        """It is the aggregator's bucket, not something a judge can return."""
        self.aggregate("every-reason")
        legend = self.benchmark_md("every-reason")
        self.assertIn("- `untyped`", legend)
        self.assertIn("not a reason the contract defines", legend)

    def test_the_counts_split_by_reason_and_the_two_columns_differ(self):
        self.aggregate("every-reason")
        data = self.benchmark("every-reason")
        primary = data["run_summary"]["with_skill"]["abstention"]
        baseline = data["run_summary"]["without_skill"]["abstention"]
        self.assertEqual(primary["reasons"],
                         {"jurisdiction": 1, "evidence": 1,
                          "underspecified": 1, "untyped": 0})
        self.assertEqual(baseline["reasons"],
                         {"jurisdiction": 0, "evidence": 1,
                          "underspecified": 2, "untyped": 0})
        self.assertEqual((primary["abstained"], primary["graded"],
                          primary["total"]), (3, 3, 6))

        # And the same split reaches the rendered file, per configuration. A
        # Detail column that printed one column's reasons for both would agree
        # with itself and with nothing else.
        md = self.benchmark_md("every-reason")
        rows = {line.split("|")[1].strip(): line
                for line in md.splitlines() if line.startswith("| With Skill |")
                or line.startswith("| Without Skill |")}
        self.assertIn("1 jurisdiction, 1 evidence, 1 underspecified",
                      rows["With Skill"])
        self.assertIn("1 evidence, 2 underspecified", rows["Without Skill"])
        self.assertNotIn("jurisdiction", rows["Without Skill"])

    def test_a_reason_outside_the_enum_is_excluded_and_named_not_bucketed(self):
        """`untyped` stays 0 in a workspace that passed validation.

        The legend says so, so something has to hold it true. An unrecognized
        reason quietly counted under `untyped` in a surviving column would
        report a kind of ruling no contract defines, and would do it in the
        column a reader compares.
        """
        proc = self.aggregate("unknown-reason")
        out = self.combined(proc)
        self.assertIn("'busy' is not one of", out)
        self.assertIn("schema_invalid", out)

        data = self.benchmark("unknown-reason")
        for config in ("with_skill", "without_skill"):
            block = data["run_summary"][config]["abstention"]
            self.assertEqual(block["reasons"]["untyped"], 0, config)
        excluded = [e["path"] for e in data["exclusions"]]
        self.assertTrue(
            any("eval-1-reason-off-enum" in p for p in excluded),
            excluded)

    def test_the_reason_keys_in_the_json_are_the_enum_plus_untyped(self):
        """The consumer contract: viewer and schemas.md both read these keys."""
        self.aggregate("every-reason")
        data = self.benchmark("every-reason")
        for config in ("with_skill", "without_skill"):
            self.assertEqual(
                list(data["run_summary"][config]["abstention"]["reasons"]),
                list(ABSTAIN_REASONS) + ["untyped"], config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
