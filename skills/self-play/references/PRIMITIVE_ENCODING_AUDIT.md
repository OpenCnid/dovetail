# Primitive Encoding Audit — five verified findings

**Status: FINDINGS ONLY — recorded July 19, 2026. Zero-paid,
session-layer, nothing built, no ratified record amended.** Every item
below is a verified statement about bytes currently in the repository.
Each names a correction that is an **owner act by dated entry**; this
record performs none of them. Where a finding bears on a ratified
record ([`RECONCILIATION.md`](RECONCILIATION.md),
[`JUDGE_COMPOSITION_GAME.md`](JUDGE_COMPOSITION_GAME.md), RESEARCH_MAP
§9's adoption bounds), the ratified record continues to govern until
the owner amends it.

**Provenance.** Produced by a derivation game played July 19, 2026 —
players: the owner (Cnid), the collaborator (M. Murphy), and Claude —
in which each round bound to one real variable at a `path:line` rather
than an invented scenario. The game's *design* output (a signed-ternary
standing axis, user-gated ratification, and the reading that the
promotion machinery is a findings recorder plus a user gate) is
collaborator direction plus session derivation, is **not** recorded
here, and is not ratified anywhere. This record is confined to what was
verified against bytes.

**Read this with** [`COMPOSITION_FROM_PRIMITIVES.md`](../../architecture/COMPOSITION_FROM_PRIMITIVES.md),
which states the principle these findings instantiate. That record
diagnosed the failure as documentation drift — prose describes the
primitive, machinery encodes an instance. Findings 1–3 show the
machinery additionally **discarded** the primitive, while implementing
a record that specified it.

---

## Verification

Every finding is re-checkable. Run the command; do not rely on this
record's compression of the result — that is the derived-source
substitution this program has already paid for twice
(`CODE_MEDIATED_TEXT.md` §2.9, `AMBIENT.md` 18).

## Finding 1 — `orientation` is specified in a ratified record and absent from the engine

S10's schema
([`FOUR_JUDGE_BASIC_MODEL.md`](FOUR_JUDGE_BASIC_MODEL.md)) gives every
judge a seven-field orientation block: `evidence_standard`,
`uncertainty_posture`, `temporal_horizon`, `stakeholder_scope`,
`reversibility`, `contradiction_sensitivity`, `abstention_boundary`.
[`RECONCILIATION.md`](RECONCILIATION.md) specifies it four times, once
per judge (lines 127, 178, 229, 285).

The engine has no representation of it. `ComposedJudgePrompt`'s
`definitionSection` carries `role`, `claimModes`, `qualifiedParameters`,
`taxonomy`, `requiredAssumptions` — and no orientation field
([`judge_intake_prompt.ts:61`](../../../src/core/graph/judge_intake_prompt.ts:61)).

```sh
grep -rn "orientation\|evidence_standard\|uncertainty_posture\|abstention_boundary\|temporal_horizon\|stakeholder_scope\|contradiction_sensitivity" src/ scripts/ --include=*.ts
# only hit: alias_resolution.test.ts — "pair orientation", unrelated
```

**LARGELY WITHDRAWN — July 20, 2026, same session.** An adversarial
debate probe broke this finding on two independent grounds, both
verified against bytes:

1. **The modal claim was false.** The original read: *"Because no code
   references it, no drill can detect its absence."* Drills in this
   repository assert over **file text**, not the import graph —
   `scripts/test_judge_convocation.ts:725-742` `readFileSync`s ten
   `src/rlm/*.py` files and `src/config/schema.ts` and token-scans
   them, none of them imported by the code under test. A drill
   comparing `definitionSection`'s field set against `RECONCILIATION`
   §2's is constructible from idioms already in the file this finding
   named as the enforcement home. "Can" was asserted over a whole
   surface from a property of one sub-surface.
2. **The absence is arguably correct.** `RECONCILIATION` §7.1
   (Composition supersession — dated entry, July 19, 2026) rules that
   *"judges, their registry selections, **orientations**, closed
   taxonomies, names and anchors all compose per context at ceremony
   time,"* and reads §1/§2 as **one composition instance**. Orientation
   *values* are therefore precisely what must not be schema-encoded.
   The engine declining to encode them is this session's own principle
   working, not a divergence from it.

