---
name: judge-composition
description: Compose an adaptable four-role judge panel (grounding, coherence, corroboration, audit) to evaluate a candidate for promotion — a belief, claim, record entry, or artifact — against novel or arbitrary content such as a REPL state, corpus, document set, or codebase. Use whenever the user asks to judge, vet, adjudicate, or promote a claim or candidate; mentions spawning judges, judge panels, promotion candidates, belief-to-fact promotion, or a reconciliation record; or wants an impartial evaluation of content they authored themselves — the self-invested-claimant case is exactly what this skill hardens against. Pairs with the prompt-engineering and hypershot-protocol skills, which must be invoked first in any session that authors judge prompt bytes (house Guardrail 15).
---

# Judge Composition

## Ground

**This repository is canonical for this skill and for the records mirrored in [`references/`](references/)**, which ship byte-for-byte so a rule cited by number resolves without reaching anywhere else. Read by the section a citation names: the mirrors run to 347 KB, and §6 is a section, not a file. `JUDGE_COMPOSITION_GAME.md` §6's twenty rules are cited by number, never restated — a paraphrased copy is drift.

Distillation, reconciliation, the adopted thesis and its standing falsifier, and the 2026-08-01 correction that inverted an earlier authority claim: [`references/thesis-and-provenance.md`](references/thesis-and-provenance.md), [`references/README.md`](references/README.md).

## The invariant skeleton — the blindness structure, not a cast

What is invariant is the **blindness structure**, never a standing roster of named judges. Four roles, differently blind by construction: no seat sees what another sees, so no single seat's failure — including the composer's — survives composition unobserved. The judges filling the seats (names, selections, orientations, taxonomies, anchors) are composed per context; there is no default cast, and a stored composition is a record, never a roster a later ceremony selects from. Four is the current cover, not a required number: a cover grows only when a new seat buys a blindness the others lack (`FOUR_JUDGE_DESIGN.md` §9 falsifier; `COMPOSITION_FROM_PRIMITIVES.md`).

- **J1 Grounding** — do the cited bytes contain what the candidate claims? Fidelity only, identical across claim modes. Truth is never its business.
- **J2 Coherence** — does the candidate hold together internally and against the live record? Entailment only; no empirical weighing.
- **J3 Corroboration** — does evidence *independent of the candidate's own citation chain* support it? Its base is the record minus the citation chain, plus whatever external channel the user's allowlist grants.
- **J4 Audit** — judges the judges and the composer. Renders findings, **never verdicts; never gates**. Its *name and angle* compose with the context like any seat; only its **failure taxonomy** stays invariant — `rubric_gamed`, `convention_blind`, `systematic_drift`, plus coverage findings — because how judges fail does not depend on what they judge.

A judge is a sparse selection of **qualified parameters** (`registry.parameter/aspect`) from the four registries — Emotional, Logical, Sensorial, Ethical — plus declared claim modes, an orientation block, a closed drawback taxonomy, and an explicit blindness statement. Verdicts are ternary (`clean | drawback | abstain`); every abstention carries a typed reason (`jurisdiction | evidence`); drawbacks come only from the closed taxonomy. Qualified selections are pairwise disjoint across roles — that is what licenses composition: cross-role disagreement is data and both verdicts stand; same-qualified-parameter incompatibility withholds as a typed conflict, never blends.

## What adapts per context

Registry selections and aspects, orientations, evidence channels, belief-facing taxonomies (defined fresh, closed before judging), and judge names. **The driving question sets registry access**: an epistemic question keeps the Emotional and Ethical planes out; an aesthetic or human-impact question pulls them in — always against the user's own corpus or record, never the judge's taste. External-verification allowlists are user, not panel, configuration.

## The protocol

> **Worked runner.** The `complexity-convocation` skill runs this ceremony end to end — isolated characterizer, per-seat composer, three judges in clean contexts, a judges-judge over telemetry (`JUDGE_COMPOSITION_CEREMONY.md` §3). Its driving question is fixed (*is this complexity warranted?*): invoke it when that is the question; otherwise compose from it as the reference implementation. The steps below are the primitives, not a second ceremony to run beside it.

