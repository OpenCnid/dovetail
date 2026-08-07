#!/usr/bin/env python3
"""Run trigger evaluation for a skill description.

Tests whether a skill's description causes Claude to reach for the skill for a
set of queries, and emits the results as JSON on stdout.

WHAT SURFACE THIS ACTUALLY MEASURES
-----------------------------------
Each probe writes a *project-scoped slash command* file into
``<probe-root>/.claude/commands/<skill>-skill-<uuid>.md`` whose frontmatter
``description`` is the candidate description under test.

That file does **not** appear in the session's ``skills`` array. Verified on
Claude Code 2.1.214 by reading the ``system``/``init`` event of a real probe:
the clone name appears in ``slash_commands`` (57 entries) and is absent from
``skills`` (29 entries). The previous version of this docstring claimed the file
"appears in Claude's available_skills list"; that claim was wrong as stated.

What *is* true, and is what makes the protocol usable:

* the model invokes the entry through the ``Skill`` tool — a captured probe's
  first tool call was ``Skill <- {"skill": "widget-forge-skill-6f09bfa7"}``; and
* asked to name its available skills, the model lists the clone alongside real
  skills.

So this measures **description-driven, model-initiated invocation of a command
file**. It is a proxy for the real ``~/.claude/skills/`` shelf, not that shelf
itself. A description tuned here transfers only insofar as the router weighs the
two surfaces alike — which is not established. Treat the absolute numbers as
proxy measurements and the *differences between descriptions* as the signal.

DESIGN NOTES (things that were wrong before, so nobody re-introduces them)
-------------------------------------------------------------------------
* Stream reading uses a daemon reader thread + ``queue.Queue``. ``select.select``
  works on sockets only on Windows and raises ``OSError`` (WinError 10038) on a
  pipe; the old code swallowed that and scored every query as a non-trigger.
* Every probe gets its **own** temp project root. Sharing one root makes N
  identical clones visible to each other: measured recall was 1.7% shared
  vs 38.3% isolated with nothing else changed (research/16-own-description.md).
  Nothing is ever written into the user's real ``.claude/``.
* A probe root bounds *where* a session runs and never bounded *what it may
  do*. ``--permission-mode`` used to default to unset, which is the CLI's
  "take this machine's permission settings", and the flag's own help text said
  so out loud. The session on the other end is driven by an eval set's queries
  and by the SKILL.md under test, both of which arrive from wherever the skill
  did, so that default handed third-party text the host's capabilities. The
  default is now ``dontAsk`` -- see :data:`SAFE_PERMISSION_MODE`, which records
  why it is that mode and not ``plan`` -- and ``inherit`` is a spelling a caller
  has to choose, alongside ``--allow-host-permissions``. ``None`` resolves to
  the safe mode rather than to inheritance, because a caller with no opinion is
  not a caller asking for one.
  **This moves the measurement**: a mode changes model behaviour, so numbers
  from before this change were taken under a different regime and are not
  comparable with numbers taken after it. Nothing in the tree re-measures them,
  and the costs in :data:`COST_PER_PROBE_USD` are among them.
* A probe that does not end in a clean verdict is recorded as ``error`` and
  excluded from scoring. It is never counted as a non-trigger — an errored
  probe passes every negative query for free, which is how a dead harness
  reports "precision 100%, recall 0%" and reads as a diagnosis.
* Detection does not bail at the first non-``Skill`` tool call. A non-matching
  tool block clears the pending state and scanning continues; only the terminal
  ``result`` event or the tool budget decides a non-trigger.
* The matcher is the exact per-probe clone name. With one clone per probe that
  is already correct, and a widened prefix match is actively harmful: measured,
  prefix matching scores a model's *refusal* to invoke ("one skill appears to be
  impersonating another", followed by Reads of the clone files to audit them) as
  a successful trigger.
* A ``--scaffold`` entry that is copied at all must be a real file or directory.
  ``copytree``/``copy2`` follow what they are handed, so a link at *any* depth
  put its target's content in the probe root, where the probe then runs.
  Preserving links instead only relocates the leak — the recreated link still
  points out of the tree — and ``copytree(symlinks=True)`` dereferences an NTFS
  junction anyway, because it keys off ``os.path.islink``, which is False for
  one. Gate on the reparse attribute, never on ``is_symlink()``.
  (Measured on CPython 3.13.1, Windows 10 10.0.19045, 2026-08-06.)
* A short list of names is dropped from the copy instead: version control,
  dependency trees, credential stores, dotenv files. ``.git`` is the security
  entry — in a worktree checkout it is a *file* holding an absolute ``gitdir:``
  pointer, which makes the probe root a live, writable checkout of the user's
  real repository, and no link is involved for the gate above to catch.
  (Measured 2026-08-06; a branch created from a probe root appeared in the host
  repository's ``refs/heads``.) The list stays short on purpose: a query naming
  an absent path is scored ``no_trigger``, not ``error``, so over-excluding
  moves the recall number silently. What is excluded is reported, never assumed
  read.
* SIGINT is left to ``signal.default_int_handler``. Installing a handler for it
  replaced the handler that raises ``KeyboardInterrupt``, so Ctrl-C never
  unwound ``run_eval``'s scheduling loop and its ``except BaseException`` --
  the branch that cancels the queued futures -- was dead code under the CLI.
  What ran instead was cleanup on the main thread while the pool's workers were
  still dequeuing, so every worker that finished during those seconds started a
  fresh *billed* ``claude``. Ctrl-C kept spending, and those children were
  registered after the cleanup snapshot and still running when ``os.kill``
  landed under SIG_DFL, where atexit does not fire, so they were orphaned too.
* A probe root is forgotten only once it is actually gone. ``_rmtree_retry``
  exists because Windows refuses to unlink a directory that is still a
  just-killed ``claude``'s cwd; discarding the registration before checking
  whether removal worked meant the one root the exit sweep needed to hear about
  was the one it had been told to forget. With ``--scaffold`` that root holds a
  copy of the user's project.
* That asymmetry is why the checks below it report rather than withhold. A hard
  link and a credential inside an innocently named file both reach the probe
  root, and both are named to the user instead of dropped: withholding either
  would move the recall number, while the user's fix for either leaves the path
  and its bytes exactly where they were. Refusing on ``st_nlink > 1`` is worse
  than useless — every ext4 directory has two links, so it refuses every Linux
  scaffold while passing on Windows, and a hard-link backup reports every file
  in a tree that nothing entered.
"""

import argparse
import atexit
import fnmatch
import json
import os
import queue
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import uuid
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from scripts.utils import configure_console, parse_skill_md

# Tools whose input may legitimately name the clone. Read is included because a
# model that opens the command file has demonstrably routed to it.
TRIGGER_TOOLS = ("Skill", "SlashCommand", "Read")

PROBE_ROOT_PREFIX = "better-skill-creator-probe-"

# --------------------------------------------------------------------------
# Permission policy for the sessions this harness launches
# --------------------------------------------------------------------------

# A probe is not this harness talking to itself. The queries come out of an eval
# set and the `<skill_content>` block comes out of a SKILL.md, and both arrive
# from wherever the skill did -- a teammate's repository, a marketplace entry, a
# downloaded archive. Each probe hands that text to a full Claude Code session
# running on this machine, under this machine's credentials, and the improvement
# call in `improve_description.py` hands over the same SKILL.md body again. With
# no `--permission-mode` a session starts in whatever `permissions.defaultMode`
# the settings it loaded specify -- which this harness's own argparse help used
# to describe as "probes otherwise inherit your permission settings and can act."
# That reading was too broad for a probe and too narrow for the improvement call:
# a probe drops the user scope with `--setting-sources project,local` and runs in
# an empty `mkdtemp`, while the improvement call loads every scope in the user's
# own repository. The unbounded case is the second one.
#
# `dontAsk` is the mode written for exactly this caller: "If you set `dontAsk`
# mode, Claude Code auto-denies every tool call that would otherwise prompt you.
# Claude runs only actions matching your `permissions.allow` rules, read-only
# Bash commands, and calls approved by a PreToolUse hook. Use this mode for CI
# pipelines or restricted environments where you pre-define exactly what Claude
# may do; the session never waits for input." Denying rather than prompting is
# what a headless run needs -- a mode that prompts has nobody to ask -- and it
# "also denies the built-in `AskUserQuestion` tool" for the same reason. In the
# protected-paths table its row is the only `Denied` of the six.
#
# Detection here reads the `tool_use` block the model emits, not what the
# permission layer then does with it, so a denied call is still a recorded
# routing decision. Nothing on that page says `dontAsk` puts instructions into
# the session the way `plan` and `auto` do -- but that is an absence of evidence,
# not a measurement, and no run has compared trigger rates under it.
#
# **`plan` is not the safe mode, and reading it as one is the error this
# paragraph exists to stop happening twice.** The published table gives
# `default` as "Reads only" and `plan` as "Reads, plus classifier-approved
# commands when auto mode is available" -- so where auto mode is available,
# `plan` runs shell commands unprompted that a session in Manual mode would have
# prompted for. It is instruction rather than enforcement at the joint that
# matters: "In sessions with bypass permissions available, Claude Code also
# doesn't enforce plan mode's blocks. Claude is still instructed to plan without
# editing, but a file edit or shell command it attempts during planning runs
# without prompting." And it puts a planning preamble in front of the routing
# decision this harness is built to measure. The old spend banner recommended it
# and the old help text gave it as the worked example; that was wrong on all
# three counts.
#
# **What this does not close.** Under `dontAsk` the allow rules are what still
# grants, along with two things no rule is needed for: the built-in read-only
# Bash set, and anything a PreToolUse hook approves. For a probe that is very
# nearly nothing -- an empty `mkdtemp` cwd, user scope dropped. For the
# improvement call it is more than nothing, because that call inherits the
# parent's cwd and passes no `--setting-sources`, so a permissive rule of the
# user's own is still in force. The CLI's `--tools ""` removes the *built-in*
# tools from the request and would close most of the rest; it "doesn't affect
# MCP tools", so closing those needs `--disallowedTools "mcp__*"` as well. It is
# named here rather than used because this change did not verify the resulting
# session, only that the flag parses (`claude --tools "" --help` exits 0).
# (Quoted 2026-08-06 from https://code.claude.com/docs/en/permission-modes.md
# and /docs/en/cli-reference.md, read against `claude --help` on Claude Code
# 2.1.223. Documented behaviour, not observed -- no live probe was run for this
# change, so what a session does under a mode is what those pages say it does.)
SAFE_PERMISSION_MODE = "dontAsk"

# The one value meaning "pass no --permission-mode at all, and take whatever the
# host's settings allow" -- the behaviour every caller used to get for free.
#
# It is spelled out rather than left as `None` because `None` is what a caller
# passes when it has no opinion, and a caller with no opinion must land on the
# safe mode. The old signature could not tell those two apart, so "I did not
# think about permissions" and "I want the host's permissions" were the same
# argument and resolved to the second one. Worth naming precisely: the old
# default was not `manual`, it was *whatever this machine's
# `permissions.defaultMode` says*, which a settings file can set to `acceptEdits`.
INHERIT_PERMISSION_MODE = "inherit"

# Modes a session may be launched with when nobody has said otherwise.
#
# `manual` and `default` are one mode under two spellings -- "Its config value is
# `default`", and Manual is the name the CLI shows -- and the row is "Reads only".
# A headless session cannot answer the prompt everything else raises, so neither
# can act beyond that row. Both bound the *prompting* path rather than action as
# such: an allow rule pre-approves under them exactly as it does under `dontAsk`,
# so all three carry the residual named above.
#
# `default` is carried as well as `manual` because it is the spelling with no
# version floor. The `manual` alias "require[s] Claude Code v2.1.200 or later",
# so on a CLI old enough to reject `dontAsk` it is just as likely to be rejected,
# and `default` is then the only safe value that still parses. (Verified
# accepted: `claude --permission-mode default --help` exits 0 on 2.1.223, though
# `claude --help` omits it from the choices it prints. 2026-08-06.)
#
# Neither is the default here, because a mode that prompts turns a probe into an
# error rather than a measurement.
SAFE_PERMISSION_MODES = frozenset({SAFE_PERMISSION_MODE, "manual", "default"})

