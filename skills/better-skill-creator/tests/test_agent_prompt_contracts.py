#!/usr/bin/env python3
"""Tests that the sub-agent prompts, the schema reference, and the consumers agree.

Run from the skill root:

    python -m unittest tests.test_agent_prompt_contracts -v
    python -m tests.test_agent_prompt_contracts

Why this file exists: `agents/*.md` is the only part of the bundle no program
reads. Nothing imports it, nothing validates it, and nothing notices when the
shape it tells a sub-agent to emit stops matching the shape a consumer reads or
`references/schemas.md` documents. That is not a hypothetical - it is R18, and
the drift it should have caught (an assignment key that gained three audit
fields; a schema doc still describing a write path that had been replaced) was
found by a human verifier instead.

The checks are structural on purpose. They compare *key trees* - field names and
nesting, with every leaf value discarded - so a prompt is free to reword its
slots, its guidance, and its examples without failing a test, and is not free to
rename a field, move it, or add one that nothing downstream knows about.

What is covered:

  1. Every ```json block in agents/*.md is valid JSON.
  2. Each agent's documented output block has the same key tree as the block for
     that artifact in references/schemas.md.
  3. The blocks grader.md promises are always present are exactly the ones
     validate_grading requires - probed by removing each and checking it fails.
  4. The de-identification reference implementation in comparator.md is executed,
     and the assignment key it really writes matches the documented one. The
     recorded seed is replayed to confirm it reproduces the A/B mapping.
  5. The eight top-level benchmark.json keys analyzer.md tells the analyst to
     expect are exactly what aggregate_benchmark emits and what schemas.md shows.

What is NOT covered: prose. A sentence in either file can still contradict the
mechanism without failing here. Item 4 is the closest thing to a guard against
that, because it runs the code the prose describes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.validate_grading import validate_grading_file  # noqa: E402

AGENTS = SKILL_ROOT / "agents"
SCHEMAS_MD = SKILL_ROOT / "references" / "schemas.md"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def fenced_blocks(path: Path, language: str) -> list[str]:
    """Every ```<language> block in a markdown file, in order."""
    text = path.read_text(encoding="utf-8")
    return re.findall(rf"```{language}\n(.*?)```", text, re.S)


def json_blocks(path: Path) -> list:
    """Every ```json block in a markdown file, parsed."""
    return [json.loads(b) for b in fenced_blocks(path, "json")]


def find_block(blocks, *required_keys):
    """The first parsed block that is an object carrying all of `required_keys`."""
    for block in blocks:
        if isinstance(block, dict) and all(k in block for k in required_keys):
            return block
    return None


def key_tree(obj):
    """Field names and nesting only; every leaf value discarded.

    Lists collapse to their first element, so a one-entry example and a
    three-entry one compare equal as long as the entries have the same shape.
    """
    if isinstance(obj, dict):
        return {k: key_tree(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [key_tree(v) for v in obj[:1]]
    return None


def shape_mismatch(a, b, path="") -> str | None:
    """First structural disagreement between two key trees, or None.

    An empty array matches an array of anything. `"needs_review": []` and
    `"needs_review": ["{Item_It_Flagged_For_A_Human}"]` are the same schema -
    one example happens to show the empty case, and a test that called that a
    contract violation would be noise that trains people to ignore it.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            where = f"{path}.{key}" if path else key
            if key not in a:
                return f"{where}: absent on the left, present on the right"
            if key not in b:
                return f"{where}: present on the left, absent on the right"
            found = shape_mismatch(a[key], b[key], where)
            if found:
                return found
        return None
    if isinstance(a, list) and isinstance(b, list):
        if not a or not b:
            return None
        return shape_mismatch(a[0], b[0], f"{path}[]")
    if isinstance(a, (dict, list)) != isinstance(b, (dict, list)):
        return f"{path or '<root>'}: {type(a).__name__} vs {type(b).__name__}"
    return None


# --------------------------------------------------------------------------
# 1. The prompts' own JSON is JSON
# --------------------------------------------------------------------------

class AgentJsonBlocksTest(unittest.TestCase):
    """A slot-bearing example is still expected to parse."""

    def test_every_json_block_in_every_agent_prompt_parses(self):
        found = 0
        for path in sorted(AGENTS.glob("*.md")):
            for idx, raw in enumerate(fenced_blocks(path, "json"), start=1):
                with self.subTest(prompt=path.name, block=idx):
                    try:
                        json.loads(raw)
                    except json.JSONDecodeError as exc:
                        self.fail(f"{path.name} json block {idx}: {exc}")
                    found += 1
        self.assertGreater(found, 0, "no ```json blocks found under agents/")


