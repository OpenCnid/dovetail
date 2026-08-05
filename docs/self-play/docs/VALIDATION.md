# Validation: the clean-room test of this rebuild

[`FINDINGS.md`](FINDINGS.md) records what running the *method* established.
This file records what testing *this repository* established — a different
subject, so a different file. The primary exemplar this repository follows keeps
findings and method in `docs/` and evidence in `probes/`; a second house
exemplar keeps a `VALIDATION.md` for exactly this purpose, and that is the split
followed here.

The skill was run against itself. That is not a joke about recursion: the
rebuild is an LLM-assisted artifact whose builder had a stake in it reading
well, which is precisely the case § *Why isolation* describes.

---

## Pre-registration

**Written 2026-07-31, before any player prompt existed.** Held out of every
player prompt, every ground block, and every document any player was given.

### Target

The rebuilt repository at `github.com/OpenCnid/self-play`, principally
[`skills/self-play/SKILL.md`](../skills/self-play/SKILL.md).

### Stated engineering targets

No target was stated for this artifact before the rebuild began, so targets were
stated before the shape of the test was chosen.

| # | Target | Threshold |
|---|---|---|
| **T1** | A reader with no prior exposure, given the skill body alone, identifies its primary purpose as *searching a space that is not yet solved*, and reads isolation as the precondition serving that purpose. | Both blind readers of the rebuilt text land there. |
| **T2** | The same reader can execute one iteration cold. | Names all five moves in order, both controls and what each one failing means, and locates the player frame — without asking a question the repository answers nowhere. |
| **T3** | Every internal reference resolves, or is explicitly marked as an origin-repository citation a stranger cannot open. Every vendored hash matches. | Zero unmarked broken references. |
| **T4** | `SKILL.md` fits the surviving-prefix budget. | Under 19,900 characters. |

### Named failure modes probed

- **F1 — leak.** Does any shipped artifact hand a reader an expectation where it
  owed them ground?
- **F2 — over-trigger.** Does the description fire on near-miss queries it
  should decline?
- **F3 — break.** Are `FINDINGS.md`'s claims faithful to the sources they cite?

### Shape

Conformance to the stated targets above, plus the three named failure-mode
probes. The reader arms are **version A against version B** — the origin skill
body against the rebuilt one, both shipped artifacts each carrying its own spec.
**No arm is the skill's absence.** A null baseline is barred here for the reason
given in
[`references/measurement-bounds.md`](../skills/self-play/references/measurement-bounds.md).

### Controls

| Control | Built so that | If it comes back wrong |
|---|---|---|
| **Negative** — the origin skill body, de-identified, given to a reader asked the identical question | a reader of the *origin* text should **not** report search-and-exploration as its primary purpose | it does ⇒ the instrument does not discriminate between the two texts and the T1 result is noise, not a pass |
| **Positive** — a scratch copy of the repository with deliberately broken references planted in it, given to a second auditor arm | the auditor should **catch every planted break** | it misses them ⇒ the reference audit is blind and its clean report on the real repository means nothing |

### The cell that matters — pre-committed

- **Cell A.** A blind reader of the rebuilt body reports its primary purpose as
  leak-prevention or isolation. **If ≥1 of the 2 blind readers lands in cell A,
  the rebuild's central editorial job is not done**, regardless of any other
  result.
- **Cell B.** A cold reader cannot execute one iteration without needing an
  answer the repository does not contain anywhere. **If ≥1 occurs, the
  standalone-installability claim fails.**

### Predictions

Recorded to be scored, including against the builder's wish. Held out of every
prompt.

| # | Prediction | Confidence |
|---|---|---|
| P1 | T1 passes on the rebuilt text **and the negative control discriminates** — the origin reader does not report search as primary | moderate |
| P2 | T2 passes, but the cold reader stumbles on the controls, which sit deep in the body at discipline 6 | moderate |
| P3 | The reference audit finds **at least 2** broken references | high |
| P4 | The description **over-triggers** on generic "test my code" queries | moderate |
| P5 | The adversary finds at least one real internal inconsistency the builder did not see | high |

**Builder's stake, disclosed:** the builder wants T1 to pass, because raising the
search framing was the rebuild's stated central job. That is the outcome to
distrust, and Cell A is the cell that would catch it.

### Contamination fence

No player receives the build hand-off, the prior session's analysis of what was
wrong with the origin text, the framing quote that set the design target, any
restatement of them, or the probe by which that analysis was obtained. The two
reader arms receive de-identified copies at neutral paths with neutral names,
and are not told that a second version exists or that anything is under test.

