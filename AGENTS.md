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
   session. It exits 2 without running the live layer when it cannot confirm
   `CLAUDE_CONFIG_DIR` reached the CLI — an exit 2 is not a pass, and the usual
   cause is a POSIX shell invoking a Windows `claude.exe`, which is what
   running from WSL does.

Nothing needs to be published elsewhere first, and nothing needs a pin.

## Releasing

`.version-bump.json` names every place the version is written and
`scripts/bump-version.sh` moves them together; `--check` exits non-zero when they
disagree. This is load-bearing rather than tidy: the marketplace entry carries
`strict: true`, and `claude plugin tag` refuses to tag when `plugin.json` and the
enclosing marketplace entry disagree. Add an entry to `RELEASE-NOTES.md`, then
tag from a commit that is already on `main`.

Run `bash scripts/check-release.sh` before you tag and read what it says. It
asks the six things a release can get wrong — manifests agreeing, manifests
matching the tag, the marketplace entry installing *this* repository, a notes
entry, the commit being on `main` (and where that commit is HEAD, *being*
`main`), and `checks` having concluded success **on that exact SHA** — and
`.github/workflows/release.yml`
asks them again when the tag is pushed. The last one is the reason the script
exists: `checks.yml` runs on commits, so a tag can point at anything, and at
`0.4.0` it pointed at the commit before four green fixes for as long as nobody
looked.

**It has two modes, and the mode decides which commit those six are asked
about.** With no tag named — or with `--head`, which says the same thing out
loud — it grades `git rev-parse HEAD` and resolves no tag to find its subject.
(It does look one up, later and for one question only: whether the version HEAD
would ship is already out. That is the already-released check below, and it is
the only `refs/tags/` read HEAD mode makes.) Name a tag and
it grades that tag's commit, or **exits 2 when this clone has no ref for it**,
rather than grading HEAD under that tag's name: `git clone --no-tags` was enough
to make it report an already-published release as passing, about a commit that
was not the one asked about. That fallback served "I am about to cut this tag",
and `--head` serves it by saying so. Run it after the tag exists and the bare
form is
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
behind HEAD is; a run grading a resolved tag keeps ancestry. That line used to be
drawn on the commit rather than on the mode, because a third way in parted them:
a tag named on the command line with no local ref kept the explicit-tag mode
while the subject fell back to HEAD. Removing that fallback removed the only case
where mode and commit disagreed, so **the mode decides again**. `release.yml`'s
`Fetch main` step is load-bearing for the comparison, since a stale
`origin/main` makes a stale HEAD look current.

**Requiring the tip is only as good as the ref the tip is read from**, and that
is a way in of its own. The check prefers `refs/remotes/origin/main` and falls back
to `refs/heads/main` when there is no remote-tracking ref, and nothing asks the
remote what the local one is worth — `refs/heads/main` is whatever this clone
last fetched, plus whatever was committed on it and never pushed. In an ordinary
working clone with a local `main` a few commits behind, `bash
scripts/check-release.sh --strict --head` reported `ok HEAD is refs/heads/main`
and exited 0 about a commit the real `main` had moved past. Same verdict as the
stale dispatch above, bought with a stale ref rather than a stale HEAD, and
reached without anybody doing anything unusual: not having fetched is what a
clone is between fetches. Both modes are unsound against it — HEAD equalling a
local `main` says nothing about the remote's tip, and a local `main` carrying
unpushed commits calls a commit that is on nobody else's `main` "on `main`" —
so **the fallback is a SKIP in both**, named in the output, with the verdict
still printed beneath it and `--strict` making it fatal. That is the contract
this gate already uses for a missing `gh` and an empty `refs/tags/`: could not
read the evidence. It is not repaired with `git ls-remote`, for the reason the
unresolvable-tag branch gives — the answer would still be "fetch it and ask
again", bought with a network call. **CI is unaffected**: `release.yml` runs
`git fetch --no-tags origin +main:refs/remotes/origin/main` before either mode,
so the remote-tracking ref is always present there. This is the local and
hand-run path, which is also the one documented above as the way to verify a
published release. What it still cannot see is a *stale*
`refs/remotes/origin/main` — the same failure with the fetch skipped rather than
the ref missing, and that fetch step is what stands in front of it.

**All of them grade that commit, and none of them grades a file off the disk.**
The manifest-reading ones used to. `check-release.sh` `cd`s to the repository root, so
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