# Why each remaining mode needs --allow-host-permissions, in the words of the
# page that documents it. A refusal quotes the row rather than saying "unsafe":
# the user chose the mode on purpose and is owed the reason it was refused.
#
# These strings are printed inside hand-wrapped blocks, so every consumer wraps
# them at the point of use rather than assuming a width.
PERMISSION_MODE_RISK = {
    "acceptEdits":
        "auto-approves file edits and the common filesystem commands (mkdir, "
        "touch, rm, rmdir, mv, cp, sed) inside the working directory",
    "auto":
        "auto-approves reads and working-directory edits outright and sends the "
        "rest to a background classifier, which approves what it does not flag",
    "bypassPermissions":
        "disables the permission prompts and safety checks, so tool calls "
        "execute immediately, including writes to protected paths",
    "plan":
        "runs \"Reads, plus classifier-approved commands when auto mode is "
        "available\" -- more than Manual mode's \"Reads only\" -- and its blocks "
        "are not enforced in sessions where bypass permissions are available",
    INHERIT_PERMISSION_MODE:
        "is this harness's name for passing no --permission-mode at all, so each "
        "session starts in whatever permissions.defaultMode the settings it "
        "loaded specify",
}

# Every value this harness accepts, bound to `choices=` so a typo is a usage
# error rather than a mode the CLI rejects one probe at a time, after the spend
# gate has already been passed.
#
# One value here is not the CLI's, deliberately: `inherit` is this harness's
# sentinel for "omit the flag" and is never forwarded -- `claude
# --permission-mode inherit` is an error, correctly. Every other member is a
# value the CLI takes, `default` included, which `claude --help` accepts without
# listing. (Checked with `claude --permission-mode <value> --help`, which
# validates before printing and starts no session; Claude Code 2.1.223,
# 2026-08-06.)
PERMISSION_MODES = tuple(sorted(SAFE_PERMISSION_MODES | set(PERMISSION_MODE_RISK)))

# Rough per-probe cost, USD, used only for the pre-flight projection.
# Sources: opus measured at $0.4267 and $0.3978 over 16-17 turns
# (research/02-trigger-eval.md F15); haiku measured at $0.0125 warm / $0.0579
# cold in an empty project (research/05-cost-safety-resource.md F2); sonnet
# measured while validating this rewrite — 6 full sessions against a small
# repo scaffold reported $0.505 total, i.e. ~$0.084 each. A probe that triggers
# early is killed before its `result` event and costs less, so these numbers are
# an upper bound per probe. Estimates for a warning, not an invoice — override
# with --cost-per-probe.
#
# Every one of those numbers was measured before SAFE_PERMISSION_MODE existed,
# i.e. with no --permission-mode passed at all. A mode changes how many turns a
# session takes and therefore what it costs, so these are the old regime's
# figures carried forward unremeasured; re-measuring them means paying for the
# runs. They are a projection the user is asked to approve, and --cost-per-probe
# is the override, so carrying them is a stale warning rather than a stale
# invoice. (Noted 2026-08-06.)
COST_PER_PROBE_USD = {
    "opus": 0.41,
    "sonnet": 0.09,
    "haiku": 0.02,
}
DEFAULT_COST_PER_PROBE_USD = 0.20

# Jobs allowed to sit submitted-but-not-yet-collected *beyond* the worker count.
# Only `num_workers` can be running, so this is the hand-off cushion that keeps a
# worker from idling between finishing one probe and being handed the next; it is
# a constant rather than a fraction of the eval set because the thing it must not
# scale with is exactly the eval set.
#
# The cushion buys nothing measurable. Sweeping 0, 1, 2, 3, 4, 8 and 16 at 4, 16
# and 32 workers against 50 ms fake probes put every value within +/-0.4% of the
# unbounded driver at >=92% utilisation -- and 50 ms is some 1200x more adverse
# than the 60-120 s a real probe takes, so at the real duration the hand-off is
# unmeasurable by construction. Nothing pins the value; the suite passes at 0, 1,
# 2 and 7.
#
# It did cost something once. While a Ctrl-C was still swallowed, the jobs sitting
# in the pool's queue were exactly the ones a freed worker could still pick up
# while `cleanup_owned` ran, so an interrupt stranded `min(this, num_workers)`
# billed sessions -- against 9 measured for the unbounded driver at 8 workers.
# `_INTERRUPTED` closed that: a worker that dequeues after the flag is up records
# `interrupted` instead of launching. The cushion is now free on both sides, and 2
# stands for want of a reason to move it.
# (Measured 2026-08-06, CPython 3.13.1, Windows 10 10.0.19045, fake worker. The
# orphan counts are from before the `_INTERRUPTED` fix and are kept as the record
# of what the window was worth on its own.)
OUTSTANDING_JOB_BUFFER = 2

_TERMINAL = object()

# --------------------------------------------------------------------------
# Blast-radius control: probe roots and child processes this process created.
# --------------------------------------------------------------------------

_OWNED_ROOTS: set[str] = set()
_LIVE_PROCS: set[subprocess.Popen] = set()
_OWNED_LOCK = threading.Lock()
_CLEANUP_INSTALLED = False

# Set the moment a run is interrupted, and read at the two points in
# `run_single_query` where a probe would otherwise start spending.
#
# This, not the scheduling loop, is what stops the tail. The main thread cannot
# be relied on to notice an interrupt promptly -- on Windows only SIGINT breaks
# it out of a blocking wait, because CPython's C signal handler sets the
# interrupt event for that signal alone -- so the decision is enforced where the
# money is spent rather than where the jobs are handed out. A worker that
# dequeues a job after this is set returns an `error` record without launching
# anything, which is never scored.
_INTERRUPTED = threading.Event()


def _rmtree_retry(path: Path, attempts: int = 5) -> bool:
    """Remove a tree, retrying briefly.

    Windows refuses to unlink a directory that is still some process's cwd, and
    a just-killed `claude` can hold it for a moment. ignore_errors=True would
    silently leave the whole tree behind, so retry instead and report.
    """
    for i in range(attempts):
        try:
            shutil.rmtree(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            if i == attempts - 1:
                return False
            time.sleep(0.2 * (i + 1))
    return False


def _register_root(path: Path) -> None:
    with _OWNED_LOCK:
        _OWNED_ROOTS.add(str(path))


def _release_root(path: Path) -> None:
    """Remove one probe root, and forget we own it only if that worked.

    Discarding unconditionally was a leak with a copy of the user's project in
    it. ``_rmtree_retry`` exists precisely because a just-killed ``claude`` can
    hold its cwd on Windows for a moment, so a root that survives all five
    attempts is the one case the exit sweep must still know about -- and it is
    the case the old order dropped from ``_OWNED_ROOTS``. By the time the sweep
    ran the holding process was gone and the retry would have succeeded, but
    nothing was left to tell it the directory existed. Under ``--scaffold`` what
    stayed behind under %TEMP% was a copy of the scaffold tree, announced by one
    stderr line.
    """
    if _rmtree_retry(path):
        with _OWNED_LOCK:
            _OWNED_ROOTS.discard(str(path))
        return
    print(
        f"Warning: could not remove probe root {path} yet; it stays registered "
        f"and is retried when this process exits.",
        file=sys.stderr,
    )


def _register_proc(proc: subprocess.Popen) -> None:
    with _OWNED_LOCK:
        _LIVE_PROCS.add(proc)


def _release_proc(proc: subprocess.Popen) -> None:
    with _OWNED_LOCK:
        _LIVE_PROCS.discard(proc)


def cleanup_owned() -> list[str]:
    """Kill our children and remove the probe roots *this process* created.

    Returns the roots that are still on disk, still registered, for whoever
    sweeps next. Same rule as :func:`_release_root`: a root is forgotten only
    once it is gone. This runs more than once in a normal interrupted run --
    from ``run_eval``'s unwind and again from the exit sweep -- and the second
    call is the one that succeeds after the process holding a directory has
    died, so it must still be able to see it.

    Deliberately never sweeps %TEMP% for other processes' probe roots by
    prefix: a concurrent run's in-flight probe must not have its command file
    deleted underneath it.
    """
    with _OWNED_LOCK:
        procs = list(_LIVE_PROCS)
        roots = list(_OWNED_ROOTS)
    for proc in procs:
        try:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
        except Exception:
            pass
    removed = {root for root in roots if _rmtree_retry(Path(root))}
    with _OWNED_LOCK:
        _OWNED_ROOTS.difference_update(removed)
        _LIVE_PROCS.difference_update(procs)
    return [root for root in roots if root not in removed]


def _final_cleanup() -> None:
    """The exit sweep, and the last chance to say what it could not remove."""
    for root in cleanup_owned():
        print(
            f"Warning: probe root {root} could not be removed and is left behind. "
            f"If --scaffold was used it holds a copy of that tree; delete it by hand.",
            file=sys.stderr,
        )


def install_cleanup_handlers() -> None:
    """Register cleanup on normal exit and on the signals we can catch.

    **SIGINT is left to** ``signal.default_int_handler``, deliberately. Handling
    it here instead was the defect: that replaced the one handler that raises
    ``KeyboardInterrupt``, so Ctrl-C never unwound ``run_eval``'s scheduling
    loop and the ``except BaseException`` branch that cancels the queued futures
    was dead code under the CLI. What ran in its place was ``cleanup_owned()``
    on the main thread -- a snapshot, then a kill with ``wait(timeout=5)`` per
    child and up to ~3s of rmtree backoff per root -- while the pool's worker
    threads were still alive and still dequeuing. Every worker that finished
    during those seconds started a fresh *billed* ``claude`` for the next queued
    job. Those children were registered after the snapshot and were still
    running when ``os.kill(os.getpid(), signum)`` landed under SIG_DFL, where
    atexit does not fire. Ctrl-C therefore kept spending and then orphaned what
    it had bought.

    The other signals get a handler that raises ``KeyboardInterrupt`` in the
    main thread, so they unwind through that same path rather than a second one
    of their own. Nothing here calls :func:`cleanup_owned`: a signal handler
    runs on the main thread, ``_OWNED_LOCK`` is not reentrant, and a handler
    that took it while the main thread already held it would hang the process
    instead of stopping it.

    What actually stops the spend is :data:`_INTERRUPTED`, which the handler
    sets and which ``run_single_query`` reads before it launches anything. The
    main thread's promptness is then not on the critical path -- which matters,
    because on Windows only SIGINT breaks a blocking wait.

    atexit does not survive SIGKILL / Stop-Process -Force, and nothing
    in-process can. What is stranded then is a probe root under the OS temp dir:
    empty when no ``--scaffold`` was given, and otherwise holding a copy of the
    scaffold tree. Nothing is ever stranded inside the user's project or home.
    """
    global _CLEANUP_INSTALLED
    if _CLEANUP_INSTALLED:
        return
    _CLEANUP_INSTALLED = True
    atexit.register(_final_cleanup)

    def _handler(signum, _frame):
        # Set first, so the workers stop launching even if the raise below has
        # to wait for the main thread to reach a bytecode boundary.
        _INTERRUPTED.set()
        raise KeyboardInterrupt(f"terminated by signal {signum}")

    sigint = getattr(signal, "SIGINT", None)
    if sigint is not None:
        try:
            # Never over SIG_IGN: a parent that ignored the signal said so, and
            # POSIX convention is to leave that alone.
            if signal.getsignal(sigint) is not signal.SIG_IGN:
                signal.signal(sigint, signal.default_int_handler)
        except (ValueError, OSError):
            # Not the main thread, or unsupported on this platform.
            pass

    for name in ("SIGTERM", "SIGBREAK", "SIGHUP"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _handler)
        except (ValueError, OSError):
            # Not the main thread, or unsupported on this platform.
            pass


# --------------------------------------------------------------------------
# Probe
# --------------------------------------------------------------------------


def claude_argv() -> list[str]:
    """Resolve the argv prefix that launches `claude`.

    `shutil.which` finds the npm `claude.cmd` shim, which a bare "claude" in an
    argv list cannot launch on Windows (CreateProcess does not consult PATHEXT
    and cannot exec a batch file); routing those through %COMSPEC% /c is what
    makes an npm install work.

    Overrides, in order:
      BETTER_SKILL_CREATOR_CLAUDE_ARGV  JSON list — used by the test suite to point at
                                 a stub so tests never spend anything.
      BETTER_SKILL_CREATOR_CLAUDE_BIN   a single path, for a non-standard install.
    """
    raw = os.environ.get("BETTER_SKILL_CREATOR_CLAUDE_ARGV")
    if raw:
        return list(json.loads(raw))
    resolved = os.environ.get("BETTER_SKILL_CREATOR_CLAUDE_BIN") or shutil.which("claude") or "claude"
    if os.name == "nt" and resolved.lower().endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", resolved]
    return [resolved]


def _pump(stream, sink) -> None:
    try:
        for raw in stream:
            sink(raw)
    except Exception:
        pass
    finally:
        sink(_TERMINAL)


class ScaffoldError(ValueError):
    """A ``--scaffold`` tree that must not be copied into a probe root."""


def _redirect_kind(entry: Path) -> str | None:
    """Name how *entry* redirects, or None when it is ordinary content.

    Gates on the reparse *attribute* rather than on ``is_symlink()``, which
    answers False for an NTFS directory junction — and a junction needs no
    elevation to create, so it is the reachable form on Windows rather than the
    exotic one. The packager was bitten by exactly this and decided containment
    the same way; see ``package_skill.py``'s module docstring.

    An entry that cannot be stat-ed is refused rather than guessed at.
    """
    try:
        info = entry.lstat()
    except OSError:
        return "unreadable entry"
    if stat.S_ISLNK(info.st_mode):
        return "symlink"
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if getattr(info, "st_file_attributes", 0) & reparse_flag:
        tag = getattr(info, "st_reparse_tag", 0)
        if tag == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003):
            return "directory junction"
        if tag == getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C):
            return "symlink"
        return f"reparse point (tag {tag:#x})"
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        return "special file"
    return None


