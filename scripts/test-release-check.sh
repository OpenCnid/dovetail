#!/usr/bin/env bash
#
# test-release-check.sh — prove a hostile tag name stays text, and that each
# mode grades the commit it says it grades.
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
# Three layers, checked apart because they fail apart:
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
#   modes      HEAD mode grades HEAD and explicit-tag mode grades the tag, in a
#              throwaway repository built so that those are different commits --
#              and each mode holds its subject to the standard its own question
#              needs: `main`'s tip for HEAD mode, anywhere on `main` for a tag.
#              Every one of the five checks grades that commit too, rather than
#              the files lying in the working tree. The third layer is newest and
#              answers a different question from the other two: not "is this
#              input safe?" but "is this the commit the answer is about?" See its
#              own blocks further down.
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

# The dispatch path has to name its mode rather than leave it to be inferred
# from an empty argument, which is what it did while the inference was wrong.
if grep -qF 'check-release.sh --strict --head' .github/workflows/release.yml; then
  note ok "release.yml asks for HEAD mode explicitly"
else
  note FAIL "release.yml no longer passes --head on the dispatch path"
  fail=1
fi

# `github.ref_type` is `tag` for a dispatch launched from a tag ref as well as
# for a tag push, so it cannot tell the two events apart; `github.event_name`
# can. This pins the field the mode is chosen on, not the shape of the steps.
if grep -q "if: github.event_name" .github/workflows/release.yml; then
  note ok "release.yml selects the mode on github.event_name"
else
  note FAIL "release.yml no longer selects the mode on github.event_name"
  fail=1
fi

# HEAD mode's already-released check reads `refs/tags/`, and `fetch-depth: 0` is
# the line that puts tags on the runner. Without it the check cannot fire, and
# the dispatch run goes green on a version that is already published — the
# original bug, restored by checkout configuration rather than by code.
if grep -qF 'fetch-depth: 0' .github/workflows/release.yml; then
  note ok "release.yml checks out with tags (fetch-depth: 0)"
else
  note FAIL "release.yml no longer fetches tags — the already-released check cannot fire"
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

# --------------------------------------------------------------------- modes
# What this catches, stated as the bug it was written from: run with no tag,
# check-release.sh printed "checking HEAD" and then, from the moment the
# manifests' own tag existed, graded that tag's commit instead. Every commit
# that landed on `main` afterwards keeping the same version inherited a verdict
# about `313b9e4`. `workflow_dispatch` ran exactly that path, so the workflow
# advertised as answering "is main releasable right now?" answered about a
# commit two releases back, and answered green.
#
# Nothing above would have seen it. The empty-argument assertion greps the
# banner for `No tag given` and stops; no test in this file has ever looked at
# *which commit* the gate chose, which is the only thing that distinguishes the
# two modes at all.
#
# So this needs a repository where the two answers differ, and builds one: the
# six files the gate reads, a commit, a tag on it, and a later commit carrying
# the same version. That is the shape `main` takes the moment anything lands
# after a release.
#
# Built rather than cloned, for two measured reasons (2026-08-06, git
# 2.47.1.windows.1). `git clone` of this repository exits 128 on Windows --
# `skills/better-skill-creator/tests/fixtures/` passes MAX_PATH, checkout
# aborts, 487 paths never arrive -- and `checks.yml` runs this script on
# `windows-latest`. And a clone's `origin/main` is frozen at clone time, so a
# commit made after it fails the ancestry check for a reason with nothing to do
# with what is under test.
echo
echo "behaviour — the commit each mode actually grades"

# Selected the way check-release.sh selects it (`:65`), and separately from the
# PyYAML-capable `$PY` above: this needs `json`, which every python has, and the
# static layer's interpreter may legitimately be absent.
command -v python3 >/dev/null 2>&1 && PYJSON=python3 || PYJSON=python

FIXTURE="$TMP/fixture"
mkdir -p "$FIXTURE/.claude-plugin" "$FIXTURE/scripts"
cp .claude-plugin/plugin.json .claude-plugin/marketplace.json "$FIXTURE/.claude-plugin/"
cp .version-bump.json RELEASE-NOTES.md "$FIXTURE/"
cp scripts/check-release.sh scripts/bump-version.sh "$FIXTURE/scripts/"

# Read out of the manifest, not written here, so the next version bump does not
# leave this section asserting against a tag nobody will cut.
FIXTURE_TAG="$("$PYJSON" -c 'import json;d=json.load(open(".claude-plugin/plugin.json"));print(d["name"]+"--v"+d["version"])')"

