#!/usr/bin/env python3
"""Skill packager - builds the distributable ``<name>.zip`` for a skill folder.

Run as a module from the skill root, because it imports the validator from the
``scripts`` package. Running it as a bare script path
(``python scripts/package_skill.py``) raises ModuleNotFoundError.

Usage:
    python -m scripts.package_skill <path/to/skill-folder> [output-directory]
                                    [--target claude-code|portable|claude-ai]
                                    [--dry-run] [--json]

Example:
    python -m scripts.package_skill ../my-skill
    python -m scripts.package_skill ../my-skill ./dist --target claude-ai

Why ``.zip`` and not ``.skill``
------------------------------
Nothing consumes a ``.skill`` file. Verified experimentally: byte-identical
archives load when named ``.zip`` and are dropped without any diagnostic when
named ``.skill`` (``claude --plugin-dir .../x.skill`` exits 0 and the command is
then "Unknown"). Every documented install surface accepts a directory, a git
repository, or a ``.zip``; none accepts a ``.skill``.

What this tool refuses to ship
------------------------------
The archive's whole purpose is to be handed to someone else, so two independent
rules decide what goes in, and every run prints a positive report of what was
included, what was excluded and why. That report is the backstop for whatever
the rules still miss, and it is what caught both of the leaks below.

**1. Containment, not link-detection.** Every candidate path is
resolved and has to stay inside the *resolved* skill folder. Testing whether a
path *is* a link was a proxy, and the proxy missed: ``Path.is_symlink()``
returns False for an NTFS directory junction, junctions need no elevation to
create (``mklink /J``), and ``os.walk(followlinks=False)`` walks straight
through one - so two files from outside the skill tree shipped silently
(research/_REMEDIATION.md R29a). A path that resolves outside the folder is
never opened, never descended into, and is named in the report. A link that
resolves *inside* the folder is skipped too, because its target already ships
under its real name; that also makes a junction loop impossible.

**2. Categories and patterns, never a filename prefix.** The
exclusion rule used to be ``name.startswith(".env")``, which matches a prefix
where the risk is a suffix and a category, so ``production.env``,
``config/local.env``, ``token.txt`` and ``secrets.yaml`` all shipped (R29b).
Exclusions now match glob patterns over the whole basename (``*.env`` as much as
``.env.*``) and credential-shaped *words* in the name, split on separators and
camelCase so ``secrets.yaml`` is caught while ``tokenizer.md`` is not.

A hard link is the one leak containment cannot close: it has no target to
resolve and is indistinguishable from an ordinary file. Files carrying more than
one link are named in the report instead.
"""

from __future__ import annotations

import argparse
import fnmatch
import inspect
import json
import os
import re
import shutil
import stat
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by the missing-dependency test
    # Match quick_validate's behaviour rather than tracebacking. Two entry points
    # in one bundle giving different treatment to the same missing dependency is
    # the disagreement class this codebase exists to close -- and a traceback is
    # a poor first experience for someone who has just installed the skill.
    print(
        "This script needs PyYAML, which is not installed.\n"
        "Install it with:  pip install -r requirements.txt\n"
        "(or:  pip install pyyaml)",
        file=sys.stderr,
    )
    raise SystemExit(1)

from scripts.quick_validate import validate_skill
from scripts.utils import SKILL_MD_NAMES, configure_console, find_skill_md

# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

VALIDATION_TARGETS = ("claude-code", "portable", "claude-ai")
DEFAULT_TARGET = "claude-code"

# POST /v1/skills documents a 30 MB ceiling on the whole upload. claude.ai has
# an undocumented limit; this is the only number that is stated anywhere.
API_SIZE_LIMIT_BYTES = 30 * 1024 * 1024

# Targets whose install surface is an *upload*, and therefore the targets where
# the documented ceiling is a hard limit rather than an advisory. Packaging for
# claude-code installs by extracting into a skills directory, which has no
# documented ceiling, so refusing there would be a false rejection - the exact
# failure class this rewrite exists to close.
UPLOAD_TARGETS = frozenset({"claude-ai"})

# A second name policy lives in run_eval.py (SCAFFOLD_EXCLUDED_NAMES), deciding
# what a probe's working directory holds rather than what a stranger receives
# from a published archive. It shares roughly twenty names with the tables below
# and diverges deliberately everywhere else: it matches case-folded, it drops no
# dot-entry it has not named, and it adopts none of the word or compound rules,
# because a scaffold entry a query names and cannot find is scored as a failed
# trigger rather than an error. Edit these tables for what an archive should
# carry; edit that one for what a probe should see. Neither is the other's
# source of truth, and widening this one does not widen that one.
#
# Dot-entries are excluded as a class. This is the one carve-out: a skills-dir
# plugin is a documented distributable shape and carries its manifest here.
DOT_ALLOWLIST = {".claude-plugin"}

# Reasons for the dot-entries an author is most likely to have lying around.
# Anything else starting with "." still goes, it just gets the generic reason.
DOT_REASONS = {
    ".git": "version control metadata (may carry credentialed remote URLs)",
    ".gitignore": "version control metadata",
    ".gitattributes": "version control metadata",
    ".gitmodules": "version control metadata",
    ".hg": "version control metadata",
    ".svn": "version control metadata",
    ".venv": "virtual environment",
    ".claude": "local Claude Code configuration",
    ".vscode": "editor configuration",
    ".idea": "editor configuration",
    ".DS_Store": "OS metadata",
    ".pytest_cache": "test cache",
    ".mypy_cache": "type-checker cache",
    ".ruff_cache": "linter cache",
    ".tox": "test environment",
    ".ipynb_checkpoints": "notebook checkpoints",
    ".ssh": "SSH key material - may contain secrets",
    ".gnupg": "GnuPG key material - may contain secrets",
    ".aws": "cloud credentials - may contain secrets",
    ".azure": "cloud credentials - may contain secrets",
    ".gcloud": "cloud credentials - may contain secrets",
    ".kube": "cluster credentials - may contain secrets",
    ".docker": "registry credentials - may contain secrets",
    ".npmrc": "package registry token - may contain secrets",
    ".pypirc": "package registry token - may contain secrets",
    # .netrc, .pgpass, .htpasswd and .git-credentials are deliberately absent:
    # they are caught by SENSITIVE_WORDS below, and two tables claiming the same
    # name is how a rule ends up edited in the one that never runs.
}

