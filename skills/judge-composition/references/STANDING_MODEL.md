# The Standing Model — how a claim is valued

**Status: RATIFIED as principle — July 20, 2026 (owner, Cnid, in
session).** This record states the standing model the derivation games
of July 19–20, 2026 produced and the owner ratified. It is ratified **as
direction and principle**; it authorizes **no build**. Two carve-outs
below (§3, §5) mark exactly where ratification stops and a separately
gated build begins — reading past them would repeat the
instance-promoted-to-frame failure this program has already paid for
([`COMPOSITION_FROM_PRIMITIVES.md`](../../architecture/COMPOSITION_FROM_PRIMITIVES.md)).

Companion record for the doubts tier this model's `-1` opens:
[`DOUBTS_WORKSPACE.md`](../../architecture/DOUBTS_WORKSPACE.md).
Governing composition law it extends:
[`RECONCILIATION.md`](RECONCILIATION.md) (dated pointer added there).

---

## 0. The derivation ground — Trellis' target function

**RATIFIED July 20, 2026.** Everything below derives from this, and
before July 19, 2026 it was undefined — `grep "target function"`
returned zero hits repo-wide, so every primitive derivation stood on an
ungrounded floor.

> **Trellis is a personalized composable expert system whose expertise
> is the user's data.** Not strictly a coding tool; not strictly a RAG
> system.

Stated by the collaborator (M. Murphy), owner-relayed July 19 and
owner-ratified July 20, 2026. Its immediate consequence is load-bearing
for the rest of this record: **the user is the domain authority by the
target function's own definition** — the system's expertise *is* the
user's data — which is why every place standing moves without a fact to
compel it, it moves by a **user gate** and not by the panel.

## 1. The signed ternary

**RATIFIED July 20, 2026 as the standing model.**

A claim holds one **standing**:

```
-1  |  0  |  +1
doubt | belief | fact
```

- **Mode, verdict and standing are one vocabulary at two times.** A
  candidate *has* a standing; a seat returns a *signed delta*; the
  resulting standing is that delta composed against the prior. The
  existing per-seat verdict enum (`clean | drawback | abstain`,
  RECONCILIATION §2) is the delta's sign — `+1 | −1 | 0` — not a
  separate object.
