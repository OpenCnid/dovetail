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
#   modes      HEAD mode grades HEAD, explicit-tag mode grades the tag, and a
#              tag with no ref here is refused rather than stood in for, in a
#              throwaway repository built so that those are different commits --
#              and each mode holds its subject to the standard its own question
#              needs: `main`'s tip for HEAD mode, anywhere on `main` for a tag.
#              Every one of the six checks grades that commit too, rather than
#              the files lying in the working tree. The third layer is newest and
#              answers a different question from the other two: not "is this
#              input safe?" but "is this the commit the answer is about?" See its
#              own blocks further down.
#   paths      the gate's *other* outside input, which the third layer created:
#              grading a commit's files means reading that commit's
#              `.version-bump.json` to learn which ones, so the commit under test
#              names the paths that become redirection targets. A listed `../x`
#              truncated a file outside the snapshot. This layer is back at the
#              first layer's question, one input over.
#
# Three more sections extend that third layer with a further question: given the
# right commit, what did the gate accept *from* it. A commit writes its own
# `.claude-plugin/marketplace.json` and its own `.version-bump.json`, so it gets
# to say which repository it installs from and which manifests check 1 is
# examined on; both were taken at face value. And the ref `main` is read from is
# not in the commit at all -- it is whatever the clone happens to carry, and a
# local one carries no news from the remote. Each is built as a fixture, graded,
# and controlled against a commit differing in that one thing. The `paths` layer
# is that question about the same file, asked of the bytes in the list rather
# than of which fields the list names.
#
# Each layer fires its own canary first. Assertions that a file did not appear --
# or did not change -- are free if nothing could have written one, and an
# unwritable temp directory would pass every one of them.
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

# Whether a well-formed tag *resolves* in this repository is not this
# repository's to decide, so neither leg below is the assertion: a working clone
# carries the pack's tags, and `checks.yml` checks out with `actions/checkout`
# and no `fetch-depth`, which fetches none. The assertion is that both legs are
# outcomes the convention reached — graded, or refused for having nothing to
# resolve — and that neither is a rejection of the shape.
#
# That split is what removing the tag-mode fallback forces here. This used to
# grep for `release dovetail--v0.4.1 at ...` and call it "reaches the checks",
# which held on CI only because the fallback printed that banner over HEAD: the
# assertion passed by way of the bug it now guards against. What resolving a tag
# does belongs to the fixture below, which owns its own `refs/tags/`.
for tag in dovetail--v0.4.1 dovetail--v1.0.0-rc.1; do
  out="$(PATH="$TMP/bin:$PATH" bash scripts/check-release.sh "$tag" 2>&1)" && rc=0 || rc=$?
  if printf '%s\n' "$out" | grep -qF "release $tag at "; then
    note ok "$tag — resolves here, and reaches the checks"
  elif [ "$rc" -eq 2 ] && printf '%s\n' "$out" | grep -qF "cannot resolve $tag"; then
    note ok "$tag — absent here, and refused as unresolvable rather than malformed"
  else
    note FAIL "$tag — neither graded nor refused as unresolvable (exit $rc)"
    fail=1
  fi
done

# The name the fallback used to swallow, and the one whose outcome here does not
# depend on the environment: no clone of this repository has a `v9.9.9` ref,
# whatever it fetched. Three ways to get this wrong, so three legs. It must not
# be refused as malformed — it is well-formed, and exit 2 alone no longer tells
# those apart, which is the cost of the change this asserts. And above all it
# must not print a banner: `release <tag> at <commit>` over a tag that resolves
# to nothing is the `--no-tags` reproduction, verbatim.
out="$(PATH="$TMP/bin:$PATH" bash scripts/check-release.sh dovetail--v9.9.9 2>&1)" && rc=0 || rc=$?
if [ "$rc" -ne 2 ]; then
  note FAIL "dovetail--v9.9.9 — exit $rc, expected 2 (nothing to resolve)"
  fail=1
elif printf '%s\n' "$out" | grep -q '^not a dovetail release tag'; then
  note FAIL "dovetail--v9.9.9 — refused as malformed; it is well-formed and absent"
  fail=1
elif printf '%s\n' "$out" | grep -q '^release dovetail--v9.9.9 at '; then
  note FAIL "dovetail--v9.9.9 — graded a commit under the name of a tag it could not resolve"
  fail=1
elif printf '%s\n' "$out" | grep -qF 'cannot resolve dovetail--v9.9.9'; then
  note ok "dovetail--v9.9.9 — well-formed, unresolvable, refused without grading HEAD"
else
  note FAIL "dovetail--v9.9.9 — exit 2 without saying the tag could not be resolved"
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
# is what counts as an acceptable HEAD, and check 5 used to answer it with
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
# still points at HEAD here, so the already-released check passes and check 5 is
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
# that passes check 5, or they would report the tag state they are testing.
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

# The third way in, which used to be a way in at all: a tag named on the command
# line that has no local ref. It fell back to grading HEAD, so `git clone
# --no-tags` was the whole reproduction -- the tag is published, the clone never
# fetched it, and the gate printed `release <tag> at <HEAD>` and passed. A
# developer checking a release that had already shipped was told it was fine,
# about a commit that was not the one they named.
#
# That is the state built here. The control above deleted `$FIXTURE_TAG` while
# `$RELEASED` still exists and `$OTHER_TAG` still points at it, so naming it is
# exactly a clone that did not fetch the tag, and it costs no extra fixture.
#
# The middle leg is the one that matters: not that it exited 2, but that neither
# commit's SHA appears in the output at all. A refusal that still names a commit
# is the fallback with a worse exit code.
#
# `--strict` shows the 2 is the input's rather than strictness's: the stub `gh`
# fails `--strict`, so a graded run would come back 1, and this returns before a
# check runs at all.
echo
echo "behaviour — a named tag with no local ref is refused, not stood in for"

git -C "$FIXTURE" -c advice.detachedHead=false checkout -q "$RELEASED"
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" --strict "$FIXTURE_TAG" 2>&1)" && rc=0 || rc=$?
if [ "$rc" -ne 2 ]; then
  note FAIL "$FIXTURE_TAG — no local ref, exit $rc, expected 2 (nothing to resolve)"
  fail=1
elif printf '%s\n' "$out" | grep -qE "$RELEASED_SHORT|$DESCENDANT_SHORT"; then
  note FAIL "$FIXTURE_TAG — no local ref, and the refusal still named a commit"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "cannot resolve $FIXTURE_TAG"; then
  note FAIL "$FIXTURE_TAG — exit 2 without saying the tag could not be resolved"
  fail=1
