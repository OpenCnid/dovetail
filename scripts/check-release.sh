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
#                  which is the thing an installer actually receives. A tag
#                  with no ref here is refused rather than stood in for.
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
# The seam leaked the other way too. Explicit-tag mode fell back to HEAD when
# the named tag had no ref here, so `git clone --no-tags` was the whole
# reproduction: the tag is published, the clone never fetched it, and the gate
# printed "release <tag> at <HEAD>" and passed. Somebody checking a release that
# had already shipped was told it was fine, about a commit that was not it. That
# fallback served "I am about to cut this tag", which `--head` now serves by
# saying so, so the tag branch refuses instead. See it for what exit 2 buys.
#
# Five checks, in the order that gives the most useful failure first:
#
#   1. the manifests agree with each other        (bump-version.sh --check)
#   2. they spell out the tag: both the pack name (a tag that says 0.4.1 and
#      and the version it carries                  installs 0.4.0 is worse than
#                                                  no tag -- and so is one that
#                                                  says `dovetail` and installs
#                                                  another pack entirely)
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
# ancestry. That line used to be drawn on the commit rather than on the mode,
# because a third branch parted them: a named tag with no ref here fell back to
# HEAD, so the mode was explicit-tag while the subject was HEAD. That branch is
# gone -- see it below for why -- and with it the only case where the two
# disagreed, so the mode decides again.
#
# All five grade the same commit, which took a fix of its own. Checks 1-3 read
# the files on disk while 4 and 5 read `$SHA`, and nothing tied the two
# together: the `cd "$ROOT"` below fixes the working tree as the subject of the
# first three, so an explicit tag was graded for ancestry and CI on its own
# commit and for version and notes on whatever was checked out. With the
# tree bumped to 0.5.0 and uncommitted, and `dovetail--v0.5.0` pointing at a
# commit whose manifests say 0.4.1 and whose notes have no 0.5.0 entry, all five
# printed `ok`. That is check 2's own "a tag that says 0.4.1 and installs 0.4.0",
# issued by the gate that exists to refuse it. So the version-bearing files come
# out of the commit now, through `git show`, and uncommitted work is reported
# rather than graded -- an installer never receives it.
#
# That fix moved the version and left the pack *name* behind, and the same shape
# came back one field over. Check 2 compared only the version, and `$PLUGIN` was
# read off the checkout, so `dovetail--v8.8.8` at a commit whose manifests say
# `otherpack` matched on the only half anybody looked at -- and checks 1, 3 and 4
# have no opinion about which pack they are reading. Four `ok`s for a tag that
# installs somebody else's pack. Check 2 now grades the whole tag, both halves
# out of `$SHA`, and HEAD mode builds the name it checks from the commit too:
# built from the checkout, an uncommitted rename pointed the already-released
# check at a pack with no tags and turned a `FAIL` into a `SKIP`.
#
# Two reads from the checkout survive on purpose. `scripts/bump-version.sh` is
# copied rather than taken from the commit -- see check 1 -- and the pack name is
# read there once, to parse the tag before there is a commit to read it from.
# That one is a shape test, not the name check; the name check is check 2, and it
# reads `$SHA`. So the narrow true statement is that no file the checks *grade*
# comes off the disk, rather than that the disk is never opened.
#
# Before any of them, the tag has to be a tag this pack could have issued:
# `<plugin>--v<major>.<minor>.<patch>`, optionally `-<prerelease>`. Anything else
# exits 2 without touching git. It does read the checkout's manifest first, for
# the name to compare against -- the one file opened before the shape is checked.
# See the block above the check for why a release gate validates its own input.
#
# The tag is not the only input, which took a fix of its own. Grading a commit's
# files rather than the checkout's means reading that commit's
# `.version-bump.json` to learn which files those are -- so the commit under test
# names the paths, and `snapshot` built a redirection target out of each one.
# Bash opens a redirection target before the command runs, so `../x` truncated a
# file outside the snapshot whatever `git show` then made of the argument. Paths
# are validated at `snapshot` now, and a list that names one outside the tree
# fails check 1 as itself rather than as manifests that disagree.
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

