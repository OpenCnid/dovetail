# Deviation register

*Working document. It records where the shipped artifact stands relative to the
work it credits, who has ruled on what, and what remains open — so a later
session can act without re-deriving any of it. Entries are closed by a named
authority on a dated ruling, never by inference.*

## Why this file exists

`README.md` states the relationship this repository has to its source:

> This repository ships the **deployed artifact, not the educational version.**
> The curriculum is the canonical authority; where the two differ, it wins.

That clause is a standing constraint on every edit. It was unfalsifiable from
inside the repository until **2026-08-03**, when Matthew Murphy supplied the
full nine-part curriculum as PDFs and Cnid placed them at `D:\lexideck\`. All
nine were read in full that day. Provenance is now a settled question rather
than an open one, and every entry below carries its answer.

The reason this matters runs in one direction only. A change that departs from
the source while the artifact still carries the source's credit is authorship
wearing the compression's credit — the failure CC BY attribution exists to
prevent. Marking a departure *as* a departure is what makes it legitimate. This
file is the mark.

CC BY 4.0 § 3(a)(1)(B) independently requires a licensee to indicate if changes
were made. A register satisfies that obligation in a checkable form.

## The curriculum, as read

Murphy's note said Parts 1–3 and 5–8 are full lessons, #4 a preview, #9 a
review. **The artifacts say otherwise on one point:** Part 3 titles itself
"Sneak Peek: Powerful Prompting Tools" and teaches no notation, while Part 4 is
a full lesson pair (Lessons 9–10) plus an appended syntax primer. The preview is
Part 3.

Part 3's Lesson 8 is an index binding each technique to the part that teaches
it, and it is the origin of the skill's A–E ordering:

| Skill | Technique | Source |
|---|---|---|
| §A | Tags | Part 4 (Lessons 9–10) |
| §B | Hierarchical Markers / Outlining | Part 5 (Lessons 11–12) |
| §C | Placeholders / Variables | Part 6 (Lessons 13–14) |
| §D | Collections | Part 7 (Lessons 15–16) |
| §E | Attention Management | Part 8 (Lessons 17–18) |
| — | Golden rules | Part 1 (Lessons 1–3) |
| — | Organizing complex requests | Part 2 (Lessons 4–6) |
| — | Combining techniques, best practices | Part 9 (Lessons 19–20) |

Two upstreams sit above these PDFs and are **not** in hand: Parts 4 and 5 both
credit a file called `Lessons.txt` ("Simplified from `Lessons.txt`"), and Part 6
cites "Assignment 2." The PDFs are themselves a simplification. Where this
register says "not in the curriculum," it means *not in these nine PDFs*.

## How entries are classified

Each entry names the gate it must pass, not how bad it is.

| Class | Meaning | Status |
|---|---|---|
| **A** | Internal contradiction — the artifact disagrees with itself | Closed. |
| **B** | House addition shipped without a mark — in the skill, not in the source | Open. Mark or remove. |
| **C** | Proposed departure — would diverge from the source if adopted | Open. Marking is the enabling move. |
| **D** | Provenance unknown | **Resolved 2026-08-03.** Kept as a record. |
| **E** | Source material the compression dropped — in the source, not in the skill | Open. Restore or accept. |

Class E did not exist before the curriculum was read. It is now the largest
group, and it is the one a reader of the skill alone cannot detect at all.

## Authorities

Two people close entries in this register, and they close different things.

| Authority | Governs | Basis |
|---|---|---|
| **Cnid** — OpenCnid Labs | Scope, sequencing, what ships, repository identity, whether a departure is worth making at all | Owns the repository and this compression of the method |
| **Matthew Murphy** | What the method *is*: the meaning of a primitive, the shape of a technique, whether a reading of the curriculum is correct | Authored the curriculum, which `README.md` names the canonical authority |

Class D is provenance, so it is Murphy's by construction. Classes A, B and C are
Cnid's to schedule — though an individual item can still turn on a question only
Murphy can answer, which is what happened with A2 and A3. When it does, the item
is referred rather than decided, and the referral is recorded below.

Neither authority is assumed. Nothing in this register was closed by inference
about what someone would probably want.

## Ruling log

### 2026-08-03 · Cnid · the fidelity route
Four routes were on the table for reconciling "the curriculum is the canonical
authority" with a set of evidence-backed corrections. Cnid chose **marking
deviations explicitly** — keep the compression identity and the A–E mapping
intact, and record departures rather than smuggle or suppress them — and scoped
this session to producing the mark, with the fixes to follow separately. This
file is that decision's artifact.

### 2026-08-03 · Cnid · Class A dispositions
Item by item: fix A1, A4, A5, A6, A7, A8; refer A2 and A3 to Murphy. On A1 the
direction was given rather than left open — *"the taxonomy needs to derive from
the master template. It was a mistake we need to fix."* On A4, use
underscores-as-spaces as the companion skill instructs. On A6, *"fix it
properly"* — read as covering both shells, the upgrade path, and
`CLAUDE_CONFIG_DIR`, not only the missing `mkdir`.

Also authorized: task chips for the four sibling repositories carrying the same
install defect, plus self-play, which is not cloned locally.

### 2026-08-03 · Murphy · `...` is a primitive, not a type
On A2. The spread operator and the ellipsis are the same token doing the same
work — *"We're applying structure to the null-array itself, which contains all
arrays. It's simply structural."* A primitive composes **inside** a container:
it *"can go inside `{}`, `()`, `[]`, `<></>`, etc."* Therefore `${...}` and
`(...)` were never unexercised types; they are containers shown holding the
primitive, and the section's error was reading its own notation as four parallel
types. Instruction given: *"simplify and pre-define the primitives better,"* and
*"fix it with confidence and absent any hedging."*

Closes A2 and D2. Applied in §C, rebuilt as containers × fill.

### 2026-08-03 · Murphy · a tag name is a categoric primitive
On A3. *"The question is malformed."* The tag vocabulary is open — *"It can be
tasks, instructions, context, data, persona, any blanket category"* — and
categoric primitives are the operative technique, inherited from hypershots. So
neither `<task>` nor `<instruction>` is canonical, and the defect was never the
mismatch between §A and the template; it was §A presenting four tags as a closed
set.

Closes A3 and D1. Applied in §A.

**Precedent worth carrying.** Both rulings answered by rejecting the question's
framing rather than choosing between the options it offered. Before treating any
remaining Class D item as a binary between two things the artifact says, check
whether the artifact is offering a false choice. D3, D5 and D6 all read as
candidates.

### 2026-08-03 · Murphy and Cnid · the curriculum supplied
Murphy provided the full nine-part curriculum as PDFs — *"I think this might be
easier, here's the full curriculum"* — and Cnid placed them at `D:\lexideck\`.
All nine were read in full the same day, one reader per part, each answering the
same question manifest against its own document with no visibility of the others.

This closed Class D outright and opened Class E. It also established that the
skill's own lineage claim is inaccurate for its flagship artifact (B3), and that
the compression reversed the source's stated position on worked examples (E1).

Both are consequences of provenance being unknowable from inside the repository
for as long as it was. Neither is a drafting error.

### 2026-08-03 · Murphy · rulings on the source read
Six rulings, given in response to the findings above. Four authorised repairs,
which are applied; two dissolved findings by supplying provenance the register
did not have.

**B3 — the credit line.** *"True."* `SKILL.md`'s lineage no longer claims to
compress the Part 9 capstone. It now states which parts each section compresses,
and which material is not curriculum at all.

**C1 — the emphasis device.** *"Let's fix it."* Applied as the source-faithful
repair: `*** CRITICAL INSTRUCTIONS ***` with the zone closed by an asterisk rule,
and §E now teaches a zone as a matched pair. Italics restored as a named device.

**C2 — positive framing.** *"Let's remediate the skill."* Murphy's fault-tolerance
sentence is restored verbatim, the invented `"Don't use jargon"` contrast is
replaced with the source's own pair, and the sparing-prohibition carve-out is
restored — which is also how the curriculum itself reconciles Part 1's rule with
Part 8's negative constraints.

**B8 — practices 1 and 3 have a source after all.** *"Two of them are from the
owner's clone of my WonderSuite prompts, which work based on topological
primitives, where the worked examples* are *hypershots."* Topological mapping and
decoherence prevention are Murphy's, by a different line of descent than the
nine-part curriculum. **They are not house inventions and the register was wrong
to imply it.** Practice 6 remains OpenCnid's (B1).

**E1 — not a reversal.** *"The prompt engineering lessons bring novices to
intermediate level… Hypershots are an advanced abstraction technique that relies
on at least some understanding of a model's internal representations and its role
as a rough-fuzzy classifier. Not novice level. However, Claude is not a novice
prompt engineer either."* And decisively: *"hypershots* are *worked examples. They
just take a form, rather than a specific shape."*

So the curriculum and the companion skill are the same practice at two altitudes,
not opposed positions. The skill now says this where the template is introduced,
and gives the selection rule: a filled example when the specific shape should be
copied, a frame when the shape should vary. `<examples>` is restored to §A as the
tag family Part 4 names.

**The upstream question is closed.** *"Lessons.txt became Lessons.md became the
PDFs via a tool I built. The source is byte-identical to the PDFs."* There is no
further upstream to consult; the nine PDFs are the source of record. The
"Assignment 2" reference in Part 6 remains unexplained but no longer implies
missing prose.

### 2026-08-03 · WonderPrompt read — practices 1 and 3 verified
`WonderPrompt.txt` (public, at `OpenCnid/axes-of-wonder`) from
`gusthemole/WonderSuite` (GPL-3.0), read in full. It is a 10 KB system prompt
titled "Topological Meta-Prompt Engineering Framework." Both practices trace, and
the document settles two further questions the curriculum could not.

**Practice 1 · Topological mapping** is its Navigational Protocol step 1, *Purpose
Mapping* — locate a prompt's position across five dimensional axes (structural,
functional, cognitive, contextual, epistemological), each a set of bipolar
continua. **The source ships a procedure the compression dropped**, which is
exactly what independent review had flagged as practice 1's defect: words spent,
no action licensed. The procedure is now restored in the skill's own terms rather
than transcribed.

**Practice 3 · Decoherence prevention** is step 2, *Coherence Calibration* —
"ensuring structural integrity across components, aligning functional
capabilities with purpose." The skill's name is that inverted.

**Open question on practice 3.** The source's coherence is *architectural* —
components aligned with purpose. The skill's practice is about *ambiguity* — "every
vague term is a fork where the model guesses." Those are different failures. The
name traces; the content may be a merge of WonderPrompt's coherence with the
curriculum's `Reduced Ambiguity` (Part 4) and `Enhanced Precision` (Part 3).
Recorded, not edited — untangling it is Murphy's call.

**The hypershot ancestor is here, and it is explicit.** WonderPrompt's *Open
Variable Encoding Protocol* states that open variables "can encode not just
content placeholders but complete instruction mechanisms," with the form
`{OperationName(parameters, contextual_conditions, adaptation_rules)}` and a set
of named primitive operations. This is the instruction-bearing variable that
`hypershot-protocol` Rule B describes, predating it — and it is a third
independent confirmation that `{...}` denotes a callable, not an unspecified
variable (B9).

The three artifacts are therefore one lineage rather than three neighbours:
WonderPrompt's open variables → hypershot's continuum → this skill's §C fills.
That relationship is currently stated nowhere.

### Open — awaiting Cnid
- **Licence: WonderSuite is GPL-3.0; this repository is CC BY 4.0.** Practices 1
  and 3 descend from `WonderPrompt.txt` (public, at `OpenCnid/axes-of-wonder`)
  from `gusthemole/WonderSuite` under GPL-3.0. The skill reproduces none of that
  document's text — the practices are short paraphrases of its Purpose Mapping
  and Coherence Calibration steps, and method is not expression — so this is
  probably a non-issue. Flagged rather than settled because a licence question is
  the owner's to answer, not an agent's, and because the credit is currently
  carried in prose with no licence note attached.
- **Whether to update `hypershot-protocol` to match.** Murphy raised it and
  conditioned it on the owner: *"If necessary, and with the owner's permission,
  you can update your hypershot skill, too."* The change would be small — that
  skill's continuum does not say `...` composes inside containers, nor that a
  tag name is itself a categoric primitive, so the two skills currently describe
  one model in two compatible vocabularies rather than one. Not started.
- **Whether this file ships publicly.** See Status.

## Disposition of Class A — 2026-08-03

| # | Disposition |
|---|---|
| A1 | **Fixed.** Template slots retyped to §C's own definitions; §C anchored to the template as its worked instance. |
| A2 | **Fixed on Murphy's ruling.** `...` is the *primitive*, not a fifth type — spread and ellipsis are the same move, structure applied to the unspecified. It goes inside any container. §C rebuilt as containers × fill; the four brackets were never parallel types, and `${...}` / `(...)` were never unexercised — they are containers shown holding the primitive. |
| A3 | **Dissolved on Murphy's ruling** — "the question is malformed." A tag name is a *categoric primitive*; the vocabulary is open, and both names are valid instances of it. §A now states this and names both. The defect was never the mismatch — it was §A presenting four tags as a closed set. |
| A4 | **Fixed.** Underscores-as-spaces throughout the template; the rule is now stated in §C. |
| A5 | **Fixed.** House-internal pointers removed; replaced with the self-contained sentence. |
| A6 | **Fixed and verified.** `mkdir -p`, a PowerShell variant, a `CLAUDE_CONFIG_DIR` note, and the silent-failure warning. Re-tested in the previously-broken state and on the upgrade path. |
| A7 | **Fixed.** `license: CC-BY-4.0` in frontmatter; `LICENSE.md` and `NOTICE` now ship inside the skill directory, so both travel with the documented install at zero context cost. |
| A8 | **Fixed.** `LICENSE.md` gains a "what this license does not cover" carve-out naming Matthew Murphy as a designated attribution party under CC BY 4.0 § 3(a)(1)(A). |

Deliberately **not** done while fixing A7, on the strength of invariant 1 below:
no licence sentence was added to `## Lineage`. That would place new bytes after
`SKILL.md:102`, in the recency slot the credit currently occupies. The shipped
`NOTICE` and `LICENSE.md` achieve the same end at zero context cost.

