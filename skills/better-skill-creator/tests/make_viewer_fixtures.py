#!/usr/bin/env python3
"""Build the eval-viewer fixture workspaces.

    python -m tests.make_viewer_fixtures [target-dir]

Default target is tests/fixtures/, which is where the committed copies live.
`tests/test_eval_viewer.py` rebuilds into a temporary directory instead, because
the viewer's server mode writes feedback.json into the workspace it is pointed
at and must never be pointed at the committed copy.

Three workspaces, each aimed at a specific defect class:

  hostile/       Canonical C1 layout carrying every payload the
                           presentation layer used to mishandle: an output file
                           that closes the embedding <script>, grader evidence
                           that closes an HTML attribute, benchmark.json fields
                           that reach innerHTML, non-ASCII in prompts, outputs
                           and evidence, an expectation with no text, an
                           assertion the two graders worded differently, and one
                           run with no timing.json at all.
  legacy-flat/   The pre-C1 layout with no run-<K> level. Must still
                           render, and must say out loud that it normalized.
  mixed-eval-id/ One eval with metadata, one without, one with a null
                           eval_id -- the mix that used to raise TypeError in
                           the run sort and produce no viewer at all. Also the
                           ungraded-run case: no grading.json anywhere in it.
  ordering-swap/ Two configurations whose graders returned the SAME
                           two assertions in OPPOSITE order, with opposite
                           results. Under positional alignment this renders as
                           two rows on which both configurations agree; the
                           truth is that they disagree on both. Also carries a
                           reworded assertion, so the drift disclosure and the
                           ordering fix are exercised on one page.
  malformed-run/ A `run-final/` directory: matches the viewer's old
                           `^run-(.+)$` and not the scripts' `^run-(\\d+)$`, so
                           it appeared here and in no benchmark number. Its
                           benchmark.json is the no-primary-survived state:
                           `primary` is null and the survivor stays labelled
                           baseline rather than being promoted.
  mixed-exclusions-        All three exclusion KINDS on one page: a run dropped
  workspace/               entirely, a run that lost only its timing.json, and
                           an eval excluded from the delta but counted in its
                           own configuration's column.
  abstain/       Ternary verdicts end to end. One eval where every check
                           abstained (no pass rate anywhere -- a `0` in any
                           cell is the defect), one where 100% over 2 ruled-on
                           checks sits beside 100% over 11 (the two must not
                           render alike), and one carrying both typed reasons
                           so `jurisdiction` and `evidence` are separable on
                           screen.
  reason-taxonomy-         Every abstention reason the contract defines, on one
  workspace/               page, plus one grading carrying a reason the page
                           does not know and one carrying none at all. Four
                           states, and no two of them may render alike:
                           `underspecified` must not read as a variant of the
                           other two, an unrecognized value must read as
                           recorded-but-unknown, and only the missing one may
                           say nothing was recorded.
  previous-contract-       grading.json in the retired boolean shape. The page
  workspace/               must name it as the previous contract and show the
                           checks as unrecorded rather than guessing whether
                           each `false` meant "verified false" or "could not
                           tell".
"""

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

# The exclusion reasons below carry the shared condition tag, and
# they are built with the real classifier rather than hand-typed. A fixture
# that spells the tag itself would keep passing after the vocabulary moved,
# which is the whole failure mode the shared classifier exists to close.
from scripts.utils import condition_line  # noqa: E402
# The abstention-reason enum, imported for the same reason as `condition_line`
# above: a fixture that spells the reasons out by hand keeps passing after the
# enum grows, and the enum growing from two to three is exactly the event these
# fixtures now have to catch.
from scripts.validate_grading import ABSTAIN_REASONS  # noqa: E402

DEFAULT_TARGET = Path(__file__).resolve().parent / "fixtures"

# --- payloads ---------------------------------------------------------------
# A skill that emits HTML contains this. It is not an exotic attack; it is a
# Tuesday.
BREAKOUT = '</script><img src=x onerror="window.__EMBED_FIRED=1"><probe id="probe-el"></probe>'
# Grader evidence quotes the output being judged, so a double quote in the
# output reaches a title="..." attribute.
ATTR = 'x" onmouseover="window.__ATTR_FIRED=1" data-z="'
NONASCII = "Итог: 42 — 日本語テキスト — café naïve"


def svg(tag):
    """Markup that announces itself if it ever becomes live DOM."""
    return '<svg onload="window.__X_FIRED_' + tag + '=1"></svg>'


def expectations(texts, verdicts, evidence_overrides=None, reasons=None):
    """Ternary-verdict expectation entries.

    `verdicts` accepts the three verdict strings, and also `True`/`False` for
    the many call sites here that predate the ternary contract and mean exactly
    "pass"/"fail". `reasons` supplies `abstainReason` by index; the default for
    an abstention is `evidence`, since "the artifacts did not carry what a
    ruling needed" is the common case.
    """
    out = []
    for i, (text, verdict) in enumerate(zip(texts, verdicts)):
        if verdict is True:
            verdict = "pass"
        elif verdict is False:
            verdict = "fail"
        evidence = (evidence_overrides or {}).get(i, "row %d checked" % i)
        reason = None
        if verdict == "abstain":
            reason = (reasons or {}).get(i, "evidence")
        out.append({"text": text, "verdict": verdict,
                    "abstainReason": reason, "evidence": evidence})
    return out


