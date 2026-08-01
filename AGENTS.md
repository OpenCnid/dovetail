# AGENTS.md

> Instructions for AI agents working in or consuming this repository. Human? The
> [README](README.md) is friendlier, and has a diagram.

## What this repo is

A **distribution pack**, not a source of truth. It contains no skill text of its
own — eight git submodules, each pinned to a commit in its own repository, plus
a plugin manifest and two scripts.

The consequence that matters: **never edit a skill here.** A change made inside
`vendor/<name>/` is a change in a detached submodule checkout, and it will be
lost the moment a pin moves. Fix it in the source repository, then move the pin.

## The gate binds work in this repository

Across OpenCnid, a session that authors bytes which will enter a model's context
as instruction invokes **`prompt-engineering`** and **`hypershot-protocol`**
first — via the Skill tool, in the session doing the writing, before its first
authored byte — and authors against them. A README that agents read, a manifest
description, a script's help text: all the same act under different filenames.

**Only the invocations satisfy this.** A commit message naming the two skills, a
checklist tick, or this paragraph quoted back each describe the gate and none of
them opens it. Confirm each body actually arrived — a `Skill` call that returned
has not necessarily delivered anything (see `harness-traps`).

Both skills are pinned in this pack. Reading a pinned copy does not open the
gate; installing it so it can be invoked does.

## Working here

- **Moving a pin ships new instructions to everyone who installs the pack.**
  Read `git diff --submodule=log` before committing a bump. `scripts/sync.sh`
  deliberately does not commit for you.
- **The two layouts are real and are spelled out, not detected.** Six skills keep
  `SKILL.md` at their repository root; `self-play` and `subagent-composition`
  keep theirs at `.claude/skills/<name>/SKILL.md`. Both `plugin.json` and
  `install.sh` enumerate every path explicitly. If you add a skill, add its path
  to both — a globbed guess is how one of them silently stops shipping.
- **Claims in the README carry their evidence state.** The plugin install route
  is marked unverified because nobody has run it on a fresh machine. If you
  verify it, replace the caveat with what you observed and on which version. Do
  not quietly delete it.
- **Attribution is not decoration.** The prompt-engineering toolkit and the
  hypershot technique are Matthew Murphy's. Any document here that teaches the
  technique credits him.

## Adding a skill to the pack

1. Publish it as its own repository first. This pack distributes; it does not host.
2. `git submodule add https://github.com/OpenCnid/<name>.git vendor/<name>`
3. Add its `SKILL.md` directory to `skills` in `.claude-plugin/plugin.json`.
4. Add the same path to `SKILLS` in `scripts/install.sh`.
5. Add a row to the README table, and say what it is *for* rather than what it is.
6. Run `bash scripts/install.sh --dry-run` and confirm the new skill appears.

## When something here and a source repo disagree

The source wins and the pin moves. This repository never gets to be right about
a skill's contents — it only gets to be right about *which commit* of that skill
it ships.
