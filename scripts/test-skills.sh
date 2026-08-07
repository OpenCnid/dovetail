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
# The live layer rests on a decision made before it: which paths this CLI can
# read. That is neither layer, it judges no skill, and `--plan` reaches it
# alone — see the plan below. `scripts/test-skills-paths.sh` grades it without
# a CLI, which is why CI can run it and cannot run the layer it serves.
#
# "Throwaway" holds only where the shell propagates CLAUDE_CONFIG_DIR to the
# CLI. A POSIX shell invoking a Windows claude.exe propagates nothing on its
# own — WSL interop drops any variable not named in WSLENV, so the variable
# never arrives, the CLI falls back to the real ~/.claude, and the marketplace
# registration and every session transcript land in the operator's own config.
# That happens silently and exits 0, so where this is that case the live layer
# names the variable in WSLENV, proves the redirect took effect before writing
# anything, and exits 2 without running when it cannot.
#
# The environment is half of it. `marketplace add` takes the repository path as
# an argument, and interop passes arguments to a Windows binary unmodified, so
# WSLENV cannot reach that one and it is converted here instead. Which
# conversion applies is decided by capability rather than by the name of an
# operating system.
#
# The live layer needs no login and costs no API turn — invoking a skill expands
# harness-side. It spends no money; what it can cost, absent the check below, is
# a write to the operator's real configuration.
#
# Usage:
#   bash scripts/test-skills.sh              # static + live
#   bash scripts/test-skills.sh --static     # static only, no claude needed
#   bash scripts/test-skills.sh --plan       # print the path plan and stop.
#                                            #   Invokes no CLI and writes
#                                            #   nothing, but does need one on
#                                            #   PATH to have something to plan
#                                            #   for, and plans against TMPDIR
#                                            #   rather than a scratch directory
#                                            #   it declines to create.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STATIC_ONLY=0
PLAN_ONLY=0
# Refused rather than ignored: a mistyped flag that silently ran the live layer
# would install the pack, which is the one thing a reader reaching for a flag is
# usually trying not to do.
case "${1:-}" in
  --static) STATIC_ONLY=1 ;;
  --plan)   PLAN_ONLY=1 ;;
  "")       ;;
  *)        echo "usage: bash scripts/test-skills.sh [--static|--plan]" >&2; exit 2 ;;
esac

# Keep in step with SKILLS in install.sh, and with the directories in skills/ —
# plugin.json names no skill, so the loader's glob makes the disk the other list.
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

# ---------------------------------------------------------------- the plan
#
# Which paths this CLI can read, settled before anything is created, by
# capability rather than by the name of an operating system. Two questions, in
# this order:
#
#   which converter does this shell have?   cygpath is MSYS or Cygwin, where the
#           CLI is a Win32 process by construction — there is no POSIX process
#           space for it to live in. wslpath is a WSL distro, where it may be
#           either, so the second question decides.
#   what does `claude` resolve to?   under a Windows drive mount, or carrying a
#           Windows extension, it is a Win32 binary reached from a POSIX shell.
#
# "Is this WSL" is the question this deliberately does not ask, because asking
# it breaks a working setup: a distro running a Linux-native CLI needs no
# conversion at all, and converting for it hands \\wsl.localhost\... to a
# process that cannot open it. The mount point rather than the extension is what
# identifies the Win32 case — measured 2026-08-06 on WSL 2.6.3.0, Ubuntu-24.04,
# where `command -v claude` answers /mnt/c/Users/.../AppData/Roaming/npm/claude,
# carrying no .exe at all.
#
# The two carriers then need opposite things, which is why one branch converts
# one path and leaves the other alone:
#
#   environment   interop drops any variable not named in WSLENV. Named with /p
#           it arrives converted, so CFG crosses as POSIX and becomes a Windows
#           path on the way. Converting it here as well corrupts it: /p
#           colon-splits the value and resolves each fragment as a relative
#           Linux path, delivering C;C:\<U+F05C>Users<U+F05C>... for C:\Users\...
#           (measured 2026-08-06 by hexdump of the delivered bytes, WSL 2.6.3.0).
#   arguments   nothing converts them. "Parameters are passed to the Windows
#           binary unmodified" is Microsoft's own description of interop, and
#           `marketplace add` takes the repository path that way — so ROOT is
#           converted here, and no WSLENV entry could have covered it.
#
# Under MSYS the runtime already rewrites both carriers for a Win32 target, so
# cygpath is not what makes Git Bash work; it is what makes the conversion
# stated rather than inherited, and it yields the backslash form. Measured
# 2026-08-06 on git-bash 5.2.37(msys), Windows 10: an unconverted /tmp path
# reached a native binary as C:/Users/....
PLAN_CLI=""; PLAN_KIND=posix; PLAN_CONVERT=none; PLAN_ENV=""
CFG_NATIVE=""; ROOT_NATIVE=""; CFG_CROSSES=""