def _redirect_target(entry: Path) -> str:
    """Where an entry points, in a form a human can recognize."""
    try:
        target = os.readlink(entry)
    except (OSError, ValueError):
        # Not a link, or a reparse tag os.readlink does not understand. The
        # resolved path is the honest answer in both cases.
        try:
            return str(entry.resolve())
        except (OSError, ValueError, RuntimeError):
            return "<unreadable>"
    # Windows hands back the extended-length form for absolute targets.
    if target.startswith("\\\\?\\UNC\\"):
        return "\\\\" + target[8:]
    if target.startswith("\\\\?\\"):
        return target[4:]
    return target


# Names never copied into a probe root, matched case-folded against the whole
# basename, for files and directories alike and at every depth.
#
# Deliberately far smaller than package_skill.py's policy, which decides what a
# *stranger* receives from a published archive. This decides what a probe's
# working directory holds, and --scaffold exists so "file paths named in queries
# resolve" — so a name a query could plausibly reach for must not be here. That
# is not a stylistic preference: a query naming an absent path spends the
# --max-tools budget hunting for it and is recorded ``no_trigger``, which is
# scored, rather than ``error``, which is not. Over-excluding therefore moves
# the recall number this harness exists to produce, and moves it silently.
#
# Measured against package_skill.py's tables, 2026-08-06: its SENSITIVE_WORDS
# and SENSITIVE_COMPOUNDS rules drop tokens.md, token-limits.md,
# counting-tokens.py and api-key-reference.md; its dot-prefix blanket drops
# .github, .editorconfig and .python-version; its ROOT_EXCLUDE_DIRS drops
# tests/; and its *.key glob drops translations.key. Of 41 realistic scaffold
# entries it kept three. None of those rules are adopted here.
SCAFFOLD_EXCLUDED_NAMES = {
    # Version control. `.git` is the one entry that is a security exclusion
    # rather than a housekeeping one, and it is not only the credentialed remote
    # URL in .git/config: in a `git worktree` checkout `.git` is a *file* holding
    # an absolute `gitdir:` pointer, which makes the probe root a live and
    # writable checkout of the user's real repository. No link is involved, so
    # the reparse gate below cannot see it. Excluded by name for that reason.
    ".git": "version control metadata (may carry credentialed remote URLs)",
    ".hg": "version control metadata",
    ".svn": "version control metadata",
    # Dependency and build trees. No eval query resolves a path inside one, and
    # they are the bulk of what a per-probe copy would carry.
    ".venv": "virtual environment",
    "venv": "virtual environment",
    # POSIX `venv` symlinks bin/python (Lib/venv/__init__.py sets use_symlinks
    # False only under os.name == "nt"), so an unexcluded environment directory
    # is a refusal on Linux and macOS and an accept on Windows. Bare `env` is
    # deliberately absent: it is far more often content than an environment.
    ".tox": "test environment",
    ".nox": "test environment",
    ".direnv": "direnv environment",
    ".conda": "conda environment",
    "virtualenv": "virtual environment",
    "node_modules": "installed dependencies",
    "site-packages": "installed dependencies",
    "__pycache__": "Python bytecode cache",
    # Credential stores. Named individually rather than by a dot-prefix blanket,
    # which would also take .github, .editorconfig and .gitignore.
    ".ssh": "SSH key material - may contain secrets",
    ".gnupg": "GnuPG key material - may contain secrets",
    ".aws": "cloud credentials - may contain secrets",
    ".azure": "cloud credentials - may contain secrets",
    ".gcloud": "cloud credentials - may contain secrets",
    ".kube": "cluster credentials - may contain secrets",
    ".docker": "registry credentials - may contain secrets",
    ".npmrc": "package registry token - may contain secrets",
    ".pypirc": "package registry token - may contain secrets",
    "id_rsa": "SSH private key",
    "id_dsa": "SSH private key",
    "id_ecdsa": "SSH private key",
    "id_ed25519": "SSH private key",
}

# Patterns, case-folded against the whole basename. Held to dotenv spellings
# alone. The packager's wider key-material globs are not adopted: `*.key` reads
# translations.key as a private key, and a localization file a query names is
# exactly what must not disappear.
_ENV_REASON = "environment file - may contain secrets"
SCAFFOLD_EXCLUDED_GLOBS = (
    (".env", _ENV_REASON),
    (".env.*", _ENV_REASON),
    ("*.env", _ENV_REASON),
)

# Spellings that exist precisely to be committed: they document which variables
# a project needs while carrying none of their values. `.env.*` matches every
# one of them, and dropping a scaffold's `.env.example` would take away the one
# file an env-shaped query can legitimately resolve.
SCAFFOLD_ENV_TEMPLATES = frozenset({
    ".env.example", ".env.sample", ".env.template", ".env.dist", ".env.defaults",
})

# Left out at every depth, not just the top level. The probe writes its own
# .claude/commands/ into the workspace root, and a scaffold's directory there
# would collide with it — but the deeper reason is that `.claude/skills/` is
# discovered at depth: `references/how-skills-load.md` records that a skill at
# `apps/web/.claude/skills/deploy` registers as `apps/web:deploy`. A scaffold
# carrying one would put a competing skill in the probe's own session, which
# measures something other than the description under test.
#
# Nested `.claude/settings.json` appears NOT to be read — the shipped CLI names
# four settings sources (user, policy, local, project) and no directory-scoped
# variant, and this repo's own findings measured a copied `permissions.allow`
# being discarded in an untrusted workspace. The skills path is the evidenced
# one; the directory goes as a whole because splitting it would keep
# `.claude/skills/` out while leaving the collision case in.
_DOT_CLAUDE_REASON = "Claude Code configuration; the probe supplies its own, and a nested skill would compete"


def _scaffold_exclusion(name: str) -> str | None:
    """Why *name* is left out of a probe root, or None when it is copied.

    Case-folded, because ``.GIT`` and ``__PYCACHE__`` name the same directory
    entries as their lowercase spellings on Windows and macOS; the packager's
    exact-name tables are case-sensitive and miss exactly that. On a
    case-sensitive filesystem this over-excludes in principle — ``.GIT`` really
    is a distinct directory on ext4 — but every differently-cased spelling of a
    name in these tables is either the thing being excluded anyway or
    implausible as content, whereas a ``.git`` created as ``.GIT`` on NTFS or
    APFS would otherwise put a credentialed config in every probe root.

    Depth-independent: no name here means one thing at the top level and
    another below it.
    """
    lowered = name.lower()
    if lowered == ".claude":
        return _DOT_CLAUDE_REASON
    if lowered in SCAFFOLD_ENV_TEMPLATES:
        return None
    reason = SCAFFOLD_EXCLUDED_NAMES.get(lowered)
    if reason is not None:
        return reason
    for pattern, why in SCAFFOLD_EXCLUDED_GLOBS:
        if fnmatch.fnmatch(lowered, pattern):
            return why
    return None


def _copytree_ignore(dirpath: str, names: list[str]) -> set[str]:
    """``shutil.copytree``'s ignore hook, so exclusion applies at every depth."""
    return {name for name in names if _scaffold_exclusion(name) is not None}


def validate_scaffold(scaffold: str | None) -> list[tuple[str, str]]:
    """Refuse a scaffold whose entries are not plain files and directories.

    ``copytree``/``copy2`` follow what they are handed, so an entry that
    redirects has its *target's content* materialized inside the probe root as
    ordinary content — and the probe subprocess runs with that root as its cwd.
    Copying links as links is not the fix: the recreated link still points out
    of the tree and the probe can follow it later.

    Everything the copy leaves out is left out of this walk first, and by the
    same predicate. The two must agree in that direction or the check refuses a
    scaffold over an entry that would never have been copied — measured, a
    ``.venv`` holding one linked package, a ``node_modules`` holding a pnpm store
    junction, and a repository whose ``.git/hooks`` are symlinked to a shared
    directory were all refused before the exclusions existed. They must agree in
    the other direction too: what is walked is exactly what is copied, so no
    excluded subtree hides a link the copy would then follow.

    The rest of the tree is walked in full, not just its top level. A scaffold
    whose own children are all ordinary directories still leaks when a link sits
    further down, because ``copytree`` dereferences at every depth.

    Returns the excluded paths and their reasons, in walk order, so one traversal
    serves both the refusal and the report. Excluded directories are pruned
    rather than measured: reporting a file count for one would mean walking into
    the junctions this function exists to decline.

    Two routes this refusal does not cover, both handled by
    :func:`scaffold_disclosures` as reports rather than gates, and one it cannot
    cover at all:

    * A **hard link** has no target to resolve and is indistinguishable from an
      ordinary file. It is reported, never refused: direction is undecidable,
      because nothing on disk records which name came first, so a scaffold that
      was hard-link snapshotted (``cp -al``, ``rsync --link-dest``, rsnapshot)
      reports every file as having an unaccounted name with nothing having
      entered the tree — measured 10 of 10. A bare ``st_nlink > 1`` is worse
      still in this loop, since every ext4 directory has ``st_nlink >= 2``
      (measured 18,696 of 18,696, against 0 of 8 on NTFS), so it would refuse
      every Linux scaffold and pass on Windows.
    * A **credential inside an innocently named file** is copied. High-precision
      markers report it; nothing here withholds the file, because a withheld
      path a query names is scored a non-trigger.
    * A **POSIX mount point or bind mount** inside the scaffold is an ordinary
      directory to ``lstat`` — no ``S_IFLNK``, no reparse attribute — so
      ``copytree`` materializes what is mounted there. Windows closes the
      equivalent case only because a volume mount point carries
      ``IO_REPARSE_TAG_MOUNT_POINT``. Comparing ``st_dev`` would close it and
      would also refuse a scaffold that legitimately spans a mount, so it is
      named here rather than gated.

    (Measured on CPython 3.13.1 / Windows 10 10.0.19045 and CPython 3.12.3 /
    WSL2 ext4, 2026-08-06.)
    """
    if not scaffold:
        return []
    src = Path(scaffold)
    if not src.is_dir():
        raise ScaffoldError(f"--scaffold {src} is not a directory")
    excluded: list[tuple[str, str]] = []
    for parent, dirnames, filenames in os.walk(src, topdown=True, followlinks=False):
        here = Path(parent)

        # Excluded before examined, and before os.walk descends. The other order
        # refuses a .venv that is itself a junction, over an entry the copy loop
        # never touches.
        kept_dirs = []
        for name in sorted(dirnames):
            reason = _scaffold_exclusion(name)
            if reason is None:
                kept_dirs.append(name)
            else:
                excluded.append((f"{(here / name).relative_to(src).as_posix()}/", reason))
        dirnames[:] = kept_dirs

        kept_files = []
        for name in sorted(filenames):
            reason = _scaffold_exclusion(name)
            if reason is None:
                kept_files.append(name)
            else:
                excluded.append(((here / name).relative_to(src).as_posix(), reason))

        # Files as well as directories: in a git worktree checkout `.git` is a
        # file, and a `.git` symlink lands here rather than in dirnames.
        for name in kept_dirs + kept_files:
            entry = here / name
            kind = _redirect_kind(entry)
            if kind is not None:
                # Raised before os.walk descends, so a junction is never walked
                # through: followlinks=False does not prune one.
                raise ScaffoldError(
                    f"--scaffold {src} contains a {kind}, which would be copied as "
                    f"whatever it points at rather than as itself:\n"
                    f"         {entry.relative_to(src)} -> {_redirect_target(entry)}"
                )
    return excluded


