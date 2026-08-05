# Findings: the Claude Code sub-agent boundary

**Probed:** 2026-07-19 (§1–§7) · 2026-08-02 (§8–§14) · **Claude Code:** 2.1.214
**Platform:** Windows 10, PowerShell + Git Bash
**Reproduce:** `bash probes/run-probes.sh` — covers §1–§6. §7 and §8–§14 are
reproducible but not in the checked-in harness; §15–§17 are doc-cited, not run.

Every row below is either cited to the Anthropic docs or observed directly by
the probe harness. Nothing here is written from a model's prior. Where the two
sources disagree, both are recorded.

Undocumented behavior carries no compatibility promise. Re-run the harness
before relying on any ⚠️ row.

---

## 1. What crosses the boundary

The load-bearing fact about sub-agents: they inherit far less than intuition
suggests.

| Crosses | Does **not** cross |
|---|---|
| The agent's own prompt (file body, or the `prompt` param) | The parent's conversation history and every tool result in it |
| The `CLAUDE.md` hierarchy — project leg measured, the rest doc-cited in §15 | The parent's system prompt and harness instructions |
| Tool *definitions* for its allowlist | Auto-memory / `MEMORY.md`, including recalled entries |
| Skills named in `skills:` — **full body** | Skill content the *parent* has loaded |
| Session extended-thinking config | The parent's reasoning, rejected paths, and the user's stated intent |
| Names of sibling agents (for `SendMessage`) | — |

**Return channel: the final message only.** Intermediate tool calls and their
results stay in the sub-agent's context and are discarded unread. A sub-agent
that works perfectly and signs off with "Done — see above" has produced nothing.

`CLAUDE.md` inheritance was verified directly, and only for the project leg: a
probe run in a directory whose project `CLAUDE.md` contained the token
`MARMOSET-7731` reported that token back. The docs describe a wider hierarchy —
user-level, `.claude/rules/`, `CLAUDE.local.md`, managed policy — with Explore
and Plan as the sole exception. No canary was planted in those legs here; see
§15. The `settingSources` qualifier this row previously carried appears in no
documentation page consulted in either pass and has been dropped rather than
left standing unsourced.

**Exception — forks.** `/subtask` and `--fork-session` inherit full conversation
context, system prompt, and tools. When continuity matters more than isolation,
fork instead of spawning. To continue an existing agent rather than cold-start a
new one, use `SendMessage` with its name or `agentId`.

---

## 2. Frontmatter reference

