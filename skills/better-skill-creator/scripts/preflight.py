#!/usr/bin/env python3
"""
Check a workspace's layout, eval-directory naming, and field names BEFORE any
sub-agent runs.

This script exists to be cheap and to refuse early. Everything it does is a
filesystem walk and a handful of JSON parses - no model calls, no network, no
spend. It is the last point at which a malformed workspace costs seconds
instead of a full iteration of executor and grader sub-agents.

Usage:
    python -m scripts.preflight <workspace-dir> [--iteration N] [--json]

<workspace-dir> may be the workspace root (holding `iteration-<N>/`
directories) or a single iteration directory.

Every failure names the exact path that is wrong and the exact path expected.

Severity, and why this script still refuses more than the readers
-----------------------------------------------------------------
Severity is not decided here. `scripts.utils.WORKSPACE_CONDITIONS` is the one
severity table, and this script, `validate_grading` and `aggregate_benchmark`
all classify from it and all print the same `C12:<condition>=<severity>` token.
Pointed at one flat-layout workspace, the three used to answer ERROR/exit 1,
WARNING/exit 0 and WARNING-plus-a-correct-benchmark: three parties, one
condition, three answers, because each computed the judgment itself.

What the three do with a severity still differs, and the shared table grants
that. A shared-table *warning* blocks here and nowhere else: the readers are
interpreting results that already exist, while this runs before any sub-agent
is spawned, where the same layout costs a rename instead of a rerun. That is a
decision about what to do, not a claim that the condition is worse than the
readers say it is - and the message says which it is.

Advisory warnings do not block: a prepared workspace with eval prompts and no
results yet is precisely the state this script exists to be run in, so it must
be able to pass.

What it checks
--------------
Layout  `run-<K>/` is always present, even for a single run (`run-1/`). A
        config directory holding `grading.json` directly is the
        `legacy_flat_layout` condition - a warning, because the readers
        normalize it and aggregate it correctly - and it blocks here anyway,
        per the paragraph above. Its grading.json and timing.json are validated
        where the readers will read them, at the flattened path, and counted in
        the census as the `run-1` they will be read as.
Naming  Eval directories are `eval-<ID>-<descriptive-slug>/`, and `<ID>` equals
        `eval_metadata.json`'s `eval_id`.
Fields  `eval_metadata.json`, `grading.json`, and `timing.json` carry the exact
        field names and types the readers expect.

And, last, the projection that matters most: it runs the aggregator's own
discovery over the tree and reports how many runs it would find. A workspace
whose gradings are all present but which aggregates to zero runs is the
flagship failure this package exists to close, and it is detectable here for
free.

Missing runs are not an error before spend - a freshly prepared workspace has
eval prompts and no results yet. Non-conforming runs always are.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.utils import (
    FLAT_AND_RUN_DIRS,
    LEGACY_FLAT_LAYOUT,
    SCHEMA_INVALID,
    UNDISCOVERABLE_GRADING,
    UNPAIRED_EVALS,
    ZERO_RUNS,
    classify_workspace_condition,
    condition_line,
    configure_console,
)
from scripts.aggregate_benchmark import discover_runs, pair_evals, resolve_roles
from scripts.validate_grading import (
    ABSENT,
    CANONICAL_CONFIGS,
    CANONICAL_LAYOUT,
    EVAL_DIR_RE,
    EXTRA_KNOWN_CONFIGS,
    ITERATION_DIR_RE,
    NON_CONFIG_DIRS,
    ROLE_CONFIGS,
    RUN_DIR_RE,
    validate_eval_metadata,
    validate_grading_file,
    validate_timing_file,
)

# Files and directories that legitimately sit in an iteration directory
# alongside the eval directories.
ITERATION_ARTIFACTS = {
    "benchmark.json", "benchmark.md", "feedback.json", "review.html",
    "analysis.json", "comparison.json", "notes.json",
}

#: Directories the walk skips, minus every name that carries a configuration
#: role. This list used to contain `skill`, and so did
#: `validate_grading.PRIMARY_ROLE_CONFIGS`: a directory the aggregator treated
#: as the *primary* configuration was skipped here entirely, so a timing.json
#: of `{"total_tokens": -999, "total_duration_seconds": -42.0}` under `skill/`
#: produced no finding at all, where the identical file under `with_skill/`
#: produced two errors. Two hardcoded lists that had to stay disjoint and did
#: not is a drift surface by construction; the subtraction removes the surface
#: rather than fixing this instance of it.
IGNORED_DIRS = frozenset(
    {".git", "__pycache__", ".claude", "node_modules", "skill"}
) - frozenset(ROLE_CONFIGS)


class Findings:
    """Ordered errors and warnings, each anchored to a path.

    A finding may carry a workspace `condition`. When it does, its level
    comes from `scripts.utils`'s severity table and not from the call site -
    preflight does not get to decide that a flat layout is an error while the
    two readers call it a warning, which is exactly what it used to do. What
    preflight *does* with the severity is still its own: a table-classified
    warning blocks (see `blocking`), because this is the gate that runs before
    money is spent and stricter is its job.
    """

    def __init__(self):
        self.items: list[dict] = []

    def error(self, path, message, expected=None, condition=None):
        self.items.append({"level": "error", "path": str(path),
                           "message": message, "expected": expected,
                           "condition": condition})

    def warning(self, path, message, expected=None, condition=None):
        self.items.append({"level": "warning", "path": str(path),
                           "message": message, "expected": expected,
                           "condition": condition})

    def classified(self, path, condition, detail="", expected=None):
        """File a finding at the shared table's severity for `condition`."""
        info = classify_workspace_condition(condition)
        record = self.error if info["severity"] == "error" else self.warning
        record(path, condition_line(condition, detail), expected=expected,
               condition=condition)

    def extend(self, path, errors, warnings, prefix="", condition=None):
        for err in errors:
            self.error(path, f"{prefix}{err}", condition=condition)
        for warn in warnings:
            self.warning(path, f"{prefix}{warn}")

    @property
    def errors(self):
        return [i for i in self.items if i["level"] == "error"]

    @property
    def warnings(self):
        return [i for i in self.items if i["level"] == "warning"]

    @property
    def blocking(self):
        """Warnings that name a workspace condition, which this gate refuses on.

        Advisory warnings - no `outputs/` yet, no configuration directories yet
        - are not here. A workspace prepared and not yet run is the state this
        script exists to check, so it must be able to pass.
        """
        return [i for i in self.items
                if i["level"] == "warning" and i.get("condition")]


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_run_dir(run_dir: Path, findings: Findings) -> dict:
    """Check one run-<K>/ directory. Returns a small census."""
    census = {"graded": False, "timed": False, "has_outputs": False}

    if not (run_dir / "outputs").is_dir():
        findings.warning(
            run_dir,
            "no outputs/ directory",
            expected=str(run_dir / "outputs"),
        )
    else:
        census["has_outputs"] = True

    grading = run_dir / "grading.json"
    if grading.is_file():
        census["graded"] = True
        errors, warnings = validate_grading_file(grading)
        if errors:
            findings.classified(
                grading, SCHEMA_INVALID,
                f"grading.json: {len(errors)} schema error(s), listed below")
        findings.extend(grading, errors, warnings)

    timing = run_dir / "timing.json"
    if timing.is_file():
        census["timed"] = True
        errors, warnings = validate_timing_file(timing)
        if errors:
            findings.classified(
                timing, SCHEMA_INVALID,
                f"timing.json: {len(errors)} schema error(s), listed below")
        findings.extend(timing, errors, warnings)
    elif census["graded"]:
        findings.warning(
            run_dir,
            f"graded but has no timing.json, so this run's tokens and duration "
            f"are unknown and will render as {ABSENT} - never as 0",
            expected=str(timing),
        )

    return census


