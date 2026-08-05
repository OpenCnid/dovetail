#!/usr/bin/env python3
"""Workspace fixtures for the benchmark-pipeline contract tests.

Each fixture is a better-skill-creator workspace built to reproduce one documented
defect. `build(root)` materializes all of them under `root`; running this
module regenerates the committed copy at `tests/fixtures/ws/`.

    python -m tests.make_workspace_fixtures

The committed copy exists so a human can look at a failing layout directly.
The tests always call `build()` into a temporary directory, because
`aggregate_benchmark` writes benchmark.json/benchmark.md into the iteration
directory it is pointed at and must never mutate a committed fixture.

Fixture             Reproduces
------------------- ------------------------------------------------------
repro-flat          research/00-orchestrator-repro.md - two configs graded
                    4/4 in the layout SKILL.md documented, which aggregated
                    to `Delta: +0.00` over an empty runs array, exit 0.
canonical           The canonical layout, two runs per configuration.
                    Anchors the statistics, which were verified correct and
                    must stay that way.
inverted-delta      research/14-workflow-design.md F2 - `old_skill` sorts
                    before `with_skill`, so a +0.75 improvement printed as
                    -0.75.
missing-timing      research/14 F4 - an unmeasured duration rendered as 0.0s
                    and was averaged in as a measurement.
pass-rate-string    `pass_rate` must be a number in [0,1]. A string used to
                    flow straight through aggregation.
summary-failed      research/11 F13.2 - `summary.failed` was never
                    cross-checked, so "1 passed, 0 failed of 3" validated
                    clean over three expectations.
grader-timing-block research/15 F4 - a `timing` block inside grading.json
                    closed the gate on timing.json, so the "Tokens" column
                    showed `execution_metrics.output_chars` instead.
mixed-metadata      research/11 F7 - one eval directory with
                    eval_metadata.json and one without.
single-run          research/11 F3 - one run per configuration reported
                    `stddev 0.0` under a header asserting 3 runs.
zero-runs           research/11 F6 - an eval directory named descriptively,
                    which no reader discovers.
unreachable-grading A grading.json parked at the eval-directory root, where
                    the aggregator never walks.
unpaired-evals      research/V1 N3 / R7 - eval-1 ran only under `with_skill`,
                    and its 100% became the whole of a `+0.50 better` delta.
baseline-only       R7, third scale - `with_skill` produced nothing, so the
                    surviving baseline was relabelled `[primary]` at exit 0.
primary-only        The legitimate single-configuration record, which the
                    baseline-only fix must not break.
bad-timing          research/V1 N1 / R5 - a negative duration and negative
                    token count, rendered as `-3600.0s | better` at exit 0.
skill-config        research/V1 N2 / R6 - a configuration directory named
                    `skill`, which preflight's ignore list skipped even though
                    the aggregator treats it as the primary.
flat-and-run        research/V1 N4 / R8 - a configuration holding both a flat
                    grading.json and a run-1/, where the flat file is silently
                    discarded and the validator claimed it was normalized.
duplicate-keys      research/V1 N5 / R9 - two eval directories declaring
                    eval_id 0, and `run-1` beside `run-01`.
all-abstained       every expectation in every run abstained, so there is no
                    pass rate anywhere. A `0` in any cell of any artifact is
                    the defect.
partly-abstained    100% over 2 ruled-on checks and 9 abstentions beside
                    100% over 11, which must not render alike.
every-reason        every typed abstention reason in one workspace,
                    including `underspecified`, which the markdown legend
                    counted and did not define. One config also carries
                    a run whose grading uses a reason outside the enum: it is
                    schema-invalid, so it must be excluded and named rather
                    than counted as `untyped` in a surviving column.
previous-contract   grading.json in the retired boolean shape, which must be
                    diagnosed as the previous contract with a migration
                    rather than as a type error.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

FIXTURE_DIR_NAME = "ws"


# --------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------

def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def grading(passed: int, failed: int, abstained: int = 0, *, pass_rate=None,
            summary_failed=None, texts=None, timing_block=False,
            execution_metrics=None, abstain_reasons=None,
            legacy_boolean=False) -> dict:
    """A well-formed grading.json, with hooks for building malformed ones.

    Verdicts are ternary: `passed` entries come first, then `failed`, then
    `abstained`. `pass_rate` is `passed / (passed + failed)` and is **None**
    when nothing was graded - abstentions leave the denominator, and a rate
    over nothing is null rather than zero.

    `legacy_boolean=True` emits the PREVIOUS contract's shape - a boolean
    `passed` per expectation and no `abstained` in the summary - for the
    fixtures that exist to prove the validator names it as such.
    """
    total = passed + failed + abstained
    labels = texts or [f"expectation {i + 1}" for i in range(total)]
    reasons = abstain_reasons or ["evidence"] * abstained
    expectations = []
    for i in range(total):
        if i < passed:
            verdict, reason = "pass", None
            evidence = "output matched the expectation"
        elif i < passed + failed:
            verdict, reason = "fail", None
            evidence = "output did not match"
        else:
            verdict = "abstain"
            reason = reasons[i - passed - failed]
            evidence = ("nothing in outputs/ could settle this; no transcript "
                        "was supplied")
        if legacy_boolean:
            expectations.append({
                "text": labels[i],
                "passed": verdict == "pass",
                "evidence": evidence,
            })
        else:
            expectations.append({
                "text": labels[i],
                "verdict": verdict,
                "abstainReason": reason,
                "evidence": evidence,
            })

    graded = passed + failed
    default_rate = (passed / graded) if graded else None
    summary = {
        "passed": passed,
        "failed": failed if summary_failed is None else summary_failed,
        "abstained": abstained,
        "total": total,
        "pass_rate": default_rate if pass_rate is None else pass_rate,
    }
    if legacy_boolean:
        del summary["abstained"]
    payload = {
        "expectations": expectations,
        "summary": summary,
    }
    if timing_block:
        payload["timing"] = {"total_duration_seconds": 191.0}
    if execution_metrics is not None:
        payload["execution_metrics"] = execution_metrics
    return payload


def timing(tokens: int, seconds: float) -> dict:
    return {
        "total_tokens": tokens,
        "duration_ms": int(seconds * 1000),
        "total_duration_seconds": seconds,
    }


def metadata(eval_id: int, name: str, prompt: str, assertions=None) -> dict:
    return {
        "eval_id": eval_id,
        "eval_name": name,
        "prompt": prompt,
        "assertions": assertions or [
            "the output is a CSV file",
            "a header row is present",
        ],
    }


def run(run_dir: Path, grading_payload, timing_payload=None,
        outputs=("result.csv",)) -> None:
    for name in outputs:
        out = run_dir / "outputs" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("name,total\nacme,42\n", encoding="utf-8")
    if grading_payload is not None:
        write_json(run_dir / "grading.json", grading_payload)
    if timing_payload is not None:
        write_json(run_dir / "timing.json", timing_payload)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def _repro_flat(root: Path) -> None:
    """research/00-orchestrator-repro.md, byte-for-byte in shape.

    `eval-0/<config>/grading.json` with no run level. Both configs graded 4/4.
    The old aggregator skipped every config directory that had no `run-*`
    child, so `results` stayed empty and it printed a full table of zeros.
    """
    it = root / "repro-flat" / "iteration-1"
    write_json(it / "eval-0" / "eval_metadata.json",
               metadata(0, "handles-empty-csv", "tidy this signups export"))
    for config in ("with_skill", "without_skill"):
        cfg = it / "eval-0" / config
        run(cfg, grading(4, 0), timing(84852, 23.332))


def _canonical(root: Path) -> None:
    """The canonical layout exactly. Two runs per configuration.

    Hand-computed: with_skill pass rates [1.0, 0.75] -> mean 0.875,
    n-1 stddev sqrt(0.03125) = 0.1768; times [60.0, 70.0] -> 65.0 +/- 7.0711;
    tokens [80000, 90000] -> 85000 +/- 7071.0678.
    without_skill [0.25, 0.5] -> 0.375 +/- 0.1768. Delta +0.50.
    """
    it = root / "canonical" / "iteration-1"
    ev = it / "eval-0-handles-empty-csv"
    write_json(ev / "eval_metadata.json",
               metadata(0, "handles-empty-csv", "tidy this signups export"))

    run(ev / "with_skill" / "run-1", grading(4, 0), timing(80000, 60.0))
    run(ev / "with_skill" / "run-2", grading(3, 1), timing(90000, 70.0))
    run(ev / "without_skill" / "run-1", grading(1, 3), timing(40000, 30.0))
    run(ev / "without_skill" / "run-2", grading(2, 2), timing(50000, 40.0))


def _inverted_delta(root: Path) -> None:
    """`old_skill` as the baseline - the improve-an-existing-skill path.

    Alphabetically `old_skill` < `with_skill`, so the pre-contract aggregator
    made the baseline primary and printed -0.75 for a +0.75 improvement.
    """
    it = root / "inverted-delta" / "iteration-1"
    ev = it / "eval-0-normalizes-dates"
    write_json(ev / "eval_metadata.json",
               metadata(0, "normalizes-dates", "normalize the date column"))
    run(ev / "with_skill" / "run-1", grading(4, 0), timing(90000, 60.0))
    run(ev / "old_skill" / "run-1", grading(1, 3), timing(40000, 30.0))


def _missing_timing(root: Path) -> None:
    """timing.json present for one run, absent for the rest.

    with_skill: run-1 timed, run-2 not -> n=1 measured, 1 unmeasured.
    without_skill: neither run timed -> tokens and duration are unknown for
    the whole configuration, and so is every delta that depends on them.
    """
    it = root / "missing-timing" / "iteration-1"
    ev = it / "eval-0-dedupes-rows"
    write_json(ev / "eval_metadata.json",
               metadata(0, "dedupes-rows", "remove duplicate rows"))
    run(ev / "with_skill" / "run-1", grading(4, 0), timing(80000, 60.0))
    run(ev / "with_skill" / "run-2", grading(4, 0), None)
    run(ev / "without_skill" / "run-1", grading(2, 2), None)


def _pass_rate_string(root: Path) -> None:
    """`"pass_rate": "100%"` - a string, and a percentage.

    with_skill run-2 is well-formed, so the benchmark is still built; the
    excluded run has to be visible in it rather than silently averaged or
    silently dropped.
    """
    it = root / "pass-rate-string" / "iteration-1"
    ev = it / "eval-0-parses-headers"
    write_json(ev / "eval_metadata.json",
               metadata(0, "parses-headers", "parse the header row"))
    run(ev / "with_skill" / "run-1",
        grading(4, 0, pass_rate="100%"), timing(80000, 60.0))
    run(ev / "with_skill" / "run-2", grading(4, 0), timing(82000, 62.0))
    run(ev / "without_skill" / "run-1", grading(1, 3), timing(40000, 30.0))


def _summary_failed(root: Path) -> None:
    """summary.failed disagrees with the expectations it summarizes.

    `{"passed": 1, "failed": 0, "total": 3}` over three expectations, one of
    which passed. The old validator checked `total` and `passed` and not
    `failed`, returned OK, and the viewer rendered "1 passed, 0 failed of 3".
    It is the only with_skill run, so the configuration ends with nothing.
    """
    it = root / "summary-failed" / "iteration-1"
    ev = it / "eval-0-counts-rows"
    write_json(ev / "eval_metadata.json",
               metadata(0, "counts-rows", "count the rows"))
    run(ev / "with_skill" / "run-1",
        grading(1, 2, summary_failed=0), timing(80000, 60.0))
    run(ev / "without_skill" / "run-1", grading(1, 3), timing(40000, 30.0))


def _grader_timing_block(root: Path) -> None:
    """A grader that obeyed the old prompt: a `timing` block inside grading.json.

    research/00 and research/15 F4: once `grading.timing.total_duration_seconds`
    was non-zero the aggregator never opened timing.json, so the real
    `total_tokens` was discarded and `execution_metrics.output_chars` was
    displayed under the header "Tokens" - wrong by roughly 7x here, and always
    in a plausible range. The duration silently became executor+grader.
    """
    it = root / "grader-timing-block" / "iteration-1"
    ev = it / "eval-0-token-column"
    write_json(ev / "eval_metadata.json",
               metadata(0, "token-column", "produce the report"))
    metrics = {"output_chars": 12450, "total_tool_calls": 15,
               "errors_encountered": 0}
    run(ev / "with_skill" / "run-1",
        grading(4, 0, timing_block=True, execution_metrics=metrics),
        timing(84852, 23.332))
    run(ev / "without_skill" / "run-1",
        grading(1, 3, timing_block=True, execution_metrics=metrics),
        timing(21533, 15.0))


def _mixed_metadata(root: Path) -> None:
    """One eval directory with eval_metadata.json and one without.

    The mix is what used to raise `TypeError: '<' not supported between
    instances of 'NoneType' and 'int'` downstream. Aggregation must name the
    missing file and carry on.
    """
    it = root / "mixed-metadata" / "iteration-1"
    ev0 = it / "eval-0-alpha-case"
    write_json(ev0 / "eval_metadata.json",
               metadata(0, "alpha-case", "the alpha prompt"))
    run(ev0 / "with_skill" / "run-1", grading(4, 0), timing(80000, 60.0))
    run(ev0 / "without_skill" / "run-1", grading(2, 2), timing(40000, 30.0))

    ev1 = it / "eval-1-beta-case"  # deliberately has no eval_metadata.json
    run(ev1 / "with_skill" / "run-1", grading(3, 1), timing(81000, 61.0))
    run(ev1 / "without_skill" / "run-1", grading(1, 3), timing(41000, 31.0))


def _single_run(root: Path) -> None:
    """Exactly one run per configuration.

    There is no sample standard deviation from one observation. The old code
    returned 0.0 and the metadata asserted `runs_per_configuration: 3`, so the
    header claimed three runs above a zero error bar.
    """
    it = root / "single-run" / "iteration-1"
    ev = it / "eval-0-single-sample"
    write_json(ev / "eval_metadata.json",
               metadata(0, "single-sample", "the only prompt"))
    run(ev / "with_skill" / "run-1", grading(4, 0), timing(80000, 60.0))
    run(ev / "without_skill" / "run-1", grading(1, 3), timing(40000, 30.0))


def _zero_runs(root: Path) -> None:
    """An eval directory named descriptively, as SKILL.md once instructed.

    `eval-*` never matches it and there is no eval_metadata.json, so nothing
    discovers it. This must refuse loudly rather than write a benchmark.
    """
    it = root / "zero-runs" / "iteration-1"
    ev = it / "csv-totals"
    run(ev / "with_skill" / "run-1", grading(4, 0), timing(80000, 60.0))
    run(ev / "without_skill" / "run-1", grading(1, 3), timing(40000, 30.0))


def _unpaired_evals(root: Path) -> None:
    """research/V1-verification.md N3 / R7 - a delta the baseline never ran.

    eval-0 scores 0% in both configurations. eval-1 exists only under
    `with_skill`, at 100%. Pooling the means reported `+0.50 better` at exit 0
    from all three tools: a favourable number whose entire magnitude came from
    an eval `without_skill` never attempted, over data whose one genuine
    comparison showed no difference at all.
    """
    it = root / "unpaired-evals" / "iteration-1"
    ev0 = it / "eval-0-both-ran-it"
    write_json(ev0 / "eval_metadata.json",
               metadata(0, "both-ran-it", "the paired prompt"))
    run(ev0 / "with_skill" / "run-1", grading(0, 2), timing(80000, 60.0))
    run(ev0 / "without_skill" / "run-1", grading(0, 2), timing(40000, 30.0))

    ev1 = it / "eval-1-only-with-skill"
    write_json(ev1 / "eval_metadata.json",
               metadata(1, "only-with-skill", "the unpaired prompt"))
    run(ev1 / "with_skill" / "run-1", grading(2, 0), timing(80000, 60.0))


def _baseline_only(root: Path) -> None:
    """A whole configuration dropped - the third scale of the same defect.

    `with_skill` produced nothing at all. `resolve_roles` had a
    `len(configs) == 1 -> that config is the primary` rule, so the surviving
    baseline was relabelled and the artifact read `Without Skill [primary]`,
    delta `—`, exit 0: a coherent-looking single-configuration report about the
    configuration nobody was testing, with nothing to say half the comparison
    was missing.
    """
    it = root / "baseline-only" / "iteration-1"
    ev = it / "eval-0-baseline-survived"
    write_json(ev / "eval_metadata.json",
               metadata(0, "baseline-survived", "the surviving prompt"))
    run(ev / "without_skill" / "run-1", grading(1, 3), timing(40000, 30.0))


def _primary_only(root: Path) -> None:
    """The mirror image, which is legitimate and must stay legitimate.

    `baseline` is null when only one configuration produced usable
    runs, the delta is absent, and nothing is invented. Recorded as a clean
    pass in research/V1-verification.md and research/V5; the fix for
    `baseline-only` must not take this with it.
    """
    it = root / "primary-only" / "iteration-1"
    ev = it / "eval-0-single-config"
    write_json(ev / "eval_metadata.json",
               metadata(0, "single-configuration", "the only configuration"))
    run(ev / "with_skill" / "run-1", grading(3, 1), timing(80000, 60.0))


def _bad_timing(root: Path) -> None:
    """research/V1-verification.md N1 / R5 - a negative duration reads "better".

    `validate_timing_file` rejects these and lives in the same package;
    `preflight` called it and the aggregator did not, so a one-hour negative
    runtime and half a million negative tokens were averaged, differenced, and
    endorsed by the Direction column at exit 0.
    """
    it = root / "bad-timing" / "iteration-1"
    ev = it / "eval-0-negative-duration"
    write_json(ev / "eval_metadata.json",
               metadata(0, "negative-duration", "the timing prompt"))
    run(ev / "with_skill" / "run-1", grading(4, 0),
        {"total_tokens": -500000, "duration_ms": -1,
         "total_duration_seconds": -3600.0})
    run(ev / "without_skill" / "run-1", grading(1, 3), timing(40000, 10.0))


def _skill_config(root: Path) -> None:
    """research/V1-verification.md N2 / R6 - `skill/` was invisible to preflight.

    `preflight.IGNORED_DIRS` held `skill` and `PRIMARY_ROLE_CONFIGS` held it
    too, so the malformed timing.json below produced no preflight finding at
    all, where the identical file under `with_skill/` produced two errors.
    """
    it = root / "skill-config" / "iteration-1"
    ev = it / "eval-0-named-skill"
    write_json(ev / "eval_metadata.json",
               metadata(0, "primary-named-skill", "the skill-named prompt"))
    run(ev / "skill" / "run-1", grading(4, 0),
        {"total_tokens": -999, "duration_ms": -1,
         "total_duration_seconds": -42.0})
    run(ev / "without_skill" / "run-1", grading(1, 3), timing(40000, 10.0))


def _flat_and_run(root: Path) -> None:
    """research/V1-verification.md N4 / R8 - both shapes in one configuration.

    `with_skill/grading.json` says 100%; `with_skill/run-1/grading.json` says
    0%. The run directory wins and the flat file is discarded in silence, while
    `validate_grading` reported that "readers normalize it to run-1" - a tool
    asserting a read that did not happen.
    """
    it = root / "flat-and-run" / "iteration-1"
    ev = it / "eval-0-two-shapes"
    write_json(ev / "eval_metadata.json",
               metadata(0, "two-shapes", "the ambiguous prompt"))
    write_json(ev / "with_skill" / "grading.json", grading(4, 0))
    run(ev / "with_skill" / "run-1", grading(0, 4), timing(80000, 60.0))
    run(ev / "without_skill" / "run-1", grading(1, 3), timing(40000, 30.0))


def _duplicate_keys(root: Path) -> None:
    """research/V1-verification.md N5 / R9 - colliding ids and run numbers.

    Two eval directories both declare `eval_id: 0`, and `run-1` and `run-01`
    both parse to run number 1. Every consumer keyed on
    (eval_id, configuration, run_number) - the viewer's per-eval breakdown is
    one - gets colliding rows, and nothing said so.
    """
    it = root / "duplicate-keys" / "iteration-1"
    for slug in ("eval-0-first-claimant", "eval-0-second-claimant"):
        ev = it / slug
        write_json(ev / "eval_metadata.json",
                   metadata(0, slug.replace("eval-0-", ""), f"the {slug} prompt"))
        run(ev / "with_skill" / "run-1", grading(4, 0), timing(80000, 60.0))
        run(ev / "without_skill" / "run-1", grading(2, 2), timing(40000, 30.0))

    # `run-01` parses to the same integer as `run-1`.
    dupe = it / "eval-0-first-claimant" / "with_skill" / "run-01"
    run(dupe, grading(0, 4), timing(81000, 61.0))


def _unreachable_grading(root: Path) -> None:
    """A grading.json parked at the eval-directory root.

    Structurally perfect, and at a path no reader walks. `rglob` finds it and
    used to report OK; the benchmark then reported nothing for that run.
    """
    it = root / "unreachable-grading" / "iteration-1"
    ev = it / "eval-0-misplaced"
    write_json(ev / "eval_metadata.json",
               metadata(0, "misplaced-grading", "the misplaced prompt"))
    write_json(ev / "grading.json", grading(4, 0))
    run(ev / "with_skill" / "run-1", grading(4, 0), timing(80000, 60.0))
    run(ev / "without_skill" / "run-1", grading(1, 3), timing(40000, 30.0))


def _all_abstained(root: Path) -> None:
    """Every expectation in every run abstained.

    The end-to-end repro for the rule that a rate over nothing is null and not
    zero. Both configurations ran, both were graded, and neither judge could
    rule on anything: eval-0 for jurisdiction, eval-1 for evidence. Every
    pass-rate cell in every artifact must read as absent. A `0` anywhere -
    `summary.pass_rate`, `runs[].result.pass_rate`, `run_summary.<config>`,
    the delta, the rendered table, the viewer - is the defect, and it is
    exactly the shape that reads as "this skill failed everything" to anyone
    skimming.

    Runs and timings are present and valid, so nothing else can be blamed for
    the absence.
    """
    it = root / "all-abstained" / "iteration-1"

    ev0 = it / "eval-0-no-jurisdiction"
    write_json(ev0 / "eval_metadata.json",
               metadata(0, "outside-jurisdiction", "produce the report",
                        assertions=["expectation 1", "expectation 2"]))
    ev1 = it / "eval-1-no-evidence"
    write_json(ev1 / "eval_metadata.json",
               metadata(1, "evidence-never-captured", "produce the report",
                        assertions=["expectation 1", "expectation 2",
                                    "expectation 3"]))

    for config, tokens, seconds in (("with_skill", 80000, 60.0),
                                    ("without_skill", 40000, 30.0)):
        run(ev0 / config / "run-1",
            grading(0, 0, 2, abstain_reasons=["jurisdiction", "jurisdiction"]),
            timing(tokens, seconds))
        run(ev1 / config / "run-1",
            grading(0, 0, 3,
                    abstain_reasons=["evidence", "evidence", "evidence"]),
            timing(tokens, seconds))


def _partly_abstained(root: Path) -> None:
    """A high rate over a small ruled-on fraction.

    `with_skill` passes both checks it was ruled on and abstains on nine, so
    its pass rate is 100%. `without_skill` is ruled on all eleven and passes
    eleven, so its pass rate is also 100%. The two are not the same result and
    no artifact may render them alike - which is only possible if the
    abstention count travels beside the rate.
    """
    it = root / "partly-abstained" / "iteration-1"
    ev = it / "eval-0-thin-evidence"
    write_json(ev / "eval_metadata.json",
               metadata(0, "thin-evidence", "produce the report",
                        assertions=[f"expectation {i + 1}" for i in range(11)]))
    run(ev / "with_skill" / "run-1",
        grading(2, 0, 9, abstain_reasons=["evidence"] * 9),
        timing(80000, 60.0))
    run(ev / "without_skill" / "run-1", grading(11, 0), timing(40000, 30.0))


def _every_reason(root: Path) -> None:
    """All three typed reasons in one workspace.

    `underspecified` was added to the enum after `benchmark.md`'s legend was
    written, and the legend was a hand-written sentence naming two reasons
    while `_fmt_abstention` printed whatever the counts held. The result was a
    count in the Detail column with no definition underneath it - and the one
    reason whose repair belongs to the person reading the benchmark was the one
    left unexplained.

    Both configurations are fully paired and every file is schema-valid, so
    nothing is excluded and the counts in the rendered table are the only thing
    under test.

    with_skill:    2 pass, 1 fail, 3 abstain - one of each reason.
    without_skill: 1 pass, 2 fail, 3 abstain - two `underspecified` and one
                   `evidence`, so the split differs between the columns and a
                   legend that printed one column's reasons for both would be
                   visibly wrong.
    """
    it = root / "every-reason" / "iteration-1"
    ev = it / "eval-0-mixed-reasons"
    write_json(ev / "eval_metadata.json",
               metadata(0, "mixed-reasons", "produce the report",
                        assertions=[f"expectation {i + 1}" for i in range(6)]))
    run(ev / "with_skill" / "run-1",
        grading(2, 1, 3, abstain_reasons=["jurisdiction", "evidence",
                                          "underspecified"]),
        timing(80000, 60.0))
    run(ev / "without_skill" / "run-1",
        grading(1, 2, 3, abstain_reasons=["underspecified", "underspecified",
                                          "evidence"]),
        timing(40000, 30.0))


def _unknown_reason(root: Path) -> None:
    """A reason outside the enum, in a file that is otherwise well-formed.

    `abstention_stats` keeps an `untyped` bucket for this, and the legend says
    it is 0 in any workspace that passed validation. That claim needs a
    workspace where the value exists to be sure the aggregator refuses it here
    rather than quietly counting it - a count under `untyped` in a surviving
    column would report a judge's ruling that no contract defines.

    eval-0 is clean on both sides so something survives; eval-1's `with_skill`
    grading carries `abstainReason: "busy"`, which fails schema validation and
    takes the eval out of the comparison.
    """
    it = root / "unknown-reason" / "iteration-1"
    ev0 = it / "eval-0-clean"
    write_json(ev0 / "eval_metadata.json",
               metadata(0, "clean", "produce the report",
                        assertions=["expectation 1", "expectation 2"]))
    run(ev0 / "with_skill" / "run-1", grading(2, 0), timing(80000, 60.0))
    run(ev0 / "without_skill" / "run-1", grading(1, 1), timing(40000, 30.0))

    ev1 = it / "eval-1-reason-off-enum"
    write_json(ev1 / "eval_metadata.json",
               metadata(1, "reason-outside-the-enum", "produce the report",
                        assertions=["expectation 1", "expectation 2"]))
    run(ev1 / "with_skill" / "run-1",
        grading(1, 0, 1, abstain_reasons=["busy"]), timing(80000, 60.0))
    run(ev1 / "without_skill" / "run-1",
        grading(1, 0, 1, abstain_reasons=["evidence"]), timing(40000, 30.0))


def _previous_contract(root: Path) -> None:
    """The PREVIOUS grading contract - a boolean `passed`, no `abstained`.

    Not malformed, just last version's format. This must be diagnosed by name
    with the migration spelled out, rather than reported as a generic type
    error that says nothing about what changed.
    """
    it = root / "previous-contract" / "iteration-1"
    ev = it / "eval-0-bool-verdicts"
    write_json(ev / "eval_metadata.json",
               metadata(0, "boolean-verdicts", "produce the report"))
    run(ev / "with_skill" / "run-1", grading(4, 0, legacy_boolean=True),
        timing(80000, 60.0))
    run(ev / "without_skill" / "run-1", grading(1, 3, legacy_boolean=True),
        timing(40000, 30.0))


BUILDERS = (
    _repro_flat,
    _canonical,
    _inverted_delta,
    _missing_timing,
    _pass_rate_string,
    _summary_failed,
    _grader_timing_block,
    _mixed_metadata,
    _single_run,
    _zero_runs,
    _unreachable_grading,
    _unpaired_evals,
    _baseline_only,
    _primary_only,
    _bad_timing,
    _skill_config,
    _flat_and_run,
    _duplicate_keys,
    _all_abstained,
    _partly_abstained,
    _every_reason,
    _unknown_reason,
    _previous_contract,
)


def build(root: Path) -> Path:
    """Materialize every workspace fixture under `root`. Returns `root`."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for builder in BUILDERS:
        builder(root)
    return root


def main(argv=None) -> int:
    target = Path(__file__).resolve().parent / "fixtures" / FIXTURE_DIR_NAME
    if target.exists():
        shutil.rmtree(target)
    build(target)
    print(f"Wrote {len(BUILDERS)} workspace fixtures to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
