#!/usr/bin/env bash
#
# test-release-check.sh — prove a hostile tag name stays text.
#
# The release gate takes exactly one input from outside the repository: the name
# of the tag that triggered it. Whoever pushes the tag chooses those bytes, and
# `git` accepts far more in a ref than the convention does -- `dovetail--v9.9.9$(id)`
# is a legal tag name and matches release.yml's `dovetail--v*` trigger.
#
# That workflow used to write `${{ github.ref_name }}` into a `run:` line.
# GitHub substitutes `${{ }}` into the shell source before bash parses it, so
# those five characters were not an argument -- they were a command
# substitution, and it ran on the runner with the workflow's token in the
# environment.
#
# Two layers, checked apart because they fail apart:
#
#   static     no workflow hands an attacker-nameable context to a `run:` body.
#              This checks the class rather than the instance: `github.ref_name`
#              is the one that bit, and `github.head_ref`, `github.actor` and
#              `github.event.*` reach a `run:` by the same route. Contexts that
#              are fixed enums -- `runner.os`, `github.ref_type` -- are nobody's
#              to choose and are left alone.
#   behaviour  check-release.sh, handed those strings directly, refuses them,
#              quotes them back verbatim, and leaves behind no file that a
#              substitution would have created.
#
# The behaviour layer fires its own canary first. Assertions that a file did not
# appear are free if nothing could have written one, and an unwritable temp
# directory would pass every one of them.
#
# The static layer is not delegated to `actionlint` because actionlint does not
# make this finding. Its `expression` check carries a fixed list of untrusted
# contexts, and `github.ref_name` is not on it: given this exact file before the
# fix, actionlint 1.7.12 exits 0, and reports the same line only once
# `github.ref_name` is swapped for `github.head_ref` (measured 2026-08-06,
# actionlint 1.7.12 with shellcheck 0.11.0). That list is right about most
# repositories and wrong about a release gate, where the tag name *is* the
# input and pushing one is the act being gated. Run actionlint as well — it
# finds things this does not — but not instead.
#
# Usage:
#   bash scripts/test-release-check.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Selected by capability rather than by name. The other scripts here want only
# stdlib and take the first python they find; this one parses YAML, and a box
# can easily carry a `python3` without PyYAML beside a `python` that has it.
PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import yaml' >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done

fail=0
note() { printf '  %-6s %s\n' "$1" "$2"; }

