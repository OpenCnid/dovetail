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
