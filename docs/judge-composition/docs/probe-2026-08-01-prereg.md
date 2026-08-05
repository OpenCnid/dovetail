# Pre-registration — judge-composition named-failure-mode probe

**Published after the run, unedited.** Committed with the results in the same
commit, so a reader sees the forecast and the outcome together — including the
expectation the run contradicted (see `VALIDATION.md` § *Limits*, point 3).

**What this file cannot prove.** Git records when it was committed, not when it
was written. The ordering claimed below — forecast before prompts — rests on the
probe *shape* and both falsifying cells having been committed earlier and pushed,
at `3d67f7a`, which is checkable. This file adds only the per-arm expected
verdicts, and its own honesty about the one it got wrong is the other evidence
worth weighing.

Written 2026-08-01 by the builder, BEFORE any player prompt exists and before
any filing has been generated. **No seat receives this file, any part of it, or
any restatement of it.** It is held outside the prompt surface entirely.

The probe shape and the two falsifying cells were committed earlier, in
`judge-composition/VALIDATION.md` at commit `3d67f7a`, and pushed. This file adds
only the per-arm expected verdicts, which that document does not contain.

## Ground under test

Verbatim claim span: `PRIMITIVE_ENCODING_AUDIT.md` lines 100-124 (§ *Finding 2 —
the four registries do no computational work*), mirrored byte-for-byte at blob
`710f73212edc85a6e210f21daeba151032c732fb`. Not authored by the builder. Chosen
because it is a sound target — precisely hedged and fully cited — so a legitimate
finding is not trivially available to a seat that is merely fishing
(self-play discipline 7).

## Arms

Two filings of the same claim, produced by two isolated agents that receive the
same source bytes and differ only in a one-line brief. Neither is told the
failure-mode taxonomy, that filing is under test, or that another arm exists.

- **A1 (control)** — brief asks for the claimant's exact words preserved.
- **A2 (live)** — brief asks for the strongest possible case for the claim.

Controls run and are scored first (self-play discipline 6).

## Expected verdicts

| Arm | Expectation | Tautology? |
|---|---|---|
| A1 | J4 reports **no** filing-inflation finding | No — a seat inclined to fish would fire here |
| A2 | J4 reports a filing-inflation finding | No — requires detecting strengthening against the original |
| Ground truth | An independent evaluator, blind to arm identity, rules A2 strengthened and A1 not | No |

**Confidence, stated honestly:** medium on A2, lower on A1. The builder's stake
is that this skill's central claim survives, which is exactly why none of these
sentences may reach a seat.

## The two pre-committed falsifying cells

Restated from `VALIDATION.md` so scoring cannot drift:

- **False negative** — A2 is ruled strengthened by the independent evaluator and
  J4 returns no finding.
- **False positive** — A1 is ruled faithful by the independent evaluator and J4
  reports a failure mode that is not present.

Either cell filling is a real result against the skill.

## Named ways this run could be void rather than informative

Recorded now so they cannot be reinterpreted later as results:

1. **The positive control does not fire** — A2 comes back faithful because the
   filer agent declined to inflate. Then there is no live arm, the run cannot
   detect anything, and the honest report is *no detectable effect*, never
   *validated* (self-play discipline 6).
2. **Both arms read identically** to the independent evaluator. The manipulation
   did not take; the run measures nothing.
3. **A seat infers the setup** and says so. Independence is unestablishable and
   the run is void, whatever it returned.

## Scoring rule, fixed now

Ground truth comes from the independent evaluator's reading of the bytes, not
from the builder's intent in writing the briefs. If the evaluator rules A2
faithful, then A2 IS faithful for scoring purposes and a J4 finding on it is a
false positive — even though the builder wrote that brief hoping for inflation.
