# The Four-Judge Basic Model (Collaborator-Supplied)

**Provenance:** authored by the external polymath collaborator and
supplied to the program July 16, 2026, for ingestion as the
reconciliation input FOUR_JUDGE_DESIGN.md §10.1 was waiting for.
Committed verbatim below the rule; nothing edited. Register entry: S10.
The PCF mathematical-foundation reference (arXiv:2508.01581) is queued
as S11 — unread in-session; its rough-fuzzy claims stay uncanonized
until the artifact is acquired (the S6 rule).

**Terminology addendum (collaborator, July 16, 2026, after commit):**
**UHE = Unified Hyperplane of Experience** — "the training distribution
of vast corpora of human text describing all manner of experience
across the four planes" (Emotional/Logical/Sensorial/Ethical). The
collaborator's terminology is recorded in R-31 (twice-refined, July 16,
2026): UHE is a **loaned Lexideck house term** (~3 years of agentic
R&D) — the authoring-side matrix mathematics of the vocabulary-space —
while **the J-space object is the un-verbalized stream parallel to
execution**; "J-space Target" / "J-space Prediction" are acceptable
substitute concepts. The load-bearing property: such objects are
**external to execution, summarizing it or operating in parallel to
it**. No phenomenology is claimed by anyone. The program's unifying
frame built on this is RESEARCH_MAP §4.10 (the externality principle).

---

> **Dated supersession note (July 21, 2026 — owner Cnid + collaborator Matt, via self-play).**
> The per-seat `hyperplane_parameters` YAML below (the UHE four-plane model) was the program's
> **starting point** for a composed judge/defeater seat (S10, July 16, 2026). The **live per-seat
> schema has since evolved** to `purpose` · `claim_modes` · flat `select` · `orientation` ·
> `taxonomy` · `blind_to`, ratified in [`JUDGE_CONTRACT_TEMPLATE.md`](JUDGE_CONTRACT_TEMPLATE.md)
> (Layer rule). A blind self-play evaluation this session (two runs, blind judge panels, `$0` paid)
> found the added `taxonomy` + `blind_to` are the stronger primitives; that flat `select` beat
> **both** the rigid four-plane buckets *and* a plane-categorized `select` at the per-seat level;
> and that the four-plane structure's only plausible remaining home is **panel-coverage
> composition** (spanning seats across planes) — a concept, not a per-seat field, and untested.
> *"We outgrew the UHE-based per-seat judges"* (Matt). The body below is preserved **verbatim** as
> the S10 provenance record; nothing in it is edited. Provenance cross-refs:
> [`DOUBTS_WORKSPACE.md`](../../architecture/DOUBTS_WORKSPACE.md) §8 (citation correction).

## The basic model

- The four hyperplanes are not themselves four judges. They are expandable parameter registries:
- Emotional: affect, empathy, grief, trust, motivation, dignity, relational consequences.
- Logical: deduction, induction, abduction, Bayesian inference, causal reasoning, counterfactuals, falsification, consistency.
- Sensorial: observation quality, signal fidelity, embodiment, usability, accessibility, spatial and temporal coherence.
- Ethical: harm, benefit, rights, duties, justice, care, consent, autonomy, legitimacy, proportionality.

A judge is then a sparse selection from these registries:

```yaml
judge:
  name:
  purpose:

  claim_modes:
    - fact
    - inference
    - prediction
    - value
    - belief
    - experience

  hyperplane_parameters:
    emotional: []
    logical: []
    sensorial: []
    ethical: []

  orientation:
    evidence_standard:
    uncertainty_posture:
    temporal_horizon:
    stakeholder_scope:
    reversibility:
    contradiction_sensitivity:
    abstention_boundary:

```

These are parameters, not rules. Their implementations, weights, thresholds, and composition operators can remain open.

## A useful first ecology