def check_config_dir(config_dir: Path, findings: Findings) -> dict:
    """Check one configuration directory. Returns a census."""
    census = {"runs": 0, "graded": 0, "timed": 0}
    name = config_dir.name

    if name not in CANONICAL_CONFIGS:
        if name in EXTRA_KNOWN_CONFIGS:
            findings.warning(
                config_dir,
                f"configuration `{name}` is understood but is not one of the "
                f"canonical names ({', '.join(CANONICAL_CONFIGS)})",
            )
        else:
            findings.error(
                config_dir,
                f"`{name}` is not a recognised configuration name. The "
                f"canonical names are {', '.join(CANONICAL_CONFIGS)}; without a "
                f"recognised name the primary/baseline roles cannot be inferred "
                f"and every delta is undefined",
                expected=str(config_dir.parent / "with_skill"),
            )

    run_dirs = []
    for child in sorted(config_dir.iterdir()):
        if child.is_dir() and RUN_DIR_RE.match(child.name):
            run_dirs.append(child)
        elif child.is_dir() and child.name.startswith("run-"):
            findings.error(
                child,
                f"`{child.name}` is not `run-<K>` with an integer K",
                expected=str(config_dir / "run-1"),
            )

    if not run_dirs:
        # run-<K>/ is ALWAYS present. A flattened config directory is the
        # layout that produced a benchmark of zeros from data graded 4/4. It
        # is still a warning and not an error, because the shared severity
        # table says so: the readers normalize it and aggregate it correctly,
        # and a gate that calls a correctly-aggregating workspace broken is wrong
        # about the workspace. This gate refuses to green-light it anyway - see
        # `Findings.blocking` - which is a decision about what to do, not about
        # what the condition is.
        if (config_dir / "grading.json").is_file():
            findings.classified(
                config_dir / "grading.json", LEGACY_FLAT_LAYOUT,
                expected=str(config_dir / "run-1" / "grading.json"),
            )
            # And census it the way every reader will read it: as run-1. The
            # old code returned here, so the summary line could say "0 run
            # dir(s), 0 graded ... 2 discoverable by aggregation" - three
            # counts of the same data that cannot all be true, and the grading
            # and timing files the aggregator was about to read went
            # unvalidated.
            run_census = check_run_dir(config_dir, findings)
            census["runs"] += 1
            census["graded"] += int(run_census["graded"])
            census["timed"] += int(run_census["timed"])
        elif (config_dir / "outputs").is_dir():
            findings.error(
                config_dir / "outputs",
                "outputs/ sits directly in the configuration directory. The "
                "canonical layout requires a run level even for a single run",
                expected=str(config_dir / "run-1" / "outputs"),
            )
        return census

    if (config_dir / "grading.json").is_file():
        # Both shapes at once. The run directories win and the flat file is
        # dropped; naming which was used is the fix (R8).
        used = ", ".join(d.name for d in run_dirs)
        findings.classified(
            config_dir / "grading.json", FLAT_AND_RUN_DIRS,
            f"the run director{'y' if len(run_dirs) == 1 else 'ies'} beside it "
            f"({used}) {'is' if len(run_dirs) == 1 else 'are'} what every "
            f"reader will use; this file is discarded",
            expected=str(config_dir / "run-1" / "grading.json"),
        )

    for run_dir in run_dirs:
        run_census = check_run_dir(run_dir, findings)
        census["runs"] += 1
        census["graded"] += int(run_census["graded"])
        census["timed"] += int(run_census["timed"])

    return census