else
  note ok "$FIXTURE_TAG — published elsewhere, unfetched here, refused rather than stood in for"
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

# ------------------------------ the same divergence, once it is committed
# The section above puts the tree and the commit at odds by leaving an edit
# uncommitted, which is one way to get there and the loud one — the gate prints
# a notice about it. The quiet way is ordinary history: a tag is published, work
# continues, `main`'s manifests move to the next version, and from then on every
# clean checkout of `main` disagrees with every tag behind it. Nothing is dirty
# and nothing is wrong.
#
# Read from the tree, check 2 turns that into a false negative about a release
# that is fine. Measured on this repository before e9928fc, with the manifests
# bumped to 0.4.2: `bash scripts/check-release.sh dovetail--v0.4.1` reported
# `tag says 0.4.1, manifests say 0.4.2` and exited 1 — about `313b9e4`, whose
# own manifests say 0.4.1 and always did. Same family as the two sections above,
# a verdict about one commit printed under another commit's name, inverted: the
# gate refusing what it should pass rather than passing what it should refuse.
#
# It is the reachable half of that bug, too. The uncommitted case needs somebody
# mid-edit; this one needs only a clone that fetched, and
# `bash scripts/check-release.sh <tag>` from a working clone is the documented
# way to verify a published release (AGENTS.md, "Releasing").
#
# No new fixture state: the control just above committed the 9.9.9 bump and left
# `main`, `origin/main` and the checkout sitting on it, which is that moved-on
# clone exactly. All this adds is the older tag back, deleted by the untagged
# control further up.
#
# Check 2 is the whole of what discriminates here, and that is not a gap in the
# case. Check 1 sees a self-consistent set of manifests whichever commit it
# reads them from, and RELEASE-NOTES.md is append-only — the tree's copy is a
# superset of the tag's, so reading the tree can only ever be too generous for
# check 3, never too strict.
echo
echo "behaviour — a published tag verified from a checkout that moved on"

# This block's canary. If the control's commit had picked nothing up, the
# checkout would still carry $COMMITTED_VERSION and the run below would pass by
# agreeing with the tag rather than by reading the tag's commit.
HEAD_VERSION="$(git -C "$FIXTURE" show "HEAD:.claude-plugin/plugin.json" \
  | "$PYJSON" -c 'import json,sys;print(json.load(sys.stdin)["version"])')"

if [ "$HEAD_VERSION" = "$DIRTY_VERSION" ] && [ "$HEAD_VERSION" != "$COMMITTED_VERSION" ]; then
  note ok "fixture: the checkout carries $HEAD_VERSION, $FIXTURE_TAG's commit carries $COMMITTED_VERSION"
else
  note FAIL "fixture: the checkout carries $HEAD_VERSION — nothing below tells the two apart"
  fail=1
fi

git -C "$FIXTURE" tag "$FIXTURE_TAG" "$RELEASED"

out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$FIXTURE_TAG" 2>&1)" && rc=0 || rc=$?

if ! printf '%s\n' "$out" | grep -qF "release $FIXTURE_TAG at $RELEASED_SHORT"; then
  note FAIL "$FIXTURE_TAG — did not grade the tagged commit ($RELEASED_SHORT)"
  fail=1
elif printf '%s\n' "$out" | grep -qF "tag says $COMMITTED_VERSION"; then
  # The symptom itself, in whichever wording check 2 fails in. Reading the
  # checkout again lands here rather than only on the exit code below.
  note FAIL "$FIXTURE_TAG — the version check read the checkout's $HEAD_VERSION"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "the commit's manifests carry $COMMITTED_VERSION"; then
  note FAIL "$FIXTURE_TAG — did not read $COMMITTED_VERSION out of $RELEASED_SHORT"
  fail=1
elif printf '%s\n' "$out" | grep -qF "uncommitted changes present"; then
  # Separates this from the section above: the divergence here is history, and
  # a notice claiming an unclean tree would send the reader to `git status` to
  # find nothing.
  note FAIL "$FIXTURE_TAG — the checkout is clean and the run said otherwise"
  fail=1
elif [ "$rc" -ne 0 ]; then
  note FAIL "$FIXTURE_TAG — exit $rc, expected 0 ($RELEASED_SHORT is a valid release)"
  fail=1
else
  note ok "$FIXTURE_TAG — $RELEASED_SHORT still passes from a checkout carrying $HEAD_VERSION"
fi

# ------------------- the tag names one pack, the commit carries another
# The two sections above put the tree and the commit at odds about the
# *version*, which is the half check 2 always compared. The name was the other
# half, and nothing compared it at all: `$PLUGIN` came off the checkout, so a
# tag was matched against the pack the reader happens to have open rather than
# against the pack the tagged commit ships.
#
# Measured before the fix, in this fixture's shape: `dovetail--v8.8.8` pointing
# at a commit whose `plugin.json` says `name: otherpack` printed
# `release dovetail--v8.8.8 at <that commit>` and four `ok`s, exit 0. Checks 1,
# 3 and 4 have no opinion about which pack they are reading — a version agrees
# with itself, a notes entry is keyed on the version, ancestry is a commit
# question — so check 2 was the only one that could have caught it, and it was
# looking at the other field. That is this check's own "a tag that says 0.4.1
# and installs 0.4.0", one field over: a tag that says `dovetail` and installs
# somebody else's pack.
#
# Reachable from the documented local form, `bash scripts/check-release.sh
# <tag>` from a working clone, whenever a tag is cut across a rename: the
# checkout carries the new name and the tagged commit still carries the old one.
# Not reachable from a tag push, where the checkout *is* the tag — the same
# reason the version half lasted as long as it did.
echo
echo "behaviour — the tag names one pack, the commit carries another"

PACK="${FIXTURE_TAG%%--v*}"
FOREIGN_PACK="otherpack"
FOREIGN_VERSION="8.8.8"
CONTROL_VERSION="7.7.7"
FOREIGN_TAG="${PACK}--v$FOREIGN_VERSION"
CONTROL_TAG="${PACK}--v$CONTROL_VERSION"

# `newline="\n"` for the same reason bump-version.sh uses it: the fixture sets
# `core.autocrlf false`, and a manifest rewritten with CRLF would show up as a
# whole-file change and as a tree that never matches its commit.
set_pack_name() {
  "$PYJSON" - "$FIXTURE/.claude-plugin/plugin.json" "$1" <<'PY'
import json, sys
path, name = sys.argv[1], sys.argv[2]
data = json.load(open(path))
data["name"] = name
with open(path, "w", newline="\n") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
}

