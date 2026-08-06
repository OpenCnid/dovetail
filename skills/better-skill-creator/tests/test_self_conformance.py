"""This skill is an instance of the category it produces, so it can be held to its own rules.

Every check here enforces something SKILL.md or a reference file tells authors to do. They exist
because the failures they catch are all silent: a SKILL.md that grew past the compaction slice still
loads and works in short sessions, and only goes wrong later, in long ones, with no error anywhere.
The point of automating them is that "remember to check" is not a mechanism.
"""

import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

# The skill ships at <repo>/skills/better-skill-creator/ so Claude Code's plugin loader
# auto-discovers it via the skills/*/SKILL.md glob. The repository README sits two levels
# above the skill root, and is the only thing up there this file reads.
#
# LICENSE.txt and NOTICE are NOT repository furniture, which this comment used to claim.
# install.sh copies the skill directory and nothing above it, so an Apache-2.0 NOTICE
# parked at the repository root ships to nobody -- see AGENTS.md, "Working here". They
# live in the skill directory and are checked there.
REPO_ROOT = SKILL_ROOT.parent.parent

# Claude Code re-attaches roughly the first 19,900 CHARACTERS of an invoked skill after
# compaction. It is a raw slice: it cuts mid-sentence, with no marker, and the model cannot
# tell it happened. Characters, not bytes -- `wc -c` over-reports on non-ASCII content.
COMPACTION_SLICE_CHARS = 19_900

# Descriptions share a listing budget of ~1% of the context window. The runtime truncates
# description + when_to_use at 1,536 combined; the upload surfaces reject past 1,024.
DESCRIPTION_HARD_CAP = 1_536

# SKILL.md's own advice: give a reference file a table of contents past ~100 lines, since the
# model decides whether to open it from a one-line pointer and needs to know what is inside.
TOC_REQUIRED_OVER_LINES = 100


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class SkillMdFitsTheCompactionSlice(unittest.TestCase):
    def test_whole_file_survives_compaction(self):
        text = read(SKILL_ROOT / "SKILL.md")
        n = len(text)
        self.assertLess(
            n,
            COMPACTION_SLICE_CHARS,
            f"SKILL.md is {n} characters, {n - COMPACTION_SLICE_CHARS} over the "
            f"{COMPACTION_SLICE_CHARS}-character compaction slice.\n"
            "Past that point, content is present on the first invocation and silently gone "
            "after the conversation compacts -- which is exactly when a long session needs it.\n"
            "Move material into references/ rather than trimming prose: reference files load on "
            "demand, are never truncated, and cost nothing until read.",
        )

    def test_the_load_bearing_half_is_early(self):
        """Only a prefix survives, so ordering is a design decision, not a style choice."""
        text = read(SKILL_ROOT / "SKILL.md")
        cut = text[:COMPACTION_SLICE_CHARS]
        for heading in ("## Improving the skill", "## Testing it against reality"):
            self.assertIn(
                heading,
                cut,
                f"{heading!r} falls outside the surviving prefix. The improvement loop is the "
                "part of this document that has to be present late in a long session.",
            )


class FrontmatterObeysItsOwnRules(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_ROOT / "SKILL.md")

    def test_description_is_quoted(self):
        """An unquoted colon-space parses as a nested mapping; the body then loads with empty
        metadata, so /better-skill-creator works while auto-triggering silently never fires."""
        line = next(l for l in self.text.splitlines() if l.startswith("description:"))
        value = line.split(":", 1)[1].strip()
        self.assertTrue(
            value.startswith('"') or value.startswith("'"),
            "SKILL.md's own description is unquoted. This file tells authors to quote theirs.",
        )

    def test_description_within_runtime_cap(self):
        m = re.search(r'^description:\s*"(.*?)"\s*$', self.text, re.M | re.S)
        self.assertIsNotNone(m, "could not parse the description as a quoted scalar")
        n = len(m.group(1))
        self.assertLessEqual(
            n,
            DESCRIPTION_HARD_CAP,
            f"description is {n} characters, over the {DESCRIPTION_HARD_CAP} runtime cap. "
            "Past it the listing entry is truncated, and the truncation is invisible.",
        )

    def test_install_directory_matches_frontmatter_name(self):
        """The rule is about the INSTALLED directory, not the checkout directory.

        This project ships as `better-skill-creator`, and the repository, the directory the
        README tells you to install it as, and the frontmatter name are all that same string.
        Holding them in agreement is what makes the skill answer to the name its own file
        states, since Claude Code takes the invocation name from the directory and treats the
        frontmatter as display-only. A clone sitting in a differently-named directory is still
        fine -- Claude Code only reads the directory name once the skill is installed under a
        skills/ path.

        What must hold is that the README tells you the directory to install it AS, and that the
        name it tells you matches the frontmatter. Otherwise the skill answers to a name its own
        documentation does not state, and `package_skill` refuses to build an archive.
        """
        m = re.search(r"^name:\s*(\S+)\s*$", self.text, re.M)
        self.assertIsNotNone(m)
        name = m.group(1)

        readme = read(REPO_ROOT / "README.md")
        self.assertRegex(
            readme,
            rf"skills/{re.escape(name)}\b",
            f"README must show the install target as a directory named {name!r} -- "
            "Claude Code takes the invocation name from the directory, and packaging "
            "refuses when the directory and frontmatter name disagree.",
        )

        if SKILL_ROOT.name != name:
            # Not a failure, but the person running from a checkout should know why
            # `python -m scripts.package_skill .` will refuse here.
            print(
                f"\n  note: checkout directory is {SKILL_ROOT.name!r}, skill name is {name!r}. "
                f"Package from a copy named {name!r}, per README.",
            )


