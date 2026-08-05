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
"""

import argparse
import atexit
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.utils import configure_console, parse_skill_md

# Tools whose input may legitimately name the clone. Read is included because a
# model that opens the command file has demonstrably routed to it.
TRIGGER_TOOLS = ("Skill", "SlashCommand", "Read")

PROBE_ROOT_PREFIX = "better-skill-creator-probe-"

# Rough per-probe cost, USD, used only for the pre-flight projection.
# Sources: opus measured at $0.4267 and $0.3978 over 16-17 turns
# (research/02-trigger-eval.md F15); haiku measured at $0.0125 warm / $0.0579
# cold in an empty project (research/05-cost-safety-resource.md F2); sonnet
# measured while validating this rewrite — 6 full sessions against a small
# repo scaffold reported $0.505 total, i.e. ~$0.084 each. A probe that triggers
# early is killed before its `result` event and costs less, so these numbers are
# an upper bound per probe. Estimates for a warning, not an invoice — override
# with --cost-per-probe.
COST_PER_PROBE_USD = {
    "opus": 0.41,
    "sonnet": 0.09,
    "haiku": 0.02,
}
DEFAULT_COST_PER_PROBE_USD = 0.20

_TERMINAL = object()

# --------------------------------------------------------------------------
# Blast-radius control: probe roots and child processes this process created.
# --------------------------------------------------------------------------

_OWNED_ROOTS: set[str] = set()
_LIVE_PROCS: set[subprocess.Popen] = set()
_OWNED_LOCK = threading.Lock()
_CLEANUP_INSTALLED = False


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
    ok = _rmtree_retry(path)
    with _OWNED_LOCK:
        _OWNED_ROOTS.discard(str(path))
    if not ok:
        print(f"Warning: could not remove probe root {path}", file=sys.stderr)


def _register_proc(proc: subprocess.Popen) -> None:
    with _OWNED_LOCK:
        _LIVE_PROCS.add(proc)


def _release_proc(proc: subprocess.Popen) -> None:
    with _OWNED_LOCK:
        _LIVE_PROCS.discard(proc)


def cleanup_owned() -> None:
    """Kill our children and remove the probe roots *this process* created.

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
    for root in roots:
        _rmtree_retry(Path(root))
    with _OWNED_LOCK:
        _OWNED_ROOTS.difference_update(roots)
        _LIVE_PROCS.difference_update(procs)


def install_cleanup_handlers() -> None:
    """Register cleanup on normal exit and on the signals we can catch.

    atexit alone does not survive SIGTERM/Ctrl-C, and neither survives SIGKILL /
    Stop-Process -Force. Nothing in-process can; the mitigation for that case is
    that the only thing stranded is an empty directory under the OS temp dir,
    never a file inside the user's project or home.
    """
    global _CLEANUP_INSTALLED
    if _CLEANUP_INSTALLED:
        return
    _CLEANUP_INSTALLED = True
    atexit.register(cleanup_owned)

    def _handler(signum, _frame):
        cleanup_owned()
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    for name in ("SIGINT", "SIGTERM", "SIGBREAK", "SIGHUP"):
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


def _make_probe_root(scaffold: str | None) -> Path:
    root = Path(tempfile.mkdtemp(prefix=PROBE_ROOT_PREFIX))
    _register_root(root)
    if scaffold:
        src = Path(scaffold)
        for child in src.iterdir():
            if child.name == ".claude":
                continue
            dest = root / child.name
            if child.is_dir():
                shutil.copytree(child, dest)
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
    permission_mode: str | None = None,
    scaffold: str | None = None,
) -> dict:
    """Run one probe and return a record.

    The record's ``status`` is one of:
      ``trigger``     — the model reached for this probe's clone
      ``no_trigger``  — the session reached a terminal verdict without doing so
      ``error``       — anything else. Never scored.

    ``status == "error"`` covers timeouts, non-zero child exits, a stream that
    ends without a ``result`` event, and any exception raised while setting the
    probe up. None of those are observations about the description.
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
        if permission_mode:
            cmd.extend(["--permission-mode", permission_mode])
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
) -> dict:
    """Print the projected spend and gate the run. Returns the projection.

    Raises SystemExit when the projection exceeds --max-cost, or when it exceeds
    --confirm-threshold and no confirmation is available.
    """
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
        "  running with cwd in a throwaway temp directory. Probes inherit your",
        "  permission settings; pass --permission-mode plan to bound what they",
        "  can do at the cost of comparability with prior measurements.",
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
    permission_mode: str | None = None,
    scaffold: str | None = None,
    verbose: bool = False,
    on_record=None,
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

    install_cleanup_handlers()

    duplicates = len(eval_set) - len({item["query"] for item in eval_set})
    if duplicates:
        print(
            f"Warning: eval set contains {duplicates} duplicate query string(s); "
            f"they are scored as separate rows.",
            file=sys.stderr,
        )

    records_by_index: dict[int, list[dict]] = {i: [] for i in range(len(eval_set))}
    jobs = [(i, item, r) for i, item in enumerate(eval_set) for r in range(runs_per_query)]
    total_jobs = len(jobs)
    completed = 0

    executor = ThreadPoolExecutor(max_workers=max(1, num_workers))
    try:
        future_to_job = {
            executor.submit(
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
            ): (idx, item, run_idx)
            for idx, item, run_idx in jobs
        }
        for future in as_completed(future_to_job):
            idx, item, run_idx = future_to_job[future]
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
    except BaseException:
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
    health: dict = {
        "probes_reporting_registration": len(checked),
        "probes_where_clone_was_not_registered": len(unregistered),
        "competing_installed_skills": competing,
    }
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
            if isinstance(r.get("cost_usd"), float):
                total_cost += r["cost_usd"]
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
                             "(~165 MB); the old default of 10 was ~2 GB. (default: 4)")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Seconds per probe. Observed sessions ran 67.5s and 83.1s, "
                             "and a timeout is an error, not a non-trigger. (default: 120)")
    parser.add_argument("--runs-per-query", type=int, default=3,
                        help="Probes per query (default: 3)")
    parser.add_argument("--trigger-threshold", type=float, default=0.5,
                        help="Trigger rate at or above which a positive passes (default: 0.5)")
    parser.add_argument("--max-tools", type=int, default=4,
                        help="Give up on a probe after this many tool calls without a "
                             "match. 0 disables. (default: 4)")
    parser.add_argument("--setting-sources", default="project,local",
                        help="Passed to claude -p. The default drops your personal skills "
                             "and plugins so an installed copy of the skill under test "
                             "cannot shadow the probe. Empty string to inherit everything.")
    parser.add_argument("--permission-mode", default=None,
                        help="Passed to claude -p (e.g. 'plan'). This is the blast-radius "
                             "knob the spend projection points at: probes otherwise inherit "
                             "your permission settings and can act. Unset by default because "
                             "it changes model behaviour and so breaks comparability with "
                             "prior measurements.")
    parser.add_argument("--scaffold", default=None,
                        help="Directory copied into each probe root (minus its .claude/) so "
                             "file paths named in queries resolve. Default: empty root.")
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

    project_spend(
        n_queries=len(eval_set),
        runs_per_query=args.runs_per_query,
        iterations=1,
        model=args.model,
        cost_per_probe=args.cost_per_probe,
        max_cost=args.max_cost,
        confirm_threshold=args.confirm_threshold,
        assume_yes=args.yes,
    )

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
        permission_mode=args.permission_mode,
        scaffold=args.scaffold,
        verbose=args.verbose,
    )

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
