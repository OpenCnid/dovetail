#!/usr/bin/env python3
"""
Validate a workspace's graded artifacts - layout and field names - before
anything downstream trusts them.

Why this exists: aggregate_benchmark.py reads grading data with .get() chains
that used to fall back to zero, e.g.

    grading.get("summary", {}).get("pass_rate", 0.0)

So a grading.json with the wrong field names did not raise - it silently
aggregated to a 0% pass rate. That renders in the benchmark as a real result,
and the natural conclusion is "the skill performed terribly" when the actual
problem is that the grader emitted `met` instead of `passed`.

The older version of this script checked field *names* only. It therefore
green-lit the exact failure it was written to prevent: a structurally perfect
set of grading files sitting at a path the aggregator never walks validated
clean, and the very next command produced `"runs": []` and a table of zeros.
Placement is now checked as hard as content:

  * a grading.json the aggregator cannot reach is an ERROR that names the path
    found and the path expected;
  * the legacy flat layout (no `run-<K>/` level) is a WARNING - readers
    normalize it to `run-1`, but it is not the canonical form;
  * a flat grading.json with `run-<K>/` beside it is a WARNING that says the
    flat file was *not* read. This script used to print "readers normalize it
    to run-1" for that shape too, which asserted a read that did not happen:
    the run directories win and the flat file is discarded (R8);
  * `summary.failed` is cross-checked, and `passed + failed + abstained ==
    total == len(expectations)` is enforced;
  * `pass_rate` must be a JSON number in [0.0, 1.0], or `null` when nothing was
    graded - a string or a percentage is an error, not a coercion;
  * verdicts are ternary. `verdict` is one of `pass`, `fail`, `abstain`;
    `abstainReason` is required when and only when the verdict is
    `abstain`, and is one of the three typed reasons - `jurisdiction`,
    `evidence`, `underspecified` - each of which names a different repair. The
    retired boolean `passed` is detected by name and reported as
    the *previous contract* with the migration spelled out, rather than as a
    generic "unexpected type" that says nothing about what changed;
  * sibling `timing.json` and the eval directory's `eval_metadata.json` are
    validated too, because they are the inputs to the token, duration, and
    eval-name columns.

Usage:
    python -m scripts.validate_grading <path> [--json]

<path> may be a single grading.json or a directory to search recursively
(normally a workspace iteration directory). Exits non-zero if any file has an
error. Warnings alone do not fail the run.

With --json the machine-readable report goes to stdout *alone*; every
human-readable line goes to stderr.

Severity. Which findings are errors and which are warnings is not decided here.
`scripts.utils.WORKSPACE_CONDITIONS` is the one severity table and
`preflight`, `aggregate_benchmark` and this script all report from
it, tagging each finding `C12:<condition>=<severity>` so the three verdicts can
be diffed rather than trusted. What this script *does* with a severity is its
own business - it exits non-zero on errors and proceeds on warnings, where
`preflight` refuses both - but it does not get to decide what the condition is.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from scripts.utils import (
    FLAT_AND_RUN_DIRS,
    LEGACY_FLAT_LAYOUT,
    SCHEMA_INVALID,
    UNDISCOVERABLE_GRADING,
    UNPAIRED_EVALS,
    ZERO_RUNS,
    condition_line,
    condition_severity,
    condition_tag,
    configure_console,
)

# --------------------------------------------------------------------------
# The one canonical layout every reader here agrees on.
# --------------------------------------------------------------------------

CANONICAL_LAYOUT = """\
<workspace>/
  iteration-<N>/
    eval-<ID>-<descriptive-slug>/
      eval_metadata.json
      <config>/                  # with_skill | without_skill | old_skill
        run-<K>/                 # ALWAYS present; a single run is run-1
          outputs/
          grading.json
          timing.json"""

ITERATION_DIR_RE = re.compile(r"^iteration-(\d+)$")
EVAL_DIR_RE = re.compile(r"^eval-(\d+)(?:-([a-z0-9]+(?:-[a-z0-9]+)*))?$")
RUN_DIR_RE = re.compile(r"^run-(\d+)$")

# Three config names are canonical. Three more show up in the wild and are
# understood; anything else is discovered dynamically but flagged, because an
# unrecognised name is how a delta ends up pointing the wrong way.
CANONICAL_CONFIGS = ("with_skill", "without_skill", "old_skill")
EXTRA_KNOWN_CONFIGS = ("new_skill", "baseline", "no_skill", "skill")
RECOGNIZED_CONFIGS = CANONICAL_CONFIGS + EXTRA_KNOWN_CONFIGS

# Roles are assigned by name, never by sorted(). `with_skill` beat `old_skill`
# to primary only by the accident that '_' (0x5F) sorts before 'o' (0x6F).
BASELINE_ROLE_CONFIGS = ("without_skill", "old_skill", "baseline", "no_skill")
PRIMARY_ROLE_CONFIGS = ("with_skill", "new_skill", "skill")

#: Every directory name that carries a primary or baseline role. This is the
#: single source `preflight.IGNORED_DIRS` subtracts itself from. `skill` was in
#: PRIMARY_ROLE_CONFIGS *and* in preflight's ignore list, so a directory the
#: aggregator treated as the primary configuration was invisible to the
#: pre-spend gate: malformed timing under `skill/` produced no finding at all,
#: where the identical file under `with_skill/` produced two errors. Two
#: hardcoded lists that must stay disjoint and are not is a drift surface by
#: construction, so they are no longer two lists.
ROLE_CONFIGS = tuple(dict.fromkeys(PRIMARY_ROLE_CONFIGS + BASELINE_ROLE_CONFIGS))

# Directories that live beside config directories and are never configs.
NON_CONFIG_DIRS = ("outputs", "inputs", "files", "__pycache__")

ABSENT = "—"  # em dash - what an unknown measurement renders as


# --------------------------------------------------------------------------
# Verdicts are ternary, and "I cannot tell" is not a failure.
#
# These four names are the vocabulary. They live here, once, and
# `aggregate_benchmark` imports them rather than restating them - a second copy
# of a closed enum is a drift surface by construction.
# --------------------------------------------------------------------------

VERDICTS = ("pass", "fail", "abstain")

#: The three typed reasons an abstention may carry. They are not
#: interchangeable and they are not free text - each one names a different
#: repair, performed by a different person. Which one applies is settled by a
#: procedure, not by which description reads closest; the procedure is stated in
#: full in references/schemas.md ("Typing an abstention") and in the same words
#: in agents/grader.md and agents/panel/seat-frame.md. In brief - three
#: questions, first `yes` decides:
#:
#:   1. is something THIS RUN could have produced missing?   -> evidence
#:      (a standard handed in from outside is not evidence; it confers
#:      standing, and question 1 covers artifacts of this run only)
#:   2. does a standard that decides it already exist, held by someone
#:      nameable who is not this judge?                      -> jurisdiction
#:      (a preference nobody has fixed is not a standard)
#:   3. can the open term be quoted - the word, comparison or threshold
#:      nobody has fixed?                                    -> underspecified
#:
#: None of the three answerable is `jurisdiction`: failing to find a standard is
#: not the same as establishing that none exists. Question 3 being affirmative
#: rather than a fall-through is deliberate - `underspecified` is the only
#: reason that puts the defect outside both the judge and the run, so it is the
#: cheapest one to write, and the ladder makes it the earned answer rather than
#: the residue.
#:
#: The third reason was found from the ground up rather than designed in:
#: on a sixteen-item corpus, two independent blind readers
#: disagreed on exactly one item, and it was a comparative claim carrying an
#: undefined term - one ruled it decidable, the other said no judge could reach
#: it. Under the procedure that split is a disagreement about question 2, which
#: is arguable from evidence rather than from taste.
ABSTAIN_REASONS = ("jurisdiction", "evidence", "underspecified")

#: One line each, in the procedure's terms rather than as loose paraphrase -
#: these strings are what an author reads when the reason is missing, and a
#: paraphrase here would be a fourth description competing with the three
#: questions above.
ABSTAIN_REASON_MEANINGS = {
    "jurisdiction": ("a standard that decides it exists and is held by someone "
                     "who is not this judge - also the answer when none of the "
                     "three questions can be answered yes"),
    "evidence": ("something this run could have produced is missing; with it "
                 "in hand this judge could have ruled"),
    "underspecified": ("no standard exists for anyone to hold - the statement "
                       "leaves a term open, and that term is named in "
                       "`evidence`"),
}

#: Said once, by every component that has to say it. `pass_rate` is a rate over
#: the expectations that were actually *ruled on*; abstentions leave the
#: denominator entirely rather than landing in it as failures. Under the
#: previous contract they landed in it as failures, so an expectation nobody
#: could check counted as evidence against the skill.
PASS_RATE_RULE = ("`pass_rate = passed / (passed + failed)`, null when that "
                  "denominator is zero - a rate over nothing "
                  "is not zero")

#: Printed whenever a file is found in the shape the previous contract defined.
#: A generic "expectations[0].passed: must be a JSON boolean, got str" would be
#: true and useless: the reader's file is not malformed, it is *last version's
#: format*, and what they need is the mapping, not a type name.
PREVIOUS_CONTRACT_MESSAGE = """\
expectations[]: {count} entr{y} carr{ies} the boolean `passed` and no `verdict`. \
That is the PREVIOUS grading contract, not a malformed file.

      The current contract replaced it: a verdict is now one of `pass`, \
