#!/usr/bin/env python3
"""A stand-in for the `claude` CLI, so the trigger-eval tests cost nothing.

`scripts/run_eval.py` and `scripts/improve_description.py` both launch whatever
`BETTER_SKILL_CREATOR_CLAUDE_ARGV` names, so the tests point that at
`[sys.executable, <this file>]` and drive it with a JSON control file named by
`STUB_CLAUDE_CONTROL`.

This stub serves **two** callers, told apart by the argv the caller builds:

* `--output-format stream-json`  -> the *probe* path (`run_eval.run_single_query`)
* `--output-format text`         -> the *optimizer* path
  (`improve_description._call_claude`), which writes its prompt to stdin and
  reads a plain-text answer back.

One control file can therefore drive a whole `run_loop` run: the probe keys and
the `optimizer_*` keys do not collide.

Probe control keys (all optional):
  mode                 "replay" (default) | "silent" | "empty"
  stream               path to a .jsonl capture to replay
  rename               replace `<name>-skill-<hex8>` in the capture with the
                       probe's own clone name (default: true)
  prepend_foreign_tool emit a Bash tool_use before the capture, to reproduce
                       "the model oriented before reaching for the skill"
  drop_result          replay everything except the terminal `result` event
  delay_before         seconds to sleep before writing anything
  exit_code            process exit code (default 0)
  stderr               text written to stderr before exiting

Optimizer control keys (all optional):
  optimizer_response   the text to write to stdout
  optimizer_responses  a list, consumed one per call; the last entry repeats.
                       This is how the 1024-character rewrite net is driven:
                       an over-long first answer, a short second one.
  optimizer_exit_code  process exit code (default 0)
  optimizer_stderr     text written to stderr before exiting
  optimizer_delay      seconds to sleep before answering

Because each call is a fresh process, the per-call index lives in a sidecar
file next to the control file. Env `STUB_CLAUDE_PROMPT_LOG` names a JSONL file
that every optimizer call appends its argv and its received prompt to, so a
test can assert on **what the optimizer was actually shown** rather than on how
the prompt was assembled.

The stub discovers the probe's clone name by looking in
`<cwd>/.claude/commands/*.md`, which is exactly where run_eval writes it.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# The real CLI speaks UTF-8. A piped Python child defaults to the locale codec
# (cp1252 on the reference machine), which would make this stub a *weaker*
# environment than production and hide exactly the encoding defects the suite
# exists to catch.
for _stream in (sys.stdin, sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

CLONE_RE = re.compile(r"[a-z0-9-]+-skill-[0-9a-f]{8}")

DEFAULT_OPTIMIZER_RESPONSE = (
    "<new_description>Use this skill when a widget manifest needs authoring or "
    "auditing.</new_description>"
)


def probe_clone_name() -> str | None:
    commands = Path.cwd() / ".claude" / "commands"
    if not commands.is_dir():
        return None
    for md in sorted(commands.glob("*.md")):
        return md.stem
    return None


def emit(obj) -> None:
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _next_call_index(control_path: str | None) -> int:
    """Per-call counter, kept on disk because every call is a new process."""
    if not control_path:
        return 0
    counter = Path(control_path + ".calls")
    try:
        index = int(counter.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        index = 0
    try:
        counter.write_text(str(index + 1), encoding="utf-8")
    except OSError:
        pass
    return index


def optimizer_mode(control: dict, control_path: str | None) -> int:
    """Serve `claude -p --output-format text`: prompt on stdin, text on stdout."""
    prompt = sys.stdin.read()
    index = _next_call_index(control_path)

    log = os.environ.get("STUB_CLAUDE_PROMPT_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps({"call": index, "argv": sys.argv[1:], "prompt": prompt}) + "\n"
            )

    delay = control.get("optimizer_delay", 0)
    if delay:
        time.sleep(delay)

    responses = control.get("optimizer_responses")
    if responses is None:
        responses = [control.get("optimizer_response", DEFAULT_OPTIMIZER_RESPONSE)]
    text = responses[min(index, len(responses) - 1)]

    if control.get("optimizer_stderr"):
        sys.stderr.write(control["optimizer_stderr"])
    sys.stdout.write(text)
    sys.stdout.flush()
    return control.get("optimizer_exit_code", 0)


def main() -> int:
    control_path = os.environ.get("STUB_CLAUDE_CONTROL")
    control = json.loads(Path(control_path).read_text(encoding="utf-8")) if control_path else {}

    argv = sys.argv[1:]
    if "text" in argv and "--output-format" in argv:
        if argv[argv.index("--output-format") + 1 : argv.index("--output-format") + 2] == ["text"]:
            return optimizer_mode(control, control_path)

    delay = control.get("delay_before", 0)
    if delay:
        time.sleep(delay)

    report = os.environ.get("STUB_CLAUDE_REPORT")
    if report:
        commands = Path.cwd() / ".claude" / "commands"
        Path(report).write_text(
            json.dumps({
                "cwd": str(Path.cwd()),
                "argv": sys.argv[1:],
                "command_files": sorted(p.name for p in commands.glob("*.md"))
                if commands.is_dir() else [],
                "command_file_text": "\n---FILE---\n".join(
                    p.read_text(encoding="utf-8") for p in sorted(commands.glob("*.md"))
                ) if commands.is_dir() else "",
                "root_entries": sorted(p.name for p in Path.cwd().iterdir()),
                "has_claudecode_env": "CLAUDECODE" in os.environ,
            }, indent=2),
            encoding="utf-8",
        )

    mode = control.get("mode", "replay")
    if mode == "silent":
        # Produce nothing and never exit until killed: the timeout path.
        time.sleep(control.get("hang_seconds", 3600))
        return 0
    if mode == "empty":
        if control.get("stderr"):
            sys.stderr.write(control["stderr"])
        return control.get("exit_code", 0)

    clone = probe_clone_name()

    if control.get("prepend_foreign_tool"):
        emit({
            "type": "stream_event",
            "event": {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "tool_use", "id": "toolu_stub", "name": "Bash", "input": {}},
            },
        })
        emit({
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": '{"command": "ls -la"}'},
            },
        })
        emit({"type": "stream_event", "event": {"type": "content_block_stop", "index": 0}})
        emit({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls -la"}}]},
        })

    stream = control.get("stream")
    if stream:
        rename = control.get("rename", True)
        for raw in Path(stream).read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            if control.get("drop_result"):
                try:
                    if json.loads(raw).get("type") == "result":
                        continue
                except json.JSONDecodeError:
                    pass
            if rename and clone:
                raw = CLONE_RE.sub(clone, raw)
            sys.stdout.write(raw + "\n")
            sys.stdout.flush()
            if control.get("per_line_delay"):
                time.sleep(control["per_line_delay"])

    if control.get("stderr"):
        sys.stderr.write(control["stderr"])
    return control.get("exit_code", 0)


if __name__ == "__main__":
    sys.exit(main())
