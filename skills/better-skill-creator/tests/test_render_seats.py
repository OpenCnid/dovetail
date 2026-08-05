#!/usr/bin/env python3
"""Tests for scripts/render_seats.py - the renderer that makes a seat's
`inputs` allowlist a fact about which bytes it was handed.

Run from the skill root:

    python -m unittest tests.test_render_seats -v
    python -m tests.test_render_seats

What these tests observe, and why they observe it there (C15). The property
under test is *what a seat can read*, and the only place that property is
visible is the bytes of the prompt file that a seat is actually handed. So:

  * The withheld-material tests search the **whole rendered file**, not the
    material section and not the renderer's own admitted/withheld bookkeeping.
    A test that asked the renderer whether it withheld something would pass on
    a renderer that reported one thing and wrote another - which is the exact
    shape of the defect being closed, where a prompt said "your allowlist
    governs which of these you may read" and handed over everything.
  * The byte-identity tests hash the sections **re-extracted from the written
    file**, so the digest in the render report has to be reproducible by
    someone who trusts the report about nothing.
  * The refusal tests assert that the output directory is still **empty**, not
    merely that the exit code was non-zero. A renderer that refuses loudly and
    writes anyway has refused nothing.

Every test here was mutation-checked: the corresponding guard in
render_seats.py was inverted or removed and the test was confirmed to fail. A
test that cannot fail for the reason it exists is not a test.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts import render_seats  # noqa: E402

FRAME = SKILL_ROOT / "agents" / "panel" / "seat-frame.md"

#: The recorded runs the defect was found in. Present in the research tree, not
#: in the shipped bundle, so the regression test over them skips when absent
#: rather than failing for the wrong reason.
RESEARCH = Path("D:/wonderprompt/research")


# --------------------------------------------------------------------------
# Fixture: a two-eval corpus with one withheld note per eval
# --------------------------------------------------------------------------

STATEMENTS = [
    "report.csv has a header row plus exactly 2 data rows.",
    "Every filename in manifest.csv follows the YYYY-MM-DD_vendor.pdf pattern.",
]

SEAT_INPUTS = {
    # The seat the note is withheld from - run 1's grounding, in miniature.
    "grounding": [
        "The outputs directory listing: file names, count, nesting, and sizes.",
        "The full contents of every deliverable, excluding any prose file the "
        "producing agent wrote about its own work, which is withheld from this "
        "seat by design.",
        "The request text, read only to fix what the statement's terms name.",
    ],
    "coherence": [
        "The request text in full, including every constraint it states that "
        "the authored statement does not repeat.",
        "The readable text of every output, taken as one output set.",
        "The authored statement's own wording, read as the thing under test.",
    ],
    "corroboration": [
        "The raw contents of every deliverable, used as a base for computing "
        "an asserted quantity again.",
        "The prose note the producing agent wrote about its own work - "
        "readable so that this seat can report when testimony is all there is.",
        "The standing fact that no execution transcript accompanies any output "
        "set in this domain.",
    ],
}


def make_composition() -> dict:
    return {
        "schema": "panel.composition/1",
        "provenance": {"skill": "fixture", "composed_at": "2026-07-31T00:00:00Z",
                       "characterization_sha256": "0" * 64},
        "seats": [
            {
                "seat": name,
                "judge": f"{name.title()} Seat",
                "purpose": f"The one question the {name} seat answers.",
                "inputs": entries,
                "blind_to": f"What the {name} seat may not consider.",
                "anchors": [{"input": "a situation", "expected": "pass"}],
            }
            for name, entries in SEAT_INPUTS.items()
        ],
    }


def make_evals(ground: Path) -> dict:
    return {
        "skill_name": "fixture",
        "evals": [
            {"id": 0, "prompt": "clean the export", "assertions": [STATEMENTS[0]],
             "_source_dir": str(ground / "eval-a")},
            {"id": 1, "prompt": "rename the invoices", "assertions": [STATEMENTS[1]],
             "_source_dir": str(ground / "eval-b")},
        ],
    }


def make_manifest(root: Path) -> dict:
    """The correct manifest: the deliverable channel excludes the note."""
    return {
        "schema": "panel.material/1",
        "root": str(root),
        "evals": [{"eval_id": 0, "base": "eval-a"},
                  {"eval_id": 1, "base": "eval-b"}],
        "channels": [
            {"id": "deliverable", "include": ["outputs/**/*"],
             "exclude": ["outputs/notes.md"]},
            {"id": "note", "include": ["outputs/notes.md"]},
            {"id": "prompt", "include": ["prompt.txt"]},
            {"id": "statements", "provides": "statements"},
            {"id": "record", "present": False,
             "why": "no execution record accompanies this corpus"},
        ],
        "seats": {
            "grounding": [
                {"entry": SEAT_INPUTS["grounding"][0], "channels": ["deliverable"]},
                {"entry": SEAT_INPUTS["grounding"][1], "channels": ["deliverable"]},
                {"entry": SEAT_INPUTS["grounding"][2], "channels": ["prompt"]},
            ],
            "coherence": [
                {"entry": SEAT_INPUTS["coherence"][0], "channels": ["prompt"]},
                {"entry": SEAT_INPUTS["coherence"][1],
                 "channels": ["deliverable", "note"]},
                {"entry": SEAT_INPUTS["coherence"][2], "channels": ["statements"]},
            ],
            "corroboration": [
                {"entry": SEAT_INPUTS["corroboration"][0], "channels": ["deliverable"]},
                {"entry": SEAT_INPUTS["corroboration"][1], "channels": ["note"]},
                {"entry": SEAT_INPUTS["corroboration"][2], "channels": ["record"]},
            ],
        },
    }


class RenderCase(unittest.TestCase):
    """A rendered fixture run, torn down per test."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="render-seats-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.ground = self.tmp / "ground"
        for name, deliverable in (("eval-a", "report.csv"), ("eval-b", "manifest.csv")):
            base = self.ground / name
            (base / "outputs").mkdir(parents=True)
            (base / "outputs" / deliverable).write_text(
                "col\n1\n2\n", encoding="utf-8")
            (base / "outputs" / "notes.md").write_text(
                "I checked every row and the count is right.\n", encoding="utf-8")
            (base / "prompt.txt").write_text("do the thing\n", encoding="utf-8")
            # The answer key. In no channel, so withheld from every seat.
            (base / "key.json").write_text('{"verdict": "fail"}\n', encoding="utf-8")

        self.composition_path = self.tmp / "composition.json"
        self.evals_path = self.tmp / "evals.json"
        self.material_path = self.tmp / "material.json"
        self.out = self.tmp / "out"

        self.write_json(self.composition_path, make_composition())
        self.write_json(self.evals_path, make_evals(self.ground))
        self.write_json(self.material_path, make_manifest(self.ground))

    # -- helpers ------------------------------------------------------
    @staticmethod
    def write_json(path: Path, document: dict) -> None:
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    def run_cli(self, *extra: str, expect: int | None = None) -> tuple[int, str, str]:
        argv = [str(self.composition_path), "--evals", str(self.evals_path),
                "--material", str(self.material_path), "--out", str(self.out),
                "--frame", str(FRAME), *extra]
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = render_seats.main(argv)
        if expect is not None:
            self.assertEqual(code, expect,
                             f"exit {code}\nstdout:\n{out.getvalue()}\n"
                             f"stderr:\n{err.getvalue()}")
        return code, out.getvalue(), err.getvalue()

    def render_ok(self) -> dict:
        self.run_cli(expect=0)
        return json.loads(
            (self.out / "render_manifest.json").read_text(encoding="utf-8"))

    def prompt(self, seat: str) -> str:
        return (self.out / f"seat_{seat}.md").read_text(encoding="utf-8")

    def mutate_manifest(self, mutate) -> None:
        manifest = json.loads(self.material_path.read_text(encoding="utf-8"))
        mutate(manifest)
        self.write_json(self.material_path, manifest)

    def assert_refused(self, reason: str, expect: int = 1) -> None:
        # Without --json the human stream is stdout; the reason has to reach a
        # human either way, so both are searched.
        code, out, err = self.run_cli(expect=expect)
        self.assertIn(reason, out + err,
                      f"expected refusal {reason!r}; got:\n{out}{err}")
        # Nothing written. A renderer that refuses and writes anyway has
        # refused nothing.
        self.assertFalse(self.out.exists() and any(self.out.iterdir()),
                         f"{self.out} is not empty after a refusal")

    @staticmethod
    def section(text: str, name: str) -> str:
        match = re.search(rf"<{name}>\n.*?\n</{name}>", text, re.S)
        assert match is not None, f"no <{name}> section"
        return match.group(0)


