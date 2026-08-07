#!/usr/bin/env python3
"""Run the eval + improve loop until all pass or max iterations reached.

Combines run_eval.py and improve_description.py in a loop, tracking history and
returning the best description found. Supports a train/test split so the
optimizer cannot see the held-out scores it is selected on.

The loop refuses to hand back a "best" description when the measurement that
chose it produced no signal — a harness that errors on every probe scores every
negative query as a pass, which reads as "precision 100%, recall 0%", which
reads as a diagnosis of the description rather than of the harness. That is the
failure this guard exists to make impossible.
"""

import argparse
import json
import random
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

from scripts.generate_report import generate_html
from scripts.improve_description import improve_description
from scripts.run_eval import (
    SAFE_PERMISSION_MODE,
    add_probe_arguments,
    check_permission_mode,
    check_probe_arguments,
    check_scaffold,
    check_skill_md_encoding,
    load_eval_set,
    print_eval_stats,
    project_spend,
    run_eval,
)
from scripts.utils import configure_console, parse_skill_md


def split_eval_set(
    eval_set: list[dict], holdout: float, seed: int = 42
) -> tuple[list[dict], list[dict]]:
    """Split eval set into train and test sets, stratified by should_trigger.

    Raises ValueError when either train stratum would be empty. A train set with
    no positive queries cannot fail, so the loop would announce "all train
    queries passed on iteration 1" and stop — the most convincing possible
    output produced by the least informative possible split.
    """
    random.seed(seed)

    trigger = [e for e in eval_set if e["should_trigger"]]
    no_trigger = [e for e in eval_set if not e["should_trigger"]]

    random.shuffle(trigger)
    random.shuffle(no_trigger)

    n_trigger_test = max(1, int(len(trigger) * holdout))
    n_no_trigger_test = max(1, int(len(no_trigger) * holdout))

    test_set = trigger[:n_trigger_test] + no_trigger[:n_no_trigger_test]
    train_set = trigger[n_trigger_test:] + no_trigger[n_no_trigger_test:]

    train_pos = sum(1 for e in train_set if e["should_trigger"])
    train_neg = len(train_set) - train_pos
    if train_pos == 0 or train_neg == 0:
        raise ValueError(
            f"Train split has {train_pos} positive and {train_neg} negative queries "
            f"(from {len(trigger)} positives and {len(no_trigger)} negatives at "
            f"--holdout {holdout}). A stratum of zero cannot fail, so the loop would "
            f"exit on iteration 1 reporting success. Add more queries "
            f"(8-10 of each is the documented target) or lower --holdout."
        )

    return train_set, test_set


def _summarize(result_list: list[dict]) -> dict:
    passed = sum(1 for r in result_list if r["pass"] is True)
    failed = sum(1 for r in result_list if r["pass"] is False)
    errored = sum(1 for r in result_list if r["pass"] is None)
    return {
        "passed": passed,
        "failed": failed,
        "errored": errored,
        "total": len(result_list),
    }


def _positive_triggers(result_list: list[dict]) -> tuple[int, int]:
    """(triggers, scored runs) over should-trigger queries."""
    pos = [r for r in result_list if r["should_trigger"]]
    return sum(r["triggers"] for r in pos), sum(r["runs"] for r in pos)