Still open inside Class A's territory but **out of scope for this pass**, since
each is a naming-quality question rather than a contradiction: `Length: ${Constraint}`
restates its own label, and the same broken install snippet appears in all four
sibling READMEs, which are separate repositories.

---

## Class A — internal contradictions

The artifact contradicts itself. Resolving these requires no reference to the
curriculum, because the standard being violated is stated inside this repository.

### A1 · §C's placeholder taxonomy contradicts the master template
`SKILL.md:35-40` against `SKILL.md:61-88`

§C assigns `[...]` "for lists or arrays." The template then uses `[Agent Name]`,
`[Role]`, `[Target format]`, `[Intended reader]`, `[Constraint]` — five single
values — in that bracket. Eleven of the template's twelve slots are `[...]`; one
is genuinely a list. The document's only worked artifact violates the document's
own taxonomy three sections after stating it.

Measured across the installed skill family, the `[Bracket Placeholder]` form
appears in exactly one place — this template — while `{Underscore_Case}` appears
382 times across 45 files. The convention as written has already been abandoned
by everything downstream of it.

### A2 · Two of §C's four placeholder types are never exercised

`SKILL.md:37, 40`

`${...}` and `(...)` are defined and appear nowhere else in the file. The
template demonstrates `{...}` once (`{Methodology}`) and `[...]` eleven times.
A reader has no worked instance of half the taxonomy.

