#!/usr/bin/env python3
"""Target-aware frontmatter validation for an Agent Skill.

Derived from ``anthropics/skills``, ``skills/skill-creator/scripts/quick_validate.py``
(Apache-2.0 -- see LICENSE.txt).

Usage (run as a module from the skill root)::

    python -m scripts.quick_validate <skill-dir> [--target TARGET] [--json]

Three rules govern this file.

**There is no single correct answer, and asserting one was the bug.**
The three surfaces a skill can be shipped to genuinely disagree about what is
legal, so the validator takes a ``--target``:

===========  ================================================  =================
target       recognised keys                                   description cap
===========  ================================================  =================
claude-code  the 31 keys Claude Code's loader recognises;       1024, **warning**
             unknown keys *warn*, they never error
portable     the 6-key Agent Skills standard set                1024
claude-ai    the portable set plus ``dependencies``             **200**
===========  ================================================  =================

Default target is ``claude-code``. Every finding names the target that
produced it, because "invalid" without a surface is not actionable: the same
``disable-model-invocation: true`` is correct on Claude Code, inert on
Claude.ai, and outside the open standard.

Hard errors in **every** target: a missing or empty ``name`` or
``description``; wrong *types* anywhere; and the structural ``name`` rules --
uppercase, whitespace, a path separator, a leading/trailing/doubled hyphen,
over 64 characters, or a character that is neither a letter, a digit nor a
hyphen. Those break the harness: the name becomes a directory component, a
``/slash-command`` and an archive member.

Every rule that is **not** uniform across targets is uniform in one respect --
it is sourced. R31 (research/V2-verification.md FP-2, FP-3) found two rules
this file asserted at the default target that no Claude Code document contains,
so both are now warnings there and errors only where a primary source states
them:

``description`` over 1024
    The 1024 is ``skills_ref.validator.MAX_DESCRIPTION_LENGTH`` and the Skills
    API's documented limit. code.claude.com/docs/en/skills states no
    per-description cap at all; what it states is that ``description`` +
    ``" - "`` + ``when_to_use`` is **truncated at 1,536** in the skill listing,
    which is checked separately here and *is* an error because the excess
    silently never reaches the model. So on ``claude-code`` an over-1024
    description is a portability warning; on ``portable`` and ``claude-ai`` it
    is an error.

``name`` != directory
    agentskills.io states the match explicitly and the Skills API rejects the
    upload, so it is an error on ``portable`` and ``claude-ai``. Claude Code
    documents the opposite: for a personal or project skill ``name`` is only
    the display label and the command comes from the directory. Warning there,
    with the packaging consequence named -- ``scripts.package_skill`` enforces
    the match itself and refuses at every target, so the warning has to say so
    or the author meets that refusal without warning.

``name`` missing stays an error on every target even though Claude Code
documents ``name`` as optional and defaulting to the directory name. That is a
deliberate exception and the message says why rather than claiming Claude Code
requires it: this package's own ``parse_skill_md`` needs a name (it becomes a
workspace directory, an eval path and an archive member), and both other
surfaces require it. Demoting it would make ``quick_validate`` bless a skill
that ``run_eval``, ``run_loop`` and ``package_skill`` all refuse -- the
disagreement class this rewrite exists to close.

A ``name`` that is well-formed but not plain ASCII -- ``日本語``, ``навык``,
``café`` -- is **valid**, and draws a portability *warning* rather than an
error. The reference validator accepts Unicode names and rejecting them here
would be stricter than the oracle, which is a false rejection; false rejections
are the failure mode this rewrite exists to close, and this one would land
hardest on the non-English authors these scripts have already failed once.

**Accumulate, don't bail.** Every check runs and every finding is
reported in one pass. The previous implementation returned on the first
problem, which turned "validate after any frontmatter edit" into a
whack-a-mole loop. Exit status is non-zero if there is at least one error;
warnings alone exit 0.

``--json`` writes one JSON object to **stdout and nothing else**; diagnostics
go to stderr. Without ``--json`` the human-readable verdict is the process's
stdout (there is no machine consumer to corrupt, and the packager and the
fixture drivers both read it there).

**Encoding.** SKILL.md is read as UTF-8 (BOM tolerated) via
:mod:`scripts.utils`; a decode failure is a message, not a traceback.

Where this deviates from the reference validator
------------------------------------------------
``agentskills/agentskills`` ``skills-ref`` is the oracle for pass/fail. What
follows was established by **running** ``skills-ref`` 0.1.1 against every
fixture, not by reading its documentation (research/V2-verification.md, whose
author installed it and drove it as a live oracle). Three beliefs an earlier
version of this docstring stated are corrected here, because a validator that
asserts what another validator does had better have run it:

* **skills-ref parses with ``strictyaml``**
  (``skills_ref.parser.parse_frontmatter``), which types every scalar as a
  string. ``description: 42``, ``name: yes`` and ``name: 2024-01-01`` are all
  *valid strings* to it. This file's type errors are therefore stricter than
  the oracle by construction, on 16 corpus fixtures.
* **skills-ref type-checks nothing on ``license``, ``allowed-tools`` or
  ``metadata``.** ``skills_ref.validator.validate_metadata`` checks the field
  *set*, ``name``, ``description`` and ``compatibility``'s length -- nothing
  else. The earlier claim that it "coerces metadata values with ``str()``" was
  wrong about where that happens: the coercion is in the *parser*, applies only
  when ``metadata`` already parsed as a mapping, and is not a validation step.
* **skills-ref accepts a fullwidth name.** It normalises NFKC on both sides
  before comparing, so ``ｅ－ｆｕｌｌｗｉｄｔｈ`` folds to ``e-fullwidth`` and
  matches that directory. This file compares NFC and rejects it.

The stricter type checking is kept deliberately: Claude Code and every
PyYAML/js-yaml-based loader *do* type these values, so ``description: 42``
reaches a real loader as an integer even though the oracle calls it a string.
Each deviation is marked ``DEVIATION`` at the point of the check:

1. ``name`` normalisation -- NFKC (oracle) vs NFC (here). NFC still matches
   canonically identical text (a decomposed ``café`` directory against a
   composed ``café`` name) without asserting that visually distinct names are
   the same one. The *charset* rule follows skills-ref exactly: letters, digits
   and hyphens, Unicode included.
2. ``compatibility: ""`` -- skills-ref accepts it (no minimum length is
   checked); the specification prose says "Must be 1-500 characters if
   provided", so it is an error here.
3. ``metadata`` values -- unchecked by the oracle; the specification says "a
   map from string keys to string values", so a nested map or a list is an
   error here rather than reaching a loader as one.
4. Duplicate keys, reserved words, and unknown-key severity are all things
   skills-ref either cannot see (PyYAML vs strictyaml) or does not model
   (it has no notion of a target).
5. A lowercase ``skill.md`` -- ``skills_ref.parser.find_skill_md`` accepts it;
   this file errors, because ``scripts.package_skill`` refuses to archive it
   and zip members are case-sensitive wherever the archive is unpacked.

One thing the oracle rejects and this file accepts: a UTF-8 BOM before the
opening ``---`` (``parse_frontmatter`` tests ``content.startswith("---")``).
Windows editors emit BOMs by default and rejecting one would be a false
rejection of a file every real loader reads.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    from scripts.utils import (
        SPEC_FIELDS,
        SkillMdError,
        actual_skill_md_name,
        configure_console,
        find_frontmatter_ambiguity,
        find_skill_md,
        load_frontmatter,
        read_text_utf8,
    )
except ImportError:  # pragma: no cover - allows `python scripts/quick_validate.py`
    # These are meant to run as modules from the skill root; this keeps the bare
    # path working anyway. `scripts` is a common enough directory name that an
    # unrelated implicit namespace package can already be cached under it (on
    # this machine, pywin32's site-packages/win32/scripts), so the stale entry
    # has to be dropped before the retry or it shadows the real package.
    _SKILL_ROOT = str(Path(__file__).resolve().parent.parent)
    if _SKILL_ROOT not in sys.path:
        sys.path.insert(0, _SKILL_ROOT)
    for _stale in [m for m in sys.modules if m == "scripts" or m.startswith("scripts.")]:
        del sys.modules[_stale]
    from scripts.utils import (  # type: ignore[no-redef]
        SPEC_FIELDS,
        SkillMdError,
        actual_skill_md_name,
        configure_console,
        find_frontmatter_ambiguity,
        find_skill_md,
        load_frontmatter,
        read_text_utf8,
    )


# --------------------------------------------------------------------------
# Field sets
# --------------------------------------------------------------------------

#: agentskills.io/specification -- the closed, portable field set.
PORTABLE_FIELDS = frozenset(SPEC_FIELDS)

#: claude.com/docs/skills/how-to documents `dependencies` for claude.ai
#: uploads. The open standard omits it, hence the separate set.
CLAUDE_AI_FIELDS = PORTABLE_FIELDS | {"dependencies"}

#: The 31 keys Claude Code's own frontmatter schema recognises, extracted from
#: the v2.1.214 binary (research/18-untaught-capabilities.md F1). The schema
#: object those 31 live in also carries ten plugin-manifest keys -- mcpServers,
#: lspServers, agents, outputStyles, themes, workflows, channels, monitors,
#: settings, userConfig -- which belong to plugin.json rather than to a skill
#: and are deliberately not listed here.
CLAUDE_CODE_SCHEMA_FIELDS = frozenset(
    {
        # base schema
        "name",
        "description",
        "model",
        "allowed-tools",
        "disallowed-tools",
        "disallowedTools",
        "argument-hint",
        "arguments",
        "disable-model-invocation",
        "user-invocable",
        "effort",
        "shell",
        "version",
        # skill extension
        "when_to_use",
        "paths",
        "hooks",
        "context",
        "agent",
        "fallback",
        "created_by",
        "improved_by",
        "defaultEnabled",
        "experimental",
        "dependencies",
        "metadata",
        "displayName",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
    }
)

#: `background` is documented at code.claude.com/docs/en/skills (v2.1.218+) but
#: is absent from the 2.1.214 schema dump; `compatibility` is a standard field
#: Claude Code silently ignores. Neither should draw a warning here.
CLAUDE_CODE_FIELDS = CLAUDE_CODE_SCHEMA_FIELDS | {"background", "compatibility"}

#: Union across targets. Used only to make the first signal in
#: :func:`scripts.utils.find_frontmatter_ambiguity` as sensitive as it can
#: safely be -- a key stranded past a stray ``---`` is worth mentioning if
#: *any* surface would have recognised it.
ALL_KNOWN_FIELDS = PORTABLE_FIELDS | CLAUDE_AI_FIELDS | CLAUDE_CODE_FIELDS

MAX_NAME_LENGTH = 64
MAX_COMPATIBILITY_LENGTH = 500
CLAUDE_AI_DESCRIPTION_MAX = 200

#: The plain-ASCII kebab shape. A name that matches this is portable
#: everywhere. A name that does *not* match is not automatically invalid --
#: see `_check_name`, which separates the structural rules (hard errors) from
#: the "not ASCII" observation (a portability warning).
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

#: Structural rules, checked individually so each gets its own message.
#: Path separators are listed explicitly (rather than left to the general
#: character check) because they are the one class that breaks the harness
#: rather than merely travelling badly: the name becomes a directory component.
NAME_PATH_SEPARATORS = ("/", "\\", ":")
WHITESPACE_PATTERN = re.compile(r"\s")

#: "Cannot contain XML tags" (platform.claude.com). Tags, not the characters --
#: `a < b`, `->`, `<=` and `n > 0` are ordinary prose and used to be rejected.
XML_TAG_PATTERN = re.compile(r"<[A-Za-z/!?][^>]*>")

#: platform.claude.com/.../agent-skills/overview, "Field requirements".
RESERVED_NAME_WORDS = ("anthropic", "claude")


# --------------------------------------------------------------------------
# Targets
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetProfile:
    """One shipping surface's rules."""

    name: str
    label: str
    fields: frozenset
    description_max: int
    #: Where `description_max` comes from, quoted in the finding. A cap with no
    #: source is the FP-2 defect: a number this file invented, presented to the
    #: author as a documented one.
    description_max_source: str
    #: What exceeding `description_max` costs here. `warning` on a surface that
    #: does not enforce the number.
    description_max_level: str = "error"
    #: What a `name` that differs from the directory costs here (FP-3).
    name_directory_level: str = "error"
    #: `description` + " - " + `when_to_use`, Claude Code's skill listing cap.
    combined_description_max: Optional[int] = None
    #: What an unrecognised key costs on this surface.
    unknown_key_level: str = "error"
    #: The reserved-word rule is a documented hard rejection on the Claude.ai /
    #: Claude API upload path only. Claude Code ships `claude-api` itself, and
    #: the open standard has no such rule, so elsewhere it is a warning.
    reserved_word_level: str = "warning"
    #: Claude Code accepts a YAML list for `allowed-tools`; the standard says
    #: "a space-separated string".
    allow_tools_as_list: bool = False