def run_loop(
    eval_set: list[dict],
    skill_path: Path,
    description_override: str | None,
    num_workers: int,
    timeout: int,
    max_iterations: int,
    runs_per_query: int,
    trigger_threshold: float,
    holdout: float,
    model: str,
    verbose: bool,
    eval_model: str | None = None,
    max_tools: int = 4,
    setting_sources: str | None = "project,local",
    include_partial_messages: bool = True,
    permission_mode: str | None = SAFE_PERMISSION_MODE,
    scaffold: str | None = None,
    live_report_path: Path | None = None,
    log_dir: Path | None = None,
    allow_host_permissions: bool = False,
) -> dict:
    """Run the eval + improvement loop."""
    # parse_skill_md raises SkillMdError (a ValueError) rather than handing back
    # a string it cannot vouch for. main() catches ValueError and exits 1, and
    # main() also runs check_skill_md_encoding before the spend gate — so a bad
    # SKILL.md stops the run before any probe, attributed to the file rather
    # than showing up as a probe error, which would mean something else.
    try:
        name, original_description, content = parse_skill_md(skill_path)
    except ValueError as exc:
        raise ValueError(f"{skill_path / 'SKILL.md'}: {exc}") from exc
    current_description = description_override or original_description

    if holdout > 0:
        train_set, test_set = split_eval_set(eval_set, holdout)
        if verbose:
            print(
                f"Split: {len(train_set)} train, {len(test_set)} test (holdout={holdout})",
                file=sys.stderr,
            )
    else:
        train_set = eval_set
        test_set = []

    n_train = len(train_set)
    history: list[dict] = []
    exit_reason = "unknown"
    warnings: list[str] = []
    total_cost = 0.0
    saw_cost = False
    # references/description-optimization.md tells the reader to check
    # `harness_health` after a loop run. run_eval returns one per call; the loop
    # used to fold it into prose warnings and drop the key, so the documented
    # check had nothing to read. Carried here per iteration and rolled up below.
    health_by_iteration: list[dict] = []

    for iteration in range(1, max_iterations + 1):
        if verbose:
            print(f"\n{'=' * 60}", file=sys.stderr)
            print(f"Iteration {iteration}/{max_iterations}", file=sys.stderr)
            print(f"Description: {current_description}", file=sys.stderr)
            print(f"{'=' * 60}", file=sys.stderr)

        # Evaluate train + test together in one batch for parallelism.
        all_queries = train_set + test_set
        t0 = time.time()
        all_results = run_eval(
            eval_set=all_queries,
            skill_name=name,
            description=current_description,
            num_workers=num_workers,
            timeout=timeout,
            runs_per_query=runs_per_query,
            trigger_threshold=trigger_threshold,
            model=eval_model or model,
            max_tools=max_tools,
            setting_sources=setting_sources,
            include_partial_messages=include_partial_messages,
            permission_mode=permission_mode,
            scaffold=scaffold,
            verbose=verbose,
            allow_host_permissions=allow_host_permissions,
        )
        eval_elapsed = time.time() - t0

        cost = all_results["summary"].get("actual_cost_usd")
        if cost is not None:
            total_cost += cost
            saw_cost = True

        # Split by index, not by query text: two identical query strings must
        # stay two rows rather than pooling into one.
        train_result_list = [r for r in all_results["results"] if r["index"] < n_train]
        test_result_list = [r for r in all_results["results"] if r["index"] >= n_train]

        train_summary = _summarize(train_result_list)
        train_results = {"results": train_result_list, "summary": train_summary}

        if test_set:
            test_summary = _summarize(test_result_list)
            test_results = {"results": test_result_list, "summary": test_summary}
        else:
            test_results = None
            test_summary = None

        errored_runs = all_results["summary"]["errored_runs"]
        if errored_runs:
            warnings.append(
                f"iteration {iteration}: {errored_runs} probe(s) errored and were "
                f"excluded from scoring"
            )

        health = all_results.get("harness_health", {}) or {}
        health_by_iteration.append({"iteration": iteration, **health})
        if health.get("competing_installed_skills"):
            warnings.append(
                f"iteration {iteration}: an installed copy of this skill is visible to "
                f"the probe session ({health['competing_installed_skills']}); it shadows "
                f"the probe and pins recall at 0%"
            )
        if health.get("probes_where_clone_was_not_registered"):
            warnings.append(
                f"iteration {iteration}: "
                f"{health['probes_where_clone_was_not_registered']} probe(s) never had "
                f"their command file registered, so they could not have triggered"
            )

        history.append({
            "iteration": iteration,
            "description": current_description,
            "train_passed": train_summary["passed"],
            "train_failed": train_summary["failed"],
            "train_errored": train_summary["errored"],
            "train_total": train_summary["total"],
            "train_results": train_result_list,
            "test_passed": test_summary["passed"] if test_summary else None,
            "test_failed": test_summary["failed"] if test_summary else None,
            "test_errored": test_summary["errored"] if test_summary else None,
            "test_total": test_summary["total"] if test_summary else None,
            "test_results": test_result_list if test_results else None,
            "errored_runs": errored_runs,
            "harness_health": health,
            "eval_seconds": round(eval_elapsed, 1),
            "eval_cost_usd": cost,
            # For backward compat with the report generator.
            "passed": train_summary["passed"],
            "failed": train_summary["failed"],
            "total": train_summary["total"],
            "results": train_result_list,
        })

        if live_report_path:
            partial_output = {
                "original_description": original_description,
                "best_description": current_description,
                "best_score": "in progress",
                "iterations_run": len(history),
                "holdout": holdout,
                "train_size": len(train_set),
                "test_size": len(test_set),
                "history": history,
            }
            live_report_path.write_text(
                generate_html(partial_output, auto_refresh=True, skill_name=name),
                encoding="utf-8",
            )

        if verbose:
            print_eval_stats("Train", train_result_list, eval_elapsed)
            if test_results:
                print_eval_stats("Test ", test_result_list)

        if train_summary["errored"] == train_summary["total"]:
            exit_reason = f"all_queries_errored (iteration {iteration})"
            print(
                f"\nEvery train query errored on iteration {iteration}. Stopping — "
                f"nothing here measures the description.",
                file=sys.stderr,
            )
            break

        if train_summary["failed"] == 0 and train_summary["errored"] == 0:
            exit_reason = f"all_passed (iteration {iteration})"
            if verbose:
                print(f"\nAll train queries passed on iteration {iteration}!", file=sys.stderr)
            break

        if iteration == max_iterations:
            exit_reason = f"max_iterations ({max_iterations})"
            if verbose:
                print(f"\nMax iterations reached ({max_iterations}).", file=sys.stderr)
            break

        if verbose:
            print("\nImproving description...", file=sys.stderr)

        t0 = time.time()
        # Strip test scores from history so the improvement model can't see them.
        blinded_history = [
            {k: v for k, v in h.items() if not k.startswith("test_")} for h in history
        ]
        try:
            new_description = improve_description(
                skill_name=name,
                skill_content=content,
                current_description=current_description,
                eval_results=train_results,
                history=blinded_history,
                model=model,
                log_dir=log_dir,
                iteration=iteration,
                permission_mode=permission_mode,
                allow_host_permissions=allow_host_permissions,
            )
        except Exception as exc:  # noqa: BLE001
            # Every completed iteration is paid for. Do not throw them away
            # because the optimizer call hit a 429 or a slow SessionEnd hook.
            note = f"{type(exc).__name__}: {exc}"
            history[-1]["note"] = f"improve_description failed: {note}"
            warnings.append(f"iteration {iteration}: improve_description failed ({note})")
            exit_reason = f"improve_failed (iteration {iteration})"
            print(f"\nimprove_description failed: {note}", file=sys.stderr)
            print("Keeping the results collected so far.", file=sys.stderr)
            break
        improve_elapsed = time.time() - t0

        if verbose:
            print(f"Proposed ({improve_elapsed:.1f}s): {new_description}", file=sys.stderr)

        current_description = new_description

    # ---- Best-iteration selection -----------------------------------------
    # max() returns the first maximal element, so a tie keeps the earliest
    # (usually original) description. That is the right conservative behaviour
    # *when the measurement is real*; the guard below is what makes sure it is.
    if test_set:
        best = max(history, key=lambda h: h["test_passed"] or 0)
        best_score = f"{best['test_passed']}/{best['test_total']}"
    else:
        best = max(history, key=lambda h: h["train_passed"])
        best_score = f"{best['train_passed']}/{best['train_total']}"

    # ---- Did we measure anything at all? ----------------------------------
    total_pos_triggers = 0
    total_pos_runs = 0
    for h in history:
        rows = (h["train_results"] or []) + (h["test_results"] or [])
        t, r = _positive_triggers(rows)
        total_pos_triggers += t
        total_pos_runs += r

    apply_recommended = True
    if total_pos_runs == 0:
        apply_recommended = False
        warnings.append(
            "no positive query produced a single scored run across any iteration — "
            "the harness measured nothing"
        )
    elif total_pos_triggers == 0:
        apply_recommended = False
        warnings.append(
            f"recall is 0% across all {len(history)} iteration(s) "
            f"({total_pos_runs} scored positive runs, 0 triggers). That is the "
            f"signature of a broken measurement, not of a narrow description. "
            f"Check for an installed copy of this skill shadowing the probe, and "
            f"re-run one query with --num-workers 1 --verbose before believing it."
        )

    # ---- Harness health, rolled up across every iteration -----------------
    # A loop that never got a registration answer reports None, not 0. Zero
    # unregistered probes and "nobody ever told us" are different facts, and
    # rendering the second as the first is the whole defect class here.
    reporting = [h for h in health_by_iteration if h.get("probes_reporting_registration") is not None]
    rolled_health = {
        "probes_reporting_registration": (
            sum(h["probes_reporting_registration"] for h in reporting) if reporting else None
        ),
        "probes_where_clone_was_not_registered": (
            sum(h.get("probes_where_clone_was_not_registered") or 0 for h in reporting)
            if reporting
            else None
        ),
        "competing_installed_skills": sorted(
            {s for h in health_by_iteration for s in (h.get("competing_installed_skills") or [])}
        ),
        # Invariant across iterations — the scaffold is the same tree each time —
        # but carried here so a reader of the loop's health does not have to
        # open per_iteration to find out what the probes never saw.
        "scaffold_exclusions": (
            next((h["scaffold_exclusions"] for h in health_by_iteration
                  if h.get("scaffold_exclusions")), [])
        ),
        "scaffold_disclosures": (
            next((h["scaffold_disclosures"] for h in health_by_iteration
                  if h.get("scaffold_disclosures")), [])
        ),
        "per_iteration": health_by_iteration,
    }

    if best["description"] == original_description and len(history) > 1:
        warnings.append(
            "the best-scoring description is the original — the loop found no "
            "measured improvement to apply"
        )

    if verbose:
        print(f"\nExit reason: {exit_reason}", file=sys.stderr)
        print(f"Best score: {best_score} (iteration {best['iteration']})", file=sys.stderr)
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    if not apply_recommended:
        print(
            "\nDO NOT APPLY this description. The measurement did not produce a signal.",
            file=sys.stderr,
        )

    return {
        "exit_reason": exit_reason,
        "original_description": original_description,
        "best_description": best["description"],
        "best_score": best_score,
        "best_train_score": f"{best['train_passed']}/{best['train_total']}",
        "best_test_score": f"{best['test_passed']}/{best['test_total']}" if test_set else None,
        "best_is_original": best["description"] == original_description,
        "final_description": current_description,
        "iterations_run": len(history),
        "holdout": holdout,
        "train_size": len(train_set),
        "test_size": len(test_set),
        "apply_recommended": apply_recommended,
        "measurement_warnings": warnings,
        "harness_health": rolled_health,
        "actual_cost_usd": round(total_cost, 4) if saw_cost else None,
        "history": history,
    }