# --------------------------------------------------------------------------
# 2. Prompt output shapes == references/schemas.md
# --------------------------------------------------------------------------

class PromptVsSchemaReferenceTest(unittest.TestCase):
    """The shape a sub-agent is told to emit is the shape the doc records."""

    @classmethod
    def setUpClass(cls):
        cls.schemas = json_blocks(SCHEMAS_MD)

    def assert_same_shape(self, agent_file, agent_keys, schema_keys, artifact):
        agent_block = find_block(json_blocks(AGENTS / agent_file), *agent_keys)
        self.assertIsNotNone(
            agent_block, f"no {artifact} block found in agents/{agent_file}")
        doc_block = find_block(self.schemas, *schema_keys)
        self.assertIsNotNone(
            doc_block, f"no {artifact} block found in references/schemas.md")
        found = shape_mismatch(key_tree(agent_block), key_tree(doc_block))
        self.assertIsNone(
            found,
            f"{artifact}: agents/{agent_file} (left) and references/schemas.md "
            f"(right) disagree about field names or nesting -- {found}",
        )

    def test_grading_json(self):
        self.assert_same_shape(
            "grader.md", ("expectations", "summary", "claims"),
            ("expectations", "summary", "claims"), "grading.json")

    def test_comparison_json(self):
        self.assert_same_shape(
            "comparator.md", ("winner", "rubric"),
            ("winner", "rubric"), "comparison.json")

    def test_analysis_json(self):
        self.assert_same_shape(
            "analyzer.md", ("comparison_summary", "improvement_suggestions"),
            ("comparison_summary", "improvement_suggestions"), "analysis.json")


# --------------------------------------------------------------------------
# 3. grader.md's "always present" == validate_grading's "required"
# --------------------------------------------------------------------------