PROFILES: dict[str, TargetProfile] = {
    "claude-code": TargetProfile(
        name="claude-code",
        label="Claude Code (CLI, desktop, IDE) and the Agent SDK",
        fields=CLAUDE_CODE_FIELDS,
        description_max=1024,
        # FP-2: no Claude Code document states a per-description cap. The
        # number belongs to the open standard and the upload paths, so it is
        # carried here as a portability warning and attributed to its source.
        description_max_source=(
            "the Agent Skills standard (skills-ref's MAX_DESCRIPTION_LENGTH) "
            "and the Skills API upload path"
        ),
        description_max_level="warning",
        # FP-3: code.claude.com documents the opposite of a required match.
        name_directory_level="warning",
        combined_description_max=1536,
        unknown_key_level="warning",
        reserved_word_level="warning",
        allow_tools_as_list=True,
    ),
    "portable": TargetProfile(
        name="portable",
        label="the Agent Skills open standard (agentskills.io)",
        fields=PORTABLE_FIELDS,
        description_max=1024,
        description_max_source=(
            'agentskills.io/specification, "Must be 1-1024 characters"'
        ),
        description_max_level="error",
        name_directory_level="error",
        unknown_key_level="error",
        reserved_word_level="warning",
        allow_tools_as_list=False,
    ),
    "claude-ai": TargetProfile(
        name="claude-ai",
        label="Claude.ai / Cowork / the Claude Skills API",
        fields=CLAUDE_AI_FIELDS,
        description_max=CLAUDE_AI_DESCRIPTION_MAX,
        description_max_source=(
            "claude.com/docs/skills/how-to, which states the 200-character "
            "limit as an explicit warning on the upload page"
        ),
        description_max_level="error",
        name_directory_level="error",
        unknown_key_level="error",
        reserved_word_level="error",
        allow_tools_as_list=False,
    ),
}