# --------------------------------------------------------------------------
# The frame is honored
# --------------------------------------------------------------------------

class TestFrameShape(RenderCase):

    def test_exactly_four_sections_in_the_frames_order(self):
        self.render_ok()
        for seat in SEAT_INPUTS:
            text = self.prompt(seat)
            tags = re.findall(r"^<(/?)([a-z_]+)>$", text, re.M)
            opens = [name for closing, name in tags if not closing]
            closes = [name for closing, name in tags if closing]
            self.assertEqual(
                opens, ["identity", "definition", "evidence", "output_schema"],
                f"{seat}: sections are {opens}")
            self.assertEqual(closes, opens, f"{seat}: sections do not close in order")
            # There is no fifth section and no task channel (constraint 1).
            stripped = text
            for name in opens:
                stripped = re.sub(rf"<{name}>\n.*?\n</{name}>", "", stripped, flags=re.S)
            self.assertEqual(stripped.strip(), "",
                             f"{seat}: text outside the four sections")

    def test_identity_and_schema_are_byte_identical_while_evidence_is_not(self):
        """The invariant that separates a frame from a form letter.

        `<identity>` and `<output_schema>` are the same bytes in every seat of
        every run - which is why they can sit up front without priming
        anything. `<evidence>` is the one section that must differ where the
        allowlists differ, and the recorded defect was precisely that all three
        were identical.
        """
        self.render_ok()
        digests = {name: {} for name in ("identity", "evidence", "output_schema")}
        for seat in SEAT_INPUTS:
            text = self.prompt(seat)
            for name in digests:
                blob = self.section(text, name).encode("utf-8")
                digests[name][seat] = hashlib.sha256(blob).hexdigest()

        self.assertEqual(len(set(digests["identity"].values())), 1,
                         f"<identity> differs across seats: {digests['identity']}")
        self.assertEqual(len(set(digests["output_schema"].values())), 1,
                         f"<output_schema> differs: {digests['output_schema']}")
        self.assertEqual(
            digests["evidence"]["grounding"] != digests["evidence"]["coherence"],
            True,
            "grounding and coherence received the same evidence block, and "
            "their allowlists differ by the note file")

    def test_identity_bytes_come_from_the_frame_file(self):
        """Not from a copy inside the renderer.

        Two representations of one fact that must agree is the drift surface
        C3 and C16 were written against. The frame is the specification; if the
        renderer carried its own copy of these bytes, editing the frame would
        silently stop changing what a seat reads.
        """
        self.render_ok()
        frame_identity = self.section(
            FRAME.read_text(encoding="utf-8"), "identity")
        self.assertIn(frame_identity, self.prompt("grounding"))

        edited = self.tmp / "edited-frame.md"
        text = FRAME.read_text(encoding="utf-8")
        edited.write_text(
            text.replace("You occupy one seat on a panel.",
                         "You occupy one seat on a jury."),
            encoding="utf-8")
        argv = [str(self.composition_path), "--evals", str(self.evals_path),
                "--material", str(self.material_path),
                "--out", str(self.tmp / "out2"), "--frame", str(edited)]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(render_seats.main(argv), 0)
        self.assertIn("You occupy one seat on a jury.",
                      (self.tmp / "out2" / "seat_grounding.md").read_text(
                          encoding="utf-8"))

    def test_output_schema_keeps_its_glosses_verbatim(self):
        """The `vacuous` and `abstainReason` glosses are not trimmed.

        Each is the only channel its finding has: without the `vacuous` gloss a
        seat routes "true, and satisfying it proves nothing" through `fail` and
        returns a false report on a true statement. Measured, not hypothesized.
        """
        self.render_ok()
        schema = self.section(self.prompt("grounding"), "output_schema")
        for token in ("vacuous", "abstainReason", "jurisdiction", "evidence",
                      "underspecified", "selfReport"):
            self.assertIn(token, schema)
        frame_schema = self.section(FRAME.read_text(encoding="utf-8"),
                                    "output_schema")
        self.assertEqual(schema, frame_schema)

    def test_definition_is_the_seat_object_and_parses_back_to_it(self):
        composition = json.loads(
            self.composition_path.read_text(encoding="utf-8"))
        self.render_ok()
        for seat in composition["seats"]:
            body = self.section(self.prompt(seat["seat"]), "definition")
            inner = body.split("<definition>\n", 1)[1].rsplit("\n</definition>", 1)[0]
            self.assertEqual(json.loads(inner), seat,
                             f"{seat['seat']}: definition is not the seat object")


