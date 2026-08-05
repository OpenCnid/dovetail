# probes/

The experiment behind [docs/FINDINGS.md](../docs/FINDINGS.md). Design rationale
and the two wrong answers it caught: [docs/PROBE-METHODOLOGY.md](../docs/PROBE-METHODOLOGY.md).

```bash
bash probes/run-probes.sh
```

## Why these are not in `.claude/agents/`

They would auto-register for anyone cloning this repo and clutter the agent
list with five diagnostics nobody asked for. `run-probes.sh` installs them,
runs them, and removes them. It refuses to start if an agent of the same name
already exists, and cleans up on interrupt.

## What's here

| file | role |
|---|---|
| `agents/probe-skills-bare.md` | `skills:` as a bare scalar |
| `agents/probe-skills-flow.md` | `skills:` as a `[flow list]` |
| `agents/probe-skills-block.md` | `skills:` as a block sequence |
| `agents/probe-skills-control.md` | **negative control** — no `skills:` field |
| `agents/probe-context-detect.md` | **positive control** — both canaries in one reply |
| `canary-skill/SKILL.md` | the content being smuggled across the boundary |
| `run-probes.sh` | install, run, print matrix, clean up |

All five agents are byte-identical apart from the one field under test, and all
are pinned to `model: haiku` with `maxTurns: 2` — cheap, fast, and too
constrained to wander into a workaround that would contaminate the result.

## Reading the matrix

The controls are not ceremony; they are the only reason the result means
anything.

- **The control recovers a canary** → the probe is contaminated. A side channel
  is open, or the canary is guessable. Fix the probe, not the finding.
- **Every row absent, including `probe-context-detect`** → suspect the harness
  before the runtime. If the positive control cannot see a `CLAUDE.md` canary,
  the probe is blind and every "absent" is noise rather than evidence.
- **`probe-context-detect` finds `CLAUDEMD_CANARY` but not `SKILL_CANARY`** →
  skill content did not cross. Before concluding `skills:` is broken, confirm
  you are on the sub-agent spawn path. `claude --agent <name>` silently drops
  the field and produces exactly this signature.

## Adding a probe

Copy an existing agent, change **one** field, keep the return frame identical.
A probe that varies two things at once cannot attribute its own result.

If you add a canary, it must be unguessable rather than merely obscure — a
token a model could reconstruct from context measures cleverness, not
inheritance. And never put a canary's value in the spawning prompt; it must
reach the agent only through the channel under test.