TARGETS = tuple(PROFILES)
DEFAULT_TARGET = "claude-code"


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

ERROR = "error"
WARNING = "warning"


@dataclass
class Finding:
    """One validation result. Always names its field and its target."""

    level: str
    field: str
    code: str
    message: str
    target: str

    def render(self) -> str:
        return f"[{self.level}] {self.target}: {self.field}: {self.message}"

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "target": self.target,
        }


class _Findings:
    """Accumulator. Nothing in this module returns on first failure."""

    def __init__(self, target: str) -> None:
        self.target = target
        self.items: list[Finding] = []

    def error(self, field_name: str, code: str, message: str) -> None:
        self.items.append(Finding(ERROR, field_name, code, message, self.target))

    def warn(self, field_name: str, code: str, message: str) -> None:
        self.items.append(Finding(WARNING, field_name, code, message, self.target))

    def add(self, level: str, field_name: str, code: str, message: str) -> None:
        self.items.append(Finding(level, field_name, code, message, self.target))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.items if f.level == ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.items if f.level == WARNING]


def _type_name(value: Any) -> str:
    return type(value).__name__


def _describe(value: Any, limit: int = 40) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


# --------------------------------------------------------------------------
# Field checks
# --------------------------------------------------------------------------


def _check_unknown_keys(data: dict, profile: TargetProfile, out: _Findings) -> None:
    unknown = sorted(set(data) - profile.fields)
    if not unknown:
        return
    listing = ", ".join(unknown)
    if profile.name == "claude-code":
        out.add(
            profile.unknown_key_level,
            "frontmatter",
            "unknown-key",
            f"key(s) not in the 31 Claude Code recognises: {listing}. Claude Code "
            f"ignores keys it does not know rather than failing the load, so this "
            f"is not fatal here -- but it also means a misspelled key "
            f"(`disabke-model-invocation`) silently does nothing. Check the "
            f"spelling before you doubt the semantics.",
        )
    else:
        out.add(
            profile.unknown_key_level,
            "frontmatter",
            "unknown-key",
            f"key(s) not accepted by {profile.label}: {listing}. Recognised here: "
            f"{', '.join(sorted(profile.fields))}. Claude Code extension keys "
            f"(when_to_use, disable-model-invocation, context, ...) are valid on "
            f"Claude Code only -- validate with --target claude-code if that is "
            f"where this skill ships.",
        )