### A3 · §A teaches `<task>`; the template ships `<instruction>`

`SKILL.md:26` against `SKILL.md:68`

The tag vocabulary is stated as `<context>` / `<task>` / `<constraints>` /
`<output_instructions>`. The template ships `<context>` / `<instruction>` /
`<constraints>` / `<output_instructions>`. Nothing says which supersedes the
other, so a reader following the file literally must guess — and the shippable
artifact is the natural thing to copy, which means the documented vocabulary is
the one discarded.

Note: deciding *which name is correct* may be Class D if either is curriculum
vocabulary. Deciding that the file should name **one** is Class A.

### A4 · The template mixes naming conventions
`SKILL.md:64-65, 70`

`[Agent Name]` and `[Platform/Environment]` use spaces and slashes;
`[Data_Collection]` uses an underscore. The companion skill states the rule the
template announces itself as an instance of: underscores-as-spaces keep a name
parseable as one token-position.

### A5 · The operative instruction in BP6 resolves to nothing for a public reader
`SKILL.md:98`

> A held expectation goes to the collaborator instead of into the prompt (your
> repository's `AMBIENT.md` ask-the-collaborator rule — rule 5 in Recursus,
> 21(a) in Trellis; `spark-steering` § *Ask first — the un-tool*, manual-invoke
> only).

`git ls-files` returns five files. There is no `AMBIENT.md`, no Recursus, no
Trellis. `spark-steering` resolves only if separately installed. The practice
correctly names what to withhold and then dead-ends on what to do instead.

The self-contained sentence already exists in this repository at `README.md:48-49`
— "A held expectation has one destination and it is not a prompt. Put it to the
collaborator." — but `README.md` never loads when the skill fires.

### A6 · The documented install command silently produces a broken install
`README.md:51-56`

```bash
cp -r prompt-engineering/.claude/skills/prompt-engineering ~/.claude/skills/
```

Tested in four filesystem states under both shells. When `~/.claude` exists but
`~/.claude/skills/` does not — the state of any user who has never installed a
skill — `cp` reads the trailing path as a rename target and produces
`~/.claude/skills/SKILL.md` with no skill directory. Exit code 0, no output, no
error. The skill never loads and nothing indicates why.

