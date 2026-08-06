#!/usr/bin/env bash
#
# check-release.sh — refuse a release that does not sit on a checked commit.
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
# Two modes, because "is this releasable?" is two questions:
#
#   HEAD mode      `--head`, or no tag at all. The subject is `git rev-parse
#                  HEAD`, always, and no tag is ever resolved. This is the
#                  pre-flight -- it answers "is `main` releasable right now?"
#   explicit-tag   a tag name. The subject is the commit that tag points at,
#                  which is the thing an installer actually receives.
#
# They were one path, and the seam leaked. The no-tag form derived a tag name
# from the manifests and then resolved it, so from the moment
# `dovetail--v0.4.1` existed, `bash scripts/check-release.sh` printed "checking
# HEAD" and graded `313b9e4` -- the commit that tag already pointed at. Every
# later commit on `main` carrying the same version inherited that verdict. It
# is the 0.4.0 failure one layer up: not a stale release this time but a stale
# answer about one, and `workflow_dispatch` ran exactly that path.
#
# So HEAD mode resolves nothing, and it fails when the version it would release
# is already tagged at another commit, because a version ships once and the
# repair for that is a bump rather than a retag.
#
# Five checks, in the order that gives the most useful failure first:
#
#   1. the manifests agree with each other        (bump-version.sh --check)
#   2. they carry the version in the tag name     (a tag that says 0.4.1 and
#                                                  installs 0.4.0 is worse than
#                                                  no tag)
#   3. RELEASE-NOTES.md has an entry for it
#   4. the commit is on `main`                    (nothing ships off a branch --
#                                                  and where that commit is HEAD
#                                                  it has to *be* `main`, not
#                                                  merely sit in its history)
#   5. `checks` concluded success on that SHA     (needs `gh`; see --strict)
#
# And one only HEAD mode can ask, between 2 and 3: that the version is not
# already released at some other commit. In explicit-tag mode the tag exists at
# the commit under test by definition, so the question is empty there. It reads
# `refs/tags/`, so a clone without tags cannot answer it -- and says so rather
# than passing, because "never released" and "never fetched" look identical from
# in here and only one of them is safe.
#
# Check 2 runs the other way round: in HEAD mode it is the empty one, because
# the version it compares against came out of the manifests it is comparing. It
# prints what HEAD would ship instead of claiming a verdict.
#
# Check 4 splits by mode as well, and that seam leaked next. Ancestry is the
# right test for a tag: a released tag is always behind the tip, and being on
# `main` at all is the whole of what it has to prove. It is the wrong test for
# HEAD mode, whose question is "is `main` releasable right now?" -- every commit
# `main` has ever carried is an ancestor of `main`, so ancestry answers about a
# state `main` has already moved past and hands that back as `main`'s verdict.
# `workflow_dispatch` takes a ref and the operator chooses it, so a run launched
# from a stale branch or an old tag lands exactly there: with HEAD at `313b9e4`
# and `origin/main` at `5b36154`, `--strict --head` reported every check `ok`
# and exited 0 -- and the commit it did not have was `5b36154` itself, the fix
# to this script's own injection hole. It is the 0.4.0 shape a third time: green
# checks, fixes landed afterwards, and the gate blessing the state before them.
#
# So a run grading HEAD requires the tip, and a run grading a resolved tag keeps
# ancestry. That line is drawn on the commit rather than on the mode, because
# they part company in the `no local tag` fallback below: the mode there is
# explicit-tag, the subject is HEAD, and it is somebody about to cut a tag from
# whatever they have checked out -- which is the 0.4.0 hand exactly.
#
# Before any of them, the tag has to be a tag this pack could have issued:
# `<plugin>--v<major>.<minor>.<patch>`, optionally `-<prerelease>`. Anything
# else exits 2 without reading a manifest or touching git. See the block above
# the check for why a release gate validates the shape of its own input.
#
# Usage:
#   bash scripts/check-release.sh                     # HEAD, as the tag the
#                                                     #   manifests imply
#   bash scripts/check-release.sh --head              # the same, said out loud
#   bash scripts/check-release.sh dovetail--v0.4.1    # check an existing tag
#   bash scripts/check-release.sh --strict            # no `gh`, no pass

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v python3 >/dev/null 2>&1 && PY=python3 || PY=python

USAGE="usage: bash scripts/check-release.sh [--strict] [--head|<tag>]"

STRICT=0
HEAD_MODE=0
ASKED_AS=""
TAG=""
for arg in "$@"; do
  case "$arg" in
    --strict) STRICT=1 ;;
    --head)   HEAD_MODE=1 ;;
    "") ;;
    -*) echo "$USAGE" >&2; exit 2 ;;
    *) TAG="$arg" ;;
  esac
done

# The two modes ask different questions, so asking for both asks for nothing.
# Exit 2 rather than pick one: this is input that did not parse, not a check
# that failed, and the difference is what tells them apart in a CI log.
if [ "$HEAD_MODE" -eq 1 ] && [ -n "$TAG" ]; then
  echo "not both: --head checks HEAD, a tag name checks that tag" >&2
  echo "$USAGE" >&2
  exit 2
fi

# No tag named is HEAD mode too. Both routes reach it: a human running the
# pre-flight by hand passes nothing, and release.yml's dispatch step passes an
# empty string. Which route it was decides only the wording -- a message that
# names the wrong reason is how the last one stayed hidden for two releases.
if [ -z "$TAG" ]; then
  ASKED_AS="No tag given"
  [ "$HEAD_MODE" -eq 1 ] && ASKED_AS="HEAD mode"
  HEAD_MODE=1
fi

PLUGIN="$("$PY" -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["name"])')"
MANIFEST_VERSION="$("$PY" -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["version"])')"