# `-c init.defaultBranch` silences the hint on git >= 2.28 and `symbolic-ref`
# names the branch on anything older, where `init -b` does not exist. The gate
# needs a ref called `main` either way.
git -C "$FIXTURE" -c init.defaultBranch=main init -q
git -C "$FIXTURE" symbolic-ref HEAD refs/heads/main

# The repository root carries `.gitattributes` pinning `eol=lf`; a fixture built
# by hand inherits only whatever `core.autocrlf` the box has. Off, so the copied
# scripts stay byte-identical and git stops warning about a rewrite nobody here
# wants -- a shell script checked out with CRLF fails as `$'\r': command not
# found`, which reads as the gate being broken.
git -C "$FIXTURE" config core.autocrlf false

# Identity per-invocation. A hosted runner has none configured and a bare
# `git commit` exits 128 there; `-c` writes to no config file.
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "release $FIXTURE_TAG"
git -C "$FIXTURE" tag "$FIXTURE_TAG"
RELEASED="$(git -C "$FIXTURE" rev-parse HEAD)"

# The later commit. It adds a new file rather than touching a manifest, so the
# version the gate reads stays byte-identical to the tagged one -- an unchanged
# version is exactly the case that produced the false green.
: > "$FIXTURE/after-the-tag.txt"
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "after the tag"
DESCENDANT="$(git -C "$FIXTURE" rev-parse HEAD)"

# A fresh `git init` has only `refs/heads/main`; the gate prefers
# `refs/remotes/origin/main` and that is what a CI checkout hands it. Point it
# at the tip so the ancestry check runs on the ref it will actually meet.
git -C "$FIXTURE" update-ref refs/remotes/origin/main "$DESCENDANT"

RELEASED_SHORT="$(git -C "$FIXTURE" rev-parse --short "$RELEASED")"
DESCENDANT_SHORT="$(git -C "$FIXTURE" rev-parse --short "$DESCENDANT")"

# This section's canary, and it is not decoration: if either commit silently
# failed -- a runner with no git identity is how -- HEAD *is* the tagged commit,
# `--is-ancestor` says ok, and every assertion below passes while proving the
# opposite of what it claims.
if [ "$RELEASED" != "$DESCENDANT" ]; then
  note ok "fixture: $DESCENDANT_SHORT is a later commit than $FIXTURE_TAG ($RELEASED_SHORT)"
else
  note FAIL "fixture: HEAD and $FIXTURE_TAG are one commit — the assertions below prove nothing"
  fail=1
fi

# Both routes into HEAD mode, against a fixture whose tag exists and points
# elsewhere. `""` is the argument release.yml's tag step passes when there is no
# tag; `--head` is what its dispatch step passes now.
for form in "" "--head"; do
  label="${form:-<no argument>}"
  out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$form" 2>&1)" && rc=0 || rc=$?

  if ! printf '%s\n' "$out" | grep -qF "release $FIXTURE_TAG at $DESCENDANT_SHORT"; then
    note FAIL "$label — HEAD mode did not grade HEAD ($DESCENDANT_SHORT)"
    fail=1
  elif printf '%s\n' "$out" | grep -qF "release $FIXTURE_TAG at $RELEASED_SHORT"; then
    note FAIL "$label — HEAD mode resolved the existing tag ($RELEASED_SHORT)"
    fail=1
  elif [ "$rc" -ne 1 ]; then
    note FAIL "$label — exit $rc, expected 1 (a released version cannot be released again)"
    fail=1
  elif ! printf '%s\n' "$out" | grep -qF "is already released, at $RELEASED_SHORT"; then
    note FAIL "$label — failed, but not because the version is already out"
    fail=1
  else
    note ok "$label — grades $DESCENDANT_SHORT and refuses to re-release $RELEASED_SHORT"
  fi
done

# The other half, and what makes the pair a mode test rather than one behaviour
# described twice: the same repository, the same tag name, the other mode, and a
# different commit comes back.
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$FIXTURE_TAG" 2>&1)" && rc=0 || rc=$?
if printf '%s\n' "$out" | grep -qF "release $FIXTURE_TAG at $RELEASED_SHORT"; then
  note ok "$FIXTURE_TAG — explicit-tag mode still grades the tagged commit ($RELEASED_SHORT)"
else
  note FAIL "$FIXTURE_TAG — explicit-tag mode no longer resolves the tag (exit $rc)"
  fail=1
fi

