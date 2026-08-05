# AGENTS.md

> Instructions for AI agents working in or consuming this repository. Human? The
> [README](README.md) is friendlier, and has a diagram.

## What this repo is

A **distribution pack**, not a source of truth. Eight git submodules, each
pinned to a commit in its own repository, plus a plugin manifest, two scripts,
a `SessionStart` hook, and exactly one skill of its own.

The consequence that matters: **never edit a vendored skill here.** A change
made inside `vendor/<name>/` is a change in a detached submodule checkout, and
it will be lost the moment a pin moves. Fix it in the source repository, then
move the pin.

**The one exception is `skills/using-dovetail/`,** and it is a real one. It
carries the companion rule and the notice that `spark-steering` and `upsum` are
invisible to the model — content that is *about the pack* rather than about any
one skill, and that no source repository is in a position to write, because none
of them knows it will be packaged as `dovetail`. It is authored here, under the
gate below, like any other instruction bytes.

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

Both skills are pinned in this pack. Reading a pinned copy does not open the
gate; installing it so it can be invoked does.

## Working here

- **Moving a pin ships new instructions to everyone who installs the pack.**
  Read `git diff --submodule=log` before committing a bump. `scripts/sync.sh`
  deliberately does not commit for you.
- **The layout rule, and its one exception.** A skill directory is *exactly what
  should land in `~/.claude/skills/<name>/`*. Seven sources therefore keep the
  skill at `.claude/skills/<name>/`, so copying that directory carries the skill
  and nothing else — no README, no licence, no `.git`. `better-skill-creator` is
  the exception and it is a real one: its `scripts/`, `references/`, `agents/`
  and `tests/` are part of the skill, so its whole repository *is* the skill
  directory.

  Both `plugin.json` and `install.sh` enumerate every path explicitly. If you add
  a skill, add its path to both — a glob that silently matches nothing installs a
  hollow pack that looks fine.
- **A skill's own hooks do not fire on the plugin route.** A nested
  `.claude-plugin/plugin.json` is honoured only where the directory is a plugin
  in its own right — that is the `install.sh` route, where each skill lands in
  `~/.claude/skills/<name>/` and auto-loads as `<name>@skills-dir`. Mounted as
  components of this pack, those manifests are ignored and their hooks never
  register. Fixing the matcher does not help; the namespaced `command_name` is a
  symptom, not the cause.

  So **pack-wide behaviour belongs in `hooks/hooks.json` at this root**, which is
  where the `SessionStart` injection of `using-dovetail` lives. Probed
  arm-by-arm on CLI 2.1.214, Windows 10, with negative controls; the pack route
  was exercised through both `--plugin-dir` and a real `marketplace add` +
  `install`. What was *not* checked is whether the injected context changes what
  the model then invokes — that needs an authenticated session, and the scratch
  config used for the probes is not logged in.
- **Claims in the README carry their evidence state.** The plugin install route
  is marked unverified because nobody has run it on a fresh machine. If you
  verify it, replace the caveat with what you observed and on which version. Do
  not quietly delete it.
- **Attribution is not decoration.** The prompt-engineering toolkit and the
  hypershot technique are Matthew Murphy's. Any document here that teaches the
  technique credits him.

## Adding a skill to the pack

1. Publish it as its own repository first. This pack distributes; it does not
   host. The sole exception is a skill *about the pack itself*, which no source
   repository can write — see `using-dovetail` above. If you think you have a
   second one, you probably have a skill that belongs upstream.
2. `git submodule add https://github.com/OpenCnid/<name>.git vendor/<name>`
3. Add its `SKILL.md` directory to `skills` in `.claude-plugin/plugin.json`.
4. Add the same path to `SKILLS` in `scripts/install.sh`.
5. Add a row to the README table, and say what it is *for* rather than what it is.
6. Run `bash scripts/install.sh --dry-run` and confirm the new skill appears.

## When something here and a source repo disagree

The source wins and the pin moves. This repository never gets to be right about
a skill's contents — it only gets to be right about *which commit* of that skill
it ships.
