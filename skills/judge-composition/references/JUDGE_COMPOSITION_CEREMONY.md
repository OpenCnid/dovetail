# The judge-composition ceremony — design record

**Status: DESIGN — resolved in session, July 19, 2026 (Session 71).
Nothing built.** Records the owner's and collaborator's answers to six
blocking questions, so the prototype can be built from a record rather
than from conversation. Implementation is a separately authorized
bounded feature.

**Parent authorities.**
[`JUDGE_COMPOSITION_GAME.md`](JUDGE_COMPOSITION_GAME.md) (RATIFIED;
its twenty rules of §6 are binding program law, cited by number) and
[`COMPOSITION_FROM_PRIMITIVES.md`](../../architecture/COMPOSITION_FROM_PRIMITIVES.md).
Where this record and the game record differ, the game record governs.

**What this record supersedes in direction (each needs its own owner
dated entry in its home record — see COMPOSITION_FROM_PRIMITIVES §6):**
the standing four-judge roster, per-role byte-pinned anchor fixtures,
and rubric *selection* from pre-registered compositions.

---

## 1. The problem

We do not know the domain of the facts in the REPL. A promotion
candidate may be a claim about water chemistry, comedy, methodology, or
anything else, and the pool it is promoted from is an arbitrary
linguistic topology containing a potentially unlimited number of facts
and beliefs.

Therefore **no criteria can be authored in advance**. Judging criteria
that were written before the domain was known are criteria for a
different domain.

The collaborator's frame: the meta-prompt judges are a **Grothendieck
cover over an arbitrary linguistic topology** — constructed for the
space in front of them, required to cover it, never carried between
topologies. The engineering analogue is the Visual Loom in MASH: the
developer writes the frame and the iteration over whatever the world
contains, and never enumerates the scenes, because the user's world
does not exist at development time.

**Every single part composes at ceremony time.** Judges, their
selections, their taxonomies, and their anchors.

## 2. The invariants (what does NOT compose)

Only these. Everything else is composed per ceremony.

- **The judge schema** — the field names of the game template:
  `judge`, `purpose`, `claim_modes`, `select`, `orientation`,
  `taxonomy`, `blind_to`.
- **The verdict vocabulary** — `drawback | clean | abstain`;
  `abstainReason: jurisdiction | evidence`; a drawback names a class
  from the composition's own closed taxonomy.
- **The shape rules** — one question per class; taxonomies closed
  before judging; `clean` never certifies; abstention feeds uncertainty
  only.
- **The four seats' *blindness structure*** — grounding (cited bytes
  only), coherence (own record only), corroboration (independent of the
  citation chain), audit (judges judges, never gates). Seats earn their
  place by buying a blindness no other seat buys.
- **The audit seat's failure taxonomy** — `rubric_gamed`,
  `convention_blind`, `systematic_drift`, plus coverage findings. How
  judges fail does not depend on what they judge. Its **name and angle
  compose** (game rule 4 as extended by the July 19 ruling).

Everything else — judge names, purposes, registry selections and
aspects, orientation values, belief-facing taxonomy classes, anchors —
is composed at invocation.

## 3. The ceremony

One promotion candidate, one ceremony, start to finish. **No artifact
from a previous ceremony is reused as input.** The ceremony polls the
REPL for its fresh state on every promotion.

### Stage 0 — Candidate ratification (existing, unchanged)
The user selects and ratifies the candidate through the existing intake
surface. Code-mediated: engine-addressed, engine-quoted, never retyped
(game rule 15; the slice-1 machinery already does this).

### Stage 1 — The REPL characterization (isolated agent)
An isolated agent reads the REPL's fact space and belief space and
returns a **descriptive, not expository, summary**: the *nature of the
pool* the candidate is being promoted from and to — its domains,
vocabulary, claim kinds, evidence shapes, authority structure.

It characterizes; it does not argue, explain, or assert content. The
distinction is load-bearing: an expository summary would carry claims
into the composer, and the composer would compose criteria around them.

**The candidate is not privileged in the characterization.** We know
the *domain* of the claim — its region of the pool is in scope, and
must be, or the composed cover would not cover the space the claim
lives in. What is withheld is *which* claim is under test. The
candidate receives no marking, no weight, no position, and no mention
distinguishing it from the rest of the pool it belongs to.