def _check_name(
    data: dict, skill_path: Path, profile: TargetProfile, out: _Findings
) -> None:
    if "name" not in data:
        # An error on every target, including the one whose documentation says
        # "All fields are optional" and that `name` "Defaults to the directory
        # name". The message states whose requirement this is rather than
        # attributing it to Claude Code, which does not have it: the standard
        # and the upload path require it, and so does this package -- the name
        # becomes a workspace directory and an archive member in run_eval,
        # run_loop, improve_description and package_skill, all of which refuse
        # a skill without one. Warning here would bless a skill every other
        # tool in the bundle rejects.
        out.error(
            "name",
            "name.missing",
            "is missing. agentskills.io and the Skills API both require it, and "
            "this toolchain needs it too -- run_eval, run_loop and package_skill "
            "all build directory and archive names from it. Claude Code alone "
            "would default it from the directory name.",
        )
        return

    raw = data["name"]
    if not isinstance(raw, str):
        out.error(
            "name",
            "name.type",
            f"must be a string, got {_type_name(raw)} ({_describe(raw)}). YAML "
            f"coerces bare values -- quote it.",
        )
        return

    name = raw.strip()
    if not name:
        # The two truthiness guards `if name:` / `if description:` used to put
        # every rule below them out of reach of exactly the value that most
        # needs checking.
        out.error("name", "name.empty", "must be a non-empty string")
        return

    if len(name) > MAX_NAME_LENGTH:
        out.error(
            "name",
            "name.too-long",
            f"is {len(name)} characters; the maximum is {MAX_NAME_LENGTH}",
        )

    # --- structural rules: hard errors on every target -------------------
    # These break the harness rather than merely travelling badly. The name
    # becomes a directory component, a slash command and an archive member, so
    # whitespace, path separators and case are not stylistic questions.
    if WHITESPACE_PATTERN.search(name):
        out.error(
            "name",
            "name.whitespace",
            f"'{name}' contains whitespace. The name becomes a directory name and "
            f"a /slash-command, neither of which can hold a space -- use a hyphen.",
        )

    separators = [sep for sep in NAME_PATH_SEPARATORS if sep in name]
    if separators:
        out.error(
            "name",
            "name.path-separator",
            f"'{name}' contains {', '.join(repr(s) for s in separators)}. The name "
            f"is used as a single directory component, so a path separator splits "
            f"it into a path.",
        )

    if name != name.lower():
        out.error(
            "name",
            "name.uppercase",
            f"'{name}' contains uppercase characters; skill names are lowercase. "
            f"Case-insensitive filesystems make an uppercase name resolve "
            f"differently on Windows and macOS than on Linux.",
        )

    if name.startswith("-") or name.endswith("-"):
        out.error(
            "name",
            "name.hyphen-edge",
            f"'{name}' starts or ends with a hyphen; hyphens go between segments",
        )

    if "--" in name:
        out.error(
            "name",
            "name.consecutive-hyphens",
            f"'{name}' contains consecutive hyphens; use one between segments",
        )

    # Characters outside "letter, digit, or hyphen" entirely. This is the
    # reference validator's rule (`c.isalnum() or c == '-'`) and it stays an
    # error: an underscore, a dot or an emoji is rejected by the oracle, by
    # the API upload path, and by the standard.
    invalid = sorted(
        {
            c
            for c in name
            if not (c.isalnum() or c == "-")
            and not c.isspace()
            and c not in NAME_PATH_SEPARATORS
        }
    )
    if invalid:
        out.error(
            "name",
            "name.invalid-chars",
            f"'{name}' contains {', '.join(repr(c) for c in invalid)}. A skill "
            f"name may only contain letters, digits and hyphens.",
        )

    # --- portability: a warning, never an error --------------------------
    # Names outside plain ASCII are accepted here, matching the reference
    # validator (`skills-ref` normalises NFKC and tests `c.isalnum()`, which
    # passes Japanese, Cyrillic, Greek and accented Latin). Rejecting them
    # would be stricter than the oracle and would fall hardest on exactly the
    # non-English authors these scripts have already failed once. The author
    # is told about the tradeoff and decides.
    non_ascii = sorted(
        {
            c
            for c in name
            if c.isalnum() and not ("a" <= c.lower() <= "z" or "0" <= c <= "9")
        }
    )
    if non_ascii:
        out.warn(
            "name",
            "name.non-ascii",
            f"'{name}' uses characters outside a-z0-9: "
            f"{', '.join(repr(c) for c in non_ascii)}. This is valid -- the Agent "
            f"Skills reference validator accepts Unicode names -- but support is "
            f"uneven in practice: some upload paths, shells and filesystems "
            f"normalise or transliterate non-ASCII directory names, and a "
            f"/slash-command built from one can be awkward to type. If the skill "
            f"is only ever installed locally this costs nothing; if you plan to "
            f"distribute it widely, an ASCII name is the safer bet.",
        )

    lowered = name.lower()
    hits = [word for word in RESERVED_NAME_WORDS if word in lowered]
    if hits:
        out.add(
            profile.reserved_word_level,
            "name",
            "name.reserved-word",
            f"contains the reserved word(s) {', '.join(hits)}. The Claude.ai and "
            f"Claude API upload paths reject these outright; Claude Code does not "
            f"(it ships `claude-api` itself) and the open standard has no such rule.",
        )

    directory = skill_path.resolve().name
    # Compared under NFC so a non-ASCII directory name that the filesystem
    # stored decomposed (macOS does this) still matches a composed frontmatter
    # name -- the two are the same text and rejecting the pair would be a false
    # mismatch of exactly the kind the non-ASCII warning above exists to avoid.
    # DEVIATION from skills-ref, which normalises NFKC: compatibility folding
    # would also equate visually distinct names (fullwidth vs ASCII), which is
    # a different claim than "these are the same string".
    if unicodedata.normalize("NFC", name) != unicodedata.normalize("NFC", directory):
        # FP-3. Severity is the target's, because the surfaces genuinely
        # disagree: agentskills.io states the match explicitly and the Skills
        # API rejects the upload, while code.claude.com says that in a personal
        # or project skill `name` sets only the display label and the command
        # still comes from the directory. Asserting an error on the surface
        # that documents the opposite is a false rejection at the *default*
        # target -- but a warning that did not name the packaging consequence
        # would be the other half of the same defect, so it names it.
        consequence = (
            "The standard requires them to match and the Skills API rejects the "
            "upload otherwise."
            if profile.name_directory_level == ERROR
            else "Claude Code accepts this -- in a personal or project skill "
            "`name` is only the display label and the /slash-command still "
            "comes from the directory, so the name you wrote is not the one "
            "you would type. It is not portable, though: `package_skill` "
            "refuses to build an archive with a mismatch, and the Skills API "
            "rejects the upload. Rename the directory or the `name` before "
            "you package or distribute this."
        )
        out.add(
            profile.name_directory_level,
            "name",
            "name.directory-mismatch",
            f"is '{name}' but the directory is '{directory}'. {consequence}",
        )


