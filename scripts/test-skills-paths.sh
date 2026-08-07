#!/usr/bin/env bash
#
# test-skills-paths.sh — prove the path decision the live layer rests on is
# settled, and correct, before the CLI is handed anything, and that reaching
# that answer invokes no CLI at all.
#
# The decision is a third thing, neither of `test-skills.sh`'s two layers: it
# runs before both, `--plan` reaches it alone, and it judges no skill. That is
# why it can be graded on a runner with no CLI, and why nothing graded it until
# now — the static layer never consults it and the live layer, which does,
# installs a plugin and starts eight sessions, so no runner executes it.
#
# It was wrong in one case and silent about it. A POSIX shell invoking a Windows
# claude.exe — WSL, which is how the defect arrived — carried CLAUDE_CONFIG_DIR
# across correctly through WSLENV and then handed the same CLI the repository
# path as an *argument*, untranslated. Interop passes arguments to a Windows
# binary unmodified, so `marketplace add` received /mnt/d/... and could not open
# it, and because both statuses were discarded the run reported eight skills
# that "did not resolve" and never named the path.
#
# What makes it worth a file of its own is that the decision cannot be read off
# the platform. "Is this WSL" is the wrong question: a distro running a
# Linux-native CLI needs no conversion, and converting for it hands
# \\wsl.localhost\... to a process that cannot open it. So the subject asks two
# capability questions instead, and those are what this grades.
#
# Three sections, checked apart because they fail apart:
#
#   selection  given a shell that has cygpath, or wslpath, or neither, and a
#              `claude` that resolves to a Windows binary or a POSIX one, the
#              plan names the converter the combination needs and converts each
#              path with it — the right path, which is a separate claim and the
#              one the defect turned on.
#   refusal    what cannot work is refused at exit 2 with the reason, before a
#              scratch config exists — a converter that answers nothing, an
#              absent CLI, an unknown flag — and, just as load-bearing, what
#              merely looks wrong is *not* refused: a Windows-shaped CLI path
#              with no converter present falls through to the plan that worked
#              before any of this.
#   no CLI     none of the above invoked `claude`. This is the section that
#              keeps the other two free: grading the decision rather than the
#              run is what costs no install and no session.
#
# The child's environment is built as a wrapper farm rather than a PATH prefix.
# A prefix cannot make a tool absent — `command -v cygpath` finds a stub that
# exits 127 as readily as the real one — and cygpath shares /usr/bin with sed,
# awk and mktemp, so pruning the directory takes the child's toolchain with it.
# Each wrapper execs one real binary by absolute path, the farm becomes the
# child's entire PATH, and which of cygpath, wslpath and claude exist in it is
# then this script's decision rather than the runner's.
#
# Nothing here runs `claude`, installs a plugin, writes a marketplace entry or
# reads the operator's config. The `claude` on the child's PATH is a stub that
# records its arguments and exits, HOME and TMPDIR point inside the scratch
# tree, and the last section asserts the stub recorded nothing and no config
# directory appeared. Every invocation of the subject goes through `run_subject`
# so that those two assertions watch every case rather than most of them.
#
# Usage:
#   bash scripts/test-skills-paths.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0
skipped=0
note() { printf '  %-6s %s\n' "$1" "$2"; }

