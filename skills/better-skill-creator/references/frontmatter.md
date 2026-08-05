# Frontmatter reference

## Contents

- [The thing that trips everyone up](#the-thing-that-trips-everyone-up)
- [Which target are you writing for?](#which-target-are-you-writing-for)
- [The two fields that matter](#the-two-fields-that-matter)
- [Controlling who can invoke a skill](#controlling-who-can-invoke-a-skill)
- [allowed-tools: a grant, not a restriction](#allowed-tools-a-grant-not-a-restriction)
- [Running a skill as a sub-agent](#running-a-skill-as-a-sub-agent)
- [YAML hazards that cost real time](#yaml-hazards-that-cost-real-time)
- [Full key reference](#full-key-reference)

---

## The thing that trips everyone up

There is no single "the frontmatter spec." There are at least three, they disagree, and a skill that is
valid under one can be rejected by another.

This matters because the disagreement is silent in both directions. Claude Code ignores keys it does
not recognize, so a typo like `disabke-model-invocation:` loads fine and simply does nothing — the
skill stays auto-invocable and you never find out. Meanwhile a strict portable validator will reject
`user-invocable: true` as an illegal key even though Claude Code documents and honors it.

So the first question is always *which target*, and `scripts/quick_validate.py` takes `--target` for
exactly this reason.

## Which target are you writing for?

| Target | Recognized keys | Unknown keys | Description cap | `name` ≠ directory |
|---|---|---|---|---|
| `claude-code` (default) | 31 documented keys | **ignored**, warning only | 1024 **warning**; 1536 combined with `when_to_use` is a hard limit | warning |
| `portable` (agentskills.io) | 6-key portable set | error | 1024 error | error |
| `claude-ai` | portable set + `dependencies` | error | **200** error | error |

Two of those are softer than you might expect, and the reason is the same in both cases: Claude Code
doesn't enforce them. It documents a 1,536-character combined truncation and never rejects on length,
and it takes the invocation name from the *directory*, treating frontmatter `name` as display-only. So
on that target they are warnings about portability, not defects. They become errors the moment you
aim at an upload surface — and `package_skill` refuses a name mismatch at every target, because the
archive's single top-level directory depends on it.

The 200-character claude.ai cap is the one that surprises people: most skills exceed it, so a skill
authored for Claude Code generally needs a shortened description before it will upload.

`compatibility` is in the portable set and is **not** in Claude Code's schema at all.

```bash
python -m scripts.quick_validate <skill-dir> --target claude-code
python -m scripts.quick_validate <skill-dir> --target portable
```

Every message names the target that produced it, so a rejection tells you whether you have a real
problem or a portability one.

## The two fields that matter

**`name`** — kebab-case, ≤64 characters, and it should **equal the directory name**. Claude Code takes
the invocation name from the directory, so a mismatch is the kind of bug where everything looks right
and the skill answers to a name you did not intend; the Skills API, claude.ai, and the packager all
require them to agree outright.

Characters outside `a-z0-9-` that are still valid identifier characters — a Japanese or Cyrillic
name — are accepted, with a portability warning. The reference validator allows them; some upload
paths, shells, and filesystems normalize or transliterate non-ASCII directory names, and a slash
command built from one can be awkward to type. Locally installed, it costs nothing.

**`description`** — this is the entire mechanism by which Claude decides to consult your skill.
Nothing else in the file participates in that decision. It is worth more attention than the rest of
the frontmatter combined, which is why `references/description-optimization.md` exists.

If you omit `description`, Claude Code falls back to the first paragraph of your body. That is almost
never what you want, and it is a quiet failure — the skill loads, and simply doesn't trigger.

**`when_to_use`** is a separate optional field that gets joined to the description as
`"<description> - <when_to_use>"` and shares the 1,536-character budget with it. Useful when the
"what it does" and "when to reach for it" halves are genuinely different sentences.

## Controlling who can invoke a skill

```yaml
disable-model-invocation: true   # only the user can invoke it, by name
user-invocable: false            # only the model can invoke it
```

`disable-model-invocation: true` removes **both the name and the description** from the model's
context. That is the point — it buys back context budget for a skill only you will ever type. Two
consequences worth knowing before you set it:

- The skill cannot be preloaded into a sub-agent, because preloading draws from the same set the model
  can invoke.
- Any trigger-rate evaluation of that skill scores 0 by construction. There is nothing to trigger.

Boolean fields accept `yes`/`no`/`on`/`off`/`1`/`0` in any case as well as `true`/`false`
(Claude Code v2.1.218+).

## `allowed-tools`: a grant, not a restriction

This one is widely misread. `allowed-tools` **pre-approves** the listed tools for the turn that invokes
the skill, so Claude can use them without prompting. It does **not** restrict anything — every other
tool remains callable, and your normal permission settings still govern them.

```yaml
allowed-tools: Bash(git add *), Bash(git commit *)
```

The grant clears when the user sends their next message; re-invoking the skill re-applies it. Note that
the Agent SDK ignores this field entirely — SDK tool access is controlled by the SDK's own
`allowedTools` option. Same file, different behavior by surface.

## Running a skill as a sub-agent

```yaml
context: fork
```

The skill runs as a forked background sub-agent with the SKILL.md body as its prompt. Only the literal
value `fork` is honored; anything else silently runs inline, which looks like the feature not working.

From the other direction, a sub-agent definition's `skills:` field preloads full skill bodies at
startup. It controls *preloading*, not *access* — without it a sub-agent can still discover and invoke
skills through the Skill tool.

## YAML hazards that cost real time

**Quote your description.** This is the single most common way a skill fails to load:

```yaml
description: Formats reports. Triggers include: dashboards, charts   # BREAKS
description: "Formats reports. Triggers include: dashboards, charts" # fine
```

An unquoted colon-space makes YAML parse the value as a nested mapping. Also hazardous unquoted:
a leading `@`, `%`, `&`, `*`, `!`, or backtick; a `#` anywhere (starts a comment); and a value that
looks like a number, a date, or `yes`/`no`/`on`/`off` when you meant a string.

**The failure is worse than a normal error.** Malformed frontmatter can load the *body* with empty
metadata — so `/your-skill` works when you test it by hand, while auto-triggering silently never fires,
because there is no description to match against. You will conclude the description is bad and go tune
it. Run the validator instead; it takes a second.

**Also:** a UTF-8 BOM makes the frontmatter undetectable ("No YAML frontmatter found"). Duplicate keys
are silently resolved last-wins by the parser.

## Full key reference

Claude Code recognizes 31 top-level keys. These are the ones worth knowing; the rest are situational
and documented at `code.claude.com/docs/en/skills`.

| Key | Type | Notes |
|---|---|---|
| `name` | string | kebab-case, ≤64; should equal directory name (required by upload surfaces and the packager) |
| `description` | string | the triggering mechanism; quote it |
| `when_to_use` | string | joined to description; shares the 1536 budget |
| `license` | string | SPDX identifier |
| `allowed-tools` | string | per-turn grant, not a restriction |
| `disable-model-invocation` | bool | hides name *and* description from context |
| `user-invocable` | bool | `false` = model-only |
| `context` | string | `fork` runs the skill as a background sub-agent |
| `metadata` | map | must be a mapping; scalars and lists are rejected |
| `compatibility` | string | portable target only; not in Claude Code's schema |
| `dependencies` | — | claude.ai target only |

**Unknown keys are ignored by Claude Code, but wrong *types* still fail.** That asymmetry is worth
internalizing: a misspelled key name is invisible, while `metadata: "a string"` is a hard error.

## Path templating

Inside the body, `${CLAUDE_SKILL_DIR}` and `${CLAUDE_PROJECT_DIR}` expand to absolute paths.
`${CLAUDE_SKILL_DIR}` also expands inside `allowed-tools` Bash rules, but only on Claude Code v2.1.129+
— on older versions the rule stays a literal string and silently never matches, so the command keeps
prompting and it looks like the grant is broken.

You often don't need either. Claude Code prepends `Base directory for this skill: <absolute path>` to
every skill body before the model sees it, so a plain relative reference like `references/schemas.md`
resolves correctly regardless of the working directory.

## Dynamic context

```markdown
Current branch: !`git branch --show-current`
```

Shell commands in `` !`...` `` run **before** the body reaches Claude, and their output replaces the
placeholder. Substitution is single-pass — output is not rescanned, so a command cannot emit another
placeholder.

Handle with care: if the command fails, **the entire skill invocation is silently aborted** — exit 0,
zero turns, empty output, nothing in `--debug`. To anyone watching it reads as "the skill didn't
trigger." Cowork disables the mechanism entirely. Use it only where a failure is impossible or
harmless, and prefer having the model run the command itself when you need to react to failure.
