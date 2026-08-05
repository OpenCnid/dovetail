#!/usr/bin/env python3
"""Tests for scripts/quick_validate.py.

Run from the skill root::

    python -m unittest tests.test_quick_validate -v
    python -m tests.test_quick_validate

Each case in tests/validator_fixtures.py is checked against all three targets.
A fixture that documented a false negative must now produce at least one error
whose message names its field and its target; a fixture that documented a false
positive must now be clean.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.quick_validate import (  # noqa: E402
    ALL_KNOWN_FIELDS,
    CLAUDE_CODE_SCHEMA_FIELDS,
    DEFAULT_TARGET,
    PORTABLE_FIELDS,
    PROFILES,
    TARGETS,
    collect_findings,
    validate_skill,
)
from tests.validator_fixtures import CASES, build  # noqa: E402


class FixtureCorpus(unittest.TestCase):
    """Every fixture, against every target."""

    corpus: Path
    _tmp: tempfile.TemporaryDirectory

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="skill-validator-fixtures-")
        cls.corpus = build(Path(cls._tmp.name) / "corpus")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _run(self, case, target):
        findings = collect_findings(self.corpus / case.dirname, target)
        errors = [f for f in findings if f.level == "error"]
        return findings, errors

    def test_every_fixture_against_every_target(self) -> None:
        for case in CASES:
            for target in TARGETS:
                with self.subTest(case=case.cid, dir=case.dirname, target=target):
                    findings, errors = self._run(case, target)
                    expected = case.expected(target)
                    rendered = "\n".join(f.render() for f in findings) or "(no findings)"

                    if expected == "pass":
                        self.assertEqual(
                            [], errors,
                            f"{case.cid} ({case.why}) should be valid for "
                            f"{target}:\n{rendered}",
                        )
                    else:
                        self.assertTrue(
                            errors,
                            f"{case.cid} ({case.why}) should be rejected for "
                            f"{target}, got:\n{rendered}",
                        )

    def test_expected_codes_are_present(self) -> None:
        for case in CASES:
            for target, codes in case.codes.items():
                with self.subTest(case=case.cid, target=target):
                    findings, _ = self._run(case, target)
                    present = {f.code for f in findings}
                    for code in codes:
                        self.assertIn(
                            code, present,
                            f"{case.cid}/{target} expected finding {code!r}; got "
                            f"{sorted(present)}",
                        )

    def test_forbidden_codes_are_absent(self) -> None:
        for case in CASES:
            for target, codes in case.forbid_codes.items():
                with self.subTest(case=case.cid, target=target):
                    findings, _ = self._run(case, target)
                    present = {f.code for f in findings}
                    for code in codes:
                        self.assertNotIn(
                            code, present,
                            f"{case.cid}/{target} must not report {code!r}",
                        )

    def test_every_finding_names_its_field_and_target(self) -> None:
        """C9: every message names which target produced it."""
        for case in CASES:
            for target in TARGETS:
                findings, _ = self._run(case, target)
                for finding in findings:
                    with self.subTest(case=case.cid, target=target, code=finding.code):
                        self.assertEqual(target, finding.target)
                        self.assertTrue(finding.field, "finding has no field")
                        self.assertIn(target, finding.render())
                        self.assertIn(finding.field, finding.render())
                        self.assertTrue(finding.message.strip())

    def test_accumulates_rather_than_bailing(self) -> None:
        """C6: one run reports every problem, not just the first."""
        findings, errors = self._run(
            next(c for c in CASES if c.cid == "NEW03"), "portable"
        )
        codes = {f.code for f in errors}
        self.assertGreaterEqual(
            len(errors), 4,
            f"expected at least 4 accumulated errors, got {sorted(codes)}",
        )
        for expected in (
            "name.uppercase",
            "name.invalid-chars",
            "name.directory-mismatch",
            "description.too-long",
            "unknown-key",
        ):
            self.assertIn(expected, codes)


class NameRules(unittest.TestCase):
    """Structural problems are errors; "not ASCII" is a portability warning.

    Rejecting a Japanese or Cyrillic name would be stricter than the reference
    validator, which accepts any `c.isalnum() or c == '-'`. That is a false
    rejection, and it falls on precisely the non-English authors these scripts
    have already failed once.
    """

    def _findings(self, name: str, dirname: str | None = None):
        directory = dirname if dirname is not None else name
        with tempfile.TemporaryDirectory(prefix="skill-name-rule-") as tmp:
            path = Path(tmp) / directory
            path.mkdir()
            (path / "SKILL.md").write_bytes(
                f'---\nname: "{name}"\ndescription: Does a thing. Use when asked.\n'
                f"---\n\nbody\n".encode("utf-8")
            )
            return collect_findings(path, DEFAULT_TARGET)

    def _codes(self, name: str, dirname: str | None = None):
        findings = self._findings(name, dirname)
        return {f.code for f in findings}, [f for f in findings if f.level == "error"]

    def test_unicode_names_are_accepted_on_every_target(self) -> None:
        for name in ("日本語-スキル", "новый-навык", "café-notes", "ελληνικά"):
            for target in TARGETS:
                with self.subTest(name=name, target=target):
                    with tempfile.TemporaryDirectory() as tmp:
                        path = Path(tmp) / name
                        path.mkdir()
                        (path / "SKILL.md").write_bytes(
                            f"---\nname: {name}\ndescription: Does a thing.\n"
                            f"---\n\nbody\n".encode("utf-8")
                        )
                        findings = collect_findings(path, target)
                    errors = [f for f in findings if f.level == "error"]
                    self.assertEqual(
                        [], errors,
                        f"{name} must not be an error on {target}: "
                        + "; ".join(f.render() for f in errors),
                    )

    def test_unicode_name_warns_about_portability(self) -> None:
        findings = self._findings("日本語-スキル")
        warning = next(f for f in findings if f.code == "name.non-ascii")
        self.assertEqual("warning", warning.level)
        message = warning.message.lower()
        # Worded as a tradeoff, not as a verdict.
        self.assertIn("valid", message)
        for forbidden in ("invalid", "not allowed", "must not", "illegal"):
            self.assertNotIn(forbidden, message)

    def test_plain_ascii_name_draws_no_warning(self) -> None:
        codes, errors = self._codes("plain-name-9")
        self.assertEqual([], errors)
        self.assertNotIn("name.non-ascii", codes)

    def test_structural_problems_are_errors(self) -> None:
        expectations = {
            "Upper-Case": "name.uppercase",
            "under_score": "name.invalid-chars",
            "has space": "name.whitespace",
            "-leading": "name.hyphen-edge",
            "trailing-": "name.hyphen-edge",
            "double--hyphen": "name.consecutive-hyphens",
            "emoji-\U0001f680": "name.invalid-chars",
            "dotted.name": "name.invalid-chars",
        }
        for name, code in expectations.items():
            with self.subTest(name=name):
                codes, errors = self._codes(name)
                self.assertTrue(errors, f"{name!r} should be rejected")
                self.assertIn(code, codes)

    def test_path_separator_is_an_error(self) -> None:
        codes, errors = self._codes("a/b", dirname="a-b")
        self.assertTrue(errors)
        self.assertIn("name.path-separator", codes)

    def test_over_64_characters_is_an_error(self) -> None:
        codes, _ = self._codes("a" * 65)
        self.assertIn("name.too-long", codes)

    def test_unicode_name_still_obeys_the_structural_rules(self) -> None:
        """Being non-ASCII buys no exemption."""
        codes, errors = self._codes("日本語 スキル")
        self.assertTrue(errors)
        self.assertIn("name.whitespace", codes)

    def test_directory_match_is_canonical_not_byte_exact(self) -> None:
        """A decomposed directory name matches a composed frontmatter name."""
        import unicodedata

        composed = unicodedata.normalize("NFC", "café-notes")
        decomposed = unicodedata.normalize("NFD", "café-notes")
        self.assertNotEqual(composed, decomposed)
        codes, errors = self._codes(composed, dirname=decomposed)
        self.assertNotIn("name.directory-mismatch", codes)
        self.assertEqual([], errors)

    def test_directory_mismatch_is_reported_on_every_target(self) -> None:
        """R31/FP-3: always reported, but the severity is the target's.

        agentskills.io states the match and the Skills API rejects the upload;
        code.claude.com states the opposite -- `name` is the display label and
        the command comes from the directory. An error at the default target
        was a false rejection of a skill following Claude Code's own docs.
        """
        expected_levels = {
            "claude-code": "warning",
            "portable": "error",
            "claude-ai": "error",
        }
        for target, level in expected_levels.items():
            with self.subTest(target=target):
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "other-name"
                    path.mkdir()
                    (path / "SKILL.md").write_bytes(
                        b"---\nname: some-name\ndescription: Does a thing.\n---\n\nx\n"
                    )
                    findings = collect_findings(path, target)
                hit = next(f for f in findings if f.code == "name.directory-mismatch")
                self.assertEqual(level, hit.level)

    def test_claude_code_mismatch_warning_names_the_packaging_consequence(self) -> None:
        """A warning that did not say packaging refuses would be half a fix."""
        findings = self._findings("some-name", dirname="other-name")
        hit = next(f for f in findings if f.code == "name.directory-mismatch")
        self.assertEqual("warning", hit.level)
        self.assertIn("package_skill", hit.message)


class Targets(unittest.TestCase):
    def test_default_target_is_claude_code(self) -> None:
        self.assertEqual("claude-code", DEFAULT_TARGET)

    def test_three_targets(self) -> None:
        self.assertEqual(("claude-code", "portable", "claude-ai"), TARGETS)

    def test_portable_field_set_is_the_standard_six(self) -> None:
        self.assertEqual(
            {"name", "description", "license", "allowed-tools", "metadata",
             "compatibility"},
            set(PORTABLE_FIELDS),
        )

    def test_claude_code_recognises_31_schema_keys(self) -> None:
        self.assertEqual(31, len(CLAUDE_CODE_SCHEMA_FIELDS))

    def test_claude_code_schema_omits_plugin_manifest_keys(self) -> None:
        for key in ("mcpServers", "lspServers", "outputStyles", "themes",
                    "workflows", "channels", "monitors", "settings", "userConfig"):
            self.assertNotIn(key, CLAUDE_CODE_SCHEMA_FIELDS)

    def test_description_caps(self) -> None:
        self.assertEqual(1024, PROFILES["claude-code"].description_max)
        self.assertEqual(1024, PROFILES["portable"].description_max)
        self.assertEqual(200, PROFILES["claude-ai"].description_max)
        self.assertEqual(1536, PROFILES["claude-code"].combined_description_max)

    def test_every_cap_names_where_its_number_comes_from(self) -> None:
        """R31: a cap with no source is the FP-2 defect in the abstract.

        The failure this artifact exists to prevent is an assertion the tool
        cannot source, so the source is a required field rather than a comment.
        """
        for name, profile in PROFILES.items():
            with self.subTest(target=name):
                self.assertTrue(profile.description_max_source.strip())
                self.assertGreater(len(profile.description_max_source), 20)

    def test_undocumented_rules_are_warnings_at_the_default_target(self) -> None:
        """The two rules no Claude Code document states."""
        self.assertEqual("warning", PROFILES["claude-code"].description_max_level)
        self.assertEqual("warning", PROFILES["claude-code"].name_directory_level)
        for name in ("portable", "claude-ai"):
            with self.subTest(target=name):
                self.assertEqual("error", PROFILES[name].description_max_level)
                self.assertEqual("error", PROFILES[name].name_directory_level)

    def test_unknown_keys_warn_on_claude_code_and_error_elsewhere(self) -> None:
        self.assertEqual("warning", PROFILES["claude-code"].unknown_key_level)
        self.assertEqual("error", PROFILES["portable"].unknown_key_level)
        self.assertEqual("error", PROFILES["claude-ai"].unknown_key_level)

    def test_all_known_fields_is_a_superset(self) -> None:
        for profile in PROFILES.values():
            self.assertTrue(profile.fields <= ALL_KNOWN_FIELDS)

    def test_unknown_target_raises(self) -> None:
        with self.assertRaises(ValueError):
            collect_findings(SKILL_ROOT, "no-such-target")


class PathHandling(unittest.TestCase):
    def test_missing_path(self) -> None:
        findings = collect_findings(SKILL_ROOT / "definitely-not-here", DEFAULT_TARGET)
        self.assertEqual(["path.missing"], [f.code for f in findings])

    def test_path_is_a_file(self) -> None:
        findings = collect_findings(SKILL_ROOT / "SKILL.md", DEFAULT_TARGET)
        self.assertEqual(["path.not-a-directory"], [f.code for f in findings])

    def test_no_traceback_escapes(self) -> None:
        """Every malformed input becomes a finding, never an exception."""
        with tempfile.TemporaryDirectory() as tmp:
            corpus = build(Path(tmp) / "corpus")
            for case in CASES:
                for target in TARGETS:
                    with self.subTest(case=case.cid, target=target):
                        collect_findings(corpus / case.dirname, target)


class DocumentedFrontmatterIsNotARejection(unittest.TestCase):
    """R30 (research/V2-verification.md FP-1).

    The previous guard treated any recognised frontmatter key at the start of a
    body line before the first body ``---`` as a hard error, including inside
    fenced code blocks. A SKILL.md that documents frontmatter and later uses a
    horizontal rule therefore failed validation, failed ``parse_skill_md`` --
    and so ``run_eval``, ``run_loop`` and ``improve_description`` -- and could
    not be packaged, with an error message asserting something false about the
    file. The reference validator accepts every one of these.
    """

    GOOD = "Extracts text and tables from PDF files. Use when working with PDFs."

    def _findings(self, name: str, body: str, target: str = DEFAULT_TARGET):
        with tempfile.TemporaryDirectory(prefix="skill-r30-") as tmp:
            path = Path(tmp) / name
            path.mkdir()
            (path / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {self.GOOD}\n---\n{body}",
                encoding="utf-8",
            )
            return collect_findings(path, target)

    def _codes(self, name: str, body: str, target: str = DEFAULT_TARGET):
        return {f.code for f in self._findings(name, body, target)}

    def test_fenced_frontmatter_example_then_a_rule_is_clean(self) -> None:
        """The definition of done, stated once."""
        body = (
            "\n## Example\n\n```yaml\nname: my-skill\ndescription: Does things\n"
            "license: MIT\nallowed-tools: Read Grep\n```\n\n---\n\n## Next\n"
        )
        for target in TARGETS:
            with self.subTest(target=target):
                findings = self._findings("r30-fenced", body, target)
                self.assertEqual(
                    [], findings,
                    "; ".join(f.render() for f in findings),
                )

    def test_fence_lengths_and_info_strings(self) -> None:
        bodies = {
            "backticks-bare": "\n```\nlicense: MIT\n```\n\n---\n\nend\n",
            "backticks-info": "\n```yaml\nlicense: MIT\n```\n\n---\n\nend\n",
            "tildes": "\n~~~yaml\nlicense: MIT\n~~~\n\n---\n\nend\n",
            "four-backticks": "\n````md\nlicense: MIT\n````\n\n---\n\nend\n",
            "indented-fence": "\n  ```\nlicense: MIT\n  ```\n\n---\n\nend\n",
        }
        for label, body in bodies.items():
            with self.subTest(fence=label):
                self.assertNotIn(
                    "skill-md.ambiguous-delimiter", self._codes("r30-fence", body)
                )

    def test_a_rule_inside_a_fence_does_not_terminate_the_region(self) -> None:
        body = "\n```yaml\nname: example\n---\nlicense: MIT\n```\n\nend\n"
        self.assertNotIn(
            "skill-md.ambiguous-delimiter", self._codes("r30-fenced-rule", body)
        )

    def test_indented_code_block_is_excluded(self) -> None:
        body = "\nExample:\n\n    license: MIT\n    ---\n\n---\n\nend\n"
        self.assertNotIn(
            "skill-md.ambiguous-delimiter", self._codes("r30-indented", body)
        )

    def test_ordinary_prose_key_line_is_not_a_finding(self) -> None:
        body = "\nNote: read this first.\n\nWarning: and this.\n\n---\n\nMore.\n"
        self.assertEqual([], self._findings("r30-prose", body))

    def test_the_original_defect_is_still_caught(self) -> None:
        """A recognised key genuinely stranded past an inner ``---``."""
        body = "license: MIT\nallowed-tools: Read\n---\n\nbody\n"
        for target in TARGETS:
            with self.subTest(target=target):
                findings = self._findings("r30-stray", body, target)
                hit = next(
                    f for f in findings if f.code == "skill-md.ambiguous-delimiter"
                )
                self.assertEqual("warning", hit.level)
                self.assertIn("license", hit.message)

    def test_a_fence_does_not_hide_a_later_stray_key(self) -> None:
        body = "license: MIT\n\n```yaml\nname: example\n```\n\n---\n\nend\n"
        self.assertIn(
            "skill-md.ambiguous-delimiter", self._codes("r30-both", body)
        )

    def test_unrecognised_stranded_key_is_caught_too(self) -> None:
        """V19's residual: the key set alone could not see a vendor key."""
        body = "  hidden\nsome-vendor-key: v\n---\n\nbody\n"
        codes = self._codes("r30-vendor", body)
        self.assertIn("skill-md.ambiguous-delimiter", codes)

    def test_the_finding_never_asserts_truncation(self) -> None:
        """The wording is the other half of the defect.

        "'name' is invisible to everything" was false for every skill that
        documents frontmatter, and a confident wrong explanation is worse than
        the silent truncation the check replaced.
        """
        body = "license: MIT\n---\n\nbody\n"
        hit = next(
            f
            for f in self._findings("r30-wording", body)
            if f.code == "skill-md.ambiguous-delimiter"
        )
        lowered = hit.message.lower()
        self.assertNotIn("truncated", lowered)
        self.assertNotIn("invisible to everything", lowered)
        # Both readings are offered, and the reader is told which is which.
        self.assertIn("horizontal rule", lowered)
        self.assertIn("if", lowered)

    def test_the_condition_never_blocks_the_shared_parse_path(self) -> None:
        """`parse_skill_md` is what run_eval/run_loop/improve_description call."""
        from scripts.utils import parse_skill_md

        with tempfile.TemporaryDirectory(prefix="skill-r30-parse-") as tmp:
            path = Path(tmp) / "r30-parse"
            path.mkdir()
            (path / "SKILL.md").write_text(
                f"---\nname: r30-parse\ndescription: {self.GOOD}\n---\n\n"
                "```yaml\nname: example\n```\n\n---\n\nend\n",
                encoding="utf-8",
            )
            name, description, _content = parse_skill_md(path)
        self.assertEqual("r30-parse", name)
        self.assertEqual(self.GOOD, description)