**That fix moved the version and left the pack name behind, and the same bug
came back one field over.** A tag is a name and a version. Check 2 compared the
version, and nothing compared the name at all: it came off the checkout, so
`dovetail--v8.8.8` pointing at a commit whose `plugin.json` says `otherpack`
matched on the only half anybody looked at, and checks 1, 3 and 4 have no
opinion about which pack they are reading — a version agrees with itself, a
notes entry is keyed on the version, ancestry is a question about a commit. Four
`ok`s and exit 0 for a tag that installs somebody else's pack, which is check
2's own "a tag that says 0.4.1 and installs 0.4.0" with the other field wrong.
Both halves now come out of the commit, and HEAD mode builds the name it checks
from the commit too — built from the checkout, an uncommitted rename pointed the
already-released check at a pack with no tags and turned that `FAIL` into a
`SKIP`, which without `--strict` is exit 0. Reachable the same way the version
half was: `bash scripts/check-release.sh <tag>` from a working clone, across a
rename. A tag push never reaches it, because there the checkout *is* the tag.

**Reading the files out of the commit made the commit an input, and that took a
fix of its own.** Grading a commit's manifests means asking that commit which
files they are, so `.version-bump.json` is read from `$SHA` and its `files[].path`
values become paths the gate opens. `snapshot()` built a redirection target out
of each one, and bash opens a redirection target *before* the command on the line
runs — so a listed `../x` truncated `x` outside the snapshot directory and then
`git show` failed on a path no commit carries, with `mkdir -p` having made the
directories on the way. The run printed `FAIL`, correctly, about manifests that
disagree, over a file it was never asked to touch that was already empty; nothing
in the output mentioned the write. Reproduced 2026-08-06 on Git Bash / Windows
10: a 36-byte canary outside the snapshot came back 0 bytes. A path now has to be
relative, normalised and free of `..` before anything is opened, and a list
naming one outside the tree fails check 1 as itself — `.version-bump.json` names
a path outside the tree — rather than as manifests that disagree, which would
send the reader to `bump-version.sh --check`, which reads the list on disk, where
the path is fine, and passes. The tag was the input everyone looked at; this was
the other one, and it arrived with the fix above.

**Staying inside the tree is not the whole of what a listed path reaches, and
neither is covering the floor.** `scripts/bump-version.sh` is relative,
normalised and inside the tree, so the guard passes it; it is on no required
field, so naming it narrows nothing; and it is the file check 1 *executes*. The
tool was copied into the snapshot **before** the commit's own paths were
materialised over it, so a list naming it replaced the tool with the commit's
blob and the gate ran that. Measured 2026-08-06 against the gate carrying both
the escape guard and the floor: a commit whose manifests genuinely disagree
(`plugin.json` 1.0.0, `marketplace.json` `metadata.version` 9.9.9) shipped a
two-line `bump-version.sh` that touched a file and exited 0, and the gate printed
`ok manifests agree with each other`, `Release check passed.`, exit 0, with the
touch performed. That is the promise below — not executing a `bash` script out of
whichever commit a tag names — broken by copy order rather than by intent. The
path is refused by name now, and the tool is copied in *last*, so the guarantee
does not rest on having thought of every way to spell one path.

Three more that neither mechanism can see, because none of them is about where a
path points or which fields a list covers. `git show <rev>:<tree>` exits 0 and
prints a tree's entry names, so a `RELEASE-NOTES.md/` **directory** whose one
entry is named `## v0.4.1 (2026-08-06)` satisfied check 4 and the gate exited 0
on a commit carrying no release notes; every object is confirmed a blob with `git
cat-file -t` before its bytes are read now, which also refuses the specs `git
show` reinterprets — given `<sha>:sub/../witness.txt` it fell through to its own
revision DWIM and printed HEAD at exit 0. `dirname` without `--` read
`-odd/extra.json` as `unknown option -- o`, leaving the parent unmade, so a
commit that carries the file was called a disagreement: the refusing direction,
on a path a git tree may perfectly well hold and the guard rightly allows. And
the path enumerator ran in a process substitution, whose status a `while` loop
never observes, so a dead enumerator meant zero lines and a *successful* snapshot
of nothing. The floor does not cover that last one — it parses the list itself
inside a `try`, so `{"path": 123, "field": "version"}` formats into its set while
`sorted()` raises in the enumerator; list the three required fields beside it and
the floor is satisfied while the loop reads nothing. Stub the tool to exit 0,
which a gate is entitled to assume a tool may do, and that commit printed `ok
manifests agree with each other` and exited 0. A `mktemp -d` that fails now exits
2 rather than letting `set -e` claim the release failed a check that never ran.