def _check_description(data: dict, profile: TargetProfile, out: _Findings) -> None:
    if "description" not in data:
        out.error(
            "description",
            "description.missing",
            "required key is missing from the frontmatter",
        )
        return

    raw = data["description"]
    if not isinstance(raw, str):
        out.error(
            "description",
            "description.type",
            f"must be a string, got {_type_name(raw)} ({_describe(raw)}). If the "
            f"text contains ': ', '#', '[' or starts with '@', wrap it in double "
            f"quotes or use a |- block scalar.",
        )
        return

    if not raw.strip():
        out.error(
            "description",
            "description.empty",
            "must be a non-empty string -- it is the only thing the model matches "
            "a request against, so an empty one installs fine and never triggers",
        )
        return

    # Length is measured on the raw value, matching the reference validator:
    # padding counts against the cap even though callers get it stripped.
    length = len(raw)
    if length > profile.description_max:
        # FP-2. The number is always attributed. Where the target does not
        # itself enforce it, this is a warning and says so outright: the
        # previous message told a Claude Code author that "the cap for Claude
        # Code ... is 1024", which no Claude Code document states, and rejected
        # a description Claude Code loads whole.
        if profile.description_max_level == ERROR:
            detail = (
                f"is {length} characters; the cap for {profile.label} is "
                f"{profile.description_max}, per {profile.description_max_source}."
            )
        else:
            detail = (
                f"is {length} characters, over {profile.description_max}. "
                f"{profile.label} documents no per-description cap and does not "
                f"reject this -- what it documents is that description + ' - ' + "
                f"when_to_use is truncated at {profile.combined_description_max} "
                f"in the skill listing, which is checked separately. The "
                f"{profile.description_max} figure comes from "
                f"{profile.description_max_source}, so this description is "
                f"rejected when you upload or publish it. Re-check with --target "
                f"portable before distributing."
            )
        out.add(
            profile.description_max_level,
            "description",
            "description.too-long",
            detail,
        )
    elif (
        profile.description_max > CLAUDE_AI_DESCRIPTION_MAX
        and length > CLAUDE_AI_DESCRIPTION_MAX
    ):
        out.warn(
            "description",
            "description.claude-ai-cap",
            f"is {length} characters. Legal here, but Claude.ai caps descriptions "
            f"at {CLAUDE_AI_DESCRIPTION_MAX} -- re-check with --target claude-ai "
            f"before uploading a zip there.",
        )

    tags = XML_TAG_PATTERN.findall(raw)
    if tags:
        out.error(
            "description",
            "description.xml-tag",
            f"contains XML tag(s): {', '.join(sorted(set(tags))[:3])}. Bare "
            f"comparison operators (a < b, n > 0, ->) are fine; tag-shaped spans "
            f"are not.",
        )

    controls = sorted(
        {c for c in raw if unicodedata.category(c) == "Cc" and c not in "\n\t"}
    )
    if controls:
        out.error(
            "description",
            "description.control-char",
            "contains raw control character(s): "
            + ", ".join(f"U+{ord(c):04X}" for c in controls),
        )

    # The documented Claude Code limit, and the only hard upper bound on this
    # target now that the undocumented 1024 is a warning (FP-2). It applies
    # whether or not `when_to_use` is present: the listing entry is the
    # description, plus " - " and when_to_use when there is one, and the entry
    # is what gets truncated. Guarding this on `when_to_use` being a string --
    # as it used to -- left a description with no upper bound at all once the
    # 1024 stopped being an error, which an 8 MB frontmatter demonstrates.
    combined_max = profile.combined_description_max
    when_to_use = data.get("when_to_use")
    if combined_max:
        has_when_to_use = isinstance(when_to_use, str)
        combined = length + (
            len(" - ") + len(when_to_use) if has_when_to_use else 0
        )
        if combined > combined_max:
            what = (
                "description + ' - ' + when_to_use"
                if has_when_to_use
                else "the description alone"
            )
            out.error(
                "description",
                "description.combined-too-long",
                f"{what} is {combined} characters; {profile.label} truncates the "
                f"skill listing entry at {combined_max}, silently, so anything past "
                f"that is never seen by the model that decides whether to use this "
                f"skill",
            )