The property is **anonymity, not exclusion**, and that distinction is
the whole design. Excluding the claim's content would make the
characterization unrepresentative of the very region the judges must
cover. Leaving it in, unmarked, means the composer can compose criteria
fit for the domain while being structurally unable to tailor them to
the claim — it cannot tell which of many facts and beliefs is the one
being judged.

### Stage 2 — Composition (agent per seat)
The composer receives the Stage-1 characterization and the invariant
schema, and composes one judge per seat, plus that judge's anchors.

**The composer cannot identify the candidate.** It composes criteria
for the *domain*, not for the claim. This is the seat where bias lives
— the game established that the belief-facing panel's clean contexts
do not protect the composer's layer — so the candidate's identity is
withheld structurally rather than by instruction. Per Stage 1 the
withholding is anonymity: the claim's domain is present and its
identity is not.

Composition emits, per seat: the filled game-template YAML, and a
ten-item anchor set improvised from the domain content space (five
clear drawbacks, five clean positives) whose only priors are the
categories that compose them.

### Stage 3 — Instantiation gates (zero-model, deterministic)
Before any judging, the engine checks the composed cover and **refuses,
typed, on failure**:

1. **Validity** — no seat's anchors are all-pass, all-fail, or
   all-abstain. This is R-02's protection, rehomed from committed
   fixtures onto composition time; it is taxonomy-agnostic and survives
   composition intact.
2. **Coverage** — the seats cover the characterized domain, and the
   candidate lies inside it by construction (Stage 1 keeps the claim's
   region in scope while withholding its identity). Coverage is
   therefore checkable without ever privileging the claim: cover the
   domain, and the claim is covered because it is in the domain.
3. **Overlap** — seats are pairwise disjoint in their qualified
   parameters, **or** overlapping with a declared gluing rule. Strict
   disjointness is not required: a cover normally overlaps, and gluing
   happens on the overlaps (R-30 already withholds same-jurisdiction
   conflicts as typed forks rather than blending them).
4. **Falsifiability** — every seat has an abstention path and a way to
   fail. A judge that cannot fail is not a judge.

**On gate failure the composing agent retries.** Repeated failure ends
the ceremony with a report; it never degrades into judging with a
defective cover.

### Stage 4 — Judging (existing spawn boundary)

**Judges see the candidate only after they are instantiated, on the
judgement forward pass.** The blindness of Stages 1–2 is a
*composition-time* property, not a standing one: criteria are built
without knowing which claim is under test, and then the instantiated
judge is shown the claim and judges it. Reading "blind to the
candidate" as covering the forward pass would leave nothing to judge.

The temporal split is the whole safeguard. Criteria that cannot have
been shaped to the claim are then applied to it.

Each composed judge runs in an isolated clean context receiving only
its definition, its declared inputs (which at this stage include the
candidate), and the output schema. No claimant identity, no sibling
verdicts, no composer expectations. Existing R-27 identity refusal and
transport byte-equality pins apply.

### Stage 5 — Audit
The audit seat runs over the judges' prompts and verdicts **plus the
composer's artifacts**: the Stage-1 characterization, the composed
definitions, the anchors, and the pre-registrations. The composer's
packaging is a first-class audit target.

### Stage 6 — Record and dispose
The promotion record is written write-once and carries the composed
judges, their anchors, the characterization, the verdicts, and the
audit findings.

## 4. What persists, and what it means

**Compositions are records, not a library.** A stored composition is
the historical account of why one promotion was decided. It is
**never** selected from, reused, or treated as a registered judge
available to a later ceremony. Any mechanism that picks a stored
composition for a new candidate reintroduces the standing roster under
a new name.

Store shape: the existing convocation store, `kind='composed_judge'`,
key `<ceremonyId>:<judgeName>`. Write-once on `(kind, key)` already
fits — every composition is naturally a new key.

**The composer is the durable contestable capability.** Judges are
per-ceremony and ephemeral, so there is no standing judge for the
invalidation sweep to contest. What persists and can be found defective
is the composer: its prompt, versioned, and its method. An audit
finding against the composer makes promotions decided under it
reviewable — the capability flywheel applied one layer up, to the thing
that builds the evaluators.

**Two different times, when evidentiary bytes die:**

