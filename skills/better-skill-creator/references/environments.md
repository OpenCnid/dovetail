# Running this workflow somewhere other than Claude Code

The loop is the same everywhere — draft, test, show a human, improve, repeat. What changes is which
machinery is available to run it. Read the section for where you are.

## Contents

- [Work out what you have, don't guess from the name](#work-out-what-you-have-dont-guess-from-the-name)
- [Claude.ai](#claudeai)
- [Cowork](#cowork)
- [Headless, remote, or no display](#headless-remote-or-no-display)
- [Updating a skill that already exists](#updating-a-skill-that-already-exists)

---

## Work out what you have, don't guess from the name

Branching on "am I in Cowork" requires you to know something you often can't check. Branching on
capabilities is checkable, and it's the same decision:

| Capability | How you know | What it gates |
|---|---|---|
| Sub-agents | you have an agent-spawning tool | parallel test runs, baselines, blind comparison |
| A browser / display | `webbrowser.open()` returns true | the served review viewer |
| The `claude` CLI | it's on PATH | description-triggering optimization |
| A writable workspace | you can create a sibling directory | iteration history |

Everything below is a consequence of one of those four being absent. If you have all four, you're in
the main flow and don't need this file.

One version fact rides on the third row rather than on PATH alone: the optimization scripts pass
`--permission-mode dontAsk` by default, which `claude --help` lists on 2.1.223. A CLI old enough to
reject that value fails loudly rather than silently — a probe whose child exits non-zero is recorded
as an `error`, not as a non-trigger, and on the improvement call the non-zero exit becomes a
`RuntimeError` that stops the loop. Either way it reads as a broken harness, which is what it is.

`--permission-mode default` is the fallback there, not `manual`: `manual` is only an alias, and it
"require[s] Claude Code v2.1.200 or later", so a CLI too old for `dontAsk` is likely too old for
`manual` too. `default` is the config-value spelling of the same mode and has no version floor.
(Checked 2026-08-06 on 2.1.223: `claude --permission-mode default --help` exits 0, though `claude
--help` does not list `default` among the choices it prints.)

## Claude.ai

**No sub-agents.** You can't run independent test executions, so read the skill's SKILL.md and follow
it yourself to complete each test prompt, one at a time.

Be honest with yourself and with the person about what this is worth: you wrote the skill and you're
executing it, holding all the context that a cold reader wouldn't. It catches obvious breakage —
missing steps, contradictions, instructions that can't be followed — and it does not tell you whether
the skill works for someone arriving fresh. Skip the baseline runs; a baseline you also execute isn't
a comparison.

**Skip the quantitative benchmark.** It's built on baseline comparison, which you don't have. Say so
rather than producing numbers with nothing behind them.

**Show results in the conversation.** No viewer. For each test case, show the prompt and what came
out. If the output is a file they need to look at, save it and tell them where. Then ask directly:
*"How does this look? Anything you'd change?"*

**Skip description optimization.** It needs `claude -p`.

**Packaging works.** `package_skill.py` needs only Python and a filesystem, and claude.ai's Skills UI
takes the `.zip` it produces. Note the 200-character description cap on that route —
`references/frontmatter.md` covers it.

## Cowork

**Sub-agents work**, so the main workflow applies — parallel runs, baselines, grading, benchmarks. If
you hit timeouts, running the test prompts in series is a fine trade.

**No display.** Generate the viewer with `--static <path>` and give the person a link to open. The
`"Submit All Reviews"` button downloads `feedback.json` rather than posting it; copy that file into
the workspace for the next iteration to pick up. You may need to request access to read it.

**Generate the viewer.** This is worth stating plainly because it's the step most often skipped here:
after running tests, produce the review viewer and put it in front of the person *before* you form
your own opinion about the outputs. Your read of the results is not a substitute for theirs — they
know what they wanted. Use `generate_review.py`, not hand-written HTML.

**Dynamic context is disabled.** `` !`command` `` substitution doesn't run in Cowork. If a skill you
are authoring depends on it, that skill will behave differently here — and its failure looks like the
skill not triggering.

**Description optimization works** — it uses `claude -p` via subprocess, no browser. Leave it until
the skill itself is settled and the person agrees it's in good shape.

**`propose_skills` carries only a SKILL.md.** Its payload is a single string, so a skill with
`scripts/` or `references/` cannot go through that channel intact. Use the zip route.

## Headless, remote, or no display

`--static <path>` is the reliable path everywhere, and on Windows it is often the *only* one that
works — the served viewer has more moving parts.

**Don't background the served viewer with `nohup ... &`.** `generate_review.py` blocks, so it has to
be launched in the background — but `nohup` does not exist on Windows and a trailing `&` is a *parse
error* in PowerShell, not a background operator. That incantation fails outright for every Windows
user. Use your harness's own background facility instead, whatever it is.

Don't hardcode how to open a file. `open` is macOS-only, `xdg-open` is Linux, `start` is Windows;
`python -c "import webbrowser,sys; webbrowser.open(sys.argv[1])" <path>` does the right thing on all
three. Same for temp paths: `/tmp` does not exist on Windows, so use your harness's scratchpad if it
gave you one, otherwise `tempfile.gettempdir()`.

And check the result rather than announcing it. `webbrowser.open()` returns a boolean. Telling someone
their browser opened when it didn't sends them looking for a window that isn't there.

## Updating a skill that already exists

Common case, and it has its own hazards.

**Keep the name.** Directory name and frontmatter `name` stay exactly as they were. If the installed
skill is `research-helper`, you ship `research-helper` — not `research-helper-v2`. The name is how
people and the harness both refer to it.

**Check whether it's plugin-managed first.** A skill under `~/.claude/plugins/cache/` is not the
person's file. Edits there take effect live, which makes them look durable, and then get wiped
wholesale by the next plugin update with no warning. Fork it to somewhere they control —
`~/.claude/skills/<name>/` for personal use, or the project's `.claude/skills/<name>/` — which also
shadows the plugin copy. Tell them you did this and why; discovering it later costs an afternoon.

**Copy before editing** in general. Installed skill directories may be read-only. Work in a scratch
copy and package from there.

**Snapshot before your first edit.** The old version *is* your baseline. Once you've edited in place
there's nothing left to compare against, and the whole question — "is the new one actually better?" —
becomes unanswerable.
