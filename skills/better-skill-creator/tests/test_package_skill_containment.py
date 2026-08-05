#!/usr/bin/env python3
"""Regression tests for R29 and R32 in scripts/package_skill.py.

Run from the skill root:

    python -m unittest tests.test_package_skill_containment -v
    python -m tests.test_package_skill_containment

Every case here reproduces a defect that was demonstrated against the previous
packager in research/V2-verification.md and is tracked in
research/_REMEDIATION.md:

R29a  An NTFS directory junction was followed. ``Path.is_symlink()`` returns
      False for ``IO_REPARSE_TAG_MOUNT_POINT`` and ``os.walk(followlinks=False)``
      walks straight through one, so two files from *outside* the skill tree
      were copied into the distributable with no warning. A junction needs no
      elevation to create (``mklink /J``), which makes it the more reachable of
      the two link forms on Windows, not the exotic one.
R29b  The exclusion rule was ``name.startswith(".env")``, so ``production.env``,
      ``config/local.env``, ``token.txt`` and ``secrets.yaml`` all shipped.
R32a  A lowercase ``skill.md`` validated clean and then could not be packaged.
R32b  An archive over the documented 30 MB ceiling reported success.

These assert containment, not link-detection, and
exclusions that match patterns and categories rather than filename prefixes.

The hostile decoration (junction, symlinks, hard link, credential-shaped files)
is materialized into a temporary workspace rather than committed, so no link
pointing out of the repository is ever checked in.
"""

from __future__ import annotations

import io
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
    API_SIZE_LIMIT_BYTES,
    _is_within,
    _real,
    _sensitive_reason,
    build_package,
    render_report,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Content that lives outside the skill folder. Reaching either string through
# any kind of link and writing it into the archive is the leak R29 describes.
OUTSIDE_VIA_LINK = "OUT-OF-TREE-REACHED-BY-LINK-3d91ac"
OUTSIDE_VIA_HARDLINK = "OUT-OF-TREE-REACHED-BY-HARDLINK-77c2fe"

# Secrets in files the old prefix rule shipped. Every one of these is a marker:
# finding it in the archive means a real author shipped a real credential.
SECRET_FILES = {
    "production.env": "DB_PASSWORD=hunter2-prod\n",
    "config/local.env": "STRIPE_KEY=sk-live-abc123def456\n",
    "token.txt": "ghp_0123456789abcdefghijklmnopqrstuvwxyzAB\n",
    "secrets.yaml": "database:\n  password: hunter2-yaml\n",
    "config/credentials.json": '{"aws_access_key_id": "AKIAIOSFODNN7EXAMPLE"}\n',
    "aws_credentials": "[default]\naws_secret_access_key = wJalrXUtnFEMIsecret\n",
    "api_key.json": '{"key": "sk-ant-api03-notreal-butshaped-likeone"}\n',
    ".env": "LEGACY_PREFIX_FORM=hunter2-dotenv\n",
    # The .claude-plugin carve-out is an allowlisted subtree; a credential
    # inside it is still a credential (research/V2-verification.md PK-4).
    ".claude-plugin/prod.env": "PLUGIN_SECRET=hunter2-plugin\n",
}

SECRET_MARKERS = (
    b"hunter2-prod",
    b"sk-live-abc123def456",
    b"ghp_0123456789",
    b"hunter2-yaml",
    b"AKIAIOSFODNN7EXAMPLE",
    b"wJalrXUtnFEMIsecret",
    b"sk-ant-api03-notreal",
    b"hunter2-dotenv",
    b"hunter2-plugin",
)

# Names that *look* credential-shaped to a substring rule and are ordinary
# documentation. Dropping these silently is the same class of defect as
# shipping a secret, so they are asserted present.
LOOKALIKE_FILES = {
    "references/tokenizer.md": "How the tokenizer works.\n",
    "references/keyboard-shortcuts.md": "Keyboard shortcuts.\n",
    "references/environments.md": "Supported environments.\n",
}

