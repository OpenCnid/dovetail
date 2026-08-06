#!/usr/bin/env bash
#
# publish-release.sh — create the release tag, and only after the gate passes.
#
# `check-release.sh` answers "should this have shipped?". It is the right
# question and it is asked too late: `release.yml` runs on `push: tags`, so by
# the time it has an answer the ref is on the remote and anything resolving
# `dovetail--v*` can already fetch it. A tag is not a proposal -- publishing it
# *is* the release, and a gate downstream of publication can only report.
#
# So this is the other half: the thing that makes the tag. It exists to be the
# only route by which one gets made, which is why the gate is not a step beside
# it but a call inside it. A workflow can be edited to run its steps in the
# wrong order; a function cannot be persuaded to return before it is called.
# Nothing here creates a ref that `run_gate` has not already passed.
#
# Two modes, and the safe one is not the default -- it is the only one that
# happens without saying `--publish` out loud:
#
#   --dry-run    run every check, print the API calls that would be made, and
#                make none of them. This is also the pre-flight: it answers "is
#                this commit publishable, and as what?" without side effects.
#   --publish    the same checks, then the three writes.
#
# Inputs arrive in the environment rather than on the command line, for the
# reason release.yml hands `RELEASE_TAG` over that way: `${{ }}` inside a `run:`
# body substitutes into the shell source before bash parses it, and a dispatch
# input is chosen by whoever dispatches.
#
#   RELEASE_SHA       the commit to release. Full 40-character hex, and it must
#                     be what is checked out -- see below for why a ref name is
#                     refused.
#   RELEASE_VERSION   the version that commit ships. Compared against the
#                     commit's own manifests and refused on disagreement.
#
# RELEASE_VERSION is redundant and that is its whole function. Every other fact
# here is read out of the commit, so a dispatch that names the wrong commit gets
# a coherent answer about the wrong release -- every check passes, because they
# all describe whatever was named. Typing the version is the one assertion the
# operator makes that the commit cannot confirm on its own, so a mismatch means
# the operator and the commit disagree about what is shipping, and that is worth
# an exit 2 rather than a preference.
#
# `RELEASE_SHA` is a SHA and never a ref name for the same reason. `main` names
# whatever `main` is at the moment each command runs, and there are several
# moments here -- checkout, gate, tag creation, and on a workflow with an
# approval gate an unbounded wait in the middle. Resolving it once and requiring
# every later step to agree is what makes those moments one commit.
#
# The gate this calls is `check-release.sh --strict --head`, unchanged, on a
# checkout of `$RELEASE_SHA`. HEAD mode is already "validate before a tag
# exists" -- it resolves no tag to find its subject -- and it holds that subject
# to `origin/main`'s tip rather than to its history. That is a real constraint
# and it is deliberate: the commit being released has to be `main` right now,
# not somewhere in `main`'s past. Releasing an ancestor is the 0.4.0 failure
# with the operator's blessing attached, and no mode here offers it.
#
# What this cannot do, stated plainly because the whole point is prevention:
# nothing in this repository stops somebody with write access pushing
# `dovetail--v9.9.9` by hand. Only a tag ruleset restricting creation to this
# workflow's identity does that. This script is what the ruleset makes the sole
# route; without the ruleset it is merely the tidy one. See AGENTS.md.
#
# Usage:
#   RELEASE_SHA=<40-hex> RELEASE_VERSION=<x.y.z> bash scripts/publish-release.sh --dry-run
#   RELEASE_SHA=<40-hex> RELEASE_VERSION=<x.y.z> bash scripts/publish-release.sh --publish

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v python3 >/dev/null 2>&1 && PY=python3 || PY=python

USAGE="usage: RELEASE_SHA=<40-hex> RELEASE_VERSION=<x.y.z> bash scripts/publish-release.sh --dry-run|--publish"

MODE=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) MODE=dry-run ;;
    --publish) MODE=publish ;;
    *) echo "$USAGE" >&2; exit 2 ;;
  esac
done

