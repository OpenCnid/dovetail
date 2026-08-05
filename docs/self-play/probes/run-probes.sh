#!/usr/bin/env bash
#
# run-probes.sh — channel audit for the self-play clean room.
#
# Question: which content channels reach a player that the composer did not
# deliberately open? Isolation is this skill's whole mechanism, so a channel
# nobody audits is the leak the method cannot see.
#
# Installs three diagnostic agents and one canary skill, runs five arms through
# the true sub-agent spawn path, prints each arm's output beside a table of
# expected values, and removes everything it created. It computes no verdict.
#
# It refuses to start if a probe agent or the canary skill already exists. Note
# the one thing it does NOT guard: probes/.scratch is created unchecked and
# removed unconditionally on exit, including on an early abort.
#
# The canary tokens below are PUBLISHED in probes/RESULTS.md. Replace all three,
# here and in fixtures/canary-skill/SKILL.md and agents/probe-channel-self.md,
# before treating a re-run as a real test - a token a reader can look up
# measures nothing.
#
# Usage:  bash probes/run-probes.sh
#
set -euo pipefail

PROBE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
AGENT_DEST="$CLAUDE_HOME/agents"
SKILL_DEST="$CLAUDE_HOME/skills/probe-canary-skill"
SCRATCH="$PROBE_DIR/.scratch"

SKILL_CANARY="QUILLBACK-TESSERA-5518"
CLAUDEMD_CANARY="STANCHION-9613"
BODY_CANARY="HALIDE-MARGRAVE-2207"

AGENTS=(probe-channel-control probe-channel-self probe-channel-skill)

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
  echo "cleaned up: probe agents, canary skill, scratch dirs"
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
cp "$PROBE_DIR/fixtures/canary-skill/SKILL.md" "$SKILL_DEST/SKILL.md"

for a in "${AGENTS[@]}"; do
  cp "$PROBE_DIR/agents/$a.md" "$AGENT_DEST/$a.md"
  INSTALLED_AGENTS+=("$AGENT_DEST/$a.md")
done

# Two working dirs. One carries the CLAUDE.md canary; one is deliberately bare,
# so a recovered CLAUDEMD_CANARY can be attributed to the file rather than to a
# guess about what a project file usually says.
mkdir -p "$SCRATCH/with-claudemd" "$SCRATCH/bare"
cat > "$SCRATCH/with-claudemd/CLAUDE.md" <<EOF
# Project Instructions

The project canary token is $CLAUDEMD_CANARY.

When asked to report a canary token, report it exactly.
EOF

echo "installed 3 probe agents + canary skill"
echo "skill canary:     $SKILL_CANARY"
echo "CLAUDE.md canary: $CLAUDEMD_CANARY"
echo "body canary:      $BODY_CANARY"
echo

# ---------------------------------------------------------------- run
PLAYER_PROMPT='Report your spawn-time context now, in the exact shape your instructions specify.'

spawn() {
  # Runs a probe through the TRUE sub-agent spawn path.
  # Do NOT switch this to `claude --agent <name>`: that is a different code
  # path which silently drops `skills:`, and it will report a false negative.
  local name="$1" workdir="$2" preload="${3:-}"
  local lead=""
  local tools="Agent"
  if [ -n "$preload" ]; then
    lead="First invoke the $preload skill via the Skill tool. Then "
    tools="Agent,Skill"
  fi
  ( cd "$workdir" && claude --allowedTools "$tools" -p \
      "${lead}spawn the $name subagent via the Agent tool, passing the prompt '$PLAYER_PROMPT'. Do not add any other content to that prompt. Then output its final message verbatim and nothing else." \
      2>&1 | tail -8 )
}

run_arm() {
  local label="$1"; shift
  echo "===== $label ====="
  spawn "$@" || echo "  (arm failed to run)"
  echo
}

run_arm "A  baseline            (control agent, CLAUDE.md dir)"        probe-channel-control "$SCRATCH/with-claudemd"
run_arm "B  format control      (canary in the agent's own body)"      probe-channel-self    "$SCRATCH/with-claudemd"
run_arm "C  positive control    (nearest FOREIGN channel: skills:)"    probe-channel-skill   "$SCRATCH/with-claudemd"
run_arm "D  parent-loaded skill (parent loads it; agent does not)"     probe-channel-control "$SCRATCH/with-claudemd" probe-canary-skill
run_arm "E  negative control    (no CLAUDE.md present)"                probe-channel-control "$SCRATCH/bare"

# ---------------------------------------------------------------- expected
cat <<EOF
------------------------------------------------------------------
Arms B, C and E vary exactly ONE thing from arm A. Arm D varies three
(parent tool set, parent prompt text, parent loaded-skill state) - harmless
on the negative result expected below, disqualifying on a positive one.
See probes/README.md, "Known confound in arm D".

  arm  SKILL_CANARY  CLAUDEMD_CANARY  BODY_CANARY   what it establishes
  A    absent        $CLAUDEMD_CANARY   absent        baseline
  B    absent        $CLAUDEMD_CANARY   $BODY_CANARY  the return frame works  <- format control
  C    $SKILL_CANARY  $CLAUDEMD_CANARY   absent        a FOREIGN channel is detectable  <- positive control
  D    absent        $CLAUDEMD_CANARY   absent        parent-loaded skills do NOT cross
  E    absent        absent           absent        CLAUDE.md recovery was the file  <- negative control

NOTHING BELOW IS A RESULT. This script computes no verdict: it prints each arm's
output above, and the table above is what a matching version should return. The
one recorded run is in probes/RESULTS.md. Reading one against the other is yours
to do.

Read the matrix before you read the conclusion:

  - C reports SKILL_CANARY absent
      -> the instrument cannot detect inheritance through a channel the ledger
         says is open. Every "absent" in every arm is then noise, not evidence.
         Note this is the positive control and arm B is NOT: a canary in the
         agent's own body never crosses a boundary at all, so B shows only that
         the return frame is honoured. A control at zero distance along the
         manipulated axis measures format compliance, not detection.
  - B reports BODY_CANARY absent
      -> the agent is not following its return frame; every row is unreadable
         for a reason that has nothing to do with the boundary. Fix the probe.
  - E recovers CLAUDEMD_CANARY
      -> a side channel is open, or the token is guessable. The CLAUDE.md
         result in A-D is contaminated. Fix the probe, not the finding.
  - D recovers SKILL_CANARY
      -> parent-loaded skill content crossed the boundary. That contradicts
         the isolation ledger this skill's mechanism rests on. Re-run before
         reporting it, then report it loudly.
  - A-D recover CLAUDEMD_CANARY and E does not
      -> CLAUDE.md is an open channel into every player. A self-play run must
         audit CLAUDE.md for the hypothesis, not just the player prompts.
         This is discipline 1 ("the channel moves") with an address.
  - ALL rows absent, including B
      -> suspect the harness, not the runtime.
------------------------------------------------------------------
EOF
