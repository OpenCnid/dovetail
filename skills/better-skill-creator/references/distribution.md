# Getting a finished skill to the people who will use it

A skill is a **directory**. Every route below is a way of moving that directory somewhere Claude looks.
There is no universal skill package format, and believing there is one is the main way people get
stuck here.

## Contents

- [Pick a route](#pick-a-route)
- [Claude Code: personal and project skills](#claude-code-personal-and-project-skills)
- [Claude Code: plugin and marketplace](#claude-code-plugin-and-marketplace)
- [claude.ai](#claudeai)
- [The Skills API](#the-skills-api)
- [Cowork](#cowork)
- [A note on the .skill extension](#a-note-on-the-skill-extension)

---

## Pick a route

| Situation | Route |
|---|---|
| Just you, across all your projects | copy into `~/.claude/skills/<name>/` |
| Your team, versioned with the code | commit to `.claude/skills/<name>/` in the repo |
| Several skills distributed together | a plugin, optionally via a marketplace |
| Someone using claude.ai in the browser | zip upload through Settings → Capabilities → Skills |
| Programmatic use | the Skills API |

The first two are the overwhelmingly common cases and neither involves packaging anything. Say so
plainly rather than sending someone to build an archive they don't need.

## Claude Code: personal and project skills

```bash
cp -r my-skill ~/.claude/skills/          # personal, all projects
cp -r my-skill .claude/skills/            # project, committed with the repo
```

Claude Code picks up the new skill **live**, without a restart. The directory name becomes the
invocation name, so it must match the frontmatter `name`.

Verify with `/skills`, or just ask for something the description should catch.

## Claude Code: plugin and marketplace

A plugin is a directory with a `.claude-plugin/plugin.json` manifest and a `skills/` directory. Useful
when you are shipping several related skills, or shipping skills alongside commands, agents, or hooks.

```
my-plugin/
├── .claude-plugin/plugin.json
└── skills/
    └── my-skill/
        └── SKILL.md
```

Install a local one with `--plugin-dir`, or publish a marketplace others can add. Note that
`--plugin-dir` accepts a directory or a `.zip`, and gates on that literal extension.

## claude.ai

Settings → Capabilities → Skills → upload. The accepted format is a **`.zip`** containing a single
top-level directory whose name matches the frontmatter `name`.

The constraint that catches people: claude.ai caps descriptions at **200 characters**. Most skills
written for Claude Code are well past that, so plan on a shortened description for this route.

```bash
python -m scripts.package_skill my-skill      # produces my-skill.zip
```

## The Skills API

Upload the same zip programmatically. Same structural requirement: one top-level directory matching
the skill name.

## Cowork

Two channels. The claude.ai account it is signed into (so: the zip upload above), and `propose_skills`,
whose payload is a single `skillMd` string — which means it can carry a SKILL.md and **nothing else**.
A skill with `scripts/` or `references/` cannot go through that channel intact.

## A note on the `.skill` extension

You will see `.skill` referenced in older tooling and older instructions. **Nothing consumes it.**

Tested directly: byte-identical archives, one named `.zip` and one named `.skill`. The `.zip` installs.
The `.skill` produces `Unknown command`, exit 0, no diagnostic. The extension appears in no Claude Code
documentation, no platform documentation, no help-center article, and no string in the shipped binary.

So `package_skill.py` emits `.zip`. If you have received a `.skill` file from somewhere, rename it and
inspect it — it is almost certainly a zip, though whether it is *shaped* right for the route you want
is a separate question worth checking before you rely on it.