# Credential markers, each self-identifying: a vendor-assigned prefix with a
# fixed body length, or a format-defined delimiter line. Nothing statistical.
#
# Entropy scoring was measured and rejected: at the lowest threshold with usable
# recall it produced 30 false positives on this repository, 28 of them file
# paths — the exact string class --scaffold exists to make resolvable — and the
# standard refinement that bans "/" to kill those discards 48% of real base64
# AWS secret keys, since standard base64 contains "/". Bare 32-hex scored 1,401
# false positives on the Python standard library. (Measured 2026-08-06 over
# 43.2 MB / 2,692 files across this repository and CPython 3.13's Lib/.)
_CREDENTIAL_MARKERS = (
    (re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY(?: BLOCK)?-----"), "private key block"),
    (re.compile(rb"^PuTTY-User-Key-File-\d+:", re.MULTILINE), "PuTTY private key"),
    (re.compile(rb"(?<![A-Z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![0-9A-Z])"), "AWS access key id"),
    (re.compile(rb"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{36}(?![A-Za-z0-9])"), "GitHub token"),
    (re.compile(rb"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{82}(?![A-Za-z0-9])"), "GitHub PAT"),
    (re.compile(rb"(?<![A-Za-z0-9_-])glpat-[A-Za-z0-9_-]{20}(?![A-Za-z0-9_-])"), "GitLab PAT"),
    (re.compile(rb"(?<![A-Za-z0-9-])xox[abposr]-[0-9]{10,13}-[0-9A-Za-z-]{10,}"), "Slack token"),
    (re.compile(rb"https://hooks\.slack\.com/services/T[0-9A-Z]{8,12}/B[0-9A-Z]{8,12}/[0-9A-Za-z]{24}"),
     "Slack webhook"),
    (re.compile(rb"(?<![A-Za-z0-9_])[sr]k_live_[0-9A-Za-z]{24,}"), "Stripe live key"),
    (re.compile(rb"(?<![A-Za-z0-9_-])sk-ant-(?:api|admin)\d{2}-[A-Za-z0-9_-]{80,}"), "Anthropic API key"),
    (re.compile(rb"(?<![A-Za-z0-9_-])sk-proj-[A-Za-z0-9_-]{40,}"), "OpenAI project key"),
    (re.compile(rb"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])"), "Google API key"),
    (re.compile(rb"(?<![A-Za-z0-9_])npm_[A-Za-z0-9]{36}(?![A-Za-z0-9])"), "npm token"),
    (re.compile(rb"(?<![A-Za-z0-9_-])pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,}"), "PyPI token"),
    (re.compile(rb"(?<![A-Za-z0-9._-])SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])"),
     "SendGrid key"),
    (re.compile(rb"AccountKey=[A-Za-z0-9+/]{86}=="), "Azure storage key"),
)

# Cheap literal gate: a file whose bytes contain none of these cannot match any
# marker, and skipping the alternation for it is a measured 15-19x speedup with
# an identical hit set.
_CREDENTIAL_PREFILTER = re.compile(
    rb"PRIVATE KEY|PuTTY-User-Key|AKIA|ASIA|gh[pousr]_|github_pat_|glpat-|xox[abposr]-"
    rb"|hooks\.slack\.com|k_live_|sk-ant-|sk-proj-|AIza|npm_|pypi-AgEI|SG\.|AccountKey="
)

# AWS's own published documentation placeholder. Structurally identical to a
# live key, and a scaffold that documents AWS setup will carry it.
_CREDENTIAL_ALLOWLIST = (b"AKIAIOSFODNN7EXAMPLE",)

# Read bound, plus an overlap so a marker starting near the edge is not cut in
# half. Measured: a 32-byte marker beginning 10 bytes before a 4 KiB bound is
# missed without the overlap. No size-based skip — at this bound a 48 MB binary
# already costs only the bound, and the extra stat measured slower than nothing.
_CREDENTIAL_READ_BYTES = 64 * 1024
_CREDENTIAL_OVERLAP = 128


def _credential_markers_in(data: bytes) -> list[str]:
    """Marker kinds present in *data*, never the matched bytes themselves."""
    if not _CREDENTIAL_PREFILTER.search(data):
        return []
    for allowed in _CREDENTIAL_ALLOWLIST:
        data = data.replace(allowed, b"")
    found = []
    for pattern, kind in _CREDENTIAL_MARKERS:
        if pattern.search(data) and kind not in found:
            found.append(kind)
    return found


def scaffold_disclosures(scaffold: str | None) -> list[tuple[str, str]]:
    """Things worth telling the user about a scaffold that is safe to copy.

    Reports, never gates. Both routes below would move the recall number if they
    withheld anything — a query naming an absent path is scored ``no_trigger``,
    which counts, rather than ``error``, which does not — and both have a fix
    that leaves the path and its bytes in place, so a report costs the user
    nothing to act on.

    Hard links are accounted by inode rather than by ``st_nlink`` alone: an
    inode is only reported when its link count exceeds the number of names for
    it *inside* the scaffold, which acquits a tree's own internal duplicates.
    Regular files only. This rides the ``lstat`` the walk already performs —
    measured 0.174s against a 0.175s baseline over 2,054 entries — and fired on
    0 of 180,766 files across fourteen real trees. Never source it from
    ``os.scandir``'s cached ``DirEntry.stat()``, which returns ``st_nlink == 0``
    for every file on Windows and would disable the check silently.

    Content is scanned once per run, never per probe: the whole-tree scan costs
    3.1s once against 864s across a 300-probe loop, and threading does not help
    because ``re`` holds the GIL. Two passes, because neither covers the other's
    case — raw bytes, which reads cp1252 and other single-byte encodings a
    decode-first scanner would skip on ``UnicodeDecodeError``, plus a UTF-16
    decode when a BOM is present, which raw bytes miss entirely on NUL
    interleaving. (Measured 2026-08-06, CPython 3.13.1 / Windows 10.)
    """
    if not scaffold:
        return []
    src = Path(scaffold)
    if not src.is_dir():
        return []

    notices: list[tuple[str, str]] = []
    by_inode: dict[tuple[int, int], list[str]] = {}
    nlink: dict[str, int] = {}

    for parent, dirnames, filenames in os.walk(src, topdown=True, followlinks=False):
        here = Path(parent)
        dirnames[:] = [n for n in sorted(dirnames) if _scaffold_exclusion(n) is None]
        for name in sorted(filenames):
            if _scaffold_exclusion(name) is not None:
                continue
            entry = here / name
            rel = entry.relative_to(src).as_posix()
            try:
                info = entry.lstat()
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            if info.st_nlink > 1 and info.st_ino:
                by_inode.setdefault((info.st_dev, info.st_ino), []).append(rel)
                nlink[rel] = info.st_nlink
            try:
                with open(entry, "rb") as handle:
                    data = handle.read(_CREDENTIAL_READ_BYTES + _CREDENTIAL_OVERLAP)
            except OSError:
                continue
            kinds = _credential_markers_in(data)
            if not kinds and data[:2] in (b"\xff\xfe", b"\xfe\xff"):
                try:
                    kinds = _credential_markers_in(data.decode("utf-16", "ignore").encode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    kinds = []
            for kind in kinds:
                notices.append((rel, kind))

    for names in by_inode.values():
        inside = len(names)
        for rel in names:
            if nlink[rel] > inside:
                notices.append(
                    (rel, f"hard link: {nlink[rel]} names on disk, {inside} inside the scaffold")
                )
    return sorted(notices)


def check_scaffold(scaffold: str | None) -> None:
    """Refuse an unsafe scaffold, and say what a safe one still leaves out.

    Both halves run once per invocation, before the spend projection. A refusal
    raised from inside the copy instead arrives once per probe through
    ``run_single_query``'s blanket handler, which records it as
    ``status: "error"`` — indistinguishable from a rate limit or a dead harness,
    and only after the user has been shown a bill and asked to approve it.

    An exclusion is worse than that, because it produces no record at all. A
    query naming an excluded path spends the tool budget hunting for it and is
    scored a clean non-trigger, so silence here reads as a description that
    failed to route. This is the last point where correcting it is free.
    """
    try:
        excluded = validate_scaffold(scaffold)
    except ScaffoldError as exc:
        print(
            f"Error: {exc}\n"
            f"       Every probe workspace would then hold content from outside the\n"
            f"       scaffold, and the probe subprocess runs inside that workspace.\n"
            f"Fix:   remove that entry, replace it with a real file or directory, or\n"
            f"       point --scaffold at a tree that contains neither.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if excluded:
        width = max(len(path) for path, _ in excluded)
        listing = "\n".join(f"  - {path.ljust(width)}  {reason}" for path, reason in excluded)
        print(
            f"Warning: {len(excluded)} path(s) in --scaffold {scaffold} are not copied "
            f"into a probe workspace:\n"
            f"{listing}\n"
            f"         Every probe runs with its workspace as cwd, so a query naming one\n"
            f"         of these finds nothing there and is scored a non-trigger. That\n"
            f"         measures the scaffold, not the description. Move anything a query\n"
            f"         is meant to resolve out from under these paths.",
            file=sys.stderr,
        )
    disclosures = scaffold_disclosures(scaffold)
    if disclosures:
        width = max(len(path) for path, _ in disclosures)
        listing = "\n".join(f"  - {path.ljust(width)}  {what}" for path, what in disclosures)
        print(
            f"Notice: {len(disclosures)} file(s) in --scaffold {scaffold} are copied into every\n"
            f"        probe workspace and are worth a look first:\n"
            f"{listing}\n"
            f"        These are copied, not withheld, because withholding a path a query\n"
            f"        names would score as a non-trigger. A marker match is far more often\n"
            f"        a test fixture than a live credential, and a hard-link reading like\n"
            f"        this is what a whole-tree backup (cp -al, rsync --link-dest) produces\n"
            f"        for every file with nothing having entered the tree. Replacing either\n"
            f"        with a real copy leaves the path and its bytes unchanged.",
            file=sys.stderr,
        )


def _make_probe_root(scaffold: str | None) -> Path:
    """A fresh temp project root, seeded from *scaffold* when one is given.

    The scaffold is validated *before* ``mkdtemp``, deliberately.
    ``run_single_query`` binds its ``probe_root`` local from this function's
    return value, so raising once the directory exists leaves it registered but
    unreleased until process exit. Refusing first means a rejected scaffold
    creates nothing at all.
    """
    validate_scaffold(scaffold)
    root = Path(tempfile.mkdtemp(prefix=PROBE_ROOT_PREFIX))
    _register_root(root)
    if scaffold:
        src = Path(scaffold)
        for child in src.iterdir():
            if _scaffold_exclusion(child.name) is not None:
                continue
            dest = root / child.name
            if child.is_dir():
                shutil.copytree(child, dest, ignore=_copytree_ignore)
            else:
                shutil.copy2(child, dest)
    (root / ".claude" / "commands").mkdir(parents=True, exist_ok=True)
    return root


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    model: str | None = None,
    max_tools: int = 4,
    setting_sources: str | None = "project,local",
    include_partial_messages: bool = True,
    permission_mode: str | None = SAFE_PERMISSION_MODE,
    scaffold: str | None = None,
    allow_host_permissions: bool = False,
) -> dict:
    """Run one probe and return a record.

    The record's ``status`` is one of:
      ``trigger``     — the model reached for this probe's clone
      ``no_trigger``  — the session reached a terminal verdict without doing so
      ``error``       — anything else. Never scored.

    ``status == "error"`` covers timeouts, non-zero child exits, a stream that
    ends without a ``result`` event, an interrupted run, and any exception
    raised while setting the probe up. None of those are observations about the
    description.
    """
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{skill_name}-skill-{unique_id}"

    record: dict = {
        "query": query,
        "probe_id": clean_name,
        "status": "error",
        "triggered": None,
        "stop_reason": None,
        "error": None,
        "tools": [],
        "elapsed_seconds": 0.0,
        "cost_usd": None,
        "probe_root": None,
        # Harness-health, read off the session's init event.
        "clone_registered": None,
        "competing_skills": [],
    }

    probe_root: Path | None = None
    proc: subprocess.Popen | None = None
    start = time.time()

    try:
        # A worker that was already queued when the run was interrupted must not
        # buy a session nobody is left to wait for. Checked here so a refused
        # probe does not even create a directory.
        if _INTERRUPTED.is_set():
            record["stop_reason"] = "interrupted"
            record["error"] = "run was interrupted before this probe launched"
            return record

        probe_root = _make_probe_root(scaffold)
        record["probe_root"] = str(probe_root)
        command_file = probe_root / ".claude" / "commands" / f"{clean_name}.md"

        indented_desc = "\n  ".join(skill_description.split("\n"))
        command_file.write_text(
            f"---\n"
            f"description: |\n"
            f"  {indented_desc}\n"
            f"---\n\n"
            f"# {skill_name}\n\n"
            f"This skill handles: {skill_description}\n",
            encoding="utf-8",
        )

        cmd = [
            *claude_argv(),
            "-p", query,
            "--output-format", "stream-json",
            "--verbose",
            "--no-session-persistence",
        ]
        if include_partial_messages:
            cmd.append("--include-partial-messages")
        if setting_sources:
            cmd.extend(["--setting-sources", setting_sources])
        # Resolved rather than tested for truth. A falsy `permission_mode` used
        # to mean "omit the flag", which made "I never thought about this" and
        # "give this session my machine's permissions" the same argument -- and
        # every caller that had not thought about it got the second reading.
        # `inherit` is now the only spelling that omits the flag, and reaching
        # it takes the opt-in as well.
        mode = validate_permission_mode(permission_mode, allow_host_permissions)
        if mode != INHERIT_PERMISSION_MODE:
            cmd.extend(["--permission-mode", mode])
        if model:
            cmd.extend(["--model", model])

        # CLAUDECODE guards interactive terminal conflicts; programmatic
        # subprocess use is safe, so drop it to allow nesting.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        env.pop("CLAUDE_CODE_ENTRYPOINT", None)

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(probe_root),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        _register_proc(proc)

        # Re-read after registration, because the window between the check above
        # and Popen is exactly where an interrupt would otherwise buy a whole
        # session that then runs to --timeout while the process waits to exit.
        # Returning here runs the `finally` below, which kills the child.
        if _INTERRUPTED.is_set():
            record["stop_reason"] = "interrupted"
            record["error"] = "run was interrupted as this probe launched"
            return record

        out_q: queue.Queue = queue.Queue()
        err_tail: deque = deque(maxlen=40)
        threading.Thread(target=_pump, args=(proc.stdout, out_q.put), daemon=True).start()
        threading.Thread(
            target=_pump,
            args=(proc.stderr, lambda ln: ln is not _TERMINAL and err_tail.append(ln)),
            daemon=True,
        ).start()

        pending_tool: str | None = None
        accumulated_json = ""
        saw_result = False

        while True:
            remaining = timeout - (time.time() - start)
            if remaining <= 0:
                record["stop_reason"] = "timeout"
                record["error"] = f"probe exceeded --timeout ({timeout}s)"
                break

            try:
                line = out_q.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue

            if line is _TERMINAL:
                record["stop_reason"] = "eof"
                break

            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type")

            # --- Harness health, from the session's own init event. ---------
            # `clone_registered` False means the probe's command file was not
            # picked up at all, so every verdict from this run is void rather
            # than a measurement of the description. `competing_skills` catches
            # an installed copy of the skill under test shadowing the probe:
            # the model routes to the real one, whose name never matches, and
            # recall pins at 0% with no other symptom.
            if etype == "system" and event.get("subtype") == "init":
                slash = event.get("slash_commands") or []
                skills = event.get("skills") or []
                record["clone_registered"] = clean_name in slash
                record["competing_skills"] = [
                    str(s) for s in skills if skill_name in str(s)
                ]
                continue

            # --- Early detection from partial message stream events. -------
            # These can only ever produce a positive verdict. A negative is
            # decided by the assistant-event tool budget or by `result`, never
            # here — that asymmetry is what makes it safe to bail out early on
            # a match without biasing the negative side.
            if etype == "stream_event":
                se = event.get("event", {})
                se_type = se.get("type", "")
                if se_type == "content_block_start":
                    cb = se.get("content_block", {})
                    if cb.get("type") == "tool_use":
                        name = cb.get("name", "")
                        # Not a trigger tool: clear state and keep scanning.
                        pending_tool = name if name in TRIGGER_TOOLS else None
                        accumulated_json = json.dumps(cb.get("input") or {})
                        if pending_tool and clean_name in accumulated_json:
                            record["status"] = "trigger"
                            record["triggered"] = True
                            record["stop_reason"] = "triggered"
                            break
                elif se_type == "content_block_delta" and pending_tool:
                    delta = se.get("delta", {})
                    if delta.get("type") == "input_json_delta":
                        accumulated_json += delta.get("partial_json", "")
                        if clean_name in accumulated_json:
                            record["status"] = "trigger"
                            record["triggered"] = True
                            record["stop_reason"] = "triggered"
                            break
                elif se_type == "content_block_stop":
                    pending_tool = None
                    accumulated_json = ""

            # --- Authoritative tool accounting. ----------------------------
            elif etype == "assistant":
                hit = False
                for item in event.get("message", {}).get("content", []):
                    if item.get("type") != "tool_use":
                        continue
                    name = item.get("name", "")
                    tool_input = item.get("input", {})
                    blob = json.dumps(tool_input if isinstance(tool_input, dict) else {})
                    record["tools"].append({"name": name, "input": blob[:300]})
                    if name in TRIGGER_TOOLS and clean_name in blob:
                        hit = True
                        break
                if hit:
                    record["status"] = "trigger"
                    record["triggered"] = True
                    record["stop_reason"] = "triggered"
                    break
                if max_tools and len(record["tools"]) >= max_tools:
                    record["status"] = "no_trigger"
                    record["triggered"] = False
                    record["stop_reason"] = "max_tools"
                    break

            elif etype == "result":
                saw_result = True
                cost = event.get("total_cost_usd")
                if isinstance(cost, (int, float)):
                    record["cost_usd"] = float(cost)
                if event.get("is_error"):
                    record["stop_reason"] = "result_error"
                    record["error"] = str(event.get("result") or "claude reported is_error")
                else:
                    record["status"] = "no_trigger"
                    record["triggered"] = False
                    record["stop_reason"] = "result"
                break

        # An EOF that never produced a `result` event is a broken probe, not a
        # measurement. Surface the child's exit code and stderr.
        if record["stop_reason"] == "eof" and not saw_result:
            try:
                rc = proc.wait(timeout=5)
            except Exception:
                rc = None
            tail = "".join(list(err_tail)[-10:]).strip()
            record["error"] = (
                f"claude exited (returncode={rc}) without emitting a result event"
                + (f"; stderr: {tail[:600]}" if tail else "")
            )

        return record

    except Exception as exc:  # noqa: BLE001 - recorded, never scored
        record["stop_reason"] = record["stop_reason"] or "exception"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["status"] = "error"
        record["triggered"] = None
        return record

    finally:
        record["elapsed_seconds"] = round(time.time() - start, 2)
        if record["status"] == "error" and record["triggered"] is not None:
            record["triggered"] = None
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=10)
            except Exception:
                pass
            _release_proc(proc)
        if probe_root is not None:
            _release_root(probe_root)


# --------------------------------------------------------------------------
# Spend projection
# --------------------------------------------------------------------------


def estimate_cost_per_probe(model: str | None) -> tuple[float, str]:
    """Return (usd_per_probe, provenance)."""
    key = (model or "").lower()
    for name, value in COST_PER_PROBE_USD.items():
        if name in key:
            return value, f"measured estimate for {name}"
    return DEFAULT_COST_PER_PROBE_USD, "unmeasured model; conservative default"


def read_confirmation(prompt: str) -> str | None:
    """Ask on stdin. Return the typed answer, or ``None`` if nothing can be read.

    **Never infer interactivity from ``isatty()`` alone.** On
    Windows ``isatty()`` returns ``True`` for ``NUL`` and for
    ``subprocess.DEVNULL``, so ``if not sys.stdin.isatty()`` does not detect a
    redirected stream: ``input()`` then runs against a stream already at EOF and
    raises ``EOFError``. That killed ``run_loop`` and ``run_eval`` at the
    documented defaults, before any probe launched -- a spend guard that
    terminated the run it was added to make safe.

    Measured on this machine (CPython 3.13, Windows 10)::

        stdin mode                          isatty()   input()
        subprocess.DEVNULL                  True       EOFError   <- guard missed
        open(os.devnull) / `< NUL`          True       EOFError   <- guard missed
        closed pipe                         False      EOFError

    ``isatty()`` False is still a sound *negative* signal, so it stays as a fast
    path that avoids printing a prompt nobody can answer. ``EOFError`` is the
    authority. Both mean the same thing to the caller: no confirmation was
    given, which is never treated as consent.
    """
    stream = sys.stdin
    if stream is None or getattr(stream, "closed", False):
        return None
    try:
        if not stream.isatty():
            return None
    except (ValueError, OSError):
        # A detached or already-closed handle. Not a terminal.
        return None
    try:
        return input(prompt)
    except EOFError:
        # The stream was NUL/DEVNULL/redirected and isatty() lied. EOF is not a
        # "yes"; it is the absence of an answer.
        print("", file=sys.stderr)
        return None
    except (KeyboardInterrupt, ValueError, OSError):
        # Ctrl-C, or stdin closed under us mid-prompt. Also not a "yes".
        print("", file=sys.stderr)
        return None


def project_spend(
    n_queries: int,
    runs_per_query: int,
    iterations: int,
    model: str | None,
    cost_per_probe: float | None,
    max_cost: float,
    confirm_threshold: float,
    assume_yes: bool,
    label: str = "trigger eval",
    permission_mode: str = SAFE_PERMISSION_MODE,
) -> dict:
    """Print the projected spend and gate the run. Returns the projection.

    Raises SystemExit when the projection exceeds --max-cost, or when it exceeds
    --confirm-threshold and no confirmation is available.

    ``permission_mode`` is displayed rather than enforced -- ``check_permission_mode``
    has already refused an unbounded run by the time this is called. It is here
    because this banner is the one screen a user reads before agreeing to spend,
    and "what will these sessions be allowed to do" belongs next to "what will
    they cost". The mode is also the variable that makes two runs incomparable,
    so it is named at the moment somebody decides to produce a number.
    """
    # Resolved the same way every other consumer resolves it, so a library
    # caller that skipped `check_permission_mode` prices a run under the mode it
    # will actually get rather than under the word `None`.
    permission_mode = SAFE_PERMISSION_MODE if permission_mode is None else permission_mode
    probes = n_queries * runs_per_query * iterations
    if cost_per_probe is None:
        per_probe, provenance = estimate_cost_per_probe(model)
    else:
        per_probe, provenance = cost_per_probe, "--cost-per-probe"
    total = probes * per_probe

    lines = [
        "",
        f"Projected spend for this {label}:",
        f"  queries              {n_queries}",
        f"  runs per query       {runs_per_query}",
    ]
    if iterations != 1:
        lines.append(f"  iterations           {iterations}")
    lines += [
        f"  probes (claude -p)   {probes}",
        f"  model                {model or '(user default)'}",
        f"  est. $/probe         ${per_probe:.4f}   [{provenance}]",
        f"  est. total           ${total:.2f}",
        f"  --max-cost           ${max_cost:.2f}",
        "",
        "  Each probe is a full Claude Code session billed to your subscription,",
        "  running with cwd in a throwaway temp directory.",
        "",
    ]
    if permission_mode == INHERIT_PERMISSION_MODE:
        lines += [
            "  They are launched with no --permission-mode, so each one starts in",
            "  whatever permissions.defaultMode the settings it loads specify.",
            "  Nothing here bounds what a query or a SKILL.md body persuades one",
            "  to do. This is also the only setting whose numbers are comparable",
            "  with the ones recorded in this tree, which were all measured before",
            "  any mode was passed.",
            "",
        ]
    elif permission_mode == SAFE_PERMISSION_MODE:
        lines += [
            f"  They run under --permission-mode {permission_mode}, which auto-denies",
            "  any call it was not pre-approved for rather than acting.",
            "  Comparable only with runs made under the same mode -- a mode changes",
            "  model behaviour, so a number measured under a different one is a",
            "  different measurement.",
            "",
        ]
    elif permission_mode in SAFE_PERMISSION_MODES:
        lines += [
            f"  They run under --permission-mode {permission_mode}, which grants reads",
            "  and prompts for everything else -- and a headless session has nobody",
            "  to prompt, so a probe that reaches for more ends as an error rather",
            "  than as a measurement. Comparable only with runs made under the same",
            "  mode.",
            "",
        ]
    else:
        # `.get` rather than `[...]`: this banner describes a decision somebody
        # else already made, and a mode it has no sentence for must not turn the
        # spend gate into a KeyError. A library caller that skipped
        # `check_permission_mode` and passed `None` reached exactly that.
        risk = PERMISSION_MODE_RISK.get(
            permission_mode, "this harness has no description of"
        )
        lines += [
            f"  They run under --permission-mode {permission_mode}, which",
            *textwrap.wrap(
                risk + ".", width=72, initial_indent="  ", subsequent_indent="  ",
            ),
            "  Comparable only with runs made under the same mode.",
            "",
        ]
    print("\n".join(lines), file=sys.stderr)

    projection = {
        "probes": probes,
        "cost_per_probe_usd": per_probe,
        "cost_per_probe_source": provenance,
        "estimated_total_usd": round(total, 4),
        "max_cost_usd": max_cost,
    }

    if total > max_cost:
        print(
            f"Refusing to start: estimated ${total:.2f} exceeds --max-cost ${max_cost:.2f}.\n"
            f"Reduce --runs-per-query / the eval set, or raise --max-cost deliberately.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if total > confirm_threshold and not assume_yes:
        answer = read_confirmation(f"Proceed with an estimated ${total:.2f}? [y/N] ")
        if answer is None:
            print(
                f"Refusing to start: estimated ${total:.2f} is over the "
                f"--confirm-threshold of ${confirm_threshold:.2f} and stdin cannot be "
                f"read for a confirmation (not a terminal, or already at EOF).\n"
                f"Re-run with --yes to confirm, or raise --confirm-threshold "
                f"deliberately.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted.", file=sys.stderr)
            raise SystemExit(2)

    return projection


# --------------------------------------------------------------------------
# Eval-set shape
# --------------------------------------------------------------------------


class EvalSetError(ValueError):
    """The eval set is valid JSON but not the shape the harness reads."""


EVAL_SET_SHAPE = (
    'A JSON array of objects, each with a "query" string and a "should_trigger"\n'
    "  boolean:\n"
    "    [\n"
    '      {"query": "write release notes for v2.1", "should_trigger": true},\n'
    '      {"query": "what is the capital of France", "should_trigger": false}\n'
    "    ]\n"
    '  An optional "id" string is carried through to the results untouched.'
)

_MAX_REPORTED_PROBLEMS = 20


def validate_eval_set(eval_set, source: str | None = None) -> list[dict]:
    """Check the eval set's *shape* before anything spends money on it.

    ``load_json_file`` proves the file is UTF-8 and syntactically valid JSON and
    stops there. A wrong *shape* therefore surfaced as a bare ``TypeError`` or
    ``KeyError`` from inside the driver -- and the missing-``should_trigger``
    case surfaced only at **scoring** time, i.e. after every probe had already
    been paid for.

    Two of these are silent rather than loud, which is why the check is strict:

    * ``{"queries": [...]}`` is the natural guess for the wrapper shape, and an
      independent verifier wrote exactly that before reading the source.
    * ``"should_trigger": "false"`` is a **non-empty string**, which is truthy,
      so a negative query would have been scored as a positive one with no
      error anywhere -- a wrong measurement that reads as a real one.

    Raises :class:`EvalSetError` listing every problem found, not just the first.
    """
    problems: list[str] = []

    if isinstance(eval_set, dict):
        wrapped = [k for k, v in eval_set.items() if isinstance(v, list)]
        if wrapped:
            problems.append(
                f'the top level is a JSON object, not an array. The array looks like it '
                f'is wrapped under the key "{wrapped[0]}" -- delete the wrapper so the '
                f'file starts with "[".'
            )
        else:
            problems.append(
                f"the top level is a JSON object with keys {sorted(eval_set)[:8]}, "
                f"not an array."
            )
    elif not isinstance(eval_set, list):
        problems.append(f"the top level is a {type(eval_set).__name__}, not an array.")
    elif not eval_set:
        problems.append(
            "the array is empty, so there is nothing to measure. An empty run "
            "produces a 100%-errored rate rather than a result."
        )
    else:
        for i, item in enumerate(eval_set):
            if not isinstance(item, dict):
                problems.append(
                    f"item {i} is a {type(item).__name__}, not an object: "
                    f"{json.dumps(item)[:60]}"
                )
                continue
            keys = sorted(str(k) for k in item)
            if "query" not in item:
                problems.append(f'item {i} has no "query" key (keys present: {keys}).')
            elif not isinstance(item["query"], str):
                problems.append(
                    f'item {i} "query" is a {type(item["query"]).__name__}, not a string.'
                )
            elif not item["query"].strip():
                problems.append(f'item {i} "query" is empty or whitespace.')
            if "should_trigger" not in item:
                problems.append(
                    f'item {i} has no "should_trigger" key (keys present: {keys}). '
                    f"Without it the query has no expected outcome to be scored against."
                )
            elif not isinstance(item["should_trigger"], bool):
                value = item["should_trigger"]
                note = ""
                if isinstance(value, str):
                    note = (
                        " A non-empty string is truthy, so this would be scored as a "
                        "should-trigger query whatever it says."
                    )
                problems.append(
                    f'item {i} "should_trigger" is a {type(value).__name__} '
                    f"({json.dumps(value)}), not a boolean.{note}"
                )

    if not problems:
        return eval_set

    shown = problems[:_MAX_REPORTED_PROBLEMS]
    tail = (
        f"\n  ... and {len(problems) - len(shown)} more"
        if len(problems) > len(shown)
        else ""
    )
    where = f" at {source}" if source else ""
    raise EvalSetError(
        f"eval set{where} is not the shape this harness reads.\n"
        f"Expected: {EVAL_SET_SHAPE}\n"
        f"Found {len(problems)} problem(s):\n"
        + "\n".join(f"  - {p}" for p in shown)
        + tail
    )


def load_eval_set(path: Path) -> list[dict]:
    """Read and shape-check an eval set, or exit 1 with an actionable message."""
    data = load_json_file(path, "eval set")
    try:
        return validate_eval_set(data, str(path))
    except EvalSetError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)


# --------------------------------------------------------------------------
# Probe scheduling arguments
# --------------------------------------------------------------------------


class ProbeArgumentError(ValueError):
    """A worker or repeat count that cannot describe a run of probes."""


def validate_probe_arguments(num_workers, runs_per_query) -> tuple[int, int]:
    """Check the two counts that decide how much work exists and how much runs.

    Both were coerced rather than checked before, and each coercion produced a
    run the caller did not ask for:

    * ``max(1, num_workers)`` turned ``0`` and ``-4`` into a *serial* run. A
      caller who asked for zero workers has a bug in whatever computed it, and
      one worker is not a reading of zero -- it is the harness picking a number
      and not saying so. The clamp existed because the bare value reaches
      ``ThreadPoolExecutor``, which raises ``ValueError: max_workers must be
      greater than 0`` -- *after* the spend gate has printed a bill and the user
      has typed "yes".
    * ``runs_per_query`` was not checked at all. ``0`` yields an empty job list,
      so every query is scored ``errored`` off zero records and the summary
      reports a 100% error rate -- which reads as a dead harness rather than as
      a bad argument. It also prices at zero probes, so ``project_spend`` waves
      it through every cost gate on the way there.

    ``bool`` is refused although it is an ``int`` subclass: ``True`` would
    otherwise pass as a one-worker, one-run request, and nothing that produces a
    boolean here meant a count.

    Raises :class:`ProbeArgumentError` listing every problem found, not just the
    first -- the two arguments are independent, so a caller who got both wrong
    hears about both.
    """
    problems: list[str] = []
    for name, value, what in (
        ("num_workers", num_workers, "how many probes run at once"),
        ("runs_per_query", runs_per_query, "how many probes each query gets"),
    ):
        if isinstance(value, bool):
            problems.append(
                f"{name} is a bool ({value!r}), which Python counts as "
                f"{int(value)}. Nothing that produced a boolean here meant {what}."
            )
        elif not isinstance(value, int):
            problems.append(
                f"{name} is a {type(value).__name__} ({value!r}), not an integer. "
                f"It counts {what}."
            )
        elif value < 1:
            problems.append(
                f"{name} is {value}, and {what} cannot be fewer than 1."
            )

    if not problems:
        return num_workers, runs_per_query

    raise ProbeArgumentError(
        "probe scheduling arguments are not counts this harness can run.\n"
        "Expected: --num-workers and --runs-per-query are both plain integers of\n"
        "  1 or more; a boolean is not a count. --num-workers 1 is the documented\n"
        "  way to read a run one probe at a time, so 1 is legitimate for either.\n"
        f"Found {len(problems)} problem(s):\n"
        + "\n".join(f"  - {p}" for p in problems)
    )


def check_probe_arguments(num_workers, runs_per_query) -> None:
    """Refuse unusable scheduling counts, or exit 1 with an actionable message.

    Called by each CLI *before* ``project_spend``, deliberately. The projection
    multiplies ``runs_per_query`` into the probe count, so ``--runs-per-query 0``
    prices the run at $0.00 and passes ``--max-cost`` and ``--confirm-threshold``
    without asking anything -- and in ``run_loop`` it also opens a browser tab
    and creates a results directory before the run that measures nothing starts.
    This is the last point where refusing costs the user nothing.

    Exit 1 is this family's code for input refused before spending, alongside
    ``load_eval_set`` and the missing-SKILL.md check. It does not cover every bad
    spelling of these two flags: ``--num-workers abc`` never arrives here at all,
    because argparse's own ``type=int`` rejects it first and exits **2** -- the
    code that otherwise means the spend gate refused, so a wrapper reading exit 2
    as "too expensive, or declined" misreads a typo. That collision is older than
    this check and is shared by every ``type=int`` and ``type=float`` argument in
    ``add_probe_arguments``; it is recorded here rather than repaired, because
    repairing it means changing how the whole parser reports a usage error.
    """
    try:
        validate_probe_arguments(num_workers, runs_per_query)
    except ProbeArgumentError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)


