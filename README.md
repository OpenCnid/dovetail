# dovetail

*Eight Claude Code skills that hold together by shape, not by glue.*

[![license](https://img.shields.io/badge/license-CC_BY_4.0-3b7ddd)](LICENSE.md)
![skills](https://img.shields.io/badge/skills-8-58a6ff)
![layout](https://img.shields.io/badge/layout-monorepo-2ea44f)
![submodules](https://img.shields.io/badge/submodules-0-9b8cf7)

A dovetail joint holds because of how the pieces are cut. No fasteners, no
adhesive — the strength *is* the fit. That is the claim this pack makes about
these eight skills, and it is meant literally: each is independently useful, and
each one's weak point is another one's subject.

## The joint

```mermaid
flowchart LR
    subgraph author["author"]
        pe["prompt-engineering"] --- hs["hypershot-protocol"]
    end
    subgraph compose["compose"]
        sc["subagent-composition"] --- jc["judge-composition"]
    end
    subgraph verify["verify"]
        sp["self-play"] --- bsc["better-skill-creator"]
    end
    subgraph carry["carry"]
        us["upsum"]
    end
    author --> compose --> verify --> carry
    ss["spark-steering"] -.->|"is a fix even the right move?"| author
```

You write instructions for a model, you compose agents to carry them, you check
what comes back without deceiving yourself, and you close the session so the
next one starts from what happened rather than from what you remember. Every
skill here is a countermeasure against fluent output that feels like rigor.

| skill | what it is for |
|---|---|
| [prompt-engineering](skills/prompt-engineering/SKILL.md) | structural clarity over magic words — tagging, markers, placeholders, attention |
| [hypershot-protocol](skills/hypershot-protocol/SKILL.md) | priming structure without priming content; frames with free variables |
| [subagent-composition](skills/subagent-composition/SKILL.md) | what crosses the sub-agent boundary, and the return contract that survives it |
| [judge-composition](skills/judge-composition/SKILL.md) | four invariant roles, composed fresh per question. No default cast |
| [self-play](skills/self-play/SKILL.md) | a clean-room search over a space you have not solved |
| [better-skill-creator](skills/better-skill-creator/SKILL.md) | author a skill, then find out whether it actually helps |
| [upsum](skills/upsum/SKILL.md) | what survives a session, decided on purpose rather than by what you happen to remember — **invoke it yourself; it does not auto-fire** |
| [spark-steering](skills/spark-steering/SKILL.md) | which capability axis is short, before you install a fix that charges rent — **invoke it yourself; it does not auto-fire** |

**Six of the eight trigger on their own. `spark-steering` and `upsum` do not**,
by design: both carry `disable-model-invocation: true`, and both make that trade
for the same reason. A diagnostic that volunteers itself becomes a tax on every
turn; a close ceremony that volunteers itself runs on every throwaway session.
In each case that is the failure mode the skill exists to prevent.

Verified on CLI 2.1.214 by asking a headless session to enumerate its skills:
**`spark-steering` does not appear in that list at all.** The model cannot see it,
so asking Claude to use it does not work either — it does not know the skill
exists. **You invoke it yourself, by typing `/spark-steering`**, which loads it
normally. `upsum` carries the same flag and `/upsum` loads it the same way; that
one has not been put through the headless check, so treat its absence from the
list as expected rather than as observed.

A correctly installed pack therefore looks like **seven skills Claude can reach
and two it will deny having** — the six above plus `using-dovetail`, the entry
point the `SessionStart` hook injects. That is the intended state, not a broken
install.

## Install

### As a plugin

```bash
/plugin marketplace add OpenCnid/dovetail
/plugin install dovetail@opencnid
/reload-plugins
```

Plugin skills are namespaced, so they cannot collide with skills you already
have — you'll reach them as `dovetail:self-play` and so on.

Installing the pack loads all nine skills at once, and a `SessionStart` hook
injects `dovetail:using-dovetail` — the companion rule, and the notice that two
of the skills are invisible to the model — into every session.

> [!NOTE]
> **Verified from GitHub**, which this note used to say was the open question.
> On CLI 2.1.214 (Windows 10), `marketplace add` of the HTTPS URL followed by
> `install` reports `Skills (9)` and `Hooks (1) SessionStart`, and all nine
> bodies load in a session.
>
> That run predates `0.3.0`, when the skills were still submodules and whether a
> plugin fetch recursed into them was the open doubt. It did. The question is now
> moot — there are no submodules to recurse into — and the result is kept because
> it is what retired the doubt rather than sidestepping it.
>
> Two things that will bite on Windows, both observed:
>
> - **Use the HTTPS URL, not the `OpenCnid/dovetail` shorthand.** The shorthand
>   resolves to `git@github.com:` and fails with *Permission denied (publickey)*
>   on any machine without SSH keys, even though the repository is public.
> - **Install under a short path.** `better-skill-creator` carries deep test
>   fixtures. Its longest path is 136 characters, which under a default
>   `~/.claude` leaves 62 below the 260-character `MAX_PATH` limit. A long
>   username or a deep `CLAUDE_CONFIG_DIR` overruns it, and the failure reads as
>   `fetch-pack: invalid index-pack output` — a clone error that says nothing
>   about path length. `git config --global core.longpaths true` removes the
>   limit.
>
>   Dropping the submodules bought 28 characters back: at `0.2.1` the same file
>   sat under `vendor/better-skill-creator/` for 164 characters and 34 of
>   headroom. Measured 2026-08-05; re-measure rather than trusting these numbers.

### Directly

```bash
git clone https://github.com/OpenCnid/dovetail.git
cd dovetail
bash scripts/install.sh
```

A plain clone is the whole thing — no `--recurse-submodules`, no fetch step, no
way to end up with a hollow pack. `--dry-run` to see what it would do, `--force`
to replace skills you already have, `--project` to install into
`./.claude/skills` and commit them with a repo. It refuses to overwrite anything
without `--force`.

## One repository

Every skill lives here, in `skills/<name>/`. There are no submodules, no pins,
and no sync step: what you clone is what installs, and a drifted copy is not a
thing that can happen because there is nothing to drift from.

This is a reversal. Until `0.3.0` the pack held eight submodules and hosted
nothing, on the principle that each skill stayed canonical in its own
repository. That bought a real property — a pin either points where it pointed
or the diff says otherwise — and cost a step before every change, plus a class
of failure where the pack and its sources could disagree about which was right.
`docs/provenance.md` records where each skill came from and the commit it
arrived at; the source repositories remain the archive of their own history.

What replaces the pin discipline is `scripts/test-skills.sh`, which checks that
every skill still loads rather than that every pointer still points.

## What is honestly weak here

- **Both install routes are now run, on one platform only.** Everything here was
  verified on CLI 2.1.214, Windows 10. Nothing has been run on macOS or Linux,
  and the two Windows traps in the install note are the kind of thing that is
  platform-shaped in both directions — there may be traps elsewhere that this
  machine cannot see.
- **A skill that loads is not a skill that works.** `scripts/test-skills.sh`
  proves each body reaches the session; it cannot prove the model then acts on
  it. That distinction is not pedantic — the injected `SessionStart` directive
  is verified to arrive and unverified to change behavior, which needs an
  authenticated run the harness deliberately does not require.
- **`prompt-engineering` and `hypershot-protocol` are not our method.** They are
  the Lexideck curriculum compressed into deployable form. The work is
  [Matthew Murphy's](https://github.com/gusthemole); credit the source, not the
  application.
- **`spark-steering` cites a 373-primitive corpus kept elsewhere**, so its
  `references/` point at material a reader here cannot open.
- **`upsum`'s summary gradient is a design, not a measured result.** Its own
  README says so: nobody has run it long enough to know whether spending the
  words on the newest entries keeps a growing record honest.
- **Nobody has measured that these eight work better together than apart.** The
  composition is argued from how they cite each other, not demonstrated. Given
  what `self-play` says about entailed outcomes, that comparison would need
  designing carefully rather than running casually.

## Standing on the shoulders of giants

The prompt-engineering toolkit and the hypershot technique are
**[Matthew Murphy's](https://github.com/gusthemole)** Lexideck curriculum. Every
frame in every skill here is a hypershot, and the idea that a variable's name can
carry its own generation rule is his. The SPARK axes come from
[arXiv:2508.01581](https://arxiv.org/abs/2508.01581). The Claude Code mechanics
these skills describe are Anthropic's product behaviour, documented at
[code.claude.com/docs](https://code.claude.com/docs).

## License

Prose and pack: [CC BY 4.0](LICENSE.md) © OpenCnid Labs. Each vendored skill
carries its own license in its own repository.

---

<div align="center">
<sub>Cut to fit. No glue.</sub>
</div>