# The pack's own name, and the one thing here read from the checkout rather than
# from the commit under test. It is what makes `dovetail--v0.4.1` a tag *this*
# pack could have issued -- a question about the convention this script enforces,
# not about any one commit -- and parsing the tag needs it before there is a
# resolved commit to read it from. The version goes the other way: it is a
# property of the commit, and it is read there, further down.
PLUGIN="$("$PY" -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["name"])')"

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
  echo "not a $2 release tag: $1" >&2
  echo "expected ${2}--v<major>.<minor>.<patch>[-prerelease]" >&2
  exit 2
}

# Sets `$VERSION` from `$TAG`, or exits 2. `$1` is the pack name the tag has to
# carry, and the two modes supply it from opposite places for the same reason
# each supplies its subject from where it does. Explicit-tag mode passes the
# checkout's name, because the tag has to parse before there is a resolved
# commit to read a name out of -- and a shape this pack could never have issued
# is refused there, before any commit is graded. HEAD mode passes the name out
# of the commit it already resolved, because by then there is one, and a version
# that cannot be a version means a stale or hand-edited manifest rather than a
# hostile push -- refusing is still the answer.
#
# Parsing against the checkout's name is a shape test, not the name check. That
# one cannot happen here, because the commit is not resolved yet; it is check 2,
# below, and it is what stops a tag naming one pack being blessed at another
# pack's commit.
parse_tag() {
  local expect="$1"
  case "$TAG" in
    *[!A-Za-z0-9.-]*) reject_tag "$TAG" "$expect" ;;
    "${expect}--v"*)  VERSION="${TAG#"${expect}--v"}" ;;
    *)                reject_tag "$TAG" "$expect" ;;
  esac

  [[ "$VERSION" =~ $VERSION_RE ]] || reject_tag "$TAG" "$expect"
}

[ "$HEAD_MODE" -eq 1 ] || parse_tag "$PLUGIN"

# The mode decides the subject, and HEAD mode decides it without consulting
# `refs/tags/` at all. That unconditional `git rev-parse HEAD` is the fix: the
# branch below used to run in both modes, so a tag that already existed silently
# took HEAD's place while the banner said "checking HEAD".
#
# There were three branches here and the third is gone, which is why the mode
# alone decides the subject again. It used to fall back to HEAD when the named
# tag had no ref, so the mode and the commit came apart and `SUBJECT_IS_HEAD`
# existed to carry the difference to check 4. Nothing parts them now.
if [ "$HEAD_MODE" -eq 1 ]; then
  SHA="$(git rev-parse HEAD)"
# An annotated tag's own object is not the commit it points at, and `git
# rev-list -n 1` resolves through to the commit either way.
elif git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  SHA="$(git rev-list -n 1 "$TAG")"
else
  # A tag this repository cannot resolve is not a subject, and a gate with no
  # subject has nothing to grade. This used to fall back to HEAD, on the theory
  # that naming a tag with no ref means "I am about to cut this" -- but `--head`
  # asks that outright now, and the fallback's price was a verdict about HEAD
  # printed under the tag's name, in a clone where the tag was published all
  # along. The message was honest by then; the answer still was not.
  #
  # Exit 2, the same code as a tag that does not parse, because it is the same
  # kind of answer: this input did not resolve to a commit, so no check ran and
  # there is no verdict either way. Exit 1 would claim the release failed one.
  #
  # Both readings are named because this branch still cannot tell them apart --
  # and `git ls-remote` would reword that rather than settle it. Even knowing
  # the tag is published at some SHA, checks 4 and 5 need that commit *here*:
  # `merge-base --is-ancestor` against an object this clone lacks is a fatal,
  # not a verdict. The answer would still be "fetch it and ask again", bought
  # with a network call on the one path that needs none.
  echo "cannot resolve $TAG in this repository" >&2
  echo "no ref refs/tags/$TAG — and this cannot tell a tag that was never made" >&2
  echo "from one this clone never fetched (git clone --no-tags, --depth 1 and" >&2
  echo "actions/checkout's default all leave refs/tags/ empty)." >&2
  echo "  git fetch --tags origin        # then ask again" >&2
  echo "  bash scripts/check-release.sh --head   # or grade HEAD, before tagging" >&2
  exit 2