def summary_of(exps):
    """The C16 summary for a list of expectations.

    Derived, never hand-typed: `pass_rate` excludes abstentions from the
    denominator and is None when nothing was ruled on, and a fixture that
    restated those by hand would keep passing after the rule moved.
    """
    counts = {"pass": 0, "fail": 0, "abstain": 0}
    for exp in exps:
        verdict = exp.get("verdict")
        if verdict in counts:
            counts[verdict] += 1
    graded = counts["pass"] + counts["fail"]
    return {
        "passed": counts["pass"],
        "failed": counts["fail"],
        "abstained": counts["abstain"],
        "total": len(exps),
        "pass_rate": round(counts["pass"] / graded, 4) if graded else None,
    }


def result_of(exps, time_seconds=None, tokens=None):
    """A `runs[].result` block for a list of expectations."""
    summary = summary_of(exps)
    return {
        "pass_rate": summary["pass_rate"],
        "passed": summary["passed"],
        "failed": summary["failed"],
        "abstained": summary["abstained"],
        "total": summary["total"],
        "time_seconds": time_seconds,
        "tokens": tokens,
    }


def _abstention(abstained, graded, total, reasons, runs, runs_without_rate=0):
    """A `run_summary.<config>.abstention` block.

    The reason keys come from the contract's enum rather than from a list
    written out here, so this matches what `abstention_stats` actually emits
    even after the enum changes. `untyped` is not in the enum - it is the
    aggregator's bucket for a reason outside it - so it is added separately.
    """
    filled = {reason: 0 for reason in ABSTAIN_REASONS}
    filled["untyped"] = 0
    filled.update(reasons)
    return {"abstained": abstained, "graded": graded, "total": total,
            "rate": round(abstained / total, 4) if total else None,
            "reasons": filled, "runs": runs,
            "runs_without_pass_rate": runs_without_rate}


def _stat(mean, stddev, lo, hi, n, missing):
    return {"mean": mean, "stddev": stddev, "min": lo, "max": hi, "n": n, "missing": missing}


