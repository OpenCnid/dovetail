#!/usr/bin/env bash
#
# install.sh — copy every skill in this pack into a Claude Code skills directory.
#
# This is the fallback path, for when you want the skills installed directly
# rather than loaded as a plugin. The plugin route is in the README and needs no
# script; this one exists because it works everywhere and depends on nothing.
#
# Usage:
#   bash scripts/install.sh                 # into ~/.claude/skills
#   bash scripts/install.sh --project       # into ./.claude/skills
#   bash scripts/install.sh --force         # overwrite skills that already exist
#   bash scripts/install.sh --dry-run       # print what would happen, change nothing
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"
FORCE=0
DRY=0

for arg in "$@"; do
  case "$arg" in
    --project) DEST="$(pwd)/.claude/skills" ;;
    --force)   FORCE=1 ;;
    --dry-run) DRY=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

# Each entry is "<name>:<path to the directory holding SKILL.md>".
#
# Every skill lives in this repository now. There are no submodules, no pins,
# and no fetch step: what you cloned is what installs. Each directory is exactly
# what should land in ~/.claude/skills/<name>/, licence included -- which is why
# every one carries its own LICENSE, rather than leaning on the root file that
# does not travel with a copied directory.
#
# using-dovetail is the entry point, naming the companion rule and the two
# disable-model-invocation skills. On the plugin route a SessionStart hook
# injects it; installed directly there is no pack to carry that hook, so it
# lands as an ordinary skill and the user reads it.
#
# Spelled out rather than globbed, even though plugin.json now relies on the
# skills/*/SKILL.md glob. The list is the thing test-skills.sh counts against,
# so a skill added to disk but to neither file is a failure rather than a
# silent partial install.
SKILLS=(
  "using-dovetail:skills/using-dovetail"
  "prompt-engineering:skills/prompt-engineering"
  "hypershot-protocol:skills/hypershot-protocol"
  "subagent-composition:skills/subagent-composition"
  "judge-composition:skills/judge-composition"
  "self-play:skills/self-play"
  "better-skill-creator:skills/better-skill-creator"
  "upsum:skills/upsum"
  "spark-steering:skills/spark-steering"
)

# ---------------------------------------------------------------- completeness
# Nothing to fetch any more, so a missing SKILL.md is a broken checkout rather
# than an un-run step, and there is no recovery to attempt on the user's behalf.
for entry in "${SKILLS[@]}"; do
  if [ ! -f "$ROOT/${entry#*:}/SKILL.md" ]; then
    echo "error: ${entry%%:*} has no SKILL.md at ${entry#*:}." >&2
    echo "       The pack is incomplete; do not treat a partial install as a full one." >&2
    exit 1
  fi
done

# ---------------------------------------------------------------- install
[ "$DRY" -eq 1 ] || mkdir -p "$DEST"
echo "destination: $DEST"
echo

installed=0; skipped=0
for entry in "${SKILLS[@]}"; do
  name="${entry%%:*}"
  src="$ROOT/${entry#*:}"
  target="$DEST/$name"

  if [ -e "$target" ] && [ "$FORCE" -eq 0 ]; then
    printf '  skip     %-22s (exists — pass --force to replace)\n' "$name"
    skipped=$((skipped + 1))
    continue
  fi

  if [ "$DRY" -eq 1 ]; then
    printf '  would    %-22s <- %s\n' "$name" "${entry#*:}"
  else
    rm -rf "$target"
    cp -r "$src" "$target"
    # Belt and braces: no skill directory holds a .git today, but version-control
    # metadata in an installed skill makes the directory look tracked while every
    # git command in it addresses a repository that is not there.
    rm -rf "$target/.git"
    printf '  install  %-22s <- %s\n' "$name" "${entry#*:}"
  fi
  installed=$((installed + 1))
done

echo
if [ "$DRY" -eq 1 ]; then
  echo "dry run: $installed would be installed, $skipped skipped. Nothing changed."
else
  echo "$installed installed, $skipped skipped."
  echo "Claude Code picks up skills live — no restart needed."
fi

if [ "$skipped" -gt 0 ]; then
  echo
  echo "Skipped skills were left exactly as they were. If one of those is a copy"
  echo "you have edited, keep it: this pack is a distribution snapshot, and your"
  echo "edited copy may be ahead of it."
fi