NAMED_DIR_EXCLUSIONS = {
    "__pycache__": "Python bytecode cache",
    "node_modules": "installed dependencies",
    "venv": "virtual environment",
    "env": "virtual environment",
    "site-packages": "installed dependencies",
}

# Excluded only when they sit directly inside the skill folder, so a skill that
# legitimately ships reference material under assets/nested/evals/ keeps it.
ROOT_EXCLUDE_DIRS = {
    "evals": "author-side eval inputs (root only)",
    "tests": "author-side tests (root only)",
}

NAMED_FILE_EXCLUSIONS = {
    "Thumbs.db": "OS metadata",
    "desktop.ini": "OS metadata",
    "id_rsa": "private key",
    "id_dsa": "private key",
    "id_ecdsa": "private key",
    "id_ed25519": "private key",
    "npm-debug.log": "build log",
}

# --------------------------------------------------------------------------
# Sensitive-content categories
#
# These are matched against the *whole basename*, case-insensitively, for both
# files and directories, dot-prefixed or not, and they are consulted before
# every other rule so the stated reason is the specific one. The rule they
# replace was ``name.startswith(".env")``: it matched a prefix where the risk is
# a suffix and a category, so it shipped production.env, config/local.env,
# token.txt and secrets.yaml (research/V2-verification.md 2.1).
# --------------------------------------------------------------------------

_ENV_REASON = "environment file - may contain secrets"

SENSITIVE_GLOBS = (
    # dotenv, in every spelling anyone actually uses
    (".env", _ENV_REASON),
    (".env.*", _ENV_REASON),
    ("*.env", _ENV_REASON),
    ("*.env.*", _ENV_REASON),
    (".envrc", "direnv environment file - may contain secrets"),
    # key material and key stores, by extension
    ("*.pem", "private key or certificate"),
    ("*.key", "private key"),
    ("*.pfx", "key store"),
    ("*.p12", "key store"),
    ("*.p8", "private key"),
    ("*.keystore", "key store"),
    ("*.jks", "key store"),
    ("*.kdbx", "password database"),
    ("*.ppk", "private key"),
    ("*.asc", "PGP key or signature material"),
    ("*.gpg", "PGP key material"),
    ("id_rsa*", "SSH private key"),
    ("id_dsa*", "SSH private key"),
    ("id_ecdsa*", "SSH private key"),
    ("id_ed25519*", "SSH private key"),
    ("known_hosts", "SSH host inventory"),
    ("authorized_keys", "SSH key material"),
    # named credential stores
    ("*.jwt", "bearer token - may contain secrets"),
    ("service-account*.json", "service account key - may contain secrets"),
    ("*serviceaccount*.json", "service account key - may contain secrets"),
)

# Words that make a name credential-shaped. Matched at word boundaries against
# the basename split on separators *and* camelCase, so ``secrets.yaml``,
# ``token.txt``, ``aws_credentials`` and ``MyApiToken.json`` are caught while
# ``tokenizer.md`` and ``keyboard-shortcuts.md`` are not. A substring rule would
# have taken those two with it, and silently dropping documentation is the same
# class of defect as silently shipping a secret.
SENSITIVE_WORDS = {
    "secret",
    "secrets",
    "credential",
    "credentials",
    "creds",
    "token",
    "tokens",
    "password",
    "passwords",
    "passwd",
    "htpasswd",
    "netrc",
    "pgpass",
    "apikey",
    "apikeys",
    "keypair",
    "keystore",
    "keyring",
    "authinfo",
    "privatekey",
}

# Compound markers checked against the basename with every separator removed,
# so ``api_key.json``, ``AWS-Access-Key.txt`` and ``client.secret`` are caught
# even though no single word matches.
SENSITIVE_COMPOUNDS = (
    "apikey",
    "apitoken",
    "authtoken",
    "accesskey",
    "accesstoken",
    "refreshtoken",
    "secretkey",
    "privatekey",
    "clientsecret",
    "sessiontoken",
)

_WORD_BOUNDARY = re.compile(
    r"[^0-9A-Za-z]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])"
)

# Matched case-insensitively against the basename. Files only.
FILE_GLOB_EXCLUSIONS = (
    ("*.pyc", "Python bytecode"),
    ("*.pyo", "Python bytecode"),
    ("*.pyd", "compiled Python extension"),
    ("*.skill", "previous build output"),
    ("*.zip", "archive / previous build output"),
    ("*.swp", "editor swap file"),
    ("*~", "editor backup file"),
)

# Member names that a Windows extraction cannot round-trip. A skill authored on
# a case-sensitive filesystem can contain all of these; the recipient sees
# silently renamed files, silently clobbered files, or a half-finished install.
WINDOWS_RESERVED_BASENAMES = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
WINDOWS_ILLEGAL_CHARS = set('<>:"|?*\\') | {chr(c) for c in range(32)}

# Anything here, and anything under scripts/, is marked executable in the
# archive. Windows carries no execute bit, so without this a skill packaged on
# Windows arrives on Linux with non-executable scripts.
EXECUTABLE_SUFFIXES = {".sh", ".bash", ".zsh", ".ksh", ".command"}


# --------------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------------


@dataclass
class Member:
    """One file that will be written into the archive."""

    source: Path
    arcname: str
    size: int
    mode: int
    date_time: tuple


@dataclass
class Exclusion:
    """One path that was deliberately left out, and why.

    ``files``/``size`` are ``None`` when the tree was never walked - a directory
    that reparses is not descended into even to count bytes, and reporting 0 for
    it would be a default that renders as a measurement.
    """

    path: str
    reason: str
    files: int | None = 1
    size: int | None = 0


@dataclass
class SkippedLink:
    """A path that was not packaged because of where it resolves to.

    ``flavor`` records *how* it reparsed (symlink, directory junction, other
    reparse point) purely so the report can name it; the packaging decision was
    made by containment, not by the flavor.
    """

    path: str
    target: str
    kind: str
    flavor: str = "symlink"
    escapes: bool = True
    warning: str = ""


