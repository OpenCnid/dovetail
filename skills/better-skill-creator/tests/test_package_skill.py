#!/usr/bin/env python3
"""Tests for scripts/package_skill.py.

Run from the skill root:

    python -m unittest tests.test_package_skill -v
    python -m tests.test_package_skill

Every case here corresponds to a defect that was demonstrated against the
previous packager in research/12-validator-packager.md (F6-F11) and
research/19-distribution-reality.md (F1, F2, F5, F8). The fixture seed lives in
tests/fixtures/; the hostile decoration (.env, .git/, .venv/, symlinks, prior
build output) is materialized into a temporary workspace rather than committed,
so a nested .git never lands inside this repository.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

import scripts.package_skill as package_module  # noqa: E402
from scripts.package_skill import (  # noqa: E402
    _normalize_validation,
    _read_frontmatter_name,
    _run_validation,
    build_package,
    check_member_names,
    render_report,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Marker strings. If any of these reaches the archive, a real author would have
# shipped a real secret.
ENV_SECRET = "SECRET=hunter2\nAPI_KEY=sk-live-abc123def456\n"
GIT_REMOTE = "url = https://user:tok3n@github.com/example/private.git"
CLAUDE_LOCAL = '{"permissions": {"allow": ["Bash(rm:*)"]}}'
OUTSIDE_SECRET = "CONTENT-FROM-OUTSIDE-THE-SKILL-TREE-2f4b9c"
PRIOR_BUILD = b"PK\x03\x04PRIOR-BUILD-ARTIFACT"


def _symlinks_available() -> bool:
    probe = Path(tempfile.mkdtemp(prefix="symlink-probe-"))
    try:
        target = probe / "t.txt"
        target.write_text("x", encoding="utf-8")
        os.symlink(target, probe / "l.txt")
        return True
    except (OSError, NotImplementedError):
        return False
    finally:
        shutil.rmtree(probe, ignore_errors=True)


SYMLINKS_AVAILABLE = _symlinks_available()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_hostile_workspace(root: Path) -> Path:
    """Copy the seed skill into root/ and decorate it with the refusal set."""
    skill = root / "hostile-skill"
    shutil.copytree(FIXTURES / "hostile-skill", skill)

    # Content outside the skill tree that a symlink will point at.
    _write(root / "outside" / "secret.txt", OUTSIDE_SECRET)
    _write(root / "outside" / "dirtree" / "leak.md", OUTSIDE_SECRET)

    # Secrets and local state.
    _write(skill / ".env", ENV_SECRET)
    _write(skill / ".env.local", ENV_SECRET)
    _write(skill / ".git" / "config", GIT_REMOTE)
    _write(skill / ".git" / "objects" / "ab" / "cdef", "binary-ish object")
    _write(skill / ".git" / "hooks" / "pre-push.sample", "#!/bin/sh\n")
    _write(skill / ".gitignore", "dist/\n")
    _write(skill / ".venv" / "pyvenv.cfg", "home = C:\\Python313")
    _write(skill / ".venv" / "Lib" / "big.txt", "x" * 4096)
    _write(skill / ".claude" / "settings.local.json", CLAUDE_LOCAL)
    _write(skill / ".vscode" / "launch.json", "{}")
    _write(skill / ".DS_Store", "mac metadata")
    _write(skill / "id_rsa", "-----BEGIN OPENSSH PRIVATE KEY-----")
    _write(skill / "server.pem", "-----BEGIN CERTIFICATE-----")

    # Build detritus.
    _write(skill / "__pycache__" / "mod.cpython-313.pyc", "bytecode")
    _write(skill / "stray.pyc", "bytecode")
    _write(skill / "node_modules" / "left-pad" / "index.js", "module.exports = 1;")
    _write(skill / "evals" / "evals.json", "{}")

    # Prior build output, at the root and in a dist/ directory.
    (skill / "hostile-skill.skill").write_bytes(PRIOR_BUILD)
    (skill / "dist").mkdir(exist_ok=True)
    (skill / "dist" / "hostile-skill.skill").write_bytes(PRIOR_BUILD)
    (skill / "dist" / "hostile-skill.zip").write_bytes(PRIOR_BUILD)

    # The one allowlisted dot-entry, and a genuinely empty directory.
    _write(skill / ".claude-plugin" / "plugin.json", '{"name": "hostile-skill"}')
    (skill / "outputs").mkdir(exist_ok=True)

    if SYMLINKS_AVAILABLE:
        os.symlink(root / "outside" / "secret.txt", skill / "link-to-secret.txt")
        os.symlink(
            root / "outside" / "dirtree",
            skill / "references" / "shared",
            target_is_directory=True,
        )
    return skill


EXPECTED_MEMBERS = {
    "hostile-skill/SKILL.md",
    "hostile-skill/.claude-plugin/plugin.json",
    "hostile-skill/assets/nested/evals/keeper.md",
    "hostile-skill/references/notes.md",
    "hostile-skill/scripts/run.sh",
    "hostile-skill/scripts/tool.py",
}
EXPECTED_DIR_ENTRIES = {"hostile-skill/outputs/"}

FORBIDDEN_SUBSTRINGS = (
    "/.env",
    "/.git",
    "/.venv",
    "/.claude/",
    "/.vscode",
    "/.DS_Store",
    "__pycache__",
    "node_modules",
    ".pyc",
    ".skill",
    ".zip",
    "id_rsa",
    ".pem",
    "shared/",
    "link-to-secret",
)


class PackagerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="package-skill-test-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.skill = build_hostile_workspace(self.root)
        self.dist = self.root / "dist-out"

    def package(self, output_dir=None, **kwargs):
        result = build_package(self.skill, output_dir or self.dist, **kwargs)
        if result.errors:
            self.fail("packaging failed: " + " | ".join(result.errors))
        return result

    def report_text(self, result) -> str:
        buffer = io.StringIO()
        render_report(result, buffer)
        return buffer.getvalue()


class TestExclusions(PackagerTestCase):
    def test_archive_contains_exactly_the_expected_members(self):
        result = self.package()
        with zipfile.ZipFile(result.archive) as archive:
            names = set(archive.namelist())
        self.assertEqual(names, EXPECTED_MEMBERS | EXPECTED_DIR_ENTRIES)

    def test_no_member_matches_a_forbidden_pattern(self):
        result = self.package()
        with zipfile.ZipFile(result.archive) as archive:
            names = archive.namelist()
        for name in names:
            for forbidden in FORBIDDEN_SUBSTRINGS:
                self.assertNotIn(
                    forbidden, name, f"{name} should not be in the distributable"
                )

    def test_secret_bytes_are_absent_from_the_archive_file(self):
        result = self.package()
        blob = result.archive.read_bytes()
        for secret in (b"hunter2", b"sk-live-abc123def456", b"tok3n", OUTSIDE_SECRET.encode()):
            self.assertNotIn(secret, blob)

    def test_nested_evals_survives_while_root_evals_is_dropped(self):
        result = self.package()
        with zipfile.ZipFile(result.archive) as archive:
            names = set(archive.namelist())
        self.assertIn("hostile-skill/assets/nested/evals/keeper.md", names)
        self.assertNotIn("hostile-skill/evals/evals.json", names)

    def test_report_names_every_exclusion_with_a_reason(self):
        result = self.package()
        report = self.report_text(result)
        for expected in (
            "hostile-skill/.env",
            "hostile-skill/.git/",
            "hostile-skill/.venv/",
            "hostile-skill/.claude/",
            "hostile-skill/hostile-skill.skill",
            "hostile-skill/dist/hostile-skill.zip",
            "hostile-skill/id_rsa",
            "hostile-skill/node_modules/",
            "hostile-skill/evals/",
        ):
            self.assertIn(expected, report, f"report must name {expected}")
        self.assertIn("may contain secrets", report)
        self.assertIn("version control metadata", report)
        self.assertIn("private key", report)

    def test_report_lists_what_was_included(self):
        result = self.package()
        report = self.report_text(result)
        for member in EXPECTED_MEMBERS:
            self.assertIn(member, report)
        self.assertIn("Included 6 file(s)", report)

    def test_excluded_directories_are_reported_once_with_their_weight(self):
        result = self.package()
        git_entries = [e for e in result.excluded if e.path == "hostile-skill/.git/"]
        self.assertEqual(len(git_entries), 1)
        self.assertEqual(git_entries[0].files, 3)
        self.assertGreater(git_entries[0].size, 0)


class TestSymlinks(PackagerTestCase):
    def setUp(self) -> None:
        if not SYMLINKS_AVAILABLE:
            self.skipTest("symlink creation is unavailable on this machine")
        super().setUp()

    def test_file_symlink_is_not_dereferenced(self):
        result = self.package()
        with zipfile.ZipFile(result.archive) as archive:
            blob = b"".join(archive.read(n) for n in archive.namelist())
        self.assertNotIn(OUTSIDE_SECRET.encode(), blob)
        self.assertNotIn(
            "hostile-skill/link-to-secret.txt", set(zipfile.ZipFile(result.archive).namelist())
        )

    def test_both_symlinks_are_reported(self):
        result = self.package()
        paths = {link.path for link in result.symlinks}
        self.assertEqual(
            paths,
            {"hostile-skill/link-to-secret.txt", "hostile-skill/references/shared/"},
        )
        report = self.report_text(result)
        self.assertIn("Skipped 2 symlink(s)", report)
        self.assertIn("not followed", report)
        self.assertTrue(any("symlink not followed" in w for w in result.warnings))


class TestArtifactShape(PackagerTestCase):
    def test_extension_is_zip(self):
        result = self.package()
        self.assertEqual(result.archive.suffix, ".zip")
        self.assertEqual(result.archive.name, "hostile-skill.zip")
        self.assertFalse(list(self.dist.glob("*.skill")))

    def test_single_top_level_directory_named_for_the_skill(self):
        result = self.package()
        with zipfile.ZipFile(result.archive) as archive:
            tops = {name.split("/")[0] for name in archive.namelist()}
        self.assertEqual(tops, {"hostile-skill"})

    def test_empty_directory_survives_the_round_trip(self):
        result = self.package()
        extracted = self.root / "extract-empty"
        with zipfile.ZipFile(result.archive) as archive:
            archive.extractall(extracted)
        self.assertTrue((extracted / "hostile-skill" / "outputs").is_dir())

    def test_scripts_carry_a_unix_execute_bit(self):
        result = self.package()
        with zipfile.ZipFile(result.archive) as archive:
            script = archive.getinfo("hostile-skill/scripts/run.sh")
            doc = archive.getinfo("hostile-skill/references/notes.md")
        self.assertEqual(script.create_system, 3, "create_system 3 (Unix) carries the mode")
        self.assertEqual((script.external_attr >> 16) & 0o777, 0o755)
        self.assertEqual((doc.external_attr >> 16) & 0o777, 0o644)

    def test_archive_passes_its_own_crc_check(self):
        result = self.package()
        with zipfile.ZipFile(result.archive) as archive:
            self.assertIsNone(archive.testzip())

    def test_no_partial_file_is_left_behind(self):
        self.package()
        self.assertEqual(list(self.dist.glob("*.partial")), [])

    def test_a_failed_write_leaves_the_previous_archive_intact(self):
        """research/12 F10: the destination used to be truncated before the walk."""
        good = self.package()
        before = good.archive.read_bytes()

        def boom(destination, members, empty_dirs, **kwargs):
            raise OSError("simulated write failure")

        original = package_module._write_archive
        package_module._write_archive = boom
        try:
            failed = build_package(self.skill, self.dist)
        finally:
            package_module._write_archive = original

        self.assertFalse(failed.ok)
        self.assertEqual(good.archive.read_bytes(), before)
        self.assertEqual(list(self.dist.glob("*.partial")), [])

    def test_unsafe_member_names_abort_the_build(self):
        """The check_member_names gate is actually wired into build_package."""
        original = package_module.check_member_names
        package_module.check_member_names = lambda names: ["s/aux.txt: reserved"]
        try:
            result = build_package(self.skill, self.dist)
        finally:
            package_module.check_member_names = original
        self.assertFalse(result.ok)
        self.assertTrue(any("cannot be extracted safely" in e for e in result.errors))
        self.assertFalse(list(self.dist.glob("*.zip")))


class TestRoundTrip(PackagerTestCase):
    def test_every_member_round_trips_byte_for_byte(self):
        result = self.package()
        extracted = self.root / "extract-bytes"
        with zipfile.ZipFile(result.archive) as archive:
            archive.extractall(extracted)
        for member in EXPECTED_MEMBERS:
            relative = member.split("/", 1)[1]
            self.assertEqual(
                (extracted / "hostile-skill" / relative).read_bytes(),
                (self.skill / relative).read_bytes(),
                f"{member} did not round-trip",
            )

    def test_installs_by_extraction_into_a_skills_directory(self):
        result = self.package()
        project = self.root / "project"
        skills = project / ".claude" / "skills"
        skills.mkdir(parents=True)
        with zipfile.ZipFile(result.archive) as archive:
            archive.extractall(skills)

        installed = skills / "hostile-skill"
        self.assertTrue((installed / "SKILL.md").is_file())
        self.assertTrue((installed / "scripts" / "tool.py").is_file())

        valid, errors, _warnings = _run_validation(installed, "claude-code")
        self.assertTrue(valid, f"extracted skill failed validation: {errors}")

    def test_rebuilding_the_extracted_copy_is_stable(self):
        first = self.package()
        extracted = self.root / "extract-stable"
        with zipfile.ZipFile(first.archive) as archive:
            archive.extractall(extracted)
        second = build_package(extracted / "hostile-skill", self.root / "dist-second")
        self.assertTrue(second.ok, second.errors)
        with zipfile.ZipFile(first.archive) as a, zipfile.ZipFile(second.archive) as b:
            self.assertEqual(set(a.namelist()), set(b.namelist()))


class TestOutputInsideSkill(PackagerTestCase):
    """research/12 F8: the archive used to embed a torn copy of itself."""

    def test_no_self_inclusion_when_output_is_inside_the_skill(self):
        result = build_package(self.skill, self.skill / "build")
        self.assertTrue(result.ok, result.errors)
        with zipfile.ZipFile(result.archive) as archive:
            names = archive.namelist()
        self.assertFalse([n for n in names if n.endswith((".zip", ".skill"))])
        self.assertEqual(set(names), EXPECTED_MEMBERS | EXPECTED_DIR_ENTRIES)

    def test_output_directory_equal_to_the_skill_directory(self):
        result = build_package(self.skill, self.skill)
        self.assertTrue(result.ok, result.errors)
        with zipfile.ZipFile(result.archive) as archive:
            self.assertEqual(set(archive.namelist()), EXPECTED_MEMBERS | EXPECTED_DIR_ENTRIES)
        again = build_package(self.skill, self.skill)
        with zipfile.ZipFile(again.archive) as archive:
            self.assertEqual(set(archive.namelist()), EXPECTED_MEMBERS | EXPECTED_DIR_ENTRIES)

    def test_second_build_into_the_skill_matches_the_first(self):
        first = build_package(self.skill, self.skill / "build")
        second = build_package(self.skill, self.skill / "build")
        self.assertTrue(second.ok, second.errors)
        with zipfile.ZipFile(first.archive) as a, zipfile.ZipFile(second.archive) as b:
            self.assertEqual(set(a.namelist()), set(b.namelist()))
        self.assertTrue(any("overwriting existing" in w for w in second.warnings))


class TestNameMatching(unittest.TestCase):
    """research/19 F5: folder name must equal the frontmatter name."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="package-skill-name-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_mismatched_directory_name_is_refused(self):
        skill = self.root / "mismatch-dir"
        shutil.copytree(FIXTURES / "mismatch-dir", skill)
        result = build_package(skill, self.root / "dist")
        self.assertFalse(result.ok)
        # Either quick_validate's hard error (C9) or the packager's own
        # archive-shape check gets there first; both must name both sides.
        combined = "\n".join(result.errors)
        self.assertIn("totally-different-name", combined)
        self.assertIn("mismatch-dir", combined)
        self.assertFalse(list((self.root / "dist").glob("*")))

    def test_packager_enforces_the_match_independently_of_the_validator(self):
        """quick_validate is not the only gate: the archive shape depends on it."""
        skill = self.root / "mismatch-dir"
        shutil.copytree(FIXTURES / "mismatch-dir", skill)
        name, error = _read_frontmatter_name(skill / "SKILL.md")
        self.assertIsNone(error)
        self.assertNotEqual(name, skill.name)

    def test_frontmatter_name_is_read_as_utf8(self):
        skill = FIXTURES / "nonascii-skill"
        name, error = _read_frontmatter_name(skill / "SKILL.md")
        self.assertIsNone(error)
        self.assertEqual(name, "nonascii-skill")