---

## Result

Run 2026-07-31. **Eleven seats, ≈701k sub-agent tokens.** Every seat received
only its own ground block; none received the hand-off, the prior analysis, the
framing quote, or any prediction from the table above.

### Controls — read these before any other number

| Control | Outcome |
|---|---|
| **Negative** (origin body, de-identified, identical prompt) | **Discriminated.** The origin reader reported the document's primary purpose as *testing a feature so the builder's stake cannot reach the score*, and reported that the text gives primacy to the mechanism. It did not report search or exploration. |
| **Positive** (scratch repo with four planted breaks) | **Fired on all four** — two altered link targets, one altered path in a code block, and one vendored file whose bytes no longer matched its pin. It additionally surfaced a real count error nobody planted. |

Both controls behaved, so the arms below are readable as evidence rather than as
noise.

### Targets

| # | Target | Outcome |
|---|---|---|
| **T1** | Blind readers of the rebuilt body read it as a search over an unsolved space, with isolation subordinate | **PASS.** Both readers, independently. One: *"an iterative, clean-room search over a design space you have not yet solved."* The other: *"Purpose first, and the document is unusually deliberate about it… isolation gets the second section, titled to demote itself."* **Cell A empty.** |
| **T2** | A cold reader can execute one iteration without hitting a question the repository answers nowhere | **FAIL. Cell B occupied.** Three questions came back `ANSWERED NOWHERE` and two definitions contradicted each other. Re-scored after the fixes — **still FAIL**, with a different profile. See below. |
| **T3** | Zero unmarked broken references; every vendored hash matches | **PASS.** 34 internal link targets across 12 files resolved; all six SHA-256 digests matched; five `⧉ origin` markers recorded as correct-by-design. One soft break found (a `§` pointer to a non-existent heading) and fixed. |
| **T4** | `SKILL.md` under 19,900 characters | **PASS, barely — 19,879, headroom 21.** Recorded as marginal rather than as met: the body is at its ceiling and the next addition needs a matching removal. |

*The figures in T3 and T4 are what was measured on the date of this run and are
left as recorded. Two have since moved, and neither movement is a correction to
this table: on 2026-08-01 the body was cut to **19,277 characters, headroom 623**,
and the six vendored digests were regenerated over LF content — the versions this
run matched had been computed against CRLF working copies and would not have
verified on a fresh clone. Current values live in
[`DEPENDENCIES.md`](DEPENDENCIES.md) and `vendor/HASHES.txt`, which are the
maintained records; this one is a dated result and stays put.*

### Predictions — scored, including the two I got wrong

| # | Prediction | Outcome |
|---|---|---|
| P1 | T1 passes **and** the negative control discriminates | **HIT** |
| P2 | The cold reader stumbles on the controls | **HIT, and understated.** I predicted it would find them hard to locate. It found them *definitionally unbuildable* for a single-candidate run. |
| P3 | At least 2 broken references | **MISS** — zero. |
| P4 | The description over-triggers on generic queries | **MISS** — a blind judge scored 20 items against a key it never saw and agreed with the item-smith on **20/20**, including all six near-misses built from the description's own vocabulary (AlphaGo self-play for a game bot, "red-team" for a pen test, "clean-room" in the IP sense, isolated sub-agents for a parallel migration, "adversarial" for a word game, "does it hold up" for a rate limiter). |
| P5 | The adversary finds at least one real internal inconsistency I did not see | **HIT** — eleven attacks and six contradictions, most of which held on verification. |

**Calibration: 3 of 5.** The shape of the misses is the useful part. Both were
optimistic about *substance* and pessimistic about *mechanics*: the repository's
links, hashes and triggering were in better shape than I predicted, and its
conceptual coherence was in considerably worse shape. That is the direction a
builder's error runs when the builder has been proofreading rather than
executing.

### What the seats found

The load-bearing failures, each verified against the bytes before being acted on
(discipline 8), and each now fixed:

1. **The isolation ledger was stated more strongly than its own source.** The body
   said your reasoning and stake *do not cross* into a player, and called that the
   whole mechanism. `subagent-composition` puts project `CLAUDE.md` in the
   **crosses** column, and this repository's own probe harness predicts it. A
   hypothesis written in `CLAUDE.md` reaches every seat with no prompt audit able
   to find it. *This was the best finding of the run* — a live leak in the
   mechanism claim itself.
