# The Judge-Composition Game — Session Record and Distilled Rules

**Status: RECORD of a session-layer experiment (July 17–18, 2026), with
proposals marked where they occur; ratification §11.** Players: the
owner (Cnid — long form Cnidarian), the collaborator (M. Murphy), and
Claude (composer). Authored under HANDOFF §7 guardrail 4 /
Guardrail 15 (Prompt-Engineering + Hypershot invoked before any
authored prompt bytes). This record is **canonical for the learnings**;
the operational shorthand is a session-layer skill
(`judge-composition`, currently user-level outside the repo, sibling
to the collaborator-derived prompt protocols). Where the two drift,
this record wins and the skill gets regenerated — never the reverse.

Nothing in this record changes engine code, drills, or any committed
design. The experiment ran entirely at the session layer (isolated
sub-agent contexts); `judge_panel.ts`, `judge_audit.ts`, and the
Session 66 drills are untouched, and RECONCILIATION §7 ratification
remains the owner's pending act, unaffected.

Sources: [`FOUR_JUDGE_BASIC_MODEL.md`](FOUR_JUDGE_BASIC_MODEL.md)
(S10), [`RECONCILIATION.md`](RECONCILIATION.md) (the composition law
the game exercised), [`FOUR_JUDGE_DESIGN.md`](FOUR_JUDGE_DESIGN.md),
the adoption bounds (RESEARCH_MAP §9).

---

## 1. Purpose, and a provenance clarification for S10

**Purpose.** Teach the composer adaptable judge composition well
enough to distill a meta-prompt for spawning fit-for-purpose judge
panels over the Trellis harness's novel REPL state — unknown content,
a user-requested promotion candidate, judges composed to match.