# No default. A mode this script guessed is a mode nobody chose, and one of the
# two writes to a remote.
if [ -z "$MODE" ]; then
  echo "no mode given: --dry-run checks and prints, --publish checks and writes" >&2
  echo "$USAGE" >&2
  exit 2
fi

SHA="${RELEASE_SHA:-}"
VERSION_CLAIMED="${RELEASE_VERSION:-}"

refuse() { echo "$1" >&2; exit 2; }

# ------------------------------------------------------------------- the input
# Full hex only, and lower case only. `git rev-parse` would happily accept
# `main`, `HEAD~3`, a short prefix or a tag, and every one of those names a
# commit that can change between now and the last write below. An abbreviation
# is refused rather than expanded for the same reason: the operator names the
# commit, or this does not run.
case "$SHA" in
  "") refuse "RELEASE_SHA is empty — name the commit to release, as a full 40-character SHA" ;;
  *[!0-9a-f]*) refuse "RELEASE_SHA is not lowercase hex: $SHA" ;;
esac
[ "${#SHA}" -eq 40 ] || refuse "RELEASE_SHA is ${#SHA} characters, expected 40: $SHA"

[ -n "$VERSION_CLAIMED" ] ||
  refuse "RELEASE_VERSION is empty — state the version being released, so the commit can disagree"

git rev-parse -q --verify "$SHA^{commit}" >/dev/null 2>&1 ||
  refuse "no commit $SHA in this repository — fetch it first"

# The checkout has to *be* the commit, not merely contain it. Every check below
# that reads the commit reads it through `git show`, but `check-release.sh
# --head` grades `git rev-parse HEAD`, and if those two are different commits
# this script reports on one and the gate blesses the other.
HEAD_SHA="$(git rev-parse HEAD)"
[ "$HEAD_SHA" = "$SHA" ] ||
  refuse "HEAD is $HEAD_SHA, RELEASE_SHA is $SHA — check out the commit being released"

# ------------------------------------------------------- what the commit says
# Both halves out of the commit, the way check-release.sh reads them, and for
# the same reason: an uncommitted rename or bump on disk describes nothing that
# ships.
MANIFEST_JSON="$(git show "$SHA:.claude-plugin/plugin.json" 2>/dev/null)" ||
  refuse "no .claude-plugin/plugin.json at $SHA — this commit does not carry this pack's manifest"

MANIFEST_ID="$(printf '%s' "$MANIFEST_JSON" |
  "$PY" -c 'import json,sys;m=json.load(sys.stdin);print(m["name"],m["version"])' 2>/dev/null)" ||
  refuse "unreadable .claude-plugin/plugin.json at $SHA"

PACK="${MANIFEST_ID%% *}"
VERSION="${MANIFEST_ID##* }"

[ "$VERSION" = "$VERSION_CLAIMED" ] ||
  refuse "RELEASE_VERSION says $VERSION_CLAIMED, $SHA ships $VERSION — one of them is the wrong commit"

TAG="${PACK}--v${VERSION}"

# The convention, checked here as well as in the gate. This is the string that
# becomes a ref on the remote, and a name assembled out of a manifest is still a
# name assembled out of a file somebody can edit.
VERSION_RE='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$'
[[ "$VERSION" =~ $VERSION_RE ]] ||
  refuse "not a release version: $VERSION — expected <major>.<minor>.<patch>[-prerelease]"
case "$PACK" in
  *[!A-Za-z0-9.-]*) refuse "not a pack name this could tag: $PACK" ;;
esac

echo "publish $TAG at $(git rev-parse --short "$SHA")"
echo

note() { printf '  %-6s %s\n' "$1" "$2"; }

# ------------------------------------------------------------ already released
# A version ships once. Both reads matter and they fail differently: a local ref
# means this clone already knows, and the remote is the one that decides. The
# remote read is a network call on a path that is about to make three more, so
# it costs nothing it was not already spending.
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  refuse "$TAG already exists locally, at $(git rev-list -n 1 "$TAG") — a published version is not re-cut"
fi