def check_eval_dir(eval_dir: Path, findings: Findings) -> dict:
    """Check one eval directory. Returns a census."""
    census = {"configs": [], "runs": 0, "graded": 0, "timed": 0}
    name = eval_dir.name
    match = EVAL_DIR_RE.match(name)

    dir_eval_id = None
    if not match:
        findings.error(
            eval_dir,
            f"`{name}` is not an eval directory name. The expected form is "
            f"`eval-<ID>-<descriptive-slug>`, e.g. eval-0-handles-empty-csv",
            expected=str(eval_dir.parent / f"eval-<ID>-{name}"),
        )
    else:
        dir_eval_id = int(match.group(1))
        if not match.group(2):
            findings.error(
                eval_dir,
                f"`{name}` has an id but no descriptive slug. The expected "
                f"form is `eval-<ID>-<descriptive-slug>` so that results are "
                f"readable "
                f"without cross-referencing metadata",
                expected=str(eval_dir.parent / f"{name}-<descriptive-slug>"),
            )

    metadata = eval_dir / "eval_metadata.json"
    if not metadata.is_file():
        findings.error(
            eval_dir,
            "no eval_metadata.json. It carries the eval id, the human-readable "
            "name, the prompt the reviewer needs to judge the output, and the "
            "author's assertions",
            expected=str(metadata),
        )
    else:
        errors, warnings = validate_eval_metadata(metadata, dir_eval_id)
        findings.extend(metadata, errors, warnings)

    # A directory neither named `eval-<ID>-<slug>` nor carrying an
    # eval_metadata.json is invisible to `is_eval_dir`, so every grading under
    # it is paid for and unreadable. The naming error above says what is wrong;
    # this says what it costs, in the same words the other two components use.
    if not match and not metadata.is_file() and any(eval_dir.rglob("grading.json")):
        findings.classified(
            eval_dir, UNDISCOVERABLE_GRADING,
            f"`{name}` holds graded runs and no reader discovers it. Rename it "
            f"`eval-<ID>-{name}` or add {metadata}",
            expected=str(eval_dir.parent / f"eval-<ID>-{name}"),
        )

    stray = eval_dir / "grading.json"
    if stray.is_file():
        # Graders have been observed writing here. The walk below only looks at
        # directories, so this file used to pass preflight in silence while
        # `validate_grading` failed the same tree.
        findings.classified(
            stray, UNDISCOVERABLE_GRADING,
            "it sits at the eval-directory root, where no reader looks, so it "
            "contributes nothing to any benchmark",
            expected=str(eval_dir / "<config>" / "run-1" / "grading.json"),
        )

    for child in sorted(eval_dir.iterdir()):
        if child.name in ITERATION_ARTIFACTS or child.name == "eval_metadata.json":
            continue
        if not child.is_dir():
            continue
        if child.name in IGNORED_DIRS:
            continue
        if child.name in NON_CONFIG_DIRS:
            # `inputs/` beside the configs is fine; `outputs/` at this level is
            # a run's output directory two levels too high.
            if child.name == "outputs":
                findings.error(
                    child,
                    "outputs/ sits at the eval level; it belongs inside a run "
                    "directory under a configuration",
                    expected=str(eval_dir / "<config>" / "run-1" / "outputs"),
                )
            continue

        census["configs"].append(child.name)
        config_census = check_config_dir(child, findings)
        census["runs"] += config_census["runs"]
        census["graded"] += config_census["graded"]
        census["timed"] += config_census["timed"]

    if not census["configs"]:
        findings.warning(
            eval_dir,
            "no configuration directories yet",
            expected=str(eval_dir / "with_skill" / "run-1"),
        )

    return census