fi

# ------------------------------------------------------- the graded checkout
# `$SHA` is settled, so from here the files the checks read come out of it. Only
# the files the checks read: `git archive` of the whole tree exceeds MAX_PATH on
# Windows -- `skills/better-skill-creator/tests/fixtures/` is the offender, and
# `checks` runs this on `windows-latest` -- and nothing else here is opened.
SNAPSHOT="$(mktemp -d)"
trap 'rm -rf "$SNAPSHOT"' EXIT

# A path this tree could carry: relative, normalised, and inside itself. Three
# of the four call sites below pass a literal and could not fail this. The
# fourth, the loop in `snapshot_manifests`, passes whatever `.version-bump.json`
# lists -- and that file is read out of the commit under test, so the commit
# being graded chooses those bytes, exactly as whoever pushes a tag chooses the
# tag name. It is the gate's second outside input, and it was the one nothing
# validated.
#
# The patterns are grouped by what they refuse rather than golfed into one,
# because the two groups are different arguments.
snapshot_path_ok() {
  case "$1" in
    # No component may be empty, `.` or `..`, and the path may not be absolute.
    # `..` is the traversal; the rest are the forms that make a denylist of `..`
    # alone look sufficient. Refusing an unnormalised path that happens to stay
    # inside is the safe direction and costs nothing -- nothing writes
    # `./plugin.json` in a list of this pack's manifests, and a run that meets
    # one says which path to repair.
    ""|.|..|./*|../*|*/./*|*/../*|*/.|*/..|/*|*/|*//*) return 1 ;;
    # Windows separates directories with a backslash, so the same bytes are one
    # ordinary filename on Linux and a directory walk on `windows-latest`, where
    # half of `checks` runs (measured 2026-08-06, git-bash 5.2.37(msys), Windows
    # 10: `..\..\x` redirected to from two directories down truncated `x` and
    # created nothing where it was written). A colon is a drive letter on the
    # same platform, and `git show`'s own `<rev>:<path>` separator on every one.
    #
    # Quoted, and that is not style: an unquoted `*\\*` in a `case` pattern is
    # `*\*`, which matches a literal asterisk and no backslash at all. Written
    # that way this arm reads as covering Windows while covering nothing.
    *'\'*|*:*) return 1 ;;
  esac
  return 0
}

# Set by `snapshot` when it refuses a path, rather than when `git show` fails to
# find one. Those are different verdicts and check 1 reads this to tell them
# apart: "this commit does not carry that manifest" is a disagreement about
# manifests, and "that is not a path in this tree" is not a manifest question at
# all.
SNAPSHOT_REFUSED=""

# Non-zero when the commit does not carry the path at all. Each caller reports
# that as its own check failing rather than aborting the run: "this commit has
# no RELEASE-NOTES.md" is a release-check answer, not a git error.
#
# The guard runs before `mkdir -p` and before the redirection, and the
# redirection is the reason it has to. Bash opens a redirection target before
# the command on the line ever runs, so a listed path of `../x` truncated `x`
# outside `$SNAPSHOT` and *then* `git show` failed on a path no commit carries.
# The gate printed FAIL -- correctly, and about manifests that disagree rather
# than about the write -- while a file it was never asked to touch was already
# empty, with `mkdir -p` having made the directories on the way. Reproduced
# 2026-08-06 on git-bash 5.2.37(msys), Windows 10: a 36-byte canary outside the
# snapshot came back 0 bytes, with `git show` failing as expected.
#
# Refused rather than clamped or resolved. A commit whose `.version-bump.json`
# points outside its own tree is not a commit to repair on the fly.
snapshot() {
  if ! snapshot_path_ok "$1"; then
    SNAPSHOT_REFUSED="$1"
    return 1
  fi
  mkdir -p "$SNAPSHOT/$(dirname "$1")"
  git show "$SHA:$1" > "$SNAPSHOT/$1" 2>/dev/null
}

