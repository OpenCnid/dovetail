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
# The live layer needs no login. Invoking a skill expands harness-side and costs
# no API turn, so this runs on an unauthenticated machine and spends nothing.
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
  "using-dovetail:skills/using-dovetail"
  "prompt-engineering:vendor/prompt-engineering/skills/prompt-engineering"
  "hypershot-protocol:vendor/hypershot-protocol/skills/hypershot-protocol"
  "subagent-composition:vendor/subagent-composition/skills/subagent-composition"
  "judge-composition:vendor/judge-composition/skills/judge-composition"
  "self-play:vendor/self-play/skills/self-play"
  "better-skill-creator:vendor/better-skill-creator/skills/better-skill-creator"
  "upsum:vendor/upsum/skills/upsum"
  "spark-steering:vendor/spark-steering/skills/spark-steering"
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
  grep -q "$path" .claude-plugin/plugin.json || { note FAIL "$name" "missing from plugin.json"; fail=1; }
  grep -q "$path" scripts/install.sh          || { note FAIL "$name" "missing from install.sh"; fail=1; }
done

if [ "$STATIC_ONLY" -eq 1 ]; then
  echo
  [ "$fail" -eq 0 ] && echo "static checks passed." || echo "static checks FAILED."
  exit "$fail"
fi

# -------------------------------------------------------------------- live
command -v claude >/dev/null 2>&1 || { echo; echo "claude not on PATH — run with --static"; exit 2; }

echo
echo "live"

CFG="$(mktemp -d)"
trap 'rm -rf "$CFG"' EXIT

# Under Git Bash the CLI is a Windows binary and cannot read an MSYS path, so
# hand it native paths. cygpath is absent elsewhere, where the paths already
# suit.
if command -v cygpath >/dev/null 2>&1; then
  CFG_NATIVE="$(cygpath -w "$CFG")"
  ROOT_NATIVE="$(cygpath -w "$ROOT")"
else
  CFG_NATIVE="$CFG"; ROOT_NATIVE="$ROOT"
fi
export CLAUDE_CONFIG_DIR="$CFG_NATIVE"

claude plugin marketplace add "$ROOT_NATIVE" >/dev/null 2>&1
claude plugin install dovetail@opencnid >/dev/null 2>&1

transcript_for() {
  local sid="$1"
  find "$CFG/projects" -name "$sid.jsonl" 2>/dev/null | head -1
}

# Pick a canary the transcript cannot satisfy by accident.
#
# Every transcript already contains the injected using-dovetail body and an
# 11KB listing of every skill description, so a short canary passes without the
# body ever loading — a `## ` heading word scored nine of nine here while two
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

# the SessionStart injection is the only channel that reaches the model before
# it acts, and the only notice it gets that two skills are invisible to it
out="$(claude -p "probe" --output-format json 2>/dev/null || true)"
sid="$(printf '%s' "$out" | sed -n 's/.*"session_id":"\([^"]*\)".*/\1/p')"
tf="$(transcript_for "$sid")"
if [ -n "$tf" ] && grep -qF "The companion rule" "$tf"; then
  note ok "SessionStart" "using-dovetail injected with no skill invoked"
else
  note FAIL "SessionStart" "entry skill did not reach session context"; fail=1
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "All skills load. Note this proves the body reaches the session, not that"
  echo "the model then acts on it — that needs an authenticated run."
else
  echo "FAILURES above."
fi
exit "$fail"