PowerShell's `Copy-Item` reproduces it. Re-running the line — the upgrade path —
is idempotent under GNU `cp` but fails under PowerShell.

`dovetail/scripts/install.sh` already does `mkdir -p`, clears the target before
copying, and honors `CLAUDE_CONFIG_DIR`. The README one-liner does none of the
three. The same snippet appears in all four sibling READMEs.

### A7 · The installed artifact carries no license and no copyright notice

directory layout; `README.md:51-56`

The install copies `.claude/skills/prompt-engineering/`, which contains exactly
one file. `LICENSE.md` and the Matthew Murphy credit live at the repository root
and do not travel. After install, the entire surviving record of both is the
`## Lineage` paragraph — which names the curriculum but states no licence, no
licence URI, no copyright holder, and no link back to the canonical repository.

House precedent exists for fixing this inside the skill directory at zero
context cost: `better-skill-creator` sets `license:` in frontmatter and ships
`LICENSE.txt` and `NOTICE` alongside its `SKILL.md`.

### A8 · `LICENSE.md` permits a compliant reuser to drop the method's credit
`LICENSE.md` (368 bytes) against `README.md:70-71`

The credit to Matthew Murphy exists only as README prose — an exhortation, not a
term. A reuser who follows the licence exactly (credit OpenCnid Labs, link CC BY
4.0, note changes) has fully complied while dropping the source of the method.

CC BY 4.0 § 3(a)(1)(A) lets a licensor designate additional attribution parties
and binds that designation downstream. Nothing here uses it. `subagent-composition`
and `dovetail` — which merely *apply* the method — both carry a "what this
license does not cover" carve-out naming Murphy. The repository that *is* the
compression has the weakest licence-level protection in the house.

---

## Class B — house additions shipped without a mark

Content that does not derive from the credited curriculum and is not currently
distinguished from content that does.

### B1 · Best practice 6 is a house addition presented as a curriculum practice
`SKILL.md:98`, against the enumeration at `SKILL.md:102`

`## Lineage` enumerates what the curriculum covers: "tags, hierarchical markers,
placeholders, collections, and attention management." §§A–E map onto those five
one-to-one and in order. Best practices 1–5 read as curriculum material. Best
practice 6 does not correspond to anything in that enumeration, and `README.md`
gives it its own section titled "The practice most people skip" — treating it as
this repository's distinctive contribution while the SKILL.md files it as item 6
of a numbered list that otherwise carries the curriculum's authority.

It is also the list's length outlier by a wide margin — 745 characters against
154, 180, 154, 228, 202 for its peers.

**This is the clearest case in the register.** Marking it costs nothing, changes
no behavior, and converts an implicit provenance claim into an explicit one.

### B2 · BP6 is duplicated near-verbatim in `hypershot-protocol`

`SKILL.md:98` against `hypershot-protocol/SKILL.md:147`

The two files carry the same argument nearly clause-for-clause, including the
identical italicized sorting question and the identical trailing parenthetical.
Neither file says the other holds half the ground. The house rule loads both
skills in the same session, so a reader currently receives the paragraph twice.

Recorded here as a maintenance defect independent of whether the redundancy is
justified: whoever edits one copy will not know to edit the other. There is a
real argument that the redundancy is load-bearing, since this skill installs and
ships standalone — a public installer without `hypershot-protocol` would lose the
practice entirely if it were cut.

### B3 · The master template is house-authored
`SKILL.md:60-89`

**The single largest finding of the source read.** The template appears in no
part of the curriculum. Part 9's capstone — the artifact the skill's lineage note
claims to compress — is a travel-itinerary example:

```
<request_document type="travel_itinerary">
  <recipient name="${traveler_name}" age_group="${age_group}"/>
  ...
  <output_instructions>
    <tone>{enthusiasticTone}</tone>
    <format>
      ## Daily Plan
      ### Day [day_number]: [day_theme]
    </format>
    <constraints>
      **IMPORTANT**: Ensure all suggested activities are ${accessibility_requirement}.
    </constraints>
  </output_instructions>
</request_document>
```

Four structural differences from the skill's template, each independently a
departure: the source nests `<constraints>` **inside** `<output_instructions>`
where the skill makes it a sibling; the source has **no `<instruction>` block and
no numbered imperative steps at all**, its verbs living inside `<constraints>`;
the source's `<format>` block carries live hierarchical markers, composing §B into
the template where the skill's flat `Key: ${Value}` lines do not; and the source's
`type` attribute holds a domain value (D5).

`SKILL.md:102` reads "This skill is the Part 9 capstone compressed into an
operational protocol." **For the template, that claim is false.** The rest of the
lineage sentence is accurate. This is the one entry where the credit line itself
needs amending, not just the register.

### B4 · §B's marker-to-role mapping is house-invented and contradicts Part 5
`SKILL.md:33`

> Match marker style to the content's natural hierarchy: numbered lists for
> sequential processes, bullets for parallel items, nested headers for domain
> decomposition.

Part 5 presents its four marker families as **interchangeable**, chosen for
consistency, and assigns none of them a semantic role. It says the opposite twice:

> "The key is less about specific syntax (unless an AI system requires it) and
> more about clearly showing levels."

> "Principle: AI Adaptability: Most modern AIs are good at inferring structure
> from common outlining conventions."

The skill is prescriptive exactly where the source is deliberately agnostic.
Independent reviewers rated this the strongest operational line in the toolkit —
which is the problem: it is good advice wearing the curriculum's authority.

### B5 · §D's "Tables" has no source
`SKILL.md:47`

The word "table" does not occur anywhere in Part 7. The source's comparison
vehicle is a numbered list, and it states a preference the skill drops: "For
typical chat-based prompting, bulleted or numbered lists are more common and
readable."

### B6 · Three §E lines are invented, and the source's hedges are stripped
`SKILL.md:51-54`

