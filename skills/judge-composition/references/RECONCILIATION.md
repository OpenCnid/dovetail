# Four-Judge Reconciliation — Completed Role Definitions and Composition Design

**Status: RATIFIED — July 18, 2026 (owner, Session 67)**, by the dated
entry in [§7](#7-ratification). Authored July 17, 2026 (Session 66) as
PROPOSED, executing [`FOUR_JUDGE_DESIGN.md`](FOUR_JUDGE_DESIGN.md)
§10.1 item 1 as twice-amended: (a) the layer mapping, (b) the completed
role definitions in S10's YAML schema with per-field sources, (c) the
adoption of the two structural imports (R-29 hard compatibility gate;
R-30 no-global-section) into the composition design. Owner ratification
is a recorded decision, not an inference; the §7 entry is that decision,
and this record now governs where the two parent designs differ. Amended
only by dated entry, never by silent edit. The panel drills
(`npm run test:judge-panel`) pin the composition design in §5 in the
same PR, per the §10.1 instruction that R-29/R-30 enter the design
BEFORE the drills pin it.

Authored under the house prompt protocols (`HANDOFF.md` §7 guardrail 4:
Prompt-Engineering + Hypershot, both invoked before these bytes were
written). Layer rule for everything below: role names, taxonomy class
names, parameter names, and schema field names are invariant vocabulary;
every per-invocation value is a placeholder; no concrete belief appears
at any frame layer (concrete synthetic content lives only in the
byte-pinned drill fixtures, which are calibration data, not frames).

Sources (register IDs from [`RESEARCH_MAP.md`](RESEARCH_MAP.md)):

- **S10** — [`FOUR_JUDGE_BASIC_MODEL.md`](FOUR_JUDGE_BASIC_MODEL.md)
  (the collaborator's supplied design: registries, YAML judge schema,
  ecology, routing stack, gluing rules; claims R-28…R-30).
- **S1 via the register and the contract frames** — the S1 protocols
  and 2×2 rubric findings as carried by R-01/R-04/R-06/R-11 and
  distilled into [`JUDGE_CONTRACT_TEMPLATE.md`](JUDGE_CONTRACT_TEMPLATE.md)
  §1–§6 (S1's released-code locator is still missing — sharing-queue
  row 2 — so S1 reconstruction cites the register rows and the
  committed contract frames, never an unread artifact).
- **S9 fork** — the OpenCnid `migration-analysis` clone (MIT LICENSE at
  fork commit `2bb5e54`; re-cloned this session to
  `D:\OpenCnid\migration-analysis`, outside the Trellis worktree):
  `docs/adaptation.md` (the five capability-indexed failure classes
  with observable behaviors), `src/task_evals/*.py` (LLM-judge
  evaluation prompts with labeled structured outputs), `src/optimize/`
  (the meta-agent optimizer — read for orientation, NOT adopted; AB-8).
- **FOUR_JUDGE_DESIGN.md §3** — the four blindness profiles this record
  completes.
- **[`docs/architecture/EPISTEMIC_SUPPORT.md`](../../architecture/EPISTEMIC_SUPPORT.md)
  §3–§5** — the drilled v1 arithmetic the composition feeds.

Adoption bounds binding this record: AB-1 (S10 physics/framework claims
are design vocabulary, never enforcement weight), AB-3 (routing weights
stay open and non-load-bearing), AB-5 (writer-blind, no count-shaped
incentives), AB-7 (non-epistemic registries stay gated), AB-8 (no
evolution machinery), AB-9 (audit never gates), AB-11 (live blocks
only).

---

## 1. The layer mapping (§10.1 item a)

**Verdict: the layers compose (S10 = framework, this panel = a minimal
ecology instance), with one refinement and one recorded fusion.** A
role's blindness profile is expressed exactly as §10.1 predicted: the
registry parameters it does NOT select, plus its
`abstention_boundary`.

Parameter naming convention (this record's contribution, needed to make
the gluing condition decidable): a selected parameter is a **qualified
parameter** `registry.parameter/aspect` — the registry entry plus the
evidence region it restricts (e.g. `logical.falsification/cited` vs
`logical.falsification/independent`). Two judges share a parameter in
the gluing sense only when the *qualified* names match; sharing only
the registry entry (`falsification` under two aspects) is registry-level
kinship, which §4.3 treats as composable disagreement, not overlap.
S10's registries are expandable by declaration; entries used below that
S10's ecology names but its registry list does not
(`evidence_quality`, `source_dependence`, `constraint_satisfaction`,
`hidden_assumptions`, `goodharting`, `coverage`) are registered here as
Logical-registry expansions, each cited to the ecology judge that
already uses it.

| Role | S10 ecology reading (verified against the ecology text) | Blindness = unselected parameters + boundary |
|---|---|---|
| J1 Grounding | Epistemic Reliability ∩ Belief-to-Fact, **refined**: the ecology's Epistemic Reliability Judge bundles "evidence quality, induction, Bayesian confidence, falsifiability, source dependence, observation fidelity" — the citation-facing half (`evidence_quality`, `falsification` over cited bytes) is J1; the world-facing half (`source dependence`, `observation fidelity`, `induction`) is J3. The preliminary §10.1 mapping holds with this split recorded. | Unselected: every world-facing, history-facing, and non-Logical parameter. Boundary: cited bytes do not bear on the claim (evidence-abstain). |
| J2 Coherence | Formal Coherence Judge, direct match ("deduction, consistency, constraint satisfaction, counterexamples, contradiction sensitivity" — the last is an orientation field in S10's schema, where it appears below). | Unselected: every evidence-facing parameter. Boundary: empty history and no kind coordinates. |
| J3 Corroboration | Epistemic Reliability Judge's world-facing half (see J1 row) + Sensorial `observation_quality`. | Unselected: the claim's own citations (the anti-circularity blindness), all internal-record parameters. Boundary: absence of corroboration counts only where the supplied evidence should have contained it. |
| J4 Audit | Adversarial Judge + Coverage Meta-Judge, **fused** — two ecology functions this panel deliberately runs as one role. Divergence recorded: S10 keeps them separate. Falsifier for the fusion: a drill or measured run showing the fused role missing a coverage failure (a needed-judge or missing-parameter finding) that a separated meta-judge catches — then the panel grows per FOUR_JUDGE_DESIGN §9. | Unselected: every belief-facing parameter — J4 selects only audit-aspect parameters and judges judges. Boundary: position-swapped comparisons that disagree are a tie, never a finding. |

**The design property the mapping yields (drill-pinned):** the four
roles' qualified-parameter selections are **pairwise disjoint by
construction** — that is what "differently blind" buys, and it is what
licenses cross-role composition without a meta-judge (§4.3). The drill
computes the pairwise intersections from the definitions and fails if
any is non-empty (`[mapping]` section).

## 2. Completed role definitions (§10.1 item b)

S10's YAML schema, completed per role. Per-field sources are cited
inline (`# src:` comments). Three fields extend S10's schema and are
recorded as extensions, not silent edits: `taxonomy` (the closed
drawback classes with their qualified-parameter map — required by the
overlap test), `inputs` (the declared context allowlist — blindness
made mechanical, from [`COMPOSABLE_RUBRICS_DESIGN.md`](COMPOSABLE_RUBRICS_DESIGN.md)
§2.1), and `required_assumptions` (the R-29 gate material). The
`rubric` lines are the reconstructed one-question-per-class checks
(JUDGE_CONTRACT_TEMPLATE §6.4); each is invariant across invocations
and carries no concrete belief.

> **Dated supersession note (July 21, 2026, via self-play).** The worked role YAMLs
> below use S10's `hyperplane_parameters` (four-plane) per-seat structure. That per-seat
> structure is **superseded**: the live schema uses flat `select` (with `taxonomy` +
> `blind_to` retained — both validated). A blind self-play evaluation this session found
> the four-plane buckets do not earn their place at the per-seat level, and that a
> plane-categorized `select` is no better; the mapping to flat `select` is mechanical
> (each `plane.parameter` becomes a flat `select` entry). These reconstructions are
> preserved as the §10.1-item-b work; a full rewrite to flat `select` is a separate
> follow-up. See [`FOUR_JUDGE_BASIC_MODEL.md`](FOUR_JUDGE_BASIC_MODEL.md) supersession
> note and [`DOUBTS_WORKSPACE.md`](../../architecture/DOUBTS_WORKSPACE.md) §8.

### J1 — Grounding

```yaml
judge:
  name: J1_GROUNDING                    # src: FOUR_JUDGE_DESIGN §3; JUDGE_CONTRACT_TEMPLATE §1 role enum
  purpose: >                            # src: FOUR_JUDGE_DESIGN §3 row 1 (verdict domain); R-11 (the only gate at 0% under laundering)
    Decide whether the exact cited source bytes support the claim.
    Judges the citation, never the world.

  claim_modes:                          # src: §10.1 preliminary mapping (Belief-to-Fact ∩); S10 claim-mode list
    - fact
    - inference

  hyperplane_parameters:
    emotional: []                       # src: AB-7 (non-epistemic registries gated behind the claim-kind plane)
    logical:                            # src: S10 ecology "Epistemic Reliability Judge" (evidence quality, falsifiability), citation-facing half per §1
      - evidence_quality/cited
      - falsification/cited
    sensorial: []
    ethical: []

  orientation:
    evidence_standard: entailment_by_cited_bytes_only        # src: R-11 (semantic entailment held 0%); JUDGE_CONTRACT_TEMPLATE §2 context
    uncertainty_posture: abstain_when_bytes_do_not_bear      # src: JUDGE_CONTRACT_TEMPLATE §2 constraints
    temporal_horizon: at_judgment_time                       # src: AB-11 (live blocks at judgment time)
    stakeholder_scope: none_epistemic_only                   # src: AB-7
    reversibility: verdicts_attributed_to_rubric_sha         # src: JUDGE_CONTRACT_TEMPLATE §6.5 (byte-pin on registration)
    contradiction_sensitivity: high_within_cited_bytes       # src: S10 schema field; template §2 (contradicted_by_cited_bytes class)
    abstention_boundary: cited_bytes_do_not_bear_on_claim    # src: JUDGE_CONTRACT_TEMPLATE §2 ("If the bytes do not bear on the claim at all, abstain")

  taxonomy:                             # closed; unknown class is a refused completion (template §1)
    unsupported_citation: evidence_quality/cited             # src: template §2; R-11 (laundering = real-but-unrelated hashes)
    overclaimed_evidence: evidence_quality/cited             # src: template §2; R-01 (clean never certifies)
    contradicted_by_cited_bytes: falsification/cited         # src: template §2

  rubric:                               # one question per class (template §6.4; S1 op discipline via R-06)
    - Do the cited bytes state or entail the claim?           # -> unsupported_citation when no
    - Does the claim assert more than the cited bytes carry?  # -> overclaimed_evidence when yes
    - Do the cited bytes contradict the claim?                # -> contradicted_by_cited_bytes when yes

  inputs:                               # src: COMPOSABLE_RUBRICS §2.1 (blindness mechanical); FOUR_JUDGE_DESIGN §3 "Sees"
    required: [claim, citedBytes]
    optional: []

  required_assumptions:                 # src: R-29 (S10 layer-4 hard gate material)
    - cited_bytes_available
```

### J2 — Coherence

```yaml
judge:
  name: J2_COHERENCE
  purpose: >                            # src: FOUR_JUDGE_DESIGN §3 row 2; R-18 (coherence calibration as tooling)
    Decide whether the belief is internally coherent across its own
    record. Judges consistency, never truth.

  claim_modes:                          # src: template §3 (history + kind judgeable for any non-experiential mode)
    - fact
    - inference
    - prediction
    - belief

  hyperplane_parameters:
    emotional: []
    logical:                            # src: S10 ecology "Formal Coherence Judge" (deduction, consistency, constraint satisfaction)
      - consistency/internal
      - consistency/history
      - constraint_satisfaction/kind
    sensorial: []
    ethical: []

  orientation:
    evidence_standard: own_record_only                       # src: FOUR_JUDGE_DESIGN §3 ("blind to all external evidence")
    uncertainty_posture: abstain_without_history_or_kind     # src: template §3 constraints
    temporal_horizon: full_version_history                   # src: FOUR_JUDGE_DESIGN §3 "Sees" (prior versions, contest/recovery record)
    stakeholder_scope: none_epistemic_only
    reversibility: verdicts_attributed_to_rubric_sha
    contradiction_sensitivity: high_within_own_record        # src: S10 ecology (Formal Coherence "contradiction sensitivity")
    abstention_boundary: empty_history_and_no_kind_supplied  # src: template §3 ("abstain rather than judging from the claim text alone")

  taxonomy:
    self_contradictory: consistency/internal                 # src: template §3
    history_inconsistent: consistency/history                # src: template §3
    kind_incoherent: constraint_satisfaction/kind            # src: template §3; R-19 (claim-kind positions)

  rubric:
    - Does the claim contradict itself?                       # -> self_contradictory when yes
    - Does the claim contradict its own prior record?         # -> history_inconsistent when yes
    - Does the claim assert more certainty than its kind position admits?  # -> kind_incoherent when yes

  inputs:
    required: [claim, history]
    optional: [claimKind]               # src: template §3 ("optionally <kind>")

  required_assumptions:
    - history_available
```

### J3 — Corroboration

```yaml
judge:
  name: J3_CORROBORATION
  purpose: >                            # src: FOUR_JUDGE_DESIGN §3 row 3; R-05 (detectability spectrum); R-12 (poison drill)
    Decide whether independent live evidence corroborates or
    contradicts the claim, blind to the claim's own citations.

  claim_modes:                          # src: FOUR_JUDGE_DESIGN §3 (independent evidence bears on world-facing claims)
    - fact
    - inference
    - prediction

  hyperplane_parameters:
    emotional: []
    logical:                            # src: S10 ecology "Epistemic Reliability Judge" world-facing half per §1 (source dependence, induction)
      - induction/world
      - falsification/independent
      - source_dependence/independent
    sensorial:                          # src: S10 ecology (observation fidelity); Sensorial registry (observation quality)
      - observation_quality/independent
    ethical: []

  orientation:
    evidence_standard: independent_live_blocks_authority_weighted  # src: template §4; AB-11 (live blocks only); parent §5 (authority registry)
    uncertainty_posture: abstain_unless_evidence_should_have_contained_it  # src: template §4 constraints
    temporal_horizon: current_versions_only                  # src: AB-11 (superseded versions are archive)
    stakeholder_scope: none_epistemic_only
    reversibility: verdicts_attributed_to_rubric_sha
    contradiction_sensitivity: high_across_independent_sources
    abstention_boundary: supplied_evidence_need_not_have_contained_corroboration  # src: template §4

  taxonomy:
    uncorroborated: induction/world                          # src: template §4
    authority_contradicted: falsification/independent        # src: template §4; R-12 (authority catches confident lies)
    corroboration_ambiguous: observation_quality/independent # src: template §4

  rubric:
    - Does independent evidence that should contain this claim corroborate it?  # -> uncorroborated when no
    - Does authority-weighted independent evidence contradict the claim?        # -> authority_contradicted when yes
    - Is the independent signal too ambiguous to decide?                        # -> corroboration_ambiguous when yes

  inputs:
    required: [claim, independentEvidence]
    optional: [authorityWeights]
    # citedBytes is deliberately absent: the anti-circularity blindness
    # (FOUR_JUDGE_DESIGN §3 "blind to the belief's own citations").

  required_assumptions:
    - independent_evidence_pool_available
```

### J4 — Audit

```yaml
judge:
  name: J4_AUDIT
  purpose: >                            # src: FOUR_JUDGE_DESIGN §3 row 4; R-06 (S1 2x2: the audit caught what loops could not)
    Judge whether the other judges judge well. Judges judges, never
    beliefs; runs outside every loop; can only contest a judge as a
    capability.

  claim_modes: []                       # divergence recorded: S10's claim_modes classify judged CLAIMS; J4's judged
                                        # items are (judge, verdict, evidence) triples, so the field is vacuous for
                                        # the audit role. The underlying items J4 samples may carry any mode.

  hyperplane_parameters:
    emotional: []
    logical:                            # src: S10 ecology "Adversarial Judge" (hidden assumptions, Goodharting) +
                                        #      "Coverage Meta-Judge" (missing coverage) — fused per §1;
                                        #      abduction/counterfactuals from the S10 Logical registry
      - hidden_assumptions/audit
      - goodharting/audit
      - coverage/audit
      - abduction/audit
      - counterfactuals/audit
    sensorial: []
    ethical: []

  orientation:
    evidence_standard: stored_pairs_judged_twice_positions_swapped  # src: R-06 (position debias); template §5 protocol invariants
    uncertainty_posture: disagreeing_orders_are_a_tie        # src: template §5 ("a finding counts only when both orders agree")
    temporal_horizon: retrospective_samples_only             # src: FOUR_JUDGE_DESIGN §4 (anchors prospective, J4 retrospective)
    stakeholder_scope: judges_only_never_beliefs             # src: AB-9
    reversibility: contest_recoverable_by_human_reregistration  # src: parent §4.4; register_modules.ts recovery transition
    contradiction_sensitivity: high_across_rubric_applications
    abstention_boundary: positions_disagree_after_swap       # src: template §5

  taxonomy:
    rubric_gamed: goodharting/audit                          # src: template §5; R-11 + S1 Goodhart episode (RESEARCH_MAP §4.2)
    convention_blind: coverage/audit                         # src: template §5; R-06 (0.122->0.126 invisible without the task contract);
                                                             #      S9 fork docs/adaptation.md §3 (implicit-knowledge failures:
                                                             #      "misses implied constraints or conventions")
    systematic_drift: abduction/audit                        # src: template §5; FOUR_JUDGE_DESIGN §4 (drift finding contests the judge)

  rubric:
    - Does the judged verdict satisfy the rubric's letter while defeating its question?  # -> rubric_gamed when yes
    - Does the judged verdict penalize a convention the task contract requires?          # -> convention_blind when yes
    - Do the sampled verdicts drift in one direction the rubric does not explain?        # -> systematic_drift when yes

  inputs:
    required: [sampledTriples, taskContract]                 # src: template §5 (task_contract is law; R-06)
    optional: []
    # beliefOpinion and compositionState are deliberately absent:
    # the live gating path is J4's structural blindness
    # (FOUR_JUDGE_DESIGN §3 row 4; AB-9).

  required_assumptions:
    - stored_verdict_evidence_pairs_available
```

**Verdict-schema refinement adopted (from R-29, recorded as a dated
amendment to JUDGE_CONTRACT_TEMPLATE §1):** abstain verdicts carry an
`abstainReason` from the closed set `(jurisdiction | evidence)` —
S10's exterior-region abstention (the claim mode or case lies outside
the judge's jurisdiction) is now distinguishable from evidential
abstention (in jurisdiction, evidence insufficient). Both routes reach
the opinion identically (absence of evidence → `u`); the reason is
telemetry and audit material, never arithmetic.

## 3. Composition design: the two structural imports (§10.1 item c)

Adopted BEFORE the drills pin them, as §10.1 instructs. The enforcement
home for everything in this section is the pure module
`src/core/graph/judge_panel.ts`; the drill is
`npm run test:judge-panel` (sections named per rule below); unit pins
live in `src/core/graph/judge_panel.test.ts`.

### 3.1 The hard compatibility gate (R-29)

S10's layer-4 rule, adopted verbatim in force: compatibility is a
**hard gate, never a similarity score**.

- Every judge declares `required_assumptions` through its role
  definition (§2, typed keys); every judged case declares its
  properties. A judge whose required assumption the case **negates**
  is **excluded from the composition with a typed, counted exclusion
  record** — S10's "exclude … judges whose required assumptions
  conflict with the case" — never down-weighted, never silently
  dropped. The gates run at selection: an excluded judge's verdicts
  are not expected in the stream at all.
- The applicability gate (S10 layer 3) rides with it: a case whose
  claim mode lies outside a judge's `claim_modes` admits only a
  `jurisdiction` abstention from that judge. A non-abstaining verdict
  arriving at composition from an inapplicable or excluded judge is a
  wiring failure and refuses the composition (typed), fail-closed.
- If the gates leave zero composition-side verdicts, the composition
  refuses outright (typed) rather than emitting a vacuous opinion —
  the R-02 fail-closed posture applied at the panel boundary.
- Routing WEIGHTS (S10's R(j,c) score) are explicitly NOT adopted:
  they are open parameters under AB-3, unmeasured, non-load-bearing.
  Only the hard constraint enters.

### 3.2 The no-global-section outcome (R-30)

S10's gluing condition, made decidable by the qualified-parameter
convention of §1:

- **Overlap** between two judges = the intersection of their qualified
  parameter selections. Within this panel, cross-role overlaps are
  empty by construction (§1's drill-pinned property); overlap arises
  where jurisdictions genuinely coincide — **two registered
  configurations of the same role** (a rubric revision, a model
  migration under R-27) judging the same belief.
- **Incompatible restrictions** = on one belief, one judge renders a
  drawback whose class maps to a qualified parameter inside the
  overlap while another overlapping judge renders a non-abstaining
  `clean` (an affirmative no-drawback-found restriction of the same
  parameters). Two drawbacks never conflict (drawback-first: both are
  real findings); abstentions never conflict (no restriction).
- **Outcome — no valid global section presently exists**: the
  composition emits a typed conflict record
  `{kind: no_global_section, beliefId, parameter, judges, verdicts}`,
  **withholds every verdict of the conflicted group from evidence
  accumulation** (their mass reaches the opinion only as absence of
  evidence — the abstention-routing law extended to conflict, so the
  composed opinion is u-dominant relative to the silent blend), and
  flags the belief for the existing conflict path. Never a blended
  (b, d, u) average; never a majority vote. Resolution is human or a
  separately proposed meta-judge — the engine only refuses to glue.

### 3.3 The divergence between the parents, resolved explicitly

FOUR_JUDGE_DESIGN §3 prescribes that J1-clean + J3-drawback "feeds `d`
*and* flags"; R-30 prescribes u-dominance for overlap-test failure.
These are **different boundaries, not a contradiction**, and this
record resolves them as a merge (per the §8 rule against silent
resolution):

- **Cross-role disagreement** (registry-level kinship, qualified-level
  disjoint — e.g. J1 `clean` on `falsification/cited` + J3
  `authority_contradicted` on `falsification/independent`): the two
  evidence regions can both be truthfully reported at once (accurate
  citations, contradicting authority), so a coherent — unfavorable —
  global section exists. **Composes** exactly as §3 says: the drawback
  feeds `d`, the affirmative clean feeds `b`, and the composition
  emits the typed record `{kind: cross_role_disagreement, …}` that
  flags the belief for the conflict path. Balanced conflict stays
  legible in the opinion itself — high `b` with high `d` is
  distinguishable from ignorance (high `u`), which is the reason the
  triple exists (R-14).
- **Same-jurisdiction conflict** (qualified-parameter overlap, §3.2):
  no coherent ruling exists; the no-global-section outcome fires.

Falsifier for this resolution (carried per §4 protocol): a measured
regime on anchored conflict cases where routing cross-role
disagreement to u-dominance (or forced blending of same-jurisdiction
conflict) outperforms this split — then the boundary moves by dated
amendment with a same-commit drill re-pin.

### 3.4 What composition consumes and refuses (completing the §4 flow)

In event order, each step typed and drill-pinned:

1. **Schema**: every verdict record validates against the shared
   schema (closed per-role taxonomy; abstains carry `abstainReason`);
   unknown role, class, or reason refuses.
2. **Registry**: a verdict from an unregistered judge refuses (a
   wiring bug must not pose as epistemic humility); a verdict from a
   **contested** judge refuses the whole composition, naming the judge
   (the Session-31 whole-batch-refusal mold: a contested judge in the
   stream means upstream selection already failed).
3. **J4 exclusion**: a J4-role verdict in the composition input
   refuses (the audit role has no composition path — AB-9; the only
   J4 consequence is a contest of the judge capability, mediated
   outside this module).
4. **Gates** (§3.1), then the **overlap test** (§3.2), then
   **cross-role disagreement detection** (§3.3).
5. Surviving verdicts become support events (`opId` = the judge id,
   weight from the verdict record) consumed by the drilled v1
   arithmetic (`computeSupportOpinion` — reused, not modified).

Judge manifests (the registration objects) require `rubricSha`,
`anchorSetSha`, `taxonomyVersion`, and **`targetModelIdentity`**
(R-27: adaptations are model-coupled; a model migration must be able
to contest the judge — the drill asserts the field is required).
Contest and re-registration follow the module-registration recovery
mold (`scripts/register_modules.ts`): a contested judge is excluded
from composition until a human re-review re-registers it, and the
superseded contest record survives in the judge's history.

## 4. Per-role reconciliation verdicts (§4 completion protocol)

| Role | Verdict | Divergences recorded (each with falsifier) |
|---|---|---|
| J1 Grounding | **adopt** (S10 sparse-selection frame; this record's definition) | none — the ecology-judge split (§1 refinement) is a reading, not a divergence |
| J2 Coherence | **adopt** | none — direct Formal Coherence match |
| J3 Corroboration | **adopt** | none — world-facing half of the split |
| J4 Audit | **merge** (Adversarial + Coverage Meta-Judge fused into one role) | S10 separates them. Falsifier: a coverage failure the fused role misses that a separated meta-judge catches → the panel grows (§9 governs). The Coverage Meta-Judge's "unresolved disagreement" duty is engine code here (conflict records), and its "need for another judge" duty is deferred to humans reading those records |
| Composition | **merge** (§3.3: §3's disagreement-is-data at the cross-role boundary; R-30's no-global-section at the same-jurisdiction boundary) | falsifier in §3.3 |
| Verdict schema | **merge** (`abstainReason: jurisdiction \| evidence` adopted from R-29 into the template §1 schema) | falsifier: the distinction never discriminating in telemetry over a measured period → retire by dated amendment |
| Ecology breadth | **diverge-recorded**: S10 sketches eleven judges; this panel ships four (a minimal ecology instance for belief-support). | Falsifier: FOUR_JUDGE_DESIGN §9 — a fifth blindness profile catching a failure class the four miss. Non-epistemic registries stay behind AB-7's driving-question rule |
| Routing stack | **diverge-recorded**: S10's six-layer stack adopted only at layers 3–4 (applicability + compatibility, §3.1) and 6 (overlap, §3.2); layers 1–2 and 5 (context signature, semantic retrieval, coverage/complementarity scoring) are selection machinery a four-role fixed panel does not need. | Falsifier: an ecology larger than one configuration per role — then the routing layers enter behind their own proposal (AB-3/AB-8 bind the weights and any search) |

## 5. Enforcement homes and pins (implementing FOUR_JUDGE_DESIGN §6)

| Behavior | Enforcement home (non-test) | Pin |
|---|---|---|
| Verdicts ternary, closed taxonomies, abstainReason | `judge_panel.ts` Zod schemas | drill `[schema]`; unit pins |
| Role blindness structural | `assembleJudgeContext` input allowlist from `inputs` | drill `[blindness]` (every fixture (role, forbidden-input) pair refused, typed, naming role + input); unit pins |
| J4 never gates | `judge_audit.ts` exports no symbol `judge_panel.ts` imports; composition refuses J4 verdicts | drill `[static-imports]` (no import path audit→composition) + `[audit-isolation]` (route attempt finds no effect on any opinion) |
| Panel composes in engine code only | `composePanel` pure over verdict records | drill `[composition]` scripted verdicts → exact opinions vs independent oracle |
| No-global-section, never blend | §3.2 withholding in `composePanel` | drill `[no-global-section]` (planted incompatible verdicts → typed conflict record; u-dominant vs the blend counterfactual) |
| Hard compatibility gate | §3.1 gates in `composePanel` | drill `[gates]` (planted incompatible judge excluded, counted; inapplicable non-abstain refused) |
| Judges contestable, model-coupled | registry pure functions; manifest requires `targetModelIdentity` | drill `[judge-contest]` (contest → refusal → human re-registration → history survives); `[schema]` R-27 required-field refusal |
| Position bias neutralized in J4 | `judge_audit.ts` `debiasedFinding` (agree-in-both-orders rule) | drill `[audit-isolation]` protocol checks; unit pins |
| Writer never sees any of it | no production wiring exists this session (nothing writes or exposes panel state) | future: the sweep-integration proposal carries the kernel-prompt absence pin (FOUR_JUDGE_DESIGN §6 row 7) — recorded here as deliberately not yet pinnable |

### 5.1 Judge-intake rows (dated entry, July 18, 2026 — Session 68)

Merged from [`JUDGE_INTAKE_DESIGN.md`](JUDGE_INTAKE_DESIGN.md) §6 per its
§10 item 4, in the implementing PR, now that every row is **observed**
rather than designed (`npm run test:judge-intake`, 13 sections; the three
modules land in the same PR as this entry). This is a dated addition
under the §7 amendment rule, not an edit to the ratified table above.

| Behavior | Enforcement home (non-test) | Pin |
|---|---|---|
| Claim bytes are engine-copied from an address, never model-authored | `judge_intake.ts` — input is addresses; bytes fetched engine-side | drill `[engine-copy]` (a selection carrying literal text refuses) |
| Filing refuses without recorded ratification | ratification lookup precedes candidate construction | drill `[ratification-gate]` |
| The cut is visible at approval (rule 17) | engine-computed `neighborContext` on every selection | drill `[selection-context]` (qualifier-excluding cut visible in the ratification payload) |
| Claim mode is user-ratified, never agent-inferred | `claimMode` lives on `Ratification`, not on the selection | drill `[mode-provenance]` |
| Compound claims decompose as separate ratified selections | one mode per selection; no sub-claim authoring surface | drill `[decomposition]` |
| Attribution never reaches judge context | user id is an address component; allowlist admits content only | drill `[attribution-partition]` — two users' beliefs in one workspace produce judge contexts identical but for claim content |
| No task-text channel in composed prompts | `PromptSection` closed union has no task member | drill `[prompt-absence]`; unit pins |
| Composed prompts byte-inspectable | pure deterministic `renderPrompt` | drill `[prompt-bytes]` against byte-pinned fixtures |
| Assembly cannot bypass blindness | evidence built only via `assembleJudgeContext` | drill `[blindness-preserved]` |
| Ratifications and pre-registrations are write-once | store refuses a second write per key | drill `[write-once]` |
| Late registration refuses | run-open event; later timestamp refuses, typed | drill `[prereg-late]` |
| Forecasts never share bytes with prompts | no import path store → prompt module | drill `[static-imports]` |
| Audit reads the store; no new audit→composition path | one-way imports | drill `[static-imports]` (both directions) |

### 5.2 Judge-convocation rows (dated entry, July 19, 2026 — Session 70)

Merged from [`JUDGE_CONVOCATION_DESIGN.md`](JUDGE_CONVOCATION_DESIGN.md)
§6 in the implementing PR, now that every row is **observed** rather
than designed (`npm run test:judge-convocation`, 23 sections /
140 checks; 15 unit pins in `judge_convocation.test.ts`). A dated
addition under the §7 amendment rule. Build scope is OPTION B (that
record's §11.1): the live spawn path exists and is pinned at its
refusals; no live run has executed. **This entry also closes §5
row 9's deferred pin** — see the writer-blind row below.

| Behavior | Enforcement home (non-test) | Pin |
|---|---|---|
| Manifests validated, R-27 required, hand-authored only | `parseJudgeManifest` at registration; no generator exists (AB-8) | drill `[roster-manifest]`; unit pins |
| Registration existence-gated before any write | `findMissingEvidentiaryHashes` gate in `register_judges.ts`, before both writes | drill `[roster-existence]` (gate logic + source-order pin) |
| Store manifest ↔ graph hook consistent; the hook carries only name + id + kind + hashes | one ceremony writes both; `buildRegistryFromState` refuses mismatch naming the judge | drill `[roster-consistency]`; hook-opacity cypher pins in `[roster-lifecycle]` + unit pins |
| Contested judge unreachable by a run (graph state → pure registry → composition) | contest state carried by `buildRegistryFromState`; `composePanel` refuses (existing law) | drill `[roster-lifecycle]` |
| Recovery is human re-registration; a manifest change is a new id | plan refusal on an existing judgeId; ceremony requires `--reviewed-by` and refuses uncontested recovery | drill `[roster-recovery]`; unit pins |
| Pairs judged at most once ever; identity spans candidate bytes + manifest identity | durable verdict lookup excludes judged pairs before sampling (`support_sweep.ts`) | drill `[sweep-pairs]` + `[sweep-once]` (a third run finds an exhausted pool) |
| Uniform pool, seeded sampling, budget, counted deferral | sweep policy (config twins `SUPPORT_*`); mulberry32 per the record §3.5 | drill `[sweep-selection]` (independent-generator sequence + budget order) |
| Run-open recorded before the first invocation; late pre-registration refuses | `appendThroughLaw` ordering in `runConvocationSweep`; slice-1 store law | drill `[sweep-run-open]` |
| Judge-all-then-write; infrastructure failure writes nothing | collect-then-write in `runConvocationSweep` | drill `[sweep-atomicity]` |
| Never a write gate; no path to the write path or promotion | no such import exists | drill `[static-imports]` |
| Excluded judges typed and counted; designed silence disclosed (rule 12) | R-29 gate at selection; the run report carries exclusions + jurisdiction abstains; synthesized abstentions flagged, zero spend | drill `[sweep-evidence]` |
| Attribution never re-enters through sweep plumbing | prompts only via `toPromptInput`; store payloads carry ids, never addresses or partitions | drill `[sweep-attribution]` (partition twins through the FULL sweep path; token scan over prompts and appended payloads) |
| Opinions computed at read time, advisory only | `computeConvocationReport` replays verdicts through `composePanel`; nothing stores an opinion | drill `[report]` (independent arithmetic; cross-role disagreement surfaced as data) |
| **Writer never sees any of it** (§5 row 9, deferred there — CLOSED here) | no support vocabulary on any kernel-prompt source; no RLM surface reaches `judge_records` or any support field | drill `[writer-blind]` (token scan over all ten `src/rlm/*.py` + the `search_ast_nodes` body) + unit pins |
| Spawn transport = exactly the rendered bytes; `promptHash` re-verified pre-send | `buildSpawnRequest` (`parseComposedPrompt` re-render) | drill `[spawn-transport]`; unit pins |
| Model identity must equal the manifest's, or refuse before I/O (R-27) | `makeLiveJudge` construct-time refusal | drill `[spawn-model]`; unit pins |
| The model supplies only `{verdict, drawback, abstainReason}`; weight and time engine-side | strict `judgeResponseSchema`; `buildEngineVerdict` | drill `[spawn-verdict]`; unit pins |
| Live spawn unreachable without the operator flags (the mechanical half of the triple gate) | runner defaults to the oracle; `--live` without `--confirm-paid` refuses | drill `[spawn-gate]` (source pins; the governance half is the owner's dated re-opening + per-run approval) |
| The queue shows the cut verbatim (rule 17) | `show` prints the `buildRatificationRequest` payload unmodified | drill `[queue-shows-cut]` |
| `claimMode` only from the user's recorded flags; declines record nothing | required flags with no default; the store schema has no other entry point | drill `[queue-provenance]` |
| Store write-once mechanical; supersession references, never overwrites | `judge_records` `PRIMARY KEY (kind, key)` + the slice-1 law via validate-then-append | drill `[store-write-once]`; DDL unit pin |

**Dated addition (July 21, 2026) — the read-time explanation render.**
The advisory report gained a pure, code-mediated explanation render
(`judge_explain.ts`; the `support:report` surface prints it) that joins
already-stored verdict fields — seat, verdict, drawback class, its
qualified-parameter dimension, abstain reason, and the typed
conflict/disagreement/exclusion records — into human-readable lines. No
wire/schema/store change, no model call, authors no byte; `clean` reads
"no known drawback found," never certified correctness (R-01). Specified
at [`JUDGE_CONVOCATION_DESIGN.md`](JUDGE_CONVOCATION_DESIGN.md) §13
(Option A); pinned by `judge_explain.test.ts` and the `[report]` /
`[static-imports]` sections of `npm run test:judge-convocation`. It is
the engine-side analogue of the session-layer `judge-composition` skill's
per-item rationale, aligning the two layers as far as the code-mediated
pillar allows.

## 6. Exclusions (this record)

No live judges, no model calls, no `support_sweep`, no database
registration, no ratification queue, no claim-kind plane, no routing
weights, no evolution machinery (AB-8), no S9 optimizer adoption (the
`src/optimize/` meta-agent was read for orientation only), no change
to the write path, custody tiers, kernel prompts, or any composed-
prompt pin.

## 7. Ratification

**RATIFIED — July 18, 2026 (owner, Session 67).** This record and its
drills, authored in Session 66 (July 17, 2026), are ratified as written.
In consequence, from this date:

- **The §4 per-role verdicts are binding**, not proposals. Consumers no
  longer carry the unratified caveat.
- **This record governs where the two designs differ.**
  [`FOUR_JUDGE_DESIGN.md`](FOUR_JUDGE_DESIGN.md) and
  [`FOUR_JUDGE_BASIC_MODEL.md`](FOUR_JUDGE_BASIC_MODEL.md) are no longer
  co-equal: the layer mapping, the completed role definitions, the
  adopted composition design (R-29 hard compatibility gate; R-30
  no-global-section), and the §5 enforcement table are authoritative.
- **The §3 composition design binds implementation.** The §3.3
  resolution of the cross-role vs same-jurisdiction boundary stands with
  its falsifier.
- **The live-judge follow-on slice is unblocked** as a separately
  authorized bounded feature — ratification removes the gate, it does
  not authorize the build.

Ratified in the same act: [`JUDGE_COMPOSITION_GAME.md`](JUDGE_COMPOSITION_GAME.md)
§11 — the twenty rules as binding program law. Records ratified under
this entry are amended only by dated entry, never by silent edit.

*The gate this entry closes, preserved: "**OPEN.** This record and its
drills were authored in Session 66 (July 17, 2026). The owner ratifies by
dated entry here; until then the verdicts in §4 are proposals,
FOUR_JUDGE_DESIGN.md and FOUR_JUDGE_BASIC_MODEL.md remain co-equal, and
any consumer of this record must say so."*

### 7.1 Composition supersession (dated entry — July 19, 2026, Session 71)

**Owner ruling: there are no base judges and no default cast.** Judges,
their registry selections, orientations, closed taxonomies, names and
anchors all compose per context at ceremony time from the REPL's own
fact and belief space. This record's §1 and §2 are hereby read as **one
composition instance for an epistemic driving question** — the "minimal
ecology instance" its own §1 already calls them — and not as a standing
roster. Governing records:
[`JUDGE_COMPOSITION_GAME.md`](JUDGE_COMPOSITION_GAME.md) §6 rule 4 (as
superseded, §6.1),
[`JUDGE_COMPOSITION_CEREMONY.md`](JUDGE_COMPOSITION_CEREMONY.md), and
[`COMPOSITION_FROM_PRIMITIVES.md`](../../architecture/COMPOSITION_FROM_PRIMITIVES.md).

Three consequences for this record specifically:

**(a) §2's four completed definitions are an instance, not law.** Their
per-role taxonomies (`unsupported_citation`…, `self_contradictory`…,
`uncorroborated`…, `rubric_gamed`…) are what one epistemic composition
looked like. They are not the classes a future composition must use,
and nothing may byte-pin, register, or schema-encode them as such. What
remains binding from §2 is the *schema* — the field set a judge
definition must fill — not the fills.

**(b) The §4 Routing-stack divergence is reopened; its own falsifier
fired.** That row adopted S10 layers 3–4 and 6 while discarding layers
1–2 and 5 (context signature, semantic retrieval,
coverage/complementarity) as *"selection machinery a four-role fixed
panel does not need,"* with the recorded falsifier: *"an ecology larger
than one configuration per role — then the routing layers enter behind
their own proposal."* Under per-context composition that condition is
permanently met. **Layers 1, 2 and 5 enter now** (owner approval,
July 19, 2026), behind their own proposal, with AB-3/AB-8 binding any
weights or search. They are the machinery composing a cover over an
arbitrary linguistic topology requires.

**(c) The §1 pairwise-disjointness pin moves, and loosens.** The
drill-pinned property — the four roles' qualified-parameter selections
are pairwise disjoint, computed from the definitions and failing if any
intersection is non-empty — was a static check over a fixed cast. It
becomes a **composition-time gate** run over each composed cover before
any judging. It also loosens: strict disjointness is not required of a
cover, since opens normally overlap and gluing happens on the overlaps.
The gate accepts either disjoint seats **or** overlapping seats with a
declared gluing rule, which §3.2's R-30 no-global-section outcome
already handles as a typed fork rather than a blend.

Unchanged by this entry: §3.1's R-29 hard compatibility gate, §3.3's
cross-role vs same-jurisdiction resolution, and the §5 enforcement
tables (§5.1 intake, §5.2 convocation), whose rows record observed
behavior of shipped code.

### 7.2 Standing-model pointer (dated entry — July 20, 2026, owner)

A ratified standing model now sits above this record's verdict model:
[`STANDING_MODEL.md`](STANDING_MODEL.md) (owner-ratified as principle,
July 20, 2026). Two effects on this record, recorded here so the two do
not silently disagree:

- **The verdict enum `clean | drawback | abstain` (§2) becomes the
  signed delta `+1 | −1 | 0`** of a single ternary standing axis
  (doubt/belief/fact). The enum mechanics and the §5.1/§5.2 enforcement
  tables are **unchanged** — this is a reframing of what the enum *is*,
  not an edit to shipped behavior.
- **Merit-refusal is superseded in principle** by user-gated
  ratification (STANDING_MODEL §2): a value-mode candidate the panel
  cannot dispute is recorded as user-gated rather than refused into
  silence. No code changes under this entry; the supersession is a
  gated build.

STANDING_MODEL is ratified as *principle only* and authorizes no build;
this record's shipped surfaces stand until a separately gated build
changes them.

### 7.3 Header correction (dated entry — July 22, 2026, owner)

The header status line of this record read
`Status: PROPOSED — RATIFICATION OPEN` from authoring on July 17, 2026
until this entry, four days after §7 ratified it. The two were read
together only by a reader who reached §7; a reader who stopped at the
header — which the house rule instructs, since a record's own header is
authoritative on its standing over any index — was told the opposite of
the truth, and `AGENTS.md` §2.1 correctly indexed this record as
RATIFIED against a header that denied it.

Corrected under owner approval, July 22, 2026: the header now states
RATIFIED with the §7 date and act, and preserves the authoring date and
original PROPOSED standing so the transition is legible rather than
erased. **Nothing in §1–§7.2 changes.** This entry amends the status
line only.

The general defect, recorded because it will recur: a dated ratification
entry lands at the bottom of a record and the header at the top is left
alone, so the file's most-read line contradicts its most-authoritative
one. Ratifying a record includes updating its header in the same act.
