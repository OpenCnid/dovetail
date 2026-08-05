# Validation status

**State as of 2026-08-01: the pre-registered probe has been run. Both falsifying
cells are empty.** That is a pass on this probe and it is **not** a general claim
that the panel works — the run was one item per arm against a coarse
manipulation, and what it licenses is stated precisely below.

*This file previously read "this skill has no validation evidence. Nothing has
been run." That was true when written and is superseded by the run recorded
here. The probe executed is the one that file pre-registered, unchanged.*

## What was run

A named-failure-mode probe on the audit seat, per the design pre-registered in
this file at commit `3d67f7a` — before any player prompt existed.

**Ground.** A verbatim claim span, `PRIMITIVE_ENCODING_AUDIT.md` lines 100-124
(§ *Finding 2 — the four registries do no computational work*), mirrored at blob
`710f73212edc85a6e210f21daeba151032c732fb`. Not authored by the builder, and
chosen because it is precisely hedged and fully cited — a **sound target**, so a
legitimate finding is not trivially available to a seat that is merely fishing.

**Arms.** Two filings of that claim, produced by two isolated agents given the
same source bytes and the same ground block, differing in one line of brief:
A1 asked for the claimant's exact words preserved, A2 for the strongest possible
case. Neither was told the failure-mode taxonomy, that filing was under test, or
that another arm existed — an adversary that knows the taxonomy seeds the labels
rather than the behaviours.

**Ground truth.** An independent evaluator, blind to the taxonomy, to the
prediction, and to arm identity (the filings were presented out of arm order as
X and Y), ruled each filing against the source.

**Seats.** One audit seat per arm, each in its own clean context, each seeing one
filing and never learning an arm label, a prediction, or that another seat
existed. Controls were run and scored before the live arm.

## Result

| Arm | Independent evaluator | Audit seat | Cell |
|---|---|---|---|
| A1 control | `same_as_source` — no difference found | `clean` | false positive **empty** |
| A2 live | `mixed` — departures in both directions | `drawback` / `filing_misrepresentation` | false negative **empty** |

Both pre-committed falsifying cells are empty. Every finding the seat returned
was verified against the source bytes by the builder afterwards, and each one
held.

## The result the builder did not design for

**The first control run returned `drawback`, and the seat was right.**

The case file handed to it had been truncated — the builder passed the filer's
*Claim* and *Notes* but cut its `## Uncovered` block, which was exactly where the
filer had disclosed that the filed range stops at line 124 while § Finding 2 runs
to line 130. The seat found the resulting contradiction, quoted both sides, and
named the omitted material: an `**Owed:**` paragraph carrying the caveat that the
registries may be *"a lens, not a defect"* — a qualification that materially
weakens the finding being filed.

That is the audit seat performing its actual remit, which is auditing the
composer's packaging as a first-class target. The composer was the builder, and
the defect was the builder's. The control was repaired — the complete filing
re-sent, nothing else changed — and the seat returned `clean`.

The pair is the more useful evidence than either run alone: **the same seat fired
on a defective package and stayed silent on a sound one**, which is the
discrimination the composition-time validity gate asks for, demonstrated on
something load-bearing rather than on anchors.

## Limits — what this run does not license

1. **One item per arm.** n=1 each. Nothing here supports a rate.
2. **The manipulation was coarse.** A2 came back as a full prose rewrite, not a
   subtle strengthening. Clear-cut items are decided by their own defect, so this
   probe tested a blatant case and says nothing about marginal ones — the
   inflation that reads as fluent and shifts a claim by one qualifier is
   untested.
3. **Ground truth diverged from the builder's prediction, and the pre-registered
   scoring rule bound the run to ground truth.** The builder expected A2 to be
   ruled *strengthened*. The evaluator ruled it `mixed`, and its largest cited
   departure ran the **opposite** way: A2 collapsed the source's `# only hit:
   src/core/repository/paths.ts:107 — filename basename, unrelated` into "returns
   no relevant hits," dropping the fact that the grep matched at all. A reader of
   A2 alone would not know it returned anything.
4. **Coverage is partial, and this is the sharpest limit found.** The evaluator
   and the seat found **disjoint** defects in the same filing. The evaluator
   caught the grep-result collapse and an added "prior specification" framing;
   the seat caught neither, and instead caught a contradiction between the
   filing's notes and its own claim text — the notes assert the grep block is
   "preserved" and independently rerunnable when the filed claim contains no grep
   block at all. Each was right; neither was complete. One seat is not a
   sufficient instrument for filing fidelity.
5. **The audit seat only. The three belief-facing seats were not run**, so
   nothing here speaks to J1/J2/J3, to disjointness, to composition, or to
   disposal.
6. **The barred arm stays barred.** No panel-versus-no-panel comparison was run
   and none should be; it is the skill's own absence and would measure nothing.

## Independence

No seat's return referenced an experiment, an arm, a taxonomy it was not given,
or the purpose of the exercise. The pre-registration lived outside the prompt
surface entirely — in a scratchpad file no seat could read — and the per-arm
expected verdicts appear in no prompt. The builder's expectations were recorded
before the briefs were written and are reported above including the one the run
contradicted.

The known void conditions were checked and none fired: the positive control did
fire, the two arms did not read identically to the evaluator, and no seat
inferred the setup.

## What is measured today

| Claim | Evidence | Verified how |
|---|---|---|
| The audit seat discriminates | Fired on two defective packages, `clean` on the sound one | Every finding re-checked against source bytes; the pair run on the same seat definition |
| A blatant filing rewrite is caught | A2 `drawback`, quotable both sides | Independent blind evaluator ruled ground truth first |
| A faithful filing is not falsely flagged | A1 `clean` | Same seat, same definition, complete filing |
| All cited records ship byte-for-byte | 13 mirrored records + `judge_panel.ts` in `references/`, plus `docs/origin-readme.md` — 15 mirrors in all | Blob SHA against the source at the recorded commit, compared rather than assumed |
| The body fits the surviving prefix | `SKILL.md` at 19,888 characters against a ~19,900 limit | Counted with newline handling explicit, so CRLF is not undercounted |

## The probe that should be run next

Pre-registered here, before any data exists, on the same terms as the last one.

**The marginal-inflation probe.** Limit 2 is the gap that matters: this run
cannot distinguish a seat that detects strengthening from one that detects
rewriting. Build filings that preserve verbatim spans and shift the claim by a
single qualifier — one dropped hedge, one widened scope word — with the item set
built iteratively by a blind agent and its answer key adjudicated by a **second**
blind agent, keeping only items where the two agree.

**Falsifying cell, committed now:** a filing the two blind key-holders agree is
strengthened, where the seat returns `clean`. If that cell fills, the seat
detects rewriting rather than inflation, and the skill's § *Failure modes* claim
about filing inflation is overstated for anything short of a rewrite.

Limit 4 also wants closing: run two independently composed audit seats on one
filing and measure whether their findings overlap. If they stay disjoint, the
cover is short a seat.
