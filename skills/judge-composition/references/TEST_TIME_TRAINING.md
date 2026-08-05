# Test-Time Training and the Sparse-Model Backend — Research-Track Record

**Status: RESEARCH INITIATION (Session 45, July 13, 2026 — owner-directed).**
This record roadmaps a research track; it ratifies NO design decision, lands
NO machinery, and changes NO runtime byte. Every rung of the ladder in §7 is
owner-gated and enters as its own proposal with its own estimate. The record
follows the house document-first mold (rows 9/10/12: the design record
precedes any implementation), one stage earlier — this is the record that
decides whether a design record is ever warranted.

**Origin.** The owner relayed an external collaborator's active line of work
(the same collaborator whose provenance-threading proposal became roadmap
row 9 — see `docs/COLLABORATOR_BRIEFING.md`): *increasingly optimized sparse
models in this harness*, adapted per turn by **Test-Time Training (TTT)** —
fast-weight layers trained during inference on the contents of the RLM's
context (the REPL variables), and — the collaborator's sharper claim — on the
harness's own composed meta-prompts, "increasing quality of response
overall." This record decomposes that claim, surveys the literature as of
July 2026, maps the mechanism onto Trellis's actual seams, and pre-states how
any adoption claim would be measured before a dollar or a GPU-hour is spent.

---

## 1. Why this record exists

Trellis's reasoning engine is an RLM — a root LM operating a persistent
Python REPL, with the knowledge substrate injected as live tool objects
(the MIT CSAIL formulation: Zhang, Kraska & Khattab, arXiv:2512.24601). The
root model today is `gpt-5.4-2026-03-05` behind the OpenAI API: a closed
model whose weights Trellis cannot touch. Every behavioral improvement this
project has shipped therefore lives in one of two layers:

1. **Tooling shape** (the permanent owner direction after Session 28):
   typed refusals, engine-computed addresses, gates, budgets — the
   mechanism that closed transcription, laundering-T1, retrieval waste,
   and the splice pathologies.