def _check_optional_string(
    data: dict,
    key: str,
    out: _Findings,
    *,
    max_length: Optional[int] = None,
    require_non_empty: bool = False,
    note: str = "",
) -> None:
    if key not in data:
        return
    value = data[key]
    if not isinstance(value, str):
        out.error(
            key,
            f"{key}.type",
            f"must be a string, got {_type_name(value)} ({_describe(value)}){note}",
        )
        return
    if require_non_empty and not value.strip():
        out.error(key, f"{key}.empty", "is present but empty; omit the key or give it a value")
        return
    if max_length is not None and len(value) > max_length:
        out.error(
            key,
            f"{key}.too-long",
            f"is {len(value)} characters; the maximum is {max_length}",
        )


def _check_allowed_tools(data: dict, profile: TargetProfile, out: _Findings) -> None:
    if "allowed-tools" not in data:
        return
    value = data["allowed-tools"]
    if isinstance(value, str):
        return
    if isinstance(value, list):
        if not profile.allow_tools_as_list:
            out.error(
                "allowed-tools",
                "allowed-tools.type",
                f"is a YAML list. {profile.label} specifies a space-separated "
                f"string; Claude Code additionally accepts a list, so this is "
                f"valid with --target claude-code only.",
            )
        elif not all(isinstance(item, str) for item in value):
            out.error(
                "allowed-tools",
                "allowed-tools.type",
                "is a list containing non-string entries",
            )
        return
    out.error(
        "allowed-tools",
        "allowed-tools.type",
        f"must be a space-separated string, got {_type_name(value)} "
        f"({_describe(value)})",
    )