class PermissionModeError(ValueError):
    """A session would be launched able to act, and nobody asked for that."""


def validate_permission_mode(
    permission_mode: str | None,
    allow_host_permissions: bool = False,
) -> str:
    """Return the mode a session may be launched with, or refuse.

    ``None`` is "no opinion" and resolves to :data:`SAFE_PERMISSION_MODE`. That
    mapping is the whole security change and it lives here rather than in the
    argv builder, so a library caller -- ``run_loop``, a notebook, a wrapper
    script -- lands on the same posture as the CLI without having to know the
    flag exists. Reaching the host's permission settings now takes the word
    ``inherit`` and the opt-in together; neither on its own gets there, and
    silence never does.

    ``allow_host_permissions`` is the opt-in, and it gates every mode outside
    :data:`SAFE_PERMISSION_MODES` rather than ``inherit`` alone. ``acceptEdits``
    and ``bypassPermissions`` are named modes, not inheritance, and they hand a
    probe more than inheriting does on a machine whose settings are strict --
    so a gate that only watched ``inherit`` would be a gate around the least
    dangerous way through.

    It is compared against ``True`` rather than tested for truth, so a caller
    that read it out of an environment variable or a config file does not open
    the gate with the string ``"false"``. Every truthy non-``bool`` fails closed;
    argparse's ``store_true`` hands over a real ``bool``, so no CLI path is
    affected.
    """
    mode = SAFE_PERMISSION_MODE if permission_mode is None else str(permission_mode)
    if mode not in PERMISSION_MODES:
        raise PermissionModeError(
            f"{mode!r} is not a permission mode this harness knows.\n"
            f"Expected one of: {', '.join(PERMISSION_MODES)}."
        )
    if mode in SAFE_PERMISSION_MODES or allow_host_permissions is True:
        return mode
    # Wrapped here rather than stored pre-wrapped: the risk strings are one
    # sentence each and every consumer prints them into a differently indented
    # block. `Error: ` is seven characters, which is the hanging indent below.
    headline = textwrap.fill(
        f"--permission-mode {mode} {PERMISSION_MODE_RISK[mode]}.",
        width=79, initial_indent=" " * 7, subsequent_indent=" " * 7,
    )[7:]
    raise PermissionModeError(
        f"{headline}\n"
        f"       These sessions are driven by the skill's own text -- the SKILL.md\n"
        f"       body under test, and the eval set written against it -- which came\n"
        f"       from wherever the skill did, and they run on this machine under\n"
        f"       its credentials.\n"
        f"Fix:   drop the flag to run under --permission-mode {SAFE_PERMISSION_MODE}, "
        f"the default,\n"
        f"       which denies every call it was not pre-approved for; or pass\n"
        f"       --allow-host-permissions as well, to choose this mode deliberately."
    )


