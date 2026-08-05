# Composition from categoric primitives

**Status: FOUNDATIONAL LESSON — recorded July 19, 2026 (Session 71) at
owner direction.** States a design principle the house already held in
several places and enforced in none, and the failure that made its
absence visible. Changes no engine code and authorizes no build. Where
it touches ratified records
([`RECONCILIATION.md`](../product/epistemic-support/RECONCILIATION.md),
[`JUDGE_COMPOSITION_GAME.md`](../product/epistemic-support/JUDGE_COMPOSITION_GAME.md)),
those amend only by owner dated entry; §6 lists what is owed rather
than performing it.

---

## 1. The principle

**Harness functions compose from categoric primitives at each phase of
the work. There are no default instances.**

A primitive is a parameter registry plus a schema plus a composition
method. An instance is a sparse selection from those registries, made
for the thing in front of it. The registries are stable and few; the
instances they admit are effectively unbounded, and every one is a
special case.

- **A frame is invariant** — field names, verdict enums, schema
  shapes, and the structural slots whose distinctness the design
  depends on.
- **An instance is not** — selections, orientations, closed
  taxonomies, names, angles.

Writing an instance down does not make it a frame. Byte-pinning it,
registering it, or hard-coding it into a wire schema *promotes* it to a
frame without anyone deciding to, and afterwards the system can no
longer express the thing it was built to do.

## 2. Why: examples anchor, primitives do not