2. **Prompt text** (deprioritized after the module #2 retirement): the
   composed system prompt, byte-pinned, reinforcing but never carrying the
   behavior.

TTT proposes a **third layer that Trellis has never had access to: the
model's own weights, adapted per run at inference time.** The proposal only
becomes physically possible if the backend moves (in whole or in part) to
open-weights models — which is exactly the collaborator's "increasingly
optimized sparse models" premise: modern sparse mixture-of-experts models
(the open-weights MoE class) are cheap enough to serve locally that
per-turn weight adaptation becomes an affordable, measurable lever rather
than a hypothetical.

The reason to take this seriously is architectural fit, not fashion: the
RLM already treats context as an external environment queried through
code. TTT layers treat context as a training signal compressed into
weights. These are complementary compressions of the same thing — and the
harness's fixed, byte-pinned meta-prompt is precisely the kind of
repeated-prefix signal that fast-weight machinery amortizes well (§4.3).
The reason for caution is equally concrete: the strongest 2026 agentic
result (§3.4) found TTT gains are *stability-shaped*, not
capability-shaped, and the strongest 2026 evaluation paper found that
perplexity-style TTT wins often fail to appear as behavioral wins. Both
findings align exactly with this project's measurement doctrine, so the
ladder in §7 is built on it.

## 2. The claim, decomposed

The collaborator's description compresses three separable hypotheses. They
are stated here so each can be tested — or rejected — on its own.

- **H1 (context adaptation).** Fast-weight layers trained per turn on the
  REPL-resident context improve the model's use of that context —
  long-context retrieval, cross-turn variable tracking, protocol
  adherence over long episodes. *Literature status: supported at modest
  effect sizes on long-context benchmarks (§3.2), with an explicit
  behavioral caveat (§3.4). Trellis-specific status: unmeasured.*
- **H2 (meta-prompt adaptation).** Because the harness re-presents the
  same composed meta-prompt bytes every turn (`RLM_SYSTEM_PROMPT` +
  `TRELLIS_ADDENDUM`, byte-pinned at `COMPOSED_SYSTEM_PROMPT_SHA256`),
  fast weights repeatedly trained over that prefix effectively *compile
  the protocol into weights*, improving instruction-following on the
  house protocol specifically. *Literature status: no direct study found;
  the nearest mechanisms are prefix-state compilation (§3.3) and
  fast-weight prefix processing (§3.1). This is the most original and
  least evidenced hypothesis — it needs a positive control before any
  belief attaches (§6).*
- **H3 (the sparse-model vehicle).** Open sparse MoE checkpoints are the
  practical substrate: cheap enough to serve, open enough to adapt.
  *Status: a premise about infrastructure, not a hypothesis about
  behavior — but it smuggles in the real gating question, which is
  whether ANY open model drives the house REPL protocol acceptably
  before TTT enters the picture at all (§7 R3). No TTT×MoE unified
  literature exists as of July 2026 (§3.5); expert-level adaptation is
  an open question for the collaborator (§9).*

The phrase "increasing quality of response overall" is treated throughout
this record as **an unmeasured hypothesis, not a finding.** Guardrail 8
applies to prospective claims too: no headline until a paired arm exists.

## 3. What the literature actually says (as of July 2026)

Three mechanism families get called "test-time training." They differ in
where the weights live, when they update, and what infrastructure they
demand — conflating them is the most common error in secondhand accounts,
and the collaborator's "FastWeights" phrasing spans at least two of them.

### 3.1 Family A — fast-weight layers as architecture

The hidden state of a sequence layer IS a small model; the layer's forward
pass IS a gradient step on a self-supervised loss over the incoming
context. "Training during test time" is the layer's normal operation, and
an outer training loop learns the learning rule itself.

- **TTT-Linear / TTT-MLP** (Sun et al., *Learning to (Learn at Test
  Time): RNNs with Expressive Hidden States*, arXiv:2407.04620, ICML
  2025): the modern statement of the idea. Linear-complexity layers whose
  hidden state (a linear model or 2-layer MLP) is updated by a
  reconstruction loss per token; matches or exceeds Transformer and Mamba
  baselines and — unlike Mamba — keeps improving past 16k context.
- **Titans** (Behrouz, Zhong & Mirrokni, Google Research,
  arXiv:2501.00663, NeurIPS 2025): a neural long-term memory module
  updated at test time by a surprise-metric gradient with momentum and
  weight decay (forgetting); attention as short-term memory beside it;
  scales past 2M-token context. **ATLAS** (arXiv:2505.23735) and the
  test-time-regression unifying framework (arXiv:2501.12352) generalize
  the family.
- **Large-chunk TTT / "Test-Time Training Done Right" (LaCT)** (Zhang
  et al., MIT + Adobe, arXiv:2505.23884; OpenReview Tb9qAxT3xv): makes
  nonlinear fast-weight updates hardware-efficient by batching updates
  over extremely large chunks (2K–1M tokens) — lifting fast-weight
  FLOPs utilization from <5% by orders of magnitude and scaling
  nonlinear state to ~40% of model parameters. Demonstrated in three
  domains: novel view synthesis (0.3B, 1M-token context, from
  scratch), language modeling (760M + 3B at 32,768 context, FROM
  SCRATCH — lower per-token loss at large token indices than GLA and
  DeltaNet, competitive with full attention), and autoregressive video
  diffusion — the one RETROFIT instance: the pretrained Wan 2.1 model
  fine-tuned with all bidirectional attention REPLACED by LaCT +
  sliding-window attention, quality COMPARABLE to the full-attention
  baseline while enabling autoregressive generation. Authors' stated
  limitation: state-based models are weaker at reasoning. **This is
  the collaborator's selected mechanism — see §12.**
- **Lineage** (the collaborator's "FastWeights" vocabulary): fast weights
  are Schmidhuber 1992 (*Learning to Control Fast-Weight Memories*) and
  Ba et al. 2016 (*Using Fast Weights to Attend to the Recent Past*,
  arXiv:1610.06258); Schlag, Irie & Schmidhuber 2021 showed linear
  attention IS a fast-weight programmer (arXiv:2102.11174) — the formal
  bridge explaining why in-context learning and fast-weight adaptation
  are siblings.

**Relevance to Trellis:** Family A requires the backend model to HAVE such
layers — either trained with them or retrofitted (the 2025 video result,
arXiv:2504.05298, grafted TTT layers onto a frozen pretrained DiT). Trellis
cannot add Family A to an API model. This family becomes available only at
or after §7 R3 (open-weights serving), and only if a checkpoint with these
layers exists or a retrofit is funded.

### 3.2 Family B — per-instance adaptation of pretrained weights

An ordinary pretrained model; an explicit optimizer step (usually LoRA or
rank-constrained fast weights) at inference time, on data derived from the
test input; weights discarded afterward. This is the family that works on
open checkpoints TODAY and the one every 2026 agentic result uses.

- **TTT for ARC** (Akyürek et al., *The Surprising Effectiveness of
  Test-Time Training for Abstract Reasoning*, arXiv:2411.07279): per-task
  LoRA adapters trained at test time on augmented demonstrations; up to
  6× accuracy over the fine-tuned base; 53% on ARC public with an 8B
  model. The canonical evidence that per-instance gradient steps buy real
  capability on the right task shape.
- **TTT on nearest neighbors** (Hardt & Sun, arXiv:2305.18466, ICLR
  2024): fine-tune briefly on retrieved neighbors of the test input.
  Directly suggestive for Trellis: the retrieval substrate could FEED the
  adaptation data path — with all the provenance questions §5 raises.
- **TTT-NTP** (Ouyang, Cai & Hu, *Test-Time Training with Next-Token
  Prediction*, arXiv:2606.21803, June 2026): drop-in fast weights at MLP
  down-projections, chunk-parallel rank-one updates tied to the native
  next-token loss; works on released checkpoints (Llama-3.1-8B,
  Mistral-7B, Qwen3 series); +3–4 points on RULER 4k–32k, +3.7–5.6 on
  LongBench-v2, general knowledge preserved. The current best evidence
  that fast-weight adaptation is deployable on open models without
  architectural surgery.
- **Self-guided TTT for long context** (arXiv:2607.09415, July 2026): the
  model selects relevant spans before adapting on them — TTT with a
  retrieval step in front, again adjacent to Trellis's shape.

### 3.3 Family C — compiled-state cousins (no per-turn gradient)

- **Cartridges / self-study** (arXiv:2506.06266): train a compact
  KV-like state per corpus OFFLINE, reuse it at inference — amortized
  context rather than per-turn training. The nearest existing mechanism
  to H2's "compile the meta-prompt" reading.
- **SEAL** (arXiv:2506.10943): the model writes its own finetuning data
  and applies persistent self-edits — adjacent but PERSISTENT, which
  places it outside this track's per-run-ephemeral scope (§5.3).
- **Transformer²** (arXiv:2501.06252): inference-time expert-vector
  selection over SVD components — adaptation without test-time gradients.

### 3.4 The two 2026 results that most constrain this track

1. **Agentic TTT** (*No Time Like the Present: Agentic Test-Time Training
   for LLM Agents*, arXiv:2607.03441, July 2026): continuous in-episode
   LoRA updates for multi-turn agents (vLLM runtime-LoRA serving), with
   token-level loss reweighting to stop the feedback loop where each
   update changes the policy that generates the next batch of training
   text. Gains: up to +5.0 ALFWorld / +4.9 SWE-bench Lite at 1.9× serving
   cost — and the authors' own characterization is that aTTT **preserves
   existing competence over long trajectories rather than teaching new
   abilities.** For Trellis this is the most load-bearing external fact:
   the realistic H1 payoff is *protocol-adherence stability over long
   REPL episodes*, a quantity the harness already counts
   (`TRELLIS_PROTOCOL_VIOLATION`, answer-channel compliance, criterion
   items in every measured run).
2. **Beyond Perplexity** (arXiv:2607.00368, July 2026): a behavioral
   evaluation framework for TTT deployment-memory claims; finds that
   perplexity improvements from TTT frequently fail to appear as
   behavioral ability to USE the newly absorbed information. This is the
   house measurement doctrine stated independently: a TTT arm must be
   judged on task behavior with pre-stated criteria, never on loss
   curves. §6 adopts it explicitly.

### 3.5 What was NOT found

No unified TTT×sparse-MoE literature (expert-level fast weights, routed
adaptation) as of July 2026 — the intersection is the collaborator's
research premise, not an established result, and §9 asks them for their
formulation. No direct study of fast-weight adaptation to a fixed
harness meta-prompt (H2) was found either; H2 is genuinely open.

## 4. What TTT would mean inside Trellis — the seams, named

### 4.1 The backend seam today

The model backend is hardcoded at exactly the places an R2 audit must
census (initial grep, to be completed by R2):

- `src/rlm/trellis_agent.py` passes
  `backend_kwargs={"model_name": "gpt-5.4-2026-03-05"}` to the rlms
  scaffold at both construction sites (research mode and author mode),
  and constructs a direct `openai.OpenAI()` client for the checker-model
  path. The rlms library (rlms==0.1.3, pinned) owns the actual API
  transport; **whether it exposes a base-URL/backend override without
  library modification is UNKNOWN and is R2's first question** —
  guardrail: no rlms modifications, so if it does not, the serving layer
  must present an OpenAI-compatible endpoint (vLLM and SGLang both do;
  the aTTT paper's serving stack is vLLM's runtime-LoRA API, which is
  encouraging for R4's feasibility).
- The worker-side completions (extraction, entailment judge, sweeps) have
  their own client constructions and pricing constants
  (gpt-5.4 $2.50/M in, $10/M out appears in runner spend gates) — R2
  censuses these; nothing here assumes they move. **A split backend
  (open model for the RLM root, API model for extraction/judging) is a
  legitimate intermediate state** and probably the first real
  configuration.

### 4.2 The embedding coupling — a substrate-identity trap named early

`vector_search` similarity runs against STORED embeddings:
`src/config/schema.ts` pins `embedding vector(1536)` with an HNSW index,
and `search_ast_nodes` orders by distance to a query embedding produced by
the SAME embedder family. Swapping the embedding model is therefore NOT a
config change: stored embeddings and query embeddings must come from the
same space, the schema pins the dimension, and a different embedder
invalidates every stored vector (a re-embed of the full live substrate, at
cost, plus a schema migration if dimensions differ). **The completion
backend and the embedding backend are separable decisions.** The cheap,
sane first configuration keeps the OpenAI embedder while the completion
backend moves. If the embedder ever moves, that is a substrate-identity
event in the Session 38 grammar-pin sense: recorded, owner-visible,
re-measured (the eight pinned seam queries are the standing instrument —
they are embedder-sensitive by construction).

### 4.3 The meta-prompt prefix and the byte pins (H2, mechanically)

Every research run presents the same composed prompt prefix, byte-pinned
(`COMPOSED_SYSTEM_PROMPT_SHA256 = 6183de3a…ed50` since the Session 51
re-pin — `scripts/test_modules.py` is authoritative; the pin moves only
with witting kernel changes). Two consequences if the backend ever carries
fast-weight machinery:

1. **Determinism of the prefix trajectory.** A fast-weight layer's state
   after processing a FIXED prefix is a pure function of (checkpoint
   hash, TTT config, prefix bytes). The prefix-adapted state can be
   computed once and snapshotted — H2's "optimizes the response to our
   internal meta-prompts" becomes, concretely, a **prefix fast-state
   cache** whose natural cache key is exactly the composed-prompt sha256
   the module registry already maintains. The house byte-pin discipline,
   built for prompt integrity, is coincidentally the exact cache-key
   discipline this mechanism needs. (Family C's cartridges are the same
   idea with offline compilation.) This is an observed architectural
   synergy, NOT a promised speedup — R5 measures or drops it.
2. **The pins become load-bearing for a new reason.** Today a silent
   prompt-byte drift breaks a hash check; under a prefix fast-state
   cache it would also silently invalidate (or worse, mis-serve) an
   adapted state. The existing rule — pins move only wittingly, both
   recomputed in the same commit — already covers this; the R5 design
   record would add the checkpoint hash and TTT config to the key.

### 4.4 Per-run state semantics

The house per-run doctrine transfers wholesale: the Session 30 retrieval
set is "per run = per process, monotone, never parked." Fast weights get
the same shape — **per-run ephemeral, reset at process start, never
serialized, never parked, never seeded across runs.** In the multi-turn
REPL, each turn re-presents the transcript, so a stateless serving backend
re-derives the fast state from the full prefix each turn; any within-run
state carry is a serving optimization, not a semantics change. Cross-run
persistence of adapted weights (the SEAL shape) would be a
capability-promotion event — Tier-3-to-somewhere — and is explicitly OUT
of this track's scope; if it is ever wanted it enters through its own
design record with its own gate, exactly as promotion did.

## 5. Trust-model analysis

### 5.1 Fast weights have no provenance standing

A fast-weight state is derived, ephemeral, and untraceable to specific
source bytes in the substrate sense — it is a compressed function of
everything the run saw. It therefore gets the Tier-3 treatment by
definition: **zero provenance standing, structurally incapable of minting
citations.** Nothing about weight adaptation touches what may be written
to the graph: writes still flow through `write_derived_insight`'s
three-layer enforcement (format → existence → retrieval membership), and
the cited addresses still have to be in the run's retrieval set.

### 5.2 The gates are model-agnostic by construction — the designed-in strength

Every enforcement mechanism this project built lives ENGINE-SIDE, in the
tool layer and the write path, not in the model: the Session 14 write
path, the Session 30 retrieval set, the Session 31 membership gate, the
Session 32 sampled detector, the Session 33 dedup/budgets, the Session 41
guarded splice family. **A backend swap — dense to sparse, API to local,
static to TTT — changes NONE of them.** This is not luck; it is the
tooling-shape doctrine paying out: because no behavioral guarantee was
ever entrusted to the model, no behavioral guarantee is lost when the
model changes. The trust model's answer to "can we swap the model?" is
"the trust model never depended on which model."

### 5.3 The threats a TTT backend adds (named now, measured later)

1. **Injection amplification.** Today, adversarial bytes in retrieved
   content influence one completion. Under TTT they also influence the
   WEIGHTS that process every subsequent token of the run — retrieved
   content becomes training data mid-flight. The existing containment
   story (bounded tool surfaces, typed refusals, the write gates, sampled
   entailment) still holds at the action boundary, and per-run reset
   bounds the blast radius to one run. But the T2 lesson generalizes:
   *what the model absorbed* is not observable the way *what the model
   cited* is. Any R4 proposal must state its adaptation-data policy —
   what byte sources are eligible to produce gradients (REPL-resident
   retrieved blocks? tool outputs? the meta-prompt only?) — as explicitly
   as the retrieval set defines citability today.
2. **Cross-run contamination.** Handled by construction if §4.4's
   per-run-ephemeral rule is kept absolute. The rule is stated in this
   record precisely so a future convenience ("warm-start from the last
   run's adapter") is recognizable as a design change, not an
   optimization.
3. **Reproducibility.** A TTT run's behavior is a function of checkpoint
   hash + TTT config (rank, learning rate, chunk size, seed) + the full
   input trajectory. The Session 38 doctrine transfers: **a model
   checkpoint is a substrate-identity object — exact-pinned by hash,
   bumped only as a recorded owner-visible event.** TTT config values are
   run-stamped in telemetry (counts and config echoes, never content),
   the same way arm assignment was verified per run in the Session 43
   measurement.

## 6. Measurement doctrine applied (before any spend)

The permanent owner direction (July 11–13, 2026) is that behavioral claims
are settled by paired measurement with pre-stated criteria, and failure
classes close by tooling shape. TTT is neither tooling shape nor prompt
text — it is a third substrate — but the acceptance discipline transfers
unchanged, and Trellis is unusually well-instrumented for it:

- **The instruments already exist.** The `est` suite (five
  sufficiency-bounded questions, truths unit-pinned) is a ready-made
  paired-arm harness — it was row 10's acceptance instrument and runs
  identically against any OpenAI-compatible backend. The
  effective-context probe suites, the OOLONG-hard set, protocol-violation
  and answer-channel counters, and the stage-2 criterion mold are all
  backend-independent.
- **The positive-control duty (the Session 28 lesson, restated for TTT):**
  before believing ANY TTT null OR win, build a condition where the
  no-TTT arm demonstrably fails and verify TTT moves it. H1's natural
  positive control is a long-horizon episode shaped like aTTT's setting
  (protocol drift over many turns); H2's is a protocol-adherence task
  where the base open model measurably violates the house protocol at a
  known rate. *A null result is meaningless until the experiment has
  demonstrated it can produce a positive one* — the A/B eval's
  meta-lesson, verbatim.
- **Behavioral, never perplexity** (arXiv:2607.00368 adopted): every
  criterion item is a task-behavior count (correctness, violations,
  refusals handled, tokens, dollars/GPU-minutes) — loss curves and
  perplexity may be RECORDED but never satisfy a criterion.
- **Counts and correctness together** (guardrail 4): a TTT arm that cuts
  tokens but drops correctness FAILS; one that lifts correctness at 1.9×
  serving cost reports both numbers.

## 7. The rung ladder (each rung owner-gated, propose-with-estimate)

The ladder is sequenced so every rung is cheap to refuse and no rung
assumes a later one. R2 is the only rung a session can execute without new
infrastructure or budget beyond its own time.

- **R1 — collaborator exchange (zero-paid, owner-mediated).** Deliver
  this record and §9's questions to the collaborator through the owner
  (the briefing's five-line proposal frame). Their formulation of the
  TTT×sparse intersection shapes R4's arms. No session dependency —
  proceeds in parallel with everything.
- **R2 — the backend-seam audit (zero-paid; the next actionable rung).**
  A read-only census + design record: every site that assumes the OpenAI
  transport, the gpt-5.4 model id, its pricing, or its token accounting
  (`trellis_agent.py` construction sites, the direct client
  constructions, worker completions, runner spend gates, telemetry
  parsers); whether rlms==0.1.3 admits a base-URL override WITHOUT
  library modification (guardrail: no rlms mods — if not, the seam is an
  OpenAI-compatible serving endpoint, full stop); the embedding-coupling
  boundary (§4.2) stated as a non-goal; the split-backend configuration
  (§4.1) designed as config, refusal-typed, defaulting to today's exact
  behavior byte-for-byte. Output: a design record in this file's §12 (or
  its own file if it outgrows this one) + NO implementation until the
  owner separately approves one.
- **R3 — the open-sparse baseline (paid: GPU or hosted-endpoint spend;
  needs R2's record).** Serve ONE owner-chosen open sparse checkpoint
  (exact-pinned by hash) behind an OpenAI-compatible endpoint; run the
  est suite + a protocol-adherence block against it, paired against a
  same-day gpt-5.4 arm. **The gating question is R3's, not R4's: can an
  open sparse model drive the house REPL protocol at an acceptable
  violation rate at all?** If R3 fails its pre-stated criterion, the
  track PAUSES at a recorded finding — TTT on a model that cannot drive
  the protocol is measurement noise. (R3 is also independently valuable:
  it prices the API-cost exit for ordinary runs.)
- **R4 — the paired TTT arm (paid; needs R3 PASS).** The same checkpoint
  with a Family-B mechanism (aTTT-style in-episode LoRA or
  TTT-NTP-style fast weights — R1's exchange picks), same instruments,
  TTT on/off paired, adaptation-data policy pre-stated (§5.3.1),
  per-run-ephemeral verified in telemetry both directions (the
  Session 43 arm-verification mold). Criterion pre-stated in the R4
  proposal; the H1 expectation calibrated by §3.4 (stability-shaped, not
  capability-shaped).
- **R5 — the meta-prompt fast-state measurement (paid; needs R4 to have
  produced a mechanism worth keeping).** H2 isolated: prefix fast-state
  compiled over the composed prompt (cache key = composed-prompt sha256 +
  checkpoint hash + TTT config, §4.3), measured on protocol-adherence
  deltas specifically. If R4 died, R5 dies with it — H2 is not reachable
  by API.

**Cost doctrine.** Local serving spends GPU-hours, not per-token dollars.
The standing ≤$5/run cap re-expresses as an owner-set per-run compute
budget stated in the R3/R4 proposals (estimate before, actuals after, in
the roadmap §5 entry — unchanged ceremony). Hosted open-model endpoints
(per-token) stay under the $5 cap as-is.

## 8. Honest scope — what this record does NOT claim

- **No TTT is possible on the current backend.** gpt-5.4 is an API model;
  nothing in this track changes today's runtime, and no runtime byte
  moved in the session that wrote this record.
- **"Increases quality of response overall" is a hypothesis** (H1+H2),
  not a finding — and the best current external evidence (§3.4) predicts
  the honest win is *stability over long episodes*, at ~2× serving cost,
  not a general quality lift. If the measurements come back
  stability-only, that is the finding this record's ladder was built to
  produce, and it gets reported at exactly that size.
- **H2 has no direct literature support** — it is the collaborator's
  conjecture plus an architectural synergy observation (§4.3). It is
  listed last in the ladder for that reason.
- **The sparse premise is not evaluated here.** Whether optimized sparse
  checkpoints are the right vehicle is R3's empirical question and the
  collaborator's expertise; this record maps the harness side only.
- **This record makes no promise that the track proceeds.** If the owner
  never gates R2 open, this file is a complete, self-contained account of
  why not-yet — which is a legitimate steady state.

## 9. Questions for the collaborator (via the owner; the briefing's frame)

1. **Mechanism selection.** For a multi-turn REPL agent with a fixed
   ~10k-token protocol prefix and run-resident retrieved context: which
   concrete mechanism do you have in mind — architectural fast-weight
   layers (TTT-Linear/Titans class, needs a trained-with-TTT
   checkpoint), in-episode LoRA (aTTT class, works on any open
   checkpoint via runtime-LoRA serving), or drop-in fast weights at MLP
   projections (TTT-NTP class)? Our R4 arms depend on this choice.
2. **The sparse intersection.** "Increasingly optimized sparse models" —
   is the sparsity doing WORK in your formulation (expert-level
   adaptation, routed fast weights — a literature we could not find as
   of July 2026), or is it the economics (open MoE = cheap serving) with
   TTT orthogonal? If the former: what does a positive control for
   expert-level adaptation look like?
3. **The meta-prompt claim (H2).** What is the mechanism by which
   fast-weight adaptation over a FIXED prefix improves responses beyond
   what the frozen model already extracts from attending to that prefix?
   A gradient step over bytes the model has fully attended to is not
   obviously additive — is the claim about effective capacity, about
   depth-of-processing, or about something empirical you have observed?
   A failing case we can reproduce (your five-line frame's "Failure it
   closes") would move this from conjecture to rung.
4. **The adaptation-data policy (§5.3).** In your setup, what byte
   sources are eligible to produce gradients at test time? Our trust
   model needs this stated as precisely as the retrieval set defines
   citability — retrieved substrate blocks, tool outputs, the prefix
   only, or everything in the REPL?

## 10. Reading list (dependency order, identifiers verified July 13, 2026)

| # | work | why it matters here |
|---|---|---|
| 1 | Zhang, Kraska & Khattab, *Recursive Language Models*, arXiv:2512.24601 | the formulation Trellis implements; TTT would live UNDER this; locator-verified note: [OpenCnid/recursive-language-models](https://github.com/OpenCnid/recursive-language-models) |
| 2 | Sun et al., *Learning to (Learn at Test Time)*, arXiv:2407.04620 | Family A's modern statement (TTT-Linear/TTT-MLP) |
| 3 | Behrouz et al., *Titans*, arXiv:2501.00663 (+ *ATLAS*, arXiv:2505.23735) | fast-weight long-term memory at 2M+ context |
| 4 | Ba et al., arXiv:1610.06258; Schlag et al., arXiv:2102.11174 | the FastWeights lineage; attention ≈ fast-weight programming |
| 5 | Akyürek et al., arXiv:2411.07279 | Family B's capability ceiling (ARC, 6×) |
| 6 | Hardt & Sun, arXiv:2305.18466 | TTT on retrieved neighbors — the retrieval-fed variant |
| 7 | Ouyang, Cai & Hu, *TTT-NTP*, arXiv:2606.21803 | drop-in fast weights on open checkpoints (June 2026) |
| 8 | *No Time Like the Present: Agentic TTT*, arXiv:2607.03441 | the multi-turn agent result + the stability-not-capability finding |
| 9 | *Beyond Perplexity*, arXiv:2607.00368 | the behavioral-evaluation framework §6 adopts |
| 10 | *Cartridges*, arXiv:2506.06266; *SEAL*, arXiv:2506.10943 | Family C: compiled prefix state; persistent self-edits (out of scope) |
| 11 | *Self-Guided TTT*, arXiv:2607.09415; LaCT, arXiv:2505.23884 | span-selected adaptation; hardware-efficient large-chunk TTT — the §12 selected mechanism |
| 12 | Szafer et al., *Navigating the Cost-Performance Pareto Frontier of Test-Time LLM Agent Adaptation*, ICLR 2026 (OpenReview tWAnCRYMcT) | cost-performance frontier; adaptation helps reasoning not facts; rollout dominates wall-clock |
| 13 | Hu et al., *Test-Time Learning for Large Language Models*, arXiv:2505.20633 (ICML 2025) | reports (Observation 3) LoRA mitigates forgetting more than full-parameter updates in the TTL setting; the drift-bound citation |
| 14 | Gurnee et al., *Verbalizable Representations Form a Global Workspace in Language Models*, transformer-circuits.pub/2026/workspace | workspace / Jacobian-lens; the §12.7 potential avenue; small-model reproductions |

## 11. Interaction with standing guardrails (nothing weakened)

- **No rlms library modifications** (guardrail 10): the backend seam, if
  ever built, is config + an OpenAI-compatible endpoint, or it is not
  built.
- **The write path, retrieval set, membership gate, detector, discipline,
  and guarded family are untouched by anything in this track** (§5.2);
  fast weights never gain provenance standing (§5.1); per-run-ephemeral
  is absolute within this track (§4.4).
- **Model checkpoints and embedders are substrate-identity objects**:
  exact-pinned, bumped as recorded owner-visible events (§4.2, §5.3.3);
  the embedder does not move as a side effect of the completion backend
  moving.
- **All spend owner-gated propose-with-estimate**; the compute-budget
  re-expression (§7) changes the unit, never the ceremony.
- **Experiment flags follow the house mold**: any TTT on/off arm flag is
  probe-only, off by default, byte-identical unset, stripped by
  `buildAgentEnv` — exactly the `TRELLIS_EXP_*` pattern.
- **No default changes**: today's backend, prompt bytes, and pins are the
  baseline every rung is measured against; a rung that lands still
  changes no default without its own recorded owner decision.

## 12. The R1 exchange — the collaborator's selection and the reliance claim (added July 13, 2026, same day)

The owner relayed the collaborator's response to this record the same
day it was written, referring to §3.1's LaCT entry. Verbatim:

> "This is the model we aim to use. With open weights, we can add a
> synthetic set layers that are the fast weights. Trellis can do this.
> It has provenance to check procedure. It can ensure the meta-prompts
> are followed as strongly as possible based on the data in the REPL.
> Each can be combined to ensure all meta-prompts perform as well as
> possible for output sculpting and efficiency. The research shows this
> improves base model performance. That's the claim we're relying on
> for our application."

This answers §9 question 1 and sharpens questions 2–4. What it
settles, what it opens, and what the house doctrine requires before
the reliance claim carries weight:

### 12.1 The selection, verified against the primary source

LaCT (arXiv:2505.23884) was re-verified against the paper on July 13,
2026; the §3.1 entry now carries the full experimental facts. The two
that matter for the plan as stated:

1. **"Add a synthetic set of layers that are the fast weights" is the
   Wan-2.1 retrofit pattern, and it is a TRAINING JOB** — the paper's
   only pretrained-model instance fine-tunes the model with the new
   layers in place (attention layers replaced by LaCT + sliding-window
   attention). It is not an inference-time configuration. In this
   record's terms the selection is **Family A obtained by retrofit**.
2. **The retrofit result reads COMPARABLE, not improved** — quality on
   par with the full-attention baseline while enabling autoregressive
   generation at linear long-context cost. The paper's superiority
   results are from-scratch architecture comparisons (760M/3B language
   models at 32k context beating GLA and DeltaNet on long-context
   per-token loss; competitive with full attention).

### 12.2 The reliance claim, decomposed (the Session 28 discipline: a premise relied on is a premise measured)

- **C1 — SUPPORTED.** Large-chunk fast-weight layers are
  hardware-efficient (utilization lifted from <5% by orders of
  magnitude; state to ~40% of parameters) and match or beat
  efficient-architecture baselines on long-context tasks; the retrofit
  path is feasible and quality-preserving. The *efficiency* half of
  "output sculpting and efficiency" has real support.
- **C2 — EXTRAPOLATED.** "The research shows this improves base model
  performance," applied to retrofitting an open LLM: LaCT does NOT
  show this. Its LM results are from-scratch comparisons at ≤3B/32k
  against linear-attention baselines; its one retrofit reads
  comparable, not improved. The nearest direct support for
  pretrained-LLM improvement is TTT-NTP (Family B, +3–4 RULER points)
  and aTTT (stability-shaped, §3.4). **C2 is the load-bearing gap that
  R3/R4 exist to measure** — stated here so nobody mistakes the
  premise for a result.
- **C3 — UNTESTED.** "Ensure the meta-prompts are followed as strongly
  as possible … output sculpting" = H2. No literature, LaCT included,
  measures prompt-adherence effects of fast weights. Trellis's
  instruments (protocol-violation counts, answer-channel compliance,
  criterion items) are exactly the right meter; R5 — or an explicit R4
  criterion item — carries it.
- **One overlap named — then CORRECTED by the owner (same day):** the
  first version of this bullet argued LaCT's long-context wins do not
  apply because the RLM removes the corpus from attention. The owner's
  correction, recorded: **large REPL dumps ARE long-context modeling
  in practice** — the code-mediated-text discipline stops the model
  *retyping* retrieved bytes, not *reading* them; printed fetch
  results, block texts, code, and extraction working sets flow through
  attention every turn, and the planned workload uses a substantial
  share of the worker agents' context to code and extract accurately.
  The architecture point survives only in narrow form (the corpus
  RESIDES outside attention and is fetched selectively); the per-run
  token flow is genuine long-context load, so C1's long-context
  quality-and-efficiency results apply to this application directly.
  §3.4's stability-shaped expectation remains the calibration for C2.
- **The authors' own limitation transfers:** state-based models are
  weaker at REASONING — the capability the RLM leans on hardest (LaCT
  pairs fast weights with window attention partly for this reason).
  Any R3/R4 criterion must include reasoning-shaped items; the est
  suite already is.

### 12.3 What "Trellis can do this" means, precisely

Trellis cannot train layers and acquires no training pipeline under
this track. What Trellis contributes — and why the collaboration is
shaped right:

1. **The acceptance instrument:** backend-independent paired-arm
   measurement with pre-stated criteria (§6) — the est suite, the
   protocol counters, OOLONG-hard, the probe suites.
2. **Provenance-gated adaptation data** — the collaborator's "it has
   provenance to check procedure," read in this record's terms: the
   §5.3 adaptation-data policy can be ENFORCED by the substrate. The
   fast-weight training signal can be restricted to engine-verified
   LIVE blocks with the run's retrieval set as the eligibility
   boundary, making *what the model absorbed* auditable the way *what
   the model cited* is today — and directly bounding the §5.3 threat 1
   injection amplification. This is a design seed for the R4 proposal,
   not machinery.
3. **The serving seam:** R2's audit, unchanged by this exchange.

Division of labor recorded: the retrofit training job is
COLLABORATOR-SIDE (or its own owner-funded proposal — either way it is
not a rung of this repo's ladder); Trellis-side rungs R2→R5 are
unchanged in order.

### 12.4 Ladder deltas from this exchange

- **R1:** question 1 ANSWERED (LaCT). Questions 2–4 stand — and
  §12.3's enforcement offer sharpens question 4 into a concrete
  proposal for the collaborator: shall the adaptation-data eligibility
  boundary BE the run's retrieval set?
- **R3** gains a checkpoint requirement: the baseline arm should be
  the SAME open checkpoint the retrofit will start from, so R4's
  comparison isolates the added layers.
- **R4** arms are now concrete: the base open checkpoint vs the same
  checkpoint with trained-in large-chunk fast-weight layers, same
  instruments, adaptation-data policy pre-stated. Its criterion
  inherits C2 and C3 explicitly — a stability-only result is a
  finding, not a failure, but it is not C2, and it gets reported at
  exactly its size (guardrail 8, Session 45's version).
- No rung's gate moved: everything remains owner-approved
  propose-with-estimate.

### 12.5 The empirical decision and the reproduction landscape (added later on July 13, 2026)

The owner's follow-up framed the undertaking as **"our own private
repro study with expansion"** and asked whether the empiricals are
worth running versus checking existing reproduction studies first.
Both were done in order; the landscape check (same day, zero-paid):

- **LaCT is peer-reviewed:** published at ICLR 2026 (no longer just a
  preprint) — confidence in C1 rises.
- **Official code exists:** github.com/a1600012888/LaCT, including
  fused Triton kernels for the TTT layer — a private reproduction
  starts from released code, not a reimplementation.
- **Independent groups already retrain the LM setup:** the KV-binding
  analysis (arXiv:2602.21204) trains its own 760M LaCT-LLM baseline on
  100B FineWeb-Edu tokens; the mechanism has also been adopted
  downstream in other domains (ZipMap, arXiv:2603.04385; elastic
  spatial memory, arXiv:2604.07350). The reproduction half of the
  undertaking carries good priors.
- **A reproducibility-report culture exists in the TTT space**
  (e.g., arXiv:2511.16691 for TTT-on-nearest-neighbors) — but **no
  external study covers C2 or C3**: nobody has published "retrofit
  fast-weight layers onto an open LLM and measure whether the LLM
  improves," and nobody has measured meta-prompt adherence under fast
  weights at all. The expansion half is novel measurement.

**The verdict recorded:** the empiricals are worth running, and they
are the ONLY route to C2/C3 — no amount of literature checking closes
a gap the literature has not measured. The ladder is already shaped as
exactly this study: R3 = the reproduction half on our workload (the
same-checkpoint baseline; does quality hold under the protocol), R4 =
the expansion half (C2 improvement, C3 adherence, the
provenance-gated adaptation-data policy). The house measurement
machinery — pre-stated criteria, paired arms, verdicts recorded
pass-or-fail with actuals — is a reproduction-study harness by
construction. Gates unchanged: each rung still enters as its own
owner-approved proposal.

### 12.6 The chunking — RATIFIED (owner, July 13, 2026): phases 0–3 and the feature-class self-edit rung

The owner ratified the following decomposition the same day, together
with the proposal that Trellis itself authors the Trellis-side code
("a prime target for Trellis editing Trellis and expanding
functionality … build this using Trellis, then we come back and
review it"). Ratification covers the SHAPE — every increment and
every paid run below still enters as its own owner-approved proposal
with its own estimate (the standing gate ceremony is untouched).

**The new rung class this creates, defined here:** a **feature-class
self-edit increment** — a TASK-ASSIGNED functionality increment
authored by Trellis through the stage-2 harness, in the lineage of
the Session 26 W-series and stage-2 increments 1–2 (which were
assigned tasks, not discovered defects). This is DISTINCT from the
defect-class increment 3, whose never-manufacture rule is untouched:
a planted defect invalidates a discovery measurement; an assigned
feature task is not a discovery claim and manufactures nothing.
Feature-class criterion mold (assembled from the standing pieces):
the standing five items (named-file-only diff; the evidence
contract's one recorded insight through the Session 31 gate;
`stage2:check` zero findings; human `git diff` review acceptance;
spend within estimate) PLUS guarded-only (`textedit_raw_splices ==
0`) PLUS the parse gate PLUS the increment's own new unit pins green.
The toolkit never touches git; every diff is human-reviewed; landing
is a human PR — "build using Trellis" means Trellis AUTHORS under the
harness, humans land.

**The spec-before-pen rule (the grounded-authoring lesson applied):**
the seam design record is HUMAN-authored before any T-increment runs
— self-edit runs are only as well-posed as their task text, and the
ratified record is what task texts derive from.

**Phase 0 — human-authored spec sessions:**
- **R2a** — the backend-seam census + the rlms verdict (Session 46's
  §3 objective; read-only, zero-paid; §7 R2 items a/b).
- **R2b** — the seam design record (§7 R2 items c/d): config shape,
  typed refusals, the three-way split backend (root completion /
  worker completions / embedder), today's behavior as the
  byte-identical default; each T-increment's scope and task-text
  skeleton pre-stated in it.

**Phase 1 — the Trellis-edits-Trellis T-series (feature-class
increments; each owner-gated ≤$5, one increment-record each in the
§5e/§5g mold, human-reviewed diff each; smallest first — the
executable-class ladder has never landed a run, so the first rung is
deliberately tiny):**
- **T1** — the config surface: backend config keys + validation +
  typed refusals + unit pins (no call-site change).
- **T2** — `buildAgentEnv` forwarding/strip for the new config, with
  its unit pins (the experiment-flag mold).
- **T3** — the `trellis_agent.py` construction-site rewire
  (`backend_kwargs` from config; default byte-identical; the policy-2
  substrate already covers this file, so graph-informed editing works
  today).
- **T4** — the fixture-endpoint drill: a zero-LLM stub
  OpenAI-compatible server (the fixture-MCP-server precedent) proving
  the byte-identical default and the seam switch.
A failed T-increment gets the increments-1/2 treatment: diagnose,
close the class mechanically, retry as its own proposal.

**Phase 2 — measurement sessions (runs, not edits):** R3a serving
bring-up + protocol smoke; R3b the paired baseline measurement (the
reproduction half); then the R4 chunks when the collaborator's
retrofit checkpoint lands (exact-pinned): R4a checkpoint acceptance +
smoke, R4b the paired C2 measurement, R4c the C3 adherence
measurement, R4d the adaptation-data-policy record (for Family-A
layers the adaptation data IS the token stream — the policy chunk
states what enters context and how the §12.3 provenance gating
applies).

**Phase 3 — R5** (meta-prompt fast-state, H2 isolated).

**Dependencies named:** (1) this record lives in `docs/` — outside
extraction scope — so T-series runs cannot query the graph about the
spec; task text carries the spec verbatim (the increments-1/2
channel) until stage-1b chunk A lands (a natural synergy, not a
prerequisite). (2) Refresh-before-use applies to every T-increment's
target area (the split-scope recipe; `src/rlm` is the policy-2 leg).

### 12.7 External cost-performance evidence and an adaptation-behavior avenue (added July 13, 2026, same day)

Three items logged after the §10 list was compiled, recorded here because they sharpen the R3/R4 criterion and the estimate basis; no gate moves.

1. Cost-performance frontier (Szafer et al., ICLR 2026; OpenReview tWAnCRYMcT). A unified empirical study of test-time agent adaptation under verifiable feedback (binary correctness, unit tests), streaming evaluation scored on pre-update predictions, adaptation compute measured as wall-clock, comparing in-context memory (ExpRAG, ReMem) against in-weights GRPO (LoRA, full fine-tuning) on open reasoning models (Qwen3-8B, Olmo3-7B). Two findings bear on this track:
   - Gains concentrate on tasks that need better reasoning over knowledge the model already holds, and are near-zero on tasks that need facts the model never learned. On Qwen3-8B, AIME24 rises 0.536 to 0.642 for both LoRA and full fine-tuning; AIME25 rises 0.429 to 0.500 (LoRA) and 0.464 (full fine-tuning); GPQA and MMLU-Pro show no consistent gain. This is external support for the H1 framing and against "quality of response overall," and it hardens the existing requirement that an R3/R4 criterion be scored on reasoning- and protocol-shaped items; a knowledge-recall criterion would flatline for reasons unrelated to whether TTT works.
   - The backward pass is a small fraction of per-step wall-clock; forward-pass generation (rollout) dominates. Consequence for R4's propose-with-estimate: the paid estimate is a generation-token estimate, not a training-cost estimate, and LoRA versus full fine-tuning is not the cost driver (the paper attributes its slower LoRA wall-clock to an adapter merge-and-reload artifact, not an inherent cost). This sets the unit the R4 estimate is built in; it moves no gate.

2. LoRA and catastrophic forgetting (Hu et al., *Test-Time Learning for Large Language Models*, arXiv:2505.20633, ICML 2025). The paper reports (its Observation 3) that LoRA mitigates catastrophic forgetting more effectively than full-parameter updates in the test-time-learning setting, and adopts LoRA for its test-time updates on that basis. Recorded as complementary to item 1, not conflated with it: the cost-Pareto study does not measure forgetting (it defers retention to future work), so the drift-bound property rests on this citation alone, and on that paper's own TTL-setting observation rather than an independent head-to-head. If an R4 arm is instantiated, this is the citation behind preferring a low-rank adapter as the retention-bounding choice.

3. Workspace manipulation as a potential avenue of investigation (not a rung). The global-workspace / Jacobian-lens result (Gurnee et al., *Verbalizable Representations Form a Global Workspace in Language Models*, transformer-circuits.pub/2026/workspace, July 6 2026) identifies a small, causally-privileged subspace that a residual-stream read can inspect; the article's own experiments are on Claude models only. What makes it an avenue for a track that can only instrument open checkpoints is the separate tooling: Anthropic released the reference implementation `anthropics/jacobian-lens` (Apache 2.0), which fits the lens on open-weight decoders, and independent third-party replications on small open models exist (e.g. github.com/tao-hpu/jspace-replication, github.com/solarkyle/jspace, spanning GPT-2 124M through Qwen3 and Gemma-3 sizes). Reproduction is partial and mixed: the lens read-out reproduces and beats a logit-lens baseline, while some higher-order effects (e.g. hidden-intermediate multi-hop) do not reproduce at the smallest scales. The possible avenue: use that instrument to probe, and perhaps manipulate, the subspace to strengthen meta-prompt adherence, i.e. H2's mechanism approached through measurement rather than fast weights. Recorded as an avenue only; out of scope for R2 through R5, no criterion attached, no claim, its viability explicitly gated on the still-partial open-checkpoint reproducibility, and subject to the same paired-arm and owner-gated discipline as everything else here should it ever be taken up. **Probe-sensitivity caveat:** a probe that reads *no effect* is informative only once a positive control has shown the probe can detect the effect it seeks — otherwise "no detectable effect" is a blind instrument, not evidence of absence (the positive-control duty, §6; the `self-play` skill's discipline 6, which learned this the hard way when a maximal-strength probe failed to fire across escalating designs).

No gate moved; no default changed; no TTT claim attaches without a paired arm.

## 13. R2a — the backend-seam census and the rlms verdict (Session 46, July 13, 2026)

Rung R2a executed as ratified (§12.6 Phase 0): a READ-ONLY census,
zero paid spend, zero code bytes moved. Method: grep-driven sweep of
`src/rlm/`, `src/workers/`, `src/core/`, `src/config/`, and
`scripts/` for transport constructions, model-id literals, pricing
constants, token accounting, and embedding calls (every
`chat.completions.create` and `embeddings.create` site in the tree is
disposed below), plus a read-only inspection of the installed
`rlms==0.1.3` package (import name `rlm`, site-packages; guardrail 10
respected — nothing modified). The seam design built on this census
is R2b's, the next session.

### 13.1 The rlms verdict — YES, with quoted evidence

**rlms==0.1.3 admits a base-URL/backend override WITHOUT library
modification.** The evidence, from the installed package:

1. `rlm/core/rlm.py` — the constructor's first two parameters:
   `RLM(backend: ClientBackend = "openai", backend_kwargs: dict[str,
   Any] | None = None, ...)`. Trellis today passes only
   `backend_kwargs={"model_name": "gpt-5.4-2026-03-05"}` and takes
   the `"openai"` default backend.
2. `rlm/clients/__init__.py::get_client` routes eight backends:
   `['openai', 'vllm', 'portkey', 'openrouter', 'anthropic',
   'azure_openai', 'gemini', 'vercel']`. The `vllm` arm is the
   OpenAI client with a mandatory endpoint: it asserts
   `"base_url is required to be set to local vLLM server address
   for vLLM"` and then constructs the same `OpenAIClient`.
3. `rlm/clients/openai.py::OpenAIClient.__init__(self, api_key=None,
   model_name=None, base_url=None, sampling_args=None, **kwargs)` —
   `base_url` is a FIRST-CLASS constructor parameter, passed straight
   into `openai.OpenAI(**client_kwargs)`. The class docstring says it
   plainly: "LM Client for running models with the OpenAI API. Works
   with vLLM as well."
4. Sub-call separability exists in the library itself:
   `other_backends`/`other_backend_kwargs` (exactly one additional
   backend supported) lets depth-1 sub-calls run a DIFFERENT
   backend from the root — relevant to R4 arm design, unused today.

**The seam call is therefore additive kwargs at the two existing
construction sites** (T3's exact scope):
`RLM(backend="openai"|"vllm", backend_kwargs={"model_name": ...,
"base_url": ..., "api_key": ...})`. No rlms byte moves.

**Recorded caveats the T-series and R3 must respect:**

- **The usage requirement (the one hard compatibility constraint
  beyond chat-completions shape):** `OpenAIClient._track_cost`
  RAISES `ValueError("No usage data received. Tracking tokens not
  possible.")` when a completion response lacks `usage`. Any serving
  endpoint must return usage on non-streaming completions (vLLM does
  by default). The R3a smoke test asserts this before anything else.
- **Token/context coupling is soft:** `rlm/utils/token_utils.py`
  keys context limits and tokenizers by model name with safe
  fallbacks (unknown model → 128,000-token default; tiktoken →
  `cl100k_base` → chars/4). Consulted only under `compaction=True`,
  which Trellis never sets. Non-blocking.
- **API-key resolution:** known base URLs map to their own env keys
  (`OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `AI_GATEWAY_API_KEY`,
  `PRIME_API_KEY`, read at import time); an unrecognized/local
  base_url leaves `api_key=None`, which the openai SDK resolves from
  `OPENAI_API_KEY` env — a local endpoint typically wants an explicit
  dummy `api_key` kwarg so runs do not depend on an unrelated real
  key being present.
- **rlms calls `load_dotenv()` at import** (both
  `rlm/clients/openai.py` and `rlm/clients/__init__.py`): a `.env`
  file in the spawned agent's working directory is read into its
  environment. An unmanaged credential input channel, recorded here
  for R2b's forwarding design.

### 13.2 The census

Legend: "moves?" = does the site have to change (or change meaning)
when the completion backend moves. Classes ordered by seam relevance.

**Class 1 — root RLM completion (the seam; T3 rewires exactly these).**

| Site | Assumption | Moves? | Pinned by |
|---|---|---|---|
| `src/rlm/trellis_agent.py:353` (author mode) | `backend_kwargs={"model_name": "gpt-5.4-2026-03-05"}`; backend defaults to `"openai"`; transport+key from ambient env | YES — T3 | No direct pin (paid-run surface; `test:rlm-sandbox` stubs the `openai` module) |
| `src/rlm/trellis_agent.py:589` (research mode) | same | YES — T3 | same |
| `src/rlm/trellis_agent.py:97,111` (`make_entailment_check`) | direct `openai.OpenAI()` + hardcoded model literal; constructed only under `TRELLIS_CITATION_ENTAIL=1` (experimental) | YES if the checker is kept; R2b decides whether it follows the seam or stays a frozen instrument | none |
| `scripts/probe_workspace_lineage.py:157`, `scripts/probe_workspace_paired.py:89` | same `backend_kwargs` mold | NO — frozen measurement instruments; retrofitting them would invalidate comparability with their recorded runs | recorded here |

**Class 2 — worker/engine completions (model id ALREADY
config-shaped; only the transport is assumed).**

The model id routes through ONE seam today: `EXTRACTION_MODEL`
(`src/config/index.ts:109`, zod default `'gpt-5.4-2026-03-05'`) →
`config.llm.extractionModel` (`index.ts:359`). Consumers:
`extraction_worker.ts:77`, `supervisor_worker.ts:76`,
`verification.ts:217` (`makeOpenAIClassifier`),
`entailment_detection.ts:208` (`makeOpenAIEntailmentJudge`),
`alias_resolution.ts:199` (`makeOpenAIAdjudicator`),
`decision_source.ts:51` (`makeOpenAIDecisionSource`),
`resolution_worker.ts:50,65`, `agent_worker.ts:188` +
`verification_worker.ts:79,135` (metric labels),
`scripts/resolve_sweep.ts:67`. **A worker-side model change is an
env-var change today; no code moves.** The transport is zero-arg
`new OpenAI()` at seven sites (`extraction_worker.ts:26`,
`supervisor_worker.ts:25`, `verification.ts:220`,
`entailment_detection.ts:211`, `alias_resolution.ts:202`,
`decision_source.ts:54`, `api/server.ts:263`) — SDK-default
transport, see §13.3. `parseLlmResponse` at the consumption boundary
is model-agnostic by construction (guardrail 7 holds under any
backend).

**Class 3 — the embedder (NON-GOAL, §4.2; listed so the boundary is
explicit).**

| Site | Call |
|---|---|
| `src/workers/extraction_worker.ts:30,193–197` | `EMBEDDING_MODEL = 'text-embedding-3-small'` literal; per-block `embeddings.create` |
| `src/rlm/trellis_tools.py:804–806` | `vector_search` query embedding, same literal |
| `src/api/server.ts:263–265` | `/retrieve` vector-fallback embedding, same literal |
| `scripts/chunking_seam_queries.ts:83–84` | the eight PINNED seam queries (standing instrument — never tuned) |
| `scripts/exp_citation_ab.ts:43,98` | experiment instrument, frozen |

All three production embedding sites are schema-coupled
(`vector(1536)` + HNSW, `src/config/schema.ts` /
`search_ast_nodes`). The embedder does NOT move with the completion
backend; an embedder move is a substrate-identity event. §13.3 names
the one place this boundary is currently soft.

**Class 4 — pricing constants (estimate-only by design; a backend
move re-prices them, never silently).**

| Site | Constant | Consumers | Pinned by |
|---|---|---|---|
| `src/benchmarks/oolong/scoring.ts:13–14` | `PRICE_PER_M_INPUT = 2.5`, `PRICE_PER_M_OUTPUT = 10` ("used when the backend does not report exact cost") | `poison_drill_runner.ts`, `exp_effective_context.ts` (spend gate, lines 1628–1630), `exp_citation_ab.ts`, `exp_citation_metadata.ts` | `scoring.test.ts:132` |
| `src/core/authoring/estimate.ts:16` | `AUTHOR_EST_PRICE_PER_1K_USD = 0.02` | `author_module.ts` refuse-before-spend ceiling (line 370, `--max-spend-usd`) | `estimate.test.ts` |

These gates bound OPENAI spend. An R3 serving arm prices in
GPU-hours or hosted per-token dollars per the §7 cost doctrine — its
proposal restates cost in those units rather than stretching these
constants.

**Class 5 — token accounting (moves cleanly; one recorded
asymmetry).**

- Python: the telemetry payload's `input_tokens` / `output_tokens` /
  `reported_cost_usd` come from rlms's `UsageSummary`; `model_usage`
  is `usage_dict["model_usage_summaries"]`, keyed BY MODEL NAME — a
  new backend appears as a new key, no shape change; the Node
  telemetry scanner tolerates additive fields (pinned).
- TypeScript: `llm_usage.ts` `chatUsage`/`embeddingUsage` tolerate a
  MISSING `usage` block (count the call, zero tokens, never throw) —
  the recorded asymmetry with rlms's `_track_cost`, which THROWS
  (§13.1). Metric labels are `operation`/`model` — the model name is
  already a bounded label value, so a backend change changes label
  VALUES only, within the T16 house style.
- `reported_cost_usd` is `None` on plain OpenAI endpoints today
  (rlms extracts cost only from OpenRouter-shaped responses); every
  house spend gate uses token counts × Class-4 constants, so nothing
  breaks when a new backend also reports no cost.

**Class 6 — report stamps and prose (recorded strings; they gate
nothing and move as wording only).** `oolong_runner.ts:137`,
`update_drill_runner.ts:199`, `poison_drill_runner.ts:467` (report
`model` fields; the poison drill already stamps `'ground-truth
oracle (LLM-free)'` in rehearsal), `author_module.ts:402`
(provenance prose), the comments at `oolong/scoring.ts:11` and
`estimate.ts:8`, `exp_citation_ab.ts:44` (`CHECKER_MODEL`, frozen
experiment instrument), and `scripts/pocs/*` (`gpt-5.4-mini`
literals; PoC archive class, frozen).

### 13.3 The unmanaged pass-through (the census's one real discovery)

Every production client in the tree — the seven zero-arg
`new OpenAI()` constructions (Node SDK `openai@^6.45.0`), the two
Python `openai.OpenAI()` constructions, and rlms's own
`OpenAIClient` with `base_url=None` — resolves its base URL from the
SDK's ambient `OPENAI_BASE_URL` environment variable when unset.
Verified in both installed SDKs (`node_modules/openai/client.js`
line 140; site-packages `openai/_client.py` line 251). Three
consequences, recorded:

1. **The transport is ALREADY overridable today with zero code
   change** — but UNMANAGED: no config validation, no typed refusal,
   no telemetry visibility, no test pin.
2. **`buildAgentEnv` (`src/workers/rlm_job.ts`) spreads `...base`
   and neither deliberately forwards nor strips `OPENAI_BASE_URL`**
   (`OPENAI_API_KEY` inherits the same way, by design — the agent
   needs it). An `OPENAI_BASE_URL` inherited from the worker's
   environment would silently redirect the child agent's root
   completions, the experimental checker client, AND the
   `vector_search` EMBEDDER together — exactly the coupling §4.2
   forbids (the embedder must never move as a side effect of the
   completion backend moving). The worker-side clients read the same
   ambient variable, so engine completions and the extraction
   embedder are coupled the same way.
3. **This is not a defect today** — no environment sets the
   variable, no behavior has changed, nothing is broken; it is a
   designed-in SDK affordance that the house config discipline does
   not yet manage. It is the precise gap the ratified T-series
   closes: T1 gives backend choice a validated config surface with
   typed refusals; T2 makes `buildAgentEnv` forward-or-strip it
   under the experiment-flag mold (the `TRELLIS_MCP_SERVERS`
   discipline); T3 passes explicit `backend_kwargs` so the child
   never resolves its transport from ambient env. **R2b's design
   must decide:** whether the config seam strips `OPENAI_BASE_URL`
   unconditionally so backend choice is expressible ONLY through
   validated config — the recommendation this census hands R2b.

### 13.4 What R2a does not do

No implementation, no config key, no env twin, no default change —
the seam design (config shape, typed refusals, the three-way root /
worker / embedder split, T-increment task-text skeletons, the R3
proposal skeleton) is R2b's deliverable, human-authored
spec-before-pen per §12.6. The embedder stays a non-goal (§4.2). The
probe scripts and experiment instruments named frozen above stay
frozen.