def check_permission_mode(
    permission_mode: str | None,
    allow_host_permissions: bool = False,
) -> str:
    """Refuse an unbounded session, or exit 1 with an actionable message.

    Called by each CLI *before* ``project_spend``, for the reason
    ``check_probe_arguments`` gives: this is the last point where refusing costs
    the user nothing. Raised from inside a probe instead, it arrives once per
    probe through ``run_single_query``'s blanket handler as ``status: "error"``
    -- indistinguishable from a rate limit -- and only after a bill has been
    approved.

    Exit 1, the family's code for input refused before spending.
    """
    try:
        mode = validate_permission_mode(permission_mode, allow_host_permissions)
    except PermissionModeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    if mode not in SAFE_PERMISSION_MODES:
        # The same sentence the refusal would have printed, because the run that
        # goes ahead is the one where knowing it matters. Naming the mode alone
        # would make the surviving message the less informative of the two.
        detail = textwrap.fill(
            f"--allow-host-permissions was given, so every session launched by this "
            f"run takes --permission-mode {mode}, which "
            f"{PERMISSION_MODE_RISK[mode]}.",
            width=79, initial_indent=" " * 9, subsequent_indent=" " * 9,
        )[9:]
        print(
            f"Warning: {detail}\n"
            f"         The SKILL.md body under test and the eval set written against\n"
            f"         it decide what those sessions try to do. Nothing further in\n"
            f"         this tool bounds them.",
            file=sys.stderr,
        )
    return mode