def build(target: Path) -> Path:
    target = Path(target)

    def w(rel, text):
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def wj(rel, obj):
        w(rel, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

    # =======================================================================
    # hostile
    # =======================================================================
    base = "hostile/iteration-1"
    e0 = base + "/eval-0-emits-html-report"

    wj(e0 + "/eval_metadata.json", {
        "eval_id": 0,
        "eval_name": "emits-html-report",
        # The canonical layout puts this two levels above <config>/run-<K>/.
        "prompt": "Build a one-page HTML report of Q3 sales. " + NONASCII,
        "assertions": ["Output is a CSV file", "Header row present", "Totals row is last"],
    })

    w(e0 + "/with_skill/run-1/outputs/report.html",
      "<h1>Q3 report</h1>\n" + BREAKOUT + "\n<p>done</p>\n")
    w(e0 + "/with_skill/run-1/outputs/notes.md",
      "# Notes\n\n" + NONASCII + "\n\nA line about `</script>` tags in markdown.\n")

    primary_texts = [
        "Output is a CSV file",
        "Header row present",
        "Totals row is last",
        "Currency is formatted",
        "No blank rows",
        "Dates are ISO-8601",
        "Encoding is UTF-8",
        "File is under 1 MB",
        "Column order matches the brief",
        "Footer note is present",
    ]
    # An independent grader on the other configuration reworded the first one.
    # Matching assertions on exact text split this into two half-empty rows.
    baseline_texts = list(primary_texts)
    baseline_texts[0] = "The output is a CSV file"

    e0_primary = expectations(
        primary_texts,
        [True, True, True, True, True, False, False, False, False, False],
        {
            0: "The grader quoted the output: " + ATTR,
            1: "Saw a literal </script> in the emitted markup, which is fine here.",
            2: NONASCII,
        },
    )
    # An expectation the grader forgot to give a text field: it used to render
    # as a bare checkmark indistinguishable from a normal pass.
    e0_primary[9] = {"verdict": "fail", "abstainReason": None,
                     "evidence": "no text field was written for this check"}
    e0_baseline = expectations(
        baseline_texts,
        [True, True, False, False, False, False, False, False, False, False])

    wj(e0 + "/with_skill/run-1/grading.json", {
        "expectations": e0_primary,
        "summary": summary_of(e0_primary),
    })
    wj(e0 + "/with_skill/run-1/timing.json",
       {"total_tokens": 1200, "duration_ms": 30000, "total_duration_seconds": 30.0})

    w(e0 + "/old_skill/run-1/outputs/report.html", "<h1>Q3 report</h1>\n<p>bare</p>\n")
    wj(e0 + "/old_skill/run-1/grading.json", {
        "expectations": e0_baseline,
        "summary": summary_of(e0_baseline),
    })
    wj(e0 + "/old_skill/run-1/timing.json",
       {"total_tokens": 900, "duration_ms": 45000, "total_duration_seconds": 45.0})

    # eval 1 is small (2 checks vs 10), which is what makes the macro-average
    # 75% while the true pooled rate is 58%.
    e1 = base + "/eval-1-summarises-csv"
    e1_texts = ["Mentions the total", "Two sentences or fewer",
                "Follows the documented ordering of steps"]
    # The third check is about HOW the work was done and this run kept no
    # transcript, so neither grader could rule on it. Under the previous
    # contract that was a fail on both sides -- an expectation nobody could
    # check, counted twice as evidence against both configurations. The two
    # reasons differ deliberately: the primary's judge was out of jurisdiction,
    # the baseline's was in jurisdiction and had nothing to read.
    e1_primary = expectations(e1_texts, [True, True, "abstain"],
                              reasons={2: "jurisdiction"})
    e1_baseline = expectations(e1_texts, [False, False, "abstain"],
                               reasons={2: "evidence"})

    wj(e1 + "/eval_metadata.json", {
        "eval_id": 1,
        "eval_name": "summarises-csv",
        "prompt": "Summarise sales.csv in two sentences.",
        "assertions": e1_texts,
    })
    w(e1 + "/with_skill/run-1/outputs/summary.txt", "Total sales were 1.2M. " + NONASCII + "\n")
    wj(e1 + "/with_skill/run-1/grading.json", {
        "expectations": e1_primary,
        "summary": summary_of(e1_primary),
    })
    # NO timing.json for this run: unknown, never 0.

    w(e1 + "/old_skill/run-1/outputs/summary.txt", "Sales happened.\n")
    wj(e1 + "/old_skill/run-1/grading.json", {
        "expectations": e1_baseline,
        "summary": summary_of(e1_baseline),
    })
    wj(e1 + "/old_skill/run-1/timing.json",
       {"total_tokens": 900, "duration_ms": 45000, "total_duration_seconds": 45.0})

    def run(eval_id, eval_name, config, result, exps):
        return {
            "eval_id": eval_id,
            "eval_name": eval_name,
            "configuration": config,
            "run_number": 1,
            "result": result,
            "expectations": exps,
            "notes": [],
        }

    runs = [
        run(0, "emits-html-report " + svg("EVALNAME"), "with_skill",
            result_of(e0_primary, 30.0, 1200), e0_primary),
        run(0, "emits-html-report", "old_skill",
            result_of(e0_baseline, 45.0, 900), e0_baseline),
        # This run had no timing.json. Absent, not zero.
        run(1, "summarises-csv", "with_skill",
            result_of(e1_primary, None, None), e1_primary),
        run(1, "summarises-csv", "old_skill",
            result_of(e1_baseline, 45.0, 900), e1_baseline),
    ]

    benchmark = {
        # C5: roles are declared. "old_skill" sorts before "with_skill", which
        # is exactly what used to make the baseline the primary and invert the
        # delta in the improve flow.
        "primary": "with_skill",
        "baseline": "old_skill",
        "metadata": {
            "skill_name": "demo-skill",
            "skill_path": None,
            "executor_model": None,
            "analyzer_model": None,
            # Fields that used to reach innerHTML with no escaping at all.
            "timestamp": "2026-07-31T00:00:00Z " + svg("TS"),
            "evals_run": [0, 1, svg("EVALS")],
            "runs_per_configuration": 1,
            "runs_per_configuration_by_config": {"with_skill": 1, "old_skill": 1},
        },
        "runs": runs,
        "run_summary": {
            "with_skill": {
                # macro mean 0.75 against a pooled rate of 7/12 = 0.583
                "pass_rate": _stat(0.75, 0.3536, 0.5, 1.0, 2, 0),
                # one run had no timing.json: n=1, missing=1, stddev null
                "time_seconds": _stat(30.0, None, 30.0, 30.0, 1, 1),
                "tokens": _stat(1200.0, None, 1200, 1200, 1, 1),
                # 1 abstention of 13 checks; 12 were ruled on. Without this
                # block the 100% on eval 1 and the 100% a fully-graded run
                # would produce are the same three characters on the page.
                "abstention": _abstention(1, 12, 13, {"jurisdiction": 1}, 2),
                "runs": 2,
            },
            "old_skill": {
                "pass_rate": _stat(0.10, 0.1414, 0.0, 0.2, 2, 0),
                "time_seconds": _stat(45.0, 0.0, 45.0, 45.0, 2, 0),
                "tokens": _stat(900.0, 0.0, 900, 900, 2, 0),
                "abstention": _abstention(1, 12, 13, {"evidence": 1}, 2),
                "runs": 2,
            },
            "delta": {
                "pass_rate": {"value": 0.65, "formatted": "+0.65",
                              "polarity": "higher_is_better", "better": True},
                # 15 seconds FASTER: negative sign, and it is good.
                "time_seconds": {"value": -15.0, "formatted": "-15.0",
                                 "polarity": "lower_is_better", "better": True},
                # 300 MORE tokens: positive sign, and it is bad.
                "tokens": {"value": 300.0, "formatted": "+300",
                           "polarity": "lower_is_better", "better": False},
            },
        },
        "exclusions": [
            {
                "path": "iteration-1/eval-2-dropped/with_skill/run-1/grading.json",
                "reason": "failed grading.json schema validation " + svg("EXCL"),
                "errors": ["expectations[0]: has 'met' where the contract has 'verdict'"],
            },
        ],
        "layout_warnings": [
            "DEPRECATED LAYOUT: iteration-1/eval-3-flat/with_skill holds grading.json "
            "directly. Reading it as run-1. " + svg("LAYOUT"),
        ],
        "notes": [
            "Analyst note with markup: " + svg("NOTE"),
            "The skill is faster but uses more tokens.",
        ],
    }
    wj(base + "/benchmark.json", benchmark)

    # No declared roles: exercises the inference path and its warning.
    no_roles = json.loads(json.dumps(benchmark))
    del no_roles["primary"]
    del no_roles["baseline"]
    wj(base + "/benchmark-no-roles.json", no_roles)

    # The pre-rewrite shape: bare formatted-string deltas, no n/missing, no
    # exclusions, the hardcoded runs_per_configuration of 3, and an evals_run
    # that is not an array (which used to throw and blank the whole tab).
    legacy = json.loads(json.dumps(benchmark))
    for key in ("primary", "baseline", "exclusions", "layout_warnings"):
        del legacy[key]
    legacy["metadata"]["runs_per_configuration"] = 3
    del legacy["metadata"]["runs_per_configuration_by_config"]
    legacy["metadata"]["evals_run"] = "0, 1"
    for config in ("with_skill", "old_skill"):
        for metric in ("pass_rate", "time_seconds", "tokens"):
            stat = legacy["run_summary"][config][metric]
            legacy["run_summary"][config][metric] = {
                "mean": stat["mean"], "stddev": stat["stddev"] or 0.0,
                "min": stat["min"], "max": stat["max"],
            }
        del legacy["run_summary"][config]["runs"]
    legacy["run_summary"]["delta"] = {
        "pass_rate": "+0.65", "time_seconds": "-15.0", "tokens": "+300",
    }
    wj(base + "/benchmark-legacy.json", legacy)

    # =======================================================================
    # legacy-flat: no run-<K> level
    # =======================================================================
    flat = "legacy-flat/iteration-1/eval-0-flat-layout"
    wj(flat + "/eval_metadata.json", {
        "eval_id": 0, "eval_name": "flat-layout",
        "prompt": "Legacy flat layout probe. " + NONASCII,
    })
    for config, verdicts in (("with_skill", [True, True]),
                             ("without_skill", [True, False])):
        w(flat + "/" + config + "/outputs/out.txt", config + " output\n")
        flat_exps = expectations(["Check A", "Check B"], verdicts)
        wj(flat + "/" + config + "/grading.json", {
            "expectations": flat_exps,
            "summary": summary_of(flat_exps),
        })

    # =======================================================================
    # mixed-eval-id: identified, unidentified and null-id evals
    # =======================================================================
    mixed = "mixed-eval-id/iteration-1"
    wj(mixed + "/eval-0-has-metadata/eval_metadata.json",
       {"eval_id": 0, "eval_name": "has-metadata", "prompt": "Identified eval."})
    w(mixed + "/eval-0-has-metadata/with_skill/run-1/outputs/a.txt", "a\n")
    w(mixed + "/eval-1-no-metadata/with_skill/run-1/outputs/b.txt", "b\n")
    wj(mixed + "/eval-2-null-id/eval_metadata.json",
       {"eval_id": None, "eval_name": "null-id", "prompt": "Eval with a null id."})
    w(mixed + "/eval-2-null-id/with_skill/run-1/outputs/c.txt", "c\n")

    # =======================================================================
    # ordering-swap: the R10 repro
    #
    # One eval, two assertions, two configurations. Each configuration was
    # graded by its own sub-agent, and the two sub-agents returned the same two
    # checks in opposite order -- which nothing in the schema forbids, because
    # nothing in the schema promises an order. Each configuration passed ONE
    # check, and a DIFFERENT one.
    #
    #   with_skill:     [ HEADER pass, TOTALS fail ]
    #   without_skill:  [ TOTALS pass, HEADER fail ]
    #
    # Aligned by position, row 1 shows pass/pass and row 2 shows fail/fail: two
    # configurations in perfect agreement, which is the opposite of the truth.
    # Aligned by text, each row shows one pass and one fail.
    # =======================================================================
    HEADER = "Header row present"
    TOTALS = "Totals row is last"
    # A third check that one grader reworded, so the drift disclosure appears
    # on the same page as the ordering fix.
    CURRENCY = "Currency is formatted"
    CURRENCY_REWORDED = "The currency is formatted"

    swap = "ordering-swap/iteration-1/eval-0-swapped-order"
    wj(swap + "/eval_metadata.json", {
        "eval_id": 0,
        "eval_name": "swapped-order",
        "prompt": "Emit the sales table.",
        "assertions": [HEADER, TOTALS, CURRENCY],
    })

    swap_primary = expectations(
        [HEADER, TOTALS, CURRENCY], [True, False, True],
        {0: "row 1 is a header", 1: "totals row is in the middle",
         2: "GBP with two decimals"})
    swap_baseline = expectations(
        [TOTALS, HEADER, CURRENCY_REWORDED], [True, False, False],
        {0: "totals row is last", 1: "no header row at all",
         2: "bare integers"})

    for config, exps in (("with_skill", swap_primary),
                         ("without_skill", swap_baseline)):
        w(swap + "/" + config + "/run-1/outputs/table.csv", config + ",1\n")
        wj(swap + "/" + config + "/run-1/grading.json", {
            "expectations": exps,
            "summary": summary_of(exps),
        })
        wj(swap + "/" + config + "/run-1/timing.json",
           {"total_tokens": 500, "duration_ms": 10000, "total_duration_seconds": 10.0})

    wj("ordering-swap/iteration-1/benchmark.json", {
        "primary": "with_skill",
        "baseline": "without_skill",
        "metadata": {
            "skill_name": "swap-demo",
            "timestamp": "2026-07-31T00:00:00Z",
            "evals_run": [0],
            "runs_per_configuration": 1,
        },
        "runs": [
            run(0, "swapped-order", "with_skill",
                result_of(swap_primary, 10.0, 500), swap_primary),
            run(0, "swapped-order", "without_skill",
                result_of(swap_baseline, 10.0, 500), swap_baseline),
        ],
        # One run per configuration: stddev is null, and any renderer that
        # prints "+/- 0" here is inventing a spread it never measured.
        "run_summary": {
            "with_skill": {
                "pass_rate": _stat(0.6667, None, 0.6667, 0.6667, 1, 0),
                "time_seconds": _stat(10.0, None, 10.0, 10.0, 1, 0),
                "tokens": _stat(500.0, None, 500, 500, 1, 0),
                "runs": 1,
            },
            "without_skill": {
                "pass_rate": _stat(0.3333, None, 0.3333, 0.3333, 1, 0),
                "time_seconds": _stat(10.0, None, 10.0, 10.0, 1, 0),
                "tokens": _stat(500.0, None, 500, 500, 1, 0),
                "runs": 1,
            },
            "delta": {
                "pass_rate": {"value": 0.3334, "formatted": "+0.33",
                              "polarity": "higher_is_better", "better": True},
            },
        },
        "exclusions": [],
        "layout_warnings": [],
        "notes": [],
    })

    # The same benchmark with run_summary deleted: the viewer must recompute
    # from runs[] and must NOT print a standard deviation for a single sample.
    swap_bench = json.loads(
        (target / "ordering-swap/iteration-1/benchmark.json").read_text(encoding="utf-8"))
    no_summary = json.loads(json.dumps(swap_bench))
    del no_summary["run_summary"]
    wj("ordering-swap/iteration-1/benchmark-no-summary.json", no_summary)

    # And with a type-invalid run_summary: mean as a string, mean as null. The
    # viewer must reject the block, fall back, and SAY that it did.
    bad_summary = json.loads(json.dumps(swap_bench))
    bad_summary["run_summary"]["with_skill"]["pass_rate"]["mean"] = "67%"
    bad_summary["run_summary"]["without_skill"]["time_seconds"]["mean"] = None
    wj("ordering-swap/iteration-1/benchmark-bad-summary.json", bad_summary)

    # =======================================================================
    # malformed-run: run-final/ instead of run-1/
    # =======================================================================
    bad_run = "malformed-run/iteration-1/eval-0-misnamed-run"
    wj(bad_run + "/eval_metadata.json", {
        "eval_id": 0, "eval_name": "misnamed-run",
        "prompt": "Anything.", "assertions": ["Check A"],
    })
    bad_run_primary = expectations(["Check A"], [True], {0: "it is there"})
    bad_run_baseline = expectations(["Check A"], [False], {0: "absent"})
    w(bad_run + "/with_skill/run-final/outputs/out.txt", "with_skill output\n")
    wj(bad_run + "/with_skill/run-final/grading.json", {
        "expectations": bad_run_primary,
        "summary": summary_of(bad_run_primary),
    })
    wj(bad_run + "/with_skill/run-final/timing.json",
       {"total_tokens": 100, "duration_ms": 1000, "total_duration_seconds": 1.0})
    w(bad_run + "/without_skill/run-1/outputs/out.txt", "without_skill output\n")
    wj(bad_run + "/without_skill/run-1/grading.json", {
        "expectations": bad_run_baseline,
        "summary": summary_of(bad_run_baseline),
    })
    wj(bad_run + "/without_skill/run-1/timing.json",
       {"total_tokens": 100, "duration_ms": 1000, "total_duration_seconds": 1.0})

    # What aggregate_benchmark.py actually emits for the tree above, copied
    # from a real run of it: with_skill is excluded entirely, so NO primary
    # configuration produced a usable run. `primary` is null and the survivor
    # stays labelled baseline -- it is deliberately not promoted, and the
    # aggregation exits non-zero. The viewer must say the comparison is
    # incomplete rather than presenting the baseline as the subject, and must
    # not re-infer a primary that the aggregator explicitly declined to name.
    wj("malformed-run/iteration-1/benchmark.json", {
        "primary": None,
        "baseline": "without_skill",
        "metadata": {
            "skill_name": "misnamed",
            "timestamp": "2026-07-31T00:00:00Z",
            "evals_run": [0],
            "runs_per_configuration": 1,
            "runs_per_configuration_by_config": {"without_skill": 1},
        },
        "runs": [
            run(0, "misnamed-run", "without_skill",
                result_of(bad_run_baseline, 1.0, 100), bad_run_baseline),
        ],
        "run_summary": {
            "without_skill": {
                "pass_rate": _stat(0.0, None, 0.0, 0.0, 1, 0),
                "time_seconds": _stat(1.0, None, 1.0, 1.0, 1, 0),
                "tokens": _stat(100.0, None, 100, 100, 1, 0),
                "abstention": _abstention(0, 1, 1, {}, 1),
                "runs": 1,
            },
            "delta": {
                "pass_rate": {"value": None, "formatted": "—",
                              "polarity": "higher_is_better", "better": None},
            },
        },
        "exclusions": [
            {
                "path": "iteration-1/eval-0-misnamed-run/with_skill/run-final",
                "reason": "run directory `run-final` is not `run-<K>` with an integer K; "
                          "expected e.g. iteration-1/eval-0-misnamed-run/with_skill/run-1",
                "errors": [],
            },
            {
                "path": "iteration-1/eval-0-misnamed-run/without_skill/run-1",
                "reason": condition_line(
                    "unpaired_evals",
                    "eval 0 ran under `without_skill` but not under any primary "
                    "configuration - none produced a usable run, so it is excluded from "
                    "every delta. It still counts toward `without_skill`'s own column, "
                    "which is why the columns and the delta cover different evals here"),
                "errors": [],
            },
        ],
        "layout_warnings": [],
        "notes": [],
    })

    # =======================================================================
    # mixed-exclusions: all three exclusion KINDS on one page
    #
    # "Excluded" stopped being one thing. A blanket "excluded from every number
    # on this page" is now false for two of the three, and a reader who sees a
    # run listed as excluded while its pass rate plainly still counts concludes
    # the page is inconsistent when it is being precise.
    # =======================================================================
    mixed_x = "mixed-exclusions/iteration-1"
    for eval_id, slug in ((0, "fully-dropped"), (1, "timing-only"), (2, "unpaired")):
        base_dir = mixed_x + "/eval-%d-%s" % (eval_id, slug)
        wj(base_dir + "/eval_metadata.json", {
            "eval_id": eval_id, "eval_name": slug,
            "prompt": "Task %d." % eval_id, "assertions": ["Check A"],
        })
        configs = ("with_skill", "without_skill") if eval_id != 2 else ("with_skill",)
        for config in configs:
            w(base_dir + "/" + config + "/run-1/outputs/out.txt", config + "\n")
            mx_exps = expectations(["Check A"], [config == "with_skill"],
                                   {0: "checked"})
            wj(base_dir + "/" + config + "/run-1/grading.json", {
                "expectations": mx_exps,
                "summary": summary_of(mx_exps),
            })
            wj(base_dir + "/" + config + "/run-1/timing.json",
               {"total_tokens": 100, "duration_ms": 2000, "total_duration_seconds": 2.0})

    def mx_run(eval_id, name, config, rate, time_s, tokens):
        exps = expectations(["Check A"], [bool(rate)], {0: "checked"})
        return run(eval_id, name, config, result_of(exps, time_s, tokens), exps)

    wj(mixed_x + "/benchmark.json", {
        "primary": "with_skill",
        "baseline": "without_skill",
        "metadata": {
            "skill_name": "mixed-exclusions",
            "timestamp": "2026-07-31T00:00:00Z",
            "evals_run": [0, 1, 2],
            "runs_per_configuration": 1,
        },
        "runs": [
            # eval 0's with_skill run is gone entirely (schema-invalid grading).
            mx_run(0, "fully-dropped", "without_skill", 0.0, 2.0, 100),
            # eval 1 kept both gradings; one lost only its timing.
            mx_run(1, "timing-only", "with_skill", 1.0, None, None),
            mx_run(1, "timing-only", "without_skill", 0.0, 2.0, 100),
            # eval 2 ran under with_skill only: counted in its own column,
            # excluded from the delta.
            mx_run(2, "unpaired", "with_skill", 1.0, 2.0, 100),
        ],
        "run_summary": {
            "with_skill": {
                "pass_rate": _stat(1.0, 0.0, 1.0, 1.0, 2, 0),
                "time_seconds": _stat(2.0, None, 2.0, 2.0, 1, 1),
                "tokens": _stat(100.0, None, 100, 100, 1, 1),
                "abstention": _abstention(0, 2, 2, {}, 2),
                "runs": 2,
            },
            "without_skill": {
                "pass_rate": _stat(0.0, 0.0, 0.0, 0.0, 2, 0),
                "time_seconds": _stat(2.0, 0.0, 2.0, 2.0, 2, 0),
                "tokens": _stat(100.0, 0.0, 100, 100, 2, 0),
                "abstention": _abstention(0, 2, 2, {}, 2),
                "runs": 2,
            },
            "delta": {
                "pass_rate": {"value": 1.0, "formatted": "+1.00",
                              "polarity": "higher_is_better", "better": True},
            },
        },
        "exclusions": [
            # dropped: the whole run is out of every figure.
            {
                "path": "iteration-1/eval-0-fully-dropped/with_skill/run-1/grading.json",
                "reason": condition_line("schema_invalid",
                                         "failed grading.json schema validation"),
                "errors": ["expectations[0]: has 'met' where the contract has 'verdict'"],
            },
            # timing only: the grading still counts.
            {
                "path": "iteration-1/eval-1-timing-only/with_skill/run-1/timing.json",
                "reason": condition_line(
                    "schema_invalid",
                    "failed timing.json schema validation, so this run's tokens and "
                    "duration are excluded and render as —. Its grading still counts"),
                "errors": ["total_tokens: -500 is negative"],
            },
            # pairing: out of the delta, in its own column.
            {
                "path": "iteration-1/eval-2-unpaired/with_skill/run-1",
                "reason": condition_line(
                    "unpaired_evals",
                    "eval 2 ran under `with_skill` but not under `without_skill`, so it "
                    "is excluded from every delta. It still counts toward `with_skill`'s "
                    "own column, which is why the columns and the delta cover different "
                    "evals here"),
                "errors": [],
            },
        ],
        "layout_warnings": [],
        "notes": [],
    })

    # =======================================================================
    # abstain: ternary verdicts end to end
    #
    # Three shapes on one page, and no two of them may render alike:
    #
    #   eval 0  every check abstained, in both configurations. There is NO
    #           pass rate. Every rate cell must read as absent -- a `0%`
    #           anywhere here says the skill failed everything, about a run
    #           nothing was ruled against.
    #   eval 1  100% over 2 ruled-on checks with 9 abstentions, against 100%
    #           over 11 ruled-on checks. Both configurations read `100%`. The
    #           abstention counts are the only thing separating a thin result
    #           from a complete one, so they travel beside every rate.
    #   eval 2  one abstention of each typed reason, so the two are visible on
    #           screen and distinguishable from each other.
    # =======================================================================
    ab = "abstain/iteration-1"

    ab0_texts = ["Follows the documented ordering of steps",
                 "Handles the malformed row"]
    ab0 = expectations(ab0_texts, ["abstain", "abstain"],
                       {0: "no transcript_path was supplied; outputs/ holds "
                           "report.csv only",
                        1: "the malformed-row case was not exercised by this run"},
                       reasons={0: "jurisdiction", 1: "evidence"})

    ab1_texts = ["Check %d" % (i + 1) for i in range(11)]
    ab1_primary = expectations(
        ab1_texts, [True, True] + ["abstain"] * 9)
    ab1_baseline = expectations(ab1_texts, [True] * 11)

    ab2_texts = ["Uses the house date format", "Was written by the skill"]
    ab2 = expectations(ab2_texts, ["abstain", "abstain"],
                       reasons={0: "evidence", 1: "jurisdiction"})

    ab_evals = (
        (0, "every-check-abstained", ab0, ab0),
        (1, "thin-versus-complete", ab1_primary, ab1_baseline),
        (2, "both-reasons", ab2, ab2),
    )

    for eval_id, slug, primary_exps, baseline_exps in ab_evals:
        eval_dir = ab + "/eval-%d-%s" % (eval_id, slug)
        wj(eval_dir + "/eval_metadata.json", {
            "eval_id": eval_id, "eval_name": slug,
            "prompt": "Task %d." % eval_id,
            "assertions": [e["text"] for e in primary_exps],
        })
        for config, exps in (("with_skill", primary_exps),
                             ("without_skill", baseline_exps)):
            w(eval_dir + "/" + config + "/run-1/outputs/out.txt", config + "\n")
            wj(eval_dir + "/" + config + "/run-1/grading.json", {
                "expectations": exps,
                "summary": summary_of(exps),
            })
            wj(eval_dir + "/" + config + "/run-1/timing.json",
               {"total_tokens": 100, "duration_ms": 2000,
                "total_duration_seconds": 2.0})

    ab_runs = []
    for eval_id, slug, primary_exps, baseline_exps in ab_evals:
        ab_runs.append(run(eval_id, slug, "with_skill",
                           result_of(primary_exps, 2.0, 100), primary_exps))
        ab_runs.append(run(eval_id, slug, "without_skill",
                           result_of(baseline_exps, 2.0, 100), baseline_exps))

    wj(ab + "/benchmark.json", {
        "primary": "with_skill",
        "baseline": "without_skill",
        "metadata": {
            "skill_name": "abstain-demo",
            "timestamp": "2026-07-31T00:00:00Z",
            "evals_run": [0, 1, 2],
            "runs_per_configuration": 3,
            "runs_per_configuration_by_config": {"with_skill": 3,
                                                 "without_skill": 3},
        },
        "runs": ab_runs,
        "run_summary": {
            # with_skill: eval 0 and eval 2 have no rate at all, eval 1 is
            # 100%. One measured value out of three runs -- and stddev stays
            # null, because one sample has no spread.
            "with_skill": {
                "pass_rate": _stat(1.0, None, 1.0, 1.0, 1, 2),
                "time_seconds": _stat(2.0, 0.0, 2.0, 2.0, 3, 0),
                "tokens": _stat(100.0, 0.0, 100, 100, 3, 0),
                "abstention": _abstention(
                    13, 2, 15, {"jurisdiction": 2, "evidence": 11}, 3, 2),
                "runs": 3,
            },
            "without_skill": {
                "pass_rate": _stat(1.0, None, 1.0, 1.0, 1, 2),
                "time_seconds": _stat(2.0, 0.0, 2.0, 2.0, 3, 0),
                "tokens": _stat(100.0, 0.0, 100, 100, 3, 0),
                "abstention": _abstention(
                    4, 11, 15, {"jurisdiction": 2, "evidence": 2}, 3, 2),
                "runs": 3,
            },
            "delta": {
                "pass_rate": {"value": 0.0, "formatted": "+0.00",
                              "polarity": "higher_is_better", "better": None},
                "time_seconds": {"value": 0.0, "formatted": "+0.0",
                                 "polarity": "lower_is_better", "better": None},
                "tokens": {"value": 0.0, "formatted": "+0",
                           "polarity": "lower_is_better", "better": None},
            },
        },
        "exclusions": [],
        "layout_warnings": [],
        "notes": [],
    })

    # =======================================================================
    # reason-taxonomy: every reason state on one page
    #
    # Four states an abstention's reason can be in, and the page must draw four
    # different things:
    #
    #   jurisdiction     someone else can rule on it -> reassign the judge
    #   evidence         this judge could have ruled -> supply the artifact
    #   underspecified   NOBODY could rule on it     -> rewrite the assertion
    #   "busy"           a value outside the enum: recorded, but this build has
    #                    no meaning for it
    #   (absent)         nothing was recorded at all
    #
    # The third and fourth are the ones that were wrong. `underspecified` is
    # schema-valid and the page's whitelist stopped at two, so it rendered as
    # "abstained: reason not recorded" - present data displayed as absent,
    # which sends the one person who could fix the sentence off to fix the
    # grader instead. The fourth shares that failure: a value the page does not
    # recognize is still a value, and reporting it as "not recorded" blames the
    # producer for an omission that never happened.
    #
    # `"busy"` and the absent reason are both schema-INVALID: validate_grading
    # rejects them and the aggregator excludes them, so neither can reach a
    # real benchmark by itself. They are here because this page is also opened
    # on hand-edited files and on files written by a grader that is ahead of or
    # behind the contract, and what it says then is the whole point of the
    # distinction.
    # =======================================================================
    rt = "reason-taxonomy/iteration-1"
    rt_texts = [
        "Emits a CSV file",
        "Totals row is last",
        "Follows the documented ordering of steps",
        "Handles the malformed row",
        "Reads well",
        "Meets the bar",
        "Is correct",
    ]
    rt_primary = expectations(
        rt_texts,
        [True, False, "abstain", "abstain", "abstain", "abstain", "abstain"],
        {
            2: "the run kept no transcript, and the ordering is the panel "
               "lead's call rather than this seat's",
            3: "outputs/ holds report.csv only; the malformed-row case was "
               "never exercised",
            4: "“well” is not defined anywhere - no threshold, no comparison, "
               "no rubric entry names it",
            5: "the file records a reason this page has no meaning for",
            6: "the file records no reason at all",
        },
        reasons={2: "jurisdiction", 3: "evidence", 4: "underspecified",
                 # Not in the enum, and deliberately not a typo of one of the
                 # three: a near-miss would test spelling, and what is under
                 # test is what the page says about a value it does not know.
                 5: "busy",
                 6: None},
    )
    # The baseline ruled on all seven, so every row in the comparison table has
    # a verdict on one side and an abstention on the other. A reader comparing
    # the two columns is exactly who needs the reason to be legible.
    rt_baseline = expectations(rt_texts, [True] * 7)

    rt_dir = rt + "/eval-0-four-reasons"
    wj(rt_dir + "/eval_metadata.json", {
        "eval_id": 0, "eval_name": "four-reason-states",
        "prompt": "Produce the report.",
        "assertions": rt_texts,
    })
    for config, exps in (("with_skill", rt_primary),
                         ("without_skill", rt_baseline)):
        w(rt_dir + "/" + config + "/run-1/outputs/report.csv",
          "name,total\nacme,42\n")
        wj(rt_dir + "/" + config + "/run-1/grading.json", {
            "expectations": exps,
            "summary": summary_of(exps),
        })
        wj(rt_dir + "/" + config + "/run-1/timing.json",
           {"total_tokens": 100, "duration_ms": 2000,
            "total_duration_seconds": 2.0})

    wj(rt + "/benchmark.json", {
        "primary": "with_skill",
        "baseline": "without_skill",
        "metadata": {
            "skill_name": "reason-taxonomy-demo",
            "timestamp": "2026-07-31T00:00:00Z",
            "evals_run": [0],
            "runs_per_configuration": 1,
            "runs_per_configuration_by_config": {"with_skill": 1,
                                                 "without_skill": 1},
        },
        "runs": [
            run(0, "four-reason-states", "with_skill",
                result_of(rt_primary, 2.0, 100), rt_primary),
            run(0, "four-reason-states", "without_skill",
                result_of(rt_baseline, 2.0, 100), rt_baseline),
        ],
        "run_summary": {
            "with_skill": {
                "pass_rate": _stat(0.5, None, 0.5, 0.5, 1, 0),
                "time_seconds": _stat(2.0, None, 2.0, 2.0, 1, 0),
                "tokens": _stat(100.0, None, 100, 100, 1, 0),
                # Two of the five carry no reason the enum defines, so they
                # pool under `untyped` - which is the aggregator's honest
                # answer and is not the same claim the page used to make about
                # them individually.
                "abstention": _abstention(
                    5, 2, 7,
                    {"jurisdiction": 1, "evidence": 1, "underspecified": 1,
                     "untyped": 2}, 1),
                "runs": 1,
            },
            "without_skill": {
                "pass_rate": _stat(1.0, None, 1.0, 1.0, 1, 0),
                "time_seconds": _stat(2.0, None, 2.0, 2.0, 1, 0),
                "tokens": _stat(100.0, None, 100, 100, 1, 0),
                "abstention": _abstention(0, 7, 7, {}, 1),
                "runs": 1,
            },
            "delta": {
                "pass_rate": {"value": -0.5, "formatted": "-0.50",
                              "polarity": "higher_is_better", "better": False},
                "time_seconds": {"value": 0.0, "formatted": "+0.0",
                                 "polarity": "lower_is_better", "better": None},
                "tokens": {"value": 0.0, "formatted": "+0",
                           "polarity": "lower_is_better", "better": None},
            },
        },
        "exclusions": [],
        "layout_warnings": [],
        "notes": [],
    })

    # The same tree, graded under the PREVIOUS contract: boolean `passed`, no
    # `abstained`, and `pass_rate` computed over `total`. Not malformed, just
    # last version's format. The page must say so and must NOT translate the
    # booleans -- a `false` there means either "verified false" or "could not
    # tell", and picking one is the invention C16 removed.
    prev = "previous-contract/iteration-1/eval-0-bool-verdicts"
    wj(prev + "/eval_metadata.json", {
        "eval_id": 0, "eval_name": "boolean-verdicts",
        "prompt": "Task graded before the ternary contract.",
        "assertions": ["Check A", "Check B"],
    })
    for config, flags in (("with_skill", [True, False]),
                          ("without_skill", [False, False])):
        w(prev + "/" + config + "/run-1/outputs/out.txt", config + "\n")
        legacy_exps = [
            {"text": text, "passed": ok, "evidence": "checked"}
            for text, ok in zip(["Check A", "Check B"], flags)
        ]
        passed = sum(1 for f in flags if f)
        wj(prev + "/" + config + "/run-1/grading.json", {
            "expectations": legacy_exps,
            "summary": {"passed": passed, "failed": len(flags) - passed,
                        "total": len(flags), "pass_rate": passed / len(flags)},
        })
        wj(prev + "/" + config + "/run-1/timing.json",
           {"total_tokens": 100, "duration_ms": 2000,
            "total_duration_seconds": 2.0})

    return target


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    build(target)
    print("eval-viewer fixtures written under " + str(target))


if __name__ == "__main__":
    main()