def _check_metadata(data: dict, out: _Findings) -> None:
    if "metadata" not in data:
        return
    value = data["metadata"]
    if not isinstance(value, dict):
        out.error(
            "metadata",
            "metadata.type",
            f"must be a mapping of string keys to string values, got "
            f"{_type_name(value)} ({_describe(value)})",
        )
        return
    # DEVIATION from skills-ref, whose parser coerces every value with str().
    # The specification says "a map from string keys to string values", so a
    # nested map is reported rather than stringified into `{'name': 'bob'}`.
    bad = sorted(
        str(key)
        for key, item in value.items()
        if not isinstance(key, str) or not isinstance(item, str)
    )
    if bad:
        out.error(
            "metadata",
            "metadata.value-type",
            f"values must be strings; these are not: {', '.join(bad)}. Quote "
            f"numbers and booleans, and flatten nested maps.",
        )


def _check_dependencies(data: dict, profile: TargetProfile, out: _Findings) -> None:
    if "dependencies" not in data:
        return
    value = data["dependencies"]
    if not isinstance(value, str):
        out.error(
            "dependencies",
            "dependencies.type",
            f"must be a comma-separated string (e.g. 'python>=3.8, pandas'), got "
            f"{_type_name(value)}",
        )
    if profile.name == "claude-code":
        out.warn(
            "dependencies",
            "dependencies.surface",
            "is documented for Claude.ai uploads only; Claude Code does not "
            "install packages from it.",
        )


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------


