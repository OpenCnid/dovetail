#!/usr/bin/env bash
#
# install-codex.sh — copy every Dovetail skill into a Codex skill location.
#
# Repository users need no install: Codex discovers the source through the
# checked-in .agents/skills bridge. This fallback makes an independent user or
# project copy while leaving that bridge and every Claude Code path untouched.
#
# Usage:
#   bash scripts/install-codex.sh                 # into ~/.agents/skills
#   bash scripts/install-codex.sh --project       # into ./.agents/skills
#   bash scripts/install-codex.sh --force         # overwrite existing skills
#   bash scripts/install-codex.sh --dry-run       # print what would happen

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
DEST="$HOME/.agents/skills"
PROJECT=0
FORCE=0
DRY=0

for arg in "$@"; do
  case "$arg" in
    --project) DEST="$(pwd -P)/.agents/skills"; PROJECT=1 ;;
    --force)   FORCE=1 ;;
    --dry-run) DRY=1 ;;
    *) echo "usage: bash scripts/install-codex.sh [--project] [--force] [--dry-run]" >&2; exit 2 ;;
  esac
done

# Running --project from this checkout would replace the checked-in links with
# copies of their own source. Codex already discovers those links; refuse rather
# than turn a convenience flag into source divergence. Existing destination
# components must also resolve exactly inside the selected project: this blocks
# symlinks, Windows junctions, and other reparse redirects before any copy or
# --force removal can leave the project tree.
if [ "$PROJECT" -eq 1 ]; then
  AGENTS_DIR="$(dirname "$DEST")"
  if [ "$DEST" = "$ROOT/.agents/skills" ]; then
    echo "error: --project from the Dovetail checkout would overwrite .agents/skills." >&2
    echo "       Run Codex here without installing, or invoke this script from the target project." >&2
    exit 2
  fi
  if [ -L "$AGENTS_DIR" ]; then
    echo "error: --project refuses a symlinked .agents destination." >&2
    echo "       Use a real directory inside the target project." >&2
    exit 2
  fi
  if [ -e "$AGENTS_DIR" ]; then
    if [ ! -d "$AGENTS_DIR" ] || [ "$(cd "$AGENTS_DIR" && pwd -P)" != "$AGENTS_DIR" ]; then
      echo "error: --project refuses a redirected .agents destination." >&2
      echo "       Use a real directory inside the target project." >&2
      exit 2
    fi
  fi
  if [ -L "$DEST" ]; then
    echo "error: --project refuses a symlinked .agents/skills destination." >&2
    echo "       Use a real directory inside the target project." >&2
    exit 2
  fi
  if [ -e "$DEST" ]; then
    if [ ! -d "$DEST" ] || [ "$(cd "$DEST" && pwd -P)" != "$DEST" ]; then
      echo "error: --project refuses a redirected .agents/skills destination." >&2
      echo "       Use a real directory inside the target project." >&2
      exit 2
    fi
  fi
fi

shopt -s nullglob
SOURCES=("$ROOT"/skills/*)
if [ "${#SOURCES[@]}" -eq 0 ]; then
  echo "error: no source skills found under skills/." >&2
  exit 1
fi

for source in "${SOURCES[@]}"; do
  if [ ! -f "$source/SKILL.md" ]; then
    echo "error: ${source#"$ROOT/"} has no SKILL.md." >&2
    exit 1
  fi
done

if [ "$DRY" -eq 0 ]; then
  mkdir -p "$DEST"
fi

echo "destination: $DEST"
echo

installed=0
skipped=0
for source in "${SOURCES[@]}"; do
  name="${source#"$ROOT/skills/"}"
  target="$DEST/$name"

  if [ -e "$target" ] || [ -L "$target" ]; then
    if [ "$FORCE" -eq 0 ]; then
      printf '  skip     %-22s (exists — pass --force to replace)\n' "$name"
      skipped=$((skipped + 1))
      continue
    fi
  fi

  if [ "$DRY" -eq 1 ]; then
    printf '  would    %-22s <- skills/%s\n' "$name" "$name"
  else
    rm -rf "$target"
    cp -R "$source" "$target"
    rm -rf "$target/.git"
    printf '  install  %-22s <- skills/%s\n' "$name" "$name"
  fi
  installed=$((installed + 1))
done

echo
if [ "$DRY" -eq 1 ]; then
  echo "dry run: $installed would be installed, $skipped skipped. Nothing changed."
else
  echo "$installed installed, $skipped skipped."
  echo "Restart Codex if the copied skills do not appear immediately."
fi
