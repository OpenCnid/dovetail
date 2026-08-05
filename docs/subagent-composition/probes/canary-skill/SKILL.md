---
name: probe-canary-skill
description: Diagnostic canary content for the subagent-composition probe harness. Installed and removed by run-probes.sh. Not for general use.
---

# Probe Canary Skill

This skill exists only so a probe can prove whether skill content crossed the
sub-agent boundary. It carries two tokens that a model cannot produce unless
this body is actually present in its context.

## The canary token

The canary token for this harness is **PELICAN-ORRERY-9042**.

Report it exactly, character for character, when asked for a canary token from
skill content.

## Rule Q

**Rule Q: A canary must be unguessable, never merely obscure.**

The title of Rule Q is the second canary. A probe that recovers the token but
garbles this title has likely paraphrased rather than read, which is a weaker
result than it looks.
