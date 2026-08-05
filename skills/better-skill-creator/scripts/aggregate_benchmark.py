#!/usr/bin/env python3
"""
Aggregate individual run results into benchmark summary statistics.

Reads grading.json / timing.json / eval_metadata.json from a workspace
iteration directory and produces benchmark.json and benchmark.md.

Usage:
    python -m scripts.aggregate_benchmark <iteration_dir> --skill-name NAME

Example:
    python -m scripts.aggregate_benchmark ../my-skill-workspace/iteration-1 \\
        --skill-name my-skill

Canonical layout - `run-<K>/` is ALWAYS present, and a single
run is `run-1/`, never a flattened config directory:

    <iteration_dir>/
      eval-<ID>-<descriptive-slug>/
        eval_metadata.json
        <config>/                  # with_skill | without_skill | old_skill
          run-<K>/
            outputs/
            grading.json
            timing.json

Two legacy shapes are still read, each with a visible deprecation warning:
a config directory holding grading.json directly (normalized to `run-1`), and
eval directories under a `runs/` subdirectory.

Severity is not decided here. `scripts.utils` holds the one
severity table; this script, `scripts.validate_grading` and `scripts.preflight`
all classify from it and all print the `C12:<condition>=<severity>` token, so
the three verdicts for one workspace can be diffed instead of trusted. What
this script *does* with a severity is its own business, under one stated rule:

  * an error-severity condition whose consequence is visible in the artifact -
    a schema-invalid `grading.json` or `timing.json`, listed in `exclusions`
    with the validator's messages - leaves the benchmark trustworthy over what
    remains, so the run exits 0 and the exclusion speaks for itself;
  * an error-severity condition that makes the artifact unsound - graded runs
    no reader can see, or a delta whose two sides did not run the same evals -
    exits non-zero.

What this script will NOT do (absent data is absent, never zero):

  * Zero discovered runs exits non-zero, prints every path searched and the
    layout expected, and writes no benchmark. It used to print `Delta: +0.00`
    and exit 0 over an empty `runs` array - a confident, well-formatted answer
    entirely disconnected from the data.
  * A missing timing.json yields `null` for that run's tokens and duration, and
    the rendered cell is an em dash. It is never 0, and 0 is never averaged in.
  * `tokens` comes from timing.json whenever timing.json exists, independently
    of any other timing source, and `tokens` is the only quantity of its kind
    emitted - never a character count wearing that label.
  * A grading.json **or timing.json** that fails schema validation is named,
    counted, and excluded from the statistics, with the exclusion recorded in
    `benchmark.json` (`exclusions`) and printed in `benchmark.md`. The timing
    half of that sentence was missing: this script validated one input file and
    accepted any bytes at all in the other, so `{"total_tokens": -500000,
    "total_duration_seconds": -3600.0}` was averaged and rendered as
    `-3600.0s | -3610.0 | better` at exit 0.
  * A delta is computed only over the evals **both** configurations ran. Where
    eval-0 scored 0% in both and eval-1 ran only under `with_skill` at 100%,
    the pooled means reported `+0.50 better` - a favourable number whose entire
    magnitude came from an eval the baseline never attempted, over data whose
    one genuine comparison showed no difference at all.
  * A run whose expectations **all abstained** has `pass_rate: null`, which
    `calculate_stats` drops rather than averages. It is not a 0%
    run, it did not happen to score badly, and it contributes nothing to a
    delta. Where that is true of every run of a configuration, that
    configuration's `pass_rate` block is `null` outright and no delta is
    reported - the same treatment a missing `timing.json` gets, for the same
    reason.

Abstention is reported next to every rate and is **not** a delta metric. Each
delta declares a polarity and abstention has no honest one: a judge that
abstains freely produces a benchmark that measures nothing while looking
rigorous, and a judge that never abstains is the defect the abstain verdict
exists to close. Signing that number in either direction would be this file
taking a side on a question the data does not answer. So
`run_summary.<config>.abstention`
carries the counts and the rate, `benchmark.md` prints them beside the pass
rate and per eval, and the judgment is left to the reader - who now has the
number needed to notice a judge that has drifted.

`runs[].result` deliberately carries no `output_chars`, `tool_calls`, or
`errors`. Their only source was `execution_metrics`, fed by a `metrics.json`
that no agent has ever produced and that the grader rewrite retired. Emitting
them as permanent nulls is not neutral - three always-empty columns read as
"measured, and the answer was nothing", which is the exact ambiguity this
rewrite exists to remove. The rule is that nothing produces them, so the
requirement is gone rather than the producer added. If a real byte-size
measurement ever lands here it gets a size label, never a token one.

Comparison direction: benchmark.json carries explicit `primary`
and `baseline` keys naming the configurations by role. They appear at the top
level and nowhere else - two copies of one contract element with nothing
cross-checking them is precisely the drift this rewrite closes. Ordering is by
role, not by `sorted()` - `old_skill` used to sort ahead of `with_skill` and
invert the sign of every delta on the improve-an-existing-skill path. Every
delta is `primary - baseline`, and carries its own polarity so a presenter can
color by goodness rather than by sign. Polarity is emitted per delta only;
there is no second top-level map that would have to agree with it.

Shape of `run_summary`:

    {
      "<config>": {
        "pass_rate":    {"mean","stddev","min","max","n","missing"} | null,
        "time_seconds": ... | null,
        "tokens":       ... | null,
        "abstention":   {"abstained","graded","total","rate",
                         "reasons":{<one key per validate_grading.ABSTAIN_REASONS>,
                                    "untyped"},
                         "runs","runs_without_pass_rate"} | null,
        "runs": <int>
      },
      "delta": {
        "<metric>": {"value": <float|null>, "formatted": "<str>",
                     "polarity": "higher_is_better"|"lower_is_better",
                     "better": true|false|null}
      }
    }

`stddev` is null when fewer than two runs were measured: one sample has no
sample standard deviation, and `± 0%` under a header claiming three runs is the
single most misleading thing this file used to emit.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.utils import (
    FLAT_AND_RUN_DIRS,
    LEGACY_FLAT_LAYOUT,
    SCHEMA_INVALID,
    UNDISCOVERABLE_GRADING,
    UNPAIRED_EVALS,
    ZERO_RUNS,
    condition_line,
    configure_console,
)
from scripts.validate_grading import (
    ABSENT,
    ABSTAIN_REASON_MEANINGS,
    ABSTAIN_REASONS,
    BASELINE_ROLE_CONFIGS,
    CANONICAL_LAYOUT,
    NON_CONFIG_DIRS,
    PASS_RATE_RULE,
    PRIMARY_ROLE_CONFIGS,
    RUN_DIR_RE,
    eval_id_from_dir_name,
    is_eval_dir,
    read_json_file,
    validate_grading_file,
    validate_timing_file,
)

# Each metric declares which direction is an improvement.
METRIC_POLARITY = {
    "pass_rate": "higher_is_better",
    "time_seconds": "lower_is_better",
    "tokens": "lower_is_better",
}

DELTA_FORMATS = {
    "pass_rate": "{:+.2f}",
    "time_seconds": "{:+.1f}",
    "tokens": "{:+.0f}",
}

#: What to DO about each typed abstention, keyed by - never restating -
#: `validate_grading.ABSTAIN_REASONS`. The enum and the one-line meanings live
#: there; only the repair sentence is here, because the repair is the half a
#: benchmark reader acts on and the meanings deliberately state the procedure
#: rather than the action.
#:
#: `_abstention_legend` walks the ENUM, not this dict, so a reason added to the
#: contract is listed with its meaning whether or not anyone remembers to write
#: a repair for it - it can go unexplained, but it can never go missing. A
#: reason with no repair here is a test failure
#: (`tests/test_benchmark_contracts.py`), not a silently thinner legend: this
#: file and `eval-viewer/viewer.html` were both hand-maintained copies of a
#: two-member enum when the enum went to three, and each has to be caught by
#: something other than whoever notices.
ABSTAIN_REASON_REPAIRS = {
    "jurisdiction": "reassign the judge - a standard that settles it exists, "
                    "and somebody who is not this judge holds it",
    "evidence": "supply the missing artifact - a transcript, the input file - "
                "and grade the run again",
    "underspecified": "rewrite the assertion - no judge could rule on it as "
                      "written, because it names no property of the artifact, "
                      "and this repair is the author's alone",
}


# --------------------------------------------------------------------------
# Statistics
#
# The arithmetic here was independently verified correct and is unchanged:
# mean, Bessel-corrected (n-1) sample stddev, min, max, rounded to 4 places.
# The only change is that unmeasured values are dropped rather than counted as
# zero, and that a sample of one reports `stddev: null` instead of `0.0`.
# --------------------------------------------------------------------------

def calculate_stats(values: list) -> dict | None:
    """
    mean / stddev / min / max over the *measured* entries of `values`.

    `None` entries are unmeasured and are excluded, not zeroed. Returns None
    when nothing at all was measured - the caller renders that as unknown.
    """
    measured = [v for v in values if v is not None]
    missing = len(values) - len(measured)

    if not measured:
        return None

    n = len(measured)
    mean = sum(measured) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in measured) / (n - 1)
        stddev = round(math.sqrt(variance), 4)
    else:
        # One sample has no sample standard deviation. Reporting 0.0 here is
        # what let a benchmark claim "85% ± 0%" under "3 runs per
        # configuration" from a single run.
        stddev = None

    return {
        "mean": round(mean, 4),
        "stddev": stddev,
        "min": round(min(measured), 4),
        "max": round(max(measured), 4),
        "n": n,
        "missing": missing,
    }


def abstention_stats(runs: list) -> dict | None:
    """Pooled abstention counts over a set of runs.

    Counts, not a mean of rates: `rate` is `abstained / total` over every
    expectation in every run, so a run with twenty expectations weighs twenty
    times a run with one. That is the right weighting for the question this
    number answers - "how much of what this judge was asked did it decline to
    rule on" - and it is deliberately a different weighting from `pass_rate`'s
    macro average over runs.

    `reasons` splits the abstentions by their typed reason, because each one
    means a different thing and calls for a different repair. A wall of
    `jurisdiction` says the expectation set is asking this seat questions it
    cannot answer; a wall of `evidence` says the runs are not producing what a
    ruling needs; a wall of `underspecified` says the assertions themselves
    name nothing to check, and that one is the eval author's to fix. The keys
    come from `ABSTAIN_REASONS`, so the split follows the enum rather than a
    second copy of it. `untyped` counts abstentions with no valid reason -
    schema-invalid gradings never reach here, so it stays 0 in practice and is
    emitted rather than assumed.

    Returns None when no run carried usable counts, which renders as unknown
    rather than as "nobody abstained".
    """
    abstained = graded = total = 0
    reasons = {reason: 0 for reason in ABSTAIN_REASONS}
    reasons["untyped"] = 0
    counted = 0
    without_rate = 0

    for run in runs:
        values = (run.get("passed"), run.get("failed"),
                  run.get("abstained"), run.get("total"))
        if run.get("pass_rate") is None:
            without_rate += 1
        if any(isinstance(v, bool) or not isinstance(v, int) for v in values):
            continue
        passed, failed, abstentions, run_total = values
        abstained += abstentions
        graded += passed + failed
        total += run_total
        counted += 1
        for exp in run.get("expectations") or []:
            if not isinstance(exp, dict) or exp.get("verdict") != "abstain":
                continue
            reason = exp.get("abstainReason")
            reasons[reason if reason in reasons else "untyped"] += 1

    if counted == 0:
        return None

    return {
        "abstained": abstained,
        "graded": graded,
        "total": total,
        # Again: no expectations at all is unknown, not 0%.
        "rate": round(abstained / total, 4) if total else None,
        "reasons": reasons,
        "runs": counted,
        "runs_without_pass_rate": without_rate,
    }


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------

def _eval_sort_key(value):
    """Sort integer eval ids numerically and anything else after, by text."""
    if isinstance(value, bool) or not isinstance(value, int):
        return (1, 0, str(value))
    return (0, value, "")


def _read_timing(run_dir: Path, warnings: list, exclusions: list) -> tuple:
    """
    Returns (time_seconds, tokens) from run_dir/timing.json.

    Either may be None. timing.json is read unconditionally whenever it exists
    - the old gate ("only if grading.json had no timing block") meant a grader
    that followed its own prompt guaranteed the real token count was discarded.

    The file goes through `validate_timing_file`, the same validator preflight
    uses, and a failure excludes its numbers exactly as a failed grading.json
    excludes its run. Without that, this function type-checked and nothing
    else: a timing.json of `{"total_tokens": -500000,
    "total_duration_seconds": -3600.0}` was averaged, differenced, and rendered
    as `-3600.0s | -3610.0 | better` at exit 0. The exclusion discipline was
    written for both input files, not just the graded one.
    """
    timing_path = run_dir / "timing.json"
    if not timing_path.is_file():
        warnings.append(
            f"{run_dir}: no timing.json - tokens and duration are unknown for "
            f"this run and render as {ABSENT}"
        )
        return None, None

    schema_errors, _ = validate_timing_file(timing_path)
    if schema_errors:
        exclusions.append({
            "path": str(timing_path),
            "reason": condition_line(
                SCHEMA_INVALID,
                "failed timing.json schema validation, so this run's tokens "
                f"and duration are excluded and render as {ABSENT}. Its "
                "grading still counts"),
            "errors": schema_errors,
        })
        return None, None

    data, error = read_json_file(timing_path)
    if error is not None:
        warnings.append(f"{timing_path}: {error} - tokens and duration unknown")
        return None, None
    if not isinstance(data, dict):
        warnings.append(f"{timing_path}: top level is not an object - "
                        f"tokens and duration unknown")
        return None, None

    def number(field, types):
        value = data.get(field)
        if value is None:
            warnings.append(f"{timing_path}: no '{field}' - renders as {ABSENT}")
            return None
        if isinstance(value, bool) or not isinstance(value, types):
            warnings.append(
                f"{timing_path}: '{field}' is {type(value).__name__} "
                f"({value!r}), not a number - treated as unknown"
            )
            return None
        return value

    seconds = number("total_duration_seconds", (int, float))
    if seconds is None:
        ms = number("duration_ms", (int,)) if "duration_ms" in data else None
        if ms is not None:
            seconds = ms / 1000.0
    tokens = number("total_tokens", (int,))
    return seconds, tokens


def _collect_runs(config_dir: Path, warnings: list, exclusions: list) -> list:
    """Return [(run_number, run_dir)] for a configuration directory."""
    runs = []
    malformed = []
    for child in sorted(config_dir.iterdir()):
        if not child.is_dir():
            continue
        match = RUN_DIR_RE.match(child.name)
        if match:
            runs.append((int(match.group(1)), child))
        elif child.name.startswith("run-"):
            malformed.append(child)

    for child in malformed:
        exclusions.append({
            "path": str(child),
            "reason": (f"run directory `{child.name}` is not `run-<K>` with an "
                       f"integer K; expected e.g. {config_dir / 'run-1'}"),
            "errors": [],
        })

    if runs:
        runs = sorted(runs)
        if (config_dir / "grading.json").is_file():
            # R8: both shapes in one configuration. The run directories win and
            # the flat file is dropped - silently, before this warning existed,
            # while `validate_grading` reported that "readers normalize it to
            # run-1". Naming which file was used is the whole fix.
            used = ", ".join(str(d) for _, d in runs)
            warnings.append(condition_line(
                FLAT_AND_RUN_DIRS,
                f"{config_dir / 'grading.json'} is NOT being read; the run "
                f"director{'y' if len(runs) == 1 else 'ies'} beside it ({used}) "
                f"{'is' if len(runs) == 1 else 'are'} what this benchmark uses. "
                f"Move or delete the flat file"))
        return runs

    if (config_dir / "grading.json").is_file():
        # Legacy flat layout. Reading it is permitted, but only by
        # normalizing to run-1 and saying so out loud.
        warnings.append(
            f"DEPRECATED LAYOUT: {condition_line(LEGACY_FLAT_LAYOUT)} "
            f"{config_dir} holds grading.json directly; reading it as run-1. "
            f"The canonical layout expects "
            f"{config_dir / 'run-1' / 'grading.json'}"
        )
        return [(1, config_dir)]

    if (config_dir / "outputs").is_dir():
        exclusions.append({
            "path": str(config_dir),
            "reason": (f"has an outputs/ directory but no run-<K>/ and no "
                       f"grading.json; expected "
                       f"{config_dir / 'run-1' / 'grading.json'}"),
            "errors": [],
        })
    return []


def _undiscoverable(child: Path) -> dict:
    """An exclusion entry for a directory holding graded runs nobody walks.

    This is an error, not a warning: unlike an excluded run it
    is not merely dropped from the statistics, it is absent from the artifact
    entirely. The spend is already sunk and the result is invisible.
    """
    return {
        "path": str(child),
        "reason": condition_line(
            UNDISCOVERABLE_GRADING,
            f"`{child.name}` holds graded runs but is not a discoverable eval "
            f"directory, so its runs are NOT in this benchmark. Rename it "
            f"`eval-<ID>-{child.name}` or add "
            f"{child / 'eval_metadata.json'}"),
        "errors": [],
    }


def discover_runs(benchmark_dir: Path) -> dict:
    """
    Walk the iteration directory and return every usable run.

    Returns {"results", "eval_names", "warnings", "exclusions", "searched"}.

    `exclusions` carries every workspace condition of error severity that
    the walk found, each with the path it applies to and the shared sentence
    for that condition; `warnings` carries the warning-severity ones. Neither
    list decides an exit code here - `main` does that, from the severities.
    """
    warnings: list[str] = []
    exclusions: list[dict] = []
    searched: list[str] = []

    search_dir = None
    for candidate in (benchmark_dir, benchmark_dir / "runs"):
        searched.append(str(candidate))
        if not candidate.is_dir():
            continue
        if any(is_eval_dir(p) for p in candidate.iterdir() if p.is_dir()):
            search_dir = candidate
            break

    if search_dir is None:
        # Nothing discoverable. Say what was rejected and why - a directory
        # named for what it tests rather than `eval-<ID>-...` is the common
        # cause and used to produce a silent all-zero benchmark.
        for candidate in (benchmark_dir, benchmark_dir / "runs"):
            if not candidate.is_dir():
                continue
            for child in sorted(candidate.iterdir()):
                if child.is_dir() and any(child.rglob("grading.json")):
                    exclusions.append(_undiscoverable(child))
        return {"results": {}, "eval_names": {}, "warnings": warnings,
                "exclusions": exclusions, "dropped_runs": [],
                "searched": searched}

    if search_dir.name == "runs":
        warnings.append(
            f"DEPRECATED LAYOUT: eval directories found under {search_dir}. "
            f"The canonical layout puts them directly under {benchmark_dir}"
        )

    for child in sorted(search_dir.iterdir()):
        if child.is_dir() and not is_eval_dir(child) and any(child.rglob("grading.json")):
            exclusions.append(_undiscoverable(child))

    results: dict[str, list] = {}
    eval_names: dict = {}
    seen_eval_dirs: dict = {}
    seen_run_keys: dict = {}
    # Runs that exist on disk and contribute nothing. Kept separately from
    # `exclusions` (which is prose keyed by path) because the pairing check
    # needs to know *which side lost which run*: an exclusion that shrinks one
    # configuration's run set and not the other's moves the delta without
    # invalidating it, which is R7's defect wearing different clothes.
    dropped_runs: list[dict] = []

    eval_dirs = sorted(
        (p for p in search_dir.iterdir() if p.is_dir() and is_eval_dir(p)),
        key=lambda p: p.name,
    )

    for eval_idx, eval_dir in enumerate(eval_dirs):
        dir_eval_id = eval_id_from_dir_name(eval_dir.name)
        eval_id = dir_eval_id
        eval_name = None

        metadata_path = eval_dir / "eval_metadata.json"
        if metadata_path.is_file():
            data, error = read_json_file(metadata_path)
            if error is not None:
                warnings.append(f"{metadata_path}: {error}")
            elif isinstance(data, dict):
                meta_id = data.get("eval_id")
                if isinstance(meta_id, int) and not isinstance(meta_id, bool):
                    if dir_eval_id is not None and meta_id != dir_eval_id:
                        warnings.append(
                            f"{metadata_path}: eval_id is {meta_id} but the "
                            f"directory says {dir_eval_id} (they must be "
                            f"equal); using {meta_id}"
                        )
                    eval_id = meta_id
                elif meta_id is not None:
                    warnings.append(
                        f"{metadata_path}: eval_id is "
                        f"{type(meta_id).__name__} ({meta_id!r}), not an "
                        f"integer; using the directory name instead"
                    )
                name = data.get("eval_name")
                if isinstance(name, str) and name.strip():
                    eval_name = name.strip()
                else:
                    warnings.append(
                        f"{metadata_path}: no usable 'eval_name'; the rendered "
                        f"benchmark will fall back to the eval id"
                    )
        else:
            warnings.append(
                f"{metadata_path} is missing; this eval has no name and no "
                f"prompt in the review artifacts"
            )

        if eval_id is None:
            eval_id = eval_idx
            warnings.append(
                f"{eval_dir}: could not determine an eval id from the directory "
                f"name or metadata; using positional index {eval_idx}"
            )
        # Two directories declaring one eval_id pool four runs from two
        # different evals under one key, with different eval_names, and every
        # consumer that keys on (eval_id, configuration, run_number) - the
        # viewer's per-eval breakdown does - gets colliding rows.
        if eval_id in seen_eval_dirs:
            warnings.append(
                f"{eval_dir}: eval_id {eval_id!r} was already claimed by "
                f"{seen_eval_dirs[eval_id]}. Their runs are pooled under one id "
                f"and any consumer keyed on (eval_id, configuration, "
                f"run_number) will collide. Give each eval a distinct id"
            )
        else:
            seen_eval_dirs[eval_id] = str(eval_dir)
        eval_names[eval_id] = eval_name

        stray = eval_dir / "grading.json"
        if stray.is_file():
            # Graders have been observed writing here. Nothing walks it, so
            # without this it is invisible rather than excluded.
            exclusions.append({
                "path": str(stray),
                "reason": condition_line(
                    UNDISCOVERABLE_GRADING,
                    f"it sits at the eval-directory root, where no reader "
                    f"looks. It contributes nothing; it belongs at "
                    f"{eval_dir / '<config>' / 'run-<K>' / 'grading.json'}"),
                "errors": [],
            })

        for config_dir in sorted(eval_dir.iterdir()):
            if not config_dir.is_dir() or config_dir.name in NON_CONFIG_DIRS:
                continue

            run_dirs = _collect_runs(config_dir, warnings, exclusions)
            if not run_dirs:
                continue

            config = config_dir.name
            results.setdefault(config, [])

            for run_number, run_dir in run_dirs:
                grading_file = run_dir / "grading.json"

                def drop(reason: str) -> None:
                    dropped_runs.append({
                        "configuration": config,
                        "eval_id": eval_id,
                        "run_number": run_number,
                        "path": str(run_dir),
                        "reason": reason,
                    })

                if not grading_file.exists():
                    exclusions.append({
                        "path": str(grading_file),
                        "reason": "grading.json not found",
                        "errors": [],
                    })
                    drop("no grading.json")
                    continue

                errors, file_warnings = validate_grading_file(grading_file)
                for warning in file_warnings:
                    warnings.append(f"{grading_file}: {warning}")
                if errors:
                    # Named, counted, excluded - and the exclusion
                    # is visible in both output artifacts.
                    exclusions.append({
                        "path": str(grading_file),
                        "reason": condition_line(
                            SCHEMA_INVALID,
                            "failed grading.json schema validation"),
                        "errors": errors,
                    })
                    drop("failed grading.json schema validation")
                    continue

                grading, error = read_json_file(grading_file)
                if error is not None or not isinstance(grading, dict):
                    exclusions.append({
                        "path": str(grading_file),
                        "reason": error or "top level is not an object",
                        "errors": [],
                    })
                    drop(error or "top level is not an object")
                    continue

                # `run-1` and `run-01` both match `^run-(\d+)$` and both parse
                # to 1, so two runs with different results used to land on one
                # (eval_id, configuration, run_number) key in silence.
                run_key = (eval_id, config, run_number)
                if run_key in seen_run_keys:
                    warnings.append(
                        f"{run_dir}: run number {run_number} is already taken "
                        f"by {seen_run_keys[run_key]} for eval {eval_id!r} / "
                        f"{config}. Both are kept, but they share a key that "
                        f"consumers treat as unique"
                    )
                else:
                    seen_run_keys[run_key] = str(run_dir)

                summary = grading.get("summary", {})
                time_seconds, tokens = _read_timing(run_dir, warnings, exclusions)

                # `execution_metrics` is read by nothing here. Its
                # `output_chars` used to be assigned to `tokens` - characters
                # run roughly 4x tokens, so the substitution always landed in a
                # plausible range and never looked wrong.
                result = {
                    "eval_id": eval_id,
                    "eval_name": eval_name,
                    "run_number": run_number,
                    "run_dir": str(run_dir),
                    # `pass_rate` is null for a run whose expectations all
                    # abstained. It stays null all the way through:
                    # calculate_stats drops it, no delta uses it, and the
                    # rendered cell is an em dash. The 0.0 the previous
                    # contract produced here was a measurement of nothing.
                    "pass_rate": summary.get("pass_rate"),
                    "passed": summary.get("passed"),
                    "failed": summary.get("failed"),
                    "abstained": summary.get("abstained"),
                    "total": summary.get("total"),
                    "time_seconds": time_seconds,
                    "tokens": tokens,
                    "expectations": grading.get("expectations", []),
                }

                notes_summary = grading.get("user_notes_summary", {})
                notes = []
                if isinstance(notes_summary, dict):
                    for key in ("uncertainties", "needs_review", "workarounds"):
                        value = notes_summary.get(key, [])
                        if isinstance(value, list):
                            notes.extend(value)
                result["notes"] = notes

                results[config].append(result)

    return {"results": results, "eval_names": eval_names, "warnings": warnings,
            "exclusions": exclusions, "dropped_runs": dropped_runs,
            "searched": searched}


# --------------------------------------------------------------------------
# Roles and aggregation
# --------------------------------------------------------------------------

def resolve_roles(configs: list, primary_arg: str | None, baseline_arg: str | None):
    """
    Decide which configuration is primary and which is the baseline.

    Returns (primary, baseline, error_message). Either role may be None when
    only one configuration exists, and which one is None is decided by the
    surviving configuration's *name*, never by the fact that it survived:

    * only `with_skill`/`new_skill` -> primary, baseline None. This is the
      single-configuration record: no delta, rather than a delta against an
      invented zero.
    * only `without_skill`/`old_skill`/`baseline`/`no_skill` -> baseline,
      primary None. A comparison missing the configuration under test, not a
      record of one.

    In both cases no delta is computed.
    """
    for name, value in (("--primary", primary_arg), ("--baseline", baseline_arg)):
        if value is not None and value not in configs:
            return None, None, (
                f"{name}={value!r} is not one of the configurations found: "
                f"{', '.join(configs) or '(none)'}"
            )

    if not configs:
        return None, None, "no configurations found"

    primary = primary_arg
    baseline = baseline_arg

    if primary and baseline:
        if primary == baseline:
            return None, None, "--primary and --baseline name the same configuration"
        return primary, baseline, None

    remaining = [c for c in configs if c not in (primary, baseline)]

    if primary and not baseline:
        if len(remaining) == 1:
            return primary, remaining[0], None
        if not remaining:
            return primary, None, None
        return None, None, (
            f"cannot infer the baseline among {', '.join(remaining)}; "
            f"pass --baseline"
        )

    if baseline and not primary:
        if len(remaining) == 1:
            return remaining[0], baseline, None
        return None, None, (
            f"cannot infer the primary among {', '.join(remaining)}; "
            f"pass --primary"
        )

    if len(configs) == 1:
        only = configs[0]
        if only in BASELINE_ROLE_CONFIGS:
            # Role, never survivorship. When the configuration under test
            # produced nothing and only the baseline survived, this returned
            # the baseline *as the primary* - so the artifact read
            # `Without Skill [primary]`, delta `—`, exit 0: a coherent-looking
            # single-configuration report about the wrong configuration, with
            # nothing to tell a reader that half the comparison was lost.
            # `without_skill` does not become the primary by default; that is
            # what "primary" means.
            return None, only, None
        return only, None, None

    primaries = [c for c in configs if c in PRIMARY_ROLE_CONFIGS]
    baselines = [c for c in configs if c in BASELINE_ROLE_CONFIGS]

    if len(configs) == 2:
        if len(primaries) == 1 and len(baselines) == 1 and primaries[0] != baselines[0]:
            return primaries[0], baselines[0], None
        if len(primaries) == 1 and not baselines:
            other = [c for c in configs if c != primaries[0]][0]
            return primaries[0], other, None
        if len(baselines) == 1 and not primaries:
            other = [c for c in configs if c != baselines[0]][0]
            return other, baselines[0], None

    if len(primaries) == 1 and len(baselines) == 1:
        return primaries[0], baselines[0], None

    return None, None, (
        f"cannot decide which of {', '.join(configs)} is the primary and which "
        f"is the baseline by role. Ordering is by role, never alphabetical - "
        f"`old_skill` sorts before `with_skill` and would invert every delta. "
        f"Pass --primary <config> --baseline <config>."
    )


def pair_evals(results: dict, primary: str | None, baseline: str | None,
               dropped_runs=None) -> dict:
    """Which evals the two configurations can actually be compared on.

    Returns ``{"paired", "unpaired", "imbalanced", "missing_role", "complete",
    "checked"}``. `paired` is the evals the delta may use; `unpaired`,
    `imbalanced` and `missing_role` are the three ways an eval leaves that set,
    and they are one class of defect at three scales - an eval, a run, a whole
    configuration. Each produces a confident artifact over data the two sides
    do not share, so each classifies the same way.

    **Unpaired.** Nothing used to compare the two eval sets, so means were
    pooled over whatever each side happened to hold. Where eval-0 scored 0% in
    both configurations and eval-1 ran only under `with_skill` at 100%, all
    three tools exited 0 and reported `+0.50 better` - a favourable number
    whose entire magnitude came from an eval the baseline never attempted,
    while the one eval both sides ran showed no difference at all.

    **Imbalanced.** The same defect one level down. When an exclusion removes a
    run from one side and not the other, the eval still appears in both, and
    the delta is recomputed over the survivors: one near-miss field name
    (`met` for `passed`) moved a delta from `+0.50` to `+0.38` at exit 0. The
    number changed and nothing said its basis had. An eval is imbalanced when
    the surviving run numbers differ between the two configurations *and* an
    exclusion is what made them differ - unequal run counts nobody excluded are
    a sampling choice, already disclosed by `metadata.runs_per_configuration`
    being null and by the per-cell `n`.

    **Missing role.** A workspace holding only the primary is a legitimate
    single-configuration record: `baseline` is null and no delta
    is reported. A workspace holding only the *baseline* is not the mirror
    image of that - the configuration under test is the thing being recorded,
    and if it produced nothing there is no result about it. Every eval is then
    present in one configuration and absent from its counterpart, which is the
    same row of the severity table as the other two.

    `checked` is False only when there is no pair to check. A configuration
    that produced nothing usable is *not* exempt - its evals are unpaired,
    which is a different statement from "this configuration contributed
    nothing" and is the one that says why no delta may be reported. Exempting
    it here would also have made this function answer differently from
    `validate_grading`'s tree walk, which is the divergence one shared severity
    table exists to stop.
    """
    empty = {"paired": [], "unpaired": {}, "imbalanced": {},
             "missing_role": None, "complete": True, "checked": False}
    if not primary and not baseline:
        return empty
    if primary and not baseline:
        return empty
    if baseline and not primary:
        baseline_runs = results.get(baseline) or []
        evals = sorted({r["eval_id"] for r in baseline_runs},
                       key=_eval_sort_key)
        if not evals:
            return empty
        return {"paired": [], "unpaired": {baseline: evals}, "imbalanced": {},
                "missing_role": "primary", "complete": False, "checked": True}

    primary_runs = results.get(primary) or []
    baseline_runs = results.get(baseline) or []

    primary_evals = {r["eval_id"] for r in primary_runs}
    baseline_evals = {r["eval_id"] for r in baseline_runs}
    shared = sorted(primary_evals & baseline_evals, key=_eval_sort_key)

    unpaired = {}
    for config, own, other in ((primary, primary_evals, baseline_evals),
                               (baseline, baseline_evals, primary_evals)):
        missing = sorted(own - other, key=_eval_sort_key)
        if missing:
            unpaired[config] = missing

    def surviving(config, eval_id):
        return {r["run_number"] for r in results.get(config) or []
                if r["eval_id"] == eval_id}

    lost: dict = {}
    for item in dropped_runs or []:
        lost.setdefault((item["configuration"], item["eval_id"]), []).append(item)

    imbalanced = {}
    paired = []
    for eval_id in shared:
        p_runs = surviving(primary, eval_id)
        b_runs = surviving(baseline, eval_id)
        p_lost = lost.get((primary, eval_id), [])
        b_lost = lost.get((baseline, eval_id), [])
        if p_runs != b_runs and (p_lost or b_lost):
            imbalanced[eval_id] = {
                primary: {"surviving": sorted(p_runs),
                          "dropped": sorted(i["run_number"] for i in p_lost)},
                baseline: {"surviving": sorted(b_runs),
                           "dropped": sorted(i["run_number"] for i in b_lost)},
            }
        else:
            paired.append(eval_id)

    return {
        "paired": paired,
        "unpaired": unpaired,
        "imbalanced": imbalanced,
        "missing_role": None,
        "complete": not unpaired and not imbalanced,
        "checked": True,
    }


def aggregate_results(results: dict, primary: str | None, baseline: str | None,
                      paired_evals=None) -> dict:
    """Aggregate run results into summary statistics plus a signed delta.

    Per-configuration statistics cover every usable run of that configuration -
    that is what the configuration did. The *delta* covers only `paired_evals`,
    the evals both sides ran, because a difference computed across two
    different eval sets is not a difference between the configurations. When
    `paired_evals` is None every eval is used, which is the same thing whenever
    the pairing is complete.
    """
    run_summary: dict = {}

    def stats_for(config, metric, eval_ids=None):
        runs = results.get(config) or []
        if eval_ids is not None:
            runs = [r for r in runs if r["eval_id"] in eval_ids]
        if not runs:
            return None
        return calculate_stats([r[metric] for r in runs])

    for config, runs in results.items():
        if not runs:
            # No usable run. Absent, not zero: every metric is null and the
            # config contributes nothing to a delta.
            run_summary[config] = {
                "pass_rate": None,
                "time_seconds": None,
                "tokens": None,
                "abstention": None,
                "runs": 0,
            }
            continue

        run_summary[config] = {
            "pass_rate": calculate_stats([r["pass_rate"] for r in runs]),
            "time_seconds": calculate_stats([r["time_seconds"] for r in runs]),
            "tokens": calculate_stats([r["tokens"] for r in runs]),
            # Beside every rate, never instead of one. A 100% pass rate over
            # two graded expectations and nine abstentions is a different
            # result from 100% over eleven, and `pass_rate` alone cannot
            # tell them apart.
            "abstention": abstention_stats(runs),
            "runs": len(runs),
        }

    delta = {}
    basis = None if paired_evals is None else set(paired_evals)

    for metric, polarity in METRIC_POLARITY.items():
        p_stats = stats_for(primary, metric, basis) if primary else None
        b_stats = stats_for(baseline, metric, basis) if baseline else None
        if p_stats is None or b_stats is None:
            delta[metric] = {
                "value": None,
                "formatted": ABSENT,
                "polarity": polarity,
                "better": None,
            }
            continue

        value = round(p_stats["mean"] - b_stats["mean"], 4)
        if value == 0:
            better = None
        elif polarity == "higher_is_better":
            better = value > 0
        else:
            better = value < 0

        delta[metric] = {
            "value": value,
            "formatted": DELTA_FORMATS[metric].format(value),
            "polarity": polarity,
            "better": better,
        }

    run_summary["delta"] = delta
    return run_summary


# --------------------------------------------------------------------------
# benchmark.json
# --------------------------------------------------------------------------

def build_benchmark(discovery: dict, primary: str | None, baseline: str | None,
                    skill_name: str = "", skill_path: str = "",
                    executor_model: str | None = None,
                    analyzer_model: str | None = None,
                    notes: list | None = None) -> dict:
    """Assemble benchmark.json from discovered runs.

    Also decides the delta's basis. When the two configurations did not run the
    same evals, the delta is computed over the evals they share and every
    unpaired eval is written into `exclusions` - the only per-path list in
    benchmark.json, and the one both `benchmark.md` and the viewer already
    render - so the artifact says what was left out of the comparison rather
    than quietly folding it in.
    """
    results = discovery["results"]
    pairing = pair_evals(results, primary, baseline,
                         discovery.get("dropped_runs"))
    run_summary = aggregate_results(
        results, primary, baseline,
        paired_evals=None if pairing["complete"] else pairing["paired"])

    exclusions = list(discovery["exclusions"])
    for config, missing in sorted(pairing["unpaired"].items()):
        counterpart = baseline if config == primary else primary
        where = (f"`{counterpart}`" if counterpart
                 else "any primary configuration - none produced a usable run")
        for eval_id in missing:
            example = next(
                (r["run_dir"] for r in results.get(config, [])
                 if r["eval_id"] == eval_id), config)
            exclusions.append({
                "path": str(example),
                "reason": condition_line(
                    UNPAIRED_EVALS,
                    f"eval {eval_id!r} ran under `{config}` but not under "
                    f"{where}, so it is excluded from every delta. It still "
                    f"counts toward `{config}`'s own column, which is why the "
                    f"columns and the delta cover different evals here"),
                "errors": [],
            })

    for eval_id, sides in sorted(pairing["imbalanced"].items(),
                                 key=lambda kv: _eval_sort_key(kv[0])):
        detail = "; ".join(
            f"`{config}` kept run(s) "
            f"{', '.join(str(r) for r in side['surviving']) or 'none'} and lost "
            f"{', '.join(str(r) for r in side['dropped']) or 'none'}"
            for config, side in sides.items())
        example = next(
            (r["run_dir"] for r in results.get(primary, [])
             if r["eval_id"] == eval_id), primary or "")
        exclusions.append({
            "path": str(example),
            "reason": condition_line(
                UNPAIRED_EVALS,
                f"eval {eval_id!r} is excluded from every delta: exclusions "
                f"left the two configurations with different surviving runs "
                f"({detail}). Its surviving runs still count toward their own "
                f"configuration's column"),
            "errors": [],
        })

    ordered_configs = [c for c in (primary, baseline) if c] + \
                      [c for c in results if c not in (primary, baseline)]

    runs = []
    for config in ordered_configs:
        for result in sorted(
            results.get(config, []),
            key=lambda r: (_eval_sort_key(r["eval_id"]), r["run_number"]),
        ):
            runs.append({
                "eval_id": result["eval_id"],
                "eval_name": result["eval_name"],
                "configuration": config,
                "run_number": result["run_number"],
                "result": {
                    "pass_rate": result["pass_rate"],
                    "passed": result["passed"],
                    "failed": result["failed"],
                    "abstained": result["abstained"],
                    "total": result["total"],
                    "time_seconds": result["time_seconds"],
                    "tokens": result["tokens"],
                },
                "expectations": result["expectations"],
                "notes": result["notes"],
            })

    eval_ids = sorted(
        {r["eval_id"] for config in results.values() for r in config},
        key=_eval_sort_key,
    )

    counts = {config: len(rs) for config, rs in results.items()}
    distinct = set(counts.values())
    # Measured, never the literal 3 this used to assert regardless of the data.
    common_count = distinct.pop() if len(distinct) == 1 else None

    return {
        # Role is explicit, and lives here only. It was also
        # mirrored into `metadata`; two copies of one contract element with
        # nothing cross-checking them drift the first time either path is
        # edited, which is the defect shape this rewrite closes.
        "primary": primary,
        "baseline": baseline,
        "metadata": {
            "skill_name": skill_name or None,
            "skill_path": skill_path or None,
            "executor_model": executor_model,
            "analyzer_model": analyzer_model,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evals_run": eval_ids,
            "runs_per_configuration": common_count,
            "runs_per_configuration_by_config": counts,
        },
        # Polarity is emitted per delta (`run_summary.delta.<metric>.polarity`)
        # and nowhere else, for the same reason. A top-level map would have to
        # agree with the per-delta fields, and nothing would check that it did.
        "runs": runs,
        "run_summary": run_summary,
        "exclusions": exclusions,
        "layout_warnings": discovery["warnings"],
        "notes": notes or [],
    }


# --------------------------------------------------------------------------
# benchmark.md
# --------------------------------------------------------------------------

def _label(config: str | None) -> str:
    return config.replace("_", " ").title() if config else ABSENT


def _fmt_abstention(block, *, short: bool = False) -> str:
    """Render one configuration's pooled abstention counts."""
    if not block:
        return ABSENT
    rate = (f"{block['rate'] * 100:.0f}%" if block["rate"] is not None
            else ABSENT)
    if short:
        return f"{block['abstained']}/{block['total']} ({rate})"
    reasons = block.get("reasons") or {}
    detail = ", ".join(f"{count} {name}" for name, count in reasons.items()
                       if count)
    cell = (f"{block['abstained']} of {block['total']} checks ({rate}); "
            f"{block['graded']} graded")
    if detail:
        cell += f" — {detail}"
    if block.get("runs_without_pass_rate"):
        cell += (f"; {block['runs_without_pass_rate']} of {block['runs']} "
                 f"run(s) produced no pass rate at all")
    return cell