def check_iteration(iteration_dir: Path, findings: Findings) -> dict:
    """Check one iteration-<N>/ directory. Returns a census."""
    census = {"evals": 0, "configs": set(), "runs": 0, "graded": 0, "timed": 0}

    if not ITERATION_DIR_RE.match(iteration_dir.name):
        findings.warning(
            iteration_dir,
            f"`{iteration_dir.name}` is not `iteration-<N>`",
            expected=str(iteration_dir.parent / "iteration-1"),
        )

    eval_dirs = []
    for child in sorted(iteration_dir.iterdir()):
        if child.name in ITERATION_ARTIFACTS or child.name in IGNORED_DIRS:
            continue
        if not child.is_dir():
            findings.warning(
                child,
                f"unexpected file `{child.name}` in the iteration directory",
            )
            continue
        if child.name == "runs":
            findings.error(
                child,
                "eval directories live directly under the iteration directory; "
                "the `runs/` level is a legacy shape readers still tolerate but "
                "the canonical layout does not define",
                expected=str(iteration_dir / "eval-<ID>-<descriptive-slug>"),
            )
            continue
        eval_dirs.append(child)

    if not eval_dirs:
        findings.error(
            iteration_dir,
            "no eval directories",
            expected=str(iteration_dir / "eval-0-<descriptive-slug>"),
        )
        return census

    for eval_dir in eval_dirs:
        eval_census = check_eval_dir(eval_dir, findings)
        census["evals"] += 1
        census["configs"].update(eval_census["configs"])
        census["runs"] += eval_census["runs"]
        census["graded"] += eval_census["graded"]
        census["timed"] += eval_census["timed"]

    configs = sorted(census["configs"])
    if len(configs) >= 2:
        _, _, role_error = resolve_roles(configs, None, None)
        if role_error:
            findings.error(
                iteration_dir,
                f"{role_error}; with no primary and baseline roles a delta has no "
                f"direction",
            )

    # The projection: what the aggregator would actually see. Cheap, and it is
    # the only check that catches "everything is graded and it still aggregates
    # to nothing".
    discovery = discover_runs(iteration_dir)
    discovered = sum(len(v) for v in discovery["results"].values())
    census["discovered"] = discovered
    census["discovery_warnings"] = discovery["warnings"]
    census["discovery_exclusions"] = discovery["exclusions"]

    if census["graded"] and discovered == 0:
        findings.classified(
            iteration_dir, ZERO_RUNS,
            f"{census['graded']} grading.json file(s) are present and the "
            f"aggregator discovers zero runs here, so this workspace "
            f"aggregates to nothing",
        )
    elif census["graded"] and discovered < census["graded"]:
        findings.warning(
            iteration_dir,
            f"{census['graded']} grading.json file(s) present but only "
            f"{discovered} run(s) are usable; the findings above say which and "
            f"why",
        )

    # Pairing, through the aggregator's own function so the two cannot answer
    # differently. Caught here it costs a rename; caught after the fact it is a
    # delta whose magnitude came from an eval one side never ran.
    if discovered:
        discovered_configs = list(discovery["results"].keys())
        primary, baseline, pairing_role_error = resolve_roles(
            discovered_configs, None, None)
        if not pairing_role_error:
            pairing = pair_evals(discovery["results"], primary, baseline,
                                 discovery.get("dropped_runs"))
            if pairing["missing_role"] == "primary":
                findings.classified(
                    iteration_dir, UNPAIRED_EVALS,
                    f"no primary configuration has a usable run; only the "
                    f"baseline `{baseline}` does. The aggregator will report "
                    f"`primary: null` rather than promote `{baseline}`, so "
                    f"there is no result about the configuration under test",
                    expected=str(iteration_dir / "eval-<ID>-<slug>"
                                 / "with_skill" / "run-1"),
                )
            for config, missing in sorted(pairing["unpaired"].items()):
                counterpart = baseline if config == primary else primary
                if counterpart is None:
                    continue  # said once, above
                findings.classified(
                    iteration_dir, UNPAIRED_EVALS,
                    f"`{config}` has usable runs for eval(s) "
                    f"{', '.join(str(e) for e in missing)} and `{counterpart}` "
                    f"has none. Any delta would be computed over two different "
                    f"eval sets",
                )
            for eval_id, sides in sorted(
                    pairing["imbalanced"].items(), key=lambda kv: str(kv[0])):
                detail = "; ".join(
                    f"`{config}` keeps run(s) "
                    f"{', '.join(str(r) for r in side['surviving']) or 'none'} "
                    f"and loses "
                    f"{', '.join(str(r) for r in side['dropped']) or 'none'}"
                    for config, side in sides.items())
                findings.classified(
                    iteration_dir, UNPAIRED_EVALS,
                    f"eval {eval_id} would be excluded from the delta: {detail}",
                )

    # Deliberately NOT replaying `discovery["exclusions"]` as findings. This
    # walk already produced every one of them from the top down, and the replay
    # emitted two identical ERROR blocks for one defect - a `run-abc/`
    # directory, or a `pass_rate: "85%"` - at the same path. The count
    # comparison above is the part with independent value: it is an
    # outcome-level backstop that still fires if these cause-level checks ever
    # drift, and it does not double-report anything.
    #
    # `zero discoverable runs with nothing graded` is not classified here.
    # Before spend that is the normal state of a prepared workspace - eval
    # prompts written, executor not yet run - and this script exists to be
    # runnable at exactly that moment. The condition is asserted the instant
    # there is graded data to lose, which is when it means something.

    return census