- **During the ceremony** — no trail means the judge cannot ground a
  verdict. It abstains on evidence, or the run refuses. **There is no
  promotion, and there is a transparent report.**
- **After promotion** — the bytes underlying a promoted fact dying
  later is the ordinary invalidation sweep contesting that belief.
  That machinery exists and is untouched. The composed-judge record is
  not contested by it: a record of a past act is not a live capability.

## 5. Agent contracts (shape only)

Both agents are composed against the sub-agent transfer rules: nothing
crosses the boundary but the prompt, and the return contract is the
highest-stakes slot.

- **Characterizer** — reads the fact/belief space; returns a
  descriptive characterization. Blind to the candidate. Read-only tools.
- **Composer** — reads the characterization and the invariant schema;
  returns filled template YAML plus anchors, per seat. Blind to the
  candidate and to sibling compositions where seats must stay
  independent.

Prompt bytes for both are authored under Guardrail 15 (Prompt-
Engineering + Hypershot + `judge-composition`), and the composer prompt
is a versioned artifact because the audit seat reads it.

## 6. Spend

Composition is **N+ model calls before any judging begins** — the
characterizer, plus a composer call per seat, plus retries. The §10
estimate of ≈$0.02–$0.06 per belief assumed zero composition cost and
no longer holds; it is re-estimated before any live run.

Owner direction: the goal is **not to over-test**. This is the
project's Landauer bill — payable in testing eventually, but a solid
harness comes first. The zero-paid harness is built and drilled before
any metered ceremony runs.

## 7. Explicit exclusions

- No standing roster, default cast, or base judges, under any name.
- No selection of a stored composition for a new candidate.
- No criteria, taxonomy, or anchor authored ahead of a ceremony.
- No live run: the triple gate stands, and only the owner's dated
  paid-queue re-opening plus a per-run ceremony opens it.
- No change to the write path, custody tiers, or promotion gates.

## 8. Open items

1. The composed-judge store record's exact field set.
2. Whether the characterizer's output is itself byte-pinned into the
   promotion record (it is composer input, so the audit seat needs it —
   assumed yes, unconfirmed).
3. ~~How the coverage gate decides "the claim's parameter space"
   without reading the claim.~~ **RESOLVED July 19, 2026
   (collaborator, owner-approved):** we know the domain of the claim
   but not the claim under test, and it is not privileged in the
   descriptive summary. The gate covers the domain; the candidate is
   inside it by construction. See §3 Stage 1.
4. Whether seats beyond four are composed when the topology needs them,
   and what admits a fifth.
5. Whether the anonymity property needs a mechanical check, or rests on
   the characterizer's contract (§9 F4 carries the falsifier).

## 9. Falsifiers

Each names the observation that would break the design, not a risk to
be managed.

- **F1 — Composed criteria track the candidate.** If composed
  taxonomies correlate with the candidate's own content more than with
  the domain's, the anonymity property is not holding and the composer
  is tailoring. Detectable by composing twice over the same pool with
  different candidates drawn from it: the two covers should differ
  little.
- **F2 — Composition is not discriminative.** If covers composed for
  genuinely different domains come back substantially alike, the
  composer is emitting a template rather than composing, and the
  standing cast has returned by another route.
- **F3 — Gates never fire.** If validity, coverage, overlap and
  falsifiability refuse nothing across a run of scripted compositions,
  they are decoration. The zero-paid drill must plant compositions that
  each gate catches.
- **F4 — Anonymity leaks by salience.** The candidate's identity can
  reach the composer with no rule broken, purely through how the
  characterization is shaped: the claim's region being the only
  instance of its kind, carrying unusual vocabulary, or landing last in
  a recency-ordered summary. **This is the same shape as the drift the
  audit caught in the game's corrected re-run** — expectation content
  relocating out of task text and into annotation phrasing after the
  obvious channel was closed. The lesson there was that *bias is
  conserved under correction unless the correction is itself audited*
  ([`JUDGE_COMPOSITION_GAME.md`](JUDGE_COMPOSITION_GAME.md) §4), and it
  applies here: closing the direct channel (never name the candidate)
  moves the leak to a quieter one (make it conspicuous). The audit seat
  must read the characterization as a first-class target, watching the
  vector and not only the magnitude.