**What survives, narrowed:** `definitionSection`
([`judge_intake_prompt.ts:61`](../../../src/core/graph/judge_intake_prompt.ts:61))
has **no slot** for a composed orientation. If orientation composes at
ceremony time and is load-bearing, the composed prompt needs somewhere
to carry it, and there is nowhere. That is a gap about the *invocation
path*, not about a ratified record being ignored.

**Also unverified in the original:** `manifestSchema` requires
`rubricSha` and `anchorSetSha` as drill-pinned 64-hex byte-pins
([`judge_panel.ts:198`](../../../src/core/graph/judge_panel.ts:198)).
Whether those cover a composed orientation was never checked before
this finding asserted the engine "has no representation of it." The
guard-don't-read mechanism proposed elsewhere in this session as
unbuilt may already partly exist.

**Owed:** nothing on the original framing, which is withdrawn. The
narrowed gap is a design question for the ceremony's invocation path.

## Finding 2 — the four registries do no computational work

S10 calls the registries the primitive: *"These are parameters, not
rules. Their implementations, weights, thresholds, and composition
operators can remain open."*

In the engine `qualifiedParameters` is
`z.array(z.string().min(1)).min(1)`
([`judge_intake_prompt.ts:65`](../../../src/core/graph/judge_intake_prompt.ts:65))
— free strings, no enum, no validation of the registry prefix.

`registryEntry()`
([`judge_panel.ts:132`](../../../src/core/graph/judge_panel.ts:132))
splits on `/` only, returning the `registry.parameter` half. Nothing
anywhere splits on `.` to recover the registry name:

```sh
grep -rn "split('\.')\|indexOf('\.')" src/ --include=*.ts
# only hit: src/core/repository/paths.ts:107 — filename basename, unrelated
```

Kinship comparison (`judge_panel.ts:524`) therefore operates at
`registry.parameter` granularity. The four plane names —
Emotional/Logical/Sensorial/Ethical — are a prefix convention inside an
unvalidated string. They are never extracted, compared, or gated on.

**Owed:** a decision on whether the registries are load-bearing. If
they are, they need a representation. If they are a lens — RESEARCH_MAP
R-31 already records that expandable registries are *"counterexample-
proof by construction — the mark of a lens, not a defect"* — then no
gate should ever be described as resting on them.

## Finding 3 — AB-7 has no enforcement code

AB-7 (RESEARCH_MAP §9) keeps the non-epistemic registries out of
epistemic questions. `RECONCILIATION.md:120` carries
`emotional: []  # src: AB-7`.

```sh
grep -rn "AB-7\|AB_7" src/ scripts/ --include=*.ts
# no results
```

The bound holds because the four authored role definitions happen to
select no emotional or ethical parameters. Given finding 2, nothing
could enforce it: a composed judge selecting `emotional.affect/reported`
would pass every check in the system.

**WITHDRAWN — July 20, 2026, same session. This finding tested the
wrong sentence.** AB-7 appears at
[`RESEARCH_MAP.md:595`](RESEARCH_MAP.md) as a table row whose bytes are:

```
| AB-7 | **Two planes ship first**; a new plane requires a governance question no existing plane answers, plus its own drill sections | R-17, parent §2.1 |
```

**Correction to this withdrawal, July 20, 2026 — a second probe caught
a fresh error inside it.** An earlier version of this paragraph called
that row *"AB-7's ratified text."* **It is not ratified.**
`RESEARCH_MAP.md` declares its own standing in its first nine lines:
*"Status: RESEARCH SYNTHESIS — PROPOSAL. Nothing in this document is
implemented, measured, promoted, or accepted"* and *"Tier-3 standing:
none."* The adopted locus of the plane rule is
[`EPISTEMIC_SUPPORT.md`](../../architecture/EPISTEMIC_SUPPORT.md) §1.1,
which names *three* planes and ends the requirement with a scope
limiter this record twice dropped: *"before any consumer reads it."*
The earlier version also quoted the row with three byte defects — a
terminal period that exists nowhere in the source, stripped `**`
emphasis, and the omitted origin cell — under the word "reads", in a
house whose rule 15 adjudicates quotation at the byte level.

