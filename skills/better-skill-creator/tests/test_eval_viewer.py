#!/usr/bin/env python3
"""Tests for the results-presentation layer: generate_review.py, viewer.html,
assets/eval_review.html.

Run from the skill root:

    python -m unittest tests.test_eval_viewer -v
    python -m tests.test_eval_viewer

Every case corresponds to a defect demonstrated in
research/03-viewer-benchmark.md, research/17-first-run-ux.md,
research/05-cost-safety-resource.md or research/01-windows-encoding.md, or to a
clause of research/_CONTRACT.md (C1 layout, C4 absent-is-not-zero, C5 colour by
goodness, C7 encoding).

Fixtures come from tests/make_viewer_fixtures.py and are rebuilt into a
temporary directory: the viewer's server mode writes feedback.json into the
workspace it is pointed at, so it must never be pointed at the committed copy.

The JavaScript in viewer.html and eval_review.html is not executed here. What
is asserted statically is the framing that no amount of JS can recover from
once it is wrong -- whether a payload can close the <script> element, whether
the escaper covers attribute delimiters, whether a removed field is still read.
Behavioural checks on the rendered pages were done in a browser against these
same fixtures.
"""

from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from functools import partial
from html import unescape as html_unescape
from http.client import HTTPConnection
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

VIEWER_DIR = SKILL_ROOT / "eval-viewer"
if str(VIEWER_DIR) not in sys.path:
    sys.path.insert(0, str(VIEWER_DIR))

import generate_review as gr  # noqa: E402
from scripts.validate_grading import ABSTAIN_REASONS  # noqa: E402
from tests.make_viewer_fixtures import build  # noqa: E402

VIEWER_HTML = (VIEWER_DIR / "viewer.html").read_text(encoding="utf-8")
EVAL_REVIEW_HTML = (SKILL_ROOT / "assets" / "eval_review.html").read_text(encoding="utf-8")

BREAKOUT = "</script>"


def strip_js_comments(js: str) -> str:
    """Drop // line comments so prose about a defect is not read as the defect."""
    return re.sub(r"^\s*//.*$", "", js, flags=re.M)


def css_declarations(html: str, selector: str) -> dict:
    """Every declaration that applies to `selector`, custom properties resolved.

    Comparing class NAMES proves nothing about how two badges look - three
    distinct classes can resolve to one colour. This reads what the rules
    actually set and substitutes `var(--x)` against `:root`, so the comparison
    is between the values a browser would paint.
    """
    style = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
    style = re.sub(r"/\*.*?\*/", "", style, flags=re.S)

    variables: dict = {}
    declarations: dict = {}
    for block in re.finditer(r"([^{}]+)\{([^{}]*)\}", style):
        selectors = [s.strip() for s in block.group(1).split(",")]
        if ":root" not in selectors and selector not in selectors:
            continue
        target = variables if ":root" in selectors else declarations
        for decl in block.group(2).split(";"):
            if ":" not in decl:
                continue
            name, _, value = decl.partition(":")
            target[name.strip()] = value.strip()

    def resolve(value: str) -> str:
        for _ in range(4):
            match = re.search(r"var\((--[\w-]+)\)", value)
            if not match or match.group(1) not in variables:
                break
            value = value.replace(match.group(0), variables[match.group(1)])
        return value

    return {name: resolve(value) for name, value in declarations.items()}


def script_bodies(html: str) -> list[str]:
    """Return the contents of each <script> element, per HTML tokenization.

    Script data ends at the first literal "</script" regardless of quoting or
    JavaScript syntax, which is the whole reason JSON escaping is not enough.
    HTML comments are skipped so that prose about the hazard is not mistaken
    for the hazard.
    """
    stripped = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    bodies = []
    pos = 0
    open_re = re.compile(r"<script\b[^>]*>", re.I)
    while True:
        match = open_re.search(stripped, pos)
        if not match:
            break
        start = match.end()
        end = stripped.lower().find("</script", start)
        if end == -1:
            bodies.append(stripped[start:])
            break
        bodies.append(stripped[start:end])
        pos = end + len("</script")
    return bodies


class ScriptLiteralEscaping(unittest.TestCase):
    """A payload must not be able to close the element it is embedded in."""

    def test_angle_brackets_and_ampersand_become_escapes(self):
        out = gr.to_script_literal({"a": "</script><img src=x onerror=alert(1)>"})
        self.assertNotIn("<", out)
        self.assertNotIn(">", out)
        self.assertNotIn("&", out)
        self.assertIn(chr(92) + "u003c", out)

    def test_payload_round_trips_byte_for_byte(self):
        # Escaping must not alter the data, only how it is spelled. JSON is a
        # subset of JavaScript object literal syntax, so json.loads is a
        # faithful stand-in for what the browser's parser does here.
        payload = {
            "breakout": "</script><probe>",
            "cyrillic": "Итог: 42",
            "japanese": "日本語テキスト",
            "quotes": 'he said "no" & she said \'yes\'',
            "separators": "line" + chr(0x2028) + "para" + chr(0x2029),
        }
        self.assertEqual(json.loads(gr.to_script_literal(payload)), payload)

    def test_line_and_paragraph_separators_are_escaped(self):
        # U+2028 and U+2029 are legal in a JSON string and terminate a line in
        # JavaScript.
        out = gr.to_script_literal({"a": chr(0x2028) + chr(0x2029)})
        self.assertNotIn(chr(0x2028), out)
        self.assertNotIn(chr(0x2029), out)

    def test_generated_page_has_no_stray_script_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build(Path(tmp)) / "hostile" / "iteration-1"
            runs = gr.find_runs(root)
            benchmark = json.loads((root / "benchmark.json").read_text(encoding="utf-8"))
            html = gr.generate_html(runs, "demo", None, benchmark)

        # The fixture's output file, its grading evidence and its benchmark
        # notes all contain "</script>".
        self.assertIn(BREAKOUT, json.dumps(runs))
        bodies = script_bodies(html)
        embedding = [b for b in bodies if "EMBEDDED_DATA" in b]
        self.assertTrue(embedding, "no script element carries EMBEDDED_DATA")
        # If a payload had closed the element, the embedding body would have
        # been truncated before the closing brace of the assignment.
        self.assertIn("EMBEDDED_DATA = {", embedding[0])
        # Everything after the assignment must survive: a breakout used to
        # truncate the element mid-object, leaving init() and
        # renderBenchmark() as page text rather than code.
        self.assertIn("renderBenchmark();", embedding[0],
                      "the inline script was truncated mid-file")
        for body in bodies:
            self.assertNotIn("</script", body.lower())


class HtmlEscapingContexts(unittest.TestCase):
    """Each value must be escaped for the context it lands in."""

    def test_escape_html_covers_attribute_delimiters(self):
        # The old escapeHtml round-tripped through textContent/innerHTML, which
        # escapes & < > and neither " nor ' -- and its output was fed straight
        # into title="...", so grader evidence could add an event handler.
        body = "\n".join(script_bodies(VIEWER_HTML))
        escaper = body[body.index("function escapeHtml"):]
        escaper = escaper[:escaper.index("\n    }")]
        for needle in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
            self.assertIn(needle, escaper, "escapeHtml does not produce " + needle)
        self.assertNotIn("innerHTML", escaper,
                         "escapeHtml still round-trips through innerHTML")

    def test_eval_review_escaper_covers_attribute_delimiters(self):
        body = "\n".join(script_bodies(EVAL_REVIEW_HTML))
        escaper = body[body.index("function escapeHtml"):]
        escaper = escaper[:escaper.index("\n    }")]
        for needle in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
            self.assertIn(needle, escaper)

    def test_benchmark_metadata_fields_are_escaped(self):
        # timestamp, evals_run, runs_per_configuration and the config label all
        # reached innerHTML raw; skill_name in the same function did not.
        body = "\n".join(script_bodies(VIEWER_HTML))
        for expr in ("metadata.timestamp", "metadata.evals_run",
                     "metadata.runs_per_configuration"):
            for line in strip_js_comments(body).splitlines():
                # Only lines that actually put the value on the page.
                if expr in line and "html +=" in line:
                    self.assertIn("escapeHtml", line,
                                  expr + " reaches the page without escaping: " + line.strip())

    def test_eval_review_template_cannot_close_its_own_script(self):
        # The template's own recovery message talks about "</script>", which
        # would break the element it lives in if written literally.
        for body in script_bodies(EVAL_REVIEW_HTML):
            self.assertNotIn("</script", body.lower())

    def test_eval_review_data_block_is_a_separate_element(self):
        # A breakout in the data must not take the rest of the page's logic
        # with it: the reader gets an explanation instead of an empty table.
        bodies = script_bodies(EVAL_REVIEW_HTML)
        data_blocks = [b for b in bodies if "__EVAL_DATA_PLACEHOLDER__" in b]
        self.assertEqual(len(data_blocks), 1)
        self.assertNotIn("showRecovery", data_blocks[0])
        self.assertTrue(any("showRecovery" in b for b in bodies if b not in data_blocks))


