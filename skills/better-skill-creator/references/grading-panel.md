# Grading with a composed panel

The default path for a graded run. One judge per expectation is cheaper and documented in
`agents/grader.md`; this is what you use when the number is going to be believed.

## Contents

- [Why a panel, and why composed](#why-a-panel-and-why-composed)
- [What it costs](#what-it-costs)
- [Running it](#running-it)
- [Reading what comes back](#reading-what-comes-back)
- [What it is known not to do](#what-it-is-known-not-to-do)

---

## Why a panel, and why composed

A single judge decides "does this statement hold?" and "is this statement worth applying?" with one
verdict, and the two questions come apart constantly. A statement can be true of an artifact that
plainly failed the task. A statement can be false in wording and satisfied in substance. One byte
cannot carry both answers, and when it tries, the one you did not ask for wins silently.

Three seats, each answering one question, differently blind:

| seat | its question |
|---|---|
| grounding | does the artifact, opened at the place the statement addresses, exhibit what it says? |
| coherence | does satisfying this statement, as written, entail that the asked-for work was done? |
| corroboration | is there warrant from a channel that is not the artifact's own account of itself? |

**The judges are composed per skill, not shipped.** This tool grades a different domain every
invocation — a spreadsheet skill, a charting skill, a code-review skill. A fixed panel would be
miscalibrated for nearly all of them, and its calibration anchors would have been written for someone
else's subject matter. So the bundle ships a characterizer, a composer, and gates. A stored
composition is a record of one run, never a roster the next run selects from.

The lineage of the four-registry structure is the `judge-composition` skill. Nothing here imports it,
and a composer that has never heard of it composes correctly from `references/judge-registries.md`
alone.

## What it costs

Six sub-agents per graded run — characterizer, composer, three seats, audit — plus one script. Against
one for the single-judge path.

For a three-eval iteration that is roughly 18 spawns instead of 3. That is the real trade and you
should say it out loud before spending it. Use the panel when the answer will be acted on: deciding
whether a rewrite helped, comparing two versions, anything you would quote to someone else. Use the
single grader when you are sanity-checking your own draft and already know what you are looking for.

## Running it

**1. Characterize.** `agents/panel/characterizer.md`, over the skill and the whole eval set. It sees
every authored assertion with nothing marked, so there is nothing for it to be blind to. Writes
`characterization.json`.

**2. Compose.** `agents/panel/composer.md`, from the characterization and
`references/judge-registries.md` — never from the statements. Criteria built before a claim is chosen
cannot have been bent to that claim, and reading ahead destroys that whether or not you meant to use
what you read. Writes `composition.json` with three seats and ten calibration anchors each.

**3. Gate, before spending anything on seats.**

```bash
python -m scripts.gate_panel <composition> --characterization <characterization>
```

Pass `--characterization`. Without it, coverage is checked against the composition's own copy of the
facets, which a composer could satisfy by deleting the ones no seat covers.

**4. Render the seat prompts with the script, not by hand.**

```bash
python -m scripts.render_seats <composition> --evals <evals.json> --material <manifest> --out <dir>
```

Each seat gets only what its own `inputs` allowlist admits. This is the seats' separation made real:
corroboration's independence is a fact about which bytes it was handed, not a promise it made. Two
runs rendered by hand both gave every seat everything and asked each to police itself — an audit
found it, and every conclusion downstream had to be qualified.

**5. Run the seats in isolation**, then compose by the gates in `agents/panel/seat-frame.md`.

**6. Run the audit seat.** It sees the definitions, the prompts, the returns, the composer's
artifacts, and the run telemetry — which the seats cannot. Skipping it is tempting when you already
know the answer, and wrong for the same reason: the audit is what a real user has *instead* of knowing
the answer.

## Reading what comes back

**A `fail` from any seat decides the item.** A `pass` elsewhere is another seat reporting its own
question satisfied — not a rebuttal.

**Two or more abstentions decide it too, as `abstain`.** A lone `pass` over two abstentions is one
seat's narrow question promoted to a claim about the item. This was measured: a seat once passed an
item while stating in terms that it had no standing on the deciding question, and the composition
made that the verdict.

**Every seat abstention reaches the record**, in `seatAbstentions`, whether or not it survives into
the item verdict. `summary.abstained` counts expectations; `summary.seat_abstained` counts seat
returns. Anything that makes those two agree has lost the signal.

**`vacuous: true` beside a `pass`** means the statement is true and satisfying it proved nothing — a
universal over an empty file. The pass stays a pass; the flag and the count are what discount it.

**Abstention reasons name who fixes it**: `evidence` → supply the artifact; `jurisdiction` → reassign
the judge; `underspecified` → **rewrite the assertion**.

## What it is known not to do

Stated because a limit you know about is cheaper than one you discover.

- **It does not decide statements nobody could decide.** If no seat's channels reach the truthmaker —
  a claim about how the run executed, with no transcript — the panel abstains, and that abstention was
  guaranteed by the composition rather than earned by looking. Read it as *untestable as composed*,
  not as evidence about the artifact.
- **It does not fix your assertions.** Measured across two corpora: statements routinely miss the
  thing the requester actually feared. A rename pattern check passed a run that renamed files in the
  one directory the request said to leave alone, and every seat found the violation and correctly
  reported that no statement reached it. The panel will tell you this in `eval_feedback`; nothing
  counts it for you.
- **Abstention typing is where careful readers disagree.** Two independent blind readers agreed on
  13/13 pass-fail items and split on 3 of 4 abstentions. The typing procedure exists to narrow that,
  and it will not eliminate it.
- **An `evidence` abstention is relative to the tools in hand.** One reader abstained on a page-count
  claim because the file format stores no pagination; another opened it in a word processor,
  repaginated, and ruled. If a seat abstains on evidence, ask whether a tool it lacked would have
  reached it.

## Spawn contracts

A sub-agent lands cold. A parameter you do not pass is read as *"that file does not exist for this
run"* — not as *"go and find it"* — which is deliberate: a judge hunting by convention finds
whatever happens to be nearby and calls it evidence.

| Spawning | Required | Optional |
|---|---|---|
| panel characterizer | `skill_dir`, `evals_path`, `characterization_path` | `outputs_sample`, `inspection_tools` |
| panel composer | `characterization_path`, `registries_path`, `composition_path` | — |
| panel seat | rendered by `scripts.render_seats` — do not hand-build | — |
| panel audit | the definitions, prompts, returns, composer artifacts, telemetry, disposition | `prereg_path` |
| grader (single-judge) | `expectations`, `eval_prompt`, `outputs_dir`, `grading_path` | `transcript_path`, `user_notes_path` |
| analyzer | `benchmark_path`, `notes_path` | `skill_path` |
| comparator | run the `<blinding_protocol>` first; pass only what it produces | — |

`eval_prompt` is the one people skip. Without it a judge cannot separate genuine completion from
output that merely has the right shape — which is the failure mode most worth catching.

The audit seat's `disposition` is not optional in practice. An audit run without it cannot check the
one constraint with a measured history: whether every seat abstention reached the record, or was
absorbed by the composition and left no trace.