# --------------------------------------------------------------------------
# Statements
# --------------------------------------------------------------------------

class TestStatements(RenderCase):

    def test_ids_in_authored_order_and_text_character_for_character(self):
        self.render_ok()
        for seat in SEAT_INPUTS:
            evidence = self.section(self.prompt(seat), "evidence")
            lines = [line for line in evidence.splitlines()
                     if re.match(r"^E\d+: ", line)]
            self.assertEqual(
                lines,
                [f"E1: {STATEMENTS[0]}", f"E2: {STATEMENTS[1]}"],
                f"{seat}: statements are not the authored bytes in authored order")

    def test_statements_are_unmarked(self):
        """No bolding, no "note that", no grouping, no reordering by interest.

        A seat handed only the statements someone thought it could rule on has
        told you nothing.
        """
        self.render_ok()
        evidence = self.section(self.prompt("grounding"), "evidence")
        head = evidence.split("## Material", 1)[0]
        for marking in ("**", "__", "<!--", "NOTE", "especially", "(likely"):
            self.assertNotIn(marking, head,
                             f"the statements block carries a marking: {marking!r}")

    def test_every_seat_gets_every_statement(self):
        self.render_ok()
        blocks = {seat: self.section(self.prompt(seat), "evidence")
                          .split("## Material", 1)[0]
                  for seat in SEAT_INPUTS}
        self.assertEqual(len(set(blocks.values())), 1,
                         "the statements block differs between seats; the "
                         "allowlist governs material, never which statements a "
                         "seat is asked to decide")

    def test_multiline_statement_is_refused_not_reflowed(self):
        evals = json.loads(self.evals_path.read_text(encoding="utf-8"))
        evals["evals"][0]["assertions"] = ["first half\nsecond half"]
        self.write_json(self.evals_path, evals)
        self.assert_refused("statement_multiline")


