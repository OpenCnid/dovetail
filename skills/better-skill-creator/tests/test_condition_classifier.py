#!/usr/bin/env python3
"""One condition, one classification, three components.

Run from the skill root:

    python -m unittest tests.test_condition_classifier -v

Verification pointed `scripts.preflight`, `scripts.validate_grading` and
`scripts.aggregate_benchmark` at one flat-layout workspace and got back
ERROR/exit 1, WARNING/exit 0, and WARNING plus a correct benchmark. Three
parties, one condition, three answers.

`TestThreeComponentsAgree` is the test that exists because that is the property
which keeps failing. It runs all three components against every workspace
fixture, extracts the `C12:<condition>=<severity>` tokens from their output,
and requires the three sets to be identical. Exit codes are deliberately *not*
required to match - components may respond differently to one severity, and
preflight uses that latitude - but a condition classified two ways
fails here, and so does a condition one component sees and another does not.

The rest of the file pins the specific repros from research/V1-verification.md
and research/V7-verification.md that these changes were made to close.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.utils import (  # noqa: E402
    FLAT_AND_RUN_DIRS,
    LEGACY_FLAT_LAYOUT,
    SCHEMA_INVALID,
    SEVERITY_ERROR,
    SEVERITY_OK,
    SEVERITY_WARNING,
    UNDISCOVERABLE_GRADING,
    UNPAIRED_EVALS,
    WORKSPACE_CONDITIONS,
    ZERO_RUNS,
    UnknownWorkspaceCondition,
    classify_workspace_condition,
    condition_line,
    condition_severity,
    condition_tag,
)
from scripts.preflight import IGNORED_DIRS  # noqa: E402
from scripts.validate_grading import (  # noqa: E402
    PRIMARY_ROLE_CONFIGS,
    RECOGNIZED_CONFIGS,
    ROLE_CONFIGS,
    classify_grading_path,
)
from scripts.aggregate_benchmark import pair_evals  # noqa: E402
from tests.make_workspace_fixtures import build  # noqa: E402

#: The token every component prints for every classified condition.
TOKEN = re.compile(r"C12:([a-z_]+)=(ok|warning|error)")


class WorkspaceCase(unittest.TestCase):
    """A private copy of every workspace fixture."""

    root: Path

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="better-skillcreator-c12-")
        cls.root = build(Path(cls._tmp))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

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

    def combined(self, proc) -> str:
        return (proc.stdout or "") + (proc.stderr or "")

    def conditions(self, proc) -> set:
        """The (condition, severity) pairs a component reported."""
        return set(TOKEN.findall(self.combined(proc)))

    def all_three(self, fixture: str) -> dict:
        it = self.iteration(fixture)
        return {
            "preflight": self.script("preflight", it),
            "validate_grading": self.script("validate_grading", it),
            "aggregate_benchmark": self.script(
                "aggregate_benchmark", it, "--skill-name", "demo"),
        }

    def benchmark(self, fixture: str) -> dict:
        path = self.iteration(fixture) / "benchmark.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def benchmark_md(self, fixture: str) -> str:
        return (self.iteration(fixture) / "benchmark.md").read_text(
            encoding="utf-8")


# --------------------------------------------------------------------------
# The severity table itself
# --------------------------------------------------------------------------

class TestSeverityTable(unittest.TestCase):
    """`scripts.utils` holds the severity table, and only it does."""

    def test_every_row_of_the_contract_is_present_with_its_severity(self):
        self.assertEqual(
            {c: s for c, (s, _, _) in WORKSPACE_CONDITIONS.items()},
            {
                "canonical_layout": SEVERITY_OK,
                LEGACY_FLAT_LAYOUT: SEVERITY_WARNING,
                FLAT_AND_RUN_DIRS: SEVERITY_WARNING,
                UNDISCOVERABLE_GRADING: SEVERITY_ERROR,
                ZERO_RUNS: SEVERITY_ERROR,
                SCHEMA_INVALID: SEVERITY_ERROR,
                UNPAIRED_EVALS: SEVERITY_ERROR,
            },
            "the table here and WORKSPACE_CONDITIONS are one table",
        )

    def test_an_unknown_condition_raises_rather_than_defaulting(self):
        """A default would be a component deciding a severity locally."""
        with self.assertRaises(UnknownWorkspaceCondition):
            classify_workspace_condition("layout_looks_a_bit_odd")
        with self.assertRaises(UnknownWorkspaceCondition):
            condition_severity("layout_looks_a_bit_odd")

    def test_the_unknown_condition_message_says_where_to_add_it(self):
        try:
            classify_workspace_condition("not_a_condition")
        except UnknownWorkspaceCondition as exc:
            self.assertIn("WORKSPACE_CONDITIONS in scripts/utils.py", str(exc))
            self.assertIn("must not decide a severity locally", str(exc))

    def test_the_tag_is_one_greppable_token(self):
        self.assertEqual(condition_tag(LEGACY_FLAT_LAYOUT),
                         "C12:legacy_flat_layout=warning")
        self.assertEqual(condition_tag(UNPAIRED_EVALS),
                         "C12:unpaired_evals=error")
        for condition in WORKSPACE_CONDITIONS:
            self.assertRegex(condition_tag(condition), TOKEN)

    def test_the_statement_is_shared_so_three_components_say_one_sentence(self):
        line = condition_line(LEGACY_FLAT_LAYOUT)
        self.assertIn("C12:legacy_flat_layout=warning", line)
        self.assertIn("legacy flat layout", line)
        detailed = condition_line(LEGACY_FLAT_LAYOUT, "and here is the path")
        self.assertTrue(detailed.startswith(line))
        self.assertIn("and here is the path", detailed)


# --------------------------------------------------------------------------
# R1: the property that keeps failing
# --------------------------------------------------------------------------

class TestThreeComponentsAgree(WorkspaceCase):
    """One workspace condition, one classification, reported by all three."""

    FIXTURES = (
        "canonical", "repro-flat", "flat-and-run", "unreachable-grading",
        "zero-runs", "pass-rate-string", "summary-failed", "bad-timing",
        "skill-config", "unpaired-evals", "duplicate-keys", "missing-timing",
        "single-run", "inverted-delta", "mixed-metadata",
        "grader-timing-block", "baseline-only", "primary-only",
    )

    def test_the_three_report_the_same_conditions_on_every_fixture(self):
        for fixture in self.FIXTURES:
            with self.subTest(fixture=fixture):
                procs = self.all_three(fixture)
                reported = {name: self.conditions(proc)
                            for name, proc in procs.items()}
                distinct = {frozenset(v) for v in reported.values()}
                self.assertEqual(
                    len(distinct), 1,
                    "one condition drew more than one verdict:\n" + "\n".join(
                        f"  {name}: {sorted(conds)}"
                        for name, conds in reported.items()),
                )

    def test_no_condition_is_ever_classified_two_ways(self):
        """The weaker property, stated separately so a failure says which."""
        severities: dict = {}
        for fixture in self.FIXTURES:
            for name, proc in self.all_three(fixture).items():
                for condition, severity in self.conditions(proc):
                    previous = severities.setdefault(condition, severity)
                    self.assertEqual(
                        previous, severity,
                        f"{fixture}/{name} called {condition} {severity!r} "
                        f"where another component called it {previous!r}")

    def test_every_reported_severity_matches_the_shared_table(self):
        for fixture in self.FIXTURES:
            for name, proc in self.all_three(fixture).items():
                for condition, severity in self.conditions(proc):
                    with self.subTest(fixture=fixture, component=name):
                        self.assertEqual(condition_severity(condition), severity)

    def test_a_conforming_workspace_produces_no_conditions_at_all(self):
        for name, proc in self.all_three("canonical").items():
            with self.subTest(component=name):
                self.assertEqual(self.conditions(proc), set())
                self.assertEqual(proc.returncode, 0, self.combined(proc))


# --------------------------------------------------------------------------
# R1: the flat layout, and preflight's census
# --------------------------------------------------------------------------

class TestLegacyFlatLayout(WorkspaceCase):
    """One flat-layout workspace: three verdicts became one classification."""

    def test_all_three_call_it_a_warning(self):
        for name, proc in self.all_three("repro-flat").items():
            with self.subTest(component=name):
                self.assertIn((LEGACY_FLAT_LAYOUT, SEVERITY_WARNING),
                              self.conditions(proc))

    def test_the_readers_proceed_and_the_pre_spend_gate_does_not(self):
        procs = self.all_three("repro-flat")
        self.assertEqual(procs["validate_grading"].returncode, 0)
        self.assertEqual(procs["aggregate_benchmark"].returncode, 0)
        self.assertEqual(procs["preflight"].returncode, 1,
                         "the gate still refuses; it just no longer disagrees "
                         "about what the condition is")

    def test_the_finding_is_filed_as_a_warning_not_as_an_error(self):
        out = self.combined(self.script("preflight", self.iteration("repro-flat")))
        line = next(l for l in out.splitlines()
                    if "C12:legacy_flat_layout" in l)
        self.assertIn("warning", line)
        # The level marker sits on the line above the message.
        marker = out.splitlines()[out.splitlines().index(line) - 1]
        self.assertTrue(marker.startswith("WARNING"), marker)

    def test_preflight_says_it_is_refusing_a_warning_not_asserting_an_error(self):
        """`flat-and-run` carries a C12 warning and no error of any kind."""
        proc = self.script("preflight", self.iteration("flat-and-run"))
        out = self.combined(proc)
        self.assertEqual(proc.returncode, 1, out)
        self.assertNotIn("ERROR  ", out)
        self.assertIn("The readers accept these and aggregate correctly", out)
        self.assertIn("warning(s) name a workspace condition", out)

    def test_the_benchmark_is_still_correct(self):
        self.script("aggregate_benchmark", self.iteration("repro-flat"),
                    "--skill-name", "demo")
        data = self.benchmark("repro-flat")
        for config in ("with_skill", "without_skill"):
            self.assertEqual(data["run_summary"][config]["pass_rate"]["mean"],
                             1.0, "refusing to read this would be wrong")

    def test_the_census_no_longer_contradicts_itself(self):
        """"0 run dir(s), 0 graded ... 2 discoverable" cannot all be true."""
        out = self.combined(self.script("preflight", self.iteration("repro-flat")))
        line = next(l for l in out.splitlines() if "discoverable by aggregation" in l)
        numbers = re.search(
            r"(\d+) run dir\(s\), (\d+) graded, (\d+) timed, "
            r"(\d+) discoverable", line)
        self.assertIsNotNone(numbers, line)
        runs, graded, timed, discovered = (int(g) for g in numbers.groups())
        self.assertEqual(runs, 2, line)
        self.assertEqual(graded, 2, line)
        self.assertEqual(timed, 2, line)
        self.assertEqual(discovered, 2, line)

    def test_preflight_validates_the_flattened_files_where_readers_read_them(self):
        """The old early return skipped the very files about to be aggregated."""
        flat = (self.iteration("repro-flat") / "eval-0" / "with_skill"
                / "grading.json")
        payload = json.loads(flat.read_text(encoding="utf-8"))
        payload["summary"]["pass_rate"] = "100%"
        flat.write_text(json.dumps(payload), encoding="utf-8")
        try:
            out = self.combined(
                self.script("preflight", self.iteration("repro-flat")))
            self.assertIn("C12:schema_invalid=error", out)
            self.assertIn("100%", out)
        finally:
            payload["summary"]["pass_rate"] = 1.0
            flat.write_text(json.dumps(payload), encoding="utf-8")


class TestPreflightStillRunsBeforeSpend(WorkspaceCase):
    """Blocking on C12 warnings must not block the state preflight is for.

    `validate_grading` refuses a workspace with no grading.json at all ("No
    grading.json found anywhere"), so preflight is the only check that runs on
    a workspace that has eval prompts and no results yet. If every warning
    blocked, that state - the one every run passes through - would never pass.
    """

    def _prepared(self, root: Path) -> Path:
        ev = root / "iteration-1" / "eval-0-handles-empty-csv"
        ev.mkdir(parents=True)
        (ev / "eval_metadata.json").write_text(json.dumps({
            "eval_id": 0, "eval_name": "handles-empty-csv",
            "prompt": "tidy this export", "assertions": ["a", "b"],
        }), encoding="utf-8")
        return root

    def test_a_prepared_workspace_with_no_results_passes(self):
        with tempfile.TemporaryDirectory() as raw:
            root = self._prepared(Path(raw))
            proc = self.script("preflight", root)
            out = self.combined(proc)
            self.assertEqual(proc.returncode, 0, out)
            self.assertIn("Safe to proceed", out)
            self.assertEqual(TOKEN.findall(out), [],
                             "zero runs before the executor has run is the "
                             "expected state, not a classified condition")

    def test_the_census_says_why_the_counts_are_zero(self):
        with tempfile.TemporaryDirectory() as raw:
            root = self._prepared(Path(raw))
            out = self.combined(self.script("preflight", root))
            self.assertIn("no results yet", out)

    def test_the_json_payload_separates_blocking_from_advisory(self):
        proc = self.script("preflight", self.iteration("flat-and-run"), "--json")
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["counts"]["errors"], 0)
        self.assertEqual(payload["counts"]["blocking_warnings"], 1)
        blocking = [f for f in payload["findings"] if f.get("condition")]
        self.assertEqual([f["condition"] for f in blocking], [FLAT_AND_RUN_DIRS])
        self.assertEqual(blocking[0]["level"], SEVERITY_WARNING)


class TestNoDoubleReporting(WorkspaceCase):
    """R3.1 - preflight replayed exclusions its own walk had already found."""

    def _workspace(self, tmp: Path) -> Path:
        shutil.copytree(self.iteration("canonical"), tmp / "iteration-1")
        return tmp

    def test_a_malformed_run_directory_is_reported_once(self):
        with tempfile.TemporaryDirectory() as raw:
            root = self._workspace(Path(raw))
            config = (root / "iteration-1" / "eval-0-handles-empty-csv"
                      / "with_skill")
            (config / "run-abc").mkdir()
            out = self.combined(self.script("preflight", root))
            self.assertEqual(
                out.count("run-abc` is not `run-<K>"), 1,
                "one condition, one block:\n" + out)

    def test_a_schema_failure_is_reported_once(self):
        with tempfile.TemporaryDirectory() as raw:
            root = self._workspace(Path(raw))
            grading = (root / "iteration-1" / "eval-0-handles-empty-csv"
                       / "with_skill" / "run-1" / "grading.json")
            payload = json.loads(grading.read_text(encoding="utf-8"))
            payload["summary"]["pass_rate"] = "85%"
            grading.write_text(json.dumps(payload), encoding="utf-8")
            out = self.combined(self.script("preflight", root))
            self.assertEqual(
                out.count(
                    "must be a number in [0.0, 1.0] or null, got str ('85%')"), 1,
                "one condition, one block:\n" + out)
            self.assertIn("C12:schema_invalid=error", out)


# --------------------------------------------------------------------------
# R5: timing.json is schema-validated by the aggregator
# --------------------------------------------------------------------------

class TestTimingIsValidated(WorkspaceCase):
    """A negative duration used to render as `-3600.0s | -3610.0 | better`."""

    def setUp(self):
        self.proc = self.script("aggregate_benchmark",
                                self.iteration("bad-timing"),
                                "--skill-name", "demo")

    def test_the_timing_file_is_excluded_and_named(self):
        data = self.benchmark("bad-timing")
        timing = [e for e in data["exclusions"] if e["path"].endswith("timing.json")]
        self.assertEqual(len(timing), 1, data["exclusions"])
        self.assertIn("C12:schema_invalid=error", timing[0]["reason"])
        self.assertTrue(any("must not be negative" in e
                            for e in timing[0]["errors"]))

    def test_the_negative_numbers_reach_no_statistic(self):
        summary = self.benchmark("bad-timing")["run_summary"]
        self.assertIsNone(summary["with_skill"]["time_seconds"])
        self.assertIsNone(summary["with_skill"]["tokens"])
        self.assertIsNone(summary["delta"]["time_seconds"]["value"])
        self.assertIsNone(summary["delta"]["tokens"]["value"])

    def test_nothing_negative_is_endorsed_as_better(self):
        md = self.benchmark_md("bad-timing")
        summary = md.split("## Excluded from aggregation")[0]
        self.assertNotIn("-3600", summary,
                         "the numbers may appear in the exclusion's errors, "
                         "never in a cell")
        self.assertNotIn("-500000", summary)
        for prefix in ("| Time", "| Tokens"):
            row = next(l for l in md.splitlines() if l.startswith(prefix))
            cells = [c.strip() for c in row.split("|")]
            # cells[1] is the metric title, which says "lower is better".
            self.assertEqual(cells[2], "—", row)   # primary: unmeasured
            self.assertEqual(cells[4], "—", row)   # delta: unmeasured
            self.assertEqual(cells[5], "—", row)   # direction: no verdict

    def test_the_grading_beside_it_still_counts(self):
        """Excluding a bad timing file must not discard a good grading."""
        stats = self.benchmark("bad-timing")["run_summary"]["with_skill"]
        self.assertEqual(stats["pass_rate"]["mean"], 1.0)

    def test_all_three_agree_it_is_schema_invalid(self):
        for name, proc in self.all_three("bad-timing").items():
            with self.subTest(component=name):
                self.assertIn((SCHEMA_INVALID, SEVERITY_ERROR),
                              self.conditions(proc))


# --------------------------------------------------------------------------
# R6: one source for configuration names
# --------------------------------------------------------------------------

class TestConfigNameSources(WorkspaceCase):
    """Two hardcoded lists that had to stay disjoint, and were not."""

    def test_no_role_carrying_name_can_be_ignored_by_the_walker(self):
        self.assertEqual(
            IGNORED_DIRS & frozenset(ROLE_CONFIGS), frozenset(),
            "a directory the aggregator treats as a configuration cannot be "
            "invisible to the gate that checks it")

    def test_skill_is_still_a_primary_role_name(self):
        self.assertIn("skill", PRIMARY_ROLE_CONFIGS)
        self.assertNotIn("skill", IGNORED_DIRS)

    def test_every_role_name_is_a_recognised_configuration(self):
        for name in ROLE_CONFIGS:
            self.assertIn(name, RECOGNIZED_CONFIGS,
                          "a name that carries a role and is not recognised is "
                          "the same drift in a different pair of lists")

    def test_a_config_named_skill_is_checked_like_any_other(self):
        out = self.combined(self.script("preflight",
                                        self.iteration("skill-config")))
        self.assertIn("C12:schema_invalid=error", out)
        self.assertIn("must not be negative", out)
        self.assertIn("skill", out)

    def test_all_three_see_the_malformed_timing_under_skill(self):
        for name, proc in self.all_three("skill-config").items():
            with self.subTest(component=name):
                self.assertIn((SCHEMA_INVALID, SEVERITY_ERROR),
                              self.conditions(proc))


# --------------------------------------------------------------------------
# R7: pairing, at eval level and at run level
# --------------------------------------------------------------------------

class TestUnpairedEvals(WorkspaceCase):
    """`+0.50 better` from an eval the baseline never ran."""

    def setUp(self):
        self.procs = self.all_three("unpaired-evals")

    def test_the_delta_is_no_longer_the_unpaired_eval(self):
        delta = self.benchmark("unpaired-evals")["run_summary"]["delta"]
        self.assertEqual(delta["pass_rate"]["value"], 0.0,
                         "eval-0 scored 0% in both configurations, and eval-0 "
                         "is the only eval both configurations ran")
        self.assertIsNone(delta["pass_rate"]["better"])

    def test_the_columns_still_describe_each_configuration(self):
        summary = self.benchmark("unpaired-evals")["run_summary"]
        self.assertEqual(summary["with_skill"]["pass_rate"]["n"], 2)
        self.assertEqual(summary["without_skill"]["pass_rate"]["n"], 1)

    def test_all_three_report_the_condition_and_refuse(self):
        for name, proc in self.procs.items():
            with self.subTest(component=name):
                self.assertIn((UNPAIRED_EVALS, SEVERITY_ERROR),
                              self.conditions(proc))
                self.assertEqual(proc.returncode, 1, self.combined(proc))

    def test_the_unpaired_eval_is_named_in_the_artifact(self):
        data = self.benchmark("unpaired-evals")
        unpaired = [e for e in data["exclusions"]
                    if "C12:unpaired_evals=error" in e["reason"]]
        self.assertEqual(len(unpaired), 1, data["exclusions"])
        self.assertIn("with_skill", unpaired[0]["reason"])
        self.assertIn("without_skill", unpaired[0]["reason"])

    def test_the_markdown_states_the_delta_basis(self):
        md = self.benchmark_md("unpaired-evals")
        self.assertIn("Incomplete pairing", md)
        self.assertIn("C12:unpaired_evals=error", md)
        self.assertIn("only-with-skill", md, "the per-eval table names it")
        row = next(l for l in md.splitlines() if l.startswith("| 1 |"))
        self.assertIn("no", row.rsplit("|", 2)[1], row)

    def test_pairing_is_computed_once_and_used_everywhere(self):
        results = {
            "with_skill": [{"eval_id": 0, "run_number": 1},
                           {"eval_id": 1, "run_number": 1}],
            "without_skill": [{"eval_id": 0, "run_number": 1}],
        }
        pairing = pair_evals(results, "with_skill", "without_skill")
        self.assertEqual(pairing["paired"], [0])
        self.assertEqual(pairing["unpaired"], {"with_skill": [1]})
        self.assertFalse(pairing["complete"])


class TestExclusionInducedImbalance(WorkspaceCase):
    """R7 one level down: an excluded run moved a delta instead of voiding it."""

    def setUp(self):
        self.procs = self.all_three("pass-rate-string")

    def test_the_delta_declines_rather_than_shifting(self):
        delta = self.benchmark("pass-rate-string")["run_summary"]["delta"]
        self.assertIsNone(delta["pass_rate"]["value"],
                          "with_skill lost run-1 to a schema failure and "
                          "without_skill lost nothing; the surviving means are "
                          "means of different things")

    def test_the_surviving_run_still_counts_for_its_own_configuration(self):
        summary = self.benchmark("pass-rate-string")["run_summary"]
        self.assertEqual(summary["with_skill"]["pass_rate"]["n"], 1)
        self.assertEqual(summary["with_skill"]["pass_rate"]["mean"], 1.0)

    def test_which_runs_were_dropped_and_from_which_side_is_named(self):
        data = self.benchmark("pass-rate-string")
        entry = next(e for e in data["exclusions"]
                     if "C12:unpaired_evals=error" in e["reason"])
        self.assertIn("with_skill", entry["reason"])
        self.assertIn("kept run(s) 2", entry["reason"])
        self.assertIn("lost 1", entry["reason"])

    def test_all_three_refuse(self):
        for name, proc in self.procs.items():
            with self.subTest(component=name):
                self.assertIn((UNPAIRED_EVALS, SEVERITY_ERROR),
                              self.conditions(proc))
                self.assertEqual(proc.returncode, 1, self.combined(proc))

    def test_unequal_run_counts_alone_are_not_this_condition(self):
        """`missing-timing` runs 2 against 1 with nothing excluded."""
        for name, proc in self.all_three("missing-timing").items():
            with self.subTest(component=name):
                self.assertEqual(self.conditions(proc), set())
        delta = self.benchmark("missing-timing")["run_summary"]["delta"]
        self.assertIsNotNone(delta["pass_rate"]["value"])

    def test_the_null_runs_per_configuration_is_explained_not_just_null(self):
        self.script("aggregate_benchmark", self.iteration("missing-timing"),
                    "--skill-name", "demo")
        self.assertIsNone(
            self.benchmark("missing-timing")["metadata"]["runs_per_configuration"])
        md = self.benchmark_md("missing-timing")
        self.assertIn("Unequal run counts", md)
        self.assertIn("runs_per_configuration", md)


# --------------------------------------------------------------------------
# R8: a flat grading.json beside run-<K>/
# --------------------------------------------------------------------------

class TestDroppedConfiguration(WorkspaceCase):
    """R7 at the third scale: a whole configuration gone.

    `resolve_roles` had `len(configs) == 1 -> that config is the primary`, so a
    workspace whose `with_skill` produced nothing reported
    `Without Skill [primary]`, delta `—`, exit 0. The baseline was promoted by
    survivorship, and the artifact then read as an ordinary
    single-configuration result rather than as a comparison that lost half its
    data - which is the version of this defect a reader is least likely to
    catch, because nothing about it looks wrong.
    """

    def test_a_surviving_baseline_is_not_promoted(self):
        from scripts.aggregate_benchmark import resolve_roles
        self.assertEqual(resolve_roles(["without_skill"], None, None)[:2],
                         (None, "without_skill"))
        self.assertEqual(resolve_roles(["old_skill"], None, None)[:2],
                         (None, "old_skill"))

    def test_a_lone_primary_is_still_the_primary(self):
        from scripts.aggregate_benchmark import resolve_roles
        self.assertEqual(resolve_roles(["with_skill"], None, None)[:2],
                         ("with_skill", None))
        self.assertEqual(resolve_roles(["new_skill"], None, None)[:2],
                         ("new_skill", None))

    def test_the_artifact_names_the_missing_role(self):
        proc = self.script("aggregate_benchmark", self.iteration("baseline-only"),
                           "--skill-name", "demo")
        out = self.combined(proc)
        self.assertEqual(proc.returncode, 1, out)
        self.assertIn("[baseline]", out)
        self.assertNotIn("[primary]", out)
        self.assertIn("No primary configuration produced a usable run", out)

        data = self.benchmark("baseline-only")
        self.assertIsNone(data["primary"])
        self.assertEqual(data["baseline"], "without_skill")

        md = self.benchmark_md("baseline-only")
        self.assertIn("**Primary**: —", md)
        self.assertIn("not relabelled as the primary", md)

    def test_all_three_classify_it_as_the_others(self):
        for name, proc in self.all_three("baseline-only").items():
            with self.subTest(component=name):
                self.assertIn((UNPAIRED_EVALS, SEVERITY_ERROR),
                              self.conditions(proc))
                self.assertEqual(proc.returncode, 1, self.combined(proc))

    def test_the_three_scales_are_one_condition(self):
        """An eval, a run, a configuration - one row of C12's table."""
        scales = {
            "unpaired-evals": "an eval present in one configuration only",
            "pass-rate-string": "runs dropped from one side by exclusion",
            "baseline-only": "an entire configuration dropped",
        }
        for fixture, description in scales.items():
            with self.subTest(scale=description):
                for name, proc in self.all_three(fixture).items():
                    self.assertIn((UNPAIRED_EVALS, SEVERITY_ERROR),
                                  self.conditions(proc),
                                  f"{name} did not classify {description}")

    def test_a_legitimate_single_configuration_record_still_passes(self):
        """Baseline null, delta absent, nothing invented."""
        procs = self.all_three("primary-only")
        for name, proc in procs.items():
            with self.subTest(component=name):
                self.assertEqual(proc.returncode, 0, self.combined(proc))
                self.assertEqual(self.conditions(proc), set())

        data = self.benchmark("primary-only")
        self.assertEqual(data["primary"], "with_skill")
        self.assertIsNone(data["baseline"])
        self.assertIsNone(data["run_summary"]["delta"]["pass_rate"]["value"])
        self.assertEqual(
            data["run_summary"]["with_skill"]["pass_rate"]["mean"], 0.75)

    def test_no_counterpart_is_not_rendered_as_an_unpaired_eval(self):
        self.script("aggregate_benchmark", self.iteration("primary-only"),
                    "--skill-name", "demo")
        md = self.benchmark_md("primary-only")
        self.assertNotIn("Incomplete pairing", md)
        row = next(l for l in md.splitlines() if l.startswith("| 0 |"))
        self.assertNotIn("no", row.rsplit("|", 2)[1],
                         "there is no counterpart to be unpaired from")


class TestFlatAndRunDirs(WorkspaceCase):
    """The flat file is discarded; the validator claimed it was normalized."""

    def test_the_classifier_distinguishes_shadowed_from_normalizable(self):
        root = self.iteration("flat-and-run")
        flat = root / "eval-0-two-shapes" / "with_skill" / "grading.json"
        self.assertEqual(classify_grading_path(flat, root)["kind"],
                         "shadowed_flat")

        legacy_root = self.iteration("repro-flat")
        legacy = legacy_root / "eval-0" / "with_skill" / "grading.json"
        self.assertEqual(classify_grading_path(legacy, legacy_root)["kind"],
                         "legacy_flat")

    def test_validate_grading_no_longer_claims_a_read_that_did_not_happen(self):
        out = self.combined(self.script("validate_grading",
                                        self.iteration("flat-and-run")))
        self.assertIn("is NOT read", out)
        self.assertIn("run-1", out)
        flat_section = out.split("with_skill")[1] if "with_skill" in out else out
        self.assertNotIn("Readers normalize it to run-1", flat_section)

    def test_the_aggregator_names_the_file_it_used(self):
        proc = self.script("aggregate_benchmark",
                           self.iteration("flat-and-run"), "--skill-name", "demo")
        out = self.combined(proc)
        self.assertIn("C12:flat_and_run_dirs=warning", out)
        self.assertIn("is NOT being read", out)
        data = self.benchmark("flat-and-run")
        self.assertEqual(data["run_summary"]["with_skill"]["pass_rate"]["mean"],
                         0.0, "run-1 says 0%; the discarded flat file says 100%")

    def test_all_three_call_it_a_warning(self):
        for name, proc in self.all_three("flat-and-run").items():
            with self.subTest(component=name):
                self.assertIn((FLAT_AND_RUN_DIRS, SEVERITY_WARNING),
                              self.conditions(proc))

    def test_preflight_blocks_on_it_and_the_readers_do_not(self):
        procs = self.all_three("flat-and-run")
        self.assertEqual(procs["preflight"].returncode, 1)
        self.assertEqual(procs["validate_grading"].returncode, 0)
        self.assertEqual(procs["aggregate_benchmark"].returncode, 0)


# --------------------------------------------------------------------------
# R9: duplicate keys, units, the evals line, the per-eval table
# --------------------------------------------------------------------------

class TestDuplicateKeys(WorkspaceCase):

    def setUp(self):
        self.proc = self.script("aggregate_benchmark",
                                self.iteration("duplicate-keys"),
                                "--skill-name", "demo")

    def test_two_directories_claiming_one_eval_id_are_named(self):
        out = self.combined(self.proc)
        self.assertIn("was already claimed by", out)
        self.assertIn("eval-0-first-claimant", out)
        self.assertIn("eval-0-second-claimant", out)

    def test_run_1_and_run_01_collide_visibly(self):
        out = self.combined(self.proc)
        self.assertIn("run-01", out)
        self.assertIn("share a key that consumers treat as unique", out)

    def test_the_collision_is_recorded_in_the_artifact(self):
        warnings = self.benchmark("duplicate-keys")["layout_warnings"]
        self.assertTrue(any("already claimed by" in w for w in warnings))
        self.assertTrue(any("run number 1 is already taken" in w
                            for w in warnings))


class TestBenchmarkMarkdown(WorkspaceCase):

    def setUp(self):
        self.script("aggregate_benchmark", self.iteration("canonical"),
                    "--skill-name", "demo")
        self.md = self.benchmark_md("canonical")

    def test_the_pass_rate_row_carries_one_unit(self):
        row = next(l for l in self.md.splitlines() if l.startswith("| Pass Rate"))
        self.assertIn("50 pp", row, row)
        self.assertNotIn("+0.50", row,
                         "a fraction between two percentage cells reads as "
                         "'+0.50%' and understates the delta 100-fold")

    def test_the_fraction_is_still_in_the_json_for_machines(self):
        delta = self.benchmark("canonical")["run_summary"]["delta"]["pass_rate"]
        self.assertEqual(delta["formatted"], "+0.50")
        self.assertEqual(delta["value"], 0.5)

    def test_time_and_token_deltas_carry_their_units(self):
        time_row = next(l for l in self.md.splitlines() if l.startswith("| Time"))
        self.assertIn("s |", time_row)
        token_row = next(l for l in self.md.splitlines() if l.startswith("| Tokens"))
        self.assertIn("tokens", token_row)

    def test_one_eval_with_id_zero_is_not_rendered_as_zero_evals(self):
        line = next(l for l in self.md.splitlines() if l.startswith("**Evals**"))
        self.assertEqual(line, "**Evals**: 1 (id 0)")

    def test_there_is_a_per_eval_breakdown(self):
        self.assertIn("## By eval", self.md)
        row = next(l for l in self.md.splitlines() if l.startswith("| 0 |"))
        self.assertIn("handles-empty-csv", row)
        self.assertIn("88%", row, "with_skill ran 4/4 and 3/4")
        self.assertIn("38%", row, "without_skill ran 1/4 and 2/4")
        self.assertIn("yes", row, "both configurations ran it")


if __name__ == "__main__":
    unittest.main(verbosity=2)