def _abstention_legend() -> list:
    """One markdown line per typed reason, generated from the enum.

    Generated rather than written out. The sentence this replaced named two
    reasons while `_fmt_abstention` above already printed whatever the counts
    contained, so when the contract's enum went to three, `underspecified`
    appeared in the Detail column of the table with no entry in the legend
    underneath it - a count with no meaning attached, in the one section whose
    whole job is to attach meanings to counts.

    Walking `ABSTAIN_REASONS` means the legend cannot fall behind the enum
    again. `ABSTAIN_REASON_REPAIRS` is consulted by key, so a reason with no
    repair sentence still gets listed with its meaning.
    """
    lines = []
    for reason in ABSTAIN_REASONS:
        meaning = ABSTAIN_REASON_MEANINGS.get(reason)
        line = f"- `{reason}`"
        if meaning:
            line += f" - {meaning}"
        repair = ABSTAIN_REASON_REPAIRS.get(reason)
        if repair:
            line += f". **Fix: {repair}.**"
        else:
            line += "."
        lines.append(line)
    # Not a contract reason and deliberately listed apart from them: it is the
    # bucket `abstention_stats` fills when an abstention carries a reason that
    # is not in the enum at all. Schema-invalid gradings never reach the
    # aggregator, so a non-zero count here is a file that was edited by hand
    # after validation, not a judge making a new kind of ruling.
    lines.append(
        "- `untyped` - not a reason the contract defines. It counts abstentions "
        "whose `abstainReason` was absent or was a value outside the list "
        "above, and it is 0 in any workspace that passed validation.")
    return lines


