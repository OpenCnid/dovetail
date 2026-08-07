# Making a skill trigger reliably

The description is the only thing Claude sees when deciding whether to consult a skill. The body,
the scripts, the references — none of it participates in that decision. So a skill can be excellent
and never run.

This document covers measuring and improving that. It costs real money; read the cost section before
starting.

## Contents

- [What triggering actually is](#what-triggering-actually-is)
- [Writing the eval queries](#writing-the-eval-queries)
- [Reviewing the query set with the person](#reviewing-the-query-set-with-the-person)
- [Running the loop](#running-the-loop)
- [When a run measures nothing](#when-a-run-measures-nothing)
- [Reading the result honestly](#reading-the-result-honestly)
- [What a good description looks like](#what-a-good-description-looks-like)

---

## What triggering actually is

Every enabled skill's name and description sit in Claude's context. When a request arrives, Claude
decides from those alone whether any skill is worth consulting.

Two consequences shape everything else here:

- **Claude handles simple things directly.** A one-step request like "read this PDF" may not trigger
  a skill however well the description matches, because there's nothing to consult *about*. Skills
  earn their place on multi-step and specialized work. This is why trivial queries are useless as
  test cases.
- **Descriptions compete.** They share a listing budget of roughly 1% of the context window, and
  every installed skill is in that pool. A long description is not free, and past roughly 20–50
  enabled skills matching degrades for everything.

## Writing the eval queries

Around 20, split evenly between should-trigger and should-not.

Make them look like real requests. Real ones carry file paths, job context, company names, column
names, a bit of backstory, and sometimes lowercase and typos:

> "ok so my boss just sent me this xlsx file (its in my downloads, called something like 'Q4 sales
> final FINAL v2.xlsx') and she wants me to add a column that shows the profit margin as a
> percentage. The revenue is in column C and costs are in column D i think"

Not `"Format this data"`. That tests nothing.

**Should-trigger (8–10).** Cover different phrasings of the same intent — some formal, some casual.
Include cases where the person never names the skill, the file type, or the domain term, and only
describes the outcome they want. Include an uncommon use case or two, and at least one where this
skill competes with another and should win.

**Should-not-trigger (8–10).** These are where the work is. The valuable ones are **near-misses** —
queries sharing vocabulary or subject matter with the description that nonetheless need something
else. Adjacent domains. Phrasings a keyword match would grab. Cases the skill touches but where
another tool is the right answer.

A negative like "write a fibonacci function" for a PDF skill is worthless — it tests nothing and
inflates your specificity score for free. If every negative is obvious, you have not measured
specificity at all.

**Hold some out.** Write a handful of queries, commit them to disk, and *then* draft your revised
description without looking at them again. The gap between tuned and held-out performance is the
only honest signal about whether a description generalizes — and that gap is routinely enormous. A
description can go from 38% to 100% on the queries you tuned against while moving far less on ones
you didn't.

## Reviewing the query set with the person

Bad queries produce a confidently wrong description, so this step earns its time.

1. Read `assets/eval_review.html`
2. Substitute the placeholders: `__EVAL_DATA_PLACEHOLDER__` (the JSON array, unquoted — it's a JS
   assignment), `__SKILL_NAME_PLACEHOLDER__`, `__SKILL_DESCRIPTION_PLACEHOLDER__`.

   **All three placeholders need escaping — there is no safe one.** The data block needs script-literal
   escaping or a query containing `</script>` ends the block early. The name and description land in
   HTML and need HTML escaping — and the description is *the field most likely to contain markup*,
   since reviewing descriptions is what this page is for. Escaping only the one that looks dangerous
   is how this went wrong the first time.

   ```python
   from pathlib import Path
   from importlib import import_module
   import html as html_mod, sys

   sys.path.insert(0, "<better-skill-creator-path>")
   to_script_literal = import_module("eval-viewer.generate_review").to_script_literal

   page = Path("assets/eval_review.html").read_text(encoding="utf-8")
   page = page.replace("__EVAL_DATA_PLACEHOLDER__", to_script_literal(eval_items))
   page = page.replace("__SKILL_NAME_PLACEHOLDER__", html_mod.escape(skill_name, quote=True))
   page = page.replace("__SKILL_DESCRIPTION_PLACEHOLDER__", html_mod.escape(description, quote=True))
   Path(out_path).write_text(page, encoding="utf-8")
   ```

   `to_script_literal` escapes `<`, `>`, `&`, and the two Unicode line separators that terminate a JS
   string. The page defends itself if you get this wrong — it raises a visible banner rather than
   executing anything — but the banner means you shipped an escaping bug, not that the page handled it.
3. Write it to a scratch location and open it. Use your harness's scratchpad or
   `tempfile.gettempdir()` — not a literal `/tmp`, which doesn't exist on Windows. Open it with
   `python -c "import webbrowser,sys; webbrowser.open(sys.argv[1])" <path>`, which works on all
   three platforms.
4. They can edit queries, flip should-trigger, and add or remove entries, then export
5. The file lands in their browser's download directory — usually `~/Downloads`, on Windows
   `%USERPROFILE%\Downloads`, and configurable anywhere. If it isn't where you expect, ask rather
   than guessing repeatedly. Check for `eval_set (1).json` if they exported more than once.

## Running the loop

```bash
python -m scripts.run_loop \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --eval-model <model-to-measure-against> \
  --max-iterations 5 \
  --max-cost <dollars>
```

**Decide the cost before you start, because the defaults will stop you.** The obvious settings — 20
queries × 3 runs × 5 iterations — are 300 probes. Measured, that is roughly **$123 on Opus, $27 on
Sonnet, $6 on Haiku** — figures taken before `--permission-mode` had a default, and not re-measured
since. The loop projects this and refuses above `--max-cost` (default `10.0`) rather
than discovering it halfway through, so the full-fat invocation does not run as written unless you
raise the cap deliberately.

That refusal is the feature. This loop is a genuinely effective way to consume someone's entire quota
while they are not watching. Show them the projection and let them pick:

- **Cut the probe count first.** `--runs-per-query 2` and `--max-iterations 3` costs a third as much
  and usually finds the same wins. Sampling more than twice per query buys precision you rarely need
  at this stage.
- **Or measure against a cheaper model** with `--eval-model`, and say plainly what you did. Ideally
  you measure against the model this person actually uses, since routing behavior differs — a cheaper
  proxy tells you about relative descriptions rather than absolute trigger rates. That is usually
  enough, because the thing you are choosing between is two descriptions.
- **Then raise `--max-cost` to the number you both agreed to**, not to something large enough to never
  bind.

It splits the set into train and held-out, measures the current description, asks Claude to propose
improvements from what failed, and re-measures each candidate on both — selecting by **held-out**
score, so a description that only helps on the tuning queries is rejected.

Run it in the background and check in periodically with where it's up to and what the scores look
like.

**Each probe runs in its own temporary project root.** This matters more than it sounds: an earlier
version registered its probes in whatever `.claude/` directory it found by walking upward — which
could be the person's project, their home directory, or a drive root — leaving files behind and
letting concurrent sessions see them. Isolation also fixed a measurement problem, because probes
sharing one directory saw each other's entries and scored each other's skills.

**A temp root bounds where a session runs, not what it may do — `--permission-mode` is the half that
does.** Every session this tool launches, probes and the improvement call alike, is driven by text
that arrived with the skill: the eval set's queries and the SKILL.md body under test. `--permission-mode`
defaults to `dontAsk`, which the CLI documents as auto-denying any call the session was not
pre-approved for, and as never waiting for an answer nobody is there to give. What this repository
does is pass that flag; what the mode then does is documented behaviour, quoted from
[the permission-modes page](https://code.claude.com/docs/en/permission-modes.md) and not measured here.
To hand those sessions this machine's permission settings instead, pass `--permission-mode inherit`
**and** `--allow-host-permissions`; the mode alone is refused before anything is spent, and the opt-in
alone changes nothing. The same opt-in is what unlocks `acceptEdits`, `auto`, `bypassPermissions` and
`plan`, several of which hand a session more than inheriting does on a machine whose settings are
strict.

Two things worth knowing rather than finding out:

- **`plan` is not the cautious choice, despite the name.** The published mode table gives `default` —
  spelled `manual` on the command line — as "Reads only", and `plan` as "Reads, plus
  classifier-approved commands when auto mode is available", and plan mode's blocks are not enforced
  in sessions where bypass permissions are available. It needs `--allow-host-permissions` like the rest.
- **A mode changes model behaviour, so it changes the measurement.** Scores are comparable only across
  runs made under the same mode. Numbers recorded here and in `scripts/run_eval.py` predate this
  default and were taken with no `--permission-mode` at all; they have not been re-measured, because
  re-measuring them means paying for the runs. Treat them as the old regime's figures.

## When a run measures nothing

Three conditions silently distort this measurement, and all three are now detected and reported in
`harness_health` — check it before believing any score.

**The probe never registered.** If the temporary command file wasn't picked up, there was nothing to
trigger and every query scores as a non-trigger. `clone_registered` tells you whether it appeared.

**An installed copy is shadowing the probe.** If the skill being measured is also installed for real,
the probe and the installation compete, and recall collapses toward zero. `competing_skills` names
them. This is worth checking first when a score looks bad, because it is indistinguishable from a bad
description by inspection — the same description measured against a shadowed probe and an isolated one
can differ by more than an order of magnitude, with nothing else changed.

**A `--scaffold` path a query named was never copied.** Version control, dependency trees, credential
stores, dotenv files and `.claude/` directories are left out of every probe workspace. A query naming
one of those paths finds nothing there, spends its tool budget looking, and scores as a non-trigger —
which counts toward recall, unlike an error, which does not. `scaffold_exclusions` lists every path
left out and why; `scaffold_disclosures` names files that were copied but are worth a look first, such
as one carrying a credential-shaped string. Both are also printed to stderr before the run starts,
which is the last point where fixing the scaffold is free.

Probes that fail — timeout, crash, missing CLI, rate limit — are recorded as **errors** and excluded
from scoring. They are not counted as "the skill correctly did not trigger." That distinction is
load-bearing: when infrastructure failures score as clean negatives, every negative passes for free,
specificity reads 100%, recall reads 0%, and the whole thing looks like a diagnosis rather than a
malfunction.

## Reading the result honestly

Check that probes actually ran before believing any score. A run where everything errored can still
produce a well-formed report.

Say which `--permission-mode` the run used when you report a number, and do not compare it against a
number taken under a different one. The projection banner names the mode directly beneath the cost,
which is the one place a reader sees both facts together — and it is the *only* place, because
`results.json` records no mode. If you save a run, save the mode beside it.

Report the held-out number, not the training number, and say which is which. If the tool selected a
candidate that only tied the original, say that too — a tie means the optimization found nothing,
which is a real and useful result.

Then apply `best_description`, show the person before and after with both scores, and re-validate:

```bash
python -m scripts.quick_validate <skill-dir>
```

Descriptions grow during optimization and the cap is easy to cross without noticing.

## What a good description looks like

From measured results rather than intuition:

- **Lead with intent, not vocabulary.** Descriptions gated on a single term only fire when someone
  uses that term. Most people describe the outcome they want instead.
- **Cover the "they never say the word" case explicitly.** This is the largest single source of
  missed triggers.
- **Name the sub-tasks.** People ask about one piece of a workflow, not the workflow. A description
  that only names the whole thing misses requests about its parts.
- **Enumerating exclusions is usually a loss.** A "Not for X, Y, Z" clause measurably *cost* recall
  while buying no specificity — the near-miss negatives were already being handled by the positive
  description being precise. Sharpen what it *is* rather than listing what it isn't.
- **Push against undertriggering.** The common failure is a skill not firing when it would have
  helped, so it's reasonable to say plainly that it should be consulted even when the task looks
  simple enough to handle directly.