This is the [hypershot protocol's](../../.claude/skills/judge-composition/README.md)
reason for existing, and it is the load-bearing half of this record.

We use primitives to **minimize the impact on downstream context**. A
hypershot is a frame with free variables — a fancy mad-lib — and it can
be anything within its reasoning shape. It primes *form* without
priming *content*.

A concrete example does the opposite, and it does it permanently. If
the example is about changing a tire, every problem downstream starts
to look like changing a tire. The example does not sit quietly beside
the abstraction it was meant to illustrate; it becomes the prior
through which everything after it is read. That is why a hypershot uses
`{Warm_Professional_Response}` rather than `"Hi there!"`, and it is why
one zero-semantic frame implicitly enumerates every valid instantiation
while scattered samples only invite interpolation between themselves.

**The failure this record exists for is that exact mechanism, operating
on the program's own documentation rather than on a model's context
window.**

## 3. What actually happened

The four judge roles entered this program as **teaching examples**.

The composition concept was alien to a prior session. The collaborator
composed the knowledge to convey it, and — *for the purpose of teaching
the coding agent building Trellis* — supplied specific examples to
crystallize what composition IS and how it works. S10's eleven-judge
list is titled "A useful first ecology." The four roles were a handful
of options drawn from a vast potential space.

They were never intended as a cast.

But an example anchors. Across seven documents, each restating the
principle correctly in prose, the examples hardened into law:

| Layer | What it says | What it encodes |
|---|---|---|
| S10 source | registries, not judges; a judge is a sparse selection | — |
| FOUR_JUDGE_DESIGN | the four are "a minimal ecology instance" | "a fifth judge with a blindness profile **already on the panel**"; per-role anchor fixtures |
| JUDGE_CONTRACT_TEMPLATE | frames with free variables | **taxonomy class names byte-identical across every invocation**; role enum closed in the wire schema |
| RECONCILIATION (ratified) | "a minimal ecology instance" | per-role taxonomies frozen as law; **"a four-role fixed panel"**, discarding S10's context-signature, semantic-retrieval and coverage layers |
| COMPOSABLE_RUBRICS_DESIGN | "composable" | *"'Adaptively-aligned' means the rubric **selection** fits the claim, not that the rubric mutates"* |
| EPISTEMIC_SUPPORT (doctrine) | — | "**a** panel of differently-blind roles — grounding, coherence, corroboration, and an audit role" |
| JUDGE_CONVOCATION_DESIGN | — | four manifests "**can land any time before the run as ordinary operator work**" |

Each step is small and locally defensible. The composite is a default
cast with the composition machinery discarded. RECONCILIATION dropped
S10's layers 1, 2 and 5 — context signature, semantic retrieval,
coverage/complementarity — on the stated grounds that *"a four-role
fixed panel does not need"* them. That sentence is the hinge: true of a
fixed panel, and a fixed panel is the thing that must not exist. The
layers discarded are precisely the ones per-context composition
requires.

**The general form: prose describes the primitive, machinery encodes an
instance, and machinery wins.** An instance that reaches a schema, a
byte-pin, a registration, or an operator checklist has become law
regardless of the hedge in the paragraph above it. This is
[`CODE_MEDIATED_TEXT.md`](CODE_MEDIATED_TEXT.md) pointed at design
records rather than content: the encoding is the claim.

## 4. What the judges actually are

**Collaborator framing (M. Murphy), owner-relayed July 19, 2026 —
recorded as direction and as the frame the program is building toward.
Not yet a dated entry in the ratified records.**

The meta-prompt judges are a **Grothendieck cover over an arbitrary
linguistic topology.**

A cover is not a cast. It is whatever collection of opens is needed to
cover the space in front of you, and it varies with that space. You do
not carry a standard cover between topologies; you construct one for
the topology you have, and the requirement it must satisfy is
**coverage** — *"we need total coverage!"* The house already holds the
other half of this: sections glue only where they agree, and
disagreement is an output rather than an average (S10's sheaf-style
gluing; IEG law L4; R-30's no-global-section outcome).

Read that way, the design falls out:

- **Four is not a number the design requires.** Role slots earn their
  place by buying a blindness no other slot buys — that is what makes
  their verdicts compose. A cover needs enough opens to cover, not four.
- **Judges are composed in language, from the REPL's own idea-space,
  prior to evaluation.** The facts and beliefs in the REPL are the
  topology; the judges are the cover constructed over it.
- **This reaches the audit seat too.** Judging judges largely fixes how
  that seat can fail, so its failure taxonomy stays near-invariant —
  but its *name and angle* compose per context and are load-bearing.
  What the audit does depends on what it is judging the judges judge.
- **The space is vast.** On the order of 10^100 possible judges; every
  one a special case. That size is not a problem to be managed, it is
  the source of the system's power, and it is why this approach was
  chosen.

Consequently the composition meta-prompts must be **built and tested**.
Until they are tested, the system is trusted or simulated — never
assumed.

**And this is not only about judges.** Other elements of Trellis are to
be treated the same way: think in categoric primitives and in how the
harness functions compose from them at each phase of the work. Judges
are simply the clearest object lesson in how it works.

## 5. What it cost

Session 71 was instructed to author four rubrics with fixed per-role
taxonomies, byte-pin them, ingest them, register them as a standing
roster, then find candidates for them to judge. It did all of that. The
work was clean by every check the house had: rubric questions verbatim
against RECONCILIATION §2, anchors five-and-five across every closed
class, extraction-free ingest, consistent uncontested read-back, green
drills, zero spend.

It was the wrong object, and no check could have said so, because every
check derived from the same instance-promoted-to-frame.

The collaborator stopped it in review. The registration was rolled back
and the fixtures deleted the same session — deleted rather than
relabeled, because §2 is the reason: four named judges sitting in the
repository under any label would keep anchoring every future judge to
those four. They remain in version history at `c9d417d`, which is
sufficient; preserving them anywhere else was over-caution.

**The shape of the failure that made it reachable has its own name and
home:** *derived-source substitution* — acting on a compression of a
governing record instead of retrieving the record, on a load-bearing
act. It is the pillar's "never copies" applied to authority rather than
bytes, and it is stated normatively in
[`CODE_MEDIATED_TEXT.md`](CODE_MEDIATED_TEXT.md) §2.9, with the
operational rule at `AMBIENT.md` 18 and the authority ordering it
depends on at `AGENTS.md` §1.5. It occurred three times in this one
session; the instances below are the first and second.

Three failures made it reachable:

1. **The session never read the game record**, whose rule 4 forbids
   what it built. No top-level index pointed there — not README,
   AGENTS.md, docs/README.md, ORIENTATION, GLOSSARY, RESEARCH_MAP, or
   EPISTEMIC_SUPPORT. Every reading path reached the superseded
   FOUR_JUDGE_DESIGN.md first.
2. **The session never invoked the `judge-composition` skill**, which
   states the invariant/adaptive split in its second paragraph. It
   lived outside the repository, so it was not part of the collection a
   session inventories. It is now versioned at
   [`.claude/skills/judge-composition/`](../../.claude/skills/judge-composition/README.md).
3. **The instruction it followed was itself drift.**
   JUDGE_CONVOCATION_DESIGN §11.2 item 3 was written July 19 — one day
   *after* the game was ratified July 18. A ratified rule did not
   propagate into the road map written beside it.

The generalization worth keeping: **a green suite proves the instance
was built correctly and says nothing about whether it should exist.**
The house already knows correct ≠ reachable (`AMBIENT.md` rule 15); this
adds correct ≠ *the right kind of thing*.

## 6. What is owed, and by whom

Corrections to ratified records are owner acts by dated entry. This
record names them; it performs none.

- **RECONCILIATION §1/§2** — per-role taxonomies and the "four-role
  fixed panel" rationale need reframing as one composition instance,
  and S10 layers 1, 2 and 5 reopening.
- **JUDGE_CONTRACT_TEMPLATE §1** — the layer rule places taxonomy class
  names and role names on the invariant side; they belong on the
  adaptive side, with the *shape* invariant instead.
- **JUDGE_CONVOCATION_DESIGN §11.2** — items 3 and 4 sequence
  roster-then-docket; composition follows the candidate. Merging them
  is the substantive fix.

### 6.1 Resolved (dated entry — July 21, 2026)

All three owed corrections have since landed by dated entry in their
home records; this register is closed. Verified this session:

- **RECONCILIATION §1/§2** — RESOLVED by
  [`RECONCILIATION.md`](../product/epistemic-support/RECONCILIATION.md)
  §7.1 (July 19, 2026): §7.1(a) reads §2's completed definitions as one
  composition instance, "not law"; §7.1(b) reopens S10 layers 1, 2 and 5
  behind their own proposal.
- **JUDGE_CONTRACT_TEMPLATE §1** — RESOLVED by
  [`JUDGE_CONTRACT_TEMPLATE.md`](../product/epistemic-support/JUDGE_CONTRACT_TEMPLATE.md)'s
  July-19 amendment (role and taxonomy names moved to the composed side)
  and its July-21 dated correction carrying the one exception (the audit
  seat's *failure* taxonomy stays invariant vocabulary).
- **JUDGE_CONVOCATION_DESIGN §11.2** — RESOLVED by
  [`JUDGE_CONVOCATION_DESIGN.md`](../product/epistemic-support/JUDGE_CONVOCATION_DESIGN.md)
  §11.2's July-19 dated entry merging items 3 and 4 ("composition
  follows the candidate"), pointing to `JUDGE_COMPOSITION_CEREMONY.md`.

The §6 intro rule stands unchanged: this record still performs no
corrections; it records that the ones it named were performed in their
home records.
- **EPISTEMIC_SUPPORT §5** — states a cast in adopted doctrine.
- **COMPOSABLE_RUBRICS_DESIGN §4** — "adaptive means selection, not
  mutation" is the opposite of composition-from-primitives and needs
  re-deciding before it is built.

Index-surface repairs — not ratified-record edits — were made in the
same session; see [`docs/README.md`](../README.md) and `AGENTS.md`.

## 7. The standing rule

Before encoding any instance of a composed thing — a judge, a rubric, a
panel, a prompt cast — ask which side of the line it falls on:

- Genuinely invariant across every context the system will ever meet?
  It may enter a schema, a byte-pin, or a registration.
- One selection made for one context? It may not, however
  well-evidenced. It is an example, it is labeled as one, and the
  machinery must remain able to compose a different one.

Two tells:

**The plural test.** If a second instance would need a second
registration under a different name, the first was never a frame.

**The teaching test.** If it entered the record to *explain* how
something works, it is an example, and examples anchor. Give it the
shortest half-life you can: illustrate, then delete. An example that
survives in the repository will be found by a later reader who has no
way to know it was only ever a mad-lib filled in once.