# --------------------------------------------------------------------------
# Eval driver
# --------------------------------------------------------------------------


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
    max_tools: int = 4,
    setting_sources: str | None = "project,local",
    include_partial_messages: bool = True,
    permission_mode: str | None = SAFE_PERMISSION_MODE,
    scaffold: str | None = None,
    verbose: bool = False,
    on_record=None,
    allow_host_permissions: bool = False,
) -> dict:
    """Run the full eval set and return results.

    Results are keyed by the eval item's **index**, not its query text, so two
    identical query strings stay two rows instead of silently pooling into one.
    """
    # Shape-check here too, not only in main(): a library caller (run_loop, a
    # notebook) otherwise reaches the same TypeError/KeyError the CLI now
    # refuses, and the missing-`should_trigger` case would not surface until
    # scoring, with every probe already paid for.
    eval_set = validate_eval_set(eval_set)
    # Same reasoning as the line above, for the same reason: a library caller
    # (run_loop, a notebook) never passes through main(), so the CLI's refusal
    # is not this function's refusal. Before the executor exists, because
    # `max_workers=0` raises out of ThreadPoolExecutor's constructor and a
    # raise from there arrives as a traceback rather than as a sentence.
    num_workers, runs_per_query = validate_probe_arguments(num_workers, runs_per_query)
    # And once here rather than once per probe. `run_single_query` resolves the
    # mode again for itself, but a refusal raised in there is caught by its
    # blanket handler and recorded as one errored probe among many; raised here
    # it stops the run before a session is bought.
    permission_mode = validate_permission_mode(permission_mode, allow_host_permissions)

    install_cleanup_handlers()
    # A new run is a new decision. Without this an interrupt that stopped an
    # earlier call would silently refuse every probe in this one -- which reads
    # as a 100%-errored harness rather than as the stop it was.
    _INTERRUPTED.clear()

    duplicates = len(eval_set) - len({item["query"] for item in eval_set})
    if duplicates:
        print(
            f"Warning: eval set contains {duplicates} duplicate query string(s); "
            f"they are scored as separate rows.",
            file=sys.stderr,
        )

    records_by_index: dict[int, list[dict]] = {i: [] for i in range(len(eval_set))}
    # A generator, never a list. Materializing every (query, run) pair up front
    # was cheap in itself; submitting all of them was not, and the two used to be
    # written as one comprehension feeding another. See `max_outstanding` below.
    queued_jobs = (
        (i, item, r) for i, item in enumerate(eval_set) for r in range(runs_per_query)
    )
    # Computed from the inputs rather than from len(jobs), so the `[n/total]`
    # denominator is the whole run even though the run is never wholly resident.
    total_jobs = len(eval_set) * runs_per_query
    completed = 0

    # The ceiling on jobs submitted-but-not-yet-collected, and the whole point of
    # the loop below.
    #
    # What scaled with the eval set was the *futures*, not the sessions. A probe
    # root and its `claude` subprocess are created inside `run_single_query` and
    # torn down in its `finally`, so concurrent sessions were capped at
    # `num_workers` before this loop existed exactly as they are after it --
    # measured, peak concurrent probes was 4 at `num_workers=4` under both the old
    # driver and this one. What submitting everything up front cost was a live
    # future and its job tuple per probe, held for the length of the run, and that
    # is small: 2,045 bytes a job, so 1.19 MiB for a 200-query set at 3 runs
    # against the ~660 MB its four sessions commit. Memory is the weakest reason
    # to bound this, and it is named here at its real size so nobody re-derives a
    # larger one.
    #
    # The queue depth also decided how much money a Ctrl-C could still spend, back
    # when one could. The pool's workers keep draining while `cleanup_owned` kills
    # the children it snapshotted, and each worker that frees up starts the next
    # queued job -- a fresh billed session, registered after the snapshot, so
    # neither killed nor cleaned. With the whole set queued that tail was bounded
    # only by how long cleanup took, and measured 9 sessions at 8 workers;
    # bounding the window cut it to OUTSTANDING_JOB_BUFFER, and `_INTERRUPTED`
    # then cut it to none, since the flag goes up before the shutdown and stops a
    # worker that has already dequeued its job -- which `cancel_futures` cannot
    # reach. The window is no longer what holds that line. It is why there was so
    # little left to hold by the time the flag was added.
    max_outstanding = num_workers + OUTSTANDING_JOB_BUFFER

    executor = ThreadPoolExecutor(max_workers=num_workers)
    try:
        outstanding: dict = {}

        def fill_window() -> None:
            """Top the window up, taking at most `max_outstanding` at a time."""
            while len(outstanding) < max_outstanding:
                try:
                    idx, item, run_idx = next(queued_jobs)
                except StopIteration:
                    return
                # `run_single_query` stays a bare module-global read at submit
                # time: the tests substitute the worker with
                # mock.patch.object(run_eval_mod, "run_single_query", ...), and
                # binding it any earlier would leave them green while quietly
                # launching real, billed sessions. Positional for the same
                # reason -- the in-tree fakes bind
                # (query, skill_name, skill_description, timeout, *args).
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    model,
                    max_tools,
                    setting_sources,
                    include_partial_messages,
                    permission_mode,
                    scaffold,
                    allow_host_permissions,
                )
                outstanding[future] = (idx, run_idx, item)

        fill_window()
        while outstanding:
            # FIRST_COMPLETED rather than waiting on a named future: a probe runs
            # up to --timeout, so blocking on the head of the queue would idle
            # every other worker behind the slowest one. Batches therefore arrive
            # in completion order, and the sort below orders each batch within
            # itself.
            done, _ = wait(outstanding, return_when=FIRST_COMPLETED)
            # `wait` hands back a *set*, and a batch holds more than one future
            # far more often than it sounds -- a worker keeps running while this
            # thread is refilling and printing, so even a single-worker run
            # collects two and three at a time. Draining the set directly
            # reported in set-iteration order, which follows id()-derived hashes
            # and so varies by platform and by build. That scrambled which query
            # each `[n/total]` line named: measured over 4 queries x 2 runs at
            # --num-workers 1, `as_completed` gave q0 q0 q1 q1 q2 q2 q3 q3 every
            # time and the bare set gave q0 q1 q0 q1 q3 q2 q2 q3. Single-worker
            # verbose is the mode run_loop points a reader at when a number looks
            # wrong, so its reading order is worth a sort. Submission order is
            # exactly (eval index, run index), because that is the order the
            # generator above yields them in; sorting on it restores the old
            # sequence identically at one worker, and is strictly more
            # deterministic than `as_completed` above one.
            # (Measured 2026-08-06, CPython 3.13.1, Windows 10 10.0.19045.)
            for future in sorted(done, key=lambda f: outstanding[f][:2]):
                idx, run_idx, item = outstanding.pop(future)
                try:
                    record = future.result()
                except Exception as exc:  # noqa: BLE001
                    record = {
                        "query": item["query"],
                        "probe_id": None,
                        "status": "error",
                        "triggered": None,
                        "stop_reason": "worker_exception",
                        "error": f"{type(exc).__name__}: {exc}",
                        "tools": [],
                        "elapsed_seconds": 0.0,
                        "cost_usd": None,
                    }
                record["run_index"] = run_idx
                record["eval_index"] = idx
                records_by_index[idx].append(record)
                completed += 1
                if on_record:
                    on_record(record)
                if verbose:
                    mark = {"trigger": "TRIG", "no_trigger": "no  ", "error": "ERR "}[record["status"]]
                    print(
                        f"[{completed}/{total_jobs}] {mark} exp={item['should_trigger']} "
                        f"({record['stop_reason']}, {record['elapsed_seconds']}s) "
                        f"{item['query'][:55]}",
                        file=sys.stderr,
                    )
                    if record["status"] == "error":
                        print(f"          error: {record['error']}", file=sys.stderr)
            # After the batch is fully accounted for, never from a done-callback:
            # `completed`, the records_by_index append and `on_record` are all
            # unguarded, and are safe only because this loop is the one thread
            # that touches them.
            fill_window()
    except BaseException:
        # Order matters. The flag goes up *before* the shutdown, because
        # cancel_futures only drains what is still queued: a worker that has
        # already dequeued its job is past that point and is stopped by the flag
        # instead. Reached by Ctrl-C because SIGINT is left to Python's own
        # handler; see install_cleanup_handlers.
        _INTERRUPTED.set()
        executor.shutdown(wait=False, cancel_futures=True)
        cleanup_owned()
        raise
    else:
        executor.shutdown(wait=True)

    # ---- Harness health, before any score is believed. --------------------
    all_records = [r for rs in records_by_index.values() for r in rs]
    checked = [r for r in all_records if r.get("clone_registered") is not None]
    unregistered = [r for r in checked if r["clone_registered"] is False]
    competing = sorted({s for r in all_records for s in (r.get("competing_skills") or [])})
    # Recomputed rather than threaded in from check_scaffold, because a library
    # caller (run_loop, a notebook) never passes through main().
    try:
        scaffold_excluded = validate_scaffold(scaffold)
    except ScaffoldError:
        # Every probe already errored on this; the records carry the reason.
        scaffold_excluded = []
    health: dict = {
        "probes_reporting_registration": len(checked),
        "probes_where_clone_was_not_registered": len(unregistered),
        "competing_installed_skills": competing,
        "scaffold_exclusions": [
            {"path": path, "reason": reason} for path, reason in scaffold_excluded
        ],
        "scaffold_disclosures": [
            {"path": path, "note": note} for path, note in scaffold_disclosures(scaffold)
        ],
    }
    if scaffold_excluded:
        names = ", ".join(path for path, _ in scaffold_excluded)
        print(
            f"WARNING: {len(scaffold_excluded)} path(s) in --scaffold were not copied "
            f"into any probe workspace ({names}). A query that named one of them could "
            f"not have resolved it, whatever the description said.",
            file=sys.stderr,
        )
    if unregistered:
        print(
            f"WARNING: in {len(unregistered)}/{len(checked)} probe(s) the command file "
            f"was not in the session's slash_commands list. Those probes could not have "
            f"triggered no matter what the description said.",
            file=sys.stderr,
        )
    if competing:
        print(
            f"WARNING: the probe session also sees {competing} in its skills list. An "
            f"installed copy of the skill under test shadows the probe: the model routes "
            f"to the real one, whose name never matches, and recall pins at 0%. "
            f"Shadow or uninstall it, or narrow --setting-sources.",
            file=sys.stderr,
        )

    results = []
    total_cost = 0.0
    have_cost = False
    for idx, item in enumerate(eval_set):
        records = records_by_index[idx]
        valid = [r for r in records if r["status"] in ("trigger", "no_trigger")]
        errored = [r for r in records if r["status"] == "error"]
        triggers = sum(1 for r in valid if r["triggered"])
        for r in records:
            # Mirror the read site in run_single_query, which accepts (int, float).
            # A bare `float` check silently drops an integer-valued cost from a
            # record this function did not produce, and if that were the only cost
            # present the summary would report None -- "nobody reported a cost" --
            # for a run that was billed. bool is excluded because it is an int
            # subclass and a boolean cost is meaningless.
            cost = r.get("cost_usd")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                total_cost += float(cost)
                have_cost = True

        should_trigger = item["should_trigger"]
        if valid:
            trigger_rate = triggers / len(valid)
            did_pass = (
                trigger_rate >= trigger_threshold
                if should_trigger
                else trigger_rate < trigger_threshold
            )
            status = "scored"
        else:
            # Absent data is absent, never zero. No verdict at all.
            trigger_rate = None
            did_pass = None
            status = "errored"

        results.append({
            "index": idx,
            "query": item["query"],
            "id": item.get("id"),
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": triggers,
            "runs": len(valid),
            "errored": len(errored),
            "errors": [r["error"] for r in errored if r.get("error")][:3],
            "pass": did_pass,
            "status": status,
        })

    passed = sum(1 for r in results if r["pass"] is True)
    failed = sum(1 for r in results if r["pass"] is False)
    errored_queries = sum(1 for r in results if r["pass"] is None)
    errored_runs = sum(r["errored"] for r in results)
    scored_runs = sum(r["runs"] for r in results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "errored": errored_queries,
            "scored_runs": scored_runs,
            "errored_runs": errored_runs,
            "actual_cost_usd": round(total_cost, 4) if have_cost else None,
        },
        "harness_health": health,
    }