@dataclass
class PackageResult:
    """The full manifest of one packaging run.

    ``symlinks`` keeps its original name for callers that already read it, but
    its membership rule is now containment: every entry is a path that resolved
    *outside* the skill folder, whatever kind of link took it there. ``flavor``
    on each entry says which kind. ``hard_links`` lists packaged files carrying
    more than one link - the case containment cannot decide.
    """

    ok: bool = False
    archive: Path | None = None
    skill_name: str | None = None
    skill_path: Path | None = None
    target: str = DEFAULT_TARGET
    dry_run: bool = False
    included: list[Member] = field(default_factory=list)
    excluded: list[Exclusion] = field(default_factory=list)
    symlinks: list[SkippedLink] = field(default_factory=list)
    empty_dirs: list[str] = field(default_factory=list)
    hard_links: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    uncompressed_bytes: int = 0
    archive_bytes: int | None = None

    def fail(self, message: str) -> "PackageResult":
        self.errors.append(message)
        self.ok = False
        return self


# --------------------------------------------------------------------------
# Validation (quick_validate is the authority; this only adapts to its shape)
# --------------------------------------------------------------------------


def _finding_lines(payload) -> list[str]:
    """Flatten whatever a validator hands back into printable lines."""
    if payload is None:
        return []
    if isinstance(payload, str):
        return [payload] if payload.strip() else []
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("text") or payload.get("detail")
        return [str(message)] if message else [str(payload)]
    if isinstance(payload, (list, tuple, set)):
        lines: list[str] = []
        for item in payload:
            lines.extend(_finding_lines(item))
        return lines
    message = getattr(payload, "message", None)
    return [str(message) if message else str(payload)]


def _normalize_validation(raw) -> tuple[bool, list[str], list[str]]:
    """Return (ok, errors, warnings) from quick_validate's return value.

    quick_validate is owned elsewhere and only its *CLI* surface is fixed, so
    accept the shapes that surface admits. An unrecognized shape raises rather
    than defaulting to "valid" - a packager that guesses "ok" on an unreadable
    verdict is exactly the silent-pass this rewrite exists to remove.
    """
    if isinstance(raw, bool):
        return raw, [], []

    if isinstance(raw, tuple) and len(raw) == 2 and isinstance(raw[0], bool):
        ok, payload = raw
        lines = _finding_lines(payload)
        if not ok:
            return False, lines, []
        # ok=True with a one-line string is a status line ("Skill is valid!"),
        # not a finding. ok=True with more than one line means the validator
        # passed but had something to say - keep it, minus its summary header,
        # because a claude.ai description-cap warning matters to whoever is
        # about to upload this zip.
        if isinstance(payload, str):
            parts = [part for part in payload.split("\n") if part.strip()]
            return True, [], parts[1:]
        return True, [], lines

    if isinstance(raw, dict):
        errors = _finding_lines(raw.get("errors"))
        warnings = _finding_lines(raw.get("warnings"))
        if not errors and not warnings:
            findings = _finding_lines(raw.get("findings") or raw.get("messages"))
            errors = findings
        for key in ("ok", "valid", "is_valid", "passed"):
            if key in raw:
                return bool(raw[key]), errors, warnings
        return not errors, errors, warnings

    for key in ("ok", "valid", "is_valid"):
        if hasattr(raw, key):
            errors = _finding_lines(getattr(raw, "errors", None))
            warnings = _finding_lines(getattr(raw, "warnings", None))
            if not errors:
                errors = _finding_lines(getattr(raw, "findings", None))
            return bool(getattr(raw, key)), errors, warnings

    raise RuntimeError(
        "scripts.quick_validate.validate_skill returned an unrecognized result "
        f"of type {type(raw).__name__}: {raw!r}. package_skill cannot tell "
        "whether the skill is valid, so it refuses to package it."
    )


def _run_validation(skill_path: Path, target: str) -> tuple[bool, list[str], list[str]]:
    kwargs = {}
    extra_warnings: list[str] = []
    try:
        parameters = inspect.signature(validate_skill).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtins/C callables
        parameters = {}
    accepts_target = "target" in parameters or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()
    )
    if accepts_target:
        kwargs["target"] = target
    elif target != DEFAULT_TARGET:
        extra_warnings.append(
            f"quick_validate in this tree is not target-aware; --target {target} "
            "was not applied to validation."
        )

    ok, errors, warnings = _normalize_validation(validate_skill(skill_path, **kwargs))
    return ok, errors, warnings + extra_warnings


# --------------------------------------------------------------------------
# Frontmatter (only the archive-shape rule; validity is quick_validate's job)
# --------------------------------------------------------------------------


def _entry_file(skill_path: Path) -> tuple[Path | None, str | None]:
    """(path, on-disk basename) of the skill's entry file, or (None, None).

    Discovery goes through ``scripts.utils.find_skill_md``, the same function
    ``quick_validate`` uses, so the two tools cannot disagree about whether a
    folder is a skill (research/V2-verification.md PK-1: a lowercase
    ``skill.md`` validated clean and then failed here with a message about
    SKILL.md being "excluded from the archive").

    The *basename* has to come back from the directory listing rather than from
    the returned path: on a case-insensitive filesystem ``skill_path/"SKILL.md"``
    happily opens a file named ``skill.md``, while the archive member name comes
    from the directory listing and is case-sensitive on every platform.
    """
    found = find_skill_md(skill_path)
    if found is None:
        return None, None
    try:
        on_disk = {entry.name for entry in os.scandir(skill_path) if entry.is_file()}
    except OSError:
        return found, found.name
    for name in SKILL_MD_NAMES:  # SKILL.md wins when a case-sensitive FS has both
        if name in on_disk:
            return skill_path / name, name
    return found, found.name