class AbsentDataIsNotZero(unittest.TestCase):
    """Absent data is absent: never rendered as zero."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = build(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_timing_json_yields_none_not_zero(self):
        runs = gr.find_runs(self.root / "hostile" / "iteration-1")
        by_id = {r["id"]: r for r in runs}
        without = by_id["eval-1-summarises-csv-with_skill-run-1"]
        self.assertIsNone(without["timing"])
        withtiming = by_id["eval-0-emits-html-report-with_skill-run-1"]
        self.assertEqual(withtiming["timing"]["total_tokens"], 1200)

    def test_missing_prompt_is_none_not_a_sentinel_string(self):
        runs = gr.find_runs(self.root / "mixed-eval-id" / "iteration-1")
        by_id = {r["id"]: r for r in runs}
        self.assertIsNone(by_id["eval-1-no-metadata-with_skill-run-1"]["prompt"])
        self.assertEqual(by_id["eval-0-has-metadata-with_skill-run-1"]["prompt"],
                         "Identified eval.")

    def test_viewer_never_defaults_a_count_to_zero(self):
        # `(summary.passed || 0)` printed 0 for a field the grader never wrote.
        body = "\n".join(script_bodies(VIEWER_HTML))
        for pattern in (r"summary\.passed\s*\|\|\s*0", r"summary\.failed\s*\|\|\s*0",
                        r"summary\.total\s*\|\|\s*0", r"r\.passed\s*\|\|\s*0",
                        r"r\.total\s*\|\|\s*0", r"r\.pass_rate\s*\|\|\s*0"):
            self.assertIsNone(re.search(pattern, body),
                              "found a zero default for " + pattern)

    def test_an_ungraded_run_says_so_rather_than_showing_nothing(self):
        # V3 4.5. The run the benchmark excluded rendered on the Outputs screen
        # with the AUTOMATED CHECKS section absent entirely -- indistinguishable
        # from a run with nothing to report, on the screen the reviewer works
        # through. The exclusion was disclosed only on the Benchmark tab.
        runs = gr.find_runs(self.root / "mixed-eval-id" / "iteration-1")
        for run in runs:
            self.assertIsNone(run["grading"])
            self.assertIsNotNone(run["grading_note"], run["id"] + " is silently ungraded")
            self.assertIn("never graded", run["grading_note"])
            self.assertIn("not a zero", run["grading_note"].replace("Nothing here is a zero score",
                                                                    "not a zero"))
        body = "\n".join(script_bodies(VIEWER_HTML))
        fn = body[body.index("function renderGrades"):]
        fn = fn[:fn.index("\n    // Compare what the grader returned")]
        self.assertIn("run.grading_note", fn)
        self.assertNotIn('section.style.display = "none"', fn,
                         "the checks section can still hide itself entirely")

    def test_a_graded_run_is_checked_against_the_assertions_the_eval_declared(self):
        # R10's other half: nothing anywhere compared expectations[].text
        # against eval_metadata.assertions, so the drift that splits rows on the
        # Benchmark tab had no explanation anywhere.
        runs = gr.find_runs(self.root / "ordering-swap" / "iteration-1")
        for run in runs:
            self.assertIsInstance(run["assertions"], list)
            self.assertIn("Header row present", run["assertions"])
        body = "\n".join(script_bodies(VIEWER_HTML))
        self.assertIn("function renderAssertionDrift", body)
        self.assertIn("run.assertions", body)

    def test_viewer_does_not_read_fields_that_no_longer_exist(self):
        # output_chars, tool_calls and errors were removed from
        # runs[].result outright: nothing has ever produced them, and a
        # permanently empty column reads as a measured zero.
        body = "\n".join(script_bodies(VIEWER_HTML))
        for field in ("output_chars", "tool_calls"):
            self.assertNotIn(field, body)
        self.assertIsNone(re.search(r"result\.errors|r\.errors\b", body))


class ComparisonDirection(unittest.TestCase):
    """Order by role, colour by goodness."""

    def test_delta_colour_comes_from_the_declared_better_flag(self):
        body = "\n".join(script_bodies(VIEWER_HTML))
        self.assertIn("entry.better === true", body)
        self.assertIn("entry.better === false", body)

    def test_delta_class_takes_a_polarity_argument(self):
        # The old deltaClass(val) coloured by sign alone, so a faster, cheaper
        # skill rendered red on two of the three headline metrics.
        body = "\n".join(script_bodies(VIEWER_HTML))
        self.assertIsNotNone(re.search(r"function deltaClass\(\s*value\s*,\s*lowerIsBetter\s*\)", body))
        self.assertIn("lowerIsBetter: true", body)

    def test_roles_are_read_from_the_top_level_not_inferred_from_sort_order(self):
        body = "\n".join(script_bodies(VIEWER_HTML))
        self.assertIn("data.primary", body)
        self.assertIn("data.baseline", body)
        self.assertNotIn("metadata.primary", body)
        self.assertNotIn("metadata.baseline", body)

    def test_headline_pass_rate_is_labelled_and_pooled(self):
        # 10 checks at 50% plus 2 checks at 100% is 58%, not 75%. Either
        # number is defensible; an unlabelled one is not.
        body = "\n".join(script_bodies(VIEWER_HTML))
        self.assertIn("microAverage", body)
        self.assertIn("every graded check, pooled", body)
        self.assertIn("mean &plusmn; sd across runs", body)


class AssertionMatching(unittest.TestCase):
    """R10. One alignment rule: exact text. Never position.

    Keying on POSITION let two graders that returned the same checks in
    opposite orders render as two rows on which both configurations agreed --
    a wrong row a reader cannot see. Keying on exact text produces a wrong row
    a reader CAN see (a split assertion), which the page then explains.
    """

    def test_assertion_key_is_the_exact_text_and_takes_no_index(self):
        body = "\n".join(script_bodies(VIEWER_HTML))
        signature = re.search(r"function assertionKey\(([^)]*)\)", body)
        self.assertIsNotNone(signature, "assertionKey is gone")
        self.assertEqual(signature.group(1).strip(), "exp",
                         "assertionKey still takes an index, so it can still key on position")
        fn = body[signature.start():]
        fn = fn[:fn.index("\n    }")]
        self.assertIn('"text:" + text', fn)
        self.assertNotIn("index", fn, "position leaked back into the alignment key")

    def test_expectation_id_is_not_consulted(self):
        # exp.id had no producer anywhere -- not grader.md, not schemas.md, not
        # validate_grading.py -- so the branch that read it never ran and the
        # positional fallback always did. Reading a field nothing writes is how
        # a second alignment rule hides inside the first.
        body = strip_js_comments("\n".join(script_bodies(VIEWER_HTML)))
        self.assertIsNone(re.search(r"exp\.id\b", body))

    def test_the_banner_states_what_the_code_does(self):
        # The old caption said "Same check, matched by position" over code that
        # keyed on exp.id with a positional fallback. A banner that describes a
        # rule the code does not implement is worse than no banner.
        body = "\n".join(script_bodies(VIEWER_HTML))
        self.assertNotIn("matched by position", body)
        self.assertIn("exact text", body)
        self.assertIn("assertion-drift", body)

    def test_every_party_states_the_same_rule(self):
        # C12's shape: the severity -- here, the alignment rule -- belongs to
        # the condition, not to the component. schemas.md, grader.md and
        # analyzer.md all say exact string equality; the viewer must not be the
        # one party doing something else.
        for rel in ("references/schemas.md", "agents/grader.md", "agents/analyzer.md"):
            text = (SKILL_ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("exact string equality", text, rel + " no longer states the rule")


class AssertionAlignmentBehaviour(unittest.TestCase):
    """The same check, executed rather than read.

    V8 demonstrated the defect by running the extracted JavaScript. So does
    this: renderAssertionTable() returns an HTML string and touches no DOM, so
    it can be called directly under node with a handful of stubs.
    """

    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")

    def _render(self, runs, configs):
        body = "\n".join(script_bodies(VIEWER_HTML))
        # Everything up to the bootstrap; init() and renderBenchmark() need a
        # document and this test does not.
        source = body.split("// ---- Start ----")[0]
        source = source.replace("/*__EMBEDDED_DATA__*/", "const EMBEDDED_DATA = {runs: []};")
        harness = (
            "const document = {addEventListener(){}, getElementById(){return null},"
            " querySelector(){return null}, querySelectorAll(){return []}};\n"
            + source
            + "\nconsole.log(renderAssertionTable("
            + json.dumps(runs) + ", " + json.dumps(configs) + "));\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "harness.js"
            script.write_text(harness, encoding="utf-8")
            out = subprocess.run([self.node, str(script)], capture_output=True, text=True,
                                 encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    @staticmethod
    def _rows(html):
        """[(label, [cell, ...]), ...] from the rendered table."""
        rows = []
        for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
            cells = re.findall(r"<td>(.*?)</td>", tr, re.S)
            if not cells:
                continue
            plain = [re.sub(r"<[^>]*>", "", c).strip() for c in cells]
            rows.append((plain[0], plain[1:]))
        return rows

    # Two graders, same two checks, opposite order, opposite results.
    SWAPPED = [
        {"configuration": "with_skill", "run_number": 1, "expectations": [
            {"text": "Header row present", "verdict": "pass", "evidence": "a"},
            {"text": "Totals row is last", "verdict": "fail", "evidence": "b"}]},
        {"configuration": "without_skill", "run_number": 1, "expectations": [
            {"text": "Totals row is last", "verdict": "pass", "evidence": "c"},
            {"text": "Header row present", "verdict": "fail", "evidence": "d"}]},
    ]

    def test_opposite_order_does_not_render_as_agreement(self):
        if not self.node:
            self.skipTest("node is not installed; the browser evidence covers this case")
        rows = self._rows(self._render(self.SWAPPED, ["with_skill", "without_skill"]))
        by_label = {label: cells for label, cells in rows}
        # Under positional alignment this was ["✓", "✓"] and ["✗", "✗"]:
        # two configurations in perfect agreement, which is the opposite of
        # what the graders actually reported.
        self.assertEqual(by_label["Header row present"], ["✓", "✗"])
        self.assertEqual(by_label["Totals row is last"], ["✗", "✓"])

    def test_a_reworded_check_splits_visibly_and_says_why(self):
        if not self.node:
            self.skipTest("node is not installed; the browser evidence covers this case")
        runs = [
            {"configuration": "with_skill", "run_number": 1, "expectations": [
                {"text": "Output is a CSV file", "verdict": "pass", "evidence": "a"}]},
            {"configuration": "without_skill", "run_number": 1, "expectations": [
                {"text": "The output is a CSV file", "verdict": "fail", "evidence": "b"}]},
        ]
        html = self._render(runs, ["with_skill", "without_skill"])
        rows = self._rows(html)
        self.assertEqual(len(rows), 2, "a reworded check must not be merged")
        # Each row half empty -- and each row naming the other's wording, so
        # the reader is told these are probably one check.
        self.assertIn("Graders worded this differently", html)
        self.assertIn("The output is a CSV file", rows[0][0])
        self.assertIn("Output is a CSV file", rows[1][0])
        self.assertIn("—", rows[0][1] + rows[1][1])

    def test_two_genuinely_different_checks_are_not_called_drift(self):
        if not self.node:
            self.skipTest("node is not installed; the browser evidence covers this case")
        runs = [
            {"configuration": "with_skill", "run_number": 1, "expectations": [
                {"text": "No blank rows", "verdict": "pass", "evidence": "a"}]},
            {"configuration": "without_skill", "run_number": 1, "expectations": [
                {"text": "No blank columns", "verdict": "fail", "evidence": "b"}]},
        ]
        html = self._render(runs, ["with_skill", "without_skill"])
        self.assertNotIn("Graders worded this differently", html)

    def test_an_untexted_check_gets_its_own_row(self):
        if not self.node:
            self.skipTest("node is not installed; the browser evidence covers this case")
        runs = [
            {"configuration": "with_skill", "run_number": 1, "expectations": [
                {"verdict": "pass", "evidence": "a"}]},
            {"configuration": "without_skill", "run_number": 1, "expectations": [
                {"verdict": "fail", "evidence": "b"}]},
        ]
        html = self._render(runs, ["with_skill", "without_skill"])
        rows = self._rows(html)
        # Aligning two textless checks by position would claim they are the
        # same check on no evidence at all.
        self.assertEqual(len(rows), 2)
        self.assertIn("cannot be compared across configurations", html)

    def test_stats_reports_no_spread_from_one_sample(self):
        # R12. stddev 0 at n=1 rendered "50% +/- 0% n=1" -- a spread that was
        # never measured, printed as a measurement of no spread. The aggregator
        # returns None there and this must match it.
        if not self.node:
            self.skipTest("node is not installed; the browser evidence covers this case")
        body = "\n".join(script_bodies(VIEWER_HTML))
        source = body.split("// ---- Start ----")[0]
        source = source.replace("/*__EMBEDDED_DATA__*/", "const EMBEDDED_DATA = {runs: []};")
        harness = (
            "const document = {addEventListener(){}, getElementById(){return null},"
            " querySelector(){return null}, querySelectorAll(){return []}};\n"
            + source
            + "\nconsole.log(JSON.stringify({one: stats([0.5]), two: stats([0.5, 1.0]),"
            " none: stats([null, null]), some: stats([2.0, null])}));\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "stats.js"
            script.write_text(harness, encoding="utf-8")
            out = subprocess.run([self.node, str(script)], capture_output=True, text=True,
                                 encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        got = json.loads(out.stdout)
        self.assertIsNone(got["one"]["stddev"], "a single sample got a standard deviation")
        self.assertEqual(got["one"]["n"], 1)
        self.assertIsNone(got["none"])
        self.assertIsNone(got["some"]["stddev"])
        self.assertEqual(got["some"]["missing"], 1, "an absent value was counted as measured")
        self.assertAlmostEqual(got["two"]["stddev"], 0.3536, places=4)

    def test_stats_matches_the_aggregator_it_claims_to_match(self):
        # Same inputs through both implementations. The comment in viewer.html
        # asserted parity for months while the two disagreed at n=1.
        if not self.node:
            self.skipTest("node is not installed; the browser evidence covers this case")
        from scripts.aggregate_benchmark import calculate_stats
        cases = [[0.5], [0.5, 1.0], [1.0, 1.0, 1.0], [2.0, None], [30.0, 45.0, 60.0]]
        body = "\n".join(script_bodies(VIEWER_HTML))
        source = body.split("// ---- Start ----")[0]
        source = source.replace("/*__EMBEDDED_DATA__*/", "const EMBEDDED_DATA = {runs: []};")
        harness = (
            "const document = {addEventListener(){}, getElementById(){return null},"
            " querySelector(){return null}, querySelectorAll(){return []}};\n"
            + source
            + "\nconsole.log(JSON.stringify(" + json.dumps(cases) + ".map(stats)));\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "parity.js"
            script.write_text(harness, encoding="utf-8")
            out = subprocess.run([self.node, str(script)], capture_output=True, text=True,
                                 encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        for case, js in zip(cases, json.loads(out.stdout)):
            py = calculate_stats(case)
            self.assertEqual(js, py, "viewer stats() and calculate_stats disagree on " + repr(case))


class LayoutReading(unittest.TestCase):
    """The canonical <config>/run-<K>/ layout, and the legacy shapes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = build(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_eval_metadata_is_found_two_levels_above_the_run_dir(self):
        # Under the canonical layout the run dir is <config>/run-<K>/ and the
        # metadata lives at the eval-dir root. Checking only run_dir and its
        # parent is what made every prompt read "(No prompt found)".
        runs = gr.find_runs(self.root / "hostile" / "iteration-1")
        self.assertTrue(runs)
        for run in runs:
            self.assertIsNotNone(run["prompt"], run["id"] + " lost its prompt")
            self.assertIsNotNone(run["eval_id"])

    def test_legacy_flat_layout_is_normalized_to_run_1_and_flagged(self):
        runs = gr.find_runs(self.root / "legacy-flat" / "iteration-1")
        self.assertEqual(len(runs), 2)
        for run in runs:
            self.assertEqual(run["layout"], "legacy-flat")
            self.assertEqual(run["run_number"], 1)

    def test_canonical_layout_is_not_flagged(self):
        runs = gr.find_runs(self.root / "hostile" / "iteration-1")
        for run in runs:
            self.assertEqual(run["layout"], "canonical")
            self.assertEqual(run["run_number"], 1)

    def test_the_run_dir_pattern_is_the_scripts_pattern(self):
        # R13. Two regexes for one contract: `^run-(\d+)$` in the scripts and
        # `^run-(.+)$` here. A run-final/ directory was a first-class run to the
        # viewer and an exclusion to the aggregator, so the page and the
        # benchmark described different data and neither said so.
        from scripts.validate_grading import RUN_DIR_RE as canonical
        self.assertEqual(gr.RUN_DIR_RE.pattern, canonical.pattern)
        self.assertIsNone(gr.RUN_DIR_RE.match("run-final"))
        self.assertIsNotNone(gr.RUN_DIR_RE.match("run-12"))

    def test_a_misnamed_run_dir_is_flagged_not_silently_accepted(self):
        runs = gr.find_runs(self.root / "malformed-run" / "iteration-1")
        by_id = {r["id"]: r for r in runs}
        bad = by_id["eval-0-misnamed-run-with_skill-run-final"]
        self.assertEqual(bad["layout"], "malformed-run")
        # Not normalized to 1: it is not run 1, and claiming so would be a
        # measurement the directory name does not support.
        self.assertIsNone(bad["run_number"])
        self.assertIn("run-final", bad["layout_note"])
        self.assertIn("excludes", bad["layout_note"])
        good = by_id["eval-0-misnamed-run-without_skill-run-1"]
        self.assertEqual(good["layout"], "canonical")
        self.assertIsNone(good["layout_note"])

    def test_the_viewer_shows_the_layout_note_on_the_run_screen(self):
        body = "\n".join(script_bodies(VIEWER_HTML))
        self.assertIn("run.layout_note", body)
        self.assertIn('id="run-notice"', VIEWER_HTML)

    def test_mixed_and_null_eval_ids_do_not_break_the_sort(self):
        # `.get("eval_id", inf)` returns the stored None, so a workspace
        # holding both identified and unidentified evals raised
        # TypeError: '<' not supported between 'NoneType' and 'int'.
        runs = gr.find_runs(self.root / "mixed-eval-id" / "iteration-1")
        self.assertEqual(len(runs), 3)
        self.assertEqual(runs[0]["eval_id"], 0)


class Encoding(unittest.TestCase):
    """Encoding is explicit on every read and write."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = build(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_io_call_omits_an_encoding(self):
        source = (VIEWER_DIR / "generate_review.py").read_text(encoding="utf-8")
        self.assertNotIn("\nwith open(", source, "a bare builtin open() is back")
        for match in re.finditer(r"\.(read_text|write_text)\(", source):
            # Walk to the matching paren so a nested call does not end the
            # argument list early.
            depth, i = 1, match.end()
            while depth and i < len(source):
                depth += {"(": 1, ")": -1}.get(source[i], 0)
                i += 1
            args = source[match.end():i - 1]
            self.assertIn("encoding=", args,
                          "unencoded I/O: " + match.group(0) + args)

    def test_decode_failures_are_named_in_the_handlers(self):
        # UnicodeDecodeError is a sibling of json.JSONDecodeError under
        # ValueError, so (JSONDecodeError, OSError) does not catch it.
        source = (VIEWER_DIR / "generate_review.py").read_text(encoding="utf-8")
        for match in re.finditer(r"except \(([^)]*)\)", source):
            group = match.group(1)
            if "JSONDecodeError" in group:
                self.assertIn("UnicodeError", group, "handler misses decode errors: " + group)

    def test_configure_console_is_called_at_the_entry_point(self):
        source = (VIEWER_DIR / "generate_review.py").read_text(encoding="utf-8")
        main = source[source.index("def main()"):]
        self.assertIn("configure_console()", main.split("\n\n")[0] + main[:400])

    def test_console_output_is_ascii_only(self):
        # The server banner was 33 U+2500 characters, which cp1252 cannot
        # encode; the process died after binding the port and before opening a
        # browser. configure_console covers it, but the banner needs no glyphs.
        source = (VIEWER_DIR / "generate_review.py").read_text(encoding="utf-8")
        code = re.sub(r"^\s*#.*$", "", source, flags=re.M)
        for call in re.findall(r"print\((.*)\)", code):
            self.assertTrue(call.isascii(), "non-ASCII inside a print(): " + call)
        self.assertNotIn(chr(0x2500), source, "the box-drawing banner rule is back")

    def test_non_ascii_survives_a_read_and_a_static_write(self):
        source = self.root / "hostile" / "iteration-1"
        runs = gr.find_runs(source)
        benchmark = json.loads((source / "benchmark.json").read_text(encoding="utf-8"))
        html = gr.generate_html(runs, "demo", None, benchmark)

        out = self.tmp / "static.html"
        out.write_text(html, encoding="utf-8")
        raw = out.read_bytes()
        raw.decode("utf-8")  # raises if the write used the platform codepage
        text = raw.decode("utf-8")

        # The double-encoded read produced U+00C2 in front of every U+00B1.
        self.assertNotIn("Â±", text)
        # The template's own typography survives.
        self.assertIn("—", text)
        # The run data is ASCII-escaped, which JavaScript decodes back to the
        # original characters -- so it is immune to the output encoding too.
        # write_text translates \n to the platform line ending, so the blob is
        # simply the rest of its own line.
        blob = text[text.index("const EMBEDDED_DATA"):].splitlines()[0].rstrip(";")
        self.assertIn(chr(92) + "u0418", blob)          # CYRILLIC CAPITAL I
        decoded = json.loads(blob[blob.index("{"):])
        self.assertIn("Итог", decoded["runs"][0]["prompt"])

    def test_non_utf8_json_warns_instead_of_crashing(self):
        bad = self.tmp / "bad.json"
        bad.write_bytes('{"prompt": "café"}'.encode("cp1252"))
        self.assertIsNone(gr.load_json_file(bad, "test file"))


class ServerBehaviour(unittest.TestCase):
    def test_address_reuse_is_off_so_a_busy_port_actually_fails(self):
        # HTTPServer sets allow_reuse_address = 1, and on Windows SO_REUSEADDR
        # lets a SECOND socket bind an address already in use. The bind then
        # succeeds, the ephemeral-port fallback never runs, and the browser is
        # handed to the previous iteration's server.
        self.assertIs(gr.ReviewServer.allow_reuse_address, False)
        first = gr.ReviewServer(("127.0.0.1", 0), gr.ReviewHandler)
        port = first.server_address[1]
        try:
            with self.assertRaises(OSError):
                gr.ReviewServer(("127.0.0.1", port), gr.ReviewHandler).server_close()
        finally:
            first.server_close()

    def _serve(self, workspace):
        import threading
        from functools import partial
        handler = partial(gr.ReviewHandler, workspace, "demo",
                          workspace / "feedback.json", {}, None)
        server = gr.ReviewServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, server.server_address[1]

    def _request(self, port, method, path, host, origin=None, body=None):
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            payload = body.encode("utf-8") if body else None
            headers = {"Host": host}
            if origin is not None:
                headers["Origin"] = origin
            if payload:
                headers["Content-Type"] = "application/json"
            conn.request(method, path, body=payload, headers=headers)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_host_and_origin_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = build(Path(tmp)) / "hostile" / "iteration-1"
            server, port = self._serve(workspace)
            try:
                good = json.dumps({"reviews": []})
                evil = json.dumps({"reviews": [{"run_id": "x", "feedback": "PWNED"}]})
                host = "localhost:%d" % port
                same_origin = "http://localhost:%d" % port

                self.assertEqual(self._request(port, "GET", "/api/feedback", host)[0], 200)
                # A hostname resolving to 127.0.0.1 must not hand a web page
                # the whole workspace (DNS rebinding).
                self.assertEqual(self._request(port, "GET", "/", "evil.example.com")[0], 403)
                # feedback.json is the input to the next skill revision.
                self.assertEqual(
                    self._request(port, "POST", "/api/feedback", host, same_origin, good)[0], 200)
                for origin in ("https://evil.example.com", "null",
                               "http://localhost:%d" % (port + 1)):
                    self.assertEqual(
                        self._request(port, "POST", "/api/feedback", host, origin, evil)[0], 403,
                        "accepted a write from " + origin)
                # A non-browser client (the harness, curl) sends no Origin.
                self.assertEqual(
                    self._request(port, "POST", "/api/feedback", host, None, good)[0], 200)
            finally:
                server.shutdown()
                server.server_close()

    def test_feedback_is_written_as_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = build(Path(tmp)) / "hostile" / "iteration-1"
            server, port = self._serve(workspace)
            try:
                # run_id must name a run that exists here; see
                # FeedbackRunIdValidation below for why.
                run_id = sorted(gr.find_run_ids(workspace))[0]
                body = json.dumps({"reviews": [{"run_id": run_id, "feedback": "Итог — café"}],
                                   "status": "complete"})
                status, _ = self._request(port, "POST", "/api/feedback",
                                          "localhost:%d" % port,
                                          "http://localhost:%d" % port, body)
                self.assertEqual(status, 200)
            finally:
                server.shutdown()
                server.server_close()
            written = (workspace / "feedback.json").read_bytes().decode("utf-8")
            self.assertIn("Итог — café", written)


class FeedbackRoundTrip(unittest.TestCase):
    def test_closing_the_done_dialog_does_not_resubmit(self):
        # closeDoneDialog() called saveCurrentFeedback(), which POSTs only the
        # non-empty entries with status "in_progress" -- so clicking OK, the
        # dialog's only button, undid the submission and deleted the
        # empty-feedback entries that distinguish "reviewed, looked fine" from
        # "never opened".
        body = "\n".join(script_bodies(VIEWER_HTML))
        fn = body[body.index("function closeDoneDialog"):]
        fn = strip_js_comments(fn[:fn.index("\n    }")])
        self.assertNotIn("saveCurrentFeedback", fn)
        self.assertIn("remove(\"visible\")", fn)

    def test_complete_payload_includes_every_run(self):
        body = "\n".join(script_bodies(VIEWER_HTML))
        fn = body[body.index("function showDoneDialog"):]
        fn = fn[:fn.index("\n    function ")]
        self.assertIn("for (const r of EMBEDDED_DATA.runs)", fn)
        self.assertIn('status: "complete"', fn)


class ServerAvailability(unittest.TestCase):
    """V3 4.2/4.3. A stalled peer must not take the viewer with it, and a POST
    must not be able to destroy a review file."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = (build(Path(self._tmp.name))
                          / "ordering-swap" / "iteration-1")
        self.feedback = self.workspace / "feedback.json"
        handler = partial(gr.ReviewHandler, self.workspace, "swap", self.feedback, {}, None)
        self.server = gr.ReviewServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self._tmp.cleanup()

    def _request(self, method, path, origin=None, body=None, timeout=15):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            headers = {"Host": "localhost:%d" % self.port}
            if origin is not None:
                headers["Origin"] = origin
            payload = body.encode("utf-8") if isinstance(body, str) else body
            if payload:
                headers["Content-Type"] = "application/json"
            conn.request(method, path, body=payload, headers=headers)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_a_half_open_connection_does_not_wedge_the_server(self):
        # Plain HTTPServer serves one connection at a time and
        # BaseHTTPRequestHandler.timeout is None, so a client that opened a
        # socket and sent half a request line blocked every other request
        # indefinitely -- the page simply stopped responding, and the server
        # logged nothing at all.
        wedge = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        try:
            wedge.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n")  # never terminated
            time.sleep(0.3)
            for _ in range(3):
                started = time.time()
                status, _ = self._request("GET", "/", timeout=10)
                self.assertEqual(status, 200)
                self.assertLess(time.time() - started, 8,
                                "a stalled peer is still delaying other requests")
                time.sleep(0.2)
        finally:
            wedge.close()

    def test_the_handler_has_a_request_timeout(self):
        # The dropped-peer half of the same fix: without this the wedging
        # connection is merely isolated to one thread and never reclaimed.
        self.assertIsNotNone(gr.ReviewHandler.timeout)
        self.assertLessEqual(gr.ReviewHandler.timeout, 60)

    def test_a_run_id_that_names_no_run_is_refused_and_nothing_is_written(self):
        # V3 4.3. One POST replaced every genuine review with entries filed
        # under a run_id present in no run, and the 8 MB result was embedded
        # into the next iteration's page.
        known = sorted(gr.find_run_ids(self.workspace))
        self.assertTrue(known)
        good = json.dumps({"reviews": [{"run_id": known[0], "feedback": "real note"}],
                           "status": "complete"})
        self.assertEqual(self._request("POST", "/api/feedback", body=good)[0], 200)
        before = self.feedback.read_text(encoding="utf-8")

        bogus = json.dumps({"reviews": [{"run_id": "no-such-run", "feedback": "PWNED"}]})
        status, body = self._request("POST", "/api/feedback", body=bogus)
        self.assertEqual(status, 400)
        self.assertIn("no-such-run", body.decode("utf-8"))
        self.assertEqual(self.feedback.read_text(encoding="utf-8"), before,
                         "a refused write still replaced the reviews on disk")

    def test_an_oversized_body_is_refused_with_an_answer_the_client_receives(self):
        self.assertLessEqual(gr.MAX_REQUEST_BYTES, 1024 * 1024)
        known = sorted(gr.find_run_ids(self.workspace))[0]
        big = json.dumps({"reviews": [{"run_id": known,
                                       "feedback": "x" * (gr.MAX_REQUEST_BYTES + 1024)}]})
        # Closing the socket with an undelivered body in flight makes Windows
        # send an RST and the client sees a reset instead of the refusal.
        status, body = self._request("POST", "/api/feedback", body=big, timeout=30)
        self.assertEqual(status, 413)
        self.assertIn("larger than", body.decode("utf-8"))

    def test_a_malformed_body_is_a_client_error_not_a_server_error(self):
        for bad in ("{not json", '{"nope": 1}', '{"reviews": "text"}',
                    '{"reviews": [{"feedback": "no run_id"}]}'):
            status, _ = self._request("POST", "/api/feedback", body=bad)
            self.assertEqual(status, 400, "wrong status for " + bad)

    def test_a_query_string_still_reaches_the_page(self):
        # V3 4.7: GET /?anything returned a stock 404 error page, so any
        # cache-buster or bookmarked URL looked like a broken viewer.
        for path in ("/", "/?v=2", "/index.html", "/index.html?cb=1"):
            self.assertEqual(self._request("GET", path)[0], 200, path)
        self.assertEqual(self._request("GET", "/nope")[0], 404)
        self.assertEqual(self._request("GET", "/api/feedback?x=1")[0], 200)


