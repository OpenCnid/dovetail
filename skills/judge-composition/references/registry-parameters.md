# The four registries: what exists, what does not, and what to do about it

Written 2026-08-01, when the originating repository was still readable, to settle
a gap this repository had recorded but not resolved: **the composition schema
selects qualified parameters from four registries, and no enumeration of those
registries shipped anywhere.**

The answer turns out to be in two parts, and the first one is not "we lost it."

## Part 1 — There is no authoritative enumeration, and that is a finding, not an omission

**No registry listing exists in the originating repository**, at the pinned commit
or at its final HEAD. This was checked by searching every `.md` and `.ts` file for
registry-shaped tokens and for any enumerating heading. Nothing of the kind is
there.

The reason is recorded in that repository's own audit —
`PRIMITIVE_ENCODING_AUDIT.md`, *"Finding 2 — the four registries do no
computational work"*:

> In the engine `qualifiedParameters` is `z.array(z.string().min(1)).min(1)` —
> free strings, no enum, no validation of the registry prefix.

and:

> The four plane names — Emotional/Logical/Sensorial/Ethical — are a prefix
> convention inside an unvalidated string. They are never extracted, compared, or
> gated on.

Kinship comparison operated at `registry.parameter` granularity; nothing anywhere
split on `.` to recover the registry name. The audit closed by recording what was
**owed**: a decision on whether the registries are load-bearing at all, noting
that if they are a *lens* rather than a mechanism, then "no gate should ever be
described as resting on them."

**That decision was never made.** So the honest statement is not that an
enumeration was lost with the repository — it is that one was never written,
because nothing in the implementation required it.

## Part 2 — A working set does exist, and it is preserved here

The reference implementation carried a concrete, role-partitioned selection with
each drawback class mapped to the parameter that licenses it. That is the closest
thing to a registry that ever existed, and it is now mirrored byte-for-byte at
[`judge_panel.ts`](judge_panel.ts) — origin path `src/core/graph/judge_panel.ts`,
blob `faf4f19ea1deafdf12db778a4389d99878da0540`, verified by SHA rather than by
having been copied.

Fourteen distinct qualified parameters, as `ROLE_DEFINITIONS` held them:

| Role | Qualified parameters | Drawback classes mapped to them |
|---|---|---|
| **J1 Grounding** | `logical.evidence_quality/cited`, `logical.falsification/cited` | `unsupported_citation`, `overclaimed_evidence` → evidence_quality; `contradicted_by_cited_bytes` → falsification |
| **J2 Coherence** | `logical.consistency/internal`, `logical.consistency/history`, `logical.constraint_satisfaction/kind` | `self_contradictory`, `history_inconsistent`, `kind_incoherent` respectively |
| **J3 Corroboration** | `logical.induction/world`, `logical.falsification/independent`, `logical.source_dependence/independent`, `sensorial.observation_quality/independent` | `uncorroborated` → induction/world; `authority_contradicted` → falsification/independent; `corroboration_ambiguous` → observation_quality/independent |
| **J4 Audit** | `logical.hidden_assumptions/audit`, `logical.goodharting/audit`, `logical.coverage/audit`, `logical.abduction/audit`, `logical.counterfactuals/audit` | `rubric_gamed` → goodharting; `convention_blind` → coverage; `systematic_drift` → abduction |

Two observations worth carrying:

- **Thirteen of the fourteen are `logical`.** One is `sensorial`. `emotional` and
  `ethical` appear in no selection at all. That is the prefix-convention finding
  visible from the other side: three of the four planes did no work in the only
  implementation that existed.
- **J3's input list deliberately omits `citedBytes`** and J4's omits
  `beliefOpinion`/`compositionState`. The blindness structure is enforced in the
  input allowlists, not in the parameter names.

## Part 3 — This is a record, not a roster

**Read this file as evidence about vocabulary, never as a cast to select from.**

The skill's own rule is that there is no default cast, and that a stored
composition is a record rather than a roster a later ceremony picks from. This
file is a stored composition. Shipping it would defeat the skill's central claim
if it were read as "the judges," so it is not that: it is one worked
instantiation, in one domain, whose registries did no computational work.

**What to do when you compose:**

1. Compose seats from the four invariant roles and the context in front of you.
2. Where a parameter from the table above genuinely fits your driving question,
   **reuse the exact string** — the disjointness gate compares strings, so a
   private synonym silently defeats it.
3. Where none fits, coin one in the `registry.parameter/aspect` form and state
   that you coined it. Do not stretch an existing name to cover something it was
   not written for.
4. **Do not treat the four plane names as gates.** The audit's finding stands:
   nothing ever validated them. Any claim that a gate rests on a registry is a
   claim this repository cannot support.

## A related file that is *not* this

The `better-skill-creator` skill ships `references/judge-registries.md`, which is
a fuller enumeration in the same `registry.parameter/aspect` grammar. **It is not
this registry and does not close this gap.** That file says so itself: its tables
are "this bundle's own vocabulary for one domain — grading statements about a
run's outputs — not a copy of the upstream registries, and they are deliberately
narrower." It credits this skill as the origin of the four-registry structure and
states that nothing in it depends on this skill being installed.

Borrow its *grammar* freely. Do not import its *names* into a composition here and
call them upstream, which would manufacture the enumeration this file just
established never existed.
