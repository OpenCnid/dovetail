#!/usr/bin/env python3
"""
Render one panel seat prompt per seat from the invariant frame, giving each seat
exactly the material its own ``inputs`` allowlist admits and nothing beyond it.

Why this exists as code rather than as prose. ``agents/panel/seat-frame.md``
already states the rule:

    exactly what this seat's `inputs` allowlist names, and nothing beyond it.
    This is the seats' separation made real: the corroboration seat's
    independence is a fact about which bytes it was handed, not a promise it
    made.

Two runs were rendered by hand against that sentence and both handed a
byte-identical evidence block to all three seats - every path to everyone, plus
one line saying "your inputs allowlist ... governs which of the files at those
paths you may treat as evidence." That converts the allowlist back into a
promise, and it puts an instruction inside the one section ``<identity>`` tells
the seat is never instruction. The breach was demonstrable: run 1's grounding
``inputs`` said the producing agent's prose note was "withheld from this seat by
design", the note files sat in the directories it was pointed at, and its return
cited one of them.

The orchestrator who did that was following the frame's prose and got it wrong
anyway. A rule that a careful reader can follow incorrectly belongs in code -
the same argument that put the panel instantiation gates in ``gate_panel.py``.

    A seat's independence is a fact about which bytes it was handed. This
    script is where that fact is made, and the render report is where it is
    checkable by someone who trusts nobody in the room.

The hard part: ``inputs`` is prose composed at runtime
--------------------------------------------------------------------------
An ``inputs`` entry is a sentence a composer wrote - "The full contents of every
deliverable in the outputs directory read as text, excluding any prose file the
producing agent wrote about its own work". Nothing in it is machine-readable,
and no amount of pattern matching turns it into a path set without guessing.
Guessing is the failure being closed, so this script does not guess.

Three routes were available: a per-entry glob on the composition, a required
machine-readable field on ``inputs``, or a **declared material manifest** the
orchestrator writes beside the composition. This takes the third.

  * A required field on ``inputs`` would change the composition schema, and
    therefore ``composer.md`` and ``gate_panel.py``. It also puts the path
    mapping inside the artifact composed blind to the candidate - the composer
    would be naming this run's files, which is exactly what composing blind is
    meant to keep it from seeing.
  * A per-entry glob is the same change wearing a smaller hat.
  * A separate manifest keeps the composition a record of one characterization,
    and puts the run-specific mapping where the run-specific knowledge is: with
    the orchestrator, who knows which files exist.

The cost is real and is not hidden: the mapping is a **judgment**, and a wrong
manifest renders a wrong prompt. So every guard here exists to make a wrong
manifest loud rather than silent:

  * Each ``inputs`` entry must be bound, one to one, in composition order, and
    the manifest repeats each entry's text **character for character**. A
    recomposition that rewords one sentence fails ``entry_text_drift`` rather
    than rendering against a stale binding.
  * An entry bound to nothing is ``entry_unmapped``. There is no fallback to
    "give this seat everything", because that fallback *is* the defect.
  * A channel two entries share must declare the overlap. The hand-rendered
    runs failed exactly here: one channel globbing ``outputs/**`` silently
    swallows the note channel beside it, and an undeclared collision between
    those two sets is the shape of the leak.
  * A seat whose allowlist admits no path at all is ``seat_admits_nothing``.
  * Every admitted path is resolved and confirmed inside its item's base,
    and refused if it carries a configuration name - ``with_skill``,
    ``without_skill``, ``old_skill`` - because the frame requires authorship
    masked and directory names are where it leaks.

What a seat is handed
--------------------------------------------------------------------------
Individual file paths, never a directory. A directory path hands over
everything inside it, which is how the recorded runs leaked the notes: the
prompt named ``.../outputs`` and the withheld file was sitting in it. Paths are
also never labelled with the channel they came from - a channel id like
``ev.executor-note`` comes from the characterization, and constraint 3 says no
seat sees the characterization.

The material block carries no sentence about the allowlist. It is a list of
what exists for this seat, closed by the frame's own invariant line - "A path
not listed here names a file that does not exist for this run." Fact, not
instruction.

Usage:
    python -m scripts.render_seats <composition> --evals <evals.json> \\
        --material <material.json> --out <dir> [--frame <seat-frame.md>] [--json]

    python -m scripts.render_seats <composition> --evals <evals.json> \\
        --emit-manifest-template <path>

Exit codes:
    0  every seat rendered
    1  at least one typed refusal; nothing was written
    2  a file could not be read, parsed, or was not supplied

With --json the machine-readable report goes to stdout *alone*; every
human-readable line goes to stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from itertools import combinations
from pathlib import Path
from typing import Any, Optional

from scripts.utils import configure_console

# --------------------------------------------------------------------------
# Schemas and invariants
# --------------------------------------------------------------------------

COMPOSITION_SCHEMA_ID = "panel.composition/1"
MATERIAL_SCHEMA_ID = "panel.material/1"
REPORT_SCHEMA_ID = "panel.render_report/1"

#: The four sections, in the frame's order. There is no fifth (constraint 1).
SECTION_ORDER = ("identity", "definition", "evidence", "output_schema")

#: Sections whose bytes are invariant across every seat, every run and every
#: skill. Asserted before anything is written, not documented and hoped for.
INVARIANT_SECTIONS = ("identity", "output_schema")

#: A free variable in the frame: ``{This_Seats_Composed_Definition...}``.
PLACEHOLDER = re.compile(r"\{[A-Z][A-Za-z0-9_]*\}")

#: The configuration directory names. Which configuration produced a file is
#: never a parameter to a seat, and a path is the usual place it leaks.
AUTHORSHIP_SEGMENTS = ("with_skill", "without_skill", "old_skill")

#: What a channel can hand a seat. ``paths`` is the only one that puts bytes in
#: front of a seat; the other two exist because a composer writes ``inputs``
#: entries that name no file at all, and an entry silently bound to nothing is
#: the hole this script exists to close.
PROVIDES = ("paths", "statements", "no-material")

#: Guard against enumerating a pathological tree while computing what was
#: withheld. Exceeded means the withheld record is partial and says so.
WITHHELD_FILE_CAP = 20000

REFUSAL_REASONS = {
    "frame_unreadable":
        "the seat frame could not be read",
    "frame_unparsable":
        "the seat frame's rendered block is missing, malformed, or does not "
        "carry the four sections in order",
    "frame_placeholder_count":
        "a frame section carries a different number of free variables than "
        "this renderer knows how to fill",
    "composition_unreadable":
        "the composition could not be read or parsed",
    "evals_unreadable":
        "the eval set could not be read or parsed",
    "manifest_unreadable":
        "the material manifest could not be read or parsed",
    "schema_unrecognized":
        "a document declares a schema this renderer does not know",
    "schema_invalid":
        "a document is structurally wrong in a way that has no reading",
    "eval_unmapped":
        "an eval contributing statements has no base directory in the manifest",
    "eval_binding_unknown":
        "the manifest binds an eval id the eval set does not contain",
    "base_missing":
        "a declared base directory does not exist",
    "statement_multiline":
        "a statement carries a line break, so it cannot be rendered on its own "
        "line unmarked",
    "statement_altered":
        "the rendered statement is not character-for-character the authored one",
    "definition_altered":
        "the rendered definition does not parse back to the seat object",
    "seat_unmapped":
        "a seat in the composition has no binding in the material manifest",
    "seat_binding_unknown":
        "the manifest binds a seat the composition does not contain",
    "entry_count_mismatch":
        "a seat's bindings do not correspond one-to-one with its `inputs`",
    "entry_text_drift":
        "a binding's quoted entry is not the composition's `inputs` text",
    "entry_unmapped":
        "an `inputs` entry names no channel, so it cannot be mapped to material",
    "unknown_channel":
        "a binding names a channel the manifest does not define",
    "channel_invalid":
        "a channel definition is structurally wrong",
    "channel_empty":
        "a channel declared present for this run resolves to no file anywhere",
    "channel_overlap_undeclared":
        "two channels resolve to a shared path without declaring the overlap",
    "pattern_escapes_base":
        "a channel pattern is absolute or climbs out of the item base",
    "path_escapes_base":
        "an admitted path resolves outside its item base",
    "authorship_leak":
        "an admitted path carries a configuration name, which discloses which "
        "configuration produced the material",
    "seat_admits_nothing":
        "a seat's allowlist admits no path at all",
    "invariant_section_differs":
        "the identity or output_schema bytes are not identical across seats",
    "out_dir_unwritable":
        "the output directory could not be created or written",
}

WARNING_REASONS = {
    "entry_carries_no_material":
        "an `inputs` entry is bound to a channel that hands over no file - the "
        "seat's own general knowledge, a standing fact about the domain, or a "
        "channel this run does not have",
    "item_without_material":
        "a statement's item has no admitted path for this seat",
    "evidence_blocks_identical":
        "two or more seats received the same evidence block, so their "
        "allowlists do not differ in what they admit",
    "withheld_truncated":
        "an item base held more files than the enumeration cap, so the "
        "withheld record for it is partial",
    "seat_sees_everything":
        "a seat was admitted every file under every item base, so nothing was "
        "withheld from it",
}


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

def _finding(reason: str, detail: str, seat: Optional[str] = None) -> dict:
    return {"reason": reason, "seat": seat, "detail": detail}


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


class Refusal(Exception):
    """A typed refusal that stops the render. Nothing is written after one."""

    def __init__(self, findings: list[dict]) -> None:
        super().__init__(findings[0]["detail"] if findings else "refused")
        self.findings = findings


def _refuse(reason: str, detail: str, seat: Optional[str] = None):
    raise Refusal([_finding(reason, detail, seat)])


def _no_material_why(channel: dict) -> str:
    """Say which of the three reasons a channel handed over no file.

    They are not interchangeable: material the seat already holds, knowledge no
    file carries, and a channel this run does not have are three different
    facts, and collapsing them into one message is how a missing channel gets
    read as a modelling convenience.
    """
    provides = channel.get("provides", "paths")
    if provides == "statements":
        return (f"channel {channel['id']} is the statements block the seat "
                f"already holds")
    if provides == "no-material":
        return channel.get("why") or f"channel {channel['id']} carries no file"
    return (channel.get("why")
            or f"channel {channel['id']} is declared absent for this run")


# --------------------------------------------------------------------------
# Loading. Encoding is always explicit, and UnicodeDecodeError is not caught
# by (json.JSONDecodeError, OSError).
# --------------------------------------------------------------------------

def read_text(path: Path) -> tuple[Optional[str], Optional[str]]:
    try:
        return path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeDecodeError, UnicodeError) as exc:
        return None, f"{path}: {exc}"


def load_json(path: Path) -> tuple[Optional[dict], Optional[str]]:
    raw, error = read_text(path)
    if error is not None:
        return None, error
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"{path}: {exc}"
    if not isinstance(document, dict):
        return None, f"{path}: top level is {type(document).__name__}, not an object"
    return document, None


def sha256_text(text: str) -> str:
    """Digest of *text*'s UTF-8 bytes.

    Hashed as bytes, never as a decoded string handed to a reader that might
    translate newlines - a digest that moves with the reader is not a digest.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def write_text(path: Path, text: str) -> None:
    """Write *text* with its newlines unchanged.

    ``Path.write_text`` translates ``\\n`` to ``\\r\\n`` on Windows, which would
    make every digest in the render report disagree with the bytes on disk -
    the report claims ``<identity>`` is byte-identical across seats, and a
    reader who checks that claim by hashing the file has to arrive at the same
    number. A digest nobody can reproduce from the artifact is not a record.
    """
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