`fail`, `abstain`, and
      `passed` was REMOVED rather than kept alongside - two representations of \
one fact
      that must agree are a drift surface.

      Migrate each entry:
        {{"passed": true}}   ->  {{"verdict": "pass",  "abstainReason": null}}
        {{"passed": false}}  ->  {{"verdict": "fail",  "abstainReason": null}}
      but only where the evidence actually showed the expectation false. Where \
the
      grader could not tell, `false` was the old contract's answer and is no \
longer
      the right one:
        could not tell  ->  {{"verdict": "abstain", "abstainReason": \
"evidence"}}
        not this judge's call  ->  {{"verdict": "abstain", "abstainReason": \
"jurisdiction"}}
        nobody could tell  ->  {{"verdict": "abstain", "abstainReason": \
"underspecified"}}

      The three are different repairs: supply the missing artifact, reassign \
the judge,
      rewrite the assertion. Only the last one is the eval author's, which is \
why
      "nobody could tell" is not a spelling of "not this judge's call".

      And in `summary`: add `abstained`, keep `passed + failed + abstained == \
total`,
      and set {rule}."""


def reason_menu() -> str:
    """Every typed reason with its meaning, for a message that names them all.

    Generated from `ABSTAIN_REASON_MEANINGS` rather than written out, because
    the enum grew once (the third reason was added later) and a hand-written
    menu is exactly the copy that stays at two while the enum is at three.
    """
    items = [f"'{reason}' ({meaning})"
             for reason, meaning in ABSTAIN_REASON_MEANINGS.items()]
    return ", ".join(items[:-1]) + f", or {items[-1]}"


def previous_contract_message(count: int) -> str:
    """`PREVIOUS_CONTRACT_MESSAGE` with its counts agreed."""
    return PREVIOUS_CONTRACT_MESSAGE.format(
        count=count,
        y="y" if count == 1 else "ies",
        ies="ies" if count == 1 else "y",
        rule=PASS_RATE_RULE,
    )


def compute_pass_rate(passed: int, failed: int):
    """`passed / (passed + failed)`, or None when nothing was graded.

    The one implementation. `aggregate_benchmark` imports it; so do the tests.
    Returning 0.0 for an all-abstain run is the exact defect the abstain
    verdict closes - it is a confident number over data that does not
    support it.
    """
    graded = passed + failed
    if graded <= 0:
        return None
    return passed / graded


def summarize_verdicts(expectations) -> dict:
    """`{passed, failed, abstained, total, pass_rate}` over an expectations array.

    Entries whose `verdict` is not one of the three are counted in `total` and
    nowhere else, so a caller can see that the counts do not close rather than
    have an unknown verdict quietly absorbed into one of the buckets.
    """
    counts = {"pass": 0, "fail": 0, "abstain": 0}
    total = 0
    for exp in expectations or []:
        total += 1
        if isinstance(exp, dict) and exp.get("verdict") in counts:
            counts[exp["verdict"]] += 1
    return {
        "passed": counts["pass"],
        "failed": counts["fail"],
        "abstained": counts["abstain"],
        "total": total,
        "pass_rate": compute_pass_rate(counts["pass"], counts["fail"]),
    }


# --------------------------------------------------------------------------
# Field-name aliases seen in practice. Mapping wrong -> correct lets us give a
# directly actionable error instead of just "unexpected schema".
# --------------------------------------------------------------------------

EXPECTATION_ALIASES = {
    "name": "text",
    "assertion": "text",
    "description": "text",
    "details": "evidence",
    "reason": "evidence",
    "justification": "evidence",
    "abstain_reason": "abstainReason",
    "abstainreason": "abstainReason",
    "abstainedReason": "abstainReason",
}

#: Names a grader reaches for when it means `verdict`. Every one of them held a
#: boolean under the previous contract, so "rename it" is not the whole fix and
#: the message says so.
VERDICT_ALIASES = ("met", "result", "success", "outcome", "status")

SUMMARY_ALIASES = {
    "pass_rate_percent": "pass_rate",
    "num_passed": "passed",
    "num_failed": "failed",
    "num_total": "total",
    "num_abstained": "abstained",
    "abstentions": "abstained",
    "skipped": "abstained",
}


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

def read_json_file(path: Path):
    """Read a UTF-8 JSON file. Returns (data, error_message)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeError as e:
        # UnicodeDecodeError is a ValueError, NOT an OSError and NOT a
        # JSONDecodeError - the usual `except (json.JSONDecodeError, OSError)`
        # lets it escape as a bare traceback.
        return None, f"could not decode as UTF-8: {e}"
    except OSError as e:
        return None, f"could not read file: {e}"

    try:
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