# The read that decides, and the one whose *failure* is the interesting case. A
# `git ls-remote` that cannot reach the remote returns nothing, and nothing is
# also what an unpublished tag returns -- the two look identical from here, and
# only one of them is safe to proceed on. So the exit status is checked apart
# from the output, and an unreachable remote refuses. This is the shape that has
# bitten this repository twice already: an empty `refs/tags/` cannot tell "never
# released" from "never fetched", and an absent `gh` cannot tell "checks passed"
# from "never asked". Absence is not evidence of absence, and on the one path
# here that writes to a remote there is no `SKIP` worth having.
if ! REMOTE_TAG="$(git ls-remote --tags --refs origin "refs/tags/$TAG" 2>/dev/null)"; then
  refuse "cannot reach origin to ask whether $TAG is published — that is not the same as it being unpublished"
fi
[ -z "$REMOTE_TAG" ] ||
  refuse "$TAG already exists on origin — a published tag is a thing other people have installed"
note ok "$TAG is not published, here or on origin"

# ------------------------------------------------------------------- the gate
# Not a step beside this script but a call inside it. `check-release.sh` is the
# six checks and this adds none of its own to them; what it adds is that the
# writes below are unreachable when it exits non-zero.
#
# `--strict` because the check this exists for is check 6 -- did `checks`
# conclude success on this exact SHA -- and without `gh` that check does not run
# at all. A publish path that silently skipped it would be publishing on the
# strength of the four checks that never needed CI.
echo
if bash scripts/check-release.sh --strict --head; then
  echo
  note ok "the release gate passed on $SHA"
else
  echo
  echo "the release gate refused $SHA — nothing was created." >&2
  exit 1
fi

# --------------------------------------------------------------- the notes body
# The entry `check-release.sh` already proved is there, from the heading to the
# next one. Read from the commit, so the release body is what the release says.
NOTES="$(git show "$SHA:RELEASE-NOTES.md" |
  awk -v v="## v$VERSION " 'index($0, v) == 1 {found = 1; next} found && /^## v/ {exit} found {print}')"

# ------------------------------------------------------------------ the writes
# Annotated, because every tag this pack has published is annotated and
# `check-release.sh` resolves through a tag object with `git rev-list -n 1`. A
# lightweight ref here would be a quiet change to what the gate is reading.
#
# Three calls, in an order chosen so a failure leaves the least behind: the tag
# object is unreferenced garbage until the ref points at it, and the ref is the
# moment the release becomes fetchable. The release object is last because it is
# the announcement, and an announcement of a tag that does not exist is worse
# than a tag nobody announced.
if [ "$MODE" = "dry-run" ]; then
  echo
  echo "dry run — these calls were NOT made:"
  echo "  POST /repos/{owner}/{repo}/git/tags   tag=$TAG object=$SHA type=commit"
  echo "  POST /repos/{owner}/{repo}/git/refs   ref=refs/tags/$TAG sha=<the tag object>"
  echo "  POST /repos/{owner}/{repo}/releases   tag_name=$TAG name=$TAG"
  echo
  echo "Release ${TAG} is publishable. Nothing was created."
  exit 0
fi

command -v gh >/dev/null 2>&1 ||
  { echo "gh is required to publish" >&2; exit 2; }

TAG_OBJECT="$(gh api --method POST "repos/{owner}/{repo}/git/tags" \
  -f tag="$TAG" -f object="$SHA" -f type=commit -f message="$TAG" --jq .sha)"
note ok "tag object $TAG_OBJECT"

gh api --method POST "repos/{owner}/{repo}/git/refs" \
  -f ref="refs/tags/$TAG" -f sha="$TAG_OBJECT" --jq .ref >/dev/null
note ok "refs/tags/$TAG — the release is now fetchable"

gh api --method POST "repos/{owner}/{repo}/releases" \
  -f tag_name="$TAG" -f name="$TAG" -f body="$NOTES" --jq .html_url

echo
echo "Release $TAG published."