- **`-1` is constructed, not residual.** A doubt is a positive object
  (a defeater's finding grounded in facts), not the mere absence of
  support. Its tier is [`DOUBTS_WORKSPACE.md`](../../architecture/DOUBTS_WORKSPACE.md).
- **Corroboration, recorded because ratification followed it:** the
  three ledger rows of [`JUDGE_COMPOSITION_GAME.md`](JUDGE_COMPOSITION_GAME.md)
  §7 replay under this model with no verdict flipped, and the Sieve's
  independent `PASS | REVISE | HALT` grammar instantiates the same
  ternary with matching semantics (`+1 | 0 | −1`). This model was tested
  against unpicked hands before it was ratified, not argued into place.

## 2. User-gated ratification and the meet rule

**RATIFIED July 20, 2026 as principle.**

- **Submission is a vote.** A candidate the panel cannot dispute, that
  the user has submitted to the ceremony, is **ratified carrying a
  user-gated qualifier** — the qualifier meaning *only the user's
  authority stands behind it*. This replaces merit-refusal, whose defect
  is that it produces silence indistinguishable from "we never looked."
  There is no tie.
- **The qualifier lives in the address**, as a distinct hash kind — not
  as metadata propagated by discipline. Identity inside a hash-guarded
  chain, so the qualifier cannot decay.
- **The meet rule** (owner-accepted explicitly, July 19): a derived
  claim's hash kind is the **meet of its dependencies' kinds**. An
  inference citing one user-gated address and one corroborated address
  cannot mint a clean hash — the qualifier cannot launder itself in one
  hop.

The stamp mechanism (address layout, hash kinds) is a **build** detail,
gated below; the principle — user-gated ratification with a contagious,
non-decaying qualifier — is what is ratified.

## 3. The panel never moves standing — CARVE-OUT

**RATIFIED July 20, 2026 as principle. This ratifies the principle and
authorizes NO code removal.**

The panel **emits signed findings; the user gates whether standing
moves, in both directions**:

- a claim the facts do not reach → **user gates** (an unverifiable
  belief, or an unverifiable doubt / skeptical lens — both recorded as
  the user's, never ratified by the panel);
- a claim the facts refute → **the panel reports; the user gates** the
  demotion. The engine has no standing to overrule the user about the
  user's own domain (the Sieve HALTed engine auto-demotion on all three
  lenses, DOUBTS_WORKSPACE game-8 record).

**Consequence, and the carve-out.** If the panel never moves standing,
the promotion machinery reduces to **a findings recorder plus a user
gate**, and every disposition in the JUDGE_COMPOSITION_GAME §6 grammar
that *acts* (promote, merit-refuse) is really a user act the engine
records. **That reduction removes shipped engine surface.** This record
ratifies the *principle* that the panel is a recorder-plus-gate. It does
**not** authorize deleting or rewriting any shipped disposition code:
that is a bounded build under the usual authorization (owner dated
entry + drills + the paid-queue gate where a live run is involved).
Ratified principle; unbuilt reduction.

## 4. Claim modes are a first vocabulary, not a primitive

**RATIFIED July 20, 2026 as a reclassification.**

The six claim modes (`fact | inference | prediction | value | belief |
experience`) are **a useful first vocabulary** — the same status
[`JUDGE_COMPOSITION_GAME.md`](JUDGE_COMPOSITION_GAME.md) §1 records for
S10's eleven judges (collaborator statement, owner-ratified). They are
**not** a validated primitive partition of assertion-space. The
provenance clarification obtained for the judges in July 2026 was never
obtained for the modes; the house assumed, then pinned the assumption
three ways (the three-way parity pins,
[`PRIMITIVE_ENCODING_AUDIT.md`](PRIMITIVE_ENCODING_AUDIT.md) finding 5).

The primitive that replaces them is not a better list — it is the
**standing axis of §1 plus the applicability-by-locus mechanism** (a
claim's evidence locus; a seat's reachable locus; applicability =
non-empty intersection; DOUBTS_WORKSPACE §12.2). The applicability gate
currently keys on the six modes (`judge_panel.ts:464`); **re-deriving it
onto locus intersection is a build item**, not performed by this record.

## 5. What is ratified, and what remains gated

**Ratified (principle / direction):** the target function (§0); the
signed-ternary standing model (§1); user-gated ratification and the meet
rule (§2); the panel-never-moves-standing principle (§3); the
reclassification of claim modes as illustrative (§4).

**NOT ratified here — each a separately gated bounded build:**

- the address/hash-kind stamp layout (§2);
- the reduction of the promotion machinery to recorder-plus-gate,
  including any code removal (§3);
- the re-derivation of the applicability gate onto locus intersection
  (§4);
- anything requiring a **live** (paid) judge run, which stays behind the
  paid-queue gate (owner dated re-opening + per-run approval under the
  ≤$5 cap).

**Correct ≠ reachable, and correct ≠ built.** A green suite proves the
first only; ratifying the principle authorizes neither the build nor the
run.

## 6. Relationship to the records this extends

- [`RECONCILIATION.md`](RECONCILIATION.md) — its verdict model
  (`clean | drawback | abstain`) becomes the signed delta of §1; its
  merit-refusal disposition is superseded by §2's user-gated
  ratification. A dated pointer is recorded there; the enforcement
  tables (§5.1/§5.2) that record shipped behavior are untouched until a
  build changes the code they observe.
- [`JUDGE_COMPOSITION_GAME.md`](JUDGE_COMPOSITION_GAME.md) — its §6
  disposition grammar is reframed by §3 (the acting dispositions become
  user acts the engine records); its twenty rules bind unchanged. A
  dated pointer is recorded there.
- [`DOUBTS_WORKSPACE.md`](../../architecture/DOUBTS_WORKSPACE.md) — the
  `-1` tier; its §14 ratification is the companion to this one.

## Provenance

Produced by the derivation games of July 19–20, 2026 (players: owner
Cnid, collaborator M. Murphy, Claude). The standing half was corroborated
by unpicked ledger rows and the Sieve grammar; the doubts half
(DOUBTS_WORKSPACE) was empirically tested (13/14 flat-earth corpus
rejected). Ratified by the owner in session, July 20, 2026. Amended only
by dated entry, never by silent edit.