class EveryPointerResolves(unittest.TestCase):
    """A reference this file names but does not ship is a dead end the model follows at runtime."""

    def test_referenced_paths_exist(self):
        text = read(SKILL_ROOT / "SKILL.md")
        missing = [
            p
            for p in sorted(set(re.findall(r"(?:references|agents|scripts|eval-viewer|assets)/[A-Za-z0-9_.-]+", text)))
            if not (SKILL_ROOT / p).exists()
        ]
        self.assertEqual(missing, [], f"SKILL.md points at files that do not exist: {missing}")

    def test_referenced_modules_exist(self):
        text = read(SKILL_ROOT / "SKILL.md")
        missing = [
            m
            for m in sorted(set(re.findall(r"scripts\.[a-z_]+", text)))
            if not (SKILL_ROOT / "scripts" / f"{m.split('.', 1)[1]}.py").exists()
        ]
        self.assertEqual(missing, [], f"SKILL.md names modules that do not exist: {missing}")

    def test_no_pointer_to_a_document_that_does_not_ship(self):
        """The guard above covers SKILL.md only, which is how 176 citations to a
        contract file and a research tree survived into shipped bytes -- 81 of
        them into the archive, two into prompts a sub-agent reads at runtime.
        A dead pointer is worse in those files than in SKILL.md, not better:
        a cold sub-agent cannot ask what it meant."""
        patterns = {
            # Case-insensitive and hyphen-tolerant: the sweep that cleared these
            # found `Contract C7` and `contract-C7` alongside the lowercase form,
            # so a pattern matching only one spelling would let a regression back.
            "contract C<n>": re.compile(r"contract[ -]C\d+", re.I),
        }
        offenders = []
        for path in sorted(SKILL_ROOT.rglob("*")):
            if not path.is_file() or path.suffix not in {".md", ".py", ".html"}:
                continue
            rel = path.relative_to(SKILL_ROOT).as_posix()
            # Scoped to what ships. package_skill's ROOT_EXCLUDE_DIRS drops these,
            # so a citation inside them never reaches a reader of the archive.
            if rel.startswith(("tests/", "evals/")):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for label, rx in patterns.items():
                hits = sorted(set(rx.findall(text)))
                if hits:
                    offenders.append(f"{rel}: {label} -> {hits[:3]}")
        self.assertEqual(
            offenders, [],
            "citations to material this repository does not ship:\n  "
            + "\n  ".join(offenders),
        )

    @unittest.skip(
        "Open decision, not a passing check. Sixteen shipping citations name a "
        "research/ corpus that does not ship, in package_skill.py, "
        "quick_validate.py, run_eval.py and utils.py. Unlike the contract "
        "citations, these were a documented choice -- test_render_seats.py says "
        "the tree is absent and skips rather than failing -- but the choice was "
        "executed as 'make the tests tolerate absence', never as 'fix the "
        "citations'. Publishing the corpus was considered and declined: an audit "
        "found verbatim decompiled vendor source, an unreleased vendor feature, "
        "and unreported vendor security defects in it. The remaining fix is to "
        "reword the sixteen so they do not read as followable paths. Skipped "
        "rather than deleted so the open item stays visible in the suite."
    )
    def test_no_pointer_to_a_research_tree_that_does_not_ship(self):
        raise AssertionError("unreachable while skipped")

    def test_long_references_have_a_table_of_contents(self):
        offenders = []
        for path in sorted((SKILL_ROOT / "references").glob("*.md")):
            text = read(path)
            if text.count("\n") + 1 > TOC_REQUIRED_OVER_LINES and "## Contents" not in text:
                offenders.append(path.name)
        self.assertEqual(
            offenders,
            [],
            f"reference files over {TOC_REQUIRED_OVER_LINES} lines with no '## Contents' "
            f"section: {offenders}. SKILL.md tells authors to add one so a model can decide "
            "what to read without loading the whole file.",
        )


class ProvenanceIsIntact(unittest.TestCase):
    """Apache-2.0 obligations, and the honesty of the derivation claim."""

    def test_license_and_notice_present(self):
        # In the skill directory, not the repository root: install.sh copies this
        # directory alone, so a NOTICE left above it never reaches the person the
        # Apache-2.0 attribution term is owed to.
        for name in ("LICENSE.txt", "NOTICE"):
            self.assertTrue(
                (SKILL_ROOT / name).is_file(),
                f"{name} is missing from the skill directory. Restore it here rather than at "
                "the repository root: install.sh copies this directory alone, so a licence "
                "left above it ships to nobody and the installed skill carries no Apache-2.0 "
                "terms or attribution at all.",
            )

    def test_notice_names_the_upstream_and_disclaims_affiliation(self):
        notice = read(SKILL_ROOT / "NOTICE")
        self.assertIn("anthropics/skills", notice)
        self.assertIn("Apache", notice)
        self.assertRegex(
            notice,
            r"(?i)not affiliated",
            "NOTICE must state plainly that this is not affiliated with or endorsed by Anthropic.",
        )


if __name__ == "__main__":
    unittest.main()