class TestMemberNameSafety(unittest.TestCase):
    """research/12 F11: names a Windows extraction cannot round-trip."""

    def test_hostile_names_are_each_flagged(self):
        problems = check_member_names(
            [
                "s/SKILL.md",
                "s/README.md",
                "s/readme.md",
                "s/refs/a:b.md",
                "s/refs/q?.md",
                "s/CON.md",
                "s/aux.txt",
                "s/trail. ",
                "s/back\\slash.md",
                "s/../escape.md",
            ]
        )
        joined = "\n".join(problems)
        self.assertIn("a:b.md", joined)
        self.assertIn("q?.md", joined)
        self.assertIn("CON.md", joined)
        self.assertIn("aux.txt", joined)
        self.assertIn("trail. ", joined)
        self.assertIn("back\\slash.md", joined)
        self.assertIn("escape.md", joined)
        self.assertIn("readme.md", joined)

    def test_a_clean_name_set_produces_no_problems(self):
        self.assertEqual(
            check_member_names(
                ["s/SKILL.md", "s/scripts/tool.py", "s/references/notes.md", "s/outputs/"]
            ),
            [],
        )


class TestValidationAdapter(unittest.TestCase):
    """package_skill must read quick_validate's verdict, never assume it."""

    def test_legacy_two_tuple(self):
        self.assertEqual(_normalize_validation((True, "Skill is valid!")), (True, [], []))
        self.assertEqual(
            _normalize_validation((False, "Name is too long")), (False, ["Name is too long"], [])
        )

    def test_accumulated_findings_list(self):
        ok, errors, _ = _normalize_validation((False, ["missing name", "missing description"]))
        self.assertFalse(ok)
        self.assertEqual(errors, ["missing name", "missing description"])

    def test_mapping_with_errors_and_warnings(self):
        ok, errors, warnings = _normalize_validation(
            {"ok": False, "errors": [{"message": "name != directory"}], "warnings": ["long"]}
        )
        self.assertFalse(ok)
        self.assertEqual(errors, ["name != directory"])
        self.assertEqual(warnings, ["long"])

    def test_object_with_attributes(self):
        class Verdict:
            ok = True
            errors: list = []
            warnings = ["description exceeds 200 chars for claude-ai"]

        ok, errors, warnings = _normalize_validation(Verdict())
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, ["description exceeds 200 chars for claude-ai"])

    def test_unrecognized_shape_raises_rather_than_assuming_valid(self):
        with self.assertRaises(RuntimeError):
            _normalize_validation(42)