# --------------------------------------------------------------------------
# The frame
# --------------------------------------------------------------------------

def parse_frame(frame_text: str) -> dict[str, str]:
    """Pull the four sections out of ``seat-frame.md``'s rendered block.

    The frame file is the specification. Copying its bytes into this module
    would make two representations of one fact that must agree, which is a
    drift surface by construction - so the invariant bytes are read from the
    frame at render time and never restated here.
    """
    fenced = re.search(r"^```md[ \t]*\n(.*?)^```", frame_text, re.S | re.M)
    if fenced is None:
        _refuse("frame_unparsable",
                "no ```md block in the frame; the rendered block is what a "
                "seat sees and it could not be located")
    block = fenced.group(1)

    sections: dict[str, str] = {}
    positions: list[tuple[int, str]] = []
    for name in SECTION_ORDER:
        match = re.search(rf"<{name}>\n.*?\n</{name}>", block, re.S)
        if match is None:
            _refuse("frame_unparsable",
                    f"the frame's rendered block has no <{name}> section")
        sections[name] = match.group(0)
        positions.append((match.start(), name))

    ordered = [name for _, name in sorted(positions)]
    if tuple(ordered) != SECTION_ORDER:
        _refuse("frame_unparsable",
                f"the frame's sections appear in the order {ordered}; the frame "
                f"fixes {list(SECTION_ORDER)} and the order is what a seat reads")

    # Four sections. There is no fifth (constraint 1): anything in the block
    # outside the four is text this renderer would silently drop or silently
    # ship, and both are wrong.
    remainder = block
    for text in sections.values():
        remainder = remainder.replace(text, "", 1)
    if remainder.strip():
        _refuse("frame_unparsable",
                "the frame's rendered block carries text outside the four "
                "sections: " + " ".join(remainder.split())[:200])

    expected = {"identity": 0, "definition": 1, "evidence": 2, "output_schema": 0}
    for name, count in expected.items():
        found = PLACEHOLDER.findall(sections[name])
        # <output_schema> keeps its own free variables verbatim - they are what
        # the seat fills in - so it is exempt from the count, not from the read.
        if name == "output_schema":
            continue
        if len(found) != count:
            _refuse("frame_placeholder_count",
                    f"<{name}> carries {len(found)} free variable(s) "
                    f"{found}; this renderer fills {count}")
    return sections


