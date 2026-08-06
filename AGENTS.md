# AGENTS.md

> Instructions for AI agents working in or consuming this repository. Human? The
> [README](README.md) is friendlier, and has a diagram.

## What this repo is

**The source of truth for eight skills**, in one repository, plus a plugin
manifest and the scripts that install and test them. No hooks: see below for
why, and for what it would take to add one.

It did not used to be. Until `0.3.0` this was a distribution pack: eight git
submodules pinned to commits in eight repositories, which it shipped without
ever hosting. That arrangement is gone — no submodules, no pins, no `vendor/`,
and no sync step. **Edit skills here.** `docs/provenance.md` records where each
one came from and the commit it arrived at; the source repositories remain as
the archive of their own history.

The rule that replaced "never edit a vendored skill" is narrower and only
applies to a subset of files: **never edit a mirror.** Several skills carry
`references/` files that are byte-pinned copies of documents from elsewhere,
with their blob SHAs recorded in the neighbouring `README.md`. Their internal
links point at the originating layout and do not resolve here — that is
correct, and repairing one is exactly the edit that ends its byte-identity and
breaks the verification the recording exists for.

## The gate binds work in this repository

Across OpenCnid, a session that authors bytes which will enter a model's context
as instruction invokes **`prompt-engineering`** and **`hypershot-protocol`**
first — via the Skill tool, in the session doing the writing, before its first
authored byte — and authors against them. A README that agents read, a manifest
description, a script's help text: all the same act under different filenames.

**Only the invocations satisfy this.** A commit message naming the two skills, a
checklist tick, or this paragraph quoted back each describe the gate and none of
them opens it. Confirm each body actually arrived — a `Skill` call that returned
has not necessarily delivered anything. The tool reports that it launched and
the body lands as a separate message, so name a section heading you can actually
see in this session's context before citing either skill; if none is there,
invoke it again.

Both skills live in `skills/` here. Reading a copy does not open the gate;
installing it so it can be invoked does.

## Working here

- **A skill directory is exactly what should land in `~/.claude/skills/<name>/`.**
  Nothing else goes in it, and nothing it needs stays out. That includes the
  licence: `install.sh` copies the directory and nothing above it, so a skill
  leaning on the root `LICENSE.md` ships with no licence at all. Every skill here
  carries its own, which is not tidiness — for a CC-BY or Apache skill it is the
  attribution term.

  Research that is *about* a skill rather than part of it lives in
  `docs/<name>/`: findings, probe harnesses, validation records, design notes.
  If a skill's `references/` cites one of those, the link crosses out of the
  skill directory and will not survive an install — check it resolves and expect
  it to be read from the repository rather than from a user's machine.
- **`plugin.json` ships no `skills` key.** The loader auto-discovers
  `skills/*/SKILL.md`, the way `obra/superpowers` does. `install.sh` still
  enumerates every skill explicitly, and `test-skills.sh` counts its list against
  the directories on disk — so a skill added to one and not the other fails
  loudly instead of installing on one route and not the other.
- **This pack ships no hooks, and adding one is harder than it looks.** A
  skill's own `.claude-plugin/plugin.json` and `hooks/` are honoured only where
  that directory is a plugin in its own right — the `install.sh` route, where it
  lands in `~/.claude/skills/<name>/` and auto-loads as `<name>@skills-dir`.
  Loaded as components of this plugin they are ignored entirely, and fixing the
  matcher does not help: the namespaced `command_name` is a symptom, not the
  cause. Pack-wide behaviour would have to live in `hooks/hooks.json` at this
  root.

  There was such a hook until `0.4.0`, injecting an entry skill on
  `SessionStart`. It was removed because it cost about 576 tokens of every
  session to carry one fact nothing else carried — that `upsum` exists — while
  `upsum` is deliberately invisible so that it *does not* volunteer itself. The
  companion rule it also carried is held by the four skills that author prompt
  bytes, in their own bodies, at no recurring cost. Probed on CLI 2.1.214,
  Windows 10; `git log` has the mechanism if a real pack-wide need appears.