class GraderRequiredBlocksTest(unittest.TestCase):
    """`expectations` and `summary` are required by both, and nothing else is.

    grader.md states that those two are always written and that `claims`,
    `user_notes_summary` and `eval_feedback` may be omitted. The validator has
    to hold the same line: requiring an optional block would make a conforming
    grader fail, and accepting a missing required one is the silent-zero this
    whole pipeline was rebuilt to close.
    """

    ALWAYS_PRESENT = ("expectations", "summary")
    OMITTABLE = ("claims", "user_notes_summary", "eval_feedback")

    @classmethod
    def setUpClass(cls):
        cls.full = find_block(
            json_blocks(AGENTS / "grader.md"), "expectations", "summary", "claims")
        assert cls.full is not None, "grader.md output block not found"

    def _concrete(self):
        """The grader block with its slots replaced by conforming values.

        The prompt's example is a frame - `"abstainReason": "{...}"` is a slot
        string - so it cannot be validated as-is. Only the values are
        substituted; every field name and every nesting level comes from the
        prompt itself.

        All three verdicts appear, because a substitution that only ever used
        `pass` and `fail` would keep passing if the prompt lost `abstain`
        entirely - which is the field the ternary vocabulary exists to add.
        """
        block = json.loads(json.dumps(self.full))
        block["expectations"] = [
            {"text": "first", "verdict": "pass", "abstainReason": None,
             "evidence": "seen"},
            {"text": "second", "verdict": "fail", "abstainReason": None,
             "evidence": "contradicted by row 3"},
            {"text": "third", "verdict": "abstain",
             "abstainReason": "evidence",
             "evidence": "no transcript was supplied"},
        ]
        block["summary"] = {"passed": 1, "failed": 1, "abstained": 1,
                            "total": 3, "pass_rate": 0.5}
        for claim in block.get("claims", []):
            claim["verified"] = True
            claim["type"] = "factual"
        return block

    def _errors_for(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "grading.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors, _warnings = validate_grading_file(path)
        return errors

    def test_grader_block_names_the_blocks_the_validator_requires(self):
        self.assertEqual(self._errors_for(self._concrete()), [])

    def test_removing_an_always_present_block_is_an_error(self):
        for field in self.ALWAYS_PRESENT:
            with self.subTest(removed=field):
                payload = self._concrete()
                del payload[field]
                self.assertTrue(
                    self._errors_for(payload),
                    f"validate_grading accepts a grading.json with no "
                    f"'{field}', but grader.md promises it is always written",
                )

    def test_removing_an_omittable_block_is_not_an_error(self):
        for field in self.OMITTABLE:
            with self.subTest(removed=field):
                payload = self._concrete()
                payload.pop(field, None)
                self.assertEqual(
                    self._errors_for(payload), [],
                    f"validate_grading rejects a grading.json with no "
                    f"'{field}', but grader.md says it may be omitted",
                )


# --------------------------------------------------------------------------
# 3a. grader.md says the three things the ternary vocabulary requires
# --------------------------------------------------------------------------

class GraderTernaryVocabularyTest(unittest.TestCase):
    """Prose, not shape - but three specific sentences whose absence is a bug.

    Everything else here compares key trees, deliberately, so a prompt is free
    to reword. These three are exceptions because each one is a rule the model
    follows rather than a field it emits, and losing any of them puts the
    previous contract's behaviour back into a file whose JSON block still looks
    correct.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = (AGENTS / "grader.md").read_text(encoding="utf-8")
        # Line-wrapped prose: a sentence that has to survive is checked against
        # the unwrapped text, so reflowing the paragraph is not a failure.
        cls.flat = re.sub(r"\s+", " ", cls.text)

    def assertSaid(self, phrase, note=""):
        self.assertIn(re.sub(r"\s+", " ", phrase), self.flat,
                      "agents/grader.md no longer says: " + phrase
                      + (" -- " + note if note else ""))

    def test_the_retired_rule_is_gone(self):
        """"when you genuinely cannot tell, it fails" is the defect itself."""
        self.assertNotIn(
            "the burden of proof sits on the expectation: when you genuinely",
            self.flat,
            "the retired instruction is still stated as the rule")
        # It may be quoted while being retired; it may not be an instruction.
        if "genuinely cannot tell, it fails" in self.flat:
            self.assertSaid("That rule is **retired**",
                            "the old rule is quoted without being retired")

    def test_all_three_verdicts_and_both_reasons_are_named(self):
        for token in ('"pass"', '"fail"', '"abstain"',
                      '"jurisdiction"', '"evidence"'):
            self.assertIn(token, self.flat, "grader.md never names " + token)

    def test_the_null_rate_is_stated(self):
        self.assertSaid("passed / (passed + failed)")
        self.assertSaid("never `0.0` for a run where nothing was graded")
        self.assertSaid('write `"pass_rate": null`')

    def test_the_two_sided_risk_is_stated(self):
        """Guidance that pushes either way produces a judge that lies."""
        lowered = re.sub(r"\s+", " ", self.text.lower())
        self.assertIn("abstain too freely", lowered)
        self.assertIn("abstain too rarely", lowered)
        self.assertIn("no setting of this dial that is safe", lowered)

    def test_the_single_judge_path_is_positioned_against_the_panel(self):
        self.assertSaid("single-judge path")
        self.assertSaid("composed panel")
        self.assertSaid("Use this single-judge path when")
        self.assertSaid("Use the composed panel when")

    def test_the_kept_rules_are_still_there(self):
        """C16 changed the verdict vocabulary and nothing else in this file."""
        self.assertSaid(
            "A path you were not given names a file that does not exist")
        self.assertSaid(
            "Evidence that cannot be rechecked by someone else is not evidence")
        for parameter in ("expectations", "eval_prompt", "outputs_dir",
                          "grading_path", "transcript_path", "user_notes_path"):
            self.assertIn("`" + parameter + "`", self.flat,
                          "the inputs table lost " + parameter)

    def test_a_missing_transcript_is_no_longer_a_fail(self):
        self.assertSaid("is **not a fail**")
        self.assertSaid('`abstain` with `abstainReason: "evidence"`')

    def test_the_prompt_does_not_tell_the_grader_to_write_passed(self):
        block = find_block(json_blocks(AGENTS / "grader.md"),
                           "expectations", "summary")
        self.assertNotIn("passed", block["expectations"][0],
                         "the retired boolean is still in the output frame")
        self.assertIn("verdict", block["expectations"][0])
        self.assertIn("abstainReason", block["expectations"][0])


# --------------------------------------------------------------------------
# 3b. Every grading.json example in schemas.md validates as written
# --------------------------------------------------------------------------

class SchemaExamplesValidateTest(unittest.TestCase):
    """The doc's `grading.json` blocks are run through the real validator.

    §6 states that its integers, its enum members and `pass_rate` are literal
    *because the validator checks the arithmetic between them*. That sentence
    is only true if someone checks - and the change to ternary verdicts is
    exactly the kind of edit that leaves a documented example one contract
    behind while every prose paragraph around it is updated.

    Slot strings are left alone: only `text` and `evidence` carry them, and
    the validator asks for a non-empty string in both.
    """

    def _grading_blocks(self):
        """Every block in schemas.md that is a grading.json (not a benchmark)."""
        return [b for b in json_blocks(SCHEMAS_MD)
                if isinstance(b, dict) and "expectations" in b and "summary" in b
                and "runs" not in b]

    def _errors_for(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "grading.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors, _warnings = validate_grading_file(path)
        return errors

    def test_at_least_one_grading_example_is_present(self):
        self.assertGreaterEqual(
            len(self._grading_blocks()), 2,
            "references/schemas.md should carry both the required-shape and "
            "the optional-blocks grading.json examples")

    def test_every_documented_grading_example_validates(self):
        for idx, block in enumerate(self._grading_blocks(), start=1):
            with self.subTest(example=idx):
                self.assertEqual(
                    self._errors_for(block), [],
                    f"references/schemas.md grading.json example {idx} does "
                    f"not validate against scripts.validate_grading")

    def test_the_documented_examples_exercise_all_three_verdicts(self):
        """A doc that only shows pass and fail documents the old contract."""
        verdicts = {
            exp.get("verdict")
            for block in self._grading_blocks()
            for exp in block.get("expectations", [])
            if isinstance(exp, dict)
        }
        self.assertEqual(
            verdicts, {"pass", "fail", "abstain"},
            "references/schemas.md's grading.json examples must show all three "
            "verdicts; abstain is the one a reader will not invent for "
            "themselves")

    def test_the_documented_benchmark_example_matches_a_real_aggregation(self):
        """§7 claims to be the aggregator's own output. Check the key tree."""
        documented = find_block(json_blocks(SCHEMAS_MD), "run_summary", "runs")
        self.assertIsNotNone(documented)
        summary = documented["run_summary"]["with_skill"]
        self.assertIn(
            "abstention", summary,
            "references/schemas.md's benchmark example has no `abstention` "
            "block; the counts must sit beside every rate")


# --------------------------------------------------------------------------
# 4. comparator.md's de-identification code really writes the documented key
# --------------------------------------------------------------------------

class DeidentifyReferenceImplementationTest(unittest.TestCase):
    """Execute the reference implementation and check what it actually writes.

    This is the check that would have caught `seed`/`swapped`/`draw` being added
    to the assignment key while references/schemas.md still documented two keys.
    """

    @classmethod
    def setUpClass(cls):
        blocks = [b for b in fenced_blocks(AGENTS / "comparator.md", "python")
                  if "def deidentify" in b]
        assert blocks, "no deidentify() block found in agents/comparator.md"
        namespace: dict = {}
        exec(compile(blocks[0], "comparator.md", "exec"), namespace)  # noqa: S102
        # staticmethod, or attribute access binds it and shifts every argument.
        cls.deidentify = staticmethod(namespace["deidentify"])
        # Located by A/B alone, not by the audit keys - otherwise dropping one
        # from the doc reads as "block not found" instead of naming the drift.
        cls.documented = find_block(json_blocks(SCHEMAS_MD), "A", "B")
        assert cls.documented is not None, \
            "no assignment_key.json block found in references/schemas.md"

    def _run(self, seed=None):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        outputs = {}
        for config in ("with_skill", "without_skill"):
            src = tmp / "src" / config
            src.mkdir(parents=True)
            (src / "result.txt").write_text(config, encoding="utf-8")
            outputs[config] = src
        comparison_dir = tmp / "comparisons" / "eval-0"
        comparison_dir.mkdir(parents=True)
        key = self.deidentify(outputs, comparison_dir, seed=seed)
        on_disk = json.loads(
            (comparison_dir / "assignment_key.json").read_text(encoding="utf-8"))
        return key, on_disk, comparison_dir

    def test_written_key_matches_the_documented_shape(self):
        _key, on_disk, _dir = self._run(seed=12345)
        written, documented = set(on_disk), set(self.documented)
        self.assertEqual(
            written, documented,
            f"assignment_key.json and references/schemas.md disagree: "
            f"written but undocumented {sorted(written - documented)}, "
            f"documented but never written {sorted(documented - written)}",
        )
        for label in ("A", "B"):
            self.assertEqual(
                set(on_disk[label]), set(self.documented[label]),
                f"assignment_key.json['{label}'] and the documented example "
                f"disagree",
            )

    def test_recorded_seed_replays_the_assignment(self):
        """A seed that does not reproduce the mapping is a record of nothing."""
        import random

        key, _on_disk, _dir = self._run()
        configs = sorted(("with_skill", "without_skill"))
        replay = list(configs)
        if random.Random(key["seed"]).random() < 0.5:
            replay.reverse()
        self.assertEqual(
            [key["A"]["configuration"], key["B"]["configuration"]], replay,
            "replaying the recorded seed does not reproduce the A/B mapping; "
            "the assignment was chosen rather than drawn, or `draw` is stale",
        )

    def test_swapped_agrees_with_the_recorded_seed(self):
        import random

        key, _on_disk, _dir = self._run()
        self.assertEqual(
            key["swapped"], random.Random(key["seed"]).random() < 0.5,
            "`swapped` disagrees with what the recorded seed draws",
        )

    def test_candidate_directories_carry_no_provenance(self):
        """The excluded files are the six channels the blinding closes."""
        _key, _on_disk, comparison_dir = self._run(seed=7)
        leaked = [p.name for p in (comparison_dir / "candidates").rglob("*")
                  if p.name in {"transcript.md", "user_notes.md", "metrics.json",
                                "timing.json", "grading.json"}]
        self.assertEqual(leaked, [], f"provenance copied into candidates: {leaked}")

    def test_candidate_directory_names_do_not_name_the_configuration(self):
        _key, on_disk, _dir = self._run(seed=7)
        for label in ("A", "B"):
            name = Path(on_disk[label]["path"]).name
            for config in ("with_skill", "without_skill", "old_skill", "new_skill"):
                self.assertNotIn(
                    config, name,
                    f"candidate {label}'s directory name states the answer",
                )


# --------------------------------------------------------------------------
# 5. analyzer.md's expected benchmark.json keys == what is actually emitted
# --------------------------------------------------------------------------

class AnalyzerBenchmarkKeysTest(unittest.TestCase):
    """analyzer.md names eight top-level keys. Three parties must agree on them."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        root = Path(cls._tmp)
        from tests.make_workspace_fixtures import build
        build(root)
        cls.iteration = root / "canonical" / "iteration-1"
        result = subprocess.run(
            [sys.executable, "-m", "scripts.aggregate_benchmark",
             str(cls.iteration), "--skill-name", "demo"],
            cwd=SKILL_ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        cls.emitted = json.loads(
            (cls.iteration / "benchmark.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _keys_named_in_analyzer(self):
        text = (AGENTS / "analyzer.md").read_text(encoding="utf-8")
        match = re.search(
            r"exactly eight top-level keys\*\*:(.+?)\.\s", text, re.S)
        self.assertIsNotNone(
            match, "analyzer.md no longer states the top-level benchmark keys")
        return set(re.findall(r"`([a-z_]+)`", match.group(1)))

    def test_analyzer_expectation_matches_the_aggregator(self):
        self.assertEqual(
            self._keys_named_in_analyzer(), set(self.emitted),
            "agents/analyzer.md and scripts/aggregate_benchmark.py disagree "
            "about benchmark.json's top-level keys",
        )

    def test_schema_reference_matches_the_aggregator(self):
        documented = find_block(json_blocks(SCHEMAS_MD), "run_summary", "runs")
        self.assertIsNotNone(
            documented, "no benchmark.json block found in references/schemas.md")
        self.assertEqual(
            set(documented), set(self.emitted),
            "references/schemas.md and scripts/aggregate_benchmark.py disagree "
            "about benchmark.json's top-level keys",
        )

    def test_documented_run_result_matches_the_aggregator(self):
        """The field that quietly grew a permanently-null column, twice."""
        documented = find_block(json_blocks(SCHEMAS_MD), "run_summary", "runs")
        self.assertEqual(
            set(documented["runs"][0]["result"]),
            set(self.emitted["runs"][0]["result"]),
            "references/schemas.md and the aggregator disagree about "
            "runs[].result",
        )


# --------------------------------------------------------------------------
# 6. The abstention-typing procedure is stated, and stated the same way
# --------------------------------------------------------------------------

class AbstentionTypingProcedureTest(unittest.TestCase):
    """Three reasons over an unstated boundary collect habits, not facts.

    There are three typed abstention reasons. The definitions alone do
    not separate them - "outside what this judge can rule on" and "no judge
    could rule" are both true of a great many statements, so a judge picking the
    closest-sounding description picks by temperament and two judges split the
    same eval set differently. This was found by an agent building a fresh
    corpus, which had to invent its own test to proceed and said so.

    So the boundary is a procedure - three questions, first `yes` decides - and
    it has to be present in every file a judge reads, in the same terms. Prose,
    not shape, and pinned for the same reason the ternary-vocabulary sentences
    above are: it is a rule the model follows rather than a field it emits, and
    losing it leaves a JSON block that still looks correct over a field nobody
    can type consistently.
    """

    JUDGE_FACING = ("grader.md", "panel/seat-frame.md")
    ALL = JUDGE_FACING + ("panel/composer.md",)

    @classmethod
    def setUpClass(cls):
        cls.flat = {
            name: re.sub(r"\s+", " ", (AGENTS / name).read_text(encoding="utf-8"))
            for name in cls.ALL
        }

    def assertSaid(self, name, pattern, note):
        self.assertRegex(
            self.flat[name], pattern,
            f"agents/{name} no longer states {note} -- the abstention-typing "
            f"procedure has to survive in every file that types an abstention",
        )

    def test_every_file_names_all_three_reasons(self):
        for name in self.ALL:
            for reason in ("jurisdiction", "evidence", "underspecified"):
                with self.subTest(prompt=name, reason=reason):
                    self.assertIn(reason, self.flat[name],
                                  f"agents/{name} never names {reason}")

    def test_the_three_questions_are_present_in_order(self):
        """Q1 missing-artifact, Q2 standard-held-by-someone, Q3 quotable term."""
        for name in self.ALL:
            text = self.flat[name]
            with self.subTest(prompt=name):
                q1 = text.find("this run could have produced")
                q2 = text.find("already exist")
                q3 = text.find("open term")
                self.assertNotEqual(q1, -1, f"agents/{name} lost question 1")
                self.assertNotEqual(q2, -1, f"agents/{name} lost question 2")
                self.assertNotEqual(q3, -1, f"agents/{name} lost question 3")
                self.assertLess(q1, q2, f"agents/{name}: question 1 no longer "
                                        f"precedes question 2, and the order is "
                                        f"what decides")
                self.assertLess(q2, q3, f"agents/{name}: question 2 no longer "
                                        f"precedes question 3")

    def test_the_fall_through_is_jurisdiction_not_underspecified(self):
        """The comfortable reason must be earned; the humble one is the residue.

        If nothing answers, the reason is `jurisdiction`: failing to find a
        standard is not establishing that none exists. Flip this and
        `underspecified` becomes the exit for every statement a judge could not
        be bothered to decide.
        """
        for name in self.ALL:
            self.assertSaid(
                name,
                r"(cannot answer any of the three|none answerable|"
                r"none of the three answerable)[^.]{0,120}jurisdiction",
                "that an unanswerable ladder falls through to `jurisdiction`")

    def test_the_two_anti_collapse_clauses_are_stated(self):
        """Without them one question swallows the others.

        A standard supplied from outside re-described as a missing document
        turns every jurisdiction case into `evidence`; a requester's unfixed
        preference treated as a standard turns every underspecified case into
        `jurisdiction`.
        """
        for name in self.JUDGE_FACING:
            self.assertSaid(
                name, r"handed [^.]{0,60}is not evidence",
                "that a standard handed in from outside is not evidence")
            self.assertSaid(
                name, r"preference nobody has fixed is not a standard",
                "that a preference nobody has fixed is not a standard")

    def test_underspecified_must_quote_the_open_term(self):
        for name in self.ALL:
            self.assertSaid(
                name, r"(quote|name|carry|naming) the open term|"
                      r"open term[^.]{0,80}(quote|evidence)",
                "that `underspecified` requires the open term be quoted")

    def test_the_composition_ordering_matches_the_ladder(self):
        """One rule at both scales, or it drifts at one of them."""
        frame = self.flat["panel/seat-frame.md"]
        evidence = frame.find("| 1 | `evidence`")
        under = frame.find("| 2 | `underspecified`")
        juris = frame.find("| 3 | `jurisdiction`")
        self.assertNotEqual(evidence, -1,
                            "seat-frame.md lost the composed-reason ordering")
        self.assertLess(evidence, under)
        self.assertLess(under, juris)


if __name__ == "__main__":
    unittest.main(verbosity=2)