# --------------------------------------------------------------------------
# Layout classification
# --------------------------------------------------------------------------

def is_eval_dir(path: Path) -> bool:
    """True if `path` is discoverable as an eval directory."""
    if not path.is_dir():
        return False
    if EVAL_DIR_RE.match(path.name):
        return True
    return (path / "eval_metadata.json").is_file()


def eval_id_from_dir_name(name: str):
    """The <ID> in `eval-<ID>-<slug>`, or None."""
    m = EVAL_DIR_RE.match(name)
    return int(m.group(1)) if m else None


def classify_grading_path(path: Path, root: Path) -> dict:
    """
    Decide whether `path` sits where the aggregator will find it.

    Returns a dict with:
        kind        "canonical" | "legacy_flat" | "unreachable"
        eval_dir    Path or None
        config      str or None
        run_number  int or None
        expected    the exact path this file should be at
        problem     a human sentence, when kind == "unreachable"
        warnings    list of non-fatal layout notes
    """
    warnings: list[str] = []
    try:
        rel_parts = list(path.resolve().relative_to(root.resolve()).parts)
    except (ValueError, OSError):
        rel_parts = [path.name]

    base = root
    if rel_parts and rel_parts[0] == "runs":
        # The pre-contract aggregator also accepted <dir>/runs/eval-*. Still
        # readable, but it is not the canonical form.
        warnings.append(
            "sits under a `runs/` directory; the canonical layout puts eval "
            "directories directly under the iteration directory"
        )
        base = root / "runs"
        rel_parts = rel_parts[1:]

    def unreachable(problem: str, expected_tail: str) -> dict:
        return {
            "kind": "unreachable",
            "eval_dir": None,
            "config": None,
            "run_number": None,
            "expected": str(base / expected_tail),
            "problem": problem,
            "warnings": warnings,
        }

    if not rel_parts or rel_parts[-1] != "grading.json":
        return unreachable(
            "not named grading.json",
            "eval-<ID>-<slug>/<config>/run-<K>/grading.json",
        )

    parts = rel_parts[:-1]

    if len(parts) == 1 and is_eval_dir(base / parts[0]):
        return unreachable(
            f"sits at the root of eval directory `{parts[0]}` instead of "
            f"inside a configuration's run directory",
            f"{parts[0]}/<config>/run-<K>/grading.json",
        )

    if len(parts) not in (2, 3):
        found = "/".join(parts) if parts else "(iteration root)"
        return unreachable(
            f"is {len(parts)} directory level(s) below the iteration root "
            f"({found}/grading.json); the aggregator walks exactly "
            f"eval-dir/config/run-dir",
            "eval-<ID>-<slug>/<config>/run-<K>/grading.json",
        )

    eval_name = parts[0]
    config = parts[1]
    eval_dir = base / eval_name

    if not is_eval_dir(eval_dir):
        return unreachable(
            f"eval directory `{eval_name}` matches neither `eval-<ID>-<slug>` "
            f"nor contains an eval_metadata.json, so no reader will discover it",
            f"eval-<ID>-{eval_name}/{config}/run-<K>/grading.json",
        )

    if not EVAL_DIR_RE.match(eval_name):
        warnings.append(
            f"eval directory `{eval_name}` is not `eval-<ID>-<slug>`; it is "
            f"reachable only because it carries an eval_metadata.json"
        )
    elif "-" not in eval_name[len("eval-"):]:
        warnings.append(
            f"eval directory `{eval_name}` has no descriptive slug; the expected "
            f"form is `{eval_name}-<descriptive-slug>`"
        )

    if config in NON_CONFIG_DIRS:
        return unreachable(
            f"`{config}` is not a configuration directory - the grading file "
            f"belongs beside the run's outputs/, not inside it",
            f"{eval_name}/<config>/run-<K>/grading.json",
        )

    if config not in RECOGNIZED_CONFIGS:
        warnings.append(
            f"configuration `{config}` is not one of "
            f"{', '.join(CANONICAL_CONFIGS)}; aggregation cannot infer whether "
            f"it is the primary or the baseline, and will require "
            f"--primary/--baseline"
        )

    if len(parts) == 2:
        # A flat grading.json is only normalizable to run-1 when nothing else
        # occupies that slot. When the config directory ALSO holds run-<K>/,
        # every reader takes the run directories and drops this file on the
        # floor - so reporting "readers normalize it to run-1" would assert a
        # read that did not happen. The severity table has a separate row for
        # it.
        config_dir = base / eval_name / config
        shadowing = []
        if config_dir.is_dir():
            try:
                shadowing = sorted(
                    child.name for child in config_dir.iterdir()
                    if child.is_dir() and RUN_DIR_RE.match(child.name)
                )
            except OSError:
                shadowing = []
        if shadowing:
            return {
                "kind": "shadowed_flat",
                "eval_dir": eval_dir,
                "config": config,
                "run_number": None,
                "expected": str(config_dir / "run-1" / "grading.json"),
                "problem": None,
                "warnings": warnings,
                "shadowed_by": shadowing,
            }
        return {
            "kind": "legacy_flat",
            "eval_dir": eval_dir,
            "config": config,
            "run_number": 1,
            "expected": str(base / eval_name / config / "run-1" / "grading.json"),
            "problem": None,
            "warnings": warnings,
        }

    run_name = parts[2]
    m = RUN_DIR_RE.match(run_name)
    if not m:
        return unreachable(
            f"run directory `{run_name}` is not `run-<K>` with an integer K",
            f"{eval_name}/{config}/run-1/grading.json",
        )

    return {
        "kind": "canonical",
        "eval_dir": eval_dir,
        "config": config,
        "run_number": int(m.group(1)),
        "expected": str(path),
        "problem": None,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# Content validation
# --------------------------------------------------------------------------

def _check_expectation(exp, idx, errors):
    """Validate one entry of the expectations array."""
    where = f"expectations[{idx}]"

    if not isinstance(exp, dict):
        errors.append(f"{where}: expected an object, got {type(exp).__name__}")
        return

    for wrong, correct in EXPECTATION_ALIASES.items():
        if wrong in exp and correct not in exp:
            errors.append(
                f"{where}: has '{wrong}' but the viewer reads '{correct}' - rename it"
            )

    for wrong in VERDICT_ALIASES:
        if wrong in exp and "verdict" not in exp:
            errors.append(
                f"{where}: has '{wrong}' where the contract has 'verdict'. "
                f"Renaming is not the whole fix - 'verdict' is one of 'pass', "
                f"'fail', 'abstain', not a boolean, and there is no boolean it "
                f"can be spelled as"
            )

    if "text" not in exp:
        errors.append(f"{where}: missing required field 'text'")
    elif not isinstance(exp["text"], str):
        errors.append(f"{where}.text: must be a string")
    elif not exp["text"].strip():
        errors.append(f"{where}.text: is empty - the viewer renders a bare "
                      "checkmark with no statement beside it")

    # ---- verdict --------------------------------------------------------
    legacy_boolean = "passed" in exp
    if legacy_boolean and "verdict" not in exp:
        # The file-level message already spelled out the migration; this line
        # only says which entries it applies to, so a 40-expectation file does
        # not repeat the whole mapping 40 times.
        errors.append(
            f"{where}: carries the retired boolean 'passed' and no 'verdict' "
            f"(the migration is spelled out above)"
        )
    else:
        if legacy_boolean:
            errors.append(
                f"{where}: carries BOTH 'verdict' and the retired boolean "
                f"'passed'. The current contract REMOVED 'passed'; it did not "
                f"keep it alongside 'verdict'. Two representations of one fact that "
                f"must agree drift the first time either is edited. Delete "
                f"'passed'"
            )

        verdict = exp.get("verdict")
        if "verdict" not in exp:
            errors.append(
                f"{where}: missing required field 'verdict' - one of "
                f"{', '.join(repr(v) for v in VERDICTS)}"
            )
        elif isinstance(verdict, bool) or not isinstance(verdict, str):
            hint = ""
            if isinstance(verdict, bool):
                hint = (f" - a boolean is the previous contract's shape; "
                        f"{verdict} is now "
                        f"\"{'pass' if verdict else 'fail'}\", and the case the "
                        f"boolean could not express is \"abstain\"")
            errors.append(
                f"{where}.verdict: must be a JSON string, got "
                f"{type(verdict).__name__} ({verdict!r}){hint}"
            )
        elif verdict not in VERDICTS:
            hint = ""
            lowered = verdict.strip().lower()
            if lowered in ("true", "passed", "yes", "ok"):
                hint = " - did you mean \"pass\"?"
            elif lowered in ("false", "failed", "no"):
                hint = (" - did you mean \"fail\"? If you could not tell, that "
                        "is \"abstain\", not \"fail\"")
            elif lowered in ("unknown", "skip", "skipped", "n/a", "na",
                             "unverifiable", "undetermined"):
                hint = (" - did you mean \"abstain\"? It also needs an "
                        "abstainReason")
            errors.append(
                f"{where}.verdict: {verdict!r} is not one of "
                f"{', '.join(repr(v) for v in VERDICTS)}{hint}"
            )

        # ---- abstainReason: required when and only when abstaining -------
        reason = exp.get("abstainReason")
        if verdict == "abstain":
            if reason is None:
                errors.append(
                    f"{where}.abstainReason: required when the verdict is "
                    f"'abstain', and "
                    f"{'absent' if 'abstainReason' not in exp else 'null'}. "
                    f"Use {reason_menu()}. An untyped "
                    f"abstention cannot be told from a judge that has stopped "
                    f"ruling on anything"
                )
            elif reason not in ABSTAIN_REASONS:
                errors.append(
                    f"{where}.abstainReason: {reason!r} is not one of "
                    f"{', '.join(repr(r) for r in ABSTAIN_REASONS)}"
                )
        elif verdict in ("pass", "fail") and reason is not None:
            errors.append(
                f"{where}.abstainReason: is {reason!r}, but the verdict is "
                f"{verdict!r}. A reason is required when and only when the "
                f"verdict is 'abstain'; write null or omit the field"
            )

    if "evidence" not in exp:
        errors.append(f"{where}: missing 'evidence' - graded results are not "
                      "reviewable without it")


def _check_summary(summary, expectations, errors):
    """Validate the summary block and cross-check it against expectations."""
    if not isinstance(summary, dict):
        errors.append(f"summary: expected an object, got {type(summary).__name__}")
        return

    for wrong, correct in SUMMARY_ALIASES.items():
        if wrong in summary and correct not in summary:
            errors.append(f"summary: has '{wrong}' but aggregation reads '{correct}'")

    for field in ("passed", "failed", "abstained", "total", "pass_rate"):
        if field not in summary:
            hint = ""
            if field == "abstained":
                hint = (f" - `total` counts every "
                        f"expectation, `abstained` counts the ones no verdict "
                        f"was reached on, and {PASS_RATE_RULE}")
            errors.append(f"summary: missing required field '{field}'{hint}")

    def whole(field):
        """The integer at `summary[field]`, or None when it is not one."""
        value = summary.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value

    for field in ("passed", "failed", "abstained", "total"):
        value = summary.get(field)
        if field in summary and whole(field) is None:
            errors.append(
                f"summary.{field}: must be a JSON integer, got "
                f"{type(value).__name__} ({value!r})"
            )
        elif whole(field) is not None and value < 0:
            errors.append(f"summary.{field}: must not be negative, got {value!r}")

    passed, failed = whole("passed"), whole("failed")
    abstained, total = whole("abstained"), whole("total")
    counts_known = None not in (passed, failed, abstained, total)
    # None when the counts are unusable, so "is the denominator zero?" stays a
    # question we decline to answer rather than one we answer wrongly.
    denominator = (passed + failed) if None not in (passed, failed) else None

    rate = summary.get("pass_rate")
    rate_is_number = (not isinstance(rate, bool)
                      and isinstance(rate, (int, float)))
    if "pass_rate" in summary:
        if rate is None:
            # Legitimate, and required, when nothing was graded. Checked
            # against the denominator below rather than accepted outright.
            pass
        elif not rate_is_number:
            hint = ""
            if isinstance(rate, str):
                hint = (" - pass_rate is a JSON number or null, not a string; a "
                        "string compares and averages as garbage downstream")
            errors.append(
                f"summary.pass_rate: must be a number in [0.0, 1.0] or null, "
                f"got {type(rate).__name__} ({rate!r}){hint}"
            )
        elif not 0.0 <= rate <= 1.0:
            hint = (" (looks like a percentage - pass_rate is a 0..1 fraction)"
                    if rate > 1 else "")
            errors.append(f"summary.pass_rate: {rate} is outside [0.0, 1.0]{hint}")

    # passed + failed + abstained == total == len(expectations).
    if counts_known and passed + failed + abstained != total:
        errors.append(
            f"summary: passed ({passed}) + failed ({failed}) + abstained "
            f"({abstained}) = {passed + failed + abstained}, but total is {total}"
        )

    # The denominator excludes abstentions, and a rate
    # over an empty denominator is null. `0.0` there is a measurement nobody
    # made - it is the same lie as a benchmark of zeros over no runs.
    if denominator is not None and "pass_rate" in summary:
        if denominator == 0 and rate is not None:
            errors.append(
                f"summary.pass_rate is {rate!r} but nothing was graded "
                f"(passed 0 + failed 0). {PASS_RATE_RULE}. A run whose "
                f"expectations all abstained has no pass rate; reporting "
                f"{rate!r} states a result the run does not contain"
            )
        elif denominator > 0 and rate is None:
            errors.append(
                f"summary.pass_rate is null but {denominator} expectation(s) "
                f"were graded (passed {passed} + failed {failed}). null means "
                f"the denominator was zero; here it is {denominator}"
            )
        elif denominator > 0 and rate_is_number:
            expected = compute_pass_rate(passed, failed)
            if abs(rate - expected) > 0.01:
                hints = []
                if rate > 1:
                    hints.append("looks like a percentage - pass_rate is a "
                                 "0..1 fraction")
                if total and abstained and abs(rate - passed / total) <= 0.01:
                    hints.append(
                        f"this is passed/total ({passed}/{total}); abstentions "
                        f"leave the denominator, so it is "
                        f"passed/(passed+failed) = {passed}/{denominator}")
                hint = f" ({'; '.join(hints)})" if hints else ""
                errors.append(
                    f"summary.pass_rate is {rate} but the counts imply "
                    f"{expected:.2f}{hint}"
                )

    # Cross-check against the expectations the summary claims to summarize. A
    # summary that disagrees with its own array is worse than a missing one -
    # it aggregates cleanly and lies.
    if not isinstance(expectations, list):
        return

    verdicted = [e for e in expectations
                 if isinstance(e, dict) and e.get("verdict") in VERDICTS]
    if len(verdicted) != len(expectations):
        return  # already reported per-expectation; counts would be noise

    actual = summarize_verdicts(verdicted)
    # The counts branch above already compared `pass_rate` against the numbers
    # the summary itself declares. When those numbers agree with the array, the
    # two checks are the same check and saying it twice trains people to skim.
    counts_agree = counts_known and (passed, failed, abstained, total) == (
        actual["passed"], actual["failed"], actual["abstained"], actual["total"])

    if total is not None and total != actual["total"]:
        errors.append(
            f"summary.total is {total} but there are {actual['total']} "
            f"expectations"
        )
    for field, verdict in (("passed", "pass"), ("failed", "fail"),
                           ("abstained", "abstain")):
        # `summary.failed` was the cross-check that was missing before: a file
        # claiming {"passed":1,"failed":0,"total":3} over 3 expectations
        # validated clean and the viewer rendered "1 passed, 0 failed of 3".
        # `abstained` is the same check on the abstention count.
        claimed = whole(field)
        if claimed is not None and claimed != actual[field]:
            errors.append(
                f"summary.{field} is {claimed} but {actual[field]} "
                f"expectation(s) have verdict=\"{verdict}\""
            )

    if counts_agree:
        return

    if actual["pass_rate"] is None and rate is not None:
        errors.append(
            f"summary.pass_rate is {rate!r} but every expectation abstained, "
            f"so nothing was graded. {PASS_RATE_RULE}"
        )
    elif actual["pass_rate"] is not None and rate_is_number:
        if abs(rate - actual["pass_rate"]) > 0.01:
            hint = (" (looks like a percentage - pass_rate is a 0..1 fraction)"
                    if rate > 1 else "")
            errors.append(
                f"summary.pass_rate is {rate} but expectations imply "
                f"{actual['pass_rate']:.2f}{hint}"
            )


def validate_grading_file(path: Path):
    """
    Validate one grading.json's *content*.

    Returns (errors, warnings), both lists of human-readable strings.
    """
    errors: list[str] = []
    warnings: list[str] = []

    data, read_error = read_json_file(path)
    if read_error:
        return [read_error], warnings

    if not isinstance(data, dict):
        return [f"top level must be an object, got {type(data).__name__}"], warnings

    expectations = data.get("expectations")
    if expectations is None:
        if "assertions" in data:
            errors.append(
                "has 'assertions' but grading.json's graded results are called "
                "'expectations'. 'assertions' is the input set an "
                "author writes into eval_metadata.json; 'expectations' is what "
                "the grader returns)"
            )
        else:
            errors.append("missing required field 'expectations'")
    elif not isinstance(expectations, list):
        errors.append(
            f"expectations: must be an array, got {type(expectations).__name__}")
    elif not expectations:
        errors.append("expectations: array is empty - nothing was graded")
    else:
        # Say "this is the previous contract" once, before the per-entry
        # errors, and say it in terms of the migration. Reported per entry it
        # reads as forty type errors; reported once it reads as what it is.
        legacy = sum(1 for e in expectations
                     if isinstance(e, dict) and "passed" in e
                     and "verdict" not in e)
        if legacy:
            errors.append(previous_contract_message(legacy))
        for idx, exp in enumerate(expectations):
            _check_expectation(exp, idx, errors)

    if "summary" not in data:
        errors.append("missing required field 'summary' - without it there is "
                      "no pass rate to aggregate")
    else:
        _check_summary(data["summary"], expectations, errors)

    if "timing" in data:
        # Graders do not write a timing block. Ignorable rather
        # than corrupting now that the aggregator reads timing.json only, so a
        # warning - but it is the block that used to gate the token column
        # closed and silently substitute a character count for it.
        warnings.append(
            "carries a 'timing' block; timing belongs only in the "
            "sibling timing.json, and aggregation ignores this block"
        )

    return errors, warnings


def validate_timing_file(path: Path):
    """Validate a timing.json. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    data, read_error = read_json_file(path)
    if read_error:
        return [read_error], warnings

    if not isinstance(data, dict):
        return [f"top level must be an object, got {type(data).__name__}"], warnings

    for field, types, label in (
        ("total_tokens", (int,), "integer"),
        ("duration_ms", (int,), "integer"),
        ("total_duration_seconds", (int, float), "number"),
    ):
        if field not in data:
            warnings.append(
                f"missing '{field}'; that cell renders as {ABSENT} (unknown), "
                f"never 0"
            )
            continue
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, types):
            errors.append(
                f"{field}: must be a JSON {label}, got "
                f"{type(value).__name__} ({value!r})"
            )
        elif value < 0:
            errors.append(f"{field}: must not be negative, got {value!r}")

    return errors, warnings


def validate_eval_metadata(path: Path, dir_eval_id=None):
    """Validate an eval_metadata.json."""
    errors: list[str] = []
    warnings: list[str] = []

    data, read_error = read_json_file(path)
    if read_error:
        return [read_error], warnings

    if not isinstance(data, dict):
        return [f"top level must be an object, got {type(data).__name__}"], warnings

    eval_id = data.get("eval_id")
    if "eval_id" not in data:
        errors.append("missing required field 'eval_id'")
    elif isinstance(eval_id, bool) or not isinstance(eval_id, int):
        errors.append(
            f"eval_id: must be a JSON integer, got {type(eval_id).__name__} "
            f"({eval_id!r}) - a non-integer id breaks the sort in every consumer"
        )
    elif dir_eval_id is not None and eval_id != dir_eval_id:
        errors.append(
            f"eval_id is {eval_id} but the directory name says {dir_eval_id}; "
            f"the two must be equal"
        )

    name = data.get("eval_name")
    if "eval_name" not in data:
        errors.append("missing required field 'eval_name' - it is the section "
                      "header in the rendered benchmark")
    elif not isinstance(name, str) or not name.strip():
        errors.append(f"eval_name: must be a non-empty string, got {name!r}")

    prompt = data.get("prompt")
    if "prompt" not in data:
        errors.append("missing required field 'prompt' - the reviewer is asked "
                      "to judge outputs without seeing what produced them")
    elif not isinstance(prompt, str) or not prompt.strip():
        errors.append(f"prompt: must be a non-empty string, got {prompt!r}")

    if "assertions" not in data:
        warnings.append(
            "missing 'assertions' (the input set an author writes; "
            "'expectations' is the graded result in grading.json)"
        )
    elif not isinstance(data["assertions"], list):
        errors.append(
            f"assertions: must be an array, got {type(data['assertions']).__name__}")

    if "expectations" in data:
        warnings.append(
            "carries 'expectations'; in eval_metadata.json the input set is "
            "called 'assertions'"
        )

    return errors, warnings


# --------------------------------------------------------------------------
# Tree walk
# --------------------------------------------------------------------------

def _infer_iteration_root(grading_path: Path, fallback: Path | None = None) -> Path:
    """
    Given a single grading.json, find the iteration directory it belongs to.

    A named `iteration-<N>` ancestor is authoritative - anchoring there is what
    makes a misplaced file's diagnosis point at the right directory instead of
    at whatever happens to sit four levels up. Failing that, canonical puts the
    file four levels down and the legacy flat layout three, so try both and
    keep whichever the classifier recognises. Pointing this script at a
    workspace root, at one iteration, or at a single file then all behave
    identically.
    """
    for ancestor in grading_path.parents:
        if ITERATION_DIR_RE.match(ancestor.name):
            return ancestor

    for depth in (4, 3):
        candidate = grading_path
        for _ in range(depth):
            candidate = candidate.parent
        if classify_grading_path(grading_path, candidate)["kind"] != "unreachable":
            return candidate

    if fallback is not None:
        return fallback
    return grading_path.parent.parent.parent.parent


def validate_tree(target: Path) -> dict:
    """
    Validate every grading.json under `target`, plus the timing.json and
    eval_metadata.json each one depends on.

    Returns a report dict (also the --json payload).
    """
    if target.is_dir():
        grading_files = sorted(target.rglob("grading.json"))
    else:
        grading_files = [target]

    # Each file is anchored to its own iteration directory, so pointing this
    # at a workspace root, at one iteration, or at a single file all behave
    # identically.
    fallback = target if target.is_dir() else target.parent
    roots = {p: _infer_iteration_root(p, fallback) for p in grading_files}

    entries = []
    eval_dirs: dict[str, int | None] = {}
    # (config, eval_id) -> {"surviving": {run numbers}, "dropped": {...}} over
    # the files a reader will actually read, for the pairing check below. Both
    # halves are needed: an eval missing from one configuration and an eval
    # whose runs a schema failure removed from one side are the same defect,
    # and the second one is invisible without the dropped set.
    read_runs: dict = {}
    error_count = 0
    warning_count = 0

    def note(condition: str, detail: str, errors: list, warnings: list) -> None:
        """File the finding at the shared table's severity - never at one we pick.

        `errors` vs `warnings` is decided by the shared table and by nothing in
        this file. That is the whole point: three components used to make
        this choice independently, and made it three different ways.
        """
        line = condition_line(condition, detail)
        if condition_severity(condition) == "error":
            errors.append(line)
        else:
            warnings.append(line)

    for path in grading_files:
        placement = classify_grading_path(path, roots[path])
        errors, warnings = validate_grading_file(path)
        if errors:
            errors.insert(0, condition_line(
                SCHEMA_INVALID,
                f"grading.json: {len(errors)} schema error(s), listed below"))
        warnings = list(placement["warnings"]) + warnings

        if placement["kind"] == "unreachable":
            errors.insert(0, condition_line(
                UNDISCOVERABLE_GRADING,
                f"placement: this file {placement['problem']}.\n"
                f"      found:    {path}\n"
                f"      expected: {placement['expected']}\n"
                f"      Aggregation will never see it; the benchmark would "
                f"report nothing for this run."
            ))
        elif placement["kind"] == "shadowed_flat":
            # R8: the flat file is NOT normalized to run-1 here - the run
            # directories win and this file is dropped. Saying "readers
            # normalize it" would assert a read that did not happen.
            used = ", ".join(placement.get("shadowed_by", []))
            note(FLAT_AND_RUN_DIRS,
                 f"placement: this flat grading.json is NOT read. The "
                 f"aggregator takes the run director{'y' if used.count(',') == 0 else 'ies'} "
                 f"({used}) beside it and discards this file. Move it to\n"
                 f"      {placement['expected']}\n"
                 f"      or delete it, so which grading was used is not a "
                 f"question of directory-listing order.",
                 errors, warnings)
        elif placement["kind"] == "legacy_flat":
            note(LEGACY_FLAT_LAYOUT,
                 f"placement: the canonical layout wants\n"
                 f"      {placement['expected']}",
                 errors, warnings)

        if placement["kind"] in ("canonical", "legacy_flat") and placement["config"]:
            eval_key = (eval_id_from_dir_name(placement["eval_dir"].name)
                        if placement["eval_dir"] is not None else None)
            slot = read_runs.setdefault(
                (placement["config"], eval_key),
                {"surviving": set(), "dropped": set()})
            half = "dropped" if errors else "surviving"
            slot[half].add(placement["run_number"])

        run_dir = path.parent
        timing_path = run_dir / "timing.json"
        if timing_path.is_file():
            t_errors, t_warnings = validate_timing_file(timing_path)
            if t_errors:
                errors.append(condition_line(
                    SCHEMA_INVALID,
                    f"timing.json: {len(t_errors)} schema error(s), listed below"))
            errors.extend(f"timing.json: {e}" for e in t_errors)
            warnings.extend(f"timing.json: {w}" for w in t_warnings)
        elif placement["kind"] != "unreachable":
            warnings.append(
                f"no timing.json beside it ({timing_path}); the token and "
                f"duration cells for this run render as {ABSENT}, not 0"
            )

        if placement["eval_dir"] is not None:
            key = str(placement["eval_dir"])
            if key not in eval_dirs:
                eval_dirs[key] = eval_id_from_dir_name(placement["eval_dir"].name)

        entries.append({
            "path": str(path),
            "kind": placement["kind"],
            "config": placement["config"],
            "run_number": placement["run_number"],
            "errors": errors,
            "warnings": warnings,
        })
        error_count += len(errors)
        warning_count += len(warnings)

    metadata_entries = []
    for key, dir_eval_id in sorted(eval_dirs.items()):
        meta_path = Path(key) / "eval_metadata.json"
        if not meta_path.is_file():
            errors = [
                f"missing.\n"
                f"      expected: {meta_path}\n"
                f"      Without it the eval has no name and no prompt, and the "
                f"reviewer judges outputs blind."
            ]
            warnings = []
        else:
            errors, warnings = validate_eval_metadata(meta_path, dir_eval_id)
        metadata_entries.append({
            "path": str(meta_path),
            "errors": errors,
            "warnings": warnings,
        })
        error_count += len(errors)
        warning_count += len(warnings)

    # ---- workspace-level conditions -------------------------------------
    # These are properties of the tree, not of any one file, and the other two
    # components report them too. Same conditions, same severities, same
    # sentences - the components differ only in what they do next.
    workspace: list[dict] = []

    def workspace_note(condition: str, detail: str, path) -> None:
        severity = condition_severity(condition)
        workspace.append({
            "path": str(path),
            "level": severity,
            "condition": condition,
            "message": condition_line(condition, detail),
        })

    readable = sum(1 for e in entries if e["kind"] in ("canonical", "legacy_flat"))
    if entries and readable == 0:
        workspace_note(
            ZERO_RUNS,
            f"{len(entries)} grading file(s) were found and not one of them "
            f"sits where the aggregator looks, so aggregation over this tree "
            f"produces nothing",
            target,
        )

    # Pairing. `validate_grading` has no notion of primary/baseline - roles are
    # resolved in `aggregate_benchmark`, which imports this module, so asking
    # for them here would be a cycle. Comparing every configuration against the
    # union is the same check for the two-configuration case, and stricter for
    # three, which is the safe direction.
    configs = sorted({config for config, _ in read_runs})

    # A workspace holding only the baseline. `aggregate_benchmark` will set
    # `primary: null` rather than relabel the survivor, and this says why
    # before anyone reads a benchmark that is about the wrong configuration.
    # The mirror case - only the primary - is the legitimate
    # single-configuration record and is not this condition.
    if (len(configs) == 1 and configs[0] in BASELINE_ROLE_CONFIGS
            and any(slot["surviving"] for slot in read_runs.values())):
        workspace_note(
            UNPAIRED_EVALS,
            f"`{configs[0]}` is the only configuration with readable gradings, "
            f"and it is a baseline. Nothing here measures a configuration under "
            f"test, so there is no comparison to make and no primary to name",
            target,
        )

    if len(configs) >= 2:
        all_evals = {eval_id for _, eval_id in read_runs}
        for config in configs:
            missing = sorted(
                str(e) for e in all_evals
                if not (read_runs.get((config, e)) or {}).get("surviving"))
            if missing:
                workspace_note(
                    UNPAIRED_EVALS,
                    f"configuration `{config}` has no readable, valid grading "
                    f"for eval id(s) {', '.join(missing)}, which other "
                    f"configurations ran. Any delta would pool them",
                    target,
                )

        # Run-level pairing: an exclusion that shrinks one side's run set for
        # an eval and not the other's moves a delta without invalidating it.
        # Unequal counts that no exclusion caused are a sampling choice, not
        # this condition.
        for eval_id in sorted(all_evals, key=str):
            slots = {c: read_runs.get((c, eval_id)) for c in configs}
            present = {c: s for c, s in slots.items() if s and s["surviving"]}
            if len(present) < 2:
                continue
            survivors = {c: tuple(sorted(s["surviving"]))
                         for c, s in present.items()}
            lost_any = any((slots[c] or {}).get("dropped") for c in present)
            if len(set(survivors.values())) > 1 and lost_any:
                detail = "; ".join(
                    f"`{c}` keeps run(s) "
                    f"{', '.join(str(r) for r in survivors[c])} and loses "
                    f"{', '.join(str(r) for r in sorted(slots[c]['dropped'])) or 'none'}"
                    for c in sorted(present))
                workspace_note(
                    UNPAIRED_EVALS,
                    f"eval {eval_id} is not comparable: {detail}",
                    target,
                )

    error_count += sum(1 for w in workspace if w["level"] == "error")
    warning_count += sum(1 for w in workspace if w["level"] == "warning")

    return {
        "root": str(target),
        "grading_files": entries,
        "eval_metadata_files": metadata_entries,
        "workspace_findings": workspace,
        "counts": {
            "grading_files": len(entries),
            "canonical": sum(1 for e in entries if e["kind"] == "canonical"),
            "legacy_flat": sum(1 for e in entries if e["kind"] == "legacy_flat"),
            "shadowed_flat": sum(1 for e in entries
                                 if e["kind"] == "shadowed_flat"),
            "unreachable": sum(1 for e in entries if e["kind"] == "unreachable"),
            "errors": error_count,
            "warnings": warning_count,
        },
        "ok": error_count == 0,
    }


def _print_entry(path: str, errors, warnings, stream):
    if errors:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "OK  "
    print(f"{status} {path}", file=stream)
    for err in errors:
        print(f"    - {err}", file=stream)
    for warn in warnings:
        print(f"    ! {warn}", file=stream)


def main(argv=None) -> int:
    configure_console()

    parser = argparse.ArgumentParser(
        prog="python -m scripts.validate_grading",
        description=(
            "Validate grading.json files (and the timing.json / "
            "eval_metadata.json they depend on) for layout and field names."
        ),
    )
    parser.add_argument(
        "path",
        type=Path,
        help="a grading.json, or a directory to search recursively "
             "(normally a workspace iteration directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable report on stdout alone; all "
             "human-readable output goes to stderr",
    )
    args = parser.parse_args(argv)

    # With --json, stdout carries the payload and nothing else.
    human = sys.stderr if args.json else sys.stdout

    if not args.path.exists():
        print(f"Error: path not found: {args.path}", file=human)
        if args.json:
            json.dump({"ok": False, "error": f"path not found: {args.path}"},
                      sys.stdout, indent=2)
            print()
        return 1

    if args.path.is_dir() and not list(args.path.rglob("grading.json")):
        message = (
            f"No grading.json found anywhere under {args.path}.\n"
            f"{condition_line(ZERO_RUNS)}\n"
            f"Expected layout:\n\n{CANONICAL_LAYOUT}\n"
        )
        print(message, file=human)
        if args.json:
            json.dump({"ok": False, "error": "no grading.json files found",
                       "condition": ZERO_RUNS,
                       "condition_tag": condition_tag(ZERO_RUNS),
                       "root": str(args.path)}, sys.stdout, indent=2)
            print()
        return 1

    report = validate_tree(args.path)

    for entry in report["grading_files"] + report["eval_metadata_files"]:
        _print_entry(entry["path"], entry["errors"], entry["warnings"], human)

    for finding in report["workspace_findings"]:
        marker = "FAIL" if finding["level"] == "error" else "WARN"
        print(f"{marker} {finding['path']}", file=human)
        print(f"    - {finding['message']}", file=human)

    counts = report["counts"]
    print("", file=human)
    shadowed = (f", {counts['shadowed_flat']} shadowed-flat"
                if counts["shadowed_flat"] else "")
    print(
        f"{counts['grading_files']} grading file(s): "
        f"{counts['canonical']} canonical, "
        f"{counts['legacy_flat']} legacy-flat, "
        f"{counts['unreachable']} unreachable{shadowed}.",
        file=human,
    )

    if counts["errors"]:
        print(
            f"{counts['errors']} error(s), {counts['warnings']} warning(s). "
            f"Fix these before aggregating.\n"
            f"Expected layout:\n\n{CANONICAL_LAYOUT}\n",
            file=human,
        )
    elif counts["warnings"]:
        print(f"No errors, {counts['warnings']} warning(s). Aggregation will "
              f"proceed; the warnings above say what is non-canonical.",
              file=human)
    else:
        print(f"All {counts['grading_files']} grading file(s) valid.", file=human)

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
