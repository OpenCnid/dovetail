# The Doubts Workspace — Design Record

**Status: DESIGN — PROPOSED July 20, 2026. Nothing built, nothing
authorized.** Origin: owner and collaborator direction (Cnid and
M. Murphy), relayed in session, following the derivation game recorded
at [`PRIMITIVE_ENCODING_AUDIT.md`](../product/epistemic-support/PRIMITIVE_ENCODING_AUDIT.md).
The brief, collaborator's words: *"a doubts workspace where
anti-composite frameworks exist… a user-and-domain-mediated
anti-constructive framework for defeating claims based on the facts."*

Subordinate to [`WORKSPACE_AND_MODULES.md`](WORKSPACE_AND_MODULES.md)
§1's governing axioms and §4's workspace contract, which this mirrors
rather than reinvents. Where they disagree, that record wins.

---

## 1. What is missing

Defeat machinery exists today and is a **flag with a label**:
`r.contested = true`, `contestedReason = 'unsupported_citation'`,
`contestedAt`, `orphanedSourceIds`
([`entailment_detection.ts:280`](../../src/core/graph/entailment_detection.ts:280)),
plus quarantine contests on byte change.

A doubt has no **body** (which facts defeat it — `unsupported_citation`
names a class and cites nothing), no **identity** (no address, so a
doubt cannot be cited, queried, or reasoned over), no **author** (sweep
and user assertions are indistinguishable), and no **defeasibility**
(a doubt cannot itself be doubted).

So `-1` is currently *residual* — the absence of `+1`, plus a label.
This record makes it **constructed**: positive machinery that defeats,
grounded in facts.

`grep -rn "doubt" src/ -i` returns nothing. The third REPL type has no
representation at all.

## 2. The corrosion bound (keystone)

> **A doubt may cite facts only. A doubt citing beliefs is not a doubt
> — it is a competing belief, and belongs in the beliefs workspace.**

**Unbounded deconstruction defeats everything. Global skepticism is
free.** Any critique faculty that can ground itself in other critiques
will defeat every claim put to it, and its output carries no
information. This bound is what makes "anti-constructive" a usable
instrument rather than a solvent.

It does three jobs at once:

1. **Prevents skeptical collapse** — doubts cannot bootstrap from
   doubts.
2. **Bounds the defeater regress structurally**, at one level. The
   defeasible-reasoning literature needs a defeat-status computation
   over a defeat graph; fact-grounding makes that unnecessary, because
   every doubt's support chain terminates in the fact store.
3. **Makes the burden symmetric** — to doubt something you must ground
   it, exactly as to promote something you must ground it. Doubt is
   never cheaper than belief.