# ------------------------------------------------------------------ static
scan_workflows() {
  "$PY" - <<'PY'
import pathlib, re, sys, yaml

# Chosen by who names the value, not by where it appears. Each of these is
# written by somebody outside the repository -- a ref name, a fork's branch, a
# webhook payload field, a dispatch input -- and reaches the runner as bytes.
UNTRUSTED_EXACT = {
    "github.ref", "github.ref_name", "github.head_ref", "github.base_ref",
    "github.actor", "github.triggering_actor",
}
UNTRUSTED_PREFIX = ("github.event.", "inputs.")

def run_bodies(node, path="$"):
    """Every `run:` string in the document, with the path that reaches it."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "run" and isinstance(value, str):
                yield path, value
            else:
                yield from run_bodies(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from run_bodies(value, f"{path}[{index}]")

workflows = sorted(
    p for ext in ("*.yml", "*.yaml")
    for p in pathlib.Path(".github/workflows").glob(ext)
)
if not workflows:
    sys.exit("  no workflows found — the selection is wrong, not the repository")

findings = []
for workflow in workflows:
    document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    for path, body in run_bodies(document):
        for expression in re.findall(r"\$\{\{(.*?)\}\}", body, re.S):
            for identifier in re.findall(r"[A-Za-z_][A-Za-z0-9_.-]*", expression):
                if identifier in UNTRUSTED_EXACT or identifier.startswith(UNTRUSTED_PREFIX):
                    findings.append((workflow.as_posix(), path, identifier, expression.strip()))
                    break

for workflow in workflows:
    hits = [f for f in findings if f[0] == workflow.as_posix()]
    if hits:
        print(f"  {'FAIL':<6} {workflow.as_posix()}")
        for _, path, identifier, expression in hits:
            print(f"         {path} interpolates {identifier}")
            print(f"         ${{{{{expression}}}}}")
            print("         Pass it through env: and expand it quoted instead.")
    else:
        print(f"  {'ok':<6} {workflow.as_posix()}")

sys.exit(1 if findings else 0)
PY
}

echo "static — untrusted context in a run: body"

if [ -z "$PY" ]; then
  note FAIL "no python with PyYAML — the workflows were not parsed"
  echo "         Install it (python -m pip install pyyaml) rather than skipping:"
  echo "         this is the layer that reads the file the vulnerability lived in."
  fail=1
else
  scan_workflows || fail=1
fi

# The env: route only helps if the expansion on the other side is quoted, and an
# unquoted "$RELEASE_TAG" splits and globs rather than substituting -- a
# different bug with the same root, and one a reader skims past.
if grep -q 'RELEASE_TAG: \${{ github.ref_type ==' .github/workflows/release.yml; then
  note ok "release.yml carries the tag in env: RELEASE_TAG"
else
  note FAIL "release.yml no longer passes the tag through env:"
  fail=1
fi

if grep -qF 'check-release.sh --strict "$RELEASE_TAG"' .github/workflows/release.yml; then
  note ok 'release.yml expands "$RELEASE_TAG" quoted'
else
  note FAIL 'release.yml does not expand "$RELEASE_TAG" quoted'
  fail=1
fi

# --------------------------------------------------------------- behaviour
echo
echo "behaviour — check-release.sh against hostile tag text"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
CANARY="$TMP/canary"

# Prove the canary can fire, by running the substitution the way the runner did:
# text spliced into a script, then handed to bash. Everything below asserts this
# file is absent, and an assertion nothing could falsify is not a test.
bash -c ": ignored\$(touch '$CANARY')" >/dev/null 2>&1 || true
if [ -e "$CANARY" ]; then
  note ok "canary fires when text is evaluated"
  rm -f "$CANARY"
else
  note FAIL "canary cannot fire — every assertion below would pass vacuously"
  fail=1
fi

# `CANARY` stands in for the temp path so these read as the payloads they are.
# Command substitution, backticks, a statement separator, and a chained &&:
# four ways the same tag name becomes a second command.
HOSTILE=(
  'dovetail--v9.9.9$(touch CANARY)'
  'dovetail--v9.9.9`touch CANARY`'
  'dovetail--v0.4.1;touch CANARY'
  'dovetail--v0.4.1 && touch CANARY'
  '$(touch CANARY)'
  'dovetail--v0.4.1$(touch CANARY)'
)

for payload in "${HOSTILE[@]}"; do
  tag="${payload//CANARY/$CANARY}"
  out="$(bash scripts/check-release.sh --strict "$tag" 2>&1)" && rc=0 || rc=$?

  if [ "$rc" -ne 2 ]; then
    note FAIL "$payload — exit $rc, expected 2 (refused)"
    fail=1
  elif [ -e "$CANARY" ]; then
    note FAIL "$payload — the substitution RAN"
    rm -f "$CANARY"
    fail=1
  elif printf '%s\n' "$out" | grep -qF -- "$tag"; then
    note ok "$payload"
  else
    note FAIL "$payload — refused, but the tag was not echoed literally"
    fail=1
  fi
done

# Shape rejections with no payload in them. These are the other half of the
# validation: a tag that is merely wrong is refused the same way, so the check
# is of the convention rather than of a metacharacter denylist.
echo
echo "behaviour — tags that are simply not release tags"
for tag in 'dovetail--vfoo' 'v0.4.1' 'dovetail--v0.4' 'dovetail--v01.0.0' 'dovetail-v0.4.1'; do
  bash scripts/check-release.sh --strict "$tag" >/dev/null 2>&1 && rc=0 || rc=$?
  if [ "$rc" -eq 2 ]; then
    note ok "$tag"
  else
    note FAIL "$tag — exit $rc, expected 2 (refused)"
    fail=1
  fi
done

# ----------------------------------------------------------------- accepted
# Validation that rejects everything is not validation. A stub `gh` that exits
# non-zero keeps this offline: check-release.sh asks `gh auth status` first and
# says so when it skips, which is the branch this takes.
echo
echo "behaviour — tags the convention does accept"

mkdir -p "$TMP/bin"
printf '#!/usr/bin/env bash\nexit 1\n' > "$TMP/bin/gh"
chmod +x "$TMP/bin/gh"

out="$(PATH="$TMP/bin:$PATH" bash scripts/check-release.sh dovetail--v0.4.1 2>&1)" && rc=0 || rc=$?
if [ "$rc" -ne 2 ] && printf '%s\n' "$out" | grep -q '^release dovetail--v0.4.1 at '; then
  note ok "dovetail--v0.4.1 reaches the checks"
else
  note FAIL "dovetail--v0.4.1 was refused as malformed (exit $rc)"
  fail=1
fi

# A well-formed tag for a version the manifests do not carry has to fail as a
# *check*, not as a parse — exit 1 with a reason, which is what tells the two
# apart when this script is the thing being debugged.
out="$(PATH="$TMP/bin:$PATH" bash scripts/check-release.sh dovetail--v9.9.9 2>&1)" && rc=0 || rc=$?
if [ "$rc" -eq 1 ] && printf '%s\n' "$out" | grep -q 'tag says 9.9.9'; then
  note ok "dovetail--v9.9.9 fails the version check rather than the parse"
else
  note FAIL "dovetail--v9.9.9 — exit $rc, expected 1 with a version mismatch"
  fail=1
fi

# release.yml passes "$RELEASE_TAG" on workflow_dispatch too, where it is empty.
# The argument loop names that case; without it, an empty argument would fall
# through to `*)` and be adopted as the tag.
out="$(PATH="$TMP/bin:$PATH" bash scripts/check-release.sh --strict "" 2>&1)" && rc=0 || rc=$?
if printf '%s\n' "$out" | grep -q '^No tag given'; then
  note ok "an empty argument still means HEAD (the workflow_dispatch path)"
else
  note FAIL "an empty argument no longer means HEAD (exit $rc)"
  fail=1
fi

echo
[ "$fail" -eq 0 ] && echo "Release-check tests passed." || echo "Release-check tests FAILED."
exit "$fail"
