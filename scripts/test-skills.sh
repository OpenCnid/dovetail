#!/usr/bin/env bash
#
# test-skills.sh — check that every skill this pack ships actually loads.
#
# Two layers, because they fail differently:
#
#   static  every declared path has a SKILL.md whose frontmatter name matches
#           its directory. Catches the hollow-pack failure: a path that moved
#           upstream, or a manifest entry nobody updated.
#   live    installs the pack into a throwaway CLAUDE_CONFIG_DIR, invokes each
#           skill, and greps the session transcript for a canary taken from the
#           skill's own body. Catches the failure static checks cannot see —
#           the skill resolves but its body never reaches the session.
#
# "Throwaway" holds only where the shell propagates CLAUDE_CONFIG_DIR to the
# CLI. Where it does not — a POSIX shell invoking a Windows claude.exe, which is
# what WSL does — the variable never arrives, the CLI falls back to the real
# ~/.claude, and the marketplace registration and every session transcript land
# in the operator's own config. That happens silently and exits 0, so the live
# layer proves the redirect took effect before writing anything, and exits 2
# without running when it cannot.
#
# The live layer needs no login and costs no API turn — invoking a skill expands
# harness-side. It spends no money; what it can cost, absent the check below, is
# a write to the operator's real configuration.
#
# Usage:
#   bash scripts/test-skills.sh              # static + live
#   bash scripts/test-skills.sh --static     # static only, no claude needed

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STATIC_ONLY=0
[ "${1:-}" = "--static" ] && STATIC_ONLY=1

# Keep in step with SKILLS in install.sh and skills in plugin.json.
SKILLS=(
  "prompt-engineering:skills/prompt-engineering"
  "hypershot-protocol:skills/hypershot-protocol"
  "subagent-composition:skills/subagent-composition"
  "judge-composition:skills/judge-composition"
  "self-play:skills/self-play"
  "better-skill-creator:skills/better-skill-creator"
  "upsum:skills/upsum"
  "spark-steering:skills/spark-steering"
)

fail=0
note() { printf '  %-8s %-22s %s\n' "$1" "$2" "${3:-}"; }

# ------------------------------------------------------------------ static
echo "static"
for entry in "${SKILLS[@]}"; do
  name="${entry%%:*}"; path="${entry#*:}"

  if [ ! -f "$path/SKILL.md" ]; then
    note FAIL "$name" "no SKILL.md at $path"; fail=1; continue
  fi

  # frontmatter name must match the directory the skill installs as, or the
  # skill loads under a name nothing references
  declared="$(awk '/^name:/{print $2; exit}' "$path/SKILL.md")"
  if [ "$declared" != "$name" ]; then
    note FAIL "$name" "frontmatter says name: ${declared:-<missing>}"; fail=1; continue
  fi

  if ! grep -q '^description:' "$path/SKILL.md"; then
    note FAIL "$name" "no description — the skill will not trigger"; fail=1; continue
  fi

  # A bang immediately followed by a backtick is command substitution, and a
  # skill body is preprocessed before it reaches the session. The sequence runs
  # at render and the load aborts — no body, no error, no clue. It shipped once
  # inside a sentence warning about it.
  if grep -q '!`' "$path/SKILL.md"; then
    note FAIL "$name" "bang-backtick in body — the skill will load as nothing"; fail=1; continue
  fi

  note ok "$name"
done

# every declared path must also appear in both manifests, or one route ships a
# skill the other does not
for entry in "${SKILLS[@]}"; do
  path="${entry#*:}"; name="${entry%%:*}"
  # plugin.json no longer enumerates skills -- it relies on the skills/*/SKILL.md
  # glob, the way superpowers does. So the check is that the glob actually reaches
  # this skill, not that a manifest names it.
  [ -f "$path/SKILL.md" ] && case "$path" in skills/*) ;; *) note FAIL "$name" "outside skills/, so auto-discovery cannot see it"; fail=1 ;; esac
  grep -q "$path" scripts/install.sh || { note FAIL "$name" "missing from install.sh"; fail=1; }
done

# The glob is now what plugin.json ships with, so a skill on disk that this list
# forgets would install silently and never be tested. Count both.
on_disk="$(ls -d skills/*/ 2>/dev/null | wc -l)"
if [ "$on_disk" -ne "${#SKILLS[@]}" ]; then
  note FAIL "inventory" "skills/ holds $on_disk directories, this list names ${#SKILLS[@]}"
  fail=1
