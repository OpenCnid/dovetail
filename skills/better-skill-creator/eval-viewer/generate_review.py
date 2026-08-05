#!/usr/bin/env python3
"""Generate and serve a review page for eval results.

Reads the workspace directory, discovers runs (directories with outputs/),
embeds all output data into a self-contained HTML page, and serves it via
a tiny HTTP server. Feedback auto-saves to feedback.json in the workspace.

Canonical workspace layout:

    <skill>-workspace/
      iteration-<N>/
        benchmark.json
        feedback.json
        eval-<ID>-<slug>/
          eval_metadata.json
          <config>/              with_skill | without_skill | old_skill
            run-<K>/             ALWAYS present, even for a single run
              outputs/
              grading.json
              timing.json

The legacy flat layout (no run-<K> level) is still read, but it is normalized
to run-1 and a deprecation warning naming the offending path is printed to
stderr. Nothing is silently tolerated.

grading.json is embedded verbatim; this script does not interpret verdicts.
One exception, and it is a disclosure rather than an interpretation: an
expectation carrying the retired boolean `passed` and no `verdict` is the
PREVIOUS grading contract, and that is reported to stderr as well as on
the page. It is not translated here, because `false` under that contract meant
either "verified false" or "the judge could not tell" and the file does not say
which -- inventing the distinction is exactly what the contract change removed.


Usage:
    python generate_review.py <workspace-path> [--port PORT] [--skill-name NAME]
    python generate_review.py <workspace-path> --previous-workspace /path/to/old/workspace
    python generate_review.py <workspace-path> --static /path/to/out.html

`--benchmark` defaults to <workspace-path>/benchmark.json when that file
exists, which is exactly where aggregate_benchmark.py writes it.

No dependencies beyond the Python stdlib are required.
"""

import argparse
import base64
import json
import mimetypes
import re
import sys
import threading
import urllib.parse
import webbrowser
from functools import partial
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ---------------------------------------------------------------------------
# Console + encoding
# ---------------------------------------------------------------------------

# This file lives at <skill-root>/eval-viewer/, outside the scripts package,
# so the shared helper is not importable without help. Prefer the shared one
# (single definition of the behaviour) and fall back to an equivalent local
# implementation if the layout ever changes.
try:  # pragma: no cover - import shim
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.utils import configure_console  # type: ignore
except Exception:  # pragma: no cover - import shim
    def configure_console() -> None:
        """Make stdout/stderr safe for non-ASCII output on every platform."""
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError, OSError):
                pass


# The run-directory pattern is a contract between readers, not a local
# convenience, and it
# is imported from the one module that owns it rather than re-typed here. This
# file used to carry its own `^run-(.+)$`, which is looser than the scripts'
# `^run-(\d+)$`: a `run-final/` directory was a first-class run to the viewer,
# was excluded by the aggregator, and the two artifacts then disagreed about
# what had been measured -- with the benchmark quietly relabelling whichever
# configuration survived as the primary. Two regexes for one contract is a
# drift surface by construction.
try:  # pragma: no cover - import shim
    from scripts.validate_grading import RUN_DIR_RE  # type: ignore
except Exception:  # pragma: no cover - import shim
    RUN_DIR_RE = re.compile(r"^run-(\d+)$")


# Every read and write in this file is UTF-8. A file that is genuinely not
# UTF-8 raises UnicodeDecodeError, which is a ValueError sibling of
# json.JSONDecodeError and is therefore NOT caught by (JSONDecodeError, OSError).
# Every handler below names UnicodeError explicitly, and none of them swallows
# the failure silently.


def warn(message: str) -> None:
    """Print a warning to stderr. Never silent, never on stdout."""
    print(f"Warning: {message}", file=sys.stderr)