| Skill | Source |
|---|---|
| "If any constraint conflicts, prioritize X over Y." | `"Ensure that you prioritize X over Y."` — one of five interchangeable focus phrasings under `Explicit Phrasing for Importance:`. The conditional and the conflict-resolution framing are house-invented. |
| "Group related constraints into attention zones so they reinforce each other." | No reinforcement claim exists. The source labels the technique `(Conceptual)`. |
| "place the most important instructions where the model attends most strongly, the beginning and end of the prompt" | "Information presented at the beginning (primacy) or end (recency) of **a prompt section** can *sometimes* carry more weight. *Consider* placing…" — scoped to a section, doubly hedged. |

### B7 · The compression stripped the source's confidence grading
Part 8 grades its own techniques in their titles: `(Conceptual)` on attention
zones, `(Advanced Concept)` on weighting, `(Careful Use)` on repetition, `(Use
Sparingly)` on ALL CAPS. Part 6 marks `Simple Arrays (Conceptual)`; Part 7 marks
`Lists of More Complex Items (Objects/Dictionaries - Conceptual)`.

**Every one of these became a flat imperative or was dropped.** This is a
systematic pattern rather than a slip: the source hedges and the compression
asserts. Any restoration pass should treat the parentheticals as content.

### B8 · Best practices 1 and 3 — *superseded 2026-08-03*
~~Topological mapping and Decoherence prevention have no source.~~ **Withdrawn.**
Murphy: they descend from his **WonderSuite** prompts, via the owner's clone —
a different line of descent from the nine-part curriculum, not an absence of one.
The lineage now credits them accordingly. Depth remains unverified pending the
WonderPrompt document (see *Open*).

What survives from the original finding, and is still worth a mark: the
curriculum's vocabulary — "informatic distance," "decoherence," "manifold
alignment" — appears in none of the nine parts, so a reader who checks the skill
against the PDFs alone will not find it. "Structural clarity" *does* appear, as
Part 5's `Principle: Structural Clarity`, scoped to hierarchical markers; the
skill promoted a section-level principle to the file's core axiom.

With B1, **one of six best practices is OpenCnid's** — practice 6 — not three.

### B9 · Additions made in this session, 2026-08-03
Recorded so they are not later mistaken for compression.

- **`<...></...>` as a fifth placeholder container** (`SKILL.md:§C`). Part 6
  enumerates exactly four containers, twice, as a closed set, and keeps tags
  (Part 4) and placeholders (Part 6) explicitly separate. Added on Murphy's
  ruling that `...` "can go inside `{}`, `()`, `[]`, `<></>`, etc." — which is
  his to extend, but it is a **new teaching, not a compression**.
- **`...` as a named primitive** (`SKILL.md:§C`). Part 6 never defines `...`; it
  appears only as the interior stand-in when naming a notation. Murphy's ruling,
  same status as above.