# The one snapshot failure that is not a check failing. Everything below reads a
# name and a version, so a commit with no manifest is not an unreleasable commit
# -- it is not this pack, and there is no verdict to give about it.
#
# Both fields come out in one read, because they are one fact: the release tag
# this commit says it is. `name` used to be taken from the checkout and only
# `version` from here, which is what let a tag naming one pack pass at another
# pack's commit -- see check 2.
if ! snapshot .claude-plugin/plugin.json ||
   ! MANIFEST_ID="$("$PY" -c 'import json,sys;m=json.load(open(sys.argv[1]));print(m["name"],m["version"])' \
       "$SNAPSHOT/.claude-plugin/plugin.json" 2>/dev/null)"; then
  echo "no readable .claude-plugin/plugin.json at $(git rev-parse --short "$SHA")" >&2
  echo "this gate grades a commit, and that commit does not carry this pack's manifest" >&2
  exit 2
fi

# One line, two fields, so command substitution's trailing-newline strip covers
# the CRLF that Python's text mode writes on Windows -- the translation the loop
# further down has to undo by hand, because reading line by line does not.
MANIFEST_NAME="${MANIFEST_ID%% *}"
MANIFEST_VERSION="${MANIFEST_ID##* }"

# HEAD mode still needs a tag *name* -- checks 2 and 3 grade a version string,
# and the tag HEAD would ship is the one HEAD's own manifests spell out, both
# halves of it, which is why this waits for the snapshot instead of reading the
# copy on disk. Naming a tag is not resolving one, and HEAD mode resolves none
# to pick its subject: the only tag it looks up is this name, and only to ask
# whether the version is already out.
#
# The name comes from `$SHA` for the same reason the version does. Built from
# the checkout, an uncommitted rename renamed what HEAD "would ship", and the
# already-released check below then went looking under a pack name that has
# never released anything and reported that it could not tell -- the one check
# the mode exists for, switched off by an unsaved edit.
if [ "$HEAD_MODE" -eq 1 ]; then
  TAG="${MANIFEST_NAME}--v${MANIFEST_VERSION}"
  parse_tag "$MANIFEST_NAME"
  echo "$ASKED_AS; checking HEAD as $TAG"
  echo
fi

fail=0
note() { printf '  %-6s %s\n' "$1" "$2"; }

echo "release $TAG at $(git rev-parse --short "$SHA")"

# Nothing the checks grade is read from the working tree any more, which is right
# and is invisible: the reader is looking at 0.5.0 in an editor while the gate
# answers about the 0.4.1 in the commit. Say so, rather than let the two be
# reconciled by guessing. (Two files on disk are still opened -- the manifest, for
# the pack name the tag is parsed against, and `bump-version.sh`, as check 1's
# tool. Neither is graded; both are named in the header.)
# Untracked files are excluded because they cannot be in the commit either way,
# and a notice that fires on every scratch file is a notice nobody reads.
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "  (uncommitted changes present — they are not graded below, and do not ship)"
fi
echo

# 1 + 2. Manifest agreement is bump-version.sh's job and it already exits
# non-zero on disagreement; all this adds is that they agree *with the tag*.
#
# The list comes out of the commit, because it describes that commit's
# manifests. The script that reads the list is copied from the checkout: it is
# the tool rather than the data, and running a `bash` script out of whichever
# commit a tag happens to name is a larger promise than this gate needs to make.
# A commit whose list the current tool cannot read fails as a disagreement,
# which is the safe direction and says `.version-bump.json is stale` when run
# by hand.
snapshot_manifests() {
  local path
  snapshot .version-bump.json || return 1
  mkdir -p "$SNAPSHOT/scripts"
  cp scripts/bump-version.sh "$SNAPSHOT/scripts/bump-version.sh" || return 1
  while IFS= read -r path; do
    # Python's default text mode writes CRLF on Windows -- the same translation
    # bump-version.sh disables with `newline="\n"` when it writes a manifest.
    # Command substitution elsewhere in this script hides it by stripping the
    # trailing `\r\n`; reading line by line does not, and `git show` was being
    # handed a path ending in a carriage return, failing, and reporting it as
    # manifests that disagree. Measured 2026-08-06 on git-bash 5.2.37(msys),
    # where both `python3` (3.12.10) and `python` (3.13.1) translate.
    snapshot "${path%$'\r'}" || return 1
  done < <("$PY" -c 'import json,sys;print("\n".join(sorted({e["path"] for e in json.load(open(sys.argv[1]))["files"]})))' \
    "$SNAPSHOT/.version-bump.json" 2>/dev/null)
}