fi

if [ "$STATIC_ONLY" -eq 1 ]; then
  echo
  [ "$fail" -eq 0 ] && echo "static checks passed." || echo "static checks FAILED."
  exit "$fail"
fi

# -------------------------------------------------------------------- live
command -v claude >/dev/null 2>&1 || { echo; echo "claude not on PATH — run with --static"; exit 2; }

echo
echo "live"

# The EXIT trap is what removes the directory: bash runs it on the way out of a
# signal death too, so TERM, HUP and a group-delivered INT are already covered
# by it alone. The signal traps exist for the exit status, and they disarm on
# entry — arming INT/TERM/HUP alongside EXIT without disarming fires the handler
# twice and, because a signal arriving during a foreground command is deferred
# until that command returns, resumes the script afterwards against a $CFG that
# no longer exists, reporting success. Re-raising rather than `exit 1` keeps a
# Ctrl-C distinguishable from `exit "$fail"` below.
#
# CFG is set empty first because the handler runs under `set -u`, and a cleanup
# that cannot finish warns instead of failing: a bare failing command in an EXIT
# trap rewrites the status to 1, which would read as a failed skill. A native
# Windows process holding a handle inside the tree is enough to make rm fail,
# and claude.exe writes there.
CFG=""
cleanup() {
  trap - EXIT INT TERM HUP
  [ -n "$CFG" ] || return 0
  rm -rf "$CFG" || {
    printf 'warning: could not remove temp config dir %s\n' "$CFG" >&2
    printf '         something still holds a handle inside it; remove it by hand\n' >&2
  }
  return 0
}
on_signal() { cleanup; trap - "$1"; kill -"$1" "$$"; }
trap cleanup EXIT
# Spelled out rather than looped: a loop needs the signal name expanded into the
# handler at arming time, which is SC2064 however it is written.
trap 'on_signal INT' INT
trap 'on_signal TERM' TERM
trap 'on_signal HUP' HUP

CFG="$(mktemp -d)"

# Under Git Bash the CLI is a Windows binary and cannot read an MSYS path, so
# hand it native paths. Absent cygpath the paths suit a native CLI — but not a
# Windows one reached from a POSIX shell, which is the WSL case the guard below
# covers.
if command -v cygpath >/dev/null 2>&1; then
  CFG_NATIVE="$(cygpath -w "$CFG")"
  ROOT_NATIVE="$(cygpath -w "$ROOT")"
else
  CFG_NATIVE="$CFG"; ROOT_NATIVE="$ROOT"
  # WSL interop drops any variable not named in WSLENV, so the export below
  # never reaches a Windows claude.exe without this; /p converts the POSIX path
  # to the Windows form. Correct only because CFG_NATIVE is POSIX in this
  # branch — /p corrupts an already-Windows value into "C;<U+F05C>Users<U+F05C>...".
  export WSLENV="${WSLENV:+$WSLENV:}CLAUDE_CONFIG_DIR/p"
fi
export CLAUDE_CONFIG_DIR="$CFG_NATIVE"

