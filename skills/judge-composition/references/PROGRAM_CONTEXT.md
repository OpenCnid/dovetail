# Epistemic-Support Program — Context for a Fresh Session

**Status: living program orientation.** July 16, 2026. You are probably
an agent (or human) opening this program with no memory of the sessions
that produced it. This file is your entry point; it is deliberately
self-contained and points at everything else. Repo-wide rules still
bind you first: read root `AGENTS.md`, take the objective from the
collaborator's live task, then read this file and the source records it names.

**Maintenance update — July 21, 2026:** the former manual handoff and root
roadmap are historical surfaces. Any session-state or objective references to
them below describe the dated program record, not current routing.

## 1. What this program is

A proposed **second axis for Trellis beliefs**: graded *epistemic
support* — a subjective-logic opinion (b, d, u) computed sweep-side by
judged events — orthogonal to the existing custody tiers, which remain
untouched. Custody answers *where did this come from*; support answers
*how has it held up*; a third, deferred plane (claim-kind) answers
*what kind of claim is it*. Standing as of July 16, 2026: the axis is
**ADOPTED forward design** (`docs/architecture/EPISTEMIC_SUPPORT.md`),
the support-computation oracle drill is **implemented and observed
green**, and everything else (judges, sweep, registration, ratification
queue, rubrics) remains proposal awaiting its own bounded feature —
see the decision record (§6).

## 2. Reading order (program-local)

**0. READ FIRST —
[`JUDGE_COMPOSITION_GAME.md`](JUDGE_COMPOSITION_GAME.md)** (RATIFIED
July 18, 2026, §11; its twenty rules of §6 are binding program law,
cited by number and never restated). The canonical record for how
judges are composed, and the most instructive document this program
has: judges are composed **per context** from primitives, and **there
is no default cast**. Its companion is
[`COMPOSITION_FROM_PRIMITIVES.md`](../../architecture/COMPOSITION_FROM_PRIMITIVES.md),
which states the principle generally and records what it cost when a
session built the standing roster the rules forbid.

This item is numbered 0 because several records below were authored
before it and encode a fixed four-judge cast with per-role taxonomies.
**Where they and the game record differ, the game record governs.**
Reading them first is how the error happened.

**0b. [`JUDGE_COMPOSITION_CEREMONY.md`](JUDGE_COMPOSITION_CEREMONY.md)**
(DESIGN, July 19, 2026) — how a promotion is actually judged under
that governance: the candidate is ratified, an isolated agent
characterizes the REPL's fact and belief spaces descriptively, and the
judges, their taxonomies and their anchors are all composed for that
pool at ceremony time. Nothing is authored in advance and nothing is
reused. The candidate's *domain* is in scope for the composer while its
*identity* is withheld — anonymity, not exclusion — and the
instantiated judges do see the claim, on the forward pass. Read it
before building anything judge-shaped.