# ------------------------------------------------------ ancestry is not enough
# Grading HEAD is only half of "is `main` releasable right now?". The other half
# is what counts as an acceptable HEAD, and check 4 used to answer it with
# `git merge-base --is-ancestor` in both modes -- which every commit `main` has
# ever carried satisfies. So the mode assertions above could pass while the gate
# still returned green about a commit `main` had moved past.
#
# `workflow_dispatch` takes a ref and the operator chooses it, so a run launched
# from a stale branch or an old tag lands precisely there. Measured on this
# repository with HEAD at `313b9e4` and `origin/main` at `5b36154`, `--strict
# --head` reported every check `ok` and exited 0, and the commit it was missing
# was `5b36154` -- the fix to this gate's own injection hole.
#
# The fixture already holds the two commits this needs; park HEAD on the tagged
# one and `main` stays a commit ahead, which is that dispatch exactly. The tag
# still points at HEAD here, so the already-released check passes and check 4 is
# the only thing that can fail -- which is what makes the exit code below mean
# one specific thing.
echo
echo "behaviour — HEAD mode on a commit main has moved past"

git -C "$FIXTURE" -c advice.detachedHead=false checkout -q "$RELEASED"

out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" --head 2>&1)" && rc=0 || rc=$?
if ! printf '%s\n' "$out" | grep -qF "release $FIXTURE_TAG at $RELEASED_SHORT"; then
  note FAIL "--head — did not grade HEAD ($RELEASED_SHORT)"
  fail=1
elif printf '%s\n' "$out" | grep -qE '^ +ok +commit is on refs/remotes/origin/main$'; then
  # The exact line the shared ancestor test printed. Reverting to it fails here
  # and on the exit code below, rather than only on a message nobody reads.
  note FAIL "--head — behind $DESCENDANT_SHORT and still called on main"
  fail=1
elif [ "$rc" -ne 1 ]; then
  note FAIL "--head — exit $rc, expected 1 (HEAD is not main's tip)"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "commit(s) behind refs/remotes/origin/main"; then
  note FAIL "--head — failed, but not because HEAD is behind main"
  fail=1
else
  note ok "--head — $RELEASED_SHORT is an ancestor of main and is refused anyway"
fi

# The half that must NOT change, and the reason this is not simply a stricter
# check in both modes: same repository, same commit, explicit-tag mode, and
# being an ancestor is the correct answer there. A released tag is always behind
# the tip, so requiring the tip would refuse every real release.
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$FIXTURE_TAG" 2>&1)" && rc=0 || rc=$?
if printf '%s\n' "$out" | grep -qE '^ +ok +commit is on refs/remotes/origin/main$'; then
  note ok "$FIXTURE_TAG — explicit-tag mode still accepts an ancestor ($RELEASED_SHORT)"
else
  note FAIL "$FIXTURE_TAG — explicit-tag mode no longer accepts an ancestor (exit $rc)"
  fail=1
fi

# And back onto the tip: the controls below run HEAD mode again and need a HEAD
# that passes check 4, or they would report the tag state they are testing.
git -C "$FIXTURE" checkout -q main

# A control for the two HEAD-mode assertions above. Drop this version's tag,
# leave the pack's other tags in place, and the same command on the same commit
# passes: so the failure was that tag, and not the fixture being unreleasable
# for some reason nobody named.
#
# The other tag is not scenery. "This version is not out yet" and "this clone
# has no tags" are different states with opposite verdicts, and a control that
# deleted every tag would assert the second must exit 0 -- which is exactly the
# fail-open the next case exists to forbid.
OTHER_TAG="${FIXTURE_TAG%%--v*}--v0.0.1"
git -C "$FIXTURE" tag "$OTHER_TAG" "$RELEASED"
git -C "$FIXTURE" tag -d "$FIXTURE_TAG" >/dev/null
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" --head 2>&1)" && rc=0 || rc=$?
if [ "$rc" -eq 0 ] && printf '%s\n' "$out" | grep -qF "release $FIXTURE_TAG at $DESCENDANT_SHORT"; then
  note ok "--head — this version untagged, the same commit passes"
else
  note FAIL "--head — untagged, $DESCENDANT_SHORT still does not pass (exit $rc)"
  fail=1
fi

# The third way in, and the one the mode flag alone does not describe: a tag
# named on the command line that has no local ref. The mode is explicit-tag --
# check 2 grades `$FIXTURE_TAG`'s version against the manifests, a real question
# there -- but there is no tag to resolve, so the commit graded is HEAD, and
# check 4 has to hold it to HEAD's standard rather than to a resolved tag's. It
# is somebody checking a release they are about to cut, from whatever they have
# checked out, which is how 0.4.0 was cut in the first place.
#
# The control above already deleted `$FIXTURE_TAG` and left `$OTHER_TAG` behind,
# so naming it here is exactly that state and costs no extra fixture.
echo
echo "behaviour — a named tag with no local ref still grades HEAD"