**Widening check 2 closed what a tag can claim and left open what the commit
behind it hands over.** A tag is a name and a version, and both are now graded
against the commit — but `plugins[0].source` in `.claude-plugin/marketplace.json`
is where a marketplace goes to *get* the pack, and it was on nobody's list.
`.version-bump.json` names version fields, so check 1 never opened it; the tag
has no source half, so check 2 had nothing to compare it against; a notes entry
is keyed on the version, ancestry is a question about a commit, and a CI run is
a question about a SHA. A commit repointing that one field at another
repository, with `name` and `version` untouched, was a whole ordinary release by
every other measure — five `ok`s and exit 0 for a tag that hands an installer
somebody else's repository under this pack's name. That is check 2's own "a tag
that says `dovetail` and installs another pack entirely", one field further
over, and the only one of these where the tag is not lying: the name and the
version really are this pack's. **Check 3 grades it, in both modes**, against
`./` exactly — the way a marketplace shipped inside the repository it lists
refers to that repository, held as narrowly as the tag shape is and for the same
reason. It is also the first of these reachable from every route, including a
tag push: the earlier two needed the tree and the commit to diverge, and this
one needs only the commit.

Its neighbour is not graded and is worth knowing about: `plugins[0].name` is
compared against nothing here either. `claude plugin tag` refuses to tag when
`plugin.json` and a `strict: true` marketplace entry disagree, so that one has a
second reader; `source` had none.

**Check 1 had a hole of a different kind: it graded whatever the commit told it
to.** `.version-bump.json` is read out of `$SHA`, which is right — that file
describes that commit's manifests — and the consequence is that the commit
chooses the syllabus it is examined on. A commit narrowing the list to
`.claude-plugin/plugin.json` alone gets `manifests agree with each other` out of
a `--check` that compared one field with itself, while `plugin.json` says one
version and the marketplace entry says another. That is exactly the
disagreement this whole apparatus exists to catch, on the `strict: true` entry
installers read, and it does not take a hostile commit — deleting a line from a
JSON list while debugging a bump, and committing it, gets there. The list still
comes from the commit, because a commit that *adds* a manifest should be graded
on it; it is now held to a **floor** of the three `<path> <field>` pairs, which
it may not drop below.

That floor is written into `check-release.sh` rather than read from the
checkout's own `.version-bump.json`, and the reason is the false-negative
direction above: the checkout's list is today's, and reading it would make every
manifest added after a release retroactively missing from that release, so a
published tag would stop verifying from a checkout that had moved on. The cost
is that adding a manifest to `.version-bump.json` needs no edit to the gate,
while removing one is meant to need one. `scripts/test-release-check.sh` builds
the narrowed commit with `bump-version.sh` itself, over the list it was just
handed, so the fixture is the reachable shape rather than a hand-built
disagreement.

**Two reads from the checkout survive, deliberately.** The pack name is read
there once, before any commit is resolved, because parsing the tag needs a name
and there is nothing else to take one from yet — that is a shape test against
this pack's convention, and the *name check* is check 2, which reads the commit.
And `scripts/bump-version.sh` is copied from the checkout rather than run out of
whichever commit a tag names, because executing a `bash` script from an
arbitrary tagged commit is a larger promise than this gate needs to make. The
cost is that check 1's verdict about a fixed commit is a function of the
checkout's tooling: refactor `bump-version.sh` so it resolves its root
differently, and check 1 silently grades the working tree again. Nothing catches
that today. So the accurate statement is that no file the checks *grade* is read
from disk — not that the disk is never opened.

**`release.yml` cannot prevent a bad tag, and the gap this closes is that
nothing said so.** It runs on `push: tags`, so the ref is on the remote before
the run exists — a dependency range resolving `dovetail--v*`, or a marketplace
source pinned with `#ref`, can fetch it while the checks are still starting.
That workflow audits, and no rearrangement inside it becomes prevention, because
the event it waits for is the publication. It keeps `contents: read` for that
reason: write there would buy the ability to delete a tag somebody may already
have installed, which is the repair this repository refuses.

