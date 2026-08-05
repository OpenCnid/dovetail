# Probe methodology: verifying claims about a system you cannot read

How to establish what an agent runtime actually does, when the docs are
incomplete and the runtime is a black box that will happily produce
confident-looking output either way.

This document exists because the probe behind [FINDINGS.md](FINDINGS.md)
produced **two fully-formed wrong conclusions** before controls caught them.
Both were plausible. Both would have shipped. The method is the only reason
they didn't.

---

## The core problem

Asking a model what is in its own context is not a measurement. A model asked
"do you have skill X loaded?" will answer from disposition as readily as from
observation, and both answers look identical. Worse, the failure is
*asymmetric*: an "absent" reply is consistent with the feature being broken
**and** with the probe being unable to perceive the feature. You cannot tell
these apart from the reply alone.

So a bare probe answers a different question than the one you asked. Every
technique below exists to close that gap.

---

## Technique 1: plant a canary the model cannot guess

Ask for a token that can only be *possessed*, never inferred.

A good canary is a distinctive proper noun buried deep in the target content —
something with essentially zero probability of being produced by a model that
lacks the content. We used a private engine name from the middle of a skill
body, plus the verbatim title of one of its numbered rules. The second is a
useful cross-check: recovering both, exactly, rules out a lucky paraphrase.

A **bad** canary is anything the model could reconstruct from context, the task
framing, or general knowledge. If the probe could pass by being clever, it
measures cleverness.

Never put the canary's value in the spawning prompt. It must reach the agent
only through the channel under test.

---

## Technique 2: close the side channels

If the agent can reach the content another way, a positive result proves
nothing.

Our probes declared `tools: WebSearch` — no `Read`, no `Bash`, no `Grep`, and
critically no `Skill` tool — so no agent could fetch the skill off disk or
invoke it directly. The prompt also instructed no tool use at all.

Then make the probe **report its own tool list**. This turns an assumption into
an observation: `TOOLS: WebSearch` in the output confirmed the allowlist held.
Had `tools:` failed to parse, the agents would have inherited everything and the
result would have been visible in the same line that carried the finding. One
probe, two verified facts.

---

## Technique 3: a negative control, always

Run an identical agent with the field under test **removed**.

This is the cheapest insurance in the entire method and it paid immediately.

**What happened:** all four probes failed with `Agent type 'x' not found` —
including the control, whose frontmatter was unambiguously valid. A syntax
problem cannot explain a control failing. That single fact redirected the
diagnosis from "my YAML is malformed" to "agent registration is not immediate,"
which turned out to be [finding §6](FINDINGS.md#6--agent-registration-lags-the-filesystem--both-ways).

Without the control, the obvious next move was to start "fixing" correct YAML —
editing working files, in pursuit of a problem that did not exist, and very
likely concluding that some arbitrary spelling was the one that "worked."

---

## Technique 4: a positive control for the probe itself

Prove the probe can detect *something* through the same channel, or "absent"
means nothing.

We planted a second canary — `MARMOSET-7731` — in a `CLAUDE.md` in the working
directory, and had the same agent report both tokens in one reply:

```
CLAUDEMD_CANARY: MARMOSET-7731
SKILL_CANARY: absent
```

Now `absent` is *informative*. The probe demonstrably perceives injected
context, so the skill genuinely was not there. Without this line, the identical
output supports the opposite reading — that the probe is simply blind and every
"absent" is noise.

Put both controls in the **same reply** where you can. Same agent, same run,
same context window: it removes run-to-run variance as an explanation.

---

## Technique 5: test the faithful path, not the convenient one

**This is where the second wrong conclusion came from, and it is the subtlest.**

`claude --agent {name}` looked like an ideal test rig: the session *is* the
agent, no nesting, one command. It returned `SKILL_CANARY: absent` across every
syntax variant. Combined with a validated positive control, that is a clean,
well-controlled, methodologically sound negative result.

It was also wrong. `--agent` is a different code path from sub-agent spawn and
silently drops `skills:`. Running the real path — spawning through the `Agent`
tool — recovered the canary immediately, in every syntax.

The lesson generalizes past this bug: **a controlled experiment on the wrong
code path is still a wrong answer.** Controls protect against noise and
blindness; they do not protect against measuring the wrong thing. Ask what
production actually executes, and execute that, even when it is more awkward to
drive.

The tell was available in advance and we missed it: the claim was about
*sub-agents*, and the rig never spawned one.

---

## Technique 6: vary exactly one thing

Five agents, differing by a single field:

| agent | varies |
|---|---|
| `probe-skills-bare` | `skills:` as bare scalar |
| `probe-skills-flow` | `skills:` as `[flow list]` |
| `probe-skills-block` | `skills:` as block sequence |
| `probe-skills-control` | `skills:` **absent** |
| `probe-context-detect` | both canaries, one reply |

Identical bodies, identical tools, identical model, identical prompt. When
results diverge, exactly one thing can explain it. When they *don't* diverge —
as when all four returned `absent` under `--agent` — that uniformity is itself
evidence, and it should prompt the question *"what do all five share that might
be the actual variable?"* That question is what surfaces a wrong-code-path
error.

Pin the model (`model: haiku`) and cap turns (`maxTurns: 2`). Cheap, fast, and
it keeps a confused agent from wandering into a workaround that contaminates
the result.

---

## Technique 7: constrain the output shape

Give the probe a rigid return frame:

```
TOOLS: <comma-separated names of every tool available to you, or "none">
SKILLS_PRELOADED: <names of any skill content present in your context, or "absent">
CANARY: <the distinctive proper noun …, or "absent">
```

Three properties earn their keep. Results become **diffable** across runs.
The literal sentinel `"absent"` gives the model an explicit non-answer, so it
does not reach for a plausible guess to fill the slot. And the framing —
*report only what you can observe; a thing you cannot find is "absent," never a
best guess* — is instruction the probe can actually follow, unlike "don't
hallucinate."

---

## The checklist

Before believing a probe result:

1. **Canary unguessable?** Could the model produce it without the content?
2. **Side channels closed?** Could it fetch the answer with a tool?
3. **Negative control?** Does the field-absent case behave differently?
4. **Positive control?** Has the probe detected *anything* through this channel?
5. **Faithful path?** Does this rig exercise what production runs?
6. **One variable?** Can anything else explain the difference?
7. **Uniform results interrogated?** If everything agrees, is the variable real?

Items 3 and 4 caught the two wrong answers here. Item 5 is the one with no
safety net — no control detects it, because the experiment is internally valid
and simply aimed at the wrong target. It has to be checked deliberately.

---

## Running it

```bash
bash probes/run-probes.sh
```

Plants both canaries, installs the five probe agents, runs each through the
sub-agent spawn path, prints the result matrix, and removes everything it
created. Findings and version pin: [FINDINGS.md](FINDINGS.md).
