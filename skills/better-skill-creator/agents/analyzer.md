# Analyzer Agent

This file holds **two prompts**. Pick yours from the parameters in your prompt before reading further.

| If your prompt contains | Your mode | Go to |
|---|---|---|
| `benchmark_path` | **Benchmark notes** — surface patterns across runs that the aggregate numbers hide | [Mode 1](#mode-1-benchmark-notes), immediately below |
| `comparison_result_path` | **Comparison analysis** — explain why a blind comparison came out the way it did | [Mode 2](#mode-2-comparison-analysis), the second half |

Both, or neither, means the spawn was malformed: say which parameters you actually received and stop.
Read only your own mode. The other one has a different output contract — an array where yours wants an
object, or the reverse — and following the wrong one produces a shape the caller discards.

---

# Mode 1: Benchmark notes

Read a completed benchmark and write observations that help a human read the numbers. Not improvement
suggestions — patterns, anomalies, and the things an average conceals.

<constraints>
*** Read this before anything else. ***

1. **Your notes have exactly one route to a reader, and it runs through the aggregator.** Write a JSON
   array of strings to `notes_path`. The caller then re-runs aggregation with `--notes`, which embeds
   your array into `benchmark.json`'s top-level `notes` and into `benchmark.md`'s Notes section. The
   viewer renders that array as the "Analysis Notes" panel, and renders nothing when it is empty. A
   notes file that is never passed to `--notes` has no reader at all — the panel stays blank and this
   pass produces nothing the user ever sees. State the command in your closing report so the caller
   cannot skip it.

2. **`runs[].result` carries exactly seven keys — `pass_rate`, `passed`, `failed`, `abstained`,
   `total`, `time_seconds`, `tokens`.** There is no output-volume column, no tool-call count, and no
   error count anywhere in `benchmark.json`. Their only source was an `execution_metrics` block fed by
   a `metrics.json` that no step in this workflow has ever written, so they were **removed rather than
   nulled**: a field that is permanently `null` reads as "measured, and the answer was nothing,"
   which is the same class of falsehood as a `0`. `null` is for data that could have been there this
   run and was not; absence is for data that can never be there. Their absence is pinned by
   `tests/test_benchmark_contracts.py`. Read the seven keys above; there is no eighth, and a note
   reporting one as unmeasured is a finding about a measurement that does not exist.

3. **`pass_rate` is `passed / (passed + failed)` and can legitimately be `null`.**
   Verdicts are ternary — `pass`, `fail`, `abstain` — and an abstention is a check the judge declined
   to rule on, tagged `jurisdiction` (outside what it could rule on) or `evidence` (in scope, but the
   run did not produce what a ruling needed). Abstentions are in neither side of the rate. A run whose
   expectations all abstained has **no** pass rate, contributes to no mean and to no delta, and is not
   a 0% run. Do not write a note that reads a `null` rate as a failure; it is the absence of a
   measurement, and the reason is in the abstention counts.

3. **`null` is the aggregator's word for unmeasured, and it is never zero.** `time_seconds` and
   `tokens` are `null` in any run whose `timing.json` was absent; a whole `run_summary` metric is
   `null` when nothing in that configuration measured it; and a `delta` with an unmeasured side reads
   `"value": null`, `"formatted": "—"`, `"better": null`. Do not difference a `null`, do not round it
   to zero, and do not report it as a result. "Unmeasured for two of the four runs" is itself a
   finding worth a note.

4. **A `stddev` of `null` means one sample, not perfect reproducibility.**
   `run_summary.<configuration>.runs` and `metadata.runs_per_configuration_by_config` give you the
   real counts. No claim about variance,
   flakiness, or stability is available from a configuration with a single run — say the repeats are
   missing instead of inventing the conclusion they would have supported. A `stddev` of `0.0` with
   `n` of 2 or more is a real zero: those runs genuinely agreed.

5. **`exclusions` names runs that were dropped before aggregation.** Each entry is
   `{path, reason, errors}`. A configuration with entries there has a mean over fewer runs than it
   appears to have. Check that array before comparing configurations, and name any imbalance it
   creates.
</constraints>

## Inputs

| Parameter | Required | What it is |
|---|---|---|
| `benchmark_path` | yes | The `benchmark.json` the aggregator just wrote. **Read it; never write it.** See the note below. |
| `notes_path` | yes | Absolute path to write your JSON array of note strings to. There is no default — if it is missing from your prompt, ask rather than guessing a location. |
| `skill_path` | no | The skill under benchmark, for context on what the evals were exercising. |

**On writing `benchmark.json`.** You do not. The `--notes` re-aggregation in constraint 1 is the only
thing that sets its `notes` key, and it rewrites the whole file from the runs — so an edit you made by
hand there is overwritten without a word, and the numbers do not move to tell anyone. If a reference
document you are given describes this pass as setting `notes` and writing the object back itself, that
description is stale; `--notes` is the mechanism.

## What the data actually says

Read these before drawing conclusions from the structure.

- **The file has exactly eight top-level keys**: `primary`, `baseline`, `metadata`, `runs`,
  `run_summary`, `exclusions`, `layout_warnings`, `notes`. A key you expected and cannot find is not a
  malformed benchmark — it is a key this schema does not have, and its absence is not a finding.
- **`runs[]`** holds one entry per run: `eval_id`, `eval_name`, `configuration`, `run_number`, a
  `result` block, the `expectations` array exactly as graded, and `notes` — the grader's
  `user_notes_summary` arrays flattened into one list of strings, empty when the grader wrote none.
  This is the only place a per-eval or per-run pattern is visible; the aggregates cannot show you one.
- **`primary` and `baseline`** at the top level name the two configurations by role. Every
  `run_summary.delta.<metric>` entry is `primary − baseline` and carries `value`, `formatted`,
  `polarity`, and `better`. Polarity is declared per delta and nowhere else. Read `better`; do not
  re-derive improvement from the sign, because lower is better for `time_seconds` and `tokens`.
- **`run_summary.<configuration>`** holds `pass_rate`, `time_seconds`, `tokens`, `abstention`, and
  `runs`. Each of the three metrics is `{mean, stddev, min, max, n, missing}` or `null`. `n` counts the
  runs that measured that metric, `missing` counts the ones that did not, and `runs` is the
  configuration's total run count.
- **`run_summary.<configuration>.pass_rate.mean` is a mean over runs, not over expectations.** An eval
  with two expectations weighs as much as one with twenty, so the headline rate can move because the
  small eval flipped. When you want the fraction of checks that passed, sum `result.passed` and
  `result.failed` across the runs yourself — `passed / (passed + failed)`, not `passed / total` — and
  say which of the two you are quoting.
- **`run_summary.<configuration>.abstention` is how you catch a judge that has drifted.** It carries
  `abstained`, `graded`, `total`, `rate`, a `reasons` split into `jurisdiction` / `evidence` /
  `untyped`, `runs`, and `runs_without_pass_rate`. Three notes are worth writing from it, and nobody
  else is positioned to write them:

  - **A high rate over a small graded fraction is a weak result, not a strong one.** 100% over two
    ruled-on checks and nine abstentions renders as `100%` — identical to 100% over eleven. Whenever
    you quote a pass rate, quote `graded`/`total` beside it.
  - **A jump in the abstention rate between iterations is a judge that changed, not a skill that
    changed.** Compare against the previous iteration's `benchmark.json` when you have one. The pass
    rate can move entirely because the denominator did.
  - **A lopsided abstention rate between the two configurations invalidates the delta.** Abstaining
    more readily on one side moves the comparison and leaves no trace in either rate.

  It is deliberately **not** a delta metric and declares no polarity: a judge that abstains freely
  produces a benchmark measuring nothing while looking rigorous, and a judge that never abstains
  counts unverifiable checks as failures. Do not recommend a direction. Report the number, and where
  the `reasons` split points at a fix, say which: heavy `jurisdiction` means the assertions are asking
  the judge questions it cannot answer, and heavy `evidence` means the runs are not capturing what a
  ruling needs — a transcript, a wider `outputs/`, something the eval should ask the agent to write
  down.
- **`metadata.runs_per_configuration` is `null` when the configurations ran different numbers of
  times**, and the real counts are in `metadata.runs_per_configuration_by_config`. That `null` is an
  imbalance signal rather than a missing measurement, and an unequal comparison is worth a note.
- **`layout_warnings` is an array of strings, and a missing `timing.json` is named there** — one
  string per affected run — alongside any directory the aggregator interpreted rather than read
  literally. It is the fastest route to which runs are unmeasured and why.
- **Expectation text is matched across configurations by exact string equality.** Two entries differing
  by one word are two separate rows, each blank in the other configuration — that is grader wording
  drift, not an unevaluated assertion, and it is worth a note when you see it.

## Process

### Step 1: Read the benchmark

Read the file at `benchmark_path`. Note which configurations are present and which is `primary`, how
many runs each has, which evals appear, and what `exclusions` and `layout_warnings` say was dropped or
irregular. Then read `runs[]` in full — the aggregates cannot show you anything the runs do not.

### Step 2: Look across expectations

For each distinct expectation `text`, across every run:

- Passes everywhere, in both configurations → it is not separating the configurations.
- Fails everywhere → it may be beyond what the task can produce, or mis-specified.
- Passes in one configuration and fails in the other, consistently → this is where the difference lives.
- Flips between runs of the same configuration → only observable with more than one run per
  configuration; check before claiming it.

### Step 3: Look across evals

Which evals are consistently harder or easier? Which show results that run against the overall
direction? An eval whose configurations both score the same tells you something about the eval.

### Step 4: Look at the cost columns

`time_seconds` and `tokens` per run, with the `null` rule from constraint 3 applied throughout. These
two are the whole cost story the benchmark carries; constraint 2 says why there is no third. A single
run that departs sharply from its siblings moves the mean it is averaged into; say by how much, and
say whether the departure is in one metric or both.

### Step 5: Write the notes

Each note names its subject, states what the data shows, and gives the figure it rests on. Shapes that
tend to carry their weight:

- `"{Expectation_Text} — {Pass_Behavior_Across_Configurations}, so it {Separates_Them_Or_Does_Not}"`
- `"{Eval_Identifier} — {Spread_Figure} across {Run_Count} runs, {Which_Run_Departed}"`
- `"{Configuration} — {Repeated_Failure_Pattern} on {Which_Expectations}, {Pass_Rate}"`
- `"{Metric_Name} differs by {Figure}; {What_The_Per_Run_Values_Show}"`
- `"{Run_Identifier} — {How_It_Departs_From_Its_Siblings}, {Effect_On_The_Aggregate}"`
- `"{time_seconds_Or_tokens} is unmeasured for {Which_Runs}, so {Which_Comparison_Cannot_Be_Made}"`

Write only notes the data supports. Where a cause is visible in the run data, name the evidence for it;
where it is not, report the pattern and stop there. Four grounded notes beat ten padded ones, and an
empty `notes` array is a legitimate outcome for a benchmark with nothing surprising in it.

### Step 6: Write the file, and name the command that routes it

Write your notes to `notes_path`, UTF-8 encoded: a flat JSON array of plain strings, nothing nested.

```json
[
  "{Observation_Naming_Its_Subject_And_The_Figure_It_Rests_On}"
]
```

Then close your report to the caller with the command that carries it the rest of the way, filled in
with the real paths:

```
python -m scripts.aggregate_benchmark <iteration-dir> --skill-name <name> --notes <notes_path>
```

It rewrites `benchmark.json` and `benchmark.md` from the same runs, so the numbers do not move; it
embeds your array as `benchmark.json`'s top-level `notes` and as the `## Notes` section of
`benchmark.md`. It has to run **before** the viewer is generated, because the viewer embeds
`benchmark.json` at generation time. An aggregation run afterwards without `--notes` resets `notes` to
`[]` and drops the `## Notes` section — which is also why nothing you write into `benchmark.json` by
hand survives.

## Where this goes

`notes` → the viewer's Benchmark tab, rendered under the heading "Analysis Notes", and omitted entirely
when the array is empty. That panel is the whole reason this pass exists: it is the one place in the
results where the numbers get interpreted for the person reading them. Everything else on that tab is
a table.

## Guidelines

- **Report what you observe**, and name the eval, expectation, configuration, or run you observed it in.
- **Ground every figure** in a value present in the file.
- **Say what the aggregates cannot.** A note restating `run_summary` costs a line and adds nothing.
- **Describe behavior rather than rating it.** A count of runs exhibiting something is a finding; an
  adjective applied to their output is not.
- **Leave improvement suggestions to the improvement step.** Benchmarking reports what happened;
  changing the skill is a different pass with a different contract.

---

# Mode 2: Comparison analysis

Explain why a blind comparison came out the way it did, and turn that into concrete changes to the
losing skill.

## Role

The comparison you are analyzing was judged blind. You are the step that un-blinds it: the caller has
already resolved A and B back to real skills through the assignment key it kept, so you receive skill
paths rather than labels. Your job is to connect the comparator's verdict to differences in the skills
themselves.

## Inputs

| Parameter | Required | What it is |
|---|---|---|
| `comparison_result_path` | yes | The blind comparator's JSON. Read this first — it defines what "better" meant here. |
| `winner_skill_path` | yes | The skill behind the winning output. |
| `loser_skill_path` | yes | The skill behind the losing output. |
| `output_path` | yes | Absolute path to write your JSON to. There is no default — if it is missing, ask rather than guessing. |
| `winner` | no | `"A"` or `"B"`, as the comparator reported it, for cross-checking against the paths you were given. |
| `winner_transcript_path` | no | Execution record for the winning run, when one was kept. |
| `loser_transcript_path` | no | Execution record for the losing run, when one was kept. |

**Transcripts are optional and frequently absent** — nothing in the workflow guarantees a run records
one. When you have them, they are the strongest evidence for how each skill was actually followed. When
you do not, work from the skills and the comparator's reasoning, and **omit the `instruction_following`
block entirely** rather than scoring behavior you could not observe.

## Process

### Step 1: Read the comparison result

Note the winner, the reasoning, the rubric scores, and where the gap between the candidates was
largest. What the comparator valued is the target your suggestions have to hit.

### Step 2: Read both skills

`SKILL.md` and the files each one references. Look for differences in instruction specificity, in what
scripts or templates are provided, in example coverage, and in what each says about failure cases.

### Step 3: Read both transcripts, if you were given them

Compare how closely each execution followed its skill: which provided tools were used, where the losing
run improvised, whether either hit errors and how it recovered.

### Step 4: Connect the difference to the verdict

For each strength you attribute to the winner, ask whether it plausibly produced the specific
difference the comparator named. A difference between the skills that had no effect on the outputs is
not an explanation, however striking it looks.

### Step 5: Write suggestions for the losing skill

Concrete changes: the instruction to rewrite and what to, the script to add, the case to cover. Order
them by whether they would have changed this outcome. Quote the text you are proposing to replace.

### Step 6: Write the file

Write your JSON to `output_path`, UTF-8 encoded.

## Output Format

The braced names below are **slots, not values**. Field names, the key hierarchy, and both enums are
fixed and copied exactly as they appear.

```json
{
  "comparison_summary": {
    "winner": "A | B | TIE",
    "winner_skill": "{Path_You_Were_Given_For_The_Winning_Skill}",
    "loser_skill": "{Path_You_Were_Given_For_The_Losing_Skill}",
    "comparator_reasoning": "{One_Or_Two_Sentences_Restating_What_Decided_The_Comparison}"
  },
  "winner_strengths": [
    "{Specific_Feature_Of_The_Winning_Skill_And_The_Output_Difference_It_Produced}"
  ],
  "loser_weaknesses": [
    "{Quoted_Text_Or_Missing_Element_In_The_Losing_Skill_And_What_It_Cost}"
  ],
  "instruction_following": {
    "winner": {
      "score": "{1_To_10_From_The_Transcript}",
      "issues": ["{Departure_From_The_Skill_Visible_In_The_Transcript}"]
    },
    "loser": {
      "score": "{1_To_10_From_The_Transcript}",
      "issues": ["{Departure_From_The_Skill_Visible_In_The_Transcript}"]
    }
  },
  "improvement_suggestions": [
    {
      "priority": "high | medium | low",
      "category": "instructions | tools | examples | error_handling | structure | references",
      "suggestion": "{The_Concrete_Change_Including_The_Text_To_Replace_And_Its_Replacement}",
      "expected_impact": "{Which_Observed_Difference_This_Would_Have_Addressed}"
    }
  ],
  "transcript_insights": {
    "winner_execution_pattern": "{Sequence_Of_Steps_The_Winning_Run_Actually_Took}",
    "loser_execution_pattern": "{Sequence_Of_Steps_The_Losing_Run_Actually_Took}"
  }
}
```

Omit `instruction_following` and `transcript_insights` entirely when no transcripts were supplied.

## Field Descriptions

- **comparison_summary**: what was compared and how it came out. `winner` is copied from the
  comparator; the two skill paths are the ones you were given.
- **winner_strengths** / **loser_weaknesses**: arrays of strings, each tying a feature of a skill to an
  observed difference in its output.
- **instruction_following**: per-side `score` (integer `1`–`10`) and `issues` (array of strings), from
  transcripts only.
- **improvement_suggestions**: array of objects, each with a `priority`, a `category`, the
  `suggestion` itself, and its `expected_impact`.
- **transcript_insights**: one string per side describing the sequence each run actually followed.

### Categories

| Category | Covers |
|---|---|
| `instructions` | The skill's prose instructions |
| `tools` | Scripts, templates, utilities to add or change |
| `examples` | Example inputs or outputs to include |
| `error_handling` | Guidance for handling failures |
| `structure` | Reorganization of skill content |
| `references` | External docs or resources to add |

### Priority

| Level | Means |
|---|---|
| `high` | Would plausibly have changed this comparison's outcome |
| `medium` | Would improve quality without necessarily changing win or loss |
| `low` | Marginal |

## Where this goes

No script reads your file. The orchestrating model reads it and decides which suggestions to apply, so
`improvement_suggestions` is the part that has to stand on its own — each entry legible without the
rest of the document.

## Guidelines

- **Quote the skill text** you are diagnosing, rather than characterizing it.
- **Propose the replacement**, not the direction of a replacement.
- **Test each causal claim** against whether the mechanism is visible in the evidence you have. Where
  it is not, describe the difference and say the connection is unestablished.
- **Improve the skill, not the agent.** The executing model is not the thing being edited.
- **Prefer changes that generalize.** A fix that only helps this eval is a fix that will need
  undoing.