# The foreign-named commit, and a tag over it carrying *this* pack's name. Only
# `plugin.json`'s `name` moves: `.version-bump.json` lists version fields alone,
# so check 1 still sees a self-consistent set and check 2 is left as the sole
# discriminator — which is the point, since check 2 is where the name was not
# being read.
bash "$FIXTURE/scripts/bump-version.sh" "$FOREIGN_VERSION" >/dev/null
printf '\n## v%s (2026-08-06)\n\nA pack by another name.\n' "$FOREIGN_VERSION" >> "$FIXTURE/RELEASE-NOTES.md"
set_pack_name "$FOREIGN_PACK"
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "rename to $FOREIGN_PACK"
FOREIGN="$(git -C "$FIXTURE" rev-parse HEAD)"
FOREIGN_SHORT="$(git -C "$FIXTURE" rev-parse --short "$FOREIGN")"
git -C "$FIXTURE" tag "$FOREIGN_TAG" "$FOREIGN"

# And the checkout the reader is sitting in: the pack's own name back, a version
# of its own, tagged and on `main`. This is the control as well as the setting —
# a clean, ordinary release that has to keep passing.
bash "$FIXTURE/scripts/bump-version.sh" "$CONTROL_VERSION" >/dev/null
printf '\n## v%s (2026-08-06)\n\nNamed as itself.\n' "$CONTROL_VERSION" >> "$FIXTURE/RELEASE-NOTES.md"
set_pack_name "$PACK"
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "rename back to $PACK"
CONTROL="$(git -C "$FIXTURE" rev-parse HEAD)"
CONTROL_SHORT="$(git -C "$FIXTURE" rev-parse --short "$CONTROL")"
git -C "$FIXTURE" tag "$CONTROL_TAG" "$CONTROL"
git -C "$FIXTURE" update-ref refs/remotes/origin/main "$CONTROL"

# This section's canary. A fixture whose checkout and tagged commit agreed on
# the name would pass every assertion below while testing nothing — and the two
# `set_pack_name` calls are exactly the kind of write that fails quietly.
DISK_NAME="$("$PYJSON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["name"])' \
  "$FIXTURE/.claude-plugin/plugin.json")"
FOREIGN_NAME="$(git -C "$FIXTURE" show "$FOREIGN:.claude-plugin/plugin.json" \
  | "$PYJSON" -c 'import json,sys;print(json.load(sys.stdin)["name"])')"

if [ "$DISK_NAME" = "$PACK" ] && [ "$FOREIGN_NAME" = "$FOREIGN_PACK" ]; then
  note ok "fixture: the checkout is $DISK_NAME, $FOREIGN_SHORT is $FOREIGN_NAME"
else
  note FAIL "fixture: checkout $DISK_NAME, commit $FOREIGN_NAME — the assertions below prove nothing"
  fail=1
fi

# Explicit-tag mode. The tag parses against the checkout's name — it has to,
# there is no resolved commit at that point — and then the commit it resolves to
# ships a different pack. Run without `--strict` so the exit code means the
# checks rather than the stub `gh`.
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$FOREIGN_TAG" 2>&1)" && rc=0 || rc=$?

if ! printf '%s\n' "$out" | grep -qF "release $FOREIGN_TAG at $FOREIGN_SHORT"; then
  note FAIL "$FOREIGN_TAG — did not grade the tagged commit ($FOREIGN_SHORT)"
  fail=1
elif [ "$rc" -ne 1 ]; then
  note FAIL "$FOREIGN_TAG — exit $rc, expected 1 ($FOREIGN_SHORT ships $FOREIGN_PACK)"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "the commit's manifests say $FOREIGN_PACK"; then
  note FAIL "$FOREIGN_TAG — the name check read the checkout rather than $FOREIGN_SHORT"
  fail=1
else
  note ok "$FOREIGN_TAG — refused: the tag names $PACK, $FOREIGN_SHORT carries $FOREIGN_PACK"
fi

# The control, and the reason the assertion above is about disagreement rather
# than about `otherpack` being unwelcome. Same checkout, same command, a tag
# whose commit carries the name it claims.
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$CONTROL_TAG" 2>&1)" && rc=0 || rc=$?

if ! printf '%s\n' "$out" | grep -qF "release $CONTROL_TAG at $CONTROL_SHORT"; then
  note FAIL "$CONTROL_TAG — did not grade the tagged commit ($CONTROL_SHORT)"
  fail=1
elif [ "$rc" -ne 0 ]; then
  note FAIL "$CONTROL_TAG — exit $rc, expected 0 ($CONTROL_SHORT carries $PACK and $CONTROL_VERSION)"
  fail=1
else
  note ok "$CONTROL_TAG — the name agreeing with the commit still passes"
fi

# HEAD mode's version of the same read, and the sharper half: here the name does
# not lose a comparison, it decides which tag namespace the already-released
# check looks in. Built from the checkout, an uncommitted rename sent that check
# hunting for tags of a pack that has never released anything, and it reported
# that it could not tell — a `SKIP` where there had been a verdict, and without
# `--strict` that is exit 0. The check the mode exists for, switched off by an
# unsaved edit to a file the gate says it does not consult.
set_pack_name "renamed"
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" --head 2>&1)" && rc=0 || rc=$?

if printf '%s\n' "$out" | grep -qF "renamed"; then
  note FAIL "--head — an uncommitted rename became the pack HEAD would ship"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "checking HEAD as $CONTROL_TAG"; then
  note FAIL "--head — did not name $PACK, the pack $CONTROL_SHORT carries"
  fail=1
elif printf '%s\n' "$out" | grep -qF "cannot tell an unreleased version from an unfetched tag"; then
  note FAIL "--head — the already-released check was pointed at a pack with no tags"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "already points here"; then
  note FAIL "--head — did not resolve $CONTROL_TAG, which points at HEAD"
  fail=1
else
  note ok "--head — an uncommitted rename does not become what HEAD would ship"
fi