def fill(section: str, values: list[str]) -> str:
    """Replace the section's free variables in order, leaving all other bytes.

    Everything around the braces is invariant text - the ``## Statements to
    decide`` heading, the closing line about a path not listed - and it comes
    from the frame rather than from here, so the frame stays the specification.
    """
    out: list[str] = []
    cursor = 0
    for index, match in enumerate(PLACEHOLDER.finditer(section)):
        out.append(section[cursor:match.start()])
        out.append(values[index])
        cursor = match.end()
    out.append(section[cursor:])
    return "".join(out)


# --------------------------------------------------------------------------
# Items: statements in authored order, with stable ids
# --------------------------------------------------------------------------

def collect_items(evals_doc: dict, evals_path: Path) -> list[dict]:
    """Assign ``E1``, ``E2``, ... in authored order across the eval set.

    Evals in file order, assertions in authored order inside each eval. No
    reordering by interest, no grouping, no omission: a seat handed only the
    statements someone thought it could rule on has told you nothing.
    """
    evals = evals_doc.get("evals")
    if not isinstance(evals, list) or not evals:
        _refuse("schema_invalid", f"{evals_path}: `evals` is missing, empty, "
                                  f"or not an array")

    items: list[dict] = []
    for position, entry in enumerate(evals):
        if not isinstance(entry, dict):
            _refuse("schema_invalid",
                    f"{evals_path}: evals[{position}] is not an object")
        eval_id = entry.get("id", entry.get("eval_id"))
        if eval_id is None:
            _refuse("schema_invalid",
                    f"{evals_path}: evals[{position}] carries no `id`")
        assertions = entry.get("assertions", [])
        if not isinstance(assertions, list):
            _refuse("schema_invalid",
                    f"{evals_path}: evals[{position}].assertions is not an array")
        for statement in assertions:
            if not _is_text(statement):
                _refuse("schema_invalid",
                        f"{evals_path}: eval {eval_id} carries a blank or "
                        f"non-string assertion")
            if "\n" in statement or "\r" in statement:
                _refuse("statement_multiline",
                        f"eval {eval_id}: a statement carries a line break. The "
                        f"frame renders one statement per line under its id; "
                        f"rewriting it to fit would be altering it, which is "
                        f"the one thing this renderer may not do.")
            items.append({
                "id": f"E{len(items) + 1}",
                "eval_id": eval_id,
                "statement": statement,
            })
    if not items:
        _refuse("schema_invalid",
                f"{evals_path}: no eval carries an assertion, so there is "
                f"nothing for a seat to decide")
    return items


def render_statements(items: list[dict]) -> str:
    """One statement per line, prefixed by its id, verbatim and unmarked.

    No bolding, no reordering, no grouping, no "note that". The seat returns the
    id and never retypes the statement (constraint 2).
    """
    return "\n".join(f"{item['id']}: {item['statement']}" for item in items)


# --------------------------------------------------------------------------
# The material manifest
# --------------------------------------------------------------------------

def resolve_base(raw_base: str, root: Optional[Path], manifest_dir: Path) -> Path:
    candidate = Path(raw_base)
    if candidate.is_absolute():
        return candidate
    return (root if root is not None else manifest_dir) / candidate


def channel_paths(channel: dict, base: Path) -> list[Path]:
    """Resolve one channel against one item base.

    Containment beats link-detection: every hit is resolved and confirmed
    inside the resolved base rather than tested for link-ness, which misses
    junctions and hardlinks.
    """
    if channel.get("provides", "paths") != "paths":
        return []
    if channel.get("present", True) is False:
        return []

    base_resolved = base.resolve()

    def expand(patterns: list[str]) -> set[Path]:
        found: set[Path] = set()
        for pattern in patterns:
            if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
                _refuse("pattern_escapes_base",
                        f"channel {channel['id']!r} pattern {pattern!r} is "
                        f"absolute or climbs out of the base. Patterns are "
                        f"relative to an item base so that one channel means "
                        f"the same thing for every item.")
            for hit in base.glob(pattern):
                if not hit.is_file():
                    continue
                resolved = hit.resolve()
                if base_resolved != resolved and base_resolved not in resolved.parents:
                    _refuse("path_escapes_base",
                            f"channel {channel['id']!r} matched {hit}, which "
                            f"resolves to {resolved}, outside {base_resolved}")
                found.add(resolved)
        return found

    admitted = expand(channel.get("include", []))
    admitted -= expand(channel.get("exclude", []))
    return sorted(admitted)