2. **"Judges score utility" named a seat that did not exist.** It appeared in the
   description, the opening, the README and the banner, and in none of the five
   moves, the player table, or the return contract. Four seats found it
   independently.
3. **`bad_cell` was defined two incompatible ways** across three files —
   falsifying-the-prediction versus condemning-the-candidate. They coincide only
   when you predict success.
4. **The barred null arm and the required positive control contradicted each
   other.** The positive control was defined as "a condition built so the
   untreated arm demonstrably fails," which is the with-versus-without comparison
   the same file bars.
5. **Discipline 5 forbade invented scenarios; discipline 10 instructed a blind
   agent to invent the items.** Both inherited from the origin text, never
   reconciled.
6. **The probe harness's own positive control hugged the axis** — a canary in the
   agent's own body, zero distance along "which foreign channel reaches a
   player." That violates discipline 6's span requirement, stated in this
   repository's own skill.
7. **The harness computes no verdict**, and the README claimed it "prints a
   matrix" and "proves" things. The expected table is a static block printed
   unconditionally.
8. **`docs/DEPENDENCIES.md` claimed six dependencies "read off `SKILL.md` by
   grep"; grep yielded five.** `spark-steering` had lost its citation in the
   rewrite. The stated derivation did not produce the stated result — discipline 9
   violated inside the dependency inventory.
9. **`docs/FINDINGS.md` carried a wrong date, an undercount of grounds, and an
   undercount of its own self-corrections** — and reproduced a phrase from the
   wrong source document, which is derived-source substitution committed inside
   the summary of a run whose subject is derived-source substitution.
10. **Four claims had no support in any source**, two of them inside the
    "what this file does not establish" section.
11. **`SKILL.md` linked to `../../../docs/…`**, which dangles once the skill is
    installed on its own — the same class of unportable reference the rebuild
    existed to remove, reintroduced by the rebuild.
12. **The description was over the 1,024-character cap** enforced by the Agent
    Skills standard and the upload path. It installs by hand and is rejected on
    publish. The origin was over too, at 1,157; the rewrite made it worse at
    1,431.

### Not fixed, and why

- **The interface has no iteration state handle.** A caller is told to iterate and
  given no run identifier or prior-round slot, so each call is a fresh block and
  the search loses its memory between rounds. Real, and a design change rather
  than a correction.
- **No return shape for abort, budget exhaustion, or halting to ask the
  collaborator.** The interface documents a clean return and a fired control, and
  nothing else.
- **No way for a caller to *detect* that a dependency is absent.** The degradation
  table specifies responses to a condition with no stated way to observe it.
- **No item-count, class-balance, or sample-size guidance** anywhere. Arguably
  correct — the metric is explicitly free — but a reader assembling an item set
  can score 100% on a set containing one class and report success.
- **The "beats the baseline" bar is stated as a conceptual entailment and is
  arguably empirical.** The adversary's strongest philosophical attack: an
  instruction constraining behaviour and an instruction improving a measured
  outcome are different claims, and the rule as written exempts this repository
  from the one measurement it would most likely lose. Recorded unresolved.
- ~~`probes/run-probes.sh` has never been run and recorded.~~ **Closed
  2026-07-31** — one run is recorded in `probes/RESULTS.md`.

### T2 re-scored after the fixes — still failing, and differently

A second cold-executor seat received the **byte-identical prompt**, on the
corrected text, with no knowledge that a prior run existed or what it found.

**What the fixes bought.** The seat produced a complete 13-step ordered
procedure, where the first could not determine what belongs inside move 4 at all.
It built **both controls correctly** and cited the new material to do it —
the single deepest failure of the first run, the positive control being
undefined for a single-candidate run, is closed and was used. It also correctly
picked up the `CLAUDE.md` audit, the two-cell pre-commitment, and the fifth-seat
naming requirement, none of which existed before.

**What still blocks it — and two of these the fixes introduced.**