class TestCommandLine(PackagerTestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "scripts.package_skill", *args],
            cwd=SKILL_ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )

    def test_plain_run_prints_the_archive_path_on_stdout(self):
        proc = self.run_cli(str(self.skill), str(self.dist))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # Resolved paths, not strings. package_skill resolves output_dir before
        # printing it, while self.dist descends from tempfile.mkdtemp(), which on
        # Windows inherits %TEMP% verbatim -- and that is an 8.3 short name
        # ("C:\Users\RUNNER~1\...") on any host whose username runs past eight
        # characters. Both spellings name one file, so comparing them as strings
        # passes only where the username happens to be short enough not to be
        # shortened, and fails on a CI runner called "runneradmin".
        self.assertEqual(
            Path(proc.stdout.strip()).resolve(),
            (self.dist / "hostile-skill.zip").resolve(),
        )
        self.assertIn("Excluded", proc.stderr)
        self.assertIn("Included", proc.stderr)

    def test_json_manifest_is_alone_on_stdout(self):
        proc = self.run_cli(str(self.skill), str(self.dist), "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        manifest = json.loads(proc.stdout)
        self.assertTrue(manifest["ok"])
        self.assertEqual(manifest["skill_name"], "hostile-skill")
        included = {entry["path"] for entry in manifest["included"]}
        self.assertEqual(included, EXPECTED_MEMBERS)
        excluded = {entry["path"] for entry in manifest["excluded"]}
        self.assertIn("hostile-skill/.env", excluded)
        self.assertIn("hostile-skill/.git/", excluded)
        self.assertIn("Included", proc.stderr)

    def test_dry_run_writes_nothing(self):
        proc = self.run_cli(str(self.skill), str(self.dist), "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Dry run", proc.stderr)
        self.assertFalse(self.dist.exists() and list(self.dist.glob("*.zip")))

    def test_mismatched_name_exits_non_zero(self):
        skill = self.root / "mismatch-dir"
        shutil.copytree(FIXTURES / "mismatch-dir", skill)
        proc = self.run_cli(str(skill), str(self.dist))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("totally-different-name", proc.stderr)
        self.assertIn("mismatch-dir", proc.stderr)
        self.assertFalse(list(self.dist.glob("*.zip")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