# ------------------------------- the commit names the files, and that is input
# The tag is the input everybody looks at. This is the other one, and it arrived
# with the fix above: once the checks grade a commit's files rather than the
# checkout's, something has to say which files, and that something is the
# commit's own `.version-bump.json`. So the commit under test chooses those
# paths, and `snapshot()` turned each into a redirection target.
#
# Bash opens a redirection target before the command on the line runs, so a
# listed path of `../x` truncated `x` outside the snapshot and *then* `git show`
# failed on a path no commit carries. The gate printed FAIL -- correctly, and
# about manifests that disagree -- over a file it was never asked to touch that
# was already empty, `mkdir -p` having made the directories on the way. Measured
# 2026-08-06 on git-bash 5.2.37(msys), Windows 10: a 36-byte canary outside the
# snapshot came back 0 bytes while the run reported the expected failure. Nothing
# in the output mentioned the write, which is what made it a quiet one.
#
# `$SNAPSHOT` is `mktemp -d`, so where `..` lands is `$TMPDIR`'s business. This
# section names `$TMPDIR` rather than guessing at one: the gate's snapshot
# directory is then one level under a directory this script owns, and
# `../canary.txt` reaches a file it can compare byte for byte.
#
# Its own fixture, rather than the one above. This needs a commit whose
# `.version-bump.json` *is* the hostile input, and grafting that onto the shared
# fixture would leave it there for everything added after.
echo
echo "behaviour — a path in .version-bump.json cannot write outside the snapshot"

ESCAPE_TMP="$TMP/escape-tmpdir"
ESCAPE_CANARY="$ESCAPE_TMP/canary.txt"
ESCAPE_PRISTINE="$TMP/canary.pristine"
ESCAPE_PATH="../canary.txt"

mkdir -p "$ESCAPE_TMP"
printf 'a canary that has to survive the gate byte for byte\n' > "$ESCAPE_CANARY"
cp "$ESCAPE_CANARY" "$ESCAPE_PRISTINE"

# This section's canary, fired the way the gate fired it: `mkdir -p` and a
# redirection built from the listed path, in a snapshot directory made where the
# gate will make its own. Every assertion below says a file did not change, and
# those are free if nothing could have changed it -- an `mktemp` that ignored
# `$TMPDIR`, or a `..` landing somewhere this script does not own, both put the
# section there quietly. The `git show` is expected to fail; that is the point.
ESCAPE_PROBE="$(TMPDIR="$ESCAPE_TMP" mktemp -d)"
mkdir -p "$ESCAPE_PROBE/$(dirname "$ESCAPE_PATH")"
git show "0000000000000000000000000000000000000000:$ESCAPE_PATH" \
  > "$ESCAPE_PROBE/$ESCAPE_PATH" 2>/dev/null || true
rm -rf "$ESCAPE_PROBE"

if [ ! -s "$ESCAPE_CANARY" ]; then
  note ok "canary fires when a listed path is redirected to"
  cp "$ESCAPE_PRISTINE" "$ESCAPE_CANARY"
else
  note FAIL "canary cannot fire — every assertion below would pass vacuously"
  fail=1
fi

ESCAPE_FIXTURE="$TMP/escape-fixture"
mkdir -p "$ESCAPE_FIXTURE/.claude-plugin" "$ESCAPE_FIXTURE/scripts"
# `marketplace.json` is here for check 3, which reads `plugins[0].source` out of
# the commit whether or not `.version-bump.json` names the file. Without it this
# fixture fails that check on every leg, and the control below -- the one that
# has to exit 0 -- would be reporting check 3 while claiming to report check 1.
cp .claude-plugin/plugin.json .claude-plugin/marketplace.json "$ESCAPE_FIXTURE/.claude-plugin/"
cp RELEASE-NOTES.md "$ESCAPE_FIXTURE/"
cp scripts/check-release.sh scripts/bump-version.sh "$ESCAPE_FIXTURE/scripts/"

git -C "$ESCAPE_FIXTURE" -c init.defaultBranch=main init -q
git -C "$ESCAPE_FIXTURE" symbolic-ref HEAD refs/heads/main
git -C "$ESCAPE_FIXTURE" config core.autocrlf false

# Commits a `.version-bump.json` naming `$1` alongside the fields check 1's
# floor requires. HEAD stays on `main`'s tip and the notes and manifests are this
# pack's own -- including the marketplace entry, which check 3 reads regardless
# of this list -- so check 1 is the only check that can fail below, which is what
# makes the exit code mean one specific thing.
#
# The floor is why this list is not `$1` alone, and the reason is the section
# further down: a commit does not get to narrow what check 1 grades, and a
# fixture listing one field would be refused for narrowing rather than for the
# path it is here to test. Adding the hostile path to a whole list keeps the
# traversal the only thing wrong with it -- and the control, whose path is
# already on the floor, adds nothing and has to pass.
#
# `newline="\n"` for the reason bump-version.sh uses it: the fixture sets
# `core.autocrlf false`, and a CRLF manifest is a file that never matches its
# commit.
escape_commit() {
  "$PYJSON" - "$ESCAPE_FIXTURE/.version-bump.json" "$1" <<'PY'
import json, sys
path, listed = sys.argv[1], sys.argv[2]
files = [
    {"path": ".claude-plugin/plugin.json", "field": "version"},
    {"path": ".claude-plugin/marketplace.json", "field": "plugins.0.version"},
    {"path": ".claude-plugin/marketplace.json", "field": "metadata.version"},
]
if listed not in {entry["path"] for entry in files}:
    files.append({"path": listed, "field": "version"})
with open(path, "w", newline="\n") as f:
    json.dump({"files": files}, f, indent=2)
    f.write("\n")
PY
  git -C "$ESCAPE_FIXTURE" add -A
  git -C "$ESCAPE_FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "list $1"
}

# Run without `--strict`: the stub `gh` fails `--strict` on its own and would
# mask check 1's 1 with a 1 of its own.
escape_run() {
  PATH="$TMP/bin:$PATH" TMPDIR="$ESCAPE_TMP" \
    bash "$ESCAPE_FIXTURE/scripts/check-release.sh" --head 2>&1
}

# The traversal itself, and the only leg here backed by a canary. The order of
# the assertions is the order they matter in: a refusal that still truncated the
# file is the bug with a better error message.
escape_commit "$ESCAPE_PATH"
out="$(escape_run)" && rc=0 || rc=$?

if ! cmp -s "$ESCAPE_PRISTINE" "$ESCAPE_CANARY"; then
  note FAIL "$ESCAPE_PATH — the gate wrote outside its snapshot"
  cp "$ESCAPE_PRISTINE" "$ESCAPE_CANARY"
  fail=1