def _fmt_cell(stats, kind: str) -> str:
    """Render mean ± stddev for one metric, or an em dash when unmeasured."""
    if stats is None:
        return ABSENT

    if kind == "pass_rate":
        mean = f"{stats['mean'] * 100:.0f}%"
        spread = f"{stats['stddev'] * 100:.0f}%" if stats["stddev"] is not None else ABSENT
    elif kind == "time_seconds":
        mean = f"{stats['mean']:.1f}s"
        spread = f"{stats['stddev']:.1f}s" if stats["stddev"] is not None else ABSENT
    else:
        mean = f"{stats['mean']:.0f}"
        spread = f"{stats['stddev']:.0f}" if stats["stddev"] is not None else ABSENT

    cell = f"{mean} ± {spread} (n={stats['n']}"
    if stats["missing"]:
        # For pass_rate a missing value is not an unmeasured one - the run was
        # graded, and every expectation in it abstained, so there is no rate.
        # Calling that "unmeasured" would file a real finding under "we did not
        # look".
        cell += (f", {stats['missing']} with no rate"
                 if kind == "pass_rate" else
                 f", {stats['missing']} unmeasured")
    return cell + ")"


def _fmt_direction(entry: dict) -> str:
    if entry["value"] is None:
        return ABSENT
    if entry["better"] is None:
        return "no change"
    return "better" if entry["better"] else "worse"


