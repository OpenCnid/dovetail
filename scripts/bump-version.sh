#!/usr/bin/env bash
#
# bump-version.sh — move this pack's version everywhere it is written, at once.
#
# The version lives in more than one file, and the copies are not decorative.
# The marketplace entry carries `strict: true`, and `claude plugin tag` refuses
# to tag a release when plugin.json and the enclosing marketplace entry
# disagree. A hand-edit that updates one and forgets the other therefore fails
# at the moment you are trying to ship, which is the worst time to find out.
#
# .version-bump.json is the list. Add a file there and this script covers it.
#
# Usage:
#   bash scripts/bump-version.sh 0.3.0     # set the version everywhere
#   bash scripts/bump-version.sh --check   # report disagreement, change nothing

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v python3 >/dev/null 2>&1 && PY=python3 || PY=python
command -v "$PY" >/dev/null 2>&1 || { echo "python is required for JSON editing" >&2; exit 2; }

[ "$#" -eq 1 ] || { echo "usage: bash scripts/bump-version.sh <version>|--check" >&2; exit 2; }

"$PY" - "$1" <<'PY'
import json, sys, re

target = sys.argv[1]
check = target == "--check"

if not check and not re.fullmatch(r"\d+\.\d+\.\d+", target):
    sys.exit(f"not a semantic version: {target}")

spec = json.load(open(".version-bump.json"))

def get(obj, path):
    for part in path.split("."):
        obj = obj[int(part)] if part.isdigit() else obj[part]
    return obj

def put(obj, path, value):
    parts = path.split(".")
    for part in parts[:-1]:
        obj = obj[int(part)] if part.isdigit() else obj[part]
    last = parts[-1]
    obj[int(last) if last.isdigit() else last] = value

found, changed = {}, 0
for entry in spec["files"]:
    path, field = entry["path"], entry["field"]
    data = json.load(open(path))
    try:
        current = get(data, field)
    except (KeyError, IndexError):
        sys.exit(f"{path}: no such field {field} — .version-bump.json is stale")
    found[f"{path} {field}"] = current
    if not check and current != target:
        put(data, field, target)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        changed += 1

width = max(len(k) for k in found)
for k, v in found.items():
    print(f"  {k:<{width}}  {v}")
print()

if check:
    distinct = set(found.values())
    if len(distinct) == 1:
        print(f"Every version agrees: {distinct.pop()}")
    else:
        # Disagreement is the failure this script exists to catch, so it exits
        # non-zero and is safe to wire into CI.
        sys.exit(f"DISAGREEMENT across {len(distinct)} versions: {sorted(distinct)}")
else:
    print(f"{changed} file(s) updated to {target}. Nothing is committed.")
PY