elif [ "$rc" -ne 1 ]; then
  note FAIL "$ESCAPE_PATH — exit $rc, expected 1 (check 1 refuses the path)"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "names a path outside the tree"; then
  # The wording is the repair. Reported as manifests that disagree -- which is
  # what it was before the guard, and what it still would be if `snapshot`
  # merely failed -- it sends the reader to `bump-version.sh --check`, which
  # reads the list on disk, where the path is fine, and passes.
  note FAIL "$ESCAPE_PATH — refused, but not as a path outside the tree"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "$ESCAPE_PATH"; then
  note FAIL "$ESCAPE_PATH — refused without naming the path"
  fail=1
else
  note ok "$ESCAPE_PATH — refused, and the canary is byte-identical"
fi

# The shapes that are not a bare `..`, sharing the canary above rather than
# each bringing one: they are aimed at it, so the `cmp` leg is live for every
# one that can reach it on the platform in hand.
#
# Two of these traverse and two cannot, and that spread is the argument for
# refusing all four. `a/../../x` escapes anywhere. `..\x` escapes on Windows and
# nowhere else -- bash hands the target to the OS, which reads the backslash as
# a separator, so the same bytes are one filename on Linux and a directory walk
# on `windows-latest`, where half of `checks` runs (measured 2026-08-06,
# git-bash 5.2.37(msys), Windows 10: a 20-byte file two directories up came back
# 0 bytes and nothing was created under the snapshot). `/etc/...` and `./x` land
# back inside the snapshot -- but only because `"$SNAPSHOT/$1"` is string
# concatenation, so a leading slash doubles rather than roots. That is an
# accident of the join, not a check, and a list carrying either is not
# describing this tree whatever it happens to land on.
for listed in 'a/../../canary.txt' '..\canary.txt' '/etc/dovetail-canary' './plugin.json' 'C:/canary.txt'; do
  escape_commit "$listed"
  out="$(escape_run)" && rc=0 || rc=$?
  if ! cmp -s "$ESCAPE_PRISTINE" "$ESCAPE_CANARY"; then
    note FAIL "$listed — the gate wrote outside its snapshot"
    cp "$ESCAPE_PRISTINE" "$ESCAPE_CANARY"
    fail=1
  elif [ "$rc" -eq 1 ] && printf '%s\n' "$out" | grep -qF "names a path outside the tree"; then
    note ok "$listed"
  else
    note FAIL "$listed — not refused as a path outside the tree (exit $rc)"
    fail=1
  fi
done

# The control, and the reason the legs above are about escaping rather than
# about `.version-bump.json` being unwelcome. Same fixture, same command, a path
# in the tree: it snapshots, check 1 grades it, and the run passes.
escape_commit ".claude-plugin/plugin.json"
out="$(escape_run)" && rc=0 || rc=$?

if ! printf '%s\n' "$out" | grep -qF "manifests agree with each other"; then
  note FAIL ".claude-plugin/plugin.json — an in-tree path no longer snapshots (exit $rc)"
  fail=1
elif [ "$rc" -ne 0 ]; then
  note FAIL ".claude-plugin/plugin.json — listed and in the tree, and the run still failed (exit $rc)"
  fail=1
else
  note ok ".claude-plugin/plugin.json — an ordinary path still snapshots and grades"
fi

# ------------------ the tag names this pack, and installs another repository
# The three sections above put the tree and the commit at odds about what the
# pack *is* — its version, then its name. This one is about what it hands an
# installer, which nothing graded at all.
#
# `plugins[0].source` in `.claude-plugin/marketplace.json` is the field a
# marketplace resolves to fetch the pack. It reads `./` because this marketplace
# ships inside the repository it lists. It is not on `.version-bump.json`'s
# list, so check 1 never sees it; check 2 compares a name and a version and has
# no opinion about it; and a notes entry, ancestry and a CI run are all answers
# about something else.
#
# Measured before the fix, in this fixture's shape: a commit repointing that one
# field at another repository, with `name` and `version` left untouched, printed
# `release <tag> at <that commit>` and five `ok`s, exit 0. That is check 2's own
# "a tag that says `dovetail` and installs another pack entirely" — one field
# further over than the name was, and this time the tag is not even lying. The
# name and the version are the pack's own; the repository behind them is not.
#
# Reachable from every route, unlike the two sections above. Those needed the
# tree and the commit to diverge, so a tag push could not reach them — there the
# checkout *is* the tag. Here nothing has to diverge: the field is simply in the
# commit, and was never read.
echo
echo "behaviour — the marketplace entry installs another repository"

# The rename the section above left on disk was never committed, and everything
# below builds commits out of this tree. Put it back rather than carry it.
git -C "$FIXTURE" checkout -q -- .claude-plugin/plugin.json

SELF_SOURCE="./"
FOREIGN_SOURCE="https://github.com/somebody-else/not-this-pack"
REPOINTED_VERSION="6.6.6"
REPOINTED_TAG="${PACK}--v$REPOINTED_VERSION"

# `newline="\n"` for the same reason set_pack_name uses it: the fixture sets
# `core.autocrlf false`, and a manifest rewritten with CRLF would show up as a
# whole-file change and as a tree that never matches its commit.
set_marketplace_source() {
  "$PYJSON" - "$FIXTURE/.claude-plugin/marketplace.json" "$1" <<'PY'
import json, sys
path, source = sys.argv[1], sys.argv[2]
data = json.load(open(path))
data["plugins"][0]["source"] = source
with open(path, "w", newline="\n") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
}

# A whole, ordinary release — bumped with the pack's own tool, notes entry and
# all — with exactly one field moved. Everything a release is graded on agrees
# with itself; the pack it installs is somebody else's.
bash "$FIXTURE/scripts/bump-version.sh" "$REPOINTED_VERSION" >/dev/null
printf '\n## v%s (2026-08-06)\n\nThis pack, from another repository.\n' "$REPOINTED_VERSION" >> "$FIXTURE/RELEASE-NOTES.md"
set_marketplace_source "$FOREIGN_SOURCE"
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "repoint the marketplace entry"
REPOINTED="$(git -C "$FIXTURE" rev-parse HEAD)"
REPOINTED_SHORT="$(git -C "$FIXTURE" rev-parse --short "$REPOINTED")"
git -C "$FIXTURE" tag "$REPOINTED_TAG" "$REPOINTED"
git -C "$FIXTURE" update-ref refs/remotes/origin/main "$REPOINTED"