def print_eval_stats(label: str, results: list[dict], elapsed: float | None = None) -> None:
    """Human-readable confusion-matrix summary, on stderr."""
    pos = [r for r in results if r["should_trigger"]]
    neg = [r for r in results if not r["should_trigger"]]
    tp = sum(r["triggers"] for r in pos)
    pos_runs = sum(r["runs"] for r in pos)
    fn = pos_runs - tp
    fp = sum(r["triggers"] for r in neg)
    neg_runs = sum(r["runs"] for r in neg)
    tn = neg_runs - fp
    total = tp + tn + fp + fn
    errored_runs = sum(r["errored"] for r in results)

    def pct(num, den):
        return f"{num / den:.0%}" if den else "--"

    tail = f" ({elapsed:.1f}s)" if elapsed is not None else ""
    print(
        f"{label}: {tp + tn}/{total} correct runs, "
        f"precision={pct(tp, tp + fp)} recall={pct(tp, tp + fn)} "
        f"accuracy={pct(tp + tn, total)}{tail}",
        file=sys.stderr,
    )
    if errored_runs:
        print(
            f"{label}: {errored_runs} ERRORED run(s) excluded from every number above.",
            file=sys.stderr,
        )
    for r in results:
        if r["pass"] is None:
            status, rate_str = "ERR ", f"0/0 +{r['errored']} err"
        else:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            if r["errored"]:
                rate_str += f" +{r['errored']} err"
        print(
            f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:60]}",
            file=sys.stderr,
        )


def check_skill_md_encoding(skill_path: Path) -> None:
    """Refuse to spend money measuring a SKILL.md the parser decoded wrongly.

    ``scripts/utils.parse_skill_md`` reads SKILL.md with the locale codec. On a
    cp1252 Windows console that decodes almost any byte *without raising* and
    returns mojibake: every em dash in this repo's own SKILL.md comes back as
    'a-euro-"'. That corrupted string is what would be written into the probe's
    command file and what would be handed to the optimizer as the skill body, so
    the measurement would be of a description the author never wrote.

    This check is a no-op once utils.py passes encoding="utf-8",
    or under PYTHONUTF8=1.
    """
    md = skill_path / "SKILL.md"
    try:
        raw = md.read_bytes()
    except OSError:
        return
    try:
        truth = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        print(f"Error: {md} is not valid UTF-8: {exc}", file=sys.stderr)
        raise SystemExit(1)
    try:
        _n, _d, content = parse_skill_md(skill_path)
    except (UnicodeDecodeError, UnicodeError) as exc:
        print(
            f"Error: could not read {md} with this interpreter's default encoding "
            f"({exc}).\nFix: pass encoding=\"utf-8\" in scripts/utils.py parse_skill_md, "
            f"or re-run with PYTHONUTF8=1 set.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001 - a bad SKILL.md must not traceback
        print(f"Error: could not parse {md}: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
    if content.lstrip("﻿") != truth.lstrip("﻿"):
        print(
            f"Error: {md} is UTF-8 but scripts/utils.parse_skill_md decoded it with the\n"
            f"       platform codec, silently corrupting {sum(1 for a, b in zip(content, truth) if a != b)}+ characters.\n"
            f"       Measuring this would score a description the author never wrote.\n"
            f"Fix:   scripts/utils.parse_skill_md must decode UTF-8 explicitly rather\n"
            f"       than through the locale codec. As a stopgap, re-run\n"
            f"       with PYTHONUTF8=1 set.",
            file=sys.stderr,
        )
        raise SystemExit(1)


def load_json_file(path: Path, what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Error: {what} not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    except UnicodeDecodeError as exc:
        print(f"Error: {what} at {path} is not valid UTF-8: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: {what} at {path} is not valid JSON: {exc}", file=sys.stderr)
        raise SystemExit(1)


def add_probe_arguments(parser: argparse.ArgumentParser) -> None:
    """Arguments shared by run_eval and run_loop, so the two cannot drift."""
    parser.add_argument("--num-workers", type=int, default=4,
                        help="Parallel probes. Each is a full Claude Code session "
                             "(~165 MB); the old default of 10 was ~2 GB. Must be 1 "
                             "or more. (default: 4)")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Seconds per probe. Observed sessions ran 67.5s and 83.1s, "
                             "and a timeout is an error, not a non-trigger. (default: 120)")
    parser.add_argument("--runs-per-query", type=int, default=3,
                        help="Probes per query. Must be 1 or more. (default: 3)")
    parser.add_argument("--trigger-threshold", type=float, default=0.5,
                        help="Trigger rate at or above which a positive passes (default: 0.5)")
    parser.add_argument("--max-tools", type=int, default=4,
                        help="Give up on a probe after this many tool calls without a "
                             "match. 0 disables. (default: 4)")
    parser.add_argument("--setting-sources", default="project,local",
                        help="Passed to claude -p. The default drops your personal skills "
                             "and plugins so an installed copy of the skill under test "
                             "cannot shadow the probe. Empty string to inherit everything.")
    parser.add_argument("--permission-mode", default=SAFE_PERMISSION_MODE,
                        choices=PERMISSION_MODES,
                        help=f"Passed to claude -p. This is the blast-radius knob: every "
                             f"session this harness launches is driven by an eval set and a "
                             f"SKILL.md that came from wherever the skill did, and runs here. "
                             f"'{SAFE_PERMISSION_MODE}' is the default because it auto-denies "
                             f"any call it was not pre-approved for and never waits for an "
                             f"answer nobody is there to give. "
                             f"'{INHERIT_PERMISSION_MODE}' passes no flag at all and takes "
                             f"your permission settings. Any mode outside "
                             f"{', '.join(sorted(SAFE_PERMISSION_MODES))} needs the "
                             f"--allow-host-permissions opt-in as well; 'plan' is one of "
                             f"them, and is looser than it sounds. A mode changes model "
                             f"behaviour, so a run is comparable only with runs made under "
                             f"the same one.")
    parser.add_argument("--allow-host-permissions", action="store_true",
                        help=f"Permit a --permission-mode outside "
                             f"{', '.join(sorted(SAFE_PERMISSION_MODES))}, including "
                             f"'{INHERIT_PERMISSION_MODE}'. Without this, a mode that lets a "
                             f"session act on this machine is refused before anything is "
                             f"spent. Pass it deliberately.")
    parser.add_argument("--scaffold", default=None,
                        help="Directory copied into each probe root so file paths named in "
                             "queries resolve. Whatever is copied must be a real file or "
                             "directory: a symlink, junction or other reparse point is "
                             "refused rather than followed, because copying one would put "
                             "content from outside the tree in the probe's working "
                             "directory. Version control, dependency trees, credential "
                             "stores, dotenv files and .claude/ directories are left out "
                             "instead of refused, and every path left out is listed before "
                             "the run starts -- read that list, because a query naming one "
                             "of them cannot resolve it and scores as a non-trigger. Files "
                             "that are copied but carry a hard link or a credential-shaped "
                             "string are named in the same place rather than withheld. "
                             "Default: empty root.")
    parser.add_argument("--no-partial-messages", action="store_true",
                        help="Disable --include-partial-messages early detection. Detection "
                             "still works off the authoritative assistant events, so this "
                             "only costs latency -- it is the escape hatch for a CLI build "
                             "whose partial stream is malformed.")
    parser.add_argument("--max-cost", type=float, default=10.0,
                        help="Refuse to start if the projected spend exceeds this (default: 10.0)")
    parser.add_argument("--confirm-threshold", type=float, default=1.0,
                        help="Require confirmation above this projected spend (default: 1.0)")
    parser.add_argument("--cost-per-probe", type=float, default=None,
                        help="Override the per-probe cost estimate used for the projection.")
    parser.add_argument("--max-error-rate", type=float, default=0.2,
                        help="Exit non-zero if this fraction of probes errored (default: 0.2)")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the spend confirmation prompt.")


def main():
    configure_console()
    parser = argparse.ArgumentParser(
        description="Run trigger evaluation for a skill description",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--description-file", default=None,
                        help="Read the description under test from this UTF-8 file")
    parser.add_argument("--model", default=None,
                        help="Model for claude -p (default: user's configured model)")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    add_probe_arguments(parser)
    args = parser.parse_args()

    check_probe_arguments(args.num_workers, args.runs_per_query)
    permission_mode = check_permission_mode(
        args.permission_mode, args.allow_host_permissions
    )

    eval_set = load_eval_set(Path(args.eval_set))
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    check_skill_md_encoding(skill_path)
    name, original_description, _content = parse_skill_md(skill_path)
    if args.description_file:
        description = Path(args.description_file).read_text(encoding="utf-8").strip()
    else:
        description = args.description or original_description

    print(f"Evaluating: {description}", file=sys.stderr)

    check_scaffold(args.scaffold)

    project_spend(
        n_queries=len(eval_set),
        runs_per_query=args.runs_per_query,
        iterations=1,
        model=args.model,
        cost_per_probe=args.cost_per_probe,
        max_cost=args.max_cost,
        confirm_threshold=args.confirm_threshold,
        assume_yes=args.yes,
        permission_mode=permission_mode,
    )

    try:
        output = run_eval(
            eval_set=eval_set,
            skill_name=name,
            description=description,
            num_workers=args.num_workers,
            timeout=args.timeout,
            runs_per_query=args.runs_per_query,
            trigger_threshold=args.trigger_threshold,
            model=args.model,
            max_tools=args.max_tools,
            setting_sources=args.setting_sources or None,
            include_partial_messages=not args.no_partial_messages,
            permission_mode=permission_mode,
            scaffold=args.scaffold,
            verbose=args.verbose,
            allow_host_permissions=args.allow_host_permissions,
        )
    except KeyboardInterrupt:
        # run_eval has already cancelled the queue, stopped the workers from
        # launching anything else and killed the children it owned. A partial
        # run is not a measurement, so nothing is written to stdout. 130 is the
        # conventional Ctrl-C status; a traceback here would say the same thing
        # less usefully.
        print(
            "\nInterrupted: the queued probes were cancelled and no further "
            "session was started.",
            file=sys.stderr,
        )
        sys.exit(130)

    summary = output["summary"]
    print_eval_stats("Results", output["results"])
    if summary["actual_cost_usd"] is not None:
        print(f"Actual reported cost: ${summary['actual_cost_usd']:.4f}", file=sys.stderr)

    # JSON on stdout alone, so machine consumers are never corrupted by chatter.
    print(json.dumps(output, indent=2))

    total_runs = summary["scored_runs"] + summary["errored_runs"]
    error_rate = summary["errored_runs"] / total_runs if total_runs else 1.0
    if error_rate > args.max_error_rate:
        print(
            f"\nERROR: {summary['errored_runs']}/{total_runs} probes errored "
            f"({error_rate:.0%} > --max-error-rate {args.max_error_rate:.0%}). "
            f"These results do not measure the description.",
            file=sys.stderr,
        )
        sys.exit(3)


if __name__ == "__main__":
    main()