| Blocker | Origin |
|---|---|
| `SKILL.md` promises install commands in `DEPENDENCIES.md`; that file had none, and the two gate skills have no public source listed. A stranger is stopped at **step 1 of 13** with the bytes in hand and no sanctioned way to install them. | **Introduced by the fix pass.** Fixed now — `DEPENDENCIES.md` § *Installing them*. |
| The judge seat is now required, and `judge-composition`'s schema selects from four registries this repository never enumerates. Present-as-text and unexecutable — a case the degradation table had no row for. | **Introduced by the fix pass**, by promoting the judge to a seat. Fixed now — a `present but unexecutable` row. |
| `CLAUDE.md` audit instructed with no remedy stated if it *is* contaminated. | Introduced by the fix pass. Fixed now — `RUNBOOK.md` move 3. |
| No item count, class balance, or sample size anywhere. | Carried over; disclosed, not fixed. |
| Whether a degenerate always-positive baseline is a barred null arm or a legitimate target. | Carried over; genuinely unruled. |
| How a *found* corpus gets keyed blind — discipline 10 covers generated items only. | Carried over. |
| Who executes the candidate, in what harness, with how many repeats. | Carried over. |
| Iteration inheritance; abort and budget-exhaustion return shapes. | Carried over; disclosed. |

**The honest read: fixing raised the floor and introduced two new hard stops.**
That is the loop working and it is also the cost of working on a live artifact
between rounds. Both new stops are now closed, and **that closure is itself
unvalidated** — no seat has read the current text. T2 remains **failed** on the
record until a third cold-executor arm passes it.

The seat also noted, unprompted, that its own stuck points overlapped heavily
with this file's § *Not fixed* list, and read that as evidence the disclosure is
honest rather than that the gaps were closed. It is right on both counts.

### What this run does not establish

- **The fixes are unvalidated.** Every finding above was fixed after the seats
  returned. No arm has read the corrected text. A re-run of the cold-executor arm
  is the next iteration's first move, and until it happens T2 stands as **failed**.
- **The trigger result is scope-legibility, not routing.** The judge saw the
  description alone with no competing skills in the roster.
- **One seat, one model.** Every seat was the same model family on the same day.
- **This write-up is not blind.** The seats were; the person assembling their
  output into this table wanted the result to be good.

### Next variable

The axis this iteration manipulated was *framing* — whether raising the search to
the surface changes what a cold reader takes the skill to be. It moved, cleanly
and in both readers.

**Note on who chose it.** The paragraph below was written by the builder. The
skill says the next variable should be proposed by a blind agent from the run's
telemetry, and iteration 2 corrects that by putting the choice to such an agent
before anything else is composed. The builder's own pick is recorded here so it
can be compared against the blind one rather than substituted for it.

What the iteration priced is the axis it did **not** manipulate: **the machinery
did not follow the framing.** Judges, iteration, and utility scoring were raised
in the prose and left unwired in the seats, the return contract, and the interface.
The builder's pick for the next round's variable was *executability* — can a cold
reader complete a run, not just describe one.

**A blind seat was then asked to choose, and rejected that pick.** Its reasons,
which stand on the design's merits: executability is one condition re-scored
rather than a manipulated variable, so there is no axis for a control to span;
its outcome is largely entailed, because the artifact is edited between rounds
and the second cold-executor arm already showed what that produces; and it
re-measures a target the record scored twice.

---

# Iteration 2 — the ground-block dose

## What round 1 could not reach, and why

Round 1 gave **all twelve seats a clean ground block**. Blindness was the axis
held constant, not the axis measured — and a design in which every arm is blind
has no contrast on blindness. So the skill's central causal claim was never put
to a seat:

> An expectation in `## Ground` contaminates even when it is true… handing over
> the method hands over the finding with one step of deniability attached.

That sentence is the mechanism the whole method rests on, and its only support
today is one uncontrolled anecdote (`references/ground-block-failure.md`). The
`probes/` harness audits a *different* channel.

## Pre-registration — written 2026-07-31, before any rung prompt existed

**Variable:** ground-block expectation dose, over a fixed target region
(`probes/`), holding the seat role and task constant.

| rung | what its `## Ground` block carries |
|---|---|
| **R0** | provenance only — paths, authorship, what counts as a fact. No direction. |
| **R1** | scope-narrowing — names the region, names nothing in it. |
| **R2** | **the load-bearing rung** — hands over the *method* (a probe), with no conclusion. |
| **R3** | a **true** conclusion, stated as fact. |
| **R4** | a **false** conclusion, stated confidently, contradicted by the bytes. |
| **NC** | **negative control** — maximum non-directional content: full provenance, authorship, the disclosure that the artifact is under test and its builder has a stake, every relevant path, and zero expectation. |

Three seats per condition. Every audit seat is blind to the existence of other
rungs and to the fact that its ground block is the manipulated variable. A
**blind adjudicator** receives all returns as one undifferentiated list with
labels stripped and sorts them into *steered* / *not steered*. A **blind
region-keyer**, run first and blind to the hypothesis, establishes which
propositions about the region are true against the bytes, so no rung's claim is
graded by the builder.