def _fmt_delta(entry: dict, kind: str) -> str:
    """Render a delta in the same unit as the two cells beside it.

    `benchmark.json` keeps `pass_rate` deltas as the raw 0..1 fraction, which
    is right for a machine. Printing that fraction between two cells carrying
    `%` is not: `| 100% | 33% | +0.67 |` reads as "+0.67%" to every human who
    has ever skimmed a table, understating a 67-point improvement by two orders
    of magnitude. The row now carries one unit.
    """
    if entry.get("value") is None:
        return ABSENT
    if kind == "pass_rate":
        return f"{entry['value'] * 100:+.0f} pp"
    if kind == "time_seconds":
        return f"{entry['value']:+.1f}s"
    return f"{entry['value']:+.0f} tokens"


def _runs_by_config(benchmark: dict) -> dict:
    grouped: dict = {}
    for run in benchmark.get("runs", []):
        grouped.setdefault(run["configuration"], []).append(run)
    return grouped


def _per_eval_rows(benchmark: dict, primary, baseline) -> list:
    """One row per eval: id, name, each configuration's mean, and the delta."""
    by_eval: dict = {}
    for run in benchmark.get("runs", []):
        key = run["eval_id"]
        entry = by_eval.setdefault(
            key, {"name": run.get("eval_name"), "configs": {}, "abstain": {}})
        if entry["name"] is None:
            entry["name"] = run.get("eval_name")
        rates = entry["configs"].setdefault(run["configuration"], [])
        result = run.get("result") or {}
        rate = result.get("pass_rate")
        if isinstance(rate, (int, float)) and not isinstance(rate, bool):
            rates.append(rate)
        # Counted per eval as well as per configuration: a single eval whose
        # checks nobody could rule on is invisible in a pooled figure, and it
        # is exactly the eval whose 100%-over-two-checks needs the caveat.
        tally = entry["abstain"].setdefault(
            run["configuration"], {"abstained": 0, "total": 0, "known": False})
        counts = (result.get("abstained"), result.get("total"))
        if all(isinstance(v, int) and not isinstance(v, bool) for v in counts):
            tally["abstained"] += counts[0]
            tally["total"] += counts[1]
            tally["known"] = True

    rows = []
    for eval_id in sorted(by_eval, key=_eval_sort_key):
        entry = by_eval[eval_id]
        def mean_of(config):
            values = entry["configs"].get(config)
            if not values:
                return None
            return sum(values) / len(values)

        def abstained_of(config):
            tally = entry["abstain"].get(config)
            if not tally or not tally["known"]:
                return ABSENT
            return f"{tally['abstained']}/{tally['total']}"

        p_mean = mean_of(primary)
        b_mean = mean_of(baseline)
        if baseline is None and primary is not None:
            # The single-configuration record. There is no
            # counterpart to pair against, so "no" would read as a defect.
            delta = ABSENT
            paired = ABSENT
        elif p_mean is None or b_mean is None:
            delta = ABSENT
            # An eval both sides ran, where one side's expectations all
            # abstained, is NOT an unpaired eval. Printing "no" there says the
            # baseline never attempted it, which is a different and worse
            # finding than the true one: both attempted it and neither
            # produced a rate to compare.
            ran_both = (primary in entry["configs"]
                        and baseline in entry["configs"])
            paired = "no rate" if ran_both else "no"
        else:
            delta = f"{(p_mean - b_mean) * 100:+.0f} pp"
            paired = "yes"
        rows.append({
            "eval_id": eval_id,
            "name": entry["name"] or ABSENT,
            "primary": f"{p_mean * 100:.0f}%" if p_mean is not None else ABSENT,
            "baseline": f"{b_mean * 100:.0f}%" if b_mean is not None else ABSENT,
            "primary_abstained": abstained_of(primary),
            "baseline_abstained": abstained_of(baseline),
            "delta": delta,
            "paired": paired,
        })
    return rows