class SkillMdFilenameCase(unittest.TestCase):
    """R32/PK-1: a lowercase ``skill.md`` validated clean and then could not be
    packaged, and the packager's message named the wrong cause."""

    def _findings(self, filename: str, target: str = DEFAULT_TARGET):
        with tempfile.TemporaryDirectory(prefix="skill-r32-") as tmp:
            path = Path(tmp) / "lower-md"
            path.mkdir()
            (path / filename).write_text(
                "---\nname: lower-md\ndescription: Does a thing. Use when asked.\n"
                "---\n\nbody\n",
                encoding="utf-8",
            )
            return collect_findings(path, target)

    def test_uppercase_is_clean(self) -> None:
        self.assertEqual([], self._findings("SKILL.md"))

    def test_lowercase_is_an_error_on_every_target(self) -> None:
        for target in TARGETS:
            with self.subTest(target=target):
                findings = self._findings("skill.md", target)
                codes = {f.code for f in findings}
                self.assertIn("skill-md.filename-case", codes)
                self.assertIn(
                    "error",
                    [f.level for f in findings if f.code == "skill-md.filename-case"],
                )

    def test_the_file_is_still_read(self) -> None:
        """Reporting the spelling must not turn into refusing to look.

        A lowercase skill.md whose frontmatter is also broken should produce
        both findings, not a `skill-md.missing` that names neither.
        """
        with tempfile.TemporaryDirectory(prefix="skill-r32-read-") as tmp:
            path = Path(tmp) / "lower-md"
            path.mkdir()
            (path / "skill.md").write_text(
                '---\nname: lower-md\ndescription: ""\n---\n\nbody\n',
                encoding="utf-8",
            )
            codes = {f.code for f in collect_findings(path, DEFAULT_TARGET)}
        self.assertIn("skill-md.filename-case", codes)
        self.assertIn("description.empty", codes)
        self.assertNotIn("skill-md.missing", codes)

    def test_case_insensitive_filesystems_do_not_hide_the_spelling(self) -> None:
        """The probe `skill_path / "SKILL.md"` succeeds on NTFS and APFS.

        That is exactly why this check reads the directory entries instead --
        on Windows the old code could not see the problem at all, and the
        failure surfaced from the packager with a message about SKILL.md being
        "excluded from the archive".
        """
        from scripts.utils import actual_skill_md_name, find_skill_md

        with tempfile.TemporaryDirectory(prefix="skill-r32-case-") as tmp:
            path = Path(tmp) / "lower-md"
            path.mkdir()
            (path / "skill.md").write_text("---\nname: x\n---\n", encoding="utf-8")
            self.assertIsNotNone(find_skill_md(path))
            self.assertEqual("skill.md", actual_skill_md_name(path))


class ValidateSkillContract(unittest.TestCase):
    """package_skill consumes (is_valid, message); that shape is load-bearing."""

    def test_returns_two_tuple(self) -> None:
        result = validate_skill(SKILL_ROOT)
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, len(result))
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], str)

    def test_accepts_target_keyword(self) -> None:
        ok_code, _ = validate_skill(SKILL_ROOT, target="claude-code")
        self.assertTrue(ok_code)

    def test_failure_message_lists_every_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            corpus = build(Path(tmp) / "corpus")
            ok, message = validate_skill(corpus / "new-multi-defect", "portable")
            self.assertFalse(ok)
            self.assertGreaterEqual(len(message.splitlines()), 5)
            self.assertIn("portable", message)

    def test_better_skill_creator_itself_validates_for_claude_code(self) -> None:
        ok, message = validate_skill(SKILL_ROOT, "claude-code")
        self.assertTrue(ok, message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
