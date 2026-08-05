#!/usr/bin/env python3
"""CLI-contract tests for scripts/quick_validate.py.

Run from the skill root::

    python -m unittest tests.test_quick_validate_cli -v
    python -m tests.test_quick_validate_cli

These run the validator as a subprocess, because the properties under test are
process-level: which stream carries what, and what the exit status is. They are
also run with the interpreter's UTF-8 mode *off*, so the cp1252 default that
crashed the old validator is the condition being exercised, not a condition
being avoided.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from tests.validator_fixtures import build  # noqa: E402


def run_validator(*args: str, utf8_mode: bool = False):
    """Invoke `python -m scripts.quick_validate` from the skill root."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONIOENCODING", None)
    if utf8_mode:
        env["PYTHONUTF8"] = "1"
    else:
        env.pop("PYTHONUTF8", None)
    return subprocess.run(
        [sys.executable, "-m", "scripts.quick_validate", *args],
        cwd=SKILL_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


class CorpusMixin(unittest.TestCase):
    corpus: Path
    _tmp: tempfile.TemporaryDirectory

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="skill-validator-cli-")
        cls.corpus = build(Path(cls._tmp.name) / "corpus")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()


class ExitStatus(CorpusMixin):
    def test_valid_skill_exits_zero(self) -> None:
        result = run_validator(str(self.corpus / "good-skill"))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Skill is valid!", result.stdout)

    def test_invalid_skill_exits_non_zero(self) -> None:
        result = run_validator(str(self.corpus / "fn-desc-empty"))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("description", result.stdout)

    def test_warnings_alone_do_not_fail(self) -> None:
        result = run_validator(str(self.corpus / "claude-helper"))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("warning", result.stdout)

    def test_same_skill_different_target_different_verdict(self) -> None:
        path = str(self.corpus / "fp-cc-fields")
        self.assertEqual(0, run_validator(path, "--target", "claude-code").returncode)
        self.assertNotEqual(0, run_validator(path, "--target", "portable").returncode)

    def test_no_traceback_on_undecodable_skill_md(self) -> None:
        result = run_validator(str(self.corpus / "crash-utf16"))
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("UTF-8", result.stdout)

    def test_no_traceback_when_skill_md_is_a_directory(self) -> None:
        result = run_validator(str(self.corpus / "crash-skillmd-is-dir"))
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("Traceback", result.stderr)

    def test_non_ascii_skill_on_a_cp1252_default_interpreter(self) -> None:
        """The crash that made the verdict depend on the machine's locale."""
        result = run_validator(str(self.corpus / "fp-smart-quotes"), utf8_mode=False)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_verdict_is_identical_under_both_interpreter_encodings(self) -> None:
        for name in ("fp-smart-quotes", "fp-nonascii-1000", "fn-latin1", "fp-bom"):
            with self.subTest(fixture=name):
                path = str(self.corpus / name)
                default = run_validator(path, utf8_mode=False)
                utf8 = run_validator(path, utf8_mode=True)
                self.assertEqual(
                    default.returncode, utf8.returncode,
                    f"{name}: verdict depends on PYTHONUTF8",
                )


class JsonOutput(CorpusMixin):
    def test_stdout_carries_json_alone(self) -> None:
        result = run_validator(str(self.corpus / "new-multi-defect"), "--json",
                               "--target", "portable")
        payload = json.loads(result.stdout)  # raises if anything else is on stdout
        self.assertFalse(payload["valid"])
        self.assertEqual("portable", payload["target"])
        self.assertGreaterEqual(payload["error_count"], 4)

    def test_json_is_valid_for_a_clean_skill(self) -> None:
        result = run_validator(str(self.corpus / "good-skill"), "--json")
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual([], payload["findings"])
        self.assertEqual(0, result.returncode)

    def test_json_for_an_unreadable_file_is_still_json(self) -> None:
        result = run_validator(str(self.corpus / "crash-utf16"), "--json")
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertEqual("skill-md.parse", payload["findings"][0]["code"])

    def test_every_finding_carries_field_code_and_target(self) -> None:
        result = run_validator(str(self.corpus / "new-multi-defect"), "--json",
                               "--target", "claude-ai")
        payload = json.loads(result.stdout)
        for finding in payload["findings"]:
            self.assertEqual({"level", "field", "code", "message", "target"},
                             set(finding))
            self.assertEqual("claude-ai", finding["target"])
            self.assertIn(finding["level"], ("error", "warning"))

    def test_json_exit_status_matches_findings(self) -> None:
        # fn-dir-mismatch is only an error where a primary source states the
        # rule (R31/FP-3), so this asks the question at one of those targets.
        result = run_validator(str(self.corpus / "fn-dir-mismatch"), "--json",
                               "--target", "portable")
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(json.loads(result.stdout)["valid"])

    def test_warnings_alone_exit_zero(self) -> None:
        """C6: warnings alone exit 0, and the JSON says so.

        The same fixture at the default target, where the mismatch is a
        warning: valid, reported, exit 0.
        """
        result = run_validator(str(self.corpus / "fn-dir-mismatch"), "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(0, result.returncode)
        self.assertTrue(payload["valid"])
        self.assertEqual(0, payload["error_count"])
        self.assertGreaterEqual(payload["warning_count"], 1)
        self.assertIn(
            "name.directory-mismatch", [f["code"] for f in payload["findings"]]
        )


class Arguments(CorpusMixin):
    def test_rejects_unknown_target(self) -> None:
        result = run_validator(str(self.corpus / "good-skill"), "--target", "nope")
        self.assertEqual(2, result.returncode)
        self.assertIn("invalid choice", result.stderr)

    def test_default_target_is_claude_code(self) -> None:
        result = run_validator(str(self.corpus / "good-skill"), "--json")
        self.assertEqual("claude-code", json.loads(result.stdout)["target"])

    def test_missing_argument_is_a_usage_error(self) -> None:
        result = run_validator()
        self.assertEqual(2, result.returncode)
        self.assertIn("usage", result.stderr.lower())

    def test_messages_name_the_target(self) -> None:
        result = run_validator(str(self.corpus / "fn-dir-mismatch"),
                               "--target", "claude-ai")
        self.assertIn("claude-ai", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