def generate_markdown(benchmark: dict, pairing: dict | None = None) -> str:
    """Generate human-readable benchmark.md from benchmark data.

    `pairing` is `pair_evals`'s result. It is a parameter rather than a second
    derivation: `runs[]` records the runs that survived and cannot say which
    ones were excluded, so a version computed here would answer the run-level
    question differently from the version that chose the delta's basis. When it
    is omitted - a caller holding only the finished file - the eval-level half
    is recomputed and the run-level half is unavailable, which the caller can
    see in the absence of an imbalance section.
    """
    metadata = benchmark["metadata"]
    run_summary = benchmark["run_summary"]
    primary = benchmark.get("primary")
    baseline = benchmark.get("baseline")

    per_config = metadata["runs_per_configuration_by_config"]
    if pairing is None:
        pairing = pair_evals(_runs_by_config(benchmark), primary, baseline)

    def sample_note(config):
        if not config:
            return ""
        return f" ({per_config.get(config, 0)} run(s))"

    # `**Evals**: 0` was indistinguishable from "this benchmark found no
    # evals". The count says which one it is.
    ids = metadata["evals_run"]
    evals = (f"{len(ids)} ({', '.join('id ' + str(e) for e in ids)})"
             if ids else "none discovered")
    lines = [
        f"# Skill Benchmark: {metadata['skill_name'] or ABSENT}",
        "",
        f"**Model**: {metadata['executor_model'] or ABSENT}",
        f"**Date**: {metadata['timestamp']}",
        f"**Evals**: {evals}",
        f"**Primary**: {_label(primary)}{sample_note(primary)}",
        f"**Baseline**: {_label(baseline)}{sample_note(baseline)}",
        "",
    ]

    if pairing["checked"] and not pairing["complete"]:
        paired = ", ".join(str(e) for e in pairing["paired"]) or "none"
        lines.append("> **Incomplete pairing.** "
                     + condition_line(UNPAIRED_EVALS))
        if pairing["missing_role"] == "primary":
            lines.append(
                f"> **No primary configuration produced a usable run.** Only "
                f"the baseline `{baseline}` did, and a surviving baseline is "
                f"not relabelled as the primary - this is a comparison missing "
                f"the configuration it was meant to be about, not a "
                f"single-configuration result.")
        for config, missing in sorted(pairing["unpaired"].items()):
            if pairing["missing_role"] == "primary":
                break  # said once, above, rather than once per configuration
            lines.append(
                f"> `{config}` alone ran eval(s) "
                f"{', '.join(str(e) for e in missing)}.")
        for eval_id, sides in sorted(pairing["imbalanced"].items(),
                                     key=lambda kv: _eval_sort_key(kv[0])):
            detail = "; ".join(
                f"`{config}` kept run(s) "
                f"{', '.join(str(r) for r in side['surviving']) or 'none'}, "
                f"lost {', '.join(str(r) for r in side['dropped']) or 'none'}"
                for config, side in sides.items())
            lines.append(
                f"> Eval {eval_id}: exclusions left the two sides with "
                f"different surviving runs - {detail}.")
        lines.extend([
            f"> The delta below covers only the eval(s) both configurations "
            f"ran comparably: {paired}. The two configuration columns cover "
            f"every usable run of that configuration, so they include evals "
            f"the delta does not - read them as descriptions of each side, not "
            f"as a comparison.",
            "",
        ])

    if metadata["runs_per_configuration"] is None and per_config:
        counts = ", ".join(f"`{c}` {n}" for c, n in sorted(per_config.items()))
        lines.extend([
            f"**Unequal run counts**: {counts}. `benchmark.json`'s "
            f"`runs_per_configuration` is `null` for this reason - there is no "
            f"single number, and reporting one would be an invention. Each "
            f"cell below carries its own `n`.",
            "",
        ])

    lines.extend([
        "## Summary",
        "",
        "Delta is primary − baseline on every metric, in the unit of the row "
        "(`pp` is percentage points). `—` means the value was never measured; "
        "it is not zero. `benchmark.json` carries the pass-rate delta as the "
        "raw 0..1 fraction.",
        "",
        f"| Metric | {_label(primary)} | {_label(baseline)} | Delta | Direction |",
        "|--------|------------|---------------|-------|-----------|",
    ])

    primary_summary = run_summary.get(primary) or {}
    baseline_summary = run_summary.get(baseline) or {}
    delta = run_summary.get("delta", {})

    for metric, title in (
        ("pass_rate", "Pass Rate (higher is better)"),
        ("time_seconds", "Time (lower is better)"),
        ("tokens", "Tokens (lower is better)"),
    ):
        entry = delta.get(metric, {"value": None, "formatted": ABSENT, "better": None})
        lines.append(
            f"| {title} "
            f"| {_fmt_cell(primary_summary.get(metric), metric)} "
            f"| {_fmt_cell(baseline_summary.get(metric), metric)} "
            f"| {_fmt_delta(entry, metric)} "
            f"| {_fmt_direction(entry)} |"
        )

    lines.extend([
        "",
        "Pass rate is the mean of per-run pass rates (a macro average over "
        "runs, not over assertions).",
    ])

    # This block sits directly under the summary table because
    # the pass rate above cannot be read without it: 100% over two graded
    # checks and nine abstentions is not the same result as 100% over eleven,
    # and the row above renders both as `100%`.
    p_abstain = primary_summary.get("abstention")
    b_abstain = baseline_summary.get("abstention")
    if p_abstain or b_abstain:
        lines.extend([
            "",
            "## Abstentions",
            "",
            f"| Configuration | Abstained | Detail |",
            "|---------------|-----------|--------|",
        ])
        for config, block in ((primary, p_abstain), (baseline, b_abstain)):
            if config is None:
                continue
            lines.append(
                f"| {_label(config)} | {_fmt_abstention(block, short=True)} "
                f"| {_fmt_abstention(block)} |")
        lines.extend([
            "",
            f"An abstention is a check the judge declined to rule on, not a "
            f"check that failed. It leaves the pass-rate denominator entirely: "
            f"{PASS_RATE_RULE}. The typed reason is not decoration - each one "
            f"names a different repair, performed by a different person, and "
            f"the `Fix:` on each line below says which person:",
            "",
        ])
        lines.extend(_abstention_legend())
        lines.extend([
            "",
            "**There is deliberately no delta on this row and no polarity.** "
            "Every other metric here declares which direction is better, "
            "and abstention has no honest answer: a judge that "
            "abstains freely produces a benchmark that measures nothing while "
            "looking rigorous, and a judge that never abstains is the defect "
            "that made an unverifiable check count as evidence against the "
            "skill. Read the number against the pass rate beside it — a high "
            "pass rate over a small graded fraction is a weak result, not a "
            "strong one — and against the same figure from the previous "
            "iteration, where a jump is a judge that has drifted.",
        ])

    # Per-eval breakdown. Without it one catastrophic eval among five is
    # invisible in the shared artifact, and a `± 35%` that is entirely
    # between-eval difficulty reads as run-to-run noise.
    rows = _per_eval_rows(benchmark, primary, baseline)
    if rows:
        lines.extend([
            "",
            "## By eval",
            "",
            "Per-eval mean pass rate over that eval's runs, with the "
            "abstentions that rate was computed *around* — `Abst.` is "
            "abstained/total checks for that eval. A rate of `—` beside a "
            "full-count abstention is an eval nobody could rule on: it has no "
            "pass rate, and it is not a zero. `Paired` is whether both "
            "configurations ran it and both produced a rate — `no` means one "
            "side never ran it, `no rate` means both ran it and at least one "
            "produced no rate to compare. Only `yes` rows contribute to the "
            "delta above.",
            "",
            f"| Eval | Name | {_label(primary)} | Abst. | {_label(baseline)} "
            f"| Abst. | Delta | Paired |",
            "|------|------|------------|-------|---------------|-------|-------|--------|",
        ])
        for row in rows:
            lines.append(
                f"| {row['eval_id']} | {row['name']} | {row['primary']} "
                f"| {row['primary_abstained']} | {row['baseline']} "
                f"| {row['baseline_abstained']} | {row['delta']} "
                f"| {row['paired']} |"
            )

    other = [c for c in run_summary
             if c not in ("delta", primary, baseline)]
    if other:
        lines.extend(["", "## Other configurations", ""])
        for config in other:
            stats = run_summary[config]
            lines.append(
                f"- **{_label(config)}**: pass rate "
                f"{_fmt_cell(stats.get('pass_rate'), 'pass_rate')}, "
                f"abstentions {_fmt_abstention(stats.get('abstention'), short=True)} "
                f"(not part of the delta)"
            )

    if benchmark.get("exclusions"):
        lines.extend([
            "",
            "## Excluded from aggregation",
            "",
            f"{len(benchmark['exclusions'])} item(s) were left out of some or "
            f"all of the numbers above. Each names its workspace condition.",
            "",
        ])
        for item in benchmark["exclusions"]:
            lines.append(f"- `{item['path']}` — {item['reason']}")
            for err in item.get("errors", []):
                lines.append(f"  - {err}")

    if benchmark.get("layout_warnings"):
        lines.extend(["", "## Layout warnings", ""])
        for warning in benchmark["layout_warnings"]:
            lines.append(f"- {warning}")

    if benchmark.get("notes"):
        lines.extend(["", "## Notes", ""])
        for note in benchmark["notes"]:
            lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def _fail(message: str) -> int:
    print(f"\nERROR: {message}", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    configure_console()

    parser = argparse.ArgumentParser(
        prog="python -m scripts.aggregate_benchmark",
        description="Aggregate benchmark run results into summary statistics",
    )
    parser.add_argument("benchmark_dir", type=Path,
                        help="the workspace iteration directory")
    parser.add_argument("--skill-name", default="",
                        help="name of the skill being benchmarked")
    parser.add_argument("--skill-path", default="",
                        help="path to the skill being benchmarked")
    parser.add_argument("--primary", default=None,
                        help="configuration to treat as primary. "
                             "Inferred from the config names when unambiguous.")
    parser.add_argument("--baseline", default=None,
                        help="configuration to treat as the baseline")
    parser.add_argument("--executor-model", default=None,
                        help="model that produced the runs; recorded verbatim")
    parser.add_argument("--analyzer-model", default=None,
                        help="model that performed the analyst pass")
    parser.add_argument("--notes", type=Path, default=None,
                        help="path to a JSON array of analyst note strings to "
                             "embed in benchmark.json and benchmark.md")
    parser.add_argument("--output", "-o", type=Path,
                        help="output path for benchmark.json "
                             "(default: <benchmark_dir>/benchmark.json)")

    args = parser.parse_args(argv)

    # This script's product is files; every human-readable line goes to stderr
    # so nothing here can corrupt a machine consumer reading stdout.
    log = sys.stderr

    if not args.benchmark_dir.exists():
        return _fail(f"directory not found: {args.benchmark_dir}")

    discovery = discover_runs(args.benchmark_dir)

    for warning in discovery["warnings"]:
        print(f"Warning: {warning}", file=log)

    results = discovery["results"]
    total_runs = sum(len(v) for v in results.values())

    if total_runs == 0:
        searched = "\n".join(f"  {p}" for p in discovery["searched"])
        excluded = ""
        if discovery["exclusions"]:
            # The validator's own messages, not just the one-line reason. When
            # every grading file was excluded there is no benchmark and no
            # `exclusions` array to read afterwards, so this console block is
            # the only place the diagnosis exists - and "failed schema
            # validation" alone does not tell anyone that their files are in
            # the previous contract's shape and how to migrate them.
            blocks = []
            for item in discovery["exclusions"]:
                lines = [f"  {item['path']}", f"    {item['reason']}"]
                lines.extend(f"      - {err}" for err in item.get("errors", []))
                blocks.append("\n".join(lines))
            excluded = "\n\nFound but excluded:\n" + "\n".join(blocks)
        return _fail(
            f"{condition_line(ZERO_RUNS)}. No benchmark was written - a "
            f"benchmark built from nothing renders as a real result.\n\n"
            f"Searched:\n{searched}{excluded}\n\n"
            f"Expected layout:\n\n{CANONICAL_LAYOUT}\n"
        )

    configs = list(results.keys())
    primary, baseline, role_error = resolve_roles(configs, args.primary, args.baseline)
    if role_error:
        return _fail(f"{role_error}\nNo benchmark was written.")

    notes = []
    if args.notes is not None:
        data, error = read_json_file(args.notes)
        if error is not None:
            return _fail(f"--notes {args.notes}: {error}")
        if not isinstance(data, list) or not all(isinstance(n, str) for n in data):
            return _fail(f"--notes {args.notes}: expected a JSON array of strings")
        notes = data

    benchmark = build_benchmark(
        discovery, primary, baseline,
        skill_name=args.skill_name,
        skill_path=args.skill_path,
        executor_model=args.executor_model,
        analyzer_model=args.analyzer_model,
        notes=notes,
    )

    output_json = args.output or (args.benchmark_dir / "benchmark.json")
    output_md = output_json.with_suffix(".md")

    # Encoding is never left to the platform default. benchmark.md
    # carries ± and — ; without this it was written in cp1252 on Windows and
    # was not valid UTF-8 for any reader downstream.
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(benchmark, f, indent=2)
    print(f"Generated: {output_json}", file=log)

    pairing = pair_evals(results, primary, baseline,
                         discovery.get("dropped_runs"))

    with open(output_md, "w", encoding="utf-8") as f:
        f.write(generate_markdown(benchmark, pairing))
    print(f"Generated: {output_md}", file=log)

    run_summary = benchmark["run_summary"]
    print("\nSummary:", file=log)
    for config in configs:
        stats = run_summary[config].get("pass_rate")
        role = ""
        if config == primary:
            role = " [primary]"
        elif config == baseline:
            role = " [baseline]"
        n = benchmark["metadata"]["runs_per_configuration_by_config"].get(config, 0)
        abstention = run_summary[config].get("abstention")
        # Printed on the same line as the rate, always. A rate on its own line
        # is the artifact that must not exist.
        beside = f", abstentions {_fmt_abstention(abstention, short=True)}"
        if stats is None and n == 0:
            print(f"  {_label(config)}{role}: no usable runs", file=log)
        elif stats is None:
            no_rate = (abstention or {}).get("runs_without_pass_rate") or 0
            why = ""
            if abstention and no_rate and no_rate == abstention.get("runs"):
                why = (" - every expectation in every run abstained, so there "
                       "is no rate to report. This is not 0%")
            print(f"  {_label(config)}{role}: no pass rate{why} "
                  f"(n={n}{beside})", file=log)
        else:
            print(f"  {_label(config)}{role}: {stats['mean'] * 100:.1f}% pass "
                  f"rate (n={n}{beside})", file=log)

    delta = run_summary.get("delta", {}).get("pass_rate", {})
    basis = ""
    if pairing["checked"] and not pairing["complete"]:
        basis = (f" over the {len(pairing['paired'])} comparable eval(s) only: "
                 f"{', '.join(str(e) for e in pairing['paired']) or 'none'}")
    print(f"  Delta (primary − baseline): {delta.get('formatted', ABSENT)} "
          f"[{_fmt_direction(delta) if delta else ABSENT}]{basis}", file=log)

    exit_code = 0

    if benchmark["exclusions"]:
        print(f"\n{len(benchmark['exclusions'])} item(s) excluded from some or "
              f"all of the statistics:", file=log)
        for item in benchmark["exclusions"]:
            print(f"  {item['path']}\n    {item['reason']}", file=log)
            for err in item.get("errors", []):
                print(f"      - {err}", file=log)

    # Exit code, from the shared severities and one stated rule: an
    # error-severity condition whose consequence is *visible in the artifact*
    # (a schema-invalid file, listed in `exclusions` with its errors) leaves
    # the benchmark trustworthy over what remains, so the run succeeds and the
    # exclusion speaks for itself. An error-severity condition that makes the
    # artifact itself unsound - data the user paid for that no reader can see,
    # or a delta whose two sides did not run the same evals - fails the run.
    if not pairing["complete"]:
        comparable = ", ".join(str(e) for e in pairing["paired"]) or "none"
        if pairing["missing_role"] == "primary":
            print(
                f"\nERROR: {condition_line(UNPAIRED_EVALS)}. No primary "
                f"configuration produced a usable run; only the baseline "
                f"`{baseline}` did. `primary` is null and the delta is {ABSENT} "
                f"- a surviving baseline is not promoted to primary, because "
                f"the result would read as a report about the configuration "
                f"under test when the configuration under test produced "
                f"nothing. Name the roles with --primary/--baseline if this "
                f"workspace really is a single-configuration record.", file=log)
        for config, missing in sorted(pairing["unpaired"].items()):
            counterpart = baseline if config == primary else primary
            if counterpart is None:
                continue  # said once, above, rather than once per eval
            print(
                f"\nERROR: {condition_line(UNPAIRED_EVALS)}. `{config}` ran "
                f"eval(s) {', '.join(str(e) for e in missing)} and "
                f"`{counterpart}` did not. The delta above covers only the "
                f"eval(s) both ran comparably ({comparable}); pooling the rest "
                f"would have reported a difference the baseline never had the "
                f"chance to produce.", file=log)
        for eval_id, sides in sorted(pairing["imbalanced"].items(),
                                     key=lambda kv: _eval_sort_key(kv[0])):
            detail = "; ".join(
                f"`{config}` kept run(s) "
                f"{', '.join(str(r) for r in side['surviving']) or 'none'} and "
                f"lost {', '.join(str(r) for r in side['dropped']) or 'none'}"
                for config, side in sides.items())
            print(
                f"\nERROR: {condition_line(UNPAIRED_EVALS)}. Eval {eval_id} is "
                f"excluded from the delta: {detail}. An excluded run must not "
                f"quietly move the comparison - it changes what the two means "
                f"are means of. The delta above covers only the eval(s) both "
                f"sides ran comparably ({comparable}).", file=log)
        exit_code = 1

    invisible = [item for item in benchmark["exclusions"]
                 if UNDISCOVERABLE_GRADING in item["reason"]]
    if invisible:
        print(f"\nERROR: {condition_line(UNDISCOVERABLE_GRADING)}. "
              f"{len(invisible)} path(s) above hold graded runs that are not in "
              f"this benchmark and cannot be, at the paths they occupy.",
              file=log)
        exit_code = 1

    empty_configs = [c for c in configs if not results[c]]
    if empty_configs:
        print(f"\nERROR: no usable runs for: {', '.join(empty_configs)}. "
              f"Those columns are unknown, not zero, and the delta against "
              f"them is not reported.", file=log)
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