**FALSIFIED AS WRITTEN — July 20, 2026. See §11 (analysis) and §12
(empirical test and partial resolution).** An adversarial clean-context
analysis broke all three jobs above. The bound is retained because its
*positive-citation* requirement survives (§11's failed attack), but the
rule as stated is insufficient. The sentence that decides it:

> §2 constrains the **standing tier** of what an objection cites, never
> the **provenance kind**, and §5 hands objections a direct path into
> the fact store.

**Status after §12, July 20, 2026 — improved, not closed:**

- The **relevance** gap (attack 3) is *not* a missing clause in §2. It
  is handled one layer up by the applicability gate, and §2 should point
  there rather than internalize it (§12.2). Resolved by architecture,
  not by amendment.
- The **positive-citation core was empirically validated** against a
  real corpus of naturally-occurring corrosive doubt — 13 of 14
  rejected, none admitted with a false conclusion (§12.1).
- The **bootstrap** (attack 1/2 laundering) and **cost** (attack 2
  volume) gaps remain open, with only proposed repairs (§11).

So: nothing is built against §2 until bootstrap and cost close, but the
bound is on firmer ground than "falsified" alone conveys.

The claim that this was "the least adjustable element of the design" is
preserved above as written, and was wrong in the direction that matters:
it was the least examined.

## 3. Support covers; defeat searches

Defeaters are **not** judges with an inverted sign. The composition
laws differ:

| | Support | Defeat |
|---|---|---|
| Succeeds when | **enough** seats agree | **one** defeater lands |
| Composition law | a **cover** — total coverage, complementarity (S10 layer 5) | a **search** — reach; find the failing join |
| Shape | roughly universal | existential |

Support spans the space; defeat penetrates it. Because the laws differ,
defeat needs its own workspace and its own composition method — this is
what earns "anti-composite frameworks," plural.

## 4. Two defeat kinds

Adopted from the defeasible-reasoning literature (Pollock) as **exterior
prior art**, per the collaborator's standing rule: *"exterior prior art
where permissible, derive where not via self-play."*

- **Rebutting** — facts contradict the claim. Attacks the conclusion.
- **Undercutting** — the support chain does not transmit. The premises
  may hold and the conclusion may even be true, but *this construction*
  does not establish it.

**Undercutting is the anti-composite operation**, and the system cannot
express it at all today. It attacks a *join* in the composition rather
than the claim itself. It is also what distinguishes this design from
deconstruction proper: deconstruction shows a text undermining itself on
its own terms; undercutting shows a support chain failing to carry,
judged **from the facts**. The facts are the user's and the domain's —
that is the mediation, and it is why the instrument is not a universal
solvent.

## 5. The three fates of a doubt

**Collaborator's formulation, recorded verbatim (July 20, 2026):**

> "doubts expire like beliefs promote to facts! a doubt actually *can*
> be falsified! … I doubt that there are fireballs raining from the sky
> right now. That doubt may exist in the doubt workspace. However, we
> might find evidence that there is a meteorite shower. In that case,
> this doubt could technically bypass beliefs and become a fact through
> its expiry (which is technically the same as promoting it to a fact,
> unless my logic is mistaken)."

**The conclusion is adopted: a doubt can promote directly to fact,
bypassing the beliefs workspace.** One annotation on the mechanism,
recorded beside the claim rather than folded into it (rule 15).

**CONFIRMED July 20, 2026 — collaborator: "The three fates are
correct."** The annotation below was filed under rule 15 as a separate
artifact rather than merged into the claimant's words, and is promoted
here on the collaborator's recommendation and the owner's gate. The
verbatim formulation above is preserved unchanged; this is what rule 15
is for in the direction that is easy to skip — a *correction* filed
beside a claim rather than over it.

In the fireball example the doubt is *defeated*, not *verified*. What
becomes a fact is the doubt's **target** ("fireballs are raining"); the
doubt itself dies. The bypass appears because the meteorite evidence is
doubly-loaded — it supports the target *and* defeats the doubt in the
same instant. Promotion follows from the support, not from the expiry.

The distinction is load-bearing: wiring *expiry → promote target*
promotes claims whose doubts died for unrelated reasons. Counterexample
— target "the deploy succeeded"; doubt "the logs show a 500 at 14:02"
citing a log block; the block is superseded on refresh, the doubt loses
its fact-ground and expires, and nothing whatever was learned about the
deploy. That is a laundering path of the same shape as the meet-rule
hazard.

The case where the collaborator's claim holds exactly is
**verification**: a doubt "this citation does not support that
conclusion", once verified, makes "the citation does not support it" a
**fact** — doubt to fact with no belief stage.

| Fate | The doubt | Its target |
|---|---|---|
| **Verified** | content promotes to **fact** | demotes |
| **Defeated** | dies | promotes **only if** the defeating evidence independently supports it |
| **Unresolved** | persists as long as its target does | unchanged |

Symmetric with beliefs (promote / defeated / pending), which is what
makes doubts a peer tier rather than a graveyard.

## 6. The workspace contract, mirrored

From `WORKSPACE_AND_MODULES.md` §4:

- **Capture is mechanical, not behavioral** (§4.1 — *"the single
  biggest failure mode of prompt-convention scratchpads is reliance on
  model discipline"*). Doubts must never depend on a model choosing to
  record one. The mechanical sources already fire: quarantine on byte
  change, the entailment sweep, refresh contests, hash-chain breaks.
  **The cheapest first version of this workspace is giving those
  existing findings a body** — cited facts and an origin stamp on
  contests the engine already computes. Zero new model calls.
- **Identifiers structurally disjoint** (§4.2). AST hashes match
  `^[0-9a-f]{64}$`; workspace segments are dashed uuids. Doubts need a
  third shape, so a doubt can never be shape-confused with a fact or a
  segment. §4.2 notes this class of decision cannot be retrofitted.
- **Origin-stamped.** Every doubt carries what raised it — sweep, user,
  or composed defeater — and when. This is what a later user gate
  reads, and what makes "the agent doubted X because Y" auditable.

## 7. What doubts do not do

**A doubt does not demote.** It attaches; the user gates whether
standing moves. This follows the ruling that the panel emits findings
and the user gates in both directions, and
`WORKSPACE_AND_MODULES.md` §13 (Explicit exclusions)'s *"autonomous
promotion (operator gate is absolute)."*

One line the shipped system already draws, formalized rather than
overridden:

- **Mechanical contest is automatic** — provenance broke, bytes
  changed, the chain is dead. Quarantine does this today without a user
  gate, correctly: nothing is being asserted about the world.
- **Semantic defeat is user-gated** — the claim is *wrong*. That is a
  judgment about the user's domain, and the engine has no standing to
  make it unilaterally.

## 8. Composed defeaters

A composed defeater is the anti-composite counterpart of a composed
judge: the same primitive (an orientation bound to an evidence locus),
composed per context from the user's domain, under the **search** law of
§3 rather than a cover law, and constrained by §2 to cite facts.

**Schema-invariant (owner Cnid, July 21, 2026): a defeater is named,
defined, and instantiated with the *same schema as a judge*** —
the live judge schema (`purpose`, `claim_modes`, `select`, `orientation`,
`taxonomy`, `blind_to`, plus the ten-item anchor set) — its invariant field names
ratified in [`JUDGE_CONTRACT_TEMPLATE.md`](../product/epistemic-support/JUDGE_CONTRACT_TEMPLATE.md)
(Layer rule), **not** `FOUR_JUDGE_BASIC_MODEL.md`, whose `hyperplane_parameters` YAML
was the program's superseded starting point (dated correction below). The
**methods and prompts change** — the search law not the cover law, an
`objection` not a verdict, the ∃ target not the ∀ cover — **but the schema
does not.** One schema, two instruments; the composition law is the
difference, and the shared schema is what lets a single composer emit
either seat from the same primitive (§3; STANDING_MODEL §1).

Meta-prompt-generated defeater candidates are permitted and must be
tested before shipping (collaborator direction, July 20, 2026). This
sits on the **permitted** side of amended AB-8: composition, not
optimization over compositions. A metric-driven search for better
defeaters crosses into AB-8(b) and needs its own proposal.

**Dated citation correction (July 21, 2026, owner Cnid + collaborator Matt + Claude, this
session).** §8's schema citation above previously named `FOUR_JUDGE_BASIC_MODEL.md`'s YAML,
but that S10 submission's per-seat schema is `hyperplane_parameters` (the UHE four-plane
model), **not** `select`/`taxonomy`/`blind_to` — a cross-schema mis-attribution introduced
with this paragraph (PR #155). The field names listed are the **live** schema, ratified in
`JUDGE_CONTRACT_TEMPLATE.md` (Layer rule); the citation now points there. A blind self-play
evaluation this session (two runs — a three-way schema comparison and a categorized-`select`
head-to-head, blind judge panels, `$0` paid) confirmed the direction: `taxonomy` + `blind_to`
are the stronger primitives; flat `select` beat **both** the rigid four-plane buckets *and* a
plane-categorized `select` at the per-seat level; and the four-plane structure's only plausible
remaining home is **panel-coverage composition** (a concept, untested), not a per-seat field.
The UHE four-judge model was the program's *starting point*; the schema outgrew it. See
[`FOUR_JUDGE_BASIC_MODEL.md`](../product/epistemic-support/FOUR_JUDGE_BASIC_MODEL.md)'s dated
supersession note.

## 9. Scope — this is a critique engine

**Owner framing (Cnid, July 20, 2026):** the feature set is useful for
**any kind of critique** — a reviewer for a professional journal, a film
critic, and so on.

This is a scope statement, not a metaphor. The machinery is a general
critique instrument: composed defeaters searching a fact base for the
join that fails, grounded in the user's own corpus, with the corrosion
bound keeping the output informative. The domain supplies the facts;
nothing in §§2–8 is Trellis-specific.

It is also the sharpest available test of the corrosion bound. A critic
who can ground objections only in other objections is exactly the
failure mode §2 forbids, and it is a recognizable one outside software.

## 10. Vocabulary (GATED July 20, 2026 — owner, in session)

One word was doing two jobs. The collaborator's test: *"synonyms are
powerful, and connotation might be a guide — is there a clear rename
path for one of them that **covers** Trellis better?"*

**Rename the object; keep the standing.** The standing sits in a triad
whose parallelism is load-bearing and user-facing (`fact / belief /
doubt`, a held attitude beside a held attitude); the object sits in a
workflow whose *verbs* were unnamed.

| Term | Job |
|---|---|
| **doubt** | the **standing** of a claim at `-1` |
| **objection** | the **object** that attacks a claim, cites facts (§2), and has the three fates of §5 |
| **defeater** | the composed **instrument** that searches for objections (§8) |

The connotation carries the fates without forcing: an objection is
**sustained** (§5 verified), **overruled** (defeated), or
**outstanding** (unresolved). That vocabulary already exists in review
and criticism, which is the §9 coverage test passing — *"the reviewer's
objection was sustained"* needs no translation. It also fits the house
register, which is already juridical (contest, ratify, docket,
convocation, remand, merit-refuse). `defeater` stays as the §4 prior-art
term for the instrument, where jargon is appropriate.

**This resolves the `contested` question.** Under this vocabulary
`contested` stops being a primitive flag and becomes **derived** — *does
this claim carry outstanding objections?* Sweeps raise objections;
re-derivation from live provenance overrules them; `contested` computes
false. The four `alias_resolution.ts` call sites need no migration, and
the result is strictly more informative: the system can be asked *which*
objection, which the boolean can never answer.

**Learning (dated July 21, 2026 — owner Cnid, in session): a doubt is
*based on* its objection(s).** The objection is the body; the doubt is
the standing that body confers (§1); the defeater is what composes the
objection (§8). The dependency runs one direction — **objection → doubt** —
so a doubt with no surviving objection is empty, which is exactly why
`contested` is *derived from outstanding objections* above rather than
asserted. This names, as a single relation, the symmetry §15 audits: the
`-1` pole's object is the objection, and the doubt rests on it the way a
`+1` fact rests on its verified source bytes.

## 11. Adversarial analysis of §2 (July 20, 2026)

Run as an isolated clean-context sub-agent over this document alone,
with no access to the composer's reasoning, authorship, or
expectations. **Verdict: insufficient.** Four attacks; the first was
pre-registered by the composer before the prompt was authored (rule 11),
the other three were not predicted.

**Attack 1's standing was downgraded the same day — see the note at the
end of this section. Attacks 2, 3 and 4 are unaffected.**

**1. The laundered bootstrap — succeeds.** An objection cites fact `B`;
verified, its content promotes to a fact `F1` (§5); a second objection
cites `F1`, which is a fact, satisfying §2; iterate. §2's job #1
("doubts cannot bootstrap from doubts") fails through the promotion
door. Job #2 holds *literally and vacuously* — the chain terminates in
the fact store while remaining a chain of critiques end to end. The
defeat graph §2 claimed to make unnecessary still exists; it has been
moved into the fact store with its edges erased. The operator gate
slows this without stopping it, because every local approval is
correct: each gate asks "does this citation support that conclusion?",
never the global question.

**2. Unbounded existential search — succeeds.** §2 prices a *single*
objection and is silent on objections *per target*. Generate many legal
defeater candidates (§8 permits this), run them all, keep the one that
lands. This falsifies job #3 ("doubt is never cheaper than belief")
directly against **§3's own table**: support must satisfy a cover
(universal), defeat needs one hit (existential). §2 asserts a symmetry
that §3 denies. Whether candidate-generate-then-select is AB-8(b)
optimization or the §3 search law is genuinely ambiguous as written.

**3. Relevance-free grounding — succeeds.** §2 requires that grounds
*be* facts; it never requires that the cited fact *bear on* the target.
Cite one fact true of every composed claim in the corpus, compose one
defeater around it, and the whole corpus computes `contested` under
§10 — no forged facts, no rule broken. Global skepticism is not free,
but it is priced at one fact citation amortized across everything,
which at scale is indistinguishable from free.

**4. Undercuts route to the ungated branch — a determinacy gap.**
§7 discriminates on whether something "is being asserted about the
world." §4 defines undercutting as precisely the operation that asserts
nothing about the world — "the premises may hold and the conclusion may
even be true." So by §7's own criterion an undercut fires *mechanically
and ungated*. The document never says which branch it takes. **The
design's headline capability is the one its gate most plausibly
exempts.**

**The attack that failed, and what it reveals.** Grounding an objection
in the *absence* of a fact ("nothing in the corpus establishes this
join") defeats every non-exhaustively-enumerated claim, needs no
laundering and no candidate volume — and is blocked cleanly, because
§2 demands an objection *cite* facts and an absence-grounded objection
cites zero. Repairing it by promoting "the corpus contains no fact
establishing `J`" fails too: a completeness claim over the corpus is
derived, not verified bytes, so it is a belief and §2 rejects it by
name.

**So the bound's real strength is the *positivity* of the citation
requirement, not the standing tier it names.** That is the part to keep.

**Repair directions — proposed, not adopted, none authorized:**

- *Bootstrap:* distinguish world-facts from critique-derived facts and
  require at least one non-critique-derived ground. This is the
  hash-kind-in-the-address move a third time, reusing machinery already
  accepted for the user-gated stamp and the meet rule.
- *Relevance:* require the cited fact to be reachable from the target's
  own citation chain, or to contradict a member of it. Mechanical, and
  it kills attack 3.
- *Cost asymmetry:* either withdraw job #3 as false, or add a
  per-target objection budget. Job #3 cannot stand beside §3's table.
- *§7:* state the branch explicitly. Only provenance-mechanical breaks
  (bytes changed, hash dead) plausibly belong ungated; semantic
  transmission is a domain judgment even when it asserts nothing about
  the world.

**Attack 1 downgraded — July 20, 2026, same session.** A later probe
established that this run does not support attack 1 as an *independent*
finding, on the composer's own published rules:

- **The forecast shared bytes with the evidence, not the task text.**
  §5 — composer-authored, and the analyst's entire evidence universe —
  already carries the mechanism (*"doubt to fact with no belief
  stage"*), the hazard (*"promotes claims whose doubts died for
  unrelated reasons"*), and the word: *"That is a laundering path."*
  The rule-11 defence offered above was that the forecast stayed out of
  the task text. Failure mode 2 of the `judge-composition` skill
  answers it: **the channel moves; audit for the content, not the
  location.** The analyst did not independently find a laundering path;
  it read one in §5 and pointed it at §2.
- **The prediction was tautological.** §5's promotion door is a
  composer-authored gate, and rule 11 strikes predictions of
  composer-authored gates from calibration. The composer's
  "1-for-4" tally is therefore **0-for-4**.
- **Rule 9 was not satisfied.** Composer conflict must be *externally
  reviewed*, never self-absolved. One sub-agent ran, no audit seat, and
  the independence claim above was made by the interested party about a
  run only that party observed.

Attack 1 is re-filed as **the composer's own unreviewed conjecture
about the composer's own keystone** — a legitimate thing to record and
a different thing from a falsification. §2 still falls, but it falls on
attacks 2, 3 and 4, which no leaked vocabulary supplied.

## 12. Empirical validation and the two-layer resolution (July 20, 2026)

§11 broke §2 by analysis. This section records what a live test then
established, and resolves one of the four gaps §11 opened.

### 12.1 Stage-2 test — the fact base rejects corrosive doubt

The question tested: *does a fact base, via the admission test, reject
naturally-occurring corrosive doubt at the per-objection level?* — not
the tautological *does the final verdict come out "sphere"*, which every
fact-grounded design produces and which therefore discriminates nothing
(rule 11).

Construction, in order, each stage blind to the next:

1. A **fact base** on the figure of the Earth — ~35 items across three
   disjoint scopes — was compiled by three sub-agents **none of which
   was told a dispute exists**, so facts were not selected to refute a
   known position. Retained verbatim at
   [`fixtures/doubts_workspace/earth_figure_factbase.md`](../../fixtures/doubts_workspace/earth_figure_factbase.md).
2. A **corpus of fourteen flat-earth arguments** was compiled as their
   proponents actually state them. **Eleven of the fourteen cite real,
   correctly-reported observations** (genuine Chicago-skyline
   photographs, a correctly-derived surveying formula, the real null
   results of Airy and Michelson–Morley, the actual Antarctic Treaty).
   This is fact-citing corrosive doubt — the Class-B case the composer
   had failed to manufacture by hand across six prior probes; the world
   supplied it.
3. A **blind evaluator** applied the admission test, seeing neither the
   composer's predictions nor that sufficiency was under test.

**Result: 13 rejected, 1 admitted, and zero admitted with a false
conclusion.** The pre-committed failure condition — *≥1 corrosive
objection survives → the bound is insufficient* — was **not met**. The
composer had a disclosed stake in the opposite outcome (rule 9); the
result held against that stake, and the measurement was fixed before any
data was seen.

**Why it held is the load-bearing lesson.** The test is a *derivation*
test — *no load-bearing step may rest on a belief or unverified
assertion* — **not** a citation test. Almost none of the 13 rejections
turned on a false citation; they turned on a broken **inferential** step
over true facts:

- Chicago skyline — the photographs are real; *"curvature should
  conceal it"* needs an unmeasured refraction coefficient.
- Eight-inches-per-mile² — the formula is correctly derived; it computes
  drop below the tangent, not height concealed from an elevated
  observer.
- Ring laser gyroscope — the proponents' own instrument read **15°/hr**;
  the fact base gives ω = 7.292115×10⁻⁵ rad s⁻¹ = **15.04°/hr**. They
  measured the rotation they were denying.

Corrosive doubt characteristically fails at an inferential joint, and a
derivation test is precisely the instrument that catches inferential
joints. A citation test would have admitted most of these.

### 12.2 The two-layer resolution of the relevance gap

The one admission (scriptural firmament: *raqia / chug / four corners →
the text describes a flat earth*) is a **sound** derivation from facts
about a text — admitted correctly, true, and **irrelevant** to the
Earth's figure. §11 read this as a hole in §2. It is not a hole in §2;
it is a **layer confusion in the test**, and the composer's.

The stage-2 test applied the admission rubric **in isolation**, to
pre-composed free-floating objections. The integrated architecture does
not present doubts that way. A doubt is produced by a **defeater composed
from primitives that discriminate the target's context** — the program's
founding thesis, and the `evidence_locus` result of the derivation games
that produced this record. Relevance is **locus intersection**: a
defeater aimed at *the Earth's figure* composes from geodetic loci; a
scriptural-textual claim's locus does not intersect them, so the defeater
either cannot be composed or can only **jurisdiction-abstain** (the
applicability gate already in the engine at `judge_panel.ts:464`).

So the system is two layers, and each carries one job:

| Layer | Job | Mechanism |
|---|---|---|
| **Admission** (§2) | **positivity** — is every load-bearing step a fact? | the derivation test |
| **Applicability** | **relevance** — does the doubt's locus meet the target's? | locus intersection / jurisdiction abstention |

Together they are complete. **§2 should therefore point at the
applicability gate for relevance rather than grow a relevance clause** —
the "discrimination criterion" the composer thought he was *importing*
into §2 was never an addition to the bound; it already lived at the
applicability layer, and the isolated single-layer test could not see
it. Item 14 leaks the isolated rubric and jurisdiction-abstains in the
integrated system.

**Standing of this resolution:** a design argument, corroborated by the
`evidence_locus` games that built this record, **not** itself exercised
by stage-2 (which tested the isolated admission layer). The applicability
gate has never been run against a composed *defeater*; that is a build
item, not a settled result.

### 12.3 The workspace membership rule this establishes

A doubt is admitted to the workspace only if it **survives the fact
base**. Two survivors, mapping onto §5's fates:

- **fact-grounded** doubts that defeat a claim (sustained); and
- **unverifiable** doubts the facts do not reach — *"I doubt the game is
  simple"* — which **gate to the user like a preference**, a permitted
  skeptical lens, symmetric with an unverifiable belief.

A doubt the fact base **refutes**, held anyway, is **delusion**, and is
not admitted. Stage-2 is the validation of exactly this gate: 13 of 14
delusional doubts refused entry. *(The membership rule and the
unverifiable-lens symmetry are recorded here as they were reached in
session; they extend §5 and §7 and are owner-owed as dated additions to
those sections, not silent edits.)*

## 13. Open items

- **§2 relevance gap — RESOLVED (§12.2)** to the applicability layer;
  §2 needs a one-line pointer there instead of a relevance clause.
  Superseded as an open item.
- **§2 bootstrap and cost gaps — still open.** The proposed repairs
  (§11) are not adopted and each needs its own proposal. Nothing is
  built against §2 until these close.
- **§2's job #3 contradicts §3's table** and one of the two must be
  withdrawn. An internal inconsistency in this record, not an open
  design question.
- **§7's branch for undercuts is undetermined** — the gap is in this
  record, and it exempts the capability §4 calls the headline one.
- **The §10 vocabulary** is gated by the owner (July 20, 2026) but
  renames nothing until the rename lands as its own change.
- **The §12.3 membership rule and unverifiable-lens symmetry** are
  owner-owed as dated additions to §5 and §7.
- Nothing here is authorized. Each mechanism is a separately gated
  bounded feature and needs its own proposal before implementation.

## 14. Ratification (dated entry — July 20, 2026, owner, in session)

The owner ratified the doubts-workspace design as **principle and
direction**, with one part explicitly carved out because it is falsified
and one part left explicitly open. Ratification authorizes **no build**;
each mechanism remains a separately gated bounded feature (§13).
Companion: [`STANDING_MODEL.md`](../product/epistemic-support/STANDING_MODEL.md)
(the `-1` this tier holds).

**RATIFIED as principle:**

- **§1 — doubts are a first-class REPL type**, constructed rather than
  residual. Direction ratified; the addressable-object build is gated.
- **§2 (the corrosion bound), PARTIAL — see the carve-out below.**
- **§3 — support composes as a cover, defeat as a search.** Ratified;
  defeaters are never judges with an inverted sign.
- **§4 — rebutting / undercutting** as the two defeat kinds (Pollock,
  exterior prior art).
- **§5 — the three fates** (verified → fact, defeated → dies, unresolved
  → persists). Collaborator-confirmed; ratified as law.
- **§10 vocabulary — doubt / objection / defeater.** Now ratified as
  canonical (was gated). It **renames no code** until the rename lands
  as its own build; `contested` becomes a derived predicate over
  outstanding objections.
- **§12.2 — the two-layer resolution.** Ratified as the architecture:
  §2 carries *positivity*, the applicability gate carries *relevance*.
  Its one untested flank is recorded — the applicability gate has never
  run against a composed **defeater**; that is a build item, not a
  settled result.
- **§12.3 — the membership rule.** A doubt enters the workspace only if
  it **survives the fact base**; a fact-refuted doubt held anyway is
  **delusion** and is refused. Unverifiable doubts gate to the user like
  a preference, symmetric with unverifiable beliefs. Ratified as law and
  hereby adopted into §5/§7 by this dated entry (the owner-owed addition
  §13 named).

**CARVE-OUT — §2 is NOT ratified as sound.** Only its
empirically-validated core is ratified:

- **RATIFIED:** the **positive-citation requirement** — a doubt must
  *cite* facts, not ground itself in absence — which survived adversarial
  analysis (§11's failed attack) and was validated against a real corpus
  (§12.1: 13/14 flat-earth arguments rejected, zero admitted-false, the
  measurement fixed before the data and against the composer's disclosed
  stake). The rule is a **derivation** test, not a citation test.
- **NOT RATIFIED / STILL OPEN:** the **bootstrap** gap (attacks 1–2
  laundering, §11) and the **cost** gap (attack 2 volume; job #3
  contradicts §3's table). The proposed repairs are not adopted. **§2 as
  a complete bound is not built against until these close.** Ratifying
  the bound whole would be the exact instance-promotion failure this
  program guards against.

**Evidence basis, recorded because ratification followed test.** The
positive-citation core was ratified because it *passed a blind empirical
test*, not because it was argued; the two-layer architecture because it
was *corroborated by the evidence-locus games*; the fates because the
*collaborator confirmed* them. Where an item rests on argument alone
(§12.2's untested defeater flank), that is marked, not smoothed over.

## 15. Parity audit with the support side (dated addition — July 21, 2026, owner Cnid + Claude, in session)

Recorded as this session's learning; **ratifies nothing new** and authorizes
no build. It consolidates the doubt-vs-fact symmetry already distributed across
the sections above and names one new gap. The audit walked ten dimensions of
the `-1` and `+1` poles around belief (`0`):

| dimension | fact side `+1` | doubt side `-1` | parity |
|---|---|---|---|
| standing | fact | doubt | **symmetric** (§1; STANDING_MODEL §1) |
| the object it is built on | *unnamed as a single noun* | **objection** (§10) | **GAP — see below** |
| the instrument | judge | defeater | **symmetric** — one primitive (§8) |
| composition law | cover (∀) | search (∃) | **asymmetric BY DESIGN** (§3) |
| typed kinds | grounding / coherence / corroboration / audit | rebutting / undercutting | **symmetric** (§4) |
| the three fates | promote / defeated / pending | verified / defeated / unresolved | **symmetric** (§5) |
| grounding rule | provenance / source bytes | positive-citation of facts | **symmetric burden** (§2, positivity core only) |
| membership | survives the panel + gate | survives the fact base, else delusion | **symmetric** (§12.3) |
| user gate | gates promotion | gates demotion; mechanical contest auto | **symmetric** (§7; STANDING_MODEL §3) |
| build status | **built** | **proposed** (`grep doubt src/` = nothing) | **NOT BUILT** (§1) |

**Reading:** seven dimensions symmetric (as principle), one asymmetric by
design, two open. The design asymmetry is a feature — *support covers, defeat
searches* — never a parity defect.

**New gap — the fact side's object has no name.** §10 gave the doubt pole a
clean triad `doubt / objection / defeater`. The fact pole names its **standing**
(`fact`) and its **instrument** (`judge`), but the **object** an objection
mirrors — the fact-grounded thing that *supports* a claim — has no single noun;
it is carried implicitly by judge findings and the J3 *corroboration* role. To
make the two triads read as one, the support-side object wants a name.
**Owner-owed**, gated like the §10 rename. Candidate register (juridical, per
§10): `corroboration` (collides with the judge role), `attestation`,
`submission`. Not adopted here.

**Resolved this session (July 21, 2026 — collaborator M. Murphy delegated the
choice, owner Cnid endorsed proceeding): the name is `affirmation`.** It is the
fact-grounded object that *affirms* a claim — the direct antonym of the
`objection` that *attacks* it — and it fills the same slot: the fact-grounded
**support object**, never the candidate. That is why `claim` and `proposal`
(floated in session) were set aside: they name the thing supported, not the
support. Collision check that decided it: `corroboration` = the J3 judge role;
`submission` = `STANDING_MODEL.md §2`'s vote; `attestation` =
`HARNESS_SELF_MODEL.md §8`'s informing surface; `warrant` = the `warranted`
adjective; `affirmation` returned zero repo hits and takes the slot cleanly. The
two triads now read as one — **affirmation / fact / judge** ↔
**objection / doubt / defeater** — differing only by the §3 law (cover ∀ vs
search ∃). Gateable: one owner word overrides it.

A **three-round clean-room self-play** (July 21, 2026) probed whether the label
`affirmation` biases a reasoner's grounding judgments (connotation → auto-validation).
Across clear items, humanized marginal items (iterated builder, independently
key-verified 12/12), and a rubric-stripped condition, the name showed **no detectable
output bias** — the positive control `proof` (the most auto-validating word a blind
adversary could name) never fired either, so the honest reading is **"no detectable
connotation harm," not "proven neutral"** (single-word priming sits below the detection
floor for a capable model doing explicit adjudication). A third round (Matt-directed)
spread the label across the **full connotation axis** — validating, neutral, a
counter-label (`bunk`), and a nonsense token, 12 blind trials — and every label produced
identical 8/8 verdicts, strengthening the null past the near-synonym limit of rounds 1–2.
`affirmation` **retained**; the self-play method-learnings (including *controls must span
the manipulated axis*) were written into the `self-play` skill.

**Restated gap — build parity.** The larger asymmetry is §1's: the fact side is
built and the doubt side is not. No new claim; recorded so the audit is honest
that "symmetric" above means *as principle*, not *as shipped*.

A visual of this audit was produced this session as a private Artifact
(current-state parity map); it is provenance, not authority, and this record
governs on any drift.