- **"unspecified variable" in the `{...}` gloss** — *an error introduced this
  session and to be reverted.* Part 6's `{...}` is `Objects or "Libraries": Used
  for task components, functions, or conceptual objects that represent complex
  operations`, and all seven source instances are named callables
  (`{generateSummary}`, `{responseGenerator}`, `{ideaGeneration}`). "Unspecified
  variable" is close to the inverse. The pre-existing gloss, "objects or
  function-like components," was correct.
- **Title_Case_With_Underscores in the template.** Applied under A4 from
  `hypershot-protocol`'s underscores-as-spaces rule. The curriculum's uniform
  practice across ~20 examples is snake_case for `${...}` and camelCase for
  `{...}`. The source never states a rule, so this contradicts nothing — but the
  two skills now pull different directions on the same token.

### B10 · §A's tag vocabulary partly departs from Part 4
`SKILL.md:25-28`

Part 4's four **families** are `Input/Context Tags`, `Instruction/Query Tags`,
`Output Specification Tags`, `Example Tags`. The skill drops the Example family
entirely and adds `persona` and `data`, which appear nowhere in Part 4.
`<constraints>` appears in the source only as a nested child inside
`<search_query>`, never as a top-level family.

On A3's underlying question: **`<task>` is curriculum** (Part 4, Instruction/Query
family, alongside `<query>` and `<instruction_set>`). Bare `<instruction>` is not.
Part 9's own trio for what tags label is "context, **query**, output specs."
Murphy's ruling that the vocabulary is open is confirmed by the source, which
states it twice and marks every tag list with an italic `Examples:`.

---

## Class C — proposed departures

Changes recommended on current external evidence that would diverge from the
credited source. Each is legitimate **only if marked as a deviation.** None
should be adopted silently.

### C1 · `*** CRITICAL ***` contradicts current vendor guidance
`SKILL.md:51` and `SKILL.md:76`

Anthropic's current living reference (*Prompting best practices*, retrieved
2026-08-03, scoped to the Claude 5 family and Opus 4.6–4.8) states that these
models are more responsive to system-prompt language and that escalation of this
exact shape now causes **overtriggering** rather than compliance — recommending
plain imperatives instead. The page states it twice, including in its migration
checklist.

Two independent considerations pull against a naive removal, and both should
survive into whatever lands:

- The caps at both sites sit inside quoted or fenced *technique being taught*,
  not in instructions addressed to the reading agent. This is demonstrated
  artifact, not authorial voice — the distinction matters, because a house-style
  pass that strips caps globally would be wrong here for the wrong reason.
- Removing it leaves §E with no worked demonstration of the technique it
  recommends. A replacement demonstration is part of the change, not optional.

Provenance of the marker itself is Class D — see D3.

### C2 · The stated mechanism behind positive framing is refuted
`SKILL.md:96`

> negation tokens can be dropped during processing, inverting meaning

Contradicted by *How Language Models Process Negation* (arXiv:2605.03052,
submitted 2026-05-04, revised 2026-05-29), which finds models implement two
negation mechanisms — a suppressive one and a constructive one, the constructive
being more prominent — and traces negation failures to late-layer shortcut
promotion rather than to dropped tokens.

**The practice survives intact; only the mechanism is wrong.** Anthropic's
current guidance endorses positive framing verbatim. A stronger and safer
argument is available without any empirical claim: a prohibition names one
forbidden path and leaves the rest of the space unconstrained, while a positive
instruction names the target.

Independently flagged as the weaker of two available arguments by a second
reviewer, and as a claim that would not be asserted cold by a third.

### C3 · Attention ordering is stated symmetrically and is not actionable
`SKILL.md:52`

"the beginning and end of the prompt" is true but gives no rule for which end
takes what. Anthropic's current guidance is asymmetric — long documents and data
first, query and instructions last — and carries the only quantified figure found
in any vendor source (up to 30% on complex multidocument inputs).

Separately and independently: the rule as written is **wrong for a system
prompt**, where an arbitrarily long conversation follows and there is no end
position to occupy. Applied literally it misplaces exactly the constraints that
most need to hold.

### C4 · The template's numbered steps prescribe a reasoning path
`SKILL.md:70-72`

Anthropic now advises general instructions over prescriptive steps for
thinking-enabled models, noting the model's reasoning frequently exceeds a
hand-written plan. Thinking is on by default for the models this skill's readers
target, so this is the default case rather than an edge case.

Highest fidelity risk in Class C — the parse/apply/generate triple is signature
curriculum shape. See D4.

### C5 · A sixth toolkit element for motivation
proposed addition after `SKILL.md:54`

Anthropic ranks supplying the reason behind a constraint as a top-level
principle, with generalization to unanticipated cases as the documented
mechanism. The skill has no slot for it.

**Constraint on adoption:** §§A–E map one-to-one and order-preserving onto the
five curriculum topics enumerated at `SKILL.md:102`. That mapping is the only
mechanism by which the README's fidelity claim is checkable at all. A sixth
lettered element breaks it. If this is adopted it must sit outside the A–E
sequence and be marked as a house addition — the same treatment as B1.

### C6 · No stopping rule for structure
proposed addition at `SKILL.md:21`

Every toolkit element is additive and nothing says when structure has stopped
paying for itself. The most consistent theme across current vendor sources is the
opposite discipline: the smallest set of high-signal tokens that gets the
behavior, adding structure only against an observed failure.

Adopting this means the skill argues against its own toolkit in the toolkit's own
framing position, which is a real rhetorical cost and a deliberate one.

---

## Class D — provenance unknown

**Do not edit these on current-model reasoning.** Each requires reading the
source first. Listed as the shopping list for whoever obtains the curriculum.

| # | Bytes | Question to answer against the source |
|---|---|---|
| ~~D1~~ | ~~the four-tag vocabulary~~ | **Resolved 2026-08-03 by Matthew Murphy.** Neither name is canonical, because the tag name is a categoric primitive and the vocabulary is open. Applied. |
| ~~D2~~ | ~~the four placeholder types~~ | **Resolved 2026-08-03 by Matthew Murphy.** Not a type taxonomy: containers plus one primitive fill. Rebuild authorized and applied. |
| ~~D3~~ | ~~`*** CRITICAL ***`~~ | **Resolved by the source.** The *device* is Murphy's; the skill's *rendering* is not. See D3 below. |
| ~~D4~~ | ~~parse / apply / generate~~ | **Resolved by the source. Not curriculum.** Appears in no part. |
| ~~D5~~ | ~~`type="Structural_Synthesis"`~~ | **Resolved by the source. Not curriculum.** See D5 below. |
| ~~D6~~ | ~~"Generate high-fidelity output."~~ | **Resolved by the source. Not curriculum.** Appears in no part. |
| ~~D7~~ | ~~the token-dropping mechanism~~ | **Resolved by the source. Is curriculum** — Part 1, Lesson 1. See D7 below. |
| ~~D8~~ | ~~best practices 1–5~~ | **Resolved by the source.** Two trace, one partially, two not at all. See D8 below. |

### D3 · The emphasis device is Murphy's; the skill's rendering is not
Part 8, Lesson 18, `Using "Attention Zones" or Delimiters (Conceptual):` ships a
**closed zone**:

```
*** CRITICAL INSTRUCTIONS ***
- The output must be less than 200 words.
- The tone must be strictly formal.
- ONLY MENTION generic product categories.
****************************
```

Part 9's capstone uses a different device again: `**IMPORTANT**: Ensure all
suggested activities are ${accessibility_requirement}.`

The skill's `*** CRITICAL ***` matches neither. Three specific divergences: the
string is wrong (the source's is `*** CRITICAL INSTRUCTIONS ***`); the zone is
never closed, which discards the delimiter-pair that is the technique's entire
point; and the source's zone holds literal prose constraints in mixed case,
demonstrating selective caps *inside* an already-emphasised zone, which an
all-placeholder version cannot show. The source also labels the whole technique
`(Conceptual)` — its own hedge, dropped.

**So C1 splits.** Correcting the string and closing the zone is a *source-faithful
repair*, available now. Removing the device on current vendor guidance is a
*departure*, and needs a mark.

### D5 · `type="Structural_Synthesis"` is not curriculum, twice over
The root-tag-with-`type`-attribute shape does trace — Part 4 has
`<request_document type="summary">` and `<analyze type="sentiment">`, Part 9 has
`<request_document type="travel_itinerary">`. But in every source instance the
`type` value names a **domain or operation of the request**, never a process
name for the method itself. `Structural_Synthesis` is house vocabulary in a slot
the source uses for something else.

### D7 · The negation mechanism is Murphy's — and the skill dropped its rationale
Part 1, Lesson 1:

> "This is critical because of something called "dropped tokens" - where negation
> words like "don't" or "not" can sometimes be lost during AI processing,
> completely inverting your meaning!"

> "Positive framing creates fault-tolerant instructions that maintain their core
> meaning even if some processing degradation occurs."

The first sentence is the skill's claim, so C2 is a **departure from the source**,
not a repair to the compression. The second sentence — the reason the practice
generalises beyond the word "don't" — the skill dropped entirely, and it happens
to survive the 2026 interpretability result intact. See E-neg.

**The curriculum contradicts itself here, and the skill silently adjudicated it.**
Part 8 teaches `Negative Constraints:` as "a powerful form of attention
management," with three worked examples in exactly the emphasised-negation form
Part 1's rule forbids. Part 4 ships `<ingredient_to_avoid>nuts</ingredient_to_avoid>`
without comment. Part 1 Lesson 2 permits "things to avoid (used sparingly)". The
skill states positive framing as absolute and drops Part 8's technique. **This
tension is Murphy's to resolve, not the skill's.**

### D8 · Provenance of best practices 1–5
| Skill practice | Source | Verdict |
|---|---|---|
| 1. Topological mapping | — | **No source in any part.** Class B. |
| 2. Phase alignment | Part 9 #8 "Mind Your Language and Tone" + #4 audience half | Partial. Name is house; source's mechanism ("The AI often mirrors the tone of your prompt") dropped. |
| 3. Decoherence prevention | — | **No source in any part.** Nearest is Part 3's "Principle: Enhanced Precision" and Part 4's "Reduced Ambiguity", neither of which is an operation you perform. Class B. |
| 4. Positive instruction framing | Part 1, Lesson 1 | **Name is verbatim** — "Positive Instruction Framing" is Part 1's own parenthetical. Exemplar "Use plain language accessible to non-specialists" is verbatim. The contrast `beats "Don't use jargon"` is **house-invented**; the source's pairs are "Don't make it boring" → "Make it exciting and engaging." |
| 5. Iterative refinement | Part 9 #6 | Faithful compression. Source's name is "Iterate, Refine, Experiment! (The Learning Loop)" and its four steps are Prompt / Analyze Output / Refine Prompt / Repeat. The skill drops **Experiment**. |

---

## Class E is not blocked, and never was

No ruling gates it. Restoring an item is the compression becoming more faithful,
so nothing here waits on Murphy or on Cnid. What made it look blocked was volume
plus the fact that the items are not the same kind of thing. Sorted by whether an
item changes what a competent agent writes:

- **Roughly two-thirds is novice scaffolding** — the prerequisites checklist, the
  four "Why Use X?" benefit blocks, the enumeration of legal bullet characters,
  most `Principle:` restatements. Load-bearing for a reader starting at zero,
  inert for this skill's reader. **Leave dropped.** Restoring it is what would turn
  the deployed artifact back into the educational one.
- **About eight items are genuine judgment** — tag nesting, Tone and Style as
  output controls, task decomposition, Contextual Introduction, Consistency,
  Repetition, Weighting, Identify Critical Elements. These turn on what the skill
  is for, which is the owner's to state.
- **Three were misfiled.** Pipe alternation, dot-path access, and tag attributes
  are not compression choices. In each the skill **states a convention and
  withholds the syntax that makes it usable** — §C defines `(...)` and never shows
  `(formal|informal)`; §A never mentions attributes while the template ships
  `type="Structural_Synthesis"`, using a device the skill never introduces. That
  is an internal defect. **Reclassified to Class A and fixed 2026-08-03.**

## Class E — source material the compression dropped

New as of the source read. A reader holding only the skill cannot detect any of
this; it is visible only against the curriculum. Restoring an item costs nothing
in fidelity terms — it is the compression becoming more faithful, not less.

### E1 · ~~The few-shot inversion~~ — *dissolved 2026-08-03 by Murphy*

**Not a reversal. An altitude difference.** Murphy: *"hypershots* are *worked
examples. They just take a form, rather than a specific shape."* The curriculum
carries a novice to intermediate; hypershots are the advanced form of the same
practice, and the skill's reader is not a novice. The skill now states the
relationship and the selection rule where the template is introduced, and
`<examples>` is restored to §A.

The finding is kept below because the *evidence* still stands and the omission
was real — what was wrong was reading it as opposition.

---

**Original finding, superseded:**
Three separate parts teach worked examples as a recommended practice:

- **Part 1, Lesson 3** is titled "Show, Don't Just Tell (Use Examples)", with
  `Principle: Example-Driven Instruction (Few-Shot Learning)` and
  `Principle: Clarity of Demonstration`.
- **Part 4** names `Example Tags` as one of four tag families:
  "If providing examples to the AI (few-shot prompting), wrap them in tags,"
  with `<example_input>` / `<example_output>`.
- **Part 9**, best practice 5: "Use Examples (Few-Shot Prompting): If you want a
  very specific style or format, providing 1-3 examples of the desired output can
  be incredibly effective."

The skill carries **no few-shot guidance at all** and routes the subject to
`hypershot-protocol`, whose founding premise is that concrete examples contaminate
and must be replaced by free-variable frames. That is a coherent position and may
well be the better one for an agent-facing artifact — but it is a **reversal of
the credited source's explicit, thrice-stated recommendation**, and nothing in
either repository marks it as one. Of everything in this register, this is the
item where an unmarked departure most misrepresents the author.

### E2 · The rationale that outlives the mechanism
Part 1, Lesson 1: "Positive framing creates fault-tolerant instructions that
maintain their core meaning even if some processing degradation occurs."

Dropped by the skill. It is the reason the practice generalises past the word
"don't" — and unlike the dropped-tokens mechanism (D7), it is untouched by the
2026 interpretability result. **Restoring it is the cheapest available answer to
C2**: it strengthens the practice, requires no departure, and is Murphy's own
sentence.

### E3 · Everything else, by part

| Part | Dropped |
|---|---|
| 1 | `Principle: Assign a Role` and `Principle: Specify the Audience` as practices (the skill has only template slots); the Prerequisites Checklist and its Basic/Intermediate tiering |
| 2 | **Task decomposition — an entire lesson** (Lesson 4) with no trace in the skill, including the sequential-vs-combined choice; `Tone:` and `Style:` as output controls (the source's Lesson 6 teaches four — Tone, Style, Format, Length — the skill ships Format, Audience, Length); the escalation ladder, "This is a precursor to more formal methods like hierarchical markers" |
| 4 | **Tag attributes and the mini-BNF** — `<tagName [ attributeName="value" ]*> content </tagName>`, given twice identically, the part's clearest signal of its own takeaway, carried by the skill in no form even though its template uses an attribute; **tag nesting with directional semantics** ("the outer `<analyze>` tag tells the AI to analyze sentiment *after* translation"); closing-tag hygiene; the scoping caveat "you don't need them for every simple question" |
| 5 | `Principle: Consistency is Key`, stated three times; the source's third Markdown level (`### Detail`, which the skill silently converted to `- Structural Detail`); `Identify Levels of Information` as a pre-writing step |
| 6 | **Pipe alternation** — `(formal\|informal)`, `(basic\|detailed\|comprehensive)` — the only concrete syntax `(...)` has, shown five times, absent from the skill, so a reader cannot write one; **dot-path access**, `{productDetails.name}`; `Principle: Nested Complexity`; the fill-time contract including the branch where the AI is left to request missing values; `Choose Clear Placeholder Names` as a method step |
| 7 | `Principle: Contextual Introduction` — state what a list represents before presenting it; the list-format preference for chat; the whole `Why Use Collections?` rationale block |
| 8 | `Repetition (Careful Use)`; `Weighting (Advanced Concept)`; italics as a distinct device; the five-item explicit-phrasing menu; `Identify Critical Elements` — the audit step that precedes any marking |
| 9 | `Principle: Synergy` and `Principle: Modularity` — Lesson 19's entire thesis, that the techniques compose; `Principle: Iterative Construction` (iterating on structure while building, distinct from iterating on output); `Provide Sufficient Context` and `Principle: Context is King`; `Quickly Review the Output`; `Consistency Can Be Key`, which is the source's own justification for having a master template at all; the closing instruction to experiment |

