#!/usr/bin/env python3
"""
Instantiation gates for a composed judge panel, run before any seat is spawned.

Why this exists as code rather than as prose. A composed cover has to be shown
to discriminate *before* it judges anything load-bearing: no seat's anchors may
be all-pass, all-fail, or all-abstain; the seats must cover the characterized
domain; overlapping seats must declare how they glue; every
seat must have both a way to fail and an abstention path. Each of those is a
sentence anyone could agree with while shipping a composition that violates it,
because a gate written as prose is a gate that can be reasoned around - and the
party doing the reasoning is the one whose composition is being gated. So the
gates live here, deterministic and zero-model, and they refuse with a typed
reason and a non-zero exit.

    A seat that cannot fire on its own anchors is a blind instrument, and a
    blind instrument's pass is noise.

Two gates beyond the four above, both serving "ship the composer, never the
cast":

  * `provenance_missing` - a composition must carry the skill it was composed
    for, when, and the SHA-256 of the characterization it was composed from.
    That is what makes a stored composition legible as a *record* of one run
    rather than a roster a later run could select from.

  * `characterization_mismatch` / `facets_trimmed` - with --characterization,
    the digest is recomputed and the embedded facet copy is checked against the
    characterization's own. Coverage is then checked against the
    characterization, not against the composition's copy of it. Without that
    pair, coverage is trivially satisfiable by deleting the facets no seat
    covers, which turns the coverage gate into a formality.

Usage:
    python -m scripts.gate_panel <composition.json> \\
        [--characterization <characterization.json>] [--json]

Exit codes:
    0  every gate passed (warnings do not gate)
    1  at least one typed refusal
    2  a file could not be read, parsed, or was not supplied

With --json the machine-readable report goes to stdout *alone*; every
human-readable line goes to stderr.

Verdict vocabulary. Anchors are written in the grading artifact's own tokens -
`pass` and `fail` - so that a seat's return needs no translation on its way into
`expectations[].verdict`; a translation layer between a seat verdict and the
artifact verdict would be a second representation of one fact, which is exactly
the drift surface one shared vocabulary removes. The house tokens `clean` and
`drawback` are accepted as aliases and normalized, because the same composer
schema is used by panels whose records speak that vocabulary. Anything else is
a typed refusal
rather than a guess.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from itertools import combinations
from pathlib import Path
from typing import Any, Optional

from scripts.utils import configure_console

# --------------------------------------------------------------------------
# The invariants. None of these adapt per domain - that is what makes them
# checkable without a model.
# --------------------------------------------------------------------------

SCHEMA_ID = "panel.composition/1"

#: The belief-facing seats. The roles are fixed; the composer fills them.
REQUIRED_SEATS = ("grounding", "coherence", "corroboration")

#: Ten anchors per seat, five a side. Ten obvious cases calibrate nothing, so
#: the count is a floor on the evidence that the seat discriminates, not a
#: stylistic preference.
ANCHOR_TOTAL = 10
ANCHOR_PER_SIDE = 5

#: Normalization, not tolerance: every token outside this map is refused.
VERDICT_ALIASES = {
    "pass": "pass",
    "clean": "pass",
    "fail": "fail",
    "drawback": "fail",
    "abstain": "abstain",
}

FACET_KINDS = ("claim_shape", "evidence_channel", "hardness")

ORIENTATION_KEYS = ("evidence_standard", "uncertainty_posture",
                    "abstention_boundary")

SEAT_STRING_FIELDS = ("judge", "purpose", "blind_to")
SEAT_LIST_FIELDS = ("claim_modes", "select", "covers", "inputs")

#: Below this many characters a field is present but says nothing a seat could
#: be held to. Warned, never refused - a threshold on prose length is a proxy,
#: and a false refusal is the failure class this codebase exists to close.
THIN_FIELD_CHARS = 60
THIN_ORIENTATION_CHARS = 40

#: Anchors are constructed situations. A concrete address is the signature of a
#: real case that was copied instead of improvised.
_ADDRESS_RE = re.compile(
    r"[A-Za-z]:[\\/]"
    r"|(?<![\w.])/(?:home|Users|tmp|var|mnt|opt|etc)/"
    r"|\bhttps?://"
    r"|[\w\-]+\.(?:csv|tsv|json|jsonl|md|xlsx|xlsm|docx|pptx|pdf|html|htm"
    r"|py|js|ts|yaml|yml|txt|gif|png|jpg|zip)\b"
)

#: Every typed refusal this script can emit, with why it exists. Emitted in the
#: --json report so a machine consumer can enumerate the gate surface without
#: reading this file, and printed by --list-reasons.
REFUSAL_REASONS = {
    "composition_unreadable":
        "the composition file could not be read, decoded, or parsed",
    "characterization_unreadable":
        "the characterization file could not be read, decoded, or parsed",
    "schema_invalid":
        "a required key is missing or holds the wrong type",
    "provenance_missing":
        "the composition does not pin the skill, the time, and the "
        "characterization digest it was composed from",
    "characterization_mismatch":
        "the supplied characterization does not hash to the digest the "
        "composition was composed against",
    "facets_trimmed":
        "the composition's embedded facet copy omits facets the "
        "characterization carries",
    "seat_missing":
        "a required belief-facing seat is absent",
    "seat_duplicate":
        "a seat role appears more than once",
    "seat_unknown":
        "a seat role outside the belief-facing set is present",
    "anchor_count":
        "a seat's anchor set is not the required size",
    "anchor_balance":
        "a seat's anchors are not five a side",
    "anchor_degenerate":
        "a seat's anchors are all-pass, all-fail, or all-abstain - the seat "
        "cannot be shown to discriminate",
    "anchor_verdict_unknown":
        "an anchor carries a verdict token outside the accepted vocabulary",
    "anchor_duplicate":
        "a seat's anchor set repeats a case, so it measures less than its "
        "count claims",
    "anchor_empty":
        "an anchor is missing its situation or its expected side",
    "coverage_gap":
        "a characterized facet is claimed by no seat",
    "overlap_undeclared":
        "two seats share ground with no gluing rule naming it",
    "gluing_rule_invalid":
        "a gluing rule is malformed or names seats that do not exist",
    "no_fail_path":
        "a seat has no closed taxonomy, so it has no way to fail",
    "no_abstain_path":
        "a seat has no abstention boundary, so 'cannot tell' has nowhere to go",
    "blind_spec_missing":
        "a seat does not state what it is blind to",
}

WARNING_REASONS = {
    "characterization_unchecked":
        "no --characterization was supplied, so the digest and the facet copy "
        "were taken on trust",
    "schema_unrecognized":
        "the composition declares a schema id this gate does not know",
    "covers_unknown_facet":
        "a seat claims a facet id the characterization does not carry",
    "gluing_rule_unused":
        "a gluing rule names a pair of seats that do not actually overlap",
    "blind_spec_thin":
        "a seat's blind_to is present but too short to bind anything",
    "orientation_thin":
        "an orientation field is present but too short to bind anything",
    "facet_kind_unknown":
        "a facet declares a kind outside the characterizer's enum",
    "anchor_carries_address":
        "an anchor names a concrete path, URL, or filename, which is the "
        "signature of a real case rather than a constructed one",
    "anchor_from_record":
        "an anchor's situation appears verbatim in the characterization, so it "
        "is a real case rather than an improvised one",
}


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

def _finding(reason: str, detail: str, seat: Optional[str] = None) -> dict:
    return {"reason": reason, "seat": seat, "detail": detail}


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_list_of_text(value: Any) -> bool:
    return (isinstance(value, list) and len(value) > 0
            and all(_is_text(item) for item in value))


# --------------------------------------------------------------------------
# Loading. Encoding is always explicit, and UnicodeDecodeError is not caught
# by (json.JSONDecodeError, OSError).
# --------------------------------------------------------------------------

def load_document(path: Path) -> tuple[Optional[dict], Optional[str]]:
    """Return ``(document, error)``. JSON always; YAML when PyYAML is present.

    The canonical wire format is JSON, matching every other artifact in this
    bundle. YAML is accepted because the house judge schema is written that way
    and re-typing a composition to satisfy a reader is a corruption channel.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, UnicodeError) as exc:
        return None, f"{path}: {exc}"

    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # noqa: PLC0415 - optional, and only on this path
        except ImportError:
            return None, (
                f"{path}: YAML input needs PyYAML "
                f"(python -m pip install -r requirements.txt), or supply the "
                f"composition as .json"
            )
        try:
            document = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            return None, f"{path}: {exc}"
    else:
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            return None, f"{path}: {exc}"

    if not isinstance(document, dict):
        return None, f"{path}: top level is {type(document).__name__}, not an object"
    return document, None


