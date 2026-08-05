"""Shared utilities for better-skill-creator scripts.

Derived from ``anthropics/skills``, ``skills/skill-creator/scripts/utils.py``
(Apache-2.0 -- see LICENSE.txt).

Three invariants shape this module.

**One severity table.** ``WORKSPACE_CONDITIONS`` and
:func:`classify_workspace_condition` are the severity table for workspace
conditions, written down once. ``scripts.preflight``,
``scripts.validate_grading`` and ``scripts.aggregate_benchmark`` all import
them; none of the three decides a severity for itself, because when they did,
one flat-layout workspace drew three different verdicts.

**Explicit encoding.** Every read here names its encoding. ``SKILL.md`` is
decoded from bytes as ``utf-8-sig``, never through ``Path.read_text()``'s
locale-dependent default: on a stock Windows install that default is cp1252,
where a UTF-8 ``SKILL.md`` either raises (bytes 0x81/0x8D/0x8F/0x90/0x9D are
undefined in cp1252 -- one closing curly quote is enough) or, worse, decodes
into mojibake nobody can see. Decoding from bytes also puts newline handling
under our control: CRLF is normalised, while a lone-CR (classic-Mac) file is
*not* silently repaired by universal-newline translation into something YAML
will happily parse.

**F14 (research/12-validator-packager.md).** This package used to contain two
disagreeing frontmatter parsers -- a hand-rolled line scanner here and
``yaml.safe_load`` in ``scripts.quick_validate`` -- so what the validator
blessed was not necessarily what ``run_eval``/``run_loop`` would use. There is
now a single extraction path (:func:`split_frontmatter` / :func:`load_frontmatter`)
and both callers go through it.

The old scanner did not merely disagree, it *corrupted*: it stripped whitespace
and then quotes without re-stripping (so ``name: "  x  "`` leaked its padding
into directory and file names downstream), it collapsed block-scalar newlines
into spaces, it left backslash escapes undecoded, and it recognised only four
of YAML's block indicators -- ``|+``, ``>+``, ``|2`` and an indicator followed
by a comment all fell through to the literal branch. Every one of those reached
the caller as an ordinary string with no signal. :func:`parse_skill_md` now
raises :class:`SkillMdError` rather than hand back a value it cannot vouch for.

**R30 (research/V2-verification.md FP-1).** The inner-``---`` check used to be a
hard error raised out of :func:`split_frontmatter`, and it scanned the body
line-by-line with no idea what a fenced code block was. So a SKILL.md that
*documents* frontmatter -- a `````yaml`` block whose first line is
``name:`` -- and then uses a markdown horizontal rule was rejected outright, by
this module and therefore by ``quick_validate``, ``run_eval``, ``run_loop``,
``improve_description`` and ``package_skill`` alike, with a message asserting
that the file's ``name`` was "invisible to everything". None of that was true,
the reference validator accepts such files, and a skill-authoring tool is
unusually likely to be pointed at skills that document frontmatter. A false
rejection carrying a confident wrong explanation is worse than the silent
truncation it replaced.

The detection is now :func:`find_frontmatter_ambiguity`: it skips fenced code
blocks, it *returns* rather than raises, and its message names the ambiguity
instead of asserting truncation. ``quick_validate`` reports it as a warning.
Indented code blocks need no special case -- both :data:`_KEY_LINE` and the
delimiter comparison are anchored at column 0, so an indented line can match
neither.

The original defect stays closed on substance: the frontmatter block still ends
at the *first* whole-line ``---`` after the opening one, so nothing past it is
ever parsed as settings, and a recognised key stranded there is still reported.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:  # PyYAML is the package's one non-stdlib dependency (research/01 F13).
    import yaml
except ImportError:  # pragma: no cover - exercised only on a machine without it
    yaml = None  # type: ignore[assignment]

_YAML_MISSING = (
    "PyYAML is required to parse SKILL.md frontmatter and is not installed. "
    "Install it with:  python -m pip install pyyaml"
)

#: The frontmatter delimiter, matched as a *whole line* and exactly.
#: A line of ``--- `` (trailing space) is deliberately not a delimiter: the
#: old regex ``^---\n(.*?)\n---`` accepted it, which meant a file whose real
#: closing delimiter never appeared still validated.
FRONTMATTER_DELIMITER = "---"

#: Accepted filenames, in preference order. ``skill.md`` is *found* because the
#: reference validator's ``find_skill_md`` finds it (skills_ref/parser.py), so
#: refusing to read one would be a worse message than reading it and saying
#: what is wrong. It is not *endorsed*: ``scripts.quick_validate`` reports a
#: lowercase spelling as an error, because zip members are case-sensitive on
#: every platform and ``scripts.package_skill`` refuses to build the archive
#: (research/V2-verification.md PK-1).
SKILL_MD_NAMES = ("SKILL.md", "skill.md")

#: The Agent Skills open standard's closed field set (agentskills.io/specification).
#: ``scripts.quick_validate`` owns the wider, per-target tables; this set exists
#: here only so :func:`find_frontmatter_ambiguity` has a conservative default.
SPEC_FIELDS = frozenset(
    {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
)

#: A ``key:`` line, anchored at column 0. The anchor is load-bearing: it is why
#: indented code blocks need no separate handling in the ambiguity scan.
_KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*)[ \t]*:(?:[ \t]|$)")

#: A markdown code fence: three or more backticks or tildes, indented at most
#: three spaces, optionally followed by an info string. CommonMark 4.5.
_FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


# --------------------------------------------------------------------------
# One severity table -- severity belongs to the condition, not the component
# --------------------------------------------------------------------------
#
# Verification pointed ``scripts.preflight``, ``scripts.validate_grading`` and
# ``scripts.aggregate_benchmark`` at one flat-layout workspace and got back
# ERROR/exit 1, WARNING/exit 0, and WARNING plus a correct benchmark. Three
# parties, one condition, three answers -- the defect class this package was
# rewritten to eliminate, reintroduced because each component computed the
# judgment for itself and was therefore free to choose differently.
#
# ``WORKSPACE_CONDITIONS`` is that severity table, written down exactly once.
# Every component imports it; no component re-derives it. What a component
# *does* with a severity remains its own business -- ``preflight`` refuses to
# green-light a workspace the readers merely warn about, because it is a
# pre-spend gate and stricter is its job -- but no component may disagree about
# what the condition *is*.
#
# Every component also prints :func:`condition_tag`'s token verbatim, so "do
# the three agree?" is answerable by diffing their output rather than by
# reading three implementations. ``tests/test_condition_classifier.py`` does
# exactly that.
#
# Adding a condition changes what all three components report, so add its row
# to ``WORKSPACE_CONDITIONS`` below and nowhere else. Never classify a
# condition inside a component.

SEVERITY_OK = "ok"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

#: Workspace condition identifiers. These strings are printed by all three
#: components and are matched by tooling and tests; do not rename casually.
CANONICAL_LAYOUT_OK = "canonical_layout"
LEGACY_FLAT_LAYOUT = "legacy_flat_layout"
FLAT_AND_RUN_DIRS = "flat_and_run_dirs"
UNDISCOVERABLE_GRADING = "undiscoverable_grading"
ZERO_RUNS = "zero_runs"
SCHEMA_INVALID = "schema_invalid"
UNPAIRED_EVALS = "unpaired_evals"

#: condition -> (severity, one-sentence statement, rationale). The statement is
#: shared so that three components describing one condition produce one
#: sentence rather than three paraphrases that drift apart.
WORKSPACE_CONDITIONS = {
    CANONICAL_LAYOUT_OK: (
        SEVERITY_OK,
        "the workspace is in the canonical <config>/run-<K>/ layout",
        "-",
    ),
    LEGACY_FLAT_LAYOUT: (
        SEVERITY_WARNING,
        "legacy flat layout: grading.json sits directly in the configuration "
        "directory, with no run-<K> level. The canonical layout requires a run "
        "level even for a single run; readers normalize it to run-1 and "
        "aggregate it correctly",
        "it aggregates correctly; refusing would be wrong",
    ),
    FLAT_AND_RUN_DIRS: (
        SEVERITY_WARNING,
        "a configuration holds both a flat grading.json and a run-<K>/ "
        "directory, so one of the two is not read",
        "ambiguous, but resolvable",
    ),
    UNDISCOVERABLE_GRADING: (
        SEVERITY_ERROR,
        "grading data is present but the aggregator cannot discover it",
        "the spend is already sunk and invisible",
    ),
    ZERO_RUNS: (
        SEVERITY_ERROR,
        "no runs are discoverable, so there is nothing to aggregate",
        "nothing to report",
    ),
    SCHEMA_INVALID: (
        SEVERITY_ERROR,
        "a grading.json or timing.json failed schema validation, so it is "
        "excluded from aggregation and listed in exclusions",
        "-",
    ),
    UNPAIRED_EVALS: (
        SEVERITY_ERROR,
        # Both forms of the same defect. The eval-level form is the original
        # wording ("evals present in one config and not its counterpart"); the
        # run-level form is that defect in different clothes, found when a
        # near-miss field name excluded one run and the delta moved from +0.50
        # to +0.38 at exit 0 rather than declining to answer. One condition and
        # one severity, because the rationale - a delta over data the two sides
        # do not share is not a comparison - covers both without amendment.
        "an eval's runs are not paired across the two configurations: it ran "
        "in one and not in the other, or exclusions left the two sides with "
        "different surviving runs",
        "a delta over unpaired evals is not a comparison",
    ),
}


class UnknownWorkspaceCondition(KeyError):
    """A component asked for a severity the shared table does not define.

    Raised rather than defaulted. A default here would be a component deciding
    a severity locally, which is the exact failure the shared table closes.
    """


def classify_workspace_condition(condition: str) -> dict:
    """The workspace-condition severity table -- the one implementation of it.

    Returns ``{"condition", "severity", "statement", "rationale", "tag"}``.
    Raises :class:`UnknownWorkspaceCondition` for anything not in the table: a
    new condition gets a row in ``WORKSPACE_CONDITIONS`` above, and is never
    classified inside a component.
    """
    try:
        severity, statement, rationale = WORKSPACE_CONDITIONS[condition]
    except KeyError:
        raise UnknownWorkspaceCondition(
            f"{condition!r} is not in the shared severity table. Add a row to "
            f"WORKSPACE_CONDITIONS in scripts/utils.py first; a component must "
            f"not decide a severity locally, because three components deciding "
            f"separately is how one workspace drew three different verdicts. "
            f"Known conditions: "
            f"{', '.join(sorted(WORKSPACE_CONDITIONS))}"
        ) from None
    return {
        "condition": condition,
        "severity": severity,
        "statement": statement,
        "rationale": rationale,
        "tag": f"C12:{condition}={severity}",
    }


def condition_severity(condition: str) -> str:
    """The shared-table severity of *condition*."""
    return classify_workspace_condition(condition)["severity"]


def condition_tag(condition: str) -> str:
    """``C12:<condition>=<severity>`` -- the token every component prints.

    One greppable token per condition means a human, or a test, can diff the
    three components' verdicts without reading three implementations.
    """
    return classify_workspace_condition(condition)["tag"]


def condition_line(condition: str, detail: str = "") -> str:
    """The shared sentence for *condition*, tagged, with optional detail."""
    info = classify_workspace_condition(condition)
    line = f"[{info['tag']}] {info['statement']}"
    if detail:
        line = f"{line}. {detail}"
    return line


class SkillMdError(ValueError):
    """A SKILL.md could not be read or parsed.

    Subclasses :class:`ValueError` so callers written against the previous
    ``parse_skill_md`` contract keep working.
    """


def configure_console() -> None:
    """Make stdout/stderr safe for non-ASCII output on every platform.

    Windows consoles default to a legacy codepage (cp1252 on most machines).
    Printing an emoji or any character outside that codepage raises
    UnicodeEncodeError and kills the process -- so a decorative marker in a
    status message becomes a hard crash for every Windows user, typically at
    the least convenient moment.

    Switching the streams to UTF-8 with errors="replace" keeps the nice output
    on terminals that can render it and degrades to a placeholder character
    where they can't, instead of aborting. Call this at the top of any entry
    point that prints non-ASCII.
    """
    for stream in (sys.stdout, sys.stderr):
        # reconfigure() exists on TextIOWrapper (3.7+); streams may be
        # redirected to something else entirely, so failing here is fine.
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def find_skill_md(skill_path: Path) -> Optional[Path]:
    """Return the SKILL.md inside *skill_path*, or ``None``.

    ``SKILL.md`` wins over ``skill.md`` when both exist. ``is_file()`` rather
    than ``exists()``: a *directory* named ``SKILL.md`` used to pass the
    existence test and then raise ``PermissionError``/``IsADirectoryError`` out
    of the read, which is not a message.
    """
    skill_path = Path(skill_path)
    for name in SKILL_MD_NAMES:
        candidate = skill_path / name
        if candidate.is_file():
            return candidate
    return None


def actual_skill_md_name(skill_path: Path) -> Optional[str]:
    """Return the SKILL.md's spelling *as stored on disk*, or ``None``.

    :func:`find_skill_md` cannot answer this and must not be asked to. It
    probes ``skill_path / "SKILL.md"``, and on a case-insensitive filesystem --
    NTFS, and APFS as shipped -- that probe succeeds against a file actually
    named ``skill.md``. The mismatch then surfaces far downstream:
    ``scripts.package_skill`` walks the real directory entries, does not
    recognise ``skill.md``, and refuses to write the archive with a message
    about SKILL.md being "excluded" (research/V2-verification.md PK-1). One
    directory listing here is the difference between that and a rename.

    Reading the entries is the only reliable way: ``os.listdir`` returns the
    stored names, ``Path.is_file()`` returns the filesystem's opinion.
    """
    skill_path = Path(skill_path)
    wanted = {name.lower() for name in SKILL_MD_NAMES}
    try:
        found = sorted(
            entry.name
            for entry in skill_path.iterdir()
            if entry.name.lower() in wanted and entry.is_file()
        )
    except OSError:  # not a directory, or unreadable -- callers report that
        return None
    if not found:
        return None
    for preferred in SKILL_MD_NAMES:
        if preferred in found:
            return preferred
    return found[0]


def read_text_utf8(path: Path) -> str:
    """Read *path* as UTF-8, tolerating a BOM, normalising CRLF to LF.

    Raises :class:`SkillMdError` on an unreadable file or on bytes that are not
    UTF-8 -- both of which previously escaped as a bare traceback from a script
    whose entire job is to print one human-readable line.

    Reading bytes and decoding explicitly (rather than ``read_text``) is what
    makes the newline policy ours. ``\\r\\n`` becomes ``\\n``; a lone ``\\r``
    is left alone so a classic-Mac file is reported as having no frontmatter
    instead of being silently repaired by universal-newline translation.
    """
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:  # includes IsADirectoryError / PermissionError
        raise SkillMdError(f"could not read {path.name}: {exc}") from exc
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        # Note: UnicodeDecodeError is a UnicodeError/ValueError, NOT an
        # OSError -- an ``except (json.JSONDecodeError, OSError)`` handler
        # elsewhere will not catch it.
        raise SkillMdError(
            f"{path.name} is not saved as UTF-8 text ({exc.reason} at byte "
            f"{exc.start}), so it cannot be read. Re-save the file as UTF-8: in "
            f"VS Code, click the encoding shown in the status bar, choose 'Save "
            f"with Encoding', then 'UTF-8'. A UTF-8 byte-order mark is fine; "
            f"UTF-16 and Latin-1/Windows-1252 are not."
        ) from exc
    return text.replace("\r\n", "\n")


@dataclass(frozen=True)
class FrontmatterAmbiguity:
    """A body line that might have been meant as frontmatter.

    ``key_line``, ``rule_line`` and ``close_line`` are 1-based line numbers in
    the file. ``recognised`` records whether ``key`` is one of the frontmatter
    keys the caller passed in, which is the difference between "this is very
    likely truncated frontmatter" and "this region merely looks like it".
    """

    key: str
    key_line: int
    rule_line: int
    close_line: int
    recognised: bool

    @property
    def message(self) -> str:
        """A description of the ambiguity, offering both readings.

        Deliberately *not* an assertion that the file is truncated. The
        previous wording ("'name' is invisible to everything") was false for
        every SKILL.md that documents frontmatter, which is most of them in a
        skill-authoring context.
        """
        which = (
            f"'{self.key}:', which is also a settings key"
            if self.recognised
            else f"'{self.key}:', which is shaped like a settings key"
        )
        return (
            f"SKILL.md line {self.key_line} begins with {which}, and line "
            f"{self.rule_line} is another line of exactly three hyphens. Only the "
            f"text between the *first* pair of --- lines (here, lines 1 to "
            f"{self.close_line}) is read as the settings block, so if '{self.key}' "
            f"was meant to be a setting it is not being read as one -- move it "
            f"above line {self.close_line}, or quote the value that contains the "
            f"stray ---. If line {self.key_line} is ordinary body text and line "
            f"{self.rule_line} is a horizontal rule, this file is fine and you can "
            f"ignore this. Lines inside ``` or ~~~ fenced code blocks are not "
            f"counted, so documenting frontmatter in an example block is safe."
        )


def _scan_body_for_stranded_key(
    body_lines: list[str], keys: frozenset[str]
) -> Optional[tuple[str, int, int, bool]]:
    """Find a key-shaped line sitting between the closing ``---`` and a later one.

    Returns ``(key, key_index, rule_index, recognised)`` -- indices are into
    *body_lines* -- or ``None`` when the body holds no later ``---`` line at
    all, in which case there is nothing ambiguous: everything below the closing
    delimiter is plainly body.

    Two independent signals qualify a line, because the residual left by the
    previous version (research/V2-verification.md V19) was that it *only* had
    the first one:

    1. The key is one the caller recognises (``license``, ``when_to_use``, ...).
       A stranded ``license: MIT`` is worth mentioning whatever the surrounding
       text looks like.
    2. The body continues the frontmatter without a break -- its very first
       line is indented (a block scalar's continuation) or is itself a ``key:``
       line. That is the shape a stray ``---`` leaves behind, and it catches a
       stranded *vendor* key that signal 1 cannot see. Ordinary prose is
       separated from the closing delimiter by a blank line, so it does not
       qualify.

    Fenced code blocks are skipped entirely, for both the key scan and the
    terminating ``---``: a fenced example is the single most likely thing to
    contain both. Indented code blocks need no handling -- ``_KEY_LINE`` and
    the delimiter comparison are both anchored at column 0.
    """
    continues_frontmatter = bool(body_lines) and _looks_like_yaml_continuation(
        body_lines[0]
    )
    fence: Optional[tuple[str, int]] = None
    hit: Optional[tuple[str, int, bool]] = None

    for index, line in enumerate(body_lines):
        fence_match = _FENCE_LINE.match(line)
        marker = fence_match.group(1) if fence_match else None
        if fence is not None:
            if (
                marker is not None
                and marker[0] == fence[0]
                and len(marker) >= fence[1]
                # A closing fence carries no info string (CommonMark 4.5).
                and not fence_match.group(2).strip()
            ):
                fence = None
            continue
        if marker is not None:
            fence = (marker[0], len(marker))
            continue

        if line == FRONTMATTER_DELIMITER:
            # The suspect region ends here. Report only if something in it
            # qualified; a bare horizontal rule on its own is not a finding.
            return None if hit is None else (hit[0], hit[1], index, hit[2])

        if hit is None:
            key_match = _KEY_LINE.match(line)
            if key_match:
                key = key_match.group(1)
                if key in keys:
                    hit = (key, index, True)
                elif continues_frontmatter:
                    hit = (key, index, False)

    return None  # no later delimiter -> this is just a body


def _looks_like_yaml_continuation(line: str) -> bool:
    """True if *line* could be the next line of the frontmatter block."""
    if not line.strip():
        return False
    if line[:1] in (" ", "\t"):
        return True
    return bool(_KEY_LINE.match(line))


def find_frontmatter_ambiguity(
    content: str, *, known_keys: Optional[Iterable[str]] = None
) -> Optional[FrontmatterAmbiguity]:
    """Report a body region that may be frontmatter stranded past a stray ``---``.

    Returns ``None`` for a file with no frontmatter block at all -- that is a
    different problem, and :func:`split_frontmatter` reports it.

    This never raises and never changes what is parsed. It exists so
    ``scripts.quick_validate`` can *warn*: the condition is genuinely
    ambiguous. ``skills_ref.parser.parse_frontmatter`` does
    ``content.split("---", 2)``, so the oracle truncates at the same place,
    says nothing about it, and passes the file whenever the keys that survive
    are valid -- and a hard rejection here rejects ordinary skills that merely
    document frontmatter.
    """
    keys = frozenset(known_keys) if known_keys is not None else SPEC_FIELDS
    lines = content.split("\n")
    if not lines or lines[0] != FRONTMATTER_DELIMITER:
        return None
    close_index = _find_closing_delimiter(lines)
    if close_index is None:
        return None

    found = _scan_body_for_stranded_key(lines[close_index + 1 :], keys)
    if found is None:
        return None
    key, key_offset, rule_offset, recognised = found
    return FrontmatterAmbiguity(
        key=key,
        key_line=close_index + 2 + key_offset,
        rule_line=close_index + 2 + rule_offset,
        close_line=close_index + 1,
        recognised=recognised,
    )


def _find_closing_delimiter(lines: list[str]) -> Optional[int]:
    for index in range(1, len(lines)):
        if lines[index] == FRONTMATTER_DELIMITER:
            return index
    return None


def split_frontmatter(content: str) -> tuple[str, str]:
    """Split *content* into ``(frontmatter_text, body)``.

    The delimiters are matched as whole lines, exactly. The previous
    implementation used ``re.match(r'^---\\n(.*?)\\n---', ..., re.DOTALL)``,
    whose non-greedy ``.*?`` stopped at the first ``\\n---`` anywhere in the
    file -- including one that is not a whole line, so ``----`` or ``--- x``
    terminated the block and everything after it was silently invisible to
    every check downstream.

    Raises :class:`SkillMdError` if the block is missing or unterminated. It
    does **not** raise for a suspicious inner ``---``: see
    :func:`find_frontmatter_ambiguity` and R30 in the module docstring.
    """
    lines = content.split("\n")

    if not lines or lines[0] != FRONTMATTER_DELIMITER:
        raise SkillMdError(
            "SKILL.md is missing its settings block. The file has to begin with a "
            "line containing exactly three hyphens (---) and nothing else, with "
            "nothing at all before it -- no blank line, no spaces, no text. That "
            "block, between two --- lines, is what holds `name` and `description` "
            "(it is called the YAML frontmatter). If the block looks like it is "
            "already there, check for a leading blank line or for line endings "
            "saved in the old Mac style"
        )

    close_index = _find_closing_delimiter(lines)

    if close_index is None:
        raise SkillMdError(
            "SKILL.md's settings block is never closed. After the opening --- "
            "line there has to be a second line containing exactly three hyphens "
            "and nothing else. A line like '--- ' with a trailing space does not "
            "count, and neither does '----'"
        )

    return "\n".join(lines[1:close_index]), "\n".join(lines[close_index + 1 :])


def _build_strict_loader():
    """A SafeLoader that refuses duplicate mapping keys.

    ``yaml.safe_load`` keeps the *last* of a duplicated key and says nothing,
    so a SKILL.md carrying two ``description:`` lines validates against one
    value and ships the other. strictyaml (which the reference validator uses)
    raises ``DuplicateKeysDisallowed``; this reproduces that behaviour on
    PyYAML.
    """
    if yaml is None:  # pragma: no cover
        return None

    class _StrictLoader(yaml.SafeLoader):
        pass

    def _no_duplicate_keys(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=True)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    None,
                    None,
                    f"duplicate key {key!r} in frontmatter",
                    key_node.start_mark,
                )
            mapping[key] = loader.construct_object(value_node, deep=True)
        return mapping

    _StrictLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys
    )
    return _StrictLoader


_STRICT_LOADER = _build_strict_loader()


def load_frontmatter(content: str) -> tuple[dict, str]:
    """Parse *content* into ``(frontmatter_mapping, body)``.

    Raises :class:`SkillMdError` for every failure mode: missing or
    unterminated frontmatter, invalid YAML, duplicate keys, and frontmatter
    that parses into something other than a mapping.

    The ``known_keys`` parameter this used to take is gone with R30: the check
    it fed no longer decides whether the file parses, so passing a key set to a
    *parse* function was misleading. Callers that want the check call
    :func:`find_frontmatter_ambiguity` directly.
    """
    frontmatter_text, body = split_frontmatter(content)

    if yaml is None or _STRICT_LOADER is None:  # pragma: no cover
        raise SkillMdError(_YAML_MISSING)

    try:
        data = yaml.load(frontmatter_text, Loader=_STRICT_LOADER)
    except yaml.YAMLError as exc:
        detail = " ".join(str(exc).split())
        raise SkillMdError(
            f"SKILL.md's settings block is not valid YAML: {detail}. The usual "
            f"cause is a value containing a colon, a '#' or a '[' -- wrap the "
            f"whole value in double quotes, or start it with |- on its own line "
            f"and indent the text below"
        ) from exc

    if data is None:
        raise SkillMdError(
            "SKILL.md's settings block is empty. It has to contain at least a "
            "`name:` line and a `description:` line between the two --- lines"
        )
    if not isinstance(data, dict):
        raise SkillMdError(
            "SKILL.md's settings block has to be a list of `key: value` lines; "
            f"this one reads as a single {type(data).__name__} instead"
        )
    return data, body


def read_skill_md(skill_path: Path) -> tuple[Path, str]:
    """Locate and read the SKILL.md under *skill_path*.

    Raises :class:`SkillMdError` with a message that distinguishes "no such
    path", "not a directory" and "no SKILL.md in it" -- the previous code
    reported all three as ``SKILL.md not found``.
    """
    skill_path = Path(skill_path)
    if not skill_path.exists():
        raise SkillMdError(f"path does not exist: {skill_path}")
    if not skill_path.is_dir():
        raise SkillMdError(f"not a directory: {skill_path}")
    skill_md = find_skill_md(skill_path)
    if skill_md is None:
        raise SkillMdError(
            f"no SKILL.md file in {skill_path}. Every skill is a folder with a "
            f"SKILL.md inside it (skill.md is accepted too). A *folder* named "
            f"SKILL.md does not count"
        )
    return skill_md, read_text_utf8(skill_md)


def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning ``(name, description, full_content)``.

    ``name`` and ``description`` are the YAML values, whitespace-stripped.
    ``full_content`` is the whole decoded file (CRLF normalised to LF).

    Raises :class:`SkillMdError` -- a :class:`ValueError` -- when the file
    cannot be read as UTF-8, has no well-formed frontmatter block, contains
    invalid or duplicated YAML, or is missing a non-empty string ``name`` or
    ``description``. Every consumer of this function (``run_eval``,
    ``run_loop``, ``improve_description``) puts these values into prompts,
    filenames and directory names; a wrong value that arrives silently is
    strictly worse than an exception, which is what the previous hand-rolled
    parser produced.

    Validation beyond "the returned values are trustworthy" is *not* done here
    -- kebab-case, length caps, directory match and the per-target key sets all
    live in :mod:`scripts.quick_validate`, which is target-aware and this is
    not.
    """
    skill_md, content = read_skill_md(Path(skill_path))
    data, _body = load_frontmatter(content)

    if "name" not in data:
        raise SkillMdError(
            f"{skill_md.name}'s settings block has no `name`. Add a line like "
            f"`name: my-skill-name` between the two --- lines; it has to match "
            f"the folder the skill lives in"
        )
    name = data["name"]
    if not isinstance(name, str):
        raise SkillMdError(
            f"{skill_md.name}'s `name` has to be text, but YAML read it as a "
            f"{type(name).__name__}. Put double quotes around the value -- "
            f"`name: \"{name}\"` -- so it is read as text"
        )
    if not name.strip():
        raise SkillMdError(
            f"{skill_md.name}'s `name` is empty. It has to be the skill's name, "
            f"matching the folder the skill lives in"
        )

    if "description" not in data:
        raise SkillMdError(
            f"{skill_md.name}'s settings block has no `description`. Add a line "
            f"like `description: What this does and when to use it.` between the "
            f"two --- lines -- it is the only thing the model reads when deciding "
            f"whether to use the skill"
        )
    description = data["description"]
    if not isinstance(description, str):
        raise SkillMdError(
            f"{skill_md.name}'s `description` has to be text, but YAML read it as "
            f"a {type(description).__name__}. Put double quotes around the whole "
            f"value so it is read as text"
        )
    if not description.strip():
        raise SkillMdError(
            f"{skill_md.name}'s `description` is empty. It is the only thing the "
            f"model reads when deciding whether to use the skill, so an empty one "
            f"means the skill installs and then never triggers"
        )

    # Strip both, matching the reference implementation's read_properties().
    # Note the deliberate asymmetry with quick_validate, which measures the
    # description's length *unstripped*: the reference validator's length check
    # is on the raw value, so padding counts against the cap even though it is
    # not part of the string a caller gets back.
    return name.strip(), description.strip(), content