EXPECTED_MEMBERS = {
    "hostile-skill/SKILL.md",
    "hostile-skill/.claude-plugin/plugin.json",
    "hostile-skill/assets/nested/evals/keeper.md",
    "hostile-skill/references/notes.md",
    "hostile-skill/references/tokenizer.md",
    "hostile-skill/references/keyboard-shortcuts.md",
    "hostile-skill/references/environments.md",
    "hostile-skill/references/hardlinked.md",
    "hostile-skill/scripts/run.sh",
    "hostile-skill/scripts/tool.py",
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _make_junction(link: Path, target: Path) -> bool:
    """Create an NTFS directory junction. No elevation required, hence R29a."""
    if os.name != "nt":
        return False
    link.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0 and link.exists()


def _hardlinks_available() -> bool:
    probe = Path(tempfile.mkdtemp(prefix="hardlink-probe-"))
    try:
        target = probe / "t.txt"
        target.write_text("x", encoding="utf-8")
        os.link(target, probe / "h.txt")
        return True
    except (OSError, NotImplementedError):
        return False
    finally:
        shutil.rmtree(probe, ignore_errors=True)


SYMLINKS_AVAILABLE = _symlinks_available()
HARDLINKS_AVAILABLE = _hardlinks_available()


def build_leak_workspace(root: Path) -> tuple[Path, dict]:
    """Copy the seed skill into root/ and decorate it with the R29 leak set.

    Returns (skill_path, facts) where facts records which link types this
    machine could actually create, so the assertions can say what they cover.
    """
    skill = root / "hostile-skill"
    shutil.copytree(FIXTURES / "hostile-skill", skill)
    _write(skill / ".claude-plugin" / "plugin.json", '{"name": "hostile-skill"}')

    for relative, text in SECRET_FILES.items():
        _write(skill / relative, text)
    for relative, text in LOOKALIKE_FILES.items():
        _write(skill / relative, text)

    # Content outside the skill folder, one file per link type so the byte scan
    # can tell which route leaked.
    outside = root / "outside"
    _write(outside / "dirtree" / "leak.md", OUTSIDE_VIA_LINK)
    _write(outside / "dirtree" / "deep" / "more.txt", OUTSIDE_VIA_LINK)
    _write(outside / "secret.txt", OUTSIDE_VIA_LINK)
    _write(outside / "hard-source.md", OUTSIDE_VIA_HARDLINK)

    facts = {"junction": False, "symlink": False, "hardlink": False, "loop": False}

    facts["junction"] = _make_junction(skill / "references" / "junction", outside / "dirtree")
    # A junction pointing back into the skill folder: contained, so containment
    # alone would descend into it forever.
    facts["loop"] = _make_junction(skill / "references" / "loop", skill)

    if SYMLINKS_AVAILABLE:
        os.symlink(outside / "secret.txt", skill / "link-to-secret.txt")
        os.symlink(
            outside / "dirtree",
            skill / "references" / "shared",
            target_is_directory=True,
        )
        facts["symlink"] = True

    if HARDLINKS_AVAILABLE:
        try:
            os.link(outside / "hard-source.md", skill / "references" / "hardlinked.md")
            facts["hardlink"] = True
        except OSError:
            facts["hardlink"] = False
    if not facts["hardlink"]:
        # Keep the member set stable when hard links are unavailable.
        _write(skill / "references" / "hardlinked.md", "ordinary file\n")

    return skill, facts


class LeakTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="package-containment-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.skill, self.facts = build_leak_workspace(self.root)
        self.dist = self.root / "dist-out"

    def package(self, **kwargs):
        result = build_package(self.skill, self.dist, **kwargs)
        if result.errors:
            self.fail("packaging failed: " + " | ".join(result.errors))
        return result

    def report_text(self, result) -> str:
        buffer = io.StringIO()
        render_report(result, buffer)
        return buffer.getvalue()

    def member_names(self, result) -> set[str]:
        with zipfile.ZipFile(result.archive) as archive:
            return set(archive.namelist())

    def archive_bytes(self, result) -> bytes:
        """Raw archive bytes *and* every member inflated.

        Scanning the file alone is not enough: DEFLATE hides a short secret from
        a substring search, so a leak can sit in an archive whose raw bytes look
        clean. Both are concatenated here and searched together.
        """
        raw = result.archive.read_bytes()
        with zipfile.ZipFile(result.archive) as archive:
            inflated = b"".join(archive.read(name) for name in archive.namelist())
        return raw + inflated


class TestContainment(LeakTestCase):
    """R29a - resolve every path and confirm it stays inside the root (C13)."""

    def test_the_fixture_actually_contains_a_junction(self):
        if os.name != "nt":
            self.skipTest("NTFS junctions do not exist on this platform")
        self.assertTrue(self.facts["junction"], "mklink /J failed; the R29a case is untested")
        junction = self.skill / "references" / "junction"
        self.assertFalse(
            junction.is_symlink(),
            "is_symlink() must be False here - that False is the whole defect",
        )
        self.assertTrue(junction.is_dir())

    def test_junction_contents_are_not_in_the_archive(self):
        if not self.facts["junction"]:
            self.skipTest("no junction on this platform")
        names = self.member_names(self.package())
        self.assertFalse(
            [n for n in names if "junction" in n],
            "content behind the junction must not be enumerated",
        )

    def test_symlink_contents_are_not_in_the_archive(self):
        if not self.facts["symlink"]:
            self.skipTest("symlink creation is unavailable on this machine")
        names = self.member_names(self.package())
        self.assertNotIn("hostile-skill/link-to-secret.txt", names)
        self.assertFalse([n for n in names if "/shared/" in n])

    def test_no_out_of_tree_content_reaches_the_archive(self):
        result = self.package()
        self.assertNotIn(OUTSIDE_VIA_LINK.encode(), self.archive_bytes(result))

    def test_every_escaping_path_is_reported_with_where_it_points(self):
        result = self.package()
        report = self.report_text(result)
        skipped = {link.path: link for link in result.symlinks}

        if self.facts["junction"]:
            entry = skipped.get("hostile-skill/references/junction/")
            self.assertIsNotNone(entry, f"the junction must be reported; report was:\n{report}")
            self.assertEqual(entry.flavor, "directory junction")
            self.assertTrue(entry.escapes)
            self.assertIn("outside", entry.target)
            self.assertIn("hostile-skill/references/junction/", report)
            self.assertIn("directory junction", report)
        if self.facts["symlink"]:
            self.assertIn("hostile-skill/link-to-secret.txt", skipped)
            self.assertIn("hostile-skill/references/shared/", skipped)
        for entry in result.symlinks:
            self.assertIn("resolves outside the skill folder", entry.warning)
            self.assertIn(entry.warning, result.warnings)

    def test_a_link_that_loops_back_into_the_tree_terminates_and_is_named(self):
        if not self.facts["loop"]:
            self.skipTest("no junction on this platform")
        result = self.package()
        reasons = {e.path: e.reason for e in result.excluded}
        self.assertIn("hostile-skill/references/loop/", reasons)
        self.assertIn("packaged under its real name", reasons["hostile-skill/references/loop/"])
        self.assertFalse([n for n in self.member_names(result) if "/loop/" in n])

    def test_containment_helpers(self):
        root = _real(self.skill)
        self.assertIsNotNone(root)
        self.assertTrue(_is_within(root, root))
        self.assertTrue(_is_within(root, root / "references" / "notes.md"))
        self.assertFalse(_is_within(root, root.parent))
        self.assertFalse(_is_within(root, root.parent / "outside" / "secret.txt"))
        # A sibling whose name merely starts with the root's name is not inside it.
        self.assertFalse(_is_within(root, Path(str(root) + "-extra") / "x.md"))
        if os.name == "nt":
            self.assertTrue(_is_within(root, Path(str(root).upper()) / "notes.md"))


class TestSensitiveExclusions(LeakTestCase):
    """R29b - patterns and categories, never a filename prefix (C13)."""

    def test_no_secret_bytes_in_the_archive(self):
        blob = self.archive_bytes(self.package())
        for marker in SECRET_MARKERS:
            self.assertNotIn(marker, blob, f"{marker!r} reached the distributable")

    def test_every_credential_shaped_file_is_excluded(self):
        result = self.package()
        names = self.member_names(result)
        excluded = {e.path for e in result.excluded}
        for relative in SECRET_FILES:
            member = f"hostile-skill/{relative}"
            self.assertNotIn(member, names, f"{member} must not be packaged")
            self.assertIn(member, excluded, f"{member} must be named in the exclusion report")

    def test_every_exclusion_carries_a_reason_and_is_printed(self):
        result = self.package()
        report = self.report_text(result)
        self.assertTrue(result.excluded)
        for exclusion in result.excluded:
            self.assertTrue(exclusion.reason.strip(), f"{exclusion.path} has no reason")
            self.assertIn(exclusion.path, report)
            self.assertIn(exclusion.reason, report)

    def test_the_positive_inclusion_report_lists_every_member(self):
        result = self.package()
        report = self.report_text(result)
        self.assertEqual(self.member_names(result), EXPECTED_MEMBERS)
        for member in EXPECTED_MEMBERS:
            self.assertIn(member, report)

    def test_documentation_that_looks_credential_shaped_survives(self):
        names = self.member_names(self.package())
        for relative in LOOKALIKE_FILES:
            self.assertIn(f"hostile-skill/{relative}", names)

    def test_sensitive_reason_table(self):
        for name in (
            "production.env",
            "local.env",
            ".env",
            ".env.production",
            ".envrc",
            "token.txt",
            "tokens.json",
            "secrets.yaml",
            "secret.txt",
            "credentials.json",
            "aws_credentials",
            "api_key.json",
            "AwsAccessKey.txt",
            "client.secret",
            "deploy.pem",
            "server.key",
            "id_rsa",
            "id_ed25519.pub",
            "vault.kdbx",
            "MyApiToken.json",
        ):
            self.assertIsNotNone(_sensitive_reason(name), f"{name} should be refused")

        for name in (
            "SKILL.md",
            "tokenizer.md",
            "keyboard-shortcuts.md",
            "environments.md",
            "monkeypatch.py",
            "keeper.md",
            "notes.md",
            "environment-setup.md",
            "screenshot.png",
        ):
            self.assertIsNone(_sensitive_reason(name), f"{name} should be kept")


class TestHardLinkResidual(LeakTestCase):
    """The one leak containment cannot close, so it is reported instead.

    A hard link is a second name for the same file: there is no target to
    resolve and nothing distinguishes it from an ordinary file. This test pins
    the *documented* behaviour - packaged, and named in the report - so that a
    future change either keeps naming it or has to change this test on purpose.
    """

    def test_hardlinked_content_is_packaged_but_named_in_the_report(self):
        if not self.facts["hardlink"]:
            self.skipTest("hard links are unavailable on this machine")
        result = self.package()
        self.assertIn("hostile-skill/references/hardlinked.md", self.member_names(result))
        self.assertIn(OUTSIDE_VIA_HARDLINK.encode(), self.archive_bytes(result))
        self.assertIn("hostile-skill/references/hardlinked.md", result.hard_links)
        report = self.report_text(result)
        self.assertIn("more than one hard link", report)
        self.assertIn("hostile-skill/references/hardlinked.md", report)


class TestCommandLineLeakReport(LeakTestCase):
    def test_cli_json_names_the_escapes_and_the_exclusions(self):
        import json

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.package_skill",
                str(self.skill),
                str(self.dist),
                "--json",
            ],
            cwd=SKILL_ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        manifest = json.loads(proc.stdout)
        self.assertEqual({entry["path"] for entry in manifest["included"]}, EXPECTED_MEMBERS)
        excluded = {entry["path"] for entry in manifest["excluded"]}
        for relative in SECRET_FILES:
            self.assertIn(f"hostile-skill/{relative}", excluded)
        for entry in manifest["excluded"]:
            self.assertTrue(entry["reason"].strip())
        if self.facts["junction"]:
            skipped = {entry["path"]: entry for entry in manifest["symlinks_skipped"]}
            junction = skipped.get("hostile-skill/references/junction/")
            self.assertIsNotNone(junction)
            self.assertEqual(junction["flavor"], "directory junction")
            self.assertTrue(junction["resolves_outside_skill_folder"])


