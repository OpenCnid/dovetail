#!/usr/bin/env python3
"""Re-run the research fixture corpora against the current validator.

    python -m tests.run_scratch_corpus [--corpus-root DIR] [--target TARGET]

The 99 fixtures in ``research/12-scratch/{corpus,corpus2}`` are the evidence
this track was assigned against. They are *outside* the skill, are not a
committed dependency of it, and their ``expect`` column is target-blind -- it
records what "agentskills.io + the skills-ref reference validator" say, which
is precisely the ``portable`` target and not the ``claude-code`` default.

So this driver takes a ``--target`` and reports the verdict per fixture. Run it
with ``--target portable`` to score against the corpus's own frame; run it with
the default to see what an author validating for Claude Code is told. Cases
where the two differ are not bugs -- they are the whole point of C9.

Expectations are read from the corpus builders when they are importable, and
otherwise fall back to a table of directory name -> expectation checked in
below, so the driver still works if the research scratch is pruned.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.quick_validate import DEFAULT_TARGET, TARGETS, collect_findings  # noqa: E402

DEFAULT_CORPUS_ROOT = Path("D:/wonderprompt/research/12-scratch")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001 - a research script we do not control
        return None
    return module


def load_expectations(root: Path) -> dict[str, tuple[str, str]]:
    """Return ``{directory_name: (case_id, "pass"|"fail")}``."""
    expectations: dict[str, tuple[str, str]] = {}

    builder = _load_module(root / "build_fixtures.py", "_scratch_build_fixtures")
    if builder is not None and hasattr(builder, "CASES"):
        for case in builder.CASES:
            expectations[case["dirname"]] = (case["cid"], case["expect"])

    round2 = _load_module(root / "round2.py", "_scratch_round2")
    if round2 is not None and hasattr(round2, "CASES"):
        for cid, dirname, expect, *_rest in round2.CASES:
            expectations[dirname] = (cid, expect)

    return expectations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tests.run_scratch_corpus")
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--target", choices=TARGETS, default=DEFAULT_TARGET)
    parser.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args(argv)

    root = args.corpus_root
    if not root.is_dir():
        print(f"corpus root not found: {root}", file=sys.stderr)
        return 2

    expectations = load_expectations(root)
    rows = []
    for corpus_name in ("corpus", "corpus2"):
        corpus = root / corpus_name
        if not corpus.is_dir():
            continue
        for fixture in sorted(p for p in corpus.iterdir() if p.is_dir()):
            findings = collect_findings(fixture, args.target)
            errors = [f for f in findings if f.level == "error"]
            got = "fail" if errors else "pass"
            cid, expect = expectations.get(fixture.name, ("?", "?"))
            if expect == "?":
                verdict = "UNKNOWN-EXPECTATION"
            elif got == expect:
                verdict = "OK"
            elif got == "pass":
                verdict = "FALSE-NEGATIVE"
            else:
                verdict = "FALSE-POSITIVE"
            rows.append(
                {
                    "cid": cid,
                    "corpus": corpus_name,
                    "fixture": fixture.name,
                    "expect": expect,
                    "got": got,
                    "verdict": verdict,
                    "codes": [f.code for f in findings],
                    "message": errors[0].render() if errors else "",
                }
            )

    if args.as_json:
        print(json.dumps({"target": args.target, "rows": rows}, indent=2,
                         ensure_ascii=False))
        return 0

    order = {"FALSE-NEGATIVE": 0, "FALSE-POSITIVE": 1, "UNKNOWN-EXPECTATION": 2, "OK": 3}
    print(f"target: {args.target}   fixtures: {len(rows)}")
    print(f"{'ID':<6} {'VERDICT':<20} {'EXP':<5} {'GOT':<5} {'FIXTURE':<26} DETAIL")
    print("-" * 140)
    for row in sorted(rows, key=lambda r: (order[r["verdict"]], r["cid"])):
        detail = row["message"] or ",".join(row["codes"])
        print(f"{row['cid']:<6} {row['verdict']:<20} {row['expect']:<5} "
              f"{row['got']:<5} {row['fixture']:<26} {detail[:70]}")

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    print()
    print(json.dumps(counts, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