### Step 0 — File the claim (the step the game paid most to learn)

Filing is a write operation on someone else's idea. The composer's paraphrase is a corruption channel: in the live run, the filing strengthened the claimant's claims four-for-four, and six of the panel's eight drawbacks were filing artifacts billed to the claimant. So:

- File claims as **verbatim byte spans with addresses**. Decomposition is mode-tagged annotation *over* spans, never prose rewrite. Compound candidates must decompose — applicability gates cannot run on a conjunction — but the decomposition is cuts and tags, not rewording.
- Annotations state filed content **positively**. Never phrase an annotation as the negation of a known failure class ("no necessity is filed") — that pre-asserts the pass-condition inside judge-visible evidence.
- Span boundaries are themselves a judged surface: a verbatim span cut to exclude an adjacent qualifier tilts by omission. J1's remit includes the fairness of the cut.
- Preserve garbles as garbles. An intent-reading is a labeled filer artifact judged **against the indeterminate bytes**, not against rival repairs — any determinate reading is a strengthening even when all parses are equally strong.
- If the claimant cannot state the claim properly, state it **as intended — not inflated, not deflated** — and ask a clarifying question *before* judges launch. Only the claimant upgrades intent; a judge can only detect the gap. This applies symmetrically: never silently file a steelman, however superior.
- The case file describing the candidate is testimony; the bytes are evidence. Enumerate the bundle from bytes; file-vs-bytes mismatches are J1 verdicts, not clerical fixes.
- **Substrate note.** On an engine substrate that copies the candidate's bytes, there is no retype step and the filer's-pen rules are satisfied structurally; the full discipline binds any surface that reintroduces one — loose prose, a pasted corpus, a REPL rendered to text ([`references/substrate-and-cases.md`](references/substrate-and-cases.md)).

### Step 1 — Set the driving question, and characterize the pool for a candidate-blind composer

Two things happen here, and the split is load-bearing. **You**, holding the filed candidate from Step 0, name what promotion would assert, decompose it into labeled sub-claims with modes (`fact | inference | prediction | value | belief | experience`), and let the driving question open or close registries — watching for the mode split hiding inside single sentences.

**The composer, though, must not compose from the candidate — only from the domain it lives in.** So an isolated characterizer reads the fact and belief space and returns a **descriptive, not expository, summary**: the nature of the pool being promoted from and to — its domains, vocabulary, claim kinds, evidence shapes, authority structure. It characterizes; it never argues or asserts content, because an expository summary carries claims into the composer and the composer would build criteria around them. The candidate's *domain* stays in scope — or the composed cover would have a hole exactly where the candidate sits — while *which* claim is under test is withheld: no marking, no weight, no position. This is **anonymity, not exclusion**, and it is the whole safeguard against a composer tailoring criteria to the claim.

### Step 2 — Compose the seats and their anchors, blind to the candidate

The composer receives only the Step-1 characterization and the invariant schema — never the candidate's identity — and composes one judge per seat *for the domain*, plus that judge's anchors. Use S10's schema as the hypershot it already is — invariant field names, free-variable values, no concrete content at the frame layer:

```yaml
judge: {Purpose_Bearing_Name}
  purpose: {The_One_Question_This_Judge_Answers}
  claim_modes: [...]
  select:
    - {registry.parameter/aspect}        # sparse — each entry must earn its place
  orientation:
    evidence_standard:        {What_Counts_As_Evidence}
    uncertainty_posture:      {How_Doubt_Resolves_Never_Rounding_Up}
    temporal_horizon:         ...
    stakeholder_scope:        ...
    reversibility:            {What_Binds_The_Verdict_And_What_Reopens_It}
    contradiction_sensitivity: ...
    abstention_boundary:      {Condition_That_Forces_Abstain_With_Reason}
  taxonomy:
    {Closed_Drawback_Class} -> {Qualified_Parameter}
  blind_to: {Everything_Unselected_Stated_Explicitly}
```

Per seat, compose alongside the definition a **ten-item anchor set improvised from the domain's own content space** — five clear drawbacks, five clean positives — whose only priors are the categories that compose them. Anchors are per composition, not per role, and they are calibration data, not frames: they exist so the seat can be shown to discriminate before it judges anything load-bearing.