**So the correction for derived-source substitution itself committed
derived-source substitution**, one paragraph after naming the failure
class. The honest counter, recorded because it is the strongest reply
available: `EPISTEMIC_SUPPORT.md:12` incorporates AB-1…AB-11 by
reference into the adopted record, which may confer ratified standing
on the bounds notwithstanding the host document's header. That question
is open and is not resolved here.

The row is a **plane-admission procedure**, not a registry allowlist. The
"keep Emotional and Ethical out of epistemic judging" reading this
finding attacked is downstream gloss (`RESEARCH_MAP.md:187`,
`FOUR_JUDGE_DESIGN.md:304`, `RECONCILIATION.md:120`). Asking whether a
plane-admission procedure has enforcement code is a different question,
and this finding never asked it.

**This is derived-source substitution** — acting on a compression of a
governing record instead of retrieving the record
(`CODE_MEDIATED_TEXT.md` §2.9, `AMBIENT.md` 18). Committed inside an
audit whose subject is encodings drifting from the records they
implement, by an author who had cited that failure class twice in the
same session.

**A second defect in the method, independent of the first:** grepping
for a bound's *label* does not test for its *mechanism*. AB-9 is
enforced in this repo by import-graph assertions that would keep working
with every occurrence of the string "AB-9" deleted
(`scripts/test_judge_intake.ts:261`, `scripts/test_judge_panel.ts:213`,
`:220`). A label-absent grep cannot distinguish "no mechanism" from
"mechanism under another name."

**Owed:** nothing on this framing. The open question it should have
asked — whether the plane-admission procedure is enforced, and whether
`judge_panel.ts:464-470`/`:542` already function as a partial registry
gate — is untouched and unexamined.

## Finding 4 — a promoted ledger row depends on a merit-refused row

[`JUDGE_COMPOSITION_GAME.md`](JUDGE_COMPOSITION_GAME.md) §7 (The final
ledger), row 1: *game-target spec* — **promote**, carrying
*"record-fit routes through the priority declaration (keystone)."*

Row 6: *examples have no primacy beyond Trellis* — **merit refused
(typed); grounded declaration**, carrying *"keystone flag."*

Row 6 is the keystone row 1's note points at (it is the only
merit-refused row carrying the keystone flag; row 7 is merit-refused
without it). So a promoted item's record-fit routes through a
declaration the same ledger declined to promote.

This is not necessarily a wrong disposition — the §6 grammar has no way
to express a promotion whose support runs through a user declaration,
so the dependency was recorded as a carried note and the note was
honoured. The finding is that **the grammar cannot type it**, and a
carried note is not machine-checkable.

**Owed:** nothing corrective to the ledger. The gap belongs to the
disposition grammar, and is the strongest argument in the program's
own record for extending it.

## Finding 5 — the abstention vocabulary encodes an axis the claim-mode vocabulary lacks

`abstainReasons` is `['evidence', 'jurisdiction']`
([`judge_intake_prompt.ts:80`](../../../src/core/graph/judge_intake_prompt.ts:80)).
The two have different sources: jurisdiction-abstention is
engine-synthesized from a claim-mode mismatch
(`JUDGE_CONVOCATION_DESIGN.md` §3.5 — S10 layer 3 is engine-decidable,
zero spend); evidence-abstention arises at judging time when a seat
cannot reach what would settle the claim.

The consequence: **reachability has no representation in the
candidate's declared type.** A candidate declares a mode; nothing
declares whether what would settle it is reachable under the active
allowlist. GAME §7 row 8 (*"routine reproduction during own work"* —
`abstain(evidence)`, disclosed untestable-as-composed) is the case in
the record.

**Owed:** a decision on whether reachability is a declared property of
a candidate or a discovered property of a run. Either is defensible;
the current design assumes the second without recording the choice.

