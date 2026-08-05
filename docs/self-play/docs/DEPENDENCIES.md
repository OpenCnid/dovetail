# Dependencies

Every skill, rule, and record `SKILL.md` names, where its pinned copy came from,
and what stops working without it.

**Vendored copies are derived artifacts.** On any drift between a copy under
`vendor/` and its source, the source wins and the copy is regenerated. A copy
here is never an authority over the thing it was copied from, and a reader
resolving a disputed claim goes to the source.

Vendored 2026-07-31. Verify a copy with:

```bash
sha256sum vendor/<name>/SKILL.md
```

## Installing them

**The maintained way to install this skill and all five dependencies at once is
[OpenCnid/dovetail](https://github.com/OpenCnid/dovetail)** — a pack that holds
each of them as a git submodule pinned to a commit, with no copies at all. Every
dependency now has its own public repository, which the pack pins and this
document records.

The commands below remain the fallback for installing from this repository
alone.

**Reading a vendored copy does not open the gate; installing it does.** The
gate is opened by *invoking* a skill, and a skill can only be invoked once it is
in a skills directory. The vendored bytes are the same bytes — what changes is
whether the harness can load them.

The two hard requirements:

```bash
cp -r vendor/prompt-engineering  ~/.claude/skills/
cp -r vendor/hypershot-protocol  ~/.claude/skills/
```

All five, if you want the skill's claims fully grounded:

```bash
cp -r vendor/*/ ~/.claude/skills/
```

Claude Code picks them up live, with no restart. Use `.claude/skills/` instead of
`~/.claude/skills/` to install them per-project and commit them with a repo.

**These are pinned copies, not upstream.** Where a dependency has a public home —
`subagent-composition` does — prefer installing from there and treat the copy
here as a fallback and a record of what this skill was built against.

## The dependency set

Read off `SKILL.md` by grep, not inherited from a list. Five skills, and nothing
else that a stranger would need to install.

| Skill | Role in this skill | What breaks without it |
|---|---|---|
| `prompt-engineering` | **Gate skill, hard.** Opens the gate for authoring player prompt bytes. | Player prompts get authored ungated. The skill's own § *House note* becomes a sentence the repository does not honour. |
| `hypershot-protocol` | **Gate skill, hard.** The player prompt frame *is* a hypershot. | The frame reads as a template with odd naming instead of a contamination-control device, and filled-in examples creep back into player prompts — the exact leak the method exists to close. |
| `subagent-composition` | The **spawn gate** (§ *When to use*) and the **isolation ledger** (§ *The players*). | Two load-bearing claims lose their grounding: that a spawn is the expensive path, and that your reasoning does not cross into a player unless you put it there. Without the second, isolation is an assumption rather than a mechanism. |
| `judge-composition` | The clean-context principle this skill generalizes, and the source of the judging seats that score utility. | § *What this is* loses its lineage, and "judges score utility" has no composition method behind it. |
| `spark-steering` | § *Ask first — the un-tool*, behind the "a held expectation goes to the collaborator" rule. | The ground-block rule names a destination for a held expectation and cannot say what that move is or why it precedes installing configuration. |

## Pins

| Skill | SHA-256 (first 16) | chars | Vendored copy | Canonical authority |
|---|---|---|---|---|
| `prompt-engineering` | `D6F1BBCAD32693BC` | 5,805 | [`vendor/prompt-engineering/SKILL.md`](../vendor/prompt-engineering/SKILL.md) | The Lexideck Prompt Engineering Curriculum (Matthew Murphy). The `SKILL.md` is the deployed artifact, not the curriculum. |
| `hypershot-protocol` | `981BD9B0D92DAF8B` | 11,106 | [`vendor/hypershot-protocol/SKILL.md`](../vendor/hypershot-protocol/SKILL.md) | Same Lexideck lineage. |
| `subagent-composition` | `D6CAFF44BA55791A` | 16,967 | [`vendor/subagent-composition/SKILL.md`](../vendor/subagent-composition/SKILL.md) | [OpenCnid/subagent-composition](https://github.com/OpenCnid/subagent-composition) at `1b9ffd5`. |
| `judge-composition` | `3E563072EB5695AA` | 19,326 | [`vendor/judge-composition/SKILL.md`](../vendor/judge-composition/SKILL.md) | [OpenCnid/judge-composition](https://github.com/OpenCnid/judge-composition) at `de7446d`, which ships all thirteen records it cites in its own `references/` and is **canonical for its own skill and for those mirrored records**. Its design record originated in a now-deprecated repository; the mirrors **in `judge-composition` itself** are what remain of it. |
| `spark-steering` | `844DD833EF86DDED` | 5,633 | [`vendor/spark-steering/SKILL.md`](../vendor/spark-steering/SKILL.md) | [OpenCnid/spark-steering](https://github.com/OpenCnid/spark-steering) at `67cb3b6`, plus its `references/`, backed by a 373-primitive map of Claude Code surfaces kept with its research paper. |

Full hashes are in [`vendor/HASHES.txt`](../vendor/HASHES.txt), verifiable with
`sha256sum -c vendor/HASHES.txt`.

**Refreshed 2026-08-01, and two things were wrong before it.** The
`judge-composition` and `subagent-composition` copies were stale — both skills
had been rewritten the same day and the pins still described the previous bodies.
And **five of the six recorded hashes did not verify on a fresh clone**: they had
been computed against CRLF working copies on Windows, while `.gitattributes`
(`eol=lf`) checks the files out as LF everywhere, so `sha256sum` on a clean
checkout produced six different digests and the manifest's own verify instruction
failed. Every hash above is now over LF content and checks out on any platform.

The vendored copies are derived artifacts. On any divergence the source
repository named in the last column wins and the copy here is regenerated —
never the reverse.

### Drift note — `subagent-composition` — **RESOLVED 2026-07-31**

The published repository carried a 13,548-byte `SKILL.md` at commit `06ad525`,
behind the copy vendored here: it predated the § *The disproving arm* section.

**Upstream is now level.** The content was ported and merged as
[OpenCnid/subagent-composition#1](https://github.com/OpenCnid/subagent-composition/pull/1),
and `main` carries it at `c5ab4fa`. The repair went to the source rather than to
this copy, which is the direction the rule requires.

*This note previously warned that the vendored copy was CRLF while upstream
normalises to LF, so the recorded SHA-256 would not match a fresh clone and
readers should compare content rather than digests.* **That is fixed rather than
still true.** Every vendored copy is LF, matching what `.gitattributes` checks
out on any platform, and the digests in `vendor/HASHES.txt` now verify with
`sha256sum -c` on a clean checkout anywhere.

### Pin note — the copies are refreshed, and the policy changed to say so

**Superseded 2026-08-01, at owner instruction.** This section previously read:

> **This is not regenerated here on purpose.** The maintained install path is
> [OpenCnid/dovetail](https://github.com/OpenCnid/dovetail), which pins the
> current skill as a submodule; the copies under `vendor/` are the record of what
> this skill was built and tested against, and rewriting that record to look
> current would defeat its only job.

That reading is retired. It also contradicted [`AGENTS.md`](../AGENTS.md), which
states the rule the other way — vendored copies are derived, and on drift the
source wins and the copy is regenerated. Two rules in one repository pointing
opposite ways is worse than either rule alone, and the one that survives is the
one the rest of the house follows.

**The copies under `vendor/` now track their sources.** They are a convenience
snapshot so a reader can see what each named dependency says without installing
it — not an authority, and not a historical record. What this skill was built and
tested against is recorded where evidence belongs: in
[`FINDINGS.md`](FINDINGS.md) and [`VALIDATION.md`](VALIDATION.md), with commits
and addresses, which is a better record than a frozen file copy because it says
*when* and *what changed*.

Regenerate with the source repositories checked out beside this one, then rerun
`sha256sum` and update the table above and `vendor/HASHES.txt` together.

### What was not vendored

Only `SKILL.md` is vendored for each dependency, because that is the file
`SKILL.md` cites. Two dependencies carry more:

- `spark-steering/references/` — not vendored, including
  `steer-1-levers.md` § *The un-tool*, which the body cites for the
  construction and its provenance. The body carries enough to act on; a reader
  wanting the derivation needs the source.
- `judge-composition/README.md` — not vendored.

## Rules this skill depends on

`SKILL.md` cites house rules that originated in another repository. Each is
restated portably here so the skill stands alone, and **every rule this skill
cites by number also ships here byte-for-byte**, extracted at commit `07bd744`
and verified by blob SHA. So each restatement below is checkable against its
source from inside this repository rather than taken on trust.

**This paragraph has been corrected twice, and both corrections are kept.** An
early version described the origin repository as private, so the restatements
were uncheckable. That was wrong and was replaced with live links to it. **The
links were wrong too**: that repository is deprecated and will be archived or
deleted, and a citation that depends on it resolving is a citation with an expiry
date. Mirrors replace the links.

**This repository is now canonical for this skill**, including for its copies of
the rules below. Nothing outside it wins on drift, because nothing outside it is
guaranteed to be there.

| Rule | Where it was cited | Disposition here |
|---|---|---|
| Measurement doctrine — instructions are specifications; a null needs a discriminating control; correctness is the whole score | § *When to use*, discipline 6, § *The cell that matters* | **Restated in full** at [`skills/self-play/references/measurement-bounds.md`](../skills/self-play/references/measurement-bounds.md). That file is what the skill cites. |
| The authoring gate — the two protocols run before the bytes | § *House note* | **Restated in full** in [`AGENTS.md`](../AGENTS.md) § *The authoring gate*. It is house-wide, so it binds work in this repository directly. |
| The positive-control duty — *a null result is meaningless until the experiment has demonstrated it can produce a positive one* | discipline 6 | **Restated verbatim in the discipline itself.** The origin citation is dropped; the sentence is load-bearing and now travels with the rule that uses it. |
| Ask-the-collaborator — put an underdetermined call to the collaborator rather than settling it with standing configuration | § *The `## Ground` block* | **Restated in full** in the section, with the reason attached. Also carried in [`AGENTS.md`](../AGENTS.md). |

## Records that stayed behind

Two auto-memory entries were cited by the origin `SKILL.md`:
`project-corrosion-bound-critique` and `feedback-encoding-tracks-presentation`.

These are **unportable by construction and are not carried forward.** Auto-memory
does not cross the sub-agent boundary (see `vendor/subagent-composition/SKILL.md`
§ *The inheritance ledger*), so they were never available to a player in the
first place, and they are not available to anyone outside the machine that holds
them. The findings they recorded are written up with their addresses in
[`FINDINGS.md`](FINDINGS.md).

## A rule the origin skill did not cite

The origin repository's `composed-evaluators.md` (rule 17) appears in this
repository's build hand-off as a rule the skill depends on. Grepping the origin
`SKILL.md` for it returns nothing: the skill never cited it. It is therefore not
a dependency and nothing here restates it.