def load_manifest(manifest: dict, manifest_path: Path, composition: dict,
                  items: list[dict]) -> dict:
    """Validate the manifest against the composition and resolve every channel.

    Every check here has the same shape: something the orchestrator could have
    got wrong becomes a typed refusal instead of a seat quietly receiving
    material its definition says it cannot see.
    """
    if manifest.get("schema") != MATERIAL_SCHEMA_ID:
        _refuse("schema_unrecognized",
                f"{manifest_path}: `schema` is {manifest.get('schema')!r}; this "
                f"renderer knows {MATERIAL_SCHEMA_ID!r}")

    root_raw = manifest.get("root")
    root = None
    if _is_text(root_raw):
        root = Path(root_raw)
        if not root.is_absolute():
            root = manifest_path.parent / root

    # ---- item bases --------------------------------------------------
    bindings = manifest.get("evals")
    if not isinstance(bindings, list) or not bindings:
        _refuse("schema_invalid", f"{manifest_path}: `evals` is missing, empty, "
                                  f"or not an array")
    base_by_eval: dict[Any, Path] = {}
    for position, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            _refuse("schema_invalid",
                    f"{manifest_path}: evals[{position}] is not an object")
        eval_id = binding.get("eval_id")
        raw_base = binding.get("base")
        if eval_id is None or not _is_text(raw_base):
            _refuse("schema_invalid",
                    f"{manifest_path}: evals[{position}] needs `eval_id` and a "
                    f"non-empty `base`")
        if eval_id in base_by_eval:
            _refuse("schema_invalid",
                    f"{manifest_path}: eval {eval_id} is bound twice")
        base = resolve_base(raw_base, root, manifest_path.parent)
        if not base.is_dir():
            _refuse("base_missing",
                    f"{manifest_path}: eval {eval_id} declares base {base}, "
                    f"which is not a directory")
        base_by_eval[eval_id] = base

    wanted = {item["eval_id"] for item in items}
    for eval_id in sorted(wanted - set(base_by_eval), key=repr):
        _refuse("eval_unmapped",
                f"eval {eval_id} contributes statements and the manifest gives "
                f"it no base. There is no default: a base guessed here is a "
                f"path set nobody declared.")
    for eval_id in sorted(set(base_by_eval) - wanted, key=repr):
        _refuse("eval_binding_unknown",
                f"the manifest binds eval {eval_id}, which the eval set does "
                f"not contain. The manifest and the eval set have drifted, and "
                f"the seat bindings cannot be trusted through that.")

    # ---- channels ----------------------------------------------------
    channels_raw = manifest.get("channels")
    if not isinstance(channels_raw, list) or not channels_raw:
        _refuse("schema_invalid", f"{manifest_path}: `channels` is missing, "
                                  f"empty, or not an array")
    channels: dict[str, dict] = {}
    for position, channel in enumerate(channels_raw):
        if not isinstance(channel, dict) or not _is_text(channel.get("id")):
            _refuse("channel_invalid",
                    f"{manifest_path}: channels[{position}] has no `id`")
        provides = channel.get("provides", "paths")
        if provides not in PROVIDES:
            _refuse("channel_invalid",
                    f"channel {channel['id']!r} declares provides="
                    f"{provides!r}; known: {', '.join(PROVIDES)}")
        if provides == "no-material" and not _is_text(channel.get("why")):
            _refuse("channel_invalid",
                    f"channel {channel['id']!r} hands over no file and gives no "
                    f"`why`. An entry bound to nothing has to say what it is "
                    f"standing in for, or it is indistinguishable from an "
                    f"entry nobody mapped.")
        for key in ("include", "exclude", "overlaps"):
            value = channel.get(key, [])
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                _refuse("channel_invalid",
                        f"channel {channel['id']!r}: `{key}` must be an array "
                        f"of strings")
        if provides == "paths" and channel.get("present", True) and not channel.get("include"):
            _refuse("channel_invalid",
                    f"channel {channel['id']!r} is declared present and lists no "
                    f"`include` pattern. Declare `present: false` if this run "
                    f"has no such channel; an empty include is not that "
                    f"statement.")
        if channel["id"] in channels:
            _refuse("channel_invalid",
                    f"{manifest_path}: channel {channel['id']!r} is defined twice")
        channels[channel["id"]] = channel

    # ---- seat bindings -----------------------------------------------
    seats = composition.get("seats")
    if not isinstance(seats, list) or not seats:
        _refuse("schema_invalid", "composition `seats` is missing, empty, or "
                                  "not an array")
    seat_names = []
    for seat in seats:
        if not isinstance(seat, dict) or not _is_text(seat.get("seat")):
            _refuse("schema_invalid", "a composition seat has no `seat` name")
        seat_names.append(seat["seat"])

    seat_bindings = manifest.get("seats")
    if not isinstance(seat_bindings, dict) or not seat_bindings:
        _refuse("schema_invalid",
                f"{manifest_path}: `seats` is missing, empty, or not an object")
    for name in seat_names:
        if name not in seat_bindings:
            _refuse("seat_unmapped",
                    f"the composition carries seat {name!r} and the manifest "
                    f"binds no material for it", seat=name)
    for name in seat_bindings:
        if name not in seat_names:
            _refuse("seat_binding_unknown",
                    f"the manifest binds seat {name!r}, which this composition "
                    f"does not contain", seat=name)

    warnings: list[dict] = []
    used_channels: set[str] = set()
    resolved_bindings: dict[str, list[dict]] = {}

    for seat in seats:
        name = seat["seat"]
        declared = seat.get("inputs")
        if not isinstance(declared, list) or not declared:
            _refuse("schema_invalid",
                    f"seat {name!r}: `inputs` is missing, empty, or not an "
                    f"array. A seat with no allowlist has no separation to "
                    f"make real.", seat=name)
        bound = seat_bindings[name]
        if not isinstance(bound, list):
            _refuse("schema_invalid",
                    f"{manifest_path}: seats[{name!r}] is not an array", seat=name)
        if len(bound) != len(declared):
            _refuse("entry_count_mismatch",
                    f"seat {name!r} declares {len(declared)} `inputs` entries "
                    f"and the manifest binds {len(bound)}. The binding is "
                    f"positional against the composition, so a count mismatch "
                    f"means every entry after the first gap is bound to the "
                    f"wrong sentence.", seat=name)

        entries: list[dict] = []
        for index, (entry_text, binding) in enumerate(zip(declared, bound)):
            if not isinstance(binding, dict):
                _refuse("schema_invalid",
                        f"seat {name!r}: binding {index} is not an object",
                        seat=name)
            quoted = binding.get("entry")
            if quoted != entry_text:
                _refuse("entry_text_drift",
                        f"seat {name!r} entry {index}: the manifest quotes\n"
                        f"    {quoted!r}\n"
                        f"and the composition says\n"
                        f"    {entry_text!r}\n"
                        f"The quoted text is the anti-drift check: a "
                        f"recomposition that rewords one sentence has to be "
                        f"re-bound rather than rendered against a stale map.",
                        seat=name)
            named = binding.get("channels")
            if not isinstance(named, list) or not named:
                _refuse("entry_unmapped",
                        f"seat {name!r} entry {index} names no channel. There "
                        f"is no fallback to 'give this seat everything' - that "
                        f"fallback is the defect this renderer closes.\n"
                        f"    entry: {entry_text}",
                        seat=name)
            for channel_id in named:
                if channel_id not in channels:
                    _refuse("unknown_channel",
                            f"seat {name!r} entry {index} names channel "
                            f"{channel_id!r}, which the manifest does not "
                            f"define", seat=name)
                used_channels.add(channel_id)
            if all(channels[c].get("provides", "paths") != "paths"
                   or channels[c].get("present", True) is False
                   for c in named):
                whys = [_no_material_why(channels[c]) for c in named]
                warnings.append(_finding(
                    "entry_carries_no_material",
                    f"entry {index} hands over no file: {'; '.join(whys)}",
                    seat=name))
            entries.append({"index": index, "entry": entry_text,
                            "channels": list(named)})
        resolved_bindings[name] = entries

    # ---- resolve every used channel against every item base ----------
    #
    # Resolution is per item, because a channel is a *kind* of material and an
    # item either has that kind or does not. A kind absent for one item is the
    # frame's "omit it silently"; a kind absent everywhere is a glob nobody
    # tested, and that is a refusal.
    resolution: dict[str, dict[str, list[Path]]] = {}
    for channel_id in sorted(used_channels):
        channel = channels[channel_id]
        per_item: dict[str, list[Path]] = {}
        for item in items:
            base = base_by_eval[item["eval_id"]]
            per_item[item["id"]] = channel_paths(channel, base)
        resolution[channel_id] = per_item
        if (channel.get("provides", "paths") == "paths"
                and channel.get("present", True)
                and not any(per_item.values())):
            _refuse("channel_empty",
                    f"channel {channel_id!r} is declared present for this run "
                    f"and matched no file under any item base. A channel that "
                    f"resolves to nothing everywhere is a pattern nobody "
                    f"tested; declare `present: false` if the channel really "
                    f"does not exist for this run.")

    # ---- undeclared overlap ------------------------------------------
    #
    # This is the check that catches the recorded leak by construction. A
    # deliverable channel written as ``outputs/**`` swallows the note channel
    # beside it, and the two sets then collide on exactly the files one seat is
    # meant not to see.
    for left, right in combinations(sorted(used_channels), 2):
        declared = (right in channels[left].get("overlaps", [])
                    or left in channels[right].get("overlaps", []))
        if declared:
            continue
        for item in items:
            shared = set(resolution[left][item["id"]]) & set(resolution[right][item["id"]])
            if shared:
                sample = ", ".join(str(p) for p in sorted(shared)[:3])
                _refuse("channel_overlap_undeclared",
                        f"channels {left!r} and {right!r} both resolve to "
                        f"{len(shared)} shared path(s) at {item['id']}: "
                        f"{sample}. An undeclared collision between two "
                        f"channels is how a file reaches a seat through a "
                        f"channel nobody meant to give it; declare it with "
                        f"`overlaps` if it is intended.")

    return {
        "root": root,
        "base_by_eval": base_by_eval,
        "channels": channels,
        "bindings": resolved_bindings,
        "resolution": resolution,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# Admission and the withheld record
# --------------------------------------------------------------------------

def admit(seat_name: str, entries: list[dict], items: list[dict],
          resolution: dict[str, dict[str, list[Path]]]) -> dict[str, list[Path]]:
    """Union this seat's entries into an admitted path set, per item."""
    admitted: dict[str, list[Path]] = {}
    for item in items:
        found: set[Path] = set()
        for entry in entries:
            for channel_id in entry["channels"]:
                found.update(resolution[channel_id][item["id"]])
        for path in found:
            for segment in path.parts:
                if segment.lower() in AUTHORSHIP_SEGMENTS:
                    _refuse("authorship_leak",
                            f"seat {seat_name!r} would be handed {path}, whose "
                            f"path names configuration {segment!r}. Which "
                            f"configuration produced the material is never a "
                            f"parameter; stage it under a neutral name before "
                            f"rendering.", seat=seat_name)
        admitted[item["id"]] = sorted(found)
    return admitted


def withhold(items: list[dict], base_by_eval: dict[Any, Path],
             admitted: dict[str, list[Path]]) -> tuple[dict[str, list[Path]], bool]:
    """Everything under the item bases that this seat was *not* handed.

    This is what makes isolation checkable from the record rather than from
    anyone's word: an auditor reads the withheld list and sees, by name, the
    files a seat could not have opened.
    """
    withheld: dict[str, list[Path]] = {}
    truncated = False
    for item in items:
        base = base_by_eval[item["eval_id"]].resolve()
        seen: list[Path] = []
        for path in base.rglob("*"):
            if len(seen) >= WITHHELD_FILE_CAP:
                truncated = True
                break
            if path.is_file():
                seen.append(path.resolve())
        given = set(admitted[item["id"]])
        withheld[item["id"]] = sorted(p for p in seen if p not in given)
    return withheld, truncated


def render_material(items: list[dict], admitted: dict[str, list[Path]]) -> str:
    """The material block: item id, then the absolute path of each file.

    Individual files, never a directory - a directory path hands over whatever
    is inside it, which is precisely how the recorded runs leaked the notes.

    No channel labels: a channel id comes from the characterization, and no seat
    sees the characterization (constraint 3). No sentence about the allowlist
    either. What is here is what exists for this seat; the frame's own closing
    line says the rest, as fact rather than as instruction.
    """
    blocks: list[str] = []
    for item in items:
        paths = admitted[item["id"]]
        if not paths:
            continue
        lines = [item["id"]]
        lines.extend(os.fspath(path) for path in paths)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------
# The render
# --------------------------------------------------------------------------

def render(frame_sections: dict[str, str], composition: dict, items: list[dict],
           material: dict) -> tuple[list[dict], list[dict]]:
    """Build one prompt per seat. Returns ``(seat_records, warnings)``."""
    statements = render_statements(items)
    warnings = list(material["warnings"])
    records: list[dict] = []

    for seat in composition["seats"]:
        name = seat["seat"]
        entries = material["bindings"][name]
        admitted = admit(name, entries, items, material["resolution"])

        if not any(admitted.values()):
            _refuse("seat_admits_nothing",
                    f"seat {name!r} was admitted no path at all. A seat with "
                    f"nothing to read cannot return a verdict, and rendering it "
                    f"anyway produces an abstention that looks like a finding "
                    f"about the artifact.", seat=name)

        for item in items:
            if not admitted[item["id"]]:
                warnings.append(_finding(
                    "item_without_material",
                    f"{item['id']} has no admitted path for this seat",
                    seat=name))

        withheld, truncated = withhold(items, material["base_by_eval"], admitted)
        if truncated:
            warnings.append(_finding(
                "withheld_truncated",
                f"an item base held more than {WITHHELD_FILE_CAP} files; the "
                f"withheld record is partial", seat=name))
        if not any(withheld.values()):
            warnings.append(_finding(
                "seat_sees_everything",
                "every file under every item base was admitted, so this seat's "
                "`inputs` allowlist excluded nothing. That is a legitimate "
                "composition and it is also what the defective hand-render "
                "looked like, so it is stated rather than assumed.", seat=name))

        # <definition>: the seat object verbatim, including blind_to and its
        # anchors. Round-tripped rather than trusted - a definition that does
        # not parse back to the composition's object is a definition somebody
        # edited at render time, which the filling rules forbid outright.
        definition_json = json.dumps(seat, indent=2, ensure_ascii=False)
        try:
            if json.loads(definition_json) != seat:
                raise ValueError("round trip differs")
        except (json.JSONDecodeError, ValueError) as exc:
            _refuse("definition_altered",
                    f"seat {name!r}: the rendered definition does not parse "
                    f"back to the composition's object ({exc})", seat=name)

        sections = {
            "identity": frame_sections["identity"],
            "definition": fill(frame_sections["definition"], [definition_json]),
            "evidence": fill(frame_sections["evidence"],
                             [statements, render_material(items, admitted)]),
            "output_schema": frame_sections["output_schema"],
        }
        prompt = "\n\n".join(sections[key] for key in SECTION_ORDER) + "\n"

        # Character-for-character, checked against what was actually written
        # rather than against what the writer intended: observe the property,
        # not a proxy for it.
        for item in items:
            expected = f"\n{item['id']}: {item['statement']}\n"
            if expected not in prompt:
                _refuse("statement_altered",
                        f"seat {name!r}: {item['id']} does not appear in the "
                        f"rendered prompt as its own unmarked line carrying the "
                        f"authored bytes", seat=name)

        records.append({
            "seat": name,
            "prompt": prompt,
            "sections": sections,
            "entries": entries,
            "admitted": admitted,
            "withheld": withheld,
        })

    # Byte-identical across every seat, asserted rather than documented.
    for key in INVARIANT_SECTIONS:
        digests = {sha256_text(record["sections"][key]) for record in records}
        if len(digests) != 1:
            _refuse("invariant_section_differs",
                    f"<{key}> differs across seats ({len(digests)} distinct "
                    f"digests). It is invariant text and a seat reading a "
                    f"different copy of it is reading a different frame.")

    evidence_digests = [sha256_text(r["sections"]["evidence"]) for r in records]
    if len(set(evidence_digests)) != len(evidence_digests):
        same = [r["seat"] for r, d in zip(records, evidence_digests)
                if evidence_digests.count(d) > 1]
        warnings.append(_finding(
            "evidence_blocks_identical",
            f"seats {', '.join(same)} received the same evidence block. Their "
            f"allowlists admit the same paths, which may be correct - but an "
            f"identical block across *every* seat is the defect this renderer "
            f"was written to close, so it is reported rather than assumed."))

    return records, warnings


def build_report(records: list[dict], items: list[dict], material: dict,
                 sources: dict, out_dir: Path, warnings: list[dict]) -> dict:
    """The record an auditor checks isolation from.

    Deterministic on purpose - no timestamp, no ordering by anything but the
    authored order - so two renders of one input are byte-identical and a diff
    between them means something changed.
    """
    channel_rows = []
    for channel_id in sorted(material["resolution"]):
        channel = material["channels"][channel_id]
        per_item = material["resolution"][channel_id]
        channel_rows.append({
            "id": channel_id,
            "provides": channel.get("provides", "paths"),
            "present": channel.get("present", True),
            "why": channel.get("why"),
            "overlaps": channel.get("overlaps", []),
            "paths_total": sum(len(v) for v in per_item.values()),
            "per_item": {item_id: len(paths) for item_id, paths in per_item.items()},
        })

    seat_rows = []
    for record in records:
        seat_rows.append({
            "seat": record["seat"],
            "prompt": {
                "path": os.fspath(out_dir / f"seat_{record['seat']}.md"),
                "sha256": sha256_text(record["prompt"]),
                "bytes": len(record["prompt"].encode("utf-8")),
            },
            "sections_sha256": {key: sha256_text(record["sections"][key])
                                for key in SECTION_ORDER},
            "entries": record["entries"],
            "admitted": {item_id: [os.fspath(p) for p in paths]
                         for item_id, paths in record["admitted"].items()},
            "withheld": {item_id: [os.fspath(p) for p in paths]
                         for item_id, paths in record["withheld"].items()},
            "admitted_total": sum(len(v) for v in record["admitted"].values()),
            "withheld_total": sum(len(v) for v in record["withheld"].values()),
        })

    evidence_digests = {row["seat"]: row["sections_sha256"]["evidence"]
                        for row in seat_rows}
    return {
        "schema": REPORT_SCHEMA_ID,
        "ok": True,
        "sources": sources,
        "out_dir": os.fspath(out_dir),
        "items": [{
            "id": item["id"],
            "eval_id": item["eval_id"],
            "statement_sha256": sha256_text(item["statement"]),
            "base": os.fspath(material["base_by_eval"][item["eval_id"]]),
        } for item in items],
        "channels": channel_rows,
        "seats": seat_rows,
        "invariants": {
            "identity_sha256": seat_rows[0]["sections_sha256"]["identity"],
            "output_schema_sha256": seat_rows[0]["sections_sha256"]["output_schema"],
            "identity_identical_across_seats": True,
            "output_schema_identical_across_seats": True,
            "evidence_sha256": evidence_digests,
            "evidence_distinct": len(set(evidence_digests.values())),
        },
        "refusals": [],
        "warnings": warnings,
        "counts": {"refusals": 0, "warnings": len(warnings),
                   "seats": len(seat_rows), "items": len(items)},
        "reason_index": {"refusals": REFUSAL_REASONS, "warnings": WARNING_REASONS},
    }


# --------------------------------------------------------------------------
# Manifest template
# --------------------------------------------------------------------------

def manifest_template(composition: dict, items: list[dict],
                      evals_doc: dict) -> dict:
    """A skeleton the orchestrator fills in.

    The entry texts are copied out of the composition so nobody re-types them -
    a re-typed sentence fails ``entry_text_drift`` and the fix is a diff nobody
    should have to read. The channel lists come back empty on purpose: the
    binding is the security-relevant judgment and this script will not make it.
    An unfilled template refuses.
    """
    source_dir_by_eval: dict[Any, str] = {}
    for entry in evals_doc.get("evals", []):
        if isinstance(entry, dict):
            eval_id = entry.get("id", entry.get("eval_id"))
            if _is_text(entry.get("_source_dir")):
                source_dir_by_eval[eval_id] = entry["_source_dir"]

    seen: list[Any] = []
    for item in items:
        if item["eval_id"] not in seen:
            seen.append(item["eval_id"])

    return {
        "schema": MATERIAL_SCHEMA_ID,
        "_README": [
            "Fill every `channels[].include` and every `seats[][].channels`.",
            "A channel is a kind of material, resolved per item base with a "
            "relative glob. Two channels that resolve to a shared path must "
            "declare it in `overlaps` - an undeclared collision is how a file "
            "reaches a seat through a channel nobody meant to give it.",
            "`provides` is one of: paths (default), statements, no-material. "
            "The last two exist because a composer writes `inputs` entries "
            "that name no file; both are recorded and warned about.",
            "`present: false` says this run has no such channel. It resolves "
            "to nothing and is omitted silently, per the frame.",
            "Do not edit `entry` - it is quoted from the composition and is "
            "checked character-for-character at render time.",
        ],
        "root": None,
        "evals": [{"eval_id": eval_id,
                   "base": source_dir_by_eval.get(eval_id)}
                  for eval_id in seen],
        "channels": [{"id": "CHANGE_ME", "include": [], "exclude": [],
                      "overlaps": []}],
        "seats": {
            seat["seat"]: [{"entry": text, "channels": []}
                           for text in seat.get("inputs", [])]
            for seat in composition.get("seats", [])
            if isinstance(seat, dict) and _is_text(seat.get("seat"))
        },
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _print_report(report: dict, stream) -> None:
    print(f"frame         {report['sources']['frame']['path']}", file=stream)
    print(f"composition   {report['sources']['composition']['path']}", file=stream)
    print(f"evals         {report['sources']['evals']['path']}", file=stream)
    print(f"material      {report['sources']['material']['path']}", file=stream)
    print(f"out           {report['out_dir']}", file=stream)
    print("", file=stream)

    for row in report["seats"]:
        print(f"  {row['seat']:<14} admitted {row['admitted_total']:>4}  "
              f"withheld {row['withheld_total']:>4}  "
              f"evidence {row['sections_sha256']['evidence'][:12]}",
              file=stream)
    invariants = report["invariants"]
    print("", file=stream)
    print(f"  identity      {invariants['identity_sha256'][:12]}  "
          f"(identical across every seat)", file=stream)
    print(f"  output_schema {invariants['output_schema_sha256'][:12]}  "
          f"(identical across every seat)", file=stream)
    print(f"  evidence      {invariants['evidence_distinct']} distinct block(s) "
          f"across {report['counts']['seats']} seat(s)", file=stream)
    print("", file=stream)

    for finding in report["warnings"]:
        where = f" [{finding['seat']}]" if finding["seat"] else ""
        print(f"WARN   {finding['reason']}{where}", file=stream)
        print(f"    ! {finding['detail']}", file=stream)
    if report["warnings"]:
        print("", file=stream)

    print(f"Rendered {report['counts']['seats']} seat prompt(s) over "
          f"{report['counts']['items']} statement(s). What each seat may read "
          f"is now a fact about which paths it was handed; the render report "
          f"names, per seat, every path admitted and every path withheld.",
          file=stream)


def _emit_refusal(findings: list[dict], human, as_json: bool, code: int) -> int:
    for finding in findings:
        where = f" [{finding['seat']}]" if finding["seat"] else ""
        print(f"REFUSE {finding['reason']}{where}", file=human)
        print(f"    - {finding['detail']}", file=human)
    print("", file=human)
    print("Nothing was written. A renderer that falls back to handing every "
          "seat everything reproduces the defect it exists to close, so it "
          "refuses instead.", file=human)
    if as_json:
        json.dump({"schema": REPORT_SCHEMA_ID, "ok": False,
                   "refusals": findings, "warnings": [],
                   "counts": {"refusals": len(findings), "warnings": 0},
                   "reason_index": {"refusals": REFUSAL_REASONS,
                                    "warnings": WARNING_REASONS}},
                  sys.stdout, indent=2)
        print()
    return code


def main(argv=None) -> int:
    configure_console()

    parser = argparse.ArgumentParser(
        prog="python -m scripts.render_seats",
        description=(
            "Render one panel seat prompt per seat from the invariant frame, "
            "giving each seat exactly the material its own `inputs` allowlist "
            "admits and nothing beyond it."
        ),
    )
    parser.add_argument("composition", type=Path, nargs="?",
                        help="composition.json written by the composer")
    parser.add_argument("--evals", type=Path, default=None,
                        help="the eval set whose assertions become the "
                             "statements to decide")
    parser.add_argument("--material", type=Path, default=None,
                        help="material manifest binding each seat's `inputs` "
                             "entries to concrete paths")
    parser.add_argument("--out", type=Path, default=None,
                        help="directory to write seat_<name>.md and "
                             "render_manifest.json into")
    parser.add_argument("--frame", type=Path, default=None,
                        help="seat-frame.md; defaults to this bundle's "
                             "agents/panel/seat-frame.md")
    parser.add_argument("--emit-manifest-template", type=Path, default=None,
                        metavar="PATH",
                        help="write a material-manifest skeleton for this "
                             "composition and eval set, then exit")
    parser.add_argument("--json", action="store_true",
                        help="emit the machine-readable report on stdout "
                             "alone; all human-readable output goes to stderr")
    parser.add_argument("--list-reasons", action="store_true",
                        help="print every typed refusal and warning this "
                             "renderer can emit, then exit")
    args = parser.parse_args(argv)

    human = sys.stderr if args.json else sys.stdout

    if args.list_reasons:
        print("Refusals (exit 1, or 2 when a file could not be read):", file=human)
        for reason, why in REFUSAL_REASONS.items():
            print(f"  {reason:<28} {why}", file=human)
        print("\nWarnings (do not gate):", file=human)
        for reason, why in WARNING_REASONS.items():
            print(f"  {reason:<28} {why}", file=human)
        if args.json:
            json.dump({"refusals": REFUSAL_REASONS, "warnings": WARNING_REASONS},
                      sys.stdout, indent=2)
            print()
        return 0

    if args.composition is None or args.evals is None:
        parser.print_usage(file=human)
        print("Error: a composition path and --evals are required.", file=human)
        return 2

    frame_path = args.frame or (Path(__file__).resolve().parent.parent
                                / "agents" / "panel" / "seat-frame.md")

    composition, error = load_json(args.composition)
    if error is not None:
        return _emit_refusal([_finding("composition_unreadable", error)],
                             human, args.json, 2)
    evals_doc, error = load_json(args.evals)
    if error is not None:
        return _emit_refusal([_finding("evals_unreadable", error)],
                             human, args.json, 2)

    if composition.get("schema") != COMPOSITION_SCHEMA_ID:
        return _emit_refusal([_finding(
            "schema_unrecognized",
            f"{args.composition}: `schema` is {composition.get('schema')!r}; "
            f"this renderer knows {COMPOSITION_SCHEMA_ID!r}")],
            human, args.json, 1)

    try:
        items = collect_items(evals_doc, args.evals)
    except Refusal as refusal:
        return _emit_refusal(refusal.findings, human, args.json, 1)

    if args.emit_manifest_template is not None:
        template = manifest_template(composition, items, evals_doc)
        try:
            args.emit_manifest_template.parent.mkdir(parents=True, exist_ok=True)
            write_text(args.emit_manifest_template,
                       json.dumps(template, indent=2, ensure_ascii=False) + "\n")
        except OSError as exc:
            return _emit_refusal([_finding("out_dir_unwritable", str(exc))],
                                 human, args.json, 2)
        print(f"Wrote a manifest skeleton to {args.emit_manifest_template}.",
              file=human)
        print("Fill in every `include` and every `channels` list. It refuses "
              "as written: an unfilled binding is `entry_unmapped`, which is "
              "the point.", file=human)
        return 0

    if args.material is None or args.out is None:
        parser.print_usage(file=human)
        print("Error: --material and --out are required to render.", file=human)
        return 2

    frame_text, error = read_text(frame_path)
    if error is not None:
        return _emit_refusal([_finding("frame_unreadable", error)],
                             human, args.json, 2)
    manifest_doc, error = load_json(args.material)
    if error is not None:
        return _emit_refusal([_finding("manifest_unreadable", error)],
                             human, args.json, 2)

    try:
        frame_sections = parse_frame(frame_text)
        material = load_manifest(manifest_doc, args.material, composition, items)
        records, warnings = render(frame_sections, composition, items, material)
    except Refusal as refusal:
        return _emit_refusal(refusal.findings, human, args.json, 1)

    sources = {
        "frame": {"path": os.fspath(frame_path), "sha256": sha256_file(frame_path)},
        "composition": {"path": os.fspath(args.composition),
                        "sha256": sha256_file(args.composition)},
        "evals": {"path": os.fspath(args.evals),
                  "sha256": sha256_file(args.evals)},
        "material": {"path": os.fspath(args.material),
                     "sha256": sha256_file(args.material)},
    }
    report = build_report(records, items, material, sources, args.out, warnings)

    try:
        args.out.mkdir(parents=True, exist_ok=True)
        for record in records:
            write_text(args.out / f"seat_{record['seat']}.md", record["prompt"])
        write_text(args.out / "render_manifest.json",
                   json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    except OSError as exc:
        return _emit_refusal([_finding("out_dir_unwritable", str(exc))],
                             human, args.json, 2)

    _print_report(report, human)
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
