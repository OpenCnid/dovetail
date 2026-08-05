# probes/

A channel audit for the clean room.

```bash
bash probes/run-probes.sh
```

## What it asks

Isolation is this skill's whole mechanism. It rests on a claim about the
sub-agent boundary — that your conversation, reasoning, stake, and prediction do
not cross into a player unless you put them there — and that claim is inherited
from `subagent-composition` rather than established here.

So the question is not *does isolation work in principle*. It is: **which
channels reach a player that the composer did not deliberately open?** A channel
nobody audits is exactly the leak discipline 1 warns about — the one that has
already been cleaned out of the task text and is sitting somewhere else.

This is a named-failure-mode probe (leak). It holds no null arm and asks nothing
about whether the skill helps.

## What's here

| file | role |
|---|---|
| `agents/probe-channel-control.md` | baseline: no `skills:`, no body canary |
| `agents/probe-channel-self.md` | **format control** — carries a canary in its own body |
| `agents/probe-channel-skill.md` | **positive control** — the nearest *foreign* channel, declared in `skills:` |
| `fixtures/canary-skill/SKILL.md` | the content being smuggled across the boundary |
| `run-probes.sh` | install, run five arms, print output beside expectations, clean up |

Three agent files, five arms. Two arms reuse the control agent and vary the
**invocation** instead of the file — one has the parent preload the canary
skill, one runs in a directory with no `CLAUDE.md`. Shipping a duplicate file
that differs only in its `name` invites the two copies to drift; varying the
invocation keeps a single definition honest.

All three agents are pinned to `model: haiku` with `maxTurns: 2` — cheap, fast,
and too constrained to wander into a workaround that would contaminate the
result.

## Why these are not in `.claude/agents/`

They would auto-register for anyone cloning this repository and clutter the
agent list with diagnostics nobody asked for. `run-probes.sh` installs them,
runs them, and removes them. It refuses to start if an agent of the same name
already exists, and cleans up on interrupt.

## Reading the matrix

The controls are not ceremony; they are the only reason the result means
anything. This is the skill's own discipline 6 turned on the skill.

- **The positive control (arm C) reports its skill canary absent** → the
  instrument cannot detect inheritance through a channel the ledger says is
  open. Every "absent" in every arm is then noise rather than evidence. *A null
  result is meaningless until the experiment has demonstrated it can produce a
  positive one.*

  **Arm C is the positive control and arm B is not.** Arm B plants its canary in
  the agent's *own body* — a channel at zero distance along the manipulated axis,
  which is "which foreign channel reaches a player." It never crosses a boundary
  at all, so it can only show that the return frame is being honoured. The
  skill's own discipline 6 requires a control to **span** the axis rather than
  hug the candidate, and an earlier version of this harness called arm B the
  positive control in violation of exactly that rule.
- **The format control (arm B) reports its body canary absent** → the agent is
  not following its return frame, and every row is unreadable for a reason that
  has nothing to do with the boundary.
- **The negative control (arm E) recovers the `CLAUDE.md` canary** → a side
  channel is open, or the token is guessable. The probe is contaminated. Fix the
  probe, not the finding.
- **Arm D recovers the skill canary** → skill content the *parent* loaded
  crossed into the player. That contradicts the ledger this skill's mechanism
  rests on. Re-run it, then report it loudly.
- **Arms A–D recover the `CLAUDE.md` canary and arm E does not** → `CLAUDE.md`
  is an open channel into every player, and a self-play run must audit it for
  the hypothesis alongside the player prompts.

## Adding a probe

Copy an existing agent, change **one** field, keep the return frame identical. A
probe that varies two things at once cannot attribute its own result.

A canary must be **unguessable rather than merely obscure** — a token a model
could reconstruct from context measures cleverness, not inheritance. Never put a
canary's value in the spawning prompt; it must reach the agent only through the
channel under test. Partial recall counts as absent, because reconstructing half
an unguessable token is not inheritance.

## Known confound in arm D

Arm D varies **three** things from arm A, not one: the parent's allowed-tool set
(`Agent` → `Agent,Skill`), the parent's prompt text (which now names
`probe-canary-skill`), and the parent's loaded-skill state. Two are enabling
conditions for the third, but the parent prompt now carries the skill's name,
which arm A's never did.

This only bites on a **positive** arm-D result: if the skill canary came back,
the harness could not distinguish "parent-loaded skill content crossed the
boundary" from "the parent relayed a name it had been told to invoke." The
expected result is negative, where the confound is harmless. Recorded rather than
quietly tolerated, because the rule printed by the script forbids varying two
things at once and this arm does.

## What has been run

**One run is recorded**, in [RESULTS.md](RESULTS.md) — Claude Code 2.1.214,
Windows, 2026-07-31, every arm matching and all three controls behaving. That is
one run on one platform with one model, not a compatibility promise. The script
still computes no verdict; the matrix in that file was read off the arms by a
person.

**The expected values are inherited from the audited source.** Arm D's expected
"does not cross" comes from `subagent-composition`'s own ledger, and a
substantially similar probe was run upstream. An audit whose design and expected
answers both come from the thing it audits is weaker than an independent one, and
this one is disclosed as such.

**The shipped canary tokens are burnt.** They are published in `RESULTS.md`, so a
verbatim re-run tests tokens a reader can look up. Replace all three — in
`run-probes.sh`, `fixtures/canary-skill/SKILL.md`, and
`agents/probe-channel-self.md` — before treating a re-run as a real test.

## Not probed

Stated for honesty; do not treat these as established.

- Whether the composer's **conversation history** crosses. The harness cannot
  cleanly separate "the boundary leaked it" from "the spawning turn passed it
  along", so the arm was not built rather than built and over-read.
- Auto-memory as a channel.
- Whether any of this holds across CLI versions, platforms, or models other than
  the pinned `haiku`.