class TestLowercaseSkillMd(unittest.TestCase):
    """R32a - a lowercase skill.md validated clean and could not be packaged."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="package-lower-md-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.skill = self.root / "lower-md"
        self.skill.mkdir()
        (self.skill / "skill.md").write_text(
            "---\n"
            "name: lower-md\n"
            "description: A skill whose entry file is spelled skill.md, which the "
            "packager must refuse for a stated reason rather than for the wrong one.\n"
            "---\n\n# lower-md\n",
            encoding="utf-8",
        )
        self.dist = self.root / "dist"

    def test_entry_file_discovery_reports_the_on_disk_spelling(self):
        """The name comes from the directory, not from a case-insensitive probe."""
        found, name = package_module._entry_file(self.skill)
        self.assertIsNotNone(found)
        self.assertEqual(name, "skill.md")

    def test_refusal_names_the_spelling_rather_than_an_exclusion_rule(self):
        result = build_package(self.skill, self.dist)
        self.assertFalse(result.ok)
        combined = "\n".join(result.errors)
        # Either quick_validate's hard error or the packager's own archive-shape
        # check gets there first; both must name the spelling and the fix, and
        # neither may blame an exclusion rule that had nothing to do with it.
        self.assertIn(
            "skill.md", combined, f"the refusal must name the spelling it found:\n{combined}"
        )
        self.assertIn(
            "SKILL.md", combined, f"the refusal must name the spelling it wants:\n{combined}"
        )
        self.assertNotIn(
            "was excluded from the archive",
            combined,
            "R32a: the old message blamed an exclusion rule that had nothing to do with it",
        )
        self.assertFalse(list(self.dist.glob("*.zip")) if self.dist.exists() else [])

    def test_a_missing_entry_file_says_what_was_looked_for(self):
        empty = self.root / "no-skill-md"
        empty.mkdir()
        result = build_package(empty, self.dist)
        self.assertFalse(result.ok)
        combined = "\n".join(result.errors)
        self.assertIn("SKILL.md", combined)
        self.assertIn("skill.md", combined)


class TestSizeCeiling(unittest.TestCase):
    """R32b - an archive over the documented ceiling reported success."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="package-size-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.skill = self.root / "hostile-skill"
        shutil.copytree(FIXTURES / "hostile-skill", self.skill)
        self.dist = self.root / "dist"

    def _add_incompressible(self, size: int) -> None:
        (self.skill / "assets").mkdir(exist_ok=True)
        (self.skill / "assets" / "blob.bin").write_bytes(os.urandom(size))

    def test_over_the_ceiling_is_refused_for_an_upload_target(self):
        self._add_incompressible(1024 * 1024)
        original = package_module.API_SIZE_LIMIT_BYTES
        package_module.API_SIZE_LIMIT_BYTES = 4096
        try:
            result = build_package(self.skill, self.dist, target="claude-ai")
        finally:
            package_module.API_SIZE_LIMIT_BYTES = original

        self.assertFalse(result.ok, "an archive the upload surface rejects is not a success")
        combined = "\n".join(result.errors)
        self.assertIn("ceiling", combined)
        self.assertIn("largest member", combined)
        self.assertIn("--target claude-code", combined)
        self.assertFalse(list(self.dist.glob("*.zip")), "no artifact may be left behind")
        self.assertFalse(list(self.dist.glob("*.partial")))

    def test_over_the_ceiling_warns_and_drops_upload_surfaces_for_a_local_target(self):
        self._add_incompressible(1024 * 1024)
        original = package_module.API_SIZE_LIMIT_BYTES
        package_module.API_SIZE_LIMIT_BYTES = 4096
        try:
            result = build_package(self.skill, self.dist, target="claude-code")
            buffer = io.StringIO()
            render_report(result, buffer)
            report = buffer.getvalue()
        finally:
            package_module.API_SIZE_LIMIT_BYTES = original

        # claude-code installs by extracting into a skills directory, where no
        # ceiling is documented; refusing there would be a false rejection.
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(any("ceiling" in w for w in result.warnings))
        self.assertIn("not listed: over the upload ceiling", report)
        self.assertNotIn("POST /v1/skills with", report)

    def test_the_real_thirty_megabyte_ceiling(self):
        """The documented number itself, not a patched stand-in."""
        self._add_incompressible(API_SIZE_LIMIT_BYTES + 1024 * 1024)
        result = build_package(self.skill, self.dist, target="claude-ai")
        self.assertFalse(result.ok)
        self.assertIn("30.0 MB", "\n".join(result.errors))
        self.assertFalse(list(self.dist.glob("*.zip")))
        self.assertFalse(list(self.dist.glob("*.partial")))

    def test_under_the_ceiling_still_lists_every_install_surface(self):
        result = build_package(self.skill, self.dist, target="claude-ai")
        self.assertTrue(result.ok, result.errors)
        buffer = io.StringIO()
        render_report(result, buffer)
        report = buffer.getvalue()
        self.assertIn("POST /v1/skills with", report)
        self.assertNotIn("not listed", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
