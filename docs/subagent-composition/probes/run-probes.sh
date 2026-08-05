#!/usr/bin/env bash
#
# run-probes.sh — re-verify the Claude Code sub-agent boundary claims in
# docs/FINDINGS.md against whatever version you have installed.
#
# Installs five diagnostic agents and one canary skill, runs each probe through
# the true sub-agent spawn path, prints a result matrix, and removes everything
# it created. It refuses to overwrite anything that already exists.
#
# Usage:  bash probes/run-probes.sh
#
set -euo pipefail

PROBE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
AGENT_DEST="$CLAUDE_HOME/agents"
SKILL_DEST="$CLAUDE_HOME/skills/probe-canary-skill"
SCRATCH="$PROBE_DIR/.scratch"

SKILL_CANARY="PELICAN-ORRERY-9042"
CLAUDEMD_CANARY="MARMOSET-7731"

AGENTS=(probe-skills-bare probe-skills-flow probe-skills-block probe-skills-control probe-context-detect)

INSTALLED_AGENTS=()
INSTALLED_SKILL=""

cleanup() {
  local f
  for f in "${INSTALLED_AGENTS[@]:-}"; do
    [ -n "$f" ] && rm -f "$f"
  done
  [ -n "$INSTALLED_SKILL" ] && rm -rf "$INSTALLED_SKILL"
  rm -rf "$SCRATCH"
  echo
  echo "cleaned up: probe agents, canary skill, scratch dir"
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------- preflight
command -v claude >/dev/null 2>&1 || {
  echo "error: 'claude' CLI not found on PATH." >&2
  exit 1
}

echo "claude version: $(claude --version 2>&1 | head -1)"
echo "config dir:     $CLAUDE_HOME"
echo

mkdir -p "$AGENT_DEST"

# Refuse to clobber anything of the user's that shares a name.
for a in "${AGENTS[@]}"; do
  if [ -e "$AGENT_DEST/$a.md" ]; then
    echo "error: $AGENT_DEST/$a.md already exists. Move it aside and re-run." >&2
    exit 1
  fi
done
if [ -e "$SKILL_DEST" ]; then
  echo "error: $SKILL_DEST already exists. Move it aside and re-run." >&2
  exit 1
fi

# ---------------------------------------------------------------- install
mkdir -p "$SKILL_DEST"
INSTALLED_SKILL="$SKILL_DEST"
cp "$PROBE_DIR/canary-skill/SKILL.md" "$SKILL_DEST/SKILL.md"

for a in "${AGENTS[@]}"; do
  cp "$PROBE_DIR/agents/$a.md" "$AGENT_DEST/$a.md"
  INSTALLED_AGENTS+=("$AGENT_DEST/$a.md")
done

# Working dir carrying the CLAUDE.md canary — the positive control.
mkdir -p "$SCRATCH"
cat > "$SCRATCH/CLAUDE.md" <<EOF
# Project Instructions

The project canary token is $CLAUDEMD_CANARY.

When asked to report a canary token, report it exactly.
EOF

echo "installed 5 probe agents + canary skill"
echo "skill canary:     $SKILL_CANARY"
echo "CLAUDE.md canary: $CLAUDEMD_CANARY"
echo

# ---------------------------------------------------------------- run
spawn() {
  # Runs a probe through the TRUE sub-agent spawn path.
  # Do NOT switch this to `claude --agent <name>`: that is a different code
  # path which silently drops `skills:`, and it will report a false negative.
  # See docs/FINDINGS.md §5.
  local name="$1"
  ( cd "$SCRATCH" && claude --allowedTools "Agent" -p \
      "Spawn the $name subagent via the Agent tool, passing the prompt 'Report your spawn-time context now, in the exact shape your instructions specify.' Then output its final message verbatim and nothing else." \
      2>&1 | tail -8 )
}

for a in "${AGENTS[@]}"; do
  echo "===== $a ====="
  spawn "$a" || echo "  (probe failed to run)"
  echo
done

# ---------------------------------------------------------------- expected
cat <<EOF
------------------------------------------------------------------
Expected on a version matching docs/FINDINGS.md (Claude Code 2.1.214):

  probe-skills-bare     SKILL_CANARY: $SKILL_CANARY
  probe-skills-flow     SKILL_CANARY: $SKILL_CANARY
  probe-skills-block    SKILL_CANARY: $SKILL_CANARY
  probe-skills-control  SKILL_CANARY: absent          <- negative control
  probe-context-detect  CLAUDEMD_CANARY: $CLAUDEMD_CANARY
                        SKILL_CANARY: $SKILL_CANARY   <- positive control

  All five            TOOLS: WebSearch                <- allowlist enforced

Read the matrix before you read the conclusion:
  - control recovers a canary  -> the probe is contaminated, not the feature
  - ALL rows absent            -> suspect the harness, not the runtime
  - context-detect finds only CLAUDEMD_CANARY -> skills did not cross; confirm
    you are on the spawn path and not session-agent mode
------------------------------------------------------------------
EOF