def _read_frontmatter_name(skill_md: Path) -> tuple[str | None, str | None]:
    """Return (name, error). Used only to enforce directory name == name.

    The archive's top-level directory name is the one packaging rule that is
    about the *artifact* rather than the source, so the packager has to know
    the declared name even though quick_validate also checks it.
    """
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, UnicodeError) as exc:
        # UnicodeDecodeError is a ValueError, not an OSError - it is not caught
        # by an (OSError,) handler and has to be named explicitly.
        return None, f"could not read {skill_md}: {exc}"

    text = text.lstrip("\ufeff")  # Windows editors emit a BOM by default.
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, "SKILL.md has no YAML frontmatter (no opening '---')"

    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() in ("---", "..."):
            end = index
            break
    if end is None:
        return None, "SKILL.md frontmatter is not closed (no trailing '---')"

    try:
        frontmatter = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        return None, f"could not parse SKILL.md frontmatter: {exc}"

    if not isinstance(frontmatter, dict):
        return None, "SKILL.md frontmatter is not a YAML mapping"

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, "SKILL.md frontmatter has no usable 'name'"
    return name.strip(), None


# --------------------------------------------------------------------------
# Collection
# --------------------------------------------------------------------------


def _name_words(name: str) -> set[str]:
    """The basename split into lowercase words on separators and camelCase.

    ``AWS_Secret-Key.json`` -> {'aws', 'secret', 'key', 'json'}. The extension is
    a word like any other, which is how ``secrets.yaml`` and ``token.txt`` are
    caught without a substring rule that would also take ``tokenizer.md``.
    """
    return {part.lower() for part in _WORD_BOUNDARY.split(name) if part}


def _sensitive_reason(name: str) -> str | None:
    """Why this name is credential-shaped, or None.

    Patterns and categories only - never a filename prefix.
    """
    lowered = name.lower()
    for pattern, reason in SENSITIVE_GLOBS:
        if fnmatch.fnmatch(lowered, pattern):
            return reason

    words = _name_words(name)
    hit = sorted(words & SENSITIVE_WORDS)
    if hit:
        return f"credential-shaped name (matched '{hit[0]}') - may contain secrets"

    squashed = re.sub(r"[^a-z0-9]+", "", lowered)
    for compound in SENSITIVE_COMPOUNDS:
        if compound in squashed:
            return f"credential-shaped name (matched '{compound}') - may contain secrets"
    return None


def _exclusion_reason(name: str, *, is_dir: bool, depth: int) -> str | None:
    """Why this entry must not be distributed, or None to include it.

    ``depth`` is 0 for entries sitting directly inside the skill folder.
    """
    # Category rules run first, and run for every entry - directory or file,
    # dot-prefixed or not, inside the .claude-plugin carve-out or outside it -
    # so the reason given is the specific one and no allowlisted subtree can
    # smuggle a credential through.
    sensitive = _sensitive_reason(name)
    if sensitive:
        return sensitive
    if name in DOT_ALLOWLIST:
        return None
    if name.startswith("."):
        return DOT_REASONS.get(name, "hidden dot-entry")
    if is_dir:
        if depth == 0 and name in ROOT_EXCLUDE_DIRS:
            return ROOT_EXCLUDE_DIRS[name]
        if name in NAMED_DIR_EXCLUSIONS:
            return NAMED_DIR_EXCLUSIONS[name]
        if name.endswith(".egg-info"):
            return "Python build metadata"
        return None
    if name in NAMED_FILE_EXCLUSIONS:
        return NAMED_FILE_EXCLUSIONS[name]
    lowered = name.lower()
    for pattern, reason in FILE_GLOB_EXCLUSIONS:
        if fnmatch.fnmatch(lowered, pattern):
            return reason
    return None


# --------------------------------------------------------------------------
# Containment
# --------------------------------------------------------------------------


def _real(path) -> Path | None:
    """The fully resolved path, or None if it cannot be resolved.

    ``resolve()`` follows symlinks, NTFS junctions, mount points and anything
    else that reparses, which is exactly why containment is decided against its
    answer rather than against ``is_symlink()`` - the latter returns False for a
    junction and let two out-of-tree files into a distributable.
    """
    try:
        return Path(path).resolve()
    except (OSError, ValueError, RuntimeError):
        return None


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def _is_within(root_real: Path, candidate_real: Path) -> bool:
    """True when *candidate_real* is the root itself or lives under it.

    Compared through ``normcase`` rather than ``Path.is_relative_to`` so a
    case-insensitive filesystem cannot make an in-tree path look like an escape.
    """
    root_key = os.path.normcase(str(root_real))
    candidate_key = os.path.normcase(str(candidate_real))
    if candidate_key == root_key:
        return True
    prefix = root_key if root_key.endswith(os.sep) else root_key + os.sep
    return candidate_key.startswith(prefix)


def _link_flavor(path: Path) -> str:
    """A human label for *how* a path reparses. Reporting only, never a gate."""
    try:
        info = os.stat(path, follow_symlinks=False)
    except OSError:
        return "path"
    if stat.S_ISLNK(info.st_mode):
        return "symlink"
    tag = getattr(info, "st_reparse_tag", 0)
    if tag == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003):
        return "directory junction"
    if tag == getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C):
        return "symlink"
    if tag:
        return f"reparse point (tag {tag:#x})"
    return "path"


def _tree_weight(path: Path, root_real: Path | None = None) -> tuple[int, int]:
    """(file count, total bytes) under an excluded directory.

    Never leaves the skill folder, even to count bytes: a directory that
    reparses outside it is pruned here too, so an excluded ``.git`` containing a
    junction cannot make this walk wander off the tree (or loop).
    """
    files = 0
    total = 0
    for dirpath, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
        if root_real is not None:
            kept = []
            for dirname in dirnames:
                child = Path(dirpath) / dirname
                resolved = _real(child)
                if resolved is None or not _is_within(root_real, resolved):
                    continue
                if not _same_path(resolved, child):
                    continue
                kept.append(dirname)
            dirnames[:] = kept
        for filename in filenames:
            candidate = os.path.join(dirpath, filename)
            files += 1
            try:
                if not os.path.islink(candidate):
                    total += os.path.getsize(candidate)
            except OSError:
                pass
    return files, total