if snapshot_manifests && bash "$SNAPSHOT/scripts/bump-version.sh" --check >/dev/null 2>&1; then
  note ok "manifests agree with each other"
# A refused path is not a disagreement, and reporting it as one sends the reader
# to `bump-version.sh --check` -- which reads the list on disk, where the path is
# fine, and passes. Nothing about the manifests was read here: the run stopped at
# the list itself. Say which path, because that is the whole of the repair.
elif [ -n "$SNAPSHOT_REFUSED" ]; then
  note FAIL ".version-bump.json names a path outside the tree: $SNAPSHOT_REFUSED"
  fail=1
else
  # Named with the commit, because the copy on disk is a different file and
  # `--check` on it may well pass while this one fails -- that gap is the bug
  # this section was rewritten for.
  note FAIL "manifests disagree at $(git rev-parse --short "$SHA") — run: bash scripts/bump-version.sh --check"
  fail=1
fi

if [ "$HEAD_MODE" -eq 1 ]; then
  # Not a check in this mode, and printed as what it is. `$VERSION` was parsed
  # back out of a tag name this script built from `$MANIFEST_VERSION`, so the
  # comparison below cannot fail here; an `ok` that cannot go the other way
  # reads as a check and is not one. It holds only because both sides now come
  # from `$SHA` -- built from the working tree and compared against the commit,
  # this would have been a real check wearing the words of an empty one.
  note ok "HEAD would ship $VERSION"
# A tag is a pack and a version, and both halves have to be the commit's own.
# The version half was the whole of this check, and the name half was compared
# against nothing: `$PLUGIN` came off the checkout, so `dovetail--v0.4.1` at a
# commit whose manifests say `otherpack` matched on the only half that was
# looked at, and checks 1, 3 and 4 have no opinion about which pack they are
# reading. Four `ok`s for a tag that installs somebody else's pack -- this
# check's own "worse than no tag", one field over.
#
# Reachable from the documented local form, `bash scripts/check-release.sh
# <tag>` from a working clone, whenever a tag is cut across a rename: the
# checkout carries the new name, the tagged commit still carries the old one.
elif [ "${MANIFEST_NAME}--v${MANIFEST_VERSION}" = "$TAG" ]; then
  note ok "the commit's manifests carry $VERSION"
# Split by which half disagrees, because they are different repairs: a wrong
# version is a bump or a retag, a wrong name is a tag cut against the wrong
# pack's history and no version will fix it.
elif [ "$MANIFEST_VERSION" != "$VERSION" ]; then
  note FAIL "tag says $VERSION, the commit's manifests say $MANIFEST_VERSION"
  fail=1
else
  note FAIL "tag names $PLUGIN, the commit's manifests say $MANIFEST_NAME — a different pack"
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
  elif [ -n "$(git tag --list "${MANIFEST_NAME}--v*")" ]; then
    note ok "$VERSION is not released yet"
  else
    # Same contract as the `gh` leg below, and it is load-bearing here rather
    # than tidy. This check reads `refs/tags/`, and an empty `refs/tags/` has
    # two readings with opposite verdicts: nothing has ever been released, or
    # this clone never fetched tags. `git clone --depth 1`, `--no-tags` and
    # actions/checkout's default all produce the second, and from inside the
    # repository the two are identical. Passing quietly on that evidence is the
    # original bug restored by environment alone, so say what could not be read.
    note SKIP "no $MANIFEST_NAME tags here — cannot tell an unreleased version from an unfetched tag"
    if [ "$STRICT" -eq 1 ]; then
      fail=1
    fi
  fi
fi

# 3. The heading format is `## v0.4.1 (2026-08-05)`. Read from the commit, where
# a missing file and a missing entry are the same answer: the release this tag
# names is undocumented in what it ships.
if snapshot RELEASE-NOTES.md && grep -q "^## v${VERSION//./\\.} " "$SNAPSHOT/RELEASE-NOTES.md"; then
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
elif [ "$HEAD_MODE" -eq 1 ]; then
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
