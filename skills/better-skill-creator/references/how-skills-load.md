# How skills actually load, and what that means for how you write them

Most authoring advice about skill length is stated in lines. Lines are a proxy. The mechanisms below
are what actually operate on your file, and once you know them the size advice stops being arbitrary.

## Contents

- [The three stages of loading](#the-three-stages-of-loading)
- [The listing budget: whether Claude sees your skill at all](#the-listing-budget-whether-claude-sees-your-skill-at-all)
- [The compaction slice: which half of your skill survives](#the-compaction-slice-which-half-of-your-skill-survives)
- [Discovery and precedence](#discovery-and-precedence)
- [Bundled files](#bundled-files)
- [Sub-agents](#sub-agents)
- [Editing a skill that a plugin installed](#editing-a-skill-that-a-plugin-installed)
- [What skills are bad at](#what-skills-are-bad-at)

---

## The three stages of loading

1. **Always present**: every enabled skill's name and description sit in context from the start, so the
   model can decide what to consult. This costs tokens continuously — see the listing budget below.
2. **On invocation**: the rendered SKILL.md body enters the conversation as a single message and
   **stays there for the rest of the session**. It is not re-read. If the model needs a detail on turn
   40, it is working from the copy loaded on turn 3.
3. **On demand**: bundled files under `references/`, `scripts/`, `assets/` are *available*, not loaded.
   Nothing enters context until the model reads it, and scripts can execute without being read at all.

Stage 3 is the lever. Moving content out of SKILL.md and into `references/` costs almost nothing —
the file-reading tool caps around 25,000 tokens / 256 KiB / 2,000 lines, which no sane reference file
approaches. **Default to moving things out.**

## The listing budget: whether Claude sees your skill at all

Descriptions share a budget of roughly **1% of the context window** — about **8,000 characters** at
200k. When the total exceeds it, Claude Code drops descriptions entirely, starting with the skills you
invoke least.

This is worth taking seriously: the skills shipped in `anthropics/skills` already total around 7,790
characters. The budget is close to full before you add anything.

The practical consequence is that description length is not free, and a long "pushy" description
competes with every other skill the user has installed. Make it earn its length.

## The compaction slice: which half of your skill survives

When the conversation is compacted, Claude Code re-attaches the most recent invocation of each skill —
but only **the first ~19,900 characters** of each. All re-attached skills share a combined budget of
about 25,000 tokens, filled most-recently-invoked first, so older skills can be dropped whole.

Two things follow, and they are the whole reason this document exists.

**First, the cap is a character slice, not a semantic one.** It cuts mid-sentence. There is no "…and
the rest was omitted" marker. The model simply has a truncated document and no way to know it.

**Second, position becomes a design variable.** Only a prefix survives. Whatever sits past ~19,900
characters is present for the first invocation and then silently gone at exactly the moment a long
session most needs it.

So the check is a character count — not a token count, and not `wc -c`:

```bash
python -c "print(len(open('SKILL.md',encoding='utf-8').read()))"   # under ~19,900 survives whole
```

`wc -c` reports **bytes**. The cap slices a string in the harness, which counts characters, so for any
skill with substantial non-ASCII content `wc -c` over-reports and will send you cutting content that
was never at risk. A tokenizer is wrong in the other direction — it would tell you roughly 4,400 for a
19,900-character file, because the limit is applied before tokenization, not after.

And the ordering rule is: **put the load-bearing workflow early, and push conditional, reference, and
environment-specific material into `references/`.** A skill whose core loop sits in the back half is a
skill whose core loop disappears in long sessions.

If your file is over the cap and you cannot cut it, at least ensure the part past the cut is material
the model can re-derive or look up, never material it must have.

## Discovery and precedence

Enterprise → personal → project → bundled, by name. A same-named skill at any level silently shadows
the one below it, including bundled skills. Plugin skills are namespaced `plugin-name:skill-name` and
cannot collide.

Nested skills (v2.1.203+): a skill at `apps/web/.claude/skills/deploy` appears as `apps/web:deploy`.
Invoking the unqualified `deploy` loads the project-root one and appends a harness-generated
instruction to also invoke directory-matching variants.

Edits to a SKILL.md are picked up **live**, within the session, no restart. Changes to a plugin's
`hooks/`, `.mcp.json`, `agents/`, or `output-styles/` are not — those need `/reload-plugins`.

## Bundled files

Claude Code prepends `Base directory for this skill: <absolute path>` to every skill body. That is why
a plain relative reference works:

```markdown
For the full schema, read `references/schemas.md`.
```

You do not need `${CLAUDE_SKILL_DIR}` for ordinary reads, though it is available and expands to the
same place.

Reference files should be **navigable**, because the model decides whether to open one based on your
one-line pointer. Give each a table of contents if it runs past ~100 lines, and say in SKILL.md *when*
to read it, not merely that it exists.

## Sub-agents

Sub-agents do **not** inherit the parent's skills. A sub-agent definition's `skills:` field preloads
full skill bodies at startup; without it, the sub-agent can still discover and invoke skills through
the Skill tool. Skills with `disable-model-invocation: true` cannot be preloaded at all.

If your skill spawns sub-agents, remember they land cold. Everything the sub-agent needs must be in the
prompt you construct or in a file you point it at — it cannot see the conversation that spawned it.

## Editing a skill that a plugin installed

A skill living under `~/.claude/plugins/cache/…` is not your file. Editing it appears to work — the
change takes effect live in the session — and is then **wiped by the next plugin update**, with no
warning.

Copy it to `~/.claude/skills/<name>/` (personal) or the project's `.claude/skills/<name>/` first, which
also shadows the plugin copy. Then edit the copy, and tell the user you did and why.

## What skills are bad at

Worth knowing before you build one:

- **They don't sync across surfaces.** A skill installed in Claude Code is not available on claude.ai
  or through the API unless you install it there too, separately.
- **Too many degrades everything.** Past roughly 20–50 enabled skills, description matching gets worse
  across the board — every skill competes for the same listing budget and the same decision.
- **A skill is not re-read.** Instructions that need to apply *at a particular later moment* are
  fragile, because the model is working from a copy loaded much earlier in a much different context.
- **The API sandbox has no network access and cannot install packages.** A skill that shells out to
  `pip install` works in Claude Code and fails there.
- **Simple one-step requests may not trigger a skill at all**, however well the description matches —
  the model handles them directly. Skills earn their keep on multi-step and specialized work, which is
  also why "read this file" is a useless trigger-eval query.
