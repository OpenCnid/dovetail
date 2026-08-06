# Dovetail Release Notes

## v0.4.1 (2026-08-05)

**Nothing a skill does changed. What changed is that the checks now run, on two
platforms, and the ones that had been asserting the pre-`0.3.0` layout stopped.**

Everything through `0.4.0` shipped from a desk where the suite was run by hand,
on Windows, when someone remembered. That is how a Linux-only bug survived two
releases.

- **`.github/workflows/checks.yml` runs the inventory, version, shell-lint and
  test passes on `ubuntu-latest` and `windows-latest`,** with `fail-fast: false`
  because when one leg goes red the other leg's result is the interesting half.
  The matrix earned itself on the first run: `test_run_loop.py`'s C7 case rebuilt
  a path from a `file://` URI by stripping the scheme textually, which drops the
  leading slash of a POSIX path. A Windows URI carries a drive letter, so it
  passed here and failed only on Linux. It uses `url2pathname` now, which also
  decodes the percent-escapes a temp directory containing a space would produce.
- **Two licence records and three test paths described a layout that ended at
  `0.3.0`.** The root `LICENSE.md` still called every skill a pinned submodule;
  `skills/self-play/LICENSE.md` licensed four files that do not ship and pointed
  at a `vendor/` tree, a `NOTICE` and a `docs/DEPENDENCIES.md` that exist nowhere
  here. `test_self_conformance.py` looked for `LICENSE.txt` and `NOTICE` two
  directories above the skill and called them "repository furniture" — the files
  were already in the right place and the test was wrong, because `install.sh`
  copies a skill directory and nothing above it, so a licence left at the root
  ships to nobody. That consequence is now in the assertion message, where the
  person who sees the failure reads it, and not only in a comment.
- **`lint-shell.sh` aborted at its first finding.** `set -euo pipefail` plus a
  pipe into `head -20` handed `set -e` shellcheck's non-zero status mid-loop: 19
  lines emitted, no summary, 3 of 5 files reached. Never a false pass — it did
  exit non-zero — but the script's own docstring promises that a clean run cannot
  mean nothing was checked, and this was that failure. Since the first offender
  was `lint-shell.sh` itself, `test-skills.sh` had never been shellcheck'd at all.
- **31 `.pyc` files were tracked** under `better-skill-creator`'s `scripts/` and
  `tests/`, so every distributed copy carried one machine's `cpython-313`
  bytecode. Removed, and `.gitignore` now covers them.
- **The README was rewritten for the reader who just wants it installed,** with
  the two routes at the top and the reasoning behind them moved below.
- **It has the diagram it has been claiming since `0.4.0`.** `docs/assets/
  banner.svg` draws the pack in three tiers: what each skill gives you alone,
  what a group unlocks that no member can, and the eight cut as the through
  dovetail the pack is named for, tails coloured in runs of two, three and three
  by group. The middle tier labels each panel with how well it is evidenced
  rather than asserting the same weight for all three — the gate is counted (2
  descriptions, 3 bodies, the house rule), the clean room is a mechanism
  (`self-play` imports both by name), and the third is drawn dashed because it
  is shared purpose with no import in either direction.

Suite after the fixes: 699 passed on Windows, 691 on Linux, 0 failed.

### Why this release exists at all

`0.4.0`'s tag points at the commit before every fix above. All of it landed on
`main` afterwards and none of it reached anyone installing the published
release, because nothing connected "the checks are green" to "this is the commit
that ships". `scripts/check-release.sh` is that connection, and
`.github/workflows/release.yml` runs it when a tag is pushed: the tagged commit
has to be on `main`, the manifests have to carry the tag's version,
`RELEASE-NOTES.md` has to have an entry for it, and the `checks` workflow has to
have concluded success **on that exact SHA** — not on an ancestor, and not on a
later commit. A tag that fails any of those is red before anybody installs it.

## v0.4.0 (2026-08-05)

**The entry skill and the `SessionStart` hook are gone.** The pack ships eight
skills and adds nothing to a session it is not asked for.

`using-dovetail` was added at `0.2.0` to carry two things into every session: the
rule that `prompt-engineering` and `hypershot-protocol` load before any prompt
bytes are authored, and the notice that `spark-steering` and `upsum` are
invisible to the model. Measured against what the rest of the pack already
carries, neither survived:

- **The companion rule was already where it was needed.** `subagent-composition`
  and `judge-composition` name both companions *in their descriptions*, so the
  pairing is visible before either is invoked, and again in their bodies;
  `self-play` carries it in its body. The one real gap was
  `better-skill-creator`, which mentioned neither — now fixed with two sentences
  in its own body, at no recurring cost.
- **`spark-steering` is named by six skills,** three of which the model can see.
  It did not need an entry point to be discoverable.
- **That left one fact nothing else carried: that `upsum` exists.** For which the
  hook spent about 576 tokens of every session — and `upsum` carries
  `disable-model-invocation` precisely so that it does *not* volunteer itself. A
  note in every session inviting the model to suggest it works against the
  reason the flag is there.

`hooks/` went with it — `hooks.json`, the `session-start` script, and the
`run-hook.cmd` polyglot. Keeping tested-but-unused machinery for a future that
may not come is how a repository accumulates weight nobody can account for;
`git log` has all of it if a real pack-wide need appears. What the removal cost
in knowledge is recorded in `AGENTS.md` instead: a skill's own hooks are inert
on the plugin route, so anything pack-wide has to live at the root, and now
nothing does.

`test-skills.sh` loses its `SessionStart` arm and keeps everything else.

## v0.3.0 (2026-08-05)

**This repository stopped being a distribution pack and became the source of
truth for its nine skills.** No submodules, no pins, no `vendor/`, no sync step.

The reason is that the old arrangement was a third pattern nobody else uses.
`obra/superpowers` — which the tooling here has been following all along — has
no submodules anywhere. It keeps one product's skills in one repository at
`skills/<name>/`, and composes *separate* products through a marketplace that
lists them by URL. Dovetail's eight held together by shape, so they were one
product wearing eight repositories.

What that bought, and what it cost:

- **A plain `git clone` is now the whole thing.** No `--recurse-submodules`, no
  fetch step, and no way to end up with a hollow pack — which was a real failure
  mode with a warning written specifically for it.
- **`plugin.json` ships no `skills` key.** The loader auto-discovers
  `skills/*/SKILL.md`, as superpowers does. `install.sh` still enumerates every
  skill, and `test-skills.sh` now counts that list against the directories on
  disk, so a skill added to one and not the other fails loudly.
- **`scripts/sync.sh` is gone.** There are no pins to move.
- **28 characters of Windows `MAX_PATH` headroom came back**, because the
  `vendor/<name>/` prefix is gone: `better-skill-creator`'s longest path went
  from 164 characters to 136, and headroom under a default `~/.claude` from 34
  to 62.
- **The cost is the property the pins provided.** A pin either pointed where it
  pointed or the diff said otherwise, and each source stayed canonical for its
  own development. `docs/provenance.md` records where every skill came from and
  the commit it arrived at; the source repositories remain the archive of their
  own history. What replaces the pin discipline is `scripts/test-skills.sh`,
  which checks that every skill still loads rather than that every pointer still
  points.

Two things the move would have broken silently, both caught before it landed:

- **Five of eight skills had no licence inside the skill directory,** relying on
  a repository root that a monorepo dissolves. `install.sh` copies the skill
  directory and nothing above it, so those five would have shipped with no
  licence at all — for CC-BY that is the attribution term, not tidiness. This is
  the same failure fixed in `better-skill-creator` at 0.2.0, and it was latent in
  five more places. Every skill now carries its own.
- **Three `references/` links pointed out of their skill directory** — two in
  `judge-composition` to its own `docs/`, one in `self-play` to its `AGENTS.md`.
  Those files are not part of a skill and now live in `docs/<name>/`; the links
  were recomputed against the new locations and confirmed to resolve. The other
  twelve escaping links were left exactly as they are: they are cross-repository
  mirror citations that never resolved here, and `self-play`'s own
  `references/README.md` records that repairing one is the edit that would end
  its byte-identity.

Research that is *about* a skill rather than part of it — findings, probe
harnesses, validation records, design notes — moved to `docs/<name>/` rather
than being left behind in the archived repositories.

## v0.2.1 (2026-08-05)

Two documentation fixes upstream, both of the same kind: a claim that was wrong
in a way nothing in the repository could disagree with.