**On C6.** The proposed "stopping rule for structure" is not a departure at all —
Part 2's precursor framing and Part 4's "you don't need them for every simple
question" are the source's own version of it. C6 reclassifies to **Class E:
restoration**.

---

## Invariants any future edit must preserve

Recorded so that a later session does not have to rediscover them, and so a diff
can be checked against them mechanically.

1. **Boundary occupancy.** `SKILL.md:17` (the core axiom) and `SKILL.md:102`
   (the credit) occupy the two positions the file's own §E identifies as
   strongest. The file practices its own attention rule on itself. *Check: does
   the diff add content before line 17 or after line 102?* If yes, it is a swap,
   and the case for evicting the axiom or the attribution has to be made
   explicitly. This constrains any proposal to append licence text to `## Lineage`.

2. **The A–E mapping.** One-to-one and order-preserving against the five topics
   at `SKILL.md:102`. *Check: does the diff reorder, merge, split, rename, or
   renumber any of A–E?*

3. **Prelude ratio.** This is the only skill in the family that loads *before*
   the ceremony, by mandate — via four sibling skills and a `UserPromptExpansion`
   hook — always alongside `hypershot-protocol`'s ~11 KB. Its bytes are paid on
   every prompt-authoring session in the house, ahead of the work. Headroom
   against the ~19,900-character prefix ceiling is therefore the wrong cost
   model. *Check: does the diff push this file toward `hypershot-protocol`'s
   size?* Additions should be funded by deletions.