`.claude/agents/{name}.md`, YAML frontmatter followed by the body (which is the
agent's system prompt).

| Field | Value | Notes |
|---|---|---|
| `name` | kebab-case | Required. Precedence: project `.claude/agents/` > user `~/.claude/agents/` > plugin. |
| `description` | plain scalar | Required. Drives automatic delegation. Quote it if it contains `: ` (colon-space), which YAML parses as a mapping. |
| `tools` | **comma-separated string** — `Read, Grep, Glob` | ✅ verified. Not a YAML list. Omitted ⇒ inherits everything. MCP form `mcp__server__tool`. |
| `disallowedTools` | comma-separated string | Applied *before* `tools`. Supports `mcp__server__*` and `mcp__*`. Not independently probed. |
| `model` | `inherit` \| `opus` \| `sonnet` \| `haiku` \| `fable` \| full ID | Default `inherit`. `CLAUDE_CODE_SUBAGENT_MODEL` sets a floor. |
| `effort` | `low`…`max` or number | Per-agent reasoning budget. Valid in filesystem frontmatter. |
| `maxTurns` | integer | Hard ceiling. The cheapest guard against an unbounded sweep. |
| `skills` | any YAML form | ✅ verified — see §3. Loads the full skill body. |
| `isolation` | `worktree` | Own git worktree; auto-removed **only if unchanged**. Not independently probed. |
| `color`, `hooks` | — | Filesystem-only, undocumented shape. `hooks` / `mcpServers` / `permissionMode` are forbidden in plugin-shipped agents. |

**Recursion.** A sub-agent can spawn its own only if `Agent` is in its `tools`;
depth caps around five levels.

---

## 3. `skills:` accepts every YAML form ✅

All three spellings are equivalent and all three load the complete skill body:

```yaml
skills: hypershot-protocol          # bare scalar / comma-separated
skills: [hypershot-protocol]        # flow sequence
skills:                             # block sequence
  - hypershot-protocol
```

**Evidence.** Three agents identical but for this field, plus a control with the
field absent. Each was asked for two tokens it could only hold if the skill body
were present: a distinctive proper noun from deep in the skill, and the verbatim
title of one of its numbered rules. Tools were restricted to `WebSearch` so no
agent could read the skill off disk.

| agent | `skills:` form | canary | rule title |
|---|---|---|---|
| `probe-skills-bare` | scalar | ✅ recovered | ✅ verbatim |
| `probe-skills-flow` | `[flow]` | ✅ recovered | ✅ verbatim |
| `probe-skills-block` | block seq | ✅ recovered | ✅ verbatim |
| `probe-skills-control` | *absent* | `absent` | `absent` |

`skills:` is the **only** way to give a sub-agent skill content. Skills loaded
in the parent session do not cross.

---

## 4. `tools:` is enforced, not advisory ✅

Every probe declared `tools: WebSearch` and every probe reported exactly one
available tool. The allowlist **replaces** inheritance rather than trimming it.

This also confirms the comma-separated syntax at runtime: had the field failed
to parse, the agents would have inherited the full tool set, and the probes
would have reported it.

---

## 5. ⚠️ `--agent {name}` silently ignores `skills:`

**The most expensive finding here.** Session-agent mode and sub-agent spawn are
different code paths, and only the spawn path preloads skills.

Same agent definition, same canary, two invocation modes:

```bash
# session-agent mode — skills: is dropped, no error, no warning
claude --agent probe-context-detect -p "..."
#   CLAUDEMD_CANARY: MARMOSET-7731
#   SKILL_CANARY: absent          ← the skill was declared and did not load

# true sub-agent spawn — skills: is honored
claude --allowedTools "Agent" -p "Spawn the probe-context-detect subagent via the Agent tool …"
#   CLAUDEMD_CANARY: MARMOSET-7731
#   SKILL_CANARY: Nexus Singularity Engine
```

Note the first result is *partially* correct — `CLAUDE.md` still crosses — which
is exactly what makes it convincing. The agent looks like it is receiving
context, so the missing skill reads as "`skills:` is broken" rather than "wrong
invocation mode."

**Practical rule:** validate agent behavior through an actual spawn. Never
through `--agent`. A working definition will otherwise read as broken, and the
failure is silent in both directions.

---

## 6. ⚠️ Agent registration lags the filesystem — both ways

Skills register the instant the file is written. Agents do not.

- A newly written agent file fails with **`Agent type 'x' not found`** while its
  definition is entirely valid.
- A **deleted** agent file can keep appearing in the available-agents list well
  after removal. Observed directly: five probe agents were announced as newly
  available *after* they had been deleted from disk.

Never read `Agent type not found` as evidence of a broken definition. To test a
new agent without waiting or restarting, use a fresh process:

```bash
claude --allowedTools "Agent" -p "Spawn the {name} subagent via the Agent tool, \
passing the prompt '{...}'. Then output its final message verbatim and nothing else."
```

---

## 7. ⚠️ The ephemeral `Agent` call is a smaller surface than the file

**Observed in the field, not by this harness.** `run-probes.sh` exercises
filesystem-defined agents; it does not exercise the `Agent` tool call's own
schema. This row is recorded because it changes when you must write a definition
instead of passing a prompt, and it is marked accordingly.

On CLI **2.1.214** the call's schema accepts `description`, `prompt`,
`subagent_type`, `model`, `run_in_background`, and `isolation`, and refuses
anything else — `additionalProperties` is `false`, so an unexpected key is a
rejected call rather than an ignored field.

| Control | Ephemeral `Agent` call | `.claude/agents/{name}.md` |
|---|---|---|
| `model` | yes | yes |
| `isolation: worktree` | yes | yes |
| background vs. synchronous | yes — `run_in_background` | caller's choice, not a field |
| `maxTurns` | **no** | yes |
| `effort` | **no** | yes |
| `tools` / `disallowedTools` | **no** — fixed by `subagent_type` | yes |
| `skills` preload | **no** | yes |

**Consequence.** A turn ceiling, a tool budget, a reasoning budget, and
preloaded skill content are all four unreachable from a bare `Agent` call.
Needing any of them is the durable-specialization trigger: write the definition,
then reach it through `subagent_type`. Reading `maxTurns` as an ephemeral
parameter costs a rejected call to discover.

**How this was established, stated plainly:** by calls that were refused, in
ordinary use, rather than by a controlled arm. It is reproducible by anyone who
passes `maxTurns` to an `Agent` call and reads the error. Adding an arm to
`run-probes.sh` that does exactly that is the obvious next probe and has not been
written.

---

## 8. Hooks observe skill invocation, and the path decides the event ✅

A hook can see a skill being invoked. Which event fires depends on how the
invocation started.

| Invocation path | Event | Field carrying the skill name |
|---|---|---|
| The model calls the `Skill` tool | `PreToolUse`, `PostToolUse` — `matcher: "Skill"` | `tool_input.skill` |
| The user types `/name` | `UserPromptExpansion` | `command_name` |

`PreToolUse` payload, observed:

```json
{"hook_event_name":"PreToolUse","tool_name":"Skill","tool_input":{"skill":"orrery-audit"},"tool_use_id":"toolu_01UqiuUM4BuVqpQVyjweR7ry"}
```

`PostToolUse` fires on the same call, carrying
`"tool_response":{"success":true,"commandName":"orrery-audit"}`.

**Control.** A second matcher group on `Read` logged in the same run. The
harness was demonstrably working before any conclusion was drawn about `Skill`.

Typing `/orrery-audit` fires `UserPromptExpansion`, and no `PreToolUse`:

```json
{"hook_event_name":"UserPromptExpansion","expansion_type":"slash_command","command_name":"orrery-audit","command_args":"","command_source":"projectSettings"}
```

The docs corroborate. [Hooks](https://code.claude.com/docs/en/hooks): "typing
`/skillname` directly bypasses `PreToolUse`."

**Sub-agent invocations reach the same channel.** A hook declared in a settings
file observed a skill invoked *inside* a sub-agent. The entry was logged under
the parent's `session_id` and carried two fields the main-thread payloads above
do not: `"agent_id":"a34b25b5ab6f4051c"` and `"agent_type":"general-purpose"`.

**The `skills:` preload path emits no skill-identifying event.** Handlers were
registered on all eleven event names the 2.1.214 binary contains, each with an
empty matcher, and a sub-agent was spawned whose definition preloaded a skill.
The preloaded skill's name appears in zero payloads:

```
$ grep -a -c 'lantern-brief' hook-log.txt
0
$ grep -a -o '"skill":"[^"]*"' hook-log.txt | sort | uniq -c
      4 "skill":"control-beacon"
```

The four `control-beacon` hits are the control: a direct `Skill` call in the same
run, under the same configuration, fired `PreToolUse` and `PostToolUse` on that
name — so the empty result for the preload is a real negative, not a dead logger.
The preload was confirmed to have happened from the `SubagentStop` payload, whose
`last_assistant_message` returned the skill body's planted marker.

What *is* observable is the generic sub-agent lifecycle, none of which names the
skill: `PreToolUse`/`PostToolUse` with `tool_name: "Agent"`, and the
`SubagentStart`/`SubagentStop` pair carrying `agent_id` and `agent_type`.

**Consequence.** No hook can condition on which skills a sub-agent preloaded. A
skill that must travel with companions has to name them in the agent definition's
own `skills:` list; there is no interception point.

---

## 9. ⚠️ `if` cannot discriminate on skill name

**What the docs say.** [Hooks](https://code.claude.com/docs/en/hooks) describes
`if` as "Permission rule syntax to filter when this hook runs," and the
[Skills](https://code.claude.com/docs/en/skills) page documents the permission
forms `Skill(name)` and `Skill(name *)`.

**What was observed on 2.1.214.** Five `if` values, all five in a single run
against a skill named `zephyr-ledger`:

| `if` value | Matched |
|---|---|
| `Skill(zephyr-ledger)` | no |
| `Skill(zephyr-ledger *)` | no |
| `Skill(zephyr-ledger*)` | no |
| `Skill(zephyr-ledger:*)` | no |
| `Skill(*)` | **yes** |

**Binary corroboration.** At the `Skill` tool's definition in the shipped
2.1.214 build, `ruleContentField present: false` — the field a rule-content
matcher would read is absent from the tool definition.

**They disagree.** The docs publish a `Skill(name)` permission syntax; on CLI
**2.1.214** that syntax does not filter a hook, and only the bare `Skill(*)`
form matches. Recorded per the house rule rather than resolved.

**What discriminates instead.** Read `tool_input.skill` inside the hook script,
or match on `UserPromptExpansion`, whose matcher matches `command_name` exactly.

---

## 10. A hook-delivered directive changes what the model invokes ✅

Two hook entries, one per invocation path from §8, each emitting a short
directive on `hookSpecificOutput.additionalContext`.

Compliance was **4 of 4** across both paths: the model invoked both named
sibling skills, in the order the directive gave, and the body canaries of both
appeared in the transcript.

**Negative control.** An unrelated decoy skill, invoked under the same hook
configuration, produced zero occurrences of the directive on either path. The
directive travels with the matched skill, not with the session.

---

## 11. ⚠️ `` !`command` `` in a skill body: renders everywhere, aborts hard

Embedded command placeholders were exercised with a two-canary design that
separates *body rendered* from *command ran*. The `skills:` preload leg was read
from the sub-agent's own sidechain transcript, not from a self-report.

| Condition | Result |
|---|---|
| Typed `/name` | Renders; both canaries present |
| Model calls the `Skill` tool | Renders; both canaries present |
| `skills:` preload in an agent definition | Renders; both canaries present |
| No shell permission grant for the command | **Whole invocation aborts**; no model turn ran at all |
| Command exits nonzero | **Whole skill render aborts**; the model receives no skill content |
| `~` / `$HOME` path outside the session working directory | Expands correctly, read refused |
| `${CLAUDE_SKILL_DIR}`-derived path outside the working directory | Permitted |
| Literal `..` after a directory segment | Rejected before execution |

The permission failure is not a failed placeholder in an otherwise-rendered
body:

```
<local-command-stderr>Error: Shell command permission check failed for pattern "!`node -e ...`": This command requires approval</local-command-stderr>
```

The refused read outside the working directory reports: "For security, Claude
Code may only read the beginning of files from the allowed working directories
for this session".

**Consequence.** An embedded command is a single point of failure for the entire
skill. A nonzero exit does not degrade the skill — it removes it.

**A sub-agent's `tools:` allowlist does not gate it.** Two agent definitions
differing in exactly two lines — `name:` and `tools:`, one granting `Read, Bash`
and one granting only `Read` — preloaded a byte-identical skill whose body
carried an embedded command. Both sub-agents received the same rendered canary,
and both transcripts contain zero `tool_use` blocks:

```
shell-carrier    RUNCANARY-MIRRORGLASS-8842 occurrences: 2   tool_use blocks: 0
noshell-carrier  RUNCANARY-MIRRORGLASS-8842 occurrences: 2   tool_use blocks: 0
```

The command is preprocessing: it runs before the body is injected, so the
allowlist that governs the sub-agent's *tool calls* never applies. This bounds
§4's "`tools:` is enforced, not advisory" — enforcement covers tool calls, and an
embedded command is not one. The arm varied `tools:` only; the skill's own
`allowed-tools` frontmatter was held constant, so this establishes that the
agent allowlist is not the gate, not that no gate exists.

---

## 12. ⚠️ A plugin manifest in a skill directory does not rename the skill

Adding `.claude-plugin/plugin.json` to a skill directory mints no
`plugin:skill` name. Before/after runs at a user-level skills root, same skill:

| Surface | Before manifest | After manifest |
|---|---|---|
| Typed slash form | bare name | bare name |
| `Skill` tool `skill` parameter | bare name | bare name |
| Hook payload `command_name` | bare name | bare name |
| Hook payload `command_source` | `userSettings` | `userSettings` |

`claude plugin details` reports `Skills (0)` and `Hooks (2)`, with
`Always-on: ~0 tok`. The root `SKILL.md` is not counted as a plugin skill
component, which is why no prefixed name appears.

The same manifest placed in a **project-local** `.claude/skills/` fired zero
plugin hooks.

Activation was observed on the next session. No install or reload command was
run, so nothing here characterizes what one would do.

---

## 13. ⚠️ Hooks fire in an untrusted workspace; `permissions.allow` does not

Hooks declared in `.claude/settings.json` execute in a workspace that has not
been trusted. Permission grants in the same file are discarded, with notice:

```
Ignoring 4 permissions.allow entries from .claude/settings.json: this workspace has not been trusted.
```

The two halves of one settings file are therefore governed differently. A hook
that shells out in an untrusted workspace runs while the grant intended to
authorize it is being ignored — see §11 for what an unpermitted command does to
a skill render.

---

## 14. Skill bodies measured against the documented hook output cap

Body sizes, YAML frontmatter stripped:

| Skill | Body characters |
|---|---|
| `subagent-composition` | 16,210 |
| `hypershot-protocol` | 10,312 |
| `prompt-engineering` | 5,118 |

**Doc-cited:** hook output strings are documented as capped at 10,000
characters, with overflow replaced by a file path and a preview.

`hypershot-protocol` alone exceeds the cap; the three together exceed it three
times over. A hook cannot deliver these bodies inline. It can deliver a
directive naming them, which is the mechanism §10 measured.

---

## 15. Doc-cited: the whole `CLAUDE.md` hierarchy crosses into sub-agents

**Cited, not probed here.**
[Create custom subagents](https://code.claude.com/docs/en/sub-agents) states
that a sub-agent loads "every level of the CLAUDE.md hierarchy the main
conversation loads," naming `~/.claude/CLAUDE.md`, project rules,
`CLAUDE.local.md`, and managed policy files. It states the carve-out is
per-agent — "The built-in Explore and Plan agents skip this" — and that it
cannot be overridden: "There is no frontmatter field or per-agent setting to
change which agents skip them."

This harness planted a canary in a **project** `CLAUDE.md` only (§1). The
user-level, rules, `CLAUDE.local.md`, and managed-policy legs are cited above
and unverified here; they are listed in §18. §1's ledger row is narrower than
this section on purpose — it records what the harness measured.

---

## 16. Doc-cited: skills after auto-compaction

**Cited, not probed here.** [Skills](https://code.claude.com/docs/en/skills)
states that auto-compaction "re-attaches the most recent invocation of each
skill after the summary, keeping the first 5,000 tokens of each," under a
combined 25,000-token ceiling filled most-recent-first.

No run in this record reached compaction, so nothing here confirms the
re-attachment, the per-skill truncation, or the ceiling.

---

## 17. ⚠️ Doc-cited: `DirectoryAdded` is documented and absent from the binary

**Established from the docs page and a read of the shipped binary. No hook was
configured to test whether the event fires.**

**What the docs say.** [Hooks](https://code.claude.com/docs/en/hooks) lists
`DirectoryAdded` among the hook events.

**What the 2.1.214 build contains.** The frozen event array holds 30 hook
events and `DirectoryAdded` is not one of them. `grep -a -c 'DirectoryAdded'
claude.exe` returns `0`, while the same grep method locates every other
documented event name in the same binary.

**They disagree.** On CLI **2.1.214** the documented event name is not present
in the binary. Whether the event can fire at runtime was not tested.

---

## 18. Not probed

Stated for honesty; do not treat these as verified.

- The ephemeral-call schema in §7 — reproducible, but not covered by the
  checked-in harness.
- §8 through §14 likewise: run on 2.1.214 on 2026-08-02, reproducible, and not
  covered by `probes/run-probes.sh`.
- Whether `UserPromptExpansion` fires on the `skills:` preload path. The §8
  preload arm registered it with an empty matcher and it never fired, but that
  run's control was mangled by MSYS path conversion — `claude -p "/name"` under
  Git Bash reached the CLI as the literal prompt `C:/Program Files/Git/name` — so
  the handler had no chance to fire from any source. Blind, not negative.
- Whether *anything* gates an embedded `` !`command` `` in a preloaded body. §11
  establishes the sub-agent's `tools:` allowlist is not the gate; the skill's own
  `allowed-tools` frontmatter was held constant and was not varied.
- Whether hook events exist whose names the binary constructs dynamically. The
  §8 preload arm registered all eleven literal event strings found by grep; an
  event assembled at runtime would have escaped that search.
- The user-level `~/.claude/CLAUDE.md`, `.claude/rules/`, `CLAUDE.local.md`, and
  managed-policy legs of the hierarchy in §15 — doc-cited only. Only the project
  leg carries a canary.
- Hook-output overflow behavior at the 10,000-character cap (§14). The
  replacement file path and preview were never observed.
- Auto-compaction re-attachment, per-skill truncation, and the combined ceiling
  (§16).
- Whether `DirectoryAdded` (§17) fires at runtime despite its absence from the
  binary.
- Plugin-manifest activation (§12) following an explicit install or reload
  command. Only next-session activation was observed.

- `disallowedTools` ordering relative to `tools`.
- `isolation: worktree` cleanup semantics and the `cleanupPeriodDays` sweep.
- Behavior at the `maxTurns` ceiling — whether it truncates or returns partial output.
- Wildcard forms (`*`) inside `tools:`.
- Automatic-delegation matching: the docs state `description` drives it but
  publish no algorithm, and we did not attempt to characterize one.
- Whether any of this holds on non-Windows platforms or other CLI versions.

---

## Sources

- [Create custom subagents](https://code.claude.com/docs/en/sub-agents)
- [Subagents in the SDK](https://code.claude.com/docs/en/agent-sdk/subagents)
- [Hooks](https://code.claude.com/docs/en/hooks)
- [Skills](https://code.claude.com/docs/en/skills)
- [Worktrees](https://code.claude.com/docs/en/worktrees) ·
  [Settings](https://code.claude.com/docs/en/settings) ·
  [Model config](https://code.claude.com/docs/en/model-config) ·
  [Plugins reference](https://code.claude.com/docs/en/plugins-reference) ·
  [Memory](https://code.claude.com/docs/en/memory)
- Probe harness: [`probes/`](../probes/), method in
  [PROBE-METHODOLOGY.md](PROBE-METHODOLOGY.md)
