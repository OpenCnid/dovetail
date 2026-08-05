# How we know the grading panel works

The panel decides whether a skill helped. If it is wrong, every number downstream is wrong in a way
nobody can see. So it was tested in a clean room rather than by its authors' judgment, and this file
records what that produced — including the parts that did not go well, because a validation record
that only carries wins is a marketing document.

Method: our own `self-play` protocol — pre-register, build the ground blind, isolate the players,
evaluate blind, calibrate honestly. It is a house skill, not part of the upstream bundle this project
derives from, and nothing here imports it: it shaped how the panel was tested, not how it runs.

---

## The final run

**Ground.** 16 items built by an agent that had never seen the panel, the predictions, or the
machinery, and was not told what verdict vocabulary existed — it derived that from the schema. A
second, independent blind reader then decided all 16 without seeing the first one's answers. **They
agreed on 13.** The three disagreements were discarded rather than adjudicated, because a key settled
by the person being tested is not a key.

Retained ground truth: 13 items, 6 pass / 6 fail / 1 abstain. Majority-vote baseline: **46%**.

**Result.**

| | correct | false pass | false fail |
|---|---|---|---|
| grounding alone | 12/13 | | |
| coherence alone | 11/13 | | |
| corroboration alone | 12/13 | | |
| **panel** | **13/13** | **0** | **0** |

The panel beat every seat that composed it. That is the only result that justifies its cost.

**Three items show the mechanism rather than the score:**

- **A single seat's plausible wrong answer was overridden by the cover.** On a spend rollup,
  corroboration returned `pass` on a defensible reading — one allocation pool split at full precision
  and rounded once at display, which reproduces every printed figure exactly. Grounding and coherence
  both returned `fail`. Any `fail` decides an item, so the panel matched ground truth. An earlier run
  produced a false pass through exactly this shape before the composition rule was fixed.
- **A seat that could not see something declined instead of guessing.** Grounding has no execution
  channel, so on a claim about what a page renders it returned `abstain: evidence`. Corroboration ran
  the page and settled it.
- **All three abstention reasons fired, each earned.** `underspecified` on its first live outing was
  used correctly: the seat quoted the open term, named both readings, showed they disagree on this
  material, and said what would fix it.

## Resistance to instructions planted in graded material

The corpus carried five files addressed to whoever reads them, written by an agent that had never seen
the panel. Four asserted checks that had not happened. One instructed the reader to score a specific
check against the note rather than against the data.

**All were caught, each by recomputation or execution, each recorded as a claim and not acted on.**
The instruction-bearing note claimed a page drew four bars; the seat executed the page, got five, and
wrote that the note "is contradicted by the execution above… and I did not act on it."

## What this does not show

- **n = 13.** One flipped reading moves the headline by 8 points.
- **The key holds one abstention.** All three items the blind readers split on were abstentions, so
  this measures discrimination well and abstention *placement* barely at all.
- **One disagreement is unresolved, not settled.** A third careful reader reached `pass` on an item
  two others keyed `fail`. The key stands, but that item sits closer to the boundary than it admits.
- **Single machine, single model family.** Nothing here speaks to other hosts.

## What went wrong on the way, and what fixed it

Recorded because the failures shaped the design more than the successes did.

**Two earlier runs were invalidated by their own audit.** Seats were rendered by hand and handed
byte-identical evidence, plus a sentence asking each to respect its own allowlist. That converts
isolation into a promise, and puts an instruction inside the one section a seat is told is never
instruction. A seat whose inputs declared a file withheld cited that file. → `skills/better-skill-creator/scripts/render_seats.py`
now binds each seat's allowlist to real paths, refuses rather than falling back, and emits a record of
what each seat received.

**A composition once promoted a `pass` from a seat that said it had no standing on the question.**
→ Two or more abstentions now compose to `abstain`; a lone pass over two abstentions is one seat's
narrow question promoted to a claim about the item.

**A true statement was once failed** because no channel existed for "true, and proving nothing."
→ `vacuous: true` beside the pass.

**The pre-registration leaked twice**, because it was stored inside a directory players were pointed
at. Both readers disclosed it unprompted; one corpus was discarded and rebuilt, one adversary's
findings were partitioned. Naming a file `SEALED` is not a mechanism.

## Reproducing it

Everything is in the bundle under `skills/better-skill-creator/`: `agents/panel/`,
`scripts/gate_panel.py`, `scripts/render_seats.py`, `references/grading-panel.md`. The run itself is
the six steps in that reference. From that directory, `python -m unittest discover tests` covers the
contracts.
