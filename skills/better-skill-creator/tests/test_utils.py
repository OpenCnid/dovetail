#!/usr/bin/env python3
"""Tests for scripts/utils.py -- the shared SKILL.md reader and parser.

Run from the skill root::

    python -m unittest tests.test_utils -v
    python -m tests.test_utils

`parse_skill_md` is the highest-severity item in this track: its return values
become prompts, directory names and file names in run_eval, run_loop and
improve_description. Every case below is a value the previous implementation
returned *wrongly and silently* (research/01-windows-encoding.md F1/F2,
research/12-validator-packager.md F14), or a failure it turned into a
traceback instead of a message.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.utils import (  # noqa: E402
    SPEC_FIELDS,
    SkillMdError,
    configure_console,
    find_frontmatter_ambiguity,
    find_skill_md,
    load_frontmatter,
    parse_skill_md,
    read_text_utf8,
    split_frontmatter,
)

GOOD_DESC = "Extracts text and tables from PDF files. Use when working with PDF documents."


class SkillDir:
    """A throwaway skill directory."""

    def __init__(self, name: str, body: str | None, *, encoding: str = "utf-8",
                 newline: str = "\n", filename: str = "SKILL.md",
                 as_directory: bool = False) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="skill-utils-")
        self.path = Path(self._tmp.name) / name
        self.path.mkdir(parents=True)
        if as_directory:
            (self.path / filename).mkdir()
        elif body is not None:
            (self.path / filename).write_bytes(
                body.replace("\n", newline).encode(encoding)
            )

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, *exc) -> None:
        self._tmp.cleanup()


class ParseSkillMdValues(unittest.TestCase):
    """The values that used to come back corrupted."""

    def test_quoted_padded_name_is_stripped(self) -> None:
        body = f'---\nname: "  padded-name  "\ndescription: {GOOD_DESC}\n---\n\nbody\n'
        with SkillDir("padded-name", body) as path:
            name, _description, _content = parse_skill_md(path)
        # The old parser did .strip().strip('"').strip("'") and never
        # re-stripped, so this came back as '  padded-name  ' and then became a
        # directory and filename component downstream.
        self.assertEqual("padded-name", name)

    def test_literal_block_scalar_keeps_its_newline(self) -> None:
        body = (
            "---\nname: literal-block\ndescription: |-\n  Extracts text from PDFs.\n"
            "  Use when the user mentions PDFs.\n---\n\nbody\n"
        )
        with SkillDir("literal-block", body) as path:
            _name, description, _content = parse_skill_md(path)
        # The hand-rolled scanner joined continuation lines with " ".
        self.assertIn("\n", description)
        self.assertEqual(
            "Extracts text from PDFs.\nUse when the user mentions PDFs.", description
        )

    def test_folded_block_scalar_folds(self) -> None:
        body = (
            "---\nname: folded-block\ndescription: >-\n  Extracts text from PDFs.\n"
            "  Use when the user mentions PDFs.\n---\n\nbody\n"
        )
        with SkillDir("folded-block", body) as path:
            _name, description, _content = parse_skill_md(path)
        self.assertEqual(
            "Extracts text from PDFs. Use when the user mentions PDFs.", description
        )

    def test_escaped_newline_is_decoded(self) -> None:
        body = (
            '---\nname: escaped-newline\ndescription: "Line one.\\nLine two."\n'
            "---\n\nbody\n"
        )
        with SkillDir("escaped-newline", body) as path:
            _name, description, _content = parse_skill_md(path)
        # The old parser left the two characters `\` and `n` in the string.
        self.assertEqual("Line one.\nLine two.", description)
        self.assertNotIn("\\n", description)

    def test_keep_block_indicator_is_handled(self) -> None:
        """`|+`, `>+` and `|2` fell through the old four-indicator check."""
        body = (
            "---\nname: keep-indicator\ndescription: |+\n  Keeps trailing newlines.\n"
            "\n---\n\nbody\n"
        )
        with SkillDir("keep-indicator", body) as path:
            _name, description, _content = parse_skill_md(path)
        self.assertEqual("Keeps trailing newlines.", description.strip())
        self.assertNotIn("|", description)

    def test_non_ascii_round_trips_without_mojibake(self) -> None:
        text = (
            "---\nname: nonascii\ndescription: Handles “curly quotes”, café, "
            "naïve — 日本語. Use for typography.\n---\n\nCafé naïve — 日本語 ✓\n"
        )
        with SkillDir("nonascii", text) as path:
            name, description, content = parse_skill_md(path)
        self.assertEqual("nonascii", name)
        self.assertIn("café", description)
        self.assertIn("日本語", description)
        # The cp1252 path decoded these into 'cafÃ©' / 'â€"' with no exception,
        # inflating len() and feeding the optimizer text the author never wrote.
        self.assertNotIn("Ã", content)
        self.assertEqual(text, content)

    def test_codepoint_counts_not_byte_counts(self) -> None:
        text = "---\nname: cjk\ndescription: " + ("日" * 1000) + "\n---\n\nbody\n"
        with SkillDir("cjk", text) as path:
            _name, description, _content = parse_skill_md(path)
        self.assertEqual(1000, len(description))

    def test_crlf_is_normalised(self) -> None:
        body = f"---\nname: crlf\ndescription: {GOOD_DESC}\n---\n\nbody\n"
        with SkillDir("crlf", body, newline="\r\n") as path:
            name, description, content = parse_skill_md(path)
        self.assertEqual("crlf", name)
        self.assertEqual(GOOD_DESC, description)
        self.assertNotIn("\r", content)

    def test_bom_is_transparent(self) -> None:
        body = "﻿" + f"---\nname: bom\ndescription: {GOOD_DESC}\n---\n\nbody\n"
        with SkillDir("bom", body) as path:
            name, _description, content = parse_skill_md(path)
        self.assertEqual("bom", name)
        self.assertFalse(content.startswith("﻿"))

    def test_lowercase_skill_md_is_found(self) -> None:
        body = f"---\nname: lower\ndescription: {GOOD_DESC}\n---\n\nbody\n"
        with SkillDir("lower", body, filename="skill.md") as path:
            self.assertIsNotNone(find_skill_md(path))
            name, _description, _content = parse_skill_md(path)
        self.assertEqual("lower", name)


class ParseSkillMdRaises(unittest.TestCase):
    """Every failure is a SkillMdError (a ValueError), never a bad value."""

    def _assert_raises(self, path, *fragments):
        with self.assertRaises(SkillMdError) as ctx:
            parse_skill_md(path)
        message = str(ctx.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)
        return message

    def test_latin1_file(self) -> None:
        body = "---\nname: latin1\ndescription: Handles café menus.\n---\n\nbody\n"
        with SkillDir("latin1", body, encoding="latin-1") as path:
            self._assert_raises(path, "not saved as UTF-8")

    def test_utf16_file(self) -> None:
        body = f"---\nname: u16\ndescription: {GOOD_DESC}\n---\n\nbody\n"
        with SkillDir("u16", body, encoding="utf-16") as path:
            self._assert_raises(path, "not saved as UTF-8")

    def test_skill_md_is_a_directory(self) -> None:
        with SkillDir("isdir", None, as_directory=True) as path:
            self._assert_raises(path, "no SKILL.md")

    def test_missing_directory(self) -> None:
        with SkillDir("gone", None) as path:
            self._assert_raises(path / "nope", "path does not exist")

    def test_path_is_a_file(self) -> None:
        body = f"---\nname: f\ndescription: {GOOD_DESC}\n---\n\nbody\n"
        with SkillDir("f", body) as path:
            self._assert_raises(path / "SKILL.md", "not a directory")

    def test_cr_only_line_endings(self) -> None:
        body = f"---\nname: cronly\ndescription: {GOOD_DESC}\n---\n\nbody\n"
        with SkillDir("cronly", body, newline="\r") as path:
            self._assert_raises(path, "missing its settings block")

    def test_unterminated_frontmatter(self) -> None:
        with SkillDir("unterm", "---\nname: unterm\n\n# body\n") as path:
            self._assert_raises(path, "never closed")

    def test_trailing_space_delimiter_is_not_a_delimiter(self) -> None:
        body = f"---\nname: tsd\ndescription: {GOOD_DESC}\n--- \n\nbody\n"
        with SkillDir("tsd", body) as path:
            self._assert_raises(path, "never closed")

    def test_duplicate_key(self) -> None:
        body = "---\nname: dup\ndescription: real one\ndescription: x\n---\n\nbody\n"
        with SkillDir("dup", body) as path:
            self._assert_raises(path, "duplicate key")

    def test_empty_description(self) -> None:
        with SkillDir("emptydesc", '---\nname: emptydesc\ndescription: ""\n---\n') as path:
            self._assert_raises(path, "`description` is empty")

    def test_empty_name(self) -> None:
        body = f'---\nname: ""\ndescription: {GOOD_DESC}\n---\n'
        with SkillDir("emptyname", body) as path:
            self._assert_raises(path, "`name` is empty")

    def test_missing_name(self) -> None:
        with SkillDir("noname", f"---\ndescription: {GOOD_DESC}\n---\n") as path:
            self._assert_raises(path, "settings block has no `name`")

    def test_non_string_name(self) -> None:
        with SkillDir("intname", f"---\nname: 12345\ndescription: {GOOD_DESC}\n---\n") as path:
            self._assert_raises(path, "`name` has to be text", "int")

    def test_invalid_yaml(self) -> None:
        body = "---\nname: badyaml\ndescription: Extracts text: tables too.\n---\n"
        with SkillDir("badyaml", body) as path:
            self._assert_raises(path, "not valid YAML")

    def test_frontmatter_is_not_a_mapping(self) -> None:
        with SkillDir("scalarfm", "---\njust a string\n---\n\nbody\n") as path:
            self._assert_raises(path, "list of `key: value` lines")

    def test_inner_delimiter_no_longer_blocks_the_parse(self) -> None:
        """R30. This used to raise, and the raise reached every caller.

        `parse_skill_md` is the one path `run_eval`, `run_loop` and
        `improve_description` have. Refusing here made an ordinary skill --
        one that documents frontmatter and later uses a horizontal rule --
        unevaluable and unpackageable as well as invalid. The name and the
        description that are actually parsed are both fine, and the reference
        validator truncates in exactly the same place and accepts the file.
        """
        body = (
            "---\nname: innerhr\ndescription: |\n  Real description line one.\n"
            "---\n  DROPPED\nlicense: MIT\n---\n\nbody\n"
        )
        with SkillDir("innerhr", body) as path:
            name, description, _content = parse_skill_md(path)
        self.assertEqual("innerhr", name)
        self.assertEqual("Real description line one.", description)

    def test_error_is_a_value_error(self) -> None:
        """Callers written against the previous ValueError contract still work."""
        with SkillDir("noname2", "---\n---\n") as path:
            with self.assertRaises(ValueError):
                parse_skill_md(path)


class ErrorMessagesAreUsable(unittest.TestCase):
    """These messages reach end users through run_eval / run_loop /
    improve_description, so they have to make sense to someone who has never
    heard the word "frontmatter"."""

    #: Every message has to point at something the reader can actually see.
    ANCHORS = ("SKILL.md", "settings block", "folder", "path", "file")

    def _messages(self):
        cases = [
            ("missing-fm", "no frontmatter here\n", {}),
            ("unclosed", "---\nname: unclosed\n", {}),
            ("empty-fm", "---\n\n---\n", {}),
            ("scalar-fm", "---\njust a string\n---\n", {}),
            ("bad-yaml", "---\nname: b\ndescription: a: b\n---\n", {}),
            ("dup", "---\nname: dup\ndescription: a\ndescription: b\n---\n", {}),
            ("no-name", f"---\ndescription: {GOOD_DESC}\n---\n", {}),
            ("int-name", f"---\nname: 42\ndescription: {GOOD_DESC}\n---\n", {}),
            ("blank-name", f'---\nname: ""\ndescription: {GOOD_DESC}\n---\n', {}),
            ("no-desc", "---\nname: no-desc\n---\n", {}),
            ("blank-desc", '---\nname: blank-desc\ndescription: ""\n---\n', {}),
            ("latin1", "---\nname: latin1\ndescription: café\n---\n",
             {"encoding": "latin-1"}),
            ("cronly", f"---\nname: cronly\ndescription: {GOOD_DESC}\n---\n",
             {"newline": "\r"}),
            # The inner-``---`` case left this list with R30: it is no longer
            # an exception, so it has no message to hold to this standard.
            # Its wording is checked in
            # tests.test_quick_validate.DocumentedFrontmatterIsNotARejection.
        ]
        collected = {}
        for name, body, kwargs in cases:
            with SkillDir(name, body, **kwargs) as path:
                try:
                    parse_skill_md(path)
                except SkillMdError as exc:
                    collected[name] = str(exc)
                else:  # pragma: no cover - a case stopped failing
                    self.fail(f"{name} was expected to raise")
        with SkillDir("nofile", None) as path:
            try:
                parse_skill_md(path)
            except SkillMdError as exc:
                collected["no-skill-md"] = str(exc)
        return collected

    def test_every_message_names_something_visible(self) -> None:
        for name, message in self._messages().items():
            with self.subTest(case=name):
                self.assertTrue(
                    any(anchor in message for anchor in self.ANCHORS),
                    f"{name}: {message!r} names nothing the reader can look at",
                )

    def test_every_message_explains_rather_than_labels(self) -> None:
        for name, message in self._messages().items():
            with self.subTest(case=name):
                self.assertGreater(
                    len(message), 60,
                    f"{name}: {message!r} is a label, not an explanation",
                )

    def test_jargon_is_glossed(self) -> None:
        """'frontmatter' may appear, but never as the only description."""
        for name, message in self._messages().items():
            with self.subTest(case=name):
                if "frontmatter" in message.lower():
                    self.assertIn("settings block", message)

    def test_no_python_repr_leaks_into_a_message(self) -> None:
        for name, message in self._messages().items():
            with self.subTest(case=name):
                self.assertNotIn("Traceback", message)
                self.assertNotIn("<class ", message)


class SplitFrontmatter(unittest.TestCase):
    def test_body_horizontal_rule_is_not_a_delimiter(self) -> None:
        content = (
            "---\nname: x\ndescription: y\n---\n\n# Heading\n\nText.\n\n---\n\nMore.\n"
        )
        frontmatter, body = split_frontmatter(content)
        self.assertEqual("name: x\ndescription: y", frontmatter)
        self.assertIn("More.", body)

    def test_prose_key_shaped_line_before_a_rule_is_allowed(self) -> None:
        content = (
            "---\nname: x\ndescription: y\n---\n\nNote: read this.\n\n"
            "Warning: and this.\n\n---\n\nMore.\n"
        )
        frontmatter, _body = split_frontmatter(content)
        self.assertEqual("name: x\ndescription: y", frontmatter)

    def test_a_suspicious_inner_rule_never_blocks_the_split(self) -> None:
        """R30. The split reports structure; it does not adjudicate intent."""
        content = "---\nname: x\ndescription: y\n---\nlicense: MIT\n---\n\nbody\n"
        frontmatter, body = split_frontmatter(content)
        self.assertEqual("name: x\ndescription: y", frontmatter)
        self.assertIn("license: MIT", body)

    def test_the_block_still_ends_at_the_first_whole_line_delimiter(self) -> None:
        """The original defect, restated as a property.

        The old non-greedy `^---\\n(.*?)\\n---` stopped at the first `\\n---`
        anywhere -- not necessarily a whole line -- so `----` and `--- x` both
        terminated the block and everything past them went unvalidated.
        """
        content = "---\nname: x\n----\ndescription: y\n--- \n---\n\nbody\n"
        frontmatter, body = split_frontmatter(content)
        self.assertEqual("name: x\n----\ndescription: y\n--- ", frontmatter)
        self.assertEqual("\nbody\n", body)

    def test_no_second_delimiter_means_no_check(self) -> None:
        content = "---\nname: x\ndescription: y\n---\n\nlicense: not frontmatter\n"
        frontmatter, body = split_frontmatter(content)
        self.assertEqual("name: x\ndescription: y", frontmatter)
        self.assertIn("license: not frontmatter", body)


class FindFrontmatterAmbiguity(unittest.TestCase):
    """R30. The detection, separated from the verdict.

    It reports rather than raises, it skips fenced code blocks, and it has two
    qualifying signals rather than one -- the second closes the residual
    research/V2-verification.md recorded (V19), where an inner ``---`` hiding
    an *unrecognised* key validated clean.
    """

    def test_recognised_stranded_key_is_reported(self) -> None:
        content = "---\nname: x\ndescription: y\n---\nlicense: MIT\n---\n\nbody\n"
        hit = find_frontmatter_ambiguity(content)
        self.assertIsNotNone(hit)
        self.assertEqual("license", hit.key)
        self.assertTrue(hit.recognised)
        self.assertEqual(5, hit.key_line)
        self.assertEqual(6, hit.rule_line)
        self.assertEqual(4, hit.close_line)

    def test_unrecognised_stranded_key_is_reported_when_adjacent(self) -> None:
        content = (
            "---\nname: x\ndescription: |\n  Real line.\n---\n"
            "  hidden\nsome-vendor-key: v\n---\n\nbody\n"
        )
        hit = find_frontmatter_ambiguity(content)
        self.assertIsNotNone(hit)
        self.assertEqual("some-vendor-key", hit.key)
        self.assertFalse(hit.recognised)

    def test_prose_separated_by_a_blank_line_is_not_reported(self) -> None:
        content = (
            "---\nname: x\ndescription: y\n---\n\nNote: read this.\n\n"
            "Warning: and this.\n\n---\n\nMore.\n"
        )
        self.assertIsNone(find_frontmatter_ambiguity(content))

    def test_fenced_blocks_are_skipped(self) -> None:
        fences = [
            ("```", "```"),
            ("```yaml", "```"),
            ("~~~", "~~~"),
            ("~~~yaml", "~~~"),
            ("````md", "````"),   # a longer fence, closed by its own length
            ("  ```", "  ```"),   # up to three spaces of indent still opens one
        ]
        for opener, closer in fences:
            with self.subTest(fence=opener):
                content = (
                    f"---\nname: x\ndescription: y\n---\n\n{opener}\nname: inner\n"
                    f"license: MIT\n---\n{closer}\n\n---\n\nend\n"
                )
                self.assertIsNone(find_frontmatter_ambiguity(content))

    def test_an_unclosed_fence_swallows_the_rest(self) -> None:
        """Conservative by design: no terminator seen means no finding."""
        content = "---\nname: x\ndescription: y\n---\n\n```\nlicense: MIT\n---\n"
        self.assertIsNone(find_frontmatter_ambiguity(content))

    def test_a_stray_key_after_a_fence_is_still_found(self) -> None:
        content = (
            "---\nname: x\ndescription: y\n---\n\n```\nname: inner\n```\n\n"
            "license: MIT\n\n---\n\nend\n"
        )
        hit = find_frontmatter_ambiguity(content)
        self.assertIsNotNone(hit)
        self.assertEqual("license", hit.key)

    def test_known_keys_widen_the_first_signal(self) -> None:
        content = (
            "---\nname: x\ndescription: y\n---\n\nwhen_to_use: z\n\n---\n\nbody\n"
        )
        # `when_to_use` is not in the portable set and the body starts with a
        # blank line, so neither signal fires...
        self.assertIsNone(find_frontmatter_ambiguity(content))
        # ...but the validator passes its full union, which recognises it.
        hit = find_frontmatter_ambiguity(
            content, known_keys=SPEC_FIELDS | {"when_to_use"}
        )
        self.assertIsNotNone(hit)
        self.assertEqual("when_to_use", hit.key)

    def test_a_bare_horizontal_rule_is_never_a_finding(self) -> None:
        content = "---\nname: x\ndescription: y\n---\n\n# Heading\n\n---\n\nMore.\n"
        self.assertIsNone(find_frontmatter_ambiguity(content))

    def test_a_file_without_frontmatter_is_not_this_functions_problem(self) -> None:
        self.assertIsNone(find_frontmatter_ambiguity("no frontmatter\n---\nx: y\n---\n"))
        self.assertIsNone(find_frontmatter_ambiguity("---\nname: x\n"))

    def test_the_message_offers_both_readings(self) -> None:
        content = "---\nname: x\ndescription: y\n---\nlicense: MIT\n---\n\nbody\n"
        message = find_frontmatter_ambiguity(content).message
        self.assertNotIn("truncated", message.lower())
        self.assertIn("horizontal rule", message)
        self.assertIn("settings block", message)
        self.assertIn("line 5", message)


class Encoding(unittest.TestCase):
    def test_read_text_utf8_rejects_non_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            path.write_bytes("café".encode("latin-1"))
            with self.assertRaises(SkillMdError):
                read_text_utf8(path)

    def test_read_text_utf8_strips_bom_and_normalises_crlf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            path.write_bytes("﻿a\r\nb\r\n".encode("utf-8"))
            self.assertEqual("a\nb\n", read_text_utf8(path))

    def test_read_text_utf8_leaves_lone_cr_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            path.write_bytes(b"a\rb\r")
            self.assertEqual("a\rb\r", read_text_utf8(path))

    def test_unicode_decode_error_is_not_an_oserror(self) -> None:
        """C7: an `except (json.JSONDecodeError, OSError)` handler misses it."""
        self.assertTrue(issubclass(UnicodeDecodeError, ValueError))
        self.assertFalse(issubclass(UnicodeDecodeError, OSError))

    def test_configure_console_is_idempotent(self) -> None:
        configure_console()
        configure_console()


class LoadFrontmatter(unittest.TestCase):
    def test_returns_mapping_and_body(self) -> None:
        data, body = load_frontmatter("---\nname: x\ndescription: y\n---\n\nbody text\n")
        self.assertEqual({"name": "x", "description": "y"}, data)
        self.assertEqual("\nbody text\n", body)

    def test_nested_duplicate_key_is_rejected(self) -> None:
        content = "---\nname: x\ndescription: y\nmetadata:\n  a: 1\n  a: 2\n---\n"
        with self.assertRaises(SkillMdError):
            load_frontmatter(content)

    def test_nested_mapping_is_fully_constructed(self) -> None:
        content = "---\nname: x\ndescription: y\nmetadata:\n  a: '1'\n  b: '2'\n---\n"
        data, _body = load_frontmatter(content)
        self.assertEqual({"a": "1", "b": "2"}, data["metadata"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