# The output is the evidence for every verdict below, so a failure that hides it
# tells the reader a needle was missing and not what the haystack held.
note_fail() {   # note_fail <message>
  note FAIL "$1"
  printf '%s\n' "$out" | sed 's/^/         /'
  fail=1
}
note_skip() {   # note_skip <message>
  note SKIP "$1"
  skipped=$((skipped + 1))
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

SUBJECT="$ROOT/scripts/test-skills.sh"
CLAUDE_LOG="$TMP/claude-calls.log"
: > "$CLAUDE_LOG"

# The farm's wrappers need one absolute interpreter, and so does every stub.
REAL_BASH="$(command -v bash)"

# Everything `--plan` reaches for outside the shell. Deliberately short: the
# plan creates no scratch directory, so mktemp, find, sed and awk are the live
# layer's dependencies rather than the plan's, and a farm that carried them
# would hide which tools the decision actually needs.
FARM_TOOLS="dirname readlink"

build_farm() {   # build_farm <dir> [extra-tool]...
  local dir="$1" tool real
  shift
  mkdir -p "$dir"
  for tool in $FARM_TOOLS "$@"; do
    real="$(command -v "$tool" 2>/dev/null)" || continue
    { printf '#!%s\n' "$REAL_BASH"
      printf 'exec "%s" "$@"\n' "$real"
    } > "$dir/$tool"
    chmod +x "$dir/$tool"
  done
}

# A converter whose answer this script chooses. It echoes its prefix followed by
# the path it was given, so an assertion can name which path was converted
# rather than only that something was. The prefix arrives in the stub's own
# environment at call time, so one stub serves the drive-letter case, the UNC
# case and the answers-nothing case without being rewritten.
write_converter() {   # write_converter <path>
  cat > "$1" <<STUB
#!$REAL_BASH
prefix="\${STUB_PREFIX-X:\\\\stub}"
[ "\$prefix" = NONE ] && exit 0
shift || true
printf '%s%s\n' "\$prefix" "\$1"
STUB
  chmod +x "$1"
}

# Records and exits. Its whole purpose is the third section: if the decision
# ever shells out to the CLI, this file stops being empty.
write_claude_stub() {   # write_claude_stub <path>
  cat > "$1" <<STUB
#!$REAL_BASH
printf '%s\n' "\$*" >> "$CLAUDE_LOG"
exit 0
STUB
  chmod +x "$1"
}

# Every run of the subject goes through here, including the one that hands it a
# flag it should refuse. That case ran bare at first — the operator's real PATH,
# real HOME, real TMPDIR — which left this file's central promise unenforced
# exactly where it was load-bearing: were the flag ever to fall through to the
# live layer, it would find the real CLI and write to the real config, and the
# two assertions watching for that watch files a bare run cannot reach.
run_subject() {   # run_subject <farm> <arg> [env-assignment]...
  local farm="$1" arg="$2"
  shift 2
  out="$(env -i \
    PATH="$farm" HOME="$TMP/home" TMPDIR="$TMP/tmproot" \
    "$@" "$REAL_BASH" "$SUBJECT" "$arg" 2>&1)" && rc=0 || rc=$?
}

run_plan() {   # run_plan <farm> [env-assignment]...
  local farm="$1"
  shift
  run_subject "$farm" --plan "$@"
}

said() { printf '%s\n' "$out" | grep -qF -- "$1"; }

# Assertions are scoped to the plan line they are about, because a bare search
# of the whole output does not distinguish the two paths — and that is not
# hypothetical. Written first as `said 'D:\drive'`, every case below passed
# against a copy of the subject with the argv conversion removed: the converter
# still ran for the config line, so the substring was present and the repository
# path went unconverted underneath it. For the same reason the needles below
# carry the operand, not just the prefix — a prefix alone cannot tell two
# conversions from one conversion used twice.
field() {   # field <name> — the value on that line of the plan, or nothing
  printf '%s\n' "$out" | awk -v k="$1" '$1 == k { $1 = ""; sub(/^[ \t]+/, ""); print; exit }'
}
field_has() { field "$1" | grep -qF -- "$2"; }
field_word() { field "$1" | awk '{print $1}'; }

mkdir -p "$TMP/home" "$TMP/tmproot"

# ------------------------------------------------------------------ selection
echo
echo "selection — the plan names the converter the combination needs"

# Canary. Every assertion in the last section says the CLI was not called, and
# an assertion nothing could falsify is not a test — so call the stub the way
# the subject would and prove the log records it.
write_claude_stub "$TMP/canary-claude"
"$TMP/canary-claude" plugin marketplace list >/dev/null 2>&1 || true
if [ -s "$CLAUDE_LOG" ]; then
  note ok "canary fires when the CLI stub is invoked"
  : > "$CLAUDE_LOG"
else
  note FAIL "canary cannot fire — the no-CLI section below would pass vacuously"
  fail=1
fi

# The other negative in that section, canaried the same way: a directory the
# check would see, made and removed, so "none appeared" means the check looked.
mkdir -p "$TMP/home/.claude"
if [ -e "$TMP/home/.claude" ]; then
  note ok "canary fires when a config directory appears under the scratch HOME"
  rm -rf "$TMP/home/.claude"
else
  note FAIL "canary cannot fire — the scratch-config assertion would pass vacuously"
  fail=1
fi

# Fixture canary. The farm claims to decide which tools exist; if the child can
# still see the runner's own /usr/bin, every case below is grading this machine
# rather than the combination it names.
build_farm "$TMP/farm-posix" claude
write_claude_stub "$TMP/farm-posix/claude"
# A prefix assignment rather than `env`, because `command` is a shell builtin
# and `env` can only exec a file — `env PATH=… command -v x` fails with "No such
# file or directory" whatever the farm holds, which reads as the farm having
# hidden everything.
if PATH="$TMP/farm-posix" command -v cygpath >/dev/null 2>&1 ||
   PATH="$TMP/farm-posix" command -v wslpath >/dev/null 2>&1; then
  note FAIL "fixture: the farm did not hide the converters — the cases below prove nothing"
  fail=1
elif ! PATH="$TMP/farm-posix" command -v dirname >/dev/null 2>&1; then
  note FAIL "fixture: the farm hid dirname too — the child cannot start"
  fail=1
else
  note ok "fixture: inside the farm cygpath and wslpath are absent, dirname is not"
fi

# Fixture canary for the converter stubs. "Present and answers nothing" and
# "present but unrunnable" reach the subject's refusal by the same route, since
# `|| CFG_NATIVE=""` swallows a 126 as readily as an empty answer. Probing the
# stub through a farm PATH keeps the mute case a test of the subject rather than
# of the stub's exec bit.
build_farm "$TMP/farm-cyg" claude
write_claude_stub "$TMP/farm-cyg/claude"
write_converter "$TMP/farm-cyg/cygpath"
probe="$(env PATH="$TMP/farm-cyg" STUB_PREFIX='C:\probe' cygpath -w /canary 2>&1 || true)"
if [ "$probe" = 'C:\probe/canary' ]; then
  note ok "fixture: the converter stub runs through the farm and echoes its operand"
else
  note FAIL "fixture: the converter stub answered '$probe' — the refusal cases could pass for the wrong reason"
  fail=1
fi

# The accept direction, first. Every refusal below is worthless if the plan
# refuses everything, and this is also the native Linux and macOS case: no
# converter is present, none is needed, and nothing is exported.
run_plan "$TMP/farm-posix"
if [ "$rc" -ne 0 ]; then
  note_fail "posix shell, posix CLI — exit $rc, expected 0"
elif [ "$(field_word config)" != "$TMP/tmproot" ]; then
  # Also the proof that `env -i` reached the child at all: the plan is computed
  # for the scratch TMPDIR this script chose, so seeing it here is what makes
  # the scratch HOME assertion in the last section mean something.
  note_fail "posix shell, posix CLI — planned against $(field_word config), not the scratch TMPDIR"
elif [ "$(field_word convert)" != none ]; then
  note_fail "posix shell, posix CLI — did not choose the no-conversion plan"
elif [ "$(field_word cli)" != posix ]; then
  note_fail "posix shell, posix CLI — misread a POSIX CLI as a Windows one"
elif said "WSLENV"; then
  note_fail "posix shell, posix CLI — named CLAUDE_CONFIG_DIR in WSLENV, which is inert here"
elif ! field_has repo "$ROOT -> $ROOT"; then
  # Choosing no conversion and performing none are separate claims. Asserted
  # only as the first, this case passed with the repository value replaced by
  # a literal that pointed nowhere.
  note_fail "posix shell, posix CLI — chose no conversion but did not pass the repository path through"
elif ! field_has export "CLAUDE_CONFIG_DIR=$TMP/tmproot"; then
  note_fail "posix shell, posix CLI — chose no conversion but exported something other than the config path"
else
  note ok "control: a POSIX CLI converts nothing, exports no WSLENV, passes both paths through"
fi

# cygpath present. Git Bash and Cygwin run the CLI as a Win32 process by
# construction, so the converter's presence settles both questions at once.
run_plan "$TMP/farm-cyg" STUB_PREFIX='C:\win'
if [ "$rc" -ne 0 ]; then
  note_fail "cygpath present — exit $rc, expected 0"
elif [ "$(field_word convert)" != cygpath ]; then
  note_fail "cygpath present — did not choose cygpath"
elif [ "$(field_word cli)" != windows ]; then
  note_fail "cygpath present — chose cygpath while calling the CLI POSIX, which is an incoherent plan"
elif ! field_has repo "C:\\win$ROOT"; then
  note_fail "cygpath present — the repository path reached argv unconverted"
elif ! field_has export "CLAUDE_CONFIG_DIR=C:\\win$TMP/tmproot"; then
  note_fail "cygpath present — CLAUDE_CONFIG_DIR was exported unconverted"
else
  note ok "cygpath present — each path converted by cygpath, and each is the right path"
fi

# wslpath present and the CLI installed inside the shell's own filesystem. This
# is the case a platform test would have broken: wslpath is present, so "am I on
# WSL" answers yes, and converting would hand a Linux process a path it cannot
# open. It needs no symlink, so it runs on every leg.
build_farm "$TMP/farm-wsl-native" wslpath claude
write_claude_stub "$TMP/farm-wsl-native/claude"
write_converter "$TMP/farm-wsl-native/wslpath"
run_plan "$TMP/farm-wsl-native" STUB_PREFIX='D:\drive'
if [ "$rc" -ne 0 ]; then
  note_fail "wslpath present, POSIX CLI — exit $rc, expected 0"
elif [ "$(field_word convert)" != none ]; then
  note_fail "wslpath present, POSIX CLI — converted for a CLI that reads POSIX paths"
elif said 'D:\drive'; then
  note_fail "wslpath present, POSIX CLI — ran wslpath anyway"
else
  note ok "wslpath present but the CLI is POSIX — nothing is converted"
fi

# A Windows CLI reached from a POSIX shell. The subject identifies it by where
# it resolves rather than by what it is named, because the real case carries no
# extension: measured 2026-08-06 on WSL 2.6.3.0, Ubuntu-24.04, `command -v
# claude` answers /mnt/c/Users/.../AppData/Roaming/npm/claude. A symlink into a
# .exe is how that shape is reproduced without a Windows mount to hand, and it
# is the only thing here that needs one.
SYMLINKS=0
mkdir -p "$TMP/win"
write_claude_stub "$TMP/win/claude.exe"
# The resolution is compared by suffix, not by equality. `readlink -f`
# canonicalises every component, and on macOS `mktemp -d` lands under a $TMPDIR
# that is itself a symlink into /private — so an equality test there fails on
# the prefix, reports "no symlinks", and skips these cases on a platform that
# has them.
if ln -s "$TMP/win/claude.exe" "$TMP/link-probe" 2>/dev/null &&
   [ -L "$TMP/link-probe" ]; then
  case "$(readlink -f "$TMP/link-probe" 2>/dev/null)" in
    */win/claude.exe) SYMLINKS=1 ;;
  esac
