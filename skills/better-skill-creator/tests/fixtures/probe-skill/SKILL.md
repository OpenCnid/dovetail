---
name: probe-skill
description: Pure-ASCII fixture skill used by the trigger-eval tests. Use this skill when a test needs a SKILL.md that parse_skill_md can read identically under any locale codec.
---

# Probe skill

Body kept ASCII on purpose: this fixture is the control for the encoding
checks, so it must round-trip through cp1252 and utf-8 alike.