## Finding 6 — the third REPL type has no representation

The collaborator's description of the runtime (July 19, 2026) is *"a
REPL where facts, beliefs, and doubts live."* Facts and beliefs have
homes. The third does not:

```sh
grep -rn "doubt" src/ -i
# no results
```

What exists is a boolean with a label — `r.contested = true`,
`contestedReason`, `contestedAt`, `orphanedSourceIds`
([`entailment_detection.ts:280`](../../../src/core/graph/entailment_detection.ts:280))
and no epistemic defeat vocabulary:

```sh
grep -rn "rebut\|refut" src/ -i            # no results
grep -rn "defeat" src/ -i                  # 2 results, both ordinary English
# trellis_scaffold.py:78,425 — "would defeat the surface's purpose",
# "defeat the re-read"; prose in comments, not a concept in the design
```

A contest marks re-adjudicability; it carries no cited evidence, no
address, and no author, and it cannot itself be contested.

The consequence is that `-1` is **residual** — defined as the absence
of support rather than constructed as defeat. Any design in which a
panel emits signed findings and a user gates them needs somewhere to
put a finding; there is currently no such object.

**NARROWED — July 20, 2026.** A probe established that "the third REPL
type has no representation" overreaches, and that the grep is weak
evidence for it. The concept **is** represented, under a juridical
register rather than an epistemic one: `contested` / `contestedReason`
/ `contestedAt` across at least ten non-test `src/` files,
`DISPUTE_CYPHER` (`verification.ts:292`), and
`abstainReason: 'evidence'` with `judge_panel.ts:540`'s *"an unjudged
or undecidable belief holds maximal uncertainty."* This record's own §1
concedes as much — *"defeat machinery exists today"* — and the
`DOUBTS_WORKSPACE.md` §10 vocabulary proposal states the four
`alias_resolution.ts` call sites need no migration, which concedes the
existing code was already doing the work under another word.

**A lexical grep measures the probe's vocabulary, not the source
tree's concepts** — and the token chosen was the one word the codebase
had not adopted. What survives is narrower and unaffected: no
**first-class, addressable** doubt object exists — the machinery that
does exist carries no cited evidence, no address, and no author, and
cannot itself be contested.

**Owed:** nothing corrective. This is a gap, not a defect, and the
design response is proposed separately at
[`DOUBTS_WORKSPACE.md`](../../architecture/DOUBTS_WORKSPACE.md).

---

## The common root (this session's reading — not established)

Findings 1, 2 and 5 share a mechanism, offered as a reading rather than
a result:

**A code-mediated design encodes what is token-valued and silently
drops what is prose-valued.** `evidence_standard` takes a sentence; a
design in which the model never counts and never copies has nowhere to
put a sentence it cannot check. So orientation fell out between the
ratified record and the implementation, and nobody decided it.

The consequence, stated as the inversion:

| Layer | S10's status | What the engine did |
|---|---|---|
| registries | *the primitive* — explicitly open | free string, never parsed |
| orientation | the per-context composition surface | absent |
| roles | illustrative ecology | frozen enum + three-way parity pins |
| claim modes | *(collaborator, July 19, 2026)* a useful first vocabulary | frozen enum + three-way parity pins |

The two layers S10 presented as examples are the two the engine froze
hardest. The two it called primitive are decorative and missing.

**A candidate resolution, recorded as a direction and not a design:**
the engine need not read an orientation to guard one — that it exists,
that its bytes are hash-pinned, that the identical orientation reached
every seat claiming it, and that it was bound before the candidate was
seen. Chain of custody over prose rather than evaluation of prose. This
is unratified and unbuilt.

## What this record does not contain

The game also produced collaborator direction and session derivation
that are **not** findings about bytes: the signed-ternary standing axis
(`-1 | 0 | 1`), user-gated ratification with the qualifier carried in
the address, the meet rule for derived claims' hash kinds, and the
reading that the panel never moves standing. Those are unratified, are
not recorded here, and would each need their own proposal before
anything is built.