So the tag is made by `.github/workflows/release-publish.yml`, which nothing but
a person can start. It takes a commit SHA, the version that commit ships, and a
confirmation defaulting to `dry-run`, and between the naming and the creating
sit the same six checks. `scripts/publish-release.sh` is where the order is
held: the gate is a call inside it rather than a step beside it, because a step
can be reordered and a function cannot be persuaded to return before it is
called. Run by hand with `--dry-run` it writes nothing and reports what would
ship, so the pre-flight survives; `bash scripts/check-release.sh --head` still
answers the narrower question and neither replaces the other.

**The version is typed twice on purpose.** Every other fact is read out of the
commit, so a dispatch naming the wrong commit gets a coherent answer about the
wrong release — every check passes, because they all describe whatever was
named. `RELEASE_VERSION` is the one assertion the operator makes that the commit
can contradict. The SHA is forty characters and never a ref name for the same
reason: `main` names whatever `main` is at the moment each command runs, and
there are several such moments here, one of them an approval of unbounded
length.

**The commit released has to be `origin/main`'s tip, not a commit somewhere in
its history.** That is HEAD mode's standard, inherited rather than replaced with
a third: releasing an ancestor is the `0.4.0` shape with the operator's blessing
attached. It is a real restriction — a candidate approved while it was the tip
is refused once `main` moves, and the repair is to re-dispatch rather than to
loosen the check. It also buys something unrelated to correctness: a commit that
is the default branch cannot differ from it under `.github/workflows/`, which is
the documented condition under which `GITHUB_TOKEN` is refused permission to
create a release at all.

**Two jobs, split on what they may do rather than on what they check.**
`validate` holds `contents: read` and `actions: read` — the second because
check 6 is an Actions API call the default token cannot otherwise make — and
runs the script in the mode that cannot write. `publish` holds `contents:
write`, which creates the tag object, the ref and the release, and buys nothing
else. A permission granted for the last step of a run is granted for all of it,
so keeping the read-only answer in a job that never held the write is what makes
"it passed" separable from "it published". `publish` re-runs every check instead
of trusting `validate`, because the approval between them is exactly when `main`
can move.

**The tag is annotated, in three calls, ordered for what a failure leaves
behind.** Every tag this pack has published is annotated and `check-release.sh`
resolves through the tag object with `git rev-list -n 1`, so a lightweight ref
would be a quiet change to what the gate reads. The tag object is unreferenced
until the ref points at it, the ref is the moment the release becomes fetchable,
and the release object is last, because announcing a tag that does not exist is
worse than a tag nobody announced.

**None of that stops a tag pushed by hand, and nothing committed here can.**
That is a GitHub tag ruleset, configured in settings.
`.github/rulesets/dovetail-release-tags.json` carries it as a reviewable file —
target `tag`, enforcement `active`, `refs/tags/dovetail--v*`, and the `creation`,
`update`, `deletion` and `non_fast_forward` rules — but GitHub imports that file
rather than reading it, so the two stay in step only while somebody re-imports
after a change. It ships with an empty bypass list, which fails closed: until the
publishing identity is added there, nothing can cut a release tag, this workflow
included. `scripts/test-release-publish.sh` asserts the file still names this
pack, because a rename would otherwise leave a ruleset guarding a namespace
nothing publishes into — indistinguishable from a working one until the release
that needs it.

What that ruleset does *not* cover is whether anything vouches for the tag once
it exists. Every tag this pack has published is annotated and none is signed
(measured 2026-08-06 across `dovetail--v0.2.0` … `dovetail--v0.4.1`), and the
publish route cannot sign one, because `gh api POST /git/tags` has no signing
input. `docs/release-integrity.md` carries that layer — the four rules this
ruleset must keep, why `required_signatures` is deliberately absent until
signing works, and `scripts/verify-release.sh`, which reports what a received
tag establishes without claiming what it cannot.

**The identity in that bypass list should be a GitHub App, and not as a
preference.** `GITHUB_TOKEN` is an App installation token, but whether the
Actions app can be granted ruleset bypass is documented neither way, so the
workflow does not depend on it: set `RELEASE_BOT_APP_ID` and the matching key and
it publishes as an App that can be named in a bypass list, leave them unset and
it publishes as `github.token`, which is correct until the ruleset is active and
cannot be after. One documented consequence arrives with the App rather than
despite it — a tag pushed with `GITHUB_TOKEN` does not trigger workflows that run
on `push`, so `release.yml` would stay silent about it, while an App token is not
suppressed that way and the tag is audited on arrival by the path that grades a
tag rather than a commit.