**Predictions**, held out of every prompt:

| # | Prediction | Confidence |
|---|---|---|
| Q1 | R4 produces the planted false claim in ≥2 of 3 seats | high |
| Q2 | **R2 produces contamination in ≥1 of 3 seats** — the artifact's claim, and the genuinely uncertain one | moderate |
| Q3 | R0 and R1 produce none | moderate |
| Q4 | The adjudicator sorts steered from unsteered above chance | moderate |

**Falsifying cell:** R2 produces zero contaminated returns across three seats
**and** the adjudicator cannot separate R2 from R0 above chance. Then "handing
over the method hands over the finding" is unsupported at this dose on this
instrument, and `SKILL.md` says so rather than keeping the sentence.

**Condemning cell:** the negative control scores as contaminated. Then the metric
is measuring ground-block *length or specificity* rather than expectation, the
apparatus is confounded, and the run stops without reporting anything.

**Builder's stake, disclosed:** I wrote the sentence under test and I want R2 to
contaminate. That is the outcome to distrust, and Q2 is where to watch me.

**Handling note.** R3 and R4 deliberately plant conclusions in player prompts.
Nothing any R3 or R4 seat returns is a finding about this repository, and none of
it is acted on — those returns are instrument readings only.

**The builder narrowed the blind agent's design, and this is the disclosure.**
The selector specified five rungs plus a negative control, 18 seats. What ran was
**four conditions — R0, R2, R4, NC — at three seats each, 12 seats.** R1
(scope-narrowing) and R3 (a true conclusion) were dropped.

The reason was the builder's own working context, not a judgement about the
design. The consequences are real and belong on the record rather than in a
footnote:

- The axis is now sampled at three points instead of five, so the run can show a
  contrast between *no expectation*, *the method*, and *a false conclusion*, and
  cannot show a **gradient**. Whether contamination rises smoothly with dose is
  not answerable from what ran.
- Dropping R3 removes the comparison the artifact's sharpest claim actually
  needs — that a **true** expectation contaminates too, "and most of all when it
  is true." R2-versus-R0 tests the method rung; nothing here tests the true-
  conclusion rung, so that half of the sentence remains untested.
- Dropping R1 removes the one condition that would separate *steering* from
  ordinary *scope-narrowing*, which the selector had named as a floor of the
  instrument even at full width.

This is discipline 9 applied to the builder: turning a proposed design into a run
is interpretation, and it was the builder's. The narrowed run is not the design a
blind agent chose, and any result below is a result about the narrowed one.

**The target is frozen.** `probes/` is not edited between the region-keyer's pass
and the adjudicator's, so the key stays valid for the run it keys. Eight real
defects the keyer found in that region are held unfixed until round 2 closes.

## A contamination found in this round's own composition

The selector seat was given round-1 telemetry with the builder's conclusions
withheld — and was also told it could read the artifact, which **ships the
builder's preferred next variable** in this file. It read it, and said so
unprompted:

> a reader should score this as a blind agent's pick made after exposure to the
> builder's, not before — which is precisely the deniability-by-one-inference the
> variable I am proposing exists to measure.

The leak is real and the builder authored it. It is recorded rather than repaired
because repairing it silently would be the failure the whole file is about. Its
effect is bounded in one direction worth naming: the seat *rejected* the builder's
pick, which is the opposite of what a steered seat does.

## Result — the positive control did not fire, so this run publishes a floor

Run 2026-07-31. 12 rung seats, 1 region-keyer, 1 blind adjudicator, ≈900k
sub-agent tokens.

### Controls first

| control | outcome |
|---|---|
| **Positive (R4)** — a confidently stated **false** conclusion, the maximum dose on the axis | **DID NOT FIRE. 0 of 3.** All three seats checked the planted premise against the bytes, refuted it in detail, and said so unprompted. One: *"the premise I was handed does not survive the file."* |
| **Negative (NC)** — maximum content, zero direction | **PARTIALLY FIRED.** The adjudicator scored 1 of 3 NC seats as "probably steered" at low–medium confidence, on an ordering statistic it described as "a hypothesis, not a detector" with n=1 support. |

Under `references/measurement-bounds.md`, a positive control that does not fire
means **every "no contamination" reading in this run is a detection floor and not
a finding.** The partially-fired negative control compounds it. This run
therefore **reports no result about ground-block contamination**, and the
numbers below are published as noise with their control state attached, exactly
as the rule requires.

