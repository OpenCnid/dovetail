#!/usr/bin/env bash
#
# check-release.sh — refuse a tag that does not point at a checked commit.
#
# This exists because of what happened at 0.4.0. The tag went up, then four
# commits landed on `main` fixing stale licence records, stale test paths, a
# Linux-only path bug, a lint that aborted at its first finding, and 31 tracked
# `.pyc` files. Every one of them was green in CI. None of them reached anybody,
# because the published release still pointed at the commit before all of it,
# and nothing anywhere connected "the checks passed" to "this is what ships".
#
# `checks.yml` runs on pushes and pull requests. It does not run on tags, and a
# tag is not a commit — it is a pointer, and it can point anywhere. So the
# question this script asks is not "do the checks pass?" but "did they already
# pass, on this exact SHA?" An ancestor is not good enough: the fix could be the
# thing that broke. A later commit is not good enough either: it is not what the
# tag hands to an installer.
#
# Five checks, in the order that gives the most useful failure first:
#
#   1. the manifests agree with each other        (bump-version.sh --check)
#   2. they carry the version in the tag name     (a tag that says 0.4.1 and
#                                                  installs 0.4.0 is worse than
#                                                  no tag)
#   3. RELEASE-NOTES.md has an entry for it
#   4. the commit is on `main`                    (nothing ships off a branch)
#   5. `checks` concluded success on that SHA     (needs `gh`; see --strict)
#
# Before any of them, the tag has to be a tag this pack could have issued:
# `<plugin>--v<major>.<minor>.<patch>`, optionally `-<prerelease>`. Anything
# else exits 2 without reading a manifest or touching git. See the block above
# the check for why a release gate validates the shape of its own input.
#
# Usage:
#   bash scripts/check-release.sh                     # check HEAD as the tag
#                                                     #   the manifests imply
#   bash scripts/check-release.sh dovetail--v0.4.1    # check an existing tag
#   bash scripts/check-release.sh --strict            # no `gh`, no pass

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v python3 >/dev/null 2>&1 && PY=python3 || PY=python

STRICT=0
TAG=""
for arg in "$@"; do
  case "$arg" in
    --strict) STRICT=1 ;;
    "") ;;
    -*) echo "usage: bash scripts/check-release.sh [--strict] [<tag>]" >&2; exit 2 ;;
    *) TAG="$arg" ;;
  esac
done

PLUGIN="$("$PY" -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["name"])')"
MANIFEST_VERSION="$("$PY" -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["version"])')"

# No tag named: check the release the working tree is currently describing. This
# is the pre-flight form -- run it before `claude plugin tag`, not after.
if [ -z "$TAG" ]; then
  TAG="${PLUGIN}--v${MANIFEST_VERSION}"
  echo "No tag given; checking HEAD as $TAG"
  echo
fi

# The tag is the one input here that somebody else names, and `git` accepts far
# more in a ref than this convention does: `dovetail--v9.9.9$(id)` is a legal
# tag name and matches the release workflow's `dovetail--v*` trigger. Nothing in
# this script evaluates it -- every use below is quoted, and the workflow now
# hands it over in an environment variable rather than splicing it into a
# command line -- so this is the layer that means a tag whose shape cannot be
# parsed is refused outright rather than half-read into a version string.
#
# Deliberately narrower than `git check-ref-format`: the convention is
# `<plugin>--v<major>.<minor>.<patch>`, optionally `-<prerelease>`, and a
# release gate has no reason to accept anything else. The character class comes
# first so that a rejection message can quote the tag knowing what is in it.
VERSION_RE='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$'

reject_tag() {
  echo "not a $PLUGIN release tag: $1" >&2
  echo "expected ${PLUGIN}--v<major>.<minor>.<patch>[-prerelease]" >&2
  exit 2
}

case "$TAG" in
  *[!A-Za-z0-9.-]*) reject_tag "$TAG" ;;
  "${PLUGIN}--v"*)  VERSION="${TAG#"${PLUGIN}--v"}" ;;
  *)                reject_tag "$TAG" ;;
esac

[[ "$VERSION" =~ $VERSION_RE ]] || reject_tag "$TAG"

# An annotated tag's own object is not the commit it points at, and `git
# rev-list -n 1` resolves through to the commit either way.
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  SHA="$(git rev-list -n 1 "$TAG")"
else
  SHA="$(git rev-parse HEAD)"
  echo "tag $TAG does not exist yet; checking HEAD ($(git rev-parse --short "$SHA"))"
  echo
fi

fail=0
note() { printf '  %-6s %s\n' "$1" "$2"; }

echo "release $TAG at $(git rev-parse --short "$SHA")"
echo

# 1 + 2. Manifest agreement is bump-version.sh's job and it already exits
# non-zero on disagreement; all this adds is that they agree *with the tag*.
if bash scripts/bump-version.sh --check >/dev/null 2>&1; then
  note ok "manifests agree with each other"
else
  note FAIL "manifests disagree — run: bash scripts/bump-version.sh --check"
  fail=1
fi

if [ "$MANIFEST_VERSION" = "$VERSION" ]; then
  note ok "manifests carry $VERSION"
else
  note FAIL "tag says $VERSION, manifests say $MANIFEST_VERSION"
  fail=1
fi

# 3. The heading format is `## v0.4.1 (2026-08-05)`.
if grep -q "^## v${VERSION//./\\.} " RELEASE-NOTES.md; then
  note ok "RELEASE-NOTES.md has a v$VERSION entry"
else
  note FAIL "RELEASE-NOTES.md has no '## v$VERSION' entry"
  fail=1
fi

# 4. `origin/main` where a remote-tracking ref exists, local `main` otherwise --
# a fresh CI checkout has the former, a working clone usually both, and a
# detached-HEAD checkout of a tag may have neither.
MAIN=""
for ref in refs/remotes/origin/main refs/heads/main; do
  if git rev-parse -q --verify "$ref" >/dev/null; then
    MAIN="$ref"
    break
  fi
done

if [ -z "$MAIN" ]; then
  note FAIL "no main ref to check against — fetch it first (git fetch origin main)"
  fail=1
elif git merge-base --is-ancestor "$SHA" "$MAIN"; then
  note ok "commit is on $MAIN"
else
  note FAIL "commit is not on $MAIN — nothing ships off a branch"
  fail=1
fi

# 5. The one that needed a new script. A run is recorded against the SHA it ran
# on, so `head_sha` is the whole check: it cannot be satisfied by a green
# ancestor. `status=success` on a workflow run is the run's conclusion, and the
# matrix reports one run, so both legs are covered by one answer.
echo
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  runs="$(gh api "repos/{owner}/{repo}/actions/workflows/checks.yml/runs?head_sha=${SHA}&status=success" \
    --jq '.workflow_runs | length' 2>/dev/null || echo error)"
  case "$runs" in
    error)  note FAIL "could not read workflow runs for $SHA" ; fail=1 ;;
    0)      note FAIL "no successful 'checks' run on this exact SHA" ; fail=1 ;;
    *)      note ok "'checks' concluded success on this SHA ($runs run(s))" ;;
  esac
else
  # Same contract as lint-shell.sh: a pass that skipped a check says so, rather
  # than letting a clean run mean nothing was checked.
  echo "  gh: not installed or not authenticated — the CI-validation check did NOT run."
  echo "  This is the check the release exists for. Install gh, or pass --strict to fail here."
  [ "$STRICT" -eq 1 ] && fail=1
fi

echo
[ "$fail" -eq 0 ] && echo "Release check passed." || echo "Release check FAILED."
exit "$fail"