def _link_target(path: Path, resolved: Path | None = None) -> str:
    """Where a path points, in a form a human can recognize."""
    try:
        target = os.readlink(path)
    except (OSError, ValueError):
        # Not a link at all, or a reparse tag os.readlink does not understand.
        # The resolved path is the honest answer in both cases.
        return str(resolved) if resolved is not None else "<unreadable>"
    # Windows hands back the extended-length form for absolute targets; the
    # point of printing this is that a human can recognize where it points.
    if target.startswith("\\\\?\\UNC\\"):
        return "\\\\" + target[8:]
    if target.startswith("\\\\?\\"):
        return target[4:]
    return target


def _zip_date_time(mtime: float) -> tuple:
    parsed = time.localtime(mtime)
    if parsed.tm_year < 1980:
        return (1980, 1, 1, 0, 0, 0)
    return tuple(parsed[:6])


def _member_mode(arcname: str, source: Path) -> int:
    executable = False
    if os.name != "nt":
        try:
            executable = bool(source.stat().st_mode & stat.S_IXUSR)
        except OSError:
            executable = False
    parts = PurePosixPath(arcname).parts
    if len(parts) > 2 and parts[1] == "scripts":
        executable = True
    if PurePosixPath(arcname).suffix.lower() in EXECUTABLE_SUFFIXES:
        executable = True
    return 0o755 if executable else 0o644


def _skipped_link(display: str, child: Path, resolved: Path | None, kind: str) -> SkippedLink:
    """Build the report entry for a path that resolves out of the skill folder."""
    flavor = _link_flavor(child)
    target = _link_target(child, resolved)
    warning = (
        f"{flavor} not followed: {display} -> {target} ({kind}); it resolves "
        "outside the skill folder, so its contents are NOT in the archive"
    )
    return SkippedLink(
        path=display, target=target, kind=kind, flavor=flavor, escapes=True, warning=warning
    )


def collect(
    skill_path: Path, root_name: str, denied_paths: set[Path]
) -> tuple[list[Member], list[Exclusion], list[SkippedLink], list[str], list[str]]:
    """Walk the skill tree once, deciding every entry's fate up front.

    Everything is enumerated before a single byte is written, which is what
    makes it impossible for the archive being produced to end up inside itself.

    Two containment rules apply to every entry, before any name-based rule:

    * a path whose resolved form is not inside the resolved skill folder is
      skipped, reported and warned about - whether it got there by symlink,
      junction, mount point or anything else that reparses;
    * a path that resolves *inside* the folder but is not itself that resolved
      path is a link into the tree. Its target already ships under its real
      name, so following it would only duplicate bytes - and refusing to follow
      it is what makes a junction loop (``refs/self -> ..``) impossible.

    Returns (members, exclusions, skipped_links, empty_dirs, multi_link_files).
    """
    members: list[Member] = []
    exclusions: list[Exclusion] = []
    skipped: list[SkippedLink] = []
    empty_dirs: list[str] = []
    multi_link: list[str] = []

    root_real = _real(skill_path)
    if root_real is None:
        raise OSError(f"could not resolve the skill folder: {skill_path}")

    for dirpath, dirnames, filenames in os.walk(skill_path, topdown=True, followlinks=False):
        here = Path(dirpath)
        rel_dir = here.relative_to(skill_path)
        depth = len(rel_dir.parts)
        entries_on_disk = len(dirnames) + len(filenames)

        kept_dirs = []
        for dirname in sorted(dirnames):
            child = here / dirname
            display = f"{root_name}/{(rel_dir / dirname).as_posix()}/"
            resolved_dir = _real(child)
            if resolved_dir is None or not _is_within(root_real, resolved_dir):
                skipped.append(_skipped_link(display, child, resolved_dir, "directory"))
                continue
            # Compared against the *real* path this entry would have if it were
            # an ordinary directory, so a skill folder that was itself reached
            # through a link does not make every child look like one.
            if not _same_path(resolved_dir, root_real / rel_dir / dirname):
                exclusions.append(
                    Exclusion(
                        display,
                        f"{_link_flavor(child)} into the skill folder (resolves to "
                        f"{resolved_dir}); the target is packaged under its real name",
                        files=None,
                        size=None,
                    )
                )
                continue
            if resolved_dir in denied_paths:
                files, size = _tree_weight(child, root_real)
                exclusions.append(
                    Exclusion(display, "output directory of this packaging run", files=files, size=size)
                )
                continue
            reason = _exclusion_reason(dirname, is_dir=True, depth=depth)
            if reason:
                files, size = _tree_weight(child, root_real)
                exclusions.append(Exclusion(display, reason, files=files, size=size))
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            child = here / filename
            rel = (rel_dir / filename).as_posix()
            display = f"{root_name}/{rel}"
            resolved = _real(child)
            if resolved is None or not _is_within(root_real, resolved):
                skipped.append(_skipped_link(display, child, resolved, "file"))
                continue
            if not _same_path(resolved, root_real / rel_dir / filename):
                exclusions.append(
                    Exclusion(
                        display,
                        f"{_link_flavor(child)} into the skill folder (resolves to "
                        f"{resolved}); the target is packaged under its real name",
                        files=None,
                        size=None,
                    )
                )
                continue
            if resolved in denied_paths:
                exclusions.append(Exclusion(display, "output of this packaging run", size=0))
                continue
            reason = _exclusion_reason(filename, is_dir=False, depth=depth)
            if reason:
                try:
                    size = child.stat().st_size
                except OSError:
                    size = 0
                exclusions.append(Exclusion(display, reason, size=size))
                continue
            try:
                info = child.stat()
            except OSError as exc:
                exclusions.append(Exclusion(display, f"unreadable: {exc}", size=0))
                continue
            # A hard link has no target to resolve, so containment cannot see
            # that its content came from outside the folder. Report it.
            if getattr(info, "st_nlink", 1) > 1:
                multi_link.append(display)
            arcname = f"{root_name}/{rel}"
            members.append(
                Member(
                    source=child,
                    arcname=arcname,
                    size=info.st_size,
                    mode=_member_mode(arcname, child),
                    date_time=_zip_date_time(info.st_mtime),
                )
            )

        # A directory that is genuinely empty on disk would otherwise vanish
        # from the archive; a directory whose contents were all excluded is
        # meant to vanish, so only the former gets an explicit entry.
        if depth and entries_on_disk == 0:
            empty_dirs.append(f"{root_name}/{rel_dir.as_posix()}")

    members.sort(key=lambda m: m.arcname)
    exclusions.sort(key=lambda e: e.path)
    skipped.sort(key=lambda s: s.path)
    return members, exclusions, skipped, sorted(empty_dirs), sorted(multi_link)