- **`upsum`'s checks command pointed at a path that only exists in a clone of
  `upsum`.** Step 4 of the close ceremony documented
  `python skills/upsum/scripts/checks.py .`, which fails with `can't open file`
  anywhere the skill is actually installed — the script sits beside the skill at
  `~/.claude/skills/upsum/scripts/checks.py`, and nothing under the working
  directory answers to a repository-relative path. The line contains two paths
  pointing at different places and only one of them moved: the script is beside
  the skill, the trailing `.` is the repository being checked. `SKILL.md` now
  resolves the script against `$SKILL_DIR`, which Claude Code announces as *Base
  directory for this skill* on load. The README keeps the clone-relative form,
  correct for a reader standing in a clone, with the installed form beside it.
  (`OpenCnid/upsum#2`)
- **`self-play`'s `AGENTS.md` reported a character count wrong by 759.** It
  claimed `SKILL.md` sat at 19,277 of 19,900 with 623 characters of headroom;
  the command documented three lines above it returns 18,518, so the real
  headroom is 1,382 — more than twice what the line offered, making its "any
  addition needs a matching removal" guidance tighter than the facts require.
  The file had not drifted; the sentence was never re-measured. Corrected and
  rewritten as a dated reading rather than a standing fact, because a bare
  number cannot go stale loudly. (`OpenCnid/self-play#4`)

Both predate the `skills/<name>/` restructure and were deliberately left alone
during it, so that a real change did not bury an unrelated one.

## v0.2.0 (2026-08-05)

The first release with notes. Everything below was probed on Claude Code
2.1.214, Windows 10; nothing has been run on macOS or Linux.

### Fixes

- **`subagent-composition` was loading as nothing, and said so silently.** Its
  `SKILL.md` contained a literal bang-backtick sequence — inside the sentence
  documenting that exact hazard. A skill body is preprocessed before it reaches
  the session, so the sequence ran at render and aborted the load: `num_turns:
  0`, an empty result, `is_error: false`, and no body in the transcript. Nothing
  surfaced, which is why a passing install and a resolving slash command proved
  nothing. Three arms in one run, one variable between the first two, with a
  second skill as control: unmodified 0 turns and 2,531 bytes of transcript with
  the body absent; trigger removed and otherwise identical, 1 turn and 32,959
  bytes with the body present; control 1 turn and 33,068 bytes. Fixed at the
  source (`OpenCnid/subagent-composition#4`); the pin follows. `docs/FINDINGS.md`
  §11 in that repository keeps the literal syntax, correctly — it is
  documentation and is never rendered as skill content.
- **`bump-version.sh` wrote CRLF.** Python's default text mode does that on
  Windows while `.gitattributes` declares `eol=lf`, so the script rewrote every
  line of a file it was asked to change one field in.

### Composition

- **The companion rule now fires on both install routes.** A skill's own hooks
  are inert on the plugin route: a nested `.claude-plugin/plugin.json` is
  honoured only where the directory is a plugin in its own right, which is the
  `install.sh` route, where each skill lands in `~/.claude/skills/<name>/` and
  auto-loads as `<name>@skills-dir`. Mounted as components of this pack those
  manifests are ignored entirely. Fixing the matcher does not help — an arm
  written to match the namespaced `command_name` fired zero times with the
  control logger alive in the same run, so the namespacing is a symptom and not
  the cause.
- **`using-dovetail` is the pack's one skill of its own,** injected by a
  `SessionStart` hook at the pack root. It carries what no source repository can
  say, because none of them knows it will be packaged as `dovetail`: the rule
  that `prompt-engineering` and `hypershot-protocol` load before any prompt bytes
  are authored, and the notice that `spark-steering` and `upsum` carry
  `disable-model-invocation` and so can only be reached by the user typing them.
  That notice has no other channel — the model cannot list what it cannot see.
  Shape follows `obra/superpowers`, which solves the same problem with one
  always-on entry skill rather than per-skill hooks.

### Layout

- **Every source now keeps its skill at `skills/<name>/`,** with a root plugin
  manifest, so the loader's `skills/*/SKILL.md` glob finds it and each repository
  is installable as a plugin in its own right. Eight repositories, eight merged
  pull requests.
