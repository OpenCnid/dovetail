---
name: hostile-skill
description: Fixture skill for the packager tests. Proves secrets, VCS data, virtualenvs and symlinks stay out of the distributable archive.
---

# Hostile skill

A fixture. The builder in `tests/test_package_skill.py` copies this tree into a
temporary workspace and decorates it with everything a packager must refuse to
ship: a `.env`, a `.git/`, a `.venv/`, a `.claude/`, prior build output, and a
symlink pointing outside the tree.

## Contents that must survive packaging

- `references/notes.md`
- `scripts/tool.py`
- `scripts/run.sh`
- `assets/nested/evals/keeper.md` (nested `evals/` is not the root `evals/`)
- `.claude-plugin/plugin.json` (the one allowlisted dot-entry)
- `outputs/` (an empty directory that is part of the skill's contract)