fi

if [ "$SYMLINKS" -eq 0 ]; then
  note_skip "windows-CLI selection case (1): this filesystem has no symlink to shape the CLI path"
  echo "         MSYS copies instead of linking, so the resolved path cannot be made"
  echo "         to end in .exe here. The Linux leg of CI is where this runs, and the"
  echo "         summary below says so rather than reporting a full pass."
else
  build_farm "$TMP/farm-wsl" wslpath
  ln -s "$TMP/win/claude.exe" "$TMP/farm-wsl/claude"
  write_converter "$TMP/farm-wsl/wslpath"

  run_plan "$TMP/farm-wsl" STUB_PREFIX='D:\drive'
  if [ "$rc" -ne 0 ]; then
    note_fail "windows CLI, wslpath present — exit $rc, expected 0"
  elif [ "$(field_word cli)" != windows ]; then
    note_fail "windows CLI, wslpath present — read a Windows CLI as a POSIX one"
  elif [ "$(field_word convert)" != wslpath ]; then
    note_fail "windows CLI, wslpath present — did not choose wslpath"
  elif ! field_has repo "D:\\drive$ROOT"; then
    note_fail "windows CLI, wslpath present — the repository path reached argv unconverted, which is the defect this file exists for"
  elif ! field_has export "WSLENV=CLAUDE_CONFIG_DIR/p"; then
    note_fail "windows CLI, wslpath present — did not name CLAUDE_CONFIG_DIR in WSLENV, so the redirect would not cross"
  elif ! field_has export "CLAUDE_CONFIG_DIR=$TMP/tmproot"; then
    note_fail "windows CLI, wslpath present — exported a converted config path, which /p corrupts on the way across"
  elif ! field_has config "D:\\drive$TMP/tmproot"; then
    # The config line shows what /p will make of the value on the way across.
    # Without this, replacing that display with the unconverted path passed
    # silently, and it is the line that shows converted-once from converted-twice.
    note_fail "windows CLI, wslpath present — did not show what the config path becomes as it crosses"
  else
    note ok "windows CLI — repo converted for argv, config left for WSLENV /p"
  fi
