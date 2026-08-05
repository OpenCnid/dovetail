# Channel audit — recorded run

**Run:** 2026-07-31 · **Claude Code:** 2.1.214 · **Platform:** Windows 10, Git Bash
**Reproduce:** `bash probes/run-probes.sh`

Canaries planted for this run — regenerate them if you re-run, since a published
token is no longer unguessable:

```
skill body   QUILLBACK-TESSERA-5518
CLAUDE.md    STANCHION-9613
agent body   HALIDE-MARGRAVE-2207
```

## The matrix, as returned

| arm | SKILL_CANARY | CLAUDEMD_CANARY | BODY_CANARY | TOOLS |
|---|---|---|---|---|
| **A** baseline | absent | `STANCHION-9613` | absent | `WebSearch` |
| **B** format control | absent | `STANCHION-9613` | `HALIDE-MARGRAVE-2207` | `WebSearch` |
| **C** positive control | `QUILLBACK-TESSERA-5518` | `STANCHION-9613` | absent | `WebSearch` |
| **D** parent-loaded skill | absent | `STANCHION-9613` | absent | `WebSearch` |
| **E** negative control | absent | **absent** | absent | `WebSearch` |

Every arm matched the expected row.

## Controls first

Read these before any other row, because they decide whether the others mean
anything.

- **Positive control (C) fired.** A canary reached the player through a *foreign*
  channel — a skill named in `skills:` — and was recovered verbatim. The
  instrument can detect inheritance. Every "absent" elsewhere is therefore
  evidence rather than noise.
- **Negative control (E) stayed silent.** With no `CLAUDE.md` present, the
  project canary came back absent. So the recoveries in A–D are the file, not a
  guess and not a side channel.
- **Format control (B) fired.** The agent honours its return frame, so an
  "absent" is a report and not a parse failure.

## What this establishes

1. **Project `CLAUDE.md` is an open channel into every player.** Arms A–D
   recovered it; E, identical to arm A but for the file's absence, did not. A hypothesis
   or a stake written in a project `CLAUDE.md` reaches every seat of a self-play
   run without anyone putting it in a prompt, and no player-prompt audit will
   find it.

   This is the load-bearing operational consequence for this skill, and it is now
   observed here rather than inherited from a dependency's ledger. `SKILL.md`
   § *The isolation ledger, and the channel it does not close* and
   `docs/RUNBOOK.md` move 3 carry the duty and the remedy.

2. **Skill content crosses only when the agent declares it.** Arm C, which named
   the canary skill in `skills:`, recovered it. Arm D, whose *parent* loaded the
   same skill while the agent did not declare it, did not. **Skills loaded by the
   composer do not cross into a player.** That is the half of the isolation
   ledger this method actually rests on, and it held.

3. **`tools:` is enforced.** All five arms declared `tools: WebSearch` and all
   five reported exactly that one tool, so the allowlist replaces inheritance
   rather than trimming it — and no arm could have read a canary off disk.

## Caveats that travel with the result

- **Arm D's confound stands.** It varies three things from arm A, not one — the
  parent's tool set, the parent's prompt text (which names the skill), and the
  parent's loaded-skill state. The confound is harmless on a *negative* arm-D
  result, which is what came back, and would have invalidated a positive one.
  See `probes/README.md` § *Known confound in arm D*.
- **One run, one platform, one CLI version, one model.** The agents are pinned to
  `haiku` with `maxTurns: 2`. Nothing here is claimed to hold across versions;
  undocumented behaviour carries no compatibility promise. Re-run before relying
  on any row.
- **Conversation history and auto-memory were not probed**, for the reason given
  in `probes/README.md` § *Not probed*: the harness cannot cleanly separate "the
  boundary leaked it" from "the spawning turn passed it along", so the arm was not
  built rather than built and over-read.
- **The harness computes no verdict.** The matrix above was read off the arms by
  a person; the script prints output beside expectations and decides nothing.

## Incidental observation

Every arm printed a permission-rule warning from the operating machine's
`settings.json`, unrelated to the probe:

```
Write(~/.claude/projects/**/memory/**) is not matched by file permission checks
— only Edit(path) rules are.
```

Recorded because it appeared in the run output and someone re-reading this file
should know it is environmental noise rather than a probe result.