def sha256_file(path: Path) -> Optional[str]:
    """SHA-256 of *path*'s bytes, or ``None`` if it cannot be read.

    Hashed as bytes, never as decoded text: a digest over a decoded string
    would change with the reader's newline handling and stop being a digest.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


# --------------------------------------------------------------------------
# The gates
# --------------------------------------------------------------------------

def check_provenance(composition: dict) -> list[dict]:
    provenance = composition.get("provenance")
    if not isinstance(provenance, dict):
        return [_finding(
            "provenance_missing",
            "no `provenance` object. A composition without provenance cannot "
            "be told from a roster, and a roster is a cast a later run could "
            "select from rather than a record of the run that composed it.",
        )]

    missing = [key for key in ("skill", "composed_at", "characterization_sha256")
               if not _is_text(provenance.get(key))]
    if missing:
        return [_finding(
            "provenance_missing",
            f"`provenance` is missing or blank at: {', '.join(missing)}",
        )]
    return []


def check_digest(composition: dict, characterization_path: Optional[Path]
                 ) -> list[dict]:
    if characterization_path is None:
        return []
    provenance = composition.get("provenance")
    if not isinstance(provenance, dict):
        return []          # already reported by check_provenance
    declared = provenance.get("characterization_sha256")
    if not _is_text(declared):
        return []          # already reported by check_provenance

    actual = sha256_file(characterization_path)
    if actual is None:
        return [_finding(
            "characterization_unreadable",
            f"{characterization_path}: could not be read for hashing",
        )]
    if actual.lower() != declared.strip().lower():
        return [_finding(
            "characterization_mismatch",
            f"composition was composed against {declared.strip().lower()}; "
            f"{characterization_path} hashes to {actual}. Either the "
            f"characterization changed after composition, or this composition "
            f"belongs to a different domain and is being reused as a cast.",
        )]
    return []


def _facet_ids(document: dict, key_path: tuple[str, ...]) -> tuple[list[str], list[dict]]:
    """Pull facet ids out of *document*, accumulating structural findings."""
    node: Any = document
    for key in key_path:
        node = node.get(key) if isinstance(node, dict) else None
    where = ".".join(key_path)

    if not isinstance(node, list):
        return [], [_finding("schema_invalid", f"`{where}` is not an array")]

    ids: list[str] = []
    findings: list[dict] = []
    for index, facet in enumerate(node):
        if not isinstance(facet, dict):
            findings.append(_finding(
                "schema_invalid", f"`{where}[{index}]` is not an object"))
            continue
        facet_id = facet.get("id")
        if not _is_text(facet_id):
            findings.append(_finding(
                "schema_invalid", f"`{where}[{index}]` has no `id`"))
            continue
        ids.append(facet_id)
        if facet.get("kind") not in FACET_KINDS:
            findings.append(_finding(
                "facet_kind_unknown",
                f"`{where}[{index}]` ({facet_id}) declares kind "
                f"{facet.get('kind')!r}; expected one of "
                f"{', '.join(FACET_KINDS)}",
            ))
    return ids, findings


def check_seat_roster(seats: list[Any]) -> list[dict]:
    findings: list[dict] = []
    seen: dict[str, int] = {}
    for index, seat in enumerate(seats):
        if not isinstance(seat, dict):
            findings.append(_finding(
                "schema_invalid", f"`seats[{index}]` is not an object"))
            continue
        role = seat.get("seat")
        if not _is_text(role):
            findings.append(_finding(
                "schema_invalid", f"`seats[{index}]` has no `seat` role"))
            continue
        seen[role] = seen.get(role, 0) + 1

    for role, count in seen.items():
        if role not in REQUIRED_SEATS:
            findings.append(_finding(
                "seat_unknown",
                f"seat role {role!r} is outside the belief-facing set "
                f"({', '.join(REQUIRED_SEATS)})", seat=role))
        elif count > 1:
            findings.append(_finding(
                "seat_duplicate",
                f"seat role {role!r} appears {count} times", seat=role))

    for role in REQUIRED_SEATS:
        if role not in seen:
            findings.append(_finding(
                "seat_missing",
                f"no seat fills the {role} role. Its question then goes "
                f"unasked and the items it would have ruled on pass through "
                f"the panel unexamined.", seat=role))
    return findings


def check_seat_shape(seat: dict, role: str) -> list[dict]:
    findings: list[dict] = []

    for field in SEAT_STRING_FIELDS:
        if not _is_text(seat.get(field)):
            if field == "blind_to":
                findings.append(_finding(
                    "blind_spec_missing",
                    "`blind_to` is missing or blank. An unstated blindness is "
                    "a seat free to answer three questions and report one "
                    "verdict, and the seats stop being separable.", seat=role))
            else:
                findings.append(_finding(
                    "schema_invalid", f"`{field}` is missing or blank",
                    seat=role))
        elif field == "blind_to" and len(seat[field].strip()) < THIN_FIELD_CHARS:
            findings.append(_finding(
                "blind_spec_thin",
                f"`blind_to` is {len(seat[field].strip())} characters; it "
                f"names too little to hold the seat to", seat=role))

    for field in SEAT_LIST_FIELDS:
        if not _is_list_of_text(seat.get(field)):
            findings.append(_finding(
                "schema_invalid",
                f"`{field}` must be a non-empty array of non-empty strings",
                seat=role))

    orientation = seat.get("orientation")
    if not isinstance(orientation, dict):
        findings.append(_finding(
            "schema_invalid", "`orientation` is missing or not an object",
            seat=role))
        findings.append(_finding(
            "no_abstain_path",
            "no `orientation`, so no abstention boundary. 'Cannot tell' then "
            "has nowhere to go but `fail`, which is the defect this panel "
            "replaces.", seat=role))
    else:
        for key in ORIENTATION_KEYS:
            value = orientation.get(key)
            if not _is_text(value):
                if key == "abstention_boundary":
                    findings.append(_finding(
                        "no_abstain_path",
                        "`orientation.abstention_boundary` is missing or "
                        "blank. A seat with no abstention path converts "
                        "'nobody could check this' into 'this is false'.",
                        seat=role))
                else:
                    findings.append(_finding(
                        "schema_invalid",
                        f"`orientation.{key}` is missing or blank", seat=role))
            elif len(value.strip()) < THIN_ORIENTATION_CHARS:
                findings.append(_finding(
                    "orientation_thin",
                    f"`orientation.{key}` is {len(value.strip())} characters; "
                    f"it states too little to bind a verdict", seat=role))

    taxonomy = seat.get("taxonomy")
    if not isinstance(taxonomy, dict) or not taxonomy:
        findings.append(_finding(
            "no_fail_path",
            "`taxonomy` is missing or empty, so this seat has no class to "
            "cite and therefore no way to fail. A judge that cannot fail is "
            "not a judge.", seat=role))
    else:
        blank = [name for name, condition in taxonomy.items()
                 if not _is_text(condition)]
        if blank:
            findings.append(_finding(
                "schema_invalid",
                f"taxonomy classes with no stated condition: "
                f"{', '.join(sorted(blank))}", seat=role))
        if len(blank) == len(taxonomy):
            findings.append(_finding(
                "no_fail_path",
                "every taxonomy class is empty, so no failure can be sorted "
                "into one", seat=role))

    return findings


def check_anchors(seat: dict, role: str,
                  characterization_blob: Optional[str]) -> tuple[list[dict], dict]:
    """Validity gate. Returns ``(findings, tally)``."""
    findings: list[dict] = []
    tally = {"pass": 0, "fail": 0, "abstain": 0, "total": 0}

    anchors = seat.get("anchors")
    if not isinstance(anchors, list):
        findings.append(_finding(
            "schema_invalid", "`anchors` is missing or not an array", seat=role))
        return findings, tally

    tally["total"] = len(anchors)
    if len(anchors) != ANCHOR_TOTAL:
        findings.append(_finding(
            "anchor_count",
            f"{len(anchors)} anchors; the anchor set is fixed at "
            f"{ANCHOR_TOTAL}, {ANCHOR_PER_SIDE} a side", seat=role))

    seen_inputs: dict[str, int] = {}
    for index, anchor in enumerate(anchors):
        label = f"anchors[{index}]"
        if not isinstance(anchor, dict):
            findings.append(_finding(
                "anchor_empty", f"{label} is not an object", seat=role))
            continue

        situation = anchor.get("input")
        if not _is_text(situation):
            findings.append(_finding(
                "anchor_empty", f"{label} has no `input` situation", seat=role))
        else:
            key = " ".join(situation.split()).lower()
            if key in seen_inputs:
                findings.append(_finding(
                    "anchor_duplicate",
                    f"{label} repeats the situation at "
                    f"anchors[{seen_inputs[key]}]", seat=role))
            else:
                seen_inputs[key] = index

            hit = _ADDRESS_RE.search(situation)
            if hit:
                findings.append(_finding(
                    "anchor_carries_address",
                    f"{label} contains {hit.group(0)!r}", seat=role))
            if (characterization_blob is not None and len(key) >= 40
                    and key in characterization_blob):
                findings.append(_finding(
                    "anchor_from_record",
                    f"{label} appears verbatim in the characterization",
                    seat=role))

        expected = anchor.get("expected")
        normalized = (VERDICT_ALIASES.get(expected.strip().lower())
                      if isinstance(expected, str) else None)
        if normalized is None:
            findings.append(_finding(
                "anchor_verdict_unknown",
                f"{label} expects {expected!r}; accepted tokens are "
                f"{', '.join(sorted(VERDICT_ALIASES))}", seat=role))
        else:
            tally[normalized] += 1

    graded = tally["pass"] + tally["fail"] + tally["abstain"]
    if graded > 0:
        for verdict in ("pass", "fail", "abstain"):
            if tally[verdict] == graded:
                findings.append(_finding(
                    "anchor_degenerate",
                    f"every anchor with a readable verdict expects "
                    f"{verdict!r}. A seat that cannot be shown to fire in both "
                    f"directions on its own anchors is a blind instrument, and "
                    f"a blind instrument's pass is noise.", seat=role))

    if (tally["pass"] != ANCHOR_PER_SIDE or tally["fail"] != ANCHOR_PER_SIDE
            or tally["abstain"] != 0):
        findings.append(_finding(
            "anchor_balance",
            f"{tally['pass']} pass / {tally['fail']} fail / "
            f"{tally['abstain']} abstain; the calibration set is fixed at "
            f"{ANCHOR_PER_SIDE} a side", seat=role))

    return findings, tally


def check_coverage(seats: list[dict], authoritative: list[str]) -> list[dict]:
    findings: list[dict] = []
    claimed: dict[str, list[str]] = {}
    for seat in seats:
        role = seat.get("seat") if _is_text(seat.get("seat")) else "?"
        covers = seat.get("covers")
        if not isinstance(covers, list):
            continue
        for facet_id in covers:
            if _is_text(facet_id):
                claimed.setdefault(facet_id, []).append(role)

    known = set(authoritative)
    for facet_id in authoritative:
        if facet_id not in claimed:
            findings.append(_finding(
                "coverage_gap",
                f"facet {facet_id!r} is claimed by no seat. A region of the "
                f"domain no seat is accountable for is a region the panel "
                f"passes through without looking.",
            ))
    for facet_id, roles in sorted(claimed.items()):
        if facet_id not in known:
            findings.append(_finding(
                "covers_unknown_facet",
                f"{', '.join(sorted(set(roles)))} claims facet {facet_id!r}, "
                f"which the characterization does not carry",
            ))
    return findings


def _declared_overlaps(composition: dict) -> tuple[dict[frozenset, set[str]], list[dict]]:
    """Map ``{seat_a, seat_b} -> set of shared items the rules name``."""
    findings: list[dict] = []
    declared: dict[frozenset, set[str]] = {}

    rules = composition.get("gluing_rules", [])
    if rules in (None, ""):
        rules = []
    if not isinstance(rules, list):
        findings.append(_finding(
            "gluing_rule_invalid", "`gluing_rules` is not an array"))
        return declared, findings

    for index, rule in enumerate(rules):
        label = f"gluing_rules[{index}]"
        if not isinstance(rule, dict):
            findings.append(_finding(
                "gluing_rule_invalid", f"{label} is not an object"))
            continue
        pair = rule.get("seats")
        if (not isinstance(pair, list) or len(pair) != 2
                or not all(_is_text(role) for role in pair)
                or not all(role in REQUIRED_SEATS for role in pair)
                or pair[0] == pair[1]):
            findings.append(_finding(
                "gluing_rule_invalid",
                f"{label}.seats must name two distinct seats from "
                f"{', '.join(REQUIRED_SEATS)}"))
            continue
        if not _is_text(rule.get("rule")):
            findings.append(_finding(
                "gluing_rule_invalid",
                f"{label} declares an overlap with no resolution rule. A "
                f"declared overlap whose rule is blank leaves the orchestrator "
                f"to blend two verdicts, which is how a disagreement becomes a "
                f"number."))
            continue

        overlap = rule.get("overlap")
        items = ([overlap] if _is_text(overlap)
                 else [item for item in overlap if _is_text(item)]
                 if isinstance(overlap, list) else [])
        if not items:
            findings.append(_finding(
                "gluing_rule_invalid",
                f"{label} names no shared ground in `overlap`"))
            continue
        declared.setdefault(frozenset(pair), set()).update(items)

    return declared, findings


def check_overlap(seats: list[dict], composition: dict) -> list[dict]:
    declared, findings = _declared_overlaps(composition)

    ground: dict[str, set[str]] = {}
    for seat in seats:
        role = seat.get("seat")
        if not _is_text(role):
            continue
        items: set[str] = set()
        select = seat.get("select")
        if isinstance(select, list):
            items.update(item for item in select if _is_text(item))
        taxonomy = seat.get("taxonomy")
        if isinstance(taxonomy, dict):
            items.update(name for name in taxonomy if _is_text(name))
        ground[role] = items

    overlapping_pairs: set[frozenset] = set()
    for left, right in combinations(sorted(ground), 2):
        shared = ground[left] & ground[right]
        if not shared:
            continue
        pair = frozenset((left, right))
        overlapping_pairs.add(pair)
        undeclared = sorted(shared - declared.get(pair, set()))
        if undeclared:
            findings.append(_finding(
                "overlap_undeclared",
                f"{left} and {right} both hold {', '.join(undeclared)} with no "
                f"gluing rule naming it. Two verdicts over the same "
                f"jurisdiction have no defined composition, so the "
                f"orchestrator would have to blend them.",
            ))

    for pair in declared:
        if pair not in overlapping_pairs:
            findings.append(_finding(
                "gluing_rule_unused",
                f"a gluing rule joins {' and '.join(sorted(pair))}, which "
                f"share no select entry and no taxonomy class",
            ))
    return findings


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def gate(composition: dict, composition_path: Path,
         characterization: Optional[dict] = None,
         characterization_path: Optional[Path] = None,
         characterization_blob: Optional[str] = None) -> dict:
    """Run every gate, accumulating findings rather than stopping at the first.

    Accumulating matters: a composer sent back with one refusal fixes one thing
    and returns for the next, and each round trip is a spawn.
    """
    refusals: list[dict] = []
    warnings: list[dict] = []

    def file_finding(finding: dict) -> None:
        target = refusals if finding["reason"] in REFUSAL_REASONS else warnings
        target.append(finding)

    declared_schema = composition.get("schema")
    if declared_schema != SCHEMA_ID:
        file_finding(_finding(
            "schema_unrecognized",
            f"`schema` is {declared_schema!r}; this gate knows {SCHEMA_ID!r}"))

    for finding in check_provenance(composition):
        file_finding(finding)
    for finding in check_digest(composition, characterization_path):
        file_finding(finding)

    if characterization_path is None:
        file_finding(_finding(
            "characterization_unchecked",
            "coverage was checked against the composition's own copy of the "
            "facets. Pass --characterization to check the digest and the copy, "
            "without which coverage is satisfiable by deleting the facets no "
            "seat covers."))

    embedded_ids, embedded_findings = _facet_ids(composition, ("domain", "facets"))
    for finding in embedded_findings:
        file_finding(finding)

    authoritative_ids = embedded_ids
    if characterization is not None:
        source_ids, source_findings = _facet_ids(characterization, ("facets",))
        for finding in source_findings:
            file_finding(finding)
        authoritative_ids = source_ids
        trimmed = [facet_id for facet_id in source_ids
                   if facet_id not in set(embedded_ids)]
        if trimmed:
            file_finding(_finding(
                "facets_trimmed",
                f"the characterization carries facets the composition's copy "
                f"omits: {', '.join(trimmed)}. Trimming the copy is how a "
                f"coverage gate is satisfied without covering anything."))

    seats_node = composition.get("seats")
    if not isinstance(seats_node, list) or not seats_node:
        file_finding(_finding(
            "schema_invalid", "`seats` is missing, empty, or not an array"))
        seats_node = []

    for finding in check_seat_roster(seats_node):
        file_finding(finding)

    seats = [seat for seat in seats_node if isinstance(seat, dict)]
    anchor_tallies: dict[str, dict] = {}
    for seat in seats:
        role = seat.get("seat") if _is_text(seat.get("seat")) else "?"
        for finding in check_seat_shape(seat, role):
            file_finding(finding)
        seat_findings, tally = check_anchors(seat, role, characterization_blob)
        for finding in seat_findings:
            file_finding(finding)
        anchor_tallies[role] = tally

    for finding in check_coverage(seats, authoritative_ids):
        file_finding(finding)
    for finding in check_overlap(seats, composition):
        file_finding(finding)

    return {
        "schema": "panel.gate_report/1",
        "composition": str(composition_path),
        "characterization": (str(characterization_path)
                             if characterization_path else None),
        "characterization_checked": characterization_path is not None,
        "skill": (composition.get("provenance", {}) or {}).get("skill")
                 if isinstance(composition.get("provenance"), dict) else None,
        "seats": [seat.get("seat") for seat in seats],
        "anchor_tallies": anchor_tallies,
        "facets": {"authoritative": len(authoritative_ids),
                   "embedded": len(embedded_ids)},
        "refusals": refusals,
        "warnings": warnings,
        "counts": {"refusals": len(refusals), "warnings": len(warnings)},
        "reason_index": {"refusals": REFUSAL_REASONS, "warnings": WARNING_REASONS},
        "ok": not refusals,
    }


def _print_report(report: dict, stream) -> None:
    print(f"composition   {report['composition']}", file=stream)
    print(f"characterization  {report['characterization'] or '— (unchecked)'}",
          file=stream)
    print(f"skill         {report['skill'] or '—'}", file=stream)
    print("", file=stream)

    for role in REQUIRED_SEATS:
        tally = report["anchor_tallies"].get(role)
        if tally is None:
            print(f"  {role:<14} — absent", file=stream)
        else:
            print(
                f"  {role:<14} anchors {tally['total']:>2}  "
                f"pass {tally['pass']}  fail {tally['fail']}  "
                f"abstain {tally['abstain']}",
                file=stream,
            )
    other = [role for role in report["anchor_tallies"] if role not in REQUIRED_SEATS]
    for role in other:
        tally = report["anchor_tallies"][role]
        print(f"  {role:<14} anchors {tally['total']:>2}  (unknown seat)",
              file=stream)
    print(f"  facets        {report['facets']['authoritative']} authoritative, "
          f"{report['facets']['embedded']} embedded", file=stream)
    print("", file=stream)

    for finding in report["refusals"]:
        where = f" [{finding['seat']}]" if finding["seat"] else ""
        print(f"REFUSE {finding['reason']}{where}", file=stream)
        print(f"    - {finding['detail']}", file=stream)
    for finding in report["warnings"]:
        where = f" [{finding['seat']}]" if finding["seat"] else ""
        print(f"WARN   {finding['reason']}{where}", file=stream)
        print(f"    ! {finding['detail']}", file=stream)

    print("", file=stream)
    counts = report["counts"]
    if report["ok"]:
        print(
            f"Gates passed: {counts['warnings']} warning(s), no refusals. "
            f"This composition is a record of one characterization — it is not "
            f"a roster, and a later run composes its own.",
            file=stream,
        )
    else:
        print(
            f"REFUSED: {counts['refusals']} gate failure(s), "
            f"{counts['warnings']} warning(s). No seat may be spawned. "
            f"Send the composer back with this report; on repeated refusal, "
            f"end with the report rather than judging through a defective "
            f"cover.",
            file=stream,
        )


def main(argv=None) -> int:
    configure_console()

    parser = argparse.ArgumentParser(
        prog="python -m scripts.gate_panel",
        description=(
            "Zero-model instantiation gates for a composed judge panel. "
            "Run before any seat is spawned."
        ),
    )
    parser.add_argument(
        "composition",
        type=Path,
        nargs="?",
        help="composition.json written by the composer (.yaml accepted when "
             "PyYAML is installed)",
    )
    parser.add_argument(
        "--characterization",
        type=Path,
        default=None,
        help="characterization.json the composition was composed against; "
             "enables the digest check and makes coverage authoritative",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable report on stdout alone; all "
             "human-readable output goes to stderr",
    )
    parser.add_argument(
        "--list-reasons",
        action="store_true",
        help="print every typed refusal and warning this gate can emit, "
             "then exit",
    )
    args = parser.parse_args(argv)

    # With --json, stdout carries the payload and nothing else.
    human = sys.stderr if args.json else sys.stdout

    if args.list_reasons:
        payload = {"refusals": REFUSAL_REASONS, "warnings": WARNING_REASONS}
        print("Refusals (exit 1):", file=human)
        for reason, why in REFUSAL_REASONS.items():
            print(f"  {reason:<28} {why}", file=human)
        print("\nWarnings (do not gate):", file=human)
        for reason, why in WARNING_REASONS.items():
            print(f"  {reason:<28} {why}", file=human)
        if args.json:
            json.dump(payload, sys.stdout, indent=2)
            print()
        return 0

    if args.composition is None:
        parser.print_usage(file=human)
        print("Error: a composition path is required.", file=human)
        if args.json:
            json.dump({"ok": False, "error": "no composition path supplied"},
                      sys.stdout, indent=2)
            print()
        return 2

    composition, error = load_document(args.composition)
    if error is not None:
        print(f"REFUSE composition_unreadable\n    - {error}", file=human)
        if args.json:
            json.dump({"schema": "panel.gate_report/1", "ok": False,
                       "refusals": [_finding("composition_unreadable", error)],
                       "warnings": [], "counts": {"refusals": 1, "warnings": 0}},
                      sys.stdout, indent=2)
            print()
        return 2

    characterization = None
    characterization_blob = None
    if args.characterization is not None:
        characterization, error = load_document(args.characterization)
        if error is not None:
            print(f"REFUSE characterization_unreadable\n    - {error}",
                  file=human)
            if args.json:
                json.dump({"schema": "panel.gate_report/1", "ok": False,
                           "refusals": [_finding("characterization_unreadable",
                                                 error)],
                           "warnings": [],
                           "counts": {"refusals": 1, "warnings": 0}},
                          sys.stdout, indent=2)
                print()
            return 2
        try:
            characterization_blob = " ".join(
                args.characterization.read_text(encoding="utf-8").split()
            ).lower()
        except (OSError, UnicodeDecodeError, UnicodeError):
            characterization_blob = None

    report = gate(
        composition,
        composition_path=args.composition,
        characterization=characterization,
        characterization_path=args.characterization,
        characterization_blob=characterization_blob,
    )

    _print_report(report, human)

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