fi

# ------------------------------------------------------------------- refusal
echo
echo "refusal — a combination that cannot work is refused, not attempted"

refusal_case() {   # refusal_case <label> <want-substring> <farm> [env-assignment]...
  local label="$1" want="$2" farm="$3" leaked
  shift 3
  run_plan "$farm" "$@"
  if [ "$rc" -ne 2 ]; then
    note_fail "$label — exit $rc, expected 2"
    return
  fi
  if ! said "$want"; then
    note_fail "$label — refused without saying why"
    return
  fi
  # No plan line may survive a refusal: the two that carry paths are the ones a
  # reader would act on, and a refusal that still printed them would be quoting
  # a decision it had just declined to make.
  leaked=""
  for f in cli convert config export repo; do
    [ -z "$(field "$f")" ] || leaked="$leaked $f"
  done
  if [ -n "$leaked" ]; then
    note_fail "$label — printed plan lines it had already refused:$leaked"
    return
  fi
  note ok "$label"
}

# A Windows-shaped CLI path with no converter present is deliberately *not* a
# refusal, and this pins that. It used to be one, and the refusal was the
# change's own worst regression: with no converter there is no evidence this
# shell can reach a Windows filesystem at all, so a Linux CLI on a second disk
# at /mnt/data was refused at exit 2 and told to install WSL. Falling through to
# the no-conversion plan is what the same setup did before any of this, and it
# works.
if [ "$SYMLINKS" -eq 0 ]; then
  note_skip "windows-shaped CLI, no converter (1): needs a symlink to shape the CLI path"
