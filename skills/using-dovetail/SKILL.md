---
name: using-dovetail
description: How the eight dovetail skills compose — the companion rule that binds prompt-authoring work, and the two skills the model cannot see for itself. Loaded into every session by the pack's SessionStart hook; also invocable directly.
---

# Using dovetail

Eight skills that hold together by shape. Six of them you can reach with the
Skill tool. Two you cannot see at all, and this section is the only notice you
get that they exist.

## The companion rule

**Authoring bytes that will enter a model's context as instruction means
invoking `prompt-engineering` and `hypershot-protocol` first — both, via the
Skill tool, before the first authored byte.**

That covers a sub-agent prompt, a judge prompt, an agent definition, a skill
body, an output schema, a README another agent will read. Same act under
different filenames. Compose the sub-agent or the judge panel *after* the two
companions are loaded, not before — `subagent-composition` and
`judge-composition` both assume they are already in context.

Confirm each body arrived. A `Skill` call that returned has not necessarily
delivered anything: the tool reports that it launched, and the body lands as a
separate message. Name a section heading you can actually see before citing
either skill; if none is there, invoke it again.

## The two you cannot see

`spark-steering` and `upsum` carry `disable-model-invocation: true`. They are
absent from the skill list, so you cannot invoke them and asking you to will not
work. **The user types `/spark-steering` or `/upsum`.** Suggest it when it fits —
`spark-steering` before installing a fix that charges rent, `upsum` when a
session holds something the next one will need — and let them make the call.

## What the rest are for

| skill | reach for it when |
|---|---|
| `prompt-engineering` | any prompt, template, or schema is being written |
| `hypershot-protocol` | an example would prime content along with structure |
| `subagent-composition` | delegating, or a sub-agent came back thin |
| `judge-composition` | a claim needs adjudicating by someone without a stake |
| `self-play` | "does this actually hold up?" is open and your own read is not evidence |
| `better-skill-creator` | a repeated workflow should become a skill, or one misbehaves |