# --------------------------------------------------------------------------
# Member-name safety
# --------------------------------------------------------------------------


def check_member_names(names: list[str]) -> list[str]:
    """Names that no recipient can extract safely. Empty list means clean."""
    problems: list[str] = []
    seen: dict[str, str] = {}

    for name in names:
        parts = PurePosixPath(name).parts
        for part in parts:
            if part in ("..", "."):
                problems.append(f"{name}: path component '{part}' is not allowed")
                continue
            bad = sorted(set(part) & WINDOWS_ILLEGAL_CHARS)
            if bad:
                shown = ", ".join(repr(c) for c in bad)
                problems.append(
                    f"{name}: component '{part}' contains {shown}, which Windows "
                    "silently rewrites on extraction"
                )
            if part != part.rstrip(". "):
                problems.append(
                    f"{name}: component '{part}' ends with a dot or space, which "
                    "Windows cannot create"
                )
            stem = part.split(".", 1)[0].upper()
            if stem in WINDOWS_RESERVED_BASENAMES:
                problems.append(
                    f"{name}: component '{part}' is the reserved DOS device name "
                    f"'{stem}'; extraction on Windows aborts part-way"
                )
        # Case collisions are checked at every level, not just on the full
        # name: two directories differing only in case merge into one on
        # Windows and macOS, which loses files just as quietly.
        prefix = ""
        for part in parts:
            prefix = f"{prefix}/{part}" if prefix else part
            lowered = prefix.lower()
            existing = seen.get(lowered)
            if existing is None:
                seen[lowered] = prefix
            elif existing != prefix:
                problems.append(
                    f"{prefix}: collides with '{existing}' on case-insensitive "
                    "filesystems; one would silently overwrite the other"
                )

    return sorted(set(problems))


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------


class ArchiveTooLarge(Exception):
    """The finished archive exceeds a ceiling the target's install surface enforces."""

    def __init__(self, size: int, limit: int) -> None:
        super().__init__(f"archive is {size} bytes, over the {limit} byte ceiling")
        self.size = size
        self.limit = limit


