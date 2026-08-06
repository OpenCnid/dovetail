# License

The prose in this repository — the README, this file, and the scripts — is
licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**:
https://creativecommons.org/licenses/by/4.0/

(c) OpenCnid Labs.

## What this license does not cover

**The skills under `skills/` carry their own licenses**, each in its own
directory, and nothing in this file relicenses any of them. That placement is
deliberate rather than tidy: `scripts/install.sh` copies a skill directory and
nothing above it, so a skill leaning on this file would ship with no license at
all. Check the license in the directory you are actually using — they are not
all the same. `better-skill-creator` is Apache-2.0 and carries a `NOTICE`
beside it that travels with the skill.

Until `0.3.0` this section said the repository contained no skill text of its
own, because every skill was then a git submodule pinned to its own repository.
That stopped being true when the skills moved in here. `docs/provenance.md`
records where each one came from and the commit it arrived at.

The **prompt-engineering toolkit and the hypershot technique** are the work of
Matthew Murphy (https://github.com/gusthemole), published as the Lexideck prompt
engineering curriculum. The **SPARK axes** are from arXiv:2508.01581. The
**Claude Code mechanics** these skills describe are Anthropic, PBC product
behaviour, documented at https://code.claude.com/docs.

This project is not affiliated with, endorsed by, or supported by Anthropic.