# The redirect above is an assumption until proven. A CLI that never received it
# falls back to the real ~/.claude, reads and writes there, and still exits 0 —
# so nothing in the exit status of the two calls below can detect it.
#
# Two checks. "No marketplaces configured" says the resolved config is not a
# populated one; alone it passes when the operator's real config happens to hold
# none, which is likeliest on the machines least able to notice. The
# .claude.json marker is the stronger half: `marketplace list` scaffolds it into
# whichever directory the CLI actually resolved, so finding it in $CFG is proof
# the redirect reached the binary. `list` needs no login, no network, and
# creates only what `add` would have created anyway.
if ! claude plugin marketplace list 2>/dev/null | grep -q 'No marketplaces configured' \
   || [ ! -e "$CFG/.claude.json" ]; then
  echo "  live layer skipped: CLAUDE_CONFIG_DIR did not take effect" >&2
  echo "  the CLI would read and write the real config; refusing to run" >&2
  exit 2
fi

claude plugin marketplace add "$ROOT_NATIVE" >/dev/null 2>&1
claude plugin install dovetail@opencnid >/dev/null 2>&1

transcript_for() {
  local sid="$1"
  # find exits 1 when projects/ is absent, pipefail carries it past head, and
  # the bare assignment at the call site adopts it — so without this guard
  # `set -e` kills the run on the first skill and the FAIL branch below, written
  # for exactly this case, never prints. Guarding the directory rather than
  # appending `|| true` keeps a genuine traversal failure fatal.
  [ -d "$CFG/projects" ] || return 0
  find "$CFG/projects" -name "$sid.jsonl" 2>/dev/null | head -1
}

# Pick a canary the transcript cannot satisfy by accident.
#
# Every transcript already contains an 11KB listing of every skill description,
# so a short canary passes without the body ever loading — a `## ` heading word scored nine of nine here while two
# skills were in fact loading nothing. Requirements: long, drawn from the body
# rather than the frontmatter (descriptions are echoed in the listing), and
# present in exactly one shipped skill.
#
# Extraction stays in the shell on purpose. Round-tripping the file through
# another interpreter re-encodes em-dashes, and the resulting mismatch reads as
# a missing body — that cost a false negative before it was understood.
canary_for() {
  local path="$1" line
  while IFS= read -r line; do
    [ "${#line}" -ge 60 ] || continue
    case "$line" in \#*|-*|\**|\>*|\|*|'`'*) continue ;; esac
    # The transcript is JSON, so a line carrying a quote or backslash is stored
    # escaped and can never match literally. Skipping such lines is what keeps
    # this a test of the body rather than a test of the encoder.
    case "$line" in *'"'*|*'\'*) continue ;; esac
    local hits=0 other
    for other in "${SKILLS[@]}"; do
      grep -qF "$line" "${other#*:}/SKILL.md" 2>/dev/null && hits=$((hits + 1))
    done
    if [ "$hits" -eq 1 ]; then printf '%s' "$line"; return; fi
  done < <(sed -n '/^---$/,/^---$/!p' "$path/SKILL.md")
}

for entry in "${SKILLS[@]}"; do
  name="${entry%%:*}"; path="${entry#*:}"

  canary="$(canary_for "$path")"
  if [ -z "$canary" ]; then
    note SKIP "$name" "no line unique enough to serve as a canary"; continue
  fi

  # MSYS_NO_PATHCONV only on the slash-command arg: Git Bash would otherwise
  # rewrite the leading slash into a file path and the command would never
  # expand. Scoped to this call, since exporting it mangles the paths above.
  out="$(MSYS_NO_PATHCONV=1 claude -p "/dovetail:$name" --output-format json 2>/dev/null || true)"
  sid="$(printf '%s' "$out" | sed -n 's/.*"session_id":"\([^"]*\)".*/\1/p')"
  tf="$(transcript_for "$sid")"

  if [ -z "$tf" ]; then
    note FAIL "$name" "no transcript — did not resolve"; fail=1
  elif grep -qF "$canary" "$tf"; then
    note ok "$name" "body loaded"
  else
    note FAIL "$name" "resolved but body absent"; fail=1
  fi
done

echo
if [ "$fail" -eq 0 ]; then
  echo "All skills load. Note this proves the body reaches the session, not that"
  echo "the model then acts on it — that needs an authenticated run."
else
  echo "FAILURES above."
fi
exit "$fail"