plan_for() {   # plan_for <config-dir>
  local cfg="$1" resolved
  command -v claude >/dev/null 2>&1 || { echo; echo "claude not on PATH — run with --static"; exit 2; }
  PLAN_CLI="$(command -v claude)"
  # A shim in ~/bin pointing into a Windows mount is still a Win32 CLI. readlink
  # -f is GNU and macOS gained it late, so a refusal leaves the unresolved path
  # — the same answer for everything that is not a symlink.
  if command -v readlink >/dev/null 2>&1; then
    resolved="$(readlink -f "$PLAN_CLI" 2>/dev/null || true)"
    if [ -n "$resolved" ]; then PLAN_CLI="$resolved"; fi
  fi

  if command -v cygpath >/dev/null 2>&1; then
    PLAN_KIND=windows; PLAN_CONVERT=cygpath
  else
    # The drive-mount test only runs where a converter says this shell can reach
    # a Windows filesystem at all, and that ordering is load-bearing rather than
    # tidy. Asked the other way round it refused a working native-Linux setup:
    # /mnt is also just where a second disk goes — an npm prefix on /mnt/data,
    # a cloud runner's ephemeral disk — so a Linux CLI there was called a
    # Windows binary and told to install WSL. Built and observed 2026-08-06, a
    # Linux `claude` at /mnt/wsl/data/bin/claude classified windows and exited 2.
    #
    # /mnt/wsl is excluded because it is WSL's own tmpfs rather than a drive
    # mount, and is where Docker Desktop injects Linux-native tools.
    #
    # The limit this leaves, said here rather than found later: a Linux-native
    # CLI installed under some *other* drive-mount path inside a distro would
    # still be read as Windows. Nothing cheap distinguishes them — the real
    # Windows case is a shell script too, not a PE — so the plan prints what it
    # decided, and `--plan` shows it without running anything.
    if command -v wslpath >/dev/null 2>&1; then
      case "$PLAN_CLI" in
        /mnt/wsl/*) ;;
        /mnt/*|/cygdrive/*|*.exe|*.EXE|*.cmd|*.CMD|*.bat|*.BAT)
          PLAN_KIND=windows; PLAN_CONVERT=wslpath ;;
      esac
    fi
  fi

  case "$PLAN_CONVERT" in
    cygpath)
      CFG_NATIVE="$(cygpath -w "$cfg" 2>/dev/null)" || CFG_NATIVE=""
      ROOT_NATIVE="$(cygpath -w "$ROOT" 2>/dev/null)" || ROOT_NATIVE=""
      CFG_CROSSES="$CFG_NATIVE"
      ;;
    wslpath)
      CFG_NATIVE="$cfg"
      ROOT_NATIVE="$(wslpath -w "$ROOT" 2>/dev/null)" || ROOT_NATIVE=""
      # Display only: what /p will make of CFG on the way across. The value
      # exported stays POSIX, for the reason in the header.
      CFG_CROSSES="$(wslpath -w "$cfg" 2>/dev/null || true)"
      PLAN_ENV="WSLENV=CLAUDE_CONFIG_DIR/p"
      export WSLENV="${WSLENV:+$WSLENV:}CLAUDE_CONFIG_DIR/p"
      ;;
    *)
      CFG_NATIVE="$cfg"; ROOT_NATIVE="$ROOT"; CFG_CROSSES="$cfg"
      ;;
  esac

  # A converter that is present and answers nothing is the same hazard as one
  # that is absent, and it fails the same way: an empty CLAUDE_CONFIG_DIR sends
  # the CLI back to the real ~/.claude.
  if [ -z "$CFG_NATIVE" ] || [ -z "$ROOT_NATIVE" ]; then
    echo "  live layer cannot run: $PLAN_CONVERT is on PATH but converted nothing" >&2
    echo "  for $cfg or $ROOT; without both paths the CLI would resolve its own" >&2
    echo "  config. Run with --static." >&2
    exit 2
  fi
}

print_plan() {   # print_plan <config-dir>
  printf '  %-9s %s\n' "cli" "$PLAN_KIND  $PLAN_CLI"
  printf '  %-9s %s\n' "convert" "$PLAN_CONVERT"
  printf '  %-9s %s\n' "config" "$1 -> $CFG_CROSSES"
  # The exported value and the value that arrives are different lines on
  # purpose. Where WSLENV carries the conversion they differ, and a reader who
  # cannot see both cannot tell a path converted once from one converted twice —
  # which is the corruption the header describes.
  # WSLENV is read back from the environment rather than reprinted from the
  # variable that decided it, so this line reports what is set instead of what
  # was intended. Deleting the export while keeping the announcement is a
  # one-token slip that silently sends the CLI to the real ~/.claude, and an
  # announcement cannot catch it.
  printf '  %-9s %s\n' "export" "CLAUDE_CONFIG_DIR=$CFG_NATIVE${WSLENV:+  WSLENV=$WSLENV}"
  printf '  %-9s %s\n' "repo" "$ROOT -> $ROOT_NATIVE"
}

if [ "$PLAN_ONLY" -eq 1 ]; then
  # The plan is a question about the live layer, so the static layer is not run
  # and no scratch directory is made. The temp root stands in for the directory
  # the live layer would create under it, and converts the same way.
  echo "plan"
  plan_for "${TMPDIR:-/tmp}"
  print_plan "${TMPDIR:-/tmp}"
  exit 0
fi

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

# every declared path must be reachable by both install routes — the plugin
# loader's glob and install.sh — or one of them ships a skill the other does not
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

# Printed rather than merely applied: when the CLI rejects a path, these four
# lines are the difference between reading the cause and reading eight skills
# that failed for no stated reason.
plan_for "$CFG"
print_plan "$CFG"
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
  echo "  it was handed CLAUDE_CONFIG_DIR=$CFG_NATIVE${PLAN_ENV:+ with $PLAN_ENV}" >&2
  echo "  and looked for $CFG/.claude.json; run --plan to see the whole plan" >&2
  exit 2
fi

# Statuses read rather than discarded. Both of these write the message that says
# which path was rejected, and swallowing them turned one unreadable argument
# into eight skills reporting "did not resolve" with nothing naming the cause.
# The layer stops here rather than grading skills it never installed, and exits
# 2 because no skill was judged either way.
if ! add_out="$(claude plugin marketplace add "$ROOT_NATIVE" 2>&1)"; then
  echo "  live layer stopped: the CLI refused the repository path" >&2
  echo "  it was handed $ROOT_NATIVE" >&2
  printf '%s\n' "$add_out" | sed 's/^/         /' >&2
  exit 2
fi
if ! install_out="$(claude plugin install dovetail@opencnid 2>&1)"; then
  echo "  live layer stopped: the pack did not install" >&2
  printf '%s\n' "$install_out" | sed 's/^/         /' >&2
  exit 2
fi

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

  # MSYS_NO_PATHCONV on this call only. What actually protects the argument is
  # the colon: MSYS reads a colon-bearing string as a POSIX path list and
  # declines to convert one whose elements are not all absolute, so for every
  # name in SKILLS the guard changes nothing — measured 2026-08-06 on git-bash
  # 5.2.37(msys), Windows 10, where /dovetail:prompt-engineering arrived
  # byte-identical with it and without it. It stays because the hazard is real
  # one character away: a colon-free /dovetail arrives as
  # C:/Program Files/Git/dovetail. It stays off the export list for a different
  # reason than the one given here before — it does not mangle an
  # already-native path, it suppresses the automatic conversion the MSYS runtime
  # performs for a Win32 target, which is what the cygpath branch above is
  # making explicit rather than replacing.
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
