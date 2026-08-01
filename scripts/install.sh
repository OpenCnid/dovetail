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
# Seven sources keep the skill at .claude/skills/<name>/ so that a copy of that
# directory carries the skill and nothing else. better-skill-creator is the one
# exception and it is a real one: its scripts/, references/, agents/ and tests/
# are part of the skill, so its whole repository is the skill directory.
#
# Every path is spelled out rather than globbed. A glob that silently matches
# nothing installs a hollow pack that looks fine.
SKILLS=(
  "prompt-engineering:vendor/prompt-engineering/.claude/skills/prompt-engineering"
  "hypershot-protocol:vendor/hypershot-protocol/.claude/skills/hypershot-protocol"
  "subagent-composition:vendor/subagent-composition/.claude/skills/subagent-composition"
  "judge-composition:vendor/judge-composition/.claude/skills/judge-composition"
  "self-play:vendor/self-play/.claude/skills/self-play"
  "better-skill-creator:vendor/better-skill-creator"
  "spark-steering:vendor/spark-steering/.claude/skills/spark-steering"
)

# ---------------------------------------------------------------- submodules
missing=0
for entry in "${SKILLS[@]}"; do
  [ -f "$ROOT/${entry#*:}/SKILL.md" ] || missing=1
done

if [ "$missing" -eq 1 ]; then
  echo "Submodules are not checked out. Fetching them now."
  echo "(A plain 'git clone' does not fetch submodules; use --recurse-submodules"
  echo " next time, or run 'git submodule update --init' yourself.)"
  echo
  git -C "$ROOT" submodule update --init --depth 1
  echo
fi

for entry in "${SKILLS[@]}"; do
  if [ ! -f "$ROOT/${entry#*:}/SKILL.md" ]; then
    echo "error: ${entry%%:*} has no SKILL.md at ${entry#*:} even after fetching." >&2
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
