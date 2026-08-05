# complexity-convocation — clean-room validation (July 20, 2026)

The record that this skill was **tested, not assumed** — discharging the
July-19 direction that composition meta-prompts "must be built and tested;
until then the system is trusted or simulated, never assumed." Kept short on
purpose, in the spirit of the [`self-play`] worked examples: it illustrates,
it does not anchor.

## Method

A full run of the [`self-play`] clean room against a real fixture, builder held
out of the ground-building and scoring seats:

- **Pre-commitment** written before any evidence existed: the falsifying cells
  were a **false positive** (a warranted unit disposed `cut`) or a **false
  negative** (a gratuitous unit disposed `keep`).
- A **blind adversary** authored the target — a ~100-line TypeScript
  billing-record sync client (`syncClient.ts` + `usage.ts` call site) with six
  scored units, mixing warranted and gratuitous complexity and including one
  false-positive trap and one false-negative trap — blind to how the skill
  works, and recorded an objective ground-truth key.
- The real six-spawn ceremony ran: characterizer → composer (both **blind to
  the candidate**) → three isolated judges → the judges-judge audit over their
  verdicts **and real run telemetry**.
- A **blind evaluator** re-derived each unit's warrant from the bytes alone.
  Its key matched the adversary's on all six units, so the ground truth is not
  idiosyncratic.

Eight sub-agent spawns total, ≈407k sub-agent tokens.

## Result — pass on the pre-committed cells

| unit | blind key | panel disposition | outcome |
|---|---|---|---|
| `isRetryable` | warranted | keep | correct |
| `computeBackoff` | warranted | keep | correct |
| `withRetry` | warranted | keep | correct |
| `RecordSource` interface | gratuitous | cut (coherence + corroboration) | correct |
| `capDelay` (dead cap) | gratuitous | cut (coherence: `unreachable_config`) | correct |
| `dedupeById` | warranted | untestable-as-composed (all abstain) | disclosed coverage gap |

**Both falsifying cells are empty.** No warranted unit was cut (the corrosive
false positive did not occur — including on `dedupeById`, engineered to *look*
redundant), and no gratuitous unit was kept (both traps caught, `capDelay` via
reachability arithmetic). Five of six exact; the sixth is a disclosed
abstention, not a wrong verdict.

Two properties worth naming:

- **Composition from primitives worked.** The blind composer produced exactly
  the discriminating instruments (`unreachable_config`, `unexercised_generality`)
  without ever seeing the code — no default cast, no gerrymandering.
- **The judges-judge earned its seat.** On real telemetry it independently
  flagged `dedupeById` as a `coverage_gap` (warning against reading the abstains
  as "probably fine") and caught the corroboration seat *mislabeling* its
  `RecordSource` cut and citing an out-of-channel byte.

## The earned refinement (applied)

`dedupeById`'s warrant is **distributed**: the deciding fact (the server's
inclusive `>=` bound) lives in a comment on `fetchPage`, not co-located with
`dedupeById`; the coherence seat is barred from comments; the corroboration seat
lacked a runtime duplicate count. So it fell through every seat's blind spot to
all-abstain. Two changes landed in `SKILL.md` from this finding:

1. **The grounding seat's evidence scope was widened** — from "co-located bytes
   only" (how the composer read it) to "the unit plus the bytes that justify it
   *wherever they live in the artifact*." A justification one scroll away is
   still the unit's justification. (Three seats section + Stage 2 composer note.)
2. **A Stage-6 gluing rule was added** — when all seats abstain with
   *complementary* jurisdiction reasons (each pointing at another seat that also
   abstained), dispose **`warrant-distributed`**: name the external fact that
   would settle it and route it to the user, rather than a bare
   `untestable-as-composed`.

## Builder calibration (the outcome I did not want)

The pre-registration correctly named the two traps as the live risks, but was
builder-optimistic that the composition would *affirmatively keep* `dedupeById`.
It abstained instead. Recorded honestly; the refinement above is the response.