else
  build_farm "$TMP/farm-bare"
  ln -s "$TMP/win/claude.exe" "$TMP/farm-bare/claude"
  run_plan "$TMP/farm-bare"
  if [ "$rc" -ne 0 ]; then
    note_fail "windows-shaped CLI, no converter — exit $rc, expected 0; refusing here breaks a native Linux CLI on a second disk"
  elif [ "$(field_word convert)" != none ]; then
    note_fail "windows-shaped CLI, no converter — chose a converter it does not have"
  elif ! field_has repo "$ROOT -> $ROOT"; then
    note_fail "windows-shaped CLI, no converter — altered the repository path with no converter to do it"
  else
    note ok "windows-shaped CLI with no converter falls through rather than refusing"
  fi
fi

# A converter that is present and answers nothing. An empty CLAUDE_CONFIG_DIR
# sends the CLI back to the real config, which is the failure the live layer's
# whole guard exists to prevent. The fixture canary above is what separates this
# from a stub that could not run.
refusal_case "converter answers nothing" "converted nothing" "$TMP/farm-cyg" STUB_PREFIX=NONE

# No CLI at all.
build_farm "$TMP/farm-nocli"
refusal_case "claude not on PATH" "claude not on PATH" "$TMP/farm-nocli"

# An unknown flag, which must not fall through to a live run. Run inside the
# farm that carries the recording CLI stub, so that a fall-through would be
# caught by the last section rather than merely believed impossible.
run_subject "$TMP/farm-posix" --bogus
if [ "$rc" -ne 2 ]; then
  note_fail "unknown flag — exit $rc, expected 2"
elif ! said "usage:"; then
  note_fail "unknown flag — refused without printing usage"
else
  note ok "unknown flag"
fi

# ------------------------------------------------------------------- no CLI
echo
echo "no CLI — the decision is reached without running claude"

if [ -s "$CLAUDE_LOG" ]; then
  note FAIL "the CLI was invoked $(wc -l < "$CLAUDE_LOG") time(s) while resolving the plan"
  sed 's/^/         /' "$CLAUDE_LOG"
  fail=1
else
  note ok "no invocation recorded across every case above"
fi

# The other half of the same claim: nothing was installed and no config was
# touched. HOME and TMPDIR were pointed inside $TMP for every run — proven by
# the control, which saw the plan computed against the scratch TMPDIR — so a
# config directory here is the CLI having been reached by some route this file
# did not model.
if [ -e "$TMP/home/.claude" ] || [ -e "$TMP/home/.claude.json" ]; then
  note FAIL "a config directory was created under the scratch HOME"
  fail=1
else
  note ok "no config directory was created"
fi

echo
if [ "$fail" -ne 0 ]; then
  echo "Skill-path tests FAILED."
elif [ "$skipped" -ne 0 ]; then
  # Not a plain "passed": three of the cases need a filesystem that can make a
  # symlink, and a run that skipped them has not checked the branch this file is
  # named for. Saying so is the difference between a pass and a pass-shaped
  # silence.
  echo "Skill-path tests passed here, with $skipped case group(s) not run — see SKIP above."
else
  echo "Skill-path tests passed."
fi
exit "$fail"
