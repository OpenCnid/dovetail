#!/usr/bin/env bash
#
# lint-shell.sh — check every shell script this pack ships.
#
# Worth having because two of these run somewhere the author is not: install.sh
# executes on a stranger's machine, and hooks/session-start executes inside
# every session as a hook, where a syntax error surfaces as a silently missing
# directive rather than as an error.
#
# Two passes, because they need different things:
#
#   bash -n     parse only. Always available, so this is the pass that gates.
#   shellcheck  semantic lint — unquoted expansions, dead assignments. Reports
#               only when installed; absence is stated rather than skipped
#               quietly, so a clean run cannot mean "nothing was checked".
#
# Usage:
#   bash scripts/lint-shell.sh
#   bash scripts/lint-shell.sh --strict   # missing shellcheck becomes a failure

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STRICT=0
[ "${1:-}" = "--strict" ] && STRICT=1

# Tracked, ours, and actually shell. Selection is by shebang or known extension
# rather than by directory: hooks/ holds hooks.json too, and a glob that assumes
# every file beside a script is a script reports a JSON parse error as a shell
# syntax error. Excluding vendor/ is deliberate — those are other repositories
# and lint there belongs to them.
FILES=()
while IFS= read -r f; do
  case "$f" in
    *.sh|*.cmd) FILES+=("$f") ;;
    *) head -c 2 "$f" 2>/dev/null | grep -q '^#!' && FILES+=("$f") ;;
  esac
done < <(git ls-files 'scripts/*' 'hooks/*' | grep -v '^vendor/')

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "no shell scripts found — the selection is wrong, not the repository" >&2
  exit 2
fi

fail=0

echo "parse (bash -n)"
for f in "${FILES[@]}"; do
  # run-hook.cmd is a polyglot: bash sees the batch block as a quoted heredoc.
  # It parses as bash by construction, and that is exactly what to verify.
  if bash -n "$f" 2>/dev/null; then
    printf '  ok    %s\n' "$f"
  else
    printf '  FAIL  %s\n' "$f"
    bash -n "$f" 2>&1 | sed 's/^/        /'
    fail=1
  fi
done

echo
if command -v shellcheck >/dev/null 2>&1; then
  echo "shellcheck ($(shellcheck --version | awk '/version:/{print $2}'))"
  for f in "${FILES[@]}"; do
    if shellcheck -S warning "$f" >/dev/null 2>&1; then
      printf '  ok    %s\n' "$f"
    else
      printf '  WARN  %s\n' "$f"
      shellcheck -S warning "$f" 2>&1 | sed 's/^/        /' | head -20
      fail=1
    fi
  done
else
  echo "shellcheck: not installed — the semantic pass did NOT run."
  echo "  Install it (https://shellcheck.net) or accept that only parsing was checked."
  [ "$STRICT" -eq 1 ] && fail=1
fi

echo
[ "$fail" -eq 0 ] && echo "Shell lint passed." || echo "Shell lint FAILED."
exit "$fail"
