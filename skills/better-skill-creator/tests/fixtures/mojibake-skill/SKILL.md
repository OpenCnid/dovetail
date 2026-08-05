---
name: mojibake-skill
description: Fixture whose non-ASCII characters all have cp1252-defined UTF-8 bytes — an em dash, an arrow →, and café — so a platform-codec read does not raise. It silently returns mojibake instead, which is the failure this fixture exists to catch.
---

# Mojibake fixture

café — naïve triage → escalation