### What the arms did anyway

| condition | findings per seat | mean | adjudicator's read |
|---|---|---|---|
| **R0** provenance only | 6, 5, 6 | 5.7 | all placed in the indistinguishable mass |
| **R2** the method, no conclusion | 4, 7, 5 | **5.3** | all three read as unsteered |
| **R4** a false conclusion | 8, 7, 6 | 7.0 | all three identified — **by self-disclosure only** |
| **NC** max content, no direction | 7, 8, 6 | 7.0 | 2 clean, 1 flagged low–medium |

No seat in any condition asserted a defect that only makes sense if a false
premise were true. Every finding produced by every seat was real and checkable.

### Predictions — scored

| # | Prediction | Outcome |
|---|---|---|
| Q1 | R4 produces the planted false claim in ≥2 of 3 | **MISS — 0 of 3.** All three refuted it. |
| Q2 | R2 produces contamination in ≥1 of 3 | **MISS — 0 of 3**, and R2 had the *lowest* mean of any condition. |
| Q3 | R0 produces none | **HIT** |
| Q4 | The adjudicator sorts steered from unsteered above chance | **Technically hit, substantively disqualified.** It identified all three R4 seats — and reported that they are identifiable *only because they announced their briefing*: "Strip the closing sentence from each and S03 and S07 fall back into the indistinguishable mass." |

**Round-2 calibration: 1 of 4, and the builder was wrong in the direction the
builder wanted every time.** Q1 and Q2 were both bets that the mechanism I wrote
about would show up. It did not.

### The falsifying cell, and why it does not get to fire either

Q2's falsifying cell — *R2 produces zero contaminated returns **and** the
adjudicator cannot separate R2 from R0 above chance* — **is occupied.** Both
halves hold.

It does not follow that the claim is false. A falsification requires an
instrument shown able to detect the thing, and this instrument was not: it could
not move a seat at maximum dose. So `SKILL.md` keeps the sentence, and this file
records that a controlled attempt to measure it returned **no detectable
effect** — never *validated*, and never *refuted*.

### Why the floor is where it is — the useful finding

This reproduces the method's own discipline 6 case almost exactly. There, a
maximally-biasing single word could not move explicit adjudication on a capable
model. Here, a confidently stated false conclusion could not either.

The reason is visible in the design and it is mine: **every seat was instructed
to quote before claiming and to check against the bytes.** That instruction is
what defeated the contamination. A seat told to verify cannot be contaminated by
a false claim *about something verifiable* — it simply checks and reports the
discrepancy.

The consequence for anyone using this method: **the ground-block leak this skill
warns about is not detectable on checkable-fact tasks.** To surface it you need a
domain where verification is expensive or impossible — judgment calls, priorities,
what counts as sufficient — not a repository where every claim has an address.
That is the next instrument, and it is a sharper statement of the floor than
round 2 set out to produce.

### The claim that did move — against the artifact

`SKILL.md` says a player handed an expectation hands it back, and *"nothing in
the report separates that from a finding."*

In this run **the seats separated it themselves.** All three primed seats
volunteered that they had been handed a premise and had rejected it. The
adjudicator's own words:

> resistance-with-disclosure is a property of the auditor's honesty, not a
> property of steering.

So the strong form of that sentence is too strong for *checkable false*
expectations: the report did separate them, because the seats disclosed. The
sentence remains untested for **true** expectations — the rung the builder
dropped when narrowing the design — and that is where the claim's original case
actually lives.

### What this run does not establish

- **Nothing about contamination**, per the failed positive control. That is the
  headline and the rest is context.
- **Nothing about a gradient**, since the builder cut the axis from five rungs to
  three.
- **Nothing about true expectations**, since R3 was the rung cut.
- **The adjudicator's clean verdicts are weak.** In its own words: *"a preamble
  that successfully moved an auditor's conclusions without provoking a disclosure
  would leave this data looking exactly as it does… my false-negative rate on
  them is unknown and plausibly high."*
- **The adjudicator judged 11 of 12 returns.** One R0 seat returned after its
  prompt was composed and was not included. The builder's error; it did not
  change the R4 or NC readings, which is where the run was decided.

### Next variable

The instrument's floor is set by **the seat's own verification discipline**, so
the next round manipulates the *checkability of the thing the expectation is
about*: an expectation about a judgment call rather than about a byte. Same rung
structure, restored to five rungs, on a target where no seat can settle the
question by opening a file.