**That key is an environment secret, and it is the part most easily got wrong.**
`workflow_dispatch` takes a ref, and the workflow that runs is the copy on that
ref — so the gate is only the gate for a dispatch from a ref carrying this
version of the file. Checking out the named SHA protects the scripts, not the
file deciding which scripts run. A repository secret is readable from a workflow
on any ref, so a branch carrying a gutted copy of `release-publish.yml` could
mint the same token; an environment secret is reachable only from a job naming
that environment, and only from a ref that environment's deployment rule allows.
Set it to `main`. Required reviewers on the same environment are what make a
publish something a second person agrees to.

**What this does not cover, said here rather than found later.** The install
route the README documents adds the marketplace with no `#ref`, and a marketplace
source of `./` resolves the default branch, so that route receives `main`'s tip
and consults no tag at all. Measured 2026-08-06: `dovetail--v0.4.1` points at
`313b9e4`, `origin/main` is at `c0ee549` thirteen commits later, and both carry
`"version": "0.4.1"` — so a consumer following the README today receives the
newer tree under the graded version's name. Everything above governs the routes
that do resolve tags, a dependency range against `dovetail--v*` and a source
pinned with `#ref`. Nothing yet governs what `main` ships to everyone else.

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
of the six checks grades that commit rather than the files on disk — in a
throwaway repository it builds with a tag, a later commit on `main`, and a
working tree bumped to a version neither commit carries, so the two answers are
different commits, the tagged one is an ancestor HEAD mode must refuse while
explicit-tag mode must not, and each remaining wrong answer is a different
version — including the pass direction, where that bump is committed and the
older tag still has to verify against it. It covers the commit-as-input half in
a second throwaway repository, whose committed `.version-bump.json` lists a path
escaping the snapshot: the gate has to refuse it *and* leave a canary outside the
snapshot byte-identical, with the canary fired first so neither assertion can
pass vacuously. That section names `$TMPDIR` rather than guessing where `..`
lands. It runs in `checks`; if you add a workflow, it will also tell you if a
`run:` body reads an attacker-nameable context.

## The branch protecting the gate

This whole section argues one thing: green checks are worth nothing unless they
ran on the commit in question. That argument does not stop at the release gate.
It applies to `main` itself, and `main` was not holding to it.

Required checks on `main` are `ubuntu-latest` and `windows-latest`, and until
2026-08-07 they carried `strict: false` — checks had to be green, but the branch
did not have to be *current*. A `pull_request` run checks out the branch merged
into `main` as of when it ran, so the moment another PR lands, that result
describes a combination that no longer exists, and nothing re-runs it. Measured
on this repository the night it bit: #31's checks went green at 01:16 against
`main` at `562fe1e` and the merge button stayed lit at 01:30. Nothing landed in
between, so nothing broke — the protection was sound by luck, which is the state
this file exists to name rather than to enjoy. #29 and #30 had already landed
under #31 while it was open, so the window was not hypothetical that night.

The push-to-`main` run is the backstop, and it is the wrong shape: it reports
after the thing has landed, which is the `0.4.0` failure with a smaller blast
radius rather than a different structure.

So `strict: true`. A branch merges only when it is up to date, which means the
checks that authorise a merge ran on the tree the merge produces. The cost is
real and worth stating: when two PRs touch one file, the second one updates and
waits for a rerun, and merges serialise. `allow_auto_merge` is off, so that wait
is a manual loop; turning it on is the obvious relief if the serialisation
starts to hurt, and `gh pr merge --auto` is what would use it.

`enforce_admins: true` alongside it, because a required check every admin can
wave through is a required check for everybody except the people merging fastest,
and this repository is mostly merged by one of them.

Squash is the only merge method now. That is not only tidiness: rebase merges
put each commit on `main` under its own subject with no PR number, so `(#NN)` was
present on some commits and absent on others for reasons unrelated to how they
were reviewed. #29 and #30 both went through review and neither is suffixed, and
that inconsistency was read here — in this session, out loud — as evidence they
had bypassed review entirely. A convention that is only sometimes true is worse
than none, because it invites exactly that inference. Every commit on `main`
carries its PR number now, and `gh api repos/{owner}/{repo}/commits/<sha>/pulls`
is the query that actually answers the question.

A published tag is a thing other people have installed. When it is wrong, the
fix is a new version, not a moved tag.