def collect_findings(skill_path, target: str = DEFAULT_TARGET) -> list[Finding]:
    """Run every check against *skill_path* and return all findings.

    Never raises for a malformed skill: a file that cannot be read or parsed
    becomes a ``SKILL.md`` finding like any other.
    """
    if target not in PROFILES:
        raise ValueError(f"unknown target {target!r}; expected one of {', '.join(TARGETS)}")
    profile = PROFILES[target]
    out = _Findings(target)
    skill_path = Path(skill_path)

    if not skill_path.exists():
        out.error("path", "path.missing", f"path does not exist: {skill_path}")
        return out.items
    if not skill_path.is_dir():
        out.error(
            "path",
            "path.not-a-directory",
            f"is not a directory: {skill_path}. Point at the skill folder, not a file.",
        )
        return out.items

    skill_md = find_skill_md(skill_path)
    if skill_md is None:
        out.error(
            "SKILL.md",
            "skill-md.missing",
            f"no SKILL.md in {skill_path} (SKILL.md or skill.md; a directory of "
            f"that name does not count)",
        )
        return out.items

    # PK-1. The file is read either way -- a message about the frontmatter is
    # more useful than a refusal to look -- but the spelling is reported,
    # because this is the one condition where a "valid!" here is followed by a
    # hard refusal downstream, and the packager's message ("SKILL.md was
    # excluded from the archive") does not name the cause.
    on_disk = actual_skill_md_name(skill_path)
    if on_disk is not None and on_disk != "SKILL.md":
        out.error(
            "SKILL.md",
            "skill-md.filename-case",
            f"the file is named '{on_disk}'; it has to be 'SKILL.md', in capitals. "
            f"On Windows and macOS the lowercase spelling appears to work because "
            f"the filesystem ignores case -- but zip members are case-sensitive "
            f"wherever the archive is unpacked, Linux filesystems are "
            f"case-sensitive, and `python -m scripts.package_skill` refuses to "
            f"build an archive it cannot find a SKILL.md in. Rename the file. "
            f"(The Agent Skills reference validator tolerates the lowercase "
            f"spelling; this is deliberately stricter, because the tools that "
            f"ship the skill do not.)",
        )

    try:
        content = read_text_utf8(skill_md)
        data, _body = load_frontmatter(content)
    except SkillMdError as exc:
        out.error("SKILL.md", "skill-md.parse", str(exc))
        return out.items

    # R30. Ambiguous, not fatal: the reference validator truncates at the same
    # place and accepts the file, and every skill that documents frontmatter in
    # a fenced block and then uses a horizontal rule used to be rejected here
    # with an error message that was false about the file.
    ambiguity = find_frontmatter_ambiguity(content, known_keys=ALL_KNOWN_FIELDS)
    if ambiguity is not None:
        out.warn("SKILL.md", "skill-md.ambiguous-delimiter", ambiguity.message)

    _check_unknown_keys(data, profile, out)
    _check_name(data, skill_path, profile, out)
    _check_description(data, profile, out)
    _check_optional_string(
        data,
        "license",
        out,
        note=". A license name or file reference, e.g. Apache-2.0",
    )
    _check_optional_string(
        data,
        "compatibility",
        out,
        max_length=MAX_COMPATIBILITY_LENGTH,
        # DEVIATION from skills-ref, which accepts `compatibility: ""`. The
        # specification prose is "Must be 1-500 characters if provided".
        require_non_empty=True,
    )
    _check_allowed_tools(data, profile, out)
    _check_metadata(data, out)
    _check_dependencies(data, profile, out)
    return out.items


def validate_skill(skill_path, target: str = DEFAULT_TARGET) -> tuple[bool, str]:
    """Validate a skill. Returns ``(is_valid, message)``.

    The two-tuple shape is the contract ``scripts.package_skill`` consumes.
    ``message`` now carries *every* finding, one per line, rather than only the
    first problem encountered.
    """
    return _render(collect_findings(skill_path, target), target)


def _render(findings: list[Finding], target: str) -> tuple[bool, str]:
    """Turn accumulated findings into the ``(is_valid, message)`` pair."""
    errors = [f for f in findings if f.level == ERROR]
    warnings = [f for f in findings if f.level == WARNING]
    lines = [f.render() for f in errors] + [f.render() for f in warnings]
    if errors:
        header = (
            f"{len(errors)} error(s)"
            + (f", {len(warnings)} warning(s)" if warnings else "")
            + f" for target '{target}':"
        )
        return False, "\n".join([header] + lines)
    if warnings:
        return True, "\n".join([f"Skill is valid! ({len(warnings)} warning(s))"] + lines)
    return True, "Skill is valid!"


def _json_payload(skill_path, target: str, findings: list[Finding]) -> dict:
    errors = [f for f in findings if f.level == ERROR]
    warnings = [f for f in findings if f.level == WARNING]
    return {
        "skill_path": str(Path(skill_path)),
        "target": target,
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "findings": [f.to_dict() for f in findings],
    }


def main(argv: Optional[list[str]] = None) -> int:
    configure_console()
    parser = argparse.ArgumentParser(
        prog="python -m scripts.quick_validate",
        description="Validate an Agent Skill's frontmatter against a shipping target.",
    )
    parser.add_argument("skill_dir", help="path to the skill directory")
    parser.add_argument(
        "--target",
        choices=TARGETS,
        default=DEFAULT_TARGET,
        help=f"shipping surface to validate against (default: {DEFAULT_TARGET})",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="emit one JSON object on stdout and nothing else",
    )
    args = parser.parse_args(argv)

    try:
        findings = collect_findings(args.skill_dir, args.target)
    except ValueError as exc:  # unknown target -- argparse should have caught it
        print(str(exc), file=sys.stderr)
        return 2

    errors = [f for f in findings if f.level == ERROR]

    if args.as_json:
        # stdout carries the JSON object alone.
        print(json.dumps(_json_payload(args.skill_dir, args.target, findings), indent=2,
                         ensure_ascii=False))
    else:
        _valid, message = _render(findings, args.target)
        print(message)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