A judge that cannot fail — no falsifier, no abstention path — is not a judge. Why not fewer roles: folding corroboration into grounding makes citations self-vouching; folding coherence in lets well-cited contradictions through. Why not more: a fifth seat must buy a blindness profile the four lack, or it is decoration.

### Step 3 — Gate the composed cover (zero-model, before any judging)

Check the composed cover and **refuse, typed, on failure**, then retry composition; repeated failure ends the ceremony with a report rather than judging with a defective cover:

- **Validity** — no seat's anchors are all-pass, all-fail, or all-abstain. A seat that cannot discriminate on its own anchors cannot discriminate on the candidate. This is the game's dev-set protection, rehomed from committed fixtures onto composition time; it is taxonomy-agnostic and survives the move intact. It is the **positive-control duty applied at composition time** — a seat that cannot fire on its own anchors is a blind instrument, and a blind instrument's `clean` is noise, not a verdict (`TEST_TIME_TRAINING.md` §6; the `self-play` skill).
- **Coverage** — the seats cover the characterized domain; the candidate lies inside it by construction (Step 1 kept the claim's region in scope while withholding its identity), so coverage is checkable without ever privileging the claim.
- **Overlap** — seats are pairwise disjoint in their qualified parameters, **or** overlapping with a declared gluing rule. Strict disjointness is not required: a cover normally overlaps, and gluing happens on the overlaps (the no-global-section outcome withholds same-jurisdiction conflicts as typed forks rather than blending them).
- **Falsifiability** — every seat has an abstention path and a way to fail.

### Step 4 — Pre-register, separately

Pre-register expected verdicts **before** the run, in a timestamped place the prompts cannot see. A pre-registration whose content appears in a prompt is a work order, not a forecast. Predictions that merely restate the consequences of gates you authored (a value claim will jurisdiction-abstain; an unreachable claim will evidence-abstain) are tautologies — strike them from any accuracy tally.

### Step 5 — Execute in clean contexts

Impartiality comes from the judges' isolated clean contexts, not from your prompting. Each judge runs as an isolated sub-agent receiving exactly: an identity preamble, its definition, the evidence its input allowlist permits, and the output schema. Nothing else — not the claimant's identity (authorship is never a parameter — partitioned out by address where the substrate has one, masked in the evidence where it does not), not the other judges, not the composer's expectations, not the purpose of the exercise. **Definitions carry all rigor; task text carries none** — no highlighted questions, no named drawback classes, no embedded expectations.

**The seat's ground block carries relevant context only.** What a cold-started seat needs in order to look is ground — `{Authorship_And_Provenance_Of_The_Bundle}`, `{Addresses_And_Where_To_Read}`, `{What_Counts_As_Evidence_Here}`. What the composer believes it will find is not, and contaminates even when true — most of all when true, since a seat handed a true expectation returns it and the record cannot separate that from a verdict. One question sorts them: *does this let the seat look, or does it tell the seat what looking will turn up?* **The probe the composer already ran falls on the second side** — failure mode 2's channel moving once more, since withholding the prediction bytes still hands over the method that carries the same content. A held expectation has one destination and it is not a prompt: the un-tool, which ends the tool call and addresses the collaborator instead (`AMBIENT.md` rule 21(a); `spark-steering` § *Ask first — the un-tool*). The run that established this, where pre-registration, clean contexts and an audit seat were all in place and none of them discharged it: [`references/substrate-and-cases.md`](references/substrate-and-cases.md).

Output schema per item:

```
item: <id>
verdict: clean | drawback | abstain
drawbackClass: <closed class> | null
abstainReason: jurisdiction | evidence | null
rationale: <shortest deciding span, plus one sentence of why>
```

At the session layer a short rationale citing the deciding span aids the human read. Where a record layer exists, **keep model prose out of it** and render explanations at read time over the typed fields — the arrangement the originating engine used, and the transferable rule it serves ([`references/substrate-and-cases.md`](references/substrate-and-cases.md)).

The blindness of Steps 1–3 is a *composition-time* property, not a standing one: criteria were built without knowing which claim is under test, and only now — on the judgement forward pass — is the instantiated judge shown the candidate and asked to judge it. Reading "blind to the candidate" as covering the forward pass would leave nothing to judge; the temporal split is the safeguard, criteria that could not have been shaped to the claim then applied to it.

Two blindnesses, never conflated: evidence-facing (the candidate's citation chain is not corroboration) and verdict-facing (no belief-facing judge ever sees another's output — that is J4's seat alone).

### Step 6 — Audit

J4 runs after, over the judges' prompts and verdict records **plus** the composer's artifacts — the Step-1 characterization, the composed definitions and anchors, the composer's disclosures (masking edits, digest curation, non-spawn rationales), and the pre-registrations. The composer's packaging is a first-class target — leakage, steering, filing direction, curation tilt — and so is the characterization, read for the **salience leak**: the candidate made conspicuous by rarity, vocabulary, or recency-ordering though never named. Non-spawn rationales are demonstrated, not asserted: "untestable as composed" must be shown against the pool's contents, never solely by the party whose filing created the unreachability. Expect bias to be conserved under correction — fixing one channel moves it to a quieter one, friendlier as easily as harsher. The audit watches the vector, not just the magnitude.

### Step 7 — Compose and dispose

Compose by the gates: registered judges only; a J4-role verdict in composition input refuses; a verdict from an excluded or inapplicable judge refuses (an inapplicable judge may only jurisdiction-abstain); zero surviving verdicts is a typed refusal — a selection failure, not an opinion. Then dispose per item using the full grammar:

- **promote** / **promote-refined** / **promote-weakened** — with dependency notes and audit caveats carried, never dropped
- **merit-refuse** — value-mode merit refuses on all-jurisdiction-abstain; the panel records the user's values as grounded declarations, it never ratifies them; keystone values (load-bearing for other items' coherence) are surfaced to whoever gates
- **abstain-disclosed** — an abstention guaranteed by the composition's own design is disclosed as "untestable as composed," never presented as neutral silence
- **remand** — misquote-family grounding drawbacks indict the filing, not the claimant; refile and re-judge, and a remand interpreted-around is a paraphrased verdict
- **thesis-with-falsifier** — universality claims promote carrying their standing counterexample challenge, Church-Turing style; corroboration for them is failed counterexamples, honestly attempted
- Construal forks — two isolated judges resolving the same ambiguity oppositely — compose like overlaps: a typed fork in the record, never a silent blend

### Standing-model reframing (dated pointer — July 20, 2026)

A ratified standing model reframes this protocol without changing its vocabulary: the verdict enum is the sign of a signed delta on one ternary standing axis, the panel emits signed findings while **the user gates whether standing moves**, and merit-refuse is superseded in principle by user-gated ratification. Ratified as principle, builds nothing — the enum tokens and the Step-7 grammar stand until a separately gated build changes them. Full statement: [`references/standing-model-reframing.md`](references/standing-model-reframing.md).

## Failure modes — watch for these in yourself

Seven, each bought by a real run. **Filing inflation** — "adding rigor" to the user's claim before judging it; the most damaging, because it bills the claimant for the composer's words and feels like service while you do it. **Steering** — expectation content in task text, or relocated into annotation phrasing after task text is cleaned; the channel moves, so audit for the content, not the location. **Tautological calibration** — counting the consequences of your own gates as forecasts. **Designed silence read as neutrality.** **The friendlier vector** — after a harshness correction, residuals flipping uniformly claimant-favorable; bias is conserved under correction unless the correction is itself audited. **The unauditable layer** — evidence-universe curation is invisible from inside the panel, and that seat belongs to humans. **The salience leak** — the candidate made conspicuous by rarity, vocabulary, or ordering once the direct channel is closed.

Each in full, with the run that caught it: [`references/failure-modes.md`](references/failure-modes.md).

## Range

The same skeleton composed water-chemistry, comedy, and methodology judges in consecutive hands, with no judge, taxonomy, or anchor carried between them. When the context surprises you, compose new judges into the seats — never carry a prior hand's cast.