4. **One frame, not a gallery.** A second template converts the hypershot into a
   few-shot set — one zero-semantic frame already enumerates every valid
   instantiation. *Check: does the diff add a second fenced template under
   "The master template"?*

5. **Non-dischargeability.** This artifact is a grammar that stays live for the
   session, not a ceremony that completes. *Check: does the diff introduce a
   terminating numbered sequence or a checklist an agent could mark done?* A
   repair lens phrased as an ongoing read is fine; a checklist gives a false
   completion signal.

6. **Description budget.** Descriptions share a budget of roughly 8,000
   characters across all installed skills, and the installed set already measures
   over it. This skill's description is among the leanest in the family, so it is
   subsidizing rather than causing the pressure. *Check: does the diff raise the
   total?* If so, name which skill's description it is proposing to evict —
   overflow drops descriptions silently, starting with least-invoked skills.

   Two measurements were taken and disagree (8,009 characters of description text;
   8,489 characters of full frontmatter). **Re-measure once, authoritatively,
   before any description edit.** A widening of the trigger surface is separately
   well-motivated — the description currently names no artifact whose name lacks
   the word "prompt," so `CLAUDE.md`, a skill body, and a tool description do not
   match it — and can plausibly be funded by cutting the ~131-character
   cross-reference that carries no trigger vocabulary and is already duplicated at
   `SKILL.md:58`.

---

## Status

**Class A: closed.** Six fixed on internal evidence; A2 and A3 resolved by
Matthew Murphy and applied. **Class D: closed** — D1 and D2 by Murphy's rulings,
D3–D8 by the source read of 2026-08-03.

**Closed by Murphy's rulings of 2026-08-03 and applied:** B3 (lineage rewritten),
C1 (emphasis zone repaired), C2 (fault-tolerance sentence restored, source's own
contrast pair, sparing-prohibition carve-out), E1 (dissolved — altitude, not
opposition), B9's `{...}` error (reverted), and the `Lessons.txt` upstream
question (there is no further upstream). B8 is withdrawn: practices 1 and 3
descend from WonderSuite.

**Still open:** the rest of Class B, Class C's remaining items, and Class E, which
is the largest group and entirely untouched.

Both rulings are recorded in full in the ruling log above, including the
precedent about false binaries that bears on the six Class D items still open.

Files changed across this work: `SKILL.md` (frontmatter, §A, §C, the master
template, best practice 6), `README.md` (install), `LICENSE.md` (attribution
carve-out), and two new files inside the skill directory (`LICENSE.md`,
`NOTICE`). Nothing in Class D was edited except where a Murphy ruling closed it
first.

Commits: `3b474da` (six Class A fixes, register added), `2c831fd` (§A and §C
rebuilt on Murphy's rulings).

Whether this file ships publicly is an open decision. The argument for shipping
it: `README.md` is the only one of the five sibling READMEs with no limits
section, the canonical authority is paywalled and therefore uncheckable by any
reader, and CC BY asks a licensee to indicate changes. The argument against: it
is a working document and reads as one.