- **A skill that loads is not a skill that works.** `scripts/test-skills.sh`
  proves each body reaches the session and cannot prove the model acts on it.
  Keep that distinction in anything you write about it.
- **Claims carry their evidence state.** Where a README or a comment records a
  measurement, record when it was taken, because a bare number cannot go stale
  loudly — a character count here was wrong by 759 for as long as nobody
  re-ran the command printed three lines above it. If you verify something
  marked unverified, replace the caveat with what you observed and on which
  version. Do not quietly delete it.
- **Attribution is not decoration.** The prompt-engineering toolkit and the
  hypershot technique are Matthew Murphy's. Any document here that teaches the
  technique credits him. The `skills/<name>/` layout and the auto-discovered
  manifest follow `obra/superpowers`.

## Adding a skill

1. Create `skills/<name>/` with a `SKILL.md` whose frontmatter `name` matches the
   directory, and put a licence in it.
2. Add the same path to `SKILLS` in `scripts/install.sh` **and** in
   `scripts/test-skills.sh`.
3. Add a row to the README table, and say what it is *for* rather than what it is.
4. Run `bash scripts/test-skills.sh`. The inventory check fails if `skills/` and
   the lists disagree, and the live layer fails if the body never reaches a
   session.

Nothing needs to be published elsewhere first, and nothing needs a pin.

## Releasing

`.version-bump.json` names every place the version is written and
`scripts/bump-version.sh` moves them together; `--check` exits non-zero when they
disagree. This is load-bearing rather than tidy: the marketplace entry carries
`strict: true`, and `claude plugin tag` refuses to tag when `plugin.json` and the
enclosing marketplace entry disagree. Add an entry to `RELEASE-NOTES.md`, then
tag from a commit that is already on `main`.

Run `bash scripts/check-release.sh` before you tag and read what it says. It
asks the five things a release can get wrong — manifests agreeing, manifests
matching the tag, a notes entry, the commit being on `main` (and where that
commit is HEAD, *being* `main`), and `checks` having concluded success **on that
exact SHA** — and `.github/workflows/release.yml`
asks them again when the tag is pushed. The last one is the reason the script
exists: `checks.yml` runs on commits, so a tag can point at anything, and at
`0.4.0` it pointed at the commit before four green fixes for as long as nobody
looked.

**It has two modes, and the mode decides which commit those five are asked
about.** With no tag named — or with `--head`, which says the same thing out
loud — it grades `git rev-parse HEAD` and resolves no tag at all. Name a tag and
it grades that tag's commit. Run it after the tag exists and the bare form is
still about HEAD, which it was not until this was split: the no-tag form used to
build a tag name out of the manifests and then resolve it, so from the moment
`dovetail--v0.4.1` existed it printed "checking HEAD" and graded `313b9e4`. Any
later commit on `main` keeping that version inherited a verdict about a commit
two releases back, and `workflow_dispatch` — the run whose whole job is "is main
releasable right now?" — ran exactly that path. HEAD mode also fails when the
version it would release is already tagged elsewhere, because a version ships
once and the repair is a bump. That last one reads `refs/tags/`, so **it needs a
clone that fetched tags** — `--depth 1` and `--no-tags` produce a repository
where "never released" and "never fetched" are the same evidence, and there it
reports that it could not run rather than passing. `release.yml` keeps
`fetch-depth: 0` for that reason, and `test-release-check.sh` asserts it does.