1. [`docs/architecture/EPISTEMIC_SUPPORT.md`](../../architecture/EPISTEMIC_SUPPORT.md)
   — the adopted doctrine record: the two-axis doctrine, the support
   state, plane geometry, the v1 arithmetic and metric grammar, the
   judge layer, the automation ladder, enforcement homes, exclusions.
   (The parent proposal it graduated from — review-series document 06 —
   was removed at owner direction at merge review, July 16, 2026; its
   text survives in PR #119 branch history.)
2. [`RESEARCH_MAP.md`](RESEARCH_MAP.md) — the evidence register:
   sources, claims with evidence classes and falsifiers (its
   register-summary header carries the current counts — trust it over
   any prose restatement), the cross-row syntheses (§4), the
   contradictions (§6), the sharing queue (§7), and the **adoption
   bounds register** — the live rules bounding what may be built on
   which evidence.
3. [`FOUR_JUDGE_DESIGN.md`](FOUR_JUDGE_DESIGN.md) — the judged-input
   architecture: four differently-blind role *slots* (grounding,
   coherence, corroboration, audit), engine-side composition, judges as
   contestable capabilities. Read it with
   [`RECONCILIATION.md`](RECONCILIATION.md) beside it — RATIFIED
   July 18, 2026, and it governs this record wherever the two differ.
   Both describe the four as "a minimal ecology instance" and then
   operate on them as a standing roster; item 0 governs that tension.
4. [`JUDGE_CONTRACT_TEMPLATE.md`](JUDGE_CONTRACT_TEMPLATE.md) — the
   prompt-facing hypershot frames and rubric-authoring rules.
5. [`ORACLE_DRILL_PROPOSAL.md`](ORACLE_DRILL_PROPOSAL.md) — the first
   drill (implemented July 16, 2026; its header carries the observed
   runs): pins the support arithmetic before any judge or sweep
   exists. `npm run test:support-oracle`.
   (The external review series that seeded this program was removed at
   owner direction at merge review; PR #119 branch history retains it.)
6. [`IEG_TEACHINGS.md`](IEG_TEACHINGS.md) — teaching record from the
   July 17, 2026 S13 dialogue sessions: the laws, the owner's
   findings, the understanding ladder with its two un-learnings, and
   the PROPOSED change queue for existing code (its §5 table is
   authoritative for the rows — counts are not restated here). Docs only;
   the register's §4.11 and rows R-32…R-38 are authoritative over it.
7. [`JUDGE_INTAKE_DESIGN.md`](JUDGE_INTAKE_DESIGN.md) *(added July 18,
   2026, Session 67)* — **judge intake**: the named bounded feature
   covering what stands between a promotion candidate and a judge —
   selection-and-ratification, clean-context prompt assembly, and the
   write-once record store. Read its §1.2 first: the
   judge-composition game ran **without a workspace**, so its filing
   rules address a transcription step Trellis does not have; §1.2
   dispositions each rule against the substrate (rules about the
   filer's pen are satisfied by
   [`WORKSPACE_AND_MODULES.md`](../../architecture/WORKSPACE_AND_MODULES.md)
   §4.1/§4.2/§6; rules about the composer's packaging survive into the
   engine). **Implemented July 18, 2026 (Session 68):** the three
   slice-1 modules (`judge_intake.ts`, `judge_intake_prompt.ts`,
   `judge_prereg.ts`) with `npm run test:judge-intake` (13 sections);
   the §6 table lives in RECONCILIATION §5.1 by dated entry; the
   record's §3.2a carries the render grammar as landed.
   Its constraints are the twenty rules of
   [`JUDGE_COMPOSITION_GAME.md`](JUDGE_COMPOSITION_GAME.md) §6 and the
   §9 shape notes — **binding program law since the July 18, 2026
   ratification (§11)** — cited by number, never restated.
8. [`JUDGE_CONVOCATION_DESIGN.md`](JUDGE_CONVOCATION_DESIGN.md) *(added
   July 18, 2026, Session 69)* — **judge convocation**: the slice-2
   proposal for what stands between a ratified candidate with a
   composed prompt and a recorded support opinion — judge registration
   (the split store/graph representation), the `support_sweep` job
   (Session 32 mold; pair-once bookkeeping; run-open binding for
   rule 20; the RECONCILIATION §5 row 9 writer-blind pin designed),
   the spawn boundary (the composed bytes ARE the interface; R-27
   model-identity refusal; oracle twin), and the ratification queue
   (WORKSPACE §6 mold). **AUTHORIZED — Option B (owner, July 18,
   2026; dated entry §11.1); IMPLEMENTED at option-B scope July 19,
   2026 (Session 70)**: four modules + the `judge_records` table +
   four operator surfaces + `npm run test:judge-convocation`
   (23 sections; the §6 rows live in RECONCILIATION §5.2, which also
   closes §5 row 9's writer-blind pin). No live run has executed; the
   paid queue remains ON HOLD; §10 registers the owner-requested
   metered promotion-cost measurement and §11.2 carries the road to
   option C (the eventual live-LLM test).

## 3. Context you cannot infer from the artifacts alone

- **Provenance standing of this program: none.** It was authored by a
  sister-lab session (branch `claude/sister-lab-repo-review-5fuu19`,
  PR #119) collaborating with an external polymath collaborator whose
  frameworks (WonderSuite, S7; the Lexideck prompt protocols, S2/S3)
  supplied the plane geometry and authoring discipline. Session
  reasoning is Tier-3; only the committed documents carry forward.
- **The collaborator's four-judge design IS now in the repo**:
  supplied July 16 (late session) and committed verbatim as
  `FOUR_JUDGE_BASIC_MODEL.md` (S10). Its reframe: four *hyperplane
  registries*, not four judges; judges are sparse selections; the
  system is an ecology. `FOUR_JUDGE_DESIGN.md`'s four roles are a
  minimal ecology instance; §10.1 (twice-amended) carried the
  ingestion protocol that Session 66 EXECUTED (July 17, 2026):
  [`RECONCILIATION.md`](RECONCILIATION.md) holds the completed
  definitions and composition design, and `npm run test:judge-panel`
  pins the structural guarantees. **RATIFIED July 18, 2026
  (RECONCILIATION §7): the co-equality is ended — RECONCILIATION.md
  governs wherever the two designs differ, and its §4 verdicts are
  binding. `JUDGE_COMPOSITION_GAME.md` §11 was ratified in the same
  act, making the twenty rules binding program law.** Terminology:
  UHE (Unified Hyperplane of Experience)
  is a loaned Lexideck house term — see the basic model's header
  addendum and RESEARCH_MAP §4.10 (**the externality principle**, the
  program's unifying frame: Trellis as an engineering practice of
  external J-spaces — typed, execution-parallel summary streams).
- **The prompt-protocol mandate is enforced at root.** `.claude/rules/prompt-authoring.md` rule 16
  requires the Prompt-Engineering and Hypershot protocols before authoring any
  prompt-like artifact; the project skill distillations live under
  `.claude/skills/`. The source curriculum remains uncommitted (Lexideck
  lineage, Patreon-distributed — AB-6 forbids committing it without
  authorization). Operational rules also survive in
  `JUDGE_CONTRACT_TEMPLATE.md` §6–§7 and the layer rule at its head.
- **Network reality:** this environment's proxy blocks most hosts
  (arxiv.org, transformer-circuits.pub) but allows github.com. All
  three primary papers now have checksum-verified OpenCnid mirrors —
  `who-grades-the-grader-pdf` (S1), `verbalizable-global-workspace-pdf`
  (S8), and `better-harnesses-smaller-models-pdf` (S9) — and all three
  have been read in full. **[Amended July 18, 2026: the mirrors were
  retired by owner ruling — S1 is now the note repo
  `who-grades-the-grader`, S9 is `better-harnesses-smaller-models`
  (PDFs in git history only; recorded hashes still verify the
  historical bytes), and S8's renamed signpost
  (`verbalizable-global-workspace`) is slated for deletion, with the
  note repo `global-workspace-in-llms` as the durable pointer. In a
  proxy-blocked environment, the historical commits of the S1/S9 repos
  remain a github.com-reachable path to the exact studied bytes. The
  full note-repo inventory, machine face, and PROPOSED ingestion
  contract are recorded in `docs/RESEARCH_NOTES_COLLECTION.md`.]** None is promoted; citing any as
  `sourceNodeIds` requires operator promotion first (AB-10). S9's
  released code is ACQUIRED: the OpenCnid fork
  `github.com/OpenCnid/migration-analysis` is cloned (outside the
  Trellis worktree at `/workspace/migration-analysis`; MIT LICENSE
  added to the fork July 16 — Copyright (c) 2026 Chenyang Yang;
  upstream carries none; bounded vendoring with attribution unblocked,
  register §7 row 9 has the dated record). S1's released-code locator
  remains missing. Note: clones die with containers — a fresh session
  re-adds the repo (`add_repo OpenCnid/migration-analysis`) and
  re-clones.
- **Dated addition (July 17, 2026):** the collaborator supplied his
  master framework — UIT-IEGv5.1, "Unified Informatic Topology and
  Informatic Exchange Geometry" (register S13, rows R-32…R-35) — with
  the note that "everything in my work is really downstream of this
  lens": the S10 gluing rules, the rough-fuzzy routing, and R-31's
  UHE "matrix mathematics" (U-Space, z = x + a(εi)) all originate
  there. He also supplied a purpose-frame direction, recorded as
  hypothesis R-35: optimal harness engineering as informatic exchange
  geometry over a parameter-mapped harness-space. The artifact is an
  **unpublished draft**: reference only, never committed (AB-1 as
  amended; sharing-queue row 10); its physics claims are coverage-only.
- **Why the map is unusually insistent about incentives:** two
  independent measurements (Trellis's citation A/B, R-11; S1's
  Goodhart episode) plus a mechanistic frame (S8's report/behavior
  dissociation, R-21) all show count-shaped incentives corrupting
  agents that verbalize the right answer. Every writer-blindness and
  never-reward-counts rule descends from that triple convergence.
  Treat those rules as load-bearing, not stylistic.

## 4. Directives for any session working this program

1. **DDD**: documents lead; no implementation without a separately
   authorized bounded feature naming its non-test entrypoint
   (`AMBIENT.md` rule 15).
2. **Zero-paid first**, always; paid runs are owner-gated with printed
   estimates (repo rule; the program's costs are bounded by existing
   telemetry — entailment sweep $0.0093/25 pairs, est-suite ~$2.40/50
   runs).
3. **Check the adoption bounds register before building on any
   source** — the register, not the prose, is authoritative for what
   an evidence class may carry. Amend it by dated entry, never silent
   edit.
4. **Keep the axes apart**: support never mints custody; custody never
   implies support; the writer never sees either.
5. **Record contradictions, don't resolve them silently** — the map's
   §6 items (model-in-the-anchor above all) are owner decisions.
6. **Update `RESEARCH_MAP.md` when evidence changes state** (e.g.,
   coverage-derived → primary-verified happened once already; the
   upgrade pattern is in the S8 row and R-20/R-21 history).
7. The sister-lab session's commits carried an AI-attribution trailer
   convention conflicting with `.claude/rules/commit-and-pr.md` rule 10; the conflict was
   disclosed and the owner resolved it at merge review (July 16, 2026)
   by squash merge — the trailers never reach `master`, and rule 10
   stands unchanged for all future program work.

## 5. State of the world (as of July 16, 2026)

- Branch: `claude/sister-lab-repo-review-5fuu19`, PR #119 (owner
  review completed July 16, 2026). Program artifacts live in this
  directory and `docs/architecture/EPISTEMIC_SUPPORT.md`.
- Trellis `master` at `40b0ff6` (Session 64 / PR #117, merged into
  this branch). Root `HANDOFF.md` was
  regenerated July 16 per its §0: the active objective is Session 66
  (four-judge role-definition completion + panel drills); the
  engineering-loop track's next objective (EL-07 stage 1, from
  master's Session-64 regeneration) is preserved as its Appendix B.
- Implemented so far: the support-oracle drill (modules, fixtures,
  entrypoint, 11 unit pins) and — Session 66, July 17, 2026 — the
  judge-panel structural modules and drill
  (`src/core/graph/judge_panel.ts` / `judge_audit.ts`,
  `npm run test:judge-panel`, 10 sections / 182 checks, 17 unit pins;
  reachability = the drill and pins only). Not implemented: live
  judges, `support_sweep`, registration against real databases,
  ratification queue, rubric instantiation, claim-kind plane. No
  support fields exist in any production schema; no judges are
  registered.

## 6. Decision record (owner rulings, July 16, 2026) and what remains open

The five decisions originally listed here were ruled on by the owner on
July 16, 2026.

**Ratification record (July 16, 2026, PR #119 merge review):** the
owner (Cnid) confirmed rulings 1–5 below, the Session-66
re-sequencing, and the AB-4 amendment, in the merge-review session.
The rulings are no longer prose claims awaiting verification; this
dated entry and the merge itself are the record.

1. **Epistemic-support axis: ACCEPTED as forward design.** Doctrine
   graduated to `docs/architecture/EPISTEMIC_SUPPORT.md`; glossary
   terms added in the same change. (The review-series document 06 it
   graduated from was removed at owner direction at merge review —
   direction pivot; its text survives in PR #119 branch history.)
2. **Model-in-the-anchor: model labeling PERMITTED** (AB-4 amended by
   dated entry with the owner's rationale — the labeler is itself a
   rough fuzzy classifier; anchors rely on sparse priming
   representations' connection to the verbalizable workspace).
   Residual guards unchanged: byte-pinned fixtures, human refresh
   ceremony, no count-shaped incentives for the labeler.
3. **Support-computation oracle drill: AUTHORIZED** as the program's
   first bounded feature (implementation began the same day; see
   `ORACLE_DRILL_PROPOSAL.md` header for live status and observed
   results — do not trust this line over that header).
4. **Composable rubrics: BUILD** — no off-the-shelf software exists;
   reconstruct from S1's released rubric/outcome data (locator still
   missing — top acquisition priority, sharing-queue row 2) plus the
   WonderSuite conceptual-primitives strategy. Design record:
   [`COMPOSABLE_RUBRICS_DESIGN.md`](COMPOSABLE_RUBRICS_DESIGN.md).
5. **Promotion of S1/S8 (S7 optional): APPROVED** — execution pending
   on a durable deployment (this container's databases are ephemeral;
   promotion here would mint provenance that dies with the container).
   Statuses and command paths: RESEARCH_MAP §7.

**Still open:**
- **Naming (owner request, July 17, 2026):** a catchier-but-precise
  program alias for UHE. The owner's working gloss: "the set of all
  possible narratives the AI might be looking at." Candidates on the
  table: **N-space / the narrative manifold** (pairs cleanly with
  J-space as its measured chart), *the experience manifold*, *the
  Loom* (kin to Trellis — one frame weaves the threads, the other
  holds the vine). UHE is a loaned Lexideck house term (R-31), so any
  alias requires the collaborator's blessing; once ruled, the
  GLOSSARY mints exactly one name (the agent-first stance, rule 5).
  **RESOLVED July 17, 2026 (collaborator ruling): the exploration was
  exploratory — UHE stands as-is; no alias minted.** Candidates above
  are preserved as history. Attribution rule recorded the same day
  (collaborator, verbatim): "Matthew Murphy owns the idea, and Cnid
  owns the code."
- **Paid queue: ON HOLD (owner ruling, July 17, 2026).** The queue
  stays recorded and important — the v2 anti-shortcut run, the
  baseline head-to-head, the R-36 knee scoping — but nothing executes
  until the owner re-opens it by dated note. **[Added July 18, 2026,
  at the slice-2 authorization: the metered promotion-cost test —
  the end-to-end cost of promoting a REPL belief to a Tier-1 fact;
  registered in `JUDGE_CONVOCATION_DESIGN.md` §10's dated note,
  estimate class ≈ $0.02–$0.06 per promoted belief.]**
- **Durable deployment: DECIDED — Option A** (owner ruling, July 17,
  2026): the owner's machine, locally, now —
  [`docs/operations/DURABLE_DEPLOYMENT.md`](../../operations/DURABLE_DEPLOYMENT.md)
  carries the record. The build (backup sidecars + restore drill +
  runbook section) is a bounded feature for an ordinary session; the
  approved S1/S8/S7 promotions execute once it stands.
- ~~Session 66's first task (owner direction, July 16): COMPLETE the
  four-judge role definitions by reconstruction from the acquired
  artifacts, then ratify — design §10.1 as amended.~~ **EXECUTED
  July 17, 2026 (Session 66):** definitions completed and drills
  pinned ([`RECONCILIATION.md`](RECONCILIATION.md); the S9 fork
  re-cloned to `D:\OpenCnid\migration-analysis`). The RATIFY half
  remains the open owner act (RECONCILIATION §7).
- ~~The S9 fork's license artifact~~ RESOLVED July 16 (MIT LICENSE in
  the fork; residual: upstream carries none — an upstream grant record
  would close the chain). S1's released-code locator remains missing
  (row 2).
- Aggregation constants beyond the drilled v1 defaults (architecture
  record §"v1 arithmetic"; amendable with drill re-pin).
- Actual execution of the approved promotions on a durable deployment.

**Follow-up queue (owner-directed at merge review, July 16, 2026 —
each is future-session work, deliberately NOT in PR #119):**
- Wire `npm run test:support-oracle` into CI (plus a
  `--negative-control` step asserting exit 3) once the CI surface for
  the program is built; until then the drill's enforcement home is
  manual-run only — a known correct-but-unreachable gap.
- `computeSupportOpinion` accepts a mixed-belief event list and
  silently merges it into one opinion; add a typed refusal when
  events disagree on `beliefId`.
- `evaluateMetric` cannot distinguish an unknown/never-registered
  `opId` from a genuine abstention (both read as `abstain`); refuse
  unknown ops against a declared op pool so a wiring bug cannot pose
  as epistemic humility.
- The zero-paid static-import pin misses `node:`-prefixed builtins
  and import-free global `fetch`; close both holes.
- `fixtures/support_oracle/generate_expected.ts` is a same-author
  re-derivation of the module it checks (common-mode risk); schedule
  an independent re-derivation of the expected values from
  `EPISTEMIC_SUPPORT.md` §3 by a different author/session.

*(Relationship to the broader queue, July 17, 2026: the PROPOSED
change queue in [`IEG_TEACHINGS.md`](IEG_TEACHINGS.md) §5 spans the
support plane, the hash authority, the engine, and the substrate; the
items above predate it and keep their standing there **by reference**
— C2(b) points here rather than duplicating. Neither queue is a work
order: the active objective comes from the collaborator's live task, and
sequencing is an owner ruling — see the precedence note at the head of that §5.)*

### 6.1 Composition rulings (dated entry — July 19, 2026, Session 71)

Seven decisions, made by the owner and the collaborator in session,
recorded here because the program's decision record is where rulings
live and a resolution that survives only in conversation is the failure
this program exists to prevent. Full design:
[`JUDGE_COMPOSITION_CEREMONY.md`](JUDGE_COMPOSITION_CEREMONY.md).

1. **There are no base judges and no default cast.** Every judge is a
   special case composed at ceremony time from the REPL's own fact and
   belief space. The four roles that appear throughout this program's
   older records were **teaching examples**, composed to explain the
   model to an earlier session, which were then promoted to a
   standardized cast across seven documents. That was never the intent.
2. **What the composer sees.** A *descriptive, not expository* summary
   of the fact and belief spaces, produced by an isolated agent — the
   nature of the pool being promoted from and to.
3. **Anonymity, not exclusion.** The domain of the claim is known and
   in scope; the claim under test is **not privileged** in that
   summary. Excluding it would leave the composed cover with a hole
   exactly where the candidate sits.
4. **Judges see the candidate on the forward pass.** The blindness is a
   composition-time property; instantiated judges are shown the claim
   and judge it. Criteria that cannot have been shaped to the claim are
   then applied to it.
5. **Compositions are records, never a library.** Stored write-once as
   the account of why one promotion was decided; never selected from or
   reused. The ceremony polls the REPL for fresh state every time.
6. **The composer is the durable contestable capability**, not the
   judge. Its prompt is versioned and the audit seat reads it. If
   evidentiary bytes are missing at ceremony time the judge cannot
   ground a verdict, so there is no promotion and there is a
   transparent report; bytes dying *after* promotion is the ordinary
   invalidation sweep contesting the belief, untouched machinery.
7. **Anchors compose at instantiation** and are validated there, with
   agent retry on gate failure.

Records amended in the same act, each by its own dated entry:
JUDGE_COMPOSITION_GAME §6 rule 4 (superseded, §6.1) and §10 item 4
(closed); RESEARCH_MAP AB-8; RECONCILIATION §7.1; EPISTEMIC_SUPPORT §5;
JUDGE_CONVOCATION_DESIGN §11.2 items 3–4 (merged); plus
JUDGE_CONTRACT_TEMPLATE §1, COMPOSABLE_RUBRICS_DESIGN §4, and
FOUR_JUDGE_DESIGN §5 as proposal-status corrections.

**Open, and load-bearing:** the registration redesign (what `rubricSha`
hashes when the rubric is composed; what a composed judge's evidentiary
basis is; one graph hook per ceremony plus a durable `composer` entity;
what survives of `judges:register`; how `support_sweep`'s sampling
re-derives with no judge × candidate matrix) wants its own design
record before implementation.
