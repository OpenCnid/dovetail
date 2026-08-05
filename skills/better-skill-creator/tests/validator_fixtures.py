#!/usr/bin/env python3
"""Fixture corpus for the frontmatter validator and the shared SKILL.md parser.

Every case here corresponds to a defect demonstrated against the previous
implementation in the research reports, or guards a rule that the fix
introduces:

* ``fn-*``      -- accepted-but-invalid inputs (the false-negative set,
                   research/12-validator-packager.md F1 and the round-2 corpus)
* ``crash-*``   -- inputs that produced a bare traceback where a message was
                   the whole point (12 F5)
* ``fp-*``      -- rejected-but-valid inputs (12 F4, 04 F7/F14, 08 F1)
* ``I18N-*`` /
  ``NM-*``      -- the split between a name that is structurally broken (a hard
                   error on every target) and one that is merely not ASCII (a
                   portability warning, matching the reference validator, which
                   accepts Unicode names)
* ``new-*``     -- defects the reports name for which the research corpus had
                   no fixture, or had one whose own expectation was internally
                   inconsistent.

Expectations are **per target**, because C9 says there is no single correct
answer and asserting one was the original bug.

Materialize with::

    python -m tests.validator_fixtures <destination-dir>
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

TARGETS = ("claude-code", "portable", "claude-ai")

GOOD_DESC = "Extracts text and tables from PDF files. Use when working with PDF documents."


def expectations(claude_code: str, portable: str, claude_ai: str) -> dict[str, str]:
    return {"claude-code": claude_code, "portable": portable, "claude-ai": claude_ai}


ALL_PASS = expectations("pass", "pass", "pass")
ALL_FAIL = expectations("fail", "fail", "fail")


@dataclass
class Case:
    """One fixture directory plus what each target should say about it."""

    cid: str
    dirname: str
    why: str
    expect: dict[str, str]
    #: SKILL.md text. ``None`` means "write no SKILL.md".
    skill_md: Optional[str] = None
    encoding: str = "utf-8"
    newline: str = "\n"
    skill_md_name: str = "SKILL.md"
    #: Create SKILL.md as a *directory* instead of a file.
    skill_md_is_dir: bool = False
    extra_files: dict[str, str] = field(default_factory=dict)
    #: target -> finding codes that must be present in the result.
    codes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: target -> finding codes that must NOT be present.
    forbid_codes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    note: str = ""

    def expected(self, target: str) -> str:
        return self.expect[target]


def fm(body: str, heading: str = "skill") -> str:
    return f"---\n{body}\n---\n\n# {heading}\n\nDo the thing.\n"


CASES: list[Case] = []


def case(*args, **kwargs) -> None:
    CASES.append(Case(*args, **kwargs))


# ---------------------------------------------------------------- baseline
case(
    "B01",
    "good-skill",
    "well-formed minimal skill; must stay valid on every surface",
    ALL_PASS,
    fm(f"name: good-skill\ndescription: {GOOD_DESC}"),
)
case(
    "B02",
    "full-skill",
    "all six portable keys, correctly typed",
    ALL_PASS,
    fm(
        f"name: full-skill\ndescription: {GOOD_DESC}\nlicense: Apache-2.0\n"
        'compatibility: Requires Python 3.11+\nallowed-tools: Read Grep\n'
        'metadata:\n  author: example-org\n  version: "1.0"'
    ),
)

# ------------------------------------------------- false negatives (12 F1)
case(
    "FN01",
    "fn-name-empty",
    'name: "" was accepted: every name rule lived inside an `if name:` guard, '
    "and an empty string is falsy",
    ALL_FAIL,
    fm(f'name: ""\ndescription: {GOOD_DESC}'),
    codes={t: ("name.empty",) for t in TARGETS},
)
case(
    "FN02",
    "fn-name-blank",
    "whitespace-only name was accepted for the same reason",
    ALL_FAIL,
    fm(f'name: "   "\ndescription: {GOOD_DESC}'),
    codes={t: ("name.empty",) for t in TARGETS},
)
case(
    "FN03",
    "fn-desc-empty",
    'description: "" was accepted; description is the only thing the model '
    "matches a request against, so the skill installs and never triggers",
    ALL_FAIL,
    fm('name: fn-desc-empty\ndescription: ""'),
    codes={t: ("description.empty",) for t in TARGETS},
)
case(
    "FN04",
    "fn-desc-blank",
    "whitespace-only description was accepted",
    ALL_FAIL,
    fm('name: fn-desc-blank\ndescription: "   "'),
    codes={t: ("description.empty",) for t in TARGETS},
)
case(
    "FN05",
    "fn-dir-mismatch",
    "frontmatter name disagrees with the directory name. agentskills.io "
    "requires the match and the Skills API rejects the upload -- but "
    "code.claude.com says that in a personal or project skill `name` is only "
    "the display label and the command comes from the directory, so on "
    "claude-code this is a warning naming the packaging consequence, not an "
    "error (R31/FP-3)",
    expectations("pass", "fail", "fail"),
    fm(f"name: totally-different\ndescription: {GOOD_DESC}"),
    codes={t: ("name.directory-mismatch",) for t in TARGETS},
    note="was ALL_FAIL before R31",
)
case(
    "FN06",
    "claude-helper",
    "reserved word 'claude' in name: a documented hard rejection on the "
    "Claude.ai/API upload path, advisory elsewhere (Claude Code ships claude-api)",
    expectations("pass", "pass", "fail"),
    fm(f"name: claude-helper\ndescription: {GOOD_DESC}"),
    codes={t: ("name.reserved-word",) for t in TARGETS},
)
case(
    "FN07",
    "anthropic-tools",
    "reserved word 'anthropic' in name",
    expectations("pass", "pass", "fail"),
    fm(f"name: anthropic-tools\ndescription: {GOOD_DESC}"),
    codes={t: ("name.reserved-word",) for t in TARGETS},
)
case(
    "FN08",
    "fn-metadata-scalar",
    "metadata: 42 was accepted; the spec types it as a map of string to string",
    ALL_FAIL,
    fm(f"name: fn-metadata-scalar\ndescription: {GOOD_DESC}\nmetadata: 42"),
    codes={t: ("metadata.type",) for t in TARGETS},
)
case(
    "FN09",
    "fn-metadata-list",
    "metadata as a YAML list was accepted",
    ALL_FAIL,
    fm(f"name: fn-metadata-list\ndescription: {GOOD_DESC}\nmetadata:\n  - a\n  - b"),
    codes={t: ("metadata.type",) for t in TARGETS},
)
case(
    "FN10",
    "fn-metadata-nested",
    "metadata with nested-map values was accepted; the reference parser "
    "stringifies them instead of reporting",
    ALL_FAIL,
    fm(
        f"name: fn-metadata-nested\ndescription: {GOOD_DESC}\n"
        "metadata:\n  author:\n    name: bob\n    email: b@x.com"
    ),
    codes={t: ("metadata.value-type",) for t in TARGETS},
)
case(
    "FN11",
    "fn-license-list",
    "license as a list was accepted; it is a license name or file reference",
    ALL_FAIL,
    fm(f"name: fn-license-list\ndescription: {GOOD_DESC}\nlicense:\n  - MIT\n  - GPL"),
    codes={t: ("license.type",) for t in TARGETS},
)
case(
    "FN12",
    "fn-allowedtools-int",
    "allowed-tools: 42 was accepted; it is a space-separated string",
    ALL_FAIL,
    fm(f"name: fn-allowedtools-int\ndescription: {GOOD_DESC}\nallowed-tools: 42"),
    codes={t: ("allowed-tools.type",) for t in TARGETS},
)
case(
    "FN13",
    "fn-compat-empty",
    'compatibility: "" was accepted because the check lived inside `if '
    "compatibility:`; the spec says 1-500 characters if provided",
    ALL_FAIL,
    fm(f'name: fn-compat-empty\ndescription: {GOOD_DESC}\ncompatibility: ""'),
    codes={t: ("compatibility.empty",) for t in TARGETS},
)
case(
    "FN14",
    "fn-dup-key",
    "a duplicated description key was accepted; PyYAML silently keeps the last, "
    "so the skill validates against one value and ships the other",
    ALL_FAIL,
    fm(
        "name: fn-dup-key\ndescription: First description, the real one.\n"
        "description: x"
    ),
    codes={t: ("skill-md.parse",) for t in TARGETS},
)
case(
    "FN15",
    "fn-trailing-space-delim",
    "a closing delimiter carrying a trailing space was treated as a delimiter "
    "by the old regex, so the file's real closing delimiter was never required",
    ALL_FAIL,
    f"---\nname: fn-trailing-space-delim\ndescription: {GOOD_DESC}\n--- \n\nbody\n",
    codes={t: ("skill-md.parse",) for t in TARGETS},
)
case(
    "FN16",
    "fn-cr-only",
    "classic-Mac CR-only line endings were repaired by universal-newline "
    "translation and the file validated; no YAML parser or loader reads it that way",
    ALL_FAIL,
    f"---\nname: fn-cr-only\ndescription: {GOOD_DESC}\n---\n\nbody\n",
    newline="\r",
    codes={t: ("skill-md.parse",) for t in TARGETS},
)
case(
    "FN17",
    "fn-latin1",
    "a Latin-1 encoded SKILL.md validated on a cp1252 machine and crashed under "
    "PYTHONUTF8; the verdict depended on the machine's locale",
    ALL_FAIL,
    fm("name: fn-latin1\ndescription: Handles café menus. Use for cafés."),
    encoding="latin-1",
    codes={t: ("skill-md.parse",) for t in TARGETS},
)
case(
    "FN18",
    "fn-inner-hr",
    "a '---' line inside a block scalar truncates the frontmatter, and every "
    "key past it is invisible to every parser -- including the reference "
    "validator, which splits on the first two '---' runs and accepts the file. "
    "R30: reported, but as a warning. The name and description that *are* "
    "parsed are both valid, the oracle passes it, and the same check used to "
    "reject ordinary skills (NEW21-NEW24)",
    ALL_PASS,
    "---\nname: fn-inner-hr\ndescription: |\n  Real description line one.\n"
    "---\n  THIS TEXT IS SILENTLY DROPPED\nlicense: MIT\n---\n\nbody\n",
    codes={t: ("skill-md.ambiguous-delimiter",) for t in TARGETS},
    forbid_codes={t: ("skill-md.parse",) for t in TARGETS},
    note="was ALL_FAIL/skill-md.parse before R30",
)
case(
    "FN19",
    "fn-desc-1024-padded",
    "length was measured after .strip(), so 1024 visible characters plus "
    "padding passed a 1024 cap; the reference validator measures the raw value. "
    "The 1024 itself is the standard's and the API's, not Claude Code's, so the "
    "severity is the target's (R31/FP-2)",
    expectations("pass", "fail", "fail"),
    f'---\nname: fn-desc-1024-padded\ndescription: "{" " * 5}{"x" * 1024}{" " * 5}"\n---\n\nbody\n',
    codes={t: ("description.too-long",) for t in TARGETS},
)
case(
    "FN20",
    "fn-desc-control",
    "a raw control character (vertical tab) inside the description was accepted",
    ALL_FAIL,
    '---\nname: fn-desc-control\ndescription: "Handles\\x0bthings. Use for stuff."\n---\n\nbody\n',
    codes={t: ("description.control-char",) for t in TARGETS},
)

# ------------------------------------------------------ crashes (12 F5)
case(
    "CR01",
    "crash-skillmd-is-dir",
    "SKILL.md existing as a *directory* passed .exists() and then raised "
    "PermissionError out of the read",
    ALL_FAIL,
    None,
    skill_md_is_dir=True,
    codes={t: ("skill-md.missing",) for t in TARGETS},
)
case(
    "CR02",
    "crash-utf16",
    "a UTF-16LE SKILL.md produced a bare UnicodeDecodeError traceback from a "
    "script whose entire job is to print one human-readable line",
    ALL_FAIL,
    f"---\nname: crash-utf16\ndescription: {GOOD_DESC}\n---\n\nbody\n",
    encoding="utf-16",
    codes={t: ("skill-md.parse",) for t in TARGETS},
)

# ------------------------------------------------- false positives (12 F4)
case(
    "FP01",
    "fp-angle-brackets",
    "both specs forbid XML *tags*, not the characters; 'a < b', '->' and "
    "'n > 0' are ordinary description prose and were rejected",
    ALL_PASS,
    fm(
        "name: fp-angle-brackets\ndescription: Compares values where a < b and "
        "n > 0. Use for numeric comparisons."
    ),
    forbid_codes={t: ("description.xml-tag",) for t in TARGETS},
)
case(
    "FP02",
    "fp-bom",
    "a UTF-8 BOM produced 'No YAML frontmatter found' on a file that visibly "
    "begins with ---; Windows editors emit BOMs by default",
    ALL_PASS,
    "﻿" + fm(f"name: fp-bom\ndescription: {GOOD_DESC}"),
)
case(
    "FP03",
    "fp-smart-quotes",
    "curly quotes crashed the validator on a cp1252 console: U+201D encodes to "
    "e2 80 9d and 0x9d is undefined in cp1252",
    ALL_PASS,
    fm(
        "name: fp-smart-quotes\ndescription: Handles “curly quotes” and "
        "em—dashes. Use for typography."
    ),
)
case(
    "FP04",
    "fp-cc-fields",
    "Claude Code's own documented frontmatter was rejected outright; it is "
    "valid there and outside the open standard everywhere else",
    expectations("pass", "fail", "fail"),
    fm(
        f"name: fp-cc-fields\ndescription: {GOOD_DESC}\n"
        "disable-model-invocation: true\nwhen_to_use: when asked\ncontext: fork"
    ),
    codes={"portable": ("unknown-key",), "claude-ai": ("unknown-key",)},
    forbid_codes={"claude-code": ("unknown-key",)},
)
case(
    "FP05",
    "fp-nonascii-1000",
    "a 1000-codepoint CJK description was rejected as '3000 characters' "
    "because cp1252 mojibake made len() count bytes, not characters",
    expectations("pass", "pass", "fail"),
    "---\nname: fp-nonascii-1000\ndescription: " + ("日" * 1000) + "\n---\n\nbody\n",
    codes={"claude-ai": ("description.too-long",)},
    forbid_codes={"claude-code": ("description.too-long",)},
)
case(
    "FP06",
    "fp-desc-emoji",
    "512 astral emoji are 512 codepoints and were rejected as 2048 characters",
    expectations("pass", "pass", "fail"),
    "---\nname: fp-desc-emoji\ndescription: " + ("\U0001f600" * 512) + "\n---\n\nbody\n",
    forbid_codes={"claude-code": ("description.too-long",)},
)
case(
    "FP07",
    "fp-name-padded",
    "a quoted, padded name must strip cleanly; the old hand-rolled parser "
    "stripped whitespace then quotes and never re-stripped, leaking the "
    "padding into downstream directory and file names",
    ALL_PASS,
    f'---\nname: "  fp-name-padded  "\ndescription: {GOOD_DESC}\n---\n\nbody\n',
)
case(
    "FP08",
    "fp-allowed-tools-list",
    "Claude Code accepts a YAML list for allowed-tools; the open standard says "
    "space-separated string",
    expectations("pass", "fail", "fail"),
    fm(
        f"name: fp-allowed-tools-list\ndescription: {GOOD_DESC}\n"
        "allowed-tools:\n  - Read\n  - Grep"
    ),
    codes={"portable": ("allowed-tools.type",)},
    forbid_codes={"claude-code": ("allowed-tools.type",)},
)
case(
    "FP09",
    "fp-dependencies",
    "Anthropic's own claude.ai authoring doc documents `dependencies`; the "
    "validator rejected it, and package_skill refused to package the skill",
    expectations("pass", "fail", "pass"),
    fm(
        f"name: fp-dependencies\ndescription: {GOOD_DESC}\n"
        "dependencies: python>=3.8, pandas>=1.5.0, matplotlib"
    ),
    codes={"portable": ("unknown-key",)},
)

# ------------------------------------------------------ name: unicode vs form
# The name rules split in two. Structural problems -- uppercase, whitespace, a
# path separator, edge or doubled hyphens, a character that is not a letter,
# digit or hyphen -- break the harness and are hard errors on every target. A
# well-formed name that simply is not ASCII is valid, and draws a portability
# warning: the reference validator accepts Unicode names, so rejecting them
# here would be a false rejection, and it would land on the authors these
# scripts have already failed once.
case(
    "I18N01",
    "n-i18n-日本語",
    "a Japanese skill name. The reference validator accepts it "
    "(c.isalnum() or c == '-'), so this validator does too -- with a "
    "portability warning, not an error",
    ALL_PASS,
    fm(f"name: n-i18n-日本語\ndescription: {GOOD_DESC}"),
    codes={t: ("name.non-ascii",) for t in TARGETS},
    forbid_codes={t: ("name.invalid-chars",) for t in TARGETS},
)
case(
    "I18N02",
    "новый-навык",
    "a Cyrillic skill name, same rule",
    ALL_PASS,
    fm(f"name: новый-навык\ndescription: {GOOD_DESC}"),
    codes={t: ("name.non-ascii",) for t in TARGETS},
)
case(
    "I18N03",
    "café-notes",
    "an accented Latin name, same rule",
    ALL_PASS,
    fm(f"name: café-notes\ndescription: {GOOD_DESC}"),
    codes={t: ("name.non-ascii",) for t in TARGETS},
)
case(
    "I18N04",
    "plain-ascii-name",
    "a plain ASCII name draws no portability warning at all",
    ALL_PASS,
    fm(f"name: plain-ascii-name\ndescription: {GOOD_DESC}"),
    forbid_codes={t: ("name.non-ascii",) for t in TARGETS},
)
case(
    "I18N05",
    "name-with-emoji",
    "an emoji is not a letter, a digit or a hyphen, so it is an error on every "
    "target -- the reference validator rejects it too. This is the boundary "
    "between 'not ASCII' (allowed) and 'not an identifier character' (not)",
    ALL_FAIL,
    fm(f'name: "name-with-emoji\U0001f680"\ndescription: {GOOD_DESC}'),
    codes={t: ("name.invalid-chars",) for t in TARGETS},
)

# ------------------------------------------ name: structural rules (errors)
case(
    "NM01",
    "nm-uppercase",
    "uppercase in the name: case-insensitive filesystems resolve it "
    "differently across platforms",
    ALL_FAIL,
    fm(f"name: NM-Uppercase\ndescription: {GOOD_DESC}"),
    codes={t: ("name.uppercase",) for t in TARGETS},
)
case(
    "NM02",
    "nm_underscore",
    "an underscore is not a letter, a digit or a hyphen. The directory matches "
    "the name here so the character rule is the only thing under test",
    ALL_FAIL,
    fm(f"name: nm_underscore\ndescription: {GOOD_DESC}"),
    codes={t: ("name.invalid-chars",) for t in TARGETS},
    forbid_codes={t: ("name.directory-mismatch",) for t in TARGETS},
)
case(
    "NM03",
    "nm name space",
    "whitespace in the name; it becomes a directory component and a "
    "/slash-command, neither of which can hold a space",
    ALL_FAIL,
    fm(f'name: "nm name space"\ndescription: {GOOD_DESC}'),
    codes={t: ("name.whitespace",) for t in TARGETS},
)
case(
    "NM04",
    "nm-path-separator",
    "a path separator splits the name into a path",
    ALL_FAIL,
    fm(f'name: "nm/path"\ndescription: {GOOD_DESC}'),
    codes={t: ("name.path-separator",) for t in TARGETS},
)
case(
    "NM05",
    "nm-lead-hyphen",
    "a leading hyphen",
    ALL_FAIL,
    fm(f'name: "-nm-lead-hyphen"\ndescription: {GOOD_DESC}'),
    codes={t: ("name.hyphen-edge",) for t in TARGETS},
)
case(
    "NM06",
    "nm-double--hyphen",
    "consecutive hyphens",
    ALL_FAIL,
    fm(f"name: nm-double--hyphen\ndescription: {GOOD_DESC}"),
    codes={t: ("name.consecutive-hyphens",) for t in TARGETS},
)
case(
    "NM07",
    "e-fullwidth",
    "a fullwidth-hyphen name. Fullwidth letters are alphanumeric, but "
    "FULLWIDTH HYPHEN-MINUS is not a letter, a digit or an ASCII hyphen, so "
    "the character rule fires -- and the directory comparison is NFC, not "
    "NFKC, so fullwidth text is not silently equated with its ASCII form",
    ALL_FAIL,
    fm(f"name: ｅ－ｆｕｌｌｗｉｄｔｈ\ndescription: {GOOD_DESC}"),
    codes={t: ("name.invalid-chars", "name.directory-mismatch") for t in TARGETS},
)

# ------------------------------------------------------------ new fixtures
case(
    "NEW01",
    "a" * 64,
    "64-character name at the boundary, with a directory that actually matches "
    "it. The research corpus's boundary fixture put the 64-char name in a "
    "directory called n-exactly-64, so it could never satisfy the "
    "directory-match rule its own spec source requires",
    ALL_PASS,
    fm(f"name: {'a' * 64}\ndescription: {GOOD_DESC}"),
)
case(
    "NEW02",
    "b" * 65,
    "65-character name, one over the cap",
    ALL_FAIL,
    fm(f"name: {'b' * 65}\ndescription: {GOOD_DESC}"),
    codes={t: ("name.too-long",) for t in TARGETS},
)
case(
    "NEW03",
    "new-multi-defect",
    "three independent errors in one file. The old validator returned on the "
    "first, turning 'validate after any frontmatter edit' into a whack-a-mole "
    "loop; C6 requires all findings in one pass",
    ALL_FAIL,
    fm(
        f"name: Bad_Name\ndescription: {'z' * 1100}\n"
        "bogus: 1\nalsobogus: 2"
    ),
    codes={
        "claude-code": (
            "name.uppercase",
            "name.invalid-chars",
            "name.directory-mismatch",
            "description.too-long",
        ),
        "portable": (
            "name.uppercase",
            "name.invalid-chars",
            "name.directory-mismatch",
            "description.too-long",
            "unknown-key",
        ),
    },
)
case(
    "NEW04",
    "new-when-to-use-cap",
    "description + ' - ' + when_to_use share a 1536-character cap in Claude "
    "Code's skill listing and are truncated past it, silently. Nothing "
    "previously knew when_to_use existed",
    ALL_FAIL,
    fm(
        f"name: new-when-to-use-cap\ndescription: {'d' * 1000}\n"
        f"when_to_use: {'w' * 600}"
    ),
    codes={"claude-code": ("description.combined-too-long",)},
)
case(
    "NEW05",
    "new-desc-201",
    "201 characters: legal on Claude Code and under the open standard, over "
    "Claude.ai's 200-character cap. The old validator's limit was 5x the limit "
    "on the surface SKILL.md sends users to",
    expectations("pass", "pass", "fail"),
    fm(f"name: new-desc-201\ndescription: {'q' * 201}"),
    codes={
        "claude-code": ("description.claude-ai-cap",),
        "claude-ai": ("description.too-long",),
    },
)
case(
    "NEW06",
    "new-desc-1024",
    "exactly 1024 characters is the inclusive boundary for the portable cap",
    expectations("pass", "pass", "fail"),
    fm(f"name: new-desc-1024\ndescription: {'q' * 1024}"),
    forbid_codes={"claude-code": ("description.too-long",)},
)
case(
    "NEW07",
    "new-desc-1025",
    "1025 characters is one over the standard's cap -- an error where a "
    "primary source states the number, a warning on claude-code where none "
    "does (R31/FP-2)",
    expectations("pass", "fail", "fail"),
    fm(f"name: new-desc-1025\ndescription: {'q' * 1025}"),
    codes={t: ("description.too-long",) for t in TARGETS},
    note="claude-code was 'fail' before R31",
)
case(
    "NEW08",
    "new-desc-xml-tag",
    "a real XML tag in the description is still rejected after the "
    "angle-bracket rule was narrowed to tag-shaped spans",
    ALL_FAIL,
    fm('name: new-desc-xml-tag\ndescription: "Use <thinking> tags. For reasoning."'),
    codes={t: ("description.xml-tag",) for t in TARGETS},
)
case(
    "NEW09",
    "new-body-note-then-hr",
    "guard against the truncated-frontmatter check firing on ordinary prose: a "
    "body line shaped like a key, followed by a markdown horizontal rule, is "
    "legal and common",
    ALL_PASS,
    f"---\nname: new-body-note-then-hr\ndescription: {GOOD_DESC}\n---\n\n"
    "Note: read this first.\n\nWarning: and this.\n\n---\n\nMore body.\n",
    forbid_codes={t: ("skill-md.parse",) for t in TARGETS},
)
case(
    "NEW10",
    "new-body-hr",
    "a plain markdown horizontal rule in the body must not be mistaken for a "
    "delimiter",
    ALL_PASS,
    fm(f"name: new-body-hr\ndescription: {GOOD_DESC}") + "\n---\n\nMore body.\n",
)
case(
    "NEW11",
    "new-lowercase-skill-md",
    "skill.md is *read* -- skills_ref.parser.find_skill_md accepts it, so a "
    "message about the frontmatter beats a refusal to look -- but it is an "
    "error, because package_skill refuses to archive it and zip members are "
    "case-sensitive wherever the archive is unpacked. Validating clean here "
    "and failing there is the R32/PK-1 disagreement",
    ALL_FAIL,
    fm(f"name: new-lowercase-skill-md\ndescription: {GOOD_DESC}"),
    skill_md_name="skill.md",
    codes={t: ("skill-md.filename-case",) for t in TARGETS},
    forbid_codes={t: ("skill-md.missing",) for t in TARGETS},
    note="was ALL_PASS before R32; deliberately stricter than the oracle",
)
case(
    "NEW12",
    "new-crlf-block",
    "CRLF file with a folded block scalar; Windows-authored skills must pass",
    ALL_PASS,
    "---\nname: new-crlf-block\ndescription: >-\n  Extracts text from PDFs.\n"
    "  Use when the user mentions PDFs.\n---\n\nbody\n",
    newline="\r\n",
)
case(
    "NEW13",
    "new-no-skill-md",
    "a directory with no SKILL.md is distinguishable from a path that does not "
    "exist and from a path that is a file",
    ALL_FAIL,
    None,
    extra_files={"README.md": "nothing here"},
    codes={t: ("skill-md.missing",) for t in TARGETS},
)
case(
    "NEW14",
    "new-unclosed",
    "an opening delimiter with no closing one",
    ALL_FAIL,
    f"---\nname: new-unclosed\ndescription: {GOOD_DESC}\n\n# body\n",
    codes={t: ("skill-md.parse",) for t in TARGETS},
)
case(
    "NEW15",
    "new-scalar-fm",
    "frontmatter that parses into a bare scalar rather than a mapping",
    ALL_FAIL,
    "---\njust a string\n---\n\nbody\n",
    codes={t: ("skill-md.parse",) for t in TARGETS},
)
case(
    "NEW16",
    "new-empty-file",
    "a zero-byte SKILL.md",
    ALL_FAIL,
    "",
    codes={t: ("skill-md.parse",) for t in TARGETS},
)
case(
    "NEW17",
    "new-tab-after-colon",
    "a tab between 'name:' and its value. YAML 1.2 permits tab as separation "
    "space, but PyYAML refuses it. Recorded as a known limitation of the "
    "parser dependency, not as a rule of the format -- the research corpus's "
    "version of this case also carried an uppercase, directory-mismatched "
    "name, so it could not have passed for two other reasons",
    ALL_FAIL,
    f"---\nname:\tnew-tab-after-colon\ndescription: {GOOD_DESC}\n---\n\nbody\n",
    codes={t: ("skill-md.parse",) for t in TARGETS},
    note="PyYAML limitation, documented rather than worked around.",
)

# ------------------------------------------------------------------ R30
# The over-correction, in every form that reached a user. A skill that
# documents frontmatter and later uses a horizontal rule was a hard error --
# unvalidatable, unevaluable and unpackageable -- with a message asserting
# something false about the file. A skill-authoring tool is pointed at skills
# that document frontmatter more often than at any other kind.
case(
    "NEW21",
    "new-fenced-frontmatter-example",
    "the FP-1 reproducer: a ```yaml block whose first line is `name:`, "
    "followed by a markdown horizontal rule. The reference validator accepts "
    "it; all three targets used to reject it",
    ALL_PASS,
    f"---\nname: new-fenced-frontmatter-example\ndescription: {GOOD_DESC}\n---\n\n"
    "## Example\n\n```yaml\nname: my-skill\ndescription: Does things\nlicense: MIT\n"
    "```\n\n---\n\n## Next\n",
    forbid_codes={
        t: ("skill-md.parse", "skill-md.ambiguous-delimiter") for t in TARGETS
    },
)
case(
    "NEW22",
    "new-tilde-fence-example",
    "the same, fenced with ~~~ rather than ```, and with a '---' line *inside* "
    "the fence: neither the key nor the rule inside a fence is counted",
    ALL_PASS,
    f"---\nname: new-tilde-fence-example\ndescription: {GOOD_DESC}\n---\n\n"
    "~~~yaml\nlicense: MIT\n---\nname: other\n~~~\n\n---\n\nend\n",
    forbid_codes={
        t: ("skill-md.parse", "skill-md.ambiguous-delimiter") for t in TARGETS
    },
)
case(
    "NEW23",
    "new-indented-frontmatter-example",
    "an indented (four-space) code block holding a frontmatter key and a "
    "'---'. Both scans are anchored at column 0, so indentation excludes a "
    "line by construction rather than by a special case",
    ALL_PASS,
    f"---\nname: new-indented-frontmatter-example\ndescription: {GOOD_DESC}\n---\n\n"
    "Example:\n\n    license: MIT\n    ---\n\n---\n\nend\n",
    forbid_codes={
        t: ("skill-md.parse", "skill-md.ambiguous-delimiter") for t in TARGETS
    },
)
case(
    "NEW24",
    "new-fence-then-real-stray",
    "a fenced example *and* a genuine stray key after it: skipping fences must "
    "not skip the finding",
    ALL_PASS,
    f"---\nname: new-fence-then-real-stray\ndescription: {GOOD_DESC}\n---\n"
    "license: MIT\n\n```yaml\nname: example\n```\n\n---\n\nend\n",
    codes={t: ("skill-md.ambiguous-delimiter",) for t in TARGETS},
)
case(
    "NEW25",
    "new-inner-hr-unknown-key",
    "V19, the residual the recognised-key-only rule could not see: an inner "
    "'---' stranding a *vendor* key. Caught now by the second signal -- the "
    "body continues the frontmatter with no blank line -- rather than by the "
    "key set",
    ALL_PASS,
    "---\nname: new-inner-hr-unknown-key\ndescription: |\n  Real line.\n---\n"
    "  hidden\nsome-vendor-key: v\n---\n\nbody\n",
    codes={t: ("skill-md.ambiguous-delimiter",) for t in TARGETS},
    note="closes the one residual V2 recorded against this check",
)
case(
    "NEW26",
    "new-prose-key-then-hr",
    "'model: opus is the default here.' as ordinary body prose, separated from "
    "the delimiter by a blank line, followed by a horizontal rule. Warned "
    "about (the key is a real one) but never an error, on any target",
    ALL_PASS,
    f"---\nname: new-prose-key-then-hr\ndescription: {GOOD_DESC}\n---\n\n"
    "model: opus is the default here.\n\n---\n\nMore body.\n",
    codes={t: ("skill-md.ambiguous-delimiter",) for t in TARGETS},
)

# ------------------------------------------------------------------ R31
# Rules the claude-code profile asserted that no Claude Code document states.
case(
    "NEW27",
    "new-cc-desc-1200",
    "a 1200-character description: over the standard's 1024, under nothing "
    "Claude Code documents, and not even truncated there (the documented "
    "1,536 applies to description + ' - ' + when_to_use)",
    expectations("pass", "fail", "fail"),
    fm(f"name: new-cc-desc-1200\ndescription: {'x' * 1200}"),
    codes={t: ("description.too-long",) for t in TARGETS},
)
case(
    "NEW28",
    "new-cc-display-label",
    "`name` used as a display label in a directory of a different name, which "
    "code.claude.com documents as the behaviour of a personal or project skill",
    expectations("pass", "fail", "fail"),
    fm(f"name: some-display-label\ndescription: {GOOD_DESC}"),
    codes={t: ("name.directory-mismatch",) for t in TARGETS},
)
case(
    "NEW29",
    "new-no-name",
    "no `name` key at all. Claude Code documents this as legal (it defaults "
    "from the directory) -- but this toolchain builds workspace directories "
    "and archive members from the name, and both other surfaces require it, so "
    "it stays an error whose message says whose requirement it is",
    ALL_FAIL,
    f"---\ndescription: {GOOD_DESC}\n---\n\nbody\n",
    codes={t: ("name.missing",) for t in TARGETS},
    note="deliberate exception to the FP-3 demotion; see quick_validate's docstring",
)


def build(destination: Path) -> Path:
    """Materialize every fixture under *destination*. Returns *destination*."""
    destination = Path(destination)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    for item in CASES:
        directory = destination / item.dirname
        directory.mkdir(parents=True, exist_ok=True)

        if item.skill_md_is_dir:
            (directory / item.skill_md_name).mkdir()
        elif item.skill_md is not None:
            text = item.skill_md.replace("\n", item.newline)
            (directory / item.skill_md_name).write_bytes(text.encode(item.encoding))

        for relative, body in item.extra_files.items():
            path = directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")

    return destination


def main(argv: Optional[list[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: python -m tests.validator_fixtures <destination-dir>",
              file=sys.stderr)
        return 2
    target = build(Path(args[0]))
    print(f"built {len(CASES)} fixtures in {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
