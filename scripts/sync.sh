#!/usr/bin/env bash
#
# sync.sh — move every pin to the current tip of its source repository's main,
# and report exactly what moved.
#
# The pack holds no copies. Each skill is a submodule pinned to a commit, so
# "the pack drifted" is not a thing that can happen quietly — a pin either
# points where it pointed or the diff says otherwise. This script is how you
# move pins on purpose.
#
# It does not commit. Read the report, then commit the pin bumps yourself.
#
# Usage:
#   bash scripts/sync.sh            # advance every pin to origin/main
#   bash scripts/sync.sh --check    # report drift, change nothing
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

git submodule update --init --quiet

moved=0
while read -r path; do
  name="$(basename "$path")"
  before="$(git -C "$path" rev-parse --short HEAD)"

  git -C "$path" fetch --quiet origin main
  after="$(git -C "$path" rev-parse --short origin/main)"

  if [ "$before" = "$after" ]; then
    printf '  current  %-22s %s\n' "$name" "$before"
    continue
  fi

  moved=$((moved + 1))
  count="$(git -C "$path" rev-list --count "$before..origin/main" 2>/dev/null || echo '?')"

  if [ "$CHECK" -eq 1 ]; then
    printf '  BEHIND   %-22s %s -> %s  (%s commit(s))\n' "$name" "$before" "$after" "$count"
  else
    git -C "$path" checkout --quiet origin/main
    printf '  moved    %-22s %s -> %s  (%s commit(s))\n' "$name" "$before" "$after" "$count"
  fi
done < <(git config --file .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}' | sort)

echo
if [ "$moved" -eq 0 ]; then
  echo "Every pin is current."
  exit 0
fi

if [ "$CHECK" -eq 1 ]; then
  echo "$moved pin(s) behind. Run without --check to advance them."
  exit 1
fi

echo "$moved pin(s) moved. Nothing is committed yet."
echo
echo "Read what actually changed before you commit it:"
echo "    git diff --submodule=log"
echo
echo "A pin bump ships new instructions to everyone who installs this pack."
echo "That is the whole point of the pack, and the reason to look first."