git -C "$FIXTURE" -c advice.detachedHead=false checkout -q "$RELEASED"
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$FIXTURE_TAG" 2>&1)" && rc=0 || rc=$?
if ! printf '%s\n' "$out" | grep -qF "no local tag $FIXTURE_TAG; checking HEAD"; then
  note FAIL "$FIXTURE_TAG — did not take the no-such-tag fallback (exit $rc)"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "release $FIXTURE_TAG at $RELEASED_SHORT"; then
  note FAIL "$FIXTURE_TAG — fell back, but did not grade HEAD ($RELEASED_SHORT)"
  fail=1
elif [ "$rc" -ne 1 ] || ! printf '%s\n' "$out" | grep -qF "commit(s) behind refs/remotes/origin/main"; then
  note FAIL "$FIXTURE_TAG — graded HEAD but accepted an ancestor of main (exit $rc)"
  fail=1
else
  note ok "$FIXTURE_TAG — no local ref: grades HEAD, and to HEAD's standard"
fi
git -C "$FIXTURE" checkout -q main

# And the state that is not that at all: no tags here whatsoever. `git clone
# --depth 1` and `--no-tags` both produce it, as does actions/checkout's
# default, and from inside the repository it is indistinguishable from a pack
# that has never shipped. The already-released check reads `refs/tags/`, so in
# that state it cannot fire -- and a check that cannot fire has to say so, or
# the gate returns the same green it returned before any of this was fixed.
#
# Asserted on the notice rather than on `--strict`: the stub `gh` already fails
# `--strict` here, so an exit code could not tell the two skips apart.
git -C "$FIXTURE" tag -d "$OTHER_TAG" >/dev/null
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" --head 2>&1)" && rc=0 || rc=$?
if printf '%s\n' "$out" | grep -qF "cannot tell an unreleased version from an unfetched tag"; then
  note ok "--head — with no tags at all, the check reports that it could not run"
else
  note FAIL "--head — with no tags at all, the gate passed without saying what it skipped"
  fail=1
fi

# ------------------------------------------- the tree under the commit
# The other half of "which commit is this about", and it hid behind the first.
# Checks 4 and 5 have always read `$SHA`. Checks 1, 2 and 3 read the files on
# disk -- `cd "$ROOT"` at the top of the gate is what put them there -- and
# nothing required those to be one commit, or the tree to be clean.
#
# Measured before the fix, in this fixture's shape: the tree bumped to 9.9.9 and
# left uncommitted, a tag of that name pointed at a commit whose own manifests
# say 0.4.1 and whose RELEASE-NOTES.md has no 9.9.9 entry. The gate printed
# `release dovetail--v9.9.9 at <that commit>`, five `ok`s, exit 0 -- the
# manifests agreeing with themselves on disk, the tag matching the disk, the
# notes entry found on disk, while ancestry and CI were asked about the commit.
# A tag that says 9.9.9 and installs 0.4.1, waved through by the check whose own
# comment calls that worse than no tag.
#
# Not reachable from a tag push, where the checkout *is* the tag. Reachable from
# the documented local form -- `bash scripts/check-release.sh <tag>` from a
# working clone -- and in HEAD mode from uncommitted edits alone, which is the
# form `workflow_dispatch` would meet if a runner ever carried a dirty tree.
#
# The fixture is reused rather than rebuilt: it already has a commit, a later
# commit, and an `origin/main`. All this adds is a disagreement between what is
# committed and what is on disk.
echo
echo "behaviour — the tree under foot is not the commit under test"

DIRTY_VERSION="9.9.9"
DIRTY_TAG="${FIXTURE_TAG%%--v*}--v$DIRTY_VERSION"
COMMITTED_VERSION="${FIXTURE_TAG#*--v}"

bash "$FIXTURE/scripts/bump-version.sh" "$DIRTY_VERSION" >/dev/null
printf '\n## v%s (2026-08-06)\n\nOn disk, in no commit.\n' "$DIRTY_VERSION" >> "$FIXTURE/RELEASE-NOTES.md"
git -C "$FIXTURE" tag "$DIRTY_TAG" "$DESCENDANT"

# This section's canary, and it earns its place the same way the last one did: a
# fixture where the tree and the commit happen to agree would pass every
# assertion below while testing nothing. `bump-version.sh` writing nowhere, or
# an editor's line endings defeating the append, both land there quietly.
DISK_VERSION="$("$PYJSON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["version"])' \
  "$FIXTURE/.claude-plugin/plugin.json")"
COMMIT_VERSION="$(git -C "$FIXTURE" show "$DESCENDANT:.claude-plugin/plugin.json" \
  | "$PYJSON" -c 'import json,sys;print(json.load(sys.stdin)["version"])')"