# --------------------------------------------------------------------------
# Material: the property the defect was in
# --------------------------------------------------------------------------

class TestMaterialIsolation(RenderCase):

    def test_a_withheld_path_appears_nowhere_in_that_seats_prompt(self):
        """Searched over the whole file, not over the material section.

        The frame's closing line says a path not listed names a file that does
        not exist for this run. That is only true if the path is not listed
        anywhere - including in a heading, a parenthetical, or an aside about
        what was left out.
        """
        self.render_ok()
        grounding = self.prompt("grounding")
        self.assertNotIn("notes.md", grounding)
        for seat in ("coherence", "corroboration"):
            self.assertIn("notes.md", self.prompt(seat),
                          f"{seat}: allowlist admits the note and it is missing")

    def test_the_answer_key_reaches_no_seat(self):
        self.render_ok()
        for seat in SEAT_INPUTS:
            self.assertNotIn("key.json", self.prompt(seat))

    def test_no_sentence_in_evidence_addresses_the_seat_about_its_allowlist(self):
        """The recorded defect, in bytes.

        Both hand-rendered runs closed the material block with "Your inputs
        allowlist, from your definition, governs which of the files at those
        paths you may treat as evidence." That converts the allowlist into a
        promise, and it places an instruction inside the one section
        `<identity>` tells the seat is never instruction.
        """
        self.render_ok()
        for seat in SEAT_INPUTS:
            evidence = self.section(self.prompt(seat), "evidence").lower()
            for banned in ("allowlist", "you may read", "not yours to read",
                           "governs which"):
                self.assertNotIn(banned, evidence,
                                 f"{seat}: the evidence block instructs the seat")

    def test_no_directory_is_handed_over(self):
        """A directory path hands over whatever is inside it.

        That is how the recorded runs leaked: the prompt named
        `.../01-contacts-dedupe/outputs` and the withheld note was sitting in
        it. Every material line has to name a file.
        """
        report = self.render_ok()
        for row in report["seats"]:
            for paths in row["admitted"].values():
                for path in paths:
                    self.assertTrue(Path(path).is_file(), f"{path} is not a file")
        evidence = self.section(self.prompt("grounding"), "evidence")
        material = evidence.split("## Material", 1)[1]
        for line in material.splitlines():
            line = line.strip()
            if not line or not (":" in line[:3] or line[1:2] == ":"):
                continue
            if re.match(r"^[A-Za-z]:[\\/]", line):
                self.assertTrue(Path(line).is_file(),
                                f"material line is not a file: {line}")

    def test_material_carries_no_channel_labels(self):
        """A channel id comes from the characterization, and no seat sees the
        characterization (constraint 3)."""
        self.render_ok()
        for seat in SEAT_INPUTS:
            evidence = self.section(self.prompt(seat), "evidence")
            material = evidence.split("## Material", 1)[1]
            for channel in ("deliverable", "note", "prompt", "record"):
                self.assertNotIn(f"\n{channel}\n", material)

    def test_report_records_admitted_and_withheld_per_seat(self):
        report = self.render_ok()
        by_seat = {row["seat"]: row for row in report["seats"]}
        grounding_withheld = sum(by_seat["grounding"]["withheld"].values(), [])
        self.assertTrue(any(p.endswith("notes.md") for p in grounding_withheld))
        coherence_admitted = sum(by_seat["coherence"]["admitted"].values(), [])
        self.assertTrue(any(p.endswith("notes.md") for p in coherence_admitted))
        # The key is withheld from everyone, and the record says so by name.
        for seat, row in by_seat.items():
            withheld = sum(row["withheld"].values(), [])
            self.assertTrue(any(p.endswith("key.json") for p in withheld), seat)

    def test_report_digests_are_reproducible_from_the_written_bytes(self):
        """An auditor who trusts the report about nothing can still check it."""
        report = self.render_ok()
        for row in report["seats"]:
            raw = Path(row["prompt"]["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),
                             row["prompt"]["sha256"])
            text = raw.decode("utf-8")
            for name, digest in row["sections_sha256"].items():
                blob = self.section(text, name).encode("utf-8")
                self.assertEqual(hashlib.sha256(blob).hexdigest(), digest,
                                 f"{row['seat']}/{name}")

    def test_render_is_deterministic(self):
        first = self.render_ok()
        firsts = {row["seat"]: row["prompt"]["sha256"] for row in first["seats"]}
        shutil.rmtree(self.out)
        second = self.render_ok()
        seconds = {row["seat"]: row["prompt"]["sha256"] for row in second["seats"]}
        self.assertEqual(firsts, seconds)


# --------------------------------------------------------------------------
# Refusals. Each is a way an orchestrator gets the mapping wrong.
# --------------------------------------------------------------------------

class TestRefusals(RenderCase):

    def test_undeclared_channel_overlap(self):
        """The recorded defect's shape, caught before a seat is spawned.

        A deliverable channel written as `outputs/**` swallows the note channel
        beside it. The two sets then collide on exactly the file one seat is
        meant not to see, and without this check the render succeeds and the
        note reaches everyone.
        """
        self.mutate_manifest(
            lambda m: m["channels"][0].__setitem__("exclude", []))
        self.assert_refused("channel_overlap_undeclared")

    def test_declared_overlap_renders(self):
        """The check discloses, it does not forbid. A real overlap is declared
        once, in a line an auditor reads."""
        def mutate(manifest):
            manifest["channels"][0]["exclude"] = []
            manifest["channels"][0]["overlaps"] = ["note"]
        self.mutate_manifest(mutate)
        self.run_cli(expect=0)
        # And now the note really does reach the seat the manifest says it does.
        self.assertIn("notes.md", self.prompt("grounding"))

    def test_entry_bound_to_nothing(self):
        self.mutate_manifest(
            lambda m: m["seats"]["grounding"][1].__setitem__("channels", []))
        self.assert_refused("entry_unmapped")

    def test_entry_text_drift(self):
        """A recomposition that rewords one sentence must not render against a
        stale binding."""
        self.mutate_manifest(
            lambda m: m["seats"]["grounding"][1].__setitem__(
                "entry", "The full contents of every deliverable."))
        self.assert_refused("entry_text_drift")

    def test_entry_count_mismatch(self):
        self.mutate_manifest(lambda m: m["seats"]["grounding"].pop())
        self.assert_refused("entry_count_mismatch")

    def test_unknown_channel(self):
        self.mutate_manifest(
            lambda m: m["seats"]["grounding"][0].__setitem__(
                "channels", ["everything"]))
        self.assert_refused("unknown_channel")

    def test_seat_with_no_binding(self):
        self.mutate_manifest(lambda m: m["seats"].pop("corroboration"))
        self.assert_refused("seat_unmapped")

    def test_seat_admits_nothing(self):
        def mutate(manifest):
            for entry in manifest["seats"]["corroboration"]:
                entry["channels"] = ["record"]
        self.mutate_manifest(mutate)
        self.assert_refused("seat_admits_nothing")

    def test_channel_that_matches_nothing_anywhere(self):
        self.mutate_manifest(
            lambda m: m["channels"][1].__setitem__("include", ["outputs/absent.md"]))
        self.assert_refused("channel_empty")

    def test_declared_absent_channel_is_not_refused(self):
        """`present: false` is the frame's "omit it silently" made explicit."""
        report = self.render_ok()
        record = next(c for c in report["channels"] if c["id"] == "record")
        self.assertFalse(record["present"])
        self.assertEqual(record["paths_total"], 0)

    def test_eval_with_no_base(self):
        self.mutate_manifest(lambda m: m["evals"].pop())
        self.assert_refused("eval_unmapped")

    def test_manifest_binds_an_eval_the_set_does_not_have(self):
        self.mutate_manifest(
            lambda m: m["evals"].append({"eval_id": 99, "base": "eval-a"}))
        self.assert_refused("eval_binding_unknown")

    def test_missing_base_directory(self):
        self.mutate_manifest(lambda m: m["evals"][0].__setitem__("base", "eval-z"))
        self.assert_refused("base_missing")

    def test_pattern_climbing_out_of_the_base(self):
        self.mutate_manifest(
            lambda m: m["channels"][0].__setitem__("include", ["../../*.json"]))
        self.assert_refused("pattern_escapes_base")

    def test_configuration_name_in_a_path(self):
        """Which configuration produced the material is never a parameter, and
        a directory name is the usual place it leaks."""
        leaky = self.ground / "eval-a" / "outputs" / "with_skill"
        leaky.mkdir()
        (leaky / "extra.csv").write_text("x\n", encoding="utf-8")
        self.assert_refused("authorship_leak")

    def test_unknown_composition_schema(self):
        composition = json.loads(self.composition_path.read_text(encoding="utf-8"))
        composition["schema"] = "panel.composition/2"
        self.write_json(self.composition_path, composition)
        self.assert_refused("schema_unrecognized")

    def test_unreadable_inputs_exit_two(self):
        self.material_path.unlink()
        self.assert_refused("manifest_unreadable", expect=2)


# --------------------------------------------------------------------------
# CLI surface (C6)
# --------------------------------------------------------------------------

class TestCli(RenderCase):

    def test_json_payload_is_alone_on_stdout(self):
        code, out, err = self.run_cli("--json", expect=0)
        payload = json.loads(out)                    # would raise on chatter
        self.assertEqual(payload["schema"], "panel.render_report/1")
        self.assertTrue(payload["ok"])
        self.assertIn("grounding", err)              # progress went to stderr

    def test_json_refusal_payload_is_alone_on_stdout(self):
        self.mutate_manifest(
            lambda m: m["seats"]["grounding"][1].__setitem__("channels", []))
        code, out, err = self.run_cli("--json", expect=1)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["refusals"][0]["reason"], "entry_unmapped")

    def test_manifest_template_refuses_as_written(self):
        """The easy path is the loud path: the skeleton carries every entry
        verbatim so nobody re-types one, and every binding empty so nobody
        renders against a guess."""
        template = self.tmp / "template.json"
        argv = [str(self.composition_path), "--evals", str(self.evals_path),
                "--emit-manifest-template", str(template)]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(render_seats.main(argv), 0)
        written = json.loads(template.read_text(encoding="utf-8"))
        self.assertEqual(
            [entry["entry"] for entry in written["seats"]["grounding"]],
            SEAT_INPUTS["grounding"])
        self.assertTrue(all(not entry["channels"]
                            for entries in written["seats"].values()
                            for entry in entries))

        # As written it refuses - the placeholder channel first.
        shutil.copy(template, self.material_path)
        self.assert_refused("channel_invalid")

        # And with the channels filled but the bindings still empty, it refuses
        # on the binding rather than falling back to handing over everything.
        written["channels"] = make_manifest(self.ground)["channels"]
        self.write_json(self.material_path, written)
        self.assert_refused("entry_unmapped")

    def test_list_reasons(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = render_seats.main(["--list-reasons"])
        self.assertEqual(code, 0)
        self.assertIn("channel_overlap_undeclared", out.getvalue())


# --------------------------------------------------------------------------
# Regression over the two recorded runs
# --------------------------------------------------------------------------

class TestRecordedRuns(unittest.TestCase):
    """The runs the audit found the defect in.

    Skipped where the research tree is not present - the shipped bundle does
    not carry it, and a test that fails for a missing fixture teaches nothing.
    """

    def setUp(self) -> None:
        if not (RESEARCH / "panel-run" / "material.json").is_file():
            self.skipTest("research/panel-run is not present")

    def render(self, run: str) -> dict:
        tmp = Path(tempfile.mkdtemp(prefix=f"{run}-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        argv = [str(RESEARCH / run / "composition.json"),
                "--evals", str(RESEARCH / "panel-run" / "evals" / "evals.json"),
                "--material", str(RESEARCH / run / "material.json"),
                "--out", str(tmp), "--frame", str(FRAME)]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(render_seats.main(argv), 0)
        report = json.loads((tmp / "render_manifest.json").read_text(encoding="utf-8"))
        report["_dir"] = str(tmp)
        return report

    def test_run_one_withholds_the_note_from_grounding(self):
        """Run 1's grounding `inputs` say the producing agent's prose note is
        "withheld from this seat by design". Its hand-rendered prompt was
        pointed at the directories the notes sat in, and its return cited
        `tree_after.txt` - a file the producing agent wrote to describe its own
        resulting state. It cannot now.
        """
        report = self.render("panel-run")
        prompt = Path(report["_dir"], "seat_grounding.md").read_text(encoding="utf-8")
        for note in ("tree_after.txt", "notes.md", "scan_summary.md",
                     "change_notes.md", "load_notes.md", "redaction_notes.md",
                     "send_checklist.md"):
            self.assertNotIn(note, prompt, f"grounding was handed {note}")
        coherence = Path(report["_dir"], "seat_coherence.md").read_text(encoding="utf-8")
        self.assertIn("tree_after.txt", coherence)

    def test_run_two_withholds_the_note_from_corroboration(self):
        """Run 2's corroboration `inputs` name no self-account channel at all,
        and its hand-rendered return cited `notes.md` and `send_checklist.md`.
        """
        report = self.render("panel-run-2")
        prompt = Path(report["_dir"], "seat_corroboration.md").read_text(encoding="utf-8")
        for note in ("tree_after.txt", "notes.md", "send_checklist.md"):
            self.assertNotIn(note, prompt, f"corroboration was handed {note}")

    def test_both_runs_produce_more_than_one_evidence_block(self):
        for run in ("panel-run", "panel-run-2"):
            report = self.render(run)
            self.assertGreater(report["invariants"]["evidence_distinct"], 1, run)
            self.assertTrue(report["invariants"]["identity_identical_across_seats"])

    def test_the_recorded_hand_rendered_prompts_carry_the_defect(self):
        """The control. If the recorded prompts did not have identical evidence
        blocks, the tests above would be measuring nothing.
        """
        for run in ("panel-run", "panel-run-2"):
            recorded = RESEARCH / run / "seats"
            if not recorded.is_dir():
                self.skipTest(f"{recorded} is not present")
            digests = set()
            for path in sorted(recorded.glob("seat_*.md")):
                text = path.read_text(encoding="utf-8")
                block = re.search(r"<evidence>\n.*?\n</evidence>", text, re.S).group(0)
                digests.add(hashlib.sha256(block.encode("utf-8")).hexdigest())
            self.assertEqual(len(digests), 1,
                             f"{run}: the recorded prompts were expected to "
                             f"share one evidence block")


if __name__ == "__main__":
    unittest.main(verbosity=2)