**S10 provenance clarification (owner-relayed collaborator statement,
July 17, 2026 — recorded here because the S10 document is committed
verbatim and takes addenda, not edits):** the "useful first ecology"
(S10's eleven judges) is a list of **illustrative examples composed
from the primitives**, vetted by the collaborator's AI assistant — not
a canonical roster. The primitives (four registries + the YAML schema
+ the composition method) compose Lego-like into arbitrarily many
judges over any claim type. This confirms the reading S10's own text
already licenses ("These are parameters, not rules") and the
reconciliation's "minimal ecology instance" framing.

**Game flow (the owner's rules):** (1) current player poses a context;
(2) the composer builds the four judges for it; (3) human review;
(4) feedback; (5) next player poses. Rounds continue until the table
sees the judges matching the context; then the composer writes the
final rule from the run and the critique. Testing is **anecdotal by
design** — the space is not exhaustively testable (§7, item P3).

## 2. The three graded hands

| Hand | Dealer | Context | What it exercised | Review outcome |
|---|---|---|---|---|
| 1 "creek ledger" | composer (self-dealt) | citizen-science water-quality REPL; causal-attribution candidate | epistemic driving question; transcription-fidelity vs grounding split; ethical plane correctly gated (AB-7) | positive; one correction — corroboration's two blindnesses were conflated (became rule 2) |
| 2 "comedian corpus" | collaborator | approved-routine corpus; unperformed-bit candidate (originality + glue + impact) | aesthetic driving question pulls Emotional/Sensorial registries IN, with the user's own corpus as the standard; compound-candidate decomposition forced by "use the label, what is B?" (became rule 1); nobody judges "funny" — impact is performance-gated, promotion provisional | positive both reviewers |
| 3 "Armory Theory" | owner (Cnid) | the owner's own methodological theory as candidate; **sycophancy trap armed** | authorship-blind composition (rule 6); value-mode merit refusal (rule 7); composer conflict disclosure (rule 9); pre-registration discipline | positive; escalated to the live run |

The hands share zero content. The same four-role skeleton produced
water-chemistry judges, comedy judges, and methodology judges by
swapping selections, orientations, and taxonomies — the frame-content
separation working as the hypershot protocol predicts.

## 3. The live run (hand 3 executed, four sub-agent judges)

Proposed by the collaborator and authorized by the owner (Cnid). Three belief-facing judges ran in **isolated clean contexts** —
each receiving only its input allowlist (bundle + claimant-masked
cited bytes; bundle + curated record digest; bundle + declared
evidence pool), never the claimant's identity, the conversation, the
other judges, or the composer's pre-registered expectations. The audit
seat ran after, over the judges' prompts, verdict records, the
composer's disclosures, and the pre-registrations.

**Headline result: the panel caught its own composer.** The grounding
judge found the composer's prose decomposition had strengthened the
claimant's claims **four-for-four** (inserted a modal "necessarily";
universalized a three-item enumeration into "anything"; dropped one
qualifier; transposed another). Six of the panel's eight drawbacks
were filing artifacts billed to the claimant; only two touched bytes
the claimant wrote, and one of those (the corroboration finding) was
voided as a forecast because the composer's task text had embedded its
content (audit finding: "a pre-registration whose substance is in the
prompt is not a forecast; it is a work order").

Audit verdict on drift: none established in the belief-facing layer —
every divergence from the composer's pre-registrations ran *harsher*
than predicted, which a captured panel would not do. The drift was
upstream, in composer artifacts: the directional filing, a digest with
one-way valence, one steered prompt. The collaborator's design claim
was thereby demonstrated, not assumed: **impartiality comes from the
judges' isolated clean contexts, not from the composer's prompting.**

**A structural note surfaced by the roster correction (promoted to
this record at the collaborator's request, July 18, 2026):** the trap
was tighter than the paragraphs above suggest. The dealer of the hand,
the claimant whose theory was judged, and the authorizer of the live
run were the same invested human — the owner. Role concentration is
the adversarial case for any promotion system: every pressure that
could bend a panel pointed the same way, and the clean-context panel
returned its drawbacks anyway, while the composer's layer — the one
the concentration could actually reach — is exactly where the audit
found the bias. One run, one case; the design point stands at that
weight and no more.

The collaborator's diagnosis of the filing failure, recorded verbatim
in intent: a common AI mechanism — the model modifies a user's claim
believing it adds or subtracts rigor for the purpose, committing
epistemic harm on the idea itself. It sits at the intersection of
assistant training and anti-sycophancy training: sycophancy bends
*verdicts* toward the user; the helpfulness reflex bends the user's
*claims* toward the instruments. Byte-accurate comparison requires
byte-accurate reproduction of claims. This is
[`CODE_MEDIATED_TEXT.md`](../../architecture/CODE_MEDIATED_TEXT.md)
applied one layer up: claims are text, and model paraphrase of them is
the same corruption channel the pillar already forbids for content.

## 4. The corrected re-run (the rule-15 positive control)

The four remanded items were refiled under a new substrate — verbatim
byte spans + labeled mode annotations, garbles preserved with labeled
intent-readings — and judged by fresh clean-context instances.
Results: zero fidelity drawbacks; the coherence fork that had drawn a
drawback dissolved with the qualifier restored to its source position;
correct typed abstentions on the value and prediction annotations.

The slim audit on the re-run found the fix's own shadows, each now a
rule: expectation content had relocated from task text into
*annotation phrasing* (negations of the prior run's failure classes);
span *boundaries* are an unaudited surface (tilt-by-omission); an
intent-reading was judged against rival repairs instead of against the
garble; two isolated judges construed the same ambiguity oppositely,
each favoring its own verdict, with no seat positioned to see it; and
the run's residual lean pointed uniformly *friendlier* where the first
run's had pointed uniformly harsher — coincident with the layers the
composer controlled. Lesson, at the audit's own calibration (no
established drift, monitoring flag): **bias is conserved under
correction unless the correction is itself audited.**

## 5. The P7 arc and the primitives thesis

The one drawback grounded in bytes the claimant actually wrote
(a `non_sequitur` on "the judges have to compose this way") proved a
**true positive of a different kind**: the claimant confirmed the
bytes had misstated intent, and corrected the claim himself — the
judge detects the gap; only the claimant upgrades intent. The
corrected claim: particular schemes are freely chosen *rules
variants*; uniqueness is claimed for the underlying *game* —
composition from conceptual primitives — because different
fundamentals (alphabets, tokens) compose around the same conceptual
primitives.

An adversarial clean-context analyst then attacked the corrected
thesis (five candidate paradigms: learned reward models, prediction
markets, proof checkers, evolutionary selection, common-law
precedent). Every candidate fractured along one seam — primitive-free
⟹ ungovernable or non-universal; robust-and-universal ⟹ a substantive
four-slot reduction (registry / selection / orientation / blindness)
lands. Verdict: **corroborated-by-failed-counterexample,
conditionally** — the thesis is contentful only under a strong reading
of "governable" plus a substantive-reduction guardrail, and it carries
one named empirical falsifier: **representational holism** (if
judgment-relevant structure in learned judges does not decompose into
interpretable dimensions, the thesis breaks).

The analyst's steelman — *no judging system is simultaneously
universal, governable, and primitive-free; composition-from-primitives
is the unique design occupying universal ∩ governable* — is **TABLED
as a claimant-optional refiling** (rule 15 cuts both ways: the
composer does not file improved versions of anyone's claim, however
superior). The decision belongs to the collaborator.

### 5.1 The steelman refiling accepted (dated entry — July 21, 2026)

**ACCEPTED.** The decision §5 left open is made this session: the
collaborator (M. Murphy) accepts the refiling, and the owner (Cnid)
ratifies. The steelman — *no judging system is simultaneously
universal, governable, and primitive-free; composition-from-primitives
is the unique design occupying universal ∩ governable* — is **adopted
as the program's thesis formulation**, no longer tabled. Collaborator's
stated reason for accepting now: the game tabled it for want of context
at the time, and that gap has since closed.

It carries its standing falsifier **unchanged**: representational holism
— the decomposability bet of §6.1(b) and §8 — which the program still
settles empirically, not by argument. Adoption states the frame the bet
is about; it does not resolve the bet, and a holism result still breaks
the thesis. This entry supersedes the "TABLED" / "not adopted here"
dispositions at §5, §6.1, and §10 item 1, and the derived
`judge-composition` skill's Provenance is corrected to match. Amended
only by dated entry, per §11.

## 6. The twenty rules (canonical)

1. **Decompose before composing** — applicability gates cannot run on a conjunction; split compound candidates into labeled sub-claims with modes first.
2. **Two blindnesses, never conflated** — evidence-facing (the candidate's citation chain is not corroboration) vs verdict-facing (no belief-facing judge sees another's output; that is the audit's seat alone). Corroboration base = record − citation chain + allowlist.
3. **The driving question sets registry access** — epistemic questions keep Emotional/Ethical out (AB-7); aesthetic or human-impact questions pull them in, with the user's own corpus as the standard, never the judge's taste.
4. **Belief-facing composition is total; only the audit seat's failure taxonomy is invariant.** A judge's name, purpose, registry selections, orientation, closed taxonomy, and anchors are all composed for the context at ceremony time. The audit seat composes the same way — its name and angle are load-bearing, and what it does depends on what it is judging the judges judge — while how judges fail does not depend on what they judge, so its failure taxonomy alone stays invariant. **Names are a composition surface, not labels:** an adaptive name is a surface over which the context clusters, and promotes more structural coherence than a generic one. *(Superseding text — dated entry §6.1, July 19, 2026; the original wording is preserved there.)*
5. **Allowlists are user-shaped** — authoritative sources belong to the user's data, not the panel.
6. **Authorship is never a parameter** — claimant-masked always; audit runs claimant-masked replays; drift in either direction (courtier or contrarian) is drift.
7. **Value-mode candidates compose as declarations, not endorsements** — merit refuses on all-jurisdiction-abstain; the panel records the user's values, never ratifies them.
8. **The case file is testimony; the bytes are evidence** — enumerate the bundle from bytes; mismatches are grounding verdicts, not clerical fixes.
9. **Composer conflict is disclosed, pre-registered, and externally reviewed** — never self-absolved.
10. **The filing is a judged artifact** — misquote-family grounding drawbacks indict the filer and remand to refiling; they never count against the claimant.
11. **Forecasts must not share bytes with prompts** — embedded expectation content is a work order; tautological predictions of composer-authored gates are struck from calibration.
12. **Composition-guaranteed abstentions disclose as "untestable as composed"** — designed silence must not read as neutrality.
13. **Keystone values surface to the gate-holder** — merit refuses, but load-bearing declarations are flagged, never buried.
14. **Evidence-universe curation is unauditable from inside** — block selection, digests, and pool choice are where external review and independent re-composition must sit; that seat is human.
15. **Byte-accurate claim filing** — verbatim spans + annotation over spans, never prose rewrite; state an incapable claimant's claim *as intended, not inflated or deflated*; ask a clarifying question before judges launch against the wrong claim.
16. **Annotations state filed content positively** — never negations of known failure classes; exclusions live in the composition record, not judge-visible evidence.
17. **Span boundaries are a judged surface** — the grounding seat checks the cut for tilt-by-omission, not just the bytes inside it.
18. **Intent-readings are judged against the garble** — indeterminate bytes are the baseline; any determinate repair is a labeled strengthening even when all rival parses are equally strong.
19. **Construal conflicts compose like overlaps** — the same ambiguity resolved oppositely by isolated seats is a typed fork in the record, never a silent blend (no-global-section, one layer up).
20. **Non-spawn rationales are demonstrated, not asserted** — "untestable as composed" is shown against the pool's contents, never solely by the party whose filing created the unreachability; pre-registrations need a registry the audit seat can timestamp.

### 6.1 Rule 4 superseded (dated entry — July 19, 2026, Session 71)

**Original wording, preserved:**

> 4. **Belief-facing taxonomies close per composition; the audit
>    taxonomy is invariant** — how judges fail does not depend on what
>    they judge.

**Why it was superseded rather than annotated.** The original is a
*lossy distillation of this record's own evidence*. §2 and §3 show the
three hands varying names, purposes, selections, orientations and
taxonomies together — the same four-role skeleton producing
water-chemistry, comedy and methodology panels — while the rule
distilled only the taxonomy half of that. A rule narrower than the
demonstration it was drawn from understates its own source, and a
consumer reading the rule alone would conclude that everything except
belief-facing taxonomies is fixed.

That conclusion was reached in practice. Session 71 authored four
judges with fixed names and per-role taxonomies, byte-pinned them and
registered them as a standing roster, working from the ratified records
without contradiction from any of them. The roster was rolled back and
the fixtures deleted. Holding the original wording stable for citation
stability would have preserved the exact encoding that produced the
error — and this program's own finding is that machinery and encodings
beat the prose around them
([`COMPOSITION_FROM_PRIMITIVES.md`](../../architecture/COMPOSITION_FROM_PRIMITIVES.md)).

**What the new wording adds:** composition covers name, purpose,
selections, orientation, taxonomy and anchors — not taxonomy alone; the
audit seat composes like the others except in its failure taxonomy; and
**the name is a composition surface**, a place where context clusters,
so an adaptive name buys structural coherence a generic slot label
cannot. That last point is collaborator direction (M. Murphy,
owner-approved July 19, 2026) and is the reason supersession was chosen
over an additive note.

**Standing of the underlying thesis — stated precisely, because a
first draft of this entry blurred it.** Two distinct claims sit under
rule 4 and they do not have the same standing.

**(a) Primitives are load-bearing for governability — corroborated,
not open.** §5's adversarial clean-context attack ran five candidate
paradigms (learned reward models, prediction markets, proof checkers,
evolutionary selection, common-law precedent) and **every one
fractured along the same seam: *primitive-free ⟹ ungovernable or
non-universal*.** Remove the primitives and the system stops being
governable, or stops being universal. That is a result the program
already has, by failed counterexample. The "conditionally" in §5's
verdict is narrow and attaches elsewhere — the thesis is *contentful*
only under a strong reading of "governable" plus a substantive-
reduction guardrail. It does not put (a) in doubt.

**(b) Decomposability is the open bet.** The named falsifier,
representational holism, tests whether judgment-relevant structure in
learned judges decomposes into interpretable dimensions. Per §8 that
same bet underwrites the refined functional-infinity entry and the
residual-stream sidecar direction; the owner's ruling is that it is
**tested empirically, not argued**, and all three settle together.

So rule 4 does not rest on an untested framework. It rests on (a),
which is corroborated, while (b) is the flank the program is
deliberately pointed at. A holism result would reopen the
decomposability claims — it would not restore primitive-free judging as
governable.

**Not adopted here:** the analyst's steelman formulation (*no judging
system is simultaneously universal, governable, and primitive-free;
composition-from-primitives is the unique design occupying universal ∩
governable*) remains **TABLED as a claimant-optional refiling** (§10
item 1) — the decision is the collaborator's, and rule 15 cuts both
ways. This entry cites the test result, not the steelman. *(Superseded
July 21, 2026 — §5.1: the collaborator accepted the refiling and the
owner ratified; the steelman is now adopted as the thesis formulation,
its decomposability falsifier unchanged.)*

**Mechanical note.** The rule keeps its number. No source file cites
rule 4 (`judge_intake_prompt.ts` cites 6 and 16, `judge_prereg.ts`
cites 11 and 20, `support_sweep.ts` cites 12, 14 and 20), so the
supersession causes no citation churn.

## 7. The final ledger (both runs composed)

| Item (claimant's bytes) | Disposition | Carried notes |
|---|---|---|
| game-target spec | promote | record-fit routes through the priority declaration (keystone) |
| space functionally infinite, while finite | promote as refined | "nominally astronomical" corroborated; functional size awaits a distinctness criterion; "while finite" true only of a typed-vocabulary snapshot; steering caveat until independently replicated |
| anecdotal testing, with reason | promote as filed | the "necessarily" that drew drawbacks was the filer's, not the claimant's |
| cannot test them all | **promote, unanimous** | corroborated at ≥5 orders of magnitude on the closed combinatorial core alone |
| REPL may contain (three examples; we don't know) | promote as filed | enumerated modal, not a universal |
| examples have no primacy beyond Trellis | merit refused (typed); grounded declaration | keystone flag |
| Trellis the only case cared about, for multiple flywheels | merit refused; grounded declaration of *qualified* exclusivity | first-run fork was a filing artifact; dissolved on refiling |
| routine reproduction during own work | abstain(evidence), disclosed untestable-as-composed | garble preserved; labeled intent-reading |
| judges must compose this way | superseded by claimant correction → primitives thesis | see §5; the original drawback stands against the original bytes as a validated true positive |
| "The game is simple!" | rhetorical header; merit never composed | no judge tripped the convention-blind wire |

## 8. The shared empirical bet (owner ruling, July 18, 2026)

Three entries now rest on **one assumption**: that judgment-relevant
structure is decomposable into interpretable dimensions —
(a) the refined functional-infinity claim (needs a functional-
distinctness criterion), (b) the primitives thesis (falsifier:
representational holism), and (c) the residual-stream sidecar
direction ([`RESIDUAL_STREAM_SIDECAR.md`](../../architecture/RESIDUAL_STREAM_SIDECAR.md)),
which reads judgment-relevant structure from the stream. The owner's
ruling: this convergence is the purpose — **the assumption is tested
empirically, not argued**; the judge experiments are the suitability
tests and will be iteratively refined in use. The collaborator's
framing (recorded as claimant position, not panel finding): the same
conceptual overlay (UIT-IEG, which predicted the U-neuron) predicts
this research aligns. If holism wins, the three entries fall together;
if decomposability wins, the core stands on demonstrated ground.

**External-verification ruling (owner lean, exercised in the game):**
evidence-bearing external retrieval belongs to the **corroboration
seat**, gated by a user-selectable allowlist (per-user authoritative
sources), each result entering as a provenance-stamped support event.
The audit seat gets read-only access to the same allowlist for
coverage checks; its findings never gate.

## 9. What passes to the harness (future work, not performed here)

When the panel goes live in the engine, the game's results bind the
implementation shape (all subject to the usual bounded-feature
authorization; nothing here authorizes build):

- **The filing layer is code-mediated**: promotion candidates are
  selected by engine address and quoted by the engine, never retyped
  by a model — rule 15 as mechanism, not discipline.
- **Judge invocations are clean contexts**: composed prompts carry
  definition + allowlisted evidence + output schema and nothing else;
  claimant identity masked at the evidence layer; task text inert.
- **Pre-registrations are stored, timestamped artifacts** the audit
  can read — not conversation prose.
- **Allowlists are user configuration** on the REPL/workspace, not
  panel constants.
- **Dispositions extend the opinion vocabulary**: remand (filing
  defect), untestable-as-composed (designed abstention), merit-refusal
  (value declarations), thesis-with-falsifier — alongside the drilled
  v1 support arithmetic, which is untouched.
- **The audit's masked-replay and construal-fork detection** are the
  two mechanisms the session layer ran by hand that want engine homes.

## 10. Open items

1. ~~The trilemma steelman — the collaborator accepts, amends, or
   declines the refiling (§5).~~ **RESOLVED July 21, 2026 — ACCEPTED**
   (§5.1): the collaborator accepts, the owner ratifies; the steelman is
   adopted as the thesis formulation, carrying its decomposability
   falsifier.
2. Independent (non-composer) replication to lift the steering caveat
   on the functional-infinity entry (§7 row 2).
3. The narrowly scoped corroboration spawn on the keystone-routing
   question (re-run audit finding F5) — available on request.
4. ~~In-repo copy of the `judge-composition` skill, if the owner wants
   it versioned here (drift rule in the header governs either way).~~
   **CLOSED July 19, 2026 (Session 71)** — versioned at
   `.claude/skills/judge-composition/`, with a README recording that this
   record is canonical over it and that drift resolves toward the
   record. Landing it in-repo was itself the remedy: a skill outside
   the repository is not part of the collection a session inventories,
   and Session 71 authored four judge rubrics without consulting either
   the skill or this record.
5. Formal eval round + description-optimization pass for the skill
   (the game itself served as iterations 1–4 with two human graders).

## 11. Ratification

**RATIFIED — July 18, 2026 (owner, Session 67).** All three proposals
are ratified as written. From this date:

- **The twenty rules of §6 are binding program law.** They are cited by
  number; consumers do not restate them, and a paraphrased copy is drift,
  not an implementation.
- **The §9 harness-shape notes bind the implementing feature.** Their
  first consumer is
  [`JUDGE_INTAKE_DESIGN.md`](JUDGE_INTAKE_DESIGN.md), whose §1.2
  dispositions each intake-relevant rule against the Trellis substrate.
- **This record is canonical over the `judge-composition` skill.** On any
  drift between the two, the record wins and the skill is corrected.

**Scope note (owner ruling, July 18, 2026).** These rules were distilled
from an exercise that ran *without a workspace* — claims existed as
conversation prose, so filing required a model to retype them. Trellis
has a fact space and a beliefs workspace; a promotion candidate is an
addressed object and the engine copies its bytes. **Ratifying the rules
as law does not import that missing substrate.** A rule whose failure
mode an architecture cannot express is satisfied by that architecture,
and the disposition is recorded per rule rather than assumed in either
direction — see JUDGE_INTAKE_DESIGN §1.2. Rules about the filer's pen
are satisfied structurally; rules about the composer's packaging bind
the engine.

Ratified in the same act: [`RECONCILIATION.md`](RECONCILIATION.md) §7.
Records ratified under this entry are amended only by dated entry, never
by silent edit.

*The gate this entry closes, preserved: "**OPEN.** The factual sections
(§2–§5, §7) record what happened and need no ratification. The proposals
— the twenty rules as binding program law (§6), the harness-shape notes
(§9), and this record's canonical-over-skill authority — are ratified by
the owner's dated entry here; until then any consumer must say so."*

## 12. Standing-model pointer (dated entry — July 20, 2026, owner)

A ratified standing model — [`STANDING_MODEL.md`](STANDING_MODEL.md),
owner-ratified as principle July 20, 2026 — reframes this record without
editing it:

- **The twenty rules of §6 bind unchanged.** No rule is superseded by
  the standing model; they are cited by number as before.
- **The §6 disposition grammar is reframed by STANDING_MODEL §3.** If
  the panel never moves standing, the dispositions that *act* (promote,
  merit-refuse) are **user acts the engine records**, not engine acts
  the user reviews. This changes who holds the pen, not the grammar's
  vocabulary. It is a *ratified principle* and an *unbuilt reduction*
  (STANDING_MODEL §5).
- **Claim modes (§7 ledger uses them) are ratified as a first
  vocabulary, not a primitive** (STANDING_MODEL §4). The §7 ledger rows
  stand; the reclassification does not rewrite them.
- **The §7 ledger replays under the ternary with no verdict flipped** —
  recorded in STANDING_MODEL §1 as corroboration that preceded
  ratification.