# HEAD mode still needs a tag *name* -- checks 2 and 3 grade a version string,
# and the version HEAD would ship is the one the manifests carry. Naming it is
# not the same as resolving it, and below, HEAD mode does not resolve it.
if [ "$HEAD_MODE" -eq 1 ]; then
  TAG="${PLUGIN}--v${MANIFEST_VERSION}"
  echo "$ASKED_AS; checking HEAD as $TAG"
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

# The mode decides the subject, and HEAD mode decides it without consulting
# `refs/tags/` at all. That unconditional `git rev-parse HEAD` is the fix: the
# branch below used to run in both modes, so a tag that already existed silently
# took HEAD's place while the banner above still said "checking HEAD".
#
# `SUBJECT_IS_HEAD` is tracked apart from `$HEAD_MODE` because the two come
# apart in the last branch, and check 4 needs the one they disagree on. The mode
# there is still explicit-tag -- check 2 grades the named tag's version against
# the manifests, which is a real question with a real answer -- but there is no
# tag to resolve, so the commit graded is HEAD. Check 4 keys off the commit.
#
# It starts strict and one branch opts out, rather than each branch declaring
# itself: a fourth branch added later and left undeclared gets the tip test,
# which is the answer that refuses a release rather than the one that waves it
# through.
SUBJECT_IS_HEAD=1
if [ "$HEAD_MODE" -eq 1 ]; then
  SHA="$(git rev-parse HEAD)"
# An annotated tag's own object is not the commit it points at, and `git
# rev-list -n 1` resolves through to the commit either way.
elif git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  SHA="$(git rev-list -n 1 "$TAG")"
  SUBJECT_IS_HEAD=0
else
  # A named tag with no local ref is usually somebody checking a release they
  # are about to cut, so this falls back to HEAD rather than refusing. "No such
  # ref here" is all it can honestly claim, though: a clone that never fetched
  # tags looks exactly like a tag that was never made, and this branch cannot
  # tell them apart. Saying "does not exist" would assert the one it prefers.
  SHA="$(git rev-parse HEAD)"
  echo "no local tag $TAG; checking HEAD ($(git rev-parse --short "$SHA"))"
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

if [ "$HEAD_MODE" -eq 1 ]; then
  # Not a check in this mode, and printed as what it is. `$VERSION` was parsed
  # back out of a tag name this script built from `$MANIFEST_VERSION` twenty
  # lines up, so the comparison below cannot fail here; an `ok` that cannot go
  # the other way reads as a check and is not one.
  note ok "HEAD would ship $VERSION"
elif [ "$MANIFEST_VERSION" = "$VERSION" ]; then
  note ok "manifests carry $VERSION"
else
  note FAIL "tag says $VERSION, manifests say $MANIFEST_VERSION"
  fail=1
fi

# HEAD mode only, and it is the check that makes the mode worth having. Not
# resolving the tag stops the gate answering about the wrong commit; it does not
# stop HEAD being unreleasable *because* that version already went out. A
# version ships once, so once `$TAG` names another commit the repair is a bump,
# not a retag -- and a published tag is a thing other people have installed.
#
# In explicit-tag mode the tag existing at the commit under test is the ordinary
# case and carries no information, so this stays quiet there.
if [ "$HEAD_MODE" -eq 1 ]; then
  if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    TAGGED="$(git rev-list -n 1 "$TAG")"
    if [ "$TAGGED" = "$SHA" ]; then
      note ok "$TAG already points here — this commit is the release"
    else
      note FAIL "$VERSION is already released, at $(git rev-parse --short "$TAGGED") — bump the version"
      fail=1
    fi
  elif [ -n "$(git tag --list "${PLUGIN}--v*")" ]; then
    note ok "$VERSION is not released yet"
  else
    # Same contract as the `gh` leg below, and it is load-bearing here rather
    # than tidy. This check reads `refs/tags/`, and an empty `refs/tags/` has
    # two readings with opposite verdicts: nothing has ever been released, or
    # this clone never fetched tags. `git clone --depth 1`, `--no-tags` and
    # actions/checkout's default all produce the second, and from inside the
    # repository the two are identical. Passing quietly on that evidence is the
    # original bug restored by environment alone, so say what could not be read.
    note SKIP "no $PLUGIN tags here — cannot tell an unreleased version from an unfetched tag"
    if [ "$STRICT" -eq 1 ]; then
      fail=1
    fi
  fi
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

# Two strengths of one question, because the two subjects need different ones. A
# resolved tag has to prove it is somewhere on `main`. A run grading HEAD has to
# prove HEAD *is* `main`, and `--is-ancestor` cannot carry that -- see the block
# at the top of the file. The behind case gets its own arm rather than folding
# into "not on main": those are opposite repairs -- fetch and re-run, against
# land it on `main` first -- and a gate that names the wrong one sends the
# reader somewhere there is nothing to find.
if [ -z "$MAIN" ]; then
  note FAIL "no main ref to check against — fetch it first (git fetch origin main)"
  fail=1
elif [ "$SUBJECT_IS_HEAD" -eq 1 ]; then
  MAIN_SHA="$(git rev-parse "$MAIN")"
  if [ "$SHA" = "$MAIN_SHA" ]; then
    note ok "HEAD is $MAIN"
  elif git merge-base --is-ancestor "$SHA" "$MAIN"; then
    behind="$(git rev-list --count "$SHA..$MAIN")"
    note FAIL "HEAD is $behind commit(s) behind $MAIN — $(git rev-parse --short "$MAIN_SHA") is what would ship"
    fail=1
  else
    note FAIL "HEAD is not on $MAIN — nothing ships off a branch"
    fail=1
  fi
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