def _write_archive(
    destination: Path,
    members: list[Member],
    empty_dirs: list[str],
    *,
    reject_over: int | None = None,
) -> None:
    """Write to a sibling temp file, verify, then move into place.

    ``reject_over`` is checked on the *finished* archive, before it is moved
    into place: a size ceiling can only be measured after compression, and an
    archive the install surface will reject should not be left on disk looking
    like a successful build (research/V2-verification.md PK-2).
    """
    temp = destination.with_name(destination.name + ".partial")
    try:
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as archive:
            for directory in empty_dirs:
                info = zipfile.ZipInfo(directory + "/", date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (0o755 << 16) | 0x10
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, b"")
            for member in members:
                info = zipfile.ZipInfo(member.arcname, date_time=member.date_time)
                # create_system 3 (Unix) is what makes external_attr's mode bits
                # mean anything to Info-ZIP on the recipient's machine.
                info.create_system = 3
                info.external_attr = member.mode << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                with open(member.source, "rb") as source, archive.open(info, "w") as target:
                    shutil.copyfileobj(source, target)

        with zipfile.ZipFile(temp) as verify:
            broken = verify.testzip()
            if broken is not None:
                raise OSError(f"archive failed its own CRC check at member {broken}")
            written = set(verify.namelist())
        expected = {m.arcname for m in members} | {d + "/" for d in empty_dirs}
        if written != expected:
            missing = sorted(expected - written)
            extra = sorted(written - expected)
            raise OSError(f"archive contents differ from plan (missing={missing}, extra={extra})")

        if reject_over is not None:
            size = temp.stat().st_size
            if size > reject_over:
                raise ArchiveTooLarge(size, reject_over)

        os.replace(temp, destination)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def build_package(
    skill_path,
    output_dir=None,
    *,
    target: str = DEFAULT_TARGET,
    dry_run: bool = False,
) -> PackageResult:
    """Plan and (unless dry_run) write the distributable archive.

    Returns a PackageResult carrying the full included/excluded manifest. Does
    not print anything; see render_report.
    """
    result = PackageResult(target=target, dry_run=dry_run)

    if target not in VALIDATION_TARGETS:
        return result.fail(
            f"Unknown --target {target!r}. Choose one of: {', '.join(VALIDATION_TARGETS)}"
        )

    try:
        skill_path = Path(skill_path).resolve()
    except OSError as exc:
        return result.fail(f"Could not resolve skill folder: {exc}")
    result.skill_path = skill_path

    if not skill_path.exists():
        return result.fail(f"Skill folder not found: {skill_path}")
    if not skill_path.is_dir():
        return result.fail(f"Path is not a directory: {skill_path}")
    if not skill_path.name:
        return result.fail(f"Skill folder has no name: {skill_path}")

    skill_md, entry_name = _entry_file(skill_path)
    if skill_md is None:
        return result.fail(
            f"SKILL.md not found in {skill_path} (looked for "
            f"{' and '.join(SKILL_MD_NAMES)})"
        )

    # 1. Validity. quick_validate is the authority.
    try:
        valid, errors, warnings = _run_validation(skill_path, target)
    except (OSError, UnicodeDecodeError, UnicodeError, RuntimeError) as exc:
        return result.fail(f"Validation could not complete: {exc}")
    result.warnings.extend(warnings)
    if not valid:
        result.errors.extend(errors or [f"quick_validate rejected the skill (target: {target})"])
        result.errors.append("Fix the validation errors before packaging.")
        return result

    # 2. Archive shape. These are the packager's own rules, enforced here rather
    #    than trusted to the validator, because they are about the *artifact*.
    #
    #    2a. The entry file's spelling. Zip members are case-sensitive on every
    #        platform, so a member named skill.md is simply not found by an
    #        install surface looking for SKILL.md. The message names the cause;
    #        the old one blamed an exclusion rule that had nothing to do with it.
    if entry_name != "SKILL.md":
        return result.fail(
            f"The skill's entry file is spelled '{entry_name}'. The archive must "
            "carry it as 'SKILL.md' - zip members are case-sensitive on every "
            "platform, so a lowercase member is not found by an install surface "
            f"that looks for SKILL.md. Rename {skill_path / entry_name} to "
            "SKILL.md and package again."
        )

    #    2b. The top-level directory name must equal the declared name, or the
    #        Skills API rejects the upload and Claude Code answers to a slash
    #        command the author never chose.
    declared_name, frontmatter_error = _read_frontmatter_name(skill_md)
    if frontmatter_error:
        return result.fail(frontmatter_error)
    result.skill_name = declared_name
    if declared_name != skill_path.name:
        return result.fail(
            f"Frontmatter name '{declared_name}' does not match the folder name "
            f"'{skill_path.name}'. The archive's single top-level directory is the "
            "folder name, and every install surface requires the two to agree - "
            f"rename the folder to '{declared_name}' (or change the frontmatter "
            "name to match the folder)."
        )

    # 3. Output location, decided before the walk so the archive can never
    #    enumerate itself.
    if output_dir:
        output_path = Path(output_dir).resolve()
        if output_path.exists() and not output_path.is_dir():
            return result.fail(f"Output path is not a directory: {output_path}")
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return result.fail(f"Could not create output directory {output_path}: {exc}")
    else:
        output_path = Path.cwd()

    destination = output_path / f"{declared_name}.zip"
    result.archive = destination
    # Anything the packaging run itself owns is denied to the walk, so an output
    # directory nested inside the skill can never be enumerated into the archive
    # it is about to receive.
    denied = set()
    for candidate in (
        destination,
        destination.with_name(destination.name + ".partial"),
        output_path,
    ):
        try:
            denied.add(candidate.resolve())
        except OSError:
            denied.add(candidate)
    denied.discard(skill_path)

    if destination.exists() and not destination.is_file():
        return result.fail(f"Output path exists and is not a file: {destination}")

    # 4. Walk.
    try:
        members, exclusions, symlinks, empty_dirs, multi_link = collect(
            skill_path, declared_name, denied
        )
    except OSError as exc:
        return result.fail(f"Could not enumerate {skill_path}: {exc}")
    result.included = members
    result.excluded = exclusions
    result.symlinks = symlinks
    result.empty_dirs = empty_dirs
    result.hard_links = multi_link
    result.uncompressed_bytes = sum(m.size for m in members)

    if not any(m.arcname == f"{declared_name}/{entry_name}" for m in members):
        return result.fail(
            f"{entry_name} was excluded from the archive - refusing to write a "
            f"skill with no {entry_name}."
        )

    problems = check_member_names([m.arcname for m in members] + [d + "/" for d in empty_dirs])
    if problems:
        result.errors.append(
            "The following member names cannot be extracted safely on every platform:"
        )
        result.errors.extend(f"  {p}" for p in problems)
        result.ok = False
        return result

    for link in symlinks:
        result.warnings.append(link.warning)

    if multi_link:
        shown = ", ".join(multi_link[:5])
        if len(multi_link) > 5:
            shown += f" and {len(multi_link) - 5} more"
        result.warnings.append(
            f"{len(multi_link)} packaged file(s) have more than one hard link "
            f"({shown}). A hard link has no target to resolve, so it is "
            "indistinguishable from an ordinary file and containment cannot tell "
            "whether its content originated outside the skill folder - check them "
            "before distributing."
        )

    if dry_run:
        result.ok = True
        return result

    if destination.exists():
        result.warnings.append(f"overwriting existing {destination}")

    # The 30 MB ceiling is documented for POST /v1/skills, the upload surface.
    # Enforced as a hard refusal for the targets that mean "I am uploading this"
    # and reported as a warning for the ones that install from a directory,
    # where no ceiling is documented and refusing would be a false rejection.
    enforced_limit = API_SIZE_LIMIT_BYTES if target in UPLOAD_TARGETS else None

    try:
        _write_archive(destination, members, empty_dirs, reject_over=enforced_limit)
    except ArchiveTooLarge as exc:
        result.fail(
            f"The archive came to {_human_size(exc.size)}, over the "
            f"{_human_size(exc.limit)} ceiling documented for POST /v1/skills - "
            f"the upload surface --target {target} packages for. Nothing was "
            "written, because an archive that surface rejects is not a "
            "successful build. Reduce what the skill carries (--dry-run lists "
            "every file and its size), or package for a target that installs "
            "from a directory: --target claude-code."
        )
        biggest = sorted(members, key=lambda m: m.size, reverse=True)[:5]
        result.errors.extend(
            f"  largest member: {m.arcname} ({_human_size(m.size)})" for m in biggest
        )
        return result
    except (OSError, zipfile.BadZipFile) as exc:
        return result.fail(f"Could not write {destination}: {exc}")

    try:
        result.archive_bytes = destination.stat().st_size
    except OSError:
        result.archive_bytes = None

    if result.archive_bytes and result.archive_bytes > API_SIZE_LIMIT_BYTES:
        result.warnings.append(
            f"archive is {_human_size(result.archive_bytes)}, over the "
            f"{_human_size(API_SIZE_LIMIT_BYTES)} ceiling documented for POST "
            "/v1/skills. It installs by extraction into a skills directory, "
            "which has no documented ceiling, but the Skills API and the "
            "claude.ai uploader will reject it - so those two surfaces are left "
            "out of the install instructions below."
        )

    result.ok = True
    return result


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def render_report(result: PackageResult, stream=None) -> None:
    """Print what is about to be distributed, and what was left out."""
    out = stream if stream is not None else sys.stderr

    def line(text: str = "") -> None:
        print(text, file=out)

    if result.skill_path:
        line(f"Packaging skill: {result.skill_path}")
        line(f"  validation target: {result.target}")
        line()

    if result.errors:
        for message in result.errors:
            line(f"ERROR: {message}" if not message.startswith("  ") else message)
        line()
        return

    verb = "Would include" if result.dry_run else "Included"
    line(f"{verb} {len(result.included)} file(s), {_human_size(result.uncompressed_bytes)} uncompressed:")
    for member in result.included:
        line(f"  + {member.arcname}  ({_human_size(member.size)})")
    for directory in result.empty_dirs:
        line(f"  + {directory}/  (empty directory, preserved)")
    line()

    if result.excluded:
        line(f"Excluded {len(result.excluded)} path(s) - none of these are in the archive:")
        width = max(len(e.path) for e in result.excluded)
        for exclusion in result.excluded:
            weight = ""
            if exclusion.path.endswith("/"):
                if exclusion.files is None or exclusion.size is None:
                    # Never walked, so its weight is unknown, not zero.
                    weight = " [not descended into]"
                else:
                    weight = f" [{exclusion.files} file(s), {_human_size(exclusion.size)}]"
            line(f"  - {exclusion.path.ljust(width)}  {exclusion.reason}{weight}")
        line()

    if result.symlinks:
        # Named for what they are. Every one of these was decided by resolving
        # the path, not by asking whether it was a symlink - which is why the
        # list can contain a junction at all.
        if {link.flavor for link in result.symlinks} == {"symlink"}:
            line(
                f"Skipped {len(result.symlinks)} symlink(s) - not followed, "
                "contents never copied in:"
            )
        else:
            line(
                f"Skipped {len(result.symlinks)} path(s) that resolve outside the "
                "skill folder - not followed, contents never copied in:"
            )
        for link in result.symlinks:
            line(f"  ~ {link.path} -> {link.target}  ({link.flavor}, {link.kind})")
        line()

    # Warnings already shown, in full, in the skipped-paths block above.
    already_shown = {link.warning for link in result.symlinks if link.warning}
    remaining = [w for w in result.warnings if w not in already_shown]
    for warning in remaining:
        line(f"WARNING: {warning}")
    if remaining:
        line()

    if result.dry_run:
        line(f"Dry run: nothing written. Would write {result.archive}")
        return

    if result.ok and result.archive:
        size = _human_size(result.archive_bytes) if result.archive_bytes is not None else "?"
        over_ceiling = (
            result.archive_bytes is not None and result.archive_bytes > API_SIZE_LIMIT_BYTES
        )
        line(f"Wrote {result.archive} ({size})")
        line()
        line("Install it by one of:")
        line("  Claude Code   extract it into ~/.claude/skills/ so the tree is")
        line(f"                ~/.claude/skills/{result.skill_name}/SKILL.md - live next session")
        if over_ceiling:
            # Naming a surface that will reject this archive would be an
            # instruction the tool's own numbers contradict.
            line("  claude.ai     not listed: over the upload ceiling (see the warning above)")
            line("  Skills API    not listed: over the upload ceiling (see the warning above)")
        else:
            line("  claude.ai     Customize > Skills > + > Create skill > Upload a skill")
            line(f'  Skills API    POST /v1/skills with -F "files[]=@{result.archive.name}"')