class BenchmarkDiscovery(unittest.TestCase):
    """V3 4.4. benchmark.json sat in the workspace and the page said none existed."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = build(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def _static(self, workspace, extra=()):
        out = self.tmp / "out.html"
        result = subprocess.run(
            [sys.executable, str(VIEWER_DIR / "generate_review.py"), str(workspace),
             "--skill-name", "demo", "--static", str(out), *extra],
            capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        return out.read_text(encoding="utf-8"), result.stderr

    @staticmethod
    def _embedded(html):
        blob = html[html.index("const EMBEDDED_DATA"):].splitlines()[0]
        return json.loads(blob[blob.index("{"):].rstrip(";"))

    def test_a_benchmark_in_the_workspace_is_found_without_being_named(self):
        workspace = self.root / "hostile" / "iteration-1"
        self.assertTrue((workspace / "benchmark.json").is_file())
        html, _ = self._static(workspace)
        data = self._embedded(html)
        self.assertIn("benchmark", data,
                      "benchmark.json one directory up from the runs was not discovered")

    def test_no_benchmark_anywhere_still_means_no_benchmark_key(self):
        workspace = self.root / "mixed-eval-id" / "iteration-1"
        self.assertFalse((workspace / "benchmark.json").is_file())
        html, _ = self._static(workspace)
        self.assertNotIn("benchmark", self._embedded(html))
        # And the page states what it knows, not what it cannot know.
        self.assertIn("No benchmark.json was passed to this viewer", html)

    def test_an_explicit_benchmark_still_wins(self):
        workspace = self.root / "hostile" / "iteration-1"
        html, _ = self._static(workspace,
                               ["--benchmark", str(workspace / "benchmark-no-roles.json")])
        data = self._embedded(html)
        self.assertNotIn("primary", data["benchmark"])


class ExclusionKinds(unittest.TestCase):
    """"Excluded" is three different things, and two of them are partial.

    One blanket "excluded from every number on this page" was exact while the
    only exclusions were schema-invalid grading files. It is now false for a
    run that lost only its timing.json (its grading still counts) and for a
    pairing exclusion (it still counts in its own configuration's column) --
    and a reader who sees a run listed as excluded beside a pass rate that
    includes it concludes the page is inconsistent, when it is being precise.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = build(Path(self._tmp.name))
        self.benchmark = json.loads(
            (self.root / "mixed-exclusions" / "iteration-1" / "benchmark.json")
            .read_text(encoding="utf-8"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_blanket_sentence_is_gone(self):
        body = "\n".join(script_bodies(VIEWER_HTML))
        # The old sentence may still appear, but only as one group's heading --
        # never as the single thing said about every exclusion.
        self.assertIn("function exclusionKind", body)
        self.assertIn("function renderExclusions", body)
        self.assertIsNone(
            re.search(r"exclusions\.length\s*\+\s*\(exclusions\.length === 1", body),
            "the exclusions banner is still counting every kind into one sentence")

    def test_kinds_are_read_from_the_shared_tag_not_from_the_prose(self):
        # scripts/utils.py prints `C12:<condition>=<severity>` for exactly this
        # purpose. Matching the sentence instead would break the next time
        # someone improves the wording -- which is how three components
        # describing one condition drifted apart before C12 existed.
        body = "\n".join(script_bodies(VIEWER_HTML))
        self.assertIn('"C12:" + condition + "="', body)
        self.assertIn('hasCondition(reason, "unpaired_evals")', body)
        from scripts.utils import condition_tag
        self.assertEqual(condition_tag("unpaired_evals"), "C12:unpaired_evals=error")

    def test_the_fixture_covers_all_three_kinds(self):
        # Guards the test below: if the fixture stopped exercising a kind, the
        # rendering assertions would pass vacuously.
        reasons = [item["reason"] for item in self.benchmark["exclusions"]]
        paths = [item["path"] for item in self.benchmark["exclusions"]]
        self.assertTrue(any("C12:unpaired_evals=" in r for r in reasons))
        self.assertTrue(any(p.endswith("timing.json") for p in paths))
        self.assertTrue(any(p.endswith("grading.json") for p in paths))

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_each_kind_gets_a_heading_that_says_excluded_from_what(self):
        body = "\n".join(script_bodies(VIEWER_HTML))
        source = body.split("// ---- Start ----")[0]
        source = source.replace("/*__EMBEDDED_DATA__*/", "const EMBEDDED_DATA = {runs: []};")
        harness = (
            "const document = {addEventListener(){}, getElementById(){return null},"
            " querySelector(){return null}, querySelectorAll(){return []}};\n"
            + source
            + "\nconsole.log(renderExclusions("
            + json.dumps(self.benchmark["exclusions"]) + "));\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "excl.js"
            script.write_text(harness, encoding="utf-8")
            out = subprocess.run([shutil.which("node"), str(script)], capture_output=True,
                                 text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        html = out.stdout
        headings = re.findall(r"<strong>(.*?)</strong>", html, re.S)
        self.assertEqual(len(headings), 3, "the three kinds did not produce three groups")

        dropped, timing, pairing = headings
        # Dropped: the original claim, now scoped to the group it is true of.
        self.assertIn("excluded from every number on this page", dropped)
        # Timing: partial, and the page has to say which cells.
        self.assertIn("timing.json", timing)
        self.assertIn("grading still counts", timing)
        self.assertNotIn("every number on this page", timing)
        # Pairing: partial in the other direction. (Headings are escaped for
        # the page, so the apostrophe arrives as &#39;.)
        self.assertIn("Change column only", pairing)
        self.assertIn("own configuration", pairing)
        self.assertNotIn("every number on this page", pairing)
        # Every entry still appears, under exactly one heading.
        for item in self.benchmark["exclusions"]:
            self.assertEqual(html.count(item["path"].replace("/", "/")), 1, item["path"])

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_a_windows_path_is_classified_the_same_as_a_posix_one(self):
        # The aggregator writes absolute native paths, so on Windows every
        # exclusion path is backslash-separated.
        body = "\n".join(script_bodies(VIEWER_HTML))
        source = body.split("// ---- Start ----")[0]
        source = source.replace("/*__EMBEDDED_DATA__*/", "const EMBEDDED_DATA = {runs: []};")
        entries = [
            {"path": r"D:\ws\iteration-1\eval-0\with_skill\run-1\timing.json",
             "reason": "[C12:schema_invalid=error] failed timing.json schema validation",
             "errors": []},
            {"path": r"D:\ws\iteration-1\eval-0\with_skill\run-1\grading.json",
             "reason": "[C12:schema_invalid=error] failed grading.json schema validation",
             "errors": []},
        ]
        harness = (
            "const document = {addEventListener(){}, getElementById(){return null},"
            " querySelector(){return null}, querySelectorAll(){return []}};\n"
            + source
            + "\nconsole.log(JSON.stringify("
            + json.dumps(entries) + ".map(exclusionKind)));\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "kinds.js"
            script.write_text(harness, encoding="utf-8")
            out = subprocess.run([shutil.which("node"), str(script)], capture_output=True,
                                 text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout), ["timing", "dropped"])


class RefusedPrimaryRole(unittest.TestCase):
    """When no primary configuration produced a usable run, the aggregator
    writes `primary: null`, leaves the survivor labelled baseline and exits
    non-zero -- deliberately, because promoting the survivor would read as a
    report about the configuration under test when it produced nothing. The
    viewer must not undo that in the one place the user actually looks."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = build(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_fixture_records_the_refusal(self):
        data = json.loads(
            (self.root / "malformed-run" / "iteration-1" / "benchmark.json")
            .read_text(encoding="utf-8"))
        self.assertIn("primary", data)
        self.assertIsNone(data["primary"])
        self.assertEqual(data["baseline"], "without_skill")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_a_declared_null_is_not_a_missing_declaration(self):
        body = "\n".join(script_bodies(VIEWER_HTML))
        source = body.split("// ---- Start ----")[0]
        source = source.replace("/*__EMBEDDED_DATA__*/", "const EMBEDDED_DATA = {runs: []};")
        cases = {
            # The case the guard exists for: a config the inference would
            # happily promote, next to an explicit refusal to name one.
            "refused": [["with_skill", "without_skill"],
                        {"primary": None, "baseline": "without_skill"}],
            # No key at all: an older or hand-written benchmark. Infer, as before.
            "absent": [["with_skill", "without_skill"], {}],
            "declared": [["with_skill", "without_skill"],
                         {"primary": "with_skill", "baseline": "without_skill"}],
            "baseline_refused": [["with_skill"],
                                 {"primary": "with_skill", "baseline": None}],
        }
        harness = (
            "const document = {addEventListener(){}, getElementById(){return null},"
            " querySelector(){return null}, querySelectorAll(){return []}};\n"
            + source
            + "\nconst cases = " + json.dumps(cases) + ";"
            + "\nconst out = {};"
            + "\nfor (const k in cases) out[k] = resolveRoles(cases[k][0], cases[k][1]);"
            + "\nconsole.log(JSON.stringify(out));\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "roles.js"
            script.write_text(harness, encoding="utf-8")
            out = subprocess.run([shutil.which("node"), str(script)], capture_output=True,
                                 text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        got = json.loads(out.stdout)
        self.assertIsNone(got["refused"]["primary"],
                          "the viewer promoted a configuration the aggregator refused to name")
        self.assertTrue(got["refused"]["primaryRefused"])
        self.assertEqual(got["absent"]["primary"], "with_skill",
                         "inference broke for benchmarks that declare no roles")
        self.assertFalse(got["absent"]["primaryRefused"])
        self.assertEqual(got["declared"]["primary"], "with_skill")
        self.assertIsNone(got["baseline_refused"]["baseline"])

    def test_the_page_says_the_comparison_is_incomplete(self):
        body = "\n".join(script_bodies(VIEWER_HTML))
        self.assertIn("This is not a comparison", body)
        self.assertIn("roles.primaryRefused", body)
        # The survivor is named as the baseline -- the thing measured AGAINST,
        # not the subject.
        self.assertIn("is the baseline", body)
        self.assertIn("measured AGAINST", body)
        # And the empty primary column says why it is empty.
        self.assertIn("(none produced a usable run)", body)


class SummaryFallbackHonesty(unittest.TestCase):
    """V3 4.6 and R12: a rejected run_summary must be disclosed, and the
    recomputed values must not invent a spread."""

    def test_a_rejected_summary_block_is_named_on_the_page(self):
        body = "\n".join(script_bodies(VIEWER_HTML))
        self.assertIn("rejectedSummaries", body)
        self.assertIn("recomputed from", body)

    def test_the_stats_comment_no_longer_claims_an_untrue_parity(self):
        source = VIEWER_HTML
        self.assertNotIn("Matches\n    // aggregate_benchmark.calculate_stats exactly", source)
        self.assertNotIn("0 for a single observation", source)


class EvalReviewPlaceholders(unittest.TestCase):
    """V3 4.1 / R22. All three placeholders carry caller text; all three need
    escaping; and an unescaped one must not become live markup."""

    def test_no_placeholder_sits_in_a_markup_context(self):
        # __SKILL_NAME_PLACEHOLDER__ was in <title> (RCDATA: "</title>" ends the
        # element) and in <h1><span>; __SKILL_DESCRIPTION_PLACEHOLDER__ was in
        # body HTML. Both fired injected handlers.
        #
        # Comments are stripped first: the guidance block quotes a title tag
        # while explaining why nothing may be substituted into one, and an
        # unstripped search matched the explanation instead of the element.
        html = re.sub(r"<!--.*?-->", "", EVAL_REVIEW_HTML, flags=re.S)
        title = re.search(r"<title>(.*?)</title>", html, re.S)
        self.assertIsNotNone(title)
        self.assertNotIn("PLACEHOLDER", title.group(1))
        for element_id in ("skill-name", "skill-desc"):
            span = re.search(r'<span id="%s">(.*?)</span>' % element_id, html)
            self.assertIsNotNone(span, element_id + " span is gone")
            self.assertEqual(span.group(1), "",
                             element_id + " is filled from markup rather than textContent")

    def test_the_name_and_description_arrive_inside_inert_templates(self):
        html = re.sub(r"<!--.*?-->", "", EVAL_REVIEW_HTML, flags=re.S)
        for placeholder in ("__SKILL_NAME_PLACEHOLDER__", "__SKILL_DESCRIPTION_PLACEHOLDER__"):
            match = re.search(r"<template[^>]*>" + placeholder + r"</template>", html)
            self.assertIsNotNone(match, placeholder + " is not inside a <template>")
        # Nested, so a lone "</template>" in a value lands in an inert parent
        # rather than in the document.
        self.assertIn('<template id="skill-meta"><template id="skill-name-src">', html)

    def test_all_three_placeholders_are_covered_by_the_guidance(self):
        # The template's own comment block used to document escaping for the
        # data placeholder alone -- next to two that needed it just as much.
        comments = re.findall(r"<!--(.*?)-->", EVAL_REVIEW_HTML, re.S)
        guidance = "\n".join(comments)
        for placeholder in ("__EVAL_DATA_PLACEHOLDER__", "__SKILL_NAME_PLACEHOLDER__",
                            "__SKILL_DESCRIPTION_PLACEHOLDER__"):
            self.assertIn(placeholder, guidance, placeholder + " has no escaping guidance")
        self.assertIn("html.escape", guidance)
        self.assertIn("THREE PLACEHOLDERS", guidance)

    def test_an_unescaped_substitution_is_reported_on_the_page(self):
        body = "\n".join(script_bodies(EVAL_REVIEW_HTML))
        self.assertIn("showUnescapedWarning", body)
        self.assertIn("hadMarkup", body)
        # A console warning is not visible to the person reviewing the page.
        self.assertIn("This page was built with unescaped text", body)

    def test_neither_page_truncates_its_own_script(self):
        # The literal "</script" ends a script element wherever it appears --
        # including inside a // comment, which truncated this file's entire
        # logic once. script_bodies() cuts at the same point, so the check has
        # to be that the LAST body still contains its final statement.
        for name, html, tail in (("eval_review.html", EVAL_REVIEW_HTML, "})();"),
                                 ("viewer.html", VIEWER_HTML, "renderBenchmark();")):
            bodies = script_bodies(html)
            self.assertIn(tail, bodies[-1], name + ": the inline script was truncated")
            for body in bodies:
                self.assertNotIn("</script", body.lower(), name)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_page_script_parses(self):
        # A syntax error leaves every span empty and the table unrendered, and
        # nothing in a static assertion notices.
        for name, html in (("eval_review.html", EVAL_REVIEW_HTML), ("viewer.html", VIEWER_HTML)):
            source = script_bodies(html)[-1].replace(
                "/*__EMBEDDED_DATA__*/", "const EMBEDDED_DATA = {runs: []};")
            with tempfile.TemporaryDirectory() as tmp:
                script = Path(tmp) / "page.js"
                script.write_text(source, encoding="utf-8")
                result = subprocess.run([shutil.which("node"), "--check", str(script)],
                                        capture_output=True, text=True, encoding="utf-8",
                                        timeout=60)
            self.assertEqual(result.returncode, 0, name + ": " + result.stderr)


class OfflineRendering(unittest.TestCase):
    def test_no_font_cdn_on_either_page(self):
        for name, html in (("viewer.html", VIEWER_HTML),
                           ("eval_review.html", EVAL_REVIEW_HTML)):
            self.assertNotIn("fonts.googleapis.com", html, name)
            self.assertNotIn("fonts.gstatic.com", html, name)

    def test_spreadsheet_preview_degrades_to_a_download(self):
        # SheetJS is the one remaining remote dependency; offline it used to
        # leave "Error rendering spreadsheet: XLSX is not defined" and no way
        # to see the file.
        body = "\n".join(script_bodies(VIEWER_HTML))
        fn = body[body.index("function renderXlsx"):]
        self.assertIn('typeof XLSX === "undefined"', fn)
        self.assertIn("getDownloadUri(file)", fn[:fn.index("XLSX.read")])


class PageScriptHarness:
    """Run viewer.html's own script under node and read what it produced.

    A check has to observe the property, not a proxy for it.
    Grepping viewer.html for the word "abstain" would pass over a page that
    computed a rate of 0% and printed the word in a caption, and grepping it
    for "underspecified" would pass over a page that names the reason in a
    comment and still draws its badge as "reason not recorded". So the page's
    script is executed against a stubbed document and the resulting HTML is
    parsed.

    `page` defaults to the checked-in template. Passing a generated page - the
    one `--static` writes, or the one the server sends - runs the same checks
    against the artifact a reader actually opens.
    """

    node = shutil.which("node")

    def _run_js(self, call, embedded=None, page=None):
        """Execute one render function against a stubbed document."""
        if not self.node:
            self.skipTest("node is not installed")
        body = "\n".join(script_bodies(page if page is not None else VIEWER_HTML))
        source = body.split("// ---- Start ----")[0]
        if embedded is not None:
            source = source.replace(
                "/*__EMBEDDED_DATA__*/",
                "const EMBEDDED_DATA = " + json.dumps(embedded) + ";")
        harness = (
            "const __sinks = {};\n"
            "function __el(id){ if(!__sinks[id]) __sinks[id] = "
            "{id, style:{}, classList:{add(){},remove(){},toggle(){}}, "
            "innerHTML:'', appendChild(){}};\n  return __sinks[id]; }\n"
            "const document = {addEventListener(){}, getElementById:__el,"
            " querySelector(){return null}, querySelectorAll(){return []},"
            " createElement(){return __el('scratch')}};\n"
            + source
            + "\n" + call + "\n"
            + "console.log(JSON.stringify(Object.fromEntries("
            "Object.entries(__sinks).map(([k,v]) => [k, v.innerHTML]))));\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "harness.js"
            script.write_text(harness, encoding="utf-8")
            out = subprocess.run([self.node, str(script)], capture_output=True,
                                 text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def _eval_js(self, expression, page=None):
        """Evaluate one expression inside the page's own script scope.

        Reads a value out of the page rather than out of its source text, so a
        table that parses differently from how it reads is still caught.
        """
        sinks = self._run_js(
            "__el('probe').innerHTML = JSON.stringify(" + expression + ");",
            {"runs": []} if page is None else None, page)
        return json.loads(sinks["probe"])

    def _benchmark_html(self, benchmark=None):
        sinks = self._run_js(
            "renderBenchmark();", {"runs": [], "benchmark": benchmark
                                   if benchmark is not None else self.benchmark})
        return sinks["benchmark-content"]

    def _grades_html(self, grading, assertions=None):
        run = {"id": "r", "grading": grading, "timing": None,
               "assertions": assertions or []}
        sinks = self._run_js(
            "renderGrades(" + json.dumps(run) + ");", {"runs": []})
        return sinks["grades-content"]

    @staticmethod
    def _text(html):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html)).strip()

    @staticmethod
    def _plain(html):
        """_text with character references resolved.

        The page escapes what it writes, so a sentence held in the page's own
        data comes back through innerHTML as `nobody else&#39;s`. Comparing
        against the source string needs the reference resolved; comparing
        against a pre-escaped copy would only assert that two spellings of the
        escaper agree.
        """
        return html_unescape(PageScriptHarness._text(html))


class TernaryVerdicts(PageScriptHarness, unittest.TestCase):
    """Ternary verdicts, executed rather than read."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = build(Path(cls._tmp.name))
        cls.benchmark = json.loads(
            (cls.root / "abstain" / "iteration-1" / "benchmark.json")
            .read_text(encoding="utf-8"))
        cls.legacy_grading = json.loads(
            (cls.root / "previous-contract" / "iteration-1"
             / "eval-0-bool-verdicts" / "with_skill" / "run-1"
             / "grading.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    # ---- the all-abstain end-to-end case --------------------------------

    def test_an_all_abstained_eval_never_renders_as_a_zero(self):
        """The whole point. `0%` on this page reads as "failed everything"."""
        html = self._benchmark_html()
        section = html[html.index("every-check-abstained"):]
        section = section[:section.index("</table>")]
        self.assertNotIn(
            "0%", self._text(section),
            "an eval nobody could rule on rendered a percentage:\n" + section)
        self.assertIn("no rate", self._text(section))

    def test_the_run_row_denominator_is_the_ruled_on_count(self):
        html = self._benchmark_html()
        section = html[html.index("every-check-abstained"):]
        section = section[:section.index("</table>")]
        # 0 of 0 ruled on, 2 of 2 abstained. `0/2` here would say the run was
        # graded on two checks and passed none.
        self.assertIn("0/0 ruled on", self._text(section))
        self.assertIn("2/2", self._text(section))

    def test_a_thin_result_and_a_complete_one_do_not_render_alike(self):
        """100% over 2 ruled-on checks beside 100% over 11."""
        html = self._benchmark_html()
        section = html[html.index("thin-versus-complete"):]
        section = section[:section.index("</table>")]
        text = self._text(section)
        # Both sides read 100%. The abstention column is the only thing that
        # separates them, so it must be present and it must differ.
        self.assertEqual(text.count("100%"), 4, text)
        self.assertIn("9/11", text, "the thin side's abstentions are missing")
        self.assertIn("0/11", text, "the complete side's zero is missing")

    def test_the_headline_pass_rate_excludes_abstentions_from_the_denominator(self):
        html = self._benchmark_html()
        head = html[:html.index("Test-by-test detail")]
        text = self._text(head)
        # with_skill ruled on 2 checks and passed both: 100%, not 2/15 = 13%.
        self.assertIn("2/2 graded checks", text)
        self.assertIn("13 abstained of 15", text)
        # without_skill ruled on 11 and passed 11.
        self.assertIn("11/11 graded checks", text)

    def test_abstentions_have_a_row_of_their_own_and_no_direction(self):
        html = self._benchmark_html()
        head = html[:html.index("Test-by-test detail")]
        self.assertIn("Abstained", self._text(head))
        self.assertIn("no direction is better", self._text(head))
        row = head[head.index("<strong>Abstained</strong>"):]
        row = row[:row.index("</tr>")]
        # Never coloured as an improvement or a regression: signing this
        # number would be the page taking a side the data does not support.
        self.assertNotIn("benchmark-delta-better", row)
        self.assertNotIn("benchmark-delta-worse", row)

    def test_both_typed_reasons_reach_the_page(self):
        html = self._benchmark_html()
        section = html[html.index("both-reasons"):]
        text = self._text(section)
        self.assertIn("jurisdiction", text)
        self.assertIn("evidence", text)

    def test_an_abstained_mark_is_never_drawn_as_a_pass_or_a_fail(self):
        """The comparison table's marks, by class, not by caption.

        Found by mutation: pointing the abstain class at
        `benchmark-delta-worse` left every text assertion green while the page
        drew ◐ in the failure colour, which is the previous contract's
        rendering under a new glyph.
        """
        html = self._benchmark_html()
        marks = re.findall(r'<span class="([^"]*)"[^>]*>◐', html)
        self.assertTrue(marks, "no abstained mark was rendered at all")
        for cls in marks:
            self.assertIn("benchmark-abstain", cls)
            self.assertNotIn("benchmark-delta-worse", cls)
            self.assertNotIn("benchmark-delta-better", cls)

    def test_a_configuration_with_no_graded_check_has_no_headline_rate(self):
        """The pooled headline, when nothing anywhere was ruled on.

        Found by mutation: `microAverage` returning `rate: 0` for a zero
        denominator put `0%` back at the top of the page — the single most
        misleading cell in the artifact, because it is the one a reader quotes.
        """
        only_abstained = json.loads(json.dumps(self.benchmark))
        only_abstained["runs"] = [r for r in only_abstained["runs"]
                                  if r["eval_id"] == 0]
        # What the aggregator emits for this tree: no rate on either side, so
        # no delta either.
        for config in ("with_skill", "without_skill"):
            only_abstained["run_summary"][config]["pass_rate"] = None
        only_abstained["run_summary"]["delta"]["pass_rate"] = {
            "value": None, "formatted": "—",
            "polarity": "higher_is_better", "better": None}
        html = self._benchmark_html(only_abstained)
        head = html[:html.index("Test-by-test detail")]

        # The headline row alone. The Abstained row below it legitimately
        # reads 100%, and a substring check over the whole table would trip
        # on it while missing the cell that matters.
        row = head[head.index("<strong>Pass rate</strong>"):]
        row = row[:row.index("</tr>")]
        text = self._text(row)
        self.assertNotIn(
            "%", text, "a rate over nothing reached the headline:\n" + text)
        self.assertIn("no rate", text)
        self.assertIn("0 of 2 checks were ruled on", text)

        # And no percentage anywhere in the macro row either.
        macro = head[head.index("<strong>Pass rate per run</strong>"):]
        macro = macro[:macro.index("</tr>")]
        self.assertNotIn("%", self._text(macro), macro)

    # ---- per-run grades panel -------------------------------------------

    def test_the_grades_panel_gives_abstentions_their_own_visual_state(self):
        grading = json.loads(
            (self.root / "abstain" / "iteration-1"
             / "eval-2-both-reasons" / "with_skill" / "run-1" / "grading.json")
            .read_text(encoding="utf-8"))
        html = self._grades_html(grading)
        # Neither the pass mark nor the fail mark.
        self.assertIn('class="assertion-status abstain"', html)
        self.assertNotIn('class="assertion-status pass"', html)
        self.assertNotIn('class="assertion-status fail"', html)
        # And the typed reason on screen, not only in the JSON.
        self.assertIn("abstained: jurisdiction", html)
        self.assertIn("abstained: evidence", html)

    def test_the_grades_panel_says_there_is_no_rate_rather_than_zero(self):
        grading = json.loads(
            (self.root / "abstain" / "iteration-1"
             / "eval-0-every-check-abstained" / "with_skill" / "run-1"
             / "grading.json").read_text(encoding="utf-8"))
        html = self._grades_html(grading)
        text = self._text(html)
        self.assertIn("no rate", text)
        self.assertNotIn("0%", text)
        self.assertIn("This is not a score of zero", text)
        self.assertIn("2 abstained of 2", text)

    def test_the_grades_summary_line_reports_abstentions(self):
        grading = json.loads(
            (self.root / "abstain" / "iteration-1"
             / "eval-1-thin-versus-complete" / "with_skill" / "run-1"
             / "grading.json").read_text(encoding="utf-8"))
        text = self._text(self._grades_html(grading))
        self.assertIn("2 passed, 0 failed, 9 abstained of 11", text)

    # ---- the previous contract -------------------------------------------

    def test_a_legacy_boolean_is_named_as_the_previous_contract(self):
        text = self._text(self._grades_html(self.legacy_grading))
        self.assertIn("previous contract", text)
        # And NOT translated: `false` meant either "verified false" or "could
        # not tell", and the file does not say which.
        self.assertNotIn('class="assertion-status fail"',
                         self._grades_html(self.legacy_grading))
        self.assertNotIn('class="assertion-status pass"',
                         self._grades_html(self.legacy_grading))

    def test_generate_review_reports_the_previous_contract_on_stderr(self):
        out = self.root.parent / "legacy-out.html"
        result = subprocess.run(
            [sys.executable, str(VIEWER_DIR / "generate_review.py"),
             str(self.root / "previous-contract" / "iteration-1"),
             "--skill-name", "demo", "--static", str(out)],
            capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("previous grading contract", result.stderr)
        self.assertIn("validate_grading", result.stderr)


class AbstentionReasonTaxonomy(PageScriptHarness, unittest.TestCase):
    """The typed abstention reasons, and the two states that are not reasons.

    The page shipped with two hand-maintained whitelists - `ABSTAIN_REASON_TEXT`
    and `abstainReasonOf` - while the contract's enum grew to three. A
    schema-VALID grading carrying `underspecified` therefore rendered as
    "abstained: reason not recorded" and "No abstainReason was recorded": the
    page reporting absent data over present data, which is worse than showing
    an unknown value plainly, because it accuses the producer of an omission
    that never happened and sends the reader to fix the grader instead of the
    sentence.

    Four states are exercised, because the page has to tell all four apart:

        jurisdiction    someone else can rule    -> reassign the judge
        evidence        this judge could have    -> supply the artifact
        underspecified  nobody could, ever       -> rewrite the assertion
        "busy"          recorded, not in the enum
        (absent)        nothing recorded at all

    Only the last of those five may say nothing was recorded.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = build(Path(cls._tmp.name))
        cls.workspace = (cls.root / "reason-taxonomy" / "iteration-1")
        cls.run_dir = (cls.workspace / "eval-0-four-reasons"
                       / "with_skill" / "run-1")
        cls.benchmark = json.loads(
            (cls.workspace / "benchmark.json").read_text(encoding="utf-8"))
        cls.grading = json.loads(
            (cls.run_dir / "grading.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    @staticmethod
    def _badges(html):
        """{badge label -> modifier class} for every reason badge on a page."""
        return {label: cls for cls, label in re.findall(
            r'<span class="assertion-reason ([^"]*)">([^<]*)</span>', html)}

    # ---- the two reason sets are one reason set --------------------------

    def test_the_pages_reason_table_is_the_contracts_enum(self):
        """The divergence itself, caught by something other than a reader.

        The enum lives in scripts/validate_grading.py and the page cannot
        import it, so nothing but a test that reads both can notice them
        drifting apart. This reads the page's table by executing the page.
        """
        keys = self._eval_js("Object.keys(ABSTAIN_REASONS)")
        self.assertEqual(
            keys, list(ABSTAIN_REASONS),
            "viewer.html's ABSTAIN_REASONS and validate_grading.ABSTAIN_REASONS "
            "disagree. They are the same enum on two sides of a boundary the "
            "page cannot import across: add the reason to the table in "
            "viewer.html, with its own sentence, repair and `cls`.")

    def test_the_page_has_exactly_one_reason_whitelist(self):
        """The whitelist is the table's key set, not a second list beside it.

        Executed, not grepped: a leftover second list would be caught here only
        if it still decided anything, and this asks the page to decide.
        """
        verdicts = self._eval_js(
            "Object.keys(ABSTAIN_REASONS).concat(['busy']).map(r => "
            "abstainReasonState({abstainReason: r}).known)")
        self.assertEqual(verdicts, [True] * len(ABSTAIN_REASONS) + [False])

    def test_every_reason_carries_its_own_wording_repair_and_class(self):
        table = self._eval_js("ABSTAIN_REASONS")
        for field in ("text", "repair", "cls"):
            values = [entry[field] for entry in table.values()]
            self.assertTrue(all(v and v.strip() for v in values), field)
            self.assertEqual(
                len(set(values)), len(values),
                f"two reasons share a {field!r}, so the page cannot be telling "
                f"a reader what to do differently about them")

    # ---- the grades panel ------------------------------------------------

    def test_each_reason_renders_with_its_own_text(self):
        text = self._plain(self._grades_html(self.grading))
        table = self._eval_js("ABSTAIN_REASONS")
        for reason in ABSTAIN_REASONS:
            self.assertIn("abstained: " + reason, text, reason)
            self.assertIn(table[reason]["text"], text, reason)
            self.assertIn(table[reason]["repair"], text, reason)

    def test_only_the_expectation_with_no_reason_says_nothing_was_recorded(self):
        """The defect, stated as a count.

        Three recognized reasons, one unrecognized value and one genuine
        absence: exactly one of the five may be reported as unrecorded.
        """
        text = self._text(self._grades_html(self.grading))
        self.assertEqual(
            text.count("No abstainReason was recorded"), 1,
            "a recorded reason was reported as never recorded:\n" + text)
        self.assertEqual(text.count("abstained: reason not recorded"), 1, text)

    def test_underspecified_is_not_drawn_as_a_variant_of_the_other_two(self):
        """Its own badge class, and its own resolved colour behind it.

        The class alone proves nothing - three classes can resolve to the same
        slate - so the stylesheet is read and the values compared after
        substituting the custom properties they refer to.
        """
        badges = self._badges(self._grades_html(self.grading))
        classes = {reason: badges["abstained: " + reason]
                   for reason in ABSTAIN_REASONS}
        self.assertEqual(len(set(classes.values())), len(classes), classes)

        under = css_declarations(VIEWER_HTML,
                                 ".assertion-reason." + classes["underspecified"])
        self.assertTrue(under, "the underspecified badge has no style rule")
        for other in ("jurisdiction", "evidence"):
            rule = css_declarations(
                VIEWER_HTML, ".assertion-reason." + classes[other]) \
                or css_declarations(VIEWER_HTML, ".assertion-reason")
            for prop in ("color", "background"):
                self.assertNotEqual(
                    under.get(prop), rule.get(prop),
                    f"underspecified shares its {prop} with {other}, so it "
                    f"reads as a near-miss of a reason with a different repair")
        self.assertIn("border-color", under,
                      "underspecified needs a mark of its own, not just a tint")

    def test_the_repair_named_for_underspecified_is_the_readers_own(self):
        """The reason it earns a slot: the fix belongs to whoever is reading."""
        repair = self._eval_js("ABSTAIN_REASONS.underspecified.repair")
        self.assertIn("rewrite the assertion", repair.lower())
        text = self._eval_js("ABSTAIN_REASONS.underspecified.text").lower()
        self.assertIn("cannot be graded as written", text)

    def test_an_unrecognized_reason_is_recorded_data_not_absent_data(self):
        html = self._grades_html(self.grading)
        badges = self._badges(html)
        label = next(k for k in badges if "busy" in k)
        self.assertNotIn("not recorded", label,
                         "a value the page does not know was reported as absent")
        # And not wearing a recognized reason's clothes either.
        known = {badges["abstained: " + r] for r in ABSTAIN_REASONS}
        self.assertNotIn(badges[label], known)
        # The sentence under it has to say the value arrived and name it.
        text = self._text(html)
        self.assertIn("“busy” was recorded", text)

    # ---- the benchmark tab -----------------------------------------------

    def test_the_comparison_table_marks_and_legend_carry_every_reason(self):
        html = self._benchmark_html()
        badges = self._badges(html)
        for reason in ABSTAIN_REASONS:
            self.assertIn(reason, badges, reason)
        self.assertTrue(any("busy" in k for k in badges), badges)
        # The legend under the table explains each mark it drew, with its
        # repair - a mark with no entry is a count with no meaning.
        legend = html[html.index("abstain-legend"):]
        legend = self._plain(legend[:legend.index("</ul>")])
        table = self._eval_js("ABSTAIN_REASONS")
        for reason in ABSTAIN_REASONS:
            self.assertIn(table[reason]["repair"], legend, reason)

    def test_an_abstained_mark_is_still_an_abstained_mark(self):
        """A reason is not a fourth verdict. Every ◐ stays in the abstain class.

        Found by mutation while adding the third reason: colouring the MARK by
        reason rather than the badge would put `underspecified` outside the
        class the abstain checks assert on, and every one of them would still
        pass.
        """
        # Only the cell marks: each carries a title. The caption below the
        # table draws a bare ◐ of its own as a key, and counting that one would
        # make this assertion agree with itself rather than with the data.
        html = self._benchmark_html()
        marks = re.findall(r'<span class="([^"]*)" title="[^"]*">◐', html)
        self.assertEqual(len(marks), 5, marks)
        for cls in marks:
            self.assertIn("benchmark-abstain", cls)

    # ---- both viewers ----------------------------------------------------

    def test_all_three_reasons_render_in_the_served_and_the_static_page(self):
        """The template is the artifact, on both surfaces - proved, not assumed.

        `--static` and the server both hand the reader whatever `generate_html`
        substituted into viewer.html, so both pages are rendered here and the
        same three sentences are required from each.
        """
        static_path = Path(self._tmp.name) / "reason-taxonomy.html"
        result = subprocess.run(
            [sys.executable, str(VIEWER_DIR / "generate_review.py"),
             str(self.workspace), "--skill-name", "demo",
             "--static", str(static_path)],
            capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        pages = {"--static": static_path.read_text(encoding="utf-8"),
                 "served": self._serve_once()}

        table = self._eval_js("ABSTAIN_REASONS")
        for name, page in pages.items():
            sinks = self._run_js(
                "renderGrades(EMBEDDED_DATA.runs.find("
                "r => r.grading && r.grading.summary.abstained > 0));",
                None, page)
            text = self._text(sinks["grades-content"])
            for reason in ABSTAIN_REASONS:
                self.assertIn("abstained: " + reason, text, name + "/" + reason)
                self.assertIn(table[reason]["text"], text, name + "/" + reason)
            self.assertEqual(text.count("No abstainReason was recorded"), 1,
                             name + ":\n" + text)

    def _serve_once(self) -> str:
        """GET / from a real ReviewServer pointed at the fixture workspace."""
        feedback = self.workspace / "feedback.json"
        handler = partial(gr.ReviewHandler, self.workspace, "demo", feedback,
                          {}, self.workspace / "benchmark.json")
        server = gr.ReviewServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=30)
            try:
                conn.request("GET", "/", headers={"Host": "localhost:%d" % port})
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                body = response.read()
            finally:
                conn.close()
        finally:
            server.shutdown()
            server.server_close()
        return body.decode("utf-8")


if __name__ == "__main__":
    unittest.main()