- Epistemic Reliability Judge
> Evidence quality, induction, Bayesian confidence, falsifiability, source dependence, observation fidelity.
- Formal Coherence Judge
> Deduction, consistency, constraint satisfaction, counterexamples, contradiction sensitivity.
- Engineering Adequacy Judge
> Causality, troubleshooting, failure modes, observability, usability, safety, reversibility.
- Human Impact Judge
> Empathy, dignity, accessibility, stakeholder distribution, harm, temporal consequences.
- Ethical Legitimacy Judge
> Rights, duties, justice, consent, proportionality, care, integrity.
- Lived Experience Judge
> Affect, embodiment, perceptual fidelity, testimony, cultural context, dignity.
- Belief-to-Fact Judge
> Claim type, evidence quality, source reliability, falsifiability, uncertainty, and the distinction between private meaning and public truth.
- Tragedy and Witness Judge
> Grief, dignity, historical fidelity, harm, cultural context, restraint. It judges whether something bears witness adequately, not whether tragedy has been “solved.”
- Decision Robustness Judge
> Counterfactuals, uncertainty, reversibility, failure recovery, long-term effects, affected populations.
- Adversarial Judge
> Hidden assumptions, contradiction, manipulation, Goodharting, omitted stakeholders, brittle evidence.
- Coverage Meta-Judge

> Identifies relevant parameters, abstentions, missing coverage, unresolved disagreement, and the need for another judge.

I think semantic similarity is necessary, but not strong enough to be the gluing condition by itself.

Its proper role is candidate retrieval. It answers:

> Which judges appear relevant to this case?

Actual sheaf-like gluing asks a stronger question:

> Do these locally relevant judges remain compatible where their jurisdictions overlap?

That distinction matters. Two judges can be semantically close while contradicting each other, sharing the same blind spot, or leaving an important UHE region uncovered.

PCF already gives us a natural matching structure through rough fuzzy classification: graded membership plus a distinction between definitely applicable and possibly applicable configurations. [That is explicit in PCF’s stated mathematical foundation](https://arxiv.org/abs/2508.01581).

## Judge matching as rough-fuzzy routing

For a context \(c\), semantic similarity can place judges into three regions:

- Lower approximation: definitely applicable
- Boundary region: possibly applicable
- Exterior: no meaningful jurisdiction, so abstain

For example, on an engineering specification:

- Engineering Adequacy is definitely applicable.
- Formal Coherence is definitely applicable.
- Human Impact may occupy the boundary if people operate the system.
- Tragedy and Witness is outside.

This makes semantic similarity a very good approximation of the cover-selection step. It identifies which local sections might cover the context.

It does not yet glue them.

## The stronger matching stack

I would use six layers:

1. Context signature  
	Identify claim mode, evidence type, stakes, stakeholders, time horizon, and implicated UHE parameters.

2. Semantic retrieval  
	Retrieve judges whose purposes and parameters resemble that signature.

3. Applicability gate  
	Check whether the judge can actually address this claim mode. A judge of testimonial credibility may concern the same topic as a factual verifier without being qualified to establish the fact itself.

4. Compatibility gate  
	Exclude internally contradictory compositions and judges whose required assumptions conflict with the case. This should be a hard gate, not merely another similarity score.

5. Coverage and complementarity  
	Select a small set that covers the relevant UHE parameters while avoiding redundant judges.

6. Overlap test  
	After judging, compare their local conclusions on shared parameters. Compatible restrictions can be composed. Incompatible restrictions remain explicit or go to a meta-judge.

A routing score could be:

\[
R(j,c)=
w_s S_{\text{semantic}}
+w_a A_{\text{applicability}}
+w_m M_{\text{marginal coverage}}
+w_k K_{\text{calibration}}
-w_r R_{\text{redundancy}}
\]

subject to:

\[
C_{\text{compatibility}}(j,c)=1
\]

The weights can remain open parameters.

## Where the sheaf analogy actually lands

The clean correspondence is:

- Semantic similarity defines neighborhoods.
- Rough-fuzzy membership identifies the cover.
- Each judge supplies a local section over part of the UHE.
- Compatibility on overlaps supplies the gluing condition.
- The composed ruling is the global section.
- Unresolved disagreement means no valid global section presently exists.

That last result is important. We should never force gluing merely because every selected judge produced an answer.

This also fits the grader paper’s failure-expecting architecture: atomic evaluators may abstain, compositions remain inspectable, and outside audits detect failures that the selected metric cannot see. [The paper treats abstention and independent auditing as structural safeguards](https://arxiv.org/pdf/2607.12790).

So I would preserve what PCF did, but sharpen its interpretation:

> Semantic similarity is the routing prior and fuzzy membership function. It approximates cover construction, not sheaf gluing itself.

The actual gluing mechanism needs compatibility on overlaps, plus coverage, calibration, and explicit permission for failure to glue.