if [ "$DISK_VERSION" = "$DIRTY_VERSION" ] && [ "$COMMIT_VERSION" = "$COMMITTED_VERSION" ]; then
  note ok "fixture: the tree says $DISK_VERSION, $DESCENDANT_SHORT says $COMMIT_VERSION"
else
  note FAIL "fixture: tree $DISK_VERSION, commit $COMMIT_VERSION — the assertions below prove nothing"
  fail=1
fi

# Explicit-tag mode. The tag resolves to a commit that carries neither the
# version the tag names nor a notes entry for it, and both of those live in
# files the working tree also has — with the answer the tree would give being
# the opposite one. Run without `--strict` so the exit code means the checks:
# the stub `gh` fails `--strict` on its own and would mask a 1 with a 1.
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$DIRTY_TAG" 2>&1)" && rc=0 || rc=$?

if ! printf '%s\n' "$out" | grep -qF "release $DIRTY_TAG at $DESCENDANT_SHORT"; then
  note FAIL "$DIRTY_TAG — did not grade the tagged commit ($DESCENDANT_SHORT)"
  fail=1
elif [ "$rc" -ne 1 ]; then
  note FAIL "$DIRTY_TAG — exit $rc, expected 1 (that commit carries $COMMIT_VERSION)"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "tag says $DIRTY_VERSION, the commit's manifests say $COMMIT_VERSION"; then
  note FAIL "$DIRTY_TAG — the version check read the tree rather than $DESCENDANT_SHORT"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "RELEASE-NOTES.md has no '## v$DIRTY_VERSION' entry"; then
  note FAIL "$DIRTY_TAG — the notes check read the tree rather than $DESCENDANT_SHORT"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "uncommitted changes present"; then
  note FAIL "$DIRTY_TAG — graded the commit without saying the tree differs from it"
  fail=1
else
  note ok "$DIRTY_TAG — version and notes graded on $DESCENDANT_SHORT, not on the tree"
fi

# HEAD mode's version of the same question, and it is not the same assertion:
# here the tree does not merely lose a comparison, it never gets to name the
# subject. The tag name HEAD mode builds decides what checks 2 and 3 grade, and
# building it from the manifests on disk would have this run announce a release
# of $DIRTY_VERSION from a commit that has never carried it.
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" --head 2>&1)" && rc=0 || rc=$?

if printf '%s\n' "$out" | grep -qF "$DIRTY_TAG"; then
  note FAIL "--head — named the tree's $DIRTY_VERSION as what HEAD would ship"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "checking HEAD as $FIXTURE_TAG"; then
  note FAIL "--head — did not name $COMMIT_VERSION, the version $DESCENDANT_SHORT carries"
  fail=1
elif [ "$rc" -ne 0 ]; then
  note FAIL "--head — exit $rc, expected 0 ($COMMIT_VERSION is untagged here and HEAD carries it)"
  fail=1
else
  note ok "--head — an uncommitted bump does not become what HEAD would ship"
fi

# The control, and the reason the two above are about divergence rather than
# about 9.9.9 being unwelcome. Commit exactly what was on disk, move the tag to
# that commit, and the same command on the same version passes.
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "release $DIRTY_TAG"
BUMPED="$(git -C "$FIXTURE" rev-parse HEAD)"
BUMPED_SHORT="$(git -C "$FIXTURE" rev-parse --short "$BUMPED")"
git -C "$FIXTURE" update-ref refs/remotes/origin/main "$BUMPED"
git -C "$FIXTURE" tag -d "$DIRTY_TAG" >/dev/null
git -C "$FIXTURE" tag "$DIRTY_TAG" "$BUMPED"

out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$DIRTY_TAG" 2>&1)" && rc=0 || rc=$?

if ! printf '%s\n' "$out" | grep -qF "release $DIRTY_TAG at $BUMPED_SHORT"; then
  note FAIL "$DIRTY_TAG — committed, but the tag no longer resolves to $BUMPED_SHORT"
  fail=1
elif [ "$rc" -ne 0 ]; then
  note FAIL "$DIRTY_TAG — committed and tagged, $BUMPED_SHORT still does not pass (exit $rc)"
  fail=1
elif printf '%s\n' "$out" | grep -qF "uncommitted changes present"; then
  note FAIL "$DIRTY_TAG — the tree is clean and the run said otherwise"
  fail=1
else
  note ok "$DIRTY_TAG — committed and tagged, the same version passes"
fi

echo
[ "$fail" -eq 0 ] && echo "Release-check tests passed." || echo "Release-check tests FAILED."
exit "$fail"