# This section's canary, and it carries the case as well as guarding it: the
# commit has to be repointed *and* still be this pack under this version, or the
# assertions below could be caught by check 2 and prove nothing about the field
# they name. A `set_marketplace_source` that wrote nowhere lands here quietly.
REPOINTED_SOURCE="$(git -C "$FIXTURE" show "$REPOINTED:.claude-plugin/marketplace.json" \
  | "$PYJSON" -c 'import json,sys;print(json.load(sys.stdin)["plugins"][0]["source"])')"
REPOINTED_NAME="$(git -C "$FIXTURE" show "$REPOINTED:.claude-plugin/plugin.json" \
  | "$PYJSON" -c 'import json,sys;print(json.load(sys.stdin)["name"])')"

if [ "$REPOINTED_SOURCE" = "$FOREIGN_SOURCE" ] && [ "$REPOINTED_NAME" = "$PACK" ]; then
  note ok "fixture: $REPOINTED_SHORT is $REPOINTED_NAME $REPOINTED_VERSION, installed from $REPOINTED_SOURCE"
else
  note FAIL "fixture: $REPOINTED_SHORT is $REPOINTED_NAME installed from $REPOINTED_SOURCE — the assertions below prove nothing"
  fail=1
fi

# Explicit-tag mode. The second leg is the one that makes this a test of the
# source field rather than of the fixture: check 2 has to *pass* here, or the
# exit code below is check 2's verdict wearing this section's name.
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$REPOINTED_TAG" 2>&1)" && rc=0 || rc=$?

if ! printf '%s\n' "$out" | grep -qF "release $REPOINTED_TAG at $REPOINTED_SHORT"; then
  note FAIL "$REPOINTED_TAG — did not grade the tagged commit ($REPOINTED_SHORT)"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "the commit's manifests carry $REPOINTED_VERSION"; then
  note FAIL "$REPOINTED_TAG — check 2 failed too; the exit code below would not be the source check's"
  fail=1
elif [ "$rc" -ne 1 ]; then
  note FAIL "$REPOINTED_TAG — exit $rc, expected 1 ($REPOINTED_SHORT installs from $FOREIGN_SOURCE)"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "$FOREIGN_SOURCE"; then
  note FAIL "$REPOINTED_TAG — refused without naming the repository it would install from"
  fail=1
else
  note ok "$REPOINTED_TAG — refused: the name and version are $PACK's, the source is not"
fi

# HEAD mode asks the same question, and it is the one asked before anybody tags
# anything. The repointed commit is HEAD, `main`'s tip and the tag's own commit
# here, so every other check passes and this exit code has one cause.
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" --head 2>&1)" && rc=0 || rc=$?

if ! printf '%s\n' "$out" | grep -qF "release $REPOINTED_TAG at $REPOINTED_SHORT"; then
  note FAIL "--head — did not grade HEAD ($REPOINTED_SHORT)"
  fail=1
elif [ "$rc" -ne 1 ]; then
  note FAIL "--head — exit $rc, expected 1 (HEAD installs from $FOREIGN_SOURCE)"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "$FOREIGN_SOURCE"; then
  note FAIL "--head — refused without naming the repository it would install from"
  fail=1
else
  note ok "--head — the pre-flight refuses it too, before there is a tag to blame"
fi

# The control, and the reason the two above are about the source rather than
# about 6.6.6. Point the entry back at this repository, commit, move the tag to
# that commit: same version, same tag name, and it passes.
set_marketplace_source "$SELF_SOURCE"
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "point the marketplace entry back at this repository"
RESTORED="$(git -C "$FIXTURE" rev-parse HEAD)"
RESTORED_SHORT="$(git -C "$FIXTURE" rev-parse --short "$RESTORED")"
git -C "$FIXTURE" update-ref refs/remotes/origin/main "$RESTORED"
git -C "$FIXTURE" tag -d "$REPOINTED_TAG" >/dev/null
git -C "$FIXTURE" tag "$REPOINTED_TAG" "$RESTORED"

out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$REPOINTED_TAG" 2>&1)" && rc=0 || rc=$?

if ! printf '%s\n' "$out" | grep -qF "release $REPOINTED_TAG at $RESTORED_SHORT"; then
  note FAIL "$REPOINTED_TAG — repointed back, but the tag no longer resolves to $RESTORED_SHORT"
  fail=1
elif [ "$rc" -ne 0 ]; then
  note FAIL "$REPOINTED_TAG — installs from $SELF_SOURCE and still does not pass (exit $rc)"
  fail=1
else
  note ok "$REPOINTED_TAG — the entry pointing at this repository still passes"
fi

# ------------------------- the commit narrows the list check 1 reads from it
# Check 1 delegates to `bump-version.sh --check`, which compares every field
# `.version-bump.json` names. `snapshot_manifests` reads that file out of `$SHA`
# -- correctly, since it describes that commit's manifests -- and the
# consequence is that the commit under test chooses the syllabus it is examined
# on. Cut the list to `.claude-plugin/plugin.json` alone and `--check` compares
# one field with itself, agrees, and check 1 prints `manifests agree with each
# other` over manifests that do not.
#
# This file has been using that narrowing as a convenience rather than treating
# it as a hazard: the pack-name section above leans on `.version-bump.json`
# listing version fields alone to keep check 1 quiet while check 2 does the
# discriminating. Same mechanism, one step further, and it stops being a
# technique.
#
# What it costs is the whole of `bump-version.sh`'s reason to exist. The
# marketplace entry carries `strict: true` and is what installers read; a
# `plugin.json` saying one version beside a marketplace entry saying another is
# the disagreement the tool was written to catch, and `claude plugin tag`
# refuses to tag on it. Measured before the fix, in this fixture's shape: exit 0
# and five `ok`s, one of them the agreement of a set of one.
#
# Not a hostile-commit story especially. Deleting a line from a JSON list while
# debugging a bump, and committing it, gets there.
echo
echo "behaviour — the commit narrows the list check 1 reads from it"

NARROWED_VERSION="4.4.4"
NARROWED_TAG="${PACK}--v$NARROWED_VERSION"

# The list, cut to the one manifest that is about to move.
cat > "$FIXTURE/.version-bump.json" <<'JSON'
{
  "files": [
    { "path": ".claude-plugin/plugin.json", "field": "version" }
  ]
}
JSON

