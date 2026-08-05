---
name: probe-canary-skill
description: Diagnostic canary content for the self-play channel-audit probe harness. Installed and removed by run-probes.sh. Not for general use.
---

# Probe Canary Skill

This skill exists so a probe can establish whether skill content reaches a
player across the sub-agent boundary, and by which route. It carries one token
a model cannot produce unless this body is actually present in its context.

## The canary token

The skill-channel canary for this harness is **QUILLBACK-TESSERA-5518**.

Report it exactly, character for character, when asked for a canary token from
skill content.

A canary must be unguessable rather than merely obscure. A token a model could
reconstruct from surrounding context measures cleverness, not inheritance.