def result_to_json(result: PackageResult) -> dict:
    return {
        "ok": result.ok,
        "dry_run": result.dry_run,
        "target": result.target,
        "skill_name": result.skill_name,
        "skill_path": str(result.skill_path) if result.skill_path else None,
        "archive": str(result.archive) if result.archive and result.ok else None,
        "archive_bytes": result.archive_bytes,
        "uncompressed_bytes": result.uncompressed_bytes,
        "included": [{"path": m.arcname, "bytes": m.size, "mode": oct(m.mode)} for m in result.included],
        "empty_directories": result.empty_dirs,
        "excluded": [
            {"path": e.path, "reason": e.reason, "files": e.files, "bytes": e.size}
            for e in result.excluded
        ],
        # Kept under its original key for any consumer that already reads it,
        # but the membership rule is now containment, not link-ness: an entry
        # here is a path that resolved outside the skill folder, whatever kind
        # of link took it there. "flavor" says which kind that was.
        "symlinks_skipped": [
            {
                "path": s.path,
                "target": s.target,
                "kind": s.kind,
                "flavor": s.flavor,
                "resolves_outside_skill_folder": s.escapes,
            }
            for s in result.symlinks
        ],
        "hard_links": result.hard_links,
        "warnings": result.warnings,
        "errors": result.errors,
    }


def package_skill(skill_path, output_dir=None, *, target: str = DEFAULT_TARGET):
    """Package a skill folder into ``<name>.zip``.

    Args:
        skill_path: Path to the skill folder.
        output_dir: Optional output directory (defaults to the current directory).
        target: Validation target - claude-code, portable or claude-ai.

    Returns:
        Path to the created .zip file, or None on any failure.
    """
    result = build_package(skill_path, output_dir, target=target)
    render_report(result)
    return result.archive if result.ok else None


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv=None) -> int:
    # Status output is UTF-8; without this the first print() aborts on a
    # Windows console running a legacy codepage.
    configure_console()

    parser = argparse.ArgumentParser(
        prog="python -m scripts.package_skill",
        description="Package a skill folder into a distributable <name>.zip.",
    )
    parser.add_argument("skill_dir", help="Path to the skill folder")
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=None,
        help="Directory to write the archive into (default: current directory)",
    )
    parser.add_argument(
        "--target",
        choices=VALIDATION_TARGETS,
        default=DEFAULT_TARGET,
        help=f"Validation target (default: {DEFAULT_TARGET})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be included and excluded without writing anything",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit the manifest as JSON on stdout (human report stays on stderr)",
    )
    args = parser.parse_args(argv)

    result = build_package(
        args.skill_dir, args.output_dir, target=args.target, dry_run=args.dry_run
    )
    render_report(result, sys.stderr)

    if args.as_json:
        print(json.dumps(result_to_json(result), indent=2), file=sys.stdout)
    elif result.ok and result.archive and not result.dry_run:
        print(str(result.archive), file=sys.stdout)

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