def preflight(target: Path, iteration: int | None = None) -> dict:
    """Run every check. Returns a report dict (also the --json payload)."""
    findings = Findings()

    if ITERATION_DIR_RE.match(target.name):
        iterations = [target]
    else:
        iterations = sorted(
            (p for p in target.iterdir()
             if p.is_dir() and ITERATION_DIR_RE.match(p.name)),
            key=lambda p: int(ITERATION_DIR_RE.match(p.name).group(1)),
        )

    if iteration is not None:
        wanted = f"iteration-{iteration}"
        iterations = [p for p in iterations if p.name == wanted]
        if not iterations:
            findings.error(
                target,
                f"no `{wanted}` directory",
                expected=str(target / wanted),
            )

    if not iterations:
        if iteration is None:
            findings.error(
                target,
                "no iteration directories. A workspace holds "
                "`iteration-<N>/` directories, and each of those holds the "
                "eval directories",
                expected=str(target / "iteration-1"),
            )
        return _report(target, [], findings)

    censuses = []
    for iteration_dir in iterations:
        census = check_iteration(iteration_dir, findings)
        census["path"] = str(iteration_dir)
        census["configs"] = sorted(census["configs"])
        censuses.append(census)

    return _report(target, censuses, findings)


def _report(target: Path, censuses: list, findings: Findings) -> dict:
    return {
        "workspace": str(target),
        "iterations": censuses,
        "findings": findings.items,
        "counts": {
            "errors": len(findings.errors),
            "warnings": len(findings.warnings),
            # Warnings that name a workspace condition. The readers proceed on
            # these; this gate does not, and `ok` says which stance produced
            # the exit code rather than leaving a caller to infer it.
            "blocking_warnings": len(findings.blocking),
        },
        "ok": not findings.errors and not findings.blocking,
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def _print_findings(report: dict, stream) -> None:
    for item in report["findings"]:
        marker = "ERROR  " if item["level"] == "error" else "WARNING"
        print(f"{marker} {item['path']}", file=stream)
        print(f"        {item['message']}", file=stream)
        if item.get("expected"):
            print(f"        expected: {item['expected']}", file=stream)


def main(argv=None) -> int:
    configure_console()

    parser = argparse.ArgumentParser(
        prog="python -m scripts.preflight",
        description=(
            "Validate a better-skill-creator workspace's layout, naming and "
            "fields before any sub-agent spend. Filesystem and JSON only."
        ),
    )
    parser.add_argument(
        "workspace",
        type=Path,
        help="the workspace directory, or a single iteration-<N> directory",
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=None,
        help="check only iteration-<N>",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable report on stdout alone; all "
             "human-readable output goes to stderr",
    )
    args = parser.parse_args(argv)

    # With --json, stdout carries the payload and nothing else.
    log = sys.stderr if args.json else sys.stdout

    if not args.workspace.exists():
        message = f"workspace not found: {args.workspace}"
        print(f"ERROR   {message}", file=log)
        if args.json:
            json.dump({"ok": False, "error": message}, sys.stdout, indent=2)
            print()
        return 1

    if not args.workspace.is_dir():
        message = f"not a directory: {args.workspace}"
        print(f"ERROR   {message}", file=log)
        if args.json:
            json.dump({"ok": False, "error": message}, sys.stdout, indent=2)
            print()
        return 1

    report = preflight(args.workspace, args.iteration)

    _print_findings(report, log)

    print("", file=log)
    for census in report["iterations"]:
        configs = ", ".join(census["configs"]) or ABSENT
        # `run dir(s)` counts a flat configuration directory as the run-1 every
        # reader normalizes it to, so this line can no longer report "0 run
        # dir(s), 0 graded ... 2 discoverable by aggregation" about one tree.
        note = ""
        if not census["graded"] and not census.get("discovered", 0):
            note = " (no results yet - expected before the executor runs)"
        print(
            f"{census['path']}: {census['evals']} eval(s), "
            f"configs [{configs}], {census['runs']} run dir(s), "
            f"{census['graded']} graded, {census['timed']} timed, "
            f"{census.get('discovered', 0)} discoverable by aggregation{note}",
            file=log,
        )

    counts = report["counts"]
    if counts["errors"]:
        print(
            f"\n{counts['errors']} error(s), {counts['warnings']} warning(s). "
            f"Fix these before spending on sub-agents.\n"
            f"Expected layout:\n\n{CANONICAL_LAYOUT}\n",
            file=log,
        )
    elif counts["blocking_warnings"]:
        # Not a disagreement with the readers about severity - they classify
        # these as warnings and so does this script, from the same table. It is
        # a disagreement about what to do, which the shared table grants: they
        # are reading results that already exist, this runs before the money is
        # spent, and a layout fixed now costs a rename.
        print(
            f"\n{counts['blocking_warnings']} of {counts['warnings']} "
            f"warning(s) name a workspace condition. The readers accept "
            f"these and aggregate correctly; this gate does not, because "
            f"fixing the layout before the run costs a rename and fixing it "
            f"after costs the run.\n"
            f"Expected layout:\n\n{CANONICAL_LAYOUT}\n",
            file=log,
        )
    elif counts["warnings"]:
        print(f"\nNo errors, {counts['warnings']} warning(s). Safe to proceed.",
              file=log)
    else:
        print("\nWorkspace conforms to the expected layout, naming and fields.",
              file=log)

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