- **The `better-skill-creator` exception is gone.** Its whole repository used to
  be the skill directory, and both `plugin.json` and `install.sh` carried a
  special case for it. Its `scripts/`, `references/`, `agents/` and `tests/` are
  still skill content and moved *with* the skill rather than being left behind,
  classified per item on evidence of what actually reads them. 365 renames, and
  its 700-test suite returns the same result as before the move.

Three failures the move caused, each found by running something rather than
reading it:

- `upsum` documents `python .../scripts/checks.py .` in both its README and its
  own `SKILL.md` — a command a user pastes and a skill instructs Claude to run,
  not prose.
- `better-skill-creator`'s `.gitattributes` and `.gitignore` patterns contain
  slashes, so git anchors them to their own directory; moving `tests/` silently
  dropped fixture binary-protection. `git check-attr` reported `text: auto` after
  the move and `text: unset` after the fix.
- `better-skill-creator` shipped `LICENSE.txt` and `NOTICE` only because its root
  was the skill directory. Afterwards the distributed artifact carried neither,
  and Apache-2.0 §4(d) requires the NOTICE in derivative distributions. Restored
  inside the skill directory.

Nothing was rewritten that merely looked like a path. Cross-repository mirror
citations still point at their originating layouts, `self-play`'s mirrors were
left untouched because that repository documents that repairing their links is
the edit that would end their byte-identity, and every hash manifest verifies
exactly as before — the skill files are pure renames, so their blob SHAs could
not move.

### Tooling

- **`scripts/test-skills.sh`** checks that every shipped skill actually loads.
  Static: frontmatter name matches directory, path present in both manifests, no
  bang-backtick. Live: installs the pack into a throwaway `CLAUDE_CONFIG_DIR`,
  invokes each skill, and greps the session transcript for a canary from that
  skill's own body. It needs no login — invoking a skill expands harness-side and
  costs no API turn. Getting the live layer honest took three attempts: a `## `
  heading word scored nine of nine while two skills were loading nothing, because
  every transcript already carries the injected entry skill and an 11KB listing
  of every description; and a canary containing a quote can never match, because
  the transcript is JSON and stores it escaped.
- **`scripts/bump-version.sh` and `.version-bump.json`** move the version in all
  three places at once. This is not cosmetic: the marketplace entry now carries
  `strict: true`, and `claude plugin tag` refuses to tag when `plugin.json` and
  the enclosing marketplace entry disagree — verified by desyncing one on
  purpose.
- **`scripts/lint-shell.sh`** gates on `bash -n` and reports `shellcheck` when
  installed, stating plainly when it did not run so a clean result cannot mean
  nothing was checked.
- **`hooks/run-hook.cmd`**, a polyglot wrapper adapted from `obra/superpowers`.
  The hook previously relied on `"shell": "bash"` with a bash already on PATH.
  The wrapper looks for Git for Windows in its two standard locations, then any
  bash on PATH, and **exits 0 when it finds none** — a machine that cannot run
  the hook still gets the nine skills, just without the injected companion rule.

### Verified

- **The plugin route works from GitHub,** which the README had flagged as
  unverified since before this work. `marketplace add` of the HTTPS URL plus
  `install` reports `Skills (9)` and `Hooks (1) SessionStart`, and all nine
  bodies load in a session. A plugin fetch does recurse into the submodules.

Two Windows traps came out of that run, both recorded because neither failure
names its own cause:

- The `OpenCnid/dovetail` shorthand resolves to `git@github.com:` and fails with
  *Permission denied (publickey)* on a machine without SSH keys, though the
  repository is public. Use the HTTPS URL.
- `fetch-pack: invalid index-pack output` is really `MAX_PATH`.
  `better-skill-creator`'s deep test fixtures leave roughly 62 characters of
  headroom below the 260-character limit under a default `~/.claude`. This
  predates the `skills/<name>/` layout, which spent 28 of those characters; the
  pre-restructure commit fails identically at the same depth.
  `git config --global core.longpaths true` removes the limit.

### Still not known

- **Whether the injected directive changes what the model invokes.** The harness
  proves each body reaches the session and cannot prove the model acts on it;
  that needs an authenticated run, which the harness deliberately does not
  require.
- **Anything about macOS or Linux.** Both install routes are run, on one platform.