# Bumped with the pack's own tool over the list it was just handed, which is
# what makes this the reachable shape rather than a hand-built disagreement:
# `bump-version.sh` moves what the list names, so plugin.json goes to 4.4.4 and
# the marketplace entry keeps the version before it.
bash "$FIXTURE/scripts/bump-version.sh" "$NARROWED_VERSION" >/dev/null
printf '\n## v%s (2026-08-06)\n\nBumped over a list of one.\n' "$NARROWED_VERSION" >> "$FIXTURE/RELEASE-NOTES.md"
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "bump over a narrowed list"
NARROWED="$(git -C "$FIXTURE" rev-parse HEAD)"
NARROWED_SHORT="$(git -C "$FIXTURE" rev-parse --short "$NARROWED")"
git -C "$FIXTURE" tag "$NARROWED_TAG" "$NARROWED"
git -C "$FIXTURE" update-ref refs/remotes/origin/main "$NARROWED"

# This section's canary, and it needs both halves. A commit whose manifests
# happened to agree would pass every assertion below by being a valid release,
# and a list that was never narrowed would leave check 1 catching the
# disagreement the ordinary way — either one turns the chain below into a test
# of something else that also exits 1.
NARROWED_LISTED="$(git -C "$FIXTURE" show "$NARROWED:.version-bump.json" \
  | "$PYJSON" -c 'import json,sys;print(len(json.load(sys.stdin)["files"]))')"
NARROWED_PLUGIN="$(git -C "$FIXTURE" show "$NARROWED:.claude-plugin/plugin.json" \
  | "$PYJSON" -c 'import json,sys;print(json.load(sys.stdin)["version"])')"
NARROWED_MARKET="$(git -C "$FIXTURE" show "$NARROWED:.claude-plugin/marketplace.json" \
  | "$PYJSON" -c 'import json,sys;print(json.load(sys.stdin)["plugins"][0]["version"])')"

if [ "$NARROWED_LISTED" = "1" ] && [ "$NARROWED_PLUGIN" != "$NARROWED_MARKET" ]; then
  note ok "fixture: $NARROWED_SHORT lists $NARROWED_LISTED version field and says $NARROWED_PLUGIN against the marketplace entry's $NARROWED_MARKET"
else
  note FAIL "fixture: $NARROWED_SHORT lists $NARROWED_LISTED fields, plugin $NARROWED_PLUGIN, marketplace $NARROWED_MARKET — the assertions below prove nothing"
  fail=1
fi

# The second leg is the symptom itself, in the wording check 1 passes in.
# Reverting to a check 1 that grades only the commit's own list lands there
# rather than only on the exit code. The third makes check 1 the sole
# discriminator: the tag names the version `plugin.json` carries, so check 2
# agrees, and nothing else here has an opinion about a marketplace version.
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$NARROWED_TAG" 2>&1)" && rc=0 || rc=$?

if ! printf '%s\n' "$out" | grep -qF "release $NARROWED_TAG at $NARROWED_SHORT"; then
  note FAIL "$NARROWED_TAG — did not grade the tagged commit ($NARROWED_SHORT)"
  fail=1
elif printf '%s\n' "$out" | grep -qF "manifests agree with each other"; then
  note FAIL "$NARROWED_TAG — a list of one was graded as manifests agreeing"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "the commit's manifests carry $NARROWED_VERSION"; then
  note FAIL "$NARROWED_TAG — check 2 failed too; the exit code below would not be check 1's"
  fail=1
elif [ "$rc" -ne 1 ]; then
  note FAIL "$NARROWED_TAG — exit $rc, expected 1 ($NARROWED_SHORT says $NARROWED_PLUGIN and $NARROWED_MARKET at once)"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF ".claude-plugin/marketplace.json plugins.0.version"; then
  note FAIL "$NARROWED_TAG — refused without naming the field the commit's list dropped"
  fail=1
else
  note ok "$NARROWED_TAG — refused: the commit does not get to choose what check 1 reads"
fi

# HEAD mode asks it too, and this is where it would be caught in practice: the
# narrowing lands on `main`, and the pre-flight is what runs next.
out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" --head 2>&1)" && rc=0 || rc=$?

if [ "$rc" -ne 1 ]; then
  note FAIL "--head — exit $rc, expected 1 (HEAD's list covers one manifest of two)"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF ".claude-plugin/marketplace.json plugins.0.version"; then
  note FAIL "--head — refused without naming the field HEAD's list dropped"
  fail=1
else
  note ok "--head — the pre-flight refuses it too, before there is a tag to blame"
fi

# The control, and the reason the two above are about the list rather than about
# 4.4.4. Put the whole list back, bump over it so the marketplace entry catches
# up, and move the tag: same version, same tag name, and it passes.
cp .version-bump.json "$FIXTURE/.version-bump.json"
bash "$FIXTURE/scripts/bump-version.sh" "$NARROWED_VERSION" >/dev/null
git -C "$FIXTURE" add -A
git -C "$FIXTURE" -c user.name=t -c user.email=t@e commit -q -m "bump over the whole list"
WHOLE_LIST="$(git -C "$FIXTURE" rev-parse HEAD)"
WHOLE_LIST_SHORT="$(git -C "$FIXTURE" rev-parse --short "$WHOLE_LIST")"
git -C "$FIXTURE" update-ref refs/remotes/origin/main "$WHOLE_LIST"
git -C "$FIXTURE" tag -d "$NARROWED_TAG" >/dev/null
git -C "$FIXTURE" tag "$NARROWED_TAG" "$WHOLE_LIST"

out="$(PATH="$TMP/bin:$PATH" bash "$FIXTURE/scripts/check-release.sh" "$NARROWED_TAG" 2>&1)" && rc=0 || rc=$?

if ! printf '%s\n' "$out" | grep -qF "release $NARROWED_TAG at $WHOLE_LIST_SHORT"; then
  note FAIL "$NARROWED_TAG — list restored, but the tag no longer resolves to $WHOLE_LIST_SHORT"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "manifests agree with each other"; then
  note FAIL "$NARROWED_TAG — the whole list is back and check 1 still does not agree"
  fail=1
elif [ "$rc" -ne 0 ]; then
  note FAIL "$NARROWED_TAG — list restored, $WHOLE_LIST_SHORT still does not pass (exit $rc)"
  fail=1
else
  note ok "$NARROWED_TAG — the whole list back, the same version passes"
fi