def load_json_file(path: Path, what: str) -> dict | None:
    """Read a JSON file as UTF-8. Returns None and warns on any failure."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeError as e:
        warn(f"{what} at {path} is not valid UTF-8 ({e}); ignoring it.")
        return None
    except json.JSONDecodeError as e:
        warn(f"{what} at {path} is not valid JSON ({e}); ignoring it.")
        return None
    except OSError as e:
        warn(f"{what} at {path} could not be read ({e}); ignoring it.")
        return None
    if not isinstance(data, dict):
        warn(f"{what} at {path} is not a JSON object; ignoring it.")
        return None
    return data


# Files to exclude from output listings
METADATA_FILES = {"transcript.md", "user_notes.md", "metrics.json"}

# Extensions we render as inline text
TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".yaml", ".yml", ".xml", ".html", ".css", ".sh", ".rb", ".go", ".rs",
    ".java", ".c", ".cpp", ".h", ".hpp", ".sql", ".r", ".toml",
}

# Extensions we render as inline images
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

# MIME type overrides for common types
MIME_OVERRIDES = {
    ".svg": "image/svg+xml",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

# Loopback names the server will answer for. Anything else is a rebinding attempt.
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Upper bound on a feedback POST. The page sends a few kilobytes of notes: one
# entry per run, each a paragraph a human typed. 1 MiB is three orders of
# magnitude of headroom over that. The previous 8 MiB ceiling was reached in
# testing -- an 8 MB body was accepted, written verbatim, and the resulting
# feedback.json was then embedded into the next iteration's page, which came
# out at 8.08 MB.
MAX_REQUEST_BYTES = 1024 * 1024

# How long a single request may hold a connection before the server drops it.
# Without this a client that opens a socket, sends half a request line and
# stops wedges the viewer forever (BaseHTTPRequestHandler.timeout is None by
# default, so rfile.readline() blocks with no deadline).
REQUEST_TIMEOUT_SECONDS = 15


def get_mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in MIME_OVERRIDES:
        return MIME_OVERRIDES[ext]
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def find_runs(workspace: Path) -> list[dict]:
    """Recursively find directories that contain an outputs/ subdirectory."""
    runs: list[dict] = []
    _find_runs_recursive(workspace, workspace, runs)
    # eval_id is None whenever no eval_metadata.json was found. `.get(key,
    # default)` returns the stored None rather than the default, so a workspace
    # mixing identified and unidentified evals used to raise TypeError here.
    runs.sort(key=lambda r: (
        r["eval_id"] if isinstance(r["eval_id"], int) else float("inf"),
        str(r["eval_id"]) if r["eval_id"] is not None else "",
        r["id"],
    ))
    _warn_about_layout(runs)
    return runs


def _warn_about_layout(runs: list[dict]) -> None:
    """Emit one visible warning per non-canonical run, at the shared severity."""
    legacy = [r for r in runs if r["layout"] == "legacy-flat"]
    if legacy:
        warn(
            f"{len(legacy)} run(s) use the legacy flat layout with no run-<K> directory. "
            "They have been read as run-1. The canonical layout is "
            "<eval-dir>/<config>/run-<K>/outputs/ — see the module docstring. "
            "Affected: " + ", ".join(r["id"] for r in legacy[:5])
            + (" ..." if len(legacy) > 5 else "")
        )

    # A `run-<not-an-integer>` directory is the condition that made the viewer
    # and the benchmark describe different data. The aggregator excludes it by
    # name; the viewer must say the same thing about the same directory rather
    # than showing it as an ordinary run.
    malformed = [r for r in runs if r["layout"] == "malformed-run"]
    if malformed:
        warn(
            f"{len(malformed)} run director(ies) are named `run-<something>` where "
            "<something> is not an integer. aggregate_benchmark.py EXCLUDES these, so "
            "they appear on this page and in no benchmark number. Rename them to "
            "run-1, run-2, ... Affected: "
            + ", ".join(r["id"] for r in malformed[:5])
            + (" ..." if len(malformed) > 5 else "")
        )


def _find_runs_recursive(root: Path, current: Path, runs: list[dict]) -> None:
    if not current.is_dir():
        return

    outputs_dir = current / "outputs"
    if outputs_dir.is_dir():
        run = build_run(root, current)
        if run:
            runs.append(run)
        return

    skip = {"node_modules", ".git", "__pycache__", "skill", "inputs"}
    try:
        children = sorted(current.iterdir())
    except OSError as e:
        warn(f"could not list {current} ({e}); skipping it.")
        return
    for child in children:
        if child.is_dir() and child.name not in skip:
            _find_runs_recursive(root, child, runs)


def find_run_ids(workspace: Path) -> set[str]:
    """Return just the run ids under `workspace`, without reading any file.

    build_run() base64-encodes every output file, so it is far too expensive to
    call on the write path. This walk answers the only question the feedback
    endpoint needs to ask: does this run_id name a run that actually exists?
    """
    ids: set[str] = set()

    def walk(current: Path) -> None:
        if not current.is_dir():
            return
        if (current / "outputs").is_dir():
            ids.add(str(current.relative_to(workspace)).replace("/", "-").replace("\\", "-"))
            return
        try:
            children = sorted(current.iterdir())
        except OSError:
            return
        skip = {"node_modules", ".git", "__pycache__", "skill", "inputs"}
        for child in children:
            if child.is_dir() and child.name not in skip:
                walk(child)

    walk(workspace)
    return ids


def _search_upwards(run_dir: Path, root: Path, filename: str) -> Path | None:
    """Find `filename` at run_dir or any ancestor up to and including root.

    The canonical layout puts eval_metadata.json at the eval-dir level, which
    is two levels above <config>/run-<K>/. Checking only run_dir and its
    parent is what made every prompt read "(No prompt found)".
    """
    for directory in [run_dir, *run_dir.parents]:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
        if directory == root:
            break
    return None


def build_run(root: Path, run_dir: Path) -> dict | None:
    """Build a run dict with prompt, outputs, grading and timing data.

    Unknown values are None, never a zero or an empty string that the viewer
    could mistake for a measurement.
    """
    prompt: str | None = None
    eval_id = None
    eval_name = None
    # The *input* set an author wrote is `assertions` in eval_metadata.json;
    # the *graded* results are `expectations` in grading.json. Carrying the
    # input set through lets the page check that the grader actually graded the
    # checks this eval declared, which nothing anywhere used to do.
    assertions: list | None = None

    metadata_path = _search_upwards(run_dir, root, "eval_metadata.json")
    if metadata_path is not None:
        metadata = load_json_file(metadata_path, "eval_metadata.json")
        if metadata is not None:
            prompt = metadata.get("prompt") or None
            eval_id = metadata.get("eval_id")
            eval_name = metadata.get("eval_name") or None
            raw_assertions = metadata.get("assertions")
            if isinstance(raw_assertions, list):
                assertions = [a for a in raw_assertions if isinstance(a, str)]
                if len(assertions) != len(raw_assertions):
                    warn(
                        f"eval_metadata.json at {metadata_path} has non-string entries in "
                        "`assertions`; they were dropped from the comparison against the "
                        "grader's expectations."
                    )
            elif raw_assertions is not None:
                warn(
                    f"eval_metadata.json at {metadata_path} has an `assertions` field that "
                    "is not an array; ignoring it."
                )

    # Fall back to transcript.md
    if not prompt:
        for candidate in [run_dir / "transcript.md", run_dir / "outputs" / "transcript.md"]:
            if candidate.is_file():
                try:
                    text = candidate.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as e:
                    warn(f"transcript.md at {candidate} could not be read ({e}).")
                    continue
                match = re.search(r"## Eval Prompt\n\n([\s\S]*?)(?=\n##|$)", text)
                if match:
                    prompt = match.group(1).strip() or None
                if prompt:
                    break

    if not prompt:
        warn(
            f"no prompt recovered for {run_dir} — looked for eval_metadata.json "
            f"from that directory up to {root}, then transcript.md."
        )

    run_id = str(run_dir.relative_to(root)).replace("/", "-").replace("\\", "-")

    # Three layouts, three verdicts, and every reader in this bundle uses the
    # same names for them:
    #
    #   canonical     run-<K> with an integer K.  ok
    #   legacy-flat   no run level at all.        warning; normalized to run-1
    #   malformed-run run-<K> with a non-integer. warning; the AGGREGATOR
    #                 excludes it, so this page and the benchmark are looking
    #                 at different data and the page has to say so.
    run_match = RUN_DIR_RE.match(run_dir.name)
    run_number: int | None = None
    layout_note: str | None = None
    if run_match:
        layout = "canonical"
        run_number = int(run_match.group(1))
    elif run_dir.name.startswith("run-"):
        layout = "malformed-run"
        layout_note = (
            "This directory is named " + repr(run_dir.name) + ", which is not "
            "run-<K> with an integer K. The benchmark aggregator excludes it, so this "
            "run is shown here and is counted in no benchmark number. Rename it to "
            "run-1 (or run-2, run-3, ...) and re-run the aggregation."
        )
    else:
        layout = "legacy-flat"
        run_number = 1  # normalized to the canonical single-run number
        layout_note = (
            "This run has no run-<K> directory (the legacy flat layout). It has been "
            "read as run-1. The canonical layout is "
            "<eval-dir>/<config>/run-<K>/outputs/."
        )

    # Collect output files
    outputs_dir = run_dir / "outputs"
    output_files: list[dict] = []
    if outputs_dir.is_dir():
        for f in sorted(outputs_dir.iterdir()):
            if f.is_file() and f.name not in METADATA_FILES:
                output_files.append(embed_file(f))

    # Load grading if present. Canonical location is the run dir; the eval-dir
    # root is accepted for graders that wrote one level up, with a warning.
    #
    # `grading_note` is the reason there are no automated checks to show. It
    # exists because an absent AUTOMATED CHECKS panel looked exactly like a run
    # with nothing to report, on the one screen the reviewer actually works
    # through -- while the same run was itemized as an exclusion on the
    # Benchmark tab. Absent data is absent, and it says so where it is missing.
    grading = None
    grading_note: str | None = None
    grading_path = run_dir / "grading.json"
    if not grading_path.is_file():
        stray = run_dir.parent / "grading.json"
        if stray.is_file():
            warn(
                f"grading.json for {run_id} was found at {stray}, not in the run "
                "directory. Reading it anyway; the canonical location is "
                f"{run_dir / 'grading.json'}."
            )
            grading_path = stray
    if grading_path.is_file():
        grading = load_json_file(grading_path, "grading.json")
        if grading is None:
            grading_note = (
                "A grading.json exists for this run but could not be read as a JSON "
                "object (a warning naming the exact fault was printed to the terminal "
                "that started this viewer). This run contributes to no benchmark number."
            )
        else:
            # A boolean `passed` with no `verdict` is the PREVIOUS
            # grading contract, and the aggregator excludes such a file outright.
            # The page says so too, but a viewer run on a stale workspace should
            # not require anyone to notice a banner: the same fact belongs in the
            # terminal, where it is a one-line instruction rather than a
            # discovery.
            legacy = sum(
                1 for exp in (grading.get("expectations") or [])
                if isinstance(exp, dict) and "passed" in exp and "verdict" not in exp
            ) if isinstance(grading, dict) else 0
            if legacy:
                warn(
                    f"{grading_path}: {legacy} expectation(s) carry the retired "
                    f"boolean 'passed' and no 'verdict'. That is the previous "
                    f"grading contract; the page shows them as unrecorded rather "
                    f"than guessing whether each false meant 'verified false' or "
                    f"'could not tell'. Run `python -m scripts.validate_grading "
                    f"{grading_path}` for the migration."
                )
    else:
        grading_note = (
            "No grading.json was written for this run, so it was never graded. Nothing "
            "here is a zero score: the checks were not run. The benchmark excludes this "
            "run from every number it reports."
        )
        warn(f"no grading.json for {run_id}; the run shows as ungraded and is excluded "
             "from the benchmark.")

    # Load timing if present. Absent timing stays None so the viewer can render
    # "unknown" rather than a zero that reads as a real measurement.
    timing = None
    timing_path = run_dir / "timing.json"
    if not timing_path.is_file():
        stray = run_dir.parent / "timing.json"
        if stray.is_file():
            timing_path = stray
    if timing_path.is_file():
        timing = load_json_file(timing_path, "timing.json")
    else:
        warn(f"no timing.json for {run_id}; time and token cells will read as unknown.")

    return {
        "id": run_id,
        "prompt": prompt,
        "eval_id": eval_id,
        "eval_name": eval_name,
        "assertions": assertions,
        "run_number": run_number,
        "layout": layout,
        "layout_note": layout_note,
        "outputs": output_files,
        "grading": grading,
        "grading_note": grading_note,
        "timing": timing,
    }


def embed_file(path: Path) -> dict:
    """Read a file and return an embedded representation."""
    ext = path.suffix.lower()
    mime = get_mime_type(path)

    if ext in TEXT_EXTENSIONS:
        # errors="replace" keeps a mixed-encoding output file reviewable rather
        # than aborting the whole page; the explicit encoding is what stops the
        # cp1252 mojibake that made non-English text unreadable on Windows.
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            content = f"(Error reading file: {e})"
        return {
            "name": path.name,
            "type": "text",
            "content": content,
        }
    elif ext in IMAGE_EXTENSIONS:
        try:
            raw = path.read_bytes()
            b64 = base64.b64encode(raw).decode("ascii")
        except OSError:
            return {"name": path.name, "type": "error", "content": "(Error reading file)"}
        return {
            "name": path.name,
            "type": "image",
            "mime": mime,
            "data_uri": f"data:{mime};base64,{b64}",
        }
    elif ext == ".pdf":
        try:
            raw = path.read_bytes()
            b64 = base64.b64encode(raw).decode("ascii")
        except OSError:
            return {"name": path.name, "type": "error", "content": "(Error reading file)"}
        return {
            "name": path.name,
            "type": "pdf",
            "data_uri": f"data:{mime};base64,{b64}",
        }
    elif ext == ".xlsx":
        try:
            raw = path.read_bytes()
            b64 = base64.b64encode(raw).decode("ascii")
        except OSError:
            return {"name": path.name, "type": "error", "content": "(Error reading file)"}
        return {
            "name": path.name,
            "type": "xlsx",
            "mime": mime,
            "data_b64": b64,
        }
    else:
        # Binary / unknown — base64 download link
        try:
            raw = path.read_bytes()
            b64 = base64.b64encode(raw).decode("ascii")
        except OSError:
            return {"name": path.name, "type": "error", "content": "(Error reading file)"}
        return {
            "name": path.name,
            "type": "binary",
            "mime": mime,
            "data_uri": f"data:{mime};base64,{b64}",
        }


def load_previous_iteration(workspace: Path) -> dict[str, dict]:
    """Load previous iteration's feedback and outputs.

    Returns a map of run_id -> {"feedback": str, "outputs": list[dict]}.
    """
    result: dict[str, dict] = {}

    # Load feedback
    feedback_map: dict[str, str] = {}
    feedback_path = workspace / "feedback.json"
    if feedback_path.is_file():
        data = load_json_file(feedback_path, "feedback.json")
        if data is not None:
            try:
                feedback_map = {
                    r["run_id"]: r["feedback"]
                    for r in data.get("reviews", [])
                    if isinstance(r, dict) and (r.get("feedback") or "").strip()
                }
            except (KeyError, TypeError, AttributeError) as e:
                warn(f"feedback.json at {feedback_path} has an unexpected shape ({e}).")

    # Load runs (to get outputs)
    prev_runs = find_runs(workspace)
    for run in prev_runs:
        result[run["id"]] = {
            "feedback": feedback_map.get(run["id"], ""),
            "outputs": run.get("outputs", []),
        }

    # Also add feedback for run_ids that had feedback but no matching run
    for run_id, fb in feedback_map.items():
        if run_id not in result:
            result[run_id] = {"feedback": fb, "outputs": []}

    return result


# ---------------------------------------------------------------------------
# Embedding (script-literal context)
# ---------------------------------------------------------------------------

# The embedded blob lands inside an inline <script> element. HTML tokenizes
# script data by looking for the literal "</script"; JSON escaping knows
# nothing about that, so an output file containing "</script>" used to close
# the element mid-assignment, leaving EMBEDDED_DATA undefined and turning the
# rest of the payload into live DOM.
#
# The fix is to escape for the context the value actually lands in — a
# JavaScript string literal inside an HTML script element — rather than to add
# another pass over the data. "<" is a legal JS escape that HTML's
# tokenizer cannot see as a tag, and it parses back to exactly "<", so the
# data reaching the page is byte-identical to the data on disk.
#
# ensure_ascii stays at its default True: the payload is then pure ASCII, so it
# survives any output encoding, and JavaScript decodes \uXXXX in string
# literals back to the original characters. (This is why issue #1034's
# diagnosis is wrong — the escapes are never visible to the user. The mojibake
# users report comes from reading files without encoding="utf-8".)
# Built rather than written out so that no tool in the chain can normalize
# the escape sequences back into the characters they are meant to replace.
_BACKSLASH_U = chr(92) + "u"

_SCRIPT_LITERAL_ESCAPES = {
    # Escaping "<" alone defeats "</script"; ">" and "&" close the
    # remaining HTML-tokenizer edges. U+2028 and U+2029 are legal inside a
    # JSON string but terminate a line in JavaScript.
    ch: _BACKSLASH_U + format(ord(ch), "04x")
    for ch in ("<", ">", "&", chr(0x2028), chr(0x2029))
}


def to_script_literal(obj: object) -> str:
    """Serialize `obj` as a JavaScript object literal safe for inline <script>."""
    data_json = json.dumps(obj)
    for char, escape in _SCRIPT_LITERAL_ESCAPES.items():
        data_json = data_json.replace(char, escape)
    return data_json


def generate_html(
    runs: list[dict],
    skill_name: str,
    previous: dict[str, dict] | None = None,
    benchmark: dict | None = None,
) -> str:
    """Generate the complete standalone HTML page with embedded data."""
    template_path = Path(__file__).parent / "viewer.html"
    template = template_path.read_text(encoding="utf-8")

    # Build previous_feedback and previous_outputs maps for the template
    previous_feedback: dict[str, str] = {}
    previous_outputs: dict[str, list[dict]] = {}
    if previous:
        for run_id, data in previous.items():
            if data.get("feedback"):
                previous_feedback[run_id] = data["feedback"]
            if data.get("outputs"):
                previous_outputs[run_id] = data["outputs"]

    embedded = {
        "skill_name": skill_name,
        "runs": runs,
        "previous_feedback": previous_feedback,
        "previous_outputs": previous_outputs,
    }
    if benchmark:
        embedded["benchmark"] = benchmark

    data_json = to_script_literal(embedded)

    return template.replace("/*__EMBEDDED_DATA__*/", f"const EMBEDDED_DATA = {data_json};")


# ---------------------------------------------------------------------------
# HTTP server (stdlib only, zero dependencies)
# ---------------------------------------------------------------------------


class ReviewServer(ThreadingHTTPServer):
    """Loopback-only HTTP server, one thread per connection.

    allow_reuse_address is explicitly off. HTTPServer sets it to 1, which sets
    SO_REUSEADDR — and on Windows SO_REUSEADDR lets a second socket bind an
    address that is already bound. The bind then succeeds, the OSError fallback
    to an ephemeral port never fires, and the browser is handed to the *previous*
    iteration's server. With it off, a busy port raises and the fallback runs.

    Threading is not about throughput. The single-threaded HTTPServer serves one
    connection at a time, so a client that opened a socket and sent a partial
    request line held the entire viewer hostage for as long as it liked — the
    page simply stopped responding, with nothing logged, because the server was
    still inside readline() on the stalled socket. One thread per connection
    plus ReviewHandler.timeout means a stalled peer costs one thread for at most
    REQUEST_TIMEOUT_SECONDS and costs every other request nothing.

    daemon_threads (inherited) keeps Ctrl+C from hanging on a live connection.
    """

    allow_reuse_address = False

    def handle_error(self, request, client_address) -> None:
        """Report a dropped connection as one line, not as a traceback.

        A browser that navigates away mid-response raises ConnectionAbortedError
        or ConnectionResetError inside wfile.write. socketserver's default is to
        dump a full traceback, and this process's output is what the model reads
        to find the viewer URL — a stack trace there reads as a crash when
        nothing is wrong.
        """
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            warn(f"browser disconnected before the page finished sending ({type(exc).__name__}).")
            return
        if isinstance(exc, TimeoutError):
            # A peer that opened a socket and then stopped talking. Reported so
            # that a wedged-looking viewer has a visible cause, but it is not a
            # crash and it no longer blocks anyone else.
            warn(
                f"dropped a connection from {client_address[0]} that sent no complete "
                f"request within {REQUEST_TIMEOUT_SECONDS}s."
            )
            return
        super().handle_error(request, client_address)


class ReviewHandler(BaseHTTPRequestHandler):
    """Serves the review HTML and handles feedback saves.

    Regenerates the HTML on each page load so that refreshing the browser
    picks up new eval outputs without restarting the server.
    """

    # StreamRequestHandler.setup() calls connection.settimeout(self.timeout).
    # The base class leaves this None, which is what let one half-open
    # connection block the process indefinitely.
    timeout = REQUEST_TIMEOUT_SECONDS

    # Serializes the read-modify-write of feedback.json now that requests are
    # handled on separate threads. Class-level: `partial` builds a new handler
    # instance per request, so an instance attribute would lock nothing.
    _feedback_lock = threading.Lock()

    def __init__(
        self,
        workspace: Path,
        skill_name: str,
        feedback_path: Path,
        previous: dict[str, dict],
        benchmark_path: Path | None,
        *args,
        **kwargs,
    ):
        self.workspace = workspace
        self.skill_name = skill_name
        self.feedback_path = feedback_path
        self.previous = previous
        self.benchmark_path = benchmark_path
        super().__init__(*args, **kwargs)

    # -- request origin checks ------------------------------------------------

    def _host_ok(self) -> bool:
        """Reject requests whose Host is not loopback (DNS-rebinding defense).

        Without this, a hostname that resolves to 127.0.0.1 lets any web page
        read the entire workspace — every embedded output file — out of this
        server.
        """
        host = self.headers.get("Host", "")
        if not host:
            return False
        try:
            hostname = urllib.parse.urlsplit("//" + host).hostname
        except ValueError:
            return False
        return hostname in LOOPBACK_HOSTS

    def _origin_ok(self) -> bool:
        """Reject cross-origin writes.

        The feedback file is the input to the next skill revision, so any page
        the user has open must not be able to overwrite it.
        """
        origin = self.headers.get("Origin")
        if origin is None:
            # Non-browser clients (curl, the model's own harness) omit Origin.
            # The Host check above still applies.
            return True
        if origin == "null":
            return False
        try:
            parts = urllib.parse.urlsplit(origin)
            port = parts.port
        except ValueError:
            return False
        if parts.scheme not in ("http", "https"):
            return False
        if parts.hostname not in LOOPBACK_HOSTS:
            return False
        return port == self.server.server_address[1]

    def _drain(self, remaining: int) -> None:
        """Read and discard up to `remaining` bytes of the request body."""
        chunk = 64 * 1024
        while remaining > 0:
            try:
                read = self.rfile.read(min(chunk, remaining))
            except (OSError, ValueError):
                return
            if not read:
                return
            remaining -= len(read)

    def _reject(self, code: int, reason: str) -> None:
        body = json.dumps({"error": reason}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    # -- handlers -------------------------------------------------------------

    def _route(self) -> str:
        """The path component of the request target, without query or fragment.

        Compared against self.path directly, `GET /?v=2` — a cache-buster, or a
        bookmark that kept a query string — fell through to a stock 404 error
        page instead of the viewer.
        """
        return urllib.parse.urlsplit(self.path).path or "/"

    def do_GET(self) -> None:
        if not self._host_ok():
            self._reject(403, "This server only answers requests addressed to localhost.")
            return

        route = self._route()
        if route == "/" or route == "/index.html":
            # Regenerate HTML on each request (re-scans workspace for new outputs)
            runs = find_runs(self.workspace)
            benchmark = None
            if self.benchmark_path and self.benchmark_path.is_file():
                benchmark = load_json_file(self.benchmark_path, "benchmark.json")
            html = generate_html(runs, self.skill_name, self.previous, benchmark)
            content = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)
        elif route == "/api/feedback":
            data = b"{}"
            if self.feedback_path.is_file():
                try:
                    data = self.feedback_path.read_bytes()
                except OSError as e:
                    warn(f"could not read {self.feedback_path} ({e}).")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        # Read the request body BEFORE deciding whether to answer it. Closing
        # the socket with an undelivered body still in flight makes Windows
        # send an RST, and the client sees a connection reset instead of the
        # 403 explaining why it was refused.
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._reject(400, "Bad Content-Length")
            return
        if length < 0 or length > MAX_REQUEST_BYTES:
            # Drain (and discard) what the client is still sending before
            # answering. Closing a socket with an undelivered body in flight
            # makes Windows send an RST, and the client then sees a connection
            # reset instead of the 413 explaining the refusal -- which is the
            # same mistake this method's opening comment was written about.
            # Bounded so an absurd Content-Length cannot make us read forever;
            # nothing is retained.
            self._drain(min(length, MAX_REQUEST_BYTES * 4))
            self._reject(413, f"Request body larger than {MAX_REQUEST_BYTES} bytes.")
            self.close_connection = True
            return
        body = self.rfile.read(length) if length else b""

        if not self._host_ok():
            self._reject(403, "This server only answers requests addressed to localhost.")
            return
        if not self._origin_ok():
            self._reject(403, "Cross-origin writes to the feedback file are refused.")
            return

        if self._route() == "/api/feedback":
            try:
                data = json.loads(body.decode("utf-8"))
                self._validate_feedback(data)
            except (json.JSONDecodeError, UnicodeError, ValueError) as e:
                # A body this server cannot use is the client's fault, and 400
                # says so; 500 blamed the server for a malformed request.
                self._reject(400, str(e))
                return
            try:
                # feedback.json is the input to the next skill revision, and the
                # whole file is replaced on every save. Two concurrent writers
                # would interleave into something neither of them wrote.
                with self._feedback_lock:
                    self.feedback_path.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
            except (OSError, UnicodeError, ValueError) as e:
                self._reject(500, str(e))
                return
            resp = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(resp)
        else:
            self.send_error(404)

    def _validate_feedback(self, data: object) -> None:
        """Raise ValueError unless `data` is a feedback document for THIS workspace.

        Every entry's run_id must name a run that exists here. Without this
        check a single POST replaced every genuine review in feedback.json with
        entries filed under a run_id that appears nowhere in the workspace —
        review notes destroyed, and the file still looked structurally valid to
        every reader downstream.
        """
        if not isinstance(data, dict) or "reviews" not in data:
            raise ValueError("Expected JSON object with 'reviews' key")
        reviews = data["reviews"]
        if not isinstance(reviews, list):
            raise ValueError("'reviews' must be an array")

        known = find_run_ids(self.workspace)
        unknown = []
        for entry in reviews:
            if not isinstance(entry, dict):
                raise ValueError("every entry of 'reviews' must be a JSON object")
            run_id = entry.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                raise ValueError("every entry of 'reviews' needs a non-empty string run_id")
            if run_id not in known:
                unknown.append(run_id)
        if unknown:
            shown = ", ".join(sorted(set(unknown))[:5])
            raise ValueError(
                f"{len(set(unknown))} run_id(s) in this submission name no run in "
                f"{self.workspace}: {shown}. Nothing was written, so the reviews already "
                "on disk are intact."
            )

    def log_message(self, format: str, *args: object) -> None:
        # Suppress request logging to keep terminal clean
        pass


def main() -> None:
    configure_console()

    parser = argparse.ArgumentParser(description="Generate and serve eval review")
    parser.add_argument("workspace", type=Path, help="Path to workspace directory")
    parser.add_argument("--port", "-p", type=int, default=3117, help="Server port (default: 3117)")
    parser.add_argument("--skill-name", "-n", type=str, default=None, help="Skill name for header")
    parser.add_argument(
        "--previous-workspace", type=Path, default=None,
        help="Path to previous iteration's workspace (shows old outputs and feedback as context)",
    )
    parser.add_argument(
        "--benchmark", type=Path, default=None,
        help="Path to benchmark.json to show in the Benchmark tab. Defaults to "
             "<workspace>/benchmark.json when that file exists.",
    )
    parser.add_argument(
        "--static", "-s", type=Path, default=None,
        help="Write standalone HTML to this path instead of starting a server",
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"Error: {workspace} is not a directory", file=sys.stderr)
        sys.exit(1)

    runs = find_runs(workspace)
    if not runs:
        print(f"No runs found in {workspace}", file=sys.stderr)
        print(
            "  Looked for any directory containing an outputs/ subdirectory. "
            "The canonical layout is "
            "<iteration-dir>/eval-<ID>-<slug>/<config>/run-<K>/outputs/",
            file=sys.stderr,
        )
        sys.exit(1)

    skill_name = args.skill_name or workspace.name.replace("-workspace", "")
    feedback_path = workspace / "feedback.json"

    previous: dict[str, dict] = {}
    if args.previous_workspace:
        previous = load_previous_iteration(args.previous_workspace.resolve())

    # aggregate_benchmark.py writes <iteration-dir>/benchmark.json, which is
    # normally the very directory this viewer is pointed at. Without this
    # default, the page asserted "No benchmark data available" about a file
    # sitting one directory above the runs it had just read.
    discovered = False
    if args.benchmark:
        benchmark_path = args.benchmark.resolve()
    else:
        candidate = workspace / "benchmark.json"
        benchmark_path = candidate if candidate.is_file() else None
        discovered = benchmark_path is not None

    benchmark = None
    if benchmark_path:
        if benchmark_path.is_file():
            benchmark = load_json_file(benchmark_path, "benchmark.json")
        else:
            warn(f"benchmark file {benchmark_path} does not exist; the Benchmark tab will be empty.")

    if args.static:
        html = generate_html(runs, skill_name, previous, benchmark)
        args.static.parent.mkdir(parents=True, exist_ok=True)
        # encoding="utf-8" matters here as much as on the read side: the page
        # declares <meta charset="UTF-8">, so writing it in the platform
        # codepage produces a file whose bytes disagree with its own header.
        args.static.write_text(html, encoding="utf-8")
        print(f"\n  Static viewer written to: {args.static}\n")
        sys.exit(0)

    handler = partial(ReviewHandler, workspace, skill_name, feedback_path, previous, benchmark_path)
    port = args.port
    try:
        server = ReviewServer(("127.0.0.1", port), handler)
    except OSError:
        # Something already holds the port. Take a free one rather than
        # sharing — a shared port means the browser talks to whichever server
        # bound first, which is the previous iteration's.
        server = ReviewServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]
        warn(
            f"port {args.port} is already in use (another viewer is probably still "
            f"running). Using port {port} instead — open the URL printed below, not "
            f"{args.port}, or you will be looking at the older server's results."
        )

    url = f"http://localhost:{port}"
    print("\n  Eval Viewer")
    print("  " + "-" * 33)
    print(f"  URL:       {url}")
    print(f"  Workspace: {workspace}")
    print(f"  Feedback:  {feedback_path}")
    if previous:
        print(f"  Previous:  {args.previous_workspace} ({len(previous)} runs)")
    if benchmark_path:
        print(f"  Benchmark: {benchmark_path}"
              + (" (found in the workspace; pass --benchmark to override)" if discovered else ""))
    else:
        print(f"  Benchmark: none - no --benchmark given and no {workspace / 'benchmark.json'}")
    print("\n  Press Ctrl+C to stop.\n")
    # The skill runs this backgrounded with stdout piped, where stdout is
    # block-buffered. Without an explicit flush the URL never reaches the
    # caller until the process exits — which for a server is never.
    sys.stdout.flush()

    if not webbrowser.open(url):
        warn(f"could not open a browser automatically. Open this address yourself: {url}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