**The modes also hold their commit to different standards, and that seam leaked
next.** Being on `main` is the whole of what a tag has to prove — a released tag
is always behind the tip — but it is not what HEAD mode asks, and
`git merge-base --is-ancestor` is satisfied by every commit `main` has ever
carried. A `workflow_dispatch` takes a ref of the operator's choosing, so a run
from a stale branch or an old tag went straight through: with HEAD at `313b9e4`
and `origin/main` at `5b36154`, `bash scripts/check-release.sh --strict --head`
reported every check `ok` and exited 0, while the commit it was missing was
`5b36154` — the fix to this gate's own injection hole. Green checks, fixes
landed afterwards, the gate blessing the state before them: the `0.4.0` shape a
third time. A run grading HEAD now requires `main`'s tip and names how far
behind HEAD is; a run grading a resolved tag keeps ancestry. **That line is
drawn on the commit, not on the mode** — they part company in the third way in,
where a tag named on the command line has no local ref: the mode is still
explicit-tag, but there is nothing to resolve, so the subject is HEAD and it
gets HEAD's standard. That is the "checking a release I am about to cut" path,
and cutting it from a stale checkout is how `0.4.0` happened. `release.yml`'s
`Fetch main` step is load-bearing for the comparison, since a stale
`origin/main` makes a stale HEAD look current.

**All five grade that commit, and none of them reads the files on disk.** The
first three used to. `check-release.sh` `cd`s to the repository root, so
manifest agreement, the version comparison and the notes entry were answered
from the working tree while ancestry and CI were answered about the resolved
SHA, and nothing required those to be one commit or the tree to be clean. With
an uncommitted bump to 0.5.0 on disk and `dovetail--v0.5.0` pointing at a commit
whose own manifests say 0.4.1 and whose notes have no 0.5.0 entry,
`bash scripts/check-release.sh --strict dovetail--v0.5.0` printed five `ok`s and
exited 0 — a tag that says one version and installs another, issued by the gate
that opens by calling that worse than no tag. The version-bearing files come out
of the commit through `git show` now, and a run with uncommitted changes says so
above the checks: that work is not graded, because it does not ship. No CI path
could reach the bug — a tag push checks the tag out, so there the tree *was* the
commit — which is how it lasted; the documented local form reached it, and HEAD
mode reached it from uncommitted edits alone.

The split refused good releases as readily as it blessed bad ones, and that half
needed no work in progress at all — only a clone that had moved on. Verifying
`dovetail--v0.4.1` from a tree carrying 0.4.2 reported `tag says 0.4.1, the
commit's manifests say 0.4.2` about `313b9e4`, whose own manifests say 0.4.1 and
always did (measured 2026-08-06 with check 2's version read pointed back at the
working tree; the wording is today's, the verdict is the one that shipped before
this was fixed). Reading the version out of the commit is what makes a published
tag verifiable from a checkout that has since moved past it — which is most
checkouts, most of the time.

`release.yml` picks the mode from `github.event_name`, not from `ref_type`: a
dispatch launched from a tag ref reports `ref_type: tag` too, so `ref_type`
cannot tell a dispatch from a push.

**The tag name is input, and the gate treats it as such.** A tag has to read
`dovetail--v<major>.<minor>.<patch>`, optionally `-<prerelease>`; anything else
exits 2 before a manifest is opened. That is narrower than `git` — `git` will
happily create `dovetail--v9.9.9$(id)`, which matches the workflow's
`dovetail--v*` trigger — and the narrowness is the point. `release.yml` hands
the tag to the script through `env: RELEASE_TAG` and expands it quoted, because
`${{ }}` inside a `run:` body substitutes into the shell source before bash
parses it, and a tag name is chosen by whoever pushes the tag.
`scripts/test-release-check.sh` holds both halves of that in place, pins which
commit each mode grades, which commits each mode will accept, and that every one
of the five checks grades that commit rather than the files on disk — in a
throwaway repository it builds with a tag, a later commit on `main`, and a
working tree bumped to a version neither commit carries, so the two answers are
different commits, the tagged one is an ancestor HEAD mode must refuse while
explicit-tag mode must not, and each remaining wrong answer is a different
version — including the pass direction, where that bump is committed and the
older tag still has to verify against it. It runs in `checks`; if you add a
workflow, it will also tell you if a `run:` body reads an attacker-nameable
context.

A published tag is a thing other people have installed. When it is wrong, the
fix is a new version, not a moved tag.