# -------------------------------- `main` read from a ref nobody has fetched
# Check 5 prefers `refs/remotes/origin/main` and accepts `refs/heads/main` when
# the remote-tracking ref is absent. Nothing contacts the remote to find out
# what the local one is worth, and in an ordinary working clone it can be worth
# very little: `refs/heads/main` is whatever this clone last fetched, plus
# whatever was committed on it and never pushed.
#
# So in a clone whose local `main` is behind, `--strict --head` printed
# `ok HEAD is refs/heads/main` and exited 0 about a commit the real `main` had
# moved past. That is the shape the section above this one exists to refuse,
# reached not by a stale HEAD but by a stale ref to compare it against — and it
# is reached without anybody doing anything unusual, because not fetching is the
# default state of a clone between fetches.
#
# Both modes are unsound against it, which is why the notice is not HEAD-mode
# only. HEAD equalling a local `main` says nothing about the remote's tip; and a
# local `main` carrying unpushed commits calls a commit that is on nobody else's
# `main` "on `main`", which is check 5's own "nothing ships off a branch".
#
# CI never meets it: `release.yml` runs `git fetch --no-tags origin
# +main:refs/remotes/origin/main` before either mode, so the remote-tracking ref
# is always there. This is the local and hand-run path, which is also the one
# AGENTS.md documents as the way to verify a release.
#
# Nothing here deletes `refs/heads/main` as well — that state (no `main` ref at
# all) is a FAIL the gate has always given, and it is not what this is about.
echo
echo "behaviour — main read from a local ref nobody has checked against the remote"

# A `gh` that answers, where every section above wants one that refuses. This is
# the one place the difference matters: the assertion is what `--strict` fails
# on, and a `gh` that is absent or unauthenticated fails `--strict` all by
# itself, so a refusing stub could not tell the two apart. This one says yes to
# everything, which is a lie about CI and exactly the point — it takes check 6
# out of the exit code so the exit code is check 5's.
mkdir -p "$TMP/bin-gh"
cat > "$TMP/bin-gh/gh" <<'SH'
#!/usr/bin/env bash
case "${1:-}" in
  auth) exit 0 ;;
  api)  echo 1 ;;
  *)    exit 1 ;;
esac
SH
chmod +x "$TMP/bin-gh/gh"

# This section's canary. Both refs have to resolve, and to the same commit, or
# deleting one below changes the answer for a reason that has nothing to do with
# which ref was read.
ORIGIN_MAIN="$(git -C "$FIXTURE" rev-parse refs/remotes/origin/main)"
LOCAL_MAIN="$(git -C "$FIXTURE" rev-parse refs/heads/main)"

if [ "$ORIGIN_MAIN" = "$LOCAL_MAIN" ]; then
  note ok "fixture: refs/heads/main and refs/remotes/origin/main are both $WHOLE_LIST_SHORT"
else
  note FAIL "fixture: refs/heads/main and refs/remotes/origin/main differ — the assertions below prove nothing"
  fail=1
fi

# The control, run first because it is also the baseline the assertions below
# are a difference from: with the remote-tracking ref present and a `gh` that
# answers, this commit is a clean release and `--strict` exits 0.
out="$(PATH="$TMP/bin-gh:$PATH" bash "$FIXTURE/scripts/check-release.sh" --strict --head 2>&1)" && rc=0 || rc=$?
if [ "$rc" -eq 0 ] && printf '%s\n' "$out" | grep -qE '^ +ok +HEAD is refs/remotes/origin/main$'; then
  note ok "--strict --head — with refs/remotes/origin/main present, $WHOLE_LIST_SHORT passes"
else
  note FAIL "--strict --head — $WHOLE_LIST_SHORT does not pass with origin/main present (exit $rc)"
  fail=1
fi

# The same commit, the same command, one ref fewer. This is `git clone --no-tags`
# for check 5: nothing about the release changed, only the evidence available to
# grade it.
git -C "$FIXTURE" update-ref -d refs/remotes/origin/main

out="$(PATH="$TMP/bin-gh:$PATH" bash "$FIXTURE/scripts/check-release.sh" --head 2>&1)" && rc=0 || rc=$?
if ! printf '%s\n' "$out" | grep -qF "grading against local refs/heads/main"; then
  note FAIL "--head — fell back to refs/heads/main without saying so"
  fail=1
elif [ "$rc" -ne 0 ]; then
  note FAIL "--head — exit $rc, expected 0 (a SKIP is not fatal on its own)"
  fail=1
else
  note ok "--head — the fallback is named, and without --strict it is not fatal"
fi

# And the assertion the section is for. `ok HEAD is refs/heads/main` still
# prints, because being level with a local `main` is worth knowing; what it is
# not worth is exit 0 under `--strict`, which is the contract this file already
# holds the `gh` leg and the empty-`refs/tags/` leg to.
out="$(PATH="$TMP/bin-gh:$PATH" bash "$FIXTURE/scripts/check-release.sh" --strict --head 2>&1)" && rc=0 || rc=$?
if ! printf '%s\n' "$out" | grep -qF "HEAD is refs/heads/main"; then
  note FAIL "--strict --head — did not name the ref it graded against"
  fail=1
elif ! printf '%s\n' "$out" | grep -qF "no refs/remotes/origin/main"; then
  note FAIL "--strict --head — graded against a local ref without reporting it as a skip"
  fail=1
elif [ "$rc" -ne 1 ]; then
  note FAIL "--strict --head — exit $rc, expected 1 (a local-only main is evidence --strict refuses)"
  fail=1
else
  note ok "--strict --head — 'ok HEAD is refs/heads/main' no longer exits 0"
fi

# Explicit-tag mode reports it too, and for its own reason: ancestry of a local
# `main` carrying unpushed commits calls a commit on nobody else's `main` on it.
out="$(PATH="$TMP/bin-gh:$PATH" bash "$FIXTURE/scripts/check-release.sh" --strict "$NARROWED_TAG" 2>&1)" && rc=0 || rc=$?
if ! printf '%s\n' "$out" | grep -qF "grading against local refs/heads/main"; then
  note FAIL "$NARROWED_TAG — explicit-tag mode graded a local main without reporting it"
  fail=1
elif [ "$rc" -ne 1 ]; then
  note FAIL "$NARROWED_TAG — exit $rc, expected 1 (--strict refuses the local-only ref in this mode too)"
  fail=1
else
  note ok "$NARROWED_TAG — explicit-tag mode reports the fallback as well"
fi

# Put it back. Nothing runs after this today, and a fixture left in a state the
# next section would have to discover is how a section acquires a dependency
# nobody wrote down.
git -C "$FIXTURE" update-ref refs/remotes/origin/main "$LOCAL_MAIN"

echo
[ "$fail" -eq 0 ] && echo "Release-check tests passed." || echo "Release-check tests FAILED."
exit "$fail"