def main():
    configure_console()
    parser = argparse.ArgumentParser(
        description="Run eval + improve loop",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override starting description")
    parser.add_argument("--max-iterations", type=int, default=5,
                        help="Max improvement iterations")
    parser.add_argument("--holdout", type=float, default=0.4,
                        help="Fraction of eval set held out for testing (0 to disable)")
    parser.add_argument("--model", required=True, help="Model for the improvement call")
    parser.add_argument("--eval-model", default=None,
                        help="Model for the trigger probes. Defaults to --model. These are "
                             "different questions: which model's triggering behaviour you are "
                             "measuring, versus which model writes the new description.")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    parser.add_argument("--report", default="auto",
                        help="HTML report path ('auto' for a temp file, 'none' to disable)")
    parser.add_argument("--results-dir", default=None,
                        help="Save results.json, report.html and logs under a timestamped "
                             "subdirectory here")
    add_probe_arguments(parser)
    args = parser.parse_args()

    check_probe_arguments(args.num_workers, args.runs_per_query)
    # Governs the improvement call as well as the probes. `--model` names a
    # different model for it, and it is a second `claude -p` on this machine
    # carrying the same SKILL.md body, so it takes the same posture rather than
    # a posture of its own.
    permission_mode = check_permission_mode(
        args.permission_mode, args.allow_host_permissions
    )

    eval_set = load_eval_set(Path(args.eval_set))
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    check_skill_md_encoding(skill_path)
    name, _, _ = parse_skill_md(skill_path)

    check_scaffold(args.scaffold)

    # Both train and test are evaluated every iteration, so the holdout does not
    # reduce the probe count — the whole eval set is priced, every iteration.
    project_spend(
        n_queries=len(eval_set),
        runs_per_query=args.runs_per_query,
        iterations=args.max_iterations,
        model=args.eval_model or args.model,
        cost_per_probe=args.cost_per_probe,
        max_cost=args.max_cost,
        confirm_threshold=args.confirm_threshold,
        assume_yes=args.yes,
        label="optimization loop",
        permission_mode=permission_mode,
    )

    if args.report != "none":
        if args.report == "auto":
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            live_report_path = (
                Path(tempfile.gettempdir())
                / f"skill_description_report_{skill_path.name}_{timestamp}.html"
            )
        else:
            live_report_path = Path(args.report)
        live_report_path.write_text(
            "<html><head><meta charset='utf-8'>"
            "<meta http-equiv='refresh' content='5'></head>"
            "<body><h1>Starting optimization loop...</h1></body></html>",
            encoding="utf-8",
        )
        webbrowser.open(live_report_path.as_uri())
    else:
        live_report_path = None

    if args.results_dir:
        timestamp = time.strftime("%Y-%m-%d_%H%M%S")
        results_dir = Path(args.results_dir) / timestamp
        results_dir.mkdir(parents=True, exist_ok=True)
    else:
        results_dir = None

    log_dir = results_dir / "logs" if results_dir else None

    try:
        output = run_loop(
            eval_set=eval_set,
            skill_path=skill_path,
            description_override=args.description,
            num_workers=args.num_workers,
            timeout=args.timeout,
            max_iterations=args.max_iterations,
            runs_per_query=args.runs_per_query,
            trigger_threshold=args.trigger_threshold,
            holdout=args.holdout,
            model=args.model,
            eval_model=args.eval_model,
            verbose=args.verbose,
            max_tools=args.max_tools,
            setting_sources=args.setting_sources or None,
            include_partial_messages=not args.no_partial_messages,
            permission_mode=permission_mode,
            scaffold=args.scaffold,
            live_report_path=live_report_path,
            log_dir=log_dir,
            allow_host_permissions=args.allow_host_permissions,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    json_output = json.dumps(output, indent=2)
    print(json_output)
    if results_dir:
        (results_dir / "results.json").write_text(json_output, encoding="utf-8")

    if live_report_path:
        live_report_path.write_text(
            generate_html(output, auto_refresh=False, skill_name=name), encoding="utf-8"
        )
        print(f"\nReport: {live_report_path}", file=sys.stderr)

    if results_dir and live_report_path:
        (results_dir / "report.html").write_text(
            generate_html(output, auto_refresh=False, skill_name=name), encoding="utf-8"
        )

    if results_dir:
        print(f"Results saved to: {results_dir}", file=sys.stderr)

    if output.get("actual_cost_usd") is not None:
        print(f"Actual reported cost: ${output['actual_cost_usd']:.4f}", file=sys.stderr)

    if not output["apply_recommended"]:
        sys.exit(4)


if __name__ == "__main__":
    main()
